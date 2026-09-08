"""Run isolated Vanish measurements and preserve failures alongside successes."""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import random
import subprocess
import sys
from typing import cast


def main():
    """Write a new JSONL record, including the exact experiment sources."""
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--output", required=True)
    _ = parser.add_argument("--steps", type=int, default=1000000)
    _ = parser.add_argument("--width", type=int, default=100)
    _ = parser.add_argument("--families", default="movement,implied,wide,state")
    _ = parser.add_argument(
        "--strategies", default="baseline,collected,compact,bounded"
    )
    _ = parser.add_argument("--seeds", default="17,43,91")
    _ = parser.add_argument("--trace-memory", action="store_true")
    arguments = parser.parse_args()
    destination = pathlib.Path(cast("str", arguments.output))
    count = cast("int", arguments.steps)
    width = cast("int", arguments.width)
    families = cast("str", arguments.families).split(",")
    strategies = cast("str", arguments.strategies).split(",")
    seeds = cast("str", arguments.seeds).split(",")
    tasks: list[list[str]] = []
    for family in families:
        for strategy in strategies:
            for seed in seeds:
                tasks.append(
                    [
                        sys.executable,
                        "-m",
                        "operation_graph_optimization.complete_benchmark",
                        "--family",
                        family,
                        "--strategy",
                        strategy,
                        "--seed",
                        seed,
                        "--steps",
                        str(count),
                        "--width",
                        str(width),
                    ]
                )
    if cast("bool", arguments.trace_memory):
        for task in tasks:
            task.append("--trace-memory")
    random.Random(501).shuffle(tasks)  # noqa: S311 - Reproducible run ordering.
    sources = {}
    for name in [
        "algorithm",
        "combination_algorithm",
        "combination_inputs",
        "graph",
        "integrated/algorithm",
        "integrated/graph",
        "complete/algorithm",
        "complete/graph",
        "complete_inputs",
        "complete_workloads",
        "integrated_variants",
        "integrated_compact",
        "integrated_inline",
        "integrated_resolved",
        "integrated_bounded",
        "integrated_workloads",
        "vanish_algorithm",
        "vanish_workloads",
        "complete_benchmark",
        "order_variants",
        "state_workloads",
        "workloads",
        "complete_matrix",
    ]:
        sources[name] = (pathlib.Path(__file__).parent / (name + ".py")).read_text()
    with destination.open("x") as stream:
        _ = stream.write(
            json.dumps({"platform": platform.platform(), "sources": sources}) + "\n"
        )
        for command in tasks:
            try:
                completed = subprocess.run(  # noqa: S603 - Fixed interpreter and module.
                    command, capture_output=True, text=True, timeout=120, check=False
                )
                record = {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            except subprocess.TimeoutExpired:
                record = {"command": command, "failure": "120 second wall timeout"}
            encoded = json.dumps(record)
            _ = stream.write(encoded + "\n")
            stream.flush()
            print(encoded, flush=True)


if __name__ == "__main__":
    main()
