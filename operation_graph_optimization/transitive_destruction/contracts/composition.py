"""Local contract forwarding as dependency expressions rather than operations."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import collections.abc

    from operation_graph_optimization.transitive_destruction.contracts import (
        registration,
    )


@dataclasses.dataclass(frozen=True)
class Connection:
    """A local expression exporting completions without its own completion event."""

    name: str
    prerequisites: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Instruction:
    """A local operation with symbolic prerequisites."""

    name: str
    prerequisites: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Plan:
    """A reusable module that mentions only its own operations and imports."""

    imports: tuple[str, ...]
    statements: tuple[Instruction | Connection, ...]
    exports: tuple[str, ...]


def instantiate(
    execution: registration.Execution,
    plan: Plan,
    imported: dict[str, tuple[registration.Operation, ...]],
    actions: dict[str, collections.abc.Callable[[], None]],
    prefix: str,
) -> dict[str, tuple[registration.Operation, ...]]:
    """Substitute direct imports without inspecting any caller or callee graph."""
    values = {name: imported[name] for name in plan.imports}
    for statement in plan.statements:
        prerequisites: list[registration.Operation] = []
        for name in statement.prerequisites:
            prerequisites.extend(values[name])
        if isinstance(statement, Connection):
            # Forwarding does not publish work or wait for any completion.
            # Multiple imported paths can identify the same operation occurrence.
            values[statement.name] = tuple(dict.fromkeys(prerequisites))
        else:
            operation = execution.allocate(
                prefix + statement.name, actions[statement.name]
            )
            execution.connect(operation, tuple(prerequisites))
            execution.publish(operation)
            values[statement.name] = (operation,)
    return {name: values[name] for name in plan.exports}
