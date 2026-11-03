# Boolean Equality Checking

What is the most efficient way for the Define compiler to find, exactly, which
boolean values in a program always equal each other, which are constant, and
which equal one of their inputs? This is what DLP 57's rules against
"redundant values" and "writing the same logic twice" need. This directory
answers it by experiment: it implements the candidate methods in C++, runs
them on generated workloads from tens of statements to seven million nodes,
compares them with ABC, CaDiCaL, Kissat, and SDDs, and measures time, memory,
and how many planted equalities each one finds.

- [algorithm.md](algorithm.md): the one combined algorithm the measurements
  recommend, with its dispatch, thresholds, and why its result is
  deterministic.
- [experiments.md](experiments.md): the setup, every results table, and what
  each shows (Experiments 1–11).
- [arguments.md](arguments.md): the conclusions that come from reasoning
  instead of measurement.
- [related_work.md](related_work.md): a literature search on how close
  existing systems and papers come to DLPs 57–59 and these algorithms.
- Follow-up studies:
  - [matching.md](matching.md): whether DLP 57's rule against writing out a
    registered operation could be exact.
  - [references.md](references.md): checking value operations that execute
    others by referring to each execution instead of copying it.
  - [steady_state.md](steady_state.md): the cost of checking programs that
    compile, stored patterns, and rechecking after edits.
  - [earlier_values.md](earlier_values.md): an exact match definition over
    values computed earlier, its cost, and whether fixing equivalent
    programs until they compile makes them the same program.
  - [precedence.md](precedence.md): a precedence rule between equivalent
    spellings of a value, and whether it makes the fixes converge.
  - [full_algorithm.md](full_algorithm.md): every check of DLPs 57–59 at
    once on whole generated programs that follow the rules, with the fix
    loop that makes them compile, and the fewest `and`s of every function
    of up to four views, which orders registered operations (DLP 59).
    Checking and fixing are linear: 18.1 s to check 150,000 operations
    and 164 s to fix them.
  - [proof/termination.md](proof/termination.md): a proof, in English and
    in Lean (`proof/fixing_termination.lean`), that fixing a program under
    DLP 57's and DLP 59's rules always terminates, including removing read
    views that don't matter and writing out the executions that would make
    a match's fix an execution cycle.

## Recommendations

### Within One Value Operation

This is what DLP 57's rules need, and it's the case to optimize.

**Decide equality exactly, over the whole value operation, with truth
tables** ([algorithm.md](algorithm.md)):

1. Structural hashing as statements are read.
2. With at most 20 inputs (DLP 57's limit), truth tables of every value,
   executions looked up in the executed operation's recorded table or
   written out when that's small. Done.

DLP 59's matches need every value's truth table anyway, so at 13–20 inputs
the SAT sweeping the earlier studies recommended there saves at most the
time of grouping tables by function, and costs much more on a first check
with no stored patterns: on whole programs of 16–20-input operations, 44 s
against 1.5 s ([full_algorithm.md](full_algorithm.md)). The truth tables
take at most 52 ms for 256 statements at 20 inputs, and up to 98 ms for
an operation that executes several 16–20-view operations; the whole
2,000-operation program of them checks in 19.6 s. Truth tables are
exact and deterministic, so the classes are a property of the graph.

What the earlier studies measured beyond that, for value operations past
20 inputs or programs checked as one graph: SAT sweeping, with a ladder of
exhaustive simulation, SAT up to 1,000 conflicts, OBDDs, and SAT with no
limit (Kissat). Every rung is exact and a class's representative is its
smallest value, so thresholds, seeds, and which engine decided a pair
change only the time (eleven exact configurations gave identical classes on
300 random instances).

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

**What the cheaper methods miss.** DLP 57 currently defines a redundant value
over cuts of at most four values. On the generated operations of up to 256
statements, that finds 58% of the planted redundancies. It misses most of
the ones that aren't local: 62% of whole-cone rewrites, 70% of case splits,
86% of absorptions of a rewritten value, 71% of contradictions with one.
Structural hashing finds 29%, and the normalized AND-of-literal-sets form
31–34%. Exact checking finds all of them, and is faster than enumerating DLP
57's cuts past a few dozen statements.

**The worst case.** Exact checking is coNP-hard, and DLP 57's limits don't
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
- **Keep matches of registered operations defined over cuts of at most four
  values** ([matching.md](matching.md)). An exact definition of "writing out
  a registered operation" is decidable (0.75–2.5 s per 256-statement
  operation, against 2–3 ms for cuts) but flags 34–47% of all values in
  operations the cut rule nearly accepts, almost all of them coincidences.
  One extension is worth adopting: let a cut's value be given to the
  registered operation as its `not` when the program has that `not` (it
  finds the 4% of planted matches cuts miss, with few extra matches, at
  about 1.4× the time). The four-view limit is justified by cost: every
  added view multiplies the cost of finding every match by 7–18. Overlapping
  matches can be ordered without a solver: by size, then value, then
  operation name, then argument rank.
- **An exact definition over earlier values** ([earlier_values.md](earlier_values.md))
  treats those flagged values as second ways of writing them. Searched the
  way Boolean resubstitution finds divisors, it checks a value operation
  that compiles in 1.4–5.7 ms at 12–16 inputs and 8–18 ms at 20, with
  matches sized by the statements fixing them removes, which also makes
  fixing terminate. But it doesn't give one way to write a program: fixing
  equivalent programs until they compile reached one program in at most
  1 of 8 families when registered operations were written out, and no order
  of fixes changed that. A precedence rule between spellings
  ([precedence.md](precedence.md)) needs one restriction to terminate (no
  fix may grow the program), costs about 50% more checking, and still
  doesn't make them converge.

No restriction can make exact checking polynomial without making some
functions need exponentially more code, unless P = coNP: any two AIGs can be
rewritten into a restricted form in polynomial time, so checking the
restricted form is still coNP-hard ([arguments.md](arguments.md)). The input
limit escapes this only because it moves part of the program out of what's
checked.

### Executions of Other Value Operations

**Refer to an execution instead of copying it**
([references.md](references.md)). Copying every execution into its caller
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
be shown distinct and nothing can stop early ([steady_state.md](steady_state.md)):

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
programs (experiments.md, Experiment 11), 150,151 value operations with
3.5 million values took 2.0 s and 178 MB from nothing, about 13 µs per
operation, and a random edit made the compiler check a median of one
operation again (at most 18), in 42 µs. A 2,000-operation program of
16-view operations, which go through SAT, took 2.8 s, and 1.6 s again with
stored patterns.

### Across a Whole Program

**DLP 57 doesn't need it.** Its rules are about one value operation, with an
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

1. **What DLP 57 guarantees.** Decided: a redundant value is one that's
   equal, as a function of the value operation's inputs, to a constant, an
   input, or an earlier value. This is exact, finds every planted redundancy,
   and the portfolio took at most 1 ms on the generated operations within DLP
   57's limits. The rejected alternative kept the current definition over cuts
   of at most four values, which misses 42% of planted redundancies and took
   1–3 ms.
2. **Bounding the worst case.** Decided: the boolean statements of one value
   operation can use at most 20 different boolean inputs. A boolean input is
   any boolean value those statements read but don't compute: a boolean view
   of the value operation, the result of a non-boolean statement (such as
   `x < 3`), or the result of executing a value operation that isn't a
   boolean value operation. An executed boolean value operation counts as the
   logic it computes, so only the values passed to it count. The compiler
   counts the inputs in one pass over the statements and reports the
   statement that first uses the 21st, so the check doesn't depend on any
   solver.
   - **Why 20.** The measurements give a cost curve, not a number. Truth
     tables decide everything exactly in time that depends only on the number
     of inputs and statements, doubling with each input: at 256 statements,
     2 ms at 16 inputs, 52 ms at 20, and 0.5–2.3 s at 24. The number 20 is a
     choice of about 50 ms as the worst case for one value operation, and it
     is provisional until real programs exist to measure.
   - **The cost.** The limit counts inputs, not difficulty, so easy logic that
     combines more than 20 conditions has to be split so that some of it is
     computed by statements that aren't boolean statements, since an
     executed boolean value operation counts as its logic. Related
     comparisons such as `x < 3` and `x < 5` count as two inputs.
   - **The rejected alternative** was no limit, under which a value operation
     that writes bit-level arithmetic two ways can take minutes or more to
     compile.
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
  DLP 57's statement order, reuse standard compositions, and contain no
  redundancy except what was planted, but they're random. How many boolean
  inputs real value operations have, which decides whether a limit of 20
  is comfortable, is unknown, and so is how many near misses real code has.
- That exact checking has no polynomial worst case under any restriction
  that keeps succinctness, and that DLP 57's limits don't bound it (the
  multiplier-from-blocks construction in [arguments.md](arguments.md) wasn't
  built).
- That exclusive or, majority, or if-then-else primitives wouldn't help.
- That the values the exact definition of a registered-operation match flags
  are coincidences, from inspecting examples, not all of them.
- That stored patterns, references, and incremental rechecking combine as
  [steady_state.md](steady_state.md) describes; each was measured
  separately. Also, that recording OBDDs instead of truth tables would avoid
  the 2^20 cost of references at 20 views.

## Files

- `src/`: the C++ implementations, built into `beq` by `build.sh`.
  - `aig.hpp`: graphs, AIGER, width, the union-find every method reports
    through.
  - `sat.hpp`: the CDCL solver. `bdd.hpp`: OBDDs with complement edges.
  - `structural.hpp`: structural hashing, the normalized form, DLP 57's
    cuts. `functional.hpp`: truth tables, OBDD equality.
  - `sweep.hpp`: SAT sweeping with the combined algorithm's ladder.
  - `match.hpp`: registered-operation matching (cuts, the first exact
    search, and the search over earlier values).
  - `hier.hpp`: libraries of operations that execute each other, with
    references, copying, stored patterns, and rechecking after edits.
  - `main.cpp`: the `beq` command.
- `gen/`: workload generators and helpers. `aig_builder.py`, `workloads.py`,
  `matching.py`, and `hierarchy.py` generate; `generate.py` is their command
  line; `verify.py` checks a method's classes with CaDiCaL;
  `cadical_miter.py` times CaDiCaL on planted pairs; `sdd_compile.py`
  compiles with SDDs; `caller_redundancy.py` counts executed operations'
  values that are redundant in their callers; `fixpoint.py` represents
  value operations as programs and applies DLP 57's fixes until they
  compile; `aiger.py` reads AIGER.
- Drivers: `experiments.py` (Experiments 1, 2, 4, 5, and 10),
  `check_methods.py` (compares all methods), `dispatch_budget.py`,
  `abc_compare.py`, `native_solvers.py`, `sdd_compare.py`,
  `matching_experiment.py`, `hierarchy_experiment.py`,
  `steady_state_experiment.py`, `caller_redundancy_experiment.py`,
  `resub_experiment.py`, `fixpoint_experiment.py`,
  `final_program_experiment.py`, `cadical_adversarial.sh`, and
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
