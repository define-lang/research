"""Measure complete lifetime collection and graph construction separately."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import struct
import time
from typing import cast

from operation_graph_optimization import (
    algorithm,
    integrated_variants,
    vanish_algorithm,
    vanish_workloads,
)
from operation_graph_optimization.integrated import algorithm as integrated


def main():
    """Print one reproducible process-isolated measurement as JSON."""
    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "--strategy",
        choices=["baseline", "collected", "direct", "unpruned", "indexed"],
        required=True,
    )
    _ = parser.add_argument(
        "--family",
        choices=[
            "local",
            "movement",
            "implied",
            "written",
            "wide",
            "state",
            "growth",
            "growth_closed",
        ],
        required=True,
    )
    _ = parser.add_argument("--steps", type=int, default=10000)
    _ = parser.add_argument("--width", type=int, default=100)
    _ = parser.add_argument("--seed", type=int, default=17)
    arguments = parser.parse_args()
    family = cast("str", arguments.family)
    seed = cast("int", arguments.seed)
    count = cast("int", arguments.steps)
    width = cast("int", arguments.width)
    strategy = cast("str", arguments.strategy)
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    started = time.perf_counter()
    steps = vanish_workloads.generate(family, seed, count, width)
    operations = [integrated_variants.convert(step) for step in steps]
    generated = time.perf_counter()
    input_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    classes = {
        "collected": integrated.Calculator,
        "direct": integrated_variants.Direct,
        "unpruned": integrated_variants.Unpruned,
        "indexed": integrated_variants.Indexed,
    }
    started_construction = time.perf_counter()
    if strategy == "baseline":
        calculator = algorithm.Calculator()
        collector = vanish_algorithm.Calculator(calculator.graph)
        for step in steps:
            occurrence = calculator.add(step.operation)
            collector.observe(
                occurrence,
                step.operation.creators,
                step.moved,
                step.vacated,
                step.ordinary_occupants,
            )
        position_done = time.perf_counter()
        vanishes = collector.finish()
        calculated = calculator.graph
    else:
        combined = classes[strategy]()
        for operation in operations:
            _ = combined.add(operation)
        position_done = time.perf_counter()
        vanishes = combined.finish()
        calculated = combined.graph
    finished = time.perf_counter()
    digest = hashlib.sha256()
    for occurrence in range(len(calculated)):
        dependencies = sorted(calculated.dependencies(occurrence))
        digest.update(struct.pack("<Q", len(dependencies)))
        for dependency in dependencies:
            digest.update(struct.pack("<Q", dependency))
    checked = time.perf_counter()
    print(
        json.dumps(
            {
                **vars(arguments),
                "python": platform.python_version(),
                "operations": len(steps),
                "vanishes": len(vanishes),
                "generation_seconds": generated - started,
                "position_and_collection_seconds": position_done - started_construction,
                "vanish_finish_seconds": finished - position_done,
                "construction_seconds": finished - started_construction,
                "edges": len(calculated.edges),
                "graph_digest": digest.hexdigest(),
                "digest_seconds": checked - finished,
                "input_peak_kib": input_rss,
                "peak_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            }
        )
    )


if __name__ == "__main__":
    main()
