"""Derive contract interfaces from action descriptions and resolved position state."""

from __future__ import annotations

import dataclasses
from typing import Literal, final

from operation_graph_optimization import algorithm as position_algorithm
from operation_graph_optimization import vanish_workloads
from operation_graph_optimization.complete import algorithm, graph
from operation_graph_optimization.transitive_destruction.interfaces import descriptions

type Variant = Literal["explicit", "lowered", "records"]


@dataclasses.dataclass(frozen=True)
class Template:
    """A caller-independent action recipe and mechanically derived interface."""

    action: descriptions.Action
    positions: tuple[int, ...]
    callees: tuple[Template, ...]


def compile_action(action: descriptions.Action) -> Template:
    """Derive the position interface, never selecting producer operations by hand."""
    compiled: dict[int, Template] = {}

    def visit(current: descriptions.Action) -> Template:
        identity = id(current)
        if identity in compiled:
            return compiled[identity]
        known = set(current.known)
        callees: list[Template] = []
        for statement in current.statements:
            if isinstance(statement, descriptions.Call):
                callee = visit(statement.action)
                callees.append(callee)
                known.update(callee.positions)
        template = Template(current, tuple(sorted(known)), tuple(callees))
        compiled[identity] = template
        return template

    return visit(action)


@dataclasses.dataclass
class Position:
    """The state needed by Collection, distinct from any child Vacate."""

    setter: int | None
    parent: int | None = None
    occupant: int | None = None
    readers: set[int] = dataclasses.field(default_factory=set)

    def copy(self) -> Position:
        """Keep destruction-time state independent from later ordinary vacancy."""
        return Position(self.setter, self.parent, self.occupant, self.readers.copy())


@dataclasses.dataclass
class Particle:
    """Known assigned positions and the requirements needed to finish its Vanish."""

    children: tuple[int, ...]
    uses: set[int]
    moved: int | None


@dataclasses.dataclass
class Contract:
    """Position-specific state plus optional explicit child Vacate identities."""

    positions: dict[int, Position]
    selected: dict[int, int]
    particles: dict[int, Particle]
    vacates: dict[int, int] = dataclasses.field(default_factory=dict)
    requirements: dict[int, set[int]] = dataclasses.field(default_factory=dict)

    def incorporate(self, callee: Contract):
        """Combine caller-only facts with the direct callee's destruction state."""
        self.positions.update(callee.positions)
        self.selected.update(callee.selected)
        self.vacates.update(callee.vacates)
        self.requirements.update(callee.requirements)
        for particle, information in callee.particles.items():
            prior = self.particles.get(particle)
            if prior is None:
                self.particles[particle] = information
            else:
                children = tuple(
                    sorted(set(prior.children) | set(information.children))
                )
                moved = (
                    information.moved if information.moved is not None else prior.moved
                )
                self.particles[particle] = Particle(
                    children, prior.uses | information.uses, moved
                )


@dataclasses.dataclass
class Result:
    """Measured graphs, interface counts, and independently resolvable oracle input."""

    graph: graph.Graph
    labels: list[str]
    children: set[int]
    steps: list[vanish_workloads.Step]
    step_labels: list[str]
    retentions: dict[int, dict[int, int]]
    vacates: dict[int, int]
    vanishes: dict[int, int]
    contract: Contract
    template: Template
    analysis_nodes: int
    boundary_records: int
    boundary_references: int


@final
class Builder:
    """Bind local recipes to position records and apply Collection and Comparison."""

    def __init__(self, variant: Variant):
        """Keep identical semantic processing across the three interface choices."""
        self.variant = variant
        self.graph = graph.Graph()
        self.labels: list[str] = []
        self.positions: dict[int, Position] = {0: Position(None)}
        self.children: dict[int, tuple[int, ...]] = {}
        self.uses: dict[int, set[int]] = {}
        self.moves: dict[int, int] = {}
        self.vacates: dict[int, int] = {}
        self.selection_requirements: dict[int, set[int]] = {}
        self.child_nodes: set[int] = set()
        self.steps: list[vanish_workloads.Step] = []
        self.step_labels: list[str] = []
        self.operation_to_step: dict[int, int] = {}
        self.retentions: dict[int, dict[int, int]] = {}
        self.retained: dict[int, int] = {}
        self.direct_step: int | None = None
        self.boundary_records = 0
        self.boundary_references = 0

    def append(self, label: str, candidates: set[int]) -> int:
        """Apply the existing Comparison rule before constructing this node."""
        operation = self.graph.append(algorithm.compare(self.graph, candidates))
        self.labels.append(label)
        return operation

    def operation(
        self,
        statement: descriptions.Create | descriptions.Move | descriptions.Select,
        states: dict[int, Position],
        label: str,
        *,
        destructor: bool = False,
    ) -> int:
        """Derive actual requirements from references, not from supplied edges."""
        source = (
            None if isinstance(statement, descriptions.Create) else statement.source
        )
        target = (
            None if isinstance(statement, descriptions.Select) else statement.target
        )
        references: list[descriptions.Reference] = []
        if source is not None:
            references.append(source)
        if target is not None:
            references.append(target)
        intermediates: set[int] = set()
        parents: set[int] = set()
        for reference in references:
            intermediates.update(reference.intermediate)
            for position in (*reference.intermediate, reference.position):
                parent = states[position].parent
                if parent is not None:
                    parents.add(parent)
            for position in reference.intermediate:
                if states[position].occupant is None:
                    raise ValueError(
                        "Reference requires an occupied intermediate position"
                    )
        candidates = set(parents)
        for position in intermediates:
            setter = states[position].setter
            if setter is not None:
                candidates.add(setter)
        if target is not None:
            state = states[target.position]
            if state.occupant is not None:
                raise ValueError("Target must be empty")
            if state.setter is not None:
                candidates.add(state.setter)
        moved = None
        if source is not None:
            state = states[source.position]
            if state.occupant is None:
                raise ValueError("Source must be occupied")
            moved = state.occupant
            if state.readers:
                candidates.update(state.readers)
            elif state.setter is not None:
                candidates.add(state.setter)
        occurrence = self.append(label, candidates)
        self.operation_to_step[occurrence] = len(self.steps)
        observed = tuple(states[p].occupant for p in sorted(intermediates))
        for parent in parents:
            uses = self.uses.setdefault(parent, set())
            uses.difference_update(candidates)
            uses.add(occurrence)
        for position in intermediates:
            states[position].readers.difference_update(candidates)
            states[position].readers.add(occurrence)
        if source is not None:
            state = states[source.position]
            state.occupant = None
            state.setter = occurrence
            state.readers.clear()
        if target is not None:
            state = states[target.position]
            state.occupant = occurrence if moved is None else moved
            state.setter = occurrence
            state.readers.clear()
        defines = ()
        if isinstance(statement, descriptions.Create):
            defines = statement.children
            self.children[occurrence] = defines
            for position in defines:
                states[position] = Position(occurrence, occurrence)
        if isinstance(statement, descriptions.Move):
            assert moved is not None  # noqa: S101 - Move requires a particle.
            self.moves[moved] = occurrence
        if isinstance(statement, descriptions.Select):
            assert moved is not None  # noqa: S101 - Selection requires a particle.
            self.vacates[moved] = occurrence
        aliases = self.retained if destructor else {}
        occupied_steps: list[int] = []
        for particle in observed:
            assert particle is not None  # noqa: S101 - References checked above.
            occupied_steps.append(self.operation_to_step[particle])
        creators = tuple(self.operation_to_step[parent] for parent in parents)
        empty = (
            None if source is None else aliases.get(source.position, source.position)
        )
        fill = None if target is None else aliases.get(target.position, target.position)
        vacated = (
            self.operation_to_step[moved]
            if isinstance(statement, descriptions.Select) and moved is not None
            else None
        )
        moved_step = (
            self.operation_to_step[moved]
            if isinstance(statement, descriptions.Move) and moved is not None
            else None
        )
        self.steps.append(
            vanish_workloads.Step(
                position_algorithm.Operation(
                    occupied=tuple(aliases.get(p, p) for p in sorted(intermediates)),
                    fill=fill,
                    empty=empty,
                    creators=creators,
                    defines=defines,
                ),
                creators,
                vacated,
                moved_step,
                tuple(occupied_steps),
            )
        )
        self.step_labels.append(label)
        return occurrence

    def capture(self, template: Template, states: dict[int, Position]) -> Contract:
        """Expose all known position facts rather than guessing future consumers."""
        records: dict[int, Position] = {}
        required: set[int] = set()
        for position in template.positions:
            state = states[position]
            records[position] = state.copy()
            if state.parent is not None:
                required.add(state.parent)
            if state.occupant is not None:
                required.add(state.occupant)
            self.boundary_references += len(state.readers) + (state.setter is not None)
        particles: dict[int, Particle] = {}
        for particle in required:
            children = tuple(p for p in self.children[particle] if p in records)
            uses = self.uses.get(particle, set()).copy()
            moved = self.moves.get(particle)
            particles[particle] = Particle(children, uses, moved)
            self.boundary_references += len(uses) + (moved is not None)
        self.boundary_records += len(records) + len(particles)
        return Contract(records, {}, particles)

    def execute(
        self,
        template: Template,
        states: dict[int, Position],
        *,
        destructor: bool = False,
        path: str = "",
    ) -> Contract | None:
        """Use only the direct callee's returned records at each call boundary."""
        contract = None
        callees = iter(template.callees)
        for index, statement in enumerate(template.action.statements):
            label = f"{path}{template.action.name}.{index}"
            if isinstance(statement, descriptions.Call):
                callee = next(callees)
                supplied = {p: states[p] for p in callee.positions}
                contract = self.execute(
                    callee, supplied, destructor=destructor, path=label + "/"
                )
                states.update(supplied)
                if contract is not None:
                    expanded = self.capture(template, states)
                    expanded.incorporate(contract)
                    contract = expanded
            elif isinstance(statement, descriptions.Select):
                contract = self.capture(template, states)
                self.select(statement, states, label, contract)
            else:
                _ = self.operation(statement, states, label, destructor=destructor)
        return contract

    def select(
        self,
        statement: descriptions.Select,
        states: dict[int, Position],
        label: str,
        contract: Contract,
    ):
        """Keep original occupancy available for destructor contract resolution."""
        position = statement.source.position
        particle = states[position].occupant
        assert particle is not None  # noqa: S101 - Valid selection.
        contract.selected[position] = particle
        vacate = self.operation(statement, states, label)
        contract.vacates[particle] = vacate
        self.direct_step = self.operation_to_step[vacate]
        self.expand_selection(contract)

    def expand_selection(self, contract: Contract):
        """Resolve precisely the child positions known at this contract boundary."""
        pending = list(contract.selected.values())
        selected = dict(contract.selected)
        while pending:
            particle = pending.pop()
            for position in contract.particles[particle].children:
                child = contract.positions[position].occupant
                if child is not None and position not in selected:
                    selected[position] = child
                    pending.append(child)
        contract.selected = selected
        for position, particle in selected.items():
            if particle in contract.vacates or particle in contract.requirements:
                continue
            state = contract.positions[position]
            candidates = state.readers.copy()
            if not candidates and state.setter is not None:
                candidates.add(state.setter)
            if self.variant != "records":
                vacate = self.append(f"child_vacate.{position}", candidates)
                self.child_nodes.add(vacate)
                contract.vacates[particle] = vacate
            else:
                contract.requirements[particle] = candidates
            self.steps.append(
                vanish_workloads.Step(
                    position_algorithm.Operation(empty=position),
                    (),
                    self.operation_to_step[particle],
                )
            )
            self.step_labels.append(f"child_vacate.{position}")

    def finish_selection(self, contract: Contract):
        """Resume from serialized contract facts, discarding private callee state."""
        self.expand_selection(contract)
        self.uses = {
            p: information.uses.copy() for p, information in contract.particles.items()
        }
        self.moves = {}
        for particle, information in contract.particles.items():
            if information.moved is not None:
                self.moves[particle] = information.moved
        self.vacates = contract.vacates.copy()
        self.selection_requirements = contract.requirements.copy()
        self.children.clear()
        self.positions.clear()
        for position in contract.positions:
            self.retained[position] = position + 1_000_000
        # Only the oracle replays the old Vacates against retained position states.
        assert self.direct_step is not None  # noqa: S101 - Selection already occurred.
        self.retentions[self.direct_step] = self.retained.copy()

    def finish(self, contract: Contract) -> dict[int, int]:
        """Construct terminal Vanishes using the existing candidate Comparison."""
        vanishes: dict[int, int] = {}
        for particle in contract.selected.values():
            candidates = self.uses.get(particle, set()).copy()
            candidates.add(particle)
            if particle in self.moves:
                candidates.add(self.moves[particle])
            if particle in self.vacates:
                candidates.add(self.vacates[particle])
            else:
                candidates.update(self.selection_requirements[particle])
            vanishes[particle] = self.append(
                f"vanish.{self.operation_to_step[particle]}", candidates
            )
        return vanishes


def construct(
    program: descriptions.Program, variant: Variant, template: Template | None = None
) -> Result:
    """Build from local descriptions; the independent oracle is never consulted."""
    builder = Builder(variant)
    setup = compile_action(program.setup)
    _ = builder.execute(setup, builder.positions)
    caller = builder.capture(setup, builder.positions)
    if template is None:
        template = compile_action(program.callee)
    supplied = {p: builder.positions[p] for p in template.positions}
    contract = builder.execute(template, supplied)
    assert contract is not None  # noqa: S101 - Programs end in selection.
    caller.incorporate(contract)
    contract = caller
    # No private callee lifetime/occupancy state may substitute for its interface.
    builder.positions.clear()
    builder.children.clear()
    builder.uses.clear()
    builder.moves.clear()
    builder.vacates.clear()
    builder.selection_requirements.clear()
    builder.finish_selection(contract)
    for destructor in program.destructors:
        plan = compile_action(destructor)
        states = {p: contract.positions[p] for p in plan.positions}
        _ = builder.execute(plan, states, destructor=True)
        contract.positions.update(states)
    vanishes = builder.finish(contract)
    analysis_nodes = len(builder.labels)
    calculated = builder.graph
    labels = builder.labels
    if variant == "lowered":
        calculated = graph.Graph()
        labels: list[str] = []
        replacements: dict[int, set[int]] = {}
        rewritten: dict[int, int] = {}
        for operation, label in enumerate(builder.labels):
            candidates: set[int] = set()
            for previous in builder.graph.dependencies(operation):
                candidates.update(replacements[previous])
            if operation in builder.child_nodes:
                replacements[operation] = candidates
                continue
            # Child Vacates only feed Vanishes in this model. Apply Vanish
            # Comparison to the substituted candidates before emitting edges.
            dependencies = (
                algorithm.compare(calculated, candidates)
                if label.startswith("vanish.")
                else list(candidates)
            )
            new = calculated.append(dependencies)
            labels.append(label)
            replacements[operation] = {new}
            rewritten[operation] = new
        vanishes = {
            particle: rewritten[operation] for particle, operation in vanishes.items()
        }
    return Result(
        calculated,
        labels,
        builder.child_nodes,
        builder.steps,
        builder.step_labels,
        builder.retentions,
        builder.vacates,
        vanishes,
        contract,
        template,
        analysis_nodes,
        builder.boundary_records,
        builder.boundary_references,
    )
