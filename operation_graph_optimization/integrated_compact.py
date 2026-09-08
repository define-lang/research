"""Avoid allocating particle-use sets merely to remember a Vacate."""

from __future__ import annotations

from typing import override

from operation_graph_optimization.integrated import algorithm


class Calculator(algorithm.Calculator):
    """Share position Collection and store only independently needed uses."""

    @override
    def _observe(
        self,
        operation: algorithm.Operation,
        occurrence: int,
        predecessors: set[int] | list[int],
    ):
        for particle in operation.quality_particles:
            if particle in operation.ordinary_occupants:
                continue
            uses = self._uses.setdefault(particle, set())
            uses.difference_update(predecessors)
            uses.add(occurrence)
        if operation.vacated is not None:
            self._vacates[operation.vacated] = occurrence
        if operation.moved is not None:
            self._last_moves[operation.moved] = occurrence

    @override
    def finish(self) -> dict[int, int]:
        """Append Vanishes without retaining singleton Vacate candidate sets."""
        result: dict[int, int] = {}
        for particle, vacate in self._vacates.items():
            candidates = self._uses.pop(particle, None)
            if candidates is None:
                candidates = {vacate}
            else:
                candidates.add(vacate)
            moved = self._last_moves.pop(particle, None)
            if moved is not None:
                candidates.add(moved)
            result[particle] = self.graph.append_terminal(
                algorithm.compare(self.graph, candidates)
            )
        return result
