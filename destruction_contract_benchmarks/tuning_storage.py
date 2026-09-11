"""Inspect retained dictionaries and partition directories outside timed runs."""

from __future__ import annotations

import argparse
import gc
import json
import sys
import typing
from pathlib import Path

from destruction_contract_benchmarks import (
    experiments,
    snapshots,
    tuning_run,
    tuning_state,
    tuning_workloads,
    workloads,
)


def storage(histories: list[list[snapshots.Snapshot]]) -> dict[str, int]:
    """Count shared collections once while excluding common keys and occupancy values."""
    states: dict[int, snapshots.Snapshot] = {}
    dictionaries: dict[int, dict[snapshots.Position, snapshots.Occupancy]] = {}
    directories: dict[
        int, tuple[dict[snapshots.Position, snapshots.Occupancy], ...]
    ] = {}
    for history in histories:
        for snapshot in history:
            states[id(snapshot)] = snapshot
    for snapshot in states.values():
        # These implementations only retain dictionaries, partition tuples, and
        # scalar bookkeeping. Inspecting direct referents avoids changing their
        # measured methods or reaching through private attributes.
        for collection in typing.cast("list[object]", gc.get_referents(snapshot)):
            if isinstance(collection, dict):
                dictionary = typing.cast(
                    "dict[snapshots.Position, snapshots.Occupancy]", collection
                )
                dictionaries[id(dictionary)] = dictionary
            elif isinstance(collection, tuple):
                directory = typing.cast(
                    "tuple[dict[snapshots.Position, snapshots.Occupancy], ...]",
                    collection,
                )
                directories[id(directory)] = directory
                for dictionary in directory:
                    dictionaries[id(dictionary)] = dictionary
    return {
        "snapshot_references": sum(len(history) for history in histories),
        "unique_snapshots": len(states),
        "unique_dictionaries": len(dictionaries),
        "retained_dictionary_entries": sum(
            len(value) for value in dictionaries.values()
        ),
        "dictionary_bytes": sum(
            sys.getsizeof(value) for value in dictionaries.values()
        ),
        "partition_directory_entries": sum(
            len(value) for value in directories.values()
        ),
        "partition_directory_bytes": sum(
            sys.getsizeof(value) for value in directories.values()
        ),
        "snapshot_bytes": sum(sys.getsizeof(value) for value in states.values()),
    }


def main():
    """Explain measured memory differences using actual retained storage shapes."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--case", required=True, choices=tuning_workloads.CASES)
    _ = parser.add_argument("--scale", type=int, default=4)
    _ = parser.add_argument("--seed", type=int, default=74921)
    _ = parser.add_argument("--pairs", required=True)
    _ = parser.add_argument("--save", type=Path)
    arguments = parser.parse_args()
    case = typing.cast("str", arguments.case)
    scale = typing.cast("int", arguments.scale)
    seed = typing.cast("int", arguments.seed)
    pairs = typing.cast("str", arguments.pairs)
    destination = typing.cast("Path | None", arguments.save)
    results: dict[str, dict[str, int]] = {}
    workload = workloads.generate(tuning_workloads.configuration(case, scale), seed)
    for pair in pairs.split(","):
        limit_text, count_text = pair.split("/")
        tuning_state.configure(int(limit_text), int(count_text))
        experiment = experiments.StateExperiment(workload, tuning_run.create_snapshot)
        experiment.build()
        results[pair] = storage(experiment.histories)
    rendered = (
        json.dumps(
            {"case": case, "scale": scale, "seed": seed, "results": results}, indent=2
        )
        + "\n"
    )
    print(rendered, end="")
    if destination is not None:
        _ = destination.write_text(rendered)


if __name__ == "__main__":
    main()
