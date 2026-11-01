"""Compile one AIGER file into SDDs with pysdd and print one JSON line.

Run with `uv run --no-project --python 3.13 --with pysdd --with click python
sdd_compile.py FILE.aag VTREE`, where VTREE is `right` (a right-linear vtree
in first-use order, which makes the SDD an OBDD), `balanced` (a balanced vtree
over the same order), or `dynamic` (balanced, with pysdd's automatic garbage
collection and vtree minimization). Every node's SDD is kept referenced, so
the reported size is the shared size of all of them. Canonical SDDs make two
nodes equal exactly when their SDDs are the same node, which is checked
against `--dump` output from `beq` when `--compare` is given.
"""

from __future__ import annotations

import json
import resource
import time

import click
from aiger import read_aag
from pysdd.sdd import SddManager, Vtree


def first_use_order(num_inputs: int, ands: list[tuple[int, int]]) -> list[int]:
    """Return the inputs (1-based) in order of first use, unused ones last."""
    order: list[int] = []
    seen = set()
    for a, b in ands:
        for lit in (a, b):
            node = lit >> 1
            if 1 <= node <= num_inputs and node not in seen:
                seen.add(node)
                order.append(node)
    order.extend(i for i in range(1, num_inputs + 1) if i not in seen)
    return order


@click.command()
@click.argument("aag")
@click.argument("vtree_kind", type=click.Choice(["right", "balanced", "dynamic"]))
@click.option(
    "--compare", default="", help="A beq --dump file to check the classes against."
)
def main(aag: str, vtree_kind: str, compare: str) -> None:
    """Compile every node and report size, time, memory, and classes."""
    num_inputs, ands = read_aag(aag)
    base_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    start = time.perf_counter()
    order = first_use_order(num_inputs, ands)
    vtree = Vtree(
        var_count=num_inputs,
        var_order=order,
        vtree_type="balanced" if vtree_kind != "right" else "right",
    )
    manager = SddManager.from_vtree(vtree)
    if vtree_kind == "dynamic":
        manager.auto_gc_and_minimize_on()
    nodes = [manager.false()] + [manager.literal(i) for i in range(1, num_inputs + 1)]
    for node in nodes:
        node.ref()

    def lit(x: int):
        node = nodes[x >> 1]
        return manager.negate(node) if x & 1 else node

    for a, b in ands:
        node = manager.conjoin(lit(a), lit(b))
        node.ref()
        nodes.append(node)
    elapsed = time.perf_counter() - start
    # Classes modulo complement: a node and its negation have different ids.
    first: dict[int, tuple[int, bool]] = {}
    rep = []
    for v, node in enumerate(nodes):
        neg = manager.negate(node)
        key, phase = (node.id, False) if node.id < neg.id else (neg.id, True)
        r, p = first.setdefault(key, (v, phase))
        rep.append(2 * r + (p ^ phase))
    agrees = None
    if compare:
        with open(compare, encoding="ascii") as f:
            agrees = rep == [int(line) for line in f]
    print(
        json.dumps(
            {
                "file": aag,
                "vtree": vtree_kind,
                "time_s": elapsed,
                "live_size": manager.live_size(),
                "live_count": manager.live_count(),
                "rss_increase_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                - base_kb,
                "redundant": sum(1 for v, r in enumerate(rep) if r >> 1 != v),
                "agrees_with_beq": agrees,
            }
        )
    )


if __name__ == "__main__":
    main()
