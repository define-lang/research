"""Bound shared pruning and release construction state during finalization."""

from __future__ import annotations

from typing import override

from operation_graph_optimization import integrated_compact
from operation_graph_optimization.integrated import algorithm


class Calculator(integrated_compact.Calculator):
    """Keep lifetime maintenance linear in the actual input requirements."""

    @override
    def _observe(
        self,
        operation: algorithm.Operation,
        occurrence: int,
        predecessors: set[int] | list[int],
    ):
        ordinary = operation.ordinary_occupants
        covered = set(ordinary) if len(ordinary) > 1 else ordinary
        for particle in operation.quality_particles:
            if particle in covered:
                continue
            uses = self._uses.setdefault(particle, set())
            if len(predecessors) <= algorithm.MAX_PRUNING_CANDIDATES:
                uses.difference_update(predecessors)
            uses.add(occurrence)
        if operation.vacated is not None:
            self._vacates[operation.vacated] = occurrence
        if operation.moved is not None:
            self._last_moves[operation.moved] = occurrence

    @override
    def finish(self) -> dict[int, int]:
        """Reuse the Vacate mapping for the completed particle-to-Vanish mapping."""
        self._positions.clear()
        for particle, vacate in self._vacates.items():
            candidates = self._uses.pop(particle, None)
            if candidates is None:
                candidates = {vacate}
            else:
                candidates.add(vacate)
            moved = self._last_moves.pop(particle, None)
            if moved is not None:
                candidates.add(moved)
            self._vacates[particle] = self.graph.append_terminal(
                algorithm.compare(self.graph, candidates)
            )
        self._uses.clear()
        self._last_moves.clear()
        return self._vacates
