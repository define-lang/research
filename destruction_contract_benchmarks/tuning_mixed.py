"""Held-out mixtures of state sizes, batch sizes, and caller shapes."""

from __future__ import annotations

import random
import typing

from destruction_contract_benchmarks import experiments, snapshots, workloads

CASES = ("mixed_small", "mixed_medium")


def configurations(case: str, scale: int, seed: int) -> list[workloads.Configuration]:
    """Jitter sizes so a threshold cannot win only at fixed power-of-two boundaries."""
    if case == "mixed_small":
        sizes = (2, 4, 8, 16, 32, 64, 128, 256)
        caller_counts = (3, 8, 16, 32)
        batches = (0, 1, 2, 4, 8)
        copies = 16 * scale
    elif case == "mixed_medium":
        sizes = (128, 256, 512, 1024)
        caller_counts = (8, 16, 32, 64)
        batches = (1, 4, 16, 64)
        copies = 4 * scale
    else:
        raise ValueError(f"unknown mixture: {case}")
    randomizer = random.Random(seed)  # noqa: S311 - Fixed held-out workload generation.
    configurations: list[workloads.Configuration] = []
    for _ in range(48):
        size = randomizer.choice(sizes)
        jittered = max(1, size + randomizer.randint(-size // 4, size // 4))
        configurations.append(
            workloads.Configuration(
                jittered,
                randomizer.choice(caller_counts),
                randomizer.choice(batches),
                min(jittered, 16),
                32,
                copies=copies,
                caller_shape=randomizer.choice(("chain", "fanout", "branching")),
            )
        )
    return configurations


class MixedStateExperiment(experiments.Experiment):
    """Retain independently shaped destruction states through the complete experiment."""

    def __init__(self, case: str, scale: int, seed: int, factory: snapshots.Factory):
        """Prepare inputs outside the measured state-construction phase."""
        self.experiments: list[experiments.StateExperiment] = []
        for index, configuration in enumerate(configurations(case, scale, seed)):
            workload = workloads.generate(configuration, seed + index * 97)
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
            result = experiment.query()
            checksum += result.checksum
            count += result.count
            parents += result.parent_lookups
        return experiments.Reads(checksum, count, parents)

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
        }
