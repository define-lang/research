from __future__ import annotations

import itertools

import pytest

from define.compiler import driver
from operation_graph_optimization import (
    algorithm,
    vanish,
    vanish_algorithm,
    vanish_workloads,
    workloads,
)


def _check(
    steps: list[vanish_workloads.Step],
    implementation: type[vanish.Collector | vanish_algorithm.Calculator],
):
    calculator = algorithm.Calculator()
    collector = implementation(calculator.graph)
    ancestors: list[set[int]] = []
    all_uses: dict[int, set[int]] = {}
    destroyed: set[int] = set()
    for step in steps:
        occurrence = calculator.add(step.operation)
        reached = set(calculator.graph.dependencies(occurrence))
        for dependency in calculator.graph.dependencies(occurrence):
            reached.update(ancestors[dependency])
        ancestors.append(reached)
        for particle in step.particles:
            all_uses.setdefault(particle, set()).add(occurrence)
        if step.vacated is not None:
            destroyed.add(step.vacated)
            all_uses.setdefault(step.vacated, set()).add(occurrence)
        if isinstance(collector, vanish_algorithm.Calculator):
            collector.observe(
                occurrence,
                step.operation.creators,
                step.moved,
                step.vacated,
                step.ordinary_occupants,
            )
        else:
            collector.observe(occurrence, step.particles, step.vacated)
    result = collector.finish()
    assert set(result) == destroyed
    for particle, occurrence in result.items():
        expected = set(all_uses[particle])
        for candidate in all_uses[particle]:
            expected.difference_update(ancestors[candidate])
        assert set(calculator.graph.dependencies(occurrence)) == expected
    return calculator.graph, result


@pytest.mark.parametrize(
    "implementation",
    [
        vanish.Collector,
        vanish.DirectPruning,
        vanish.Incremental,
        vanish_algorithm.Calculator,
    ],
)
@pytest.mark.parametrize("seed", range(5))
def test_random_real_source(
    implementation: type[vanish.Collector | vanish_algorithm.Calculator], seed: int
):
    program = workloads.random_program(seed, 70, 8)
    validated = driver.Driver().validate_source(program.source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    _ = _check(vanish_workloads.resolve(program.operations), implementation)


@pytest.mark.parametrize(
    "implementation",
    [
        vanish.Collector,
        vanish.DirectPruning,
        vanish.Incremental,
        vanish_algorithm.Calculator,
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
    implementation: type[vanish.Collector | vanish_algorithm.Calculator],
    family: str,
    seed: int,
):
    _ = _check(vanish_workloads.generate(family, seed, 70, 8), implementation)


@pytest.mark.parametrize(
    "implementation",
    [
        vanish.Collector,
        vanish.DirectPruning,
        vanish.Incremental,
        vanish_algorithm.Calculator,
    ],
)
@pytest.mark.parametrize("kind", ["constructor", "interface", "destructor"])
def test_actual_quality_access_outlives_vacancy(
    implementation: type[vanish.Collector | vanish_algorithm.Calculator], kind: str
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
        vanish.Collector,
        vanish.DirectPruning,
        vanish.Incremental,
        vanish_algorithm.Calculator,
    ],
)
def test_shared_destructor_moves_protect_original_particles_not_replacements(
    implementation: type[vanish.Collector | vanish_algorithm.Calculator],
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
    calculator = algorithm.Calculator()
    collector = implementation(calculator.graph)
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
    for occurrence, step in enumerate(steps):
        if occurrence == 2:
            calculator.retain({1: 10})
        assert calculator.add(step.operation) == occurrence
        if isinstance(collector, vanish_algorithm.Calculator):
            collector.observe(
                occurrence,
                step.operation.creators,
                step.moved,
                step.vacated,
                step.ordinary_occupants,
            )
        else:
            collector.observe(occurrence, step.particles, step.vacated)
    result = collector.finish()
    assert set(result) == {0, 1}
    assert set(calculator.graph.dependencies(result[0])) == {3, 6}
    assert set(calculator.graph.dependencies(result[1])) == {2, 6}
    assert set(calculator.graph.dependencies(4)) == {3}


@pytest.mark.parametrize(
    "implementation",
    [
        vanish.Collector,
        vanish.DirectPruning,
        vanish.Incremental,
        vanish_algorithm.Calculator,
    ],
)
def test_transitive_movement_does_not_prolong_child_lifetime(
    implementation: type[vanish.Collector | vanish_algorithm.Calculator],
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
        vanish.Collector,
        vanish.DirectPruning,
        vanish.Incremental,
        vanish_algorithm.Calculator,
    ],
)
def test_ordinary_action_interface_and_implied_uses_outlive_vacancy(
    implementation: type[vanish.Collector | vanish_algorithm.Calculator],
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
        vanish.Collector,
        vanish.DirectPruning,
        vanish.Incremental,
        vanish_algorithm.Calculator,
    ],
)
def test_retained_intermediate_occupancy_does_not_cover_a_quality_use(
    implementation: type[vanish.Collector | vanish_algorithm.Calculator],
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
    calculator = algorithm.Calculator()
    collector = implementation(calculator.graph)
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
    for occurrence, step in enumerate(steps):
        if occurrence == 2:
            calculator.retain({1: 10, 2: 20})
        assert calculator.add(step.operation) == occurrence
        if isinstance(collector, vanish_algorithm.Calculator):
            collector.observe(
                occurrence,
                step.operation.creators,
                step.moved,
                step.vacated,
                step.ordinary_occupants,
            )
        else:
            collector.observe(occurrence, step.particles, step.vacated)
    result = collector.finish()
    assert set(calculator.graph.dependencies(result[0])) == {3, 5}
    assert set(calculator.graph.dependencies(result[1])) == {2, 5}
    assert set(calculator.graph.dependencies(result[4])) == {5}
