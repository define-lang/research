"""Resolve lifetime inputs independently of dependency calculation."""

from __future__ import annotations

import dataclasses
import random

from operation_graph_optimization import (
    algorithm,
    order_variants,
    state_workloads,
    workloads,
)


@dataclasses.dataclass(slots=True)
class Step:
    """Position requirements and the original particles actually required."""

    operation: algorithm.Operation
    particles: tuple[int, ...]
    vacated: int | None
    moved: int | None = None
    ordinary_occupants: tuple[int, ...] = ()


def resolve(operations: list[algorithm.Operation]) -> list[Step]:
    """Track selected identities without consulting calculated dependencies."""
    occupied: dict[int, int] = {}
    result: list[Step] = []
    for occurrence, operation in enumerate(operations):
        required = set(operation.creators)
        observed = tuple(occupied[position] for position in operation.occupied)
        vacated = None
        moved = None
        if operation.empty is not None:
            particle = occupied.pop(operation.empty)
            if operation.fill is None:
                vacated = particle
            else:
                occupied[operation.fill] = particle
                required.add(particle)
                moved = particle
        elif operation.fill is not None:
            occupied[operation.fill] = occurrence
        result.append(Step(operation, tuple(required), vacated, moved, observed))
    return result


def independent_uses(seed: int, steps: int, width: int) -> list[algorithm.Operation]:
    """Interleave constructor accesses to distinct implied child positions."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible experiments.
    operations = [algorithm.Operation(fill=0, defines=tuple(range(1, width + 1)))]
    occupied: set[int] = set()
    for _ in range(steps):
        position = randomizer.randrange(1, width + 1)
        if position in occupied:
            operations.append(algorithm.Operation(empty=position, creators=(0,)))
            occupied.remove(position)
        else:
            operations.append(algorithm.Operation(fill=position, creators=(0,)))
            occupied.add(position)
    # Automatic destruction selects remaining children without written references.
    positions = [0, *sorted(occupied)]
    randomizer.shuffle(positions)
    operations.extend(algorithm.Operation(empty=position) for position in positions)
    return operations


def generate(family: str, seed: int, steps: int, width: int) -> list[Step]:
    """Prepare complete inputs before timing either graph construction phase."""
    groups: dict[int, int] = {}
    if family == "wide":
        operations = independent_uses(seed, steps, width)
    elif family == "implied":
        operations = list(workloads.implied_uses(seed, steps, width))
    elif family == "movement":
        operations = list(workloads.overlapping_moves(seed, steps, width))
    elif family == "written":
        operations = list(workloads.preceding_uses(seed, steps, width))
    elif family == "local":
        operations = workloads.random_program(seed, steps, width).operations
    else:
        operations, groups = state_workloads.generate(
            seed,
            steps,
            width=width,
            depth=6,
            branching=2,
            distribution="growth"
            if family in {"growth", "growth_closed"}
            else "balanced",
        )
    if family == "growth_closed":
        occupied: set[int] = set()
        for operation in operations:
            if operation.empty is not None:
                occupied.remove(operation.empty)
            if operation.fill is not None:
                occupied.add(operation.fill)
        positions = sorted(occupied)
        random.Random(seed + 211).shuffle(positions)  # noqa: S311 - Reproducible selection order.
        groups[len(operations)] = len(positions)
        operations.extend(algorithm.Operation(empty=position) for position in positions)
    reordered, _, _ = order_variants.reorder(operations, groups, seed + 101)
    return resolve(reordered)
