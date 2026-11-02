"""The full algorithm on whole programs that follow DLPs 57-59.

Each program (`gen/program.py`) is generated as a programmer might first
write it, then fixed until it compiles (`beq program --mode fix`), which is
also the measurement of the fix loop on programs that don't compile yet.
The fixed program is checked by an independent implementation of every
rule (`gen/program_check.py`) on a sample of its operations, then timed
with every check at once (`beq program --mode check`): from nothing,
storing patterns; again unchanged with the stored patterns; after random
edits, checking again only what each edit affects; and after edits to
booleans.defcl, which check every operation's matches and spellings again.

This is a study of whole large programs, so its runs may take longer than
30 seconds, within the limits below. Run with `uv run --frozen --python
3.14 python full_algorithm_experiment.py`; results go to
`results/full_algorithm.jsonl`.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time

import click
from experiments import BEQ, HERE, RESULTS, WORK, OutOfMemoryError, run_limited

# Name, generator options.
PROGRAMS = [
    ("ops_15k", ["levels=12", "boolean_per_level=1000", "mixed_per_level=250"]),
    ("ops_150k", ["levels=12", "boolean_per_level=10000", "mixed_per_level=2500"]),
    (
        "ops_2k_wide",
        [
            "levels=5",
            "boolean_per_level=320",
            "mixed_per_level=80",
            "views=16,20",
            "statements=30,80",
            "comparisons=10,17",
            "mixed_statements=20,60",
        ],
    ),
]
# Caps, in seconds: every compiler step at 150k operations should take
# tens of seconds, so one that reaches its cap is a finding, recorded as a
# timeout. The fix loop and the tooling (generating, and the independent
# checker) get more.
STEP_SECONDS = 60
FIX_SECONDS = 300
TOOL_SECONDS = 120
MEMORY_GB = 4
TOOL_MEMORY_GB = 8
# Operations the independent checker samples, with what they execute. It
# handles at most 12 boolean inputs per operation in reasonable time, so
# the wide program isn't sampled.
SAMPLE = 300
CLOSURE = 1200


def beq(args: list[str], seconds: float = STEP_SECONDS) -> list[dict]:
    """Run `beq program` under the limits; return its JSON lines."""
    done = run_limited(
        [str(BEQ), "program", *args], seconds, MEMORY_GB, long_study=True
    )
    return [json.loads(line) for line in done.stdout.splitlines()]


def blocks_of(text: str) -> tuple[list[str], dict[str, list[str]]]:
    """Return a program's operation names in order, and each one's lines."""
    blocks: dict[str, list[str]] = {}
    order: list[str] = []
    current: list[str] = []
    for line in text.splitlines()[1:]:
        current.append(line)
        if line == "end":
            name = current[0].split()[1]
            blocks[name] = current
            order.append(name)
            current = []
    return order, blocks


def add_closure(name: str, blocks: dict[str, list[str]], needed: set[str]) -> set[str]:
    """Return what `name` and everything it executes add to `needed`."""
    added: set[str] = set()
    stack = [name]
    while stack:
        current = stack.pop()
        if current in needed or current in added:
            continue
        added.add(current)
        for line in blocks[current]:
            words = line.split()
            if words[0] in ("call", "run"):
                stack.append(words[1])
    return added


def sample_program(text: str, rng: random.Random) -> tuple[str, dict[str, int], int]:
    """Return a sample of the program, the operations chosen by level, and how many were skipped.

    Up to SAMPLE operations, in random order, each with everything it
    executes, while those stay within CLOSURE operations: the independent
    checker's time is about linear in the operations it checks, and the
    deeper levels of a large program execute many.
    """
    order, blocks = blocks_of(text)
    registered = text.splitlines()[0].split()[1:]
    needed: set[str] = set()
    for name in registered:
        needed |= add_closure(name, blocks, needed)
    chosen: dict[str, int] = {}
    skipped = 0
    names = list(order)
    rng.shuffle(names)
    for name in names:
        if sum(chosen.values()) == SAMPLE:
            break
        added = add_closure(name, blocks, needed)
        if len(needed) + len(added) > CLOSURE:
            skipped += 1
            continue
        needed |= added
        level = name.split("_")[0]
        chosen[level] = chosen.get(level, 0) + 1
    out = [text.splitlines()[0]]
    for name in order:
        if name in needed:
            out.extend(blocks[name])
    return "\n".join(out) + "\n", chosen, skipped


def verify(compiled: str, rng: random.Random) -> dict[str, object]:
    """Check a sample of the operations with the independent checker."""
    text = (WORK / "full_algorithm" / compiled).read_text()
    sub, chosen, skipped = sample_program(text, rng)
    path = WORK / "full_algorithm" / ("sample_" + compiled)
    path.write_text(sub)
    start = time.perf_counter()
    done = run_limited(
        [sys.executable, str(HERE / "gen" / "program_check.py"), str(path)],
        TOOL_SECONDS,
        TOOL_MEMORY_GB,
        long_study=True,
    )
    results = [json.loads(line) for line in done.stdout.splitlines()]
    elapsed = time.perf_counter() - start
    failing = [r for r in results if r["errors"]]
    checked = beq([str(path), "--mode", "check", "--how", "tt"])[-1]
    return {
        "status": "ok",
        "sampled": sum(chosen.values()),
        "sampled_by_level": chosen,
        "skipped": skipped,
        "checked_with_dependencies": len(results),
        "independent_failing": len(failing),
        "independent_examples": failing[:5],
        "beq_failing": checked["ops_with_errors"],
        "independent_s": elapsed,
    }


@click.command()
@click.option("--only", default="", help="Run only this program.")
@click.option(
    "--steps",
    default="",
    help="Comma-separated steps to run on an existing program; by default "
    "the program is generated and every step runs.",
)
def main(only: str, steps: str) -> None:
    """Generate, fix, verify, and time each program."""
    out = WORK / "full_algorithm"
    out.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "full_algorithm.jsonl").open("a", encoding="utf-8") as results:

        def record(row: dict[str, object]) -> None:
            results.write(json.dumps(row) + "\n")
            results.flush()
            print(json.dumps(row)[:400], flush=True)

        for name, options in PROGRAMS:
            if only and name != only:
                continue
            raw = out / f"{name}_raw.prog"
            compiled = out / f"{name}.prog"
            patterns = out / f"{name}.patterns"
            hashes = out / f"{name}.hashes"
            if not steps:
                start = time.perf_counter()
                run_limited(
                    [
                        sys.executable,
                        str(HERE / "gen" / "program.py"),
                        str(raw),
                        "1",
                        *options,
                    ],
                    TOOL_SECONDS,
                    TOOL_MEMORY_GB,
                    long_study=True,
                )
                record(
                    {
                        "program": name,
                        "run": "generate",
                        "wall_s": time.perf_counter() - start,
                        "bytes": raw.stat().st_size,
                    }
                )
            runs = [
                ("fix", [str(raw), "--mode", "fix", "--out", str(compiled)]),
                ("verify", None),
                (
                    "first",
                    [
                        str(compiled),
                        "--mode",
                        "check",
                        "--patterns_out",
                        str(patterns),
                        "--slowest",
                        "20",
                    ],
                ),
                # Checking again with incremental rechecking: every
                # operation's text is unchanged, so only hashes are compared.
                (
                    "hash",
                    [str(compiled), "--mode", "unchanged", "--hashes_out", str(hashes)],
                ),
                (
                    "unchanged_incremental",
                    [str(compiled), "--mode", "unchanged", "--hashes_in", str(hashes)],
                ),
                (
                    "edits",
                    [
                        str(compiled),
                        "--mode",
                        "edits",
                        "--edits",
                        "200",
                        "--patterns_in",
                        str(patterns),
                    ],
                ),
                (
                    "registry",
                    [
                        str(compiled),
                        "--mode",
                        "registry",
                        "--slowest",
                        "5",
                        "--patterns_in",
                        str(patterns),
                    ],
                ),
            ]
            if not steps or "fix" in steps.split(","):
                # The other steps check what this run's fix wrote, never an
                # earlier run's.
                compiled.unlink(missing_ok=True)
            for run, args in runs:
                if steps and run not in steps.split(","):
                    continue
                if run != "fix" and not compiled.exists():
                    break
                try:
                    if run == "verify" and name.endswith("wide"):
                        continue
                    if run == "verify":
                        sample_rng = random.Random(name)  # noqa: S311 - A reproducible sample.
                        record(
                            {
                                "program": name,
                                "run": run,
                                **verify(compiled.name, sample_rng),
                            }
                        )
                        continue
                    if run == "registry":
                        # Register a user operation of three views that many
                        # operations execute.
                        text = compiled.read_text()
                        calls: dict[str, int] = {}
                        views: dict[str, int] = {}
                        for line in text.splitlines():
                            words = line.split()
                            if words[0] == "op" and words[2] == "bool":
                                views[words[1]] = int(words[3])
                            elif words[0] == "call":
                                calls[words[1]] = calls.get(words[1], 0) + 1
                        candidates = [
                            n
                            for n, v in views.items()
                            if 2 <= v <= 4 and n.startswith("b")
                        ]
                        # A program whose operations all read more views
                        # than a registered operation may only reorders
                        # booleans.defcl.
                        if candidates:
                            chosen = max(
                                candidates,
                                key=lambda n: (views[n] == 3, calls.get(n, 0)),
                            )
                            args = [*args, "--register", chosen]
                    start = time.perf_counter()
                    rows = beq(args, FIX_SECONDS if run == "fix" else STEP_SECONDS)
                    wall = time.perf_counter() - start
                except subprocess.TimeoutExpired:
                    record({"program": name, "run": run, "status": "timeout"})
                    continue
                except OutOfMemoryError:
                    record({"program": name, "run": run, "status": "out of memory"})
                    continue
                if run == "edits":
                    edits = rows[:-1]
                    record(
                        {
                            "program": name,
                            "run": run,
                            "status": "ok",
                            "wall_s": wall,
                            **rows[-1],
                            "edit_rows": edits,
                        }
                    )
                elif run == "registry":
                    for row in rows:
                        record(
                            {
                                "program": name,
                                "run": run,
                                "status": "ok",
                                "wall_s": wall,
                                **row,
                            }
                        )
                else:
                    record(
                        {
                            "program": name,
                            "run": run,
                            "status": "ok",
                            "wall_s": wall,
                            **rows[-1],
                        }
                    )


if __name__ == "__main__":
    main()
