# Collecting parent Creates: insert then remove, or skip?

Keep the existing insert-then-remove implementation. Avoiding the insertion of
covered parent Creates did not produce a consistent improvement across these
workloads. This is a comparison of two implementations, not a proof that either
is universally fastest.

## Implementations compared

The baseline initializes the candidate set with `operation.creators`, collects
the other candidates and the parent Creates they cover, then calls
`candidates.difference_update(covered_creators)`.

The alternative starts with an empty candidate set. After collecting the other
candidates and removing covered Creates, it loops over `operation.creators`,
adding only those absent from `covered_creators`.

The alternative still needs the removal: another collection rule can also add
the same parent Create. Both implementations remove covered Creates regardless
of why they were collected. Both use Python sets, not lists.

The additional Python loop and membership checks can offset saved insertions and
removals; the baseline uses bulk set operations. This is a possible explanation
for the close timings, not an isolated measurement of those costs.

## Measurements

Measurements were taken during the interactive investigation on 2026-09-07,
using CPython 3.14.7. The host was not reserved or pinned for this experiment.
CPU model, measurement-time commit, and competing host activity were not
captured. Do not infer them from the metadata of earlier experiments.

The [raw artifact](collection_results.json) preserves all 150 measured builds:
seven screening cases with seven runs per variant, four larger cases with five
runs per variant, and a six-run-per-variant confirmation of one larger case.
These are eleven distinct workload configurations and one repeated
configuration. Each case also ran an excluded warm-up pair. No slow measured
runs were discarded.

Generation, valid-operation selection, input reordering, explicit garbage
collection, and validation were outside the timer. Timed construction includes
Calculator initialization, all three construction phases, graph and cache
updates, and dispatch of simultaneous groups. Garbage collection remained
enabled during construction. Variant order alternated between repetitions.

All compared graphs had identical complete dependency sets for every operation.
The first eleven cases also passed the independent randomized execution check
with seed 101; the confirmation compared graphs without repeating that check.
These checks use resolved operations from the existing workload generators; this
experiment did not additionally run the compiler on generated source.

Median wall times in seconds; negative change means skipping was faster:

| Phase        | Workload          | Depth | Operations | Insert/remove |    Skip | Change |
| ------------ | ----------------- | ----: | ---------: | ------------: | ------: | -----: |
| Screen       | Balanced          |     4 |     50,874 |       0.08059 | 0.08004 | -0.68% |
| Screen       | Growth            |     4 |     73,598 |       0.45319 | 0.45583 | +0.58% |
| Screen       | Growth            |     6 |     73,310 |       0.38594 | 0.38358 | -0.61% |
| Screen       | Movement          |     6 |     34,536 |       0.33567 | 0.33508 | -0.18% |
| Screen       | Destruction       |     6 |     57,478 |       0.06814 | 0.06784 | -0.45% |
| Screen       | Implied positions |     — |     60,200 |       0.06302 | 0.06279 | -0.36% |
| Screen       | Shared parent     |     — |     60,403 |       0.08874 | 0.08710 | -1.85% |
| Large        | Reordered growth  |     6 |    252,078 |       3.17352 | 3.19384 | +0.64% |
| Large        | Growth            |     6 |    251,747 |       2.77866 | 2.57772 | -7.23% |
| Large        | Shared parent     |     — |    600,403 |       0.88638 | 0.88275 | -0.41% |
| Large        | Implied positions |     — |    600,200 |       0.63116 | 0.62344 | -1.22% |
| Confirmation | Growth            |     6 |    251,747 |       2.60966 | 2.63216 | +0.86% |

The apparent 7.23% advantage did not reproduce. Its baseline runs ranged from
2.548 to 4.443 seconds. The repeat measured CPU time as well: median baseline
2.60165 seconds versus alternative 2.62419 seconds. CPU and wall times were
close in that repeat, so these data do not establish CPU scheduling contention
as the cause of the earlier variation. No statistically established winner or
confidence interval is claimed.

## Reproduction and provenance

The JSON contains every measured repetition, seeds, dimensions, cache settings,
the compared algorithm sources, and supporting source snapshots. It also
contains the algorithm after the subsequent simplification described below. The
measured `_collect` source hash was emitted by the original experiment and is
recorded separately from the checkout HEAD observed when archiving. Supporting
sources were captured when archiving, not hashed during the runs; no intervening
changes to those sources are known.

An embedded replay script reconstructs the experiment from those records. It
loads the two algorithm snapshots in memory and refuses to run against changed
supporting source files. It does not edit the live algorithm. This is a replay
script assembled during archival, not a claim to preserve the original stdin
commands byte for byte. It additionally reports CPU time for every phase.

From this checkout, with the local development environment already generated:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync --offline python -c 'import json; exec(compile(json.load(open("operation_graph_optimization/collection_results.json"))["replay_source"], "<collection-replay>", "exec"))' --smoke
```

Omit `--smoke` to repeat all configurations at their recorded sizes. Use
`--phase screen`, `--phase large`, or `--phase confirmation` to select a phase.
Smoke runs verify replay and graph equality on small inputs; their timings are
not performance evidence. If supporting sources have changed, use the archived
copies in a separate checkout, not by overwriting active development files.

## Subsequent simultaneous-Vacate simplification

After these measurements, `Calculator.simultaneous()` was changed from two
passes to calling `add()` for each Vacate. In valid simultaneous destruction,
each Vacate empties a distinct position. Additional transitive child Vacates
have no Position References, so recording one does not change the position
information collected by another. This is not permission to interleave arbitrary
other operations within a group or to give Vacates different recency.

The change removes deferred recording and reconstruction of dependency sets. It
does not change the selected parent-Create collection strategy. No before and
after performance measurement of this simplification was made; none of the times
above, or in the earlier reports, measures that simplified implementation.

After the change, all four of these targets passed, including integration cases
that reverse the order of Vacates:

```sh
bazelisk test --noshow_progress --ui_event_filters=-info //operation_graph_optimization:algorithm_integration_test //operation_graph_optimization:state_workloads_integration_test //operation_graph_optimization:pyright_test //operation_graph_optimization:format_test
```

The independent reference implementation was not changed to mirror the
simplification. The artifact retains the pre-change algorithm as well as the
post-change snapshot, so the measurements can be reproduced without undoing the
current implementation.

## Preservation boundary

Keep this report, its raw artifact, and the earlier experiment reports and raw
artifacts together when migrating the investigation. Existing restoration
patches describe their historical source versions; they should not be assumed to
apply to the subsequently simplified algorithm. Preserve the patches rather than
silently rewriting their historical meaning.

Generated caches such as `__pycache__` are not research artifacts. The source
snapshots and replay instructions preserve this comparison independently of
those caches. Creating or publishing a research repository is a separate step;
this record does not assert that an external archive already exists.

Archival validation passed all twelve replay smoke cases, verified the original
measured `_collect` hash, and checked the 150-build count and supporting source
snapshots. The artifact records SHA-256 hashes for both compared algorithms, the
post-experiment algorithm, and the supporting files.
