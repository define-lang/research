"""Measure graph construction separately from selecting and resolving operations."""

from __future__ import annotations

import gc
import hashlib
import json
import time
import tracemalloc
from typing import TYPE_CHECKING

import click

from operation_graph_optimization import combination_algorithm, combination_inputs
from operation_graph_optimization.transitive_destruction import experiment, snapshot

if TYPE_CHECKING:
    from operation_graph_optimization.complete import graph


def digest(
    calculated: graph.Graph,
    vanishes: dict[int, int],
    scenario: experiment.Scenario,
    prepared: experiment.Prepared,
    *,
    proposed: bool,
) -> str:
    """Normalize away only transitive Vacates after construction timing ends."""
    reverse = {new: old for old, new in prepared.occurrences.items()}
    hashed = hashlib.sha256()
    for old, new in prepared.occurrences.items():
        dependencies = calculated.dependencies(new if proposed else old)
        previous = (
            sorted(reverse[p] for p in dependencies)
            if proposed
            else sorted(dependencies)
        )
        hashed.update(repr((old, previous)).encode())
    keyed: dict[int, int] = {}
    for particle, vanish in vanishes.items():
        keyed[reverse[particle] if proposed else particle] = vanish
    ordinary_count = len(prepared.operations) if proposed else len(scenario.steps)
    for particle, vanish in sorted(keyed.items()):
        if vanish < ordinary_count:
            candidates = {vanish}
        else:
            candidates = set(calculated.dependencies(vanish))
        if proposed:
            previous = sorted(reverse[p] for p in candidates)
        else:
            expanded: set[int] = set()
            for candidate in candidates:
                if candidate in scenario.transitive:
                    expanded.update(calculated.dependencies(candidate))
                else:
                    expanded.add(candidate)
            previous = sorted(combination_algorithm.compare(calculated, expanded))
        hashed.update(repr(("vanish", particle, previous)).encode())
    return hashed.hexdigest()


@click.command()
@click.option(
    "--family", type=click.Choice(["written", "implied", "retained"]), required=True
)
@click.option(
    "--strategy", type=click.Choice(["current", "proposed", "snapshot"]), required=True
)
@click.option("--steps", type=int, default=100000)
@click.option("--width", type=int, default=32)
@click.option("--seed", type=int, default=17)
@click.option("--memory", is_flag=True)
def main(
    family: str, strategy: str, steps: int, width: int, seed: int, *, memory: bool
):
    """Run one fresh-process measurement with precomputed valid inputs."""
    if family == "retained":
        scenario = experiment.retained(seed, steps, width)
    else:
        scenario = experiment.cascade(
            seed,
            steps,
            width,
            implied=family == "implied",
        )
    operations = [combination_inputs.convert(step) for step in scenario.steps]
    separate = combination_inputs.classify(scenario.steps)
    prepared = experiment.prepare(scenario)
    _ = gc.collect()
    if memory:
        tracemalloc.start()
    started = time.perf_counter()
    if strategy == "proposed":
        candidate, vanishes = experiment.construct(prepared)
        calculated = candidate.graph
    elif strategy == "snapshot":
        selected = snapshot.Calculator(prepared.separate, prepared.transitive)
        for occurrence, operation in enumerate(prepared.operations):
            for particle, position in prepared.selections.get(occurrence, []):
                selected.select_transitively(particle, position)
            if occurrence in prepared.retentions:
                selected.retain(prepared.retentions[occurrence])
            _ = selected.add(operation)
        for particle, position in prepared.selections.get(len(prepared.operations), []):
            selected.select_transitively(particle, position)
        vanishes = selected.finish()
        calculated = selected.graph
    else:
        baseline = combination_algorithm.Calculator(separate)
        for occurrence, operation in enumerate(operations):
            if occurrence in scenario.retentions:
                baseline.retain(scenario.retentions[occurrence])
            _ = baseline.add(operation)
        vanishes = baseline.finish()
        calculated = baseline.graph
    elapsed = time.perf_counter() - started
    peak = tracemalloc.get_traced_memory()[1] if memory else None
    if memory:
        tracemalloc.stop()
    result = {
        "family": family,
        "strategy": strategy,
        "steps": steps,
        "width": width,
        "seed": seed,
        "memory": memory,
        "seconds": elapsed,
        "construction_peak_bytes": peak,
        "original_operations": len(scenario.steps),
        "transitive_vacates": len(scenario.transitive),
        "vertices": len(calculated),
        "edges": len(calculated.edges),
        "digest": digest(
            calculated,
            vanishes,
            scenario,
            prepared,
            proposed=strategy != "current",
        ),
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
