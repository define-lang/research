# Exact Matching of Registered Operations

DLP 58 forbids writing out a registered boolean operation instead of
executing it. Today a _match_ is defined over cuts: a value matches a
registered operation R if, over some cut of at most four values, its truth
table equals R's, with the cut's values given to R's views in some order.
Now that redundant values are checked exactly over the whole value
operation, could this rule be exact too: a value is a written-out R if, as a
function of the operation's inputs, it equals R applied to values the
operation already has?

**Short answer:** it can be decided, but it shouldn't be the rule. Exact
matching costs 0.75–2.5 s per 200- to 256-statement value operation (against
2–3 ms for cuts). More importantly, it flags 34–47% of all the values in
operations that DLP 58's cut rule nearly accepts, almost all of them
coincidences.
The cut definition is the defensible one. One cheap extension is worth
adopting: let a cut's value be given to R as its `not` when the program
already has that `not`. The four-view limit is justified by the cost of
enumerating every cut, which grows 7–18 times per added view.

The code is `src/match.hpp` (`beq match`), the workloads `gen/matching.py`,
the driver `matching_experiment.py`, and the results `results/matching.jsonl`
(`summarize.py matching`).

## What Was Compared

Common to every definition, following DLP 58:

- **Values** are the values the caller's own statements compute, never
  values inside an execution.
- **Available values** are the operation's inputs, the values its statements
  compute, and the literals its statements were given (so `not x` is
  available only if the program computes it).
- **An execution of R on the same arguments isn't a match.** A match is a
  group of at least two statements (counting `not` statements), and the
  arguments must be distinct values: views of a logical operation can't
  alias (DLP 55).

The definitions:

| Name            | A value v matches R(a₁, …, aₖ) when                                                                                                                                                                     |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cuts`          | DLP 58: the aᵢ are the values of a cut of v (at most four), and v's table over the cut equals R's in some view order.                                                                                  |
| `cuts_negated`  | Like `cuts`, but a cut value can be given as its `not` if the program has that `not`.                                                                                                                   |
| `cut_values`    | Over a cut of v, the aᵢ can be any available values that are functions of a subset of the cut, and v's table over the cut equals R of their tables.                                                   |
| `exact_cone`    | v equals R(a₁, …, aₖ) as a function of the operation's inputs, every aᵢ is in v's cone, every aᵢ matters, and the aᵢ are reached by the statements between them and v.                                |
| `exact_support` | Like `exact_cone`, but the aᵢ can be any available values whose inputs are among v's.                                                                                                                   |
| `exact_any`     | Like `exact_cone`, but the aᵢ can be any available values. This is the definition the question asks about.                                                                                              |

"Every aᵢ matters" means R's difference with respect to view i, at those
values, is true for some input assignment. Without it, a value with a
correlated argument that does nothing would match a smaller function.

### The Exact Search

The candidate tuples are O(nᵏ) for n available values, so the search is
directed by R:

1. Give values to R's views one at a time. After each one, prune the partial
   assignment if, on some sampled input assignment, no values of the
   remaining views give v's value there (a precomputed reachability table
   for R makes this a few bitwise operations per view).
2. For the last view, its value is forced wherever R depends on it, so the
   candidates are found by a masked scan.
3. Check each candidate exactly on the full truth tables (at most 20 inputs,
   so at most 2^20 bits). A candidate that fails adds the input assignment
   where it failed to the sample.

Pruning on samples only uses necessary conditions, so nothing is missed, and
the final check makes it sound. Interchangeable views are given values in
increasing order, so a symmetric R isn't searched once per view order. The
cost is O(n^(k−1)) partial tuples per value in the worst case, with heavy
pruning in practice.

An earlier version enumerated every minimal set of available values that v
is a function of (minimal hitting sets of pairs of input assignments where v
differs) and compared the function over each with every R. It was 20–40
times slower, because a value is a function of thousands of such sets,
almost none of which are a registered operation's arguments.

## Workloads

`gen/matching.py` generates value operations like Experiment 1's, with the
registered operations `or`, `xor`, `eq`, `implies`, `mux`, and `maj`
(two and three views), executed as statements, and `and`, `and3`, `or3`
unregistered. Registered operations are never given negated values, which
would usually be a match of another one (`or(not a, b)` is `implies(a, b)`),
so the operations are close to passing DLP 58's cut rule. Redundant
statements are rejected. With probability 0.15, a step plants a written-out
registered operation on available values:

- `local`: another way of writing R directly on its arguments. Cuts see it.
- `sop`: R written as an irredundant sum of products over the inputs of its
  arguments' cones, so a composite argument that the operation already has
  is never computed again. Cuts see only the inputs.

A third kind, a case split `(c and R(args)) or (not c and R(args))` on an
unrelated value, was generated and always rejected: its two sides are equal
values, so it's a redundant value, which DLP 58 reports first. That kind of
hidden match can't exist in a value operation that compiles.

Five operations each of 8 and 12 inputs with 64 statements, 12 inputs with
200, and 16 and 20 inputs with 256: 162 `local` and 11 `sop` plants.

## Results

Median time per operation, and values flagged that weren't planted (mean per
operation, of its statement values):

| size | cuts | cuts_negated | cut_values | exact_cone | exact_support | exact_any |
| ---- | ---- | ------------ | ---------- | ---------- | ------------- | --------- |
| 8 inputs, 64 statements | 501 µs, 2.2 of 74 | 897 µs, 2.4 of 74 | 2.79 ms, 48.2 of 74 | 20.1 ms, 17.6 of 74 | 43 ms, 31.4 of 74 | 47.3 ms, 34.6 of 74 |
| 12 inputs, 64 statements | 463 µs, 1.6 of 73 | 938 µs, 1.6 of 73 | 2.72 ms, 42.8 of 73 | 15.3 ms, 11.8 of 73 | 26.2 ms, 23.2 of 73 | 40.3 ms, 25.6 of 73 |
| 12 inputs, 200 statements | 1.72 ms, 6.8 of 220 | 2.29 ms, 7.6 of 220 | 9.79 ms, 130.8 of 220 | 357 ms, 40.4 of 220 | 577 ms, 77.8 of 220 | 753 ms, 81.8 of 220 |
| 16 inputs, 256 statements | 2.26 ms, 9.0 of 282 | 3.97 ms, 9.8 of 282 | 15.3 ms, 172.4 of 282 | 876 ms, 47.8 of 282 | 1.1 s, 91.4 of 282 | 1.73 s, 96.4 of 282 |
| 20 inputs, 256 statements | 2.74 ms, 9.8 of 283 | 4.83 ms, 10.0 of 283 | 21.6 ms, 171.2 of 283 | 5.87 s, 44.2 of 283 | 1.96 s, 93.6 of 283 | 2.53 s, 97.8 of 283 |

Each cell is the median time, then the mean number of values flagged that
weren't planted, of the mean number of values per operation. Times are of
single runs, alongside other runs; the two cut methods, timed against each
other at the best of five runs, take 42 ms and 59 ms for all 25 operations.

Planted matches found:

| Method          | `local`   | `sop`  |
| --------------- | --------- | ------ |
| `cuts`          | 156/162   | 0/11   |
| `cuts_negated`  | 162/162   | 0/11   |
| `cut_values`    | 162/162   | 4/11   |
| `exact_cone`    | 155/162   | 0/11   |
| `exact_support` | 162/162   | 8/11   |
| `exact_any`     | 162/162   | 9/11   |

The six `local` plants that `cuts` misses are written out using a value x
where R needs `not x`, which the program also has (for example `maj(425,
504, 364)` where 425 is `not 424`, and the written-out logic reads 424). The
cut's table is then R with one view negated, which isn't R. `cuts_negated`
finds all six, flags 10 more values in all 25 operations than `cuts` does
(157 against 147), and takes about 40% longer (59 ms against 42 ms for all 25).
`exact_cone` misses seven, most likely because its arguments must be literals
its cone reads, while the comparison identifies an argument by its function
and picks the first literal with that function, which can be elsewhere (this
was confirmed for one of them). The two `sop` plants that `exact_any` misses
weren't investigated.

### What the exact definition flags

The fully exact definition (`exact_any`) flags 26–98 values per operation,
on average, that weren't planted: 34–47% of all the values in operations
that are nearly free of cut matches. They're coincidences. Examples:

- `nor(x, y)` where x and y can never both be true "is" `eq(x, y)`.
- `and3(a, b, c)` where `b` implies `c` "is" `mux(b, a, b)`, among many
  other `mux` and `maj` expressions over values correlated with v.
- A value built from values whose functions overlap "is" `implies` of two
  of them.

With a couple of hundred values available, R applied to some of them covers
so many functions that a value built from correlated values often equals
one of them. Reporting those as matches would make programmers rewrite
perfectly ordinary logic into an execution that isn't any simpler, and
`cut_values`, which restricts the arguments to functions of the cut's
values, is even worse (43–172 coincidental values per operation), because
over at most four values there are only 65,536 functions in all.

The only thing the exact definitions add that's a real written-out
operation is `sop`: R computed from the inputs under an argument that the
operation has but doesn't use. `exact_support` finds 8 of 11 at
0.03–2 s per operation, but only together with dozens of coincidences.

### The arity limit

On one operation of each of the three largest sizes (12 inputs and 200
statements, 16 and 256, 20 and 256), with four extra random registered
operations of arity k and cuts of up to k values:

| k | cuts, time (best of five)       | cuts enumerated      | exact (`exact_cone`)                       |
| - | ------------------------------- | -------------------- | ------------------------------------------ |
| 3 |                                 |                      | 0.36–5.9 s (the table above)               |
| 4 | 1.8 ms, 3.1 ms, 2.1 ms          | 1,625, 3,043, 2,138  | 30 s, 421 s, 298 s                         |
| 5 | 13 ms, 28 ms, 14 ms             | 3,435, 7,497, 4,480  | more than 30 minutes on the first          |
| 6 | 168 ms, 511 ms, 161 ms          | 8,164, 20,238, 9,874 | not run                                    |

The cut timings are `results/matching_arity_cuts.jsonl`, measured alone;
the exact runs are in `results/matching.jsonl`. They ran before the
30-second limit per check that's the rule now, alongside other runs, and
are only meant to show the growth.

DLP 58 needs every match, so every cut has to be enumerated. The number of
cuts grows 2–3 times per added view and the time 7–18 times (each cut is
also compared in every view order, k! of them), so four views costs 2–3 ms
per operation, five 13–28 ms, and six 0.16–0.51 s. The exact search grows
about 100 times per added view and doesn't finish five within 30 minutes.
So the four-view limit is justified by cost: it keeps finding every match
at about the cost of the redundant-value check itself, five would still be
affordable at about 30 ms, and six would be the most expensive check in the
compiler.

## Which Match to Report

DLP 58 reports the largest match, then the one whose last statement comes
first. With the cut definition, a match is determined by the program text
alone (its statements and the registered operations), so this order is
deterministic and doesn't depend on any solver. To make it total: the size
of a match is the number of statements between its arguments and its value
(counting `not` statements); ties go to the value that comes first; then to
the registered operation's name; then to the arguments in DLP 58's rank
order. Every step compares things the program states, so every compiler
reports the same match.

## Recommendations

1. **Keep matches defined over cuts.** The exact definition is decidable,
   but it would reject a large fraction of ordinary code as written-out
   operations. Exactness matters for redundant values, where an equal
   value is unambiguous; for matches, the structure is what says that the
   programmer wrote an operation out.
2. **Let a cut's value be given to R as its `not`** when the program has
   that value. It finds the written-out operations that use x where R needs
   `not x` (4% of the planted ones), with few extra matches.
3. **Keep the limit of four read views** for registered operations: every
   added view multiplies the cost of finding every match by 7–18.
4. **Order overlapping matches** by size, then by value, then by operation
   name, then by argument rank.

## What's Measured and What's Argued

Measured: everything in the tables, on generated workloads, with the
registered operations listed above. Argued: that the flagged values are
coincidences rather than written-out operations (from inspecting examples,
not from all of them), and that the same holds for real code and other
registered sets.
