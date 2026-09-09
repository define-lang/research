# Small Destruction Contract interface experiments

## Recommendation

Use **position-specific destruction-time state** as the contract interface. A
single child Vacate completion is not a sufficient substitute for that state.

Under the priorities of code simplicity, then spec simplicity, then performance
and memory, retain explicit child Vacates for now. They fit the current rules
and require no extra lowering pass. The record-only alternative works in this
model, but does not remove the position and particle information that the
interface already needs. Its measured construction advantage is small.

This separates two decisions that the earlier experiments conflated:

1. What information crosses an action boundary?
2. Does a selected child have a Vacate node in the graph?

The answer to the first is substantially the same in all three designs. The
second can be changed without inventing a different callee interface for every
possible caller.

## The derived interface

An action description states the positions known through its contract and gives
Creates, Moves, direct calls, and destruction selection. It does not supply
dependency edges, producer exports, or candidate sets.

The compiler recipe includes the action's known positions and its direct
callees' position interfaces. At destruction, it exports:

- For each known position: its occupant, its parent particle's Create, its
  setter, and its readers.
- For each relevant known particle: its known child positions, recorded quality
  uses, and most recent direct Move.
- The identities of selected particles, plus the variant-specific destruction
  prerequisite representation described below.

Those producer references are obtained mechanically from Collection's state.
The callee need not predict which destructor the caller will contribute. When
the caller resolves a destructor operation, that operation's references select
the appropriate position records, and ordinary Collection and Comparison choose
its dependencies.

The caller merges its additional child-position and particle information with
the direct callee's returned contract. Before resolving caller-only destructors,
the experiment clears all private callee occupancy and lifetime maps and
reconstructs the necessary state from the merged contract. No hidden shared
state supplies a missing export at that stage.

Returning records is not equivalent to waiting for them to become runtime-ready.
They are compiler information containing references to graph operations. Any
eventual runtime arrivals must follow those operations' actual dependencies, not
the moment the parent Vacate completes.

## Three candidates

| Candidate | Contract representation beyond common state | Additional construction work | Spec impact |
| --- | --- | --- | --- |
| Explicit child Vacates | A Vacate reference for each selected child | Construct those nodes; include them in Vanish Collection | Keeps the current model |
| Explicit, then lowered | The same references | Substitute child Vacate prerequisites while constructing the lowered graph; repeat Vanish Comparison | No semantic rule change required for a proven implementation optimization |
| Records only | The selected position's readers, or its setter when it has no readers | Preserve that candidate set for the child's Vanish instead of creating its Vacate | Distinguish direct Vacation from transitive selection and specify the latter's Vanish prerequisites |

All three still need the common position and particle records. The lowering
candidate is not a simpler interface; it adds a representation transformation.
The records-only candidate has a slightly smaller graph-construction path, but
replaces a uniform operation rule with a separate selection case. There is no
decisive code-simplicity improvement here that outweighs keeping the current
spec model.

There is no generic transitive reduction in construction. The lowered candidate
only substitutes the identified child Vacates, whose consumers in this model
are Vanishes, and applies the existing Vanish Comparison to the resulting
candidates before adding edges. Tests use a separate, deliberately slow
reachability/projection oracle.

## A case that rules out a single completion as the whole interface

The focused reader case has a particle whose child positions are 6, 7, and 8.
The callee independently Creates particles in 6 and 7. The caller knows an
additional destructor that Moves the particle in 6 to the empty position 8 and
back.

The destructor's first Move needs the Create in 6, not the Create in 7. The
Vacate of the parent of these positions depends on both Creates because both
operations read that parent's occupied position.

The captured setter of 6 therefore supplies the correct dependency. An aggregate
parent or child readiness event does not. The test verifies the exact edges,
including that the unrelated Create is absent from the Move's prerequisites.

## Correctness experiments

There are 486 tests:

- 480 combinations of 40 seeds, widths 4/8/24, and forwarding depths 0/1/6/20.
  Generation chooses valid Creates and Moves from current occupancy, including
  Moves between different child positions. Three caller-only destructors then
  use the preserved position identities, including positions unknown to the
  callee.
- An unchanged callee template with different caller-known destructor sets.
- Independent readers and setters with two calls to the identical callee
  template and distinct operation occurrences.
- Callee exports that exclude caller-only child positions, followed by correct
  caller augmentation.
- Contract sufficiency after private callee occupancy and lifetime state is
  discarded.
- Reordered caller Creates that change particle identities without changing
  the callee template.
- Fully occupied child positions with no available destructor Moves.

The explicit variant matches the existing complete whole-program algorithm's
exact dependency sets. Both alternatives match the independently projected,
transitively minimal graph after removing child Vacates. Thus they preserve the
same ordering among retained operations in these cases. The oracle is not used
to choose the interface or construct any candidate graph.

## Secondary measurements

Each shape used three seeds, with seven construction samples per seed and
rotated variant order. These are medians of the three per-seed medians, in
milliseconds:

| Child positions | Forwarding depth | Explicit | Lowered | Records only |
| ---: | ---: | ---: | ---: | ---: |
| 32 | 0 | 2.47 | 2.80 | 2.40 |
| 32 | 20 | 2.96 | 3.26 | 2.87 |
| 256 | 0 | 13.08 | 15.40 | 12.90 |
| 256 | 20 | 16.27 | 18.61 | 16.24 |
| 2,048 | 0 | 104.36 | 123.86 | 103.96 |
| 2,048 | 20 | 129.81 | 149.77 | 129.36 |

For width 2,048 and depth 20, median peak traced Python allocations were:

| Explicit | Lowered | Records only |
| ---: | ---: | ---: |
| 9.45 MiB | 13.45 MiB | 9.20 MiB |

These measurements exclude description generation and callee template
compilation. They include binding the descriptions, contract capture/merging,
graph construction, oracle-trace recording, and the optional lowering pass.
Setup and destructor recipes are compiled during construction. Memory is
measured in separate untimed runs. The host is not reserved for benchmarks.

Explicit and records-only construction are approximately tied. The lowerer's
extra graph and remapping tables cost time and peak memory in this straightforward
implementation; this is not a lower bound on every possible lowerer.

All candidates deliberately leave Vacate/Vanish combination off to isolate the
interface comparison. The `runtime_nodes` field in the raw data means graph
nodes after optional lowering, not measured runtime tasks. The existing
combination optimization could remove many of the explicit variant's extra
nodes. These are not performance comparisons against the optimized production
compiler or scheduler.

[results.json](results.json) preserves every timing sample, memory result, and
the exact measured sources. The shared-state boundary counters do not count
variant-specific Vacate references or saved selection candidates separately;
the peak-allocation measurement includes them.

## Scope

This is deliberately not another Define compiler implementation. Positions and
intermediate positions are supplied as already-resolved identities. The model
does not parse source, verify quality assignment or action triggers, or generate
runtime code. The generated cases have one destruction selection and Move-only
destructors; they do not cover arbitrary interleaved destruction, destructor
Creates, or replacing a destroyed parent during its destructors.

Templates are reusable action recipes. Binding them constructs an explicit
whole-program experimental graph, on which the existing Comparison algorithm
can answer reachability queries. This does not establish an efficient purely
per-action implementation of every caller-dependent Comparison, nor a complete
production static action planner. The result established here is which
information the interfaces need and that it is sufficient for the tested
abstract action model.

No new spec rule, general proof, production compiler change, or runtime
performance claim follows automatically from these tests.

## Files and commands

- `descriptions.py`: semantic input descriptions and occupancy-driven generation.
- `compiler.py`: reusable recipes, contract records, and the three constructions.
- `interface_test.py`: whole-program oracle and focused/randomized comparisons.
- `benchmark.py`: fixed-input construction and allocation measurements.

```sh
bazelisk test --noshow_progress --ui_event_filters=-info //operation_graph_optimization/transitive_destruction/interfaces:interface_test
uv run --frozen --group dev -m operation_graph_optimization.transitive_destruction.interfaces.benchmark --width 2048 --steps 4096 --depth 20 --seed 0 --repeat 7
```
