"""Check the termination measure against the Python fix loop.

Runs `gen/fixpoint.py`'s fix loop, with DLP 59's rules (precedence with the
restriction that no fix grows the program), on the families of
`fixpoint_experiment.py`, and checks after every fix that the measure of
termination.md went down: the number of statements, then the multiset of
the executions' (negations, AIG nodes, declared order), then the multiset
of the values' ranks. Prints how many fixes of each kind there were and how
many didn't decrease the measure. Run with `uv run --frozen --python 3.14
python proof/measure_check.py` from the study's directory.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "gen"))
import fixpoint
import fixpoint_experiment as fe


def multiset_less(smaller: Counter, larger: Counter) -> bool:
    """Return whether `smaller` is below `larger` in the multiset order.

    Dershowitz and Manna: they differ, and every element that `smaller` has
    more of is below some element that `larger` has more of.
    """
    if smaller == larger:
        return False
    gained = [x for x in smaller if smaller[x] > larger[x]]
    lost = [y for y in larger if larger[y] > smaller[y]]
    return all(any(x < y for y in lost) for x in gained)


def measure(p: fixpoint.Program, order: list[str]) -> tuple[int, Counter, Counter]:
    """Return the measure of termination.md for a canonical program."""
    keys = fixpoint.rank_keys(p)
    triples: Counter = Counter()
    for op, args in p.statements:
        if op in fixpoint.REGISTERED:
            negations = sum(
                1
                for a in args
                if a >= p.inputs and p.statements[a - p.inputs][0] == "not"
            )
            triples[(negations, fixpoint.AIG_NODES[op], order.index(op))] += 1
    ranks = Counter(keys[p.inputs :])
    return len(p.statements), triples, ranks


def decreased(before: tuple, after: tuple) -> bool:
    """Return whether the measure went down, comparing in order."""
    if after[0] != before[0]:
        return after[0] < before[0]
    if after[1] != before[1]:
        return multiset_less(after[1], before[1])
    return multiset_less(after[2], before[2])


def main() -> None:
    """Fix every program and check the measure at every fix."""
    checker = fe.Checker(str(fe.WORK / "fixpoint" / "measure"))
    checker.spellings = True
    checker.strict = True
    fixes: Counter = Counter()
    failures: Counter = Counter()
    examples: dict[str, str] = {}
    statuses: Counter = Counter()
    for name, order in fe.ORDERS.items():
        checker.order = order

        def observe(
            before: fixpoint.Program,
            after: fixpoint.Program,
            kind: str,
            order: list[str] = order,
        ) -> None:
            fixes[kind] += 1
            if not decreased(measure(before, order), measure(after, order)):
                failures[kind] += 1
                examples.setdefault(
                    kind, fixpoint.text(before) + "\n=>\n" + fixpoint.text(after)
                )

        for kind, rewrites in fe.KINDS.items():
            for inputs, statements in fe.SIZES:
                for family in range(8):
                    rng = random.Random(f"fix-{kind}-{inputs}-{statements}-{family}")  # noqa: S311 - The experiment's workloads.
                    base = fixpoint.base_program(rng, inputs, statements)
                    programs = [base]
                    attempts = 0
                    while len(programs) < 5 and attempts < 50:
                        attempts += 1
                        variant = fixpoint.Rewriter(base, rng, rewrites).run()
                        if len(variant.statements) <= 256:
                            programs.append(variant)
                    for program in programs:
                        outcome = fixpoint.fix(
                            program,
                            checker,
                            precedence=order,
                            strict=True,
                            observe=observe,
                        )
                        statuses[(name, outcome.status)] += 1
    print(json.dumps({"fixes": fixes, "not_decreasing": failures}))
    print(json.dumps({str(k): v for k, v in statuses.items()}))
    for kind, text in examples.items():
        print(f"--- {kind}\n{text}")


if __name__ == "__main__":
    main()
