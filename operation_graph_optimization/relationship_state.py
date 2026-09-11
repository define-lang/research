"""Exact finite continuation search keyed by completed operation sets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from operation_graph_optimization import precedence_choice, relationship_periods

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator


def _reachable(initial: set[int], following: Callable[[int], Iterable[int]]):
    reached = initial.copy()
    pending = list(initial)
    while pending:
        current = pending.pop()
        for later in following(current):
            if later not in reached:
                reached.add(later)
                pending.append(later)
    return reached


class Search:
    """Continuation certificates for one resolved finite operation set."""

    def __init__(
        self,
        periods: list[list[relationship_periods.Period]],
        edges: set[precedence_choice.Precedence],
        count: int,
    ):
        """Prepare the ordinary prerequisites and possible parent relationships."""
        self.full: int = (1 << count) - 1
        self.prerequisites: list[int] = [0] * count
        for earlier, later in edges:
            self.prerequisites[later] |= 1 << earlier
        self.periods: list[list[tuple[int, int, int]]] = []
        self.beginnings: dict[int, tuple[int, int]] = {}
        for particle, relationships in enumerate(
            relationship_periods.cyclic_periods(periods)
        ):
            compiled: list[tuple[int, int, int]] = []
            for period in relationships:
                beginning = 0
                if period.beginning is not None:
                    beginning = 1 << period.beginning
                    self.beginnings[period.beginning] = particle, period.parent
                ending = 0
                if period.ending is not None:
                    for operation in period.ending:
                        ending |= 1 << operation
                compiled.append((beginning, ending, period.parent))
            self.periods.append(compiled)
        # Cache one next operation, not an entire suffix at every subset.
        self.choices: dict[int, int] = {self.full: count}

    def permits_effect(self, completed: int, operation: int):
        """Check the next relationship effect after a legal prefix."""
        beginning = self.beginnings.get(operation)
        if beginning is None:
            return True
        following = completed | (1 << operation)
        active: list[int | None] = [None] * len(self.periods)
        for particle, relationships in enumerate(self.periods):
            for first, last, parent in relationships:
                if (not first or first & following) and (
                    not last or last & following != last
                ):
                    active[particle] = parent
        particle, parent = beginning
        # A final restoration's occupied result precedes its immediate release.
        active[particle] = parent
        visited: set[int] = set()
        current: int | None = particle
        while current is not None:
            if current in visited:
                return False
            visited.add(current)
            current = active[current]
        return True

    def _successors(self, completed: int) -> Iterator[tuple[int, int]]:
        for operation, required in enumerate(self.prerequisites):
            bit = 1 << operation
            if completed & bit or required & completed != required:
                continue
            if self.permits_effect(completed, operation):
                yield operation, completed | bit

    def completion(self, completed: int = 0) -> tuple[int, ...] | None:
        """Find a suffix after a legal prefix, or prove none exists."""
        pending = [(completed, self._successors(completed))]
        while pending:
            current, successors = pending[-1]
            if current in self.choices:
                _ = pending.pop()
                continue
            successor = next(successors, None)
            if successor is None:
                self.choices[current] = -1
                _ = pending.pop()
                continue
            operation, following = successor
            if following in self.choices:
                if self.choices[following] != -1:
                    self.choices[current] = operation
                continue
            # Reconsider this successor once its continuation has been solved.
            pending[-1] = current, self._prepend(successor, successors)
            pending.append((following, self._successors(following)))
        if self.choices[completed] == -1:
            return None
        order: list[int] = []
        while completed != self.full:
            operation = self.choices[completed]
            order.append(operation)
            completed |= 1 << operation
        return tuple(order)

    @staticmethod
    def _prepend(
        first: tuple[int, int], remaining: Iterator[tuple[int, int]]
    ) -> Iterator[tuple[int, int]]:
        yield first
        yield from remaining


class PartitionedSearch:
    """Independent continuation searches coupled only by ordinary edges."""

    def __init__(
        self,
        periods: list[list[relationship_periods.Period]],
        dependencies: Callable[[int], Iterable[int]],
        dependents: Callable[[int], Iterable[int]],
    ):
        """Group possible cycles and any ordinary paths coupling their choices."""
        self.searches: list[Search] = []
        self.operations: list[list[int]] = []
        relevant = relationship_periods.cyclic_periods(periods)
        if not any(relevant):
            return
        following: list[list[int]] = []
        for relationships in relevant:
            following.append([period.parent for period in relationships])
        components = precedence_choice.strong_components(following)
        boundaries: dict[int, set[int]] = {}
        for particle, relationships in enumerate(relevant):
            if not relationships:
                continue
            component = components[particle]
            if component not in boundaries:
                boundaries[component] = set()
            for period in relationships:
                if period.beginning is not None:
                    boundaries[component].add(period.beginning)
                if period.ending is not None:
                    boundaries[component].update(period.ending)
        boundary_events: set[int] = set()
        for events in boundaries.values():
            boundary_events.update(events)
        # Only paths between boundaries can return to a competing group.
        # Ordinary predecessors and successors outside these paths remain in
        # the real graph but need not enlarge a continuation search.
        involved = sorted(
            _reachable(boundary_events, dependents)
            & _reachable(boundary_events, dependencies)
        )
        indices = {operation: index for index, operation in enumerate(involved)}
        groups: list[list[int]] = []
        for events in boundaries.values():
            groups.append([indices[event] for event in events])
        projected_edges: set[precedence_choice.Precedence] = set()
        for later in involved:
            for earlier in dependencies(later):
                if earlier in indices:
                    projected_edges.add((indices[earlier], indices[later]))
        divided = precedence_choice.partition(groups, projected_edges, len(involved))
        component_parts: dict[int, int] = {}
        for component, events in boundaries.items():
            # An initially legal arrangement cannot have a possible cycle
            # consisting entirely of relationships with no boundary event.
            component_parts[component] = divided.part_of[indices[next(iter(events))]]
        particles: dict[int, list[int]] = {}
        for particle, relationships in enumerate(relevant):
            if relationships:
                part = component_parts[components[particle]]
                if part not in particles:
                    particles[part] = []
                particles[part].append(particle)
        local_edges: dict[int, set[precedence_choice.Precedence]] = {}
        for part in particles:
            local_edges[part] = set()
        for earlier, later in projected_edges:
            part = divided.part_of[earlier]
            if part in particles and part == divided.part_of[later]:
                local_edges[part].add(
                    (divided.index_of[earlier], divided.index_of[later])
                )
        for part, members in particles.items():
            local_particle = {particle: index for index, particle in enumerate(members)}
            local_periods: list[list[relationship_periods.Period]] = []
            for particle in members:
                converted: list[relationship_periods.Period] = []
                for period in relevant[particle]:
                    beginning = None
                    if period.beginning is not None:
                        beginning = divided.index_of[indices[period.beginning]]
                    ending = None
                    if period.ending is not None:
                        ending = tuple(
                            divided.index_of[indices[event]] for event in period.ending
                        )
                    converted.append(
                        relationship_periods.Period(
                            local_particle[period.parent], beginning, ending
                        )
                    )
                local_periods.append(converted)
            operations = [involved[index] for index in divided.operations[part]]
            self.operations.append(operations)
            self.searches.append(
                Search(local_periods, local_edges[part], len(operations))
            )

    @classmethod
    def from_edges(
        cls,
        periods: list[list[relationship_periods.Period]],
        edges: set[precedence_choice.Precedence],
    ):
        """Prepare adjacency when the input does not already provide it."""
        following: dict[int, list[int]] = {}
        preceding: dict[int, list[int]] = {}
        for earlier, later in edges:
            following.setdefault(earlier, []).append(later)
            preceding.setdefault(later, []).append(earlier)
        return cls(
            periods,
            lambda operation: preceding.get(operation, ()),
            lambda operation: following.get(operation, ()),
        )

    def has_completion(self, completed: int):
        """Test continuation after a legal prefix without a global search."""
        for search, operations in zip(self.searches, self.operations, strict=True):
            local_completed = 0
            for local, operation in enumerate(operations):
                if completed & (1 << operation):
                    local_completed |= 1 << local
            if search.completion(local_completed) is None:
                return False
        return True
