"""Vanish dependency construction from resolved particle requirements."""

from __future__ import annotations

from typing import override

from operation_graph_optimization import algorithm, graph


class Collector:
    """Retain lifetime candidates until all position dependencies are known."""

    def __init__(self, calculated: graph.Graph):
        """Share the graph whose occurrence identities appear in requirements."""
        self.graph: graph.Graph = calculated
        self.candidates: dict[int, set[int]] = {}
        self.vacates: dict[int, int] = {}

    def _use(self, particle: int, occurrence: int, dependencies: list[int]):
        del dependencies
        self.candidates.setdefault(particle, set()).add(occurrence)

    def observe(self, occurrence: int, particles: tuple[int, ...], vacated: int | None):
        """Include actual quality uses, direct movement, and selected Vacation."""
        dependencies = list(self.graph.dependencies(occurrence))
        for particle in particles:
            if particle != vacated:
                self._use(particle, occurrence, dependencies)
        if vacated is not None:
            self.vacates[vacated] = occurrence
            self._use(vacated, occurrence, dependencies)

    def finish(self) -> dict[int, int]:
        """Append Vanishes without changing position setters or readers."""
        result: dict[int, int] = {}
        for particle in self.vacates:
            candidates = self.candidates.pop(particle)
            result[particle] = self.graph.append(
                algorithm.compare(self.graph, candidates)
            )
        return result


class DirectPruning(Collector):
    """Retire a previous use when the new use directly depends on it."""

    @override
    def _use(self, particle: int, occurrence: int, dependencies: list[int]):
        candidates = self.candidates.setdefault(particle, set())
        candidates.difference_update(dependencies)
        candidates.add(occurrence)


class Incremental(Collector):
    """Maintain the exact antichain after every particle requirement."""

    @override
    def _use(self, particle: int, occurrence: int, dependencies: list[int]):
        del dependencies
        candidates = self.candidates.setdefault(particle, set())
        covered: list[int] = []
        for previous in candidates:
            if self.graph.reaches(occurrence, previous):
                covered.append(previous)
        candidates.difference_update(covered)
        candidates.add(occurrence)
