"""Compare SDDs (pysdd) with beq's OBDDs on a sample of every workload.

For each instance, `beq bdd` (first-use order) gives the OBDD size and time
and dumps its classes; `gen/sdd_compile.py` then compiles the same graph with
a right-linear vtree (an OBDD), a balanced vtree, and a balanced vtree with
dynamic minimization, and checks that the classes match. Run after
`experiments.py` has generated `work/`, with `uv run --frozen --python 3.14
python sdd_compare.py`; results are appended to `results/sdd.jsonl`.
"""

from __future__ import annotations

import json
import subprocess

import click
from experiments import (
    BEQ,
    HERE,
    RESULTS,
    WORK,
    OutOfMemoryError,
    generate,
    run_limited,
)

SAMPLE = [
    *[
        f"operations/op_i{i}_s{s}_w8_{k}"
        for i in (16, 32, 64)
        for s in (64, 256)
        for k in (0, 1)
    ],
    *[f"library/library_{k:03d}" for k in range(0, 200, 20)],
    *[f"adversarial/parity_i{i}_c3" for i in (16, 32, 64, 128)],
    *[f"adversarial/hwb_i{i}" for i in (12, 16, 20, 24)],
    *[f"adversarial/mult_commuted_b{b}" for b in (4, 6, 8)],
    *[f"adversarial/tangle_i32_s256_{k}" for k in (0, 1)],
    "adversarial/cmp_b8_c10",
    *[f"mux/mux_a{a}" for a in (3, 4, 5, 6, 7)],
    # Larger programs fail the same way the smallest one does.
    "program/program_t200_c1000_r50",
]


@click.command()
@click.option("--timeout", type=float, default=300)
def main(timeout: float) -> None:
    """Run the comparison on the sample."""
    for a in (3, 4, 5, 6, 7):
        generate(["multiplexer", "--out", str(WORK / "mux"), "--address-bits", str(a)])
    path = RESULTS / "sdd.jsonl"
    done_before = set()
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            done_before.add((r["instance"], r["engine"]))
    with path.open("a", encoding="utf-8") as out:
        for name in SAMPLE:
            aag = WORK / f"{name}.aag"
            if (aag.stem, "sdd_dynamic") in done_before:
                continue
            dump = aag.with_suffix(".bdd.dump")
            done = run_limited(
                [str(BEQ), "bdd", str(aag), "--dump", str(dump)], timeout, 8
            )
            bdd = json.loads(done.stdout)
            record = {
                "instance": aag.stem,
                "engine": "obdd",
                "status": bdd["status"],
                "time_s": bdd["time_s"],
                "size": bdd["stats"].get("bdd_shared_size"),
                "rss_increase_kb": bdd["peak_rss_kb"] - bdd["rss_after_parse_kb"],
                "inputs": bdd["inputs"],
                "ands": bdd["ands"],
            }
            out.write(json.dumps(record) + "\n")
            for vtree in ("right", "balanced", "dynamic"):
                command = [
                    "uv",
                    "run",
                    "--no-project",
                    "--python",
                    "3.13",
                    "--with",
                    "pysdd",
                    "--with",
                    "click",
                    "python",
                    "sdd_compile.py",
                    str(aag),
                    vtree,
                    "--compare",
                    str(dump),
                ]
                try:
                    done = run_limited(command, timeout, 8, cwd=HERE / "gen")
                    sdd = json.loads(done.stdout.splitlines()[-1])
                    record = {
                        "instance": aag.stem,
                        "engine": f"sdd_{vtree}",
                        "status": "ok",
                        **sdd,
                    }
                except subprocess.TimeoutExpired as error:
                    record = {
                        "instance": aag.stem,
                        "engine": f"sdd_{vtree}",
                        "status": "timeout",
                        "time_s": error.timeout,
                    }
                except OutOfMemoryError:
                    record = {
                        "instance": aag.stem,
                        "engine": f"sdd_{vtree}",
                        "status": "out of memory",
                    }
                except subprocess.CalledProcessError as error:
                    # Past the memory limit, pysdd aborts.
                    record = {
                        "instance": aag.stem,
                        "engine": f"sdd_{vtree}",
                        "status": f"failed: exit {error.returncode}",
                    }
                out.write(json.dumps(record) + "\n")
                out.flush()
                print(
                    aag.stem,
                    record["engine"],
                    record["status"],
                    record.get("live_count"),
                    record.get("time_s"),
                    flush=True,
                )


if __name__ == "__main__":
    main()
