"""Compiler Child State algorithm with process-local tuning parameters."""

from __future__ import annotations

import typing

from destruction_contract_benchmarks import snapshots

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

flat_limit = 256
partition_count = 1_024
partition_mask = partition_count - 1


def configure(limit: int, partitions: int):
    """Set parameters before creating snapshots in an isolated worker."""
    if limit < 1:
        raise ValueError("flat limit must be positive")
    if partitions < 1 or partitions & (partitions - 1):
        raise ValueError("partition count must be a positive power of two")
    global flat_limit, partition_count, partition_mask
    flat_limit = limit
    partition_count = partitions
    partition_mask = partitions - 1


@typing.final
class FlatChildState(snapshots.Snapshot):
    """A small or newly captured destruction-time snapshot."""

    __slots__: tuple[str, ...] = ("_values",)

    def __init__(self, values: dict[tuple[str, ...], snapshots.Occupancy]):
        """Take ownership of values that will no longer be mutated."""
        self._values = values

    @typing.override
    def get(self, position: tuple[str, ...]) -> snapshots.Occupancy | None:
        return self._values.get(position)

    @typing.override
    def with_caller(
        self, caller: dict[tuple[str, ...], snapshots.Occupancy]
    ) -> snapshots.Snapshot:
        if len(self._values) < flat_limit:
            values = caller.copy()
            values.update(self._values)
            if len(values) == len(self._values):
                return self
            return FlatChildState(values)
        additions: dict[tuple[str, ...], snapshots.Occupancy] = {}
        for position, occupancy in caller.items():
            if position not in self._values:
                additions[position] = occupancy
        if not additions:
            return self
        return _extended_state(self._values, additions)

    @typing.override
    def items(
        self,
    ) -> Iterable[tuple[tuple[str, ...], snapshots.Occupancy]]:
        return self._values.items()


@typing.final
class ExtendedChildState(snapshots.Snapshot):
    """Destruction-time state with a small amount of additional caller knowledge."""

    __slots__: tuple[str, ...] = ("_additions", "_base")

    def __init__(
        self,
        base: dict[tuple[str, ...], snapshots.Occupancy],
        additions: dict[tuple[str, ...], snapshots.Occupancy],
    ):
        """Take ownership of disjoint dictionaries that will no longer be mutated."""
        self._base = base
        self._additions = additions

    @typing.override
    def get(self, position: tuple[str, ...]) -> snapshots.Occupancy | None:
        occupancy = self._base.get(position)
        if occupancy is not None:
            return occupancy
        return self._additions.get(position)

    @typing.override
    def with_caller(
        self, caller: dict[tuple[str, ...], snapshots.Occupancy]
    ) -> snapshots.Snapshot:
        unknown: dict[tuple[str, ...], snapshots.Occupancy] = {}
        for position, occupancy in caller.items():
            if position not in self._base and position not in self._additions:
                unknown[position] = occupancy
        if not unknown:
            return self
        return _extended_state(self._base, self._additions | unknown)

    @typing.override
    def items(
        self,
    ) -> Iterator[tuple[tuple[str, ...], snapshots.Occupancy]]:
        yield from self._base.items()
        yield from self._additions.items()


@typing.final
class PartitionedChildState(snapshots.Snapshot):
    """Destruction-time state with shared, independently extensible caller knowledge."""

    __slots__: tuple[str, ...] = ("_addition_count", "_additions", "_base")

    def __init__(
        self,
        base: dict[tuple[str, ...], snapshots.Occupancy],
        additions: tuple[dict[tuple[str, ...], snapshots.Occupancy], ...],
        addition_count: int,
    ):
        """Take ownership of dictionaries that will no longer be mutated."""
        self._base = base
        self._additions = additions
        self._addition_count = addition_count

    @typing.override
    def get(self, position: tuple[str, ...]) -> snapshots.Occupancy | None:
        occupancy = self._base.get(position)
        if occupancy is not None:
            return occupancy
        return self._additions[hash(position) & partition_mask].get(position)

    @typing.override
    def with_caller(
        self, caller: dict[tuple[str, ...], snapshots.Occupancy]
    ) -> snapshots.Snapshot:
        changed: dict[int, dict[tuple[str, ...], snapshots.Occupancy]] = {}
        addition_count = self._addition_count
        for position, occupancy in caller.items():
            if position in self._base:
                continue
            partition_index = hash(position) & partition_mask
            previous = self._additions[partition_index]
            if position in previous:
                continue
            addition_count += 1
            partition = changed.get(partition_index)
            if partition is None:
                partition = previous.copy()
                changed[partition_index] = partition
            partition[position] = occupancy
        if not changed:
            return self
        additions = list(self._additions)
        for partition_index, partition in changed.items():
            additions[partition_index] = partition
        if addition_count >= len(self._base):
            base = self._base.copy()
            for partition in additions:
                base.update(partition)
            return FlatChildState(base)
        return PartitionedChildState(self._base, tuple(additions), addition_count)

    @typing.override
    def items(
        self,
    ) -> Iterator[tuple[tuple[str, ...], snapshots.Occupancy]]:
        yield from self._base.items()
        for partition in self._additions:
            yield from partition.items()


def _extended_state(
    base: dict[tuple[str, ...], snapshots.Occupancy],
    additions: dict[tuple[str, ...], snapshots.Occupancy],
) -> snapshots.Snapshot:
    if len(additions) >= len(base):
        return FlatChildState(base | additions)
    if len(additions) >= flat_limit:
        partitions: list[dict[tuple[str, ...], snapshots.Occupancy]] = [
            {} for _ in range(partition_count)
        ]
        for position, occupancy in additions.items():
            partitions[hash(position) & partition_mask][position] = occupancy
        return PartitionedChildState(base, tuple(partitions), len(additions))
    return ExtendedChildState(base, additions)
