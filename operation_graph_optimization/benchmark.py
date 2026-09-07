"""Reproducible standalone rule benchmarks with bounded process resources."""

from __future__ import annotations

import json
import platform
import resource
import time

import click

from operation_graph_optimization import (
    algorithm,
    order_variants,
    state_workloads,
    validation,
    workloads,
)


@click.command()
@click.option(
    "--workload",
    type=click.Choice(
        [
            "interleaved",
            "overlapping",
            "uses",
            "implied",
            "shared",
            "vacancy",
            "vacancy_long",
            "destruction",
            "shared_join",
            "deep",
            "multiple_shared",
            "state",
        ]
    ),
    required=True,
)
@click.option("--steps", type=click.IntRange(min=1), default=100_000)
@click.option("--width", type=click.IntRange(min=1), default=100)
@click.option("--seed", type=int, default=17)
@click.option("--cache-targets", type=click.IntRange(min=0), default=1024)
@click.option("--cache-mib", type=click.IntRange(min=0), default=64)
@click.option("--depth", type=click.IntRange(min=0), default=4)
@click.option("--branching", type=click.IntRange(min=1), default=2)
@click.option("--access", type=click.Choice(["local", "implied"]), default="local")
@click.option("--reorder-seed", type=int, default=None)
@click.option(
    "--distribution",
    type=click.Choice(
        [
            "balanced",
            "concrete",
            "growth",
            "movement",
            "destruction",
        ]
    ),
    default="balanced",
)
@click.option("--memory-mib", type=click.IntRange(min=64), default=2048)
@click.option("--cpu-seconds", type=click.IntRange(min=1), default=120)
def main(
    workload: str,
    steps: int,
    width: int,
    seed: int,
    cache_targets: int,
    cache_mib: int,
    depth: int,
    branching: int,
    access: str,
    reorder_seed: int | None,
    distribution: str,
    memory_mib: int,
    cpu_seconds: int,
):
    """Measure generation separately from calculation and graph checks."""
    memory_bytes = memory_mib * 1024**2
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    generators = {
        "interleaved": workloads.interleaved_moves,
        "overlapping": workloads.overlapping_moves,
        "uses": workloads.preceding_uses,
        "implied": workloads.implied_uses,
        "shared": workloads.shared_parent,
        "vacancy": workloads.vacancy_reuse,
        "vacancy_long": workloads.long_vacancy_reuse,
        "shared_join": workloads.shared_join,
        "multiple_shared": workloads.multiple_shared_parents,
    }
    start = time.perf_counter()
    vacancies: list[algorithm.Operation] = []
    groups: dict[int, int] = {}
    if workload == "state":
        operations, groups = state_workloads.generate(
            seed,
            steps,
            width,
            depth,
            branching,
            distribution,
            access,
        )
    elif workload == "destruction":
        operations, vacancies = workloads.simultaneous_destruction(seed, steps, width)
    elif workload == "deep":
        program = workloads.tree_program(seed, steps, depth=width)
        operations, vacancies = program.operations, program.simultaneous
    else:
        operations = list(generators[workload](seed, steps, width))
    generated = time.perf_counter()
    generation_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if vacancies:
        groups[len(operations)] = len(vacancies)
        operations.extend(vacancies)
    if reorder_seed is not None:
        operations, groups, _ = order_variants.reorder(operations, groups, reorder_seed)
    reordered = time.perf_counter()
    calculator = algorithm.Calculator(cache_targets, cache_mib * 1024**2)
    occurrence = 0
    while occurrence < len(operations):
        count = groups.get(occurrence, 1)
        if count > 1:
            _ = calculator.simultaneous(operations[occurrence : occurrence + count])
        else:
            _ = calculator.add(operations[occurrence])
        occurrence += count
    calculated = time.perf_counter()
    calculation_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    validation.check_random_schedule(operations, calculator.graph, seed + 1)
    checked = time.perf_counter()
    position_requirements = 0
    particle_requirements = 0
    defined_positions = 0
    creates = moves = destroys = longest_reference = 0
    for operation in operations:
        if operation.empty is None:
            creates += 1
        elif operation.fill is None:
            destroys += 1
        else:
            moves += 1
        longest_reference = max(longest_reference, len(operation.occupied))
        position_requirements += len(operation.occupied)
        position_requirements += int(operation.fill is not None)
        position_requirements += int(operation.empty is not None)
        particle_requirements += len(operation.creators)
        defined_positions += len(operation.defines)
    print(
        json.dumps(
            {
                "workload": workload,
                "steps": steps,
                "width": width,
                "seed": seed,
                "cache_targets": cache_targets,
                "cache_mib": cache_mib,
                "depth": depth,
                "branching": branching,
                "access": access,
                "reorder_seed": reorder_seed,
                "distribution": distribution,
                "simultaneous_groups": len(groups),
                "operations": len(calculator.graph),
                "edges": len(calculator.graph.edges),
                "position_requirements": position_requirements,
                "particle_requirements": particle_requirements,
                "defined_positions": defined_positions,
                "creates": creates,
                "moves": moves,
                "destroys": destroys,
                "max_occupied_requirements": longest_reference,
                "generation_seconds": generated - start,
                "generation_peak_rss_kib": generation_peak,
                "calculation_peak_rss_kib": calculation_peak,
                "reorder_seconds": reordered - generated,
                "calculation_seconds": calculated - reordered,
                "check_seconds": checked - calculated,
                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "python": platform.python_version(),
                "platform": platform.platform(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
