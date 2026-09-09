from __future__ import annotations

import dataclasses

import pytest

from operation_graph_optimization.complete import algorithm
from operation_graph_optimization.transitive_destruction.interfaces import (
    compiler,
    descriptions,
)


def expected(result: compiler.Result) -> dict[str, set[str]]:
    baseline = algorithm.Calculator()
    for index, step in enumerate(result.steps):
        if index in result.retentions:
            baseline.retain(result.retentions[index])
        operation = step.operation
        _ = baseline.add(
            algorithm.Operation(
                occupied=operation.occupied,
                fill=operation.fill,
                empty=operation.empty,
                quality_particles=operation.creators,
                defines=operation.defines,
                ordinary_occupants=step.ordinary_occupants,
                moved=step.moved,
                vacated=step.vacated,
            )
        )
    vanishes = baseline.finish()
    names = dict(enumerate(result.step_labels))
    for particle, vanish in vanishes.items():
        names[vanish] = f"vanish.{particle}"
    dependencies: dict[str, set[str]] = {}
    for index, name in names.items():
        dependencies[name] = {names[p] for p in baseline.graph.dependencies(index)}
    return dependencies


def actual(result: compiler.Result) -> dict[str, set[str]]:
    dependencies: dict[str, set[str]] = {}
    for index, name in enumerate(result.labels):
        dependencies[name] = {
            result.labels[p] for p in result.graph.dependencies(index)
        }
    return dependencies


def project(explicit: dict[str, set[str]]) -> dict[str, set[str]]:
    # This intentionally slow, independent oracle is never used by construction.
    previous: dict[str, set[str]] = {}
    kept: dict[str, set[str]] = {}
    for name, dependencies in explicit.items():
        transitive = set(dependencies)
        for dependency in dependencies:
            transitive.update(previous[dependency])
        previous[name] = transitive
        if name.startswith("child_vacate."):
            continue
        candidates = {p for p in transitive if not p.startswith("child_vacate.")}
        direct = candidates.copy()
        for candidate in candidates:
            direct.difference_update(previous[candidate])
        kept[name] = direct
    return kept


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("width", [4, 8, 24])
@pytest.mark.parametrize("depth", [0, 1, 6, 20])
def test_derived_interfaces_match_whole_program_calculation(
    seed: int, width: int, depth: int
):
    program = descriptions.generate(seed, width, 30, depth)
    template = compiler.compile_action(program.callee)
    explicit = compiler.construct(program, "explicit", template)
    oracle = expected(explicit)
    assert actual(explicit) == oracle
    projected = project(oracle)
    for variant in ("lowered", "records"):
        result = compiler.construct(program, variant, template)
        assert actual(result) == projected
        assert result.template is template


def test_one_callee_interface_handles_different_caller_only_destructors():
    program = descriptions.generate(5, 12, 10, 3)
    template = compiler.compile_action(program.callee)
    for count in range(len(program.destructors) + 1):
        caller = dataclasses.replace(program, destructors=program.destructors[:count])
        explicit = compiler.construct(caller, "explicit", template)
        assert actual(explicit) == expected(explicit)
        records = compiler.construct(caller, "records", template)
        assert actual(records) == project(expected(explicit))
        assert records.template is template


def reader_case() -> descriptions.Program:
    setup = descriptions.Action(
        "setup",
        tuple(range(9)),
        (
            descriptions.Create(descriptions.Reference(0), (1,)),
            descriptions.Create(descriptions.Reference(1, (0,)), (2, 3, 4, 5)),
            descriptions.Create(descriptions.Reference(2, (0, 1))),
            descriptions.Create(descriptions.Reference(3, (0, 1)), (6, 7, 8)),
        ),
    )
    reusable = descriptions.Action(
        "swap",
        (0, 1, 2, 4),
        (
            descriptions.Move(
                descriptions.Reference(2, (0, 1)), descriptions.Reference(4, (0, 1))
            ),
            descriptions.Move(
                descriptions.Reference(4, (0, 1)), descriptions.Reference(2, (0, 1))
            ),
        ),
    )
    callee = descriptions.Action(
        "select",
        tuple(range(9)),
        (
            descriptions.Call(reusable),
            descriptions.Call(reusable),
            descriptions.Create(descriptions.Reference(6, (0, 1, 3))),
            descriptions.Create(descriptions.Reference(7, (0, 1, 3))),
            descriptions.Select(descriptions.Reference(0)),
        ),
    )
    destructor = descriptions.Action(
        "cleanup",
        (6, 8),
        (
            descriptions.Move(descriptions.Reference(6), descriptions.Reference(8)),
            descriptions.Move(descriptions.Reference(8), descriptions.Reference(6)),
        ),
    )
    return descriptions.Program(setup, callee, (destructor,))


def test_readers_and_setters_survive_repeated_calls_without_an_aggregate_gate():
    program = reader_case()
    template = compiler.compile_action(program.callee)
    assert template.callees[0] is template.callees[1]
    explicit = compiler.construct(program, "explicit", template)
    oracle = expected(explicit)
    assert actual(explicit) == oracle
    assert oracle["cleanup.0"] == {"select.2"}
    assert oracle["child_vacate.3"] == {"select.2", "select.3"}
    for variant in ("lowered", "records"):
        result = compiler.construct(program, variant, template)
        assert actual(result) == project(oracle)
        assert actual(result)["cleanup.0"] == {"select.2"}


def test_caller_only_children_do_not_change_the_callee_interface():
    program = descriptions.generate(4, 12, 10)
    template = compiler.compile_action(program.callee)
    builder = compiler.Builder("records")
    setup = compiler.compile_action(program.setup)
    _ = builder.execute(setup, builder.positions)
    supplied = {
        position: builder.positions[position] for position in template.positions
    }
    exported = builder.execute(template, supplied)
    assert exported is not None
    assert set(exported.positions) == set(template.positions)
    assert set(template.positions) < set(setup.positions)
    caller_result = compiler.construct(program, "records", template)
    assert set(caller_result.contract.positions) == set(setup.positions)
    assert caller_result.template is template


def test_contract_is_sufficient_without_private_callee_lifetime_state():
    program = reader_case()
    # construct() clears all private occupancy and lifetime maps at this boundary.
    explicit = compiler.construct(program, "explicit")
    records = compiler.construct(program, "records")
    assert actual(records) == project(expected(explicit))
    assert records.contract.vacates == {0: 10}


def test_caller_particle_identities_do_not_change_the_callee_template():
    program = descriptions.generate(7, 12, 20)
    template = compiler.compile_action(program.callee)
    statements = program.setup.statements
    reordered = dataclasses.replace(
        program.setup, statements=(*statements[:2], *reversed(statements[2:]))
    )
    for setup in (program.setup, reordered):
        caller = dataclasses.replace(program, setup=setup)
        explicit = compiler.construct(caller, "explicit", template)
        records = compiler.construct(caller, "records", template)
        assert actual(explicit) == expected(explicit)
        assert actual(records) == project(expected(explicit))
        assert records.template is template


def test_no_destructor_moves_when_all_child_positions_are_occupied():
    program = descriptions.generate(0, 2, 100)
    assert [action.statements for action in program.destructors] == [(), (), ()]
    explicit = compiler.construct(program, "explicit")
    oracle = expected(explicit)
    assert actual(explicit) == oracle
    for variant in ("lowered", "records"):
        assert actual(compiler.construct(program, variant)) == project(oracle)
