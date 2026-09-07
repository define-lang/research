# Follow-up optimization experiments

The result is [algorithm.py](algorithm.py), with [graph.py](graph.py) providing
storage and reachability searches. [The rule description](rules.md) includes the
creation shortcut and its justification. No specification change is required:
these shortcuts calculate the same Comparison result. There is still no
whole-graph transitive minimization pass.

This is the best measured default from this investigation, not a proof of
universal time optimality. It substantially improves the difficult state-driven
patterns without unbounded indexing. It does not win every pattern.

The subsequent [cache-sizing investigation](cache_sizing.md) separates actual
cache demand from its ceiling and extends the byte-budget measurements without
changing this implementation.

[Threshold tuning](thresholds.md) subsequently names the three algorithm
thresholds, raises the two optional-work limits to 16, and retains the
Comparison crossover at 64. The measurements below describe the earlier
settings.

## What changed

- A later supplier or use of a particle's assigned position covers that
  particle's Create **regardless of why the Create was collected**. This avoids
  expensive searches that merely rediscover creation requirements.
- Ordinary operations prune remembered uses using collected candidates, not just
  final direct dependencies. Comparison already proves that the operation
  follows every collected candidate.
- Two candidates need no sort. Equal-height candidates are independent.
  Collections of up to 64 candidates otherwise use pairwise questions; wider
  collections use shared traversal after cheap direct-dependency omissions.
- Reachability searches use both heights and occurrence identifiers as bounds.
  They search breadth-first from both ends; this was a better default on the
  mixed growth and uniform-choice patterns.
- Cached target columns cover only the target through its latest queried
  following occurrence. They do not allocate the unused graph prefix or suffix.
  The default permits 1,024 targets sharing a 64-MiB logical byte budget.
  Allocation is demand-driven, not a reservation of 64 MiB for every
  compilation.

The inductive creation argument, candidate-coverage argument, search
correctness, and memory accounting are in [the derivation](analysis.md).

## Screening experiments

All times are graph construction alone, in seconds. These were exploratory
single-run comparisons, not confidence intervals. Some rows describe cumulative
implementation steps; they must not be added together as independent speedups.
The recorded parameter sweeps and directional comparisons are preserved in
[the raw results](optimization_results.json).

| Experiment                                                                         | Evidence                                                                                                                                 | Decision                                                                                                  |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Selected greatest-height dependency path, with jump pointers                       | 25,000 growth statements: 2.38 s versus the 2.40 s baseline                                                                              | Reject: extra per-operation storage did not materially help                                               |
| Cache complete ancestor rows as well as target columns                             | 25,000 growth statements: 2.66 s in the cumulative prototype                                                                             | Reject: more memory and no improvement                                                                    |
| Apply creation coverage across collection reasons                                  | 25,000 growth statements: 0.85 s with the original graph search                                                                          | Keep                                                                                                      |
| Retain pruned uses as extra occupancy witnesses                                    | Early improvement to 0.74 s at 25,000 statements; later, removing that storage improved the million-statement case from 27.36 to 26.58 s | Reject from the final design                                                                              |
| Breadth-first versus depth-first, with the same collection and range-sized columns | Growth at 100,000 statements: 2.10 versus 2.26 s; uniform concrete choices: 2.20 versus 2.38 s                                           | Prefer breadth-first; depth-first was slightly faster on overlapping Moves and the small shared-join case |
| Shared traversal above 16 rather than 64 candidates                                | Growth at 100,000 statements: 2.67 versus 2.07 s                                                                                         | Keep the 64-candidate threshold                                                                           |
| Range-sized versus whole-prefix columns                                            | One million growth statements: 27.36 versus 43.20 s in the same cumulative prototype                                                     | Keep range-sized columns                                                                                  |
| 64, 256, or 1,024 cached targets, still capped at 64 MiB                           | One million growth statements: 35.83, 24.99, and 23.92 s                                                                                 | Prefer 1,024 targets                                                                                      |
| Increase target limit to 4,096                                                     | One million growth statements: 24.08 s, with greater process peak memory                                                                 | No demonstrated benefit                                                                                   |
| 16, 64, or 256 MiB cache budget, with 1,024 targets                                | One million growth statements: 24.53, 23.74, and 23.74 s                                                                                 | Keep 64 MiB; the larger budget gave no measurable benefit                                                 |
| Immediately accept an entirely equal-height collection                             | Large preceding-use case: 1.73 s in the final matrix, versus 1.93 s before this shortcut                                                 | Keep                                                                                                      |

Extra historical-use storage also increased the shared-parent workload's
after-construction process peak from about 192 to 280 MiB and its construction
time from 1.51 to 1.67 s. Those peaks are cumulative process measurements, not
isolated sizes of that data structure.

## Final measurements

Measured on 2026-09-06, CPython 3.14.7, on the same Ryzen 9950X machine as
[the baseline measurements](state_benchmarks.md). Processes ran sequentially;
the machine was not reserved or CPU-pinned. Some exploratory runs overlapped
formatting or targeted tests. The final matrix did not overlap another benchmark
or a test run.

**The graph timer starts only after all operation selection and input reordering
have finished.** It includes Calculator initialization, Collection, Comparison,
record updates, graph storage, and cache maintenance. Generation, reordering,
and independent execution checks have separate timers.

A 55-run matrix covered all eleven structured families and all five state
distributions across three seeds, plus seven independent input reorderings.
After the final equal-height shortcut, a further 33-run matrix repeated all five
state distributions across all three seeds, all eleven structured families at
seed 17, and all seven reorderings. The earlier matrix remains in the raw data
with its own source hash; it is not relabeled as a measurement of the final
file.

The subsequent lint cleanup only combined equivalent conditions and added local
lint annotations. Recursive compilation checks confirmed identical executable
bytecode, constants, and calling metadata. The raw data includes both source
hashes and a patch restoring the exact measured source.

### One million state-driven caller statements

Seeds 17, 41, and 97; width 100, depth 4, branching 2, local access.

| Distribution             | Baseline graph time (s) | Final graph time (s) |
| ------------------------ | ----------------------: | -------------------: |
| Balanced kinds           |             3.430–3.465 |          3.020–3.058 |
| Uniform concrete choices |           37.629–39.866 |        23.680–23.969 |
| Movement-heavy           |           10.472–10.703 |        11.256–11.407 |
| Destruction-heavy        |             2.648–2.749 |          2.528–2.594 |
| Growth-heavy             |     No completed result |        23.745–23.823 |

The old growth runs exceeded a 120-CPU-second **whole-process** limit. That is
not a measured graph time. The final growth runs construct approximately 2.52
million expanded operations and pass execution checks. The preserved baseline
failures must not be interpreted as completed or validated graphs.

### Structured families

These are the final seed-17 runs, compared with the same baseline seed and
sizes. The preceding 55-run matrix tested all three seeds for these families.

| Family          | Baseline graph time (s) | Final graph time (s) |
| --------------- | ----------------------: | -------------------: |
| interleaved     |                   1.214 |                1.210 |
| overlapping     |                   5.250 |                4.144 |
| uses            |                   1.868 |                1.732 |
| implied         |                   1.080 |                1.122 |
| shared          |                   1.473 |                1.457 |
| vacancy         |                   2.341 |                2.126 |
| destruction     |                   2.605 |                2.599 |
| shared_join     |                   2.213 |                2.288 |
| vacancy_long    |                   1.869 |                1.767 |
| deep            |                   1.957 |                0.363 |
| multiple_shared |                   1.857 |                1.810 |

The deep family uses 65-name references and about 30,400 operations. Most other
structured families have approximately one million operations. The exact sizes
and requirement counts are in the raw records.

### Independently reordered inputs

Generation seed 17. These orders come from the separate, unreduced conflict
graph, not from the optimized builder's graph. Reordering remains outside the
graph timer.

| Input                       | Reorder seed | Reordering (s) | Graph construction (s) | Whole-process peak (MiB) |
| --------------------------- | -----------: | -------------: | ---------------------: | -----------------------: |
| growth, depth 4, local      |           41 |         12.218 |                 31.851 |                   1670.6 |
| concrete, depth 4, local    |           97 |          5.653 |                 26.256 |                    813.1 |
| balanced, depth 4, local    |           41 |          6.510 |                  3.519 |                   1137.8 |
| balanced, depth 4, local    |           97 |          6.553 |                  3.517 |                   1141.9 |
| balanced, depth 12, implied |           41 |          6.963 |                  3.231 |                   1259.8 |
| overlapping                 |           41 |          3.432 |                  4.892 |                    668.4 |
| shared                      |           41 |          3.714 |                  1.479 |                    695.8 |

Ordinary growth runs peaked at 1099.0 MiB for the complete process, including
inputs and the independent checker. Reordered growth also includes the
reorderer's large temporary structures. None of these figures is an isolated
graph-memory measurement. Base graph storage remains approximately `24N + 24E`
bytes, in addition to position records, use sets, allocation overhead, and the
bounded cache.

## Trade-offs and limits

The default favors the difficult mixed workloads. Movement-heavy generation is
about 6–8% slower than the baseline. The implied-use and shared-join structured
cases are also slightly slower in the final seed-17 comparison. Their exact
figures are shown rather than hidden by an overall average. Breadth-first search
was not uniformly faster than depth-first in screening.

A smaller target limit reduces cache storage on some programs but can repeat
substantial work; increasing the byte budget beyond the working set buys
nothing. The defaults bound both entry count and logical bytes. Applications
with tighter memory constraints can lower those limits without changing the
calculated graph. Full transitive closure, unbounded indexes, extra historical
use sets, and the selected-path prototype are not retained.

The valid-source fixtures have the scope described in
[state_workloads.md](state_workloads.md); they do not exercise every possible
contract or destructor body. Existing targeted destructor and implied-access
integration cases remain necessary. Arbitrary dependency reachability can be
expressed by valid source, as shown in the derivation, so these results do not
prove a linear worst-case construction time or a universally optimal algorithm.

## Verification

All 88 large and independently reordered runs passed their execution checks, as
did the 27 recorded screening runs. Small integration cases compare exact
dependencies with the independent full-history reference, not the compiler's
current graph. The two integration targets contain 111 and 51 cases, including
the new wide real-source case and the enlarged independent-use case.

Repository-wide coverage passed all 357 test targets. The coverage analyzer
reported zero actionable uncovered branches in the investigation code; nine
explicit-exit-only branches were omitted. Bazel linting and type checking also
passed. The final lint cleanup was verified to preserve executable bytecode. The
production compiler was not modified, and nothing was committed.

## Reproduction

Generate the local development environment as described in the README, then:

```sh
uv run -m operation_graph_optimization.benchmark --workload state --steps 1000000 --distribution growth --seed 17
uv run -m operation_graph_optimization.benchmark --workload state --steps 1000000 --distribution concrete --seed 41
uv run -m operation_graph_optimization.benchmark --workload state --steps 1000000 --distribution growth --reorder-seed 41 --memory-mib 4096 --cpu-seconds 300
uv run -m operation_graph_optimization.benchmark --workload state --steps 1000000 --distribution growth --cache-targets 64 --cache-mib 16
```

The raw final records contain every run's arguments and the measured source
hashes. Defaults are a 2-GiB virtual-address-space limit and 120 CPU seconds for
the entire process; some reordered cases explicitly raise those limits.

To reproduce the old implementation, use a disposable copy of the investigation
files, apply [restore_baseline.patch](restore_baseline.patch), and specify
`--cache-targets 8`. The patch restores the exact baseline algorithm and graph
hashes without modifying the production compiler. It is an experiment archive,
not part of the resulting algorithm. Do not apply it over work you want to keep.
