from __future__ import annotations

import itertools
from pathlib import Path

from define.compiler import driver


def test_competing_relationship_changes_have_valid_source():
    source = Path(__file__).with_name("identity_move_conflict.dfn").read_text()
    validation = driver.Driver().validate_source(source).program_validation
    assert validation.all_exceptions == []
    assert validation.all_diagnostics == []


def test_separately_safe_moves_can_jointly_make_a_cycle():
    initial: dict[str, str | None] = {"P": None, "Q": "P", "R": None}
    changes: dict[str, tuple[str, str | None]] = {
        "A": ("Q", None),
        "B": ("P", "R"),
        "C": ("R", "Q"),
    }
    observations: dict[tuple[str, ...], list[bool]] = {}
    for order in itertools.permutations(changes):
        parents = initial.copy()
        cycles: list[bool] = []
        for name in order:
            particle, parent = changes[name]
            parents[particle] = parent
            cyclic = False
            for start in parents:
                seen: set[str] = set()
                current: str | None = start
                while current is not None:
                    if current in seen:
                        cyclic = True
                        break
                    seen.add(current)
                    current = parents[current]
            cycles.append(cyclic)
        observations[order] = cycles
        assert parents == {"P": "R", "Q": None, "R": "Q"}
    assert observations == {
        ("A", "B", "C"): [False, False, False],
        ("A", "C", "B"): [False, False, False],
        ("B", "A", "C"): [False, False, False],
        ("B", "C", "A"): [False, True, False],
        ("C", "A", "B"): [False, False, False],
        ("C", "B", "A"): [False, True, False],
    }


def test_no_monotone_completion_conditions_admit_exactly_the_safe_orders():
    monotone_tables = (
        (False, False, False, False),
        (False, False, False, True),
        (False, True, False, True),
        (False, False, True, True),
        (False, True, True, True),
        (True, True, True, True),
    )
    others = ((1, 2), (0, 2), (0, 1))
    safe = {(0, 1, 2), (0, 2, 1), (1, 0, 2), (2, 0, 1)}
    largest_size = 0
    for tables in itertools.product(monotone_tables, repeat=3):
        admitted: set[tuple[int, ...]] = set()
        for order in itertools.permutations(range(3)):
            completed: set[int] = set()
            for operation in order:
                first, second = others[operation]
                mask = int(first in completed) + 2 * int(second in completed)
                if not tables[operation][mask]:
                    break
                completed.add(operation)
            else:
                admitted.add(order)
        assert admitted != safe
        if admitted <= safe:
            largest_size = max(largest_size, len(admitted))
    assert largest_size == 3
