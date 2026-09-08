"""Integrated alternatives kept separate from the recommended algorithm."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from operation_graph_optimization.integrated import algorithm

if TYPE_CHECKING:
    from operation_graph_optimization import vanish_workloads


class Direct(algorithm.Calculator):
    """Share Comparison's result instead of Collection's candidates."""

    @override
    def add(self, operation: algorithm.Operation) -> int:
        """Calculate one operation and maintain its position and particle uses."""
        candidates = self._collect(operation)
        dependencies = algorithm.compare(self.graph, candidates)
        occurrence = self.graph.append(dependencies)
        self._record(operation, occurrence, candidates)
        self._observe(operation, occurrence, dependencies)
        return occurrence


class Unpruned(algorithm.Calculator):
    """Defer all particle-use pruning until final Comparison."""

    @override
    def _observe(
        self,
        operation: algorithm.Operation,
        occurrence: int,
        predecessors: set[int] | list[int],
    ):
        super()._observe(operation, occurrence, [])


class Indexed(algorithm.Calculator):
    """Include terminal Vanishes in the reverse reachability index."""

    @override
    def finish(self) -> dict[int, int]:
        """Append the same Vanishes using ordinary indexed insertion."""
        result: dict[int, int] = {}
        for particle in self._vacates:
            candidates = self._uses.pop(particle)
            moved = self._last_moves.pop(particle, None)
            if moved is not None:
                candidates.add(moved)
            result[particle] = self.graph.append(
                algorithm.compare(self.graph, candidates)
            )
        return result


def convert(step: vanish_workloads.Step) -> algorithm.Operation:
    """Resolve the same workload into the complete algorithm's input type."""
    operation = step.operation
    return algorithm.Operation(
        occupied=operation.occupied,
        fill=operation.fill,
        empty=operation.empty,
        creators=operation.creators,
        defines=operation.defines,
        quality_particles=operation.creators,
        ordinary_occupants=step.ordinary_occupants,
        moved=step.moved,
        vacated=step.vacated,
    )
