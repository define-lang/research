from __future__ import annotations

import itertools
import random

from operation_graph_optimization import precedence_choice


def satisfies(
    order: tuple[int, ...],
    clauses: tuple[precedence_choice.Clause, ...],
    edges: set[precedence_choice.Precedence],
):
    indices = {operation: index for index, operation in enumerate(order)}
    if any(indices[earlier] >= indices[later] for earlier, later in edges):
        return False
    for clause in clauses:
        if not any(
            all(indices[earlier] < indices[later] for earlier, later in alternative)
            for alternative in clause
        ):
            return False
    return True


def test_release_requires_both_vacate_and_last_use_before_the_move():
    clauses = ((frozenset({(0, 3)}), frozenset({(1, 3), (2, 3)})),)
    assert precedence_choice.completion_order(clauses, {(3, 0), (3, 1)}, 4) is None
    assert precedence_choice.completion_order(clauses, {(3, 0), (3, 2)}, 4) is None
    order = precedence_choice.completion_order(clauses, {(3, 0)}, 4)
    assert order is not None
    assert satisfies(order, clauses, {(3, 0)})


def test_incompatible_edges_within_one_alternative_are_rejected():
    clauses = ((frozenset({(0, 1), (1, 2), (2, 0)}),),)
    assert precedence_choice.completion_order(clauses, set(), 3) is None


def test_conjunction_alternatives_match_exhaustive_total_orders():
    generator = random.Random(608917)  # noqa: S311 - Reproducible finite exploration.
    count = 6
    orders = tuple(itertools.permutations(range(count)))
    for _ in range(150):
        clauses: list[precedence_choice.Clause] = []
        for _ in range(generator.randrange(1, 7)):
            alternatives: list[precedence_choice.Alternative] = []
            for _ in range(generator.randrange(1, 4)):
                precedences: set[precedence_choice.Precedence] = set()
                for _ in range(generator.randrange(1, 4)):
                    earlier, later = generator.sample(range(count), 2)
                    precedences.add((earlier, later))
                alternatives.append(frozenset(precedences))
            clauses.append(tuple(alternatives))
        constraints = tuple(clauses)
        legal = [order for order in orders if satisfies(order, constraints, set())]
        required = precedence_choice.necessary_precedences(constraints, set(), count)
        if legal:
            expected_required: set[precedence_choice.Precedence] = set()
            for earlier in range(count):
                for later in range(count):
                    if all(
                        order.index(earlier) < order.index(later) for order in legal
                    ):
                        expected_required.add((earlier, later))
            assert required == expected_required
        else:
            assert required is None
        prefix = tuple(generator.sample(range(count), generator.randrange(count)))
        edges = set(itertools.pairwise(prefix))
        if prefix:
            for later in range(count):
                if later not in prefix:
                    edges.add((prefix[-1], later))
        expected = any(order[: len(prefix)] == prefix for order in legal)
        actual = precedence_choice.completion_order(constraints, edges, count)
        assert (actual is not None) == expected
        parts = precedence_choice.factor(constraints, edges, count)
        factored = all(
            precedence_choice.completion_order(
                part.clauses, part.edges, len(part.operations)
            )
            is not None
            for part in parts
        )
        assert factored == expected
        certificate = precedence_choice.factored_completion_order(
            constraints, edges, count
        )
        assert (certificate is not None) == expected
        if certificate is not None:
            assert satisfies(certificate, constraints, edges)
        if actual is not None:
            assert satisfies(actual, constraints, edges)


def test_independent_choices_have_local_operation_indices():
    clauses = (
        (frozenset({(0, 1)}), frozenset({(1, 0)})),
        (frozenset({(3, 4)}), frozenset({(4, 3)})),
    )
    parts = precedence_choice.factor(clauses, {(1, 2), (2, 3)}, 5)
    assert sorted(len(part.operations) for part in parts) == [1, 2, 2]
    for part in parts:
        for clause in part.clauses:
            for alternative in clause:
                assert all(
                    earlier < len(part.operations) and later < len(part.operations)
                    for earlier, later in alternative
                )


def test_ordinary_precedence_can_couple_separate_choice_clauses():
    clauses = (
        (frozenset({(0, 1)}), frozenset({(1, 0)})),
        (frozenset({(2, 3)}), frozenset({(3, 2)})),
    )
    parts = precedence_choice.factor(clauses, {(1, 2), (3, 0)}, 4)
    assert len(parts) == 1
    assert len(parts[0].operations) == 4


def test_variable_free_contradiction_is_preserved():
    parts = precedence_choice.factor(((),), set(), 0)
    assert len(parts) == 1
    assert (
        precedence_choice.completion_order(parts[0].clauses, parts[0].edges, 0) is None
    )
    assert precedence_choice.factored_completion_order(((),), set(), 0) is None


def test_negation_handles_self_precedence_and_empty_alternatives():
    clauses: tuple[precedence_choice.Clause, ...] = (
        (),
        (frozenset(),),
        (frozenset({(1, 1), (0, 2)}), frozenset({(1, 2), (0, 1)})),
        (frozenset({(0, 1)}), frozenset({(1, 0)})),
    )
    for clause in clauses:
        negation = precedence_choice.negate_clause(clause)
        for order in itertools.permutations(range(3)):
            assert satisfies(order, negation, set()) != satisfies(
                order, (clause,), set()
            )
