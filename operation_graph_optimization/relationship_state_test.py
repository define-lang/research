from __future__ import annotations

import pytest

from operation_graph_optimization import (
    precedence_choice,
    relationship_periods,
    relationship_state,
)


def independent_periods():
    return [
        [relationship_periods.Period(1, 0, (1,))],
        [relationship_periods.Period(0, 2, (3,))],
        [relationship_periods.Period(3, 4, (5,))],
        [relationship_periods.Period(2, 6, (7,))],
    ]


@pytest.mark.parametrize("couple_choices", [False, True])
def test_partitions_match_full_search_for_every_legal_prefix(*, couple_choices: bool):
    periods = independent_periods()
    edges = {(0, 1), (2, 3), (4, 5), (6, 7)}
    if couple_choices:
        # The ninth event lies on an ordinary path between choice groups.
        # Ignoring it would incorrectly treat their choices as independent.
        edges.update({(1, 8), (8, 6), (7, 2)})
    divided = relationship_state.PartitionedSearch.from_edges(periods, edges)
    assert sorted(len(operations) for operations in divided.operations) == (
        [9] if couple_choices else [4, 4]
    )
    clauses = relationship_periods.cycle_clauses(periods)
    prefixes: dict[int, tuple[int, ...]] = {0: ()}
    pending = [0]
    while pending:
        completed = pending.pop()
        prefix = prefixes[completed]
        prefix_edges = edges.copy()
        for earlier in prefix:
            for later in range(9):
                if not completed & (1 << later):
                    prefix_edges.add((earlier, later))
        certificate = precedence_choice.completion_order(clauses, prefix_edges, 9)
        assert divided.has_completion(completed) == (certificate is not None)
        for operation in range(9):
            bit = 1 << operation
            if completed & bit:
                continue
            if any(
                later == operation and not completed & (1 << earlier)
                for earlier, later in edges
            ):
                continue
            following = (*prefix, operation)
            if relationship_periods.first_violation(periods, following) is not None:
                continue
            if completed | bit not in prefixes:
                prefixes[completed | bit] = following
                pending.append(completed | bit)


def test_acyclic_relationships_require_no_search_objects():
    periods = [[], [relationship_periods.Period(0, 1, (2,))]]
    divided = relationship_state.PartitionedSearch.from_edges(periods, {(0, 1), (1, 2)})
    assert divided.operations == []
    assert divided.searches == []
    assert divided.has_completion(0)
    assert divided.has_completion(3)


def test_one_way_predecessors_and_successors_do_not_enlarge_searches():
    periods = independent_periods()
    edges = {(0, 1), (2, 3), (4, 5), (6, 7), (8, 0), (1, 9), (8, 10), (10, 9)}
    divided = relationship_state.PartitionedSearch.from_edges(periods, edges)
    assert sorted(divided.operations) == [[0, 1, 2, 3], [4, 5, 6, 7]]
    assert divided.has_completion(0)


def test_partitioned_search_rejects_an_acyclic_dead_end():
    periods = [
        [relationship_periods.Period(2, 2, (4,))],
        [],
        [
            relationship_periods.Period(0, 0, (1,)),
            relationship_periods.Period(1, 1, (7,)),
        ],
    ]
    edges = {(0, 1), (0, 3), (2, 4), (3, 4), (4, 5), (3, 6), (1, 7)}
    divided = relationship_state.PartitionedSearch.from_edges(periods, edges)
    assert divided.has_completion(0)
    assert not divided.has_completion(1 << 2)
