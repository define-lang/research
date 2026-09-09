from __future__ import annotations

from typing import cast

import pytest

from define.compiler import driver
from operation_graph_optimization import algorithm, vanish_workloads
from operation_graph_optimization.transitive_destruction import experiment


@pytest.fixture(params=[False, True], autouse=True)
def selection_strategy(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    original = experiment.verify

    def verify(scenario: experiment.Scenario):
        original(scenario, snapshot_selection=cast("bool", request.param))

    monkeypatch.setattr(experiment, "verify", verify)


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("width", [1, 4, 16])
@pytest.mark.parametrize("implied", [False, True])
def test_random_cascades(seed: int, width: int, *, implied: bool):
    experiment.verify(experiment.cascade(seed, 300, width, implied=implied))


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("width", [1, 4, 16])
def test_random_shared_destructor_moves(seed: int, width: int):
    experiment.verify(experiment.retained(seed, 80, width))


@pytest.mark.parametrize("explicit_child", [False, True])
@pytest.mark.parametrize("destructor", [False, True])
def test_real_source_direct_and_transitive_destruction(
    *, explicit_child: bool, destructor: bool
):
    destructor_definition = ""
    destructor_constraint = ""
    if destructor:
        destructor_definition = """define the potential action<my.domain.com:my_lib:/cleanup> {
    it also assigns the position</child>.
    it happens when {
        this particle is being destroyed.
    } and it does {
        define the position<temporary>.
        move the particle in position</child> to position<temporary>.
        move the particle in position<temporary> to position</child>.
    }
}
"""
        destructor_constraint = "                it has the action</cleanup>."
    destroy_statement = "        destroy the particle in position<parent>."
    if explicit_child:
        destroy_statement = (
            "        destroy the particle in position<parent>::position</child>."
        )
    # The destructor is assigned only when its occupied-child requirement holds.
    if explicit_child and destructor:
        destructor_constraint = ""
    source = f"""define the potential position<my.domain.com:my_lib:/leaf>.
define the potential position<my.domain.com:my_lib:/child> {{
    it may only contain particles where {{
        it has the position</leaf>.
    }}
}}
{destructor_definition}define the potential action<my.domain.com:my_lib:/test> {{
    it happens when {{
        this particle is created.
    }} and it does {{
        define the position<parent> {{
            it may only contain particles where {{
                it has the position</child>.
{destructor_constraint}
            }}
        }}
        create a particle in position<parent>.
        create a particle in position<parent>::position</child>.
        create a particle in position<parent>::position</child>::position</leaf>.
{destroy_statement}
    }}
}}
"""
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    operations = [
        algorithm.Operation(fill=0, defines=(1,)),
        algorithm.Operation(occupied=(0,), fill=1, creators=(0,), defines=(2,)),
        algorithm.Operation(occupied=(0, 1), fill=2, creators=(0, 1)),
    ]
    if explicit_child:
        operations.extend(
            [
                algorithm.Operation(occupied=(0,), empty=1, creators=(0,)),
                algorithm.Operation(empty=2),
                algorithm.Operation(empty=0),
            ]
        )
        transitive = {4}
    else:
        operations.extend(algorithm.Operation(empty=p) for p in (0, 1, 2))
        transitive = {4, 5}
    steps = vanish_workloads.resolve(operations)
    retentions: dict[int, dict[int, int]] = {}
    if destructor and not explicit_child:
        retentions = {3: {1: 10, 2: 20}}
        steps.extend(
            [
                vanish_workloads.Step(
                    algorithm.Operation(empty=10, fill=30, creators=(0,)),
                    (0, 1),
                    None,
                    1,
                ),
                vanish_workloads.Step(
                    algorithm.Operation(empty=30, fill=10, creators=(0,)),
                    (0, 1),
                    None,
                    1,
                ),
            ]
        )
    experiment.verify(experiment.Scenario(steps, transitive, retentions))


@pytest.mark.parametrize("forward", [False, True])
@pytest.mark.parametrize("repetitions", [1, 2])
def test_real_source_caller_contributes_child_and_destructor(
    repetitions: int, *, forward: bool
):
    forwarding = (
        """define the potential action<my.domain.com:my_lib:/forward> {
    it also assigns the action</destroyer>.
    define the position<input>.
    it happens when {
        the position<input> has a particle.
    } and it does {
        move the particle in position<input> to action</destroyer>::position<input>.
    }
}
"""
        if forward
        else ""
    )
    action = "forward" if forward else "destroyer"
    call = f"""        create a particle in position<parent>.
        create a particle in position<parent>::position</child>.
        move the particle in position<parent> to action</{action}>::position<input>.
"""
    source = f"""define the potential position<my.domain.com:my_lib:/child>.
define the potential action<my.domain.com:my_lib:/cleanup> {{
    it also assigns the position</child>.
    it happens when {{
        this particle is being destroyed.
    }} and it does {{
        define the position<temporary>.
        move the particle in position</child> to position<temporary>.
        move the particle in position<temporary> to position</child>.
    }}
}}
define the potential action<my.domain.com:my_lib:/destroyer> {{
    define the position<input>.
    it happens when {{
        the position<input> has a particle.
    }} and it does {{
        destroy the particle in position<input>.
    }}
}}
{forwarding}define the potential action<my.domain.com:my_lib:/test> {{
    it also assigns the action</{action}>.
    it happens when {{
        this particle is created.
    }} and it does {{
        define the position<parent> {{
            it may only contain particles where {{
                it has the position</child>.
                it has the action</cleanup>.
            }}
        }}
{call * repetitions}
    }}
}}
"""
    validated = driver.Driver().validate_source(source).program_validation
    assert validated.all_exceptions == []
    assert validated.all_diagnostics == []
    steps = [
        vanish_workloads.Step(algorithm.Operation(fill=99, defines=(10, 12)), (), None)
    ]
    transitive: set[int] = set()
    retentions: dict[int, dict[int, int]] = {}
    for repetition in range(repetitions):
        parent = len(steps)
        child = parent + 1
        position = 100 * repetition + 1
        preserved = position + 20
        temporary = position + 30
        steps.extend(
            [
                vanish_workloads.Step(
                    algorithm.Operation(fill=0, defines=(position,)), (), None
                ),
                vanish_workloads.Step(
                    algorithm.Operation(
                        occupied=(0,), fill=position, creators=(parent,)
                    ),
                    (parent,),
                    None,
                    ordinary_occupants=(parent,),
                ),
                vanish_workloads.Step(
                    algorithm.Operation(empty=0, fill=10, creators=(0,)),
                    (0, parent),
                    None,
                    parent,
                ),
            ]
        )
        if forward:
            steps.append(
                vanish_workloads.Step(
                    algorithm.Operation(empty=10, fill=12, creators=(0,)),
                    (0, parent),
                    None,
                    parent,
                )
            )
        selection = len(steps)
        retentions[selection] = {position: preserved}
        transitive.add(selection + 1)
        steps.extend(
            [
                vanish_workloads.Step(
                    algorithm.Operation(empty=12 if forward else 10, creators=(0,)),
                    (0,),
                    parent,
                ),
                vanish_workloads.Step(algorithm.Operation(empty=position), (), child),
                vanish_workloads.Step(
                    algorithm.Operation(
                        empty=preserved, fill=temporary, creators=(parent,)
                    ),
                    (parent, child),
                    None,
                    child,
                ),
                vanish_workloads.Step(
                    algorithm.Operation(
                        empty=temporary, fill=preserved, creators=(parent,)
                    ),
                    (parent, child),
                    None,
                    child,
                ),
            ]
        )
    experiment.verify(experiment.Scenario(steps, transitive, retentions))


def test_real_source_constructor_child_create_can_outlive_parent_vanish():
    source = """define the potential position<my.domain.com:my_lib:/leaf>.
define the potential action<my.domain.com:my_lib:/make_leaf> {
    it also assigns the position</leaf>.
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position</leaf>.
    }
}
define the potential position<my.domain.com:my_lib:/child> {
    it may only contain particles where {
        it has the action</make_leaf>.
    }
}
define the potential action<my.domain.com:my_lib:/test> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<parent> {
            it may only contain particles where {
                it has the position</child>.
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
    operations = [
        algorithm.Operation(fill=0, defines=(1,)),
        algorithm.Operation(occupied=(0,), fill=1, creators=(0,), defines=(2,)),
        algorithm.Operation(fill=2, creators=(1,)),
        algorithm.Operation(empty=0),
        algorithm.Operation(empty=1),
        algorithm.Operation(empty=2),
    ]
    scenario = experiment.Scenario(vanish_workloads.resolve(operations), {4, 5})
    experiment.verify(scenario)
    calculated, vanishes = experiment.construct(experiment.prepare(scenario))
    assert not calculated.graph.reaches(vanishes[0], 2)
    assert not calculated.graph.reaches(2, vanishes[0])
    assert calculated.graph.reaches(vanishes[1], 2)
