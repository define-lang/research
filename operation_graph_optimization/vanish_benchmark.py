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
    vanish,
    vanish_algorithm,
    vanish_workloads,
)


def main():
    """Print one reproducible process-isolated measurement as JSON."""
    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "--strategy",
        choices=[
            "base",
            "deferred",
            "direct",
            "incremental",
            "specialized",
            "vacancy_covered",
        ],
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
    generated = time.perf_counter()
    input_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    classes = {
        "deferred": vanish.Collector,
        "direct": vanish.DirectPruning,
        "incremental": vanish.Incremental,
        "specialized": vanish_algorithm.Calculator,
        "vacancy_covered": vanish_algorithm.Calculator,
    }
    started_construction = time.perf_counter()
    calculator = algorithm.Calculator()
    collector = None if strategy == "base" else classes[strategy](calculator.graph)
    for step in steps:
        occurrence = calculator.add(step.operation)
        if isinstance(collector, vanish_algorithm.Calculator):
            collector.observe(
                occurrence,
                step.operation.creators,
                step.moved,
                step.vacated,
                step.ordinary_occupants if strategy == "vacancy_covered" else (),
            )
        elif collector is not None:
            collector.observe(occurrence, step.particles, step.vacated)
    position_done = time.perf_counter()
    retained_candidates = (
        0 if collector is None else sum(map(len, collector.candidates.values()))
    )
    started_finish = time.perf_counter()
    vanishes = {} if collector is None else collector.finish()
    finished = time.perf_counter()
    digest = hashlib.sha256()
    for occurrence in range(len(calculator.graph)):
        dependencies = sorted(calculator.graph.dependencies(occurrence))
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
                "vanish_finish_seconds": finished - started_finish,
                "construction_seconds": position_done
                - started_construction
                + finished
                - started_finish,
                "candidates_before_finish": retained_candidates,
                "edges": len(calculator.graph.edges),
                "graph_digest": digest.hexdigest(),
                "digest_seconds": checked - finished,
                "input_peak_kib": input_rss,
                "peak_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            }
        )
    )


if __name__ == "__main__":
    main()
