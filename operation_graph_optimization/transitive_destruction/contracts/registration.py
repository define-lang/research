"""Completion-aware operation registration without child readiness events."""

from __future__ import annotations

import dataclasses
import threading
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    import collections.abc


@dataclasses.dataclass(eq=False)
class Operation:
    """One execution occurrence, shared by aliases of its completion."""

    name: str
    action: collections.abc.Callable[[], None]
    prerequisites: set[Operation] = dataclasses.field(default_factory=set)
    consumers: list[Operation] = dataclasses.field(default_factory=list)
    remaining: int = 0
    published: bool = False
    completed: bool = False


@final
class Execution:
    """Serialize registration metadata, not the execution of operation bodies."""

    def __init__(self):
        """Keep publication distinct from prerequisite completion."""
        self.ready: list[Operation] = []
        self.operations: list[Operation] = []
        self.lock = threading.Lock()

    def allocate(
        self, name: str, action: collections.abc.Callable[[], None]
    ) -> Operation:
        """Allocate before publication so every required connection can be wired."""
        operation = Operation(name, action)
        with self.lock:
            self.operations.append(operation)
        return operation

    def connect(self, operation: Operation, prerequisites: tuple[Operation, ...]):
        """Subscribe atomically with observing each prerequisite's completion."""
        with self.lock:
            if operation.published:
                raise ValueError("Cannot add prerequisites after publication")
            for prerequisite in prerequisites:
                # Two imported connections can name the same execution occurrence.
                if prerequisite in operation.prerequisites:
                    continue
                operation.prerequisites.add(prerequisite)
                if not prerequisite.completed:
                    prerequisite.consumers.append(operation)
                    operation.remaining += 1

    def publish(self, operation: Operation):
        """Release an operation only after its complete prerequisite list is known."""
        with self.lock:
            if operation.published:
                raise ValueError("Operation is already published")
            operation.published = True
            if operation.remaining == 0:
                self.ready.append(operation)

    def complete(self, operation: Operation):
        """Deliver completion only to actual consumers, not an aggregate child hook."""
        with self.lock:
            if not operation.published or operation.remaining or operation.completed:
                raise ValueError("Operation cannot complete in its current state")
            operation.completed = True
            for consumer in operation.consumers:
                consumer.remaining -= 1
                if consumer.remaining == 0 and consumer.published:
                    self.ready.append(consumer)
            operation.consumers.clear()

    def take(self, index: int = 0) -> Operation:
        """Remove one runnable operation before executing it without the lock."""
        with self.lock:
            return self.ready.pop(index)


def dependencies(execution: Execution) -> dict[str, set[str]]:
    """Inspect registered dependencies without changing scheduling decisions."""
    result: dict[str, set[str]] = {}
    for operation in execution.operations:
        result[operation.name] = {p.name for p in operation.prerequisites}
    return result
