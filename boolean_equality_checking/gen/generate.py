"""Write workload instances as AIGER files with their planted pairs.

Run from this directory, for example
`uv run --frozen python generate.py value-operation --out ../work/ops --inputs 16 --statements 200 --count 5`.
"""

from __future__ import annotations

import pathlib
import random

import click
import hierarchy
import matching
import workloads


@click.group()
def cli() -> None:
    """Generate workloads."""


def _out(out: str, name: str) -> str:
    path = pathlib.Path(out)
    path.mkdir(parents=True, exist_ok=True)
    return str(path / f"{name}.aag")


@cli.command("value-operation")
@click.option("--out", required=True)
@click.option("--inputs", type=int, required=True)
@click.option("--statements", type=int, required=True)
@click.option("--count", type=int, default=1)
@click.option("--seed", type=int, default=1)
@click.option("--plant-rate", type=float, default=0.08)
@click.option("--window", type=int, default=8)
@click.option("--input-rate", type=float, default=0.35)
@click.option("--prefix", default="op")
@click.option("--near-miss-rate", type=float, default=0.0)
@click.option("--cube-size", type=int, default=12)
def value_operation(
    out: str,
    inputs: int,
    statements: int,
    count: int,
    seed: int,
    plant_rate: float,
    window: int,
    input_rate: float,
    prefix: str,
    near_miss_rate: float,
    cube_size: int,
) -> None:
    """Write value operations like realistic code."""
    for k in range(count):
        rng = random.Random(f"{seed}-{inputs}-{statements}-{window}-{k}")  # noqa: S311
        b = workloads.value_operation(
            rng,
            inputs,
            statements,
            plant_rate,
            window,
            input_rate,
            near_miss_rate=near_miss_rate,
            cube_size=cube_size,
        )
        b.write(_out(out, f"{prefix}_i{inputs}_s{statements}_w{window}_{k}"))


@cli.command("comparators")
@click.option("--out", required=True)
@click.option("--bits", type=int, required=True)
@click.option("--count", type=int, default=1)
@click.option("--seed", type=int, default=1)
def comparators(out: str, bits: int, count: int, seed: int) -> None:
    """Write comparisons and sums, each written two ways."""
    b = workloads.comparators(random.Random(f"{seed}-{bits}-{count}"), bits, count)  # noqa: S311
    b.write(_out(out, f"cmp_b{bits}_c{count}"))


@cli.command("multiplier")
@click.option("--out", required=True)
@click.option("--bits", type=int, required=True)
@click.option("--kind", type=click.Choice(["commuted", "kogge"]), required=True)
def multiplier(out: str, bits: int, kind: str) -> None:
    """Write two multipliers whose products are equal."""
    workloads.multipliers(bits, kind).write(_out(out, f"mult_{kind}_b{bits}"))


@cli.command("parity")
@click.option("--out", required=True)
@click.option("--inputs", type=int, required=True)
@click.option("--copies", type=int, default=2)
@click.option("--seed", type=int, default=1)
def parity(out: str, inputs: int, copies: int, seed: int) -> None:
    """Write parity of the inputs computed in different orders."""
    workloads.parity(random.Random(f"{seed}-{inputs}"), inputs, copies).write(  # noqa: S311
        _out(out, f"parity_i{inputs}_c{copies}")
    )


@cli.command("hwb")
@click.option("--out", required=True)
@click.option("--inputs", type=int, required=True)
def hwb(out: str, inputs: int) -> None:
    """Write the hidden weighted bit function two ways."""
    workloads.hidden_weighted_bit(inputs).write(_out(out, f"hwb_i{inputs}"))


@cli.command("multiplexer")
@click.option("--out", required=True)
@click.option("--address-bits", type=int, required=True)
def multiplexer(out: str, address_bits: int) -> None:
    """Write data[address] as a multiplexer tree and as a decoder."""
    workloads.multiplexer(address_bits).write(_out(out, f"mux_a{address_bits}"))


@cli.command("matching")
@click.option("--out", required=True)
@click.option("--inputs", type=int, required=True)
@click.option("--statements", type=int, required=True)
@click.option("--count", type=int, default=1)
@click.option("--seed", type=int, default=1)
def matching_command(
    out: str, inputs: int, statements: int, count: int, seed: int
) -> None:
    """Write value operations with written-out registered operations."""
    for k in range(count):
        rng = random.Random(f"matching-{seed}-{inputs}-{statements}-{k}")  # noqa: S311
        b, rec = matching.matching_operation(rng, inputs, statements)
        matching.write(b, rec, _out(out, f"match_i{inputs}_s{statements}_{k}"))


@cli.command("hierarchy")
@click.option("--out", required=True)
@click.option("--levels", type=int, required=True)
@click.option("--per-level", type=int, default=6)
@click.option("--views", type=int, default=10)
@click.option("--executions", type=int, default=3)
@click.option("--ands", type=int, default=12)
@click.option("--seed", type=int, default=1)
@click.option(
    "--unchecked", is_flag=True, help="Don't track tables or reject redundant values."
)
@click.option("--near-misses", type=int, default=0)
@click.option("--cube-size", type=int, default=8)
@click.option("--twin-rate", type=float, default=0.3)
@click.option(
    "--name",
    default="",
    help="File name, without .lib; derived from the options by default.",
)
def hierarchy_command(
    out: str,
    levels: int,
    per_level: int,
    views: int,
    executions: int,
    ands: int,
    seed: int,
    *,
    unchecked: bool,
    near_misses: int,
    cube_size: int,
    twin_rate: float,
    name: str,
) -> None:
    """Write a library of operations that execute each other."""
    rng = random.Random(f"hierarchy-{seed}-{levels}-{views}-{executions}")  # noqa: S311
    ops = hierarchy.library(
        rng,
        levels,
        per_level,
        views,
        executions,
        ands,
        twin_rate,
        checked=not unchecked,
        near_misses=near_misses,
        cube_size=cube_size,
    )
    path = pathlib.Path(out)
    path.mkdir(parents=True, exist_ok=True)
    hierarchy.write(
        ops, str(path / f"{name or f'lib_l{levels}_v{views}_e{executions}'}.lib")
    )


@cli.command("tangle")
@click.option("--out", required=True)
@click.option("--inputs", type=int, required=True)
@click.option("--statements", type=int, required=True)
@click.option("--count", type=int, default=1)
@click.option("--seed", type=int, default=1)
def tangle(out: str, inputs: int, statements: int, count: int, seed: int) -> None:
    """Write value operations whose statements read values from anywhere."""
    for k in range(count):
        rng = random.Random(f"tangle-{seed}-{inputs}-{statements}-{k}")  # noqa: S311
        workloads.tangle(rng, inputs, statements).write(
            _out(out, f"tangle_i{inputs}_s{statements}_{k}")
        )


@cli.command("program")
@click.option("--out", required=True)
@click.option("--templates", type=int, default=200)
@click.option("--calls", type=int, required=True)
@click.option("--seed", type=int, default=1)
@click.option(
    "--region", type=int, default=0, help="Calls per region; 0 makes one region."
)
def program(out: str, templates: int, calls: int, seed: int, region: int) -> None:
    """Write a whole program with every call inlined."""
    rng = random.Random(f"program-{seed}-{templates}")  # noqa: S311
    b = workloads.program(rng, templates, calls, region_calls=region)
    suffix = f"_r{region}" if region else ""
    b.write(_out(out, f"program_t{templates}_c{calls}{suffix}"))


@cli.command("library")
@click.option("--out", required=True)
@click.option("--templates", type=int, default=200)
@click.option("--seed", type=int, default=1)
def library(out: str, templates: int, seed: int) -> None:
    """Write the value operations that `program` inlines, one file each.

    Each file holds all three ways of writing one operation on the same
    inputs, so the planted pairs are the operation's outputs written two ways.
    """
    rng = random.Random(f"program-{seed}-{templates}")  # noqa: S311
    for k, b in enumerate(workloads.library_files(rng, templates)):
        b.write(_out(out, f"library_{k:03d}"))


if __name__ == "__main__":
    cli()
