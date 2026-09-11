"""Randomized fresh-process measurements of the unpartitioned copy threshold."""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import os
import random
import resource
import sys
import typing
from pathlib import Path

import click

from destruction_contract_benchmarks import (
    experiments,
    run,
    snapshots,
    threshold_workloads,
    tuning_mixed,
    tuning_workloads,
    unpartitioned_state,
    workloads,
)


def create_snapshot(
    values: dict[snapshots.Position, snapshots.Occupancy],
) -> snapshots.Snapshot:
    """Include the independent initial dictionary capture in measured work."""
    return unpartitioned_state.FlatChildState(values.copy())


@click.command()
@click.option("--cases", default=",".join(threshold_workloads.SCREEN_CASES))
@click.option("--limits", default="1,4,8,16,32,64,128,256")
@click.option("--scales", default="1")
@click.option("--seeds", default="74921")
@click.option("--repetitions", type=click.IntRange(min=1), default=1)
@click.option("--order-seed", type=int, default=95321)
@click.option("--cpu", type=int, default=2)
@click.option("--memory-mib", type=int, default=2048)
@click.option("--timeout", type=float, default=60.0)
@click.option("--worker", is_flag=True, hidden=True)
@click.option("--variants", default="limit_256", hidden=True)
@click.option("--scale", type=int, default=1, hidden=True)
@click.option("--seed", type=int, default=74921, hidden=True)
@click.option(
    "--results-directory",
    type=click.Path(path_type=Path, file_okay=False),
    default="destruction_contract_benchmarks/threshold_results",
)
def main(
    *,
    cases: str,
    limits: str,
    scales: str,
    seeds: str,
    repetitions: int,
    order_seed: int,
    cpu: int,
    memory_mib: int,
    timeout: float,
    worker: bool,
    variants: str,
    scale: int,
    seed: int,
    results_directory: Path,
):
    """Compare thresholds without changing the compiler checkout."""
    if cpu not in os.sched_getaffinity(0):
        raise click.BadParameter(f"CPU {cpu} is not available")
    if worker:
        os.sched_setaffinity(0, {cpu})
        resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
        unpartitioned_state.configure(int(variants.removeprefix("limit_")))
        experiment = threshold_workloads.ThresholdExperiment(
            cases, scale, seed, create_snapshot
        )
        click.echo(json.dumps(run.measure(experiment, trace_allocations=False)))
        return
    case_names = cases.split(",")
    limit_values = [int(value) for value in limits.split(",")]
    scale_values = [int(value) for value in scales.split(",")]
    seed_values = [int(value) for value in seeds.split(",")]
    for values in (limit_values, scale_values, seed_values):
        if min(values) < 1 or len(values) != len(set(values)):
            raise click.BadParameter("expected distinct positive integers")
    configurations: dict[str, object] = {}
    for case in case_names:
        for size in scale_values:
            for input_seed in seed_values:
                configurations[f"{case}:{size}:{input_seed}"] = [
                    dataclasses.asdict(configuration)
                    for configuration in threshold_workloads.configurations(
                        case, size, input_seed
                    )
                ]
    directory = results_directory / datetime.datetime.now(datetime.UTC).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    directory.mkdir(parents=True)
    source_hashes: dict[str, str] = {}
    source_directory = directory / "sources"
    source_directory.mkdir()
    for module in (
        experiments,
        run,
        snapshots,
        threshold_workloads,
        tuning_mixed,
        tuning_workloads,
        unpartitioned_state,
        workloads,
    ):
        source = Path(typing.cast("str", module.__file__))
        content = source.read_bytes()
        source_hashes[source.name] = hashlib.sha256(content).hexdigest()
        _ = (source_directory / f"{source.name}.txt").write_bytes(content)
    source = Path(__file__)
    content = source.read_bytes()
    source_hashes[source.name] = hashlib.sha256(content).hexdigest()
    _ = (source_directory / f"{source.name}.txt").write_bytes(content)
    manifest = {
        "python": sys.version,
        "cpuinfo": Path("/proc/cpuinfo").read_text(),
        "argv": sys.argv,
        "cpu": cpu,
        "memory_limit_mib": memory_mib,
        "timeout_s": timeout,
        "cases": case_names,
        "limits": limit_values,
        "scales": scale_values,
        "seeds": seed_values,
        "repetitions": repetitions,
        "order_seed": order_seed,
        "configurations": configurations,
        "source_sha256": source_hashes,
    }
    _ = (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    jobs: list[tuple[str, int, int, int, int]] = []
    for repetition in range(repetitions):
        for size in scale_values:
            for input_seed in seed_values:
                for case in case_names:
                    for limit in limit_values:
                        jobs.append((case, size, input_seed, limit, repetition))
    random.Random(order_seed).shuffle(jobs)  # noqa: S311 - Reproducible measurement order.
    expected: dict[tuple[str, int, int], run.Scalar] = {}
    click.echo(f"Results: {directory}")
    for index, (case, size, input_seed, limit, repetition) in enumerate(jobs, 1):
        variant = f"limit_{limit}"
        result = run.run_child(
            case,
            variant,
            size,
            input_seed,
            cpu,
            timeout,
            memory_mib,
            allocation=False,
            worker_module="destruction_contract_benchmarks.threshold_run",
        )
        result.update(
            case=case,
            scale=size,
            seed=input_seed,
            variant=variant,
            repetition=repetition,
            allocation_tracing=False,
        )
        filename = f"{case}__s{size}__seed{input_seed}__{variant}__r{repetition}.json"
        _ = (directory / filename).write_text(json.dumps(result, indent=2) + "\n")
        if result["status"] == "ok":
            checksum = expected.setdefault((case, size, input_seed), result["checksum"])
            if result["checksum"] != checksum:
                raise ValueError(f"inconsistent checksum: {filename}")
        click.echo(f"{index}/{len(jobs)} {filename} {result['status']}")


if __name__ == "__main__":
    main()
