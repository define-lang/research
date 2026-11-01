"""Generate the workloads for each experiment, run every method, record results.

Run from this directory with `uv run --frozen --python 3.14 python
experiments.py EXPERIMENT`, after building `src/beq` with `src/build.sh`.
Instances go to `work/` (not kept; regenerate them with the same command) and
results are appended to `results/EXPERIMENT.jsonl`, one JSON object per run.
"""

from __future__ import annotations

import concurrent.futures
import json
import pathlib
import subprocess
import sys

import click

HERE = pathlib.Path(__file__).resolve().parent
BEQ = HERE / "src" / "beq"
WORK = HERE / "work"
RESULTS = HERE / "results"
# Memory limit for each measured process. Up to eight run at a time on a
# machine with 64 GB.
MEMORY_GB = 4
# No check may take longer than this on one graph, whatever its driver asks.
MAX_SECONDS = 30
GENERATE = [sys.executable, str(HERE / "gen" / "generate.py")]

# Method configurations: a name and the arguments to `beq`.
METHODS: dict[str, list[str]] = {
    "strash": ["strash"],
    "norm_single": ["norm_single"],
    "norm_all": ["norm_all", "--literal_budget", "200000000"],
    "cuts4": ["cuts4", "--cut_budget", "100000000"],
    "tt": ["tt", "--tt_max", "24"],
    "bdd_first_use": ["bdd", "--order", "first_use", "--bdd_nodes", "30000000"],
    "bdd_natural": ["bdd", "--order", "natural", "--bdd_nodes", "30000000"],
    "sweep": ["sweep"],
    "sweep_unscoped": ["sweep", "--scope", "0"],
    # Starts a new solver past 300 variables, to check that recycling is exact.
    "sweep_recycling": ["sweep", "--recycle_vars", "300"],
    "sweep_exhaustive": ["sweep", "--exhaustive", "12"],
    "sweep_bdd_rescue": ["sweep", "--bdd_rescue", "1000"],
    # SAT sweeping with both rescues, before the dispatch was added.
    "portfolio": ["sweep", "--exhaustive", "12", "--bdd_rescue", "1000"],
    # The combined algorithm, with its dispatch (see README.md).
    "auto": ["auto"],
    # The combined algorithm with Kissat as the last step for a pair.
    "auto_kissat": ["auto", "--external", "kissat", "--temp_dir", str(WORK / "tmp")],
    # The combined algorithm forced through its truth-table switch, to check it.
    "auto_forced_switch": [
        "auto",
        "--small_inputs",
        "0",
        "--bdd_rescue",
        "1",
        "--bdd_rescue_nodes",
        "4",
    ],
}


class OutOfMemoryError(Exception):
    """A measured process crashed at its memory limit."""


def run_limited(
    command: list[str],
    timeout: float,
    memory_gb: int,
    *,
    long_study: bool = False,
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    """Run a measured process with a wall-clock limit and a memory limit.

    `timeout` and `prlimit` wrap the process itself, so it can't outlive the
    limit even if this driver is killed. A process that reaches the limit
    raises `subprocess.TimeoutExpired`; one that crashes, which is how
    reaching the memory limit shows up, raises `OutOfMemoryError`. Only the
    final study of a whole large program may take longer than
    `MAX_SECONDS`.
    """
    if not long_study:
        timeout = min(timeout, MAX_SECONDS)
    wrapped = [
        "timeout",
        "-s",
        "KILL",
        str(timeout),
        "prlimit",
        f"--as={memory_gb << 30}",
        *command,
    ]
    done = subprocess.run(  # noqa: S603, PLW1510 - The status is checked below.
        wrapped,
        capture_output=True,
        text=True,
        timeout=timeout + 60,
        **kwargs,  # type: ignore[arg-type]
    )
    # `timeout` sends KILL to its whole process group, itself included.
    if done.returncode in (137, -9):
        raise subprocess.TimeoutExpired(command, timeout)
    if done.returncode in (134, 139, -6, -11):
        raise OutOfMemoryError(" ".join(command))
    if done.returncode != 0:
        raise subprocess.CalledProcessError(
            done.returncode, command, done.stdout, done.stderr
        )
    return done


def generate(args: list[str]) -> None:
    """Run the workload generator."""
    subprocess.run([*GENERATE, *args], check=True, cwd=HERE / "gen")  # noqa: S603 - This directory's own generator.


def run_one(
    aag: pathlib.Path, method: str, extra: list[str], timeout: float
) -> dict[str, object]:
    """Run one method on one instance and return its JSON record."""
    planted = aag.with_suffix(".planted")
    cmd = [
        str(BEQ),
        METHODS[method][0],
        str(aag),
        *METHODS[method][1:],
        "--planted",
        str(planted),
        *extra,
    ]
    try:
        # This directory's own binary, on generated files.
        out = run_limited(cmd, timeout, MEMORY_GB).stdout
        record = json.loads(out)
    except subprocess.TimeoutExpired as error:
        record = {"status": "timeout", "time_s": error.timeout, "file": str(aag)}
    except OutOfMemoryError:
        record = {"status": "out of memory", "file": str(aag)}
    record["config"] = method
    record["instance"] = aag.stem
    if extra:
        record["extra"] = " ".join(extra)
    return record


def run_all(
    name: str,
    instances: list[pathlib.Path],
    methods: list[str],
    timeout: float,
    jobs: int,
    extra: list[str] | None = None,
) -> None:
    """Run every method on every instance and append the results."""
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{name}.jsonl"
    tasks = [(aag, m) for aag in instances for m in methods]
    with (
        concurrent.futures.ThreadPoolExecutor(jobs) as pool,
        path.open("a", encoding="utf-8") as out,
    ):
        futures = [
            pool.submit(run_one, aag, m, extra or [], timeout) for aag, m in tasks
        ]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            out.write(json.dumps(record) + "\n")
            out.flush()
            print(
                record["instance"],
                record["config"],
                record["status"],
                record.get("time_s"),
                flush=True,
            )


@click.group()
def cli() -> None:
    """Run experiments."""


def _only(methods: list[str], only: str) -> list[str]:
    """Return the methods named in `only` (comma-separated), or all of them."""
    return [m for m in methods if m in only.split(",")] if only else methods


@cli.command()
@click.option("--jobs", type=int, default=8)
@click.option(
    "--only", default="", help="Comma-separated methods to run instead of all."
)
def operations(jobs: int, only: str) -> None:
    """Realistic value operations from 4 to 128 inputs and 16 to 1024 statements."""
    out = WORK / "operations"
    for inputs in (4, 8, 12, 16, 20, 24, 32, 48, 64, 96, 128):
        for statements in (16, 64, 256, 1024):
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
                ]
            )
    instances = sorted(out.glob("*.aag"))
    methods = [
        "strash",
        "norm_single",
        "norm_all",
        "cuts4",
        "tt",
        "bdd_first_use",
        "bdd_natural",
        "sweep",
        "sweep_exhaustive",
        "sweep_bdd_rescue",
        "portfolio",
        "auto",
    ]
    run_all(
        "operations",
        instances,
        _only(methods, only),
        timeout=120,
        jobs=jobs,
        extra=["--repeat", "5"],
    )


@cli.command()
@click.option("--jobs", type=int, default=4)
@click.option(
    "--only", default="", help="Comma-separated methods to run instead of all."
)
@click.option("--timeout", type=float, default=120)
def adversarial(jobs: int, only: str, timeout: float) -> None:
    """Parity, multipliers, hidden weighted bit, and tangles."""
    out = WORK / "adversarial"
    for inputs in (8, 12, 16, 20, 24, 28, 32, 40, 48, 64, 96, 128):
        generate(
            ["parity", "--out", str(out), "--inputs", str(inputs), "--copies", "3"]
        )
    for bits in range(3, 13):
        for kind in ("commuted", "kogge"):
            generate(
                ["multiplier", "--out", str(out), "--bits", str(bits), "--kind", kind]
            )
    for inputs in (8, 12, 16, 20, 24, 28, 32, 40):
        generate(["hwb", "--out", str(out), "--inputs", str(inputs)])
    for inputs in (16, 32, 64):
        for statements in (256, 1024):
            generate(
                [
                    "tangle",
                    "--out",
                    str(out),
                    "--inputs",
                    str(inputs),
                    "--statements",
                    str(statements),
                    "--count",
                    "3",
                ]
            )
    for bits in (8, 16, 32, 64):
        generate(
            ["comparators", "--out", str(out), "--bits", str(bits), "--count", "10"]
        )
    instances = sorted(out.glob("*.aag"))
    methods = [
        "strash",
        "norm_single",
        "cuts4",
        "tt",
        "bdd_first_use",
        "bdd_natural",
        "sweep",
        "sweep_exhaustive",
        "sweep_bdd_rescue",
        "portfolio",
        "auto",
    ]
    # Kissat as the last step is run separately, with a longer timeout.
    if "auto_kissat" in only.split(","):
        methods.append("auto_kissat")
    # Runs allowed to take long are timed once.
    repeat = "3" if timeout <= 120 else "1"
    run_all(
        "adversarial",
        instances,
        _only(methods, only),
        timeout=timeout,
        jobs=jobs,
        extra=["--repeat", repeat],
    )


@cli.command()
@click.option("--jobs", type=int, default=1)
@click.option("--max-calls", type=int, default=1_000_000)
@click.option(
    "--only", default="", help="Comma-separated methods to run instead of all."
)
def program(jobs: int, max_calls: int, only: str) -> None:
    """Whole programs with every call inlined, from 1,000 to 1,000,000 calls.

    Programs come in two shapes: one long dataflow where any call can read the
    last 64 values, and regions of 50 calls, like separate actions.
    """
    out = WORK / "program"
    sizes = [c for c in (1000, 4000, 16000, 64000, 256000, 1000000) if c <= max_calls]
    instances = []
    for calls in sizes:
        for region in (0, 50):
            generate(
                [
                    "program",
                    "--out",
                    str(out),
                    "--calls",
                    str(calls),
                    "--region",
                    str(region),
                ]
            )
            suffix = f"_r{region}" if region else ""
            instances.append(out / f"program_t200_c{calls}{suffix}.aag")
    # Exact sweeping of the largest one-dataflow program would take hours, so
    # it stops at 256,000 calls there, and the unscoped solver, which is
    # slower, at 64,000.
    for aag in instances:
        calls = int(aag.stem.split("_c")[1].split("_")[0])
        methods = ["strash", "norm_single"]
        if calls <= 256000 or aag.stem.endswith("_r50"):
            methods += ["sweep", "portfolio", "auto"]
        if calls <= 64000:
            methods.append("sweep_unscoped")
        run_all("program", [aag], _only(methods, only), timeout=3600, jobs=jobs)


@cli.command()
@click.option("--jobs", type=int, default=8)
@click.option(
    "--only", default="", help="Comma-separated methods to run instead of all."
)
def library(jobs: int, only: str) -> None:
    """Each value operation of the programs' library, checked once by itself."""
    out = WORK / "library"
    generate(["library", "--out", str(out)])
    instances = sorted(out.glob("*.aag"))
    methods = ["strash", "cuts4", "tt", "bdd_first_use", "sweep", "portfolio", "auto"]
    run_all(
        "library",
        instances,
        _only(methods, only),
        timeout=60,
        jobs=jobs,
        extra=["--repeat", "5"],
    )


@cli.command()
@click.option("--jobs", type=int, default=8)
@click.option(
    "--seeds-only", is_flag=True, help="Run only the seeds, not the conflict limits."
)
def limits(jobs: int, *, seeds_only: bool) -> None:
    """SAT sweeping with conflict limits and different seeds."""
    instances = sorted((WORK / "operations").glob("*_s256_*.aag")) + sorted(
        (WORK / "adversarial").glob("*.aag")
    )
    for conflicts in () if seeds_only else (1, 10, 100, 1000, 10000):
        run_all(
            "limits",
            instances,
            ["sweep"],
            timeout=120,
            jobs=jobs,
            extra=["--conflicts", str(conflicts)],
        )
    for seed in (1, 2, 3):
        run_all(
            "limits",
            instances,
            ["portfolio"],
            timeout=120,
            jobs=jobs,
            extra=["--seed", str(seed)],
        )


if __name__ == "__main__":
    cli()
