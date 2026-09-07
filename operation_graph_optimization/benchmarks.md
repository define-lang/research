# Structured baseline benchmark results

These results cover the original structured workload families. The separate
[state-driven measurements](state_benchmarks.md) freely mix valid caller
statements and expose a substantial growth-heavy performance problem absent from
these earlier families.

These are historical measurements of the baseline implementation. See the
[follow-up experiments](optimization_experiments.md) for the current algorithm
and its measurements; the raw baseline records remain unchanged.

Measured on 2026-09-06 with CPython 3.14.7 on an AMD Ryzen 9 9950X (16 cores, 32
logical CPUs, boost disabled, reported maximum 4.3 GHz), Linux
7.1.8-200.fc44.x86_64, glibc 2.43. The machine reported about 60.5 GiB RAM. Runs
were separate, sequential processes, without concurrent test or benchmark runs
from this investigation. They were not CPU-pinned and the host was not reserved
exclusively for these measurements.

[Raw results](benchmark_results.json) include all timings, counts, seeds, memory
measurements, limits, and hashes of the measured Python files.

## Large workloads

Each row has three runs with seeds 17, 41, and 97. Every run passed independent
randomized execution checks. Times below are graph calculation alone; memory
includes input generation and retained input objects. The final column also
includes the independent checker. Peaks are the maximum across the three runs,
not estimates obtained by subtracting process high-water marks.

| Workload        |   Steps |  Width | Operations | Calculation range (s) | Median (s) | Peak through calculation (MiB) | Entire process peak (MiB) |
| --------------- | ------: | -----: | ---------: | --------------------: | ---------: | -----------------------------: | ------------------------: |
| interleaved     | 1000000 |  10000 |  1,020,000 |           1.194–1.214 |      1.202 |                          197.4 |                     261.9 |
| overlapping     | 1000000 |   1000 |  1,002,000 |           5.250–5.285 |      5.280 |                          243.1 |                     290.0 |
| uses            |  500000 |    100 |  1,000,200 |           1.840–1.868 |      1.840 |                          434.5 |                     516.5 |
| implied         |  500000 |   1000 |  1,002,000 |           1.080–1.083 |      1.081 |                          292.0 |                     331.6 |
| shared          |  500000 |     10 |  1,000,043 |           1.468–1.479 |      1.473 |                          192.3 |                     261.6 |
| vacancy         |  250000 |      1 |  1,000,004 |           2.333–2.347 |      2.341 |                          391.4 |                     474.7 |
| destruction     |  500000 |    100 |  1,000,200 |           2.605–2.759 |      2.703 |                          523.4 |                     567.4 |
| shared_join     |  166667 | 166667 |  1,000,009 |           2.192–2.214 |      2.213 |                          341.1 |                     418.4 |
| vacancy_long    |   15000 |      1 |  1,020,004 |           1.854–1.869 |      1.868 |                          201.3 |                     267.2 |
| deep            |   10000 |     64 |     30,399 |           1.940–1.957 |      1.949 |                          116.4 |                     116.4 |
| multiple_shared |  500000 |   1000 |  1,043,000 |           1.857–1.864 |      1.864 |                          461.5 |                     536.9 |

Ten of these rows calculate approximately one million operations each. The
deep-reference row instead has 1,347,032 position requirements and 1,286,816
particle requirements across 30,399 operations. It also constructs matching
source text during generation. Its width parameter is reference depth.

Workload meanings:

- `interleaved`: randomly interleaved independent particles moving between
  locals.
- `overlapping`: random movement to vacant locals, with overlapping
  dependencies.
- `uses`: many independent child uses before the defining particles' vacancy.
- `implied`: repeated direct implied access to positions supplied by a Create.
- `shared`: child operations through a shared parent after its Move.
- `vacancy`: a new particle visits old vacancies in a new randomized order.
- `destruction`: large randomly enumerated simultaneous selections.
- `shared_join`: many old vacancies followed by a common dependency and a long
  independent sequence, then direct implied reuse of those vacancies.
- `vacancy_long`: old vacancies whose former particles have long independent
  subsequent sequences.
- `multiple_shared`: 1,000 independent copies of the shared-parent pattern, with
  randomized interleaving of their child operations.
- `deep`: defining particles move, followed by child operations through long
  written references.

Generation took approximately 0.55–1.18 seconds in the million-operation runs.
Execution checking usually took 1.44–2.75 seconds; `shared_join` took
13.33–13.40 seconds. Those costs are not included in the calculation column. The
raw data keeps them visible rather than attributing all process time to the
algorithm or omitting verification cost.

For each table row, use its workload, steps, and width with:

```sh
uv run -m operation_graph_optimization.benchmark --workload overlapping --steps 1000000 --width 1000 --seed 17
```

Repeat with seeds 41 and 97. The default limits used were 2 GiB virtual address
space and 120 CPU seconds per process. The algorithm retained at most eight
memoized target columns within a 64 MiB logical-byte budget. Source setup and
the remaining options are described in the [README](README.md).

## Cache trade-off

Separate smaller runs compared the same final algorithm with and without its
optional cache, using seed 17. These are single-run comparisons, not a claim
about a statistical distribution.

| Workload        |  Steps | Width | Cache off (s) | Cache on (s) |
| --------------- | -----: | ----: | ------------: | -----------: |
| overlapping     | 100000 |  1000 |         0.475 |        0.503 |
| shared          |   5000 |    10 |         0.015 |        0.015 |
| shared_join     |   5000 |  5000 |         7.066 |        0.060 |
| multiple_shared |  50000 |   100 |         0.173 |        0.172 |

The bounded cache costs about 6% on this random-overlap comparison and avoids
repeated long searches in the shared-dependency case. The shared-parent cases
now use the stronger remembered-use rule and no longer depend on caching.
Turning it off changes neither the rules nor the graph. Reproduce the uncached
column with `--cache-targets 0`.

Earlier experiments rejected eager path indexing, one-query cache admission,
backward-only searching, and immutable use lists; their structural reasons are
in [the analysis](analysis.md#alternatives-evaluated). The final raw results do
not mix timings from those superseded implementations.

## What these results establish

The implemented rule calculation handles these large, valid-operation families
with practical time and memory, including randomized source orders and runtime
schedules. The measured memory includes a materialized operation list; a caller
can stream ordinary operations and release proven-dead analysis records.

These measurements are not a worst-case bound, an enterprise application
benchmark, or a proof of universal time optimality. Memory for source
resolution, action expansion, and lifetime analysis is outside the measured
algorithm. The [complexity analysis](analysis.md#bounds-and-scope) accounts
explicitly for reachability work and retained-state copies instead of claiming
linear total time for every valid program.
