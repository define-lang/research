"""Small independent all-conflicts interpreter for differential verification."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from operation_graph_optimization import algorithm


class Reference:
    """Retain full record histories instead of last changes and use lists."""

    def __init__(self):
        """Start with empty local positions and no operations."""
        self.histories: dict[int, list[tuple[int, bool]]] = {}
        self.ancestors: list[set[int]] = []
        self.dependencies: list[set[int]] = []

    def retain(self, positions: dict[int, int]):
        """Keep the ordinary prefix and share subsequent retained changes."""
        for ordinary, retained in positions.items():
            self.histories[retained] = list(self.histories[ordinary])

    def _calculate(self, operation: algorithm.Operation) -> int:
        conflicts = set(operation.creators)
        for position in (*operation.occupied, operation.fill, operation.empty):
            if position is None:
                continue
            for previous, changed in self.histories.get(position, []):
                if changed or position == operation.empty:
                    conflicts.add(previous)
        ancestors = set(conflicts)
        for conflict in conflicts:
            ancestors.update(self.ancestors[conflict])
        dependencies = set(conflicts)
        for conflict in conflicts:
            dependencies.difference_update(self.ancestors[conflict])
        occurrence = len(self.dependencies)
        self.dependencies.append(dependencies)
        self.ancestors.append(ancestors)
        return occurrence

    def _record(self, operation: algorithm.Operation, occurrence: int):
        for position in operation.occupied:
            self.histories.setdefault(position, []).append((occurrence, False))
        for position in (operation.fill, operation.empty):
            if position is not None:
                self.histories.setdefault(position, []).append((occurrence, True))

    def add(self, operation: algorithm.Operation) -> int:
        """Orient every earlier conflict before this operation."""
        occurrence = self._calculate(operation)
        self._record(operation, occurrence)
        return occurrence

    def simultaneous(self, operations: list[algorithm.Operation]) -> list[int]:
        """Give simultaneous vacancies no conflicts with their peers."""
        occurrences = [self._calculate(operation) for operation in operations]
        for operation, occurrence in zip(operations, occurrences, strict=True):
            self._record(operation, occurrence)
        return occurrences
