"""Inputs and equivalence checks for removing selected transitive Vacates."""

from __future__ import annotations

import dataclasses
import random

from operation_graph_optimization import (
    algorithm as positions,
)
from operation_graph_optimization import (
    combination_inputs,
    complete_inputs,
    integrated_workloads,
    vanish_workloads,
)
from operation_graph_optimization.complete import algorithm as explicit
from operation_graph_optimization.transitive_destruction import algorithm, snapshot


@dataclasses.dataclass
class Scenario:
    """An existing-model execution with explicitly identified transitive selection."""

    steps: list[vanish_workloads.Step]
    transitive: set[int]
    retentions: dict[int, dict[int, int]] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Prepared:
    """Pre-resolved algorithm inputs, excluding generation from construction."""

    operations: list[algorithm.Operation]
    transitive: set[int]
    separate: set[int]
    retentions: dict[int, dict[int, int]]
    occurrences: dict[int, int]
    selections: dict[int, list[tuple[int, int]]]


def prepare(scenario: Scenario) -> Prepared:
    """Remove selected Vacates and reuse unchanged child-position information."""
    removed_positions: set[int] = set()
    for occurrence in scenario.transitive:
        position = scenario.steps[occurrence].operation.empty
        assert position is not None  # noqa: S101 - Inputs explicitly identify Vacates.
        removed_positions.add(position)
    aliases: dict[int, int] = {}
    retentions: dict[int, dict[int, int]] = {}
    occurrences: dict[int, int] = {}
    operations: list[algorithm.Operation] = []
    selections: dict[int, list[tuple[int, int]]] = {}
    for previous, step in enumerate(scenario.steps):
        retained: dict[int, int] = {}
        for ordinary, preserved in scenario.retentions.get(previous, {}).items():
            if ordinary in removed_positions:
                aliases[preserved] = ordinary
            else:
                retained[ordinary] = preserved
        if retained:
            retentions[len(operations)] = retained
        if previous in scenario.transitive:
            assert step.vacated is not None  # noqa: S101 - Selected Vacate.
            assert step.operation.empty is not None  # noqa: S101 - Selected position.
            selections.setdefault(len(operations), []).append(
                (occurrences[step.vacated], step.operation.empty)
            )
            continue
        occurrences[previous] = len(operations)
        operation = step.operation
        operations.append(
            algorithm.Operation(
                occupied=tuple(aliases.get(p, p) for p in operation.occupied),
                fill=aliases.get(operation.fill, operation.fill)
                if operation.fill is not None
                else None,
                empty=aliases.get(operation.empty, operation.empty)
                if operation.empty is not None
                else None,
                quality_particles=tuple(occurrences[p] for p in operation.creators),
                defines=operation.defines,
                ordinary_occupants=tuple(
                    occurrences[p] for p in step.ordinary_occupants
                ),
                moved=occurrences[step.moved] if step.moved is not None else None,
                vacated=occurrences[step.vacated] if step.vacated is not None else None,
            )
        )
    transitive: set[int] = set()
    for occurrence in scenario.transitive:
        particle = scenario.steps[occurrence].vacated
        assert particle is not None  # noqa: S101 - Selected occurrence is a Vacate.
        transitive.add(occurrences[particle])
    separate = {occurrences[p] for p in combination_inputs.classify(scenario.steps)}
    return Prepared(
        operations, transitive, separate, retentions, occurrences, selections
    )


def construct(prepared: Prepared) -> tuple[algorithm.Calculator, dict[int, int]]:
    """Build only the experimental graph from prepared requirements."""
    calculator = algorithm.Calculator(prepared.separate, prepared.transitive)
    for occurrence, operation in enumerate(prepared.operations):
        if occurrence in prepared.retentions:
            calculator.retain(prepared.retentions[occurrence])
        _ = calculator.add(operation)
    return calculator, calculator.finish()


def verify(scenario: Scenario, *, snapshot_selection: bool = False):
    """Compare exact projected dependencies, not only vertex or edge counts."""
    baseline = explicit.Calculator()
    for occurrence, step in enumerate(scenario.steps):
        if occurrence in scenario.retentions:
            baseline.retain(scenario.retentions[occurrence])
        assert baseline.add(complete_inputs.convert(step)) == occurrence  # noqa: S101
    baseline_vanishes = baseline.finish()
    prepared = prepare(scenario)
    candidate = (
        snapshot.Calculator(prepared.separate, prepared.transitive)
        if snapshot_selection
        else algorithm.Calculator(prepared.separate, prepared.transitive)
    )
    for occurrence, operation in enumerate(prepared.operations):
        if isinstance(candidate, snapshot.Calculator):
            for particle, position in prepared.selections.get(occurrence, []):
                candidate.select_transitively(particle, position)
        if occurrence in prepared.retentions:
            candidate.retain(prepared.retentions[occurrence])
        _ = candidate.add(operation)
    if isinstance(candidate, snapshot.Calculator):
        for particle, position in prepared.selections.get(len(prepared.operations), []):
            candidate.select_transitively(particle, position)
    candidate_vanishes = candidate.finish()
    assert set(candidate_vanishes) == {  # noqa: S101 - Independent research oracle.
        prepared.occurrences[p] for p in baseline_vanishes
    }
    for old, new in prepared.occurrences.items():
        expected = {prepared.occurrences[p] for p in baseline.graph.dependencies(old)}
        assert set(candidate.graph.dependencies(new)) == expected  # noqa: S101
    for particle, vanish in baseline_vanishes.items():
        pending = list(baseline.graph.dependencies(vanish))
        expected: set[int] = set()
        while pending:
            previous = pending.pop()
            if previous in scenario.transitive:
                pending.extend(baseline.graph.dependencies(previous))
            else:
                expected.add(previous)
        # This is an independent projection oracle, not an algorithm step.
        maximal = set(expected)
        for following in expected:
            for previous in expected:
                if baseline.graph.reaches(following, previous):
                    maximal.discard(previous)
        expected_new = {prepared.occurrences[p] for p in maximal}
        actual_vanish = candidate_vanishes[prepared.occurrences[particle]]
        if actual_vanish < len(prepared.operations):
            actual = {actual_vanish}
        else:
            actual = set(candidate.graph.dependencies(actual_vanish))
        assert actual == expected_new  # noqa: S101


def retained(seed: int, steps: int, width: int) -> Scenario:
    """Select child particles while destructor Moves share their original positions."""
    operations, retentions = integrated_workloads.retained(seed, steps, width)
    transitive: set[int] = set()
    for occurrence, step in enumerate(operations):
        if step.vacated is not None and step.vacated != 0:
            transitive.add(occurrence)
    return Scenario(operations, transitive, retentions)


def cascade(seed: int, steps: int, width: int, *, implied: bool) -> Scenario:
    """Randomize child creation and selection without changing particle identities."""
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible valid choices.
    operations: list[positions.Operation] = []
    transitive: set[int] = set()
    for batch in range(max(1, steps // (4 * width + 2))):
        parent = len(operations)
        start_position = 1 + batch * 2 * width
        children = list(range(start_position, start_position + width))
        operations.append(positions.Operation(fill=0, defines=tuple(children)))
        randomizer.shuffle(children)
        particles: dict[int, int] = {}
        for child in children:
            particles[child] = len(operations)
            operations.append(
                positions.Operation(
                    fill=child,
                    occupied=(0,),
                    creators=(parent,),
                    defines=(child + width,),
                )
            )
        randomizer.shuffle(children)
        for child in children:
            operations.append(
                positions.Operation(
                    fill=child + width,
                    occupied=() if implied else (0, child),
                    creators=(particles[child],)
                    if implied
                    else (parent, particles[child]),
                )
            )
        selected = [0, *children]
        selected.extend(child + width for child in children)
        randomizer.shuffle(selected)
        for position in selected:
            if position:
                transitive.add(len(operations))
            operations.append(positions.Operation(empty=position))
    return Scenario(vanish_workloads.resolve(operations), transitive)
