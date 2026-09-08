"""Measure complete lifetime collection and graph construction separately."""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import platform
import resource
import struct
import time
import tracemalloc
from typing import cast

from operation_graph_optimization import (
    algorithm,
    combination_algorithm,
    combination_inputs,
    complete_inputs,
    complete_workloads,
    integrated_bounded,
    integrated_compact,
    integrated_inline,
    integrated_resolved,
    integrated_variants,
    integrated_workloads,
    vanish_algorithm,
    vanish_workloads,
    workloads,
)
from operation_graph_optimization.complete import algorithm as complete
from operation_graph_optimization.integrated import algorithm as integrated


def main():
    """Print one reproducible process-isolated measurement as JSON."""
    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "--strategy",
        choices=[
            "pre_vanish",
            "early_combination",
            "late_combination",
            "baseline",
            "collected",
            "direct",
            "unpruned",
            "indexed",
            "compact",
            "bounded",
            "inline",
            "resolved",
            "final",
        ],
        required=True,
    )
    _ = parser.add_argument(
        "--family",
        choices=[
            "retained",
            "deep6",
            "deep20",
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
    _ = parser.add_argument("--trace-memory", action="store_true")
    arguments = parser.parse_args()
    family = cast("str", arguments.family)
    seed = cast("int", arguments.seed)
    count = cast("int", arguments.steps)
    width = cast("int", arguments.width)
    strategy = cast("str", arguments.strategy)
    trace_memory = cast("bool", arguments.trace_memory)
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    started = time.perf_counter()
    retentions: dict[int, dict[int, int]] = {}
    if family == "retained":
        steps, retentions = integrated_workloads.retained(seed, count, width)
    elif family in {"deep6", "deep20"}:
        depth = 6 if family == "deep6" else 20
        program = workloads.tree_program(seed, count // 4, depth, width)
        steps = complete_workloads.resolve_program(program)
        del program
    else:
        steps = vanish_workloads.generate(family, seed, count, width)
    operations = [integrated_variants.convert(step) for step in steps]
    final_operations = [complete_inputs.convert(step) for step in steps]
    combined_operations = [combination_inputs.convert(step) for step in steps]
    generated = time.perf_counter()
    input_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    classes = {
        "inline": integrated_inline.Calculator,
        "resolved": integrated_resolved.Calculator,
        "compact": integrated_compact.Calculator,
        "bounded": integrated_bounded.Calculator,
        "collected": integrated.Calculator,
        "direct": integrated_variants.Direct,
        "unpruned": integrated_variants.Unpruned,
        "indexed": integrated_variants.Indexed,
    }
    if trace_memory:
        tracemalloc.start()
    started_classification = time.perf_counter()
    separate: set[int] = set()
    if strategy == "early_combination":
        separate = combination_inputs.classify(steps)
    elif strategy == "late_combination":
        for step in steps:
            separate.update(step.particles)
            if step.vacated is not None:
                separate.add(step.vacated)
    classification_seconds = time.perf_counter() - started_classification
    started_cpu = time.process_time()
    started_construction = time.perf_counter()
    if strategy == "pre_vanish":
        calculator = algorithm.Calculator()
        for index, step in enumerate(steps):
            if index in retentions:
                calculator.retain(retentions[index])
            _ = calculator.add(step.operation)
        position_done = time.perf_counter()
        vanishes: dict[int, int] = {}
        calculated = calculator.graph
    elif strategy in {"early_combination", "late_combination"}:
        combined_calculator = combination_algorithm.Calculator(separate)
        for index, operation in enumerate(combined_operations):
            if index in retentions:
                combined_calculator.retain(retentions[index])
            _ = combined_calculator.add(operation)
        position_done = time.perf_counter()
        vanishes = combined_calculator.finish()
        calculated = combined_calculator.graph
    elif strategy == "baseline":
        calculator = algorithm.Calculator()
        collector = vanish_algorithm.Calculator(calculator.graph)
        for index, step in enumerate(steps):
            if index in retentions:
                calculator.retain(retentions[index])
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
    elif strategy == "final":
        final_calculator = complete.Calculator()
        for index, operation in enumerate(final_operations):
            if index in retentions:
                final_calculator.retain(retentions[index])
            _ = final_calculator.add(operation)
        position_done = time.perf_counter()
        vanishes = final_calculator.finish()
        calculated = final_calculator.graph
    else:
        combined = classes[strategy]()
        for index, operation in enumerate(operations):
            if index in retentions:
                combined.retain(retentions[index])
            _ = combined.add(operation)
        position_done = time.perf_counter()
        vanishes = combined.finish()
        calculated = combined.graph
    finished = time.perf_counter()
    construction_cpu = time.process_time() - started_cpu
    traced_peak = tracemalloc.get_traced_memory()[1] if trace_memory else None
    if trace_memory:
        tracemalloc.stop()
    storage_bytes = 0
    for value in cast("dict[str, object]", vars(calculated)).values():
        if isinstance(value, array.array):
            storage_bytes += len(value) * value.itemsize
    digest = hashlib.sha256()
    ordered_digest = hashlib.sha256()
    ordered_digest.update(calculated.offsets)
    ordered_digest.update(calculated.edges)
    for occurrence in range(len(calculated)):
        dependencies = sorted(calculated.dependencies(occurrence))
        digest.update(struct.pack("<Q", len(dependencies)))
        for dependency in dependencies:
            digest.update(struct.pack("<Q", dependency))
    position_digest = hashlib.sha256()
    for occurrence in range(len(steps)):
        dependencies = sorted(calculated.dependencies(occurrence))
        position_digest.update(struct.pack("<Q", len(dependencies)))
        for dependency in dependencies:
            position_digest.update(struct.pack("<Q", dependency))
    lifetime_digest = hashlib.sha256()
    combined_count = 0
    for particle in sorted(vanishes):
        occurrence = vanishes[particle]
        if occurrence < len(steps):
            dependencies = [occurrence]
            combined_count += 1
        else:
            dependencies = sorted(calculated.dependencies(occurrence))
        lifetime_digest.update(struct.pack("<QQ", particle, len(dependencies)))
        for dependency in dependencies:
            lifetime_digest.update(struct.pack("<Q", dependency))
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
                "classification_seconds": classification_seconds,
                "construction_with_classification_seconds": finished
                - started_construction
                + classification_seconds,
                "combined_vanishes": combined_count,
                "separate_particle_candidates": len(separate),
                "position_digest": position_digest.hexdigest(),
                "lifetime_digest": lifetime_digest.hexdigest(),
                "construction_cpu_seconds": construction_cpu,
                "edges": len(calculated.edges),
                "graph_storage_bytes": storage_bytes,
                "construction_traced_peak_bytes": traced_peak,
                "graph_digest": digest.hexdigest(),
                "ordered_graph_digest": ordered_digest.hexdigest(),
                "digest_seconds": checked - finished,
                "input_peak_kib": input_rss,
                "peak_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            }
        )
    )


if __name__ == "__main__":
    main()
