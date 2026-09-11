"""Alternative immutable Child State snapshots for standalone experiments."""

from __future__ import annotations

import abc
import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

type Position = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Occupancy:
    """The state and diagnostic fill location of a known position."""

    state: int
    fill_site: int


EMPTY = Occupancy(0, 0)
ERROR = Occupancy(2, 0)


class Snapshot(abc.ABC):
    """An immutable destruction-time view that a caller can extend."""

    __slots__: tuple[str, ...] = ()

    @abc.abstractmethod
    def get(self, position: Position) -> Occupancy | None:
        """Look up known state, distinguishing absent state from empty."""
        raise NotImplementedError

    @abc.abstractmethod
    def with_caller(self, caller: dict[Position, Occupancy]) -> Snapshot:
        """Combine earlier caller knowledge with authoritative callee state."""
        raise NotImplementedError

    @abc.abstractmethod
    def items(self) -> Iterable[tuple[Position, Occupancy]]:
        """Enumerate all known positions."""
        raise NotImplementedError

    def nearest_occupied_parent(self, position: Position) -> Occupancy | None:
        """Find the closest known occupied position among the parent names."""
        for depth in range(len(position) - 1, -1, -1):
            occupancy = self.get(position[:depth])
            if occupancy is not None and occupancy.state == 1:
                return occupancy
        return None


class CurrentFlat(Snapshot):
    """Copy a caller snapshot and overlay the callee, as the compiler does."""

    __slots__: tuple[str, ...] = ("values",)
    values: dict[Position, Occupancy]

    def __init__(self, values: dict[Position, Occupancy]):
        """Publish a private dictionary as a snapshot."""
        self.values = values

    @typing.override
    def get(self, position: Position) -> Occupancy | None:
        return self.values.get(position)

    @typing.override
    def with_caller(self, caller: dict[Position, Occupancy]) -> Snapshot:
        values = caller.copy()
        values.update(self.values)
        return CurrentFlat(values)

    @typing.override
    def items(self) -> Iterable[tuple[Position, Occupancy]]:
        return self.values.items()


class SharedFlat(CurrentFlat):
    """Reuse unchanged snapshots and copy only when callers add knowledge."""

    __slots__: tuple[str, ...] = ()

    @typing.override
    def with_caller(self, caller: dict[Position, Occupancy]) -> SharedFlat:
        additions: dict[Position, Occupancy] = {}
        for position, value in caller.items():
            if position not in self.values:
                additions[position] = value
        if not additions:
            return self
        return SharedFlat(self.values | additions)


class Partitioned(Snapshot):
    """Share dictionary partitions and copy each changed partition once."""

    __slots__: tuple[str, ...] = ("mask", "partitions", "size")
    partitions: tuple[dict[Position, Occupancy], ...]
    mask: int
    size: int

    def __init__(self, partitions: tuple[dict[Position, Occupancy], ...], size: int):
        """Publish private dictionary partitions."""
        self.partitions = partitions
        self.mask = len(partitions) - 1
        self.size = size

    @classmethod
    def empty(cls, count: int) -> Partitioned:
        """Share an empty immutable bucket until a caller adds knowledge."""
        empty: dict[Position, Occupancy] = {}
        return cls((empty,) * count, 0)

    @classmethod
    def from_values(cls, values: dict[Position, Occupancy], count: int) -> Partitioned:
        """Build a hash-partitioned snapshot, charging for its index."""
        partitions: list[dict[Position, Occupancy]] = [{} for _ in range(count)]
        mask = count - 1
        for position, value in values.items():
            partitions[hash(position) & mask][position] = value
        return cls(tuple(partitions), len(values))

    @typing.override
    def get(self, position: Position) -> Occupancy | None:
        return self.partitions[hash(position) & self.mask].get(position)

    @typing.override
    def with_caller(self, caller: dict[Position, Occupancy]) -> Partitioned:
        changed: dict[int, dict[Position, Occupancy]] = {}
        size = self.size
        for position, value in caller.items():
            partition_index = hash(position) & self.mask
            previous = self.partitions[partition_index]
            if position in previous:
                continue
            size += 1
            partition = changed.get(partition_index)
            if partition is None:
                partition = previous.copy()
                changed[partition_index] = partition
            partition[position] = value
        if not changed:
            return self
        partitions = list(self.partitions)
        for partition_index, partition in changed.items():
            partitions[partition_index] = partition
        return Partitioned(tuple(partitions), size)

    @typing.override
    def items(self) -> Iterator[tuple[Position, Occupancy]]:
        for partition in self.partitions:
            yield from partition.items()


class BaseAndPartitions(Snapshot):
    """Read common callee state directly and share partitions of new knowledge."""

    __slots__: tuple[str, ...] = ("additions", "base")
    base: dict[Position, Occupancy]
    additions: Partitioned

    def __init__(self, base: dict[Position, Occupancy], additions: Partitioned):
        """Publish a common base and disjoint caller additions."""
        self.base = base
        self.additions = additions

    @typing.override
    def get(self, position: Position) -> Occupancy | None:
        value = self.base.get(position)
        if value is not None:
            return value
        return self.additions.get(position)

    @typing.override
    def with_caller(self, caller: dict[Position, Occupancy]) -> BaseAndPartitions:
        unknown: dict[Position, Occupancy] = {}
        for position, value in caller.items():
            if position not in self.base:
                unknown[position] = value
        additions = self.additions.with_caller(unknown)
        if additions is self.additions:
            return self
        if additions.size >= max(len(self.base), 256):
            base = self.base.copy()
            base.update(additions.items())
            return BaseAndPartitions(base, Partitioned.empty(len(additions.partitions)))
        return BaseAndPartitions(self.base, additions)

    @typing.override
    def items(self) -> Iterator[tuple[Position, Occupancy]]:
        yield from self.base.items()
        yield from self.additions.items()


class AdaptiveFlat(CurrentFlat):
    """Use native flat dictionaries for small state and migrate when it grows."""

    __slots__: tuple[str, ...] = ("partition_count", "threshold")
    partition_count: int
    threshold: int

    def __init__(
        self, values: dict[Position, Occupancy], threshold: int, partition_count: int
    ):
        """Keep the small-object path free of partition directories."""
        super().__init__(values)
        self.threshold = threshold
        self.partition_count = partition_count

    @typing.override
    def with_caller(self, caller: dict[Position, Occupancy]) -> Snapshot:
        additions: dict[Position, Occupancy] = {}
        for position, value in caller.items():
            if position not in self.values:
                additions[position] = value
        if not additions:
            return self
        values = self.values | additions
        if len(values) >= self.threshold:
            return BaseAndPartitions(values, Partitioned.empty(self.partition_count))
        return AdaptiveFlat(values, self.threshold, self.partition_count)


def adaptive(
    values: dict[Position, Occupancy], threshold: int, partitions: int
) -> Snapshot:
    """Choose a representation by state size, not by benchmark case name."""
    if len(values) < threshold:
        return AdaptiveFlat(values.copy(), threshold, partitions)
    return BaseAndPartitions(values.copy(), Partitioned.empty(partitions))


class CompactFlat(CurrentFlat):
    """Keep unchanged and small snapshots on the direct dictionary path."""

    __slots__: tuple[str, ...] = ()

    @typing.override
    def with_caller(self, caller: dict[Position, Occupancy]) -> Snapshot:
        if len(self.values) < 256:
            values = caller.copy()
            values.update(self.values)
            if len(values) == len(self.values):
                return self
            return CompactFlat(values)
        additions: dict[Position, Occupancy] = {}
        for position, value in caller.items():
            if position not in self.values:
                additions[position] = value
        if not additions:
            return self
        return CompactBase(self.values, additions).compact()


class CompactBase(Snapshot):
    """Share a direct-lookup base with a small flat dictionary of additions."""

    __slots__: tuple[str, ...] = ("additions", "base")
    base: dict[Position, Occupancy]
    additions: dict[Position, Occupancy]

    def __init__(
        self, base: dict[Position, Occupancy], additions: dict[Position, Occupancy]
    ):
        """Publish disjoint immutable dictionaries."""
        self.base = base
        self.additions = additions

    @typing.override
    def get(self, position: Position) -> Occupancy | None:
        value = self.base.get(position)
        if value is not None:
            return value
        return self.additions.get(position)

    @typing.override
    def with_caller(self, caller: dict[Position, Occupancy]) -> Snapshot:
        unknown: dict[Position, Occupancy] = {}
        for position, value in caller.items():
            if position not in self.base and position not in self.additions:
                unknown[position] = value
        if not unknown:
            return self
        return CompactBase(self.base, self.additions | unknown).compact()

    def compact(self) -> Snapshot:
        """Bound growth without paying partition costs for small additions."""
        if len(self.additions) >= len(self.base):
            return CompactFlat(self.base | self.additions)
        if len(self.additions) >= 256:
            return BaseAndPartitions(
                self.base, Partitioned.from_values(self.additions, 1024)
            )
        return self

    @typing.override
    def items(self) -> Iterator[tuple[Position, Occupancy]]:
        yield from self.base.items()
        yield from self.additions.items()


class Overlay(Snapshot):
    """Bound dictionary-overlay depth by periodically materializing a snapshot."""

    __slots__: tuple[str, ...] = ("depth", "maximum_depth", "previous", "values")
    values: dict[Position, Occupancy]
    previous: Overlay | None
    depth: int
    maximum_depth: int

    def __init__(
        self,
        values: dict[Position, Occupancy],
        previous: Overlay | None,
        maximum_depth: int,
    ):
        """Publish additions that do not replace known callee state."""
        self.values = values
        self.previous = previous
        self.depth = 0 if previous is None else previous.depth + 1
        self.maximum_depth = maximum_depth

    @typing.override
    def get(self, position: Position) -> Occupancy | None:
        current: Overlay | None = self
        while current is not None:
            value = current.values.get(position)
            if value is not None:
                return value
            current = current.previous
        return None

    @typing.override
    def with_caller(self, caller: dict[Position, Occupancy]) -> Overlay:
        additions: dict[Position, Occupancy] = {}
        for position, value in caller.items():
            if self.get(position) is None:
                additions[position] = value
        if not additions:
            return self
        if self.depth == self.maximum_depth:
            additions.update(self.items())
            return Overlay(additions, None, self.maximum_depth)
        return Overlay(additions, self, self.maximum_depth)

    @typing.override
    def items(self) -> Iterator[tuple[Position, Occupancy]]:
        current: Overlay | None = self
        while current is not None:
            yield from current.values.items()
            current = current.previous


class _PositionNode:
    __slots__: tuple[str, ...] = ("children", "occupancy")
    occupancy: Occupancy | None
    children: dict[str, _PositionNode]

    def __init__(self, occupancy: Occupancy | None, children: dict[str, _PositionNode]):
        self.occupancy = occupancy
        self.children = children


class PositionTree(Snapshot):
    """Batch path-copying position trie with direct shared child views."""

    __slots__: tuple[str, ...] = ("top",)
    top: _PositionNode

    def __init__(self, top: _PositionNode):
        """Publish a node whose descendants will no longer be mutated."""
        self.top = top

    @classmethod
    def from_values(cls, values: dict[Position, Occupancy]) -> PositionTree:
        """Construct a position tree without repeated path copying."""
        top = _PositionNode(None, {})
        for position, value in values.items():
            current = top
            for name in position:
                child = current.children.get(name)
                if child is None:
                    child = _PositionNode(None, {})
                    current.children[name] = child
                current = child
            current.occupancy = value
        return cls(top)

    @typing.override
    def get(self, position: Position) -> Occupancy | None:
        current = self.top
        for name in position:
            child = current.children.get(name)
            if child is None:
                return None
            current = child
        return current.occupancy

    @typing.override
    def with_caller(self, caller: dict[Position, Occupancy]) -> PositionTree:
        additions: dict[Position, Occupancy] = {}
        for position, value in caller.items():
            if self.get(position) is None:
                additions[position] = value
        if not additions:
            return self
        top = _PositionNode(self.top.occupancy, self.top.children.copy())
        private_nodes = {top}
        for position, value in additions.items():
            current = top
            for name in position:
                child = current.children.get(name)
                if child is None:
                    child = _PositionNode(None, {})
                    current.children[name] = child
                    private_nodes.add(child)
                elif child not in private_nodes:
                    child = _PositionNode(child.occupancy, child.children.copy())
                    current.children[name] = child
                    private_nodes.add(child)
                current = child
            current.occupancy = value
        return PositionTree(top)

    @typing.override
    def items(self) -> Iterator[tuple[Position, Occupancy]]:
        stack: list[tuple[Position, _PositionNode]] = [((), self.top)]
        while stack:
            position, current = stack.pop()
            if current.occupancy is not None:
                yield position, current.occupancy
            for name, child in current.children.items():
                stack.append(((*position, name), child))

    def at_particle(self, position: Position) -> PositionTree:
        """Obtain a child's state without copying its transitive children."""
        current = self.top
        for name in position:
            current = current.children[name]
        return PositionTree(current)


type Factory = Callable[[dict[Position, Occupancy]], Snapshot]

FACTORIES: dict[str, Factory] = {
    "current_flat": lambda values: CurrentFlat(values.copy()),
    "shared_flat": lambda values: SharedFlat(values.copy()),
    "partitions_16": lambda values: Partitioned.from_values(values, 16),
    "partitions_64": lambda values: Partitioned.from_values(values, 64),
    "partitions_256": lambda values: Partitioned.from_values(values, 256),
    "partitions_1024": lambda values: Partitioned.from_values(values, 1024),
    "overlay_4": lambda values: Overlay(values.copy(), None, 4),
    "overlay_16": lambda values: Overlay(values.copy(), None, 16),
    "position_tree": PositionTree.from_values,
    "base_partitions_64": lambda values: BaseAndPartitions(
        values.copy(), Partitioned.empty(64)
    ),
    "base_partitions_1024": lambda values: BaseAndPartitions(
        values.copy(), Partitioned.empty(1024)
    ),
    "adaptive_256": lambda values: adaptive(values, 256, 1024),
    "adaptive_2048": lambda values: adaptive(values, 2048, 1024),
    "compact_base": lambda values: CompactFlat(values.copy()),
}
