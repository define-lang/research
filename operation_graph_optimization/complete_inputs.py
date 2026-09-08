"""Adapt archived workloads to the standalone complete algorithm."""

from __future__ import annotations

from typing import TYPE_CHECKING

from operation_graph_optimization.complete import algorithm

if TYPE_CHECKING:
    from operation_graph_optimization import vanish_workloads


def convert(step: vanish_workloads.Step) -> algorithm.Operation:
    """Supply the resolved requirements shared by both collection rules."""
    operation = step.operation
    return algorithm.Operation(
        occupied=operation.occupied,
        fill=operation.fill,
        empty=operation.empty,
        quality_particles=operation.creators,
        defines=operation.defines,
        ordinary_occupants=step.ordinary_occupants,
        moved=step.moved,
        vacated=step.vacated,
    )
