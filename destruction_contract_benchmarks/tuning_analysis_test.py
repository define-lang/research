from __future__ import annotations

import json
import math
import typing

import pytest

from destruction_contract_benchmarks import tuning_analysis

if typing.TYPE_CHECKING:
    from pathlib import Path


def test_medians_include_failure_counts(tmp_path: Path):
    common = {
        "case": "small_objects",
        "scale": 4,
        "seed": 74921,
        "variant": "production",
        "flat_limit": 256,
        "partition_count": 1024,
        "allocation_tracing": False,
    }
    for index, duration in enumerate((1.0, 2.0, 9.0)):
        record = common | {
            "status": "ok",
            "total_cpu_s": duration,
            "peak_rss_bytes": duration * 1024,
            "incremental_rss_bytes": duration * 512,
        }
        _ = (tmp_path / f"{index}.json").write_text(json.dumps(record))
    _ = (tmp_path / "failure.json").write_text(
        json.dumps(common | {"status": "timeout"})
    )
    _ = (tmp_path / "manifest.json").write_text("{}")
    aggregates = tuning_analysis.collect([tmp_path])
    assert aggregates == {
        (("small_objects", 4, 74921), "256/1024"): tuning_analysis.Aggregate(
            2.0, 2048.0, 1024.0, 1.0, 9.0, 3, 1
        )
    }
    summary = tuning_analysis.report(aggregates, "256/1024", ["256/1024"])
    assert "| 256/1024 | 1/1 | 1 | 1.000 | 1.000 |" in summary
    assert "| 3 | 1 | 1.000 |" in summary


def test_traced_timings_are_not_ranked(tmp_path: Path):
    _ = (tmp_path / "traced.json").write_text('{"allocation_tracing": true}')
    with pytest.raises(ValueError, match="allocation-traced"):
        _ = tuning_analysis.collect([tmp_path])


def test_missing_and_failed_cases_remain_visible():
    case = ("deep_callers", 4, 74921)
    successful = tuning_analysis.Aggregate(2.0, 100.0, 50.0, 1.0, 3.0, 3, 0)
    failed = tuning_analysis.Aggregate(
        math.inf, math.inf, math.inf, math.inf, math.inf, 0, 3
    )
    aggregates: dict[tuning_analysis.Group, tuning_analysis.Aggregate] = {
        (case, "256/1024"): successful,
        (case, "4096/4"): failed,
    }
    summary = tuning_analysis.report(aggregates, "256/1024", ["4096/4", "missing"])
    assert "| 4096/4 | 0/1 | 3 | unavailable |" in summary
    assert "| 0 | 3 | inf |" in summary
    with pytest.raises(ValueError, match="missing baseline"):
        _ = tuning_analysis.report(aggregates, "missing", [])


def test_ratio_geometric_mean():
    assert tuning_analysis.geometric_mean([0.5, 2.0]) == 1.0


def test_invalid_numeric_field():
    with pytest.raises(TypeError, match="not a number"):
        _ = tuning_analysis.number({"value": "not numeric"}, "value")
