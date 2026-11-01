"""Time native CaDiCaL and Kissat on the miters of the hardest planted pairs.

For each pair, `beq cnf` writes the two cones and asserts that they differ, so
UNSAT (exit code 20) proves the pair equal. The pairs are every planted pair
of the parity and hidden weighted bit instances and the two middle product
bits of each multiplier (the hardest ones). Run after `experiments.py
adversarial` has generated `work/adversarial`, with `uv run --frozen --python
3.14 python native_solvers.py`; results are appended to `results/native.jsonl`.
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import subprocess
import time

import click
from experiments import BEQ, MAX_SECONDS, MEMORY_GB, RESULTS, WORK

SOLVERS = {"cadical": ["cadical", "-q"], "kissat": ["kissat", "-q"]}


def pairs() -> list[tuple[str, int, str]]:
    """Return (instance stem, pair index, kind) for every pair to check."""
    out = []
    for aag in sorted((WORK / "adversarial").glob("*.aag")):
        name = aag.stem
        if not re.match(r"(parity|hwb|mult)_", name):
            continue
        for index, line in enumerate(
            aag.with_suffix(".planted").read_text().splitlines()
        ):
            kind = line.split()[2]
            if name.startswith("mult") and not kind.startswith("product_bit_"):
                continue
            out.append((name, index, kind))
    return out


def run(
    name: str, index: int, kind: str, solver: str, timeout: float
) -> dict[str, object]:
    """Write one pair's CNF and time one solver on it."""
    aag = WORK / "adversarial" / f"{name}.aag"
    cnf = aag.with_suffix(f".pair{index}.cnf")
    if not cnf.exists():
        command = [
            str(BEQ),
            "cnf",
            str(aag),
            "--planted",
            str(aag.with_suffix(".planted")),
            "--pair",
            str(index),
        ]
        subprocess.run([*command, "--out", str(cnf)], check=True)  # noqa: S603
    record: dict[str, object] = {
        "instance": name,
        "pair": index,
        "kind": kind,
        "solver": solver,
    }
    timeout = min(timeout, MAX_SECONDS)
    start = time.perf_counter()
    try:
        done = subprocess.run(  # noqa: S603
            # `timeout` sits under `time`, so the solver itself is killed.
            [
                "/usr/bin/time",
                "-f",
                "MAXRSS %M",
                "timeout",
                "-s",
                "KILL",
                str(timeout),
                "prlimit",
                f"--as={MEMORY_GB << 30}",
                *SOLVERS[solver],
                str(cnf),
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        record.update(status="timeout", time_s=timeout)
        return record
    record["time_s"] = time.perf_counter() - start
    if done.returncode == 137:
        record.update(status="timeout", time_s=timeout)
        return record
    record["status"] = {10: "different", 20: "equal"}.get(
        done.returncode, f"exit {done.returncode}"
    )
    record["peak_rss_kb"] = int(re.findall(r"MAXRSS (\d+)", done.stderr)[-1])
    return record


@click.command()
@click.option("--jobs", type=int, default=4)
@click.option("--timeout", type=float, default=600)
def main(jobs: int, timeout: float) -> None:
    """Run both solvers on every chosen pair."""
    path = RESULTS / "native.jsonl"
    done_before = set()
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            done_before.add((r["instance"], r["pair"], r["solver"]))
    tasks = [
        (*p, s) for p in pairs() for s in SOLVERS if (p[0], p[1], s) not in done_before
    ]
    with (
        concurrent.futures.ThreadPoolExecutor(jobs) as pool,
        path.open("a", encoding="utf-8") as out,
    ):
        futures = [pool.submit(run, *t, timeout) for t in tasks]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            out.write(json.dumps(record) + "\n")
            out.flush()
            print(
                record["instance"],
                record["pair"],
                record["solver"],
                record["status"],
                record["time_s"],
                flush=True,
            )


if __name__ == "__main__":
    main()
