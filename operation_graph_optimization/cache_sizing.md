# Cache sizing

Keep the current 64-MiB byte ceiling and 1,024-target ceiling. The cache already
allocates on demand and admits targets only after repeated expensive searches;
64 MiB is not reserved for every graph. These are measured defaults, not a
universal optimum. No algorithm or specification changes were made in this
follow-up.

The subsequent [target-count investigation](target_sizing.md) varies the other
ceiling, including removing it. That experiment does reach the 64-MiB byte
ceiling on the existing growth workload and retains the same defaults.

## Measurements

[Raw records](cache_sizing_results.json) contain 38 uninstrumented timing runs
and seven separate diagnostic runs, including the exact diagnostic script and
source hashes. All 45 runs passed the independent randomized execution check.
These checks are not exhaustive schedule verification; the implementation is
unchanged from the previously validated version.

Measurements used CPython 3.14.7 on 2026-09-06. Processes ran sequentially,
without concurrent benchmark or test runs, on an unreserved, unpinned machine.
Each table entry is a single run; different seeds are different inputs, not
repetitions. Small timing differences should not be interpreted as statistically
significant. Earlier measurements remain in
[the optimization report](optimization_experiments.md).

Only graph construction is timed, including cache maintenance. Valid-operation
selection, input reordering, and independent execution checks are excluded.
Diagnostic timings and resident-memory measurements are excluded from the
performance comparison because instrumentation adds overhead and retains mock
call records.

### Byte-budget sweep

Graph construction seconds, with the target ceiling fixed at 1,024:

| Workload                                                                  | No cache | 1 MiB | 4 MiB | 16 MiB | 32 MiB | 64 MiB | 128 MiB |
| ------------------------------------------------------------------------- | -------: | ----: | ----: | -----: | -----: | -----: | ------: |
| Growth, 100,000 statements, seed 17                                       |    3.122 | 2.939 | 2.250 |  2.073 |  2.091 |  2.064 |   2.053 |
| Uniform concrete choices, 100,000 statements, seed 17                     |    2.017 | 2.182 | 2.170 |  2.176 |  2.195 |  2.185 |   2.182 |
| Movement-heavy, 100,000 statements, seed 17                               |    0.978 | 1.111 | 1.123 |  1.115 |  1.108 |  1.113 |   1.116 |
| Shared join, 120,007 expanded operations                                  |  108.998 | 0.256 | 0.256 |  0.256 |      — |  0.259 |       — |
| Growth, 1,000,000 statements, seed 17                                     |        — |     — |     — | 24.133 | 23.932 | 23.751 |  23.688 |
| Growth, 1,000,000 statements, seed 41                                     |        — |     — |     — | 24.456 | 23.780 | 23.761 |  23.794 |
| Growth, 100,000 statements, seed 41, independently reordered with seed 97 |        — | 3.210 |     — |  2.578 |      — |  2.576 |   2.597 |

The million-statement inputs expand to about 2.52 million operations. Unlisted
combinations were not run in this sweep. The previous investigation also tested
256 MiB on million-statement growth and larger target ceilings; neither showed a
useful improvement over the current defaults.

### Actual allocation and eviction

With a 128-MiB allowance, these diagnostic runs measured the following logical
cache peaks. None encountered byte-budget pressure.

| Workload                                     | Peak bytes | Peak MiB | Peak targets | Evictions due to target ceiling |
| -------------------------------------------- | ---------: | -------: | -----------: | ------------------------------: |
| Million-statement growth, seed 17            | 60,935,336 |    58.11 |        1,024 |                          13,730 |
| Million-statement growth, seed 41            | 60,414,785 |    57.62 |        1,024 |                          13,823 |
| Reordered 100,000-statement growth           | 24,046,357 |    22.93 |        1,024 |                             679 |
| Uniform concrete choices, 100,000 statements |  2,908,770 |     2.77 |        1,024 |                             195 |
| Movement-heavy, 100,000 statements           |  1,550,694 |     1.48 |          616 |                               0 |
| Shared join, 120,007 expanded operations     |     60,003 |    0.057 |            1 |                               0 |

For these inputs, 64 and 128 MiB permit exactly the same cache behavior, not
merely similar measured performance: the larger-budget run never needs 64 MiB,
and every possible target-to-query range is smaller than 64 MiB. Starting from
the same state, neither budget changes admission or eviction decisions. The
small timing differences between them are therefore not evidence of a cache
benefit.

For the first growth input, 60,935,336 bytes is sufficient to reproduce the
larger-budget run's cache behavior with the same target ceiling. That is an
input-specific threshold sufficient to avoid additional byte-driven evictions,
**not** a proof that this exact byte count minimizes execution time. Different
eviction decisions at smaller budgets can still be competitive.

At 32 MiB, that same input reached the byte ceiling, encountered byte pressure
on 12,274 column requests, and evicted 14,115 columns. Its peak target count was
837: here bytes, not the target ceiling, constrained the cache. It allocated
14,774 columns in total, compared with 14,754 at 128 MiB. This helps explain why
the added eviction pressure produced only a small timing difference.

Logical cache bytes exclude bytearray spare capacity, object and dictionary
overhead, and transient allocation during growth. They are not a process RSS
limit. The normal benchmark's RSS figures also include generated inputs and
other graph data; they cannot isolate cache memory by subtraction.

## Can the graph choose an exact optimal limit?

Not from its current size or shape alone. Two valid continuations of the same
input can reuse earlier expensive questions differently. A target with no more
queries needs no cache, whereas repeated future queries can make its retention
valuable. Current observations do not reveal which continuation will occur. Even
for a completed workload, wall-clock noise and the choice of acceptable memory
cost prevent treating the fastest single measurement as an exact optimum.

The measured trade-offs also argue against a simple graph-size formula:

- About 59 KiB makes the shared-join case hundreds of times faster.
- The movement-heavy case is faster without caching, although its cache already
  uses very little memory. Reducing the byte ceiling does not remove the cost of
  checking admission and doing memoized work.
- Growth benefits from much more cached state; a small ceiling incurs additional
  searches and allocation, but 64 MiB already exceeds the observed byte needs.

An online controller could sample cached and uncached searches, periodically
probe alternate budgets, and react to changing reuse. That would be a heuristic,
with extra work and potentially delayed reactions when the input changes
patterns. Eviction count alone would be a poor signal: a target never queried
again is harmless to evict. A faithful comparison must account for search work
saved and cache maintenance, not just hit rate. No new controller was
implemented or benchmarked here; these measurements do not justify adding one to
replace the existing demand-driven allocation and repeated-expense admission
policy.

Given the preference for time while keeping memory bounded, retain 64 MiB. 32
MiB is a reasonable lower-memory option with little measured loss on these
growth inputs, but not a demonstrated improvement. Larger byte ceilings have no
benefit on the diagnostic inputs at the current target ceiling. Increasing the
target ceiling is a separate trade-off, already tested in the previous
investigation, not an automatic consequence of having unused byte allowance.

## Reproduction and future tuning

After the repository's local-development setup, the existing benchmark can
measure any byte and target budget, for example:

```sh
uv run -m operation_graph_optimization.benchmark --workload state --distribution growth --steps 1000000 --seed 17 --cache-mib 32 --cache-targets 1024
```

The raw artifact records every run's arguments. Its `diagnostic_probe` field
contains the exact Python script used for the separate occupancy measurements.
Save that field's string as `/tmp/define-cache-diagnostics.py` and run it from
the repository directory with the recorded diagnostic arguments:

```sh
PYTHONPATH=. uv run /tmp/define-cache-diagnostics.py --workload state --distribution growth --steps 1000000 --seed 17 --cache-mib 128 --memory-mib 4096
```

The probe wraps `_column` with `patch.object(..., autospec=True)` without
changing the method's decisions. It measures every column request, allocation,
eviction, and post-request byte and target count. Pressure counters count
requests whose initial state exceeds the respective ceiling, not the number of
evictions attributable to each ceiling when both bind. The reported peak is the
maximum logical cache size, not transient allocation. No probe runs in the
normal algorithm or the uninstrumented timing runs.

For another workload, sweep budgets on identical generated inputs, separately
measure actual occupancy and pressure with a generous budget, and repeat clean
timings around the observed plateau. Keep generation and validation outside the
timer. Repeat across seeds and independently reordered inputs before changing
the default. A cache-request trace alone is insufficient: changing the cache
changes subsequent search paths and therefore the trace itself.

## Specification

The specification is unchanged. Its Comparison already keeps a collected
candidate only if no kept candidate depends on it, directly or indirectly. The
creation-coverage shortcut recognizes one such existing dependency earlier; the
search and cache changes accelerate that same determination. They neither add
nor remove semantic ordering requirements. Cache budgets belong in the
implementation, not in the language specification.
