"""Reproducible destruction-analysis workload shapes, independent of storage."""

from __future__ import annotations

import random
from dataclasses import dataclass

from destruction_contract_benchmarks import snapshots


@dataclass(frozen=True, slots=True)
class Configuration:
    """The dimensions and access pattern of one synthetic program family."""

    initial_positions: int
    callers: int
    additions: int
    overlap: int
    queries: int
    copies: int = 1
    name_depth: int = 3
    caller_shape: str = "chain"
    enumerate_every: int = 0
    query_rounds: int = 1
    query_caller_knowledge: bool = False


@dataclass(frozen=True, slots=True)
class Caller:
    """Knowledge supplied by one distinct caller of a retained action summary."""

    callee: int
    knowledge: dict[snapshots.Position, snapshots.Occupancy]
    queries: tuple[snapshots.Position, ...]


@dataclass(frozen=True, slots=True)
class Workload:
    """Shared program input used by every candidate."""

    configuration: Configuration
    initial: dict[snapshots.Position, snapshots.Occupancy]
    callers: tuple[Caller, ...]


def configuration(case: str, scale: int) -> Configuration:
    """Construct explicitly scaled workloads without hidden global indexes."""
    match case:
        case "small_objects":
            return Configuration(12, 3, 2, 3, 12, copies=2_000 * scale)
        case "wide_registry":
            return Configuration(4_096 * scale, 8, 64, 64, 4_096, name_depth=2)
        case "deep_callers":
            return Configuration(2_048 * scale, 256 * scale, 4, 4, 128)
        case "unchanged_callers":
            return Configuration(2_048 * scale, 256 * scale, 0, 16, 128)
        case "library_fanout":
            return Configuration(
                2_048 * scale, 128 * scale, 8, 8, 256, caller_shape="fanout"
            )
        case "branching_callers":
            return Configuration(
                1_024 * scale, 255 * scale, 16, 8, 256, caller_shape="branching"
            )
        case "dense_callers":
            return Configuration(1_024 * scale, 32, 1_024 * scale, 512, 1_024)
        case "read_heavy":
            return Configuration(4_096 * scale, 64, 16, 16, 4_096, query_rounds=8)
        case "deep_names":
            return Configuration(512 * scale, 32, 8, 8, 512, name_depth=64 * scale)
        case "full_traversal":
            return Configuration(4_096 * scale, 32, 32, 16, 512, enumerate_every=1)
        case "older_caller_knowledge":
            return Configuration(
                128, 256 * scale, 16, 4, 1_024, query_caller_knowledge=True
            )
        case _:
            raise ValueError(f"unknown case: {case}")


CASES = (
    "small_objects",
    "wide_registry",
    "deep_callers",
    "unchanged_callers",
    "library_fanout",
    "branching_callers",
    "dense_callers",
    "read_heavy",
    "deep_names",
    "full_traversal",
    "older_caller_knowledge",
)


def _position(index: int, depth: int) -> snapshots.Position:
    if depth == 2:
        return (f"position</resource_{index}>", "position</handle>")
    if depth > 8:
        prefix = ("position</component>",) * (depth - 2)
        return (*prefix, f"position</resource_{index}>", "position</handle>")
    return (
        f"position</group_{index // 64}>",
        f"position</resource_{index % 64}>",
        "position</handle>",
    )


def _occupancy(index: int) -> snapshots.Occupancy:
    if index % 11 == 0:
        return snapshots.EMPTY
    if index % 19 == 0:
        return snapshots.ERROR
    return snapshots.Occupancy(1, index + 1)


def _add_position(
    values: dict[snapshots.Position, snapshots.Occupancy],
    position: snapshots.Position,
    occupancy: snapshots.Occupancy,
    fill_site: int,
):
    for depth in range(1, len(position)):
        parent = position[:depth]
        if parent not in values:
            values[parent] = snapshots.Occupancy(1, fill_site)
    values[position] = occupancy


def generate(configuration: Configuration, seed: int) -> Workload:
    """Generate caller knowledge and both successful and absent requirements."""
    randomizer = random.Random(seed)  # noqa: S311 - Benchmark inputs must be reproducible.
    initial: dict[snapshots.Position, snapshots.Occupancy] = {}
    for index in range(configuration.initial_positions):
        _add_position(
            initial,
            _position(index, configuration.name_depth),
            _occupancy(index),
            index + 1,
        )
    initial_keys = tuple(initial)
    callers: list[Caller] = []
    next_index = configuration.initial_positions
    for caller_index in range(configuration.callers):
        match configuration.caller_shape:
            case "chain":
                callee = caller_index
            case "fanout":
                callee = 0
            case "branching":
                callee = caller_index // 2
            case _:
                raise ValueError(configuration.caller_shape)
        knowledge: dict[snapshots.Position, snapshots.Occupancy] = {}
        new_positions: list[snapshots.Position] = []
        for _ in range(configuration.additions):
            position = _position(next_index, configuration.name_depth)
            _add_position(knowledge, position, _occupancy(next_index), next_index + 1)
            new_positions.append(position)
            next_index += 1
        for _ in range(configuration.overlap):
            position = randomizer.choice(initial_keys)
            # The callee must win even when the caller disagrees on occupancy.
            knowledge[position] = snapshots.Occupancy(1, -caller_index - 1)
        queries: list[snapshots.Position] = []
        earlier_keys = initial_keys
        if configuration.query_caller_knowledge and callee:
            earlier = randomizer.randrange(callee)
            earlier_keys = tuple(callers[earlier].knowledge)
        for query_index in range(configuration.queries):
            match query_index % 8:
                case 0:
                    position = _position(
                        next_index + query_index + 100_000_000,
                        configuration.name_depth,
                    )
                case 1 | 2 if new_positions:
                    position = randomizer.choice(new_positions)
                case _:
                    position = randomizer.choice(earlier_keys)
            queries.append(position)
        callers.append(Caller(callee, knowledge, tuple(queries)))
    return Workload(configuration, initial, tuple(callers))
