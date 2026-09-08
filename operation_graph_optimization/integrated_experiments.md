# Complete operation graph construction

## Result

Use [complete/algorithm.py](complete/algorithm.py) and
[complete/graph.py](complete/graph.py) together. They have no dependency on the
research harness or archived implementations. [The complete rules](complete/rules.md)
and [input contract](complete/README.md) accompany them.

The result integrates Create, Move, Vacate, and Vanish construction in one
calculator. It is the recommended implementation among the alternatives tested,
not a claim of universal time optimality. No compiler or specification files
were changed, and nothing was committed.

## Design choices

The baseline is the archived position algorithm plus the best previous Vanish
collector, already using the most recent direct Move and ordinary-occupancy
coverage. The investigation compared:

- Sharing position Collection candidates with lifetime pruning, sharing only
  final direct dependencies, and deferring particle-use pruning.
- Indexing every operation versus storing Vanish edges without adding their
  reverse index entries.
- Singleton Vacate candidate sets versus keeping only actual quality-use sets.
- Separate recording versus a shared position/particle recording pass.
- Unbounded versus bounded optional pruning.
- Source-resolved particle identities versus deriving them again from position
  information.
- General reachability queries versus an indexed-only path for Comparison.

The result shares Collection and recording, bounds optional pruning, stores
Vacates separately, reuses their mapping for the returned Vanishes, and releases
construction state at finalization. It retains source-resolved identities:
repeating identity resolution did not give a consistent speed advantage.

The same quality-particle input supplies both Create and Vanish requirements.
Vanishes retain all graph edges but need no reverse construction index.
Comparison never receives a Vanish candidate, so it can use the indexed-only
query path without checking for terminal operations on every query.

Final position setters cannot replace all particle-use information. A
constructor's implied child Create requires its parent particle, but the child's
subsequent transitive Vacate does not. Substituting the final setter would
unnecessarily order the parent's Vanish after that child Vacate. A real-source
integration test checks this distinction.

## Final implementation timings

Median complete-construction seconds, three seeds per implementation:

| Workload | Requested steps | Baseline | Integrated |
| --- | ---: | ---: | ---: |
| Direct movement | 1,000,000 | 3.789 | 3.759 |
| Implied quality uses | 1,000,000 | 4.493 | 3.180 |
| Mixed state-driven operations | 1,000,000 | 5.424 | 4.762 |
| Growth followed by remaining Vacates | 250,000 | 27.406 | 26.074 |
| Wide independent uses | 100,000 | 0.238 | 0.175 |
| Shared retained destructor Moves | 100,000 | 0.194 | 0.166 |
| Seven-name references, including destruction | 100,000 | 0.747 | 0.729 |
| Twenty-one-name references, including destruction | 100,000 | 1.010 | 0.987 |

The first three rows are from `complete_fast_scale_results.jsonl`, the fourth
from `complete_fast_closed_results.jsonl`, the next two from
`complete_fast_results.jsonl`, and the last two from
`complete_deep_results.jsonl`.

A requested step is a generator parameter, not a uniform operation count. The
million-step implied workload has 2,000,200 Create/Move/Vacate operations and
1,000,100 Vanishes. The completed deep workloads have 700 and 2,100 Vanishes,
respectively. Their parameters count child-position levels: `deep6` and
`deep20` mean seven and twenty-one position names including the local parent.

The largest clear gains are on lifetime-heavy workloads. Movement and deep
references are close to baseline. Growth-heavy results are less stable: the
100,000-step mixed-seed matrix included a slower integrated median. Five repeated
runs of the identical seed-17 completed-growth input gave median wall times
7.622 versus 7.483 seconds, but one integrated run took 9.334 seconds. Its CPU
time was also high, so the outlier is not just wall-clock descheduling. Its cause
was not established; do not claim a consistent growth-heavy speed advantage
from the small median difference.

The repeated-input run and corrected deep runs also compare ordered adjacency
digests, not just dependency sets. Those digests match too.

## Construction allocation peaks

Separate allocation-traced runs start after all inputs have been prepared.
These are 30,000 requested steps, width 100, seed 17. Instrumented times are
excluded from speed comparisons.

| Workload | Baseline peak MiB | Integrated peak MiB |
| --- | ---: | ---: |
| Local operations | 5.18 | 2.81 |
| Implied quality uses | 12.97 | 6.14 |
| Written quality uses | 17.49 | 10.14 |
| Mixed state-driven operations | 12.59 | 7.78 |
| Completed growth | 26.68 | 18.24 |
| Shared retained destructor Moves | 3.91 | 3.85 |

The data are in `complete_memory_results.jsonl`. Avoiding singleton Vacate sets
and releasing construction state account for additional object-memory savings
beyond the graph arrays.

Omitting Vanishes from the reverse index saves exactly
`8 * number_of_Vanishes + 16 * number_of_Vanish_edges` bytes of array payload.
The `graph_storage_bytes` field counts array elements, not spare capacity,
Python-object overhead, or cache storage. Process RSS high-water marks include
generated inputs and are not isolated graph-memory measurements.

## Validation

All five repository test targets pass. The integrated suite has 444 cases,
including real Define source, independent all-conflicts position checks,
independent lifetime-ancestor checks, optional-pruning variants, retained
destructor state, ordinary/interface/implied access, replacements, simultaneous
Vacates, and cache growth and admission limits.

The standalone algorithm and graph have full executable line and branch
coverage: 181 lines/98 branches and 140 lines/62 branches, respectively.
Real source is validated by the compiler; its destruction graph is not used as
the expected graph.

Across this follow-up's 523 completed measurements, all runs succeeded and all
per-input graph comparisons matched. This is a correctness check in addition
to the independent small-input tests, not a replacement for them.

## Source-workload correction

The archived tree and simultaneous-destruction generators store automatic
Vacates separately from their statement operations. Early deep measurements
omitted that list and therefore measured prefixes without Vanishes. The
corrected source adapter includes it.

Those old position-only fixtures also put redundant parent-Create metadata on
transitive Vacates. That metadata is not an actual quality use. The adapter
removes it; otherwise a parent Vanish would unnecessarily depend on child
Vacates. A source integration test specifically checks that this does not happen.
The archived generators and earlier measurements remain unchanged.

## Measurements and reproducibility

Each JSONL file starts with exact experiment sources and platform information.
Following records preserve commands, exit statuses, streams, and measurements.
Trial order is randomized; each trial uses a fresh process with limits of 3 GiB
address space, 90 CPU seconds, and 120 wall seconds.

Generation, selection of valid operations, reordering, identity resolution, and
input conversion happen before construction timing. Timed work includes
calculator initialization, both kinds of requirement maintenance, Comparison,
graph insertion, and final Vanish construction. Digest calculation is afterward.
Later diagnostic runs additionally record construction CPU time.

The first exploratory batch briefly overlapped initial type/test checks. Later
benchmark batches ran without concurrent test or benchmark processes started by
this investigation. These measurements do not eliminate host/runtime variation.

| Record | Runs | Purpose |
| --- | ---: | --- |
| `integrated_initial_results.jsonl` | 120 | Shared Collection, direct dependencies, deferred pruning, terminal indexing |
| `integrated_compact_results.jsonl` | 132 | Compact lifetime state and bounded pruning |
| `integrated_resolution_results.jsonl` | 33 | Shared recording versus internal identity resolution |
| `complete_final_results.jsonl` | 66 | First standalone implementation; deep cases were prefixes |
| `complete_scale_results.jsonl` | 30 | First standalone million-step scaling |
| `complete_closed_results.jsonl` | 6 | First standalone completed-growth scaling |
| `complete_width_results.jsonl` | 12 | 10,000-position width, before indexed-query refinement |
| `complete_fast_results.jsonl` | 66 | Indexed-only Comparison; deep cases were still prefixes |
| `complete_fast_scale_results.jsonl` | 18 | Final million-step scaling |
| `complete_fast_closed_results.jsonl` | 6 | Final completed-growth scaling |
| `complete_memory_results.jsonl` | 12 | Construction-only allocation peaks |
| `complete_deep_results.jsonl` | 12 | Deep references with actual automatic destruction |
| `complete_repeat_results.jsonl` | 10 | Repeated identical growth input, CPU times and ordered digests |

From the research repository, use a new destination filename:

```sh
uv run --frozen -m operation_graph_optimization.complete_matrix --output measurements.jsonl --steps 1000000 --families movement,implied,state,retained --strategies baseline,final
uv run --frozen -m operation_graph_optimization.complete_matrix --output deep.jsonl --steps 100000 --families deep6,deep20 --strategies baseline,final
uv run --frozen -m operation_graph_optimization.complete_matrix --output allocations.jsonl --steps 30000 --families local,implied,written,state,growth_closed,retained --strategies baseline,final --seeds 17 --trace-memory
```

The large workloads use the existing state-driven generator and independent valid
reordering, plus randomized direct Moves through shared retained destructor
positions after Vacates and replacement creation. They are not claimed to
enumerate every possible destructor program.

Candidate-coverage arguments justify the equivalent collection rules. Shared
recording and terminal storage require no new semantic ordering, whole-graph
transitive reduction, or execution barrier. Measurements select a practical
implementation among tested alternatives; they do not prove universal time
optimality.
