"""State, per-particle contract, and propagation-history benchmark consumers."""

from __future__ import annotations

import abc
import typing
from dataclasses import dataclass

from destruction_contract_benchmarks import snapshots, workloads


@dataclass(frozen=True, slots=True)
class Reads:
    """Observable work that must agree across storage variants."""

    checksum: int = 0
    count: int = 0
    parent_lookups: int = 0


def score(occupancy: snapshots.Occupancy | None) -> int:
    """Include diagnostic source identity as well as occupancy in comparisons."""
    if occupancy is None:
        return 7
    return occupancy.state * 13 + occupancy.fill_site


class Experiment(abc.ABC):
    """One prepared input with separately measurable construction and reads."""

    @abc.abstractmethod
    def build(self) -> None:
        """Construct and retain summaries needed by later callers."""
        raise NotImplementedError

    @abc.abstractmethod
    def query(self) -> Reads:
        """Read requirement state or diagnostic propagation history."""
        raise NotImplementedError

    def traverse(self) -> Reads:
        """Perform bulk Child State enumeration when the workload needs it."""
        return Reads()

    @abc.abstractmethod
    def dimensions(self) -> dict[str, int]:
        """Describe the amount of input and retained analysis."""
        raise NotImplementedError


@typing.final
class StateExperiment(Experiment):
    """Compare shared-state composition and lookup across retained callers."""

    def __init__(self, workload: workloads.Workload, factory: snapshots.Factory):
        """Prepare equivalent program inputs for one snapshot implementation."""
        self.workload = workload
        self.factory = factory
        self.histories: list[list[snapshots.Snapshot]] = []

    @typing.override
    def build(self):
        for _ in range(self.workload.configuration.copies):
            history = [self.factory(self.workload.initial)]
            for caller in self.workload.callers:
                history.append(history[caller.callee].with_caller(caller.knowledge))
            self.histories.append(history)

    @typing.override
    def query(self) -> Reads:
        checksum = 0
        lookups = 0
        parent_lookups = 0
        for _ in range(self.workload.configuration.query_rounds):
            for history in self.histories:
                for version, caller in enumerate(self.workload.callers, 1):
                    snapshot = history[version]
                    for query_index, position in enumerate(caller.queries):
                        checksum += score(snapshot.get(position))
                        lookups += 1
                        if query_index % 32 == 0:
                            checksum += score(
                                snapshot.nearest_occupied_parent(position)
                            )
                            parent_lookups += 1
        return Reads(checksum, lookups, parent_lookups)

    @typing.override
    def traverse(self) -> Reads:
        checksum = 0
        enumerated = 0
        if self.workload.configuration.enumerate_every:
            for history in self.histories:
                for version in range(
                    1, len(history), self.workload.configuration.enumerate_every
                ):
                    for position, occupancy in history[version].items():
                        checksum += len(position) + score(occupancy)
                        enumerated += 1
        return Reads(checksum, enumerated)

    @typing.override
    def dimensions(self) -> dict[str, int]:
        return {
            "initial_state_entries": len(self.workload.initial),
            "copies": self.workload.configuration.copies,
            "versions_per_copy": len(self.workload.callers) + 1,
        }


@dataclass(frozen=True, slots=True)
class Destruction:
    """Shared action and source information for simultaneous destruction."""

    action: str
    position: snapshots.Position
    is_automatic: bool


@dataclass(frozen=True, slots=True)
class Fact:
    """The destruction of one particular particle."""

    destruction: Destruction
    position: snapshots.Position


@dataclass(frozen=True)
class CurrentContract:
    """The current unslotted record, with independently materialized Child State."""

    destroyed_position_contracted: snapshots.Position
    destruction_fact: Destruction
    destroyed_position_in_destroying_action: snapshots.Position
    child_state: dict[snapshots.Position, snapshots.Occupancy]
    verified_destructors: dict[snapshots.Position, tuple[str, ...]]
    is_auto_destruction: bool
    trigger_chain: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ParticleContract:
    """A per-particle contract that references shared Child State."""

    destruction_fact: Fact
    destroyed_position_contracted: snapshots.Position
    child_state: snapshots.Snapshot
    verified_destructors: tuple[str, ...]
    propagation: History | None


@dataclass(frozen=True, slots=True)
class History:
    """One diagnostic propagation step sharing its preceding history."""

    step: int
    previous: History | None


@dataclass(frozen=True, slots=True)
class Requirement:
    """Equivalent relative-position queries for the two contract representations."""

    particle_index: int
    contract_index: int
    relative_to_particle: snapshots.Position
    relative_to_contract: snapshots.Position


@typing.final
class SourceState:
    """A mutable tracker-shaped hash index shared by all projection inputs."""

    def __init__(self, values: dict[snapshots.Position, snapshots.Occupancy]):
        """Build the same parent-key index used by the current compiler trie."""
        self.values = values
        self.children: dict[snapshots.Position, set[snapshots.Position]] = {}
        for position in values:
            self.children.setdefault(position[:-1], set()).add(position)

    def snapshot(
        self, position: snapshots.Position
    ) -> dict[snapshots.Position, snapshots.Occupancy]:
        """Capture independent destruction-time state for a particle."""
        descendants: list[tuple[snapshots.Position, snapshots.Occupancy]] = []
        stack: list[tuple[snapshots.Position, snapshots.Position]] = [(position, ())]
        while stack:
            full_position, relative_position = stack.pop()
            for full_child in self.children.get(full_position, ()):
                relative_child = (*relative_position, full_child[-1])
                descendants.append((relative_child, self.values[full_child]))
                stack.append((full_child, relative_child))
        result: dict[snapshots.Position, snapshots.Occupancy] = {}
        for relative_child, occupancy in descendants:
            if occupancy.state == 1:
                result[relative_child] = snapshots.Occupancy(1, occupancy.fill_site)
            else:
                result[relative_child] = occupancy
        return result


@dataclass(frozen=True, slots=True)
class ProjectionInput:
    """Particles with different contract boundaries but identical requirements."""

    source: SourceState
    particles: tuple[snapshots.Position, ...]
    boundaries: tuple[snapshots.Position, ...]
    requirements: tuple[Requirement, ...]
    copies: int
    query_rounds: int


PROJECTION_CASES = (
    "contracts_chain",
    "contracts_balanced",
    "contracts_wide",
    "contracts_late_children",
    "contracts_small",
)


def projection_input(case: str, scale: int) -> ProjectionInput:
    """Prepare particles and source state for contract-representation experiments."""
    values: dict[snapshots.Position, snapshots.Occupancy] = {}
    particles: list[snapshots.Position] = [("position</destroyed>",)]
    copies = 1
    match case:
        case "contracts_chain":
            for depth in range(1, 128 * scale):
                particles.append((*particles[-1], f"position</child_{depth}>"))
        case "contracts_balanced":
            level = particles.copy()
            for _ in range(5):
                next_level: list[snapshots.Position] = []
                for parent in level:
                    for index in range(4):
                        child = (*parent, f"position</child_{index}>")
                        particles.append(child)
                        next_level.append(child)
                level = next_level
            copies = scale
        case "contracts_wide" | "contracts_late_children":
            for index in range(2_048 * scale):
                particles.append((*particles[0], f"position</child_{index}>"))
        case "contracts_small":
            particles.append((*particles[0], "position</child>"))
            copies = 5_000 * scale
        case _:
            raise ValueError(case)
    for index, particle in enumerate(particles):
        values[particle] = snapshots.Occupancy(1, index + 1)
        values[(*particle, "position</resource>")] = snapshots.Occupancy(
            1, index + 10_000
        )
        values[(*particle, "position</empty>")] = snapshots.EMPTY
        values[(*particle, "position</error>")] = snapshots.ERROR
    if case == "contracts_late_children":
        boundaries = (particles[0],)
    else:
        boundaries = tuple(particles)
    requirements: list[Requirement] = []
    for index, particle in enumerate(particles):
        contract_index = 0 if case == "contracts_late_children" else index
        contract_position = boundaries[contract_index]
        for name in ("resource", "empty", "error", "absent"):
            relative = (f"position</{name}>",)
            requirements.append(
                Requirement(
                    index,
                    contract_index,
                    relative,
                    (*particle[len(contract_position) :], *relative),
                )
            )
    return ProjectionInput(
        SourceState(values),
        tuple(particles),
        boundaries,
        tuple(requirements),
        copies,
        4,
    )


@typing.final
class CurrentProjection(Experiment):
    """Current contract boundaries, duplicated snapshots, and verification maps."""

    def __init__(self, source: ProjectionInput):
        """Prepare input without charging the benchmark for tracker construction."""
        self.source = source
        self.records: list[list[CurrentContract]] = []

    @typing.override
    def build(self):
        for _ in range(self.source.copies):
            destruction = Destruction(
                "action</destroyer>", self.source.particles[0], is_automatic=False
            )
            contracts: list[CurrentContract] = []
            for position in self.source.boundaries:
                verified: dict[snapshots.Position, tuple[str, ...]] = {
                    (): ("action</destructor>",)
                }
                if len(self.source.boundaries) == 1:
                    for particle in self.source.particles[1:]:
                        verified[particle[len(position) :]] = ("action</destructor>",)
                contracts.append(
                    CurrentContract(
                        position,
                        destruction,
                        position,
                        self.source.source.snapshot(position),
                        verified,
                        is_auto_destruction=False,
                        trigger_chain=(),
                    )
                )
            self.records.append(contracts)

    @typing.override
    def query(self) -> Reads:
        checksum = 0
        count = 0
        for _ in range(self.source.query_rounds):
            for records in self.records:
                for requirement in self.source.requirements:
                    record = records[requirement.contract_index]
                    checksum += score(
                        record.child_state.get(requirement.relative_to_contract)
                    )
                    count += 1
        return Reads(checksum, count)

    @typing.override
    def dimensions(self) -> dict[str, int]:
        return {
            "initial_state_entries": len(self.source.source.values),
            "particles_per_copy": len(self.source.particles),
            "contracts_per_copy": len(self.source.boundaries),
            "copies": self.source.copies,
        }


@typing.final
class SharedProjection(Experiment):
    """One record per particle, with either hash-indexed or direct tree views."""

    def __init__(self, source: ProjectionInput, variant: str):
        """Select the concrete shared-state representation to measure."""
        self.source = source
        self.variant = variant
        self.records: list[list[ParticleContract]] = []

    @typing.override
    def build(self):
        for _ in range(self.source.copies):
            destruction = Destruction(
                "action</destroyer>", self.source.particles[0], is_automatic=False
            )
            snapshot = snapshots.FACTORIES[self.variant](self.source.source.values)
            contracts: list[ParticleContract] = []
            for position in self.source.particles:
                state = (
                    snapshot.at_particle(position)
                    if isinstance(snapshot, snapshots.PositionTree)
                    else snapshot
                )
                contracts.append(
                    ParticleContract(
                        Fact(destruction, position),
                        position,
                        state,
                        ("action</destructor>",),
                        None,
                    )
                )
            self.records.append(contracts)

    @typing.override
    def query(self) -> Reads:
        checksum = 0
        count = 0
        use_relative_names = self.variant == "position_tree"
        for _ in range(self.source.query_rounds):
            for records in self.records:
                for requirement in self.source.requirements:
                    record = records[requirement.particle_index]
                    position = requirement.relative_to_particle
                    if not use_relative_names:
                        position = (*record.destruction_fact.position, *position)
                    checksum += score(record.child_state.get(position))
                    count += 1
        return Reads(checksum, count)

    @typing.override
    def dimensions(self) -> dict[str, int]:
        return {
            "initial_state_entries": len(self.source.source.values),
            "particles_per_copy": len(self.source.particles),
            "contracts_per_copy": len(self.source.particles),
            "copies": self.source.copies,
        }


HISTORY_CASES = ("history_chain", "history_fanout", "history_diagnostics")


@typing.final
class HistoryExperiment(Experiment):
    """Compare current per-contract tuples with shared tuple and linked histories."""

    def __init__(self, case: str, variant: str, scale: int):
        """Prepare the call topology and diagnostic read frequency."""
        self.variant = variant
        self.depth = 256 * scale
        self.contracts = 64 if case != "history_diagnostics" else 1
        self.read_every = (
            1 if case == "history_diagnostics" else max(1, self.depth // 8)
        )
        self.callees = list(range(self.depth))
        if case == "history_fanout":
            self.callees.extend([self.depth] * (256 * scale))
        self.tuple_versions: list[list[tuple[int, ...]]] = []
        self.linked_versions: list[list[History | None]] = []

    @typing.override
    def build(self):
        if self.variant == "linked_history":
            self.linked_versions.append([None] * self.contracts)
            for step, callee in enumerate(self.callees, 1):
                history = History(step, self.linked_versions[callee][0])
                self.linked_versions.append([history] * self.contracts)
            return
        self.tuple_versions.append([()] * self.contracts)
        for step, callee in enumerate(self.callees, 1):
            previous = self.tuple_versions[callee]
            if self.variant == "shared_tuple_history":
                self.tuple_versions.append([(step, *previous[0])] * self.contracts)
            else:
                self.tuple_versions.append([(step, *history) for history in previous])

    @typing.override
    def query(self) -> Reads:
        checksum = 0
        count = 0
        if self.variant == "linked_history":
            for version in range(1, len(self.linked_versions), self.read_every):
                current = self.linked_versions[version][0]
                while current is not None:
                    checksum += current.step
                    count += 1
                    current = current.previous
        else:
            for version in range(1, len(self.tuple_versions), self.read_every):
                for step in self.tuple_versions[version][0]:
                    checksum += step
                    count += 1
        return Reads(checksum, count)

    @typing.override
    def dimensions(self) -> dict[str, int]:
        return {"callers": len(self.callees), "contracts_per_caller": self.contracts}


ALL_CASES = (*workloads.CASES, *PROJECTION_CASES, *HISTORY_CASES)


def variants_for(case: str) -> tuple[str, ...]:
    """List meaningful implementations for the selected experiment family."""
    if case in workloads.CASES:
        return tuple(snapshots.FACTORIES)
    if case in PROJECTION_CASES:
        return (
            "current_contracts",
            "shared_flat",
            "partitions_1024",
            "position_tree",
            "compact_base",
        )
    if case in HISTORY_CASES:
        return ("current_history", "shared_tuple_history", "linked_history")
    raise ValueError(case)


def prepare(case: str, variant: str, scale: int, seed: int) -> Experiment:
    """Prepare common input before timing a concrete implementation."""
    if case in workloads.CASES:
        workload = workloads.generate(workloads.configuration(case, scale), seed)
        return StateExperiment(workload, snapshots.FACTORIES[variant])
    if case in PROJECTION_CASES:
        source = projection_input(case, scale)
        if variant == "current_contracts":
            return CurrentProjection(source)
        return SharedProjection(source, variant)
    if case in HISTORY_CASES:
        return HistoryExperiment(case, variant, scale)
    raise ValueError(case)
