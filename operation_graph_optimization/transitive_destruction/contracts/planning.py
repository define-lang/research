"""Static, reusable action plans with dependency connections rather than hooks."""

from __future__ import annotations

import concurrent.futures
import dataclasses
import random
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    import collections.abc


@dataclasses.dataclass(frozen=True)
class Operation:
    """A local operation and its already-derived symbolic dependencies."""

    name: str
    dependencies: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Instruction:
    """Integer references resolved before runtime instance construction."""

    name: str
    dependencies: tuple[int, ...]


@dataclasses.dataclass(frozen=True)
class Plan:
    """Reusable local instructions; callers supply only the imported connections."""

    inputs: tuple[str, ...]
    instructions: tuple[Instruction, ...]
    exports: tuple[int, ...]


def compile_plan(
    inputs: tuple[str, ...], operations: tuple[Operation, ...], exports: tuple[str, ...]
) -> Plan:
    """Resolve local names without seeing any caller or complete program graph."""
    indices = {name: index for index, name in enumerate(inputs)}
    instructions: list[Instruction] = []
    for operation in operations:
        dependencies = tuple(indices[name] for name in operation.dependencies)
        indices[operation.name] = len(indices)
        instructions.append(Instruction(operation.name, dependencies))
    return Plan(inputs, tuple(instructions), tuple(indices[name] for name in exports))


@dataclasses.dataclass(eq=False)
class Task:
    """One actual operation, not a connection or destruction-selection callback."""

    name: str
    remaining: int
    action: collections.abc.Callable[[], None]
    dependents: list[Task] = dataclasses.field(default_factory=list)


def instantiate(
    plan: Plan,
    inputs: tuple[tuple[Task, ...], ...],
    prefix: str,
    actions: dict[str, collections.abc.Callable[[], None]],
    tasks: list[Task],
) -> tuple[tuple[Task, ...], ...]:
    """Wire the statically specified edges before publishing runnable operations."""
    connections = list(inputs)
    for instruction in plan.instructions:
        predecessors: list[Task] = []
        for index in instruction.dependencies:
            predecessors.extend(connections[index])
        task = Task(
            prefix + instruction.name, len(predecessors), actions[instruction.name]
        )
        for predecessor in predecessors:
            predecessor.dependents.append(task)
        tasks.append(task)
        connections.append((task,))
    return tuple(connections[index] for index in plan.exports)


@final
class Execution:
    """Run dependency counters; no lookup, reachability, or minimization at runtime."""

    def __init__(self, tasks: list[Task]):
        """Prepare an execution after all dependency connections exist."""
        self.ready = [task for task in tasks if task.remaining == 0]
        self.finished: list[str] = []
        self.count = len(tasks)

    def complete(self, task: Task):
        """Publish one operation to precisely its statically connected consumers."""
        self.finished.append(task.name)
        for dependent in task.dependents:
            dependent.remaining -= 1
            if dependent.remaining == 0:
                self.ready.append(dependent)

    def run(self, seed: int) -> list[str]:
        """Choose progressively among runnable operations for schedule exploration."""
        randomizer = random.Random(seed)  # noqa: S311 - Reproducible schedules.
        while self.ready:
            index = randomizer.randrange(len(self.ready))
            task = self.ready[index]
            self.ready[index] = self.ready[-1]
            _ = self.ready.pop()
            task.action()
            self.complete(task)
        if len(self.finished) != self.count:
            raise ValueError("Execution has unfinished operations")
        return self.finished

    def run_threaded(self, workers: int = 4) -> list[str]:
        """Execute independent operation bodies concurrently on real worker threads."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            pending: dict[concurrent.futures.Future[None], Task] = {}
            while self.ready or pending:
                for task in self.ready:
                    pending[executor.submit(task.action)] = task
                self.ready.clear()
                completed, _ = concurrent.futures.wait(
                    pending, return_when=concurrent.futures.FIRST_COMPLETED
                )
                for future in completed:
                    future.result()
                    self.complete(pending.pop(future))
        if len(self.finished) != self.count:
            raise ValueError("Execution has unfinished operations")
        return self.finished


def edges(tasks: list[Task]) -> dict[str, set[str]]:
    """Inspect actual runtime connections for validation, never for scheduling."""
    result: dict[str, set[str]] = {task.name: set() for task in tasks}
    for predecessor in tasks:
        for dependent in predecessor.dependents:
            result[dependent.name].add(predecessor.name)
    return result
