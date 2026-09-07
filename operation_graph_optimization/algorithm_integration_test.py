from __future__ import annotations

import dataclasses
import itertools
import random
from typing import TYPE_CHECKING

import pytest

from define.compiler import driver
from operation_graph_optimization import (
    algorithm,
    graph,
    reference,
    validation,
    workloads,
)

if TYPE_CHECKING:
    import collections.abc


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("cache_targets", [0, 1, 8])
def test_random_source(seed: int, cache_targets: int):
    program = workloads.random_program(seed, 80)
    result = driver.Driver().validate_source(program.source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator(cache_targets)
    oracle = reference.Reference()
    for operation in program.operations:
        occurrence = calculator.add(operation)
        assert oracle.add(operation) == occurrence
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
    validation.check_random_schedule(program.operations, calculator.graph, seed + 11)


@pytest.mark.parametrize(
    ("generate", "width"),
    [
        (workloads.random_program, 8),
        (workloads.tree_program, 12),
        (workloads.joined_program, 96),
    ],
)
@pytest.mark.parametrize(
    ("pruning", "supplier_search", "pairwise_comparison"),
    [(0, 0, 2), (4, 4, 32), (16, 16, 64), (1_000_000, 1_000_000, 1_000_000)],
)
def test_threshold_choices_preserve_source_dependencies(
    generate: collections.abc.Callable[[int, int, int], workloads.Program],
    width: int,
    pruning: int,
    supplier_search: int,
    pairwise_comparison: int,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(algorithm, "MAX_PRUNING_CANDIDATES", pruning)
    monkeypatch.setattr(algorithm, "MAX_SUPPLIER_SEARCH_CANDIDATES", supplier_search)
    monkeypatch.setattr(
        algorithm, "MAX_PAIRWISE_COMPARISON_CANDIDATES", pairwise_comparison
    )
    program = generate(17, 32, width)
    result = driver.Driver().validate_source(program.source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    for operation in program.operations:
        occurrence = calculator.add(operation)
        assert oracle.add(operation) == occurrence
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
    validation.check_random_schedule(program.operations, calculator.graph, 29)


@pytest.mark.parametrize(
    "generate",
    [
        workloads.interleaved_moves,
        workloads.overlapping_moves,
        workloads.preceding_uses,
        workloads.implied_uses,
        workloads.shared_parent,
        workloads.multiple_shared_parents,
        workloads.vacancy_reuse,
        workloads.shared_join,
    ],
)
@pytest.mark.parametrize("cache_targets", [0, 1, 8])
def test_large_and_small_generated_histories(
    generate: collections.abc.Callable[
        [int, int, int], collections.abc.Iterator[algorithm.Operation]
    ],
    cache_targets: int,
):
    calculator = algorithm.Calculator(cache_targets)
    oracle = reference.Reference()
    for operation in generate(17, 250, 12):
        occurrence = calculator.add(operation)
        assert oracle.add(operation) == occurrence
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )


def test_every_small_schedule_preserves_occupancy_and_each_edge_is_needed():
    program = workloads.random_program(7, 2, positions=2)
    calculator = algorithm.Calculator()
    for operation in program.operations:
        _ = calculator.add(operation)
    dependencies = [
        set(calculator.graph.dependencies(index))
        for index in range(len(program.operations))
    ]
    necessary: set[tuple[int, int]] = set()
    serial_state: dict[int, int] = {}
    selected: list[int] = []
    for occurrence, operation in enumerate(program.operations):
        particle = (
            serial_state[operation.empty] if operation.empty is not None else occurrence
        )
        selected.append(particle)
        if operation.empty is not None:
            del serial_state[operation.empty]
        if operation.fill is not None:
            serial_state[operation.fill] = particle
    for schedule in itertools.permutations(range(len(program.operations))):
        completed: set[int] = set()
        state: dict[int, int] = {}
        violations: set[tuple[int, int]] = set()
        valid = True
        for occurrence in schedule:
            for dependency in dependencies[occurrence] - completed:
                violations.add((occurrence, dependency))
            operation = program.operations[occurrence]
            if operation.fill is not None:
                if operation.fill in state:
                    valid = False
                state[operation.fill] = selected[occurrence]
            if operation.empty is not None:
                if state.get(operation.empty) != selected[occurrence]:
                    valid = False
                _ = state.pop(operation.empty, None)
            completed.add(occurrence)
        if not violations:
            assert valid
        if not valid and len(violations) == 1:
            necessary.update(violations)
    all_edges: set[tuple[int, int]] = set()
    for occurrence, previous in enumerate(dependencies):
        for dependency in previous:
            all_edges.add((occurrence, dependency))
    assert necessary == all_edges


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("depth", [1, 4, 12])
def test_random_source_moves_positions_and_uses_deep_references(seed: int, depth: int):
    program = workloads.tree_program(seed, 12, depth)
    result = driver.Driver().validate_source(program.source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    for operation in program.operations:
        assert calculator.add(operation) == oracle.add(operation)
    assert calculator.simultaneous(program.simultaneous) == oracle.simultaneous(
        program.simultaneous
    )
    for occurrence in range(len(calculator.graph)):
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
    validation.check_random_schedule(
        [*program.operations, *program.simultaneous], calculator.graph, seed
    )


@pytest.mark.parametrize("width", [12, 96])
def test_chained_destination_after_many_independent_source_uses(width: int):
    lines: list[str] = []
    for name in ["target", "temporary", *[f"child{index}" for index in range(width)]]:
        lines.append(f"define the potential position<my.domain.com:my_lib:/{name}>.")
    lines.extend(
        [
            "define the potential action<my.domain.com:my_lib:/test> {",
            "    it happens when {",
            "        this particle is created.",
            "    } and it does {",
            "        define the position<a> {",
            "            it may only contain particles where {",
        ]
    )
    for index in range(width):
        lines.append(f"                it has the position</child{index}>.")
    lines.extend(
        [
            "            }",
            "        }",
            "        define the position<b> {",
            "            it may only contain particles where {",
            "                it has the position</target>.",
            "                it has the position</temporary>.",
            "            }",
            "        }",
            "        create a particle in position<a>.",
            "        create a particle in position<b>.",
            "        create a particle in position<b>::position</temporary>.",
            "        destroy the particle in position<b>::position</temporary>.",
        ]
    )
    operations = [
        algorithm.Operation(fill=0, defines=tuple(range(4, 4 + width))),
        algorithm.Operation(fill=1, defines=(2, 3)),
        algorithm.Operation(occupied=(1,), fill=3, creators=(1,)),
        algorithm.Operation(occupied=(1,), empty=3, creators=(1,)),
    ]
    for index in range(width):
        lines.append(
            f"        create a particle in position<a>::position</child{index}>."
        )
        operations.append(
            algorithm.Operation(occupied=(0,), fill=4 + index, creators=(0,))
        )
    lines.extend(
        [
            "        move the particle in position<a> to position<b>::position</target>.",
            "    }",
            "}",
        ]
    )
    operations.append(
        algorithm.Operation(occupied=(1,), empty=0, fill=2, creators=(1,))
    )
    result = driver.Driver().validate_source("\n".join(lines) + "\n").program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    for operation in operations:
        assert calculator.add(operation) == oracle.add(operation)
    assert set(calculator.graph.dependencies(len(operations) - 1)) == {
        1,
        *range(4, 4 + width),
    }
    vacancies = [
        algorithm.Operation(empty=1),
        algorithm.Operation(empty=2, creators=(1,)),
    ]
    for child in range(4, 4 + width):
        vacancies.append(algorithm.Operation(empty=child, creators=(0,)))
    assert calculator.simultaneous(vacancies) == oracle.simultaneous(vacancies)
    for occurrence in range(len(calculator.graph)):
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
    validation.check_random_schedule([*operations, *vacancies], calculator.graph, 36)


@pytest.mark.parametrize("cache_bytes", [64, 512, 4096])
@pytest.mark.parametrize("cache_targets", [0, 1, 8])
def test_shared_parent_source_with_bounded_reachability_cache(
    cache_bytes: int, cache_targets: int
):
    program = workloads.shared_program(31, 250)
    result = driver.Driver().validate_source(program.source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator(cache_targets, cache_bytes)
    oracle = reference.Reference()
    for operation in program.operations:
        occurrence = calculator.add(operation)
        assert oracle.add(operation) == occurrence
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )


def test_moving_a_particle_after_many_child_creates_then_destroying_its_old_parent():
    width = 96
    lines: list[str] = []
    for child in range(width):
        lines.append(
            f"define the potential position<my.domain.com:my_lib:/child{child}>."
        )
    constraints = [
        "    it may only contain particles where {",
    ]
    for child in range(width):
        constraints.append(f"        it has the position</child{child}>.")
    constraints.append("    }")
    lines.append("define the potential position<my.domain.com:my_lib:/branch> {")
    lines.extend(constraints)
    lines.extend(
        [
            "}",
            "define the potential action<my.domain.com:my_lib:/test> {",
            "    it happens when {",
            "        this particle is created.",
            "    } and it does {",
            "        define the position<before> {",
            "            it may only contain particles where {",
            "                it has the position</branch>.",
            "            }",
            "        }",
            "        define the position<after> {",
        ]
    )
    lines.extend("        " + line for line in constraints)
    lines.extend(
        [
            "        }",
            "        create a particle in position<before>.",
            "        create a particle in position<before>::position</branch>.",
        ]
    )
    operations = [
        algorithm.Operation(fill=0, defines=(1,)),
        algorithm.Operation(
            occupied=(0,), fill=1, creators=(0,), defines=tuple(range(3, 3 + width))
        ),
    ]
    for child in range(width):
        lines.append(
            f"        create a particle in position<before>::position</branch>::position</child{child}>."
        )
        operations.append(
            algorithm.Operation(occupied=(0, 1), fill=3 + child, creators=(0, 1))
        )
    lines.extend(
        [
            "        move the particle in position<before>::position</branch> to position<after>.",
            "        destroy the particle in position<before>.",
        ]
    )
    operations.extend(
        [
            algorithm.Operation(occupied=(0,), empty=1, fill=2, creators=(0,)),
            algorithm.Operation(empty=0),
        ]
    )
    for child in range(width):
        lines.append(
            f"        destroy the particle in position<after>::position</child{child}>."
        )
        operations.append(
            algorithm.Operation(occupied=(2,), empty=3 + child, creators=(1,))
        )
    lines.extend(["    }", "}"])
    result = driver.Driver().validate_source("\n".join(lines) + "\n").program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    for operation in operations:
        assert calculator.add(operation) == oracle.add(operation)
    assert set(calculator.graph.dependencies(width + 2)) == set(range(2, width + 2))
    assert set(calculator.graph.dependencies(width + 3)) == {width + 2}
    vacancies = [algorithm.Operation(empty=2)]
    assert calculator.simultaneous(vacancies) == oracle.simultaneous(vacancies)
    for occurrence in range(len(calculator.graph)):
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
    validation.check_random_schedule([*operations, *vacancies], calculator.graph, 91)


@pytest.mark.parametrize("seed", range(5))
def test_reusing_old_vacancies_in_source(seed: int):
    program = workloads.vacancy_program(seed)
    result = driver.Driver().validate_source(program.source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    for operation in program.operations:
        occurrence = calculator.add(operation)
        assert oracle.add(operation) == occurrence
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
    validation.check_random_schedule(program.operations, calculator.graph, seed)


@pytest.mark.parametrize("seed", range(5))
def test_implied_reuse_is_independent_of_callers_common_dependency(seed: int):
    program = workloads.joined_program(seed)
    result = driver.Driver().validate_source(program.source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    for operation in program.operations:
        occurrence = calculator.add(operation)
        assert oracle.add(operation) == occurrence
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
    validation.check_random_schedule(program.operations, calculator.graph, seed)


@pytest.mark.parametrize("seed", range(5))
def test_simultaneous_destruction_of_independent_particles_and_their_children(
    seed: int,
):
    program = workloads.destruction_program(seed)
    result = driver.Driver().validate_source(program.source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    for operation in program.operations:
        assert calculator.add(operation) == oracle.add(operation)
    assert calculator.simultaneous(program.simultaneous) == oracle.simultaneous(
        program.simultaneous
    )
    for occurrence in range(len(calculator.graph)):
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
    validation.check_random_schedule(
        [*program.operations, *program.simultaneous], calculator.graph, seed
    )


def test_many_unrelated_old_vacancies_with_long_later_uses():
    operations = list(workloads.long_vacancy_reuse(19, 1100, 1))
    cached = algorithm.Calculator()
    uncached = algorithm.Calculator(cache_targets=0)
    for operation in operations:
        assert cached.add(operation) == uncached.add(operation)
    assert cached.graph.offsets == uncached.graph.offsets
    assert cached.graph.edges == uncached.graph.edges
    validation.check_random_schedule(operations, cached.graph, 72)


def test_reachability_cache_survives_growth_and_multiple_evictions():
    calculator = algorithm.Calculator(cache_targets=8, cache_bytes=1600)
    for operation in workloads.interleaved_moves(1, 198, 1):
        _ = calculator.add(operation)
    # Repeated queries make several old answers useful before the same valid
    # single-particle program grows beyond the space available for their copies.
    for previous in range(8):
        for _ in range(3):
            assert calculator.graph.reaches(199, previous)
    for operation in workloads.interleaved_moves(2, 498, 1):
        _ = calculator.add(operation)
    for previous in range(8):
        assert calculator.graph.reaches(699, previous)


def test_position_identifier_assignment_does_not_change_dependencies():
    program = workloads.tree_program(37, 30)
    randomizer = random.Random(94)  # noqa: S311 - Reproducible identifier assignment.
    positions: set[int] = set()
    for operation in [*program.operations, *program.simultaneous]:
        positions.update((*operation.occupied, *operation.defines))
        if operation.fill is not None:
            positions.add(operation.fill)
        if operation.empty is not None:
            positions.add(operation.empty)
    shuffled = list(positions)
    randomizer.shuffle(shuffled)
    mapping = dict(zip(sorted(positions), shuffled, strict=True))
    original = algorithm.Calculator()
    renamed = algorithm.Calculator()
    remapped: list[algorithm.Operation] = []
    for operation in [*program.operations, *program.simultaneous]:
        remapped.append(
            dataclasses.replace(
                operation,
                occupied=tuple(mapping[position] for position in operation.occupied),
                fill=None if operation.fill is None else mapping[operation.fill],
                empty=None if operation.empty is None else mapping[operation.empty],
                defines=tuple(mapping[position] for position in operation.defines),
            )
        )
    for operation in program.operations:
        _ = original.add(operation)
    for operation in remapped[: len(program.operations)]:
        _ = renamed.add(operation)
    assert original.simultaneous(program.simultaneous) == renamed.simultaneous(
        remapped[len(program.operations) :]
    )
    for occurrence in range(len(original.graph)):
        assert set(original.graph.dependencies(occurrence)) == set(
            renamed.graph.dependencies(occurrence)
        )


def test_repeated_action_calls_use_distinct_operations_and_shared_interface_positions():
    source = """define the potential action<my.domain.com:my_lib:/transfer> {
    define the position<input>.
    define the position<result>.
    it happens when {
        the position<input> has a particle.
    } and it does {
        move the particle in position<input> to position<result>.
    }
}
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<parent> {
            it may only contain particles where {
                it has the action</transfer>.
            }
        }
        create a particle in position<parent>.
        create a particle in position<parent>::action</transfer>::position<input>.
        destroy the particle in position<parent>::action</transfer>::position<result>.
        create a particle in position<parent>::action</transfer>::position<input>.
        destroy the particle in position<parent>::action</transfer>::position<result>.
    }
}
"""
    result = driver.Driver().validate_source(source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    operations = [algorithm.Operation(fill=0, defines=(1, 2))]
    for _ in range(2):
        operations.extend(
            [
                algorithm.Operation(occupied=(0,), fill=1, creators=(0,)),
                algorithm.Operation(empty=1, fill=2, creators=(0,)),
                algorithm.Operation(occupied=(0,), empty=2, creators=(0,)),
            ]
        )
    operations.append(algorithm.Operation(empty=0))
    for operation in operations:
        assert calculator.add(operation) == oracle.add(operation)
    expected: list[set[int]] = [set(), {0}, {1}, {2}, {2}, {3, 4}, {5}, {6}]
    assert [
        set(calculator.graph.dependencies(index)) for index in range(len(operations))
    ] == expected
    assert oracle.dependencies == expected
    validation.check_random_schedule(operations, calculator.graph, 91)


def test_shared_retained_state_inherits_ordinary_uses_and_excludes_vacancy():
    source = """define the potential position<my.domain.com:my_lib:/child>.
define the potential action<my.domain.com:my_lib:/cleanup> {
    it also assigns the position</child>.
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<scratch>.
        move the particle in position</child> to position<scratch>.
        move the particle in position<scratch> to position</child>.
    }
}
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<parent> {
            it may only contain particles where {
                it has the position</child>.
                it has the action</cleanup>.
            }
        }
        create a particle in position<parent>.
        create a particle in position<parent>::position</child>.
        destroy the particle in position<parent>.
    }
}
"""
    result = driver.Driver().validate_source(source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    for operation in [
        algorithm.Operation(fill=0, defines=(1,)),
        algorithm.Operation(occupied=(0,), fill=1, creators=(0,)),
    ]:
        assert calculator.add(operation) == oracle.add(operation)
    calculator.retain({0: 10, 1: 11})
    oracle.retain({0: 10, 1: 11})
    vacancies = [
        algorithm.Operation(empty=0),
        algorithm.Operation(empty=1, creators=(0,)),
    ]
    assert calculator.simultaneous(vacancies) == oracle.simultaneous(vacancies)
    for operation in [
        algorithm.Operation(empty=11, fill=12, creators=(0,)),
        algorithm.Operation(empty=12, fill=11, creators=(0,)),
    ]:
        occurrence = calculator.add(operation)
        assert oracle.add(operation) == occurrence
    for occurrence in range(len(calculator.graph)):
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
    assert set(calculator.graph.dependencies(4)) == {1}
    assert set(calculator.graph.dependencies(5)) == {4}
    calculator.forget((10, 11, 12))


def test_comparison_for_arbitrary_preceding_graphs():
    # This checks the mathematical subroutine, not whether arbitrary graphs are
    # realizable by Define. Valid-source coverage is separate above.
    randomizer = random.Random(812)  # noqa: S311 - Reproducible graph checks.
    calculated = graph.Graph(8)
    ancestors: list[set[int]] = []
    for occurrence in range(400):
        candidates = set(
            randomizer.sample(
                range(occurrence), min(occurrence, randomizer.randrange(96))
            )
        )
        expected = set(candidates)
        reached = set(candidates)
        for candidate in candidates:
            expected.difference_update(ancestors[candidate])
            reached.update(ancestors[candidate])
        dependencies = algorithm.compare(calculated, candidates)
        assert set(dependencies) == expected
        assert calculated.append(dependencies) == occurrence
        ancestors.append(reached)
        for previous in range(occurrence):
            assert calculated.reaches(occurrence, previous) == (previous in reached)


@pytest.mark.parametrize("reverse_destroys", [False, True])
def test_implied_constructor_access_and_written_access_after_parent_move(
    *,
    reverse_destroys: bool,
):
    source = """define the potential position<my.domain.com:my_lib:/marker>.
define the potential action<my.domain.com:my_lib:/construct> {
    it also assigns the position</marker>.
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position</marker>.
        destroy the particle in position</marker>.
    }
}
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the position</marker>.
                it has the action</construct>.
            }
        }
        define the position<destination> {
            it may only contain particles where {
                it has the position</marker>.
            }
        }
        create a particle in position<source>.
        move the particle in position<source> to position<destination>.
        create a particle in position<destination>::position</marker>.
    }
}
"""
    result = driver.Driver().validate_source(source).program_validation
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    calculator = algorithm.Calculator()
    oracle = reference.Reference()
    for operation in [
        algorithm.Operation(fill=0, defines=(1,)),
        algorithm.Operation(fill=1, creators=(0,)),
        algorithm.Operation(empty=1, creators=(0,)),
        algorithm.Operation(empty=0, fill=2),
        algorithm.Operation(occupied=(2,), fill=1, creators=(0,)),
    ]:
        assert calculator.add(operation) == oracle.add(operation)
    vacancies = [
        algorithm.Operation(empty=2),
        algorithm.Operation(empty=1, creators=(0,)),
    ]
    if reverse_destroys:
        vacancies.reverse()
    assert calculator.simultaneous(vacancies) == oracle.simultaneous(vacancies)
    assert [set(calculator.graph.dependencies(index)) for index in range(7)] == [
        set(),
        {0},
        {1},
        {0},
        {2, 3},
        {4},
        {4},
    ]
    assert [
        set(calculator.graph.dependencies(index)) for index in range(7)
    ] == oracle.dependencies
