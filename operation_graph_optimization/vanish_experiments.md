# Vanish collection experiments

## Result and scope

The recommended implementation is [vanish_algorithm.py](vanish_algorithm.py).
It keeps the last direct Move per particle, cheaply prunes quality-use candidates
when a new candidate directly depends on them, and applies the existing
Comparison to the remaining candidates plus the particle's Vacate and last Move.
It also omits quality uses already ordered before Vacate by an ordinary
intermediate-position requirement. Retained destructor references are excluded
from that shortcut. In the harness, `specialized` isolates the last-Move
specialization; `vacancy_covered` enables both and is the recommended mode.
The [rule derivation](vanish_rules.md) explains the exact correspondence.

No compiler or spec files were changed. No dependency requirement is weakened:
the last Move represents the preceding chain of direct Moves of the same
particle. This is a possible simplification of Vanish Collection, not a change
to permitted concurrency. It introduces no new threshold or cache policy.

The occupancy shortcut likewise preserves the graph: an operation requiring P
in an ordinary intermediate position precedes the Move or Vacate that empties
that position, and any later Moves of P precede its final ordinary Vacate.
Thus P's Vacate already covers this use. The input identifies ordinary
intermediate occupants, not guessed reachability; classification and input
resolution are included in generation, and candidate filtering is timed.

## Initial alternatives

The 72-run [preliminary matrix](vanish_preliminary_results.json) compared
position construction alone, deferred candidate collection, direct-dependency
pruning, and incremental exact antichains. Each family used 100,000 requested
steps, width 100, and seeds 17, 43, and 91. Requested steps and expanded operation
counts differ, and both are recorded.

Direct pruning helped most families but failed badly on interleaved Moves:
median total construction was 50.547 seconds, versus 3.702 for deferred
collection and 0.522 for incremental antichains. It retained roughly 2,300
candidates instead of 100,100, yet final Comparison became much slower. Fewer
candidates alone do not imply less reachability work; pruning also changes the
candidate density and which Comparison strategy the existing implementation uses.

Incremental antichains were not a good general replacement: written references
took 12.090 seconds versus 0.664 deferred, and wide implied access took 1.310
versus 0.240. Independent candidates require repeated reachability checks even
though none can be discarded. The final implementation summarizes the known
direct-Move chain without making these queries for arbitrary quality uses.

The [initial large matrix](vanish_large_results.jsonl) was deliberately stopped
after nine completed measurements to focus on this specialization. Completed
records and its source snapshot are preserved. Unfinished runs are not results.
One completed million-step movement run took 51.714 seconds with deferred
collection; another took 48.578 with direct pruning. This incomplete matrix is
not used for median comparisons.

## Repeated comparison

The 63-run [comparison matrix](vanish_final_results.jsonl) uses randomized run
order, seven families, three seeds, and 100,000 requested steps at width 100.
The table gives median **total construction seconds**, including lifetime
collection and final Vanish Comparison. Position-only measurements omit Vanish
entirely and are not competing implementations of the same complete result.

| Workload | Position graph only | Deferred Vanish | Specialized Vanish |
| --- | ---: | ---: | ---: |
| local | 0.160 | 0.287 | 0.218 |
| movement | 0.372 | 3.795 | 0.378 |
| implied | 0.224 | 0.544 | 0.400 |
| written | 0.388 | 0.689 | 0.617 |
| wide | 0.105 | 0.246 | 0.217 |
| state | 0.328 | 0.526 | 0.458 |
| growth | 3.216 | 5.931 | 3.944 |

The specialized implementation was faster than deferred collection in each
family's median. This establishes a choice among these measured alternatives,
not universal time optimality. Growth-heavy position construction and general
reachability still dominate substantial costs.

## Million-step scaling

All 24 runs in the [scale matrix](vanish_scale_results.jsonl) completed. Each
family used one million requested steps, width 100, and three seeds. Every
specialized graph digest matched its deferred counterpart, including all
original operations and appended Vanishes.

| Workload | Deferred seconds | Specialized seconds |
| --- | ---: | ---: |
| movement | 50.442 | 3.844 |
| implied | 7.030 | 4.232 |
| wide | 2.820 | 2.521 |
| state | 5.856 | 5.213 |

These are medians of total construction time, not just final Vanish insertion.
The implied family contains 2,000,200 original operations and 1,000,100 Vanishes.
The largest specialized process peak in this matrix was about 1,401 MiB,
including workload generation and all inputs. The wide family's maximum peak
was about 696 MiB specialized versus 814 MiB deferred. In several other families
generation dominated the peak, preventing a useful isolated collector-memory
comparison from these resident-memory numbers.

Reproduce with:

```sh
uv run --frozen -m operation_graph_optimization.vanish_matrix --output /tmp/vanish-scale.jsonl --steps 1000000 --families movement,implied,wide,state --strategies deferred,specialized --seeds 17,43,91
```

## Wider antichains and complete destruction

The [width matrix](vanish_width_results.jsonl) uses 10,000 requested steps and
10,000 possible independent implied positions across three seeds. All twelve
graphs matched by digest. Median construction was 0.035 seconds deferred,
0.034 direct-pruned, 10.259 incremental-antichain, and 0.032 last-Move-specialized.
This exposes the incremental strategy's repeated work on genuinely independent
uses; an exact antichain after every use is not a good default.

The [completed-growth baseline](vanish_closed_results.jsonl) additionally destroys
every remaining particle after 250,000 growth-heavy steps. The last-Move strategy
took 50.527 seconds for seed 17, including 24.094 seconds in final Vanish
Comparison. Two deferred runs were killed with return code -9 under the stated
resource limits. The remaining baseline repetitions were stopped deliberately;
the successful run and failures are retained, not relabeled as final passes.

This motivated the second specialization: omit quality uses already ordered by
ordinary occupancy. The [follow-up](vanish_covered_closed_results.jsonl) completed
all three seeds in 25.998–29.783 seconds, with final Vanish processing taking
1.104–1.166 seconds. Seed 17's full graph digest matches the successful baseline.
Position graph construction now dominates this workload. The extra reference
classification is counted in generation, and the filtering is counted in
construction; neither disappears from the recorded costs.

The retained-intermediate-reference source regression checks the boundary of
this rule: a reference through retained destructor state still delays the
original particle's Vanish. Ordinary action interface and implied accesses are
also checked explicitly, not just constructors and destructors.

Reproduce these stress families with:

```sh
uv run --frozen -m operation_graph_optimization.vanish_matrix --output /tmp/vanish-width.jsonl --steps 10000 --width 10000 --families wide --strategies deferred,direct,incremental,specialized --seeds 17,43,91
uv run --frozen -m operation_graph_optimization.vanish_matrix --output /tmp/vanish-completed-growth.jsonl --steps 250000 --width 100 --families growth_closed --strategies vacancy_covered --seeds 17,43,91
```

## Final cross-workload trade-off

All 48 runs in the [occupancy-coverage comparison](vanish_covered_results.jsonl)
completed with matching full graph digests for every pair. These are median total
construction seconds at 100,000 requested steps, width 100, and three seeds:

| Workload | Last-Move only | With occupancy coverage |
| --- | ---: | ---: |
| local | 0.218 | 0.220 |
| movement | 0.374 | 0.376 |
| implied | 0.390 | 0.390 |
| written | 0.589 | 0.595 |
| wide | 0.216 | 0.220 |
| state | 0.453 | 0.448 |
| growth | 3.972 | 3.502 |
| growth_closed | 9.548 | 7.520 |

The extra classification/filtering is not free. Median construction was about
0–1.8% slower in several non-benefiting families, about 1% faster in the balanced
state family, 12% faster in growth, and 21% faster in completed growth. The
small differences are not evidence of a universal performance ordering. The
completed-growth stress result makes the shortcut worthwhile as a default when
ordinary intermediate occupants are already available from source resolution.
If obtaining that information is expensive for a different caller, the last-Move
specialization alone remains a correct alternative; charge that caller's
resolution cost before choosing.

Four [final million-step checks](vanish_covered_scale_results.jsonl), using seed
17 with both shortcuts enabled, matched the earlier deferred graph digests.
Total construction was 3.855 seconds for movement, 4.166 for implied access,
5.336 for balanced state-driven operations, and 2.474 for wide access.

After removing a redundant repeated-candidate guard, the
[final implementation check](vanish_verified_results.jsonl) repeated all eight
families at 100,000 steps with seed 17. Every graph digest matched the preceding
matrix. Its snapshot records the final algorithm exactly.

## Reproduction and measurement boundaries

Measurements used CPython 3.14.6 (free-threaded build), Linux x86-64, and an AMD
Ryzen 9 9950X. Matrix files record the platform and embed source snapshots. The
preliminary implementation is represented by the initial large matrix's snapshot;
annotation and formatting corrections during preliminary runs did not change
its algorithms. Existing archived implementations and measurements are unchanged.

Each measurement runs in a fresh process, with a 3-GiB address-space limit and
a 90-second CPU limit. The matrix runner also imposes a 120-second wall timeout
and preserves failures. It randomizes the order of processes with seed 501.

Generation includes state-based choice, independent operation-order
randomization, and particle-identity resolution. None is timed as construction.
The construction timer includes initializing the graph and collector, building
all position dependencies, maintaining lifetime collections, Comparison, and
appending Vanishes. Counting retained candidates is outside that timer. Scale
runs also hash every operation's sorted dependencies **after** timing to compare
complete graphs, not just edge counts.

Peak resident memory is the process high-water mark, including generation and
retained inputs. It is not a measurement of collector allocations alone;
generation can dominate it. Candidate counts omit the specialized implementation's
separate last-Move dictionary, which has at most one occurrence per moved
particle. This dictionary's allocation and maintenance are included in timing
and resident memory.

From the research repository, run:

```sh
uv run --frozen -m operation_graph_optimization.vanish_benchmark --strategy vacancy_covered --family movement --steps 1000000 --width 100 --seed 17
uv run --frozen -m operation_graph_optimization.vanish_matrix --output /tmp/vanish-reproduction.jsonl --steps 100000 --families local,movement,implied,written,wide,state,growth --strategies base,deferred,specialized --seeds 17,43,91
bazelisk test --noshow_progress --ui_event_filters=-info //operation_graph_optimization:vanish_integration_test
```

The matrix destination must not already exist, so reruns cannot overwrite an
earlier record accidentally.

## Validity and limits

The local, movement, implied, written, and wide families preserve selected
occupancy while varying valid choices and independent operation ordering. State
and growth use the existing state-driven sampler with depth six and branching
two. They include partial executions with particles still alive; `growth_closed`
additionally Vacates all remaining particles. Complete lifetime collection is
required only for the particles whose Vanishes are emitted.

Reordering comes from the archive's independent conflict construction, not from
the optimized graph. These are reordered resolved operations, not a claim that
arbitrary interleaving of action bodies can be written as one flat source block.
Actual particle identities and the chosen occupancy-conflict orientation are
preserved. The benchmark does not resolve arbitrary Define source or implement
modular destructor analysis.

Source-based integration checks validate real Define programs independently of
the compiler's operation graph. They cover local reuse and direct movement,
constructor and interface access that can outlive Vacate, destructor access,
shared retained child movement, replacement identities, and transitive movement
that does not delay a child's Vanish. Small generated cases compare every Vanish
dependency against an independent ancestor-set oracle. Small source cases also
enumerate schedules to confirm that actual uses precede Vanish while remaining
unordered with Vacate when appropriate.

## Final validation

All four research Bazel test targets pass, including 144 Vanish integration and
differential cases. The final `vanish_algorithm.py` has coverage of all 36
executable lines and all 14 reported branches. Formatting, lint, type checking,
and repository hooks pass. Bazel testing was supplied by the coverage run rather
than duplicated by the hook.

The first coverage attempt exposed missing runtime `coverage` dependencies in
the archive's Python test targets. The BUILD wiring now supplies them; the final
coverage report contains measured execution rather than empty records. Existing
archived algorithm sources and recorded measurements were preserved.

Across all matrices, 244 measurements completed successfully and two runs were
killed under the configured limits. Deliberately interrupted, unrecorded
repetitions are not counted as results. No universal time-optimality theorem is
claimed, and no compiler or specification changes were made.
