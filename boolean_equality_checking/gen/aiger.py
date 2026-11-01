"""Read ASCII AIGER files written by `aig_builder`."""

from __future__ import annotations


def read_aag(path: str) -> tuple[int, list[tuple[int, int]]]:
    """Return the number of inputs and the fanins of each `and` node."""
    with open(path, encoding="ascii") as f:
        header = f.readline().split()
        num_inputs, num_ands = int(header[2]), int(header[5])
        num_outputs = int(header[4])
        for _ in range(num_inputs + num_outputs):
            f.readline()
        ands = []
        for _ in range(num_ands):
            _, a, b = (int(x) for x in f.readline().split())
            ands.append((a, b))
    return num_inputs, ands
