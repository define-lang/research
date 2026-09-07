# Cached-target limit

Keep 1,024 targets with the 64-MiB byte ceiling. It is a well-supported default
on the tested workloads, not a proven uniquely optimal count. The measured
performance plateau starts around 512 targets. Removing the target ceiling did
not consistently improve speed and retained more data.

This investigation changes neither the algorithm nor the specification.

## Scope and method

[Raw measurements](target_sizing_results.json) record 154 clean timing runs and
three separate occupancy probes. All 157 runs passed the independent randomized
execution check. These are not exhaustive checks of all execution schedules; the
previously validated implementation is unchanged.

Only graph construction is timed. Valid-operation generation, input reordering,
and execution checks happen outside that timer. Processes ran sequentially
without concurrent benchmarks or tests on an unreserved, unpinned host using
CPython 3.14.7 on 2026-09-06. Screening and confirmation execution orders were
shuffled independently; the artifact records that procedure and all arguments.

The byte ceiling stays at 64 MiB. The initial 110 runs compared 64, 256, 1,024,
4,096, and effectively unlimited targets across:

- All eleven structured families: interleaved and overlapping Moves, preceding
  uses, implied uses, shared parents, vacancy reuse, simultaneous destruction,
  shared joins, long vacancy reuse, chained references (`deep --width 6`), and
  multiple shared parents.
- All five state-driven distributions at 100,000 statements, each with seeds 17
  and 41: balanced, uniform concrete choices, growth, movement, and destruction.
- Growth with 100,000 statements and seed 41, independently reordered with
  seed 97.

Another 20 runs checked 512 and 2,048 on all five state-driven distributions and
both seeds. Eighteen large runs compared 512, 1,024, and unlimited targets on
every distribution at one million statements, plus a second growth seed. Six
additional growth runs brought the close comparison on that second seed to three
repetitions per setting.

"Unlimited" uses the existing parameter set to 67,108,865. Every cached target
has at least one logical byte, so the 64-MiB byte ceiling prevents that count
from ever binding. This exactly models byte-only eviction without modifying the
implementation. The separate bookkeeping for repeated-expense admission remains
unchanged.

## Performance

Small target limits mainly hurt growth. At 100,000 statements, 64 targets took
about 2.37–2.51 seconds on ordinary growth, versus 2.00–2.06 at 1,024. Reordered
growth took 3.131 versus 2.591 seconds. Above 256, small growth results were
close. Other distributions and structured families showed no consistent benefit
from increasing the ceiling.

Construction seconds at one million statements follow. Entries are single runs
except the last row, which reports medians of three repetitions on identical
input.

| Distribution and seed        | 512 targets | 1,024 targets | No target ceiling |
| ---------------------------- | ----------: | ------------: | ----------------: |
| Balanced, 17                 |       3.033 |         3.042 |             3.062 |
| Uniform concrete choices, 17 |      23.977 |        24.023 |            23.914 |
| Growth, 17                   |      23.820 |        23.776 |            23.786 |
| Movement, 17                 |      11.297 |        11.257 |            11.324 |
| Destruction, 17              |       2.442 |         2.464 |             2.474 |
| Growth, 41; median of three  |      23.890 |        23.594 |            23.622 |

The repeated growth measurements were:

| Target ceiling | Minimum | Median | Maximum |
| -------------- | ------: | -----: | ------: |
| 512            |  23.828 | 23.890 |  23.980 |
| 1,024          |  23.527 | 23.594 |  23.699 |
| None           |  23.606 | 23.622 |  23.892 |

The 512-target median was about 1.25% slower than 1,024 on that input. The
uncapped median differed from 1,024 by only 0.12%, with overlapping observed
ranges. Three repetitions on an unreserved host are not a precise statistical
estimate: treat 1,024 and uncapped as tied, not as evidence of a tiny universal
speed advantage. Smaller differences on other inputs likewise do not establish
winners. No real-program frequency distribution is assumed, so unrelated
workload times are not added into a supposedly universal score.

## Memory and actual byte pressure

Separate probes on million-statement growth with seed 17 measured:

| Target ceiling        | Peak logical cache MiB | Peak targets | Evictions | Requests encountering byte pressure |
| --------------------- | ---------------------: | -----------: | --------: | ----------------------------------: |
| 512                   |                  26.95 |          512 |    14,284 |                                   0 |
| 1,024; previous probe |                  58.11 |        1,024 |    13,730 |                                   0 |
| None                  |                  64.00 |        1,478 |    13,516 |                              11,131 |

The 1,024 row comes from the [previous measurements](cache_sizing.md), with
identical algorithm and graph hashes and the same input. That probe allowed 128
MiB but never needed 64 MiB, so its cache behavior is the same at 64 MiB. The
two new growth probes keep the 64-MiB ceiling.

**Removing the target ceiling makes this existing workload hit the byte
ceiling.** This directly tests byte-only limiting under sustained pressure,
unlike the earlier runs that never needed 64 MiB. It did not produce a speed
advantage. The uncapped run allocated 14,750 columns in total, versus 14,754 at
1,024: many additional retained entries did not avoid another allocation on this
input.

For 100,000 uniform-choice statements, uncapped retention reached 1,219 targets
and 3,442,499 bytes (3.28 MiB), with no evictions. The earlier 1,024-target
probe reached 2,908,770 bytes (2.77 MiB) and evicted 195 targets. Both made
exactly 5,863 column requests and 1,219 allocations. Here, the extra retained
entries did not prevent any later allocation.

These are logical bytearray lengths, not isolated RSS measurements. Object,
dictionary, allocator, and temporary growth costs are additional. Probes add
mock call records and timing overhead; their timings and process memory peaks
are excluded from the performance comparison.

## Decision and limitations

Retain 1,024 targets: it reaches the measured speed plateau, avoids the small
repeated-growth penalty observed at 512, and retains less data than uncapped
caching without a demonstrated loss in speed. This follows the preference for
time provided memory remains reasonable.

512 is a defensible lower-memory alternative: its logical cache peak on the
measured growth input was less than half as large. It is not consistently
faster. Larger limits, including no target ceiling, demonstrated no reason to
change the default. The previous million-statement sweep also found 256 slower
than 1,024 and no useful gain at 4,096; those older measurements are supporting
evidence, not repetitions of this experiment.

This does not prove that 1,024 is uniquely optimal, test every integer between
sampled limits, or guarantee the same plateau on unseen programs. Nor does it
prove a target ceiling is indispensable alongside a byte ceiling. It establishes
a practical choice among tested policies across varied valid workloads,
including independently reordered input and actual byte pressure.

## Reproduction

After the repository's local-development setup, for example:

```sh
uv run -m operation_graph_optimization.benchmark --workload state --distribution growth --steps 1000000 --seed 41 --cache-mib 64 --cache-targets 512
uv run -m operation_graph_optimization.benchmark --workload state --distribution growth --steps 1000000 --seed 41 --cache-mib 64 --cache-targets 1024
uv run -m operation_graph_optimization.benchmark --workload state --distribution growth --steps 1000000 --seed 41 --cache-mib 64 --cache-targets 67108865
```

The raw artifact records all workload arguments and execution order. The
separate probe uses the exact `diagnostic_probe` script archived in
`cache_sizing_results.json`, as described in
[its reproduction instructions](cache_sizing.md#reproduction-and-future-tuning).
Byte-pressure counters count requests, not individual evictions.
