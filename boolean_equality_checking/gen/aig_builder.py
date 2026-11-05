"""Build And-Inverter Graphs the way Define value operations write them.

Literals are `2 * node + complement`. Node 0 is constant false. The builder does
no structural hashing, because a program can write the same statement twice and
the methods under test have to find that.
"""

from __future__ import annotations

import array
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


@dataclass
class Planted:
    """Two literals that are equal by construction, and why."""

    a: int
    b: int
    kind: str


@dataclass
class Builder:
    """An AIG under construction, with planted equalities to look for."""

    num_inputs: int
    fanin0: array.array[int] = field(default_factory=lambda: array.array("I"))
    fanin1: array.array[int] = field(default_factory=lambda: array.array("I"))
    planted: list[Planted] = field(default_factory=list)
    outputs: list[int] = field(default_factory=list)
    # Values of every node on random input patterns, when simulation is on.
    sims: list[int] | None = None
    sim_mask: int = 0
    # After reorder_first_need: the new index of each node of the original.
    node_map: array.array[int] | None = None

    def enable_simulation(self, num_patterns: int, seed: int) -> None:
        """Simulate every node built from now on with random input patterns."""
        rng = random.Random(seed)  # noqa: S311 - Reproducible workloads.
        self.sim_mask = (1 << num_patterns) - 1
        self.sims = [0] + [
            rng.getrandbits(num_patterns) for _ in range(self.num_inputs)
        ]

    def sim(self, lit: int) -> int:
        """Return the simulated value of a literal."""
        assert self.sims is not None  # noqa: S101 - Only called with simulation on.
        value = self.sims[lit >> 1]
        return value ^ self.sim_mask if lit & 1 else value

    def truncate(self, num_ands: int) -> None:
        """Remove every `and` node after the first num_ands."""
        del self.fanin0[num_ands:]
        del self.fanin1[num_ands:]
        if self.sims is not None:
            del self.sims[1 + self.num_inputs + num_ands :]

    def input(self, index: int) -> int:
        """Return the literal of input `index`, counting from 0."""
        return 2 * (index + 1)

    def num_nodes(self) -> int:
        """Return the number of nodes, counting the constant and the inputs."""
        return 1 + self.num_inputs + len(self.fanin0)

    def and2(self, a: int, b: int) -> int:
        """Append an `and` node."""
        self.fanin0.append(a)
        self.fanin1.append(b)
        if self.sims is not None:
            self.sims.append(self.sim(a) & self.sim(b))
        return 2 * (self.num_nodes() - 1)

    def or2(self, a: int, b: int) -> int:
        """Return `a or b`, written as `not (not a and not b)`."""
        return self.and2(a ^ 1, b ^ 1) ^ 1

    def and_n(self, lits: Sequence[int]) -> int:
        """Return the `and` of the literals as a left-leaning chain."""
        result = lits[0]
        for lit in lits[1:]:
            result = self.and2(result, lit)
        return result

    def or_n(self, lits: Sequence[int]) -> int:
        """Return the `or` of the literals as a left-leaning chain."""
        return self.and_n([lit ^ 1 for lit in lits]) ^ 1

    def plant(self, a: int, b: int, kind: str) -> None:
        """Record that literals a and b are equal by construction."""
        self.planted.append(Planted(a, b, kind))

    def is_and(self, lit: int) -> bool:
        """Return whether the literal's node is an `and` node."""
        return (lit >> 1) > self.num_inputs

    def fanins(self, lit: int) -> tuple[int, int]:
        """Return the two fanin literals of an `and` node."""
        index = (lit >> 1) - self.num_inputs - 1
        return self.fanin0[index], self.fanin1[index]

    def reorder_first_need(
        self, roots: Iterable[int], *, keep_unneeded: bool = True
    ) -> Builder:
        """Return a copy in DLP 58's statement order, with literals remapped.

        Each value comes right before the statement that first needs it, with
        a statement's inputs in order, starting from the roots in order. Nodes
        no root needs come last, in their original order.
        """
        first_and = self.num_inputs + 1
        total = self.num_nodes()
        new_index = array.array("I", [0]) * total
        for node in range(first_and):
            new_index[node] = node
        placed = bytearray(total)
        order = array.array("I")

        def visit(root: int) -> None:
            stack = [root]
            while stack:
                node = stack[-1]
                if node < first_and or placed[node]:
                    stack.pop()
                    continue
                f0 = self.fanin0[node - first_and] >> 1
                f1 = self.fanin1[node - first_and] >> 1
                pending = [
                    child
                    for child in (f1, f0)
                    if child >= first_and and not placed[child]
                ]
                if pending:
                    stack.extend(pending)
                    continue
                placed[node] = 1
                order.append(node)
                stack.pop()

        for root in roots:
            visit(root >> 1)
        if keep_unneeded:
            for node in range(first_and, total):
                if not placed[node]:
                    visit(node)
        for position, node in enumerate(order):
            new_index[node] = first_and + position

        def remap(lit: int) -> int:
            return 2 * new_index[lit >> 1] + (lit & 1)

        out = Builder(self.num_inputs)
        out.node_map = new_index
        for node in order:
            out.fanin0.append(remap(self.fanin0[node - first_and]))
            out.fanin1.append(remap(self.fanin1[node - first_and]))
        out.planted = [
            Planted(remap(p.a), remap(p.b), p.kind)
            for p in self.planted
            if keep_unneeded
        ]
        out.outputs = [remap(lit) for lit in self.outputs]
        return out

    def write(self, path: str) -> None:
        """Write the graph as ASCII AIGER and its planted pairs next to it."""
        num_ands = len(self.fanin0)
        max_var = self.num_inputs + num_ands
        with open(path, "w", encoding="ascii") as out:
            out.write(
                f"aag {max_var} {self.num_inputs} 0 {len(self.outputs)} {num_ands}\n"
            )
            out.writelines(f"{2 * (i + 1)}\n" for i in range(self.num_inputs))
            out.writelines(f"{lit}\n" for lit in self.outputs)
            first = 2 * (self.num_inputs + 1)
            out.writelines(
                f"{first + 2 * k} {f0} {f1}\n"
                for k, (f0, f1) in enumerate(zip(self.fanin0, self.fanin1, strict=True))
            )
        with open(path.removesuffix(".aag") + ".planted", "w", encoding="ascii") as out:
            out.writelines(f"{p.a} {p.b} {p.kind}\n" for p in self.planted)
