from __future__ import annotations

import pytest

from define.compiler import driver
from operation_graph_optimization import (
    combination_inputs,
    complete_inputs,
    complete_workloads,
    reference,
    workloads,
)
from operation_graph_optimization import (
    simplification_experiment as experiment,
)


def check(prepared: experiment.Prepared):
    oracle = reference.Reference()
    uses: dict[int, set[int]] = {}
    vacates: dict[int, int] = {}
    for occurrence, step in enumerate(prepared.steps):
        if occurrence in prepared.retentions:
            oracle.retain(prepared.retentions[occurrence])
        assert oracle.add(step.operation) == occurrence
        for particle in step.operation.creators:
            uses.setdefault(particle, set()).add(occurrence)
        if step.moved is not None:
            uses.setdefault(step.moved, set()).add(occurrence)
        if step.vacated is not None:
            vacates[step.vacated] = occurrence
            uses.setdefault(step.vacated, set()).add(occurrence)
    expected: dict[int, set[int]] = {}
    for particle in vacates:
        candidates = uses[particle]
        kept = set(candidates)
        for candidate in candidates:
            kept.difference_update(oracle.ancestors[candidate])
        expected[particle] = kept
    for variant in experiment.VARIANTS:
        calculated, vanishes = experiment.construct(variant, prepared)
        actual = [
            set(calculated.dependencies(occurrence))
            for occurrence in range(len(prepared.steps))
        ]
        assert actual == oracle.dependencies
        actual_vanishes: dict[int, set[int]] = {}
        for particle, occurrence in vanishes.items():
            actual_vanishes[particle] = (
                {occurrence}
                if occurrence < len(prepared.steps)
                else set(calculated.dependencies(occurrence))
            )
        assert actual_vanishes == expected


@pytest.mark.parametrize("family", experiment.FAMILIES)
@pytest.mark.parametrize("seed", range(8))
def test_random_valid_operations(family: str, seed: int):
    check(experiment.prepare(family, seed, 80, 12))


@pytest.mark.parametrize("depth", [1, 6, 20])
def test_real_source(depth: int):
    program = workloads.tree_program(17, 12, depth, 8)
    validation = driver.Driver().validate_source(program.source).program_validation
    assert validation.all_exceptions == []
    assert validation.all_diagnostics == []
    steps = complete_workloads.resolve_program(program)
    check(
        experiment.Prepared(
            steps,
            [complete_inputs.convert(step) for step in steps],
            [combination_inputs.convert(step) for step in steps],
            {},
        )
    )


@pytest.mark.parametrize("family", ["wide", "written", "retained", "growth_closed"])
def test_wide_candidate_sets(family: str):
    check(experiment.prepare(family, 17, 500, 100))
