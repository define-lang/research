from __future__ import annotations

import itertools
import random

from operation_graph_optimization import relationship_exclusion
from operation_graph_optimization.complete import graph


def make_graph(count: int, edges: set[tuple[int, int]]):
    calculated = graph.Graph()
    for later in range(count):
        predecessors: list[int] = []
        for earlier in range(later):
            if (earlier, later) in edges:
                predecessors.append(earlier)
        _ = calculated.append(predecessors)
    return calculated


def precedes(order: tuple[int, ...], earlier: int, later: int):
    return order.index(earlier) < order.index(later)


def check_orders(count: int, edges: set[tuple[int, int]], ends: tuple[int, ...]):
    first, first_end, second, second_end = ends
    alternatives = relationship_exclusion.collect(
        make_graph(count, edges), first, (first_end,), second, (second_end,)
    )
    witnesses: set[int] = set()
    for order in itertools.permutations(range(count)):
        if not all(precedes(order, earlier, later) for earlier, later in edges):
            continue
        separated = precedes(order, first_end, second) or precedes(
            order, second_end, first
        )
        accepted = not alternatives or any(
            all(precedes(order, earlier, later) for earlier, later in alternative)
            for alternative in alternatives
        )
        assert accepted == separated
        if separated:
            for index, alternative in enumerate(alternatives):
                if all(
                    precedes(order, earlier, later) for earlier, later in alternative
                ):
                    witnesses.add(index)
    assert witnesses == set(range(len(alternatives)))


def test_every_four_event_dependency_graph():
    optional = ((0, 2), (0, 3), (1, 2), (1, 3))
    for mask in range(1 << len(optional)):
        edges = {(0, 1), (2, 3)}
        for index, edge in enumerate(optional):
            if mask & (1 << index):
                edges.add(edge)
        check_orders(4, edges, (0, 1, 2, 3))


def test_dependencies_through_other_operations():
    generator = random.Random(803217)  # noqa: S311 - Reproducible graph coverage.
    for _ in range(100):
        edges = {(0, 2), (3, 5)}
        for earlier, later in itertools.combinations(range(6), 2):
            if generator.randrange(3) == 0:
                edges.add((earlier, later))
        check_orders(6, edges, (0, 2, 3, 5))


def test_future_visit_cannot_be_blocked_by_its_own_required_predecessor():
    # In future_moves_must_remain_executable, visitor's visit ends at B.
    # Parent's reverse relationship cannot end at E until A has executed.
    # Thus the reverse ordering E before A is unavailable, and B must precede C.
    edges = {(0, 1), (0, 3), (2, 4), (3, 4)}
    assert relationship_exclusion.collect(make_graph(5, edges), 0, (1,), 2, (4,)) == (
        ((1, 2),),
    )


def test_initial_relationship_cannot_run_after_its_reverse():
    assert relationship_exclusion.collect(
        make_graph(3, {(1, 2)}), None, (0,), 1, (2,)
    ) == (((0, 1),),)


def test_relationship_without_an_end_cannot_run_first():
    assert relationship_exclusion.collect(
        make_graph(3, {(0, 1)}), 0, (1,), 2, None
    ) == (((1, 2),),)


def test_joined_end_requires_both_independent_operations():
    calculated = make_graph(6, {(0, 1), (0, 2), (3, 4), (3, 5)})
    assert relationship_exclusion.collect(calculated, 0, (1, 2), 3, (4, 5)) == (
        ((1, 3), (2, 3)),
        ((4, 0), (5, 0)),
    )


def test_one_blocked_member_prevents_the_reverse_join():
    calculated = make_graph(6, {(0, 1), (0, 2), (3, 4), (3, 5), (0, 5)})
    assert relationship_exclusion.collect(calculated, 0, (1, 2), 3, (4, 5)) == (
        ((1, 3), (2, 3)),
    )


def test_existing_precedence_supplies_part_of_a_join():
    calculated = make_graph(6, {(0, 1), (0, 2), (3, 4), (3, 5), (1, 3)})
    assert relationship_exclusion.collect(calculated, 0, (1, 2), 3, (4, 5)) == (
        ((2, 3),),
    )


def test_ordered_endings_need_only_the_last_operation():
    calculated = make_graph(6, {(0, 1), (1, 2), (3, 4), (4, 5)})
    assert relationship_exclusion.collect(calculated, 0, (1, 2), 3, (4, 5)) == (
        ((2, 3),),
        ((5, 0),),
    )
