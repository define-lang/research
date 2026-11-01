"""How often an executed operation's values are redundant in its caller.

An executed value operation has passed every check over its own read views:
its values are distinct from each other, from the constants, and from its
views. In a caller, its read views get the caller's values, which can be
related, so its values can still be redundant from the caller's
perspective. This generates a library like `hierarchy.py`'s (without twins)
and, for every operation above the first level, tries random executions of
operations from the level below, the way the generator does, then counts:

- results that are redundant in the caller: constant, equal to an argument
  (or its `not`), equal to another of the caller's values, or equal to
  another result of the same execution;
- the executed operation's own values (including the ones that aren't
  written views) that are constant or equal to another value of the caller
  or of the execution, which is what copying the execution would find.

Arguments are drawn two ways: like the generator (any available value, a
fifth of them negated), and only from the caller's own read views, all
different.

Prints one JSON line per library.
"""

from __future__ import annotations

import json
import random

import click
import hierarchy


def evaluate(
    by_name: dict[str, hierarchy.Op], callee: hierarchy.Op, args: list[int], views: int
) -> list[int]:
    """Return the tables of all of the callee's values, over the caller's views."""
    mask = (1 << (1 << views)) - 1
    tables = [0, *args]

    def table_of(lit: int) -> int:
        t = tables[lit >> 1]
        return t ^ mask if lit & 1 else t

    for st in callee.statements:
        if st[0] == "and":
            tables.append(table_of(st[1]) & table_of(st[2]))
        else:
            inner = by_name[st[1]]
            tables.extend(hierarchy._apply(inner, [table_of(a) for a in st[3:]], views))
    return tables


def classify(
    by_name: dict[str, hierarchy.Op],
    caller: hierarchy.Op,
    callee: hierarchy.Op,
    args: list[int],
) -> dict[str, bool | int]:
    """Classify one execution's results and values in the caller."""
    views = caller.views
    mask = caller.mask()
    arg_tables = [caller.table_of(a) for a in args]
    values = evaluate(by_name, callee, arg_tables, views)
    results = [values[o >> 1] ^ (mask if o & 1 else 0) for o in callee.outputs]

    def key(t: int) -> int:
        return min(t, t ^ mask)

    arg_keys = {key(t) for t in arg_tables}
    caller_keys = {key(t) for t in caller.tables} - arg_keys - {0}
    out: dict[str, bool | int] = {
        "constant": any(key(t) == 0 for t in results),
        "equals_argument": any(key(t) in arg_keys for t in results),
        "equals_caller_value": any(key(t) in caller_keys for t in results),
        "results_equal": len({key(t) for t in results}) < len(results),
    }
    out["any"] = any(out.values())
    # The callee's own values, as copying would see them: redundant when
    # constant, equal to one of the caller's values, or equal to an earlier
    # value of the execution.
    seen = {key(t) for t in caller.tables}
    redundant = 0
    for t in values[1 + callee.views :]:
        k = key(t)
        if k in seen:
            redundant += 1
        seen.add(k)
    out["internal_values"] = len(values) - 1 - callee.views
    out["internal_redundant"] = redundant
    return out


@click.command()
@click.option("--levels", type=int, default=6)
@click.option("--views", type=int, default=10)
@click.option("--executions", type=int, default=3)
@click.option("--attempts", type=int, default=50, help="Per operation and draw.")
@click.option("--seed", type=int, default=1)
def main(levels: int, views: int, executions: int, attempts: int, seed: int) -> None:
    """Generate a library and count redundant values of random executions."""
    rng = random.Random(f"caller-{seed}-{levels}-{views}-{executions}")  # noqa: S311 - Reproducible workloads.
    ops = hierarchy.library(rng, levels, 6, views, executions, 12, twin_rate=0)
    by_name = {op.name: op for op in ops}
    by_level: dict[int, list[hierarchy.Op]] = {}
    for op in ops:
        by_level.setdefault(int(op.name[1:].split("_")[0]), []).append(op)
    totals: dict[str, dict[str, int]] = {}
    for draw in ("generator", "independent_views"):
        counts: dict[str, int] = {}
        for level in range(1, levels):
            for caller in by_level[level]:
                available = [2 * v for v in range(1, len(caller.tables))]
                for _ in range(attempts):
                    callee = rng.choice(by_level[level - 1])
                    if draw == "generator":
                        args = [
                            a ^ int(rng.random() < 0.2)
                            for a in rng.sample(available, callee.views)
                        ]
                    else:
                        args = [
                            2 * v for v in rng.sample(range(1, views + 1), callee.views)
                        ]
                    result = classify(by_name, caller, callee, args)
                    counts["executions"] = counts.get("executions", 0) + 1
                    for name, value in result.items():
                        counts[name] = counts.get(name, 0) + int(value)
        totals[draw] = counts
    print(
        json.dumps(
            {"levels": levels, "views": views, "executions": executions, **totals}
        )
    )


if __name__ == "__main__":
    main()
