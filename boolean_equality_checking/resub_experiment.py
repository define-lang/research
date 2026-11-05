"""Time exact matching over earlier values, searched like Boolean resubstitution.

On the matching workloads of `matching_experiment.py` (regenerated
deterministically), runs `beq match --how resub`, DLP 58's cuts, and the
first exact search (`--how exact --anchor any`, whose arguments are also
earlier values), and checks that the two exact searches find the same
matches, apart from the opposite results that only `resub` looks for. Run
with `uv run --frozen --python 3.14 python resub_experiment.py`; results go
to `results/resub.jsonl`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

import click
from experiments import (
    BEQ,
    HERE,
    MEMORY_GB,
    RESULTS,
    WORK,
    OutOfMemoryError,
    run_limited,
)

if TYPE_CHECKING:
    import pathlib

SIZES = [(8, 64), (12, 64), (12, 200), (16, 256), (20, 256)]
CONFIGS = {
    "cuts": ["--how", "cuts", "--repeat", "5"],
    "resub": ["--how", "resub", "--repeat", "3"],
    "exact_any": ["--how", "exact", "--anchor", "any"],
}


def matches(dump: pathlib.Path) -> set[tuple[str, ...]]:
    """Return the matches in a dump, apart from opposite results."""
    out = set()
    for line in dump.read_text().splitlines():
        value, op, *args = line.split()
        if not op.startswith("not:"):
            out.add((value, op, *sorted(args, key=int)))
    return out


@click.command()
def main() -> None:
    """Generate the workloads and run every configuration on each."""
    out = WORK / "matching"
    for inputs, statements in SIZES:
        run_limited(
            [
                sys.executable,
                str(HERE / "gen" / "generate.py"),
                "matching",
                "--out",
                str(out),
                "--inputs",
                str(inputs),
                "--statements",
                str(statements),
                "--count",
                "5",
            ],
            30,
            MEMORY_GB,
            cwd=HERE / "gen",
        )
    with (RESULTS / "resub.jsonl").open("a", encoding="utf-8") as results:
        for inputs, statements in SIZES:
            for k in range(5):
                aag = out / f"match_i{inputs}_s{statements}_{k}.aag"
                row: dict[str, object] = {"file": aag.stem}
                for config, args in CONFIGS.items():
                    dump = aag.with_suffix(f".{config}.dump")
                    command = [str(BEQ), "match", str(aag), *args, "--dump", str(dump)]
                    try:
                        record = json.loads(run_limited(command, 30, MEMORY_GB).stdout)
                    except subprocess.TimeoutExpired:
                        row[config] = {"status": "timeout"}
                        continue
                    except OutOfMemoryError:
                        row[config] = {"status": "out of memory"}
                        continue
                    lines = dump.read_text().splitlines()
                    row[config] = {
                        "status": record["status"],
                        "time_s": record["time_s"],
                        "matches": len(lines),
                        "opposite": sum(" not:" in line for line in lines),
                        "values": len({line.split()[0] for line in lines}),
                        "planted_by_kind": record["planted_by_kind"],
                        "stats": record["stats"],
                    }
                exact = aag.with_suffix(".exact_any.dump")
                resub = aag.with_suffix(".resub.dump")
                if exact.exists() and resub.exists():
                    a, b = matches(exact), matches(resub)
                    row["only_exact_any"] = len(a - b)
                    row["only_resub"] = len(b - a)
                results.write(json.dumps(row) + "\n")
                results.flush()
                print(json.dumps(row)[:300], flush=True)


if __name__ == "__main__":
    main()
