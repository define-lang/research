# State-driven baseline benchmark results

Measured on 2026-09-06 on the same machine as the
[structured-workload measurements](benchmarks.md). The rule algorithm and graph
implementation were unchanged from the earlier structured measurements; file
hashes, full arguments, successful results, and failed runs are preserved in
[the raw data](state_benchmark_results.json). Runs used separate, sequential
processes. The machine was not reserved or CPU-pinned; documentation formatting
occasionally ran concurrently.

This document preserves the baseline, including its failures. The implementation
has since changed; see [the follow-up experiments](optimization_experiments.md)
for current measurements. Commands below describe the baseline workload inputs,
not a claim that today's code reproduces the old timings.

**Every graph-construction time below excludes operation selection, source
generation, input reordering, and execution validation.** The timer starts after
the entire input list is ready and covers initialization of the Calculator and
calculation of the graph. Other phase timings remain separate in the raw data.

## One million randomized caller statements

Each distribution used seeds 17, 41, and 97, width 100, depth 4, branching 2,
and local access. There was no input reordering in this first comparison: the
state-driven generator itself freely mixed valid statements. The extra
constructor operations and transitive Destroys explain why operation counts
exceed statement counts. The distributions and precise supported fixture are
described in [State-driven randomized workloads](state_workloads.md).

| Distribution             | Expanded operations |                      Graph construction (s) | Maximum whole-process peak (MiB) |
| ------------------------ | ------------------: | ------------------------------------------: | -------------------------------: |
| Balanced kinds           | 1,692,969–1,694,612 |                                 3.430–3.465 |                            604.5 |
| Uniform concrete choices | 1,029,758–1,030,231 |                               37.629–39.866 |                            450.3 |
| Movement-heavy           | 1,151,215–1,152,122 |                               10.472–10.703 |                            354.3 |
| Destruction-heavy        | 1,919,282–1,920,035 |                                 2.648–2.749 |                            699.2 |
| Growth-heavy             | No completed result | All three runs killed at the resource limit |                     Not reported |

The growth runs exited with SIGKILL after approximately 120 seconds, under a
120-CPU-second process limit and a 2-GiB virtual-address-space limit. **That is
not a measured 120-second graph-construction time:** the process budget covers
all phases, and those runs did not reach the final timing report or schedule
validation. A separate generation-only run for seed 17 produced 2,521,256
operations in 6.672 seconds with a 462.1-MiB peak. Generating the input is not
the large cost demonstrated by the smaller completed runs below.

Every completed run passed randomized execution checks of exact particle
identities and occupancy. The failed runs are not counted as validated graphs.

## Growth-heavy size series

These use seed 17 and the same shape and default cache settings as above. Both
columns are shown to make the timing distinction explicit.

| Caller statements | Expanded operations | Input generation (s) | Graph construction (s) |
| ----------------: | ------------------: | -------------------: | ---------------------: |
|            10,000 |              23,351 |                0.063 |                  0.207 |
|            25,000 |              60,750 |                0.163 |                  2.400 |
|            50,000 |             124,245 |                0.325 |                  8.847 |
|           100,000 |             249,946 |                0.706 |                 26.041 |

The growth is much faster than the increase in operation count in this sample;
this is an empirical scaling problem, not a proved asymptotic bound. A separate
10,000-statement profiling check identified Comparison and dependency
reachability searches as the main graph-construction cost.

At 25,000 statements, graph construction took 1.717 seconds with caching off,
2.400 seconds with the default eight cache targets, and 2.221 seconds with 32
targets. These are single-run comparisons. Increasing the cache alone does not
resolve the observed problem, and turning it off is not a universal solution:
the older shared-dependency experiment benefited substantially from caching.

## Reordered and implied-access inputs

These use generation seed 17. Input order is chosen by the independent
conflict-graph helper, not the rule algorithm. Reordering is timed separately.
Memory peaks include that helper and its temporary structures; they are not
isolated memory measurements of graph construction.

| Workload                          | Expanded operations | Reorder seed | Reordering (s) | Graph construction (s) | Whole-process peak (MiB) |
| --------------------------------- | ------------------: | -----------: | -------------: | ---------------------: | -----------------------: |
| Balanced state, depth 4, local    |           1,693,524 |           41 |          6.797 |                  4.144 |                  1,051.4 |
| Balanced state, depth 4, local    |           1,693,524 |           97 |          7.009 |                  4.058 |                  1,050.1 |
| Balanced state, depth 12, implied |           1,707,432 |         None |              — |                  3.222 |                    688.0 |
| Balanced state, depth 12, implied |           1,707,432 |           41 |          7.162 |                  3.563 |                  1,190.2 |
| Overlapping Moves                 |           1,002,000 |           41 |          3.595 |                  5.920 |                    581.1 |
| Shared-parent pattern             |           1,000,043 |           41 |          3.826 |                  1.574 |                    696.5 |

The implied cases used width 20; the local state cases used width 100. Depth 12
is the fixture's permitted depth, not a guarantee that random sampling reached
it: those runs had at most six combined intermediate-position requirements in
one operation. The older targeted deep-reference workload remains necessary.

## Conclusions and reproduction

Across these 27 graph-construction attempts, 24 completed and passed schedule
validation; three growth-heavy attempts hit the resource limit. The sampler, its
exhaustive choice checks, and the independent input reorderer are in place. The
results exposed a performance weakness that the earlier structured patterns
missed. They did not justify calling that implementation uniformly efficient at
this scale, let alone universally optimal. These records are unchanged by the
subsequent optimization work.

Every raw record includes its complete benchmark arguments. For example:

```sh
uv run -m operation_graph_optimization.benchmark --workload state --steps 100000 --width 100 --distribution growth --seed 17
uv run -m operation_graph_optimization.benchmark --workload state --steps 1000000 --width 100 --distribution concrete --seed 17
uv run -m operation_graph_optimization.benchmark --workload state --steps 1000000 --width 100 --distribution balanced --reorder-seed 41 --seed 17
```

Setup and additional generator details are in [the README](README.md) and
[the workload description](state_workloads.md). Repository-wide coverage passed
all 357 test targets, including 51 new integration cases. Coverage analysis
found no actionable uncovered branches in the investigation code.
