"""Finite cycle constraints for uninterrupted parent relationships."""

from __future__ import annotations

from dataclasses import dataclass

from operation_graph_optimization import precedence_choice


@dataclass(frozen=True, slots=True)
class Period:
    """A parent relationship with optional boundaries in the collected events."""

    parent: int
    beginning: int | None
    ending: tuple[int, ...] | None


def _cycle_clause(cycle: list[Period] | tuple[Period, ...]):
    alternatives: list[precedence_choice.Alternative] = []
    for ending_index, ending_period in enumerate(cycle):
        if ending_period.ending is None:
            continue
        for beginning_index, beginning_period in enumerate(cycle):
            if ending_index == beginning_index or beginning_period.beginning is None:
                continue
            alternatives.append(
                frozenset(
                    (ending, beginning_period.beginning)
                    for ending in ending_period.ending
                )
            )
    return tuple(alternatives)


def cycle_clauses(periods: list[list[Period]]):
    """Characterize total orders without overlapping cyclic relationships."""
    periods = cyclic_periods(periods)
    clauses: list[precedence_choice.Clause] = []
    for first in range(len(periods)):
        pending: list[tuple[int, tuple[Period, ...], frozenset[int]]] = [
            (first, (), frozenset({first}))
        ]
        while pending:
            particle, previous, visited = pending.pop()
            for period in periods[particle]:
                if period.parent < first:
                    continue
                if period.parent == first:
                    cycle = (*previous, period)
                    clauses.append(_cycle_clause(cycle))
                elif period.parent not in visited:
                    pending.append(
                        (period.parent, (*previous, period), visited | {period.parent})
                    )
    return tuple(clauses)


def cyclic_periods(periods: list[list[Period]]) -> list[list[Period]]:
    """Keep only periods whose parent relationship can belong to a cycle."""
    increasing = True
    decreasing = True
    for particle, relationships in enumerate(periods):
        for period in relationships:
            increasing = increasing and particle < period.parent
            decreasing = decreasing and particle > period.parent
        if not increasing and not decreasing:
            break
    # A strict rank change on every possible edge rules out a cycle without
    # allocating the reverse adjacency needed for component construction.
    if increasing or decreasing:
        return [[] for _ in periods]
    following: list[list[int]] = []
    for relationships in periods:
        following.append([period.parent for period in relationships])
    components = precedence_choice.strong_components(following)
    relevant: list[list[Period]] = []
    for particle, relationships in enumerate(periods):
        # A cycle cannot leave a strongly connected component and return.
        # Discarding these periods prevents walking long acyclic ancestries.
        relevant.append(
            [
                period
                for period in relationships
                if components[particle] == components[period.parent]
            ]
        )
    return relevant


def guarded_moves(periods: list[list[Period]], moves: set[int]):
    """Identify Moves that need permission beyond ordinary dependencies."""
    guarded: set[int] = set()
    for relationships in cyclic_periods(periods):
        for period in relationships:
            if period.beginning is not None and period.beginning in moves:
                guarded.add(period.beginning)
    return guarded


def first_violation(
    periods: list[list[Period]], order: tuple[int, ...]
) -> precedence_choice.Clause | None:
    """Find a cycle at a Move effect, including before its later release."""
    periods = cyclic_periods(periods)
    if not any(periods):
        return None
    beginnings: dict[int, tuple[int, Period]] = {}
    endings: dict[int, list[tuple[int, Period]]] = {}
    remaining: dict[Period, int] = {}
    active: list[Period | None] = [None] * len(periods)
    for particle, relationships in enumerate(periods):
        for period in relationships:
            if period.beginning is None:
                active[particle] = period
            else:
                beginnings[period.beginning] = particle, period
            if period.ending is not None:
                remaining[period] = len(period.ending)
                for ending in period.ending:
                    if ending not in endings:
                        endings[ending] = []
                    endings[ending].append((particle, period))
    for operation in order:
        for particle, period in endings.get(operation, ()):
            remaining[period] -= 1
            if remaining[period] == 0 and active[particle] is period:
                active[particle] = None
        beginning = beginnings.get(operation)
        if beginning is None:
            continue
        particle, period = beginning
        active[particle] = period
        visited: dict[int, int] = {}
        chain: list[Period] = []
        current = particle
        relationship = active[current]
        while relationship is not None:
            if current in visited:
                return _cycle_clause(chain[visited[current] :])
            visited[current] = len(chain)
            chain.append(relationship)
            current = relationship.parent
            relationship = active[current]
        # A restoration must be checked even when this very operation ends
        # its last preserved occupancy use. Removing it earlier hides cycles.
        if period.ending is not None and remaining[period] == 0:
            active[particle] = None
    return None


def completion_order(
    periods: list[list[Period]],
    edges: set[precedence_choice.Precedence],
    count: int,
) -> tuple[int, ...] | None:
    """Find a legal finite continuation by discovering violated cycle clauses."""
    clauses: list[precedence_choice.Clause] = []
    while True:
        order = precedence_choice.factored_completion_order(
            tuple(clauses), edges, count
        )
        if order is None:
            return None
        violation = first_violation(periods, order)
        if violation is None:
            return order
        clauses.append(violation)
