from __future__ import annotations

import dataclasses

import pytest

from destruction_contract_benchmarks import (
    experiments,
    snapshots,
    threshold_run,
    threshold_workloads,
    unpartitioned_state,
)


@pytest.mark.parametrize("limit", [1, 4, 8, 16, 32, 64, 128, 256])
@pytest.mark.parametrize("case", threshold_workloads.EXACT_CASES)
def test_retained_states_match_independent_flat_oracle(limit: int, case: str):
    unpartitioned_state.configure(limit)
    configuration = threshold_workloads.configurations(case, 1, 74921)[0]
    configuration = dataclasses.replace(configuration, copies=1)
    workload = threshold_workloads.exact_workload(configuration)
    assert len(workload.initial) == configuration.initial_positions
    experiment = experiments.StateExperiment(workload, threshold_run.create_snapshot)
    oracle = experiments.StateExperiment(workload, snapshots.CurrentFlat)
    experiment.build()
    oracle.build()
    assert experiment.query() == oracle.query()
    for actual, expected in zip(
        experiment.histories[0], oracle.histories[0], strict=True
    ):
        assert dict(actual.items()) == dict(expected.items())
        for position, occupancy in expected.items():
            assert actual.get(position) is occupancy
        assert actual.get(("position</not_present>",)) is None
        assert actual.with_caller(dict(actual.items())) is actual


@pytest.mark.parametrize("case", threshold_workloads.MIXED_CASES)
def test_mixture_inputs_are_reproducible_and_independent(case: str):
    first = threshold_workloads.configurations(case, 1, 74921)
    assert first == threshold_workloads.configurations(case, 1, 74921)
    assert first != threshold_workloads.configurations(case, 1, 28413)
    assert len(first) == 24
    for configuration in first:
        assert configuration.initial_positions > 0


@pytest.mark.parametrize("case", ["mixture_unknown", "unknown_16"])
def test_unknown_case(case: str):
    with pytest.raises(ValueError, match="unknown"):
        _ = threshold_workloads.configurations(case, 1, 74921)


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_threshold(limit: int):
    with pytest.raises(ValueError, match="positive"):
        unpartitioned_state.configure(limit)


@pytest.mark.parametrize("case", ["small_objects", "mixed_small", "mixture_short"])
def test_composite_experiment_reads_match_flat(case: str):
    unpartitioned_state.configure(16)
    actual = threshold_workloads.ThresholdExperiment(
        case, 1, 28413, threshold_run.create_snapshot
    )
    expected = threshold_workloads.ThresholdExperiment(
        case, 1, 28413, snapshots.CurrentFlat
    )
    actual.build()
    expected.build()
    assert actual.query() == expected.query()
    assert actual.traverse() == expected.traverse()
    assert actual.dimensions() == expected.dimensions()
