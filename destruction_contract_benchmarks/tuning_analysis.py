"""Summarize parameter sweeps without hiding failures or per-case regressions."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import typing
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

if typing.TYPE_CHECKING:
    from destruction_contract_benchmarks import run

type Case = tuple[str, int, int]
type Group = tuple[Case, str]


@dataclass(frozen=True)
class Aggregate:
    """Repeated measurements for one case, scale, seed, and parameter pair."""

    cpu: float
    peak: float
    retained: float
    minimum_cpu: float
    maximum_cpu: float
    samples: int
    failures: int


def number(record: run.Record, key: str) -> float:
    """Read a numeric result field."""
    value = record[key]
    if not isinstance(value, int | float):
        raise TypeError(f"not a number: {key}={value}")
    return float(value)


def collect(directories: list[Path]) -> dict[Group, Aggregate]:
    """Combine repetitions while keeping every resource failure visible."""
    records: defaultdict[Group, list[run.Record]] = defaultdict(list)
    for directory in directories:
        for filename in sorted(directory.glob("*.json")):
            if filename.name == "manifest.json":
                continue
            record = typing.cast("run.Record", json.loads(filename.read_text()))
            if record["allocation_tracing"]:
                raise ValueError("allocation-traced timings must not be ranked")
            case = (
                str(record["case"]),
                int(number(record, "scale")),
                int(number(record, "seed")),
            )
            parameter = str(record["variant"])
            if parameter == "production":
                parameter = f"{int(number(record, 'flat_limit'))}/{int(number(record, 'partition_count'))}"
            records[(case, parameter)].append(record)
    aggregates: dict[Group, Aggregate] = {}
    for group, repetitions in records.items():
        cpu: list[float] = []
        peak: list[float] = []
        retained: list[float] = []
        failures = 0
        for record in repetitions:
            if record["status"] != "ok":
                failures += 1
                continue
            cpu.append(number(record, "total_cpu_s"))
            peak.append(number(record, "peak_rss_bytes"))
            retained.append(number(record, "incremental_rss_bytes"))
        if cpu:
            aggregates[group] = Aggregate(
                statistics.median(cpu),
                statistics.median(peak),
                statistics.median(retained),
                min(cpu),
                max(cpu),
                len(cpu),
                failures,
            )
        else:
            aggregates[group] = Aggregate(
                math.inf, math.inf, math.inf, math.inf, math.inf, 0, failures
            )
    return aggregates


def geometric_mean(values: list[float]) -> float:
    """Aggregate ratios without assigning physical units to the result."""
    return math.exp(statistics.mean(math.log(value) for value in values))


def report(
    aggregates: dict[Group, Aggregate], baseline: str, details: list[str]
) -> str:
    """Show comparable-case ratios together with coverage and failure counts."""
    baselines: dict[Case, Aggregate] = {}
    parameters: set[str] = set()
    for (case, parameter), aggregate in aggregates.items():
        parameters.add(parameter)
        if parameter == baseline:
            baselines[case] = aggregate
    if not baselines:
        raise ValueError(f"missing baseline: {baseline}")
    rows: list[tuple[float, str]] = []
    for parameter in sorted(parameters):
        cpu_ratios: list[float] = []
        peak_ratios: list[float] = []
        failures = 0
        worst_cpu = (0.0, "")
        worst_peak = (0.0, "")
        for case, reference in baselines.items():
            candidate = aggregates.get((case, parameter))
            if candidate is None:
                continue
            failures += candidate.failures
            if not candidate.samples or not reference.samples:
                continue
            cpu = candidate.cpu / reference.cpu
            peak = candidate.peak / reference.peak
            cpu_ratios.append(cpu)
            peak_ratios.append(peak)
            name = f"{case[0]}:s{case[1]}:seed{case[2]}"
            worst_cpu = max(worst_cpu, (cpu, name))
            worst_peak = max(worst_peak, (peak, name))
        if not cpu_ratios:
            rows.append(
                (
                    math.inf,
                    f"| {parameter} | 0/{len(baselines)} | {failures} | unavailable | unavailable | unavailable | unavailable |",
                )
            )
            continue
        mean_cpu = geometric_mean(cpu_ratios)
        mean_peak = geometric_mean(peak_ratios)
        rows.append(
            (
                mean_cpu,
                f"| {parameter} | {len(cpu_ratios)}/{len(baselines)} | {failures} | {mean_cpu:.3f} | {mean_peak:.3f} | {worst_cpu[0]:.3f} ({worst_cpu[1]}) | {worst_peak[0]:.3f} ({worst_peak[1]}) |",
            )
        )
    lines = [
        f"Ratios relative to {baseline}; lower is better. Cases include scale and seed.",
        "Only compare aggregate scores with equal coverage and no failures.",
        "",
        "| Pair/control | Cases | Failures | CPU geomean | Peak RSS geomean | Worst CPU | Worst RSS |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in sorted(rows):
        lines.append(row)
    for parameter in details:
        lines.extend(
            [
                "",
                f"## {parameter}",
                "",
                "| Case | Scale | Seed | CPU ms (min-max) | Peak MiB | Additional retained MiB | Samples | Failures | CPU ratio |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for case, reference in sorted(baselines.items()):
            aggregate = aggregates.get((case, parameter))
            if aggregate is None:
                continue
            ratio = aggregate.cpu / reference.cpu if reference.samples else math.nan
            lines.append(
                f"| {case[0]} | {case[1]} | {case[2]} | {aggregate.cpu * 1000:.2f} ({aggregate.minimum_cpu * 1000:.2f}-{aggregate.maximum_cpu * 1000:.2f}) | {aggregate.peak / 2**20:.2f} | {aggregate.retained / 2**20:.2f} | {aggregate.samples} | {aggregate.failures} | {ratio:.3f} |"
            )
    return "\n".join(lines) + "\n"


def main():
    """Print a reproducible Markdown summary of one or more comparable sweeps."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("directories", nargs="+", type=Path)
    _ = parser.add_argument("--baseline", default="256/1024")
    _ = parser.add_argument("--details", default="")
    _ = parser.add_argument("--save", type=Path)
    arguments = parser.parse_args()
    directories = typing.cast("list[Path]", arguments.directories)
    baseline = typing.cast("str", arguments.baseline)
    details = typing.cast("str", arguments.details)
    destination = typing.cast("Path | None", arguments.save)
    summary = report(
        collect(directories), baseline, details.split(",") if details else []
    )
    print(summary, end="")
    if destination is not None:
        _ = destination.write_text(summary)


if __name__ == "__main__":
    main()
