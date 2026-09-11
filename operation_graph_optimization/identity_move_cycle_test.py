from __future__ import annotations

import itertools
from pathlib import Path

from define.compiler import driver


def test_move_into_former_child_has_valid_source():
    source = Path(__file__).with_name("identity_move_cycle.dfn").read_text()
    validation = driver.Driver().validate_source(source).program_validation
    assert validation.all_exceptions == []
    assert validation.all_diagnostics == []


def test_endpoint_requirements_allow_a_circular_intermediate_relationship():
    owners: dict[str, str | None] = {
        "parent": None,
        "detached": None,
        "P.child": "P",
        "Q.inner": "Q",
    }
    initial: dict[str, str | None] = {
        "parent": "P",
        "detached": None,
        "P.child": "Q",
        "Q.inner": None,
    }
    moves = {
        "detach_child": ("P.child", "detached", "Q"),
        "move_parent": ("parent", "Q.inner", "P"),
    }
    observations: dict[tuple[str, ...], list[bool]] = {}
    final_states: list[dict[str, str | None]] = []
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
        final_states.append(occupancy)
    assert observations == {
        ("detach_child", "move_parent"): [False, False],
        ("move_parent", "detach_child"): [True, False],
    }
    assert final_states == [
        {"parent": None, "detached": "Q", "P.child": None, "Q.inner": "P"},
        {"parent": None, "detached": "Q", "P.child": None, "Q.inner": "P"},
    ]
