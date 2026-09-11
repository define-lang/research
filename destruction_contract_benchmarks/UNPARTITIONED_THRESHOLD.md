# Choosing the unpartitioned Child State copy threshold

## Recommendation

Use `_FLAT_LIMIT = 16` as the next default. The evidence supports a substantially
lower threshold, not a uniquely optimal integer: limits 8, 12, and 16 form a
near-tied region in repeated held-out mixtures. Sixteen avoids the additional
lookup cost on the smallest short/read-heavy cases while capturing most of the
memory savings from earlier sharing. It is not chosen because powers of two
are required; they are not.

Across 2,176 fresh-worker measurements, there were no resource failures or
checksum disagreements. In the final 85-case confirmation, limit 16 reduced
the equal-case CPU geometric mean by 7.0% and peak RSS geometric mean by 18.9%
relative to 256. The earlier held-out mixtures showed reductions of 15.1% and
30.3%. These are experimental aggregates, not predicted whole-compiler gains.

This recommendation accepts a real CPU tradeoff: dense additions and unchanged
knowledge favor Flat copying. The worst confirmed exact-size case was 60.9%
slower with 16; mixed dense and mixed unchanged workloads were about 36% and
38% slower in the final run. A caller distribution dominated by those patterns
would favor a larger threshold. The compiler remains at 256 pending acceptance
of this tradeoff; this investigation changes research files only.

## Scope

The compiler no longer partitions caller additions. Its remaining `_FLAT_LIMIT`
chooses between copying a small complete dictionary and sharing the original
dictionary with a separately copied additions dictionary. Compaction still
combines additions with the original dictionary when their sizes match.

`unpartitioned_state.py` follows the current compiler source, SHA-256
`c123ea89e616b58c065f97b99bee2f4e138417ee4957ba6eb7c654526676d538`, with benchmark
occupancy types, the benchmark abstract interface, and a process-local
configuration function. No compiler source is changed by this investigation.
The previous partitioned tuning results remain separate and unchanged.

## Plan specified before screening

Screen limits 1, 4, 8, 16, 32, 64, 128, and 256. The limit need not be a power
of two. Use exact initial dictionary sizes 1, 4, 8, 16, 32, 64, 128, and 256
across eight patterns: three callers, sixteen successive callers, fan-out,
branching callers, unchanged knowledge, overlapping knowledge with one addition,
dense additions with overlap, and frequent reads. Include all eleven original
state workloads and both earlier mixed workloads as wider checks. Exact-size
cases use 1,024 copies at scale 1; they count dictionary entries, not resources.

Dense callers add as many new entries as the original dictionary contains.
Unchanged and overlapping callers repeat the complete original dictionary with
conflicting occupancy, so the callee's precedence and the cost of checking
already-known entries are both exercised. Exact cases perform eight reads per
caller state, including original, added, and absent positions; read-heavy cases
repeat these reads 32 times. Every state is retained through measurement.

Use one screening repetition to locate a region, not declare a winner. Refine
with intermediate limits and at least three randomized repetitions. Confirm
using separate seeded mixtures of 24 small-state configurations per caller
pattern, jittered away from powers of two, and multiple seeds. Preserve individual
regressions rather than selecting solely by an equal-case geometric mean. Such
weighting is not a measured distribution of real programs. Treat a few percent
as insufficient evidence of a stable improvement.

Workers run sequentially in fresh processes pinned to CPU 2. Record CPU and
wall time for construction, reads, and traversal; peak, initial, and retained
RSS; complete configurations; hashes and exact source snapshots; and all
resource failures. Input generation is outside operation timings but included
in RSS. The default limits are 60 seconds and 2,048 MiB RSS per worker.
Do not interpret a killed baseline as a measured speedup.

Tests compare every retained state at every screened exact-size case and limit
against an independent flat oracle. They also verify complete query results,
unchanged-state reuse, occupancy precedence, and reproducible held-out inputs.

## Reproduce

```sh
uv run --frozen -m destruction_contract_benchmarks.threshold_run
bazelisk test --noshow_progress --ui_event_filters=-info //destruction_contract_benchmarks:threshold_workloads_test
```

Every run's manifest records its complete command line. The earlier result
analyzer accepts these records with `--baseline limit_256` and
`--details limit_8,limit_16,limit_256`.

## Screening observations

The [screening run](threshold_results/20260909T034404.951174Z/summary.md)
contains 616 successful measurements: eight limits across 77 workloads.
All variants agree on their per-workload checksums. Limits 8, 16, and 32 had
nearly identical equal-case CPU ratios, about 0.95 relative to 256, with peak
RSS ratios of 0.882, 0.888, and 0.900 respectively. Those aggregate differences
are not sufficient to choose between them from a single repetition.

The newly added cases expose opposing costs. Short histories of four entries
favor retaining Flat state, and frequent reads of small extended states can
cost more CPU. Dense additions and repeated already-known knowledge also favor
larger copy thresholds. For example, dense additions from 64 initial entries
were approximately 1.7 times as expensive with lower thresholds. Lower limits
substantially reduce memory and CPU for longer histories of sparse changes.
Thus the earlier one-new-entry microbenchmark alone would overstate the case
for sharing immediately.

Refine 8, 12, 16, 24, 32, 48, 64, 128, and 256 using all eight held-out
small-state mixtures and the two earlier general mixtures, three repetitions
each, with seeds 28413 and 63829. The compiler remains unchanged throughout.

## Held-out refinement

The [repeated mixture run](threshold_results/20260909T034608.825877Z/summary.md)
contains 540 successful measurements: nine limits, ten mixtures, two seeds,
three repetitions. The first eight mixtures each hold 24 exact-size
configurations with jittered sizes; the last two are the earlier general
mixtures. All successful variants have matching per-case checksums.

| Limit | Equal-case CPU ratio | Peak RSS ratio | Worst CPU ratio |
| --- | ---: | ---: | ---: |
| 8 | 0.848 | 0.691 | 1.417 |
| 12 | 0.846 | 0.693 | 1.416 |
| 16 | 0.849 | 0.697 | 1.414 |
| 24 | 0.853 | 0.707 | 1.412 |
| 32 | 0.873 | 0.722 | 1.402 |
| 48 | 0.883 | 0.748 | 1.347 |
| 64 | 0.900 | 0.783 | 1.328 |
| 128 | 0.919 | 0.834 | 1.273 |
| 256 | 1.000 | 1.000 | 1.000 |

The ratios are relative to 256 and use geometric means of per-case median
ratios. They are not end-to-end compiler speedups or a production-weighted
average. The few-tenths-of-a-percent gap between 8, 12, and 16 does not establish
an exact winner. Sixteen preserves Flat copying for the tiniest states while
remaining in that best-performing region. The power-of-two value is convenient,
not an algorithmic requirement.

Concrete medians for seed 28413, scale 1, compare the leading candidate with
the current threshold. CPU includes construction, reads, and traversal; peak
RSS includes the interpreter, input objects, and all retained states.

| Mixture | CPU ms, 256 | CPU ms, 16 | Peak MiB, 256 | Peak MiB, 16 |
| --- | ---: | ---: | ---: | ---: |
| Three callers | 14.33 | 9.09 | 43.44 | 31.50 |
| Sixteen successive callers | 96.74 | 46.31 | 107.38 | 42.22 |
| Fan-out | 38.38 | 19.15 | 64.49 | 33.86 |
| Branching callers | 77.30 | 39.41 | 96.86 | 37.21 |
| Unchanged knowledge | 9.58 | 13.56 | 30.27 | 30.37 |
| Overlapping knowledge | 14.19 | 16.61 | 43.55 | 31.66 |
| Dense additions | 33.69 | 45.40 | 63.85 | 59.95 |
| Frequent reads | 157.08 | 160.22 | 43.38 | 31.48 |
| Earlier mixed small | 67.82 | 59.33 | 61.27 | 41.51 |
| Earlier mixed medium | 80.49 | 79.66 | 144.22 | 139.75 |

The regressions are real tradeoffs, not hidden failures: lower thresholds
replace efficient C-level dictionary copies with Python-level membership
checks for already-known caller knowledge, and Extended lookups sometimes
consult two dictionaries. For unchanged knowledge, Flat also returns the
existing state after its temporary copy, so lower thresholds do not save
retained-state memory. Conversely, new sparse knowledge can share the original
dictionary across many retained states.

The confirmation compares 8, 16, 32, and 256 over all 77 screening workloads
plus eight new mixtures, at scale 2 and seed 74921, with three repetitions.
This seed's small-state mixtures were not used to select the leading candidate.

## Full confirmation

The [confirmation run](threshold_results/20260909T034807.793120Z/summary.md)
contains 1,020 measurements: 85 cases, four limits, three repetitions at scale
2 and seed 74921. All completed successfully with matching checksums.

| Limit | Equal-case CPU ratio | Peak RSS ratio | Worst CPU ratio |
| --- | ---: | ---: | ---: |
| 8 | 0.929 | 0.801 | 1.626 |
| 16 | 0.930 | 0.811 | 1.609 |
| 32 | 0.932 | 0.831 | 1.644 |
| 256 | 1.000 | 1.000 | 1.000 |

All three lower values have very similar aggregate CPU results. Eight uses
slightly less memory, but it also extends states that sixteen leaves flat.
For the frequent-read case starting with eight entries, median CPU was
219.26 ms at limit 8 versus 196.87 ms at limit 16. The latter's 196.29–209.52 ms
range is below the former's 216.87–219.27 ms range. There are corresponding
counterexamples at other sizes: frequent reads starting at sixteen entries
favor limit 32. The recommendation deliberately selects a compromise rather
than implying that a fixed threshold wins for every access pattern.

Actual medians for all ten mixture workloads in this final run:

| Mixture | CPU ms, 256 | CPU ms, 16 | Peak MiB, 256 | Peak MiB, 16 |
| --- | ---: | ---: | ---: | ---: |
| Three callers | 28.91 | 18.75 | 58.27 | 37.07 |
| Sixteen successive callers | 193.86 | 98.40 | 184.24 | 58.25 |
| Fan-out | 80.34 | 42.46 | 98.58 | 42.29 |
| Branching callers | 151.37 | 81.93 | 155.52 | 49.62 |
| Unchanged knowledge | 20.44 | 28.20 | 34.29 | 34.36 |
| Overlapping knowledge | 30.30 | 34.24 | 58.49 | 37.33 |
| Dense additions | 65.12 | 88.70 | 92.36 | 89.58 |
| Frequent reads | 309.67 | 324.64 | 58.21 | 37.13 |
| Earlier mixed small | 158.20 | 125.82 | 109.12 | 59.62 |
| Earlier mixed medium | 126.94 | 126.16 | 204.26 | 188.76 |

For an exact-size adverse case, dense additions from 64 initial entries cost
55.14 ms (54.71–56.73) at limit 16 versus 34.28 ms (33.67–34.77) at 256.
Peak RSS decreased from 82.00 to 67.05 MiB. Unchanged knowledge from 128
initial entries cost 28.58 ms versus 17.99 ms, with equal 36.04 MiB peak RSS.
These regressions are not timing noise and are retained in the recommendation.

## Interpretation and validation

The benchmark and production algorithm syntax trees match after normalizing
interface types, configuration names, and annotations. The measurements use
Python 3.14.6's free-threading build on an AMD Ryzen 9 9950X. Inputs and all
retained states contribute to peak RSS; CPU covers state construction and
reads, not input generation or a complete compiler invocation.

The exact-size cases use shared synthetic position names and occupancy objects;
their repeated state copies isolate storage policy rather than measuring all
objects in a real program. No production workload distribution is available.
Keep the per-case tables and ranges when revisiting this default, rather than
reusing the aggregate score as a universal performance claim.

The full research build and all 16 Bazel test targets passed. Package Ruff
checks and formatting passed, and repository-wide Basedpyright and other
pre-commit checks passed; the Bazel hook was run separately as the full test
command. An audit verified all 2,176 expected measurement files, successful
checksum agreement, and the hashes of every archived source snapshot.
