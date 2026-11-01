# Experiments

Every number here comes from `results/*.jsonl`, produced by
`run_everything.sh` and `cadical_adversarial.sh`, and summarized by
`summarize.py` (whose full output is in `results/*_tables.md`). The arguments
that go with these results are in [arguments.md](arguments.md).

## Setup

### Machine

AMD Ryzen 9 9950X (16 cores, 32 threads), 60 GB of memory, Fedora with Linux
7.2, GCC 16.2.1 with `-O2 -march=native`. Other work was running on the
machine at the same time (load average 7 to 9), and the per-operation
experiments ran six instances in parallel, so times have some noise: treat
differences smaller than about 1.5× as ties. Programs ran one at a time.
Small instances were timed as the fastest of five repetitions (three for the
adversarial ones).

Memory is the peak resident size above what the process had after reading
its graph. (The raw `peak_rss_kb` includes memory inherited from the Python
driver at `fork`, so it's only meaningful as a difference.)

### Methods

All methods are in `src/` and run on an AIGER file. Each reports its classes
through the same union-find with a phase bit, so a class can hold a node, the
complement of another node, a constant, or an input. "Redundant nodes" are
the nodes whose class has an earlier member.

| Name                  | What it is                                                                                                                                                                                                                                         | Exact? |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| `strash`              | Structural hashing with the trivial rules (`a and a`, `a and not a`, constants).                                                                                                                                                                   | No     |
| `norm_single`         | The normalized AND-of-literal-sets form from the background survey, hash-consed, flattening only inputs with one user.                                                                                                                             | No     |
| `norm_all`            | The same form, flattening through every non-inverted `and`.                                                                                                                                                                                       | No     |
| `cuts4`               | DLP 57's redundant-value rule: every cut of at most four values, with no pruning, and a 16-bit truth table for each; a node is redundant when, over one of its cuts, it's constant, equals a cut value, or equals an earlier node over that cut. | No     |
| `tt`                  | Truth tables over every input, 2^I bits per node, freed after the last use except for one per class.                                                                                                                                              | Yes    |
| `bdd_first_use`       | A shared reduced OBDD with complement edges, inputs ordered by first use in statement order.                                                                                                                                                      | Yes    |
| `bdd_natural`         | The same OBDD with inputs in their numbered order.                                                                                                                                                                                                | Yes    |
| `sweep`               | SAT sweeping (fraiging): 1,024 random patterns, then nodes in topological order checked against candidates with the same simulation signature, merged into a reduced graph when proved equal; counterexamples become new patterns. One incremental solver, branching only on the cones of the two nodes compared (when they have at most 4,096 nodes), replaced by a new one past 100,000 variables (then past four times what its first question needs). | Yes    |
| `sweep_unscoped`      | `sweep` letting the solver branch on any variable.                                                                                                                                                                                                 | Yes    |
| `sweep_recycling`     | `sweep` starting a new solver past 300 variables; used only to check that recycling doesn't change answers.                                                                                                                                       | Yes    |
| `sweep_exhaustive`    | `sweep`, but a pair whose cones read at most 12 inputs is decided by simulating every assignment of them.                                                                                                                                          | Yes    |
| `sweep_bdd_rescue`    | `sweep`, but a SAT call that reaches 1,000 conflicts is retried with OBDDs of the two cones (first-use order, up to 4M nodes), then with SAT without a limit.                                                                                       | Yes    |
| `portfolio`           | `sweep_exhaustive` and `sweep_bdd_rescue` together, with no dispatch.                                                                                                                                                                              | Yes    |
| `auto`                | The combined algorithm of [algorithm.md](algorithm.md): truth tables up to 12 inputs, otherwise `portfolio` with a truth-table switch at up to 20 inputs.                                                                                          | Yes    |
| `auto_kissat`         | `auto` with Kissat 4.0.4 as the last step for a pair.                                                                                                                                                                                              | Yes    |

The SAT solver is `src/sat.hpp`, a MiniSat-style CDCL solver written for this
(two watched literals, VSIDS, first-UIP learning with recursive minimization,
phase saving, Luby restarts, LBD-based clause deletion, incremental solving
under assumptions). The standard tools are compared with it: ABC (the YosysHQ
fork, "UC Berkeley, ABC 1.01") in Experiment 7, native CaDiCaL 2.2.1 and
Kissat 4.0.4 in Experiment 8, and CaDiCaL 1.9.5 through `python-sat` in
Experiment 3, which was run before the native solvers were installed.

Every exact method runs to completion; nothing has a conflict limit unless an
experiment says so.

### Correctness

`check_methods.py` generated 300 random small instances across all the
families (value operations, tangles, parity, multipliers, hidden weighted bit) and ran
every method on each, with the sweepers given only 64 random patterns so that
counterexample handling gets exercised. All eleven exact configurations
(including `auto`, and `auto` forced through its truth-table switch) gave
identical classes on all 300, and every merge made by the four inexact
methods held in those classes (`results/check_methods.txt`:
`instances=300 disagreements=0`). `gen/verify.py` also checks a method's
classes on any instance with CaDiCaL: every claimed equality is proved, and
every pair of distinct classes that agree on 4,096 random patterns is proved
different. It passed on a 16,735-node program used while developing.

### Workloads

All generators are in `gen/workloads.py` and write AIGER files with a list of
_planted_ pairs: two literals that are equal by construction.

- **Value operations** (`value_operation`) imitate DLP 57's boolean
  statements. Inputs stand for comparisons and interface views. Each
  statement calls `and`, `or`, `implies`, exclusive or, equality, a
  multiplexer, majority, or a three-way `and` or `or`, weighted the way
  conditions are usually written (mostly `and` and `or`), on values from the
  last eight statements and on inputs, preferring inputs not read yet. A
  quarter of the arguments are negated. Every composition has two to four
  equivalent ways of writing it (for example four ways to write exclusive
  or), and each call picks one at random. Statements are emitted in DLP 57's
  statement order (each value right before the statement that first needs
  it). The generator rejects any statement whose value is constant, equal
  to an input, or equal to an earlier value on 256 random patterns, so the
  operations are ones DLP 57 would accept apart from the planted violations.
  With probability 0.08, a step plants one instead:
  - `duplicate`: the same call on the same values again.
  - `shallow`: the same call written a different way.
  - `deep`: a whole earlier value rewritten, with every call in its cone
    written a different way.
  - `shannon`: a value written as a case split on one of its inputs, with
    both cofactors rewritten.
  - `absorb`: `v and (w or u)`, where `w` is a rewritten copy of `v`.
  - `absorb_input`: `x and (x or v)` for an input `x`.
  - `contradiction`: `v and not w`, where `w` is a rewritten copy of `v`.
- **Tangles**: value operations whose statements read values from anywhere
  earlier, so many values stay live.
- **Parity**: the parity of n inputs as a chain in input order, as a
  balanced tree, and as a chain in a random order, each exclusive or written
  a random way.
- **Multipliers**: an n-bit array multiplier against the same design with
  its operands swapped (`commuted`), or against one using parallel-prefix
  adders (`kogge`). Every product bit is planted.
- **Hidden weighted bit**: the `k`-th input, where `k` counts the true
  inputs (false when none are), written
  as a multiplexer tree on a ripple counter and as an `or` of "count equals
  k and the `k`-th input" on a tree counter. Every OBDD for it is exponential under
  every order (Bryant 1991, from memory).
- **Comparators**: ten n-bit `x < y` and `x + y` on bits drawn from a shared
  pool, each written two ways (ripple and most-significant-first for `<`,
  ripple and Kogge–Stone for `+`).
- **Programs** (`program`): a library of 200 value operations (3 to 10
  inputs, 6 to 40 statements, 1 to 3 outputs, each written three equivalent
  ways), executed with every call inlined. Arguments are recent values and
  fresh comparisons. Popularity follows 1/k, so a few operations are called
  most of the time. 2% of calls repeat an earlier call's operation and
  arguments exactly (`call_repeat`), and 2% repeat it written a different way
  (`call_rewrite`). Calls whose outputs look redundant on 64 random patterns
  are dropped, the way DLP 57 would reject them. Two shapes: one long
  dataflow, where any call can read the last 64 values, and _regions_ of 50
  calls, like separate actions, where a call reads only values of its own
  region and half of its comparisons are shared with the rest of the program.

## Experiment 1: Realistic Value Operations

220 value operations: 4 to 128 inputs, 16 to 1,024 statements, five of each.
DLP 57 allows at most 256 boolean statements, so the 1,024-statement ones show
what happens past that limit.

### What each method finds

| Method          | Planted pairs found, ≤ 256 statements | Planted pairs found, all | Redundant nodes found, all |
| --------------- | ------------------------------------- | ------------------------ | -------------------------- |
| `strash`        | 252/872 (28.9%)                       | 616/2,228 (27.6%)        | 27.3%                      |
| `norm_single`   | 268/872 (30.7%)                       | 675/2,228 (30.3%)        | 31.6%                      |
| `norm_all`      | 294/872 (33.7%)                       | 721/2,228 (32.4%)        | 35.2%                      |
| `cuts4`         | 506/872 (58.0%)                       | 1,243/2,228 (55.8%)      | 43.3%                      |
| every exact one | 872/872                               | 2,228/2,228              | 100%                       |

By kind of planted pair, over all 220 operations:

| Kind            | `strash` | `norm_all` | `cuts4` | exact |
| --------------- | -------- | ---------- | ------- | ----- |
| `duplicate`     | 186/193  | 187/193    | 191/193 | all   |
| `shallow`       | 264/509  | 359/509    | 496/509 | all   |
| `absorb_input`  | 0/190    | 4/190      | 190/190 | all   |
| `deep`          | 110/630  | 139/630    | 188/630 | all   |
| `shannon`       | 20/327   | 27/327     | 91/327  | all   |
| `absorb`        | 1/177    | 4/177      | 26/177  | all   |
| `contradiction` | 35/202   | 1/202      | 61/202  | all   |

(`norm_all` finds fewer contradictions than `strash` because flattening
merges `v`'s and `w`'s structure into different sets.)

DLP 57's cuts find what's local: a call written another way, a duplicate,
an absorption by an input. They miss most of what the proposal calls
"writing the same logic twice" when it's written over more than four
values: 70% of whole-cone rewrites, 72% of case splits, 85% of absorptions
of a rewritten value, and 70% of contradictions with a rewritten value. The
structural forms find even less.

### Time

Median and slowest of five, for 16, 256 (DLP 57's limit), and 1,024
statements. "—" means the method can't run (truth tables past 24 inputs).

16 statements:

| Inputs | `and` nodes | Width | `strash` | `norm_all` | `cuts4` | `tt` | `bdd_first_use` | `sweep` | `portfolio` |
| ------ | ----------- | ----- | -------- | ---------- | ------- | ---- | --------------- | ------- | ----------- |
| 4 | 31 | 9 | 0.17 µs / 0.2 µs | 1.54 µs / 3.72 µs | 64.1 µs / 353 µs | 2.01 µs / 3.3 µs | 5.69 µs / 6.23 µs | 12.4 µs / 17.1 µs | 7.58 µs / 11.9 µs |
| 8 | 34 | 11 | 0.19 µs / 0.21 µs | 1.87 µs / 3.06 µs | 25.6 µs / 344 µs | 3.64 µs / 4.04 µs | 6.68 µs / 7.04 µs | 10.5 µs / 16.2 µs | 8.82 µs / 13.6 µs |
| 12 | 34 | 8 | 0.18 µs / 0.24 µs | 2.34 µs / 2.6 µs | 56.6 µs / 57.9 µs | 11.9 µs / 13.2 µs | 6.71 µs / 15 µs | 11.5 µs / 13.4 µs | 8.16 µs / 8.77 µs |
| 16 | 35 | 8 | 0.19 µs / 0.19 µs | 2.42 µs / 2.98 µs | 28.3 µs / 66.5 µs | 183 µs / 192 µs | 7.26 µs / 9.79 µs | 13.1 µs / 16.3 µs | 7.95 µs / 12.9 µs |
| 20 | 36 | 8 | 0.19 µs / 0.2 µs | 2.37 µs / 2.99 µs | 52 µs / 129 µs | 3.58 ms / 3.74 ms | 7.91 µs / 8.5 µs | 11.9 µs / 17.6 µs | 9.33 µs / 14.1 µs |
| 24 | 35 | 10 | 0.2 µs / 0.25 µs | 2.6 µs / 3.15 µs | 47.7 µs / 141 µs | 75.1 ms / 83.1 ms | 7.69 µs / 8.99 µs | 13.6 µs / 24.2 µs | 11.8 µs / 25.7 µs |
| 32 | 26 | 8 | 0.2 µs / 0.27 µs | 1.32 µs / 2.81 µs | 15.7 µs / 81.1 µs | — | 6.4 µs / 8.5 µs | 9.45 µs / 11.1 µs | 8.14 µs / 11.1 µs |
| 48 | 33 | 9 | 0.2 µs / 0.26 µs | 1.95 µs / 3.3 µs | 46.8 µs / 169 µs | — | 9.02 µs / 10.1 µs | 11 µs / 14.6 µs | 8.69 µs / 14.1 µs |
| 64 | 35 | 10 | 0.19 µs / 0.22 µs | 1.98 µs / 2.41 µs | 26.4 µs / 57.8 µs | — | 8.45 µs / 8.91 µs | 14.4 µs / 18.1 µs | 12.1 µs / 13.9 µs |
| 96 | 33 | 8 | 0.19 µs / 0.28 µs | 2.17 µs / 2.84 µs | 37.8 µs / 79.8 µs | — | 9.45 µs / 11.7 µs | 16.3 µs / 24.9 µs | 13.9 µs / 16.7 µs |
| 128 | 30 | 9 | 0.21 µs / 0.24 µs | 2.08 µs / 3.08 µs | 49.1 µs / 165 µs | — | 9.24 µs / 13 µs | 21 µs / 24.2 µs | 17.6 µs / 26 µs |

256 statements:

| Inputs | `and` nodes | Width | `strash` | `norm_all` | `cuts4` | `tt` | `bdd_first_use` | `sweep` | `portfolio` |
| ------ | ----------- | ----- | -------- | ---------- | ------- | ---- | --------------- | ------- | ----------- |
| 4 | 542 | 21 | 2.36 µs / 3.53 µs | 29.8 µs / 37.4 µs | 2.23 ms / 2.41 ms | 24 µs / 27.1 µs | 17.5 µs / 20.7 µs | 679 µs / 742 µs | 378 µs / 612 µs |
| 8 | 523 | 24 | 2.55 µs / 3.36 µs | 33.9 µs / 55.7 µs | 1.4 ms / 2.31 ms | 32.4 µs / 46.8 µs | 34.1 µs / 64.5 µs | 377 µs / 709 µs | 378 µs / 865 µs |
| 12 | 530 | 26 | 2.21 µs / 2.64 µs | 32.5 µs / 34.9 µs | 1.22 ms / 1.88 ms | 132 µs / 160 µs | 57.8 µs / 96.1 µs | 258 µs / 401 µs | 319 µs / 408 µs |
| 16 | 571 | 30 | 2.48 µs / 2.65 µs | 34.1 µs / 38.2 µs | 1.43 ms / 1.86 ms | 1.87 ms / 1.96 ms | 167 µs / 196 µs | 248 µs / 453 µs | 315 µs / 477 µs |
| 20 | 509 | 35 | 2.21 µs / 4.25 µs | 31.9 µs / 66.4 µs | 1.21 ms / 3.08 ms | 30.2 ms / 51.5 ms | 242 µs / 1.17 ms | 262 µs / 982 µs | 308 µs / 995 µs |
| 24 | 572 | 38 | 2.44 µs / 2.87 µs | 36.6 µs / 42.1 µs | 1.71 ms / 2.04 ms | 539 ms / 662 ms | 314 µs / 616 µs | 258 µs / 327 µs | 266 µs / 366 µs |
| 32 | 567 | 46 | 2.49 µs / 3.06 µs | 34.1 µs / 36.7 µs | 1.12 ms / 1.22 ms | — | 619 µs / 1.34 ms | 306 µs / 688 µs | 318 µs / 680 µs |
| 48 | 509 | 51 | 2.23 µs / 2.78 µs | 30.5 µs / 37.2 µs | 1.09 ms / 1.39 ms | — | 318 µs / 1.87 ms | 224 µs / 773 µs | 234 µs / 717 µs |
| 64 | 568 | 65 | 2.32 µs / 2.95 µs | 34.5 µs / 46.1 µs | 1.21 ms / 1.61 ms | — | 3.82 ms / 79.4 ms | 311 µs / 340 µs | 358 µs / 467 µs |
| 96 | 539 | 63 | 2.58 µs / 3.63 µs | 34.5 µs / 43.1 µs | 1.27 ms / 1.5 ms | — | 976 µs / 23.1 ms | 231 µs / 468 µs | 301 µs / 491 µs |
| 128 | 532 | 50 | 2.24 µs / 2.76 µs | 32.5 µs / 35 µs | 1.24 ms / 1.57 ms | — | 1.32 ms / 3.63 ms | 308 µs / 466 µs | 278 µs / 492 µs |

1,024 statements:

| Inputs | `and` nodes | Width | `strash` | `norm_all` | `cuts4` | `tt` | `bdd_first_use` | `sweep` | `portfolio` |
| ------ | ----------- | ----- | -------- | ---------- | ------- | ---- | --------------- | ------- | ----------- |
| 4 | 2113 | 41 | 9.66 µs / 11.2 µs | 139 µs / 158 µs | 28.2 ms / 45.5 ms | 76.6 µs / 78.8 µs | 45.8 µs / 51.9 µs | 4.95 ms / 8.76 ms | 2.17 ms / 2.68 ms |
| 8 | 2350 | 38 | 10.2 µs / 11 µs | 146 µs / 168 µs | 6.65 ms / 7.21 ms | 117 µs / 131 µs | 204 µs / 248 µs | 2.22 ms / 3.06 ms | 3.31 ms / 3.75 ms |
| 12 | 2094 | 37 | 9.48 µs / 10.3 µs | 143 µs / 150 µs | 5.65 ms / 6.4 ms | 519 µs / 532 µs | 360 µs / 436 µs | 1.59 ms / 2.95 ms | 2.35 ms / 3.06 ms |
| 16 | 2087 | 40 | 9.73 µs / 9.96 µs | 139 µs / 164 µs | 5.19 ms / 5.84 ms | 6.82 ms / 7.57 ms | 913 µs / 2.09 ms | 2.7 ms / 7.09 ms | 2.52 ms / 7.19 ms |
| 20 | 2164 | 48 | 9.69 µs / 10.1 µs | 149 µs / 163 µs | 4.5 ms / 5.53 ms | 114 ms / 122 ms | 1.32 ms / 1.56 ms | 1.41 ms / 2.38 ms | 1.34 ms / 2.2 ms |
| 24 | 2167 | 50 | 10 µs / 10.5 µs | 147 µs / 153 µs | 5.22 ms / 6.56 ms | 2.04 s / 2.25 s | 2.79 ms / 8.5 ms | 2.15 ms / 2.53 ms | 2.14 ms / 2.71 ms |
| 32 | 2123 | 57 | 9.84 µs / 10.3 µs | 146 µs / 149 µs | 5.69 ms / 6.29 ms | — | 8.21 ms / 28.3 ms | 3 ms / 3.37 ms | 3.1 ms / 3.86 ms |
| 48 | 2140 | 75 | 9.9 µs / 11.7 µs | 145 µs / 167 µs | 4.45 ms / 5.14 ms | — | 173 ms / 234 ms | 2.18 ms / 8.4 ms | 2.32 ms / 7.56 ms |
| 64 | 2169 | 82 | 10.1 µs / 11.3 µs | 152 µs / 164 µs | 6.46 ms / 8.33 ms | — | 161 ms / 732 ms | 3.5 ms / 6.53 ms | 2.56 ms / 5.91 ms |
| 96 | 2165 | 107 | 9.74 µs / 10.5 µs | 156 µs / 165 µs | 5.21 ms / 6.17 ms | — | 237 ms / 2.19 s (1 fails) | 3.11 ms / 6.16 ms | 2.95 ms / 6.36 ms |
| 128 | 2097 | 122 | 9.26 µs / 10.5 µs | 143 µs / 144 µs | 5.08 ms / 5.73 ms | — | 1.26 s / 10.7 s | 1.13 ms / 1.45 ms | 1.32 ms / 1.76 ms |

(The OBDD that fails reached the 30M-node limit.)

- **Exact checking is cheap for this kind of logic.** Within DLP 57's limit,
  the portfolio's slowest run of 165 operations was 1.0 ms, and its median
  55 µs. Even at 1,024 statements the slowest was 7.6 ms.
- **DLP 57's cuts are slower than exact checking** past a few dozen
  statements: 1–3 ms at 256 statements against 0.3 ms for the portfolio,
  because enumerating every cut with no pruning gives hundreds of cuts per
  node.
- **Truth tables** are the fastest exact method up to about 12 inputs and
  unusable past 20: 0.5 s and 700 MB at 24 inputs and 256 statements, 2 s and
  1.9 GB at 1,024.
- **OBDDs in first-use order** are the fastest exact method for small
  operations (6–9 µs at 16 statements), and fast up to 32 inputs, but they
  grow with inputs and statements: a median of 1.3 s and up to 1 GB at 128 inputs
  and 1,024 statements, and one failure. `bdd_natural` is much worse (2.8 s
  median at 128 inputs and 256 statements, three failures at 1,024), so the
  first-use order the draft proposes is the right one when OBDDs are used.
- **SAT sweeping** stays between 0.2 and 1 ms at 256 statements for every
  input count, because nearly every candidate pair it sees is really equal
  (simulation separates the rest), and those are easy for SAT.

### Width and OBDD size

From the first operation of each size (`results/operations_tables.md` has all
of them):

| Inputs | Statements | `and` nodes | Width | OBDD nodes | Widest level |
| ------ | ---------- | ----------- | ----- | ---------- | ------------ |
| 16     | 256        | 489         | 37    | 3,688      | 460          |
| 24     | 256        | 572         | 38    | 6,359      | 807          |
| 64     | 256        | 630         | 65    | 76,348     | 7,470        |
| 128    | 256        | 505         | 49    | 34,746     | 2,401        |
| 24     | 1,024      | 2,109       | 50    | 44,132     | 4,496        |
| 64     | 1,024      | 2,169       | 87    | 830,828    | 117,953      |
| 128    | 1,024      | 2,122       | 133   | 488,248    | 29,301       |

Over all operations, the width is 4–15 (median 9) at 16 statements, 12–32
(21) at 64, 17–74 (38) at 256, and 32–133 (52) at 1,024. The bound 2^w per
level is between 2^17 and 2^133 where the real widest level is hundreds of
nodes to about a hundred thousand. So the draft's bound holds but says nothing useful here,
and a limit k small enough to keep 2^k manageable (say 16) would put most
operations of 64 statements, and nearly all of 256, above it. Width grows with statements
because a comparison that's read again later stays live from its first use
to its last.

## Experiment 2: Adversarial Cases

Per-instance times (fastest of three); a fraction after a time means only
that many planted pairs were found; "limit" means the method can't run
(truth tables past 24 inputs, or an OBDD past 30M nodes); "timeout" means
more than 120 s. Tangles (statements reading from anywhere, widths 64–247)
are omitted here: every exact method that could run finished every one in
under 30 ms
(`results/adversarial_tables.md`).

| Instance          | Inputs | `and` nodes | Width | `cuts4`        | `tt`    | `bdd_first_use` | `sweep` | `sweep_exhaustive` | `sweep_bdd_rescue` | `portfolio` |
| ----------------- | ------ | ----------- | ----- | -------------- | ------- | --------------- | ------- | ------------------ | ------------------ | ----------- |
| parity_i16_c3 | 16 | 180 | 21 | 369 µs 0/3 | 625 µs | 68.1 µs | 9.97 ms | 41.7 ms | 10 ms | 8.22 ms |
| parity_i24_c3 | 24 | 276 | 29 | 559 µs 0/3 | 333 ms | 81 µs | 154 ms | 144 ms | 9.06 ms | 7.85 ms |
| parity_i40_c3 | 40 | 468 | 46 | 954 µs 0/3 | limit | 264 µs | 4.19 s | 5.9 s | 10 ms | 10 ms |
| parity_i48_c3 | 48 | 564 | 54 | 1.16 ms 0/3 | limit | 321 µs | timeout | timeout | 11.6 ms | 10.2 ms |
| parity_i128_c3 | 128 | 1524 | 136 | 3.16 ms 0/3 | limit | 3.54 ms | timeout | timeout | 22.3 ms | 20.6 ms |
| mult_commuted_b6 | 12 | 610 | 44 | 1.34 ms 2/12 | 168 µs | 1.48 ms | 106 ms | 370 µs | 66.5 ms | 372 µs |
| mult_commuted_b8 | 16 | 1166 | 62 | 2.53 ms 2/16 | 3.9 ms | 29.1 ms | 3.54 s | 4.06 s | 246 ms | 220 ms |
| mult_commuted_b9 | 18 | 1510 | 71 | 3.31 ms 2/18 | 21 ms | 153 ms | 23.6 s | 26.1 s | 977 ms | 735 ms |
| mult_commuted_b10 | 20 | 1898 | 80 | 3.92 ms 2/20 | 101 ms | 794 ms | timeout | timeout | 3.75 s | 3.23 s |
| mult_commuted_b11 | 22 | 2330 | 89 | 4.91 ms 2/22 | 461 ms | 3.15 s | timeout | timeout | timeout | timeout |
| mult_commuted_b12 | 24 | 2806 | 98 | 6.72 ms 2/24 | 2.3 s | limit | timeout | timeout | timeout | timeout |
| mult_kogge_b8 | 16 | 1370 | 117 | 3.69 ms 2/16 | 4.46 ms | 30 ms | 4.67 s | 4.22 s | 289 ms | 247 ms |
| mult_kogge_b10 | 20 | 2322 | 178 | 7.06 ms 2/20 | 118 ms | 1.09 s | timeout | timeout | 4.43 s | 3.55 s |
| mult_kogge_b12 | 24 | 3522 | 245 | 10.2 ms 2/24 | 3.01 s | limit | timeout | timeout | timeout | timeout |
| hwb_i24 | 24 | 1007 | 156 | 4.49 ms 0/1 | 1.08 s | 3.44 ms | 22.3 ms | 20.2 ms | 22.2 ms | 19.7 ms |
| hwb_i32 | 32 | 1457 | 191 | 6.21 ms 0/1 | limit | 73.8 ms | 63.6 ms | 74.7 ms | 52.6 ms | 53.4 ms |
| hwb_i40 | 40 | 1972 | 262 | 8.8 ms 0/1 | limit | 1.29 s | 131 ms | 115 ms | 81.3 ms | 79.5 ms |
| cmp_b16_c10 | 64 | 6140 | 211 | 7.35 ms 20/180 | limit | 232 ms | 42.9 ms | 31.2 ms | 45.1 ms | 31.1 ms |
| cmp_b32_c10 | 128 | 13340 | 414 | 19.6 ms 20/340 | limit | limit | 362 ms | 281 ms | 345 ms | 268 ms |
| cmp_b64_c10 | 256 | 28700 | 803 | 43.9 ms 20/660 | limit | limit | 2.25 s | 1.83 s | 2.09 s | 1.83 s |

`strash` and `norm_single` found none of these planted pairs except the two
lowest product bits.

- **Each engine has its own exponential case.** SAT sweeping fails on parity
  in a different order (timeout from 48 inputs), which is known to be hard
  for resolution, while OBDDs decide 128-input parity in 3.5 ms. OBDDs fail
  on hidden weighted bit (1.3 s at 40 inputs, growing about 4× per 4 inputs)
  and on comparators over scattered bits, where SAT takes 63–131 ms and
  0.3–2 s. This is why the portfolio combines them: apart from
  multipliers, it finishes every family above in milliseconds to seconds,
  though it can be 30 to 100 times slower than OBDDs on parity, because it
  spends 1,000 conflicts on SAT before switching.
- **Multipliers defeat everything** that doesn't enumerate: SAT grows about
  6× per bit, OBDDs about 5× per bit, and the portfolio times out from 11
  bits. Truth tables are fastest here because multipliers have few inputs
  (2.3 s at 12 bits, 24 inputs), but they're exponential in the inputs.
- **The OBDD rescue** is what makes the portfolio robust: from 1,000 conflicts
  it switches a hard pair to OBDDs of its cones, which turns parity from a
  timeout into 10 ms and multipliers from timeouts at 10 bits into 3–4 s.
  Exhaustive simulation of small cones helps small multipliers (0.4 ms
  against 106 ms at 6 bits) but nothing else much.

## Experiment 3: CaDiCaL on the Same Pairs

To check that the hard cases are hard for SAT in general and not just for
the solver written here, CaDiCaL 1.9.5 (`python-sat`) decided each planted
pair of the adversarial instances separately, with only the two cones encoded
and no sweeping, four files at a time with 600 s per file. "Ran out" means the
file's remaining pairs weren't decided in that time (`results/cadical_tables.md`):

| instance | pairs decided | ran out of 600 s | slowest pair | all pairs decided | most conflicts |
| -------- | ------------- | ---------------- | ------------ | ----------------- | -------------- |
| hwb_i8 | 1 |  | 3.63 ms | 3.63 ms | 482 |
| hwb_i12 | 1 |  | 16.8 ms | 16.8 ms | 1,722 |
| hwb_i16 | 1 |  | 45 ms | 45 ms | 4,190 |
| hwb_i20 | 1 |  | 80.4 ms | 80.4 ms | 7,173 |
| hwb_i24 | 1 |  | 106 ms | 106 ms | 9,441 |
| hwb_i28 | 1 |  | 151 ms | 151 ms | 12,287 |
| hwb_i32 | 1 |  | 208 ms | 208 ms | 17,525 |
| hwb_i40 | 1 |  | 501 ms | 501 ms | 33,278 |
| mult_commuted_b3 | 6 |  | 142 µs | 421 µs | 42 |
| mult_commuted_b4 | 8 |  | 1.41 ms | 3.97 ms | 225 |
| mult_commuted_b5 | 10 |  | 8.96 ms | 31.7 ms | 978 |
| mult_commuted_b6 | 12 |  | 47 ms | 197 ms | 3,749 |
| mult_commuted_b7 | 14 |  | 175 ms | 761 ms | 14,921 |
| mult_commuted_b8 | 16 |  | 778 ms | 3.05 s | 55,193 |
| mult_commuted_b9 | 18 |  | 3.45 s | 13.8 s | 186,794 |
| mult_commuted_b10 | 20 |  | 17.8 s | 69.3 s | 654,423 |
| mult_commuted_b11 | 22 |  | 112 s | 422 s | 2,848,036 |
| mult_commuted_b12 | 13 | yes | 259 s | 388 s | 6,120,312 |
| mult_kogge_b3 | 6 |  | 138 µs | 435 µs | 39 |
| mult_kogge_b4 | 8 |  | 1.38 ms | 4.32 ms | 228 |
| mult_kogge_b5 | 10 |  | 9.92 ms | 35.3 ms | 1,066 |
| mult_kogge_b6 | 12 |  | 54.6 ms | 236 ms | 4,590 |
| mult_kogge_b7 | 14 |  | 195 ms | 911 ms | 15,359 |
| mult_kogge_b8 | 16 |  | 900 ms | 3.96 s | 58,215 |
| mult_kogge_b9 | 18 |  | 4.45 s | 18.3 s | 223,113 |
| mult_kogge_b10 | 20 |  | 22.5 s | 87 s | 777,606 |
| mult_kogge_b11 | 22 |  | 130 s | 516 s | 3,088,649 |
| mult_kogge_b12 | 13 | yes | 343 s | 498 s | 8,017,820 |
| parity_i8_c3 | 3 |  | 449 µs | 804 µs | 139 |
| parity_i12_c3 | 3 |  | 1.25 ms | 1.99 ms | 372 |
| parity_i16_c3 | 3 |  | 15.8 ms | 24.8 ms | 3,196 |
| parity_i20_c3 | 3 |  | 103 ms | 123 ms | 27,947 |
| parity_i24_c3 | 3 |  | 93.6 ms | 138 ms | 32,332 |
| parity_i28_c3 | 3 |  | 239 ms | 305 ms | 77,712 |
| parity_i32_c3 | 3 |  | 101 ms | 136 ms | 31,346 |
| parity_i40_c3 | 3 |  | 19.9 s | 20.3 s | 3,543,696 |
| parity_i48_c3 | 1 | yes | 768 µs | 768 µs | 317 |
| parity_i64_c3 | 1 | yes | 988 µs | 988 µs | 427 |

- CaDiCaL shows the same growth on parity in a random order (3.5M conflicts
  at 40 inputs, and more than 600 s at 48) and multipliers (about 5× per bit,
  130 s for the hardest product bit at 11 bits, and the middle bits at 12
  bits unfinished after 600 s), so those curves come from CDCL, not from
  this solver. On hidden weighted bit it's easy, as for `sweep`.
- On the same multipliers, CaDiCaL on one pair at a time is about as fast as
  `sweep` on all pairs together (for example 8 bits: 0.8 s for the hardest
  pair, 3 s for all 16, against 3.5 s for `sweep`). So the solver written
  here is within a small factor of CaDiCaL on these, and sweeping (proving the
  low bits first and reusing them) isn't what makes them feasible or not.

## Experiment 4: Checking Each Value Operation Once

DLP 57's rules apply to one value operation at a time, so a compiler checks
each definition once, no matter how many times it's executed. This checks
each of the 200 operations of the program library by itself, with its three
ways of writing it side by side, so the planted pairs are its outputs written
two ways (`results/library_tables.md`):

| method | finished | total time | slowest | planted pairs found |
| ------ | -------- | ---------- | ------- | ------------------- |
| strash | 200/200 | 75.6 µs | 1 µs | 195/748 |
| cuts4 | 200/200 | 46.5 ms | 2.38 ms | 392/748 |
| tt | 200/200 | 928 µs | 21.5 µs | 748/748 |
| bdd_first_use | 200/200 | 1.4 ms | 17.2 µs | 748/748 |
| sweep | 200/200 | 5.23 ms | 119 µs | 748/748 |
| portfolio | 200/200 | 3.83 ms | 114 µs | 748/748 |

All 200 definitions, 15,010 `and` nodes in all, take 0.9 ms with truth
tables, 1.4 ms with OBDDs, and 3.8 ms with the portfolio. The same library
inlined into programs is what Experiment 5 checks.

## Experiment 5: Whole Programs

These are rough figures, relevant only to optional program-wide
optimization: DLP 57 checks one value operation at a time (Experiment 4).
They are single runs that took up to several minutes on one graph, made
before the rule that no check may take more than about 30 seconds, and they
weren't rerun.

Programs from 1,000 to 1,000,000 calls of the 200-operation library, with
every call inlined, in both shapes, run one at a time
(`results/program_tables.md` has every run). Every exact sweep found every
planted pair in every program they finished, and all exact runs of one
program found identical classes. The three exact sweeps of each program ran
back to back, so they saw the same load. "Without recycling" is the same
sweeper run earlier with one solver for the whole program
(`results/preliminary/program_without_recycling.jsonl`). Peak memory
includes about 17 MB inherited from the Python driver.

| Shape         | Calls     | `and` nodes | `strash` (time, planted found) | `norm_single` | `sweep` (time, peak memory) | `auto` (time, peak memory) | `portfolio` | `sweep` without recycling | Redundant nodes |
| ------------- | --------- | ----------- | ------------------------------ | ------------- | --------------------------- | -------------------------- | ----------- | ------------------------- | --------------- |
| one dataflow | 1,000 | 10,267 | 144 µs, 73% | 1.05 ms, 73% | 48.5 ms, 17 MB | 48.3 ms, 17 MB | 47.9 ms | 45.8 ms, 17 MB | 3,617 |
| one dataflow | 4,000 | 34,387 | 438 µs, 73% | 3.83 ms, 73% | 290 ms, 23 MB | 301 ms, 24 MB | 297 ms | 275 ms, 23 MB | 11,315 |
| one dataflow | 16,000 | 146,197 | 2.55 ms, 72% | 18.1 ms, 74% | 3.6 s, 75 MB | 3.23 s, 78 MB | 4.08 s | 4.16 s, 88 MB | 48,243 |
| one dataflow | 64,000 | 560,594 | 17.8 ms, 71% | 118 ms, 73% | 31.9 s, 274 MB | 36 s, 284 MB | 33.9 s | 48.7 s, 357 MB | 186,137 |
| one dataflow | 256,000 | 2,190,421 | 119 ms, 70% | 1.05 s, 72% | 398 s, 1 GB | 393 s, 996 MB | 385 s | 550 s, 1.2 GB | 729,130 |
| one dataflow | 1,000,000 | 8,259,997 | 458 ms, 71% | 4.38 s, 73% | not run | not run | not run | not run |  |
| regions of 50 | 1,000 | 6,961 | 102 µs, 74% | 665 µs, 77% | 12 ms, 17 MB | 12.1 ms, 17 MB | 11 ms | 12 ms, 17 MB | 2,602 |
| regions of 50 | 4,000 | 30,158 | 424 µs, 71% | 3.37 ms, 73% | 112 ms, 21 MB | 108 ms, 20 MB | 108 ms | 105 ms, 21 MB | 10,475 |
| regions of 50 | 16,000 | 119,428 | 1.89 ms, 72% | 15.5 ms, 73% | 1.04 s, 70 MB | 1.02 s, 70 MB | 1.02 s | 1.15 s, 74 MB | 41,842 |
| regions of 50 | 64,000 | 478,430 | 15.7 ms, 72% | 142 ms, 74% | 4.81 s, 158 MB | 5.23 s, 165 MB | 6.06 s | 16.6 s, 285 MB | 167,491 |
| regions of 50 | 256,000 | 1,849,727 | 74.3 ms, 71% | 753 ms, 73% | 22.7 s, 390 MB | 22.1 s, 420 MB | 22 s | 334 s, 994 MB | 654,191 |
| regions of 50 | 1,000,000 | 7,018,550 | 358 ms, 71% | 3.92 s, 74% | 138 s, 1.4 GB | 137 s, 1.5 GB | 142 s | not run | 2,468,172 |

- **Structural methods are linear and cheap**: 0.46 s and 600 MB for 8.3M
  nodes with structural hashing, 4.4 s and 1.2 GB with the normalized form.
  They find the 2% of calls that repeat an earlier call exactly, and some of
  the rewritten ones (70–77% of planted pairs in all), but only about 11% of
  the redundant nodes the exact methods find. Most of those are nodes inside
  inlined calls that are constant or equal to something else only because of
  the values a particular call was given.
- **Exact SAT sweeping scales nearly linearly when the program is made of
  separate regions**: 1.0 s at 119K nodes, 4.8 s at 478K, 23 s at 1.8M, and
  138 s and 1.4 GB at 7.0M. The combined algorithm (`auto`) costs the same
  (137 s at 7.0M): on whole programs its extra steps neither help nor hurt. That shape is the realistic one for Define, where
  boolean values flow between the value operations of one action, not through
  the whole program.
- **With one long dataflow, it grows about as n^1.7**: 3.6 s at 146K nodes,
  32 s at 561K, 398 s and 1 GB at 2.2M. There the cones of late values span
  most of the program, so every SAT question is about a large part of it.
- **Solver recycling matters at this scale.** One solver holding the whole
  program makes each call slower as the program grows (334 s instead of 21 s
  for 1.8M nodes in regions). Starting a new solver past 100,000 variables
  fixes that, but on the one-dataflow shape it re-encodes huge cones; the
  rule used (the next threshold is four times what the first question after
  a restart needs) keeps the benefit for regions and still helps the
  one-dataflow shape (398 s against 550 s at 2.2M).
- **Restricting decisions to the compared cones** helps regions (4.8 s
  against 6.0 s at 478K nodes) and the one-dataflow shape at 561K (32 s
  against 39 s), but not at 146K (3.6 s against 2.8 s).
- For comparison, checking each of the 200 operations once by itself
  (Experiment 4) took 1–4 ms in all.

## Experiment 6: Conflict Limits and Seeds

`sweep` with a conflict limit on each SAT call, and the portfolio (no limit)
with three random seeds, on the 55 value operations of 256 statements and the
62 adversarial instances (`results/limits_tables.md`). A pair the solver
gives up on stays unmerged, which is what ABC's fraiging does at a limit.

| options | instances | finished | instances with undecided pairs | undecided pairs | planted pairs missed | total time |
| ------- | --------- | -------- | ------------------------------ | --------------- | -------------------- | ---------- |
| --conflicts 1 | 117 | 117 | 117 | 25508 | 2288 | 2 s |
| --conflicts 10 | 117 | 117 | 68 | 943 | 349 | 2.71 s |
| --conflicts 100 | 117 | 117 | 34 | 368 | 243 | 3.03 s |
| --conflicts 1000 | 117 | 117 | 26 | 204 | 179 | 6.43 s |
| --conflicts 10000 | 117 | 117 | 18 | 138 | 128 | 42 s |
| --seed 1 | 117 | 113 | 0 | 0 | 0 | 492 s |
| --seed 2 | 117 | 113 | 0 | 0 | 0 | 492 s |
| --seed 3 | 117 | 113 | 0 | 0 | 0 | 492 s |

Instances finished with every seed: 113; with differing classes: 0

Undecided pairs by family, as instances affected / undecided pairs:

| Conflict limit | Value operations (55) | Tangles (18) | Parity (12) | Multipliers (20) | Hidden weighted bit (8) | Comparators (4) |
| -------------- | --------------------- | ------------ | ----------- | ---------------- | ----------------------- | --------------- |
| 1              | 55 / 12,575           | 18 / 5,509   | 12 / 119    | 20 / 1,695       | 8 / 1,732               | 4 / 3,878       |
| 10             | 19 / 24               | 5 / 10       | 12 / 100    | 20 / 627         | 8 / 132                 | 4 / 50          |
| 100            | 0                     | 0            | 11 / 70     | 16 / 241         | 6 / 56                  | 1 / 1           |
| 1,000          | 0                     | 0            | 9 / 29      | 14 / 158         | 3 / 17                  | 0               |
| 10,000         | 0                     | 0            | 8 / 24      | 10 / 114         | 0                       | 0               |

- **Realistic operations never need more than about 100 conflicts.** The
  hardest single SAT call in any of the 165 value operations of up to 256
  statements took 93 conflicts (median over operations: 2), and 394 for the
  1,024-statement ones. So for this kind of logic, a limit of a few hundred
  conflicts never changes an answer, but that's an observation about these
  workloads, not a guarantee.
- **On the adversarial cases, the answer depends on the limit**, and which
  pairs are missed moves as the limit moves. That's why a limit can't be the
  language's rule (see [arguments.md](arguments.md)).
- **Seeds don't change anything.** With no limit, all 113 instances that
  finished (the other four are the 11- and 12-bit multipliers) got identical
  classes with all three seeds. The seed changes only the random simulation
  patterns, and so the order in which pairs are proved, never the result.

## Experiment 7: ABC

ABC's equivalence commands on the same instances (`abc_compare.py`,
`results/abc_tables.md`). Each instance becomes a miter with one
`x xor y` output per planted pair (`beq miter`):

- `&fraig`: ABC's current SAT sweeping (default: up to 1M conflicts per
  node, 2,000 sweeping iterations, solver recycled every 500 calls).
- `&fraig -x`: its newer implementation.
- `fraig`: the older one (default: 100 conflicts per node).
- `&cec -m`: combinational equivalence checking of a miter. `-m` proves only
  one output, so for it the miter's outputs are combined into one `or`
  (`beq miter --single 1`); "proved" means every planted pair of the
  instance at once.

A pair counts as found by the `fraig` commands when its output became
constant false in the reduced graph. ABC's own timer has 10 ms resolution,
so the value operations were run five to a process and timed from outside,
subtracting a script that only reads and writes the same files, best of
three. That leaves ABC's fixed cost per call in its times, which matters for
small operations.

Value operations, median over the size's 11 groups of ABC's time per
operation divided by the combined algorithm's (`auto`), with what each
found:

| Statements | `&fraig`             | `&fraig -x`          | `fraig`                    | `&cec -m`               |
| ---------- | -------------------- | -------------------- | -------------------------- | ----------------------- |
| 16         | 38× slower, 59/59    | 158× slower, 59/59   | 10× slower, 59/59          | 73× slower, 55/55 proved |
| 64         | 19×, 218/218         | 150×, 218/218        | 8.8×, 218/218              | 47×, 55/55              |
| 256        | 4.8×, 595/595        | 49×, 595/595         | 3.0×, 595/595              | 24×, 55/55              |
| 1,024      | 2.8×, 1,356/1,356    | 8.6×, 1,356/1,356    | 1.5×, 1,336/1,356          | 7.1×, 55/55             |

The 200 library operations took 0.9 ms in all with `auto`, against 60 ms
with `&fraig`, 31 ms with `fraig`, 0.8 s with `&fraig -x`, and 0.17 s with
`&cec`, all finding everything.

Adversarial instances (time for all pairs; a fraction means only that many
were found; "timeout" means more than 300 s):

| Instance          | `auto`  | `auto_kissat` | `&fraig`         | `&fraig -x`     | `fraig`         | `&cec -m`        |
| ----------------- | ------- | ------------- | ---------------- | --------------- | --------------- | ---------------- |
| parity_i16_c3 | 8.69 ms | 8.76 ms | 17 ms | 50 ms | 1.52 ms, 1/3 | 15.2 ms |
| parity_i48_c3 | 10.5 ms | 10.7 ms | 31.3 s, 1/3 | 92.2 s, 1/3 | 1.86 ms, 0/3 | 1.42 s |
| parity_i128_c3 | 21.9 ms | 20.9 ms | 27.6 s, 1/3 | 93.3 s, 1/3 | 3.68 ms, 0/3 | 1.15 s |
| hwb_i24 | 20.7 ms | 21.1 ms | 27 ms | 73.6 ms | 6.33 ms, 0/1 | 162 ms |
| hwb_i40 | 81.1 ms | 82.2 ms | 341 ms | 601 ms | 10.5 ms, 0/1 | 900 ms |
| mult_commuted_b8 | 222 ms | 223 ms | 2.12 s | 15.1 s | 24.6 ms, 4/16 | 4.97 s |
| mult_commuted_b10 | 3.75 s | 3.9 s | 86.8 s | timeout | 38.6 ms, 4/20 | 224 s |
| mult_commuted_b11 | timeout | 134 s | timeout | timeout | 49.8 ms, 4/22 | timeout |
| mult_commuted_b12 | timeout | 878 s | timeout | timeout | 51 ms, 4/24 | timeout |
| mult_kogge_b8 | 276 ms | 255 ms | 3.53 s | 18.7 s | 25.1 ms, 4/16 | 5.53 s |
| mult_kogge_b10 | 4.81 s | 4.24 s | 153 s, 19/20 | timeout | 41.9 ms, 4/20 | 224 s |
| mult_kogge_b11 | timeout | 156 s | timeout | timeout | 41.6 ms, 4/22 | timeout |
| mult_kogge_b12 | timeout | 1.15e+03 s | timeout | timeout | 50.4 ms, 4/24 | timeout |
| cmp_b8_c10 | 1.19 ms | 1.4 ms | 6.36 ms | 8.56 ms | 4.62 ms | 9.31 ms |
| cmp_b16_c10 | 30.8 ms | 31.9 ms | 32.4 ms | 13.5 ms | 16.8 ms | 26.8 ms |
| cmp_b32_c10 | 283 ms | 270 ms | 306 ms | 41.9 ms | 70.3 ms | 114 ms |
| cmp_b64_c10 | 1.82 s | 1.77 s | 1.66 s | 118 ms | 327 ms | 483 ms |
| tangle_i64_s1024_0 | 1.7 ms | 1.89 ms | 3.36 ms | 11 ms | 2.46 ms | 7.17 ms |

- **On realistic value operations, the combined algorithm is faster than
  every ABC command and finds the same pairs.** The gap is 3–5× at 256
  statements and narrows with size (1.5–2.8× at 1,024, where ABC's fixed
  cost per call matters less). The old `fraig` misses pairs at 1,024
  statements because of its conflict limit.
- **ABC's newer `&fraig -x` is the fastest of all on comparators** (118 ms for
  the 64-bit ones against 1.8 s for `auto`), the one family where the
  combined algorithm loses clearly.
- **Neither SAT sweeping in ABC handles parity in a different order**:
  `&fraig` and `&fraig -x` leave two of the three pairs undecided at 48 and
  128 inputs, while `&cec` proves them (1.4 s and 1.2 s), and `auto` decides
  them in 11–22 ms through its OBDD step.
- **Multipliers**: `&cec` proves the 10-bit ones in 224 s and nothing past
  that within 300 s; `auto` takes 4–5 s at 10 bits, and with Kissat as its
  last step it finishes 11 bits in 134–156 s and 12 bits in 878–1,150 s.

Whole programs (Experiment 5's), with every call copied in. These are
rough figures: each was one run, alongside other runs, before the 30-second
limit per check that's the rule now, and they matter only for optional
program-wide optimization, which DLP 57 doesn't need. ABC had 1,800 s and,
for the last runs, 16 GB; "out of memory" means it crashed at that limit.

| Program                    | `and` nodes | `auto` | `&fraig` | `&fraig -x` | `fraig`  | `&cec -m`     |
| -------------------------- | ----------- | ------ | -------- | ----------- | -------- | ------------- |
| regions of 50, 64,000 calls | 478K       | 5.2 s  | 1.8 s    | 0.41 s      | 11.7 s   | 9.3 s         |
| regions, 256,000 calls     | 1.85M       | 22 s   | 10.9 s   | 2.7 s       | 194 s    | 52 s          |
| regions, 1,000,000 calls   | 7.0M        | 137 s  | 70 s     | 12.1 s      | timeout  | out of memory |
| one dataflow, 64,000 calls | 561K        | 36 s   | 324 s    | 40 s        | 526 s    | 132 s         |
| one dataflow, 256,000 calls | 2.2M       | 393 s  | timeout  | 661 s       | timeout  | out of memory |

- **`&fraig -x` is the fastest program-wide engine on programs made of
  regions**, 8–11 times faster than `auto` (12 s against 137 s at 7M
  nodes), and every command that finished found every planted pair.
- **On one long dataflow it loses that lead**: about the same as `auto` at
  561K nodes and 1.7 times slower at 2.2M, where `&fraig` and `fraig` don't
  finish in 30 minutes.
- **`&cec` runs out of memory** on the two largest programs (it had used
  19 GB at 561K nodes before the limit was added).

So if the compiler ever does program-wide optimization by SAT sweeping,
ABC's `&fraig -x` approach is the one to start from. It isn't needed for
DLP 57's rules, which are checked one value operation at a time.

## Experiment 8: Native CaDiCaL and Kissat

Native CaDiCaL 2.2.1 and Kissat 4.0.4 (`native_solvers.py`,
`results/native_tables.md`) on the miter of each hard pair separately: every
pair of the parity and hidden weighted bit instances, and the two middle
product bits of each multiplier, written by `beq cnf` with only the two
cones, 300 s per pair, four at a time. `auto` is the time for all pairs of
the instance together.

| instance | CaDiCaL 2.2.1, slowest pair | Kissat 4.0.4, slowest pair | auto, all pairs |
| -------- | --------------------------- | -------------------------- | --------------- |
| hwb_i8 | 5.9 ms | 5.43 ms | 18 µs |
| hwb_i12 | 15.5 ms | 14.3 ms | 104 µs |
| hwb_i16 | 29.7 ms | 29.8 ms | 5.01 ms |
| hwb_i20 | 58.9 ms | 123 ms | 12.1 ms |
| hwb_i24 | 91.8 ms | 145 ms | 20.7 ms |
| hwb_i28 | 153 ms | 255 ms | 43 ms |
| hwb_i32 | 255 ms | 312 ms | 56.6 ms |
| hwb_i40 | 480 ms | 603 ms | 81.1 ms |
| mult_commuted_b3 | 1.85 ms | 1.46 ms | 18.2 µs |
| mult_commuted_b4 | 2.81 ms | 2.6 ms | 19.1 µs |
| mult_commuted_b5 | 7.63 ms | 8.04 ms | 47.4 µs |
| mult_commuted_b6 | 22.7 ms | 34.6 ms | 162 µs |
| mult_commuted_b7 | 132 ms | 174 ms | 108 ms |
| mult_commuted_b8 | 542 ms | 604 ms | 222 ms |
| mult_commuted_b9 | 2.76 s | 1.93 s | 739 ms |
| mult_commuted_b10 | 15.3 s | 7.85 s | 3.75 s |
| mult_commuted_b11 | 56.3 s | 30.2 s | timeout |
| mult_commuted_b12 | 300 s (1 of 2 time out) | 139 s | timeout |
| mult_kogge_b3 | 5.81 ms | 1.78 ms | 9.28 µs |
| mult_kogge_b4 | 3.4 ms | 2.95 ms | 20.4 µs |
| mult_kogge_b5 | 7.59 ms | 9.08 ms | 51.2 µs |
| mult_kogge_b6 | 32 ms | 35.1 ms | 187 µs |
| mult_kogge_b7 | 150 ms | 250 ms | 121 ms |
| mult_kogge_b8 | 672 ms | 623 ms | 276 ms |
| mult_kogge_b9 | 3.54 s | 2.39 s | 976 ms |
| mult_kogge_b10 | 14.3 s | 10.1 s | 4.81 s |
| mult_kogge_b11 | 76.6 s | 34.9 s | timeout |
| mult_kogge_b12 | 300 s (1 of 2 time out) | 244 s | timeout |
| parity_i8_c3 | 3.91 ms | 3.17 ms | 8.81 µs |
| parity_i12_c3 | 4.9 ms | 2.62 ms | 40.3 µs |
| parity_i16_c3 | 7.21 ms | 6.91 ms | 8.69 ms |
| parity_i20_c3 | 47.9 ms | 39.3 ms | 7.57 ms |
| parity_i24_c3 | 261 ms | 69.5 ms | 8.33 ms |
| parity_i28_c3 | 159 ms | 116 ms | 8.54 ms |
| parity_i32_c3 | 153 ms | 86.2 ms | 8.99 ms |
| parity_i40_c3 | 11.4 s | 448 ms | 11 ms |
| parity_i48_c3 | 300 s (2 of 3 time out) | 29.9 s | 10.5 ms |
| parity_i64_c3 | 300 s (2 of 3 time out) | 300 s (2 of 3 time out) | 12.7 ms |
| parity_i96_c3 | 300 s (2 of 3 time out) | 300 s (2 of 3 time out) | 17.5 ms |
| parity_i128_c3 | 300 s (2 of 3 time out) | 300 s (2 of 3 time out) | 21.9 ms |

- **Kissat is the strongest single solver here.** It's about 2× faster than
  CaDiCaL on the hardest multiplier bits (30–35 s against 56–77 s at 11
  bits), up to 25× faster on parity (0.45 s against 11.4 s at 40 inputs),
  and the only one that finishes both middle bits of the 12-bit multipliers
  within 300 s (139–244 s).
- **Parity in a different order defeats both solvers** from 64 inputs, while
  the combined algorithm decides it through OBDDs in milliseconds.
- **The built-in solver is the weak link on multipliers**: `auto` gives up at
  11 bits within 120 s, while Kissat solves those bits. That's why
  `auto_kissat` hands the pairs that get past every other step to Kissat.
  On everything else, the built-in solver is never what decides the time,
  because pairs that reach it are rare.

## Experiment 9: SDDs

SDDs were in the candidate list because, in theory, a vtree that follows a
tree decomposition can be exponentially smaller than any OBDD. `sdd_compare.py`
compiled a sample of every workload with pysdd 1.0 (`results/sdd_tables.md`)
in three ways: a right-linear vtree in first-use order (which makes the SDD
an OBDD), a balanced vtree over the same order, and a balanced vtree with
pysdd's automatic garbage collection and vtree minimization. The sample
includes a tree-shaped workload, a multiplexer `data[address]` written as a
tree on the address bits and as a decoder (11 to 135 inputs). Every SDD gave
the same classes as `beq`'s OBDDs, so canonical SDDs work as an exact
equality check by node identity, as OBDDs do. The SDDs are driven from
Python, which adds about 0.4 µs per node (measured), negligible except on
the smallest library operations.

| instance | inputs | `and` nodes | OBDD nodes, time | SDD right-linear (nodes, time, memory) | SDD balanced | SDD balanced + minimization |
| -------- | ------ | ----------- | ---------------- | -------------------------------------- | ------------ | --------------------------- |
| op_i16_s64_w8_0 | 16 | 132 | 508, 160 µs | 551, 633 µs, 0 KB | 301, 568 µs, 0 KB | 177, 7.23 ms, 0 KB |
| op_i16_s64_w8_1 | 16 | 145 | 967, 196 µs | 1,128, 1.04 ms, 0 KB | 489, 980 µs, 0 KB | 409, 14.2 ms, 15.2 MB |
| op_i16_s256_w8_0 | 16 | 489 | 3,688, 365 µs | 4,538, 3.68 ms, 0 KB | 2,013, 4.75 ms, 688 KB | 1,859, 152 ms, 140 MB |
| op_i16_s256_w8_1 | 16 | 600 | 3,845, 382 µs | 4,582, 4.18 ms, 0 KB | 1,832, 5.33 ms, 1.9 MB | 1,321, 91.9 ms, 114 MB |
| op_i32_s64_w8_0 | 32 | 123 | 1,422, 195 µs | 1,626, 1.42 ms, 0 KB | 627, 1.25 ms, 0 KB | 317, 44.8 ms, 68.3 MB |
| op_i32_s64_w8_1 | 32 | 186 | 1,991, 263 µs | 2,342, 1.66 ms, 0 KB | 1,082, 2.36 ms, 0 KB | 516, 65.5 ms, 101 MB |
| op_i32_s256_w8_0 | 32 | 567 | 4,786, 393 µs | 5,791, 4.21 ms, 924 KB | 2,951, 7.99 ms, 9.57 MB | 1,617, 181 ms, 142 MB |
| op_i32_s256_w8_1 | 32 | 586 | 13,354, 865 µs | 15,750, 11.1 ms, 20.9 MB | 5,637, 17.1 ms, 32.2 MB | 5,163, 432 ms, 151 MB |
| op_i64_s64_w8_0 | 64 | 143 | 3,014, 272 µs | 3,044, 2.27 ms, 0 KB | 977, 2.1 ms, 0 KB | 451, 38.7 ms, 54.4 MB |
| op_i64_s64_w8_1 | 64 | 142 | 1,044, 194 µs | 1,054, 1.2 ms, 0 KB | 352, 636 µs, 0 KB | 226, 18.8 ms, 21.6 MB |
| op_i64_s256_w8_0 | 64 | 630 | 76,348, 4.65 ms | 81,979, 51.6 ms, 95 MB | 15,698, 198 ms, 119 MB | 5,788, 988 ms, 150 MB |
| op_i64_s256_w8_1 | 64 | 526 | 10,889, 651 µs | 11,924, 10.1 ms, 15.8 MB | 3,010, 8.05 ms, 5.96 MB | 862, 197 ms, 143 MB |
| library_000 | 3 | 17 | 9, 155 µs | 8, 121 µs, 0 KB | 8, 112 µs, 0 KB | 8, 130 µs, 0 KB |
| library_020 | 5 | 53 | 38, 134 µs | 40, 169 µs, 0 KB | 33, 160 µs, 0 KB | 33, 668 µs, 0 KB |
| library_040 | 3 | 119 | 27, 158 µs | 30, 298 µs, 0 KB | 30, 308 µs, 0 KB | 30, 380 µs, 0 KB |
| library_060 | 4 | 147 | 78, 143 µs | 96, 281 µs, 0 KB | 74, 300 µs, 0 KB | 81, 586 µs, 0 KB |
| library_080 | 10 | 73 | 93, 150 µs | 97, 352 µs, 0 KB | 55, 322 µs, 0 KB | 47, 1.29 ms, 0 KB |
| library_100 | 10 | 6 | 13, 176 µs | 5, 101 µs, 0 KB | 4, 101 µs, 0 KB | 4, 140 µs, 0 KB |
| library_120 | 9 | 90 | 157, 158 µs | 193, 447 µs, 0 KB | 114, 465 µs, 0 KB | 73, 3.28 ms, 0 KB |
| library_140 | 8 | 52 | 45, 153 µs | 46, 181 µs, 0 KB | 42, 181 µs, 0 KB | 36, 1.1 ms, 0 KB |
| library_160 | 8 | 67 | 58, 160 µs | 63, 310 µs, 0 KB | 59, 357 µs, 0 KB | 63, 900 µs, 0 KB |
| library_180 | 5 | 92 | 76, 254 µs | 91, 347 µs, 0 KB | 81, 361 µs, 0 KB | 66, 824 µs, 0 KB |
| parity_i16_c3 | 16 | 180 | 1,266, 193 µs | 1,443, 1.25 ms, 0 KB | 467, 650 µs, 0 KB | 486, 16.1 ms, 23.7 MB |
| parity_i32_c3 | 32 | 372 | 5,242, 333 µs | 6,114, 4.35 ms, 0 KB | 1,405, 1.56 ms, 0 KB | 1,416, 51.4 ms, 93.2 MB |
| parity_i64_c3 | 64 | 756 | 20,621, 896 µs | 24,353, 16.3 ms, 27.1 MB | 3,646, 3.5 ms, 0 KB | 3,715, 129 ms, 142 MB |
| parity_i128_c3 | 128 | 1,524 | 85,908, 3.68 ms | 102,236, 70.4 ms, 93.6 MB | 9,195, 9.63 ms, 11 MB | 9,762, 280 ms, 148 MB |
| hwb_i12 | 12 | 404 | 2,850, 304 µs | 3,379, 4.23 ms, 1.12 MB | 1,147, 2.81 ms, 0 KB | 1,505, 51 ms, 69.7 MB |
| hwb_i16 | 16 | 602 | 7,791, 547 µs | 9,694, 9.8 ms, 19.1 MB | 2,868, 8.98 ms, 7.85 MB | 2,684, 158 ms, 142 MB |
| hwb_i20 | 20 | 831 | 20,267, 1.35 ms | 24,919, 23 ms, 48.8 MB | 6,744, 30.4 ms, 46.1 MB | 6,528, 396 ms, 155 MB |
| hwb_i24 | 24 | 1,007 | 56,793, 3.6 ms | 67,437, 50 ms, 84.8 MB | 17,933, 92.7 ms, 110 MB | 10,513, 1.46 s, 182 MB |
| mult_commuted_b4 | 8 | 230 | 1,585, 243 µs | 1,786, 2.39 ms, 0 KB | 730, 1.77 ms, 0 KB | 699, 10.9 ms, 8.62 MB |
| mult_commuted_b6 | 12 | 610 | 25,983, 1.59 ms | 28,880, 30.6 ms, 54.1 MB | 8,804, 24.8 ms, 43.7 MB | 5,894, 241 ms, 150 MB |
| mult_commuted_b8 | 16 | 1,166 | 306,051, 25.4 ms | 342,531, 348 ms, 197 MB | 78,835, 316 ms, 174 MB | 41,133, 11.1 s, 239 MB |
| tangle_i32_s256_0 | 32 | 491 | 3,069, 301 µs | 3,447, 3.66 ms, 0 KB | 2,142, 5.96 ms, 2.45 MB | 1,372, 96.3 ms, 116 MB |
| tangle_i32_s256_1 | 32 | 519 | 1,908, 281 µs | 2,127, 2.45 ms, 0 KB | 1,017, 2.55 ms, 0 KB | 852, 58 ms, 78.8 MB |
| cmp_b8_c10 | 32 | 2,780 | 36,372, 2.47 ms | 43,417, 33.5 ms, 47.1 MB | 16,743, 30.8 ms, 50.5 MB | 8,317, 867 ms, 152 MB |
| mux_a3 | 11 | 52 | 107, 175 µs | 120, 215 µs, 0 KB | 93, 224 µs, 0 KB | 63, 1.23 ms, 0 KB |
| mux_a4 | 20 | 124 | 304, 193 µs | 340, 393 µs, 0 KB | 226, 523 µs, 0 KB | 213, 2.24 ms, 0 KB |
| mux_a5 | 37 | 284 | 785, 226 µs | 868, 806 µs, 0 KB | 475, 1.22 ms, 0 KB | 354, 6.92 ms, 0 KB |
| mux_a6 | 70 | 636 | 1,914, 227 µs | 2,092, 1.73 ms, 0 KB | 1,014, 4.12 ms, 0 KB | 897, 25.3 ms, 25.4 MB |
| mux_a7 | 135 | 1,404 | 4,499, 355 µs | 4,868, 5.23 ms, 0 KB | 2,078, 19.3 ms, 29.6 MB | 1,859, 39.8 ms, 54.2 MB |
| program_t200_c1000_r50 | 790 | 6,961 | limit:bdd_nodes | failed: exit 1 | failed: exit 1 | timeout |

Runs whose classes differ from beq's OBDD: 0

Over the 41 instances where everything finished, against `beq`'s OBDDs:

| SDD                       | Nodes, OBDD ÷ SDD (min / median / max) | Time, SDD ÷ OBDD (min / median / max) |
| ------------------------- | -------------------------------------- | ------------------------------------- |
| balanced vtree            | 0.9 / 2.1 / 9.3                        | 0.57 / 6.4 / 54                       |
| balanced, with minimizing | 0.9 / 2.6 / 13                         | 0.8 / 112 / 499                       |

- **SDDs are smaller but slower.** A balanced vtree gives 2.1× fewer nodes
  in the median and up to 9.3× (128-input parity: 9,195 against 85,908), but
  takes 6.4× longer to build in the median. Minimizing the vtree shrinks
  them a little more at 100× the time.
- **The tree-shaped workload doesn't need them:** the multiplexer's OBDD in
  first-use order is already linear in its size (4,499 nodes for 135 inputs),
  and the balanced SDD is 2.2× smaller.
- **Neither scales to programs:** on the smallest program (7K nodes, 790
  inputs), the OBDD passed 67M nodes, the right-linear and balanced SDDs ran
  out of 8 GB, and minimizing ran past 300 s, while SAT sweeping took 12 ms.
- **For equality checking, size isn't what matters.** Both kinds of diagram
  are slower than the combined algorithm on every realistic operation in the
  sample (5–200 ms for balanced SDDs at 256 statements, against about
  0.3 ms). So SDDs aren't a contender here.

## Experiment 10: The Combined Algorithm End to End

`auto` ([algorithm.md](algorithm.md)) on every workload, compared per
instance with the fastest of the seven other exact configurations on that
same instance (`summarize.py auto`, `results/auto_tables.md`). That's a hard
baseline: it's the best of seven measurements, chosen after the fact, so a
ratio of 1 means matching an oracle that knew which engine to use.

### Absolute cost

| Workload                                   | `auto`                                   | For comparison                                                       |
| ------------------------------------------ | ---------------------------------------- | -------------------------------------------------------------------- |
| Value operations, 16 statements (55)       | median 7.8 µs, slowest 20 µs             | OBDDs 7.7 µs median; `sweep` 13 µs                                   |
| Value operations, ≤ 256 statements (165)   | median 32 µs, slowest 0.86 ms            | `sweep` 46 µs / 0.98 ms; OBDDs 20 µs median but 79 ms slowest        |
| Value operations, ≤ 1,024 statements (220) | median 43 µs, slowest 7.2 ms             | `sweep` 142 µs / 8.8 ms; OBDDs up to 10.7 s; truth tables up to 2.2 s |
| Library, 200 operations                    | 0.9 ms in all (every one by truth tables) | ABC `&fraig` 60 ms                                                   |
| Adversarial (62), with Kissat last         | all finish; 58 under 5 s; 11-bit multipliers 134–156 s; 12-bit 878–1,150 s | without Kissat, the 11- and 12-bit multipliers don't finish in 120 s |

Every run found every planted pair.

### Against the fastest exact method per instance

#### operations

220 instances; auto / fastest exact method: median 1.06, 90th percentile 1.92, max 5.58
auto faster than or equal to every exact method on 40
paths taken: {'sweep': 160, 'tt': 60}; unfinished: []
- op_i20_s256_w8_4: 3.67 times (228 µs against bdd_natural 62.1 µs)
- op_i16_s1024_w8_0: 3.93 times (2.22 ms against bdd_first_use 565 µs)
- op_i16_s256_w8_3: 5.58 times (302 µs against bdd_first_use 54.1 µs)

#### adversarial

58 instances; auto / fastest exact method: median 1.17, 90th percentile 87.39, max 261.05
auto faster than or equal to every exact method on 15
paths taken: {'sweep': 46, 'tt': 12}; unfinished: ['mult_commuted_b11', 'mult_commuted_b12', 'mult_kogge_b11', 'mult_kogge_b12']
- mult_commuted_b7: 142.42 times (108 ms against tt 755 µs)
- parity_i20_c3: 154.04 times (7.57 ms against bdd_first_use 49.2 µs)
- parity_i16_c3: 261.05 times (8.69 ms against bdd_natural 33.3 µs)

#### library

200 instances; auto / fastest exact method: median 0.97, 90th percentile 1.05, max 1.65
auto faster than or equal to every exact method on 144
paths taken: {'tt': 200}; unfinished: []
- library_004: 1.46 times (13.4 µs against bdd_first_use 9.2 µs)
- library_002: 1.52 times (7.22 µs against tt 4.74 µs)
- library_105: 1.65 times (0.79 µs against tt 0.48 µs)

#### program

11 instances; auto / fastest exact method: median 1.01, 90th percentile 1.10, max 1.13
auto faster than or equal to every exact method on 2
paths taken: {'sweep': 11}; unfinished: []
- program_t200_c64000_r50: 1.09 times (5.23 s against sweep 4.81 s)
- program_t200_c1000_r50: 1.10 times (12.1 ms against portfolio 11 ms)
- program_t200_c64000: 1.13 times (36 s against sweep 31.9 s)

- **On realistic operations it's within 1.06× of the oracle in the median**
  and within 2× for 90% of them. The worst case, 5.6×, is a 256-statement
  operation where an OBDD happened to take 54 µs against 302 µs: a
  quarter-millisecond lost.
- **On adversarial instances the median is 1.17×, but the tail is long**:
  up to 261× on parity, where OBDDs take 33 µs and `auto` spends 1,000
  conflicts of SAT first (8.7 ms), and 142× on a 7-bit multiplier (108 ms
  against 0.76 ms with truth tables over its 14 inputs). In absolute terms
  those losses are milliseconds to a tenth of a second.
- **Library operations** all go to truth tables and match the oracle.

### Trying an OBDD first

`dispatch_budget.py` (`results/dispatch_budget.txt`) tried a whole-graph OBDD
before sweeping, within F nodes per graph node, on 143 instances:

| F            | Operations, total | Adversarial, total | Worst ratio to the best F | Settled by the OBDD |
| ------------ | ----------------- | ------------------ | ------------------------- | ------------------- |
| 0 (none)     | 62 ms             | 12.0 s             | 251                       | 0                   |
| 4            | 76 ms             | 12.1 s             | 250                       | 6                   |
| 16           | 85 ms             | 12.0 s             | 44                        | 53                  |
| 64           | 141 ms            | 12.2 s             | 11                        | 87                  |

A large budget removes the long tail (worst ratio 11 instead of 251), but
more than doubles the cost of realistic operations, and the adversarial
total doesn't change because multipliers dominate it. Since programs that
compile are mostly realistic logic, the combined algorithm doesn't try an
OBDD first. Every budget gave identical classes.

### Cost of measuring and choosing

- Choosing between truth tables and sweeping reads the number of inputs:
  free.
- The ladder's extra steps (exhaustive simulation of small cones, the OBDD
  rescue) make `auto` faster than plain `sweep` on value operations (32 µs
  against 46 µs median at up to 256 statements), because exhaustive
  simulation of a cone with at most 12 inputs is cheaper than a SAT call.
- Failed rungs cost what they spend before giving up: at most 1,000
  conflicts (milliseconds) before the OBDD rescue, and up to 4M OBDD nodes
  (seconds, only on multipliers here) before the truth tables or the last
  SAT step.

### Determinism

Every exact configuration gives the same classes (Correctness, above,
including `auto` and `auto` forced through its truth-table switch on every
hard pair), three seeds give the same classes, and every OBDD-first budget
gives the same classes. So which rung decides a pair is invisible in the
result. [algorithm.md](algorithm.md) explains why.

### Whole programs

On the eleven programs of Experiment 5, timed back to back with `sweep` and
`portfolio` on each, `auto` took 0.90–1.13 times `sweep`'s time
(`results/program.jsonl`). On a whole program every value has more than 12
inputs, so the dispatch always chooses sweeping, and the ladder's extra
steps are rarely reached.

## Experiment 11: The Modular Algorithm on Whole Programs

The one study allowed past 30 seconds a check: the complete modular
algorithm on large programs (`final_program_experiment.py`,
`results/final_program.jsonl`). A program is a library of boolean value
operations that execute each other (`gen/hierarchy.py`, 20 or 10 levels),
checked the way the compiler would: every value operation once, in
dependency order, with executions as references; truth tables with lookups
up to 12 views, otherwise SAT with the hybrid refinement and stored patterns
(`beq hier --how auto`). Each program was checked from nothing, checked
again unchanged with the patterns stored by the first check, and edited at
random 200 times with only the affected operations checked again. Limits:
1,800 s and 16 GB per run. Everything ran alone on an idle machine.

| Program | Operations | Values | First check (wall, peak memory) | Unchanged, with patterns | Slowest operation | One edit: rechecked median / most, time median / slowest |
| ------- | ---------- | ------ | ------------------------------- | ------------------------ | ----------------- | -------------------------------------------------------- |
| 10 views, compiles | 15,002 | 346K | 0.21 s, 21 MB | 0.21 s | 38 µs | 1 / 8, 15 µs / 110 µs |
| 10 views, compiles | 150,151 | 3.5M | 2.0 s, 178 MB | 2.1 s | 116 µs | 1 / 18, 42 µs / 305 µs |
| 16 views, random | 2,000 | 138K | 2.8 s, 38 MB (74,561 SAT calls) | 1.6 s (17,441 SAT calls) | 22 ms | 1 / 26, 0.7 ms / 18 ms |

About a third of the operations in the 10-view programs are the generator's
twins (each a sum of products of another operation's function), counted as
ordinary operations. The 16-view program was generated without tracking
functions, so 1,738 of its 2,000 operations have redundant values; it
measures the SAT path, which only operations with more than 12 views take.

- **Checking is linear in the number of operations** at about 13 µs per
  10-view operation, so 150,000 value operations (3.5 million values) take
  2 seconds and 178 MB, of which 1.3 s is checking and the rest reading
  the library.
- **Stored patterns matter only on the SAT path**: truth tables never call
  a solver. On the 16-view program, patterns cut the SAT calls by 77% and
  the time by 44%; the remaining calls prove the redundant values, which
  patterns can't do.
- **An edit costs one operation's check in the median**, at most 18–26
  operations, and under a third of a millisecond with truth tables.

Compare Experiment 5, where one program of 7M nodes with every call copied
in took 137 s, and one long dataflow of 2.2M nodes took 393 s.
