"""Check every method against the others on many small random instances.

The exact methods (truth tables, both OBDD orders, and every SAT sweeping
configuration) must give identical classes, and every merge an inexact method
makes must hold in those classes. Run with `uv run --frozen --python 3.14
python check_methods.py`; it prints one line per disagreement and a summary.
"""

from __future__ import annotations

import random
import subprocess
from typing import TYPE_CHECKING

import click
from experiments import BEQ, GENERATE, HERE, MEMORY_GB, METHODS, run_limited

if TYPE_CHECKING:
    import pathlib

EXACT = [
    "tt",
    "bdd_first_use",
    "bdd_natural",
    "sweep",
    "sweep_unscoped",
    "sweep_recycling",
    "sweep_exhaustive",
    "sweep_bdd_rescue",
    "portfolio",
    "auto",
    "auto_forced_switch",
]
SOUND = ["strash", "norm_single", "norm_all", "cuts4"]


def classes(aag: pathlib.Path, method: str, extra: list[str]) -> list[int]:
    """Return the representative literal of every node under one method."""
    dump = aag.with_suffix(f".{method}.dump")
    command = [
        str(BEQ),
        METHODS[method][0],
        str(aag),
        *METHODS[method][1:],
        "--dump",
        str(dump),
        *extra,
    ]
    run_limited(command, 600, MEMORY_GB)
    return [int(x) for x in dump.read_text().split()]


@click.command()
@click.option("--count", type=int, default=200)
def main(count: int) -> None:
    """Generate count instances of mixed families and compare all methods."""
    out = HERE / "work" / "check"
    rng = random.Random(11)  # noqa: S311 - Reproducible workloads.
    specs = []
    for k in range(count):
        family = rng.choice(["op", "op", "tangle", "parity", "mult", "hwb"])
        if family == "op":
            specs.append(
                [
                    "value-operation",
                    "--inputs",
                    str(rng.randint(3, 18)),
                    "--statements",
                    str(rng.randint(5, 300)),
                    "--seed",
                    str(k),
                    "--plant-rate",
                    str(rng.choice([0.05, 0.2])),
                ]
            )
        elif family == "tangle":
            specs.append(
                [
                    "tangle",
                    "--inputs",
                    str(rng.randint(3, 18)),
                    "--statements",
                    str(rng.randint(5, 300)),
                    "--seed",
                    str(k),
                ]
            )
        elif family == "parity":
            specs.append(
                [
                    "parity",
                    "--inputs",
                    str(rng.randint(2, 18)),
                    "--copies",
                    "3",
                    "--seed",
                    str(k),
                ]
            )
        elif family == "mult":
            specs.append(
                [
                    "multiplier",
                    "--bits",
                    str(rng.randint(2, 6)),
                    "--kind",
                    rng.choice(["commuted", "kogge"]),
                ]
            )
        else:
            specs.append(["hwb", "--inputs", str(rng.randint(2, 16))])
    disagreements = 0
    checked = 0
    for k, spec in enumerate(specs):
        target = out / str(k)
        command = [*GENERATE, *spec[:1], "--out", str(target), *spec[1:]]
        subprocess.run(command, check=True, cwd=HERE / "gen")  # noqa: S603 - Runs this directory's own generator.
        for aag in sorted(target.glob("*.aag")):
            checked += 1
            # A small sweep budget forces counterexample handling and flushes.
            extra = ["--sim_rounds", "1"]
            exact = {
                m: classes(aag, m, extra if m.startswith("sweep") else [])
                for m in EXACT
            }
            reference = exact["tt"]
            for m, c in exact.items():
                if c != reference:
                    disagreements += 1
                    print(f"DISAGREE {aag} {m}")
            for m in SOUND:
                c = classes(aag, m, [])
                for v, rep in enumerate(c):
                    # v equals rep, so their exact representatives must match.
                    if reference[v] != reference[rep >> 1] ^ (rep & 1):
                        disagreements += 1
                        print(f"UNSOUND {aag} {m} node {v}")
                        break
    print(f"instances={checked} disagreements={disagreements}")


if __name__ == "__main__":
    main()
