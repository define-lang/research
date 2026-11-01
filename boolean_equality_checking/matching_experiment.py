"""Compare ways of finding written-out registered operations (DLP 57 matches).

Generates value operations with planted matches (`gen/matching.py`), then
runs `beq match` with DLP 57's cuts, cuts with available values as
arguments, and the exact definition with three anchorings; and, for the
arity limit, cuts and the exact search with extra random registered
operations of arity 4, 5, and 6. Run with `uv run --frozen --python 3.14
python matching_experiment.py`; results go to `results/matching.jsonl`.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

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

CONFIGS = {
    "cuts": ["--how", "cuts"],
    "cuts_negated": ["--how", "cuts_negated"],
    "cut_values": ["--how", "cut_values"],
    "exact_cone": ["--how", "exact", "--anchor", "cone"],
    "exact_support": ["--how", "exact", "--anchor", "support"],
    "exact_any": ["--how", "exact", "--anchor", "any"],
}


def run(
    binary: str, aag: str, config: str, args: list[str], timeout: float
) -> dict[str, object]:
    """Run one matcher configuration and add what it flagged."""
    dump = aag.removesuffix(".aag") + f".{config}.matches"
    command = [binary, "match", aag, *args, "--dump", dump]
    try:
        done = run_limited(command, timeout, MEMORY_GB)
    except subprocess.TimeoutExpired as error:
        return {
            "file": aag,
            "config": config,
            "status": "timeout",
            "time_s": error.timeout,
        }
    except OutOfMemoryError:
        return {"file": aag, "config": config, "status": "out of memory"}
    record = json.loads(done.stdout)
    base = pathlib.Path(aag.removesuffix(".aag"))
    planted = {
        line.split()[0]
        for line in base.with_suffix(".planted").read_text().splitlines()
    }
    flagged = {line.split()[0] for line in pathlib.Path(dump).read_text().splitlines()}
    statements = len(base.with_suffix(".statements").read_text().splitlines())
    record.update(
        config=config,
        flagged=len(flagged),
        flagged_unplanted=len(flagged - planted),
        planted_values=len(planted),
        statements=statements,
    )
    return record


@click.command()
@click.option("--timeout", type=float, default=1800)
@click.option("--binary", default=str(BEQ), help="The beq binary to run.")
def main(timeout: float, binary: str) -> None:
    """Generate the workloads and run every configuration."""
    out = WORK / "matching"
    gen = [
        sys.executable,
        str(HERE / "gen" / "generate.py"),
        "matching",
        "--out",
        str(out),
    ]
    sizes = [(8, 64), (12, 64), (12, 200), (16, 256), (20, 256)]
    for inputs, statements in sizes:
        command = [
            *gen,
            "--inputs",
            str(inputs),
            "--statements",
            str(statements),
            "--count",
            "5",
        ]
        run_limited(command, 600, MEMORY_GB, cwd=HERE / "gen")
    files = [str(out / f"match_i{i}_s{s}_{k}.aag") for i, s in sizes for k in range(5)]
    path = RESULTS / "matching.jsonl"
    # Runs already recorded are skipped, so an interrupted run can resume.
    done_before = set()
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            done_before.add((r["file"], r["config"]))
    with path.open("a", encoding="utf-8") as results:
        for aag in files:
            for config, args in CONFIGS.items():
                if (aag, config) in done_before:
                    continue
                record = run(binary, aag, config, args, timeout)
                results.write(json.dumps(record) + "\n")
                results.flush()
                print(aag, config, record["status"], record["time_s"], flush=True)
        # The arity limit: extra registered operations of arity k, cuts of
        # size k, on one operation of each of the three largest sizes. The
        # exact search grows about 90 times per arity, so it stops at 5, and
        # runs at 5 only on the smallest of them, where it already doesn't
        # finish within the time limit.
        larger = [f for f in files if f.endswith(("_s200_0.aag", "_s256_0.aag"))]
        for aag in larger:
            for k in (4, 5, 6):
                extra = ["--extra_arity", str(k), "--extra_count", "4"]
                runs = [("cuts", ["--how", "cuts", "--cut_size", str(k)])]
                if k == 4 or (k == 5 and aag == larger[0]):
                    runs.append(("exact_cone", ["--how", "exact", "--anchor", "cone"]))
                for config, args in runs:
                    if (aag, f"{config}_arity{k}") in done_before:
                        continue
                    record = run(
                        binary, aag, f"{config}_arity{k}", [*args, *extra], timeout
                    )
                    record["arity"] = k
                    results.write(json.dumps(record) + "\n")
                    results.flush()
                    print(
                        aag, config, k, record["status"], record["time_s"], flush=True
                    )


if __name__ == "__main__":
    main()
