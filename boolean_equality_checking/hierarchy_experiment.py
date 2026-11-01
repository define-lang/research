"""Compare referring to executed value operations with copying them.

Generates libraries where boolean value operations execute each other
several levels deep (`gen/hierarchy.py`) and checks every operation with
`beq hier`: copying every execution into one flat graph, truth tables with
lookups, OBDDs with composition, and SAT with abstraction refinement
(expanding an execution that disagrees, adding one clause per assignment,
and a hybrid that adds clauses for an execution's first four disagreements
and expands it after that). Run with `uv run --frozen --python 3.14 python
hierarchy_experiment.py`; results go to `results/hierarchy.jsonl`.
"""

from __future__ import annotations

import json
import subprocess
import sys

import click
from experiments import BEQ, HERE, RESULTS, WORK, OutOfMemoryError, run_limited

METHODS = ["tt", "bdd", "sat", "sat_clauses", "sat_hybrid", "copy"]


@click.command()
@click.option("--timeout", type=float, default=600)
@click.option("--binary", default=str(BEQ), help="The beq binary to run.")
def main(timeout: float, binary: str) -> None:
    """Generate the libraries and check every operation with every method."""
    out = WORK / "hierarchy"
    gen = [
        sys.executable,
        str(HERE / "gen" / "generate.py"),
        "hierarchy",
        "--out",
        str(out),
    ]
    libraries: list[tuple[str, dict[str, object]]] = []
    for executions in (3, 4):
        for levels in (2, 4, 6, 8, 10, 12, 14):
            name = f"deep_e{executions}_l{levels}"
            args = [
                "--levels",
                str(levels),
                "--views",
                "10",
                "--executions",
                str(executions),
                "--name",
                name,
            ]
            libraries.append(
                (
                    name,
                    {
                        "levels": levels,
                        "views": 10,
                        "executions": executions,
                        "args": args,
                    },
                )
            )
    for views in (12, 16, 20):
        name = f"wide_v{views}"
        args = ["--levels", "8", "--views", str(views), "--unchecked", "--name", name]
        libraries.append(
            (name, {"levels": 8, "views": views, "executions": 3, "args": args})
        )
    for _name, params in libraries:
        subprocess.run([*gen, *params["args"]], check=True, cwd=HERE / "gen")  # noqa: S603
    with (RESULTS / "hierarchy.jsonl").open("a", encoding="utf-8") as results:
        for name, params in libraries:
            for method in METHODS:
                command = [binary, "hier", str(out / f"{name}.lib"), "--how", method]
                try:
                    lines = run_limited(command, timeout, 16).stdout.splitlines()
                    status = "ok"
                except subprocess.TimeoutExpired:
                    lines = []
                    status = "timeout"
                except OutOfMemoryError:
                    lines = []
                    status = "out of memory"
                for line in lines:
                    record = json.loads(line)
                    record.update(
                        library=name,
                        levels=params["levels"],
                        lib_views=params["views"],
                        lib_executions=params["executions"],
                        run_status=status,
                    )
                    results.write(json.dumps(record) + "\n")
                if status != "ok":
                    results.write(
                        json.dumps(
                            {"library": name, "how": method, "run_status": status}
                        )
                        + "\n"
                    )
                results.flush()
                print(name, method, status, len(lines), flush=True)


if __name__ == "__main__":
    main()
