# Choosing Child State thresholds

## Recommendation

Keep `_FLAT_LIMIT = 256` and `_PARTITION_COUNT = 1024` as the provisional
general-purpose pair. The investigation does **not** prove these are optimal;
it finds no replacement that consistently improves CPU without substantial
memory or workload-specific regressions. The smaller-limit screening winner
failed held-out mixtures, and larger partition counts trade batched efficiency
for sparse-history growth. The existing pair also has a real large-batch memory
problem, so retaining it is not a claim that scaling is solved.

The next design experiment should separate the small-complete-state cutoff from
the additions-partitioning cutoff, then test a size-aware partition policy.
Those are research directions, not validated fixes. No compiler code was changed.
Across six rounds, 2,751 fresh-worker measurements cover coarse screening,
repeated refinement, held-out mixtures, and larger retained histories. Raw
results, failures, manifests, and per-case summaries are preserved below.

## Question and scope

Choose evidence-backed values for Define's `_FLAT_LIMIT` and `_PARTITION_COUNT`,
starting from 256 and 1,024. One limit controls both direct dictionary copying
for small complete snapshots and copying the additions dictionary before
partitioning. Those two uses need not have the same theoretical crossover.

This is a parameter experiment, not a change to the compiler and not a proof
that one parameter pair is optimal for every possible input distribution.
Preserve CPU efficiency across common small inputs while avoiding excessive
retained memory for large caller graphs. Report CPU/memory tradeoffs instead of
collapsing them into an unexplained composite score.

## Algorithm under test

`tuning_state.py` follows the compiler's `child_state.py` as read on September 8,
2026. The source file's SHA-256 was
`25ced0a5d75620f8e7b06337c7dba64a8edcca6315f63d795f84bc4dfa2e8594`.
Only occupancy types, the abstract benchmark interface, and process-local
configuration differ. Every worker configures the parameters before creating
any snapshots. There is no per-object parameter field or per-call tuning
dispatch in the measured algorithm.

Unlike the old `compact_base` prototype, the compiler algorithm returns to a
flat dictionary after partition compaction, and updates its additions directly
without constructing a separate filtered caller dictionary first. Consequently,
the old prototype is a control, not a substitute for testing the current
algorithm. The old results in `README.md` are not rerun or reinterpreted here.

## Method, specified before screening

- Screen flat limits 16, 64, 256, 1,024, and 4,096 against partition counts 4,
  16, 64, 256, 1,024, and 4,096. Include the current pair as a reference and the
  original flat-copy and `compact_base` algorithms as controls.
- Use all 11 original state workloads, four medium chain sizes, four medium
  fan-out sizes, and sparse, batched, overlapping, and branching additions.
  Medium case names count initial resources, not dictionary entries; manifests
  and results record both configuration and actual state cardinality. Their
  sizes stay fixed while scale increases their number of copies.
- Start at scale 4 with one repetition and seed 74921 to identify promising
  regions, not to declare a winner. Refine between screened parameter values
  and confirm with repeated randomized measurements, a second input/hash seed,
  and larger scales. Verify the new cases against an independent flat oracle.
- Workers are sequential fresh processes pinned to one CPU. Input generation
  is outside timed state operations but remains included in RSS. CPU, wall
  time, input RSS, retained RSS, peak RSS, per-case checksum, and resource-limit
  failures are recorded. Use separate tracemalloc runs for allocation evidence,
  never their timings for ranking.
- Apply the same default 60-second timeout and 1,536 MiB polled RSS limit as the
  earlier experiment. Do not interpret a killed baseline as a measured speedup.
- Randomize the complete job order with an explicit order seed. Record source
  hashes, all configuration values, CPU information, memory information,
  interpreter version, and command-line arguments in each manifest. Do not
  overwrite historical measurements.
- Compare per-case medians and ranges. Summaries may use equal-case geometric
  mean ratios, but must retain the individual cases and worst regressions:
  equal-case weighting is an experimental convenience, not a measured
  distribution of real Define programs. Prefer a stable CPU/memory compromise
  over an isolated best timing. Repeated differences of a few percent may be
  noise and are not sufficient by themselves to select a constant.

## Reproduce

From the research repository on Linux:

```sh
uv run --frozen -m destruction_contract_benchmarks.tuning_run --controls current_flat,compact_base
bazelisk test --noshow_progress --ui_event_filters=-info //destruction_contract_benchmarks:all
uv run --frozen ruff check destruction_contract_benchmarks
uv run --frozen basedpyright destruction_contract_benchmarks
```

The first command is the screening matrix, not a quick smoke test. Manifests in
`tuning_results/` contain exact reproduction arguments for subsequent runs.

## Why a universal fixed partition count cannot be optimal

Let `P` be the partition count, `K` the current additions count, and `b` the
number of newly learned positions in a caller batch. Under approximately uniform
hashing, a batch touches an expected `P * (1 - (1 - 1/P)^b)` partitions. Each
touched dictionary holds approximately `K/P` earlier entries. Thus copying
earlier entries costs approximately `K * (1 - (1 - 1/P)^b)`, in addition to
copying the `P`-element directory. For `b` much smaller than `P`, this becomes
approximately `b*K/P + P`, with different real costs per entry and per pointer.

This is a cost model, not a timing prediction: dictionary capacities, hash costs,
allocation size classes, reads, compaction, and retained versions all matter.
It nonetheless shows why a fixed optimum independent of `K` and `b` is
impossible. Larger partition counts reduce old-entry copying but increase
directory copying and storage. The right compromise must be measured over a
stated size and batch range. A fixed count cannot guarantee bounded memory for
arbitrarily long retained histories; tuning constants does not change that
algorithmic limitation.

The flat limit has a different tradeoff. Raising it avoids allocating partition
directories for short-lived additions, but retains more complete dictionary
copies for medium-sized state and copies larger additions dictionaries before
sharing them. Lowering it too far penalizes small objects and shallow fan-out.

`tuning_storage.py` independently counts unique retained dictionaries, their
entry counts and shallow sizes, and partition-directory entries. It runs
outside the timed experiments and excludes common keys and occupancy objects;
its byte counts are not substitutes for RSS. It helps distinguish structural
memory growth from allocator noise.

## Coarse screening

Run: [`20260909T023324.482726Z`](tuning_results/20260909T023324.482726Z/summary.md).
This run contains 736 measurements: 30 production parameter pairs and two
controls across 23 cases, scale 4, seed 74921, one repetition. Every production
pair completed every case with the same per-case checksum. The flat-copy
control exceeded the memory limit in two cases; its incomplete aggregate must
not be compared with the complete production aggregates.

The fastest complete equal-case CPU aggregate was 64/256, at 0.934 times the
256/1024 reference. That is not sufficient to select it: batched additions used
244 MiB peak versus 118 MiB with 64/1024. Conversely, increasing to 64/4096
reduced batched-addition peak to 98 MiB, but increased sparse-update peak from
88 to 191 MiB and CPU from 58 to 106 ms. All of these are screening observations
requiring repeated confirmation, not final claims.

Flat limits 1,024 and 4,096 were poor on medium-sized state. Limit 16 combined
with large partition directories was poor on shallow fan-out. The next run
therefore refines limits 32, 64, 128, and 256 against counts 128, 256, 512, and
1,024 with three repetitions rather than assuming that the coarse winner is
optimal.

## Repeated refinement and held-out inputs

The [refinement run](tuning_results/20260909T023733.360178Z/summary.md) contains
1,104 measurements: 16 pairs, all 23 cases, three repetitions. All completed.
64/1024 had a CPU geometric mean of 0.977 relative to 256/1024, with essentially
unchanged worst-case peak RSS. Smaller partition counts improved the aggregate
but increased batched-addition memory; 64/128 used 3.097 times the reference
peak in that case. This made 64/1024 a candidate, not a recommendation.

Before confirming it, two independently generated mixture workloads were added.
Each retains 48 configurations selected by a seeded generator, varying state
size, caller count, batch size, overlap, and chain/fan-out/branching structure.
The generator jitters sizes around a logarithmic grid instead of selecting only
threshold boundaries. All configurations are recorded in the manifests. Tests
compare every retained state against an independent flat-dictionary oracle.
These are held-out synthetic workloads, not a production-program sample.

The [held-out run](tuning_results/20260909T024708.662118Z/summary.md) contains
600 measurements: eight pairs, all 25 cases, seed 28413, three repetitions.
All completed with matching checksums. The promising smaller flat limit has
substantial counterexamples:

| Case, scale 4 | 256/1024 CPU ms | 64/1024 CPU ms | 256/1024 peak MiB | 64/1024 peak MiB |
| --- | ---: | ---: | ---: | ---: |
| Branching callers | 101.69 | 64.95 | 88.27 | 65.79 |
| Medium chain, 32 initial resources | 25.66 | 20.98 | 43.10 | 29.77 |
| Mixed small | 288.52 | 354.12 | 157.49 | 152.92 |
| Mixed medium | 771.26 | 1046.64 | 414.00 | 627.01 |

Values are medians of three fresh workers. Mixed-medium CPU ranges were
763.94–772.13 ms for the reference and 1043.79–1055.50 ms for 64/1024:
the 35.7% CPU regression is not an isolated timing outlier. Peak RSS increased
51.5%. The 0.993 equal-case CPU aggregate conceals these regressions.

[Other held-out candidates](tuning_results/20260909T024708.662118Z/alternatives.md)
do not resolve the tradeoff. 64/512 had the best equal-case CPU aggregate,
0.976, but increased mixed-medium CPU 16.7% and batched-addition peak 35.7%.
64/4096 increased mixed-medium CPU to 2,320.62 ms and peak RSS to 1,522.23 MiB,
3.01 and 3.68 times the reference respectively.

## Large retained histories

The [larger screening run](tuning_results/20260909T024239.242151Z/summary.md)
contains 98 measurements at scales 16 and 32. Only 64/4096 completed all
14 case/scale groups under the 1,536 MiB RSS limit. The reference exceeded it
for scale-32 batched additions and dense callers. This does not establish
64/4096 as the best choice: the memory ceiling censors the reference, while
larger directories penalize sparse changes. A subsequent run raises the RSS
allowance to 4,096 MiB to measure the actual tradeoff.

The independent storage census explains the opposing effects. At scale 4,
batched additions with 64 partitions retained 7,271,333 dictionary entries
(291,637,112 shallow dictionary bytes); with 1,024 partitions they retained
1,167,886 entries (48,803,336 bytes). With sparse additions, increasing from
1,024 to 4,096 partitions reduced dictionary bytes only from 3,815,128 to
3,471,464, while directory bytes rose from 33,495,600 to 133,397,040.
See [batched storage](tuning_results/batch_storage.json) and
[sparse storage](tuning_results/sparse_storage.json). This is genuine retained
structure, not just an RSS measurement artifact.

The [large confirmation](tuning_results/20260909T025141.911671Z/summary.md)
contains 105 measurements: five pairs, seven cases at scale 32, three
repetitions, seed 74921, with a 4,096 MiB RSS allowance. Every measurement
completed. The previously censored reference is expensive, but the alternatives
have substantial costs elsewhere:

| Pair | Batched CPU ms | Batched peak MiB | Sparse CPU ms | Sparse peak MiB |
| --- | ---: | ---: | ---: | ---: |
| 256/1024 | 1985.95 | 3861.21 | 694.54 | 611.52 |
| 64/1024 | 2009.22 | 3860.83 | 700.59 | 611.52 |
| 64/4096 | 1024.41 | 1322.50 | 1062.45 | 1376.38 |
| 64/8192 | 939.47 | 989.91 | 1614.30 | 2391.78 |

Increasing to 4,096 partitions nearly halves batched CPU and cuts peak RSS by
65.8%, but increases sparse CPU 53.0% and peak RSS 125.1%. Increasing again to
8,192 gives diminishing batched gains and raises sparse peak to 3.91 times the
reference. Lowering only the flat limit does not solve large batched memory.

## Larger flat limits on both mixture seeds

The [final mixture check](tuning_results/20260909T025718.296402Z/summary.md)
contains 108 measurements: nine pairs, two mixtures, two seeds, three
repetitions. All completed with matching checksums. Raising the flat limit
does not remove the tradeoff. At 1024/1024, mixed-medium CPU improved 20–28%,
but its peak RSS increased 51–70%; mixed-small CPU worsened 19–20% and peak
RSS increased about 47%. At 512/1024, mixed-small CPU worsened 15–17% and
peak RSS increased 38–39%. Keeping limit 256 while increasing partitions to
4,096 worsened mixed-medium CPU 59–64% and peak RSS 60–65%, with essentially
unchanged mixed-small results. Thus the large-directory counterexample is not
merely an artifact of combining it with limit 64.

## Validation and scope

The full research build and all 14 Bazel tests passed, including six benchmark
test targets. Benchmark Ruff checks, formatting, and Basedpyright passed.
Repository-wide hooks passed except for four Basedpyright warnings in unrelated
in-progress `transitive_destruction/contracts/composition_integration_test.py`;
that file was not changed by this investigation. The Bazel hook was executed
separately as the full test command. An audit verified all 2,751 expected result
files and checksum agreement among successful variants in each case/scale/seed
group. The 15 recorded resource failures remain present: two flat-copy controls
in coarse screening and 13 measurements in the lower-memory large screening.

These are standalone state-operation benchmarks on an AMD Ryzen 9 9950X with
Python 3.14.6's free-threading build, pinned to CPU 2. They are not end-to-end
compiler speedups, do not establish the frequency of these workloads in real
programs, and do not establish a universal optimum across hardware or Python
versions. Three repetitions reveal large stable differences but do not justify
fine-grained claims about a few percent. Input generation is excluded from
operation CPU time; peak RSS includes inputs and retained states. Incremental
RSS can occasionally be negative because memory is reclaimed between readings;
the comparisons above use peak RSS, not that noisy difference.

The timed Child State implementation remained unchanged across all rounds.
The runner gained explicit pair selection and then mixture support; manifests
record these source changes. Earlier rounds do not contain the later mixture
cases. Preserve the separate run directories instead of treating them as one
uniform dataset or silently dropping resource failures.
