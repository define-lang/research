# Simplifying the complete Particle Operation algorithm

The spec now records every parent particle of a named position or action as a
Vanish candidate, without an ordinary-occupancy omission. It specifies separate
Vacates and Vanishes. These experiments test whether corresponding implementation
simplifications are worthwhile, not new semantics.

## Variants

Each variant is a separate static implementation; there are no per-operation
experimental feature switches. They share the existing resolved-operation type
and graph storage and reachability implementation.

| Variant | Change |
| --- | --- |
| `early` | Archived early-combination implementation, including classification in the measurement. |
| `separate` | Archived complete algorithm without combination; still omits ordinarily covered Vanish uses. |
| `broad` | `separate`, but records all parent-particle uses. |
| `unpruned` | `broad`, without incremental Vanish candidate pruning. |
| `collection` | `unpruned`, without Collection omission bookkeeping; removes `parent_create` and `recent_use` from position records. |
| `ordered` | `collection`, using only the spec's ordered Comparison scan. |
| `simple` | `ordered`, also without incremental reader pruning. |
| `no_pruning` | `unpruned`, without reader pruning, but retains optimized Collection and Comparison. |
| `broad_ordered` | `broad`, using only the ordered Comparison scan; retains other pruning and Collection optimizations. |
| `collection_pruned` | Simplified Collection, but with broad recording and incremental Vanish and reader pruning retained. |

## Correctness and measurements

`simplification_test.py` compares every ordinary dependency row with the
independent all-conflicts interpreter. For each Vanish, its oracle collects all
actual parent-particle uses, all direct Moves, and the Vacate, then removes
redundancy using the interpreter's full predecessor sets. Generic reduction is
used only by that test oracle, not by any measured construction. Cases include
real Define source, valid state-generated operations, shared retained destructor
state, wide candidate sets, and reference chains generated at depths six and
twenty.

Every measured construction additionally checks a fingerprint of the complete
ordinary dependency rows and every particle's Vanish dependencies. For this
comparison only, an early-combined Vanish is represented by a dependency on its
Vacate. This normalization compares logical prerequisites; it does not pretend
that combination leaves the actual vertex set unchanged. Node and edge counts
in the data remain the actual constructed counts.

Source generation, random valid-operation selection, requirement resolution,
and input conversion occur before timing. Timings include classification where
applicable, graph construction, retained-state copying, and Vanish completion.
They exclude fingerprinting, explicit garbage collection between runs, and
allocation tracing. Variant order is shuffled reproducibly for each repetition.
Each family and seed runs in a fresh process.

Peak memory is incremental traced Python allocation during a separate
construction, including classification and final graph storage. It excludes the
already prepared inputs, so it is not total compiler memory or process RSS.
All variants receive the same prepared inputs; potential savings from no longer
resolving ordinary-occupancy information are not included. The existing
reachability cache settings are unchanged.

The state and growth workloads choose valid operations progressively and also
use the archived valid-order randomization. Other families deliberately stress
specific patterns: local reuse, overlapping Moves, implied accesses, written
references, wide sets of uses, retained destructor Moves, and deep references.
They are not a uniform distribution over all valid Define programs.

`simplification_benchmark.py` preserves raw samples, graph fingerprints, node and
edge counts, memory peaks, environment information, exact source snapshots, and
process failures. Result files are created exclusively and never overwritten.

## Results

All 87 correctness cases pass for all ten variants. All completed benchmark
constructions have matching graph fingerprints under the combination
normalization described above.

### Broad recording and separate Vanishes

The following times are seconds for graph construction at 100,000 requested
steps. Each cell is the median of three seeds' medians, with three repetitions
per seed. Requested steps are generator parameters, not necessarily the number
of operations: these cases contain approximately 77,000–277,000 ordinary
operations, before separate Vanishes.

| Workload | Early combination | Separate Vanishes | Broad recording |
| --- | ---: | ---: | ---: |
| Local reuse | 0.173 | 0.200 | 0.196 |
| Moves | 0.374 | 0.371 | 0.369 |
| Implied references | 0.301 | 0.312 | 0.305 |
| Written references | 0.430 | 0.484 | 0.541 |
| Wide uses | 0.174 | 0.179 | 0.175 |
| Random valid state | 0.364 | 0.409 | 0.415 |
| Growing valid state | 7.245 | 7.557 | 9.051 |
| Retained destructor state | 0.183 | 0.170 | 0.165 |
| Depth six | 0.727 | 0.735 | 0.768 |
| Depth twenty | 1.526 | 1.496 | 1.581 |

Broad recording alone is approximately unchanged on several workloads, but
costs about 12% for written references and 20% for growing state relative to
separate Vanishes with the ordinary-occupancy omission. These are observed
medians, not statistical confidence bounds. Removing early combination is a
separate tradeoff: it costs time on local reuse and written references, but
saves time on retained destructor state. Neither choice wins everywhere.

The million-step confirmation uses seed 17 and three repetitions. Times are
medians in seconds; all complete dependency fingerprints match.

| Workload | Ordinary operations | Early combination | Separate Vanishes | Broad recording |
| --- | ---: | ---: | ---: | ---: |
| Local reuse | 1,000,201 | 1.779 | 2.082 | 2.066 |
| Written references | 2,000,200 | 5.583 | 6.087 | 7.089 |
| Retained destructor state | 1,000,259 | 2.007 | 1.840 | 1.809 |
| Depth six | 751,700 | 7.215 | 7.263 | 7.635 |

Separate allocation measurements at 100,000 requested steps, seed 17, give the
following peak MiB. These include the constructed graph but exclude prepared
inputs; they are not process RSS. Broad recording's extra candidate storage is
visible for written and deep references, whereas removing combination primarily
affects local reuse here.

| Workload | Early combination | Separate Vanishes | Broad recording |
| --- | ---: | ---: | ---: |
| Local reuse | 8.36 | 9.79 | 9.79 |
| Written references | 37.32 | 37.32 | 43.31 |
| Retained destructor state | 13.30 | 13.29 | 13.29 |
| Depth six | 4.63 | 4.64 | 4.78 |
| Depth twenty | 5.24 | 5.25 | 5.73 |

### Other simplifications

At 2,000 requested steps, averaging the two seeds' three-sample medians:

| Workload | Broad recording | All simplifications | Slowdown |
| --- | ---: | ---: | ---: |
| Wide uses | 0.00343 | 0.514 | 150× |
| Retained destructor state | 0.00369 | 0.609 | 165× |
| Implied references | 0.00602 | 0.0670 | 11× |
| Depth six | 0.0199 | 0.192 | 9.6× |
| Depth twenty | 0.0412 | 0.940 | 23× |

Removing Collection's omission bookkeeping is expensive even when incremental
pruning is retained: the `collection_pruned` control is approximately 6× slower
on implied references and 17× slower at depth twenty than `broad`. Thus the
regression is not merely the cumulative removal of several optimizations.
The simplest variant also increases peak construction allocation at depth
twenty from about 1.5 MiB to 7.5 MiB.

The controls isolate the other costs too. Removing only incremental Vanish
pruning (`unpruned`) makes depth-twenty construction about 9.4× slower.
Removing reader pruning as well (`no_pruning`) makes written-reference
construction about 3× slower than `broad`. Using the plain ordered Comparison
while keeping Collection and pruning (`broad_ordered`) costs about 89% on wide
uses, 38% on implied references, and 28% on local reuse in this small matrix.

The initial 20,000-step sweep completed eight family/seed cases before a wide
case exceeded the 180-second child-process limit. The sweep was then stopped;
its partial results and timeout are preserved. That limit covers generation,
all variants' timed repetitions, fingerprinting, and separate memory runs, so
the timeout is not a measured construction time for any individual variant.
The completed 2,000-step matrix tests all ten variants; larger runs concentrate
on the three viable alternatives.

## Recommendation

Keep the existing Collection omissions, cheap incremental reader and Vanish
candidate pruning, and specialized Comparison. Their benefits are substantial;
the spec need not describe every implementation shortcut that constructs the
same dependencies.

Broad recording is a reasonable simplicity choice, not a performance win. It
removes the per-operation ordinary-occupancy filter, agrees with the spec, and
passes the independent oracle, but retaining that filter is faster for some
important patterns. Likewise, separate Vanishes match the spec directly, with
a measurable cost in some patterns and a benefit in others. No new semantic
rule is needed. These experiments do not replace the archived implementation
or the implementation in Define.

## Reproducing the measurements

Run `uv run --frozen -m operation_graph_optimization.simplification_benchmark`
with a new `--destination` filename. The result files preserve the exact child
commands and source snapshots:

- `simplification_sweep_results.jsonl`: partial 20,000-step, two-seed sweep,
  three repetitions and separate allocation measurements.
- `simplification_small_results.jsonl`: complete 2,000-step, two-seed matrix of
  all ten variants, three repetitions and separate allocation measurements.
- `simplification_scale_results.jsonl`: complete 100,000-step, three-seed matrix
  of `early,separate,broad`, three repetitions, without allocation tracing.
- `simplification_million_results.jsonl`: four million-step families, seed 17,
  three repetitions of `early,separate,broad`, without allocation tracing.
- `simplification_memory_results.jsonl`: five 100,000-step families, seed 17,
  one untimed allocation measurement per variant, after one untraced timing.

These finite workloads establish equivalence on the tested cases and expose
specific costs; they do not prove optimality over all valid programs.

## Validation

Repository-wide Bazel coverage passes all 17 test targets. The new test target
runs 87 cases, each comparing all ten variants with the independent oracle.
Ruff lint and formatting checks and Basedpyright pass for all new Python files.

Coverage inspection still reports 62 uncovered branch outcomes across the
variant copies and experiment helper. These include archived Comparison fast
paths, the unused `forget` interface, and fingerprinting, which the benchmark
exercises outside the coverage run. This is not a claim of complete branch
coverage. No production compiler code or spec text was changed by this
experiment.
