# Referring to Executed Value Operations Instead of Copying Them

The earlier workloads copied (inlined) every executed boolean value operation
into the caller's graph. The design now refers to them instead: an execution
is one node that names the executed value operation and the values it was
given. That's possible because DLP 57's rules only look at the values the
caller's own statements compute, and the executed value operation was
already checked where it's defined. This compares the two.

**Short answer:** referring is what makes deep libraries feasible. Copying
grows by the number of executions per operation at every level (3–4 times
here), reaching millions of nodes and hundreds of milliseconds per operation
at 10–12 levels, and running out of a 20M-node limit at 14. With references,
every method's cost per operation is independent of depth. Truth tables with
lookups are the cheapest exact method up to about 16 views; at 20 views,
recording a table of 2^20 combinations costs about 13 ms per operation,
while OBDDs take 0.1 ms. SAT needs a
refinement scheme that doesn't degenerate: expanding an execution at its
first disagreement can turn into copying (4.6 s for one library), adding one, adding one
clause per disagreeing assignment can need millions of clauses at 16–20
views (31 s, or no answer in 10 minutes), and the hybrid (clauses for an
execution's first four disagreements, then expand it) handled every library
in milliseconds, apart from recording the 20-view tables.

The code is `src/hier.hpp` (`beq hier`), the libraries `gen/hierarchy.py`,
the driver `hierarchy_experiment.py`, and the results
`results/hierarchy.jsonl.gz` (`summarize.py hierarchy`).

## The Methods

Each value operation is checked once, in dependency order, and records the
truth table (and, for the OBDD method, the OBDD) of each view it writes. Its
check is about its own values only.

| Name          | How an execution is handled                                                                                                                                                                                                                                                 |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `copy`        | Its graph is inlined, recursively, into one flat graph, which the combined algorithm then checks.                                                                                                                                                                         |
| `tt`          | Truth tables over the operation's views; an execution is one lookup in the executed operation's recorded table for each combination of views.                                                                                                                             |
| `bdd`         | OBDDs over the views in order; an execution composes the executed operation's recorded OBDDs with the OBDDs of the values it was given.                                                                                                                                    |
| `sat`         | Simulation with lookups groups the values; each candidate pair goes to SAT on the operation's own statements, with each execution's results as free variables. A satisfying assignment is checked against the executed operations' tables, and an execution that disagrees is _expanded_: its own statements are added as clauses, with its executions as new free results. |
| `sat_clauses` | Like `sat`, but an execution that disagrees gets one clause fixing its results for the values it had in that assignment.                                                                                                                                                   |
| `sat_hybrid`  | Clauses for an execution's first four disagreements, then it's expanded.                                                                                                                                                                                                   |

Every method is exact: expansion and clauses are both counterexample-guided
abstraction refinement, and they end because each execution has finitely
many clauses or one expansion, so a satisfying assignment that every
execution agrees with is a real difference.

## Libraries

`gen/hierarchy.py` generates libraries in levels of six operations. Each
operation reads 10 views and writes one or two, and has twelve `and`
statements and, above the first level, three or four executions of
operations from the level below. Every value is tracked by its exact truth
table and redundant statements are rejected, so the libraries compile, except
for planted redundancies: half the operations get a _twin_ computing the same
function as an irredundant sum of products, and an execution of the twin on
the same values as an earlier execution of the original is a redundant
value that only reasoning about functions finds. For more views (12, 16, 20)
the libraries are generated without tracking, so they contain some
redundant values by chance and no twins.

## Results

Each method was run on each library by itself on an otherwise idle
machine, with a limit of 600 s per run; two runs of `sat_clauses` took
longer than the 30 s per check that's the rule now. Deepest level of each
library, median time per operation:

| library | tt | bdd | sat | sat_clauses | sat_hybrid | copy |
| ------- | -- | --- | --- | ----------- | ---------- | ---- |
| deep_e3_l2 | 16.7 µs | 107 µs | 72.3 µs | 2.77 ms | 85.5 µs | 8.6 µs, 60 nodes |
| deep_e3_l4 | 12.1 µs | 99 µs | 43.9 µs | 45.9 µs | 44.4 µs | 60.2 µs, 507 nodes |
| deep_e3_l6 | 12.8 µs | 106 µs | 43.4 µs | 46.2 µs | 44.5 µs | 462 µs, 4,541 nodes |
| deep_e3_l8 | 12.7 µs | 104 µs | 45.6 µs | 47.2 µs | 45.5 µs | 3.55 ms, 39,773 nodes |
| deep_e3_l10 | 13.3 µs | 103 µs | 47.9 µs | 48.9 µs | 48.2 µs | 31.8 ms, 361,225 nodes |
| deep_e3_l12 | 15.7 µs | 114 µs | 68.3 µs | 2.11 ms | 81.2 µs | 307 ms, 3,245,020 nodes |
| deep_e3_l14 | 12.9 µs | 102 µs | 49.1 µs | 50.7 µs | 46.5 µs | 6.1 µs, 12 nodes (6 of 7 past the limit) |
| deep_e4_l2 | 17.9 µs | 102 µs | 67.7 µs | 137 µs | 68.2 µs | 10.4 µs, 71 nodes |
| deep_e4_l4 | 21.9 µs | 103 µs | 163 µs | 8.73 ms | 131 µs | 126 µs, 1,064 nodes |
| deep_e4_l6 | 16.3 µs | 102 µs | 58.9 µs | 62.6 µs | 59.4 µs | 1.65 ms, 17,466 nodes |
| deep_e4_l8 | 17.3 µs | 103 µs | 68 µs | 69.4 µs | 66 µs | 24.2 ms, 277,872 nodes |
| deep_e4_l10 | 16.4 µs | 102 µs | 64 µs | 64.9 µs | 61.7 µs | 393 ms, 4,520,950 nodes |
| deep_e4_l12 | 16 µs | 102 µs | 58 µs | 58 µs | 57.7 µs | 6.8 µs, 15 nodes (6 of 11 past the limit) |
| deep_e4_l14 | 16.8 µs | 114 µs | 60.2 µs | 58.6 µs | 97.7 µs | 5.19 µs, 12 nodes (6 of 9 past the limit) |
| wide_v12 | 54.1 µs | 102 µs | 100 µs | 2.31 ms | 101 µs | 9.04 ms, 39,373 nodes |
| wide_v16 | 526 µs | 98.4 µs | 613 µs | 646 µs | 644 µs | 5.42 ms, 39,377 nodes |
| wide_v20 | 12.6 ms | 103 µs | 12.5 ms | timeout | 12.4 ms | 4.69 ms, 39,381 nodes |

Whole libraries, total time, with the number of SAT refinements:

| library | tt | bdd | sat | sat_clauses | sat_hybrid | copy | methods that finished agree |
| ------- | -- | --- | --- | ----------- | ---------- | ---- | --------------------------- |
| deep_e3_l2 | 114 µs | 1.7 ms | 484 µs, 13 refinements | 16 ms, 6,881 refinements | 567 µs, 71 refinements | 79.2 µs | True, planted 6/6 |
| deep_e3_l4 | 287 µs | 4.21 ms | 1.3 ms, 56 refinements | 53 ms, 19,172 refinements | 1.5 ms, 247 refinements | 629 µs | True, planted 10/10 |
| deep_e3_l6 | 469 µs | 6.66 ms | 2.34 ms, 164 refinements | 48.4 ms, 21,918 refinements | 2.59 ms, 483 refinements | 4.55 ms | True, planted 14/14 |
| deep_e3_l8 | 651 µs | 7.97 ms | 2.96 ms, 162 refinements | 77 ms, 28,154 refinements | 3.03 ms, 332 refinements | 33.7 ms | True, planted 17/17 |
| deep_e3_l10 | 820 µs | 10.2 ms | 4.76 ms, 386 refinements | 80.6 ms, 33,182 refinements | 4.16 ms, 584 refinements | 308 ms | True, planted 20/20 |
| deep_e3_l12 | 991 µs | 12.4 ms | 4.36 ms, 179 refinements | 121 ms, 48,830 refinements | 4.75 ms, 634 refinements | 2.71 s | True, planted 28/28 |
| deep_e3_l14 | 1.12 ms | 12.7 ms | 5.4 ms, 322 refinements | 86.4 ms, 31,918 refinements | 4.75 ms, 377 refinements | 7.58 s (6 unfinished) | True, planted 19/19 |
| deep_e4_l2 | 134 µs | 1.75 ms | 602 µs, 16 refinements | 19.2 ms, 8,025 refinements | 658 µs, 81 refinements | 97.3 µs | True, planted 4/4 |
| deep_e4_l4 | 391 µs | 3.71 ms | 2.11 ms, 194 refinements | 92.6 ms, 31,797 refinements | 2.34 ms, 578 refinements | 1.09 ms | True, planted 15/15 |
| deep_e4_l6 | 599 µs | 5.89 ms | 2.85 ms, 198 refinements | 49.3 ms, 23,221 refinements | 2.66 ms, 324 refinements | 15.4 ms | True, planted 14/14 |
| deep_e4_l8 | 886 µs | 8.24 ms | 9.78 ms, 1,708 refinements | 116 ms, 42,793 refinements | 4.98 ms, 1,067 refinements | 207 ms | True, planted 28/28 |
| deep_e4_l10 | 1.08 ms | 10 ms | 10.7 ms, 1,985 refinements | 130 ms, 53,277 refinements | 5.89 ms, 1,235 refinements | 3.29 s | True, planted 31/31 |
| deep_e4_l12 | 1.29 ms | 11.7 ms | 10.5 ms, 1,785 refinements | 140 ms, 60,051 refinements | 6.3 ms, 921 refinements | 12.8 s (6 unfinished) | True, planted 36/36 |
| deep_e4_l14 | 1.6 ms | 15.7 ms | 4.6 s, 151,400 refinements | 155 ms, 66,749 refinements | 13.5 ms, 3,281 refinements | 12.3 s (18 unfinished) | True, planted 48/48 |
| wide_v12 | 2.31 ms | 5.45 ms | 4.91 ms, 198 refinements | 392 ms, 100,549 refinements | 4.98 ms, 651 refinements | 82.4 ms | True, planted 0/0 |
| wide_v16 | 23.8 ms | 5.88 ms | 31.6 ms, 539 refinements | 31.4 s, 1,196,500 refinements | 31.3 ms, 967 refinements | 47.1 ms | True, planted 0/0 |
| wide_v20 | 530 ms | 5.41 ms | 525 ms, 288 refinements |  | 524 ms, 515 refinements | 45.1 ms | True, planted 0/0 |

Every method that finished gave identical classes on every library, and
every planted redundancy was found.

- **Copying grows by the number of executions per level**: 3.6 ms and 40K
  nodes per deepest operation at 8 levels with three executions each, 307 ms
  and 3.2M nodes at 12, and past the 20M-node limit at 14; with four
  executions, 393 ms and 4.5M nodes at 10 levels.
- **With references, depth doesn't matter**: at the deepest level, 12–22 µs
  per operation with truth tables, 100–120 µs with OBDDs, and 45–160 µs with
  SAT, at every depth from 2 to 14.
- **Expanding at the first disagreement can degenerate into copying**: on the
  library with four executions per operation and 14 levels, `sat` needed
  151,400 refinements and 4.6 s, against 14 ms for `sat_hybrid` (with an
  earlier version of the generator, 86 s).
- **One clause per assignment can need as many clauses as the executed
  operation has combinations of views**: 1.2M refinements and 31 s for the
  16-view library, and no answer within 10 minutes at 20 views.
- **The hybrid was never far from the best SAT variant**: 14 ms against
  155 ms and 4.6 s on the deepest library, 524 ms on the widest one (almost
  all of it recording truth tables), and within 10% of `sat` everywhere else.
- **At 20 views, recording truth tables is the expensive part**: a lookup per
  combination over 2^20 combinations costs about 12.6 ms per operation, and
  `sat` and `sat_hybrid` spend the same, because they record the same
  tables. OBDD composition takes 0.1 ms. For an 8-level library at 20 views,
  copying (45 ms for all 48 operations) beats referring with truth tables
  (530 ms), because copying never builds a table. Recording OBDDs instead,
  and looking results up in them for simulation and for the SAT method's
  consistency check, would avoid the 2^20 cost; that's argued, not
  measured.

## What the Executed Operation's Own Check Saves

An executed value operation has already passed every check where it's
defined: its values are distinct from each other, from the constants, and
from its read views. That guarantee is over its own read views, which are
independent there. In a caller, the read views get the caller's values,
which can be related, so the guarantee doesn't carry over by itself.
`gen/caller_redundancy.py` (driver `caller_redundancy_experiment.py`,
results `results/caller_redundancy.jsonl`) generates libraries like the
ones above, without twins, and tries random executions of operations from
the level below in every operation, with the arguments drawn two ways: like
the generator (any value the caller has, a fifth of them negated), and only
the caller's own read views, all different.

| views, executions | arguments | executions | a result is redundant | constant | equal to an argument | equal to another result | equal to another caller value | executed operation's values redundant |
| ----------------- | --------- | ---------- | --------------------- | -------- | -------------------- | ----------------------- | ----------------------------- | ------------------------------------- |
| 6, 3              | any value | 2,350      | 44%                   | 24%      | 22%                  | 1.1%                    | 1.7%                          | 43%                                   |
| 6, 3              | read views | 2,350     | 2.0%                  | 0        | 0                    | 0                       | 2.0%                          | 3.6%                                  |
| 10, 3             | any value | 2,050      | 28%                   | 19%      | 11%                  | 1.1%                    | 0.5%                          | 27%                                   |
| 10, 3             | read views | 2,050     | 2.0%                  | 0        | 0                    | 0                       | 2.0%                          | 1.8%                                  |
| 10, 4             | any value | 2,300      | 35%                   | 22%      | 13%                  | 2.0%                    | 0.8%                          | 32%                                   |
| 10, 4             | read views | 2,300     | 2.0%                  | 0        | 0                    | 0                       | 2.0%                          | 1.4%                                  |
| 12, 3             | any value | 540        | 26%                   | 18%      | 8.7%                  | 1.3%                    | 0.4%                          | 21%                                   |
| 12, 3             | read views | 540       | 1.7%                  | 0        | 0                    | 0                       | 1.7%                          | 1.4%                                  |

The last column counts all of the executed operation's values, written
views or not, that are constant or equal to one of the caller's values or
an earlier value of the execution: what copying the execution into the
caller would find. The 14-view library didn't fit in the 30-second limit
in Python and was replaced by the 12-view one.

What the earlier check saves:

- **The executed operation's other values are never the caller's
  concern.** DLP 57 asks only about the values the caller's statements
  compute, and an execution's results are the only ones of its values the
  caller has. With references, the check never sees the rest; the recorded
  table or OBDD stands in for them. With copying, they're in the graph, and
  under related arguments 21–43% of them are redundant, which the sweep
  proves at a cost and then ignores (the 40–57 merged nodes per operation in
  [steady_state.md](steady_state.md) are these).
- **With distinct read views as arguments, the results need no check
  against each other, the constants, or the arguments**: they're the
  executed operation's own functions under other names. None of the 7,240
  executions of that kind had such a redundancy. A result can still equal
  another of the caller's values (about 2%), so it still has to be checked
  against those.
- **Each executed operation is checked once**, where it's defined, and what
  it records (its tables, OBDDs, and patterns) is reused by every caller.
  That's what makes the reference methods' cost independent of depth.

What it doesn't save:

- **With related arguments, an execution's results are often redundant in
  the caller**: 26–44% of these executions had at least one, mostly
  constant results (18–24%) or results equal to an argument (9–22%). So the
  caller has to check an execution's results like any of its own values,
  which is what every method here does. These rates are for the generator's
  random choice of arguments; how often real code passes related values is
  unknown.
- **The executed operation's patterns don't carry over.** They're
  assignments of its own read views, which the caller's arguments may never
  produce, so they can't separate the caller's values. Only its recorded
  function is reusable.

## Recommendations

1. **Refer to executions; don't copy them.** Every reference method's cost
   per operation is flat in depth, while copying multiplies by the number of
   executions per level.
2. **For truth tables, a lookup per combination is fine up to about 16
   views** and costs about 13 ms per operation at 20 (the cost of recording a
   2^20-combination table), which is the cost the 20-input limit has to
   absorb. Recording OBDDs is a way around it for wide operations.
3. **For SAT, use the hybrid refinement.** Expanding at the first
   disagreement can degenerate into copying, and one clause per assignment
   can need as many clauses as there are combinations of the executed
   operation's views.
4. **OBDD composition** was the most even method here (about 0.1 ms per
   operation at every depth and width), because the generated functions have
   small OBDDs; it inherits OBDDs' worst cases on other logic.
