"""Time CaDiCaL on the miter of each planted pair, as an independent solver.

Run with `uv run --no-project --python 3.13 --with python-sat --with click
python cadical_miter.py FILE.aag`. Prints one JSON line per pair as soon as it
is decided. Only the cones of the two literals are encoded. python-sat can't
interrupt CaDiCaL, so time limits are applied from outside, per file.
"""

from __future__ import annotations

import json
import time

import click
from aiger import read_aag
from pysat.solvers import Solver


@click.command()
@click.argument("aag")
@click.option(
    "--limit",
    type=int,
    default=0,
    help="Check only the first N planted pairs; 0 checks all.",
)
def main(aag: str, limit: int) -> None:
    """Check every planted pair of AAG with a fresh CaDiCaL per pair."""
    num_inputs, ands = read_aag(aag)
    with open(aag.removesuffix(".aag") + ".planted", encoding="ascii") as f:
        pairs = [line.split() for line in f]
    if limit:
        pairs = pairs[:limit]
    for a_text, b_text, kind in pairs:
        a, b = int(a_text), int(b_text)
        solver = Solver(name="cadical195")
        solver.add_clause([-1])
        cone: set[int] = set()
        stack = [a >> 1, b >> 1]
        while stack:
            n = stack.pop()
            if n in cone or n <= num_inputs:
                continue
            cone.add(n)
            fa, fb = ands[n - num_inputs - 1]
            stack.extend((fa >> 1, fb >> 1))

        def lit(x: int) -> int:
            v = (x >> 1) + 1
            return -v if x & 1 else v

        for n in sorted(cone):
            fa, fb = ands[n - num_inputs - 1]
            z = n + 1
            solver.add_clause([-z, lit(fa)])
            solver.add_clause([-z, lit(fb)])
            solver.add_clause([z, -lit(fa), -lit(fb)])
        start = time.perf_counter()
        results = []
        for assumptions in ([lit(a), -lit(b)], [-lit(a), lit(b)]):
            results.append(solver.solve(assumptions=assumptions))
            if results[-1]:
                break
        elapsed = time.perf_counter() - start
        status = "different" if any(results) else "equal"
        stats = solver.accum_stats()
        print(
            json.dumps(
                {
                    "file": aag,
                    "a": a,
                    "b": b,
                    "kind": kind,
                    "status": status,
                    "time_s": elapsed,
                    "cone_ands": len(cone),
                    "conflicts": stats.get("conflicts", 0),
                }
            ),
            flush=True,
        )
        solver.delete()


if __name__ == "__main__":
    main()
