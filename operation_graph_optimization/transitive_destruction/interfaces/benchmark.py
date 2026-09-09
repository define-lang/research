"""Measure fixed action-description construction separately from generation."""

from __future__ import annotations

import gc
import json
import random
import statistics
import time
import tracemalloc

import click

from operation_graph_optimization.transitive_destruction.interfaces import (
    compiler,
    descriptions,
)


@click.command()
@click.option("--width", type=int, required=True)
@click.option("--steps", type=int, required=True)
@click.option("--depth", type=int, default=0)
@click.option("--seed", type=int, default=0)
@click.option("--repeat", type=int, default=5)
def main(width: int, steps: int, depth: int, seed: int, repeat: int):
    """Report prototype costs, not production compiler or scheduler performance."""
    program = descriptions.generate(seed, width, steps, depth)
    template = compiler.compile_action(program.callee)
    variants: list[compiler.Variant] = ["explicit", "lowered", "records"]
    samples: dict[str, list[float]] = {variant: [] for variant in variants}
    randomizer = random.Random(seed)  # noqa: S311 - Balanced measurement order.
    for variant in variants:
        _ = compiler.construct(program, variant, template)
    for _ in range(repeat):
        randomizer.shuffle(variants)
        for variant in variants:
            _ = gc.collect()
            start = time.perf_counter()
            result = compiler.construct(program, variant, template)
            elapsed = time.perf_counter() - start
            samples[variant].append(elapsed)
            del result
    rows: list[dict[str, object]] = []
    for variant in variants:
        _ = gc.collect()
        tracemalloc.start()
        result = compiler.construct(program, variant, template)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rows.append(
            {
                "variant": variant,
                "seconds": samples[variant],
                "median_seconds": statistics.median(samples[variant]),
                "peak_bytes": peak,
                "analysis_nodes": result.analysis_nodes,
                "runtime_nodes": len(result.labels),
                "runtime_edges": len(result.graph.edges),
                "boundary_records": result.boundary_records,
                "boundary_references": result.boundary_references,
            }
        )
        del result
    arguments = {
        "width": width,
        "steps": steps,
        "depth": depth,
        "seed": seed,
        "repeat": repeat,
    }
    print(json.dumps({"arguments": arguments, "results": rows}, sort_keys=True))


if __name__ == "__main__":
    main()
