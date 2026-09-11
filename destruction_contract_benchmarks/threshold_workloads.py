"""Exact small-state sizes and caller patterns for the unpartitioned crossover."""

from __future__ import annotations

import random
import typing

from destruction_contract_benchmarks import (
    experiments,
    snapshots,
    tuning_mixed,
    tuning_workloads,
    workloads,
)

SIZES = (1, 4, 8, 16, 32, 64, 128, 256)
SHAPES = (
    "short",
    "chain",
    "fanout",
    "branching",
    "unchanged",
    "overlap",
    "dense",
    "read",
)
EXACT_CASES: list[str] = []
for shape in SHAPES:
    for size in SIZES:
        EXACT_CASES.append(f"{shape}_{size}")
MIXED_CASES = tuple(f"mixture_{shape}" for shape in SHAPES)
SCREEN_CASES = (*EXACT_CASES, *workloads.CASES, *tuning_mixed.CASES)


def configuration(shape: str, size: int, scale: int) -> workloads.Configuration:
    """Distinguish new knowledge, repeated knowledge, and lookup-heavy use."""
    caller_count = {"chain": 16, "fanout": 8, "branching": 15}.get(shape, 3)
    caller_shape = shape if shape in ("fanout", "branching") else "chain"
    overlap = size if shape in ("unchanged", "overlap", "dense") else 0
    additions = 0 if shape == "unchanged" else 1
    if shape == "dense":
        additions = size
    query_rounds = 32 if shape == "read" else 1
    return workloads.Configuration(
        size,
        caller_count,
        additions,
        overlap,
        8,
        copies=1024 * scale,
        name_depth=1,
        caller_shape=caller_shape,
        query_rounds=query_rounds,
    )


def exact_workload(configuration: workloads.Configuration) -> workloads.Workload:
    """Use exact dictionary cardinalities rather than counting initial resources."""
    positions: list[snapshots.Position] = []
    initial: dict[snapshots.Position, snapshots.Occupancy] = {}
    for index in range(configuration.initial_positions):
        position = (f"position</initial_{index}>",)
        positions.append(position)
        initial[position] = snapshots.EMPTY
    callers: list[workloads.Caller] = []
    for index in range(configuration.callers):
        callee = index
        if configuration.caller_shape == "fanout":
            callee = 0
        elif configuration.caller_shape == "branching":
            callee = index // 2
        knowledge: dict[snapshots.Position, snapshots.Occupancy] = {}
        if configuration.overlap:
            knowledge = dict.fromkeys(positions, snapshots.ERROR)
        first_addition = index * max(1, configuration.additions)
        addition = (f"position</addition_{first_addition}>",)
        for added in range(configuration.additions):
            knowledge[(f"position</addition_{first_addition + added}>",)] = (
                snapshots.ERROR
            )
        queries = (
            positions[0],
            positions[len(positions) // 2],
            positions[-1],
            addition,
            ("position</addition_0>",),
            positions[0],
            ("position</missing_first>",),
            ("position</missing_second>",),
        )
        callers.append(workloads.Caller(callee, knowledge, queries))
    return workloads.Workload(configuration, initial, tuple(callers))


def configurations(case: str, scale: int, seed: int) -> list[workloads.Configuration]:
    """Record jittered held-out inputs separately from fixed screening sizes."""
    if case.startswith("mixture_"):
        shape = case.removeprefix("mixture_")
        if shape not in SHAPES:
            raise ValueError(f"unknown mixture: {case}")
        randomizer = random.Random(seed)  # noqa: S311 - Reproducible held-out inputs.
        result: list[workloads.Configuration] = []
        for _ in range(24):
            size = randomizer.choice((2, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192))
            size = max(1, size + randomizer.randint(-size // 4, size // 4))
            item = configuration(shape, size, scale)
            result.append(
                workloads.Configuration(
                    item.initial_positions,
                    item.callers,
                    item.additions,
                    item.overlap,
                    item.queries,
                    copies=64 * scale,
                    name_depth=item.name_depth,
                    caller_shape=item.caller_shape,
                    query_rounds=item.query_rounds,
                )
            )
        return result
    if case in tuning_mixed.CASES:
        return tuning_mixed.configurations(case, scale, seed)
    if case in tuning_workloads.CASES:
        return [tuning_workloads.configuration(case, scale)]
    shape, _, size_text = case.rpartition("_")
    if shape not in SHAPES:
        raise ValueError(f"unknown shape: {case}")
    return [configuration(shape, int(size_text), scale)]


class ThresholdExperiment(experiments.Experiment):
    """Retain comparable caller histories across one or several state sizes."""

    def __init__(self, case: str, scale: int, seed: int, factory: snapshots.Factory):
        """Prepare inputs before timing construction and requirement reads."""
        self.experiments: list[experiments.StateExperiment] = []
        for index, item in enumerate(configurations(case, scale, seed)):
            if case in (*tuning_workloads.CASES, *tuning_mixed.CASES):
                workload = workloads.generate(item, seed + index * 97)
            else:
                workload = exact_workload(item)
            self.experiments.append(experiments.StateExperiment(workload, factory))

    @typing.override
    def build(self):
        for experiment in self.experiments:
            experiment.build()

    @typing.override
    def query(self) -> experiments.Reads:
        checksum = 0
        count = 0
        parents = 0
        for experiment in self.experiments:
            reads = experiment.query()
            checksum += reads.checksum
            count += reads.count
            parents += reads.parent_lookups
        return experiments.Reads(checksum, count, parents)

    @typing.override
    def traverse(self) -> experiments.Reads:
        checksum = 0
        count = 0
        for experiment in self.experiments:
            reads = experiment.traverse()
            checksum += reads.checksum
            count += reads.count
        return experiments.Reads(checksum, count)

    @typing.override
    def dimensions(self) -> dict[str, int]:
        return {
            "distinct_configurations": len(self.experiments),
            "initial_state_entries": sum(
                len(item.workload.initial) for item in self.experiments
            ),
            "copies": sum(
                item.workload.configuration.copies for item in self.experiments
            ),
            "retained_states": sum(
                item.workload.configuration.copies * (len(item.workload.callers) + 1)
                for item in self.experiments
            ),
        }
