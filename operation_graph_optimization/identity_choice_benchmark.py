"""Full construction with many independently randomized competing Moves."""

from __future__ import annotations

import argparse
import functools
import json
import platform
import random
import sys
import time

from operation_graph_optimization import (
    identity_algorithm,
    identity_benchmark,
    relationship_benchmark,
)


def generate(count: int, seed: int):
    """Choose uniformly among all currently valid Creates and Moves."""
    generator = random.Random(seed)  # noqa: S311 - Reproducible source generation.
    parents: list[int | None] = []
    for group in range(count):
        parent, child, third = 3 * group, 3 * group + 1, 3 * group + 2
        parents.extend((None, parent, None, None, third, child))
    completed = [0] * count
    ready: list[tuple[int, int]] = []
    ready_indices: dict[tuple[int, int], int] = {}
    for group in range(count):
        for operation in (0, 2):
            ready_indices[group, operation] = len(ready)
            ready.append((group, operation))
    operations: list[identity_algorithm.Operation] = []
    vanishes: list[identity_algorithm.Vanish] = []
    prerequisites = (0, 1, 0, 2, 5, 6)
    while ready:
        group, selected = ready[generator.randrange(len(ready))]
        # A competing Move can cease to be ready. Recompute this group's
        # entire valid choice set, not just newly satisfied prerequisites.
        for operation in range(6):
            index = ready_indices.pop((group, operation), None)
            if index is not None:
                last = ready.pop()
                if index < len(ready):
                    ready[index] = last
                    ready_indices[last] = index
        completed[group] |= 1 << selected
        parent, child, third = 3 * group, 3 * group + 1, 3 * group + 2
        position = 6 * group
        if selected == 0:
            operations.append(
                identity_algorithm.Create(f"create({parent})", parent, position)
            )
        elif selected == 1:
            operations.append(
                identity_algorithm.Create(f"create({child})", child, position + 1)
            )
        elif selected == 2:
            operations.append(
                identity_algorithm.Create(f"create({third})", third, position + 2)
            )
        elif selected == 3:
            operations.append(
                identity_algorithm.Move(
                    f"move({child})", child, position + 1, position + 3
                )
            )
        elif selected == 4:
            operations.append(
                identity_algorithm.Move(
                    f"move({parent})", parent, position, position + 4
                )
            )
        else:
            operations.append(
                identity_algorithm.Move(
                    f"move({third})", third, position + 2, position + 5
                )
            )
        if completed[group] == 63:
            selected_particles = [
                (parent, position + 4),
                (child, position + 3),
                (third, position + 5),
            ]
            generator.shuffle(selected_particles)
            for particle, occupied in selected_particles:
                operations.append(
                    identity_algorithm.Vacate(
                        f"vacate({particle})", particle, occupied, group
                    )
                )
                vanishes.append(
                    identity_algorithm.Vanish(f"vanish({particle})", particle)
                )
            continue
        for operation, required in enumerate(prerequisites):
            state = completed[group]
            if state & (1 << operation) or state & required != required:
                continue
            if operation == 4 and state & 32 and not state & 8:
                continue
            if operation == 5 and state & 16 and not state & 8:
                continue
            ready_indices[group, operation] = len(ready)
            ready.append((group, operation))
    operations.extend(vanishes)
    return identity_benchmark.make_workload(operations, tuple(parents))


def main():
    """Time full graph construction separately from valid-order selection."""
    parser = argparse.ArgumentParser(description=__doc__)
    arguments = relationship_benchmark.Arguments([100, 1000, 10000], 3)
    _ = parser.add_argument("--sizes", nargs="+", type=int, default=arguments.sizes)
    _ = parser.add_argument("--repeats", type=int, default=arguments.repeats)
    arguments = parser.parse_args(namespace=arguments)
    rows: list[dict[str, object]] = []
    for count in arguments.sizes:
        started = time.perf_counter()
        workload = generate(count, 903817)
        generation = time.perf_counter() - started
        actual, searches = identity_benchmark.partitioned_construct(workload)
        previous = identity_benchmark.previous_construct(workload.previous_operations)
        if len(actual.dependencies) != len(previous):
            raise AssertionError("Graph operation counts differ")
        for operation in range(len(previous)):
            if set(actual.dependencies.dependencies(operation)) != set(
                previous.dependencies(operation)
            ):
                raise AssertionError("Ordinary graph dependencies differ")
        if len(searches.searches) != count or not searches.has_completion(0):
            raise AssertionError("Independent valid groups did not remain executable")
        sizes = [len(operations) for operations in searches.operations]
        del actual, previous, searches
        rows.append(
            {
                "groups": count,
                "operations": len(workload.operations),
                "seed": 903817,
                "generation_seconds": generation,
                "search_size_min": min(sizes),
                "search_size_max": max(sizes),
                "with_partitioned_searches": relationship_benchmark.measure(
                    functools.partial(
                        identity_benchmark.partitioned_construct, workload
                    ),
                    arguments.repeats,
                ),
                "with_cycle_clauses": relationship_benchmark.measure(
                    functools.partial(identity_benchmark.complete_construct, workload),
                    arguments.repeats,
                ),
                "prior_ordinary_backend": relationship_benchmark.measure(
                    functools.partial(
                        identity_benchmark.previous_construct,
                        workload.previous_operations,
                    ),
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
