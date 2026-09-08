"""Conservative early combination certificates from resolved requirements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from operation_graph_optimization import combination_algorithm

if TYPE_CHECKING:
    from operation_graph_optimization import vanish_workloads


def classify(steps: list[vanish_workloads.Step]) -> set[int]:
    """Identify particles for which ordinary occupancy does not certify combination."""
    separate: set[int] = set()
    # Most particles may never Move; tracking later Moves avoids retaining
    # every destroyed identity solely to detect retained movement.
    moved_later: set[int] = set()
    for step in reversed(steps):
        ordinary = step.ordinary_occupants
        covered = set(ordinary) if len(ordinary) > 1 else ordinary
        for particle in step.operation.creators:
            if particle not in covered:
                separate.add(particle)
        if step.vacated is not None and step.vacated in moved_later:
            separate.add(step.vacated)
        if step.moved is not None:
            moved_later.add(step.moved)
    return separate


def convert(step: vanish_workloads.Step) -> combination_algorithm.Operation:
    """Supply actual requirements without changing the position construction."""
    operation = step.operation
    return combination_algorithm.Operation(
        occupied=operation.occupied,
        fill=operation.fill,
        empty=operation.empty,
        quality_particles=operation.creators,
        defines=operation.defines,
        ordinary_occupants=step.ordinary_occupants,
        moved=step.moved,
        vacated=step.vacated,
    )
