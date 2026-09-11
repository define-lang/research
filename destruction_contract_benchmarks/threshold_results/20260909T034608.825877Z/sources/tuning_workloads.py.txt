"""Threshold-sensitive workloads supplementing the original benchmark families."""

from __future__ import annotations

from destruction_contract_benchmarks import workloads

MEDIUM_SIZES = (32, 128, 512, 2_048)
MEDIUM_CASES = tuple(f"medium_{size}" for size in MEDIUM_SIZES)
FANOUT_CASES = tuple(f"fanout_{size}" for size in MEDIUM_SIZES)
EXTRA_CASES = (
    "sparse_updates",
    "batch_updates",
    "overlap_updates",
    "branch_updates",
)
CASES = (*workloads.CASES, *MEDIUM_CASES, *FANOUT_CASES, *EXTRA_CASES)


def configuration(case: str, scale: int) -> workloads.Configuration:
    """Keep medium-object sizes fixed while scaling their number of instances."""
    if case in workloads.CASES:
        return workloads.configuration(case, scale)
    if case in MEDIUM_CASES:
        size = int(case.removeprefix("medium_"))
        return workloads.Configuration(size, 16, 1, 8, 32, copies=64 * scale)
    if case in FANOUT_CASES:
        size = int(case.removeprefix("fanout_"))
        return workloads.Configuration(
            size, 8, 4, 8, 32, copies=64 * scale, caller_shape="fanout"
        )
    match case:
        case "sparse_updates":
            return workloads.Configuration(4_096 * scale, 1_024 * scale, 1, 1, 32)
        case "batch_updates":
            return workloads.Configuration(4_096 * scale, 128 * scale, 64, 16, 32)
        case "overlap_updates":
            return workloads.Configuration(1_024 * scale, 128 * scale, 1, 1_024, 32)
        case "branch_updates":
            return workloads.Configuration(
                1_024 * scale, 255 * scale, 128, 16, 32, caller_shape="branching"
            )
        case _:
            raise ValueError(f"unknown tuning case: {case}")
