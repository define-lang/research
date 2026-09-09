"""Preserve isolated timings, allocation peaks, and complete graph fingerprints."""

from __future__ import annotations

import gc
import json
import pathlib
import platform
import random
import resource
import subprocess
import sys
import time
import tracemalloc

import click

from operation_graph_optimization import simplification_experiment as experiment


def measure(
    family: str,
    seed: int,
    count: int,
    width: int,
    repeat: int,
    variants: list[str],
    *,
    memory: bool,
):
    """Time only construction, with allocation tracing in separate executions."""
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    prepared = experiment.prepare(family, seed, count, width)
    randomizer = random.Random(seed + 1701)  # noqa: S311 - Reproducible measurement order.
    samples: dict[str, list[float]] = {variant: [] for variant in variants}
    reference_digest = None
    records: dict[str, dict[str, object]] = {}
    for _ in range(repeat):
        order = list(variants)
        randomizer.shuffle(order)
        for variant in order:
            _ = gc.collect()
            started = time.perf_counter()
            calculated, vanishes = experiment.construct(variant, prepared)
            elapsed = time.perf_counter() - started
            samples[variant].append(elapsed)
            digest = experiment.fingerprint(calculated, vanishes, len(prepared.steps))
            if reference_digest is None:
                reference_digest = digest
            if digest != reference_digest:
                raise ValueError(f"Graph mismatch for {variant}")
            records[variant] = {
                "nodes": len(calculated),
                "edges": len(calculated.edges),
                "digest": digest,
            }
            del calculated, vanishes
    for variant in variants:
        if memory:
            _ = gc.collect()
            tracemalloc.start()
            calculated, vanishes = experiment.construct(variant, prepared)
            peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            records[variant]["peak_bytes"] = peak
            del calculated, vanishes
        records[variant]["seconds"] = samples[variant]
    return {
        "family": family,
        "seed": seed,
        "requested_steps": count,
        "width": width,
        "operations": len(prepared.steps),
        "variants": records,
    }


@click.command()
@click.option("--destination", type=click.Path(path_type=pathlib.Path))
@click.option("--families", default=",".join(experiment.FAMILIES))
@click.option("--seeds", default="17,43,91")
@click.option("--count", default=20000)
@click.option("--width", default=100)
@click.option("--repeat", default=3)
@click.option("--variants", default=",".join(experiment.VARIANTS))
@click.option("--child", is_flag=True)
@click.option("--memory/--no-memory", default=True)
def main(
    destination: pathlib.Path | None,
    families: str,
    seeds: str,
    count: int,
    width: int,
    repeat: int,
    variants: str,
    *,
    child: bool,
    memory: bool,
):
    """Run each workload in a fresh process and retain timeout evidence."""
    if child:
        print(
            json.dumps(
                measure(
                    families,
                    int(seeds),
                    count,
                    width,
                    repeat,
                    variants.split(","),
                    memory=memory,
                )
            )
        )
        return
    if destination is None:
        raise click.UsageError("--destination is required")
    sources = {}
    directory = pathlib.Path(__file__).parent
    for path in directory.glob("*.py"):
        sources[path.name] = path.read_text()
    for name in ["complete/algorithm.py", "complete/graph.py"]:
        sources[name] = (directory / name).read_text()
    with destination.open("x") as stream:
        _ = stream.write(
            json.dumps(
                {
                    "platform": platform.platform(),
                    "python": sys.version,
                    "sources": sources,
                }
            )
            + "\n"
        )
        for family in families.split(","):
            for seed in seeds.split(","):
                command = [
                    sys.executable,
                    "-m",
                    "operation_graph_optimization.simplification_benchmark",
                    "--child",
                    "--families",
                    family,
                    "--seeds",
                    seed,
                    "--count",
                    str(count),
                    "--width",
                    str(width),
                    "--repeat",
                    str(repeat),
                    "--variants",
                    variants,
                    "--memory" if memory else "--no-memory",
                ]
                try:
                    completed = subprocess.run(  # noqa: S603 - Fixed module and interpreter.
                        command,
                        capture_output=True,
                        text=True,
                        timeout=180,
                        check=False,
                    )
                    record = {
                        "command": command,
                        "returncode": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    }
                except subprocess.TimeoutExpired:
                    record = {"command": command, "failure": "180 second timeout"}
                _ = stream.write(json.dumps(record) + "\n")
                stream.flush()
                print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
