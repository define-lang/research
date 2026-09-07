"""State-driven valid operations, independent of dependency graph construction."""

from __future__ import annotations

import dataclasses
import random
from typing import cast, final

from operation_graph_optimization import algorithm


class Positions:
    """A collection with constant-time indexed selection and removal."""

    def __init__(self):
        """Start with no eligible positions."""
        self.values: list[int] = []
        self.indexes: dict[int, int] = {}

    def add(self, position: int):
        """Include a newly eligible position."""
        self.indexes[position] = len(self.values)
        self.values.append(position)

    def remove(self, position: int):
        """Remove a position that is no longer eligible."""
        index = self.indexes.pop(position)
        last = self.values.pop()
        if index < len(self.values):
            self.values[index] = last
            self.indexes[last] = index


@dataclasses.dataclass(slots=True)
class Position:
    """A position defined by a particular particle, or by the current action."""

    rank: int
    owner: int | None
    name: str
    particle: int | None = None


@dataclasses.dataclass(slots=True)
class Particle:
    """An existing particle and the positions it defines."""

    position: int
    children: tuple[int, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class Choice:
    """One valid statement's final position or source and destination."""

    source: int | None = None
    destination: int | None = None


@final
class State:
    """Track occupancy and particle identity without consulting operation edges."""

    def __init__(self, width: int, depth: int, branching: int, access: str = "local"):
        """Start with empty local positions of each supported constraint shape."""
        self.branching = branching
        self.access = access
        self.positions: dict[int, Position] = {}
        self.particles: dict[int, Particle] = {}
        self.empty = [Positions() for _ in range(depth + 1)]
        self.occupied = [Positions() for _ in range(depth + 1)]
        self.next_position = 0
        self.occurrence = 0
        for rank in range(depth + 1):
            for index in range(width):
                prefix = "/" if access == "implied" else ""
                _ = self._position(rank, None, f"position<{prefix}p{rank}_{index}>")
        self.initial: list[algorithm.Operation] = []
        if access == "implied":
            # The action's own particle exists before its implied qualities
            # can be accessed; it is not one of the movable test particles.
            self.initial.append(
                algorithm.Operation(fill=-1, defines=tuple(self.positions))
            )
            self.occurrence = 1

    def _position(self, rank: int, owner: int | None, name: str) -> int:
        position = self.next_position
        self.next_position += 1
        self.positions[position] = Position(rank, owner, name)
        self.empty[rank].add(position)
        return position

    def counts(self) -> tuple[int, int, int]:
        """Count valid Creates, Moves, and Destroy statements."""
        creates = moves = destroys = 0
        for empty, occupied in zip(self.empty, self.occupied, strict=True):
            creates += len(empty.values)
            moves += len(empty.values) * len(occupied.values)
            destroys += len(occupied.values)
        return creates, moves, destroys

    def choice(self, kind: int, ticket: int) -> Choice:
        """Select one statement by its index among all choices of its kind."""
        for empty, occupied in zip(self.empty, self.occupied, strict=True):
            if kind == 0:
                count = len(empty.values)
            elif kind == 1:
                count = len(empty.values) * len(occupied.values)
            else:
                count = len(occupied.values)
            if ticket >= count:
                ticket -= count
                continue
            if kind == 0:
                return Choice(destination=empty.values[ticket])
            if kind == 2:
                return Choice(source=occupied.values[ticket])
            source, destination = divmod(ticket, len(empty.values))
            return Choice(occupied.values[source], empty.values[destination])
        raise IndexError("Choice ticket is outside the valid operation collection")

    def sample(self, randomizer: random.Random, distribution: str) -> Choice:
        """Choose without favoring collection insertion order."""
        counts = self.counts()
        if distribution == "concrete":
            weights = counts
        else:
            preferences = {
                "balanced": (1, 1, 1),
                "growth": (8, 4, 1),
                "movement": (1, 12, 1),
                "destruction": (4, 1, 4),
            }[distribution]
            weights = tuple(
                preference if count else 0
                for preference, count in zip(preferences, counts, strict=True)
            )
        ticket = randomizer.randrange(sum(weights))
        for kind, weight in enumerate(weights):
            if ticket < weight:
                return self.choice(kind, randomizer.randrange(counts[kind]))
            ticket -= weight
        raise AssertionError("A weighted choice must select an operation kind")

    def reference(self, position: int) -> tuple[str, tuple[int, ...], tuple[int, ...]]:
        """Resolve the written reference using the particles' current positions."""
        names: list[str] = []
        occupied: list[int] = []
        creators: list[int] = []
        current = position
        while True:
            state = self.positions[current]
            names.append(state.name)
            if state.owner is None:
                if self.access == "implied":
                    creators.append(0)
                break
            creators.append(state.owner)
            current = self.particles[state.owner].position
            occupied.append(current)
        return "::".join(reversed(names)), tuple(occupied), tuple(creators)

    def statement(self, choice: Choice) -> str:
        """Render a choice before applying its effects."""
        if choice.source is None:
            destination = cast("int", choice.destination)
            return f"create a particle in {self.reference(destination)[0]}."
        source = self.reference(choice.source)[0]
        if choice.destination is None:
            return f"destroy the particle in {source}."
        destination = self.reference(choice.destination)[0]
        return f"move the particle in {source} to {destination}."

    def apply(self, choice: Choice) -> list[algorithm.Operation]:
        """Apply one statement, selecting all simultaneous Destroys together."""
        occupied: list[int] = []
        creators: list[int] = []
        for position in (choice.source, choice.destination):
            if position is not None:
                _, required, owners = self.reference(position)
                # Move references can share intermediate positions and particles.
                for intermediate in required:
                    if intermediate not in occupied:
                        occupied.append(intermediate)
                for owner in owners:
                    if owner not in creators:
                        creators.append(owner)
        if choice.source is None:
            destination_position = cast("int", choice.destination)
            destination = self.positions[destination_position]
            children: list[int] = []
            if destination.rank:
                for index in range(self.branching):
                    children.append(
                        self._position(
                            destination.rank - 1,
                            self.occurrence,
                            f"position</child{destination.rank}_{index}>",
                        )
                    )
            particle = self.occurrence
            self.particles[particle] = Particle(destination_position, tuple(children))
            self._fill(destination_position, particle)
            operations = [
                algorithm.Operation(
                    occupied=tuple(occupied),
                    fill=choice.destination,
                    creators=tuple(creators),
                    defines=tuple(children),
                )
            ]
            # Each rank's constructor performs this local work. These are real
            # callee statements, not sampler-imposed follow-up choices.
            temporary = self.next_position
            self.next_position += 1
            operations.extend(
                [
                    algorithm.Operation(fill=temporary),
                    algorithm.Operation(empty=temporary),
                ]
            )
        elif choice.destination is not None:
            particle = self._empty(choice.source)
            self._fill(choice.destination, particle)
            self.particles[particle].position = choice.destination
            operations = [
                algorithm.Operation(
                    occupied=tuple(occupied),
                    empty=choice.source,
                    fill=choice.destination,
                    creators=tuple(creators),
                )
            ]
        else:
            operations = [
                algorithm.Operation(
                    occupied=tuple(occupied),
                    empty=choice.source,
                    creators=tuple(creators),
                )
            ]
            pending = [choice.source]
            removed: list[int] = []
            while pending:
                position = pending.pop()
                particle = self._empty(position)
                for child in self.particles.pop(particle).children:
                    removed.append(child)
                    if self.positions[child].particle is not None:
                        pending.append(child)
                        operations.append(algorithm.Operation(empty=child))
            for child in removed:
                self.empty[self.positions[child].rank].remove(child)
                del self.positions[child]
        self.occurrence += len(operations)
        return operations

    def _empty(self, position: int) -> int:
        state = self.positions[position]
        particle = cast("int", state.particle)
        state.particle = None
        self.occupied[state.rank].remove(position)
        self.empty[state.rank].add(position)
        return particle

    def _fill(self, position: int, particle: int):
        state = self.positions[position]
        self.empty[state.rank].remove(position)
        self.occupied[state.rank].add(position)
        state.particle = particle


def generate(
    seed: int,
    steps: int,
    width: int,
    depth: int,
    branching: int,
    distribution: str,
    access: str = "local",
) -> tuple[list[algorithm.Operation], dict[int, int]]:
    """Generate mixed statements and mark simultaneous Destroy groups."""
    state = State(width, depth, branching, access)
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    operations = list(state.initial)
    groups: dict[int, int] = {}
    for _ in range(steps):
        choice = state.sample(randomizer, distribution)
        batch = state.apply(choice)
        if choice.destination is None and len(batch) > 1:
            groups[len(operations)] = len(batch)
        operations.extend(batch)
    return operations, groups
