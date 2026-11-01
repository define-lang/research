"""Time the complete modular algorithm on whole large programs.

A program here is a library of boolean value operations that execute each
other (`gen/hierarchy.py`), and checking it means checking every value
operation once, in dependency order, the way the compiler would: truth
tables with lookups for operations of at most 12 views, otherwise SAT with
executions as references and the hybrid refinement (`beq hier --how auto`).
Each program is checked from nothing (storing patterns), checked again
unchanged with the stored patterns, and edited at random 200 times, with
only the operations each edit affects checked again (`beq hier_edit`).

This is the one study allowed to take longer than 30 seconds on one graph.
Run with `uv run --frozen --python 3.14 python final_program_experiment.py`;
results go to `results/final_program.jsonl`.
"""

from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
import time

import click
from experiments import BEQ, HERE, RESULTS, WORK, OutOfMemoryError, run_limited

# Name, generator options.
PROGRAMS = [
    (
        "ops_10k_v10",
        ["--levels", "20", "--per-level", "500", "--views", "10", "--twin-rate", "0"],
    ),
    (
        "ops_100k_v10",
        ["--levels", "20", "--per-level", "5000", "--views", "10", "--twin-rate", "0"],
    ),
    (
        "ops_2k_v16",
        [
            "--levels",
            "10",
            "--per-level",
            "200",
            "--views",
            "16",
            "--unchecked",
            "--near-misses",
            "3",
            "--cube-size",
            "12",
        ],
    ),
]
TIMEOUT = 1800
MEMORY_GB = 16


def timed(command: list[str]) -> tuple[float, int, list[dict]]:
    """Run beq under the limits; return wall time, peak memory in KB, and rows."""
    start = time.perf_counter()
    done = run_limited(
        ["/usr/bin/time", "-f", "MAXRSS %M", *command],
        TIMEOUT,
        MEMORY_GB,
        long_study=True,
    )
    elapsed = time.perf_counter() - start
    rss = int(re.findall(r"MAXRSS (\d+)", done.stderr)[-1])
    return elapsed, rss, [json.loads(line) for line in done.stdout.splitlines()]


def summarize_check(rows: list[dict]) -> dict[str, object]:
    """Totals over the per-operation rows of `beq hier`."""
    times = [r["time_s"] for r in rows]
    return {
        "operations": len(rows),
        "not_ok": sum(r["status"] != "ok" for r in rows),
        "check_s": sum(times),
        "slowest_operation_s": max(times),
        "median_operation_s": statistics.median(times),
        "operations_with_redundant_value": sum(r["redundant"] > 0 for r in rows),
        "sat_calls": sum(r["stats"].get("sat_calls", 0) for r in rows),
        "patterns_added": sum(r["stats"].get("patterns_added", 0) for r in rows),
        "values": sum(r["values"] for r in rows),
    }


@click.command()
@click.option("--only", default="", help="Run only this program.")
def main(only: str) -> None:
    """Generate each program and time every way of checking it."""
    out = WORK / "final_program"
    with (RESULTS / "final_program.jsonl").open("a", encoding="utf-8") as results:

        def record(row: dict[str, object]) -> None:
            results.write(json.dumps(row) + "\n")
            results.flush()
            print(json.dumps(row), flush=True)

        for name, options in PROGRAMS:
            if only and name != only:
                continue
            lib = out / f"{name}.lib"
            patterns = out / f"{name}.patterns"
            start = time.perf_counter()
            run_limited(
                [
                    sys.executable,
                    str(HERE / "gen" / "generate.py"),
                    "hierarchy",
                    "--out",
                    str(out),
                    *options,
                    "--name",
                    name,
                ],
                TIMEOUT,
                MEMORY_GB,
                long_study=True,
                cwd=HERE / "gen",
            )
            record(
                {
                    "program": name,
                    "run": "generate",
                    "wall_s": time.perf_counter() - start,
                    "bytes": lib.stat().st_size,
                }
            )
            runs = {
                "first": ["--patterns_out", str(patterns)],
                "recheck_unchanged": ["--patterns_in", str(patterns)],
            }
            for run, extra in runs.items():
                command = [str(BEQ), "hier", str(lib), "--how", "auto", *extra]
                try:
                    wall, rss, rows = timed(command)
                except subprocess.TimeoutExpired:
                    record({"program": name, "run": run, "status": "timeout"})
                    continue
                except OutOfMemoryError:
                    record({"program": name, "run": run, "status": "out of memory"})
                    continue
                record(
                    {
                        "program": name,
                        "run": run,
                        "status": "ok",
                        "wall_s": wall,
                        "peak_rss_kb": rss,
                        **summarize_check(rows),
                    }
                )
            try:
                wall, rss, rows = timed(
                    [str(BEQ), "hier_edit", str(lib), "--edits", "200"]
                )
            except subprocess.TimeoutExpired:
                record({"program": name, "run": "edits", "status": "timeout"})
                continue
            except OutOfMemoryError:
                record({"program": name, "run": "edits", "status": "out of memory"})
                continue
            checked = [r["checked"] for r in rows]
            times = [r["time_s"] for r in rows]
            record(
                {
                    "program": name,
                    "run": "edits",
                    "status": "ok",
                    "wall_s": wall,
                    "peak_rss_kb": rss,
                    "edits": len(rows),
                    "rechecked_median": statistics.median(checked),
                    "rechecked_max": max(checked),
                    "edit_time_median_s": statistics.median(times),
                    "edit_time_max_s": max(times),
                }
            )


if __name__ == "__main__":
    main()
