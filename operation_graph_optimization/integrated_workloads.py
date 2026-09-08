"""Whole-graph workloads with shared retained destructor state."""

from __future__ import annotations

import random

from operation_graph_optimization import algorithm, vanish_workloads


def retained(
    seed: int, count: int, width: int
) -> tuple[list[vanish_workloads.Step], dict[int, dict[int, int]]]:
    """Randomize valid direct Moves of selected children during destruction."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible valid choices.
    steps = [
        vanish_workloads.Step(
            algorithm.Operation(fill=0, defines=tuple(range(1, width + 1))), (), None
        )
    ]
    for child in range(1, width + 1):
        steps.append(
            vanish_workloads.Step(
                algorithm.Operation(occupied=(0,), fill=child, creators=(0,)),
                (0,),
                None,
                ordinary_occupants=(0,),
            )
        )
    aliases = {child: child + width for child in range(1, width + 1)}
    retentions = {len(steps): aliases}
    selected = list(range(width + 1))
    randomizer.shuffle(selected)
    for particle in selected:
        steps.append(
            vanish_workloads.Step(algorithm.Operation(empty=particle), (), particle)
        )
    steps.append(vanish_workloads.Step(algorithm.Operation(fill=0), (), None))
    moved: set[int] = set()
    for _ in range(count):
        child = randomizer.randrange(1, width + 1)
        retained_position = child + width
        temporary = child + 2 * width
        if child in moved:
            source, destination = temporary, retained_position
            moved.remove(child)
        else:
            source, destination = retained_position, temporary
            moved.add(child)
        steps.append(
            vanish_workloads.Step(
                algorithm.Operation(empty=source, fill=destination, creators=(0,)),
                (0, child),
                None,
                child,
            )
        )
    for child in sorted(moved):
        steps.append(
            vanish_workloads.Step(
                algorithm.Operation(
                    empty=child + 2 * width, fill=child + width, creators=(0,)
                ),
                (0, child),
                None,
                child,
            )
        )
    return steps, retentions
