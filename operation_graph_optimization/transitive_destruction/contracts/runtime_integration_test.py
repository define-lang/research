from __future__ import annotations

import random
import threading

import pytest

from define.compiler import driver
from operation_graph_optimization.transitive_destruction.contracts import (
    cases,
    planning,
)


@pytest.mark.parametrize("width", [1, 2, 8])
@pytest.mark.parametrize("depth", [0, 1, 20])
@pytest.mark.parametrize("mode", ["none", "first", "all"])
def test_source_and_modular_runtime_edges(width: int, depth: int, mode: str):
    active = () if mode == "none" else (0,) if mode == "first" else tuple(range(width))
    case = cases.make_case(width, active)
    validated = driver.Driver().validate_source(case.source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    callee = cases.callee_plan(width)
    plans = cases.compile_caller(case, callee)
    tasks, state = cases.assemble(case, plans, depth=depth)
    assert plans.callee is callee
    assert planning.edges(tasks) == cases.expected(case)
    assert len(tasks) == len(cases.expected(case))
    _ = planning.Execution(tasks).run(17)
    assert state.alive == {0}


@pytest.mark.parametrize("seed", range(40))
def test_every_runtime_ready_set_matches_exact_dependencies(seed: int):
    case = cases.make_case(2, (0, 1))
    expected = cases.expected(case)
    plans = cases.compile_caller(case, cases.callee_plan(2))
    tasks, state = cases.assemble(case, plans, depth=5)
    execution = planning.Execution(tasks)
    completed: set[str] = set()
    randomizer = random.Random(seed)  # noqa: S311 - Reproducible schedules.
    while execution.ready:
        allowed: set[str] = set()
        for name, prerequisites in expected.items():
            if name not in completed and prerequisites <= completed:
                allowed.add(name)
        assert {task.name for task in execution.ready} == allowed
        index = randomizer.randrange(len(execution.ready))
        task = execution.ready.pop(index)
        task.action()
        execution.complete(task)
        completed.add(task.name)
    assert completed == set(expected)
    assert state.alive == {0}


def test_shared_child_hook_removes_permitted_runtime_order():
    case = cases.make_case(2, (0, 1))
    callee = cases.callee_plan(2)
    for shared_hook in (False, True):
        plans = cases.compile_caller(case, callee, shared_hook=shared_hook)
        tasks, _ = cases.assemble(case, plans)
        execution = planning.Execution(tasks)
        # Hold one callee branch while allowing every other runnable operation.
        while True:
            available = [task for task in execution.ready if task.name != "callee_out1"]
            if not available:
                break
            task = available[0]
            execution.ready.remove(task)
            task.action()
            execution.complete(task)
        assert ("destructor_back0" in execution.finished) is not shared_hook
        assert "vacate_parent" not in execution.finished
        _ = execution.run(7)


def test_real_threads_do_not_wait_for_a_shared_child_or_parent_event():
    case = cases.make_case(2, (0, 1))
    plans = cases.compile_caller(case, cases.callee_plan(2))
    tasks, state = cases.assemble(case, plans)
    indexed = {task.name: task for task in tasks}
    other_destructor_finished = threading.Event()
    original_callee = indexed["callee_out1"].action
    original_destructor = indexed["destructor_back0"].action

    def delayed_branch():
        assert other_destructor_finished.wait(timeout=5)
        original_callee()

    def independent_destructor():
        original_destructor()
        other_destructor_finished.set()

    indexed["callee_out1"].action = delayed_branch
    indexed["destructor_back0"].action = independent_destructor
    _ = planning.Execution(tasks).run_threaded()
    assert state.alive == {0}


def test_repeated_callers_share_code_not_runtime_connections():
    callee = cases.callee_plan(2)
    tasks: list[planning.Task] = []
    states: list[cases.State] = []
    expected: dict[str, set[str]] = {}
    for occurrence in range(12):
        case = cases.make_case(2, (occurrence % 2,))
        plans = cases.compile_caller(case, callee)
        prefix = f"call{occurrence}."
        local, state = cases.assemble(case, plans, depth=12, prefix=prefix)
        tasks.extend(local)
        states.append(state)
        for name, dependencies in cases.expected(case).items():
            expected[prefix + name] = {
                prefix + predecessor for predecessor in dependencies
            }
        assert plans.callee is callee
    assert planning.edges(tasks) == expected
    _ = planning.Execution(tasks).run(91)
    assert [state.alive for state in states] == [{0}] * 12
