"""Collection and Comparison for resolved, valid Define Particle Operations."""

from __future__ import annotations

import dataclasses
from typing import final

from operation_graph_optimization.complete import algorithm, graph

# These limits bound optional pruning; larger collections still receive full
# Comparison, so skipping a shortcut cannot change the graph.
MAX_PRUNING_CANDIDATES = 16


@dataclasses.dataclass(slots=True)
class _Position:
    setter: int
    readers: set[int] | None = None


def compare(calculated: graph.Graph, candidates: set[int]) -> list[int]:
    """Apply the spec's ordered Comparison directly."""
    ordered = sorted(candidates, key=calculated.heights.__getitem__, reverse=True)
    kept: list[int] = []
    for candidate in ordered:
        if not any(calculated.reaches_indexed(later, candidate) for later in kept):
            kept.append(candidate)
    return kept


@final
class Calculator:
    """Calculate dependencies while following the specified serial state."""

    def __init__(self, cache_targets: int = 1024, cache_bytes: int = 64 * 1024**2):
        """Keep occupancy analysis separate from dependency reachability."""
        self.graph = graph.Graph(cache_targets, cache_bytes)
        self._positions: dict[int, _Position] = {}
        self._particle_uses: dict[int, set[int]] = {}
        self._last_moves: dict[int, int] = {}
        self._vacates: dict[int, int] = {}

    def retain(self, positions: dict[int, int]):
        """Preserve position information for shared destructor use."""
        for ordinary, retained in positions.items():
            state = self._positions[ordinary]
            readers = None if state.readers is None else state.readers.copy()
            self._positions[retained] = _Position(
                state.setter,
                readers,
            )

    def forget(self, positions: tuple[int, ...]):
        """Release records after source analysis proves they have no future uses."""
        for position in positions:
            del self._positions[position]

    def _collect(self, operation: algorithm.Operation) -> set[int]:
        candidates = set(operation.quality_particles)
        for position in (*operation.occupied, operation.fill):
            if position is not None:
                state = self._positions.get(position)
                if state is not None:
                    candidates.add(state.setter)
        if operation.empty is not None:
            state = self._positions[operation.empty]
            if state.readers is None:
                candidates.add(state.setter)
            else:
                candidates.update(state.readers)
        return candidates

    def _record(
        self, operation: algorithm.Operation, occurrence: int, collected: set[int]
    ):
        for position in operation.occupied:
            state = self._positions[position]
            if state.readers is None:
                state.readers = {occurrence}
            else:
                # Bounding this optional pruning keeps long references from
                # multiplying work by an arbitrarily large dependency count.
                if len(collected) <= MAX_PRUNING_CANDIDATES:
                    state.readers.difference_update(collected)
                state.readers.add(occurrence)
        for position in (operation.fill, operation.empty):
            if position is None:
                continue
            state = self._positions.get(position)
            if state is None:
                self._positions[position] = _Position(occurrence)
            else:
                state.setter = occurrence
                state.readers = None
        for position in operation.defines:
            self._positions[position] = _Position(occurrence)

        for particle in operation.quality_particles:
            uses = self._particle_uses.setdefault(particle, set())
            uses.add(occurrence)
        if operation.vacated is not None:
            self._vacates[operation.vacated] = occurrence
        if operation.moved is not None:
            self._last_moves[operation.moved] = occurrence

    def finish(self) -> dict[int, int]:
        """Finish the graph; no further operations may be added."""
        self._positions.clear()
        for particle, vacate in self._vacates.items():
            candidates = self._particle_uses.pop(particle, None)
            if candidates is None:
                candidates = {vacate}
            else:
                candidates.add(vacate)
            moved = self._last_moves.pop(particle, None)
            if moved is not None:
                candidates.add(moved)
            self._vacates[particle] = self.graph.append_terminal(
                compare(self.graph, candidates)
            )
        self._particle_uses.clear()
        self._last_moves.clear()
        return self._vacates

    def add(self, operation: algorithm.Operation) -> int:
        """Calculate and record one Create, Move, or Vacate."""
        candidates = self._collect(operation)
        dependencies = compare(self.graph, candidates)
        occurrence = self.graph.append(dependencies)
        self._record(operation, occurrence, candidates)
        return occurrence

    def simultaneous(self, operations: list[algorithm.Operation]) -> list[int]:
        """Calculate Vacates selected by one simultaneous destruction."""
        return [self.add(operation) for operation in operations]
