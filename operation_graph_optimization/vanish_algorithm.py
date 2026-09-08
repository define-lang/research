"""Vanish Collection specialized for ordered direct Moves."""

from __future__ import annotations

from typing import final

from operation_graph_optimization import algorithm, graph


@final
class Calculator:
    """Calculate Vanishes without changing existing position dependencies."""

    def __init__(self, calculated: graph.Graph):
        """Share occurrence identities with the position-dependency graph."""
        self.graph = calculated
        self.candidates: dict[int, set[int]] = {}
        self.last_moves: dict[int, int] = {}
        self.vacates: dict[int, int] = {}

    def observe(
        self,
        occurrence: int,
        quality_particles: tuple[int, ...],
        moved: int | None,
        vacated: int | None,
        ordinary_occupants: tuple[int, ...] = (),
    ):
        """Record actual quality uses, direct movement, and selected Vacation."""
        if quality_particles and ordinary_occupants:
            covered = set(ordinary_occupants)
            quality_particles = tuple(
                particle for particle in quality_particles if particle not in covered
            )
        if quality_particles or vacated is not None:
            dependencies = self.graph.dependencies(occurrence)
            for particle in quality_particles:
                candidates = self.candidates.setdefault(particle, set())
                candidates.difference_update(dependencies)
                candidates.add(occurrence)
            if vacated is not None:
                self.vacates[vacated] = occurrence
                candidates = self.candidates.setdefault(vacated, set())
                candidates.difference_update(dependencies)
                candidates.add(occurrence)
        if moved is not None:
            self.last_moves[moved] = occurrence

    def finish(self) -> dict[int, int]:
        """Append each selected particle's Vanish after its maximal candidates."""
        result: dict[int, int] = {}
        for particle in self.vacates:
            candidates = self.candidates.pop(particle)
            last_move = self.last_moves.pop(particle, None)
            if last_move is not None:
                candidates.add(last_move)
            result[particle] = self.graph.append(
                algorithm.compare(self.graph, candidates)
            )
        return result
