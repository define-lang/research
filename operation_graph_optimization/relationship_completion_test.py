from __future__ import annotations

import dataclasses
import heapq
import itertools
import random

from operation_graph_optimization import departure_exclusion, relationship_exclusion
from operation_graph_optimization.complete import graph


@dataclasses.dataclass(frozen=True)
class Operation:
    particle: int
    source: int
    target: int | None


@dataclasses.dataclass
class Exploration:
    transitions: dict[int, dict[int, int]]
    completable: set[int]


@dataclasses.dataclass(frozen=True)
class Residence:
    particle: int
    owner: int
    start: int | None
    end: int | None


def occupancy_edges(operations: tuple[Operation, ...]):
    edges: set[tuple[int, int]] = set()
    setters: dict[int, int] = {}
    for index, operation in enumerate(operations):
        positions = [operation.source]
        if operation.target is not None:
            positions.append(operation.target)
        for position in positions:
            if position in setters:
                edges.add((setters[position], index))
            setters[position] = index
    return edges


def collect_residences(
    initial: tuple[int | None, ...],
    owners: tuple[int | None, ...],
    operations: tuple[Operation, ...],
    *,
    merge_same_parent: bool = True,
):
    residences: list[list[Residence]] = [[] for _ in initial]
    starts: list[int | None] = [None for _ in initial]
    locations = list(initial)
    for index, operation in enumerate(operations):
        owner = owners[operation.source]
        following_owner = None if operation.target is None else owners[operation.target]
        locations[operation.particle] = operation.target
        if merge_same_parent and owner == following_owner:
            continue
        if owner is not None:
            residences[operation.particle].append(
                Residence(operation.particle, owner, starts[operation.particle], index)
            )
        starts[operation.particle] = index
    for particle, position in enumerate(locations):
        if position is not None:
            owner = owners[position]
            if owner is not None:
                residences[particle].append(
                    Residence(particle, owner, starts[particle], None)
                )
    return residences


def relationship_clauses(
    initial: tuple[int | None, ...],
    owners: tuple[int | None, ...],
    operations: tuple[Operation, ...],
    *,
    merge_same_parent: bool = True,
):
    residences = collect_residences(
        initial, owners, operations, merge_same_parent=merge_same_parent
    )

    clauses: list[set[tuple[int, int]]] = []
    for first in range(len(initial)):
        pending: list[tuple[int, tuple[Residence, ...], set[int]]] = [
            (first, (), {first})
        ]
        while pending:
            particle, previous, visited = pending.pop()
            for residence in residences[particle]:
                if residence.owner < first:
                    continue
                if residence.owner == first:
                    cycle = (*previous, residence)
                    alternatives: set[tuple[int, int]] = set()
                    for earlier, later in itertools.product(cycle, repeat=2):
                        if earlier.end is not None and later.start is not None:
                            alternatives.add((earlier.end, later.start))
                    clauses.append(alternatives)
                elif residence.owner not in visited:
                    pending.append(
                        (
                            residence.owner,
                            (*previous, residence),
                            visited | {residence.owner},
                        )
                    )
    return clauses


def closure(edges: set[tuple[int, int]], count: int):
    rows = [0] * count
    for first, last in edges:
        rows[first] |= 1 << last
    for middle in range(count):
        for first in range(count):
            if rows[first] & (1 << middle):
                rows[first] |= rows[middle]
    reachable: set[tuple[int, int]] = set()
    for first in range(count):
        for last in range(count):
            if rows[first] & (1 << last):
                reachable.add((first, last))
    return reachable


def propagate(
    clauses: list[set[tuple[int, int]]], edges: set[tuple[int, int]], count: int
):
    remaining = clauses.copy()
    while True:
        reachable = closure(edges, count)
        if any((index, index) in reachable for index in range(count)):
            return None
        reduced: list[set[tuple[int, int]]] = []
        forced: set[tuple[int, int]] = set()
        for clause in remaining:
            if clause & reachable:
                continue
            alternatives: set[tuple[int, int]] = set()
            for first, last in clause:
                if first != last and (last, first) not in reachable:
                    alternatives.add((first, last))
            if not alternatives:
                return None
            if len(alternatives) == 1:
                forced.update(alternatives)
            else:
                reduced.append(alternatives)
        if not forced:
            return reachable, reduced
        edges = edges | forced
        remaining = reduced


def has_completion(
    clauses: list[set[tuple[int, int]]], edges: set[tuple[int, int]], count: int
) -> bool:
    return completion_order(clauses, edges, count) is not None


def topological_order(edges: set[tuple[int, int]], count: int):
    successors: list[list[int]] = [[] for _ in range(count)]
    incoming = [0] * count
    for first, last in edges:
        successors[first].append(last)
        incoming[last] += 1
    ready = [index for index in range(count) if incoming[index] == 0]
    heapq.heapify(ready)
    order: list[int] = []
    while ready:
        current = heapq.heappop(ready)
        order.append(current)
        for following in successors[current]:
            incoming[following] -= 1
            if incoming[following] == 0:
                heapq.heappush(ready, following)
    return tuple(order) if len(order) == count else None


def completion_order(
    clauses: list[set[tuple[int, int]]], edges: set[tuple[int, int]], count: int
) -> tuple[int, ...] | None:
    if not clauses:
        return topological_order(edges, count)
    propagated = propagate(clauses, edges, count)
    if propagated is None:
        return None
    reachable, remaining = propagated
    if not remaining:
        return topological_order(reachable, count)
    alternatives = min(remaining, key=len)
    for alternative in sorted(alternatives):
        order = completion_order(remaining, reachable | {alternative}, count)
        if order is not None:
            return order
    return None


def violated_clause(
    initial: tuple[int | None, ...],
    owners: tuple[int | None, ...],
    operations: tuple[Operation, ...],
    residences: list[list[Residence]],
    order: tuple[int, ...],
):
    active: dict[int, Residence] = {}
    starting: dict[int, Residence] = {}
    for periods in residences:
        for period in periods:
            if period.start is None:
                active[period.particle] = period
            else:
                starting[period.start] = period
    locations = list(initial)
    for index in order:
        operation = operations[index]
        before = owners[operation.source]
        after = None if operation.target is None else owners[operation.target]
        locations[operation.particle] = operation.target
        if before == after:
            continue
        if before is not None:
            del active[operation.particle]
        if after is None:
            continue
        active[operation.particle] = starting[index]
        chain: list[int] = []
        visited: dict[int, int] = {}
        current: int | None = operation.particle
        while current is not None:
            if current in visited:
                cycle = chain[visited[current] :]
                alternatives: set[tuple[int, int]] = set()
                for first, last in itertools.product(cycle, repeat=2):
                    end = active[first].end
                    start = active[last].start
                    if end is not None and start is not None:
                        alternatives.add((end, start))
                return alternatives
            visited[current] = len(chain)
            chain.append(current)
            position = locations[current]
            current = None if position is None else owners[position]
    return None


def lazy_completion(
    initial: tuple[int | None, ...],
    owners: tuple[int | None, ...],
    operations: tuple[Operation, ...],
    prefix: tuple[int, ...],
):
    residences = collect_residences(initial, owners, operations)
    edges = occupancy_edges(operations) | set(itertools.pairwise(prefix))
    completed = set(prefix)
    if prefix:
        for later in range(len(operations)):
            if later not in completed:
                edges.add((prefix[-1], later))
    clauses: list[set[tuple[int, int]]] = []
    while True:
        order = completion_order(clauses, edges, len(operations))
        if order is None:
            return None, clauses
        violation = violated_clause(initial, owners, operations, residences, order)
        if violation is None:
            return order, clauses
        clauses.append(violation)


def strong_components(successors: list[set[int]]):
    predecessors: list[set[int]] = [set() for _ in successors]
    for first, following in enumerate(successors):
        for last in following:
            predecessors[last].add(first)
    visited: set[int] = set()
    finished: list[int] = []
    for first in range(len(successors)):
        pending = [(first, False)]
        while pending:
            current, returning = pending.pop()
            if returning:
                finished.append(current)
            elif current not in visited:
                visited.add(current)
                pending.append((current, True))
                for following in successors[current]:
                    if following not in visited:
                        pending.append((following, False))
    component = [-1] * len(successors)
    count = 0
    for first in reversed(finished):
        if component[first] != -1:
            continue
        component[first] = count
        pending_vertices = [first]
        while pending_vertices:
            current = pending_vertices.pop()
            for previous in predecessors[current]:
                if component[previous] == -1:
                    component[previous] = count
                    pending_vertices.append(previous)
        count += 1
    return component


def choice_parts(
    initial: tuple[int | None, ...],
    owners: tuple[int | None, ...],
    operations: tuple[Operation, ...],
):
    parents: list[set[int]] = [set() for _ in initial]
    for particle, position in enumerate(initial):
        if position is not None:
            owner = owners[position]
            if owner is not None:
                parents[particle].add(owner)
    for operation in operations:
        if operation.target is not None:
            owner = owners[operation.target]
            if owner is not None:
                parents[operation.particle].add(owner)
    particle_components = strong_components(parents)
    sizes: dict[int, int] = {}
    for component in particle_components:
        sizes[component] = sizes.get(component, 0) + 1
    groups: dict[int, int] = {}
    operation_groups: list[int] = []
    for index, operation in enumerate(operations):
        component = particle_components[operation.particle]
        if sizes[component] == 1:
            component = len(initial) + index
        if component not in groups:
            groups[component] = len(groups)
        operation_groups.append(groups[component])
    following: list[set[int]] = [set() for _ in groups]
    for first, last in occupancy_edges(operations):
        first_group = operation_groups[first]
        last_group = operation_groups[last]
        if first_group != last_group:
            following[first_group].add(last_group)
    components = strong_components(following)
    parts: dict[int, set[int]] = {}
    for index, group in enumerate(operation_groups):
        component = components[group]
        if component not in parts:
            parts[component] = set()
        parts[component].add(index)
    return list(parts.values())


def factored_completion(
    clauses: list[set[tuple[int, int]]],
    ordinary: set[tuple[int, int]],
    parts: list[set[int]],
    prefix: tuple[int, ...],
    count: int,
):
    for part in parts:
        local_clauses: list[set[tuple[int, int]]] = []
        for clause in clauses:
            first, _ = next(iter(clause))
            if first in part:
                assert all(first in part and last in part for first, last in clause)
                local_clauses.append(clause)
        local_edges: set[tuple[int, int]] = set()
        for first, last in ordinary:
            if first in part and last in part:
                local_edges.add((first, last))
        local_prefix = tuple(index for index in prefix if index in part)
        local_edges.update(itertools.pairwise(local_prefix))
        if local_prefix:
            for later in part:
                if later not in local_prefix:
                    local_edges.add((local_prefix[-1], later))
        if not has_completion(local_clauses, local_edges, count):
            return False
    return True


def test_interval_clauses_match_all_orders_of_random_valid_move_sequences():
    generator = random.Random(731)  # noqa: S311 - Reproducible counterexample search.
    for _ in range(100):
        initial = (0, 1, 2, 3)
        owners = (None, None, None, None, 0, 1, 2, 3)
        locations: list[int] = list(initial)
        generated: list[Operation] = []
        for _ in range(6):
            choices: list[Operation] = []
            for particle, source in enumerate(locations):
                for target in range(len(owners)):
                    if target in locations:
                        continue
                    changed = locations.copy()
                    changed[particle] = target
                    if not has_cycle(tuple(changed), owners):
                        choices.append(Operation(particle, source, target))
            operation = generator.choice(choices)
            generated.append(operation)
            assert operation.target is not None
            locations[operation.particle] = operation.target
        operations = tuple(generated)
        clauses = relationship_clauses(initial, owners, operations)
        edges = occupancy_edges(operations)
        for order in itertools.permutations(range(len(operations))):
            ranks = {operation: index for index, operation in enumerate(order)}
            if any(ranks[first] >= ranks[last] for first, last in edges):
                continue
            current: list[int | None] = list(initial)
            valid = True
            for index in order:
                operation = operations[index]
                current[operation.particle] = operation.target
                valid = valid and not has_cycle(tuple(current), owners)
            satisfies = all(
                any(ranks[first] < ranks[last] for first, last in clause)
                for clause in clauses
            )
            assert valid == satisfies


def has_cycle(locations: tuple[int | None, ...], owners: tuple[int | None, ...]):
    for particle in range(len(locations)):
        visited: set[int] = set()
        current: int | None = particle
        while current is not None:
            if current in visited:
                return True
            visited.add(current)
            position = locations[current]
            current = None if position is None else owners[position]
    return False


def explore(
    initial: tuple[int | None, ...],
    owners: tuple[int | None, ...],
    operations: tuple[Operation, ...],
):
    prerequisites: list[int] = []
    setters: dict[int, int] = {}
    for index, operation in enumerate(operations):
        required = setters.get(operation.source, 0)
        if operation.target is not None:
            required |= setters.get(operation.target, 0)
            setters[operation.target] = 1 << index
        setters[operation.source] = 1 << index
        prerequisites.append(required)

    states = {0: initial}
    pending = [0]
    transitions: dict[int, dict[int, int]] = {}
    while pending:
        completed = pending.pop()
        locations = states[completed]
        successors: dict[int, int] = {}
        transitions[completed] = successors
        for index, operation in enumerate(operations):
            bit = 1 << index
            if (
                completed & bit
                or prerequisites[index] & completed != prerequisites[index]
            ):
                continue
            assert locations[operation.particle] == operation.source
            if operation.target is not None:
                assert operation.target not in locations
            changed = list(locations)
            changed[operation.particle] = operation.target
            after = tuple(changed)
            if has_cycle(after, owners):
                continue
            following = completed | bit
            successors[index] = following
            if following in states:
                assert states[following] == after
            else:
                states[following] = after
                pending.append(following)

    full = (1 << len(operations)) - 1
    assert full in states
    completable = {full}
    for completed in sorted(states, reverse=True):
        if any(
            following in completable for following in transitions[completed].values()
        ):
            completable.add(completed)
    return Exploration(transitions, completable)


def follow(exploration: Exploration, order: tuple[int, ...]):
    completed = 0
    for index in order:
        completed = exploration.transitions[completed][index]
    return completed


def test_vacates_release_competing_relationship_changes():
    initial = (0, 1, 2)
    owners = (None, 0, None, None, 2, 1)
    operations = (
        Operation(1, 1, 3),
        Operation(0, 0, 4),
        Operation(2, 2, 5),
        Operation(1, 3, None),
        Operation(0, 4, None),
        Operation(2, 5, None),
    )
    exploration = explore(initial, owners, operations)
    assert 2 not in exploration.transitions[follow(exploration, (1,))]
    assert 1 not in exploration.transitions[follow(exploration, (2,))]
    assert follow(exploration, (1, 4, 2, 0, 3, 5)) == 63
    assert follow(exploration, (2, 5, 1, 0, 3, 4)) == 63
    assert set(exploration.transitions) == exploration.completable


def test_direct_exclusion_rules_preserve_all_completable_two_particle_prefixes():
    generator = random.Random(290771)  # noqa: S311 - Reproducible source generation.
    initial = (0, 1)
    owners = (None, None, None, 0, 0, 1, 1)
    for _ in range(1000):
        operations = generate_moves(initial, owners, 12, generator)
        periods = collect_residences(initial, owners, operations)
        edges = occupancy_edges(operations)
        calculated = graph.Graph()
        for later in range(len(operations)):
            dependencies: list[int] = []
            for earlier in range(later):
                if (earlier, later) in edges:
                    dependencies.append(earlier)
            _ = calculated.append(dependencies)
        forced: set[tuple[int, int]] = set()
        for first in periods[0]:
            for second in periods[1]:
                assert first.start is not None
                assert second.start is not None
                before, after = (
                    (first, second) if first.start < second.start else (second, first)
                )
                assert before.end is not None
                assert after.start is not None
                alternatives = relationship_exclusion.collect(
                    calculated,
                    before.start,
                    (before.end,),
                    after.start,
                    None if after.end is None else (after.end,),
                )
                if len(alternatives) == 1:
                    forced.update(alternatives[0])
        exploration = explore(initial, owners, operations)
        allowed = {0}
        for completed in sorted(exploration.transitions):
            if completed not in allowed:
                continue
            for operation, following in exploration.transitions[completed].items():
                admitted = all(
                    later != operation or bool(completed & (1 << earlier))
                    for earlier, later in forced
                )
                assert admitted == (following in exploration.completable)
                if admitted:
                    allowed.add(following)
        assert allowed == exploration.completable


def test_disjoint_exclusions_share_a_departure_dependency():
    # This is disjoint_relationship_visits_share_departure_dependencies in
    # Define's normal testdata. Neither independent exclusion prevents the
    # two reverse entries from jointly blocking the departures they require.
    initial = (0, 1, 2, 3)
    owners = (None, None, None, None, 0, 1, 2, 3, None, None)
    operations = (
        Operation(0, 0, 5),
        Operation(0, 5, 8),
        Operation(0, 8, 0),
        Operation(2, 2, 7),
        Operation(2, 7, 9),
        Operation(2, 9, 2),
        Operation(1, 1, 4),
        Operation(1, 4, 9),
        Operation(3, 3, 6),
        Operation(3, 6, 8),
        Operation(0, 0, None),
        Operation(1, 9, None),
        Operation(2, 2, None),
        Operation(3, 8, None),
    )
    exploration = explore(initial, owners, operations)
    assert (1 << 6) in exploration.completable
    assert (1 << 8) in exploration.completable
    assert (1 << 6 | 1 << 8) not in exploration.completable
    assert len(exploration.transitions) == 177
    assert len(exploration.completable) == 176
    allowed = {0}
    for completed in sorted(exploration.transitions):
        if completed not in allowed:
            continue
        for operation, following in exploration.transitions[completed].items():
            admitted = (
                operation not in (6, 8)
                or bool(completed & ((1 << 1) | (1 << 4)))
                or not bool(completed & (1 << (8 if operation == 6 else 6)))
            )
            assert admitted == (following in exploration.completable)
            if admitted:
                allowed.add(following)
    assert allowed == exploration.completable


def test_departure_cycle_check_matches_every_prefix_of_disjoint_visit_pairs():
    for count in (1, 2, 3):
        for successors in itertools.permutations(range(count)):
            initial = tuple(range(count * 2))
            owners: tuple[int | None, ...] = (
                *((None,) * (count * 2)),
                *range(count * 2),
                *((None,) * count),
            )
            operations: list[Operation] = []
            forward_ends: list[int] = []
            reverse_beginnings: list[int] = []
            reverse_ends: list[int] = []
            for index in range(count):
                first = index * 2
                second = first + 1
                child = count * 2 + second
                handoff = count * 4 + index
                operations.extend(
                    (
                        Operation(first, first, child),
                        Operation(first, child, handoff),
                        Operation(first, handoff, first),
                    )
                )
                forward_ends.append(len(operations) - 2)
            for index, successor in enumerate(successors):
                first = index * 2
                second = first + 1
                child = count * 2 + first
                reverse_beginnings.append(len(operations))
                operations.extend(
                    (
                        Operation(second, second, child),
                        Operation(second, child, count * 4 + successor),
                    )
                )
                reverse_ends.append(len(operations) - 1)
            for index, successor in enumerate(successors):
                operations.extend(
                    (
                        Operation(index * 2, index * 2, None),
                        Operation(index * 2 + 1, count * 4 + successor, None),
                    )
                )
            exploration = explore(initial, owners, tuple(operations))
            allowed = {0}
            for completed in sorted(exploration.transitions):
                if completed not in allowed:
                    continue
                first_completed = 0
                second_started = 0
                second_completed = 0
                for index in range(count):
                    if completed & (1 << forward_ends[index]):
                        first_completed |= 1 << index
                    if completed & (1 << reverse_beginnings[index]):
                        second_started |= 1 << index
                    if completed & (1 << reverse_ends[index]):
                        second_completed |= 1 << index
                for operation, following in exploration.transitions[completed].items():
                    admitted = True
                    if operation in reverse_beginnings:
                        admitted = departure_exclusion.permits_entry(
                            successors,
                            first_completed,
                            second_started,
                            second_completed,
                            reverse_beginnings.index(operation),
                        )
                    assert admitted == (following in exploration.completable)
                    if admitted:
                        allowed.add(following)
            assert allowed == exploration.completable


def test_immediately_acyclic_move_can_prevent_completion_even_with_vacates():
    initial = (0, 1, 2)
    owners = (None, None, None, 0, 1, 2)
    operations = (
        Operation(2, 2, 3),
        Operation(2, 3, 4),
        Operation(0, 0, 5),
        Operation(1, 1, 2),
        Operation(0, 5, 1),
        Operation(0, 1, None),
        Operation(1, 2, None),
        Operation(2, 4, None),
    )
    exploration = explore(initial, owners, operations)
    after_early_move = follow(exploration, (2,))
    assert exploration.transitions[after_early_move] == {}
    assert after_early_move not in exploration.completable
    assert follow(exploration, tuple(range(8))) == 255
    for completed, successors in exploration.transitions.items():
        if 2 in successors:
            assert (successors[2] in exploration.completable) == bool(
                completed & (1 << 1)
            )


def test_successive_occupants_cannot_exchange_complete_visits():
    initial = (0, 1)
    owners = (None, None, None)
    operations = (
        Operation(0, 0, 2),
        Operation(0, 2, 0),
        Operation(1, 1, 2),
        Operation(1, 2, 1),
    )
    exploration = explore(initial, owners, operations)
    assert exploration.transitions == {
        0: {0: 1},
        1: {1: 3},
        3: {2: 7},
        7: {3: 15},
        15: {},
    }
    assert exploration.completable == {0, 1, 3, 7, 15}


def test_same_parent_moves_do_not_interrupt_relationships():
    initial = (0, 3, 2, 5)
    owners = (None, None, 0, None, 1, 2, 2, 3, 3)
    operations = (
        Operation(3, 5, 6),
        Operation(2, 2, 4),
        Operation(2, 4, 1),
        Operation(0, 0, 7),
        Operation(3, 6, 0),
        Operation(1, 3, 8),
        Operation(1, 8, 6),
        Operation(0, 7, None),
        Operation(1, 6, None),
        Operation(2, 1, None),
        Operation(3, 0, None),
    )
    exploration = explore(initial, owners, operations)
    assert 5 in exploration.transitions[0]
    assert (1 << 5) not in exploration.completable
    prefix_edges = {(5, index) for index in range(len(operations)) if index != 5}
    edges = occupancy_edges(operations) | prefix_edges
    separate = relationship_clauses(
        initial, owners, operations, merge_same_parent=False
    )
    continuous = relationship_clauses(initial, owners, operations)
    assert propagate(separate, edges, len(operations)) is not None
    assert propagate(continuous, edges, len(operations)) is None


def generate_moves(
    initial: tuple[int, ...],
    owners: tuple[int | None, ...],
    count: int,
    generator: random.Random,
):
    locations = list(initial)
    generated: list[Operation] = []
    for _ in range(count):
        choices: list[Operation] = []
        for particle, source in enumerate(locations):
            for target in range(len(owners)):
                if target in locations:
                    continue
                changed = locations.copy()
                changed[particle] = target
                if not has_cycle(tuple(changed), owners):
                    choices.append(Operation(particle, source, target))
        operation = generator.choice(choices)
        generated.append(operation)
        assert operation.target is not None
        locations[operation.particle] = operation.target
    for particle, source in enumerate(locations):
        generated.append(Operation(particle, source, None))
    return tuple(generated)


def unrecognized_dead_end(
    initial: tuple[int, ...],
    owners: tuple[int | None, ...],
    operations: tuple[Operation, ...],
):
    exploration = explore(initial, owners, operations)
    bad = set(exploration.transitions) - exploration.completable
    if not bad:
        return None
    clauses = relationship_clauses(initial, owners, operations)
    ordinary = occupancy_edges(operations)
    paths: dict[int, tuple[int, ...]] = {0: ()}
    for completed in sorted(exploration.transitions):
        for operation, following in exploration.transitions[completed].items():
            if following not in paths:
                paths[following] = (*paths[completed], operation)
    for completed in sorted(bad):
        prefix = paths[completed]
        constraints = ordinary | set(itertools.pairwise(prefix))
        for later in range(len(operations)):
            if not completed & (1 << later):
                constraints.add((prefix[-1], later))
        if propagate(clauses, constraints, len(operations)) is not None:
            return prefix
    return None


def test_propagation_rejects_random_dead_ends():
    generator = random.Random(572203)  # noqa: S311 - Reproducible counterexample search.
    owners = (None, None, None, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4)
    for trial in range(400):
        initial = (0, 3, 5, 7, 9) if trial % 2 else (0, 3, 4, 5, 7)
        operations = generate_moves(initial, owners, 14, generator)
        assert unrecognized_dead_end(initial, owners, operations) is None


def test_propagation_alone_can_miss_incompatible_alternatives():
    initial = (0, 3, 4, 11, 7)
    owners = (None, None, None, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4)
    operations = (
        Operation(3, 11, 8),
        Operation(2, 4, 6),
        Operation(0, 0, 1),
        Operation(3, 8, 12),
        Operation(4, 7, 5),
        Operation(4, 5, 8),
        Operation(2, 6, 0),
        Operation(1, 3, 10),
        Operation(2, 0, 3),
        Operation(1, 10, 0),
        Operation(3, 12, 4),
        Operation(0, 1, None),
        Operation(1, 0, None),
        Operation(2, 3, None),
        Operation(3, 4, None),
        Operation(4, 8, None),
    )
    exploration = explore(initial, owners, operations)
    assert 7 in exploration.transitions[0]
    assert (1 << 7) not in exploration.completable
    clauses = relationship_clauses(initial, owners, operations)
    edges = occupancy_edges(operations)
    assert has_completion(clauses, edges, len(operations))
    edges |= {(7, index) for index in range(len(operations)) if index != 7}
    assert propagate(clauses, edges, len(operations)) is not None
    assert not has_completion(clauses, edges, len(operations))


def test_exact_alternative_search_matches_state_exploration():
    generator = random.Random(5291)  # noqa: S311 - Reproducible differential test.
    initial = (0, 3, 4)
    owners = (None, None, None, 0, 1, 2)
    for _ in range(100):
        operations = generate_moves(initial, owners, 7, generator)
        exploration = explore(initial, owners, operations)
        clauses = relationship_clauses(initial, owners, operations)
        ordinary = occupancy_edges(operations)
        parts = choice_parts(initial, owners, operations)
        paths: dict[int, tuple[int, ...]] = {0: ()}
        for completed in sorted(exploration.transitions):
            for operation, following in exploration.transitions[completed].items():
                if following not in paths:
                    paths[following] = (*paths[completed], operation)
        for completed, prefix in paths.items():
            edges = ordinary | set(itertools.pairwise(prefix))
            if prefix:
                for later in range(len(operations)):
                    if not completed & (1 << later):
                        edges.add((prefix[-1], later))
            assert has_completion(clauses, edges, len(operations)) == (
                completed in exploration.completable
            )
            lazy_order, learned = lazy_completion(initial, owners, operations, prefix)
            assert (lazy_order is not None) == (completed in exploration.completable)
            assert len(learned) <= len(clauses)
            assert factored_completion(
                clauses, ordinary, parts, prefix, len(operations)
            ) == (completed in exploration.completable)


def test_source_ordered_suffix_is_not_an_exact_completion_check():
    initial = (0, 3, 4, 5, 7)
    owners = (None, None, None, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4)
    operations = (
        Operation(1, 3, 1),
        Operation(0, 0, 10),
        Operation(2, 4, 6),
        Operation(1, 1, 2),
        Operation(0, 10, 12),
        Operation(2, 6, 10),
        Operation(2, 10, 1),
        Operation(3, 5, 3),
        Operation(3, 3, 6),
        Operation(3, 6, 11),
        Operation(2, 1, 5),
        Operation(4, 7, 0),
        Operation(0, 12, None),
        Operation(1, 2, None),
        Operation(2, 5, None),
        Operation(3, 11, None),
        Operation(4, 0, None),
    )
    exploration = explore(initial, owners, operations)
    prefix = (0, 1, 2, 4, 7)
    completed = follow(exploration, prefix)
    assert completed in exploration.completable
    after_next = exploration.transitions[completed][3]
    assert 5 not in exploration.transitions[after_next]


def test_earliest_currently_executable_operation_can_prevent_completion():
    initial = (0, 3, 5, 7, 9)
    owners = (None, None, None, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4)
    operations = (
        Operation(3, 7, 6),
        Operation(2, 5, 2),
        Operation(2, 2, 5),
        Operation(3, 6, 4),
        Operation(1, 3, 10),
        Operation(1, 10, 2),
        Operation(2, 5, 6),
        Operation(3, 4, 8),
        Operation(4, 9, 1),
        Operation(0, 0, 12),
        Operation(2, 6, 11),
        Operation(1, 2, 7),
        Operation(2, 11, 2),
        Operation(3, 8, 11),
        Operation(0, 12, None),
        Operation(1, 7, None),
        Operation(2, 2, None),
        Operation(3, 11, None),
        Operation(4, 1, None),
    )
    exploration = explore(initial, owners, operations)
    completed = follow(exploration, (1, 9))
    assert completed in exploration.completable
    assert min(exploration.transitions[completed]) == 4
    assert exploration.transitions[completed][4] not in exploration.completable


def test_independent_relationship_choices_have_separate_parts():
    initial = (0, 4, 2, 6)
    owners = (None, None, None, None, 0, 1, 2, 3)
    operations = (
        Operation(1, 4, 1),
        Operation(0, 0, 5),
        Operation(3, 6, 3),
        Operation(2, 2, 7),
        Operation(0, 5, None),
        Operation(1, 1, None),
        Operation(2, 7, None),
        Operation(3, 3, None),
    )
    parts = choice_parts(initial, owners, operations)
    assert parts == [{0, 1, 4, 5}, {2, 3, 6, 7}]
    exploration = explore(initial, owners, operations)
    clauses = relationship_clauses(initial, owners, operations)
    ordinary = occupancy_edges(operations)
    for prefix in ((0,), (2,), (0, 1), (2, 3), (0, 2, 1, 3)):
        assert follow(exploration, prefix) in exploration.completable
        assert factored_completion(clauses, ordinary, parts, prefix, len(operations))
