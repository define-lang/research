# Algorithm thresholds

The selected defaults are:

| Constant                             | Value | Purpose                                                                                 |
| ------------------------------------ | ----: | --------------------------------------------------------------------------------------- |
| `MAX_PRUNING_CANDIDATES`             |    16 | Bound optional removal of earlier remembered uses for each referenced position.         |
| `MAX_SUPPLIER_SEARCH_CANDIDATES`     |    16 | Bound the full search for a remembered use that makes a supplier candidate unnecessary. |
| `MAX_PAIRWISE_COMPARISON_CANDIDATES` |    64 | Use shared traversal rather than pairwise reachability questions above this count.      |

The two former eights increase to 16; Comparison remains at 64. These are named
implementation choices, not language rules or uniquely optimal mathematical
constants. The specification is unchanged.

## What can be derived from logic?

Pruning and supplier omission are optional shortcuts. For pruning, the guard
bounds the number of collected candidates passed to the set operation for each
referenced position. Above the guard, retaining extra remembered uses remains
correct. For supplier search, the guard bounds the candidate set involved in the
intersection check. Above it, only the most recently remembered use is checked;
Comparison resolves any redundancy left over. A fixed bound keeps this optional
work from multiplying arbitrarily large candidate collections by long
references. The correctness arguments do not depend on the numeric bound.

Comparison has a different trade-off. Pairwise comparison can ask up to
`k * (k - 1) / 2` reachability questions. Shared traversal visits shared earlier
vertices once per comparison rather than searching the same ancestry repeatedly.
But its ancestry can be much larger than the candidate set, whereas cached or
quickly rejected pairwise questions can be cheap. Equal-height collections
already have a fast path in both methods.

Consequently, candidate count alone cannot determine the exact cheaper method.
The graph shape, earlier cache use, interpreter, and hardware affect the
crossover. We can narrow an empirical region and select a reasonable default; we
cannot derive an exact universal integer from these cost bounds.

## Experiments

[The raw artifact](threshold_results.json) contains 422 construction benchmarks,
all successful, with arguments, settings, source variants, and the exact
benchmark launcher. Each run also passed the independent randomized execution
check. Those checks are not exhaustive verification of every possible schedule.

All measurements exclude source generation, valid-operation selection, input
reordering, and execution validation. Processes ran sequentially without
concurrent benchmark or test runs on an unreserved, unpinned host using CPython
3.14.7 on 2026-09-06. These are exploratory single measurements, not confidence
intervals. All unusually slow measurements remain in the artifact. Major sweeps
used shuffled execution order; the artifact records the procedure and ordering.

The phases were:

- 174 independent screening runs: each threshold varied while the other two
  retained their original settings. Inputs included growth, uniform concrete
  choices, long references, shared joins, overlapping Moves, and multiple shared
  parents. Optional-work limits ranged from zero to effectively unrestricted.
  Comparison ranged from 8 through 256 and effectively unrestricted pairwise
  work.
- 48 runs of an alternative guard that allowed full set work when either the
  candidate set or the remembered-use set was small.
- 24 depth checks comparing that alternative with the original guards at depths
  2, 6, and 12, including inputs with up to 21 occupied-position requirements
  across an operation's references.
- 87 finer independent runs, including limits 6, 8, 10, 12, 16, 24, and 32 for
  each optional shortcut, and Comparison checks across two seeds, two reference
  depths, and independently reordered input.
- Three runs of a direct-edge-based cost estimate and six runs of a variant that
  reconsidered pairwise comparison after direct-dependency omissions.
- 36 joint-setting runs with both optional-work limits at 16 and Comparison
  limits 40, 48, 52, 56, 60, 64, 68, 72, and 80.
- 44 final confirmations covering all eleven structured families, all five
  state-driven distributions on a fresh seed, reordered input, and larger
  inputs.

## Why increase the two eights?

Representative independent screening times, in seconds:

| Varied shortcut and workload                                      | Disabled full shortcut | Limit 4 | Limit 8 | Limit 16 | Unrestricted |
| ----------------------------------------------------------------- | ---------------------: | ------: | ------: | -------: | -----------: |
| Remembered-use pruning, growth, 100,000 statements                |                 10.826 |   2.762 |   2.126 |    2.081 |        2.089 |
| Supplier intersection search, uniform choices, 100,000 statements |                  2.520 |   2.421 |   2.181 |    2.164 |        2.178 |

Disabling full supplier search still permits its existing most-recent-use check.
Disabling pruning keeps the remembered uses rather than losing them.

Eight was adequate for many shorter-reference inputs, but not consistently for
longer ones. At depth six, raising pruning alone from 8 to 16 changed growth
construction from 2.785 to 2.571 seconds; raising supplier search alone changed
it from 2.833 to 2.694 seconds. The other shortcut remained at 8 in each of
those independent comparisons. The final larger-input comparison below checks
the combined effect.

Beyond 16 there was no consistent additional benefit. Keeping a finite guard
preserves the bound on optional work for wide collections and long references.
The alternative based on both set sizes helped some low-limit cases but did not
show a consistent improvement at the useful settings, so it was rejected.

## How tightly is Comparison's crossover known?

With the original optional-work limits, the initial growth sweep improved from
3.678 seconds at Comparison limit 8 to 2.650 at 16, 2.313 at 24, and 2.128
at 32. Larger settings usually clustered near 2.1 seconds. One 64-limit run took
2.993 seconds; other runs of the same settings were near 2.1. It remains in the
raw data and is not used to manufacture an apparent optimum elsewhere.

The joint sweep, with both optional-work limits at 16, gave:

| Comparison limit | Growth, depth 4, seed 17 | Growth, depth 6, seed 17 | Growth, depth 6, seed 41 | Reordered growth, depth 4, seed 41 |
| ---------------- | -----------------------: | -----------------------: | -----------------------: | ---------------------------------: |
| 40               |                    2.131 |                    2.668 |                    2.570 |                              2.601 |
| 48               |                    2.082 |                    2.629 |                    2.566 |                              2.622 |
| 52               |                    2.085 |                    2.572 |                    2.573 |                              2.610 |
| 56               |                    2.101 |                    2.629 |                    2.595 |                              2.594 |
| 60               |                    2.092 |                    2.615 |                    2.658 |                              2.580 |
| 64               |                    2.095 |                    2.634 |                    2.567 |                              2.623 |
| 68               |                    2.091 |                    2.604 |                    2.540 |                              2.574 |
| 72               |                    2.076 |                    2.597 |                    2.567 |                              2.586 |
| 80               |                    2.108 |                    2.574 |                    2.546 |                              2.591 |

Each input has 100,000 statements. Reordering uses seed 97 and is outside the
timer. The numbers support a broad region around 48–80, not one precise winner.
They do not justify choosing an exact integer such as 52 or 68 from its fastest
single run. Larger-input confirmations support retaining 64 within that region:

| Input, both optional limits 16                 | Comparison 56 | Comparison 64 | Comparison 72 |
| ---------------------------------------------- | ------------: | ------------: | ------------: |
| Growth, 1,000,000 statements, depth 4, seed 17 |        23.499 |        23.395 |        23.411 |
| Growth, 500,000 statements, depth 6, seed 17   |        41.457 |        40.791 |        41.488 |

A simple proposed cost rule chose shared traversal when the number of possible
pairwise queries exceeded the candidates' total immediate dependency count. It
increased growth time to 6.528 seconds, versus about 2.1. Immediate edge counts
omit deeper ancestry and cache effects. Rechecking the threshold after
direct-dependency omissions also showed no clear benefit. Neither extra policy
is retained.

## Final matched comparisons

These compare the old policy (8, 8, 64) with the selected policy (16, 16, 64),
using the same implementation with named constants. They measure policy changes,
not the tiny possible effect of replacing literal constants with named globals.

| Input                                                       | Old policy | Selected policy |
| ----------------------------------------------------------- | ---------: | --------------: |
| Growth, 1,000,000 statements, depth 4, seed 17              |     23.744 |          23.395 |
| Growth, 500,000 statements, depth 6, seed 17                |     58.478 |          40.791 |
| Uniform concrete choices, 1,000,000 statements, seed 17     |     23.984 |          23.705 |
| Growth, 100,000 statements, seed 97                         |      2.193 |           2.182 |
| Growth, 100,000 statements, seed 41, reordered with seed 97 |      2.582 |           2.564 |
| Movement, 100,000 statements, seed 97                       |      1.113 |           1.126 |

The demanding longer-reference case improved about 30%. Most other differences
were small. Some structured inputs were slightly slower: for example, shared
join took 0.262 versus 0.255 seconds, and vacancy reuse took 0.187 versus 0.182.
There is no universal speedup claim. The raw artifact includes every structured
family and both settings, not only favorable rows.

An intermediate progress update incorrectly compared the reordered 2.582-second
run with the unreordered 2.182-second run. The two separate matched rows above
correct that comparison; they are not evidence of a 16% improvement.

## Validation and reproduction

Final repository-wide coverage passed all 357 test targets. The coverage
analyzer reported zero actionable uncovered branches in
`operation_graph_optimization`, with nine explicit-exit-only branches omitted.
Bazel integration and type checks also passed. The final lint correction removed
one blank line after imports; the artifact preserves the measured source and
records the final source hash separately.

The integration test `test_threshold_choices_preserve_source_dependencies`
checks actual generated Define source with random operations, long references,
and shared joins. Twelve cases cover skipped optional work, small limits, normal
limits, and effectively unrestricted pairwise comparisons. Each compares every
dependency row against the independent full-history reference algorithm.

The artifact contains all source variants and the exact launcher. Save its
`benchmark_launcher` string as `/tmp/define-threshold-benchmark.py`, then, after
the repository's local-development setup, run from the repository directory:

```sh
PYTHONPATH=. uv run /tmp/define-threshold-benchmark.py --pruning 16 --supplier 16 --comparison 64 --workload state --distribution growth --steps 100000 --depth 6
```

The launcher changes the three module constants before generation starts; it
does not instrument the timed methods. Recorded arguments reproduce individual
runs against their recorded source variant. The cache defaults stay at 1,024
targets and 64 MiB throughout this investigation.

`restore_baseline.patch` has been refreshed to apply to the current files. The
previous patch is preserved in the raw artifact for the older measurements.
