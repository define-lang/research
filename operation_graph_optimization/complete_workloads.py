"""Complete source workloads with the current automatic-destruction semantics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from operation_graph_optimization import algorithm, vanish_workloads

if TYPE_CHECKING:
    from operation_graph_optimization import workloads


def resolve_program(program: workloads.Program) -> list[vanish_workloads.Step]:
    """Include the automatic destruction recorded separately by source generators."""
    operations = list(program.operations)
    for vacate in program.simultaneous:
        # The archived position-only fixtures supplied parent Creates here, but
        # a transitive Vacate does not actually use its parent's qualities.
        operations.append(algorithm.Operation(empty=vacate.empty))
    return vanish_workloads.resolve(operations)
