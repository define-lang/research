"""Measure isolated destruction-state prototypes with CPU and RSS limits."""

from __future__ import annotations

import datetime
import gc
import hashlib
import json
import os
import random
import resource
import subprocess
import sys
import time
import tracemalloc
import typing
from pathlib import Path

import click

from destruction_contract_benchmarks import experiments

type Scalar = str | int | float | bool | None
type Record = dict[str, Scalar]


def _memory_status(process: str = "self") -> dict[str, int]:
    values: dict[str, int] = {}
    with Path(f"/proc/{process}/status").open() as status:
        for line in status:
            name, _, value = line.partition(":")
            if name in {"VmRSS", "VmHWM", "VmSize"}:
                values[name] = int(value.split()[0]) * 1_024
    return values


def measure(
    experiment: experiments.Experiment,
    *,
    trace_allocations: bool,
) -> Record:
    """Retain reusable action summaries while composing and reading contracts."""
    _ = gc.collect()
    before = _memory_status()
    if trace_allocations:
        tracemalloc.start()
    build_wall_start = time.perf_counter()
    build_cpu_start = time.process_time()
    experiment.build()
    build_cpu = time.process_time() - build_cpu_start
    build_wall = time.perf_counter() - build_wall_start

    query_cpu_start = time.process_time()
    query_wall_start = time.perf_counter()
    queries = experiment.query()
    query_cpu = time.process_time() - query_cpu_start
    query_wall = time.perf_counter() - query_wall_start

    traversal_cpu_start = time.process_time()
    traversal_wall_start = time.perf_counter()
    traversal = experiment.traverse()
    traversal_cpu = time.process_time() - traversal_cpu_start
    traversal_wall = time.perf_counter() - traversal_wall_start
    _ = gc.collect()
    after = _memory_status()
    allocated, allocated_peak = (
        tracemalloc.get_traced_memory() if trace_allocations else (0, 0)
    )
    if trace_allocations:
        tracemalloc.stop()
    result: Record = {
        "status": "ok",
        "lookups": queries.count,
        "parent_lookups": queries.parent_lookups,
        "enumerated_entries": traversal.count,
        "checksum": queries.checksum + traversal.checksum,
        "build_cpu_s": build_cpu,
        "build_wall_s": build_wall,
        "query_cpu_s": query_cpu,
        "query_wall_s": query_wall,
        "traversal_cpu_s": traversal_cpu,
        "traversal_wall_s": traversal_wall,
        "total_cpu_s": build_cpu + query_cpu + traversal_cpu,
        "total_wall_s": build_wall + query_wall + traversal_wall,
        "input_rss_bytes": before["VmRSS"],
        "retained_rss_bytes": after["VmRSS"],
        "peak_rss_bytes": after["VmHWM"],
        "incremental_rss_bytes": after["VmRSS"] - before["VmRSS"],
        "python_retained_bytes": allocated,
        "python_peak_bytes": allocated_peak,
    }
    result.update(experiment.dimensions())
    return result


def _worker(
    case: str, variant: str, scale: int, seed: int, *, allocation: bool
) -> Record:
    input_start = time.process_time()
    experiment = experiments.prepare(case, variant, scale, seed)
    input_cpu = time.process_time() - input_start
    result = measure(experiment, trace_allocations=allocation)
    result["input_cpu_s"] = input_cpu
    return result


def _run_child(
    case: str,
    variant: str,
    scale: int,
    seed: int,
    cpu: int,
    timeout: float,
    memory_mib: int,
    *,
    allocation: bool,
) -> Record:
    arguments = [
        sys.executable,
        "-m",
        "destruction_contract_benchmarks.run",
        "--worker",
        "--cases",
        case,
        "--variants",
        variant,
        "--scale",
        str(scale),
        "--seed",
        str(seed),
        "--cpu",
        str(cpu),
    ]
    if allocation:
        arguments.append("--allocation")
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = str(seed)
    started = time.monotonic()
    status = "ok"
    sampled_peak = 0
    with subprocess.Popen(  # noqa: S603 - Fixed worker module, argument list, no shell.
        arguments,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    ) as process:
        while process.poll() is None:
            try:
                sampled_peak = max(
                    sampled_peak, _memory_status(str(process.pid)).get("VmRSS", 0)
                )
            except FileNotFoundError:
                break
            if sampled_peak > memory_mib * 1_024 * 1_024:
                status = "memory_limit"
                process.kill()
                break
            if time.monotonic() - started > timeout:
                status = "timeout"
                process.kill()
                break
            time.sleep(0.05)
        stdout, stderr = process.communicate()
        if status != "ok":
            return {"status": status, "sampled_peak_rss_bytes": sampled_peak}
        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode, arguments, stdout, stderr
            )
    result = typing.cast("Record", json.loads(stdout))
    result["sampled_peak_rss_bytes"] = sampled_peak
    return result


@click.command()
@click.option("--cases", default=",".join(experiments.ALL_CASES), show_default=True)
@click.option("--variants", default="all", show_default=True)
@click.option("--scale", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--repetitions", type=click.IntRange(min=1), default=3, show_default=True)
@click.option("--seed", type=int, default=74_921, show_default=True)
@click.option("--cpu", type=int, default=2, show_default=True)
@click.option("--timeout", type=float, default=60.0, show_default=True)
@click.option("--memory-mib", type=int, default=1_536, show_default=True)
@click.option("--allocation", is_flag=True)
@click.option("--worker", is_flag=True, hidden=True)
@click.option(
    "--results-directory",
    type=click.Path(path_type=Path, file_okay=False),
    default="destruction_contract_benchmarks/results",
    show_default=True,
)
def main(
    *,
    cases: str,
    variants: str,
    scale: int,
    repetitions: int,
    seed: int,
    cpu: int,
    timeout: float,
    memory_mib: int,
    allocation: bool,
    worker: bool,
    results_directory: Path,
):
    """Run sequential isolated measurements, preserving every raw result."""
    case_names = cases.split(",")
    variant_names = variants.split(",")
    for case in case_names:
        if case not in experiments.ALL_CASES:
            raise click.BadParameter(f"unknown case: {case}")
        if variants != "all" and not set(variant_names).intersection(
            experiments.variants_for(case)
        ):
            raise click.BadParameter(f"no applicable variants for {case}")
    if worker:
        os.sched_setaffinity(0, {cpu})
        # RSS is limited by the parent; the virtual limit also bounds runaway
        # allocations while allowing the free-threaded allocator's reservations.
        resource.setrlimit(resource.RLIMIT_AS, (8 * 1_024**3, 8 * 1_024**3))
        result = _worker(
            case_names[0], variant_names[0], scale, seed, allocation=allocation
        )
        click.echo(json.dumps(result))
        return

    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = results_directory / timestamp
    directory.mkdir(parents=True)
    manifest: Record = {
        "python": sys.version,
        "executable": sys.executable,
        "cpu_affinity": cpu,
        "cases": cases,
        "variants": variants,
        "scale": scale,
        "seed": seed,
        "repetitions": repetitions,
        "allocation_tracing": allocation,
        "timeout_s": timeout,
        "memory_limit_mib": memory_mib,
    }
    source_hash = hashlib.sha256()
    for source_file in sorted(Path(__file__).parent.glob("*.py")):
        source_hash.update(source_file.name.encode())
        source_hash.update(source_file.read_bytes())
    manifest["source_sha256"] = source_hash.hexdigest()
    with (directory / "manifest.json").open("x") as manifest_file:
        json.dump(manifest, manifest_file, indent=2)
        _ = manifest_file.write("\n")
    click.echo(f"Results: {directory}")
    randomizer = random.Random(seed)  # noqa: S311 - Repeat the same randomized job order.
    expected_checksums: dict[str, Scalar] = {}
    for repetition in range(repetitions):
        jobs: list[tuple[str, str]] = []
        for case in case_names:
            for variant in experiments.variants_for(case):
                if variants == "all" or variant in variant_names:
                    jobs.append((case, variant))
        randomizer.shuffle(jobs)
        for case, variant in jobs:
            result = _run_child(
                case,
                variant,
                scale,
                seed,
                cpu,
                timeout,
                memory_mib,
                allocation=allocation,
            )
            result.update(
                case=case,
                variant=variant,
                scale=scale,
                repetition=repetition,
                allocation_tracing=allocation,
            )
            if result["status"] == "ok":
                expected_checksum = expected_checksums.setdefault(
                    case, result["checksum"]
                )
                if expected_checksum != result["checksum"]:
                    raise ValueError(f"inconsistent result for {case}: {result}")
            with (directory / f"{case}__{variant}__{repetition}.json").open("x") as raw:
                json.dump(result, raw, indent=2)
                _ = raw.write("\n")
            click.echo(json.dumps(result))


if __name__ == "__main__":
    main()
