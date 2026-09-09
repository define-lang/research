# Destruction without transitive child Vacate nodes

## Finding

A transitive child's Vacate can be eliminated **as a graph node** when no
remaining Create, Move, or Vacate consumes the ordinary position state that it
would have changed. Its prerequisites must then be transferred to its Vanish.
This is not permission to lose the identity or pre-destruction state of the
selected child, or to leave it accessible to ordinary code.

The experiment implements two constructions and compares them with the existing
early-combination algorithm. Both match the projected reference graphs in the
tested cases. Neither is an established replacement for the current compiler or
a complete proof that all valid Define source satisfies the elimination
condition.

The practical result is mixed: eliminating nodes can help when transitive
Vacate and Vanish could not previously combine, but often saves no nodes when
they already combine. Keeping their prerequisites until finalization can cost
additional memory and time.

## Scope and artifacts

- [algorithm.py](algorithm.py): remember all actual quality requirements for
  particles selected transitively, including ordinary intermediate accesses.
  Complete their Vanishes from those requirements, their Creates, and latest
  direct Moves. No transitive selection-time position update is performed.
- [snapshot.py](snapshot.py): at transitive selection, save the selected position's
  readers, or its setter when there are no readers. Add those prerequisites to
  the particle's recorded Vanish candidates without adding a node or emptying
  the position. Retain the existing ordinary-occupancy omission for other
  quality requirements.
- [experiment.py](experiment.py): independent identification of which Vacates
  are transitive, input preparation, workload construction, and comparison with
  the explicit graph.
- [model_integration_test.py](model_integration_test.py): real Define source and
  randomized resolved-operation tests. The compiler validates source; its
  currently implemented Operation Graph is not used as the expected graph.
- [benchmark.py](benchmark.py): construction-only timing and normalized graph
  digests.
- [initial_results.json](initial_results.json) and
  [comparison_results.json](comparison_results.json): commands, raw results,
  and exact experiment source snapshots.

The Define spec, proofs, compiler, and existing design algorithm were not edited.
Existing research measurements were preserved. These are experimental algorithms,
not changes to the reference algorithm in `complete/`.

## Proposed construction

Direct explicit destruction and automatic destruction of a local particle still
have a Vacate. That event makes an independently usable position available for
replacement, even when the previous particle has not vanished.

For a particle selected only because it is a transitive child of a particle
being destroyed:

1. Record the particle's identity and which destruction selected it.
2. Keep its positions and their state available to destruction operations.
   Do not create a transitive Vacate graph node or clear those position records.
3. Preserve the prerequisites that would have reached its Vacate, either by
   tracking all actual particle requirements or by capturing position information
   at selection as described above.
4. Record subsequent destructor requirements and direct Moves normally.
5. At completion, apply the existing Comparison to this child's Vanish
   candidates. Do not add its parent's Vacate or Vanish as an automatic
   dependency.

The second version still performs a per-selected-child bookkeeping step.
It reuses the existing Vacate's *dependency calculation inputs*, but does not
reinvent its position-changing operation or graph vertex. Eliminating the vertex
does not eliminate the need to preserve relevant facts.

For positions that the old construction copied solely to preserve their state
across a removed transitive Vacate, the new construction can use the unchanged
original record. All destructors referring to that position must share the same
subsequent changes. A copied record is still necessary when an actual direct
Vacate separates ordinary access from destruction access.

This is a proposed representation of destruction selection and lifetime
dependencies. It does not by itself settle how to rewrite the spec's conceptual
Vacation definition. In particular, removing a graph node does not prove that a
selected child should continue to count as ordinarily occupying a position.

## Graph correspondence argument

Let T be the selected transitive Vacates being removed from the existing explicit
Create/Move/Vacate/Vanish graph. The following hypotheses are necessary:

1. Each removed operation has no Position References and acts on the selected
   child's particular original position, not a replacement's position.
2. No retained Create, Move, or Vacate has a dependency path through an operation
   in T. Its changed ordinary position state has no later consumer.
3. Destruction operations use the unchanged pre-Vacation position information,
   with shared subsequent changes, rather than the state changed by T.
4. Particle identities, direct selection events, actual Position References,
   and the chosen ordering of conflicting destructor operations are unchanged.

These are not conclusions inferred from passing tests.

Under these hypotheses, induct on retained Creates, Moves, and Vacates. Removing
T does not change any position information they consult: ordinary changed
records have no later consumers, and destruction records retain the same state.
Their Collection candidates and resulting dependencies therefore correspond
exactly after renumbering. None of their dependencies needs repair.

For a removed child Vacate v, let C(v) be its position Collection: its readers,
or its setter if there are no readers. It has no reference-derived candidates.
Let U be the other Vanish candidates for its selected particle. The old Vanish
has the reachability generated by {v} union U. After removing v, the same
reachability on retained operations is generated by C(v) union U. Apply the
existing Comparison to that candidate set. This is exactly the selection-time
snapshot construction; no full-graph reduction is performed.

Adding the child's Create is harmless: the selected position's current fill
depends on that Create, and each current reader depends on the fill.
For the all-requirements construction, the fill is either the child's Create
or a direct Move; all later direct Moves form a dependency chain. Each reader
of the occupied position requires that child's assigned qualities. Consequently
the child's Create, latest direct Move, and recorded quality requirements cover
C(v). Conversely these requirements are already covered by the original Vanish:
ordinary accesses precede v, and the other requirements were collected explicitly.
Thus both constructions give the same terminal reachability and Comparison
chooses the same minimal dependencies.

This proves graph correspondence under the listed hypotheses, not source-level
completeness or the safety of a different physical memory representation.
Vanish/Vacate combination is normalized as an implicit Vanish depending only on
its Vacate before comparison. The oracle projects away only T. Generic
projection and pairwise reachability enumeration occur in validation, never in
the production construction.

## Why the ordinary-access omission changes

The current algorithm may omit an operation that requires the particle to occupy
an ordinary intermediate position: the particle's Vacate already follows that
operation. Without the child's Vacate, blindly retaining this omission loses
that prerequisite.

The all-requirements variant therefore retains these operations for transitively
selected particles. The snapshot variant retains the omission but preserves its
justification by recording the selected position's existing prerequisites.
Moving a parent particle does not, by itself, require a transitive child to
remain alive. An actual reference to one of the child's assigned qualities does.

A real-source constructor test checks the important concurrency boundary:
creating an implied leaf requires the particle defining the leaf, but need not
wait for the defining particle's parent's destruction. Neither prototype adds
an ordering from the parent Vacate or Vanish to the child's Vanish.

## Destruction Contracts

The current Destruction Fact identifies the specific particle destroyed, and
Child State records the known occupancy immediately before destruction. Those
concepts remain necessary without transitive Vacate nodes.

A proposed contract interpretation distinguishes:

| Information | Meaning |
| --- | --- |
| Direct Destruction Fact | A particular callee destruction vacates its directly selected particle's position. That Vacate remains an operation. |
| Transitive selection | A particular child particle was selected by that same destruction. This is identity/state information, not another position-changing operation. |
| Child State | The original positions and particles available to destruction operations at that selection, extended with caller knowledge. |
| Lifetime prerequisites | References to the operations or unresolved dependencies that the selected particle's Vanish must wait for. |

The transitive selection must identify both the original particle and the
particular destruction occurrence. A textual child name or the current occupant
of a reused position is insufficient. If a destructor moves the selected child,
its identity and selection do not change. Repeated executions of the same callee
must have distinct particle/selection instances.

When a caller knows an additional child or destructor, it contributes selection
information and the corresponding lifetime prerequisites at the destruction
described by the contract, not at the caller's later position state. It must not
make a child's Vanish depend on a parent Vacate simply to identify that moment.
Nor may it introduce a whole-destructor completion dependency.

A compiler resolving this modularly would need unresolved lifetime dependencies
that callers can supply, just as it currently needs Destruction Connections.
A lower-level action cannot finalize or certify combination using an incomplete
view of caller-known qualities. The new model does not make that problem vanish.

The integration cases cover direct and forwarded callee destruction with
caller-only child/destructor knowledge, repeated calls, and destructor Moves.
They validate source and then use independently described *resolved* operations.
They do not implement modular contract composition or prove that symbolic
lifetime dependencies suffice for every possible caller. That remains a
necessary obligation before a specification or compiler replacement.

## Measurements

The first matrix contains 18 successful measurements. The extended matrix
contains 39: 27 repeated small timings, six million-step checks, and six isolated
allocation measurements. All comparable normalized graph digests match.

Median total construction seconds, three seeds, approximately 100,000 original
Create/Move/Vacate operations, width 32:

| Workload | Current early combination | All requirements | Selection snapshot |
| --- | ---: | ---: | ---: |
| Written child/leaf creation | 0.146 | 0.153 | 0.159 |
| Implied leaf constructors | 0.180 | 0.132 | 0.145 |
| Shared destructor Moves | 0.213 | 0.386 | 0.229 |

There is substantial runtime variation. For example, current shared-Move times
in the extended matrix ranged from 0.139 to 0.222 seconds; in the initial matrix
their median was 0.139. The single-seed million-step results are checks, not
confidence intervals:

| Workload | Current | Selection snapshot |
| --- | ---: | ---: |
| Written child/leaf creation | 2.575 | 1.653 |
| Implied leaf constructors | 2.680 | 1.658 |
| Shared destructor Moves | 1.411 | 2.600 |

Those fluctuations do not establish a universal speed ordering. In particular,
the written workload reverses its small-run ordering at larger size.

At roughly one million original operations, the written workload has 999,960
vertices in both graphs: the current algorithm already combines the child
Vacates and Vanishes. The implied workload decreases from 1,246,104 to 999,960
vertices and from 1,730,699 to 1,238,411 edges. The shared-Move workload removes
only 32 vertices because it repeatedly moves the same 32 selected children.

Construction-only peak allocated bytes, separate traced runs at roughly 30,000
operations:

| Workload | Current | Selection snapshot |
| --- | ---: | ---: |
| Written child/leaf creation | 4,865,128 | 9,061,592 |
| Implied leaf constructors | 7,096,392 | 7,996,264 |
| Shared destructor Moves | 1,480,080 | 1,691,658 |

These measurements exclude input preparation and are not process resident
memory. The increased peak demonstrates why fewer completed graph nodes does
not imply cheaper construction. Snapshot state lives until Vanish finalization.

## Measurement boundaries and limits

Each measurement ran in a fresh process. Trial order was shuffled with a fixed
seed; no tests or other benchmarks launched by this investigation overlapped
the measured runs. The host was not reserved. Instrumented memory-run timings
are excluded from speed comparisons.

Construction timing includes graph/calculator initialization, position
construction, lifetime collection, optional pruning, selection snapshots where
applicable, final Comparison, and node insertion. It excludes valid-operation
selection, identity resolution, early-combination classification, conversion
between the old and proposed inputs, validation, and digest computation.

Source-resolution inputs are supplied to both variants. The prototype copies
the supplied tracked-particle set when adding transitively selected particles;
that copy is included in construction time and allocation. Savings from a
future compiler generating a smaller input directly are not measured.

The cascade generator randomizes child creation order, leaf creation order,
and simultaneous selection enumeration within valid families. It is not a
fully general state-driven sampler of every possible Define operation.
The shared-Move generator progressively chooses valid moves and restores
destructor guarantees. These workloads do not measure arbitrary depth, every
contract shape, or the complete earlier benchmark corpus.

To reproduce an individual measurement from the research repository:

```sh
uv run --frozen -m operation_graph_optimization.transitive_destruction.benchmark --family implied --strategy snapshot --steps 1000000 --width 32 --seed 17
bazelisk test --noshow_progress --ui_event_filters=-info //operation_graph_optimization/transitive_destruction:model_integration_test
```

## Recommendation

Validation: repository-wide coverage passes all six research test targets,
including 234 cases in the new integration target. Repository-wide Basedpyright
and the new files' Ruff checks pass. Coverage was inspected; the copied general
Comparison, retain/forget paths, and some optional pruning branches are not all
exercised by this focused suite. This is not a claim of complete branch coverage.

Separate **selection information** from **runtime Vacate nodes** in the design
discussion. This experiment supports investigating elimination of transitive
Vacate nodes without pretending that selection and lifetime dependencies disappear.

Do not change the spec solely for a claimed speed improvement: these measurements
do not establish one across workloads. Before adopting the model, discharge the
no-ordinary-consumer condition for all valid source, design modular contract
composition without caller-specific callee rewrites, and benchmark that
implementation against the current early-combination path.
