"""Measure relationship calculations separately from workload generation."""

from __future__ import annotations

import argparse
import functools
import json
import platform
import statistics
import sys
import time
from typing import TYPE_CHECKING

from operation_graph_optimization import precedence_choice, relationship_periods

if TYPE_CHECKING:
    from collections.abc import Callable


class Arguments(argparse.Namespace):
    """Typed command-line benchmark parameters."""

    def __init__(self, sizes: list[int], repeats: int):
        """Set the benchmark's command-line defaults."""
        super().__init__()
        self.sizes: list[int] = sizes
        self.repeats: int = repeats


def measure(calculation: Callable[[], object], repeats: int):
    """Measure repeated calculations without generating their inputs."""
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        result = calculation()
        samples.append(time.perf_counter() - started)
        # The certificate must stay alive until timing ends, so destruction of
        # the preceding repetition cannot inflate the next construction time.
        del result
    return {"samples_seconds": samples, "median_seconds": statistics.median(samples)}


def main():
    """Report relationship construction timings and execution environment."""
    parser = argparse.ArgumentParser(description=__doc__)
    arguments = Arguments([200, 500, 1000], 3)
    _ = parser.add_argument("--sizes", nargs="+", type=int, default=arguments.sizes)
    _ = parser.add_argument("--repeats", type=int, default=arguments.repeats)
    arguments = parser.parse_args(namespace=arguments)
    rows: list[dict[str, object]] = []
    for count in arguments.sizes:
        periods: list[list[relationship_periods.Period]] = []
        for particle in range(count - 1):
            periods.append(
                [relationship_periods.Period(particle + 1, count - 1 - particle, None)]
            )
        periods.append([])
        order = tuple(range(count))
        if relationship_periods.cycle_clauses(periods) != ():
            raise AssertionError("An acyclic chain acquired a cycle condition")
        if relationship_periods.first_violation(periods, order) is not None:
            raise AssertionError("An acyclic chain rejected its valid certificate")
        rows.append(
            {
                "workload": "acyclic_chain",
                "particles": count,
                "collection": measure(
                    functools.partial(relationship_periods.cycle_clauses, periods),
                    arguments.repeats,
                ),
                "certificate": measure(
                    functools.partial(
                        relationship_periods.first_violation, periods, order
                    ),
                    arguments.repeats,
                ),
            }
        )
        # One nontrivial alternative among unrelated operations exposes any
        # accidental whole-problem reachability calculation.
        clauses = ((frozenset({(0, 1)}), frozenset({(1, 0)})),)
        certificate = precedence_choice.factored_completion_order(clauses, set(), count)
        if certificate is None or sorted(certificate) != list(range(count)):
            raise AssertionError("The completion certificate omits operations")
        rows.append(
            {
                "workload": "one_choice_with_unrelated_operations",
                "operations": count,
                "completion": measure(
                    functools.partial(
                        precedence_choice.factored_completion_order,
                        clauses,
                        set(),
                        count,
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
