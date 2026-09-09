from __future__ import annotations

import concurrent.futures
import functools
import random
import threading

import pytest

from define.compiler import driver
from operation_graph_optimization.transitive_destruction.contracts import (
    cases,
    composition,
    registration,
)


def noop():
    pass


def finish(execution: registration.Execution, index: int = 0):
    operation = execution.take(index)
    operation.action()
    execution.complete(operation)


def ancestors(dependencies: dict[str, set[str]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for name, predecessors in dependencies.items():
        previous = set(predecessors)
        for predecessor in predecessors:
            previous.update(result[predecessor])
        result[name] = previous
    return result


@pytest.mark.parametrize("seed", range(80))
def test_arbitrary_dependency_composition_without_scheduled_connections(seed: int):
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible graph exploration.
    # This tests composition for general dependency graphs, not Define validity.
    size = 96
    ordinary: dict[str, set[str]] = {}
    for index in range(size):
        previous = list(ordinary)
        chosen = randomizer.sample(
            previous, min(len(previous), randomizer.randrange(6))
        )
        ordinary[f"operation{index}"] = set(chosen)
    selected: dict[str, set[str]] = {}
    for index in range(12):
        selected[f"selection{index}"] = set(randomizer.sample(list(ordinary), 4))
    terminals: dict[str, set[str]] = {}
    for index in range(12):
        terminals[f"vanish{index}"] = {
            f"selection{index}",
            *randomizer.sample(list(ordinary), 4),
        }
    explicit = ordinary | selected | terminals
    relation = ancestors(explicit)
    projected: dict[str, set[str]] = {}
    for name, previous in relation.items():
        if name not in selected:
            projected[name] = previous - selected.keys()

    execution = registration.Execution()
    exported: dict[str, tuple[registration.Operation, ...]] = {}
    items = list(explicit.items())
    while items:
        count = randomizer.randrange(1, 10)
        batch, items = items[:count], items[count:]
        local = {name for name, _ in batch}
        imported: set[str] = set()
        statements: list[composition.Instruction | composition.Connection] = []
        for name, previous in batch:
            imported.update(previous - local)
            if name in selected:
                statements.append(composition.Connection(name, tuple(previous)))
            else:
                statements.append(composition.Instruction(name, tuple(previous)))
        plan = composition.Plan(tuple(imported), tuple(statements), tuple(local))
        actions = dict.fromkeys(local, noop)
        exported.update(composition.instantiate(execution, plan, exported, actions, ""))
        # Registration can happen after completion, rather than only before run().
        for _ in range(randomizer.randrange(len(execution.ready) + 1)):
            if execution.ready:
                finish(execution, randomizer.randrange(len(execution.ready)))
    assert ancestors(registration.dependencies(execution)) == projected
    assert len(execution.operations) == size + len(terminals)
    while execution.ready:
        completed = {op.name for op in execution.operations if op.completed}
        allowed: set[str] = set()
        for name, required in projected.items():
            if name not in completed and required <= completed:
                allowed.add(name)
        assert {op.name for op in execution.ready} == allowed
        finish(execution, randomizer.randrange(len(execution.ready)))
    assert all(op.completed for op in execution.operations)


@pytest.mark.parametrize("seed", range(24))
def test_source_plans_with_forwarded_and_late_registered_consumers(seed: int):
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible registration order.
    width = 1 + seed % 8
    active = tuple(range(seed % width, width))
    case = cases.make_case(width, active)
    validated = driver.Driver().validate_source(case.source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    plans = cases.compile_caller(case, cases.callee_plan(width))
    state = cases.State()
    execution = registration.Execution()
    names: dict[str, tuple[registration.Operation, ...]] = {}
    local_plans = [plans.prefix, plans.callee]
    local_plans.extend(plans.destructors)
    local_plans.append(plans.lifetime)
    completions: dict[str, tuple[registration.Operation, ...]] = {}
    for number, original in enumerate(local_plans):
        imported: dict[str, tuple[registration.Operation, ...]] = {}
        if original is plans.callee:
            imported = dict.fromkeys(original.inputs, names["call"])
        elif original is plans.lifetime:
            imported = completions
        elif number >= 2:
            branch = active[number - 2]
            imported = {"ready": names[f"callee_back{branch}"]}
        forward = composition.Plan(
            original.inputs,
            tuple(
                composition.Connection(f"forward_{name}", (name, name))
                for name in original.inputs
            ),
            tuple(f"forward_{name}" for name in original.inputs),
        )
        for _ in range(seed % 21):
            forwarded = composition.instantiate(execution, forward, imported, {}, "")
            imported = {name: forwarded[f"forward_{name}"] for name in original.inputs}
            assert all(len(values) == 1 for values in imported.values())
        symbols = list(original.inputs)
        statements: list[composition.Instruction | composition.Connection] = []
        for instruction in original.instructions:
            predecessors = tuple(symbols[index] for index in instruction.dependencies)
            statements.append(composition.Instruction(instruction.name, predecessors))
            symbols.append(instruction.name)
        plan = composition.Plan(
            original.inputs, tuple(statements), tuple(symbols[len(original.inputs) :])
        )
        actions = {
            name: functools.partial(state.apply, case.effects[name])
            for name in plan.exports
        }
        names.update(composition.instantiate(execution, plan, imported, actions, ""))
        if original is plans.callee:
            completions = {f"ready{i}": names[f"callee_back{i}"] for i in range(width)}
        elif number >= 2 and original is not plans.lifetime:
            branch = active[number - 2]
            completions[f"ready{branch}"] = names[f"destructor_back{branch}"]
        for _ in range(randomizer.randrange(len(execution.ready) + 1)):
            if execution.ready:
                finish(execution, randomizer.randrange(len(execution.ready)))
    assert registration.dependencies(execution) == cases.expected(case)
    while execution.ready:
        finish(execution, randomizer.randrange(len(execution.ready)))
    assert all(op.completed for op in execution.operations)
    assert state.alive == {0}


@pytest.mark.parametrize("seed", range(40))
def test_completion_and_registration_race_has_no_lost_arrival(seed: int):
    execution = registration.Execution()
    producer = execution.allocate("producer", noop)
    execution.publish(producer)
    assert execution.take() is producer
    consumer = execution.allocate("consumer", noop)
    start = threading.Barrier(2)

    def register():
        _ = start.wait()
        execution.connect(consumer, (producer, producer))
        execution.publish(consumer)

    def complete():
        _ = start.wait()
        execution.complete(producer)

    functions = [register, complete] if seed % 2 else [complete, register]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        pending = [executor.submit(function) for function in functions]
        for future in pending:
            future.result()
    assert execution.ready == [consumer]
    assert consumer.prerequisites == {producer}
    finish(execution)
    assert consumer.completed


def test_connections_do_not_automatically_preserve_transitive_minimality():
    execution = registration.Execution()
    plan = composition.Plan(
        (),
        (
            composition.Instruction("a", ()),
            composition.Instruction("b", ("a",)),
            composition.Connection("child_selection", ("a",)),
            composition.Instruction("vanish", ("child_selection", "b")),
        ),
        ("vanish",),
    )
    _ = composition.instantiate(
        execution, plan, {}, dict.fromkeys(("a", "b", "vanish"), noop), ""
    )
    actual = registration.dependencies(execution)
    assert actual == {"a": set(), "b": {"a"}, "vanish": {"a", "b"}}
    assert ancestors(actual) == ancestors({"a": set(), "b": {"a"}, "vanish": {"b"}})


def test_same_callee_accepts_aliased_ordered_and_independent_imports():
    callee = composition.Plan(
        ("first", "second"),
        (composition.Instruction("use", ("first", "second")),),
        ("use",),
    )
    for relationship in ("alias", "ordered", "independent", "multiple"):
        execution = registration.Execution()
        first = execution.allocate("a", noop)
        second = execution.allocate("b", noop)
        if relationship == "ordered":
            execution.connect(second, (first,))
        execution.publish(first)
        execution.publish(second)
        supplied: dict[str, tuple[registration.Operation, ...]] = {
            "first": (first,),
            "second": (first,) if relationship == "alias" else (second,),
        }
        if relationship == "multiple":
            supplied["first"] = (first, second)
        result = composition.instantiate(execution, callee, supplied, {"use": noop}, "")
        consumer = result["use"][0]
        assert consumer.prerequisites == (
            {first} if relationship == "alias" else {first, second}
        )
        finish(execution)
        assert (consumer in execution.ready) is (relationship == "alias")
        while execution.ready:
            finish(execution)
        assert consumer.completed
    assert callee == composition.Plan(
        ("first", "second"),
        (composition.Instruction("use", ("first", "second")),),
        ("use",),
    )


def test_publishing_before_contract_resolution_cannot_be_repaired_later():
    execution = registration.Execution()
    vanish = execution.allocate("vanish", noop)
    execution.publish(vanish)
    finish(execution)
    destructor = execution.allocate("destructor", noop)
    with pytest.raises(ValueError, match="after publication"):
        execution.connect(vanish, (destructor,))


def test_late_setup_can_delay_work_even_with_completion_aware_registration():
    execution = registration.Execution()
    predecessor = execution.allocate("predecessor", noop)
    execution.publish(predecessor)
    finish(execution)
    # The operation is logically runnable, but late setup has not published it.
    destructor = execution.allocate("destructor", noop)
    execution.connect(destructor, (predecessor,))
    assert execution.ready == []
    assert destructor.remaining == 0
    execution.publish(destructor)
    assert execution.ready == [destructor]
