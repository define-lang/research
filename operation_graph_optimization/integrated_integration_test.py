from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

import pytest

from define.compiler import driver
from operation_graph_optimization import (
    algorithm,
    combination_algorithm,
    combination_inputs,
    complete_inputs,
    complete_workloads,
    integrated_bounded,
    integrated_compact,
    integrated_inline,
    integrated_resolved,
    integrated_variants,
    integrated_workloads,
    reference,
    vanish_workloads,
    workloads,
)
from operation_graph_optimization.complete import algorithm as complete
from operation_graph_optimization.integrated import algorithm as integrated

if TYPE_CHECKING:
    import collections.abc


type Calculator = (
    integrated.Calculator
    | integrated_inline.Calculator
    | integrated_resolved.Calculator
    | complete.Calculator
)


def _add(calculator: Calculator, step: vanish_workloads.Step) -> int:
    if isinstance(calculator, complete.Calculator):
        return calculator.add(complete_inputs.convert(step))
    return calculator.add(integrated_variants.convert(step))


@pytest.mark.parametrize("depth", [1, 6, 20])
@pytest.mark.parametrize("seed", [17, 43, 91])
def test_real_source_with_long_chained_names(depth: int, seed: int):
    program = workloads.tree_program(seed, 12, depth, 3)
    validated = driver.Driver().validate_source(program.source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    _, vanishes = _check(
        complete_workloads.resolve_program(program), complete.Calculator
    )
    assert len(vanishes) == 3 * (depth + 1)


@pytest.mark.parametrize(
    "generate",
    [
        workloads.shared_program,
        workloads.joined_program,
        workloads.vacancy_program,
        workloads.destruction_program,
    ],
)
@pytest.mark.parametrize("width", [3, 80])
def test_real_source_with_shared_dependencies(
    generate: collections.abc.Callable[[int, int, int], workloads.Program],
    width: int,
):
    program = generate(17, max(12, width), width)
    validated = driver.Driver().validate_source(program.source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    _ = _check(complete_workloads.resolve_program(program), complete.Calculator)


@pytest.mark.parametrize(
    ("pruning", "setter_search", "comparison"),
    [(0, 0, 2), (16, 16, 64), (100000, 100000, 100000)],
)
def test_complete_graph_is_independent_of_optional_pruning(
    monkeypatch: pytest.MonkeyPatch,
    pruning: int,
    setter_search: int,
    comparison: int,
):
    monkeypatch.setattr(complete, "MAX_PRUNING_CANDIDATES", pruning)
    monkeypatch.setattr(complete, "MAX_SETTER_SEARCH_CANDIDATES", setter_search)
    monkeypatch.setattr(complete, "MAX_PAIRWISE_COMPARISON_CANDIDATES", comparison)
    monkeypatch.setattr(combination_algorithm, "MAX_PRUNING_CANDIDATES", pruning)
    monkeypatch.setattr(
        combination_algorithm, "MAX_SETTER_SEARCH_CANDIDATES", setter_search
    )
    monkeypatch.setattr(
        combination_algorithm, "MAX_PAIRWISE_COMPARISON_CANDIDATES", comparison
    )
    program = workloads.joined_program(17, 20, 96)
    validated = driver.Driver().validate_source(program.source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    _ = _check(complete_workloads.resolve_program(program), complete.Calculator)


@pytest.mark.parametrize("cache_targets", [0, 1, 8])
def test_complete_cache_growth_on_real_source(cache_targets: int):
    program = workloads.vacancy_program(17, 160, 4)
    validated = driver.Driver().validate_source(program.source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    steps = complete_workloads.resolve_program(program)
    calculator = complete.Calculator(cache_targets=cache_targets, cache_bytes=1600)
    oracle = reference.Reference()
    for occurrence, step in enumerate(steps):
        assert calculator.add(complete_inputs.convert(step)) == occurrence
        assert oracle.add(step.operation) == occurrence
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
        if occurrence and occurrence % 100 == 0:
            for previous in range(occurrence):
                for _ in range(3):
                    assert calculator.graph.reaches_indexed(occurrence, previous) == (
                        previous in oracle.ancestors[occurrence]
                    )
    actual_vanishes = calculator.finish()
    expected, expected_vanishes = _check(steps, complete.Calculator)
    assert actual_vanishes == expected_vanishes
    for occurrence in range(len(expected)):
        assert set(calculator.graph.dependencies(occurrence)) == set(
            expected.dependencies(occurrence)
        )


@pytest.mark.parametrize("mode", ["written", "action"])
def test_comparison_collapses_ordered_readers(
    mode: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(complete, "MAX_PRUNING_CANDIDATES", 0)
    monkeypatch.setattr(complete, "MAX_PAIRWISE_COMPARISON_CANDIDATES", 2)
    monkeypatch.setattr(combination_algorithm, "MAX_PRUNING_CANDIDATES", 0)
    monkeypatch.setattr(combination_algorithm, "MAX_PAIRWISE_COMPARISON_CANDIDATES", 2)
    action = mode == "action"
    definition = ""
    constraint = ""
    declaration = "        define the position<temporary>."
    destination = "position<temporary>"
    if action:
        definition = """define the potential action<my.domain.com:my_lib:/restore> {
    it also assigns the position</child>.
    define the position<input>.
    it happens when {
        the position<input> has a particle.
    } and it does {
        move the particle in position<input> to position</child>.
    }
}
"""
        constraint = "                it has the action</restore>."
        declaration = ""
        destination = "position<parent>::action</restore>::position<input>"
    body: list[str] = []
    operations = [
        algorithm.Operation(fill=0, defines=(1, 2) if action else (1,)),
        algorithm.Operation(occupied=(0,), fill=1, creators=(0,)),
    ]
    for _ in range(3):
        body.append(
            f"        move the particle in position<parent>::position</child> to {destination}."
        )
        operations.append(
            algorithm.Operation(occupied=(0,), empty=1, fill=2, creators=(0,))
        )
        if not action:
            body.append(
                f"        move the particle in {destination} to position<parent>::position</child>."
            )
        operations.append(
            algorithm.Operation(
                occupied=() if action else (0,), empty=2, fill=1, creators=(0,)
            )
        )
    body_text = "\n".join(body)
    source = f"""define the potential position<my.domain.com:my_lib:/child>.
{definition}define the potential action<my.domain.com:my_lib:/test> {{
    it happens when {{
        this particle is created.
    }} and it does {{
        define the position<parent> {{
            it may only contain particles where {{
                it has the position</child>.
{constraint}
            }}
        }}
{declaration}
        create a particle in position<parent>.
        create a particle in position<parent>::position</child>.
{body_text}
        destroy the particle in position<parent>.
    }}
}}
"""
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    parent_vacate = len(operations)
    last_written = parent_vacate - (2 if action else 1)
    operations.extend([algorithm.Operation(empty=0), algorithm.Operation(empty=1)])
    calculated, vanishes = _check(
        vanish_workloads.resolve(operations), complete.Calculator
    )
    assert set(calculated.dependencies(parent_vacate)) == {last_written}
    expected = {parent_vacate}
    if action:
        expected.add(parent_vacate - 1)
    assert set(calculated.dependencies(vanishes[0])) == expected


def test_complete_cache_admission_stays_bounded_on_independent_source_chains():
    moves = 1200
    names = [
        "position<a>",
        "position<alternate_a>",
        "position<b>",
        "position<alternate_b>",
    ]
    body = [f"        define the {name}." for name in names]
    body.extend(
        [
            "        create a particle in position<a>.",
            "        create a particle in position<b>.",
        ]
    )
    operations = [algorithm.Operation(fill=0), algorithm.Operation(fill=2)]
    for first in (0, 2):
        for index in range(moves):
            source, destination = first + index % 2, first + 1 - index % 2
            body.append(
                f"        move the particle in {names[source]} to {names[destination]}."
            )
            operations.append(algorithm.Operation(empty=source, fill=destination))
    body.extend(
        [
            "        destroy the particle in position<a>.",
            "        destroy the particle in position<b>.",
        ]
    )
    operations.extend([algorithm.Operation(empty=0), algorithm.Operation(empty=2)])
    body_text = "\n".join(body)
    source = f"""define the potential action<my.domain.com:my_lib:/test> {{
    it happens when {{
        this particle is created.
    }} and it does {{
{body_text}
    }}
}}
"""
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    calculator = complete.Calculator(cache_targets=8)
    for step in vanish_workloads.resolve(operations):
        _ = calculator.add(complete_inputs.convert(step))
    last_a, last_b = moves + 1, 2 * moves + 1
    # Unrelated questions must remain correct when admission bookkeeping fills.
    for previous in range(2, 1027):
        assert not calculator.graph.reaches_indexed(last_b, previous)
    for previous in range(2, 10):
        for _ in range(3):
            assert calculator.graph.reaches_indexed(last_a, previous)
        assert not calculator.graph.reaches_indexed(last_b, previous)
    vanishes = calculator.finish()
    assert set(calculator.graph.dependencies(vanishes[0])) == {last_b + 1}
    assert set(calculator.graph.dependencies(vanishes[1])) == {last_b + 2}


def _check(
    steps: list[vanish_workloads.Step],
    implementation: type[Calculator],
    retentions: dict[int, dict[int, int]] | None = None,
    forgotten: tuple[int, ...] = (),
):
    calculator = implementation()
    oracle = reference.Reference()
    ancestors: list[set[int]] = []
    all_uses: dict[int, set[int]] = {}
    destroyed: set[int] = set()
    for index, step in enumerate(steps):
        if retentions is not None and index in retentions:
            calculator.retain(retentions[index])
            oracle.retain(retentions[index])
        occurrence = _add(calculator, step)
        assert oracle.add(step.operation) == occurrence
        assert (
            set(calculator.graph.dependencies(occurrence))
            == oracle.dependencies[occurrence]
        )
        reached = set(calculator.graph.dependencies(occurrence))
        for dependency in calculator.graph.dependencies(occurrence):
            reached.update(ancestors[dependency])
        ancestors.append(reached)
        for particle in step.particles:
            all_uses.setdefault(particle, set()).add(occurrence)
        if step.vacated is not None:
            destroyed.add(step.vacated)
            all_uses.setdefault(step.vacated, set()).add(occurrence)
    calculator.forget(forgotten)
    result = calculator.finish()
    assert set(result) == destroyed
    for particle, occurrence in result.items():
        expected = set(all_uses[particle])
        for candidate in all_uses[particle]:
            expected.difference_update(ancestors[candidate])
        assert set(calculator.graph.dependencies(occurrence)) == expected
    for particle, occurrence in result.items():
        expected_ancestors = set(all_uses[particle])
        for use in all_uses[particle]:
            expected_ancestors.update(ancestors[use])
        for previous in range(len(calculator.graph)):
            assert calculator.graph.reaches(occurrence, previous) == (
                previous in expected_ancestors
            )
    separate = combination_inputs.classify(steps)
    for tracked in (separate, set(all_uses)):
        combined = combination_algorithm.Calculator(tracked)
        vacates: dict[int, int] = {}
        for index, step in enumerate(steps):
            if retentions is not None and index in retentions:
                combined.retain(retentions[index])
            assert combined.add(combination_inputs.convert(step)) == index
            assert set(combined.graph.dependencies(index)) == oracle.dependencies[index]
            if step.vacated is not None:
                vacates[step.vacated] = index
        combined.forget(forgotten)
        combined_vanishes = combined.finish()
        assert set(combined_vanishes) == destroyed
        for particle, occurrence in combined_vanishes.items():
            expected = set(calculator.graph.dependencies(result[particle]))
            vacate = vacates[particle]
            if particle not in tracked:
                assert all_uses[particle] <= ancestors[vacate] | {vacate}
            if expected == {vacate}:
                assert occurrence == vacate
            else:
                assert occurrence >= len(steps)
                assert set(combined.graph.dependencies(occurrence)) == expected
            for previous in range(len(steps)):
                assert (
                    occurrence == previous
                    or combined.graph.reaches(occurrence, previous)
                ) == calculator.graph.reaches(result[particle], previous)
    return calculator.graph, result


@pytest.mark.parametrize(
    "implementation",
    [
        integrated.Calculator,
        integrated_compact.Calculator,
        integrated_bounded.Calculator,
        integrated_inline.Calculator,
        integrated_resolved.Calculator,
        complete.Calculator,
    ],
)
@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("width", [1, 8, 80])
def test_random_destructor_moves_with_replacement(
    implementation: type[Calculator],
    seed: int,
    width: int,
):
    steps, retentions = integrated_workloads.retained(seed, 120, width)
    _ = _check(steps, implementation, retentions)


def test_retained_moves_wait_for_ordinary_child_readers():
    source = """define the potential position<my.domain.com:my_lib:/leaf>.
define the potential position<my.domain.com:my_lib:/child> {
    it may only contain particles where {
        it has the position</leaf>.
    }
}
define the potential action<my.domain.com:my_lib:/cleanup> {
    it also assigns the position</child>.
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<temporary>.
        move the particle in position</child> to position<temporary>.
        move the particle in position<temporary> to position</child>.
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
        create a particle in position<parent>::position</child>::position</leaf>.
        destroy the particle in position<parent>::position</child>::position</leaf>.
        destroy the particle in position<parent>.
    }
}
"""
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    steps = vanish_workloads.resolve(
        [
            algorithm.Operation(fill=0, defines=(1,)),
            algorithm.Operation(occupied=(0,), fill=1, creators=(0,), defines=(2,)),
            algorithm.Operation(occupied=(0, 1), fill=2, creators=(0, 1)),
            algorithm.Operation(occupied=(0, 1), empty=2, creators=(0, 1)),
            algorithm.Operation(empty=1),
            algorithm.Operation(empty=0),
        ]
    )
    steps.extend(
        [
            vanish_workloads.Step(
                algorithm.Operation(empty=10, fill=30, creators=(0,)), (0, 1), None, 1
            ),
            vanish_workloads.Step(
                algorithm.Operation(empty=30, fill=10, creators=(0,)), (0, 1), None, 1
            ),
        ]
    )
    calculated, vanishes = _check(steps, complete.Calculator, {4: {1: 10}}, (10, 30))
    assert set(calculated.dependencies(6)) == {3}
    assert calculated.reaches(7, 3)
    assert set(calculated.dependencies(vanishes[1])) == {4, 7}


def test_automatic_child_vacates_do_not_require_parent_qualities():
    program = workloads.destruction_program(17, 4, 1)
    validated = driver.Driver().validate_source(program.source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    steps = complete_workloads.resolve_program(program)
    calculated, vanishes = _check(steps, complete.Calculator)
    parent_vacate = next(
        occurrence for occurrence, step in enumerate(steps) if step.vacated == 0
    )
    assert set(calculated.dependencies(vanishes[0])) == {parent_vacate}


def test_simultaneous_vacates_preserve_the_complete_graph():
    steps, retentions = integrated_workloads.retained(17, 80, 8)
    expected, expected_vanishes = _check(steps, complete.Calculator, retentions)
    calculator = complete.Calculator()
    for step in steps[:9]:
        _ = calculator.add(complete_inputs.convert(step))
    calculator.retain(retentions[9])
    vacancies = [complete_inputs.convert(step) for step in steps[9:18]]
    assert calculator.simultaneous(vacancies) == list(range(9, 18))
    for step in steps[18:]:
        _ = calculator.add(complete_inputs.convert(step))
    assert calculator.finish() == expected_vanishes
    for occurrence in range(len(expected)):
        assert set(calculator.graph.dependencies(occurrence)) == set(
            expected.dependencies(occurrence)
        )
    combined = combination_algorithm.Calculator(combination_inputs.classify(steps))
    for step in steps[:9]:
        _ = combined.add(combination_inputs.convert(step))
    combined.retain(retentions[9])
    combined_vacancies = [combination_inputs.convert(step) for step in steps[9:18]]
    assert combined.simultaneous(combined_vacancies) == list(range(9, 18))
    for step in steps[18:]:
        _ = combined.add(combination_inputs.convert(step))
    assert combined.finish() == expected_vanishes
    for occurrence in range(len(expected)):
        assert set(combined.graph.dependencies(occurrence)) == set(
            expected.dependencies(occurrence)
        )


@pytest.mark.parametrize("written_child_destroy", [False, True])
def test_final_position_setter_cannot_replace_a_particle_quality_use(
    *,
    written_child_destroy: bool,
):
    source = """define the potential position<my.domain.com:my_lib:/child>.
define the potential action<my.domain.com:my_lib:/initialize> {
    it also assigns the position</child>.
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position</child>.
    }
}
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<parent> {
            it may only contain particles where {
                it has the action</initialize>.
            }
        }
        create a particle in position<parent>.
        destroy the particle in position<parent>.
    }
}
"""
    if written_child_destroy:
        source = source.replace(
            "                it has the action</initialize>.",
            "                it has the action</initialize>.\n                it has the position</child>.",
        )
        source = source.replace(
            "        destroy the particle in position<parent>.",
            "        destroy the particle in position<parent>::position</child>.\n        destroy the particle in position<parent>.",
        )
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    steps = vanish_workloads.resolve(
        [
            algorithm.Operation(fill=0, defines=(1,)),
            algorithm.Operation(fill=1, creators=(0,)),
            algorithm.Operation(occupied=(0,), empty=1, creators=(0,))
            if written_child_destroy
            else algorithm.Operation(empty=1),
            algorithm.Operation(empty=0),
        ]
    )
    calculated, vanishes = _check(steps, complete.Calculator)
    assert combination_inputs.classify(steps) == {0}
    if written_child_destroy:
        assert set(calculated.dependencies(vanishes[0])) == {3}
    else:
        assert set(calculated.dependencies(vanishes[0])) == {1, 3}
        assert not calculated.reaches(vanishes[0], 2)


@pytest.mark.parametrize(
    "implementation",
    [
        integrated.Calculator,
        integrated_variants.Direct,
        integrated_variants.Unpruned,
        integrated_variants.Indexed,
        integrated_compact.Calculator,
        integrated_bounded.Calculator,
        integrated_inline.Calculator,
        integrated_resolved.Calculator,
        complete.Calculator,
    ],
)
@pytest.mark.parametrize("seed", range(5))
def test_random_real_source(
    implementation: type[Calculator],
    seed: int,
):
    program = workloads.random_program(seed, 70, 8)
    validated = driver.Driver().validate_source(program.source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    _ = _check(complete_workloads.resolve_program(program), implementation)


@pytest.mark.parametrize(
    "implementation",
    [
        integrated.Calculator,
        integrated_variants.Direct,
        integrated_variants.Unpruned,
        integrated_variants.Indexed,
        integrated_compact.Calculator,
        integrated_bounded.Calculator,
        integrated_inline.Calculator,
        integrated_resolved.Calculator,
        complete.Calculator,
    ],
)
@pytest.mark.parametrize(
    "family",
    [
        "local",
        "movement",
        "implied",
        "written",
        "wide",
        "state",
        "growth",
        "growth_closed",
    ],
)
@pytest.mark.parametrize("seed", range(3))
def test_reordered_valid_inputs(
    implementation: type[Calculator],
    family: str,
    seed: int,
):
    _ = _check(vanish_workloads.generate(family, seed, 70, 8), implementation)


@pytest.mark.parametrize(
    "implementation",
    [
        integrated.Calculator,
        integrated_variants.Direct,
        integrated_variants.Unpruned,
        integrated_variants.Indexed,
        integrated_compact.Calculator,
        integrated_bounded.Calculator,
        integrated_inline.Calculator,
        integrated_resolved.Calculator,
        complete.Calculator,
    ],
)
@pytest.mark.parametrize("kind", ["constructor", "interface", "destructor"])
def test_actual_quality_access_outlives_vacancy(
    implementation: type[Calculator],
    kind: str,
):
    interface = kind == "interface"
    destructor = kind == "destructor"
    reference = "position<marker>" if interface else "position</marker>"
    declarations = (
        "    define the position<marker>."
        if interface
        else "    it also assigns the position</marker>."
    )
    trigger = "being destroyed" if destructor else "created"
    source = f"""define the potential position<my.domain.com:my_lib:/marker>.
define the potential action<my.domain.com:my_lib:/work> {{
{declarations}
    it happens when {{
        this particle is {trigger}.
    }} and it does {{
        create a particle in {reference}.
        destroy the particle in {reference}.
    }}
}}
define the potential action<my.domain.com:my_lib:/test> {{
    it happens when {{
        this particle is created.
    }} and it does {{
        define the position<parent> {{
            it may only contain particles where {{
                it has the action</work>.
            }}
        }}
        create a particle in position<parent>.
        destroy the particle in position<parent>.
    }}
}}
"""
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    operations = [algorithm.Operation(fill=0, defines=(1,))]
    if destructor:
        operations.append(algorithm.Operation(empty=0))
    operations.extend(
        [
            algorithm.Operation(fill=1, creators=(0,)),
            algorithm.Operation(empty=1, creators=(0,)),
        ]
    )
    if not destructor:
        operations.append(algorithm.Operation(empty=0))
    steps = vanish_workloads.resolve(operations)
    calculated, vanishes = _check(steps, implementation)
    vacancy = 1 if destructor else 3
    last_use = 3 if destructor else 2
    assert set(calculated.dependencies(vanishes[0])) == {vacancy, last_use}
    assert not calculated.reaches(vacancy, last_use)
    schedules: list[dict[int, int]] = []
    for order in itertools.permutations(range(len(calculated))):
        indexes = {occurrence: index for index, occurrence in enumerate(order)}
        valid = True
        for occurrence in order:
            for dependency in calculated.dependencies(occurrence):
                if indexes[dependency] > indexes[occurrence]:
                    valid = False
        if valid:
            schedules.append(indexes)
            assert indexes[last_use] < indexes[vanishes[0]]
    assert any(order[vacancy] < order[last_use] for order in schedules)


@pytest.mark.parametrize(
    "implementation",
    [
        integrated.Calculator,
        integrated_variants.Direct,
        integrated_variants.Unpruned,
        integrated_variants.Indexed,
        integrated_compact.Calculator,
        integrated_bounded.Calculator,
        integrated_inline.Calculator,
        integrated_resolved.Calculator,
        complete.Calculator,
    ],
)
def test_shared_destructor_moves_protect_original_particles_not_replacements(
    implementation: type[Calculator],
):
    source = """define the potential position<my.domain.com:my_lib:/child>.
define the potential action<my.domain.com:my_lib:/cleanup> {
    it also assigns the position</child>.
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<temporary>.
        move the particle in position</child> to position<temporary>.
        move the particle in position<temporary> to position</child>.
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
        create a particle in position<parent>.
        create a particle in position<parent>::position</child>.
    }
}
"""
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    calculator = implementation()
    steps = [
        vanish_workloads.Step(algorithm.Operation(fill=0, defines=(1,)), (), None),
        vanish_workloads.Step(
            algorithm.Operation(occupied=(0,), fill=1, creators=(0,)), (0,), None
        ),
        vanish_workloads.Step(algorithm.Operation(empty=1), (), 1),
        vanish_workloads.Step(algorithm.Operation(empty=0), (), 0),
        vanish_workloads.Step(algorithm.Operation(fill=0, defines=(2,)), (), None),
        vanish_workloads.Step(
            algorithm.Operation(empty=10, fill=11, creators=(0,)), (0, 1), None, 1
        ),
        vanish_workloads.Step(
            algorithm.Operation(empty=11, fill=10, creators=(0,)), (0, 1), None, 1
        ),
    ]
    # The prefix ends before the replacement's child Create and later destruction.
    _ = _check(steps, implementation, {2: {1: 10}})
    assert 1 in combination_inputs.classify(steps)
    for occurrence, step in enumerate(steps):
        if occurrence == 2:
            calculator.retain({1: 10})
        assert _add(calculator, step) == occurrence
    result = calculator.finish()
    assert set(result) == {0, 1}
    assert set(calculator.graph.dependencies(result[0])) == {3, 6}
    assert set(calculator.graph.dependencies(result[1])) == {2, 6}
    assert set(calculator.graph.dependencies(4)) == {3}


@pytest.mark.parametrize(
    "implementation",
    [
        integrated.Calculator,
        integrated_variants.Direct,
        integrated_variants.Unpruned,
        integrated_variants.Indexed,
        integrated_compact.Calculator,
        integrated_bounded.Calculator,
        integrated_inline.Calculator,
        integrated_resolved.Calculator,
        complete.Calculator,
    ],
)
def test_transitive_movement_does_not_prolong_child_lifetime(
    implementation: type[Calculator],
):
    source = """define the potential position<my.domain.com:my_lib:/child>.
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the position</child>.
            }
        }
        define the position<destination>.
        create a particle in position<source>.
        create a particle in position<source>::position</child>.
        move the particle in position<source> to position<destination>.
    }
}
"""
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    steps = vanish_workloads.resolve(
        [
            algorithm.Operation(fill=0, defines=(1,)),
            algorithm.Operation(occupied=(0,), fill=1, creators=(0,)),
            algorithm.Operation(empty=0, fill=2),
            algorithm.Operation(empty=1),
            algorithm.Operation(empty=2),
        ]
    )
    calculated, result = _check(steps, implementation)
    assert set(calculated.dependencies(result[1])) == {3}
    assert not calculated.reaches(result[1], 2)
    assert set(calculated.dependencies(result[0])) == {4}


@pytest.mark.parametrize(
    "implementation",
    [
        integrated.Calculator,
        integrated_variants.Direct,
        integrated_variants.Unpruned,
        integrated_variants.Indexed,
        integrated_compact.Calculator,
        integrated_bounded.Calculator,
        integrated_inline.Calculator,
        integrated_resolved.Calculator,
        complete.Calculator,
    ],
)
def test_ordinary_action_interface_and_implied_uses_outlive_vacancy(
    implementation: type[Calculator],
):
    source = """define the potential position<my.domain.com:my_lib:/marker>.
define the potential action<my.domain.com:my_lib:/transfer> {
    it also assigns the position</marker>.
    define the position<input>.
    define the position<result>.
    it happens when {
        the position<input> has a particle.
    } and it does {
        move the particle in position<input> to position<result>.
        create a particle in position</marker>.
        destroy the particle in position</marker>.
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
        destroy the particle in position<parent>.
    }
}
"""
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    steps = vanish_workloads.resolve(
        [
            algorithm.Operation(fill=0, defines=(1, 2, 3)),
            algorithm.Operation(occupied=(0,), fill=1, creators=(0,)),
            algorithm.Operation(empty=1, fill=2, creators=(0,)),
            algorithm.Operation(fill=3, creators=(0,)),
            algorithm.Operation(empty=3, creators=(0,)),
            algorithm.Operation(empty=0),
            algorithm.Operation(empty=2),
        ]
    )
    calculated, result = _check(steps, implementation)
    assert set(calculated.dependencies(result[0])) == {2, 4, 5}
    assert not calculated.reaches(5, 2)
    assert not calculated.reaches(5, 4)


@pytest.mark.parametrize(
    "implementation",
    [
        integrated.Calculator,
        integrated_variants.Direct,
        integrated_variants.Unpruned,
        integrated_variants.Indexed,
        integrated_compact.Calculator,
        integrated_bounded.Calculator,
        integrated_inline.Calculator,
        integrated_resolved.Calculator,
        complete.Calculator,
    ],
)
def test_retained_intermediate_occupancy_does_not_cover_a_quality_use(
    implementation: type[Calculator],
):
    source = """define the potential position<my.domain.com:my_lib:/leaf>.
define the potential position<my.domain.com:my_lib:/child> {
    it may only contain particles where {
        it has the position</leaf>.
    }
}
define the potential action<my.domain.com:my_lib:/cleanup> {
    it also assigns the position</child>.
    it happens when {
        this particle is being destroyed.
    } and it does {
        create a particle in position</child>::position</leaf>.
        destroy the particle in position</child>::position</leaf>.
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
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    calculator = implementation()
    steps = [
        vanish_workloads.Step(algorithm.Operation(fill=0, defines=(1,)), (), None),
        vanish_workloads.Step(
            algorithm.Operation(occupied=(0,), fill=1, creators=(0,), defines=(2,)),
            (0,),
            None,
            ordinary_occupants=(0,),
        ),
        vanish_workloads.Step(algorithm.Operation(empty=1), (), 1),
        vanish_workloads.Step(algorithm.Operation(empty=0), (), 0),
        vanish_workloads.Step(
            algorithm.Operation(occupied=(10,), fill=20, creators=(0, 1)), (0, 1), None
        ),
        vanish_workloads.Step(
            algorithm.Operation(occupied=(10,), empty=20, creators=(0, 1)), (0, 1), 4
        ),
    ]
    _ = _check(steps, implementation, {2: {1: 10, 2: 20}})
    for occurrence, step in enumerate(steps):
        if occurrence == 2:
            calculator.retain({1: 10, 2: 20})
        assert _add(calculator, step) == occurrence
    result = calculator.finish()
    assert set(calculator.graph.dependencies(result[0])) == {3, 5}
    assert set(calculator.graph.dependencies(result[1])) == {2, 5}
    assert set(calculator.graph.dependencies(result[4])) == {5}
