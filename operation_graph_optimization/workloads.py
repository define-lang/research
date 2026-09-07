"""Valid occupancy workloads with corresponding generated Define source."""

from __future__ import annotations

import dataclasses
import random
from typing import TYPE_CHECKING, cast

from operation_graph_optimization import algorithm

if TYPE_CHECKING:
    import collections.abc


@dataclasses.dataclass(slots=True)
class Program:
    """Source statements and their resolved operation requirements."""

    source: str
    operations: list[algorithm.Operation]
    simultaneous: list[algorithm.Operation] = dataclasses.field(default_factory=list)


def random_program(seed: int, steps: int, positions: int = 8) -> Program:
    """Generate valid local Create, Move, and Destroy statements."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    lines = ["define the potential action<my.domain.com:my_lib:/test> {"]
    lines.extend(
        [
            "    it happens when {",
            "        this particle is created.",
            "    } and it does {",
        ]
    )
    operations: list[algorithm.Operation] = []
    occupied: list[int] = []
    empty = list(range(positions))
    for position in empty:
        lines.append(f"        define the position<p{position}>.")
        # Every declaration must be live regardless of the random choices.
        lines.append(f"        create a particle in position<p{position}>.")
        lines.append(f"        destroy the particle in position<p{position}>.")
        operations.extend(
            [
                algorithm.Operation(fill=position),
                algorithm.Operation(empty=position),
            ]
        )
    for _ in range(steps):
        choice = randomizer.randrange(3)
        if empty and (choice == 0 or not occupied):
            destination = empty.pop(randomizer.randrange(len(empty)))
            occupied.append(destination)
            lines.append(f"        create a particle in position<p{destination}>.")
            operations.append(algorithm.Operation(fill=destination))
        elif occupied and empty and choice == 1:
            source = occupied.pop(randomizer.randrange(len(occupied)))
            destination = empty.pop(randomizer.randrange(len(empty)))
            occupied.append(destination)
            empty.append(source)
            lines.append(
                f"        move the particle in position<p{source}> to position<p{destination}>."
            )
            operations.append(algorithm.Operation(fill=destination, empty=source))
        else:
            source = occupied.pop(randomizer.randrange(len(occupied)))
            empty.append(source)
            lines.append(f"        destroy the particle in position<p{source}>.")
            operations.append(algorithm.Operation(empty=source))
    for position in occupied:
        lines.append(f"        destroy the particle in position<p{position}>.")
        operations.append(algorithm.Operation(empty=position))
    lines.extend(["    }", "}"])
    return Program("\n".join(lines) + "\n", operations)


def interleaved_moves(
    seed: int, steps: int, width: int
) -> collections.abc.Iterator[algorithm.Operation]:
    """Interleave independent particles moving between two local positions."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    occupied = list(range(width))
    empty = list(range(width, 2 * width))
    for position in occupied:
        yield algorithm.Operation(fill=position)
    for _ in range(steps):
        particle = randomizer.randrange(width)
        source, destination = occupied[particle], empty[particle]
        yield algorithm.Operation(fill=destination, empty=source)
        occupied[particle], empty[particle] = destination, source
    randomizer.shuffle(occupied)
    for position in occupied:
        yield algorithm.Operation(empty=position)


def overlapping_moves(
    seed: int, steps: int, width: int
) -> collections.abc.Iterator[algorithm.Operation]:
    """Move particles to randomly chosen vacant local positions."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    occupied = list(range(width))
    empty = list(range(width, 2 * width))
    for position in occupied:
        yield algorithm.Operation(fill=position)
    for _ in range(steps):
        particle = randomizer.randrange(width)
        vacancy = randomizer.randrange(width)
        source, destination = occupied[particle], empty[vacancy]
        yield algorithm.Operation(fill=destination, empty=source)
        occupied[particle], empty[vacancy] = destination, source
    randomizer.shuffle(occupied)
    for position in occupied:
        yield algorithm.Operation(empty=position)


def preceding_uses(
    seed: int, steps: int, width: int
) -> collections.abc.Iterator[algorithm.Operation]:
    """Repeatedly fill and empty child positions through occupied parents."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    for parent in range(width):
        yield algorithm.Operation(fill=parent)
    for index in range(steps):
        parent = randomizer.randrange(width)
        child = width + index
        yield algorithm.Operation(occupied=(parent,), fill=child, creators=(parent,))
        yield algorithm.Operation(occupied=(parent,), empty=child, creators=(parent,))
    parents = list(range(width))
    randomizer.shuffle(parents)
    for parent in parents:
        yield algorithm.Operation(empty=parent)


def implied_uses(
    seed: int, steps: int, width: int
) -> collections.abc.Iterator[algorithm.Operation]:
    """Interleave direct implied accesses to positions defined by particles."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    for particle in range(width):
        yield algorithm.Operation(fill=particle, defines=(width + particle,))
    for _ in range(steps):
        particle = randomizer.randrange(width)
        position = width + particle
        yield algorithm.Operation(fill=position, creators=(particle,))
        yield algorithm.Operation(empty=position, creators=(particle,))
    for particle in range(width):
        yield algorithm.Operation(empty=particle)


def tree_program(seed: int, steps: int, depth: int = 4, width: int = 3) -> Program:
    """Move defining particles and operate through their current written chains."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    definitions: list[str] = []
    for level in reversed(range(depth)):
        if level == depth - 1:
            definitions.append(
                f"define the potential position<my.domain.com:my_lib:/child{level}>."
            )
        else:
            definitions.extend(
                [
                    f"define the potential position<my.domain.com:my_lib:/child{level}> {{",
                    "    it may only contain particles where {",
                    f"        it has the position</child{level + 1}>.",
                    "    }",
                    "}",
                ]
            )
    body = ["        define the position<scratch>."]
    operations: list[algorithm.Operation] = []
    occupied = list(range(width))
    empty = list(range(width, 2 * width))
    child_positions: list[tuple[int, ...]] = []
    creators: list[tuple[int, ...]] = []
    for position in range(2 * width):
        body.extend(
            [
                f"        define the position<p{position}> {{",
                "            it may only contain particles where {",
                "                it has the position</child0>.",
                "            }",
                "        }",
            ]
        )
    for particle in range(width):
        children = tuple(
            range(2 * width + particle * depth, 2 * width + (particle + 1) * depth)
        )
        child_positions.append(children)
        particle_creators = [len(operations)]
        operations.append(algorithm.Operation(fill=particle, defines=(children[0],)))
        chain = f"position<p{particle}>"
        body.append(f"        create a particle in {chain}.")
        parents = (particle,)
        for level, child in enumerate(children):
            chain += f"::position</child{level}>"
            body.append(f"        create a particle in {chain}.")
            defines = (children[level + 1],) if level + 1 < depth else ()
            operations.append(
                algorithm.Operation(
                    occupied=parents,
                    fill=child,
                    creators=tuple(particle_creators),
                    defines=defines,
                )
            )
            parents = (*parents, child)
            particle_creators.append(len(operations) - 1)
        creators.append(tuple(particle_creators[:-1]))
    scratch = 2 * width + width * depth
    # Each constrained destination needs a real child access, not merely a Move.
    choices = list(range(width))
    choices.extend(randomizer.randrange(width) for _ in range(steps))
    for particle in choices:
        source, destination = occupied[particle], empty[particle]
        body.append(
            f"        move the particle in position<p{source}> to position<p{destination}>."
        )
        operations.append(algorithm.Operation(empty=source, fill=destination))
        occupied[particle], empty[particle] = destination, source
        chain = f"position<p{destination}>"
        for level in range(depth):
            chain += f"::position</child{level}>"
        body.append(f"        move the particle in {chain} to position<scratch>.")
        body.append(f"        move the particle in position<scratch> to {chain}.")
        children = child_positions[particle]
        parents = (destination, *children[:-1])
        operations.extend(
            [
                algorithm.Operation(
                    occupied=parents,
                    empty=children[-1],
                    fill=scratch,
                    creators=creators[particle],
                ),
                algorithm.Operation(
                    occupied=parents,
                    empty=scratch,
                    fill=children[-1],
                    creators=creators[particle],
                ),
            ]
        )
    vacancies: list[algorithm.Operation] = []
    for particle, position in enumerate(occupied):
        vacancies.append(algorithm.Operation(empty=position))
        for level, child in enumerate(child_positions[particle]):
            vacancies.append(
                algorithm.Operation(empty=child, creators=(creators[particle][level],))
            )
    randomizer.shuffle(vacancies)
    lines = [
        *definitions,
        "define the potential action<my.domain.com:my_lib:/test> {",
        "    it happens when {",
        "        this particle is created.",
        "    } and it does {",
        *body,
        "    }",
        "}",
    ]
    return Program("\n".join(lines) + "\n", operations, vacancies)


def shared_parent(
    seed: int, steps: int, width: int
) -> collections.abc.Iterator[algorithm.Operation]:
    """Interleave long child-operation sequences after a defining-particle Move."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    yield algorithm.Operation(fill=0, defines=tuple(range(2, 2 + width)))
    for child in range(2, 2 + width):
        yield algorithm.Operation(occupied=(0,), fill=child, creators=(0,))
    yield algorithm.Operation(empty=0, fill=1)
    for index in range(width + steps):
        child = 2 + (index if index < width else randomizer.randrange(width))
        scratch = width + child
        yield algorithm.Operation(
            occupied=(1,), empty=child, fill=scratch, creators=(0,)
        )
        yield algorithm.Operation(
            occupied=(1,), empty=scratch, fill=child, creators=(0,)
        )
    for child in range(2, 2 + width):
        yield algorithm.Operation(occupied=(1,), empty=child, creators=(0,))
    yield algorithm.Operation(empty=1)


def multiple_shared_parents(
    seed: int, steps: int, width: int
) -> collections.abc.Iterator[algorithm.Operation]:
    """Interleave independent copies of the validated shared-parent pattern."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    for parent in range(width):
        first_position = 22 * parent
        creator = 12 * parent
        children = tuple(range(first_position + 2, first_position + 12))
        yield algorithm.Operation(fill=first_position, defines=children)
        for child in children:
            yield algorithm.Operation(
                occupied=(first_position,), fill=child, creators=(creator,)
            )
        yield algorithm.Operation(empty=first_position, fill=first_position + 1)
    for index in range(10 * width + steps):
        if index < 10 * width:
            parent, child_index = divmod(index, 10)
        else:
            parent = randomizer.randrange(width)
            child_index = randomizer.randrange(10)
        first_position = 22 * parent
        child = first_position + 2 + child_index
        scratch = child + 10
        yield algorithm.Operation(
            occupied=(first_position + 1,),
            empty=child,
            fill=scratch,
            creators=(12 * parent,),
        )
        yield algorithm.Operation(
            occupied=(first_position + 1,),
            empty=scratch,
            fill=child,
            creators=(12 * parent,),
        )
    for parent in range(width):
        first_position = 22 * parent
        for child in range(first_position + 2, first_position + 12):
            yield algorithm.Operation(
                occupied=(first_position + 1,), empty=child, creators=(12 * parent,)
            )
        yield algorithm.Operation(empty=first_position + 1)


def shared_program(seed: int, steps: int, width: int = 3) -> Program:
    """Render the shared-parent stress history as fully validated source."""
    definitions: list[str] = []
    for child in range(width):
        definitions.append(
            f"define the potential position<my.domain.com:my_lib:/child{child}>."
        )
    body: list[str] = []
    for parent in range(2):
        body.extend(
            [
                f"        define the position<p{parent}> {{",
                "            it may only contain particles where {",
            ]
        )
        for child in range(width):
            body.append(f"                it has the position</child{child}>.")
        body.extend(["            }", "        }"])
    for child in range(width):
        body.append(f"        define the position<scratch{child}>.")
    current_parent = 0
    operations = list(shared_parent(seed, steps, width))
    for operation in operations:
        names: dict[int, str] = {0: "position<p0>", 1: "position<p1>"}
        for child in range(width):
            names[child + 2] = f"position<p{current_parent}>::position</child{child}>"
            names[width + child + 2] = f"position<scratch{child}>"
        if operation.fill is not None and operation.empty is not None:
            source, destination = operation.empty, operation.fill
            body.append(
                f"        move the particle in {names[source]} to {names[destination]}."
            )
            if source == 0:
                current_parent = 1
        elif operation.fill is not None:
            body.append(f"        create a particle in {names[operation.fill]}.")
        else:
            position = cast("int", operation.empty)
            body.append(f"        destroy the particle in {names[position]}.")
    lines = [
        *definitions,
        "define the potential action<my.domain.com:my_lib:/test> {",
        "    it happens when {",
        "        this particle is created.",
        "    } and it does {",
        *body,
        "    }",
        "}",
    ]
    return Program("\n".join(lines) + "\n", operations)


def vacancy_reuse(
    seed: int, steps: int, width: int
) -> collections.abc.Iterator[algorithm.Operation]:
    """Reuse unrelated old vacancies while their former particles have later uses."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    for parent in range(width):
        defined = tuple(width + child for child in range(parent, steps, width))
        yield algorithm.Operation(fill=parent, defines=defined)
    children = list(range(steps))
    randomizer.shuffle(children)
    for child in children:
        parent = child % width
        position, scratch = width + child, width + steps + child
        yield algorithm.Operation(occupied=(parent,), fill=position, creators=(parent,))
        yield algorithm.Operation(
            occupied=(parent,), empty=position, fill=scratch, creators=(parent,)
        )
        yield algorithm.Operation(empty=scratch)
    source = width + 2 * steps
    yield algorithm.Operation(fill=source)
    randomizer.shuffle(children)
    previous_parent: int | None = None
    for child in children:
        parent = child % width
        required = (parent,)
        if previous_parent is not None and previous_parent != parent:
            required = (previous_parent, parent)
        destination = width + child
        yield algorithm.Operation(
            occupied=required, empty=source, fill=destination, creators=required
        )
        source = destination
        previous_parent = parent
    final_parent = (source - width) % width
    yield algorithm.Operation(
        occupied=(final_parent,), empty=source, creators=(final_parent,)
    )
    for parent in range(width):
        yield algorithm.Operation(empty=parent)


def long_vacancy_reuse(
    seed: int, steps: int, width: int
) -> collections.abc.Iterator[algorithm.Operation]:
    """Add long unrelated uses of the former particles before vacancy reuse."""
    for operation in vacancy_reuse(seed, steps, width):
        if (
            operation.empty is not None
            and operation.fill is None
            and width + steps <= operation.empty < width + 2 * steps
        ):
            alternate = operation.empty + 2 * steps + width
            for _ in range(32):
                yield algorithm.Operation(empty=operation.empty, fill=alternate)
                yield algorithm.Operation(empty=alternate, fill=operation.empty)
        yield operation


def shared_join(
    seed: int, steps: int, width: int
) -> collections.abc.Iterator[algorithm.Operation]:
    """Reuse implied positions independently of a common preceding parent Move."""
    destination, side, trigger = 3 * steps + 2, 3 * steps + 3, 3 * steps + 4
    main_start = 3 * steps + 1
    for index, operation in enumerate(vacancy_reuse(seed, steps, 1)):
        if index == 0:
            yield dataclasses.replace(
                operation, defines=(*operation.defines, side, trigger)
            )
        elif index < main_start:
            yield operation
        elif index == main_start:
            yield algorithm.Operation(empty=0, fill=destination)
            for _ in range(width):
                yield algorithm.Operation(
                    occupied=(destination,), fill=side, creators=(0,)
                )
                yield algorithm.Operation(
                    occupied=(destination,), empty=side, creators=(0,)
                )
            yield algorithm.Operation(
                occupied=(destination,), fill=trigger, creators=(0,)
            )
            yield algorithm.Operation(empty=trigger, creators=(0,))
            yield operation
        elif operation.empty == 0:
            yield algorithm.Operation(empty=destination)
        else:
            yield dataclasses.replace(operation, occupied=(), creators=(0,))


def joined_program(seed: int, steps: int = 10, width: int = 20) -> Program:
    """Render a caller's common dependency and independent implied-position action."""
    operations = list(shared_join(seed, steps, width))
    destination, side, trigger = 3 * steps + 2, 3 * steps + 3, 3 * steps + 4
    main = 2 * steps + 1
    names = {
        0: "position<source>",
        destination: "position<destination>",
        side: "position<destination>::position</side>",
        trigger: "position<destination>::action</reuse>::position<input>",
    }
    lines = ["define the potential position<my.domain.com:my_lib:/side>."]
    for child in range(steps):
        lines.append(
            f"define the potential position<my.domain.com:my_lib:/child{child}>."
        )
        names[1 + child] = f"position<source>::position</child{child}>"
        names[steps + 1 + child] = f"position<scratch{child}>"
    lines.append("define the potential action<my.domain.com:my_lib:/reuse> {")
    for child in range(steps):
        lines.append(f"    it also assigns the position</child{child}>.")
    lines.extend(
        [
            "    define the position<input>.",
            "    it happens when {",
            "        the position<input> has a particle.",
            "    } and it does {",
            "        destroy the particle in position<input>.",
            "        define the position<main>.",
            "        create a particle in position<main>.",
        ]
    )
    main_start = 3 * steps + 1 + 1 + 2 * width + 2
    for operation in operations[main_start + 1 : -1]:
        source = cast("int", operation.empty)
        source_name = (
            "position<main>" if source == main else f"position</child{source - 1}>"
        )
        if operation.fill is None:
            lines.append(f"        destroy the particle in {source_name}.")
        else:
            lines.append(
                f"        move the particle in {source_name} to position</child{operation.fill - 1}>."
            )
    lines.extend(
        [
            "    }",
            "}",
            "define the potential action<my.domain.com:my_lib:/test> {",
            "    it happens when {",
            "        this particle is created.",
            "    } and it does {",
            "        define the position<source> {",
            "            it may only contain particles where {",
        ]
    )
    for child in range(steps):
        lines.append(f"                it has the position</child{child}>.")
    lines.extend(
        [
            "                it has the position</side>.",
            "                it has the action</reuse>.",
            "            }",
            "        }",
            "        define the position<destination> {",
            "            it may only contain particles where {",
            "                it has the position</side>.",
            "                it has the action</reuse>.",
            "            }",
            "        }",
        ]
    )
    for child in range(steps):
        lines.append(f"        define the position<scratch{child}>.")
    for operation in operations[: main_start - 1]:
        if operation.fill is not None and operation.empty is not None:
            lines.append(
                f"        move the particle in {names[operation.empty]} to {names[operation.fill]}."
            )
        elif operation.fill is not None:
            lines.append(f"        create a particle in {names[operation.fill]}.")
        else:
            position = cast("int", operation.empty)
            lines.append(f"        destroy the particle in {names[position]}.")
    lines.extend(["    }", "}"])
    return Program("\n".join(lines) + "\n", operations)


def vacancy_program(seed: int, steps: int = 20, width: int = 2) -> Program:
    """Render the old-vacancy workload without treating compiler graphs as an oracle."""
    definitions: list[str] = []
    for child in range(steps):
        definitions.append(
            f"define the potential position<my.domain.com:my_lib:/child{child}>."
        )
    body: list[str] = []
    names: dict[int, str] = {}
    for parent in range(width):
        names[parent] = f"position<p{parent}>"
        body.extend(
            [
                f"        define the position<p{parent}> {{",
                "            it may only contain particles where {",
            ]
        )
        for child in range(parent, steps, width):
            body.append(f"                it has the position</child{child}>.")
            names[width + child] = f"position<p{parent}>::position</child{child}>"
        body.extend(["            }", "        }"])
    for child in range(steps):
        names[width + steps + child] = f"position<scratch{child}>"
        body.append(f"        define the position<scratch{child}>.")
    names[width + 2 * steps] = "position<main>"
    body.append("        define the position<main>.")
    operations = list(vacancy_reuse(seed, steps, width))
    for operation in operations:
        if operation.fill is not None and operation.empty is not None:
            body.append(
                f"        move the particle in {names[operation.empty]} to {names[operation.fill]}."
            )
        elif operation.fill is not None:
            body.append(f"        create a particle in {names[operation.fill]}.")
        else:
            position = cast("int", operation.empty)
            body.append(f"        destroy the particle in {names[position]}.")
    lines = [
        *definitions,
        "define the potential action<my.domain.com:my_lib:/test> {",
        "    it happens when {",
        "        this particle is created.",
        "    } and it does {",
        *body,
        "    }",
        "}",
    ]
    return Program("\n".join(lines) + "\n", operations)


def simultaneous_destruction(
    seed: int, steps: int, width: int
) -> tuple[list[algorithm.Operation], list[algorithm.Operation]]:
    """Create occupied child positions, then select every particle together."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible workloads.
    operations: list[algorithm.Operation] = []
    vacancies: list[algorithm.Operation] = []
    for parent in range(width):
        defined = tuple(width + child for child in range(parent, steps, width))
        operations.append(algorithm.Operation(fill=parent, defines=defined))
        vacancies.append(algorithm.Operation(empty=parent))
    children = list(range(steps))
    randomizer.shuffle(children)
    for child in children:
        parent = child % width
        operations.append(
            algorithm.Operation(
                occupied=(parent,), fill=width + child, creators=(parent,)
            )
        )
        vacancies.append(algorithm.Operation(empty=width + child, creators=(parent,)))
    randomizer.shuffle(vacancies)
    return operations, vacancies


def destruction_program(seed: int, steps: int = 20, width: int = 2) -> Program:
    """Render the simultaneous selection as ordinary local automatic destruction."""
    lines: list[str] = []
    for child in range(steps):
        lines.append(
            f"define the potential position<my.domain.com:my_lib:/child{child}>."
        )
    lines.extend(
        [
            "define the potential action<my.domain.com:my_lib:/test> {",
            "    it happens when {",
            "        this particle is created.",
            "    } and it does {",
        ]
    )
    for parent in range(width):
        lines.extend(
            [
                f"        define the position<p{parent}> {{",
                "            it may only contain particles where {",
            ]
        )
        for child in range(parent, steps, width):
            lines.append(f"                it has the position</child{child}>.")
        lines.extend(["            }", "        }"])
    operations, vacancies = simultaneous_destruction(seed, steps, width)
    for operation in operations:
        position = cast("int", operation.fill)
        if position < width:
            lines.append(f"        create a particle in position<p{position}>.")
        else:
            child = position - width
            parent = child % width
            lines.append(
                f"        create a particle in position<p{parent}>::position</child{child}>."
            )
    lines.extend(["    }", "}"])
    return Program("\n".join(lines) + "\n", operations, vacancies)
