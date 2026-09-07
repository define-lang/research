from __future__ import annotations

import random
from typing import cast

import pytest

from define.compiler import driver
from operation_graph_optimization import (
    algorithm,
    order_variants,
    reference,
    state_workloads,
    validation,
)


def _enumerate_valid(state: state_workloads.State) -> set[state_workloads.Choice]:
    choices: set[state_workloads.Choice] = set()
    for position, value in state.positions.items():
        if value.particle is None:
            choices.add(state_workloads.Choice(destination=position))
        else:
            choices.add(state_workloads.Choice(source=position))
            for destination, other in state.positions.items():
                if other.particle is None and other.rank == value.rank:
                    choices.add(state_workloads.Choice(position, destination))
    return choices


def _check_all_choices(state: state_workloads.State):
    indexed: list[state_workloads.Choice] = []
    for kind, count in enumerate(state.counts()):
        indexed.extend(state.choice(kind, ticket) for ticket in range(count))
    assert len(indexed) == len(set(indexed))
    assert set(indexed) == _enumerate_valid(state)


def _render(
    width: int,
    depth: int,
    branching: int,
    statements: list[str],
    access: str,
) -> str:
    definitions: list[str] = []
    # Distinct constructor qualities make unequal ranks incompatible,
    # including leaves, so the fixture permits exactly same-rank Moves.
    for rank in range(depth + 1):
        definitions.extend(
            [
                f"define the potential action<my.domain.com:my_lib:/kind{rank}> {{",
                "    it happens when {",
                "        this particle is created.",
                "    } and it does {",
                "        define the position<temporary>.",
                "        create a particle in position<temporary>.",
                "        destroy the particle in position<temporary>.",
                "    }",
                "}",
            ]
        )

    def position_definition(name: str, rank: int, indentation: str):
        definitions.extend(
            [
                indentation + name + " {",
                indentation + "    it may only contain particles where {",
                indentation + f"        it has the action</kind{rank}>.",
            ]
        )
        if rank:
            for child in range(branching):
                definitions.append(
                    indentation + f"        it has the position</child{rank}_{child}>."
                )
        definitions.extend([indentation + "    }", indentation + "}"])

    for rank in range(1, depth + 1):
        for index in range(branching):
            position_definition(
                f"define the potential position<my.domain.com:my_lib:/child{rank}_{index}>",
                rank - 1,
                "",
            )
    if access == "implied":
        for rank in range(depth + 1):
            for index in range(width):
                position_definition(
                    f"define the potential position<my.domain.com:my_lib:/p{rank}_{index}>",
                    rank,
                    "",
                )
    definitions.append("define the potential action<my.domain.com:my_lib:/test> {")
    if access == "implied":
        for rank in range(depth + 1):
            for index in range(width):
                definitions.append(
                    f"    it also assigns the position</p{rank}_{index}>."
                )
    definitions.extend(
        [
            "    it happens when {",
            "        this particle is created.",
            "    } and it does {",
        ]
    )
    if access == "local":
        for rank in range(depth + 1):
            for index in range(width):
                position_definition(
                    f"define the position<p{rank}_{index}>", rank, "        "
                )
    definitions.extend("        " + statement for statement in statements)
    definitions.extend(["    }", "}"])
    return "\n".join(definitions) + "\n"


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("access", ["local", "implied"])
@pytest.mark.parametrize(
    "distribution", ["balanced", "concrete", "growth", "movement", "destruction"]
)
def test_every_available_choice_during_real_random_source(
    seed: int, distribution: str, access: str
):
    state = state_workloads.State(width=2, depth=3, branching=2, access=access)
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible source generation.
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    statements: list[str] = []
    operations = list(state.initial)
    groups: dict[int, int] = {}
    statement_at: dict[int, str] = {}
    for operation in state.initial:
        assert calculator.add(operation) == oracle.add(operation)

    def apply(choice: state_workloads.Choice):
        statements.append(state.statement(choice))
        statement_at[len(operations)] = statements[-1]
        batch = state.apply(choice)
        if choice.destination is None:
            if len(batch) > 1:
                groups[len(operations)] = len(batch)
            assert calculator.simultaneous(batch) == oracle.simultaneous(batch)
        else:
            for operation in batch:
                assert calculator.add(operation) == oracle.add(operation)
        operations.extend(batch)
        _check_all_choices(state)

    for _ in range(100):
        _check_all_choices(state)
        # Changing storage order must not remove any selectable operation.
        for pool in [*state.empty, *state.occupied]:
            randomizer.shuffle(pool.values)
            pool.indexes = {
                position: index for index, position in enumerate(pool.values)
            }
        _check_all_choices(state)
        apply(state.sample(randomizer, distribution))

    # This source-only epilogue exercises declarations and constraints that the
    # random region may never use; it is absent from performance workloads.
    top = [
        position for position, value in state.positions.items() if value.owner is None
    ]
    for position in top:
        if state.positions[position].particle is not None:
            apply(state_workloads.Choice(source=position))
    for position in top:
        pending = [position]
        while pending:
            current = pending.pop()
            apply(state_workloads.Choice(destination=current))
            particle = cast("int", state.positions[current].particle)
            pending.extend(state.particles[particle].children)
        apply(state_workloads.Choice(source=position))

    source = _render(2, 3, 2, statements, access)
    result = driver.Driver().validate_source(source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    actual = [
        set(calculator.graph.dependencies(index)) for index in range(len(operations))
    ]
    assert actual == oracle.dependencies
    for schedule_seed in range(3):
        validation.check_random_schedule(operations, calculator.graph, schedule_seed)

    reordered, reordered_groups, original = order_variants.reorder(
        operations, groups, seed + 100
    )
    reordered_calculator = algorithm.Calculator()
    occurrence = 0
    while occurrence < len(reordered):
        count = reordered_groups.get(occurrence, 1)
        _ = reordered_calculator.simultaneous(
            reordered[occurrence : occurrence + count]
        )
        occurrence += count
    for current, previous in enumerate(original):
        mapped = {
            original[dependency]
            for dependency in reordered_calculator.graph.dependencies(current)
        }
        assert mapped == oracle.dependencies[previous]
    validation.check_random_schedule(reordered, reordered_calculator.graph, seed + 101)
    # Constructor bodies remain in their action definitions; the list below
    # contains only the caller statements, including whole destruction groups.
    reordered_statements: list[str] = []
    for previous in original:
        if previous in statement_at:
            reordered_statements.append(statement_at[previous])
    result = (
        driver.Driver()
        .validate_source(_render(2, 3, 2, reordered_statements, access))
        .program_validation
    )
    assert result.all_exceptions == []
    assert result.all_diagnostics == []


def test_mixed_generator_batches_match_independent_graph():
    operations, groups = state_workloads.generate(17, 500, 3, 4, 2, "growth")
    assert groups
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    occurrence = 0
    while occurrence < len(operations):
        count = groups.get(occurrence, 1)
        batch = operations[occurrence : occurrence + count]
        assert calculator.simultaneous(batch) == oracle.simultaneous(batch)
        occurrence += count
    actual = [
        set(calculator.graph.dependencies(index)) for index in range(len(operations))
    ]
    assert actual == oracle.dependencies
    validation.check_random_schedule(operations, calculator.graph, 41)
