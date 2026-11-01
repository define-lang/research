"""Measure checking in the steady state: value operations that compile.

Part 1, flat value operations through the combined algorithm: operations
that compile, ones that compile and have near misses (values that differ from
an earlier one on a 2^-c fraction of input combinations), and failing ones
with planted redundancies for comparison.

Part 2, libraries with references (`beq hier --how sat_hybrid`): checking
that stops at the
first redundant value against checking everything; checking with patterns
stored by an earlier check, unchanged and after light edits.

Part 3, incremental rechecking: random edits to deep libraries, counting the
operations each edit makes the compiler check again (`beq hier_edit`).

Run with `uv run --frozen --python 3.14 python steady_state_experiment.py`;
results go to `results/steady_state.jsonl`.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from typing import TYPE_CHECKING

import click
from experiments import BEQ, HERE, MEMORY_GB, RESULTS, WORK, run_limited

if TYPE_CHECKING:
    import pathlib

GENERATE = [sys.executable, str(HERE / "gen" / "generate.py")]


def generate(args: list[str]) -> None:
    """Run the workload generator."""
    subprocess.run([*GENERATE, *args], check=True, cwd=HERE / "gen")  # noqa: S603


def beq(binary: str, args: list[str], timeout: float = 1800) -> list[dict]:
    """Run beq and return its JSON lines."""
    done = run_limited([binary, *args], timeout, MEMORY_GB)
    return [json.loads(line) for line in done.stdout.splitlines()]


def edit_library(
    source: pathlib.Path, target: pathlib.Path, fraction: float, seed: int
) -> int:
    """Negate one literal of one `and` in a fraction of the operations."""
    rng = random.Random(seed)  # noqa: S311 - Reproducible edits.
    blocks: list[list[str]] = []
    for line in source.read_text().splitlines():
        if line.startswith("op "):
            blocks.append([])
        blocks[-1].append(line)
    edited = 0
    for block in blocks:
        ands = [k for k, line in enumerate(block) if line.startswith("and ")]
        if ands and rng.random() < fraction:
            k = rng.choice(ands)
            _, a, b = block[k].split()
            block[k] = f"and {a} {int(b) ^ 1}"
            edited += 1
    target.write_text("".join(line + "\n" for block in blocks for line in block))
    return edited


@click.command()
@click.option("--binary", default=str(BEQ), help="The beq binary to run.")
def main(binary: str) -> None:
    """Run all three parts."""
    with (RESULTS / "steady_state.jsonl").open("a", encoding="utf-8") as results:

        def record(part: str, rows: list[dict], **extra: object) -> None:
            for row in rows:
                row.update(part=part, **extra)
                results.write(json.dumps(row) + "\n")
            results.flush()

        # Part 1.
        out = WORK / "steady"
        for inputs in (12, 16, 20):
            for statements in (64, 256):
                variants = {
                    "compiles": ["--plant-rate", "0"],
                    "fails": ["--plant-rate", "0.08"],
                    **{
                        f"near_c{c}": [
                            "--plant-rate",
                            "0",
                            "--near-miss-rate",
                            "0.05",
                            "--cube-size",
                            str(c),
                        ]
                        for c in (10, 14, 18)
                        if c <= inputs
                    },
                }
                for variant, options in variants.items():
                    prefix = f"{variant}"
                    generate(
                        [
                            "value-operation",
                            "--out",
                            str(out),
                            "--inputs",
                            str(inputs),
                            "--statements",
                            str(statements),
                            "--count",
                            "5",
                            "--prefix",
                            prefix,
                            *options,
                        ]
                    )
                    for k in range(5):
                        aag = out / f"{prefix}_i{inputs}_s{statements}_w8_{k}.aag"
                        for method in ("auto", "tt"):
                            rows = beq(
                                binary,
                                [method, str(aag), "--tt_max", "20", "--repeat", "3"],
                            )
                            record(
                                "flat",
                                rows,
                                variant=variant,
                                inputs_n=inputs,
                                statements_n=statements,
                            )
                print("part 1", inputs, statements, flush=True)

        # Part 2.
        libs = WORK / "steady_libs"
        libraries = {
            "compiles_v10": [
                "--views",
                "10",
                "--near-misses",
                "3",
                "--cube-size",
                "9",
                "--twin-rate",
                "0",
            ],
            "fails_v10": [
                "--views",
                "10",
                "--near-misses",
                "3",
                "--cube-size",
                "9",
                "--twin-rate",
                "0.5",
            ],
            "compiles_v14": [
                "--views",
                "14",
                "--near-misses",
                "3",
                "--cube-size",
                "12",
                "--twin-rate",
                "0",
            ],
            "fails_v14": [
                "--views",
                "14",
                "--near-misses",
                "3",
                "--cube-size",
                "12",
                "--twin-rate",
                "0.5",
            ],
        }
        for name, options in libraries.items():
            generate(
                [
                    "hierarchy",
                    "--out",
                    str(libs),
                    "--levels",
                    "8",
                    *options,
                    "--name",
                    name,
                ]
            )
            lib = libs / f"{name}.lib"
            patterns = libs / f"{name}.patterns"
            record(
                "refs",
                beq(binary, ["hier", str(lib), "--how", "tt"]),
                library=name,
                run="tt",
            )
            record(
                "refs",
                beq(
                    binary,
                    [
                        "hier",
                        str(lib),
                        "--how",
                        "sat_hybrid",
                        "--patterns_out",
                        str(patterns),
                    ],
                ),
                library=name,
                run="first",
            )
            record(
                "refs",
                beq(
                    binary,
                    ["hier", str(lib), "--how", "sat_hybrid", "--stop_first", "1"],
                ),
                library=name,
                run="stop_first",
            )
            record(
                "refs",
                beq(
                    binary,
                    [
                        "hier",
                        str(lib),
                        "--how",
                        "sat_hybrid",
                        "--patterns_in",
                        str(patterns),
                    ],
                ),
                library=name,
                run="recheck_unchanged",
            )
            edited_lib = libs / f"{name}_edited.lib"
            edited = edit_library(lib, edited_lib, 0.2, 7)
            record(
                "refs",
                beq(
                    binary,
                    [
                        "hier",
                        str(edited_lib),
                        "--how",
                        "sat_hybrid",
                        "--patterns_in",
                        str(patterns),
                    ],
                ),
                library=name,
                run="recheck_edited",
                edited_ops=edited,
            )
            record(
                "refs",
                beq(binary, ["hier", str(edited_lib), "--how", "sat_hybrid"]),
                library=name,
                run="edited_without_patterns",
                edited_ops=edited,
            )
            print("part 2", name, flush=True)

        # Part 3.
        for name, options in {
            "deep_e3_l10": ["--levels", "10", "--executions", "3"],
            "deep_e3_l14": ["--levels", "14", "--executions", "3"],
            "deep_e4_l12": ["--levels", "12", "--executions", "4"],
        }.items():
            generate(
                [
                    "hierarchy",
                    "--out",
                    str(libs),
                    "--views",
                    "10",
                    *options,
                    "--name",
                    f"edit_{name}",
                ]
            )
            rows = beq(
                binary, ["hier_edit", str(libs / f"edit_{name}.lib"), "--edits", "400"]
            )
            record("edits", rows, library=name)
            print("part 3", name, flush=True)


if __name__ == "__main__":
    main()
