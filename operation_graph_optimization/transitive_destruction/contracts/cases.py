"""Independent source cases, modular plans, and observable particle operations."""

from __future__ import annotations

import dataclasses
import functools
import threading
from typing import final

from operation_graph_optimization import algorithm, vanish_workloads
from operation_graph_optimization.transitive_destruction import experiment
from operation_graph_optimization.transitive_destruction.contracts import planning


@dataclasses.dataclass(frozen=True)
class Effect:
    """An operation on original particle and position identities."""

    kind: str
    particle: int
    source: int | None = None
    target: int | None = None
    required: tuple[int, ...] = ()


@final
class State:
    """Check actual access to original particles after transitive selection."""

    def __init__(self):
        """Keep particle identities separate from their occupied positions."""
        self.alive: set[int] = set()
        self.positions: dict[int, int] = {}
        self.lock = threading.Lock()

    def apply(self, effect: Effect):
        """Execute one source-derived operation, raising on invalid lifetime access."""
        with self.lock:
            if not set(effect.required) <= self.alive:
                raise ValueError("Operation requires a particle that is not alive")
            if effect.kind == "create":
                if effect.target is None or effect.target in self.positions:
                    raise ValueError("Create requires an empty target")
                self.positions[effect.target] = effect.particle
                self.alive.add(effect.particle)
            elif effect.kind == "move":
                if (
                    effect.source is None
                    or self.positions[effect.source] != effect.particle
                ):
                    raise ValueError("Move requires its original particle")
                if effect.target is None or effect.target in self.positions:
                    raise ValueError("Move requires an empty target")
                del self.positions[effect.source]
                self.positions[effect.target] = effect.particle
            elif effect.kind == "vacate":
                if (
                    effect.source is None
                    or self.positions.pop(effect.source) != effect.particle
                ):
                    raise ValueError("Vacate requires its original particle")
                self.alive.remove(effect.particle)
            elif effect.kind == "vanish":
                self.alive.remove(effect.particle)
            elif effect.kind != "selection":
                raise ValueError("Unknown experimental operation")


@dataclasses.dataclass
class Case:
    """A fixed callee can be used with different caller-only destructor knowledge."""

    source: str
    scenario: experiment.Scenario
    labels: dict[int, str]
    effects: dict[str, Effect]
    width: int
    active: tuple[int, ...]


def make_case(width: int, active: tuple[int, ...]) -> Case:
    """Construct valid source and separately describe its resolved operations."""
    names = [f"branch{i}" for i in range(width)]
    definitions = "\n".join(
        f"define the potential position<my.domain.com:my_lib:/{name}>."
        for name in names
    )
    constraints = "\n".join(f"        it has the position</{name}>." for name in names)
    implied = "\n".join(
        f"    it also assigns the position</branch{i}>." for i in active
    )
    destructor_body: list[str] = []
    for i in active:
        destructor_body.extend(
            [
                f"        define the position<temporary{i}>.",
                f"        move the particle in position</branch{i}> to position<temporary{i}>.",
                f"        move the particle in position<temporary{i}> to position</branch{i}>.",
            ]
        )
    destructor_definition = ""
    destructor_constraint = ""
    if active:
        destructor_definition = f"""define the potential action<my.domain.com:my_lib:/cleanup> {{
{implied}
    it happens when {{
        this particle is being destroyed.
    }} and it does {{
{chr(10).join(destructor_body)}
    }}
}}
"""
        destructor_constraint = "                it has the action</cleanup>."
    callee_body: list[str] = []
    fills: list[str] = []
    for i in range(width):
        callee_body.extend(
            [
                f"        define the position<temporary{i}>.",
                f"        move the particle in position<input>::position</child>::position</branch{i}> to position<temporary{i}>.",
                f"        move the particle in position<temporary{i}> to position<input>::position</child>::position</branch{i}>.",
            ]
        )
        fills.append(
            f"        create a particle in position<child_source>::position</branch{i}>."
        )
    source = f"""{definitions}
define the potential position<my.domain.com:my_lib:/child> {{
    it may only contain particles where {{
{constraints}
    }}
}}
{destructor_definition}define the potential action<my.domain.com:my_lib:/destroyer> {{
    define the position<input> {{
        it may only contain particles where {{
            it has the position</child>.
        }}
    }}
    it happens when {{
        the position<input> has a particle.
    }} and it does {{
{chr(10).join(callee_body)}
        destroy the particle in position<input>.
    }}
}}
define the potential action<my.domain.com:my_lib:/test> {{
    it also assigns the action</destroyer>.
    it happens when {{
        this particle is created.
    }} and it does {{
        define the position<parent> {{
            it may only contain particles where {{
                it has the position</child>.
            }}
        }}
        define the position<child_source> {{
            it may only contain particles where {{
{constraints}
{destructor_constraint}
            }}
        }}
        create a particle in position<parent>.
        create a particle in position<child_source>.
{chr(10).join(fills)}
        move the particle in position<child_source> to position<parent>::position</child>.
        move the particle in position<parent> to action</destroyer>::position<input>.
    }}
}}
"""
    labels: dict[int, str] = {}
    effects: dict[str, Effect] = {}
    operations: list[algorithm.Operation] = []

    def append(name: str, operation: algorithm.Operation, effect: Effect):
        labels[len(operations)] = name
        operations.append(operation)
        effects[name] = effect

    append(
        "owner",
        algorithm.Operation(fill=99, defines=(10,)),
        Effect("create", 0, target=99),
    )
    append(
        "parent",
        algorithm.Operation(fill=0, defines=(1,)),
        Effect("create", 1, target=0),
    )
    positions = tuple(100 + i for i in range(width))
    append(
        "child",
        algorithm.Operation(fill=2, defines=positions),
        Effect("create", 2, target=2),
    )
    for i in range(width):
        append(
            f"create{i}",
            algorithm.Operation(occupied=(2,), fill=100 + i, creators=(2,)),
            Effect("create", 3 + i, target=100 + i, required=(2,)),
        )
    append(
        "place_child",
        algorithm.Operation(occupied=(0,), empty=2, fill=1, creators=(1,)),
        Effect("move", 2, source=2, target=1, required=(1, 2)),
    )
    append(
        "call",
        algorithm.Operation(empty=0, fill=10, creators=(0,)),
        Effect("move", 1, source=0, target=10, required=(0, 1)),
    )
    for i in range(width):
        append(
            f"callee_out{i}",
            algorithm.Operation(
                occupied=(10, 1), empty=100 + i, fill=200 + i, creators=(0, 1, 2)
            ),
            Effect(
                "move", 3 + i, source=100 + i, target=200 + i, required=(0, 1, 2, 3 + i)
            ),
        )
        append(
            f"callee_back{i}",
            algorithm.Operation(
                occupied=(10, 1), empty=200 + i, fill=100 + i, creators=(0, 1, 2)
            ),
            Effect(
                "move", 3 + i, source=200 + i, target=100 + i, required=(0, 1, 2, 3 + i)
            ),
        )
    selection = len(operations)
    append(
        "vacate_parent",
        algorithm.Operation(empty=10, creators=(0,)),
        Effect("vacate", 1, source=10, required=(0, 1)),
    )
    append("vacate_child", algorithm.Operation(empty=1), Effect("selection", 2))
    for i in range(width):
        append(
            f"vacate{i}", algorithm.Operation(empty=100 + i), Effect("selection", 3 + i)
        )
    steps = vanish_workloads.resolve(operations)
    retentions = {1: 1000}
    for i in range(width):
        retentions[100 + i] = 1100 + i
    for i in active:
        labels[len(steps)] = f"destructor_out{i}"
        steps.append(
            vanish_workloads.Step(
                algorithm.Operation(empty=1100 + i, fill=300 + i, creators=(2,)),
                (2, 3 + i),
                None,
                3 + i,
            )
        )
        effects[f"destructor_out{i}"] = Effect(
            "move", 3 + i, source=100 + i, target=300 + i, required=(2, 3 + i)
        )
        labels[len(steps)] = f"destructor_back{i}"
        steps.append(
            vanish_workloads.Step(
                algorithm.Operation(empty=300 + i, fill=1100 + i, creators=(2,)),
                (2, 3 + i),
                None,
                3 + i,
            )
        )
        effects[f"destructor_back{i}"] = Effect(
            "move", 3 + i, source=300 + i, target=100 + i, required=(2, 3 + i)
        )
    effects["vanish_child"] = Effect("vanish", 2)
    for i in range(width):
        effects[f"vanish{i}"] = Effect("vanish", 3 + i)
    transitive = set(range(selection + 1, selection + width + 2))
    return Case(
        source,
        experiment.Scenario(steps, transitive, {selection: retentions}),
        labels,
        effects,
        width,
        active,
    )


def callee_plan(width: int) -> planning.Plan:
    """Compile the callee without knowing any caller's additional destructors."""
    inputs = tuple(f"start{i}" for i in range(width))
    operations: list[planning.Operation] = []
    for i in range(width):
        operations.append(planning.Operation(f"callee_out{i}", (f"start{i}",)))
        operations.append(planning.Operation(f"callee_back{i}", (f"callee_out{i}",)))
    ends = tuple(f"callee_back{i}" for i in range(width))
    operations.append(planning.Operation("vacate_parent", ends))
    return planning.compile_plan(inputs, tuple(operations), (*ends, "vacate_parent"))


@dataclasses.dataclass(frozen=True)
class Plans:
    """Caller-specific wiring around an unchanged callee plan."""

    prefix: planning.Plan
    callee: planning.Plan
    forwarding: planning.Plan
    destructors: tuple[planning.Plan, ...]
    lifetime: planning.Plan
    hook: planning.Plan | None


def compile_caller(
    case: Case, callee: planning.Plan, *, shared_hook: bool = False
) -> Plans:
    """Derive caller wiring from its own knowledge and direct-callee exports."""
    width = case.width
    prefix = [planning.Operation(name, ()) for name in ("owner", "parent", "child")]
    prefix.extend(planning.Operation(f"create{i}", ("child",)) for i in range(width))
    prefix.append(
        planning.Operation(
            "place_child", ("parent", *tuple(f"create{i}" for i in range(width)))
        )
    )
    prefix.append(planning.Operation("call", ("owner", "place_child")))
    prefix_plan = planning.compile_plan((), tuple(prefix), ("call",))
    names = tuple(f"ready{i}" for i in range(width))
    forwarding = planning.compile_plan((*names, "vacated"), (), (*names, "vacated"))
    hook = None
    if shared_hook and case.active:
        hook = planning.compile_plan(
            names, (planning.Operation("vacate_child", names),), ("vacate_child",)
        )
    destructors: list[planning.Plan] = []
    for i in case.active:
        destructor = planning.compile_plan(
            ("ready",),
            (
                planning.Operation(f"destructor_out{i}", ("ready",)),
                planning.Operation(f"destructor_back{i}", (f"destructor_out{i}",)),
            ),
            (f"destructor_back{i}",),
        )
        destructors.append(destructor)
    terminal = [planning.Operation("vanish_child", names)]
    terminal.extend(
        planning.Operation(f"vanish{i}", (f"ready{i}",)) for i in range(width)
    )
    lifetime = planning.compile_plan(names, tuple(terminal), ())
    return Plans(prefix_plan, callee, forwarding, tuple(destructors), lifetime, hook)


def assemble(
    case: Case, plans: Plans, *, depth: int = 0, prefix: str = ""
) -> tuple[list[planning.Task], State]:
    """Connect local plans using direct-callee exports, never a flattened graph."""
    width = case.width
    state = State()
    actions = {
        name: functools.partial(state.apply, effect)
        for name, effect in case.effects.items()
    }
    tasks: list[planning.Task] = []
    supplied = planning.instantiate(plans.prefix, (), prefix, actions, tasks)[0]
    connections = planning.instantiate(
        plans.callee, tuple(supplied for _ in range(width)), prefix, actions, tasks
    )
    for _ in range(depth):
        connections = planning.instantiate(
            plans.forwarding, connections, prefix, {}, tasks
        )
    prerequisites = list(connections[:width])
    if plans.hook is not None:
        shared = planning.instantiate(
            plans.hook, tuple(prerequisites), prefix, actions, tasks
        )[0]
        prerequisites = [shared for _ in range(width)]
    completions = list(connections[:width])
    for i, destructor in zip(case.active, plans.destructors, strict=True):
        completions[i] = planning.instantiate(
            destructor, (prerequisites[i],), prefix, actions, tasks
        )[0]
    _ = planning.instantiate(plans.lifetime, tuple(completions), prefix, actions, tasks)
    return tasks, state


def expected(case: Case) -> dict[str, set[str]]:
    """Obtain the independent whole-program oracle only after assembling plans."""
    prepared = experiment.prepare(case.scenario)
    calculated, vanishes = experiment.construct(prepared)
    names = {new: case.labels[old] for old, new in prepared.occurrences.items()}
    for particle, vanish in vanishes.items():
        if vanish >= len(prepared.operations):
            names[vanish] = "vanish_child" if particle == 2 else f"vanish{particle - 3}"
    result: dict[str, set[str]] = {}
    for occurrence, name in names.items():
        result[name] = {names[p] for p in calculated.graph.dependencies(occurrence)}
    return result
