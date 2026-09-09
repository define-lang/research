# Destruction Contract storage experiments

These are standalone algorithm prototypes, not compiler benchmarks. They compare
current-style storage with proposed shared Child State, per-particle Destruction
Contracts, and shared propagation history. No production compiler representation
has been changed by this experiment.

## Archive provenance

Moved from `tools/destruction_contract_benchmarks/` in the Define working tree
on September 8, 2026. The baseline was modeled against Define commit
`bce3e24f7` ("Verify Destructors separately for each destroyed particle").
The measurements below predate this relocation; they have not been rerun or
relabeled as research-repository measurements.

All original raw JSON results and manifests are preserved byte-for-byte under
`results/`. Tests and workloads evolved between measurements, and the earlier runner
recorded hashes but did not save per-run source snapshots. Some screening
manifests also predate source hashing. Those provenance gaps cannot be repaired
from a hash alone.

The runnable files here change package imports, the child-process module name,
the default results path, and Bazel integration for this repository. These
relocation changes do not alter the benchmark algorithms. No compiler checkout
or generated parser files are required to run them.

The post-relocation smoke run `results/20260909T021334.797588Z/` checks small
objects, deep callers, contract chains, and history chains at scale 1 with one
repetition. All eight measurements succeeded with matching per-case checksums.
It validates the relocated runner, not the historical performance conclusions;
its Python version and source hash are recorded in its own manifest.

## Decision

Use **per-particle contracts sharing hash-indexed Child State**, with shared
linked propagation history. Keep small state in ordinary dictionaries; reuse
unchanged snapshots. For larger state, retain a directly queried dictionary of
known callee knowledge and a separate dictionary of additions. Once additions
become large, use copied-on-write hash partitions. Compact additions into the
common dictionary when they double its size. The `compact_base` prototype
implements this policy, with thresholds of 256 entries and 1,024 partitions.

This is the best tested general-purpose starting point, not a universal optimum
or a finished compiler design. It preserves the small-object CPU baseline and
substantially improves the large sparse cases. The exact thresholds are
provisional. The 64-partition control beats it on branching calls and dense
updates; ordinary flat copying beats both on dense updates. Do not add a
production heuristic for those cases without measuring its effect on retained
versions and other workloads.

Do **not** choose a per-name persistent position tree as the general lookup
representation. Its child views are cheap, but its long-name lookup and update
costs are much worse. Nor should every small object pay for a large partition
directory. The largest gains come from removing overlapping state copies and
repeated history copies, not from replacing every dictionary with a tree.

## Reproduce

From the research repository directory (Linux, Python 3.14 or newer):

```sh
uv run --frozen -m destruction_contract_benchmarks.run --scale 4 --repetitions 3 --variants current_flat,shared_flat,base_partitions_64,compact_base,current_contracts,linked_history,current_history,shared_tuple_history
```

The default includes all cases and candidates; use `--cases` and `--variants` to
select subsets. Invalid case names fail. For mixed experiment families, variants
that do not apply to a family are skipped. Every selected family must have at
least one applicable variant. `--cpu` must identify an available Linux CPU.

Results are timestamped JSON files in the archived `results/` directory. Each run
records its arguments, Python version, and a hash of the Python benchmark
sources. Each measurement records construction, lookup, and traversal CPU and
wall time; input construction CPU; input, retained, and peak RSS; and dimensions
and result checksums. Use `--allocation` for a separate Python-allocation
measurement. Never compare its timings with untraced timings.

```sh
bazelisk test --noshow_progress --ui_event_filters=-info //destruction_contract_benchmarks:all
uv run --frozen ruff check destruction_contract_benchmarks
uv run --frozen ruff format --check destruction_contract_benchmarks
uv run --frozen basedpyright destruction_contract_benchmarks
```

## Method and limits

Measured September 8, 2026, on an AMD Ryzen 9 9950X, 60 GiB RAM, Linux, CPython
3.14.7 free-threading build. Workers run sequentially, pinned to CPU 2, with
fixed hash/input seed 74921 and randomized candidate order. Timings exclude
interpreter startup and common input generation. Common input remains resident
and is included in total RSS. The default worker limits are 60 seconds and 1,536
MiB RSS. RSS is polled every 50 ms, so a killed worker can overshoot the limit.
The worker also has an 8 GiB virtual-address limit, allowing for the
free-threaded allocator's large reservations.

RSS comes from Linux `/proc`, including allocator overhead; it is not an
estimate from object sizes. Incremental retained RSS subtracts input RSS. Peak
RSS includes input and temporaries, and can be much larger. Allocator page reuse
can make a small incremental RSS misleading; consult the separate allocation
measurements. No speedup is assigned to a baseline that exceeded a resource
limit.

All successful variants must produce the same result checksum within a run.
Tests additionally compare complete stored dictionaries with a flat oracle,
retained earlier versions, independent callers, occupied/empty/error/absent
state, callee precedence, compaction, parent lookup, contract requirements, and
complete diagnostic history step order. Checksums are a benchmark guard, not a
substitute for compiler semantic tests.

The three experiment families isolate different costs:

- **State propagation:** retain all versions across small independent objects,
  wide registries, call chains, unchanged callers, library fan-out, branching
  callers, dense additions, frequent requirements, deep names, and full
  traversal. Exact lookup includes absent state; every 32nd query also searches
  occupied parent names. A separate case queries earlier caller knowledge rather
  than concentrating reads on the original callee dictionary.
- **Contract construction:** reproduce transitive child enumeration,
  relative-name tuple construction, occupied-record allocation, and current
  unslotted contract records. Compare with slotted per-particle records sharing
  one snapshot. Include chains, balanced children, wide children,
  later-discovered children, and many small objects. This includes creating the
  candidate's index.
- **History:** compare one copied tuple per contract, one shared tuple per call,
  and one shared linked history per call. Retain earlier versions and read some
  histories; the diagnostic-heavy case reads a history at every action.

These models use string tuples, lightweight occupancy records and quality
tuples, not complete ASTs, Contributed Operations, Moves, origin translation,
all possible verification dependencies, or actual compiler diagnostics. They do
not jointly measure per-particle record propagation through a large call graph.
Contract requirements are fixed synthetic distributions, not sampled production
programs. The state suite charges one shared snapshot per destruction/version,
not every possible destruction in an entire program. Common tracker input is
retained by both projection variants. Do not multiply isolated speedups
together, interpret these sizes as complete program memory, or claim an
end-to-end compiler speedup.

## Repeated measurements: scale 4

Three untraced measurements per combination. CPU values are medians, in
milliseconds, including construction and all timed reads/traversals. Memory is
total peak RSS in MiB from the median-CPU sample, not just incremental storage.
The candidate is `compact_base`, or `linked_history` for history cases.

| Workload                   | Size                                        | Current CPU | Candidate CPU | Current peak MiB | Candidate peak MiB |
| -------------------------- | ------------------------------------------- | ----------: | ------------: | ---------------: | -----------------: |
| Small state                | 8,000 independent objects, 4 versions each  |       79.22 |         79.06 |            69.54 |              69.54 |
| Wide registry              | 32,768 initial entries, 8 callers           |       10.47 |          6.44 |            46.59 |              36.82 |
| Deep callers               | 16,512 initial entries, 1,024 callers       |      444.77 |         34.48 |           871.43 |              51.37 |
| Unchanged callers          | 16,512 initial entries, 1,024 callers       |      362.98 |         18.65 |           619.93 |              38.07 |
| Library fan-out            | 512 callers of one callee                   |      190.06 |         20.44 |           329.73 |              39.06 |
| Branching callers          | 1,020 callers                               |      231.94 |        101.38 |           339.73 |              88.32 |
| Dense callers              | 32 callers, 4,096 new resource names each   |      146.39 |        145.12 |           365.46 |             189.20 |
| Read-heavy                 | 2,097,152 exact queries plus parent queries |      577.75 |        396.74 |           128.49 |              48.94 |
| Deep names                 | 256 name components                         |        7.39 |          5.22 |            57.84 |              53.66 |
| Full traversal             | 32 versions enumerated                      |      101.54 |         89.44 |            77.73 |              38.55 |
| Overlapping contracts      | 512 particles in a chain                    |      838.80 |         11.27 |           858.22 |              32.13 |
| Balanced contracts         | 4 groups of 1,365 particles                 |       61.32 |         19.66 |            47.85 |              30.16 |
| Wide contracts             | 8,193 particles                             |       45.96 |         28.84 |            55.76 |              47.33 |
| Later-discovered children  | 8,193 particles, one original contract      |       27.49 |         28.90 |            53.35 |              47.21 |
| Small contracts            | 20,000 groups of 2 particles                |      208.34 |        149.49 |            72.41 |              42.71 |
| History chain              | 1,024 callers, 64 contracts each            |      121.45 |          0.43 |           309.31 |              26.55 |
| History fan-out            | 2,048 callers, 64 contracts each            |      376.37 |          0.88 |           951.12 |              27.24 |
| Diagnostic-heavy histories | 1,024 callers, one contract each            |       10.27 |         10.88 |            30.09 |              26.10 |

For perspective, incremental retained storage in the deep-call case is 832.92
versus 12.99 MiB. The overlapping-contract case is 826.30 versus 0.14 MiB; that
small candidate increment does not include the approximately 32 MiB common
input.

Representative CPU ranges across all three samples: deep calls 443.43–445.23 ms
versus 33.50–36.42 ms; overlapping contracts 833.82–851.88 versus 10.97–11.33
ms; small state 79.05–80.47 versus 79.05–82.80 ms. The largest
current-wide-contract sample was 54.73 ms versus its 45.96 ms median. These are
observed ranges, not statistical confidence intervals. Wall time for the median
deep-call samples was 445.92 versus 34.56 ms, and for overlapping contracts
840.89 versus 11.30 ms.

### Tradeoffs and rejected candidates

- Shared flat dictionaries alone use 832.80 MiB additional retained RSS for deep
  calls, despite reducing CPU to 210.97 ms. Sharing between particles is not
  enough if every caller still copies all known state.
- The fixed 64-partition base is better on branching callers: 60.63 ms and 56.18
  MiB total peak, versus 101.38 ms and 88.32 MiB for `compact_base`. But
  imposing it on small objects takes 174.97 ms versus 79.22 ms currently. The
  adaptive small dictionary path matters.
- Dense additions favor native flat copying: `shared_flat` takes 105.09 ms
  versus 145.12 ms for `compact_base`, but peaks at 372.47 versus 189.20 MiB.
  The candidate matches the current 146.39 ms baseline; it does not match the
  fastest dense-only control. This remains an optimization opportunity, not a
  hidden victory.
- Later-discovered children cost about 5% more CPU with per-particle records in
  this model. They save memory, but record creation is real work.
- Diagnostic-heavy linked histories take about 6% more CPU by median, with a
  10.86–11.90 ms range. Shared tuples take 10.38 ms and 30.07 MiB. Linked
  history is compelling for ordinary propagation, not faster for every history
  read.
- Initial one-repetition screening found the position tree took about 146 ms for
  deep names versus 8 ms currently, and 260 ms for small state versus 80 ms. A
  1,024-partition snapshot for every small contract group took 2,234 ms and
  nearly 1.5 GiB additional RSS. These are screening observations, not the
  repeated measurements used for the main decision.

## Larger workloads

At scale 8, three repetitions of current-style deep calls, branching calls,
overlapping contracts, earlier-caller-knowledge reads, and history fan-out all
exceeded the 1,536 MiB RSS limit. The proposed variants completed every case.
Library fan-out still completed with the current model: 741.68 ms and about
1,339 MiB peak, versus 45.15 ms and about 53 MiB with shared state.

At scale 32, the proposed variants completed all selected cases in three
repetitions. There is no numerical baseline speedup at this size: the smaller
current-style runs already exceeded the limit.

| Workload              | Size                                   | Median CPU ms | CPU range ms  | Peak MiB |
| --------------------- | -------------------------------------- | ------------: | ------------- | -------: |
| Deep callers          | 132,096 initial entries, 8,192 callers |        484.69 | 469.16–498.69 |   321.77 |
| Library fan-out       | 4,096 independent callers              |        274.29 | 267.12–300.57 |   141.95 |
| Branching callers     | 8,160 callers                          |        808.65 | 807.39–931.38 |   376.05 |
| Overlapping contracts | 4,096 particles in a chain             |        653.53 | 644.39–654.39 |   383.66 |
| History fan-out       | 16,384 callers, 64 contracts each      |         14.92 | 14.88–14.96   |    38.65 |

The long particle chain still consumes substantial common input memory: full
position-name tuples themselves grow quadratically with chain depth. Sharing
contract state removes overlapping snapshots; it does not make long names free.
Similarly, fixed-count dictionary partitions do not give asymptotically constant
update cost: a changed partition grows with the state assigned to it. Geometric
compaction and partition sharing improve these measured sizes but do not prove
acceptable memory at every possible program size. Very large retained histories
of dense additions remain a separate worst case.

## Second seed and allocation checks

Three repetitions with seed 28413 reproduced the main tradeoffs at scale 4.
Current versus candidate median CPU: deep calls 449.54 versus 36.20 ms,
read-heavy 587.85 versus 396.82 ms, dense callers 148.58 versus 151.27 ms, and
small state 78.78 versus 81.47 ms. Thus small state and dense updates can have a
few percent overhead; the original seed's near-equality is not a promise of zero
overhead.

The earlier-caller-knowledge case starts with only 258 known entries and adds
knowledge through 1,024 callers. Most successful reads select knowledge supplied
by a previous caller, not the initial dictionary. Current storage took 495.42 ms
and 1,047.22 MiB peak; shared flat copying took 312.93 ms and 1,048.45 MiB;
`compact_base` took 231.76 ms and 103.17 MiB. The benefit is not limited to
reads of the original dictionary.

Separate allocation tracing at scale 2 confirms the storage differences. These
are retained Python allocations created after common input preparation, in MiB;
they exclude common input and allocator overhead. One sample per combination; no
traced timings were used for performance claims.

| Workload              | Current retained | Candidate retained | Current Python peak | Candidate Python peak |
| --------------------- | ---------------: | -----------------: | ------------------: | --------------------: |
| Small state           |            18.96 |              18.96 |               19.10 |                 19.10 |
| Deep callers          |           195.54 |               5.30 |              195.68 |                  5.44 |
| Overlapping contracts |           100.24 |              0.073 |              102.25 |                 0.208 |
| History fan-out       |           195.99 |              0.660 |              196.12 |                 0.794 |

## Raw run inventory

All paths below are relative to `results/`. Raw files are local and
intentionally ignored by Git; this report preserves the primary measurements.

- `20260908T224550.584905Z`: initial scale-4 state screening, nine candidates.
- `20260908T225124.057966Z`: initial contract and history screening.
- `20260908T225400.475450Z`: shared-base and small-state threshold screening.
- `20260908T225643.207973Z`: compact-addition screening.
- `20260908T225835.127227Z`: complete scale-4 table above, three repetitions.
  Source hash:
  `0e393db61f4a7ab2f2f24a33d81273581952c418879a54623d0e18baceceb3ef`. The
  earlier-caller-knowledge workload and additional tests were added afterward;
  this table's algorithms and query distributions were not changed.
- `20260908T230011.022662Z`: scale-8 limits and earlier-caller-knowledge tests,
  three repetitions.
- `20260908T230050.087425Z`: scale-32 proposed variants, three repetitions.
- `20260908T230235.240857Z`: second seed and earlier-caller-knowledge
  comparisons, scale 4, three repetitions.
- `20260908T230319.515586Z`: separate scale-2 allocation measurements.
