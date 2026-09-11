from __future__ import annotations

import dataclasses
import enum
import itertools
import random

from operation_graph_optimization import (
    identity_algorithm,
    identity_choice_benchmark,
    precedence_choice,
    relationship_periods,
    relationship_state,
)


class Kind(enum.Enum):
    CREATE = enum.auto()
    MOVE = enum.auto()
    VACATE = enum.auto()
    VANISH = enum.auto()


@dataclasses.dataclass(frozen=True)
class Operation:
    name: str
    kind: Kind
    particle: int
    source: int | None = None
    target: int | None = None
    prerequisites: frozenset[int] = frozenset()


@dataclasses.dataclass(frozen=True)
class State:
    completed: frozenset[int]
    live: frozenset[int]
    vacated: frozenset[int]
    locations: tuple[int | None, ...]


@dataclasses.dataclass
class Example:
    owners: tuple[int | None, ...]
    operations: tuple[Operation, ...]
    retained_uses: dict[int, frozenset[int]]
    observe_move_before_release: bool = True

    def needs(self, operation: Operation):
        particles: set[int] = set()
        if operation.kind != Kind.CREATE:
            particles.add(operation.particle)
        for position in (operation.source, operation.target):
            if position is not None:
                owner = self.owners[position]
                if owner is not None:
                    particles.add(owner)
        return particles

    def cyclic(self, locations: list[int | None]):
        for particle in range(len(locations)):
            visited: set[int] = set()
            current: int | None = particle
            while current is not None:
                if current in visited:
                    return True
                visited.add(current)
                position = locations[current]
                current = None if position is None else self.owners[position]
        return False

    def advance(self, state: State, index: int):
        operation = self.operations[index]
        if index in state.completed or not operation.prerequisites <= state.completed:
            return None
        if not self.needs(operation) <= state.live:
            return None
        locations = list(state.locations)
        live = set(state.live)
        vacated = set(state.vacated)
        completed = state.completed | {index}
        if operation.kind == Kind.CREATE:
            if operation.particle in live or operation.target in locations:
                return None
            live.add(operation.particle)
            locations[operation.particle] = operation.target
        elif operation.kind == Kind.MOVE:
            if locations[operation.particle] != operation.source:
                return None
            if operation.target in locations:
                return None
            locations[operation.particle] = operation.target
        elif operation.kind == Kind.VACATE:
            vacated.add(operation.particle)
        else:
            if operation.particle not in vacated:
                return None
            for following, user in enumerate(self.operations):
                if following not in completed and operation.particle in self.needs(
                    user
                ):
                    return None
            live.remove(operation.particle)
        # The two observations distinguish a Move's occupied result from the
        # state after its last destruction use ends occupancy preservation.
        if self.observe_move_before_release and self.cyclic(locations):
            return None
        for particle in vacated:
            remaining = self.retained_uses.get(particle, frozenset()) - completed
            if not remaining:
                locations[particle] = None
        if self.cyclic(locations):
            return None
        for particle, position in enumerate(locations):
            if position is not None:
                assert particle in live
                owner = self.owners[position]
                assert owner is None or owner in live
        return State(completed, frozenset(live), frozenset(vacated), tuple(locations))


def destructor_example():
    # The local held position and the implied /child position both belong to
    # particle 0; modelling held as an unrelated position misses the cycle.
    return Example(
        owners=(None, 0, 1, None, 2, 0),
        operations=(
            Operation("test.create(parent)", Kind.CREATE, 0, target=0),
            Operation("test.create(parent::/child)", Kind.CREATE, 1, target=1),
            Operation("test.create(parent::/child::/leaf)", Kind.CREATE, 2, target=2),
            Operation("test.move(parent::/child::/leaf, detached)", Kind.MOVE, 2, 2, 3),
            Operation("test.move(parent, detached::/return)", Kind.MOVE, 0, 0, 4),
            Operation("destroy_parent.move(/child, held)", Kind.MOVE, 1, 1, 5),
            Operation("destroy_parent.move(held, /child)", Kind.MOVE, 1, 5, 1),
            Operation("test.vacate(detached::/return::/child)", Kind.VACATE, 1, 1),
            Operation(
                "test.vacate(detached::/return)",
                Kind.VACATE,
                0,
                4,
                prerequisites=frozenset({4}),
            ),
            Operation(
                "test.vacate(detached)",
                Kind.VACATE,
                2,
                3,
                prerequisites=frozenset({3}),
            ),
            Operation("test.vanish(detached::/return::/child)", Kind.VANISH, 1),
            Operation("test.vanish(detached::/return)", Kind.VANISH, 0),
            Operation("test.vanish(detached)", Kind.VANISH, 2),
        ),
        retained_uses={1: frozenset({5, 6})},
    )


def follow(example: Example, order: tuple[int, ...]):
    count = max(operation.particle for operation in example.operations) + 1
    state = State(frozenset(), frozenset(), frozenset(), (None,) * count)
    for index in order:
        following = example.advance(state, index)
        assert following is not None
        state = following
    return state


def helper_destructor_example():
    example = destructor_example()
    example.owners += (0, 3)
    operations = list(example.operations)
    operations[5] = Operation(
        "destroy_parent.move(/child, /helper::/hold)", Kind.MOVE, 1, 1, 7
    )
    operations[6] = Operation(
        "destroy_parent.move(/helper::/hold, /child)", Kind.MOVE, 1, 7, 1
    )
    operations.extend(
        (
            Operation("test.create(parent::/helper)", Kind.CREATE, 3, target=6),
            Operation("test.vacate(detached::/return::/helper)", Kind.VACATE, 3, 6),
            Operation("test.vanish(detached::/return::/helper)", Kind.VANISH, 3),
        )
    )
    example.operations = tuple(operations)
    return example


def joint_cycle_example():
    return Example(
        owners=(None, None, None, 0, 0, 1, 1, 2, 2, None),
        operations=(
            Operation("test.create(first)", Kind.CREATE, 0, target=0),
            Operation("test.create(second)", Kind.CREATE, 1, target=1),
            Operation("test.create(third)", Kind.CREATE, 2, target=2),
            Operation("test.move(third, first::/first_right)", Kind.MOVE, 2, 2, 4),
            Operation("test.move(first, second::/second_right)", Kind.MOVE, 0, 0, 6),
            Operation(
                "test.move(second::/second_right::/first_right, second::/second_left)",
                Kind.MOVE,
                2,
                4,
                5,
            ),
            Operation("test.move(second::/second_left, third)", Kind.MOVE, 2, 5, 2),
            Operation("test.move(second, third::/third_left)", Kind.MOVE, 1, 1, 7),
            Operation(
                "test.move(third::/third_left::/second_right, third::/third_left::/second_left)",
                Kind.MOVE,
                0,
                6,
                5,
            ),
            Operation(
                "test.move(third::/third_left::/second_left, returned_first)",
                Kind.MOVE,
                0,
                5,
                9,
            ),
            Operation(
                "test.move(third::/third_left, returned_first::/first_left)",
                Kind.MOVE,
                1,
                7,
                3,
            ),
            Operation(
                "test.vacate(returned_first)",
                Kind.VACATE,
                0,
                9,
                prerequisites=frozenset({9}),
            ),
            Operation(
                "test.vacate(returned_first::/first_left)",
                Kind.VACATE,
                1,
                3,
                prerequisites=frozenset({10}),
            ),
            Operation(
                "test.vacate(third)", Kind.VACATE, 2, 2, prerequisites=frozenset({6})
            ),
            Operation("test.vanish(returned_first)", Kind.VANISH, 0),
            Operation("test.vanish(returned_first::/first_left)", Kind.VANISH, 1),
            Operation("test.vanish(third)", Kind.VANISH, 2),
        ),
        retained_uses={},
    )


def test_two_cycle_conditions_jointly_imply_a_three_particle_condition():
    example = joint_cycle_example()
    clauses = relationship_periods.cycle_clauses(collect_periods(example))
    edges = mandatory_edges(example)
    required = precedence_choice.necessary_precedences(clauses, edges, 17)
    assert required is not None
    assert len(clauses) == 3
    assert len(clauses[1]) == 6
    negation = precedence_choice.negate_clause(clauses[1])
    # Even all universally required precedences cannot remove this condition
    # alone; its redundancy comes from the other two conditions together.
    assert precedence_choice.completion_order(negation, required, 17) is not None
    assert precedence_choice.completion_order((clauses[0], *negation), required, 17)
    assert precedence_choice.completion_order((clauses[2], *negation), required, 17)
    assert (
        precedence_choice.completion_order(
            (clauses[0], clauses[2], *negation), required, 17
        )
        is None
    )
    assert follow(example, tuple(range(17))).live == frozenset()


def construct_example(example: Example, order: tuple[int, ...]):
    operations: list[identity_algorithm.Operation] = []
    for index in order:
        operation = example.operations[index]
        if operation.kind == Kind.CREATE:
            assert operation.target is not None
            converted = identity_algorithm.Create(
                operation.name, operation.particle, operation.target
            )
        elif operation.kind == Kind.MOVE:
            assert operation.source is not None
            assert operation.target is not None
            converted = identity_algorithm.Move(
                operation.name, operation.particle, operation.source, operation.target
            )
        elif operation.kind == Kind.VACATE:
            assert operation.source is not None
            converted = identity_algorithm.Vacate(
                operation.name, operation.particle, operation.source, 0
            )
        else:
            converted = identity_algorithm.Vanish(operation.name, operation.particle)
        operations.append(converted)
    return identity_algorithm.construct(operations, example.owners)


def test_random_competing_workloads_are_valid_in_the_particle_interpreter():
    for seed in range(20):
        workload = identity_choice_benchmark.generate(5, seed)
        operations: list[Operation] = []
        for operation in workload.operations:
            if isinstance(operation, identity_algorithm.Create):
                converted = Operation(
                    operation.name,
                    Kind.CREATE,
                    operation.particle,
                    target=operation.target,
                )
            elif isinstance(operation, identity_algorithm.Move):
                converted = Operation(
                    operation.name,
                    Kind.MOVE,
                    operation.particle,
                    operation.source,
                    operation.target,
                )
            elif isinstance(operation, identity_algorithm.Vacate):
                converted = Operation(
                    operation.name, Kind.VACATE, operation.particle, operation.position
                )
            else:
                assert isinstance(operation, identity_algorithm.Vanish)
                converted = Operation(operation.name, Kind.VANISH, operation.particle)
            operations.append(converted)
        example = Example(workload.parents, tuple(operations), {})
        current = State(frozenset(), frozenset(), frozenset(), (None,) * 15)
        for index, operation in enumerate(operations):
            # The generator emits an ordinary destruction only after its
            # selected particle has reached the stated source position.
            if operation.kind == Kind.VACATE:
                assert current.locations[operation.particle] == operation.source
            following = example.advance(current, index)
            assert following is not None
            current = following
        assert current.live == frozenset()
        assert current.completed == frozenset(range(len(operations)))


def test_identity_construction_matches_endpoint_lifetime_and_cycle_requirements():
    cases = [
        (destructor_example(), (0, 1, 2, 3, 4, 7, 8, 9, 5, 6, 10, 11, 12)),
        (
            helper_destructor_example(),
            (0, 1, 2, 13, 3, 4, 7, 8, 9, 14, 5, 6, 10, 15, 11, 12),
        ),
        (joint_cycle_example(), tuple(range(17))),
    ]
    generator = random.Random(710013)  # noqa: S311 - Reproducible finite exploration.
    for _ in range(40):
        example = generated_example(generator)
        ordinary: list[int] = []
        destruction: list[int] = []
        vanishes: list[int] = []
        for index, operation in enumerate(example.operations):
            if operation.kind == Kind.VANISH:
                vanishes.append(index)
            elif operation.name.startswith("destructor."):
                destruction.append(index)
            else:
                ordinary.append(index)
        cases.append((example, tuple(ordinary + destruction + vanishes)))
    for example, order in cases:
        assert follow(example, order).live == frozenset()
        constructed = construct_example(example, order)
        count = len(example.operations)
        indexed = relationship_state.PartitionedSearch(
            constructed.periods,
            constructed.dependencies.dependencies,
            constructed.dependencies.indexed_dependents,
        )
        assert indexed.has_completion(0)
        expected_consumers: list[set[int]] = [set() for _ in constructed.operations]
        for later, operation in enumerate(constructed.operations):
            if isinstance(operation, identity_algorithm.Vanish):
                continue
            for earlier in constructed.dependencies.dependencies(later):
                expected_consumers[earlier].add(later)
        for earlier, operation in enumerate(constructed.operations):
            if isinstance(operation, identity_algorithm.Vanish):
                continue
            assert (
                set(constructed.dependencies.indexed_dependents(earlier))
                == (expected_consumers[earlier])
            )
        original = {
            operation.name: index for index, operation in enumerate(example.operations)
        }
        reordered = [original[operation.name] for operation in constructed.operations]
        actual_edges: set[precedence_choice.Precedence] = set()
        for later in range(count):
            for earlier in constructed.dependencies.dependencies(later):
                actual_edges.add((reordered[earlier], reordered[later]))
        expected_edges = mandatory_edges(example)
        assert precedence_choice.closure(
            actual_edges, count
        ) == precedence_choice.closure(expected_edges, count)
        actual_clauses: list[precedence_choice.Clause] = []
        for clause in relationship_periods.cycle_clauses(constructed.periods):
            alternatives: list[precedence_choice.Alternative] = []
            for alternative in clause:
                alternatives.append(
                    frozenset(
                        (reordered[earlier], reordered[later])
                        for earlier, later in alternative
                    )
                )
            actual_clauses.append(tuple(alternatives))
        expected_clauses = relationship_periods.cycle_clauses(collect_periods(example))
        for clause in actual_clauses:
            assert (
                precedence_choice.completion_order(
                    expected_clauses + precedence_choice.negate_clause(clause),
                    expected_edges,
                    count,
                )
                is None
            )
        for clause in expected_clauses:
            assert (
                precedence_choice.completion_order(
                    tuple(actual_clauses) + precedence_choice.negate_clause(clause),
                    actual_edges,
                    count,
                )
                is None
            )


def test_specialized_runtime_permissions_match_every_reachable_state():
    example = Example(
        (None, 0, None, None, 2, 1),
        (
            Operation("create(parent)", Kind.CREATE, 0, target=0),
            Operation("create(parent::/child)", Kind.CREATE, 1, target=1),
            Operation("create(third)", Kind.CREATE, 2, target=2),
            Operation("move(child, detached_child)", Kind.MOVE, 1, 1, 3),
            Operation("move(parent, third::/end)", Kind.MOVE, 0, 0, 4),
            Operation("move(third, child::/inner)", Kind.MOVE, 2, 2, 5),
            Operation(
                "vacate(parent)", Kind.VACATE, 0, source=4, prerequisites=frozenset({4})
            ),
            Operation(
                "vacate(child)", Kind.VACATE, 1, source=3, prerequisites=frozenset({3})
            ),
            Operation(
                "vacate(third)", Kind.VACATE, 2, source=5, prerequisites=frozenset({5})
            ),
            Operation("vanish(parent)", Kind.VANISH, 0),
            Operation("vanish(child)", Kind.VANISH, 1),
            Operation("vanish(third)", Kind.VANISH, 2),
        ),
        {},
    )
    required: dict[int, set[int]] = {
        3: set(),
        4: set(),
        5: set(),
        6: {4},
        7: {3},
        8: {5},
        9: {3, 6},
        10: {7, 8},
        11: {6, 8},
    }
    initial = follow(example, (0, 1, 2))
    states = {initial.completed: initial}
    pending = [initial]
    while pending:
        state = pending.pop()
        for operation in range(3, 12):
            if operation in state.completed:
                continue
            permitted = required[operation] <= state.completed
            if operation == 4:
                permitted = permitted and (
                    3 in state.completed
                    or 5 not in state.completed
                    or 8 in state.completed
                )
            elif operation == 5:
                permitted = permitted and (
                    3 in state.completed
                    or 4 not in state.completed
                    or 6 in state.completed
                )
            following = example.advance(state, operation)
            assert permitted == (following is not None)
            if following is not None and following.completed not in states:
                states[following.completed] = following
                pending.append(following)
    assert frozenset(range(12)) in states


def test_alternative_paths_force_a_precedence_without_a_fixed_intermediate():
    # Either complete Move excursion can run first. Both begin by leaving R,
    # and both end in positions defined by H. Thus H must be created before R
    # can Vanish, but neither excursion supplies a fixed intermediate event.
    operations: list[identity_algorithm.Operation] = [
        identity_algorithm.Create("create(parent)", 0, 0),
        identity_algorithm.Create("create(parent::/p)", 1, 1),
        identity_algorithm.Create("create(parent::/q)", 2, 2),
        identity_algorithm.Move("move(p, q::/child)", 1, 1, 4),
        identity_algorithm.Create("create(helper)", 3, 5),
        identity_algorithm.Move("move(q::/child, helper::/left)", 1, 4, 6),
        identity_algorithm.Move("move(q, p::/child)", 2, 2, 3),
        identity_algorithm.Move("move(p::/child, helper::/right)", 2, 3, 7),
        identity_algorithm.Vacate("vacate(parent)", 0, 0, 0),
        identity_algorithm.Vacate("vacate(helper)", 3, 5, 1),
        identity_algorithm.Vacate("vacate(helper::/left)", 1, 6, 1),
        identity_algorithm.Vacate("vacate(helper::/right)", 2, 7, 1),
        identity_algorithm.Vanish("vanish(parent)", 0),
        identity_algorithm.Vanish("vanish(helper)", 3),
        identity_algorithm.Vanish("vanish(helper::/left)", 1),
        identity_algorithm.Vanish("vanish(helper::/right)", 2),
    ]
    constructed = identity_algorithm.construct(
        operations, (None, 0, 0, 1, 2, None, 3, 3)
    )
    edges: set[precedence_choice.Precedence] = set()
    for later in range(len(operations)):
        for earlier in constructed.dependencies.dependencies(later):
            edges.add((earlier, later))
    clauses = relationship_periods.cycle_clauses(constructed.periods)
    assert clauses == ((frozenset({(5, 6)}), frozenset({(7, 3)})),)
    required = precedence_choice.necessary_precedences(clauses, edges, len(operations))
    assert required is not None
    assert (4, 12) in required
    assert (4, 12) not in precedence_choice.closure(edges, len(operations))
    for intermediate in range(len(operations)):
        assert not ((4, intermediate) in required and (intermediate, 12) in required)


def test_relationship_can_continue_beyond_the_collected_graph():
    operations: list[identity_algorithm.Operation] = [
        identity_algorithm.Create("create(parent)", 0, 0),
        identity_algorithm.Create("create(parent::/child)", 1, 1),
    ]
    constructed = identity_algorithm.construct(operations, (None, 0))
    assert constructed.periods == [
        [],
        [relationship_periods.Period(parent=0, beginning=1, ending=None)],
    ]
    assert relationship_periods.completion_order(constructed.periods, {(0, 1)}, 2) == (
        0,
        1,
    )
    # An unended relationship cannot be used as the ending alternative that
    # permits a later reverse relationship.
    cyclic_periods = [
        [relationship_periods.Period(parent=1, beginning=2, ending=None)],
        constructed.periods[1],
    ]
    assert (
        relationship_periods.completion_order(cyclic_periods, {(0, 1), (1, 2)}, 3)
        is None
    )


def test_initial_parent_relationship_orders_a_later_reverse_relationship():
    # The child already occupies the parent's position at this graph boundary.
    # There is no beginning event that could be delayed instead of detachment.
    periods = [
        [relationship_periods.Period(1, 0, None)],
        [relationship_periods.Period(0, None, (1, 2))],
    ]
    assert relationship_periods.cycle_clauses(periods) == (
        (frozenset({(1, 0), (2, 0)}),),
    )
    assert relationship_periods.completion_order(periods, set(), 3) == (1, 2, 0)
    assert relationship_periods.completion_order(periods, {(0, 1)}, 3) is None
    assert relationship_periods.completion_order(periods, {(0, 2)}, 3) is None
    assert relationship_periods.first_violation(periods, (1, 2, 0)) is None
    assert relationship_periods.first_violation(periods, (2, 1, 0)) is None
    assert relationship_periods.first_violation(periods, (1, 0, 2)) is not None
    assert relationship_periods.first_violation(periods, (2, 0, 1)) is not None
    assert relationship_state.Search(periods, set(), 3).completion() == (1, 2, 0)
    assert relationship_state.Search(periods, {(0, 1)}, 3).completion() is None
    assert relationship_state.Search(periods, {(0, 2)}, 3).completion() is None


def test_completed_set_search_backtracks_from_an_acyclic_dead_end():
    # This is the future_moves_must_remain_executable source situation. Moving
    # parent before visitor's two Moves prevents either visit from completing.
    example = Example(
        owners=(None, None, None, 0, 1, 2),
        operations=(
            Operation("create(parent)", Kind.CREATE, 0, target=0),
            Operation("create(other)", Kind.CREATE, 1, target=1),
            Operation("create(visitor)", Kind.CREATE, 2, target=2),
            Operation("move(visitor, parent::/landing)", Kind.MOVE, 2, 2, 3),
            Operation("move(parent::/landing, other::/landing)", Kind.MOVE, 2, 3, 4),
            Operation("move(parent, visitor::/inner)", Kind.MOVE, 0, 0, 5),
            Operation("move(other, visitor)", Kind.MOVE, 1, 1, 2),
            Operation("move(visitor::/inner, other)", Kind.MOVE, 0, 5, 1),
            Operation(
                "vacate(parent)", Kind.VACATE, 0, 1, prerequisites=frozenset({7})
            ),
            Operation("vacate(other)", Kind.VACATE, 1, 2, prerequisites=frozenset({6})),
            Operation(
                "vacate(visitor)", Kind.VACATE, 2, 4, prerequisites=frozenset({4})
            ),
            Operation("vanish(parent)", Kind.VANISH, 0),
            Operation("vanish(other)", Kind.VANISH, 1),
            Operation("vanish(visitor)", Kind.VANISH, 2),
        ),
        retained_uses={},
    )
    initial = follow(example, (0, 1, 2))
    assert example.advance(initial, 5) is not None
    periods = collect_periods(example)
    edges = mandatory_edges(example)
    search = relationship_state.Search(periods, edges, len(example.operations))
    assert search.completion(7 | (1 << 5)) is None
    certificate = search.completion()
    assert certificate is not None
    assert follow(example, certificate).live == frozenset()

    # Give the tempting but incorrect Move the lowest operation number. A
    # successful search must not depend on trying serial source order first.
    permutation = (5, 0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13)
    indices = {original: index for index, original in enumerate(permutation)}
    relabeled: list[list[relationship_periods.Period]] = []
    for relationships in periods:
        converted: list[relationship_periods.Period] = []
        for period in relationships:
            assert period.beginning is not None
            assert period.ending is not None
            converted.append(
                relationship_periods.Period(
                    period.parent,
                    indices[period.beginning],
                    tuple(indices[ending] for ending in period.ending),
                )
            )
        relabeled.append(converted)
    relabeled_edges = {(indices[earlier], indices[later]) for earlier, later in edges}
    search = relationship_state.Search(relabeled, relabeled_edges, len(permutation))
    certificate = search.completion()
    assert certificate is not None
    original_order = tuple(permutation[operation] for operation in certificate)
    assert follow(example, original_order).live == frozenset()
    assert -1 in search.choices.values()


def test_interface_reuse_does_not_reuse_another_executions_local_position():
    operations: list[identity_algorithm.Operation] = [
        identity_algorithm.Create("create(gateway)", 0, 0),
        identity_algorithm.Create("create(item)", 1, 1),
        identity_algorithm.Move("worker.move(item, held)", 1, 1, 2),
        identity_algorithm.Vacate("worker.vacate(held)", 1, 2, 1),
        identity_algorithm.Create("create(item)#2", 2, 1),
        identity_algorithm.Move("worker#2.move(item, held)", 2, 1, 3),
        identity_algorithm.Vacate("worker#2.vacate(held)", 2, 3, 2),
        identity_algorithm.Vacate("vacate(gateway)", 0, 0, 0),
        identity_algorithm.Vanish("worker.vanish(held)", 1),
        identity_algorithm.Vanish("worker#2.vanish(held)", 2),
        identity_algorithm.Vanish("vanish(gateway)", 0),
    ]
    constructed = identity_algorithm.construct(operations, (None, 0, 0, 0))
    dependencies = [
        list(constructed.dependencies.dependencies(index)) for index in range(11)
    ]
    assert [set(previous) for previous in dependencies] == [
        set(),
        {0},
        {1},
        {2},
        {2},
        {4},
        {5},
        {0},
        {3},
        {6},
        {3, 6, 7},
    ]


def test_nested_destruction_releases_a_surviving_particles_position_for_reuse():
    operations: list[identity_algorithm.Operation] = [
        identity_algorithm.Create("create(parent)", 0, 0),
        identity_algorithm.Vacate("vacate(parent)", 0, 0, 0),
        identity_algorithm.Create("destructor.create(/temporary)", 1, 1),
        identity_algorithm.Vacate("destructor.vacate(/temporary)", 1, 1, 1),
        identity_algorithm.Create("destructor.create(/temporary)#2", 2, 1),
        identity_algorithm.Vacate("destructor.vacate(/temporary)#2", 2, 1, 2),
        identity_algorithm.Vanish("destructor.vanish(/temporary)", 1),
        identity_algorithm.Vanish("destructor.vanish(/temporary)#2", 2),
        identity_algorithm.Vanish("vanish(parent)", 0),
    ]
    constructed = identity_algorithm.construct(operations, (None, 0))
    dependencies = [
        set(constructed.dependencies.dependencies(index)) for index in range(9)
    ]
    # The parent belongs to a different destruction. Its /temporary is reused,
    # so the first temporary Vacate supplies the second Create's vacancy.
    assert dependencies == [set(), {0}, {0}, {2}, {3}, {4}, {3}, {5}, {1, 5}]


def test_two_relationship_excursions_have_disconnected_safe_orders():
    example = Example(
        owners=(None, None, 0, 1),
        operations=(
            Operation("test.create(first)", Kind.CREATE, 0, target=0),
            Operation("test.create(second)", Kind.CREATE, 1, target=1),
            Operation("test.move(first, second::/child)", Kind.MOVE, 0, 0, 3),
            Operation("test.move(second::/child, first)", Kind.MOVE, 0, 3, 0),
            Operation("test.move(second, first::/child)", Kind.MOVE, 1, 1, 2),
            Operation("test.move(first::/child, second)", Kind.MOVE, 1, 2, 1),
            Operation(
                "test.vacate(first)", Kind.VACATE, 0, 0, prerequisites=frozenset({3})
            ),
            Operation(
                "test.vacate(second)", Kind.VACATE, 1, 1, prerequisites=frozenset({5})
            ),
            Operation("test.vanish(first)", Kind.VANISH, 0),
            Operation("test.vanish(second)", Kind.VANISH, 1),
        ),
        retained_uses={},
    )
    initial = follow(example, (0, 1))
    accepted: set[tuple[int, ...]] = set()
    for order in itertools.permutations(range(2, 6)):
        state = initial
        for index in order:
            following = example.advance(state, index)
            if following is None:
                break
            state = following
        else:
            accepted.add(order)
    assert accepted == {(2, 3, 4, 5), (4, 5, 2, 3)}
    # No single adjacent exchange connects the two orders. Intermediate
    # invalid arrangements cannot be used to justify a concurrency proof.
    for order in accepted:
        for index in range(3):
            exchanged = list(order)
            exchanged[index], exchanged[index + 1] = (
                exchanged[index + 1],
                exchanged[index],
            )
            assert tuple(exchanged) not in accepted
    clauses = relationship_periods.cycle_clauses(collect_periods(example))
    edges = mandatory_edges(example)
    assert precedence_choice.completion_order(clauses, edges | {(3, 4)}, 10) is not None
    assert precedence_choice.completion_order(clauses, edges | {(5, 2)}, 10) is not None
    assert (
        precedence_choice.completion_order(clauses, edges | {(2, 5), (4, 3)}, 10)
        is None
    )
    assert follow(example, (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)).live == frozenset()
    assert follow(example, (0, 1, 4, 5, 7, 2, 3, 6, 8, 9)).live == frozenset()


def mandatory_edges(example: Example):
    creates: dict[int, int] = {}
    vanishes: dict[int, int] = {}
    edges: set[precedence_choice.Precedence] = set()
    for index, operation in enumerate(example.operations):
        if operation.kind == Kind.CREATE:
            creates[operation.particle] = index
        elif operation.kind == Kind.VANISH:
            vanishes[operation.particle] = index
    setters: dict[int, int] = {}
    for index, operation in enumerate(example.operations):
        for previous in operation.prerequisites:
            edges.add((previous, index))
        if operation.kind != Kind.VANISH:
            for particle in example.needs(operation):
                edges.add((creates[particle], index))
                edges.add((index, vanishes[particle]))
            if operation.kind == Kind.CREATE:
                edges.add((index, vanishes[operation.particle]))
        if operation.kind == Kind.VANISH or (
            operation.kind == Kind.VACATE
            and operation.particle in example.retained_uses
        ):
            continue
        for position in (operation.source, operation.target):
            if position is not None:
                if position in setters:
                    edges.add((setters[position], index))
                setters[position] = index
    return edges


def collect_periods(example: Example):
    count = max(operation.particle for operation in example.operations) + 1
    periods: list[list[relationship_periods.Period]] = [[] for _ in range(count)]
    current: list[tuple[int, int] | None] = [None] * count
    vacates: dict[int, int] = {}
    for index, operation in enumerate(example.operations):
        particle = operation.particle
        if operation.kind == Kind.VACATE:
            vacates[particle] = index
        if operation.kind not in (Kind.CREATE, Kind.MOVE):
            continue
        assert operation.target is not None
        parent = example.owners[operation.target]
        previous = current[particle]
        if previous is not None:
            beginning, old_parent = previous
            if old_parent == parent:
                continue
            periods[particle].append(
                relationship_periods.Period(old_parent, beginning, (index,))
            )
        current[particle] = None if parent is None else (index, parent)
    for particle, previous in enumerate(current):
        if previous is not None:
            beginning, parent = previous
            ending = example.retained_uses.get(particle, frozenset()) | {
                vacates[particle]
            }
            periods[particle].append(
                relationship_periods.Period(parent, beginning, tuple(ending))
            )
    return periods


def test_collected_periods_match_all_helper_example_prefixes():
    example = helper_destructor_example()
    edges = mandatory_edges(example)
    clauses = relationship_periods.cycle_clauses(collect_periods(example))
    initial = State(frozenset(), frozenset(), frozenset(), (None, None, None, None))
    states = {initial.completed: initial}
    pending = [initial]
    while pending:
        state = pending.pop()
        for index in range(len(example.operations)):
            if index in state.completed:
                continue
            prefix_edges = edges.copy()
            for finished in state.completed:
                prefix_edges.add((finished, index))
            for unfinished in range(len(example.operations)):
                if unfinished not in state.completed and unfinished != index:
                    prefix_edges.add((index, unfinished))
            possible = precedence_choice.completion_order(
                clauses, prefix_edges, len(example.operations)
            )
            discovered = relationship_periods.completion_order(
                collect_periods(example), prefix_edges, len(example.operations)
            )
            assert (discovered is not None) == (possible is not None)
            following = example.advance(state, index)
            assert (following is not None) == (possible is not None)
            if following is not None and following.completed not in states:
                states[following.completed] = following
                pending.append(following)


def generated_example(generator: random.Random, move_count: int = 4):
    owners: tuple[int | None, ...] = (None, None, None, 0, 0, 1, 1, 2, 2)
    operations = [
        Operation(f"create({particle})", Kind.CREATE, particle, target=particle)
        for particle in range(3)
    ]
    example = Example(owners, (), {})
    locations = [0, 1, 2]
    setters = {particle: particle for particle in range(3)}
    direct = list(range(3))
    for _ in range(move_count):
        choices: list[tuple[int, int]] = []
        for particle in range(3):
            for target in range(len(owners)):
                if target in locations:
                    continue
                changed: list[int | None] = list(locations)
                changed[particle] = target
                if not example.cyclic(changed):
                    choices.append((particle, target))
        particle, target = generator.choice(choices)
        source = locations[particle]
        required = {setters[source]}
        if target in setters:
            required.add(setters[target])
        index = len(operations)
        operations.append(
            Operation(
                f"move({index})",
                Kind.MOVE,
                particle,
                source,
                target,
                frozenset(required),
            )
        )
        locations[particle] = target
        setters[source] = index
        setters[target] = index
        direct[particle] = index
    for particle, source in enumerate(locations):
        parent = owners[source]
        if parent is None:
            continue
        choices = []
        for target in range(len(owners)):
            if target in locations:
                continue
            changed = list(locations)
            changed[particle] = target
            if not example.cyclic(changed):
                choices.append((particle, target))
        _, target = generator.choice(choices)
        first = len(operations)
        required = {setters[source]}
        if target in setters:
            required.add(setters[target])
        operations.extend(
            (
                Operation(
                    f"destructor.move({first})",
                    Kind.MOVE,
                    particle,
                    source,
                    target,
                    frozenset(required),
                ),
                Operation(
                    f"destructor.move({first + 1})",
                    Kind.MOVE,
                    particle,
                    target,
                    source,
                    frozenset({first}),
                ),
            )
        )
        example.retained_uses[particle] = frozenset({first, first + 1})
        setters[source] = first + 1
        setters[target] = first + 1
        break
    for particle, source in enumerate(locations):
        operations.append(
            Operation(
                f"vacate({particle})",
                Kind.VACATE,
                particle,
                source,
                prerequisites=frozenset({direct[particle]}),
            )
        )
    for particle in range(3):
        operations.append(Operation(f"vanish({particle})", Kind.VANISH, particle))
    example.operations = tuple(operations)
    return example


def test_generated_create_move_destruction_periods_match_completion():
    generator = random.Random(931571)  # noqa: S311 - Reproducible bounded exploration.
    for _ in range(40):
        example = generated_example(generator)
        edges = mandatory_edges(example)
        periods = collect_periods(example)
        clauses = relationship_periods.cycle_clauses(periods)
        moves = {
            index
            for index, operation in enumerate(example.operations)
            if operation.kind == Kind.MOVE
        }
        guarded = relationship_periods.guarded_moves(periods, moves)
        state_search = relationship_state.Search(
            periods, edges, len(example.operations)
        )
        divided_search = relationship_state.PartitionedSearch.from_edges(periods, edges)
        predecessors: list[set[int]] = [set() for _ in example.operations]
        for earlier, later in edges:
            predecessors[later].add(earlier)
        last_use_periods: list[list[relationship_periods.Period]] = []
        for particle_periods in periods:
            shortened: list[relationship_periods.Period] = []
            for period in particle_periods:
                destruction_moves: list[int] = []
                other_events: set[int] = set()
                assert period.ending is not None
                for ending in period.ending:
                    if example.operations[ending].kind == Kind.MOVE:
                        destruction_moves.append(ending)
                    else:
                        other_events.add(ending)
                if destruction_moves:
                    other_events.add(max(destruction_moves))
                shortened.append(
                    dataclasses.replace(period, ending=tuple(other_events))
                )
            last_use_periods.append(shortened)
        initial = State(frozenset(), frozenset(), frozenset(), (None, None, None))
        states = {initial.completed: initial}
        pending = [initial]
        successors: dict[frozenset[int], list[frozenset[int]]] = {}
        while pending:
            state = pending.pop()
            following_sets: list[frozenset[int]] = []
            for index in range(len(example.operations)):
                following = example.advance(state, index)
                if following is not None:
                    following_sets.append(following.completed)
                    if following.completed not in states:
                        states[following.completed] = following
                        pending.append(following)
                    else:
                        assert states[following.completed] == following
            successors[state.completed] = following_sets
        full = frozenset(range(len(example.operations)))
        assert full in states
        completable = {full}
        for completed in sorted(states, key=len, reverse=True):
            if any(following in completable for following in successors[completed]):
                completable.add(completed)
        for completed, state in states.items():
            completed_bits = sum(1 << operation for operation in completed)
            suffix = state_search.completion(completed_bits)
            assert (suffix is not None) == (completed in completable)
            assert divided_search.has_completion(completed_bits) == (
                completed in completable
            )
            if suffix is not None:
                current = state
                for operation in suffix:
                    following = example.advance(current, operation)
                    assert following is not None
                    current = following
                assert current.completed == full
            prefix_edges = edges.copy()
            for finished in completed:
                for unfinished in range(len(example.operations)):
                    if unfinished not in completed:
                        prefix_edges.add((finished, unfinished))
            possible = precedence_choice.completion_order(
                clauses, prefix_edges, len(example.operations)
            )
            assert (possible is not None) == (completed in completable)
            discovered = relationship_periods.completion_order(
                last_use_periods, prefix_edges, len(example.operations)
            )
            assert (discovered is not None) == (completed in completable)
            if discovered is not None:
                assert follow(example, discovered).live == frozenset()
            if completed in completable:
                for index in range(len(example.operations)):
                    if index in completed or index in guarded:
                        continue
                    if predecessors[index] <= completed:
                        assert example.advance(state, index) is not None
                        assert completed | {index} in completable


def test_final_move_observation_changes_the_allowed_schedule():
    example = helper_destructor_example()
    prefix = (0, 1, 2, 13, 14, 7, 5, 4)
    state = follow(example, prefix)
    assert example.advance(state, 6) is None
    ordinary_first = follow(example, (*prefix, 3, 6, 8, 9, 10, 15, 11, 12))
    after_release = dataclasses.replace(example, observe_move_before_release=False)
    destructor_first = follow(after_release, (*prefix, 6, 3, 8, 9, 10, 15, 11, 12))
    assert ordinary_first == destructor_first


def test_parent_vacate_can_permit_the_destructor_return_before_the_leaf_move():
    example = helper_destructor_example()
    prefix = (0, 1, 2, 13, 14, 7, 5, 4, 8)
    state = follow(example, prefix)
    assert example.advance(state, 6) is not None
    final = follow(example, (*prefix, 6, 3, 9, 10, 15, 11, 12))
    assert final.live == frozenset()
    assert final.locations == (None, None, None, None)


def test_last_destructor_use_can_release_occupancy_before_vanish():
    example = destructor_example()
    ordinary_first = follow(example, (0, 1, 2, 7, 5, 6, 3, 4, 8, 9, 10, 11, 12))
    parent_first = follow(example, (0, 1, 2, 7, 5, 6, 4, 3, 8, 9, 10, 11, 12))
    assert ordinary_first == parent_first
    assert parent_first.live == frozenset()
    assert parent_first.locations == (None, None, None)


def test_child_position_use_protects_existence_not_old_occupancy():
    example = destructor_example()
    state = follow(example, (0, 1, 2, 7, 5, 6))
    assert state.locations == (0, None, 2)
    assert example.advance(state, 10) is None
    assert example.advance(state, 4) is not None


def test_same_parent_move_does_not_release_retained_relationship():
    example = destructor_example()
    state = follow(example, (0, 1, 2, 7, 5))
    assert example.advance(state, 4) is None


def test_last_destructor_use_without_vacate_does_not_release_occupancy():
    example = destructor_example()
    state = follow(example, (0, 1, 2, 5, 6))
    assert example.advance(state, 4) is None


def test_sharing_destructors_must_both_finish_occupancy_use():
    example = destructor_example()
    example.owners += (0,)
    extra_operations = (
        Operation("other_destructor.move(/child, held)", Kind.MOVE, 1, 1, 6),
        Operation("other_destructor.move(held, /child)", Kind.MOVE, 1, 6, 1),
    )
    example.operations += extra_operations
    example.retained_uses[1] = frozenset({5, 6, 13, 14})
    state = follow(example, (0, 1, 2, 7, 5, 6))
    assert example.advance(state, 4) is None
    state = follow(example, (0, 1, 2, 7, 5, 6, 13, 14))
    assert example.advance(state, 4) is not None


def test_all_reachable_prefixes_match_the_relationship_alternative():
    example = destructor_example()
    initial = State(frozenset(), frozenset(), frozenset(), (None, None, None))
    states = {initial.completed: initial}
    pending = [initial]
    while pending:
        state = pending.pop()
        # Once all particles exist, only the relationship condition remains
        # for the parent Move. Particle lifetimes forbid their early Vanishes.
        if {0, 1, 2} <= state.completed and 4 not in state.completed:
            released = 3 in state.completed or {6, 7} <= state.completed
            assert (example.advance(state, 4) is not None) == released
        for index in range(len(example.operations)):
            following = example.advance(state, index)
            if following is not None:
                previous = states.get(following.completed)
                if previous is None:
                    states[following.completed] = following
                    pending.append(following)
                else:
                    assert previous == following
    assert frozenset(range(len(example.operations))) in states


def test_join_clause_matches_every_complete_order_of_the_example():
    example = destructor_example()
    # These are the example's endpoint and lifetime requirements, without
    # any relationship ordering. The state model independently checks them
    # by inspecting occupancy, existence, and future uses.
    edges: set[precedence_choice.Precedence] = {
        (0, 1),
        (1, 2),
        (2, 3),
        (2, 4),
        (1, 5),
        (5, 6),
        (1, 7),
        (4, 8),
        (3, 9),
        (7, 10),
        (3, 10),
        (6, 10),
        (8, 11),
        (7, 11),
        (6, 11),
        (9, 12),
        (8, 12),
    }
    clauses = ((frozenset({(3, 4)}), frozenset({(7, 4), (6, 4)})),)
    initial = State(frozenset(), frozenset(), frozenset(), (None, None, None))
    states = {initial.completed: initial}
    pending = [initial]
    while pending:
        state = pending.pop()
        for index in range(len(example.operations)):
            if index in state.completed:
                continue
            prefix_edges = edges.copy()
            for finished in state.completed:
                prefix_edges.add((finished, index))
            for unfinished in range(len(example.operations)):
                if unfinished not in state.completed and unfinished != index:
                    prefix_edges.add((index, unfinished))
            possible = precedence_choice.completion_order(
                clauses, prefix_edges, len(example.operations)
            )
            following = example.advance(state, index)
            assert (following is not None) == (possible is not None)
            if following is not None and following.completed not in states:
                states[following.completed] = following
                pending.append(following)
