"""Direct dependency selection for two opposite parent relationship periods."""

from __future__ import annotations

from typing import TYPE_CHECKING

from operation_graph_optimization.complete import algorithm

if TYPE_CHECKING:
    from operation_graph_optimization.complete import graph


def collect(
    dependencies: graph.Graph,
    earlier_beginning: int | None,
    earlier_ending: tuple[int, ...],
    later_beginning: int,
    later_ending: tuple[int, ...] | None,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Compare two source-ordered, nonoverlapping opposite relationships."""
    candidates = set(earlier_ending)
    candidates.difference_update(
        ending
        for ending in earlier_ending
        if dependencies.reaches(later_beginning, ending)
    )
    if not candidates:
        return ()
    forward = tuple(
        (ending, later_beginning)
        for ending in algorithm.compare(dependencies, candidates)
    )
    if (
        earlier_beginning is None
        or later_ending is None
        or any(
            ending == earlier_beginning
            or dependencies.reaches(ending, earlier_beginning)
            for ending in later_ending
        )
    ):
        return (forward,)
    reverse = tuple(
        (ending, earlier_beginning)
        for ending in algorithm.compare(dependencies, set(later_ending))
    )
    return (forward, reverse)
