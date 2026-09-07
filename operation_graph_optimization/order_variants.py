"""Valid statement reorderings from an independent, unreduced conflict graph."""

from __future__ import annotations

import dataclasses
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from operation_graph_optimization import algorithm


def reorder(
    operations: list[algorithm.Operation],
    groups: dict[int, int],
    seed: int,
) -> tuple[list[algorithm.Operation], dict[int, int], list[int]]:
    """Randomize ready statements without using the rule algorithm's graph."""
    starts: list[int] = []
    statement_for: list[int] = []
    occurrence = 0
    while occurrence < len(operations):
        count = groups.get(occurrence, 1)
        statement_for.extend([len(starts)] * count)
        starts.append(occurrence)
        occurrence += count

    changed: dict[int, int] = {}
    used: dict[int, set[int]] = {}
    consumers: list[list[int]] = [[] for _ in starts]
    remaining: list[int] = []
    for statement, start in enumerate(starts):
        count = groups.get(start, 1)
        dependencies: set[int] = set()
        for operation in operations[start : start + count]:
            dependencies.update(
                statement_for[creator] for creator in operation.creators
            )
            for position in (*operation.occupied, operation.fill, operation.empty):
                if position is not None and position in changed:
                    dependencies.add(changed[position])
            if operation.empty is not None:
                dependencies.update(used.get(operation.empty, ()))
        remaining.append(len(dependencies))
        for dependency in dependencies:
            consumers[dependency].append(statement)
        # A simultaneous group observes one preceding state, not its peers.
        for operation in operations[start : start + count]:
            for position in operation.occupied:
                used.setdefault(position, set()).add(statement)
            for position in (operation.fill, operation.empty, *operation.defines):
                if position is not None:
                    changed[position] = statement
                    _ = used.pop(position, None)

    randomizer = random.Random(seed)  # noqa: S311 - Reproducible valid source orders.
    ready = [statement for statement, count in enumerate(remaining) if count == 0]
    ordered: list[int] = []
    reordered_groups: dict[int, int] = {}
    while ready:
        index = randomizer.randrange(len(ready))
        statement = ready[index]
        ready[index] = ready[-1]
        _ = ready.pop()
        start = starts[statement]
        count = groups.get(start, 1)
        if count > 1:
            reordered_groups[len(ordered)] = count
        ordered.extend(range(start, start + count))
        for consumer in consumers[statement]:
            remaining[consumer] -= 1
            if remaining[consumer] == 0:
                ready.append(consumer)
    if len(ordered) != len(operations):
        raise ValueError("The independent statement dependencies contain a cycle")
    new_occurrence = [0] * len(operations)
    for current, original in enumerate(ordered):
        new_occurrence[original] = current
    reordered: list[algorithm.Operation] = []
    for original in ordered:
        operation = operations[original]
        reordered.append(
            dataclasses.replace(
                operation,
                creators=tuple(
                    new_occurrence[creator] for creator in operation.creators
                ),
            )
        )
    return reordered, reordered_groups, ordered
