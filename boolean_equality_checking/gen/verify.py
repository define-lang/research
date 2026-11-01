"""Check a method's classes independently with CaDiCaL.

Run with `uv run --with python-sat --with click python verify.py FILE.aag DUMP`,
where DUMP is the `--dump` output of `beq`. Every claimed equality is proved
with CaDiCaL (soundness). Every pair of distinct classes that agree on 4096
random patterns is proved different (completeness for every pair that random
simulation can't separate, which is where a missed equality would hide).
"""

from __future__ import annotations

import random
import sys

import click
from aiger import read_aag
from pysat.solvers import Solver


@click.command()
@click.argument("aag")
@click.argument("dump")
@click.option("--patterns", type=int, default=4096)
def main(aag: str, dump: str, patterns: int) -> None:
    """Verify the classes in DUMP for the graph in AAG."""
    num_inputs, ands = read_aag(aag)
    with open(dump, encoding="ascii") as f:
        rep = [int(line) for line in f]
    num_nodes = 1 + num_inputs + len(ands)
    if len(rep) != num_nodes:
        raise click.ClickException(f"{dump} has {len(rep)} lines for {num_nodes} nodes")

    solver = Solver(name="cadical195")
    # Variable of node n is n + 1; node 0 is false.
    solver.add_clause([-1])

    def lit(x: int) -> int:
        v = (x >> 1) + 1
        return -v if x & 1 else v

    for k, (a, b) in enumerate(ands):
        z = num_inputs + 2 + k
        solver.add_clause([-z, lit(a)])
        solver.add_clause([-z, lit(b)])
        solver.add_clause([z, -lit(a), -lit(b)])

    def equal(x: int, y: int) -> bool:
        return not solver.solve(assumptions=[lit(x), -lit(y)]) and not solver.solve(
            assumptions=[-lit(x), lit(y)]
        )

    unsound = 0
    for v in range(num_nodes):
        if rep[v] != 2 * v and not equal(2 * v, rep[v]):
            unsound += 1
            print(f"unsound: node {v} is not equal to {rep[v]}")

    rng = random.Random(7)  # noqa: S311 - Reproducible patterns.
    mask = (1 << patterns) - 1
    sim = [0] + [rng.getrandbits(patterns) for _ in range(num_inputs)]
    for a, b in ands:
        sa = sim[a >> 1] ^ (mask if a & 1 else 0)
        sb = sim[b >> 1] ^ (mask if b & 1 else 0)
        sim.append(sa & sb)
    groups: dict[int, list[int]] = {}
    for v in range(num_nodes):
        if rep[v] == 2 * v:
            s = sim[v] ^ (mask if sim[v] & 1 else 0)
            groups.setdefault(s, []).append(v)
    incomplete = 0
    checked = 0
    for members in groups.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                u, v = members[i], members[j]
                phase = (sim[u] ^ sim[v]) & 1
                checked += 1
                if equal(2 * u, 2 * v + phase):
                    incomplete += 1
                    print(f"incomplete: nodes {u} and {v} are equal")
    print(
        f"nodes={num_nodes} unsound={unsound} incomplete={incomplete} unseparated_pairs_checked={checked}"
    )
    sys.exit(1 if unsound or incomplete else 0)


if __name__ == "__main__":
    main()
