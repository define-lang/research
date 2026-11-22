# Boolean Equality Checking

What is the most efficient way for the Define compiler to find, exactly, which
boolean values in a program always equal each other, which are constant, and
which equal one of their inputs? This is what DLP 59's rules against
"redundant values" and "writing the same logic twice" need. This directory
answers it by experiment: it implements the candidate methods in C++, runs
them on generated workloads from tens of statements to seven million nodes,
compares them with ABC, CaDiCaL, Kissat, and SDDs, and measures time, memory,
and how many planted equalities each one finds.

- [algorithm.md](algorithm.md): the authoritative specification of the current
  reference algorithm (`beq program --method auto`), including truth-table and
  ROBDD dispatch, the budget-free canonical 4,000,000-node ROBDD limit, exact
  match and spelling search, and the human-readable DLP 61 registered-operation
  order.
- [arguments.md](arguments.md): the conclusions that come from reasoning
  instead of measurement, including why a canonical ROBDD node limit is
  compiler-independent while heuristic solver or step budgets are not.
- [full_algorithm.md](full_algorithm.md): every check of DLPs 59–61 at once on
  whole generated programs, with the fix loop, incremental rechecking, and the
  fewest `and`s of every function of up to four views.
- [results/budget.md](results/budget.md): budget-free measurements across all
  3,265 real-code units (11 codebases) and 277 generated adversarial workloads.
- [proof/termination.md](proof/termination.md): a proof, in English and in Lean
  ([proof/fixing_termination.lean](proof/fixing_termination.lean)), that fixing
  a program of static finite DAG value operations under DLPs 59–61 always
  terminates (`dag_prog_terminates` discharges finiteness directly from
  Define's acyclic computation graphs).
- [related_work.md](related_work.md): a literature search on how close existing
  systems and papers come to DLPs 59–61 and these algorithms.
- Historical component studies (archived in `studies/`):
  - [studies/experiments.md](studies/experiments.md): earlier single-graph
    benchmarks and SAT-sweeping comparisons (Experiments 1–11).
  - [studies/matching.md](studies/matching.md): whether DLP 59's rule against
    writing out a registered operation could be exact.
  - [studies/references.md](studies/references.md): checking value operations
    that execute others by referring to each execution instead of copying it.
  - [studies/steady_state.md](studies/steady_state.md): the cost of checking
    programs that compile, stored patterns, and rechecking after edits.
  - [studies/earlier_values.md](studies/earlier_values.md): an exact match
    definition over values computed earlier and convergence experiments.
  - [studies/precedence.md](studies/precedence.md): a precedence rule between
    equivalent spellings of a value.

## Recommendations

### Within One Value Operation

This is what DLP 59–61's rules need, and it is the case to optimize.

**Decide equality, symmetry, matches, and spellings exactly per value
operation, using truth tables for small input counts and complement-edge ROBDDs
past them, with a canonical 4,000,000-node ROBDD limit and no step budget**
([algorithm.md](algorithm.md)):

1. **Guaranteed envelope (`≤ 256` boolean statements and `≤ 20` boolean
   inputs):** always compiles. Truth tables run directly when `I ≤ 16` (or
   `I ≤ 20` when executing an operation of more than 6 read views), and serve
   as a complete fallback if an operation inside the envelope hits the ROBDD
   node limit. Executions refer to the executed operation's recorded summary
   (compact AIG, mux-tree or `8 × 8` bit-matrix-transpose table lookup, or
   recorded `Diagram`).
2. **Beyond the guaranteed envelope (`S > 256` or `I > 20`):** evaluate with
   complement-edge ROBDDs (native `land`/`lor`/`lxor`/`ite`, zero-allocation
   `O(I)` lockstep `distinguishing_path`, `O(|Diagram|)` Chow/Walsh symmetry
   pre-partitioning + lockstep `are_symmetric`) in deterministic first-reached
   DFS input order over the value operation's DAG. Accept if and only if the
   canonical shared ROBDD of all boolean statements has at most **4,000,000
   reachable non-terminal nodes**.
3. **Unified single-pass match and spelling search:** one `Matcher` handles
   both matches and spellings over exact canonical class IDs, arbitrary-width
   varied-density + BDD collision-splitting samples, MFFC-size pruning,
   `mux` two-case data-first search, direct `xor`/`eq` hash lookup, and
   descending-MFFC best-match search.
4. **Human-readable DLP 61 registered-operation order:** `and`, `not`, then
   `(fewest_ands, read_views, project_before_stdlib, fewer_interchangeable_groups, counting_order_truth_table)`,
   giving `and`, `not`, `or`, `implies`, `xor`, `eq`, `mux`, `maj`.

On all **3,265 real-code units** past the old limits across 11 codebases
([results/budget.md](results/budget.md)), **3,264 / 3,265 (99.97%)** compile
cleanly with **0 timeouts and no step budget** (median **0.35 ms**, p99
**21.86 ms**, max **1.19 s**); only `mypy`'s `visit_comparison_expr` (2,078
inputs, 2,011 statements, 44.4M ROBDD nodes) exceeds the 4,000,000-node limit.
All **277** generated adversarial workloads (`dense`, `xor_heavy`, `parity`,
`read_once`, `long` up to 1,024 statements, `real`, and multipliers up to
28×28) finish in **≤ 2.15 s** with **0 timeouts**. On whole generated programs,
14,897 operations check in **1.34 s** (84 MB RSS) and 1,995 wide 16–20-input
operations check in **12.26 s** (188 MB RSS).

What the earlier single-graph studies ([studies/experiments.md](studies/experiments.md))
measured for whole programs checked as one flattened AIG: SAT sweeping, with a
ladder of exhaustive simulation, SAT up to 1,000 conflicts, OBDDs, and SAT with
no limit (Kissat). Every rung is exact and a class's representative is its
smallest value, so thresholds, seeds, and which engine decided a pair change
only the time (eleven exact configurations gave identical classes on 300 random
instances).

This is essentially the combination of Kuehlmann, Paruthi, Krohm, and Ganai,
"Robust Boolean Reasoning for Equivalence Checking and Functional Property
Verification" (IEEE TCAD 21(12), 2002), which used structural hashing, random
simulation, BDD sweeping, and circuit SAT together on one AIG. Exhaustive
simulation of small windows inside SAT sweeping is in Pan et al.,
["A Semi-Tensor Product based Circuit Simulation for SAT-sweeping"](https://arxiv.org/abs/2312.00421)
(DATE 2024). Nothing here needed a new algorithm.

| Workload                                     | Combined algorithm                        | Against the fastest exact method on each instance |
| -------------------------------------------- | ----------------------------------------- | ------------------------------------------------ |
| Value operations, ≤ 256 statements (165)     | median 32 µs, slowest 0.86 ms             |                                                  |
| Value operations, ≤ 1,024 statements (220)   | median 43 µs, slowest 7.2 ms              | median 1.06×, 90th percentile 1.9×, worst 5.6×    |
| Library, 200 operations                      | 0.9 ms in all                             | median 0.97×                                     |
| Adversarial (62), with Kissat last           | all finish; 58 under 5 s; 11-bit multipliers 134–156 s, 12-bit 878–1,150 s | median 1.17×, worst 261× (parity: 8.7 ms against 33 µs) |

**Against other tools.** On realistic value operations, the combined
algorithm is faster than every ABC command and finds the same pairs: ABC's
`&fraig` is 4.8× slower at 256 statements and 2.8× at 1,024, `&cec` 24× and
7×. ABC wins on one family, comparators (`&fraig -x`: 118 ms against 1.8 s
for 64 bits), and loses on parity in a different order, which its SAT
sweeping leaves undecided. Of the native solvers, Kissat is about 2× faster
than CaDiCaL on multiplier bits and up to 25× on parity, which is why it's
the last rung. SDDs give 2.1× fewer nodes than OBDDs in the median but take
6.4× longer, and fail on the smallest program, so they aren't a contender.

**What the cheaper methods miss.** DLP 59 currently defines a redundant value
over cuts of at most four values. On the generated operations of up to 256
statements, that finds 58% of the planted redundancies. It misses most of
the ones that aren't local: 62% of whole-cone rewrites, 70% of case splits,
86% of absorptions of a rewritten value, 71% of contradictions with one.
Structural hashing finds 29%, and the normalized AND-of-literal-sets form
31–34%. Exact checking finds all of them, and is faster than enumerating DLP
59's cuts past a few dozen statements.

**The worst case.** Exact checking is coNP-hard, and DLP 59's limits don't
bound it, because an executed boolean value operation can be any function of
twelve views (see [arguments.md](arguments.md)). The combined algorithm
handles every adversarial family measured here in at most seconds except
multipliers: parity of 128 inputs in three different orders in 22 ms (SAT
alone, and native CaDiCaL and Kissat, time out from 48–64 inputs), hidden
weighted bit of 40 inputs in 81 ms, 64-bit comparators in 1.8 s. Multipliers
written two ways take minutes from 11 bits even with Kissat, growing about
5–6× per bit. Truth tables are the fastest thing for multipliers, because
they depend only on the number of inputs, which is what Decision 2 below
relies on.

### Restrictions

The task allowed restrictions on how programs are written:

- **A limit of 20 boolean inputs per value operation** bounds the worst case
  (Decision 2 below): truth tables take at most 52 ms for 256 statements at
  20 inputs (2 ms at 16), and 120 ms for 1,024 statements, whatever the
  logic. The combined algorithm reaches them only when its ladder fails.
- **Not recommended: a limit on width (live values along the statement
  order).** Measured widths of the generated operations are 17–74 (median
  38) at 256 statements and 32–133 at 1,024, because a condition that's
  read again later stays live, while their OBDDs are thousands of nodes,
  nowhere near the 2^w per level the bound allows. Any limit small enough to
  matter would send nearly every operation past it. The draft's other point
  holds: inputs in first-use order are much better than numbered order for
  OBDDs (1.3 ms against 2.8 s median at 128 inputs and 256 statements).
- **Not recommended: a solver budget as the rule.** With a conflict limit,
  the answers on hard cases change as the limit changes, and they'd depend on
  the solver's version and heuristics. A budget is fine as a performance
  knob in front of something exact, which is how the ladder uses it.
- **No change to the primitive operations.** Exclusive or as a primitive
  would make parity structural, but the combined algorithm already decides
  it in milliseconds, and the case that stays hard (multipliers) is hard
  with exclusive or too. Majority or if-then-else don't change any measured
  cost. This is argued from the measurements, not measured with another gate
  set.
- **Keep matches of registered operations exact over earlier values**
  (see the historical progression in [studies/matching.md](studies/matching.md),
  [studies/earlier_values.md](studies/earlier_values.md), and
  [studies/precedence.md](studies/precedence.md), plus the final unified search
  in [algorithm.md](algorithm.md)). The four-view limit is justified by cost
  (each added view multiplies search cost by 7–18×), and replacing a match is
  restricted to groups removing at least 2 statements (3 for an opposite
  result) so refactoring provably terminates.
- **No heuristic solver or step budget as a language rule**
  ([arguments.md](arguments.md)). Instead, past the guaranteed `(256 statements,
  20 inputs)` envelope, compilation uses a canonical **4,000,000-node shared
  ROBDD limit** under a fixed deterministic DFS variable order. Because the
  shared ROBDD is mathematically unique, every compiler gives the exact same
  answer, and raising the limit is strictly Forward Compatible.

No restriction can make exact checking polynomial without making some
functions need exponentially more code, unless P = coNP: any two AIGs can be
rewritten into a restricted form in polynomial time, so checking the
restricted form is still coNP-hard ([arguments.md](arguments.md)). The input
limit escapes this only because it moves part of the program out of what's
checked.

### Executions of Other Value Operations

**Refer to an execution instead of copying it**
([studies/references.md](studies/references.md)). Copying every execution into its caller
grows 3–4 times per level: 316 ms and 3.2M nodes per operation at 12 levels
with three executions each, and past 20M nodes at 14. Referring to it, each
operation costs the same at any depth:

- **Truth tables with lookups** in the executed operations' recorded tables:
  12–22 µs per operation, the cheapest up to about 16 views. At 20 views,
  recording a table of 2^20 combinations costs about 12.6 ms per operation,
  where OBDDs with composition take 0.1 ms.
- **SAT with refinement**: an execution starts as an unknown function
  constrained by its recorded table where the solver's model disagrees.
  Expanding an execution at its first disagreement can degenerate into
  copying (4.6 s for one library), and adding one clause per disagreeing
  assignment can need millions of clauses (no answer in 10 minutes at 20
  views). A hybrid, clauses for an execution's first four disagreements and
  then expanding it, handled every library in milliseconds (14 ms for the
  one where expansion took 4.6 s).
- **What the executed operation's own check saves.** It has already passed
  every check, but over its own independent read views. So the caller never
  needs to look at its other values, and when its arguments are distinct
  read views of the caller, its results can't be constant, equal to each
  other, or equal to an argument (none in 7,240 such executions). With
  related arguments, though, 26–44% of random executions had a result that
  was redundant in the caller, so results are still checked like the
  caller's own values. Its stored patterns don't carry over to the caller.

### Programs That Compile

Most checks are of value operations that compile, where every value has to
be shown distinct and nothing can stop early ([studies/steady_state.md](studies/steady_state.md)):

- An operation that compiles costs about as much as one that doesn't
  (0.21 ms at 256 statements and 20 inputs). The solver is needed mostly for
  near misses, values that differ from an earlier one on very few input
  combinations; they raise the cost to about 1 ms.
- **Store the patterns** (assignments of the views) that showed values
  distinct with each compiled operation, at most one per value. On the next
  check, an unchanged operation that compiles needs no solver call, and
  after edits the solver makes 8–17% of the calls it would otherwise.
- **Check again only what an edit can affect**: the edited operation, and its
  callers while the function of a written view changes. Over 1,200 random
  edits, a median of one operation was checked again (at most 14), in
  12–21 µs.
- Stopping at the first redundant value saves nothing on operations that
  compile, and about a third on libraries where many fail.

### Whole Programs, Checked One Value Operation at a Time

The complete modular algorithm (references, truth tables up to 12 views,
otherwise SAT with the hybrid refinement and stored patterns) checks every
value operation of a program once, in dependency order. On generated
programs ([studies/experiments.md](studies/experiments.md), Experiment 11), 150,151 value operations with
3.5 million values took 2.0 s and 178 MB from nothing, about 13 µs per
operation, and a random edit made the compiler check a median of one
operation again (at most 18), in 42 µs. A 2,000-operation program of
16-view operations, which go through SAT, took 2.8 s, and 1.6 s again with
stored patterns.

### Across a Whole Program

**DLP 59 doesn't need it.** Its rules are about one value operation, with an
execution of another value operation counted as one statement, so the
compiler checks each definition once. All 200 operations of the program
library checked exactly in 1–4 ms in total, while the programs that execute
them, with every call inlined, are hundreds of thousands to millions of
nodes.

If the compiler wants program-wide equalities anyway, for optimization,
these are rough figures from single runs on graphs with every call copied
in, made before the rule that no check takes more than about 30 seconds:

- Structural hashing takes 0.46 s and 600 MB for an 8.3M-node program. It
  finds repeated calls, 70–77% of the planted pairs, but only about 11% of
  the redundant nodes.
- Exact SAT sweeping takes 138 s and 1.4 GB for a 7.0M-node program made of
  separate regions (like actions), growing nearly linearly, and 398 s and
  1 GB for a 2.2M-node program that is one long dataflow, growing about as
  n^1.7. It needs a solver that's restarted as it grows (334 s instead of
  23 s at 1.8M nodes without that).
- ABC's `&fraig -x` is much faster on programs made of regions (12 s
  against 137 s at 7.0M nodes, 2.7 s against 22 s at 1.8M) but slower on
  the one-dataflow shape (661 s against 393 s at 2.2M), where `&fraig` and
  the older `fraig` don't finish in 30 minutes and `&cec` runs out of 16 GB.
  For program-wide optimization, it's the approach to start from.

So program-wide exact checking is feasible for whole programs in minutes,
but it isn't something to run on every compile, and nothing in the rules
needs it.

## Decisions

1. **What DLP 59 guarantees.** Decided: a redundant value is one that's
   equal, as a function of the value operation's inputs, to a constant, an
   input, or an earlier value. This is exact, finds every planted redundancy,
   and the portfolio took at most 1 ms on the generated operations within DLP
   59's limits. The rejected alternative kept the current definition over cuts
   of at most four values, which misses 42% of planted redundancies and took
   1–3 ms.
2. **Bounding the worst case without a step budget.** Decided: every value
   operation with at most **256 boolean statements and 20 boolean inputs**
   always compiles (guaranteed by truth tables). Past that envelope, a value
   operation compiles if and only if its canonical shared ROBDD (under the
   deterministic first-reached DFS input order over its DAG) has at most
   **4,000,000 reachable non-terminal nodes**.
   - **Why this rule.** Unlike a heuristic SAT conflict limit or operational
     step counter, the canonical ROBDD node count is a pure mathematical
     property of the value operation's DAG—identical across compilers and
     machines, Forward Compatible when raised, and simple to explain. Across
     all 3,265 real-code units past the old limits, 3,264 (99.97%) compile
     cleanly in ≤ 1.19 s (median 0.35 ms) with zero timeouts
     ([results/budget.md](results/budget.md)).
   - **Rejected alternatives:** no limit (exponential bit-level arithmetic can
     take minutes or OOM), a hard 20-input cutoff (rejects large real-world
     condition chains with tiny BDDs), and an operational step budget
     (unpredictable, compiler-dependent, and hard to communicate).
3. **The width limit.** Decided: dropped from the compiler design, keeping
   first-use input order for OBDDs. Measured widths were 17–74 at 256
   statements, so any limit small enough to matter would reject nearly every
   value operation.

## What's Verified and What's Argued

Verified by experiment, on generated workloads:

- All eleven exact configurations, including the combined algorithm and the
  combined algorithm forced through its truth-table switch, give identical
  classes on 300 random instances, and every inexact method's merges hold
  in them. Three seeds, every OBDD-first budget, and every exact run of each
  whole program also agree.
- Every number in the tables above and in the linked writeups.
- The hard cases are hard for ABC, CaDiCaL, and Kissat too, so they aren't
  an artifact of the solver written here.
- In the follow-up studies, every method that finished agreed with every
  other, and patterns, references, and stopping early never changed a
  class.

Argued, not measured:

- That the generated value operations resemble real Define code. They follow
  DLP 59's statement order, reuse standard compositions, and contain no
  redundancy except what was planted, but they're random. How many boolean
  inputs real value operations have, which decides whether a limit of 20
  is comfortable, is unknown, and so is how many near misses real code has.
- That exact checking has no polynomial worst case under any restriction
  that keeps succinctness, and that DLP 59's limits don't bound it (the
  multiplier-from-blocks construction in [arguments.md](arguments.md) wasn't
  built).
- That exclusive or, majority, or if-then-else primitives wouldn't help.
- That the values the exact definition of a registered-operation match flags
  are coincidences, from inspecting examples, not all of them.
- That stored patterns, references, and incremental rechecking combine as
  [studies/steady_state.md](studies/steady_state.md) describes; each was measured
  separately.

## Files

- `src/`: the C++23 reference implementation, built into `beq` by `build.sh`.
  - `aig.hpp`: graphs, AIGER, arbitrary-width `Assignment`, union-find.
  - `sat.hpp`: the CDCL solver.
  - `bdd.hpp`: complement-edge ROBDDs with native `land`/`lor`/`lxor`/`ite`,
    zero-allocation `O(I)` `distinguishing_path`, and `reachable_node_count`.
  - `diagram.hpp`: reduced uncomplemented `Diagram` recorded for ROBDD-checked
    boolean value operations, with `O(|Diagram|)` Chow/Walsh `level_signatures`
    and zero-allocation lockstep `are_symmetric`.
  - `methods.hpp`: exact checking engines (`ChunkMethod`, `BddMethod`,
    `SatMethod`, `SplitMethod`) and diagnostic care-set/relation helpers.
  - `match.hpp`: unified single-pass registered-operation match and spelling
    search (`Matcher`), with arbitrary-width varied-density + BDD
    collision-splitting samples, MFFC-size pruning, `mux` two-case data-first
    search, direct `xor`/`eq` hash lookup, and best-match modes (`kBestOverall`,
    `kBestPerValue`, `kAll`).
  - `program.hpp`, `program_fix.hpp`, `program_main.hpp`: whole-program
    checking (`beq program --method auto`, defaulting to the budget-free
    canonical 4,000,000-node ROBDD limit past `(256 statements, 20 inputs)`),
    `8 × 8` bit-matrix-transpose wide table lookups, human-readable DLP 61
    ordering, exact bucket-verified `tt_keys`, 128-bit incremental fingerprints,
    and deterministic fixing.
  - `structural.hpp`, `functional.hpp`, `sweep.hpp`, `hier.hpp`, `split.hpp`:
    earlier single-graph, hierarchical, and split-check engines.
  - `main.cpp`: the `beq` command.
- `reference_test.py`: regression and cross-check test suite verifying `beq`
  (`tt`, `bdd`, `auto`, `--plain 1`, `--mode fix`, `--mode registry`) against
  `gen/program_check.py`, `I = 64..4,500`, wide lookups, and BDD symmetry.
- `proof/`: Lean 4 formal termination proof (`fixing_termination.lean`,
  including `dag_prog_terminates` discharging finiteness from Define's finite
  DAGs) and prose explanation (`termination.md`).
- `studies/`: archived earlier component study writeups (`experiments.md`,
  `matching.md`, `references.md`, `steady_state.md`, `earlier_values.md`,
  `precedence.md`).
- `gen/`: workload generators and helpers. `aig_builder.py`, `workloads.py`,
  `matching.py`, and `hierarchy.py` generate; `generate.py` is their command
  line; `verify.py` checks a method's classes with CaDiCaL;
  `cadical_miter.py` times CaDiCaL on planted pairs; `sdd_compile.py`
  compiles with SDDs; `caller_redundancy.py` counts executed operations'
  values that are redundant in their callers; `fixpoint.py` represents
  value operations as programs and applies DLP 59's fixes until they
  compile; `aiger.py` reads AIGER.
- Drivers: `experiments.py` (Experiments 1, 2, 4, 5, and 10),
  `check_methods.py` (compares all methods), `dispatch_budget.py`,
  `abc_compare.py`, `native_solvers.py`, `sdd_compare.py`,
  `matching_experiment.py`, `hierarchy_experiment.py`,
  `steady_state_experiment.py`, `caller_redundancy_experiment.py`,
  `resub_experiment.py`, `fixpoint_experiment.py`,
  `final_program_experiment.py`, `split_experiment.py` (the split check on
  the real-code study's operations past the limits, and its exactness
  against checks over every input; results in `results/split.json`),
  `methods_experiment.py` (where truth tables over every input stop being
  the fastest exact check, against the other methods; tables in
  `results/methods_tables.md`; with `real_steps`, DLP 59's rule on every
  real-code unit past the study's limits; the budget's measurements are in
  `results/budget.md`), `cadical_adversarial.sh`, and
  `run_everything.sh`. Every driver runs each check through
  `experiments.run_limited`, which kills it past 30 seconds (only the final
  whole-program study may take longer) or past its memory limit.
  `summarize.py` turns results into tables.
- `results/`: raw results as JSON lines, one per run, and the tables made
  from them (`*_tables.md`); the largest are compressed (`.jsonl.gz`).
  `results/preliminary/` holds runs that the writeups don't use, except
  where they say so: the first runs of Experiments 1 and 2 (before solver
  decisions were limited to the cones being compared), the whole-program
  run before solver recycling, which Experiment 5 compares against, the
  reference and steady-state runs before the hybrid refinement and while
  other runs shared the machine, and a whole-program rerun that was
  stopped.

## Reproducing

From this directory, with ABC, CaDiCaL, and Kissat installed (`abc`,
`cadical`, and `kissat` on the path):

```sh
./run_everything.sh        # about a day; appends to results/
./cadical_adversarial.sh   # needs network access for python-sat
uv run --frozen --python 3.14 python summarize.py operations
```

`run_everything.sh` builds `beq` and uses its own environment in
`work/venv`. The workloads are regenerated deterministically into `work/`,
which isn't kept (it reaches about 1 GB).
`.gitignore` excludes it and the built binary.
