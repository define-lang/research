from __future__ import annotations

import sys

from destruction_contract_benchmarks import snapshots, tuning_state, tuning_storage


def test_shared_snapshots_and_dictionaries_are_counted_once():
    values = {("known",): snapshots.EMPTY}
    state = tuning_state.FlatChildState(values)
    assert tuning_storage.storage([[state, state], [state]]) == {
        "snapshot_references": 3,
        "unique_snapshots": 1,
        "unique_dictionaries": 1,
        "retained_dictionary_entries": 1,
        "dictionary_bytes": sys.getsizeof(values),
        "partition_directory_entries": 0,
        "partition_directory_bytes": 0,
        "snapshot_bytes": sys.getsizeof(state),
    }


def test_partition_storage_counts_shared_base_once():
    base = {("known",): snapshots.EMPTY}
    additions: tuple[dict[snapshots.Position, snapshots.Occupancy], ...] = (
        {("new",): snapshots.ERROR},
        {},
    )
    first = tuning_state.PartitionedChildState(base, additions, 1)
    second = tuning_state.PartitionedChildState(base, additions, 1)
    assert tuning_storage.storage([[first, second]]) == {
        "snapshot_references": 2,
        "unique_snapshots": 2,
        "unique_dictionaries": 3,
        "retained_dictionary_entries": 2,
        "dictionary_bytes": sys.getsizeof(base)
        + sum(sys.getsizeof(value) for value in additions),
        "partition_directory_entries": 2,
        "partition_directory_bytes": sys.getsizeof(additions),
        "snapshot_bytes": sys.getsizeof(first) + sys.getsizeof(second),
    }
