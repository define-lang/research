"""Compare Child State parameters in randomized, resource-limited processes."""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import os
import platform
import random
import resource
import sys
import time
import typing
from pathlib import Path

import click

from destruction_contract_benchmarks import (
    experiments,
    run,
    snapshots,
    tuning_mixed,
    tuning_state,
    tuning_workloads,
    workloads,
)


def integers(value: str) -> list[int]:
    """Parse a nonempty parameter list without silently dropping duplicates."""
    values = [int(item) for item in value.split(",")]
    if any(item < 1 for item in values) or len(values) != len(set(values)):
        raise click.BadParameter("expected distinct positive integers")
    return values


def create_snapshot(
    values: dict[snapshots.Position, snapshots.Occupancy],
) -> snapshots.Snapshot:
    """Charge each experiment for capturing its initial dictionary."""
    return tuning_state.FlatChildState(values.copy())


@click.command()
@click.option("--cases", default=",".join(tuning_workloads.CASES))
@click.option("--flat-limits", default="16,64,256,1024,4096")
@click.option("--partition-counts", default="4,16,64,256,1024,4096")
@click.option("--pairs", default="")
@click.option("--scales", default="4")
@click.option("--seeds", default="74921")
@click.option("--repetitions", type=click.IntRange(min=1), default=1)
@click.option("--controls", default="")
@click.option("--order-seed", type=int, default=93_157)
@click.option("--cpu", type=int, default=2)
@click.option("--timeout", type=float, default=60.0)
@click.option("--memory-mib", type=int, default=1_536)
@click.option("--allocation", is_flag=True)
@click.option("--worker", is_flag=True, hidden=True)
@click.option("--variants", default="production", hidden=True)
@click.option("--scale", type=int, default=1, hidden=True)
@click.option("--seed", type=int, default=74_921, hidden=True)
@click.option(
    "--results-directory",
    type=click.Path(path_type=Path, file_okay=False),
    default="destruction_contract_benchmarks/tuning_results",
)
def main(
    *,
    cases: str,
    flat_limits: str,
    partition_counts: str,
    pairs: str,
    scales: str,
    seeds: str,
    repetitions: int,
    controls: str,
    order_seed: int,
    cpu: int,
    timeout: float,
    memory_mib: int,
    allocation: bool,
    worker: bool,
    variants: str,
    scale: int,
    seed: int,
    results_directory: Path,
):
    """Sweep parameters without overlapping benchmark workers."""
    limits = integers(flat_limits)
    counts = integers(partition_counts)
    for count in counts:
        if count & (count - 1):
            raise click.BadParameter("partition counts must be powers of two")
    case_names = cases.split(",")
    for case in case_names:
        if case not in (*tuning_workloads.CASES, *tuning_mixed.CASES):
            raise click.BadParameter(f"unknown tuning case: {case}")
    if cpu not in os.sched_getaffinity(0):
        raise click.BadParameter(f"CPU {cpu} is not available")
    if worker:
        os.sched_setaffinity(0, {cpu})
        resource.setrlimit(resource.RLIMIT_AS, (8 * 1_024**3, 8 * 1_024**3))
        tuning_state.configure(limits[0], counts[0])
        input_start = time.process_time()
        if variants == "production":
            factory = create_snapshot
        else:
            factory = snapshots.FACTORIES[variants]
        experiment: experiments.Experiment
        if cases in tuning_mixed.CASES:
            experiment = tuning_mixed.MixedStateExperiment(cases, scale, seed, factory)
        else:
            configuration = tuning_workloads.configuration(cases, scale)
            workload = workloads.generate(configuration, seed)
            experiment = experiments.StateExperiment(workload, factory)
        input_cpu = time.process_time() - input_start
        result = run.measure(experiment, trace_allocations=allocation)
        result["input_cpu_s"] = input_cpu
        click.echo(json.dumps(result))
        return

    scale_values = integers(scales)
    seed_values = integers(seeds)
    control_names = controls.split(",") if controls else []
    for control in control_names:
        if control not in snapshots.FACTORIES:
            raise click.BadParameter(f"unknown control: {control}")
    parameter_pairs: list[tuple[int, int]] = []
    if pairs:
        for pair in pairs.split(","):
            limit_text, count_text = pair.split("/")
            limit = int(limit_text)
            count = int(count_text)
            tuning_state.configure(limit, count)
            parameter_pairs.append((limit, count))
        if len(parameter_pairs) != len(set(parameter_pairs)):
            raise click.BadParameter("duplicate parameter pairs")
    else:
        for limit in limits:
            for count in counts:
                parameter_pairs.append((limit, count))
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = results_directory / timestamp
    directory.mkdir(parents=True)
    source_hashes: dict[str, str] = {}
    for module in (
        experiments,
        run,
        snapshots,
        tuning_mixed,
        tuning_state,
        tuning_workloads,
        workloads,
    ):
        source_file = Path(typing.cast("str", module.__file__))
        source_hashes[source_file.name] = hashlib.sha256(
            source_file.read_bytes()
        ).hexdigest()
    source_hashes["tuning_run.py"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    configurations: dict[str, object] = {}
    for case in case_names:
        for size in scale_values:
            if case in tuning_mixed.CASES:
                for input_seed in seed_values:
                    configurations[f"{case}:{size}:{input_seed}"] = [
                        dataclasses.asdict(configuration)
                        for configuration in tuning_mixed.configurations(
                            case, size, input_seed
                        )
                    ]
            else:
                configurations[f"{case}:{size}"] = dataclasses.asdict(
                    tuning_workloads.configuration(case, size)
                )
    manifest = {
        "python": sys.version,
        "platform": platform.platform(),
        "cpuinfo": Path("/proc/cpuinfo").read_text(),
        "meminfo": Path("/proc/meminfo").read_text(),
        "argv": sys.argv,
        "flat_limits": limits,
        "partition_counts": counts,
        "parameter_pairs": parameter_pairs,
        "scales": scale_values,
        "seeds": seed_values,
        "cases": case_names,
        "controls": control_names,
        "repetitions": repetitions,
        "order_seed": order_seed,
        "cpu": cpu,
        "timeout_s": timeout,
        "memory_limit_mib": memory_mib,
        "allocation_tracing": allocation,
        "source_sha256": source_hashes,
        "configurations": configurations,
    }
    _ = (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    click.echo(f"Results: {directory}")
    jobs: list[tuple[str, int, int, int, str, int, int]] = []
    for repetition in range(repetitions):
        for size in scale_values:
            for input_seed in seed_values:
                for case in case_names:
                    for limit, count in parameter_pairs:
                        jobs.append(
                            (
                                case,
                                size,
                                input_seed,
                                repetition,
                                "production",
                                limit,
                                count,
                            )
                        )
                    for control in control_names:
                        jobs.append(
                            (case, size, input_seed, repetition, control, 256, 1_024)
                        )
    randomizer = random.Random(order_seed)  # noqa: S311 - Reproducible measurement order.
    randomizer.shuffle(jobs)
    expected_checksums: dict[tuple[str, int, int], run.Scalar] = {}
    started = time.monotonic()
    for index, (case, size, input_seed, repetition, variant, limit, count) in enumerate(
        jobs, 1
    ):
        result = run.run_child(
            case,
            variant,
            size,
            input_seed,
            cpu,
            timeout,
            memory_mib,
            allocation=allocation,
            worker_module="destruction_contract_benchmarks.tuning_run",
            extra_arguments=(
                "--flat-limits",
                str(limit),
                "--partition-counts",
                str(count),
            ),
        )
        result.update(
            case=case,
            scale=size,
            seed=input_seed,
            repetition=repetition,
            variant=variant,
            flat_limit=limit,
            partition_count=count,
            allocation_tracing=allocation,
        )
        filename = f"{case}__s{size}__seed{input_seed}__{variant}__f{limit}_p{count}__r{repetition}.json"
        _ = (directory / filename).write_text(json.dumps(result, indent=2) + "\n")
        if result["status"] == "ok":
            checksum = expected_checksums.setdefault(
                (case, size, input_seed), result["checksum"]
            )
            if result["checksum"] != checksum:
                raise ValueError(f"inconsistent result: {filename}")
        click.echo(
            f"{index}/{len(jobs)} {filename} {result['status']} elapsed={time.monotonic() - started:.1f}s"
        )


if __name__ == "__main__":
    main()
