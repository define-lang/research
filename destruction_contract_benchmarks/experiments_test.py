from __future__ import annotations

import dataclasses

import pytest

from destruction_contract_benchmarks import experiments, snapshots, workloads


@pytest.mark.parametrize("case", experiments.PROJECTION_CASES)
def test_contract_projections_preserve_requirement_results(case: str):
    source = dataclasses.replace(experiments.projection_input(case, 1), copies=2)
    expected = experiments.CurrentProjection(source)
    expected.build()
    expected_reads = expected.query()
    for variant in experiments.variants_for(case)[1:]:
        candidate = experiments.SharedProjection(source, variant)
        candidate.build()
        assert candidate.query() == expected_reads


@pytest.mark.parametrize("case", experiments.HISTORY_CASES)
def test_history_variants_preserve_diagnostic_steps(case: str):
    expected = experiments.prepare(case, "current_history", 1, 4)
    expected.build()
    expected_reads = expected.query()
    for variant in experiments.variants_for(case)[1:]:
        candidate = experiments.prepare(case, variant, 1, 4)
        candidate.build()
        assert candidate.query() == expected_reads


@pytest.mark.parametrize("case", experiments.HISTORY_CASES)
def test_history_variants_preserve_complete_step_order(case: str):
    expected = experiments.HistoryExperiment(case, "current_history", 1)
    expected.build()
    linked = experiments.HistoryExperiment(case, "linked_history", 1)
    linked.build()
    shared = experiments.HistoryExperiment(case, "shared_tuple_history", 1)
    shared.build()
    assert shared.tuple_versions == expected.tuple_versions
    for actual_version, expected_version in zip(
        linked.linked_versions, expected.tuple_versions, strict=True
    ):
        for actual, expected_steps in zip(
            actual_version, expected_version, strict=True
        ):
            actual_steps: list[int] = []
            while actual is not None:
                actual_steps.append(actual.step)
                actual = actual.previous
            assert tuple(actual_steps) == expected_steps


def test_state_experiments_include_parent_queries_and_enumeration():
    workload = workloads.generate(
        workloads.Configuration(
            16, 8, 3, 3, 64, copies=2, enumerate_every=1, query_rounds=2
        ),
        8,
    )
    expected = experiments.StateExperiment(
        workload, snapshots.FACTORIES["current_flat"]
    )
    expected.build()
    expected_queries = expected.query()
    expected_traversal = expected.traverse()
    assert expected_queries.parent_lookups > 0
    assert expected_traversal.count > 0
    for factory in snapshots.FACTORIES.values():
        candidate = experiments.StateExperiment(workload, factory)
        candidate.build()
        assert candidate.query() == expected_queries
        assert candidate.traverse() == expected_traversal


def test_queries_of_earlier_caller_knowledge_match_flat_oracle():
    workload = workloads.generate(
        workloads.Configuration(16, 32, 8, 4, 64, query_caller_knowledge=True), 18
    )
    expected = experiments.StateExperiment(
        workload, snapshots.FACTORIES["current_flat"]
    )
    expected.build()
    for factory in snapshots.FACTORIES.values():
        candidate = experiments.StateExperiment(workload, factory)
        candidate.build()
        assert candidate.query() == expected.query()
        assert candidate.traverse() == experiments.Reads()


@pytest.mark.parametrize("case", workloads.CASES)
def test_state_workload_configuration(case: str):
    configuration = workloads.configuration(case, 2)
    assert configuration.initial_positions > 0
    assert configuration.callers > 0


@pytest.mark.parametrize("case", ["wide_registry", "deep_names", "library_fanout"])
def test_prepare_state_cases(case: str):
    assert experiments.variants_for(case) == tuple(snapshots.FACTORIES)
    experiment = experiments.prepare(case, "compact_base", 1, 4)
    assert isinstance(experiment, experiments.StateExperiment)
    assert experiment.dimensions()["initial_state_entries"] > 0


@pytest.mark.parametrize("variant", ["current_contracts", "compact_base"])
def test_prepare_contract_cases(variant: str):
    experiment = experiments.prepare("contracts_chain", variant, 1, 4)
    experiment.build()
    assert experiment.query().count == 128 * 4 * 4
    assert experiment.dimensions()["contracts_per_copy"] == 128
