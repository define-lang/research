from __future__ import annotations

import itertools
from pathlib import Path

from define.compiler import driver


def test_either_detachment_has_valid_source():
    source = Path(__file__).with_name("identity_move_choice.dfn").read_text()
    validation = driver.Driver().validate_source(source).program_validation
    assert validation.all_exceptions == []
    assert validation.all_diagnostics == []


def test_either_detachment_prevents_circular_relationships():
    owners: dict[str, str | None] = {
        "parent": None,
        "detached_child": None,
        "detached_grandchild": None,
        "P.child": "P",
        "Q.inner": "Q",
        "R.end": "R",
    }
    initial: dict[str, str | None] = {
        "parent": "P",
        "detached_child": None,
        "detached_grandchild": None,
        "P.child": "Q",
        "Q.inner": "R",
        "R.end": None,
    }
    moves = {
        "A": ("P.child", "detached_child", "Q"),
        "B": ("Q.inner", "detached_grandchild", "R"),
        "C": ("parent", "R.end", "P"),
    }
    observations: dict[tuple[str, ...], list[bool]] = {}
    for order in itertools.permutations(moves):
        occupancy = initial.copy()
        cycles: list[bool] = []
        for name in order:
            source, target, selected = moves[name]
            assert occupancy[source] == selected
            assert occupancy[target] is None
            occupancy[source] = None
            occupancy[target] = selected
            parents: dict[str, str | None] = {}
            for position, particle in occupancy.items():
                if particle is not None:
                    parents[particle] = owners[position]
            cyclic = False
            for particle in parents:
                seen: set[str] = set()
                current: str | None = particle
                while current is not None:
                    if current in seen:
                        cyclic = True
                        break
                    seen.add(current)
                    current = parents[current]
            cycles.append(cyclic)
        observations[order] = cycles
        assert occupancy == {
            "parent": None,
            "detached_child": "Q",
            "detached_grandchild": "R",
            "P.child": None,
            "Q.inner": None,
            "R.end": "P",
        }
    assert observations == {
        ("A", "B", "C"): [False, False, False],
        ("A", "C", "B"): [False, False, False],
        ("B", "A", "C"): [False, False, False],
        ("B", "C", "A"): [False, False, False],
        ("C", "A", "B"): [True, False, False],
        ("C", "B", "A"): [True, False, False],
    }


def test_no_dependency_dag_admits_exactly_the_safe_move_orders():
    orders = tuple(itertools.permutations("ABC"))
    safe = {
        ("A", "B", "C"),
        ("A", "C", "B"),
        ("B", "A", "C"),
        ("B", "C", "A"),
    }
    possible_edges = tuple(itertools.permutations("ABC", 2))
    largest_families: set[frozenset[tuple[str, ...]]] = set()
    largest_size = 0
    for mask in range(1 << len(possible_edges)):
        edges: list[tuple[str, str]] = []
        for index, edge in enumerate(possible_edges):
            if mask & (1 << index):
                edges.append(edge)
        admitted: set[tuple[str, ...]] = set()
        for order in orders:
            if all(order.index(before) < order.index(after) for before, after in edges):
                admitted.add(order)
        if admitted and admitted <= safe:
            if len(admitted) > largest_size:
                largest_size = len(admitted)
                largest_families.clear()
            if len(admitted) == largest_size:
                largest_families.add(frozenset(admitted))
    assert largest_size == 3
    assert largest_families == {
        frozenset({("A", "B", "C"), ("A", "C", "B"), ("B", "A", "C")}),
        frozenset({("A", "B", "C"), ("B", "A", "C"), ("B", "C", "A")}),
    }
