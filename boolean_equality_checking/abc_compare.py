"""Run ABC's equivalence commands on the same workloads as `beq`.

Each instance is turned into a miter with one `x xor y` output per planted
pair (`beq miter`). `&fraig`, `&fraig -x`, and `fraig` reduce the whole graph
and write it back; a planted pair counts as found when its output became
constant false. `&cec -m` proves all outputs of the miter at once.

ABC's own timer has 10 ms resolution, so small instances are run many to a
process, and the time of a script that only reads and writes the same files
is subtracted. Run after `experiments.py` has generated `work/` with
`uv run --frozen --python 3.14 python abc_compare.py`; results are appended to
`results/abc.jsonl`.
"""

from __future__ import annotations

import collections
import json
import re
import subprocess
import time
from typing import TYPE_CHECKING

import click
from experiments import BEQ, MAX_SECONDS, RESULTS, WORK

if TYPE_CHECKING:
    import pathlib

COMMANDS = {
    "abc_&fraig": "&r {m}; &fraig; &w {o}",
    "abc_&fraig_x": "&r {m}; &fraig -x; &w {o}",
    "abc_fraig": "read_aiger {m}; strash; fraig; write_aiger {o}",
    "abc_&cec": "&r {s}; &cec -m",
    "baseline": "&r {m}; &w {o}",
}


def miter(aag: pathlib.Path, *, single: bool = False) -> pathlib.Path:
    """Write the miter of an instance's planted pairs, once.

    With single set, the miter has one output, the `or` of every pair's
    difference, because `&cec -m` proves only the first output.
    """
    out = aag.with_suffix(".miter1.aig" if single else ".miter.aig")
    if not out.exists():
        planted = aag.with_suffix(".planted")
        command = [
            str(BEQ),
            "miter",
            str(aag),
            "--planted",
            str(planted),
            "--out",
            str(out),
        ]
        subprocess.run([*command, "--single", str(int(single))], check=True)  # noqa: S603
    return out


def outputs_false(aig: pathlib.Path) -> int:
    """Return how many outputs of a binary AIGER file are constant false."""
    with aig.open("rb") as f:
        header = f.readline().split()
        count = int(header[4])
        return sum(1 for _ in range(count) if int(f.readline()) == 0)


# ABC's address space limit, so a run can't take the machine's memory.
MEMORY_LIMIT_BYTES = 16 << 30


class AbcFailedError(Exception):
    """ABC exited with an error, usually from reaching the memory limit."""

    def __init__(self, status: str) -> None:
        """Record the status to report for the run."""
        super().__init__(status)
        self.status = status


def run_script(commands: list[str], timeout: float) -> tuple[float, int, str]:
    """Run ABC on a script; return wall time, peak memory in KB, and output.

    Scripts that take under ten seconds run three times, keeping the fastest.
    """
    elapsed, rss, stdout = _run_once(commands, timeout)
    if elapsed < 10:
        for _ in range(2):
            again = _run_once(commands, timeout)
            if again[0] < elapsed:
                elapsed, rss, stdout = again
    return elapsed, rss, stdout


def _run_once(commands: list[str], timeout: float) -> tuple[float, int, str]:
    timeout = min(timeout, MAX_SECONDS)
    script = "; ".join(commands)
    start = time.perf_counter()
    # `timeout` sits under `time`, so ABC itself is killed when it runs out.
    command = [
        "/usr/bin/time",
        "-f",
        "MAXRSS %M",
        "timeout",
        "-s",
        "KILL",
        str(timeout),
        "prlimit",
        f"--as={MEMORY_LIMIT_BYTES}",
        "abc",
        "-c",
        script,
    ]
    done = subprocess.run(  # noqa: S603
        command, capture_output=True, text=True, timeout=timeout + 60, check=False
    )
    elapsed = time.perf_counter() - start
    if done.returncode == 137:
        raise subprocess.TimeoutExpired(command, timeout)
    rss = int(re.findall(r"MAXRSS (\d+)", done.stderr)[-1])
    if done.returncode != 0:
        # ABC doesn't check for failed allocations, so reaching the limit
        # shows up as a crash.
        if done.returncode in (134, 139):
            raise AbcFailedError("out of memory")
        raise AbcFailedError(f"failed: exit {done.returncode}")
    return elapsed, rss, done.stdout


def run_group(
    name: str, group: str, files: list[pathlib.Path], timeout: float, only: str = ""
) -> None:
    """Run every ABC command on a group of instances in one process each."""
    miters = [miter(f) for f in files]
    singles = [miter(f, single=True) for f in files]
    planted_total = sum(
        len(f.with_suffix(".planted").read_text().splitlines()) for f in files
    )
    base_time, _, _ = run_script(
        [COMMANDS["baseline"].format(m=m, o="/dev/null") for m in miters], timeout
    )
    path = RESULTS / f"{name}.jsonl"
    done_before = set()
    if path.exists():
        done_before = {
            (r["group"], r["config"])
            for r in map(json.loads, path.read_text().splitlines())
        }
    with path.open("a", encoding="utf-8") as out:
        for command, template in COMMANDS.items():
            if (
                command == "baseline"
                or (only and command != only)
                or (group, command) in done_before
            ):
                continue
            outs = [
                m.with_suffix(f".{command.replace('&', 'g')}.out.aig") for m in miters
            ]
            record: dict[str, object] = {
                "group": group,
                "config": command,
                "instances": len(files),
                "planted_total": planted_total,
            }
            try:
                elapsed, rss, stdout = run_script(
                    [
                        template.format(m=m, o=o, s=one)
                        for m, o, one in zip(miters, outs, singles, strict=True)
                    ],
                    timeout,
                )
            except subprocess.TimeoutExpired as error:
                record.update(status="timeout", time_s=error.timeout)
            except AbcFailedError as error:
                record.update(status=error.status, time_s=None)
            else:
                record.update(
                    status="ok", time_s=max(elapsed - base_time, 0.0), peak_rss_kb=rss
                )
                if command == "abc_&cec":
                    # Each single-output miter proved means all of its pairs.
                    record["proved"] = stdout.count("Networks are equivalent")
                    record["cec_output"] = " | ".join(
                        line.strip()
                        for line in stdout.splitlines()
                        if "equivalent" in line.lower()
                    )[:400]
                else:
                    record["planted_found"] = sum(
                        outputs_false(o) for o in outs if o.exists()
                    )
            out.write(json.dumps(record) + "\n")
            out.flush()
            print(group, command, record["status"], record["time_s"], flush=True)


@click.command()
@click.option(
    "--part",
    type=click.Choice(["operations", "adversarial", "library", "program", "all"]),
    default="all",
)
@click.option("--only", default="", help="Run only this command, such as abc_&cec.")
def main(part: str, only: str) -> None:
    """Run ABC on the generated workloads."""
    if part in ("operations", "all"):
        groups: dict[str, list[pathlib.Path]] = collections.defaultdict(list)
        for f in sorted((WORK / "operations").glob("op_*.aag")):
            groups[re.sub(r"_w8_\d+$", "", f.stem)].append(f)
        for group, files in groups.items():
            run_group("abc", group, files, timeout=600, only=only)
    if part in ("library", "all"):
        run_group(
            "abc",
            "library",
            sorted((WORK / "library").glob("library_*.aag")),
            timeout=600,
            only=only,
        )
    if part in ("adversarial", "all"):
        for f in sorted((WORK / "adversarial").glob("*.aag")):
            if ".miter" in f.name:
                continue
            run_group("abc", f.stem, [f], timeout=300, only=only)
    if part in ("program", "all"):
        # Smallest first. The one-dataflow program of 1,000,000 calls is
        # skipped, as it is for exact sweeping.
        programs = [
            f
            for f in (WORK / "program").glob("program_*.aag")
            if ".miter" not in f.name and f.stem != "program_t200_c1000000"
        ]
        for f in sorted(programs, key=lambda f: f.stat().st_size):
            run_group("abc", f.stem, [f], timeout=1800, only=only)


if __name__ == "__main__":
    main()
