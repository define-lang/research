# Early Vacate/Vanish combination

## Question and safety condition

The explicit complete algorithm always emits Vanish separately. This experiment
tests the specification's existing Combining Vacate and Vanish permission.
The exact condition is that every quality use and every direct Move of the
particle already precedes its Vacate. The Vacate is then Vanish's only direct
dependency. Combining removes a terminal vertex without changing dependencies
among any remaining operations or postponing vacancy.

The English argument is in the Define repository's
`proofs/operation_graph/theorems/vanishment-proof.md`, under "Certifying
combination before constructing Vanish." No specification change is required.

## Experimental implementations

`combination_algorithm.py` preserves the complete position construction and
accepts a set of particle identities that still need lifetime analysis. For
other particles, it skips quality-use and direct-Move tracking and records the
Vacate as the combined operation immediately. For the remaining particles,
finalization applies ordinary Vanish Collection and Comparison. If the result
is just the Vacate, it records that as the combined operation; otherwise it
appends a separate Vanish. `complete/graph.py` needs no modification.
The refined version also skips the quality-use filtering loop when the
whole-input certificate leaves no particles requiring lifetime analysis.

`combination_inputs.classify` conservatively marks a particle for lifetime
analysis if any actual quality use lacks ordinary intermediate occupancy of
that particle, or if a direct Move occurs after its selected Vacation in the
resolved serial input. The latter uses recency, not an assumed execution order.
Every simultaneous Vacate is processed before the destruction operations that
follow that simultaneous selection. Their enumeration does not order them.

This full-input classification proves absence of relevant future uses without
consulting the graph. It is not yet a compiler analysis of triggered callees.
Its cost is measured separately and added to construction time in a second
reported total. Source generation, valid-operation selection, reordering, and
input conversion remain excluded. A compiler could accumulate an equivalent
summary during existing source resolution; the experiment does not assume that
such a summary is free.

The compared strategies are:

- `pre_vanish`: only the archived Create/Move/Vacate graph, with no lifetime work.
- `final`: the complete explicit Vacate/Vanish implementation.
- `late_combination`: track all required particles, combining only after
  Comparison finds the Vacate is the sole dependency.
- `early_combination`: skip certified lifetime tracking and also apply the
  finalization check to uncertified particles.

An interface or implied reference in a transitively triggered action may escape
the ordinary occupancy requirement. A written reference through retained
destructor state may do so too. Conversely, those reference forms do not imply
that combination is forbidden: other requirements may already put the use
before Vacate. A directly moved particle need not have any accessed qualities
of its own. Another particle's destructor may move it after Vacation.

## Validation method

The integrated tests compare all Create/Move/Vacate rows with an independent
full-conflict reference. Their independent all-use ancestry oracle also checks
that every early-certified particle's uses are covered by its Vacate. Both
combination paths must agree exactly with the explicit graph's Vanish
dependencies after expanding a combined operation into Vacate followed by
Vanish. Tests include real Define source, implied/interface accesses,
destructor Moves, retained intermediate occupancy, replacements, long names,
and independently reordered valid inputs.

Adding the retained, never-accessed-position case exposed a missing capability
in the independent oracle: it previously recorded only accesses, not the Create
that defined a position. Its histories now include that defining Create, so a
retained empty position has its actual initial prerequisite. All tests using
the oracle are checked after this correction. The source case contrasting
automatic child Vacation with a written child Destroy also checks that implied
access can be covered by a later ordinary reference, allowing final combination
even when the early certificate declines it.

Benchmark graphs have different vertex counts, so their raw full-graph hashes
cannot match. `position_digest` compares the unchanged ordinary operation rows.
`lifetime_digest` compares particle identities and the explicit Vanish
dependencies, treating a combined operation as an implicit Vanish with only
its Vacate as dependency. This normalization is outside the timer and does not
modify the measured graph. Pre-Vanish runs have no lifetime graph to compare.

Exact source snapshots are embedded in each JSONL measurement file. Earlier
algorithms and recorded results remain unchanged; this is a separate experiment.

## Repeated construction measurements

The initial matrix has 120 runs: ten families, four implementations, and seeds
17, 43, and 91. Every run completed, all position digests matched, and every
complete lifetime digest matched after the normalization above. At 100,000
requested steps, combination at finalization alone changed implied-use
construction from 0.301 to 0.294 seconds and mixed construction from 0.401 to
0.391 seconds. It still did all the lifetime tracking; its setup scan made the
respective totals 0.311 and 0.407 seconds. There was no general speed advantage
to that approach, although it reduced graph storage.

The 60-run refined matrix repeats all ten families and three seeds for the
explicit algorithm and early combination. Median seconds:

| Workload | Explicit | Early combination construction | Including classification |
| --- | ---: | ---: | ---: |
| Local operations | 0.198 | 0.166 | 0.175 |
| Direct Moves | 0.372 | 0.365 | 0.372 |
| Implied quality uses | 0.302 | 0.267 | 0.291 |
| Written references | 0.542 | 0.457 | 0.493 |
| Wide independent uses | 0.179 | 0.157 | 0.168 |
| Mixed state-driven operations | 0.453 | 0.335 | 0.352 |
| Completed growth | 7.684 | 7.232 | 7.306 |
| Shared retained destructor Moves | 0.163 | 0.168 | 0.179 |
| Seven-name references | 0.748 | 0.709 | 0.726 |
| Twenty-one-name references | 0.999 | 0.938 | 0.981 |

These medians are not confidence intervals. Several runs slowed substantially:
explicit written-reference times ranged from 0.531 to 0.895 seconds; early
written-reference times from 0.391 to 0.524; early completed-growth times from
6.851 to 9.149. All remain in the records. The initial batch's explicit mixed
median was 0.401 rather than 0.453. The results support the optimization's
benefit, but not a precise or universal percentage improvement.

The retained-destructor workload combines none of its 101 Vanishes. Its extra
classification and membership checks are pure overhead. Direct movement has
only 100 Vanishes despite 100,000 Moves, so little work disappears. Long-name
inputs have only 700 or 2,100 Vanishes; the classification scan traverses many
references to save relatively few vertices. The whole-input fast path helps
their construction, but the separate scan consumes most of that saving.

All Vanishes combine in the local, written, mixed, completed-growth, and deep
families. The implied family combines 100,000 of 100,100; the wide family all
but one. Those remaining parent particles have actual independent implied
quality uses. These counts describe the generated inputs, not a prediction of
the frequency in production programs.

## Graph storage

Each eligible Vanish in the explicit implementation has one edge to its Vacate.
Removing it saves 24 bytes of array payload: one offset, one height, and one
dependency. Vanishes already had no reverse-index entries. Thus the graph-array
saving is exactly `24 * combined_vanishes`, independent of timing variation.
For 100,000-step implied inputs that is 2,400,000 bytes. Graph arrays are about
20% smaller there and about 17% smaller in the mixed inputs. Python collections
and peak allocations are separate measurements, not included in these counts.

## Practical recommendation

Use early combination when source resolution can supply the sufficient
certificate cheaply, and retain the exact finalization check for other
particles. Do not infer the certificate from the particle having no destructor
or from the absence of accesses to its own qualities: another destructor may
move it directly. Do not use an unfinished scan to assert that no future callee
can require it.

The full resolved-input scan tested here is correct, but is not demonstrated to
be the best compiler implementation of that analysis. It traverses all quality
requirements and, in the final version, remembers directly moved particles.
Its time is linear in resolved operations plus reference requirements, and its
temporary memory is linear in the marked and directly moved particle counts.
It is worthwhile on several measured workloads and detrimental on the
retained-Move workload. Incorporating the
same facts into existing resolution could avoid that separate traversal; doing
so is not included in the measurements or implemented in the compiler.

## Classification refinement

The first classifier scanned forward and remembered every vacated particle to
detect a subsequent direct Move. At one million implied-workload steps, this
scan cost 0.378 seconds, exceeding the 0.294-second construction saving:
explicit construction took 3.119 seconds, early construction 2.825, and the
latter including classification 3.203. Those nine large-input measurements are
preserved in `combination_scale_results.jsonl`.

The final classifier scans backward. At each Vacate, the remembered Move
identities are precisely the particles moved later in the resolved sequence.
Membership therefore tests the same condition as the forward scan. Quality-use
classification is independent of traversal order. This records moved particles
rather than every destroyed particle: the implied workload needs no such Move
identities at all, instead of remembering over a million Vacates. This is an
analysis optimization, not a graph or language rule change.

The construction algorithm is unchanged by that refinement. All 445 integrated
cases pass with the reverse scan, including the two source boundaries above.

## Final million-step check

The reverse-scan matrix compares the final experiment with both earlier
algorithms on the same inputs. These are individual seed-17 runs, not medians:

| Workload | Pre-Vanish | Explicit Vanish | Early construction | Including classification |
| --- | ---: | ---: | ---: | ---: |
| Direct Moves | 3.745 | 3.773 | 3.723 | 3.809 |
| Implied quality uses | 2.190 | 3.131 | 2.810 | 3.090 |
| Mixed state-driven operations | 3.515 | 4.513 | 3.745 | 3.976 |

The reverse scan reduced implied classification from 0.378 to 0.280 seconds.
It made direct-Move classification slightly slower, 0.086 versus 0.062 seconds,
because it records repeated Moves instead of testing them against a mostly
empty Vacate set. Mixed classification was similar, 0.231 versus 0.226 seconds.
The refinement avoids the large all-Vacates set, but does not eliminate analysis
cost or make the optimization beneficial on every workload.

The implied input has 2,000,200 Create/Move/Vacate occurrences. It combines one
million of 1,000,100 Vanishes and saves 24,000,000 bytes of graph-array payload.
The mixed input has 1,691,864 original occurrences and combines all 680,848
Vanishes. Direct movement combines all 100 Vanishes, which is negligible beside
its million Moves. None of these savings changes the required graph ordering.

## Final allocation measurements

Construction plus classification allocation peaks, 30,000 requested steps,
width 100, seed 17, with input preparation excluded:

| Workload | Explicit MiB | Early combination MiB |
| --- | ---: | ---: |
| Local operations | 2.814 | 2.408 |
| Implied quality uses | 6.147 | 5.565 |
| Written references | 10.143 | 10.143 |
| Mixed state-driven operations | 7.776 | 7.426 |
| Completed growth | 18.239 | 17.836 |
| Shared retained destructor Moves | 3.854 | 3.863 |

The original and reverse classifiers gave essentially the same overall peaks:
their temporary sets did not dominate these smaller inputs. Graph-array savings
do not translate directly into peak savings because position construction may
reach its peak before Vanishes are appended. In particular, written-reference
peak allocations did not improve despite its smaller completed graph. Traced
timings are excluded from performance comparisons, and these are not total
process resident-memory measurements.

## Records and reproduction

All 222 measurements completed successfully. Across all six files, position
digests agree for every shared input, and normalized lifetime digests agree for
every complete implementation. Source snapshots, commands, exit statuses, and
raw timings are preserved in the records:

Final repository-wide coverage passes all five test targets, including 445
integrated cases. The combination algorithm has 191/191 executable lines and
104/104 branches covered; the classifier has 20/20 lines and 10/10 branches;
the updated independent oracle has 45/45 lines and 24/24 branches. Formatting,
lint, and type checks pass.

The separate `pre_vanish_comparison_results.jsonl` belongs to an earlier
interrupted command. Final inspection found that it continued in the background,
contrary to the earlier conversational statement that no runs had started. It
contains 28 successful records and 20 argument-parsing failures after the
pre-Vanish option was removed during that interruption. It is preserved but
excluded from these comparisons. Its final modification was at 00:44:53 on
September 8, 2026; the first combination matrix was created at 00:51:05, so it
did not overlap the timed combination experiments.

| File | Runs | Version |
| --- | ---: | --- |
| `combination_initial_results.jsonl` | 120 | Four-way comparison, forward classification |
| `combination_refined_results.jsonl` | 60 | Whole-input fast path, forward classification |
| `combination_scale_results.jsonl` | 9 | Million-step check, forward classification |
| `combination_memory_results.jsonl` | 12 | Allocation peaks, forward classification |
| `combination_reverse_scale_results.jsonl` | 9 | Final reverse-classification million-step check |
| `combination_reverse_memory_results.jsonl` | 12 | Final allocation peaks |

All processes ran sequentially within each matrix, with randomized trial order.
No tests or other benchmarks launched by this investigation ran concurrently
with the measurements. The host was not reserved, so unrelated activity and
runtime variation remain possible. No universal time-optimality claim follows.

From the research repository, choose a new filename to preserve prior records:

```sh
uv run --frozen -m operation_graph_optimization.complete_matrix --output combination.jsonl --steps 100000 --families local,movement,implied,written,wide,state,growth_closed,retained,deep6,deep20 --strategies pre_vanish,final,early_combination,late_combination
uv run --frozen -m operation_graph_optimization.complete_matrix --output combination-memory.jsonl --steps 30000 --families local,implied,written,state,growth_closed,retained --strategies final,early_combination --seeds 17 --trace-memory
```

The compiler and specification are unchanged by this experiment. The English
proof extension is uncommitted, as are the research changes. No Lean theorem
was added: the new source-level certificate uses the existing Comparison and
combination arguments rather than requiring a different mathematical model.
