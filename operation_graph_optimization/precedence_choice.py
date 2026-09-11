"""Finite precedence constraints with conjunctions as alternatives."""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass

type Precedence = tuple[int, int]
type Alternative = frozenset[Precedence]
type Clause = tuple[Alternative, ...]


def negate_clause(clause: Clause):
    """Express a clause's negation as clauses over strict total orders."""
    negation: list[Clause] = []
    for alternative in clause:
        # A self-precedence is false, whereas reversing it would still be
        # false. Its conjunction therefore needs no negated constraint.
        if any(earlier == later for earlier, later in alternative):
            continue
        negation.append(
            tuple(frozenset({(later, earlier)}) for earlier, later in alternative)
        )
    return tuple(negation)


@dataclass
class Part:
    """One independent finite precedence-choice problem."""

    operations: list[int]
    clauses: tuple[Clause, ...]
    edges: set[Precedence]


def strong_components(following: list[list[int]]):
    """Partition a directed graph by mutual reachability."""
    preceding: list[list[int]] = [[] for _ in following]
    for earlier, later_operations in enumerate(following):
        for later in later_operations:
            preceding[later].append(earlier)
    visited: set[int] = set()
    finished: list[int] = []
    for first in range(len(following)):
        if first in visited:
            continue
        visited.add(first)
        pending = [(first, iter(following[first]))]
        while pending:
            current, successors = pending[-1]
            later = next(successors, None)
            if later is None:
                finished.append(current)
                _ = pending.pop()
            elif later not in visited:
                visited.add(later)
                pending.append((later, iter(following[later])))
    components = [-1] * len(following)
    component = 0
    for first in reversed(finished):
        if components[first] != -1:
            continue
        components[first] = component
        pending_operations = [first]
        while pending_operations:
            current = pending_operations.pop()
            for earlier in preceding[current]:
                if components[earlier] == -1:
                    components[earlier] = component
                    pending_operations.append(earlier)
        component += 1
    return components


@dataclass
class Partition:
    """Operation groups whose ordinary precedence quotient is acyclic."""

    operations: list[list[int]]
    part_of: list[int]
    index_of: list[int]


def partition(groups: list[list[int]], edges: set[Precedence], count: int) -> Partition:
    """Keep each supplied group together without cycles between groups."""
    representatives = list(range(count))

    def representative(operation: int):
        while operation != representatives[operation]:
            representatives[operation] = representatives[representatives[operation]]
            operation = representatives[operation]
        return operation

    for group in groups:
        for operation in group:
            representatives[representative(operation)] = representative(group[0])
    identifiers: dict[int, int] = {}
    operation_groups: list[int] = []
    for operation in range(count):
        first = representative(operation)
        if first not in identifiers:
            identifiers[first] = len(identifiers)
        operation_groups.append(identifiers[first])
    following: list[list[int]] = [[] for _ in identifiers]
    for earlier, later in edges:
        before = operation_groups[earlier]
        after = operation_groups[later]
        if before != after:
            following[before].append(after)
    components = strong_components(following)
    parts: list[list[int]] = [[] for _ in range(max(components, default=-1) + 1)]
    part_of: list[int] = []
    indices: list[int] = []
    for operation, identifier in enumerate(operation_groups):
        component = components[identifier]
        part = parts[component]
        part_of.append(component)
        indices.append(len(part))
        part.append(operation)
    return Partition(parts, part_of, indices)


def factor(clauses: tuple[Clause, ...], edges: set[Precedence], count: int):
    """Partition clauses without losing precedence between their choices."""
    groups: list[list[int]] = []
    for clause in clauses:
        operations: set[int] = set()
        for alternative in clause:
            for earlier, later in alternative:
                operations.add(earlier)
                operations.add(later)
        groups.append(list(operations))
    divided = partition(groups, edges, count)
    parts: list[Part] = []
    for members in divided.operations:
        parts.append(Part(members, (), set()))
    indices = divided.index_of
    for earlier, later in edges:
        component = divided.part_of[earlier]
        if component == divided.part_of[later]:
            parts[component].edges.add((indices[earlier], indices[later]))
    part_clauses: dict[int, list[Clause]] = {}
    for clause, group in zip(clauses, groups, strict=True):
        if not group:
            # A variable-free false clause is still a contradiction, including
            # for a problem with no operations at all.
            if not clause:
                return [Part([], ((),), set())]
            continue
        component = divided.part_of[group[0]]
        converted: list[Alternative] = []
        for alternative in clause:
            converted.append(
                frozenset(
                    (indices[earlier], indices[later]) for earlier, later in alternative
                )
            )
        if component not in part_clauses:
            part_clauses[component] = []
        part_clauses[component].append(tuple(converted))
    for component, local_clauses in part_clauses.items():
        parts[component].clauses = tuple(local_clauses)
    return parts


def closure(edges: set[Precedence], count: int):
    """Find the strict transitive consequences of a precedence relation."""
    rows = [0] * count
    for earlier, later in edges:
        rows[earlier] |= 1 << later
    for middle in range(count):
        for earlier in range(count):
            if rows[earlier] & (1 << middle):
                rows[earlier] |= rows[middle]
    result: set[Precedence] = set()
    for earlier in range(count):
        for later in range(count):
            if rows[earlier] & (1 << later):
                result.add((earlier, later))
    return result


def topological_order(edges: set[Precedence], count: int):
    """Find a total order extending the given precedence relation."""
    following: list[list[int]] = [[] for _ in range(count)]
    incoming = [0] * count
    for earlier, later in edges:
        following[earlier].append(later)
        incoming[later] += 1
    ready = [index for index in range(count) if incoming[index] == 0]
    heapq.heapify(ready)
    order: list[int] = []
    while ready:
        earlier = heapq.heappop(ready)
        order.append(earlier)
        for later in following[earlier]:
            incoming[later] -= 1
            if incoming[later] == 0:
                heapq.heappush(ready, later)
    return tuple(order) if len(order) == count else None


def completion_order(
    clauses: tuple[Clause, ...], edges: set[Precedence], count: int
) -> tuple[int, ...] | None:
    """Find a total order satisfying every clause and mandatory precedence."""
    while True:
        if not clauses:
            return topological_order(edges, count)
        reachable = closure(edges, count)
        if any((index, index) in reachable for index in range(count)):
            return None
        remaining: list[Clause] = []
        forced: set[Precedence] = set()
        for clause in clauses:
            if any(alternative <= reachable for alternative in clause):
                continue
            possible: list[Alternative] = []
            for alternative in clause:
                if any(
                    earlier == later or (later, earlier) in reachable
                    for earlier, later in alternative
                ):
                    continue
                possible.append(alternative - reachable)
            if not possible:
                return None
            if len(possible) == 1:
                forced.update(possible[0])
            else:
                remaining.append(tuple(possible))
        clauses = tuple(remaining)
        if forced:
            edges = reachable | forced
            continue
        if not clauses:
            return topological_order(reachable, count)
        selected = min(clauses, key=len)
        for alternative in selected:
            order = completion_order(clauses, reachable | alternative, count)
            if order is not None:
                return order
        return None


def factored_completion_order(
    clauses: tuple[Clause, ...], edges: set[Precedence], count: int
) -> tuple[int, ...] | None:
    """Compose local completion witnesses without global reachability closure."""
    if not clauses:
        return topological_order(edges, count)
    combined = edges.copy()
    for part in factor(clauses, edges, count):
        order = completion_order(part.clauses, part.edges, len(part.operations))
        if order is None:
            return None
        # These edges choose one search certificate, not the runtime graph.
        # Acyclicity of the quotient permits every local witness to compose.
        for earlier, later in itertools.pairwise(order):
            combined.add((part.operations[earlier], part.operations[later]))
    return topological_order(combined, count)


def necessary_precedences(
    clauses: tuple[Clause, ...], edges: set[Precedence], count: int
):
    """Find precedence shared by every satisfying order of a finite problem."""
    witness = completion_order(clauses, edges, count)
    if witness is None:
        return None
    required: set[Precedence] = set()
    for index, earlier in enumerate(witness):
        for later in witness[index + 1 :]:
            reverse = completion_order(clauses, edges | {(later, earlier)}, count)
            if reverse is None:
                required.add((earlier, later))
    return required
