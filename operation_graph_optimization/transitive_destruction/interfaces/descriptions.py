"""Small action descriptions with references but no supplied dependency edges."""

from __future__ import annotations

import dataclasses
import random


@dataclasses.dataclass(frozen=True)
class Reference:
    """A resolved position identity and the written intermediate positions."""

    position: int
    intermediate: tuple[int, ...] = ()


@dataclasses.dataclass(frozen=True)
class Create:
    """Create a particle that assigns the listed child positions."""

    target: Reference
    children: tuple[int, ...] = ()


@dataclasses.dataclass(frozen=True)
class Move:
    """Move the selected particle between two existing positions."""

    source: Reference
    target: Reference


@dataclasses.dataclass(frozen=True)
class Select:
    """Issue destruction of an occupied position and its transitive children."""

    source: Reference


@dataclasses.dataclass(frozen=True)
class Action:
    """An independently described action and the positions its contract knows."""

    name: str
    known: tuple[int, ...]
    statements: tuple[Create | Move | Select | Call, ...]


@dataclasses.dataclass(frozen=True)
class Call:
    """One direct-callee occurrence, without caller-dependent callee code."""

    action: Action


@dataclasses.dataclass(frozen=True)
class Program:
    """Caller setup, destruction through a callee, and caller-only destructors."""

    setup: Action
    callee: Action
    destructors: tuple[Action, ...]


def generate(seed: int, width: int, steps: int, depth: int = 0) -> Program:
    """Choose valid operations from current occupancy, independently of graph rules."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible descriptions.
    positions = tuple(range(2, width + 2))
    known_count = max(2, width // 2)
    visible = positions[:known_count]
    setup: list[Create | Move | Select | Call] = [
        Create(Reference(0), (1,)),
        Create(Reference(1, (0,)), positions),
    ]
    occupied = set(positions[::2])
    for position in sorted(occupied):
        setup.append(Create(Reference(position, (0, 1))))
    body: list[Create | Move | Select | Call] = []
    for _ in range(steps):
        filled = sorted(occupied.intersection(visible))
        empty = sorted(set(visible) - occupied)
        if not empty:
            break
        target = randomizer.choice(empty)
        if filled and randomizer.randrange(5):
            source = randomizer.choice(filled)
            body.append(Move(Reference(source, (0, 1)), Reference(target, (0, 1))))
            occupied.remove(source)
        else:
            body.append(Create(Reference(target, (0, 1))))
        occupied.add(target)
    body.append(Select(Reference(0)))
    callee = Action("callee", (0, 1, *visible), tuple(body))
    for index in range(depth):
        callee = Action(f"forward{index}", (0, 1, *visible), (Call(callee),))
    destructors: list[Action] = []
    for index in range(3):
        moves: list[Create | Move | Select | Call] = []
        touched: set[int] = set()
        for _ in range(max(1, steps // 3)):
            empty = sorted(set(positions) - occupied)
            if not empty or not occupied:
                break
            source = randomizer.choice(sorted(occupied))
            target = randomizer.choice(empty)
            moves.append(Move(Reference(source), Reference(target)))
            occupied.remove(source)
            occupied.add(target)
            touched.update((source, target))
        destructors.append(
            Action(f"destructor{index}", tuple(sorted(touched)), tuple(moves))
        )
    return Program(
        Action("caller", (0, 1, *positions), tuple(setup)), callee, tuple(destructors)
    )
