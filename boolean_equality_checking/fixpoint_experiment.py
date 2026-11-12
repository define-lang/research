"""Whether applying DLP 59's fixes to equivalent programs reaches one program.

Generates families of value operations (`gen/fixpoint.py`): a random base
program and variants that compute the same functions written differently
(registered operations written out with `and` and `not`, De Morgan's law,
values computed twice, reassociated `and`s, distributed `and`s, or all of
them). Each program is fixed until it compiles, with matches found by the
exact definition over earlier values (`beq match --how resub`), and the
fixed programs of each family are compared. Run with `uv run --frozen
--python 3.14 python fixpoint_experiment.py`; results go to
`results/fixpoint.jsonl`.
"""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import time

import click
from experiments import (
    BEQ,
    HERE,
    MEMORY_GB,
    RESULTS,
    WORK,
    OutOfMemoryError,
    run_limited,
)

sys.path.insert(0, str(HERE / "gen"))
import fixpoint

KINDS = {
    "expand": {"expand"},
    "demorgan": {"demorgan"},
    "duplicate": {"duplicate"},
    "reassociate": {"reassociate"},
    "distribute": {"distribute"},
    "mixed": {"expand", "demorgan", "duplicate", "reassociate", "distribute"},
}
SIZES = [(8, 16), (12, 30), (16, 50)]


class Checker:
    """Finds matches with beq, under the limits, and keeps its timings."""

    def __init__(self, base: str) -> None:
        """Write the graphs it checks to BASE.*."""
        self.base = base
        self.calls = 0
        self.last_time = 0.0
        self.total_time = 0.0
        self.max_time = 0.0
        # Also list the spellings of executions, for the precedence rule,
        # with its declared order so `beq` can leave out lower-precedence
        # ones, and whether opposite spellings are left out.
        self.spellings = False
        self.order: list[str] | None = None
        self.strict = False

    def precedence_options(self) -> list[str]:
        """Return the options that give `beq` the precedence rule."""
        if not self.order:
            return []
        return [
            "--precedence",
            ",".join(self.order),
            "--precedence_strict",
            str(int(self.strict)),
        ]

    def __call__(self, p: fixpoint.Program) -> list[fixpoint.Match]:
        """Return every match `beq` finds in the program."""
        lit_to_value = fixpoint.write_aig(p, self.base)
        raw = self.base + ".raw"
        command = [
            str(BEQ),
            "match",
            self.base + ".aag",
            "--how",
            "resub",
            "--file_order",
            "1",
            "--dump_raw",
            raw,
            "--dump",
            "/dev/null",
            "--spellings",
            str(int(self.spellings)),
            *self.precedence_options(),
        ]
        record = json.loads(run_limited(command, 30, MEMORY_GB).stdout)
        if record["status"] != "ok":
            raise RuntimeError(record["status"])
        self.calls += 1
        self.last_time = record["time_s"]
        self.total_time += record["time_s"]
        self.max_time = max(self.max_time, record["time_s"])
        out = []
        with open(raw, encoding="ascii") as f:
            for line in f:
                value, op, size, *args = line.split()
                spelling = op.startswith("spell:")
                op = op.removeprefix("spell:")
                opposite = op.startswith("not:")
                out.append(
                    fixpoint.Match(
                        lit_to_value[int(value)],
                        op.removeprefix("not:"),
                        opposite,
                        int(size),
                        tuple(lit_to_value[int(a)] for a in args),
                        spelling,
                    )
                )
        return out


POLICIES = ["largest", "earliest", "smallest"]
# Two arbitrary declared orders of the registered operations, for the
# precedence rule.
ORDERS = {
    "A": ["or", "implies", "xor", "eq", "mux", "maj"],
    "B": ["maj", "mux", "eq", "xor", "implies", "or"],
}


def fix_program(
    checker: Checker,
    program: fixpoint.Program,
    policy: str,
    *,
    plain_arguments: bool = False,
    precedence: list[str] | None = None,
    strict: bool = False,
) -> tuple[dict[str, object], str | None]:
    """Fix one program; return its result row and its fixed program's text."""
    checker.calls = 0
    checker.total_time = checker.max_time = 0.0
    start = time.perf_counter()
    row: dict[str, object] = {
        "policy": policy,
        "statements_before": len(program.statements),
    }
    try:
        outcome = fixpoint.fix(
            program,
            checker,
            policy=policy,
            plain_arguments=plain_arguments,
            precedence=precedence,
            strict=strict,
        )
    except subprocess.TimeoutExpired:
        row["status"] = "timeout"
        return row, None
    except OutOfMemoryError:
        row["status"] = "out of memory"
        return row, None
    final_text = fixpoint.text(outcome.final)
    # The cost of checking the fixed program, which compiles: the best of
    # three runs.
    fixpoint.write_aig(outcome.final, checker.base)
    timed = json.loads(
        run_limited(
            [
                str(BEQ),
                "match",
                checker.base + ".aag",
                "--how",
                "resub",
                "--file_order",
                "1",
                "--repeat",
                "3",
                "--dump",
                "/dev/null",
                "--spellings",
                str(int(precedence is not None)),
                *checker.precedence_options(),
            ],
            30,
            MEMORY_GB,
        ).stdout
    )
    row.update(
        final_check_s=timed["time_s"],
        final_matches=timed["matches"],
        final_inputs=outcome.final.inputs,
        status=outcome.status,
        rounds=outcome.rounds,
        redundant_fixes=outcome.redundant_fixes,
        match_fixes=outcome.match_fixes,
        precedence_fixes=outcome.precedence_fixes,
        statements_after=len(outcome.final.statements),
        largest=max(outcome.sizes),
        final_hash=hashlib.sha256(final_text.encode()).hexdigest()[:16],
        final=final_text,
        beq_calls=checker.calls,
        check_s=checker.total_time,
        slowest_check_s=checker.max_time,
        last_check_s=checker.last_time,
        wall_s=time.perf_counter() - start,
    )
    return row, final_text


@click.command()
@click.option("--families", type=int, default=8, help="Per kind and size.")
@click.option("--variants", type=int, default=4)
@click.option(
    "--large-only",
    is_flag=True,
    help="Only fix random programs of 600 statements, for programs near DLP "
    "59's limit of 256 once they compile.",
)
@click.option(
    "--plain-arguments",
    is_flag=True,
    help="Only the families, with the candidate rule that an execution "
    "isn't given a `not` another registered operation doesn't need.",
)
@click.option(
    "--precedence",
    type=click.Choice(sorted(ORDERS)),
    help="Add the precedence rule between spellings, with this declared order.",
)
@click.option(
    "--steady-only",
    is_flag=True,
    help="Only the random programs of 256 statements.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Every fix shrinks the program, or keeps its size for precedence.",
)
def main(
    families: int,
    variants: int,
    *,
    large_only: bool,
    plain_arguments: bool,
    precedence: str | None,
    strict: bool,
    steady_only: bool,
) -> None:
    """Fix every program of every family and compare the results."""
    out = WORK / "fixpoint"
    out.mkdir(parents=True, exist_ok=True)
    checker = Checker(str(out / "program"))
    checker.spellings = precedence is not None
    order = ORDERS[precedence] if precedence else None
    checker.order = order
    checker.strict = strict
    suffix = f"|prec:{precedence}" if precedence else ""
    if strict:
        suffix += "|strict"
    with (RESULTS / "fixpoint.jsonl").open("a", encoding="utf-8") as results:

        def record(row: dict[str, object]) -> None:
            results.write(json.dumps(row) + "\n")
            results.flush()

        if large_only:
            for inputs in (12, 16, 20):
                for k in range(4):
                    rng = random.Random(f"large-{inputs}-{k}")  # noqa: S311 - Reproducible workloads.
                    base = fixpoint.base_program(rng, inputs, 600)
                    row, _ = fix_program(checker, base, "largest")
                    record(
                        {
                            "part": "large",
                            "inputs": inputs,
                            "base_statements": 600,
                            **row,
                        }
                    )
                    print("large", inputs, k, row.get("status"), flush=True)
            return

        # Programs at DLP 59's limit of 256 statements, fixed until they
        # compile, for the cost of checking a program that compiles.
        steady = not plain_arguments and (
            not precedence or (strict and precedence == "A")
        )
        for inputs in (12, 16, 20) if steady else ():
            for k in range(5):
                rng = random.Random(f"steady-{inputs}-{k}")  # noqa: S311 - Reproducible workloads.
                base = fixpoint.base_program(rng, inputs, 256)
                row, _ = fix_program(
                    checker, base, "largest", precedence=order, strict=strict
                )
                row["policy"] += suffix
                record(
                    {"part": "steady", "inputs": inputs, "base_statements": 256, **row}
                )
                print("steady", inputs, k, row.get("status"), flush=True)
        if steady_only:
            return
        policies = ["largest+plain"] if plain_arguments else POLICIES
        # Every order of fixes for the main configurations, DLP 59's for the
        # others.
        if (precedence or strict) and not (strict and precedence == "A"):
            policies = ["largest"]
        for kind, rewrites in KINDS.items():
            if plain_arguments and kind not in ("expand", "demorgan", "mixed"):
                continue
            for inputs, statements in SIZES:
                for family in range(families):
                    rng = random.Random(f"fix-{kind}-{inputs}-{statements}-{family}")  # noqa: S311 - Reproducible workloads.
                    base = fixpoint.base_program(rng, inputs, statements)
                    programs = [base]
                    attempts = 0
                    while len(programs) < variants + 1 and attempts < 50:
                        attempts += 1
                        variant = fixpoint.Rewriter(base, rng, rewrites).run()
                        if len(variant.statements) <= 256:
                            programs.append(variant)
                    for policy in policies:
                        finals = []
                        for index, program in enumerate(programs):
                            row, final = fix_program(
                                checker,
                                program,
                                policy.removesuffix("+plain"),
                                plain_arguments=plain_arguments,
                                precedence=order,
                                strict=strict,
                            )
                            row["policy"] = policy + suffix
                            finals.append(final)
                            record(
                                {
                                    "part": "families",
                                    "kind": kind,
                                    "inputs": inputs,
                                    "base_statements": statements,
                                    "family": family,
                                    "program": index,
                                    **row,
                                }
                            )
                        distinct = len({f for f in finals if f is not None})
                        print(
                            kind,
                            inputs,
                            statements,
                            family,
                            policy,
                            f"{len(programs)} programs, {distinct} distinct results",
                            flush=True,
                        )


if __name__ == "__main__":
    main()
