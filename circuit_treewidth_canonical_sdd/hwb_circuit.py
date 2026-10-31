"""A circuit of pathwidth O(log n) for the hidden weighted bit function.

HWB_n(x_1, ..., x_n) is x_w, where w = x_1 + ... + x_n, and 0 when w = 0.

The circuit has fan-in at most 2 and only AND, OR, and NOT gates, with one
input vertex per variable. It is the circuit that hwb_circuit_pathwidth.lean
formalizes, with the same vertex names and the same intervals. This script
evaluates it against the definition of HWB_n and checks that the intervals form
a path decomposition of its graph, measuring the width.

Run from the repository root:

    uv run --frozen python circuit_treewidth_canonical_sdd/hwb_circuit.py
"""

from __future__ import annotations

import itertools
import random

Vertex = tuple[str, ...] | tuple[str, int] | tuple[str, int, int]


class CheckFailedError(Exception):
    """A property that the proof claims was found to be false."""


def check(condition: bool, message: str) -> None:  # noqa: FBT001 - a predicate
    """Raise CheckFailedError with the message unless the condition holds."""
    if not condition:
        raise CheckFailedError(message)


def hwb(x: list[bool]) -> bool:
    """Return HWB_n(x): the bit at the position given by the weight of x."""
    weight = sum(x)
    return weight > 0 and x[weight - 1]


class HwbCircuit:
    """The circuit of Theorem 3.1 for HWB_n, with its path decomposition."""

    def __init__(self, n: int) -> None:
        """Build the circuit for n inputs with L = the bit length of n."""
        self.n: int = n
        self.bits: int = max(1, n.bit_length())
        # gate[v] = (op, inputs); input vertices have op "input".
        self.gate: dict[Vertex, tuple[str, list[Vertex]]] = {}
        # interval[v] = (lo, hi): the bags (steps 1..n) that contain v.
        self.interval: dict[Vertex, tuple[int, int]] = {}
        self._build()

    def cnt(self, i: int, j: int) -> Vertex:
        """Return bit j of the count after i inputs; the count after none is zero."""
        return ("zero",) if i == 0 else ("cnt", i, j)

    def carry(self, i: int, j: int) -> Vertex:
        """Return the carry into bit j of step i; the carry into bit 0 is x_i."""
        return ("inp", i) if j == 0 else ("carry", i, j)

    def lit(self, i: int, j: int) -> Vertex:
        """Return the literal that is true when bit j of the final count equals i's."""
        return ("cnt", self.n, j) if (i >> j) & 1 else ("nw", j)

    def eq(self, i: int, j: int) -> Vertex:
        """Return the gate that is true when bits 0..j of the final count equal i's."""
        return self.lit(i, 0) if j == 0 else ("e", i, j)

    def out(self, i: int) -> Vertex:
        """Return the disjunction of t(1), ..., t(i); for i = 0 it is zero."""
        return ("zero",) if i == 0 else ("o", i)

    def _add(self, v: Vertex, op: str, inputs: list[Vertex], lo: int, hi: int) -> None:
        self.gate[v] = (op, inputs)
        self.interval[v] = (lo, hi)

    def _build(self) -> None:
        n, bits = self.n, self.bits
        for i in range(1, n + 1):
            self._add(("inp", i), "input", [], i, i)
        self._add(("nx0",), "not", [("inp", 1)], 1, 1)
        self._add(("zero",), "and", [("inp", 1), ("nx0",)], 1, 1)
        for i in range(1, n + 1):
            for j in range(bits):
                a, c = self.cnt(i - 1, j), self.carry(i, j)
                self._add(("carry", i, j + 1), "and", [a, c], i, i)
                self._add(("or", i, j), "or", [a, c], i, i)
                self._add(("nand", i, j), "not", [("carry", i, j + 1)], i, i)
                lo, hi = (1, n) if i == n else (i, i + 1)
                self._add(("cnt", i, j), "and", [("or", i, j), ("nand", i, j)], lo, hi)
        for j in range(bits):
            self._add(("nw", j), "not", [("cnt", n, j)], 1, n)
        for i in range(1, n + 1):
            for j in range(1, bits):
                self._add(("e", i, j), "and", [self.eq(i, j - 1), self.lit(i, j)], i, i)
            self._add(("t", i), "and", [("inp", i), self.eq(i, bits - 1)], i, i)
            hi = n if i == n else i + 1
            self._add(("o", i), "or", [self.out(i - 1), ("t", i)], i, hi)

    def evaluate(self, x: list[bool]) -> bool:
        """Return the value of the output o(n) on input x, in topological order."""
        value: dict[Vertex, bool] = {}
        for v, (op, inputs) in self.gate.items():
            if op == "input":
                value[v] = x[int(v[1]) - 1]
            elif op == "not":
                value[v] = not value[inputs[0]]
            elif op == "and":
                value[v] = value[inputs[0]] and value[inputs[1]]
            else:
                value[v] = value[inputs[0]] or value[inputs[1]]
        return value[self.out(self.n)]

    def check_decomposition(self) -> int:
        """Check that the intervals form a path decomposition; return its width."""
        for v, (op, inputs) in self.gate.items():
            lo, hi = self.interval[v]
            check(1 <= lo <= hi <= self.n, f"bad interval for {v}")
            check(op == "input" or 1 <= len(inputs) <= 2, f"bad fan-in for {v}")
            for u in inputs:
                ulo, uhi = self.interval[u]
                check(max(lo, ulo) <= min(hi, uhi), f"wire {u} -> {v} is in no bag")
        bag_sizes = [0] * (self.n + 1)
        for lo, hi in self.interval.values():
            for p in range(lo, hi + 1):
                bag_sizes[p] += 1
        return max(bag_sizes) - 1


def main() -> None:
    """Check the circuit for a range of n and print the widths."""
    rng = random.Random(1)  # noqa: S311 - reproducible test inputs, not secrets
    print("n bits vertices width bound_8L+5")
    for n in [*range(1, 17), 32, 64, 128, 256, 1024]:
        circuit = HwbCircuit(n)
        width = circuit.check_decomposition()
        bound = 8 * circuit.bits + 5
        check(width <= bound, f"width {width} exceeds {bound}")
        if n <= 14:
            inputs = (list(x) for x in itertools.product([False, True], repeat=n))
        else:
            inputs = ([rng.random() < 0.5 for _ in range(n)] for _ in range(2000))
        for x in inputs:
            check(circuit.evaluate(x) == hwb(x), f"wrong value on {x}")
        print(n, circuit.bits, len(circuit.gate), width, bound)
    print("all checks passed (exhaustive for n <= 14, 2000 random inputs above)")


if __name__ == "__main__":
    main()
