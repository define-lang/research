from __future__ import annotations

import pytest

from destruction_contract_benchmarks import (
    snapshots,
    tuning_state,
    tuning_workloads,
    workloads,
)


@pytest.mark.parametrize("limit", [1, 16, 64, 256, 1_024, 4_096])
@pytest.mark.parametrize("partitions", [1, 4, 16, 64, 256, 1_024, 4_096])
@pytest.mark.parametrize("shape", ["chain", "branching", "fanout"])
def test_parameters_preserve_retained_versions(limit: int, partitions: int, shape: str):
    tuning_state.configure(limit, partitions)
    workload = workloads.generate(
        workloads.Configuration(512, 48, 64, 16, 16, caller_shape=shape), 28413
    )
    history: list[snapshots.Snapshot] = [tuning_state.FlatChildState(workload.initial)]
    oracles = [workload.initial]
    for caller in workload.callers:
        history.append(history[caller.callee].with_caller(caller.knowledge))
        oracles.append(caller.knowledge | oracles[caller.callee])
    for actual, expected in zip(history, oracles, strict=True):
        assert dict(actual.items()) == expected
        assert actual.with_caller(expected) is actual
        assert actual.get(("missing",)) is None
        for position, occupancy in expected.items():
            assert actual.get(position) == occupancy


def test_partition_compaction_returns_to_flat_state():
    tuning_state.configure(16, 64)
    initial = {(str(index),): snapshots.EMPTY for index in range(64)}
    state = tuning_state.FlatChildState(initial).with_caller(
        {(str(index),): snapshots.ERROR for index in range(64, 80)}
    )
    assert isinstance(state, tuning_state.PartitionedChildState)
    state = state.with_caller(
        {(str(index),): snapshots.ERROR for index in range(80, 128)}
    )
    assert isinstance(state, tuning_state.FlatChildState)
    assert len(dict(state.items())) == 128
    state = state.with_caller({("new",): snapshots.EMPTY})
    assert isinstance(state, tuning_state.ExtendedChildState)


@pytest.mark.parametrize(("limit", "partitions"), [(0, 16), (16, 0), (16, 3), (-1, 16)])
def test_invalid_parameters(limit: int, partitions: int):
    with pytest.raises(ValueError, match="must be"):
        tuning_state.configure(limit, partitions)


@pytest.mark.parametrize("case", tuning_workloads.CASES)
def test_workload_configurations(case: str):
    configuration = tuning_workloads.configuration(case, 1)
    assert configuration.initial_positions > 0
    assert configuration.callers > 0


def test_unknown_workload():
    with pytest.raises(ValueError, match="unknown tuning case"):
        _ = tuning_workloads.configuration("missing", 1)
