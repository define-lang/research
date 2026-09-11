"""Compare full identified-operation construction with the prior backend."""

from __future__ import annotations

import argparse
import dataclasses
import functools
import json
import platform
import random
import sys
import time

from operation_graph_optimization import (
    identity_algorithm,
    relationship_benchmark,
    relationship_periods,
    relationship_state,
)
from operation_graph_optimization.complete import algorithm, graph


@dataclasses.dataclass
class Workload:
    """Equivalent resolved inputs for the two construction backends."""

    operations: list[identity_algorithm.Operation]
    parents: tuple[int | None, ...]
    previous_operations: list[algorithm.Operation]


def generate(count: int, seed: int, depth: int):
    """Randomize all ready Creates and same-parent Moves in a bounded-depth tree."""
    generator = random.Random(seed)  # noqa: S311 - Reproducible benchmark generation.
    owners: list[int | None] = [None]
    children: list[list[int]] = [[] for _ in range(count)]
    depths = [0]
    available_parents = [0]
    for particle in range(1, count):
        parent = generator.choice(available_parents)
        owners.append(parent)
        children[parent].append(particle)
        depths.append(depths[parent] + 1)
        if depths[-1] < depth:
            available_parents.append(particle)
    parents = tuple(owners + owners)
    operations: list[identity_algorithm.Operation] = []
    ready = [(0, 0)]
    while ready:
        selected = generator.randrange(len(ready))
        particle, phase = ready[selected]
        ready[selected] = ready[-1]
        _ = ready.pop()
        if phase == 0:
            operations.append(
                identity_algorithm.Create(f"create({particle})", particle, particle)
            )
            for child in children[particle]:
                ready.append((child, 0))
        elif phase == 1:
            operations.append(
                identity_algorithm.Move(
                    f"move_out({particle})", particle, particle, count + particle
                )
            )
        else:
            operations.append(
                identity_algorithm.Move(
                    f"move_back({particle})", particle, count + particle, particle
                )
            )
        if phase < 2:
            ready.append((particle, phase + 1))
    destroyed = list(range(count))
    generator.shuffle(destroyed)
    for particle in destroyed:
        operations.append(
            identity_algorithm.Vacate(f"vacate({particle})", particle, particle, 0)
        )
    for particle in destroyed:
        operations.append(identity_algorithm.Vanish(f"vanish({particle})", particle))

    return make_workload(operations, parents)


def make_workload(
    operations: list[identity_algorithm.Operation], parents: tuple[int | None, ...]
):
    """Express the same identified effects for both graph constructors."""
    count = max(operation.particle for operation in operations) + 1
    defined: list[list[int]] = [[] for _ in range(count)]
    for position, parent in enumerate(parents):
        if parent is not None:
            defined[parent].append(position)
    creates: dict[int, int] = {}
    previous: list[algorithm.Operation] = []
    for operation in operations:
        if isinstance(operation, identity_algorithm.Vanish):
            continue
        if isinstance(operation, identity_algorithm.Create):
            parent = parents[operation.target]
            qualities = () if parent is None else (creates[parent],)
            creates[operation.particle] = len(previous)
            previous.append(
                algorithm.Operation(
                    fill=operation.target,
                    quality_particles=qualities,
                    defines=tuple(defined[operation.particle]),
                )
            )
        elif isinstance(operation, identity_algorithm.Move):
            required_parents: set[int] = set()
            for position in (operation.source, operation.target):
                parent = parents[position]
                if parent is not None:
                    required_parents.add(creates[parent])
            previous.append(
                algorithm.Operation(
                    empty=operation.source,
                    fill=operation.target,
                    quality_particles=tuple(required_parents),
                    moved=creates[operation.particle],
                )
            )
        elif isinstance(operation, identity_algorithm.Vacate):
            parent = parents[operation.position]
            qualities = () if parent is None else (creates[parent],)
            previous.append(
                algorithm.Operation(
                    empty=operation.position,
                    quality_particles=qualities,
                    vacated=creates[operation.particle],
                )
            )
        else:
            raise TypeError(operation)
    return Workload(operations, parents, previous)


def previous_construct(operations: list[algorithm.Operation]) -> graph.Graph:
    """Use the unchanged prior backend with the same identified requirements."""
    calculator = algorithm.Calculator()
    for operation in operations:
        _ = calculator.add(operation)
    _ = calculator.finish()
    return calculator.graph


def complete_construct(workload: Workload):
    """Construct ordinary dependencies, lifetime dependencies, and all conditions."""
    constructed = identity_algorithm.construct(workload.operations, workload.parents)
    conditions = relationship_periods.cycle_clauses(constructed.periods)
    return constructed, conditions


def partitioned_construct(workload: Workload):
    """Construct the full graph and prepare local relationship searches."""
    constructed = identity_algorithm.construct(workload.operations, workload.parents)
    searches = relationship_state.PartitionedSearch(
        constructed.periods,
        constructed.dependencies.dependencies,
        constructed.dependencies.indexed_dependents,
    )
    return constructed, searches


def main():
    """Measure complete collection, including deferred Vanishes and periods."""
    parser = argparse.ArgumentParser(description=__doc__)
    arguments = relationship_benchmark.Arguments([1000, 10000, 100000], 3)
    _ = parser.add_argument("--sizes", nargs="+", type=int, default=arguments.sizes)
    _ = parser.add_argument("--repeats", type=int, default=arguments.repeats)
    arguments = parser.parse_args(namespace=arguments)
    rows: list[dict[str, object]] = []
    for count in arguments.sizes:
        started = time.perf_counter()
        workload = generate(count, 711039, 6)
        generation = time.perf_counter() - started
        actual = identity_algorithm.construct(workload.operations, workload.parents)
        prior = previous_construct(workload.previous_operations)
        if len(actual.dependencies) != len(prior):
            raise AssertionError("Construction operation counts differ")
        for operation in range(len(prior)):
            if set(actual.dependencies.dependencies(operation)) != set(
                prior.dependencies(operation)
            ):
                raise AssertionError(
                    "Equivalent resolved requirements produced different edges"
                )
        del actual, prior
        rows.append(
            {
                "particles": count,
                "operations": len(workload.operations),
                "seed": 711039,
                "depth_limit": 6,
                "generation_seconds": generation,
                "identity_construction": relationship_benchmark.measure(
                    functools.partial(
                        identity_algorithm.construct,
                        workload.operations,
                        workload.parents,
                    ),
                    arguments.repeats,
                ),
                "including_relationship_conditions": relationship_benchmark.measure(
                    functools.partial(complete_construct, workload), arguments.repeats
                ),
                "including_partitioned_searches": relationship_benchmark.measure(
                    functools.partial(partitioned_construct, workload),
                    arguments.repeats,
                ),
                "previous_backend": relationship_benchmark.measure(
                    functools.partial(previous_construct, workload.previous_operations),
                    arguments.repeats,
                ),
            }
        )
    print(
        json.dumps(
            {"python": sys.version, "platform": platform.platform(), "rows": rows},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
