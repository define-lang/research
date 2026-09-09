"""Compare complete graph construction under cumulative simplifications."""

from __future__ import annotations

import dataclasses
import hashlib
import struct
from typing import TYPE_CHECKING

from operation_graph_optimization import (
    combination_algorithm,
    combination_inputs,
    complete_inputs,
    complete_workloads,
    integrated_workloads,
    simplification_broad,
    simplification_broad_ordered,
    simplification_collection,
    simplification_collection_pruned,
    simplification_no_pruning,
    simplification_ordered,
    simplification_simple,
    simplification_unpruned,
    vanish_workloads,
    workloads,
)
from operation_graph_optimization.complete import algorithm

if TYPE_CHECKING:
    from operation_graph_optimization.complete import graph


VARIANTS = (
    "early",
    "separate",
    "broad",
    "unpruned",
    "collection",
    "ordered",
    "simple",
    "no_pruning",
    "broad_ordered",
    "collection_pruned",
)
FAMILIES = (
    "local",
    "movement",
    "implied",
    "written",
    "wide",
    "state",
    "growth_closed",
    "retained",
    "deep6",
    "deep20",
)


@dataclasses.dataclass
class Prepared:
    """Keep generation and requirement resolution outside measured construction."""

    steps: list[vanish_workloads.Step]
    operations: list[algorithm.Operation]
    combined: list[combination_algorithm.Operation]
    retentions: dict[int, dict[int, int]]


def prepare(family: str, seed: int, count: int, width: int) -> Prepared:
    """Reuse the archived valid-operation and source generators."""
    retentions: dict[int, dict[int, int]] = {}
    if family == "retained":
        steps, retentions = integrated_workloads.retained(seed, count, width)
    elif family in {"deep6", "deep20"}:
        depth = 6 if family == "deep6" else 20
        program = workloads.tree_program(seed, max(1, count // 4), depth, width)
        steps = complete_workloads.resolve_program(program)
    else:
        steps = vanish_workloads.generate(family, seed, count, width)
    return Prepared(
        steps,
        [complete_inputs.convert(step) for step in steps],
        [combination_inputs.convert(step) for step in steps],
        retentions,
    )


def construct(variant: str, prepared: Prepared) -> tuple[graph.Graph, dict[int, int]]:
    """Include classification, retained-state copying, and Vanish completion."""
    if variant == "early":
        early = combination_algorithm.Calculator(
            combination_inputs.classify(prepared.steps)
        )
        for occurrence, operation in enumerate(prepared.combined):
            if occurrence in prepared.retentions:
                early.retain(prepared.retentions[occurrence])
            _ = early.add(operation)
        return early.graph, early.finish()
    classes = {
        "separate": algorithm.Calculator,
        "broad": simplification_broad.Calculator,
        "unpruned": simplification_unpruned.Calculator,
        "collection": simplification_collection.Calculator,
        "collection_pruned": simplification_collection_pruned.Calculator,
        "ordered": simplification_ordered.Calculator,
        "simple": simplification_simple.Calculator,
        "no_pruning": simplification_no_pruning.Calculator,
        "broad_ordered": simplification_broad_ordered.Calculator,
    }
    calculator = classes[variant]()
    for occurrence, operation in enumerate(prepared.operations):
        if occurrence in prepared.retentions:
            calculator.retain(prepared.retentions[occurrence])
        _ = calculator.add(operation)
    return calculator.graph, calculator.finish()


def fingerprint(calculated: graph.Graph, vanishes: dict[int, int], count: int) -> str:
    """Expand combined Vanish identities only for comparison with separate nodes."""
    digest = hashlib.sha256()
    for occurrence in range(count):
        dependencies = sorted(calculated.dependencies(occurrence))
        digest.update(struct.pack("<Q", len(dependencies)))
        for dependency in dependencies:
            digest.update(struct.pack("<Q", dependency))
    for particle, occurrence in sorted(vanishes.items()):
        dependencies = (
            [occurrence]
            if occurrence < count
            else sorted(calculated.dependencies(occurrence))
        )
        digest.update(struct.pack("<QQ", particle, len(dependencies)))
        for dependency in dependencies:
            digest.update(struct.pack("<Q", dependency))
    return digest.hexdigest()
