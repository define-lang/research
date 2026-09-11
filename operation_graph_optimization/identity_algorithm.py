"""Occupancy, lifetime, and relationship collection on resolved identities."""

from __future__ import annotations

import array
import dataclasses

from operation_graph_optimization import relationship_periods
from operation_graph_optimization.complete import algorithm, graph


@dataclasses.dataclass(frozen=True, slots=True)
class Operation:
    """A resolved Particle Operation on one selected particle."""

    name: str
    particle: int


@dataclasses.dataclass(frozen=True, slots=True)
class Create(Operation):
    """Creation of a fresh particle at an identified target position."""

    target: int


@dataclasses.dataclass(frozen=True, slots=True)
class Move(Operation):
    """Direct movement between identified source and target positions."""

    source: int
    target: int


@dataclasses.dataclass(frozen=True, slots=True)
class Vacate(Operation):
    """A selected ordinary vacancy belonging to one simultaneous destruction."""

    position: int
    destruction: int


@dataclasses.dataclass(frozen=True, slots=True)
class Vanish(Operation):
    """The end of the selected particle's existence."""


@dataclasses.dataclass(slots=True)
class Construction:
    """Ordinary dependencies and the collected parent relationship periods."""

    operations: list[Operation]
    dependencies: graph.Graph
    periods: list[list[relationship_periods.Period]]


def construct(operations: list[Operation], parents: tuple[int | None, ...]):
    """Construct dependencies and periods with the supplying Creates included."""
    count = max(operation.particle for operation in operations) + 1
    selected_by: list[int | None] = [None] * count
    for operation in operations:
        if isinstance(operation, Vacate):
            selected_by[operation.particle] = operation.destruction

    periods: list[list[relationship_periods.Period]] = [[] for _ in range(count)]
    current: list[tuple[int, int] | None] = [None] * count
    lifetimes: list[set[int]] = [set() for _ in range(count)]
    # Particle identities already index dense lifetime and period records.
    # The negative index denotes an operation not yet encountered, avoiding
    # three additional hash tables for the same identities.
    creates = array.array("q", [-1]) * count
    vacates = array.array("q", [-1]) * count
    last_moves = array.array("q", [-1]) * count
    setters: dict[int, int] = {}
    calculated = graph.Graph()
    ordered: list[Operation] = []
    vanishes: list[Vanish] = []
    for operation in operations:
        if isinstance(operation, Vanish):
            vanishes.append(operation)
            continue
        index = len(ordered)
        needed: set[int] = set()
        if isinstance(operation, Create):
            positions = (operation.target,)
        elif isinstance(operation, Move):
            positions = (operation.source, operation.target)
            needed.add(operation.particle)
        elif isinstance(operation, Vacate):
            positions = (operation.position,)
            needed.add(operation.particle)
        else:
            raise TypeError(operation)
        candidates: set[int] = set()
        for position in positions:
            parent = parents[position]
            if parent is not None:
                needed.add(parent)
            setter = setters.get(position)
            if setter is not None:
                candidates.add(setter)
            elif parent is not None:
                candidates.add(creates[parent])
        for particle in needed:
            # Each endpoint setter already follows its defining particle's
            # Create; an occupied source also supplies the selected particle.
            # There are at most two candidates, so pruning needs no cutoff.
            lifetimes[particle].difference_update(candidates)
            lifetimes[particle].add(index)
        _ = calculated.append(algorithm.compare(calculated, candidates))
        ordered.append(operation)

        if isinstance(operation, Vacate):
            vacates[operation.particle] = index
            parent = parents[operation.position]
            if parent is None or selected_by[parent] != operation.destruction:
                setters[operation.position] = index
            continue
        for position in positions:
            setters[position] = index
        if isinstance(operation, Create):
            creates[operation.particle] = index
        else:
            last_moves[operation.particle] = index
        parent = parents[operation.target]
        previous = current[operation.particle]
        if previous is not None:
            beginning, previous_parent = previous
            if previous_parent == parent:
                continue
            periods[operation.particle].append(
                relationship_periods.Period(previous_parent, beginning, (index,))
            )
        current[operation.particle] = None if parent is None else (index, parent)

    for particle, previous in enumerate(current):
        if previous is not None:
            beginning, parent = previous
            ending: tuple[int, ...] | None = None
            if vacates[particle] != -1:
                ending = (vacates[particle],)
                # Earlier direct Moves already supply the selected occupancy
                # for Vacate. Only destruction Moves can finish afterward.
                if last_moves[particle] > vacates[particle]:
                    ending = (*ending, last_moves[particle])
            periods[particle].append(
                relationship_periods.Period(parent, beginning, ending)
            )
    for operation in vanishes:
        candidates = lifetimes[operation.particle]
        candidates.add(vacates[operation.particle])
        _ = calculated.append_terminal(algorithm.compare(calculated, candidates))
        ordered.append(operation)
    return Construction(ordered, calculated, periods)
