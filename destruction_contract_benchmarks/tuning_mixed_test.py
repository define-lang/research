from __future__ import annotations

import pytest

from destruction_contract_benchmarks import (
    snapshots,
    tuning_mixed,
    tuning_run,
    tuning_state,
)


@pytest.mark.parametrize("case", tuning_mixed.CASES)
def test_mixed_workloads_match_flat_state(case: str):
    tuning_state.configure(64, 1024)
    actual = tuning_mixed.MixedStateExperiment(
        case, 1, 28413, tuning_run.create_snapshot
    )
    expected = tuning_mixed.MixedStateExperiment(
        case, 1, 28413, snapshots.FACTORIES["shared_flat"]
    )
    actual.build()
    expected.build()
    assert actual.query() == expected.query()
    assert actual.dimensions() == expected.dimensions()
    for actual_experiment, expected_experiment in zip(
        actual.experiments, expected.experiments, strict=True
    ):
        for actual_history, expected_history in zip(
            actual_experiment.histories, expected_experiment.histories, strict=True
        ):
            for actual_state, expected_state in zip(
                actual_history, expected_history, strict=True
            ):
                assert dict(actual_state.items()) == dict(expected_state.items())


def test_invalid_mixture():
    with pytest.raises(ValueError, match="unknown mixture"):
        _ = tuning_mixed.configurations("missing", 1, 74921)
