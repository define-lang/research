"""Independent randomized execution checks for ordinary resolved operations."""

from __future__ import annotations

import array
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from operation_graph_optimization import algorithm, graph


def check_random_schedule(
    operations: list[algorithm.Operation], calculated: graph.Graph, seed: int
):
    """Execute a randomized topological schedule with exact occupant identities."""
    required = array.array("Q")
    requirement_offsets = array.array("Q", [0])
    selected = array.array("Q")
    serial_state: dict[int, int] = {}
    for occurrence, operation in enumerate(operations):
        for position in (*operation.occupied, operation.empty):
            if position is None:
                continue
            required.append(serial_state[position])
        requirement_offsets.append(len(required))
        particle = (
            serial_state[operation.empty] if operation.empty is not None else occurrence
        )
        selected.append(particle)
        if operation.empty is not None:
            del serial_state[operation.empty]
        if operation.fill is not None:
            if operation.fill in serial_state:
                raise ValueError("The serial workload fills an occupied position")
            serial_state[operation.fill] = particle

    consumers_count = array.array("Q", [0]) * len(operations)
    remaining = array.array("Q")
    ready: list[int] = []
    for following in range(len(operations)):
        start, end = calculated.offsets[following], calculated.offsets[following + 1]
        remaining.append(end - start)
        if start == end:
            ready.append(following)
        for offset in range(start, end):
            previous = calculated.edges[offset]
            if previous >= following:
                raise ValueError("A dependency is not a preceding operation")
            consumers_count[previous] += 1
    consumer_offsets = array.array("Q", [0])
    for count in consumers_count:
        consumer_offsets.append(consumer_offsets[-1] + count)
    consumers = array.array("Q", [0]) * len(calculated.edges)
    next_consumer = consumer_offsets[:-1]
    for following in range(len(operations)):
        for offset in range(
            calculated.offsets[following], calculated.offsets[following + 1]
        ):
            previous = calculated.edges[offset]
            consumers[next_consumer[previous]] = following
            next_consumer[previous] += 1

    randomizer = random.Random(seed)  # noqa: S311 - Reproducible execution orders.
    completed = bytearray(len(operations))
    state: dict[int, int] = {}
    count = 0
    while ready:
        index = randomizer.randrange(len(ready))
        occurrence = ready[index]
        ready[index] = ready[-1]
        _ = ready.pop()
        operation = operations[occurrence]
        required_positions = operation.occupied
        if operation.empty is not None:
            required_positions = (*required_positions, operation.empty)
        for offset, position in enumerate(required_positions):
            if (
                state.get(position)
                != required[requirement_offsets[occurrence] + offset]
            ):
                raise ValueError("A scheduled operation observes the wrong particle")
        for creator in operation.creators:
            if not completed[creator]:
                raise ValueError(
                    "A scheduled operation uses a particle before its Create"
                )
        if operation.empty is not None:
            del state[operation.empty]
        if operation.fill is not None:
            if operation.fill in state:
                raise ValueError("A scheduled operation fills an occupied position")
            state[operation.fill] = selected[occurrence]
        completed[occurrence] = 1
        count += 1
        for offset in range(
            consumer_offsets[occurrence], consumer_offsets[occurrence + 1]
        ):
            following = consumers[offset]
            remaining[following] -= 1
            if remaining[following] == 0:
                ready.append(following)
    if count != len(operations) or state != serial_state:
        raise ValueError("The schedule is incomplete or has the wrong final occupancy")
