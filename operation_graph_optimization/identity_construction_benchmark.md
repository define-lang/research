# Identified-operation construction measurements

These experiments compare complete occupancy and lifetime construction on the
same resolved endpoint requirements. The revised calculation also collects
parent relationship periods and conditions. The prior backend is the unchanged
`complete/algorithm.py`; it does not calculate those relationship conditions.
This is not a comparison between compiler runs with old and new source rules.

## Workload and timing boundaries

The generator creates a tree with maximum depth six. At each step it chooses
randomly among ready Creates and Moves. A child's Create becomes eligible when
its defining particle is created; each particle's two Moves preserve its parent
relationship and follow its own preceding operation. Their ordering relative to
other ready operations is randomized. Finally the generator randomizes the
Vacates of one simultaneous destruction and appends the corresponding Vanishes.

Every particle contributes five operations. Seed 711039 supplies the same
inputs to both backends. Before timing, the benchmark checks equality of every
ordinary and Vanish dependency set. The tree's possible parent relationships
are acyclic, so it requires no alternative cycle conditions.

Generation, conversion to the prior input format, and correctness checks are
outside the construction timings. Generation is reported separately in the raw
results. These inputs are resolved operations, not a measurement of parsing or
source identity resolution. This family tests many interleavings but does not
cover arbitrary parent-changing Moves or sharing destructors; the semantic
tests cover those separately.

Measurements used an AMD Ryzen 9 9950X, Linux 7.1.8, and CPython 3.14.6
free-threading build. Each table entry is the median of three wall-clock samples.

## Successive implementation choices

The first implementation used dictionaries for particle-indexed bookkeeping and
strongly connected components to discharge acyclic relationships. The next
variant checked for a strictly increasing or decreasing particle-number rank
before allocating component records. This certificate changes no permitted
order; failure of the rank test still uses the complete component calculation.

The dense-record variant replaces the three particle-indexed dictionaries by
compact integer arrays and records each particle's destruction directly.
The compact-period variant uses fixed-field records and tuples of end events,
rather than a dictionary-backed record and a hash set for each period. An
ordinary Move already preceding Vacate is not a separate end event; a last
destruction Move still participates in the required Join.

| Variant | 5,000 operations | 50,000 operations | 1,000,000 operations |
| --- | ---: | ---: | ---: |
| Dictionaries, component calculation | 0.008574 s | 0.087070 s | 3.202330 s |
| Rank certificate | 0.007936 s | 0.082921 s | 3.025379 s |
| Dense particle records | 0.007932 s | 0.082091 s | 2.810596 s |
| Compact relationship periods | 0.007829 s | 0.079160 s | 2.745612 s |
| Prior backend, paired with final row | 0.009289 s | 0.094672 s | 2.934564 s |

All revised rows include relationship-condition construction, even though it
finds no cycles on this family. Ordinary construction alone is recorded
separately in the JSON files. The final row is about 6% faster than the prior
backend at one million operations on this family; this is not a universal speed
claim or a bound for an interacting choice problem.

## Allocation measurements

A separate `tracemalloc` run used 100,000 operations generated with the same
seed and depth. Inputs were generated before tracing, garbage was collected
before each backend, and its returned result remained alive when measured.
Tracing was not enabled for the timings above.

| Representation | Allocations retained by result (bytes) | Peak traced allocations (bytes) |
| --- | ---: | ---: |
| Dense arrays, hash-set period ends | 16,688,672 | 28,867,112 |
| Dense arrays, compact period ends | 11,726,400 | 23,904,624 |
| Prior backend | 4,546,832 | 13,979,456 |

The revised result retains identified operations and relationship periods in
addition to the ordinary graph. The prior result contains only that graph.
The measurements therefore expose the extra retained representation, not a
like-for-like graph-storage comparison. Input objects, process resident memory,
and allocator overhead outside `tracemalloc` are not included.

## Reproduction and records

```sh
uv run --frozen python -m operation_graph_optimization.identity_benchmark --sizes 1000 10000 200000 --repeats 3
```

Raw samples and generation costs are preserved in `identity_components_results.json`,
`identity_rank_results.json`, `identity_dense_results.json`, and
`identity_compact_period_results.json`. The dictionary implementation is archived
in `identity_algorithm_before_dense.txt`; the pre-component relationship
calculation is in `relationship_periods_before_components.txt`.

An attempted no-operation action fixture containing only an unused position
declaration was rejected by the existing Unreferenced Names rule. It was removed,
not treated as valid source or marked as an expected compiler failure. No
empty-input extension of the full-input constructor was retained from it.
