"""Unpartitioned production Child State algorithm with a tunable copy threshold."""

from __future__ import annotations

import typing

from destruction_contract_benchmarks import snapshots

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


# In our initial experiments, we saw that memory starts to grow quite a bit
# with _very_ large child states (more than 255 tracked positions, over thousands
# of actions). The solution to this was a partitioned representation that maintains
# more constant memory at large sizes. However, those large sizes should be extremely
# rare, so the partitioning implementation seemed like unnecessary complexity.
# If we need it, a full description of it is in the research repo, in
# destruction_contract_benchmarks/TUNING.md.

# The benchmarked compact_base prototype used 256 to keep small snapshots
# on the cheap dictionary-copy path, avoiding sharing overhead.
# This is a measured starting point, not an exhaustively tuned crossover.
flat_limit = 256


def configure(limit: int):
    """Set the copy threshold before constructing any benchmark states."""
    if limit < 1:
        raise ValueError("flat limit must be positive")
    global flat_limit
    flat_limit = limit


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
    """Destruction-time state sharing original knowledge across callers."""

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


def _extended_state(
    base: dict[tuple[str, ...], snapshots.Occupancy],
    additions: dict[tuple[str, ...], snapshots.Occupancy],
) -> snapshots.Snapshot:
    if len(additions) >= len(base):
        return FlatChildState(base | additions)
    return ExtendedChildState(base, additions)
