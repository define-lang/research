"""Count the functions in canonical SDDs of tree automata on balanced vtrees.

A tree automaton with states 0..m-1 has a binary operation op, a map alpha
from a leaf's bit to a state, and accepting states acc. On the complete binary
vtree of depth d over 2^d variables, it computes f(x) = [state of the root is
in acc], where the state of a leaf is alpha[x_i] and the state of an internal
node is op[left state][right state]. Every circuit of treewidth k gives such
an automaton on the vtree of its decomposition, with at most 2^(2^O(k))
states (section 5 of canonical-sdd-proof.md), though the automaton changes
from node to node; here one automaton is used at every node.

A function g over the variables below node t that appears in the canonical
SDD of f is [state of t is in S] for a set S of states reachable at t, and
different sets give different functions. The canonical SDD is computed exactly
at this level: for g = S at node t with children l and r, the sub for a left
state a is {b : op[a][b] in S}, the primes are the classes of left states with
equal subs, and g is decomposed at t unless it depends on only one child.

The script reports, for random automata, the largest number of distinct
decision nodes at one vtree node as the depth grows, and compares it with
2^(number of reachable states) - 2, the number of nonconstant sets. With
--check it also builds the truth table for depth 3 and compares the canonical
SDD size with the one computed by the canon tool.

Run from the repository root:

    uv run --frozen python circuit_treewidth_canonical_sdd/tree_automaton_functions.py
"""

from __future__ import annotations

import random
import subprocess
import tempfile
from dataclasses import dataclass, field

import click


class CheckFailedError(Exception):
    """A computed value disagreed with the canon tool."""


@dataclass
class Automaton:
    """A tree automaton: states 0..states-1, op, leaf map alpha, accepting acc."""

    states: int
    op: list[list[int]]
    alpha: tuple[int, int]
    acc: frozenset[int]


@dataclass
class Result:
    """The canonical SDD's size and its largest number of decisions at a node."""

    size: int
    max_decisions_at_a_node: int
    reachable_at_root: int
    decisions: dict[str, set[frozenset[int]]] = field(default_factory=dict)


def canonical(automaton: Automaton, depth: int) -> Result:
    """Compute the canonical SDD of the automaton on the vtree of this depth."""
    reachable = [frozenset(automaton.alpha)]
    for _ in range(depth):
        below = reachable[-1]
        reachable.append(frozenset(automaton.op[a][b] for a in below for b in below))
    visited: dict[str, set[frozenset[int]]] = {}
    decisions: dict[str, set[frozenset[int]]] = {}
    size = 0

    def process(path: str, height: int, states: frozenset[int]) -> None:
        nonlocal size
        here = reachable[height]
        states = states & here
        if not states or states == here or height == 0:
            return
        seen = visited.setdefault(path, set())
        if states in seen:
            return
        seen.add(states)
        below = reachable[height - 1]
        classes: dict[frozenset[int], set[int]] = {}
        for a in below:
            sub = frozenset(b for b in below if automaton.op[a][b] in states)
            classes.setdefault(sub, set()).add(a)
        if len(classes) == 1:
            (sub,) = classes
            process(path + "R", height - 1, sub)
            return
        if all(not sub or sub == below for sub in classes):
            process(path + "L", height - 1, frozenset(classes.get(below, set())))
            return
        decisions.setdefault(path, set()).add(states)
        size += len(classes)
        for sub, prime in classes.items():
            process(path + "L", height - 1, frozenset(prime))
            process(path + "R", height - 1, sub)

    process("", depth, automaton.acc)
    largest = max((len(v) for v in decisions.values()), default=0)
    return Result(size, largest, len(reachable[depth]), decisions)


def random_automaton(states: int, rng: random.Random) -> Automaton:
    """Return an automaton with a random operation, leaf map, and accepting set."""
    op = [[rng.randrange(states) for _ in range(states)] for _ in range(states)]
    acc = frozenset(a for a in range(states) if rng.random() < 0.5)
    alpha = (rng.randrange(states), rng.randrange(states))
    return Automaton(states, op, alpha, acc)


def evaluate(automaton: Automaton, depth: int, assignment: int) -> bool:
    """Return f(assignment), where bit i of assignment is variable i."""
    level: list[int] = [
        automaton.alpha[(assignment >> i) & 1] for i in range(1 << depth)
    ]
    while len(level) > 1:
        pairs = range(len(level) // 2)
        level = [automaton.op[level[2 * i]][level[2 * i + 1]] for i in pairs]
    return level[0] in automaton.acc


def balanced_vtree(lo: int, hi: int) -> str:
    """Return the complete binary vtree over variables lo..hi-1 in canon's syntax."""
    if hi - lo == 1:
        return str(lo)
    mid = (lo + hi) // 2
    return "(" + balanced_vtree(lo, mid) + " " + balanced_vtree(mid, hi) + ")"


def check_against_canon(canon: str, rng: random.Random, count: int) -> None:
    """Compare sizes with the canon tool on the truth tables of depth-3 automata."""
    depth = 3
    n = 1 << depth
    for _ in range(count):
        automaton = random_automaton(rng.randrange(2, 7), rng)
        values = (evaluate(automaton, depth, a) for a in range(1 << n))
        bits = "".join("1" if value else "0" for value in values)
        with tempfile.NamedTemporaryFile("w", suffix=".tt") as table:
            _ = table.write(f"{n}\n{bits}\n")
            table.flush()
            output = subprocess.run(  # noqa: S603 - runs the tool named on the command line
                [canon, "size", table.name, balanced_vtree(0, n)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.split()
        if int(output[0]) != canonical(automaton, depth).size:
            raise CheckFailedError(f"{automaton}: canon gives {output[0]}")
    print(f"check: {count} random automata of depth 3 agree with the canon tool")


@click.command()
@click.option("--max-depth", default=11, help="Largest vtree depth.")
@click.option("--trials", default=40, help="Random automata per state count.")
@click.option(
    "--check", "canon", default=None, help="Path of the canon binary to compare with."
)
def main(max_depth: int, trials: int, canon: str | None) -> None:
    """Report decision nodes per vtree node for random automata."""
    rng = random.Random(2026)  # noqa: S311 - reproducible test inputs, not secrets
    if canon is not None:
        check_against_canon(canon, rng, 200)
    click.echo(
        "states: best random automaton (by decisions at one node at the largest depth)"
    )
    click.echo(
        "  depth d, vtree with 2^d variables: most decision nodes at one vtree node"
    )
    for states in (3, 4, 5, 6, 8, 10):
        best: tuple[int, list[Result]] | None = None
        for _ in range(trials):
            automaton = random_automaton(states, rng)
            results = [canonical(automaton, d) for d in range(2, max_depth + 1)]
            score = results[-1].max_decisions_at_a_node
            if best is None or score > best[0]:
                best = (score, results)
        if best is None:
            return
        results = best[1]
        reachable = results[-1].reachable_at_root
        by_depth = [r.max_decisions_at_a_node for r in results]
        sizes = [r.size for r in results]
        click.echo(
            f"m={states} reachable={reachable} nonconstant_sets={2**reachable - 2} "
            + f"by_depth={by_depth} size_by_depth={sizes}"
        )


if __name__ == "__main__":
    main()
