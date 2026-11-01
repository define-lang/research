# Checking Programs That Compile

Most of the time, the compiler checks value operations that compile: every
value is distinct from every other, from the constants, and from the views.
Showing that is the whole cost, because nothing can stop early. This study
measures that cost, the saving from stopping at the first redundant value,
patterns stored by one check and reused by the next, and how many operations
an edit makes the compiler check again.

**Short answer:** the combined algorithm already handles operations that
compile cheaply, and the solver is needed almost only for near misses:
values that differ from an earlier one on very few input combinations.
Storing the input assignments that showed values distinct removes almost all
of those solver calls on the next check, takes at most one assignment per
value, and is the one addition worth making. Stopping at the first redundant
value saves nothing on operations that compile and about a third on ones that
don't. An edit makes the compiler check a median of one operation again.

The code is `src/hier.hpp` (`beq hier --patterns_in/--patterns_out/
--stop_first`, `beq hier_edit`) and the driver `steady_state_experiment.py`.
The results are `results/steady_state.jsonl`, summarized in
`results/steady_state_tables.md` (`summarize.py steady`).

## Workloads

- **Flat value operations** like Experiment 1's, with 12, 16, or 20 inputs
  and 64 or 256 statements, five of each: ones that compile; ones with
  planted redundancies (`fails`); and ones that compile but have near
  misses (`near_cC`): about 5% of steps add `v or (a cube of C inputs)`, a
  value that differs from v on one combination in 2^C.
- **Libraries with references** (`gen/hierarchy.py`), eight levels of
  operations executing operations of the level below, with 10 or 14 views
  and three near misses per operation (cubes of 9 and 12 views). The
  `fails` libraries also execute twins (the same function written as a sum
  of products) on the same values, which are redundant values. They are
  checked with references and the hybrid refinement (see
  [references.md](references.md)).
- **Deep libraries for editing**: 10 views, three or four executions per
  operation, 10–14 levels, 91–113 operations.

## 1. The Cost of Showing Every Value Distinct

Flat operations through `beq auto` (median of five, each the best of three
runs; SAT calls and counterexamples are medians). Everything in this study
ran by itself on an otherwise idle machine.

| inputs | statements | operations | median  | slowest | SAT calls | counterexamples | truth tables |
| ------ | ---------- | ---------- | ------- | ------- | --------- | --------------- | ------------ |
| 12     | 256        | compiles   | 131 µs  | 135 µs  | 0         | 0               | 130 µs       |
| 12     | 256        | near_c10   | 155 µs  | 168 µs  | 0         | 0               | 160 µs       |
| 16     | 256        | compiles   | 193 µs  | 294 µs  | 58        | 1               | 1.48 ms      |
| 16     | 256        | fails      | 268 µs  | 604 µs  | 74        | 0               | 1.71 ms      |
| 16     | 256        | near_c14   | 779 µs  | 922 µs  | 114       | 29              | 2.03 ms      |
| 20     | 256        | compiles   | 207 µs  | 213 µs  | 64        | 0               | 30.7 ms      |
| 20     | 256        | fails      | 267 µs  | 1.18 ms | 62        | 0               | 30.7 ms      |
| 20     | 256        | near_c14   | 814 µs  | 989 µs  | 119       | 38              | 36.0 ms      |
| 20     | 256        | near_c18   | 1.21 ms | 1.61 ms | 197       | 74              | 33.0 ms      |

The full table, with 64-statement operations, is in
`results/steady_state_tables.md`.

- **An operation that compiles costs about as much as one that doesn't.**
  Simulation shows almost every pair distinct; there's no shortcut, but
  there's nothing expensive either.
- **Near misses are what the solver is for.** Random simulation finds a
  difference on one combination in 2^14 or 2^18 only by luck, so each near
  miss costs a solver call that returns a counterexample. They raise the
  cost 4–5 times, to about 1 ms.
- **The solver calls on operations that compile** (about 60 at 16–20
  inputs) are proofs, not counterexamples: equal internal nodes that come
  from writing `or`, `xor`, `mux`, and the others out as `and` and `not`
  (40–57 merged nodes per 256-statement operation). They aren't values of
  the operation. With registered operations referred to rather than
  copied, they wouldn't be in the graph at all; that's argued from the
  references study, not measured on flat operations.
- **Truth tables lose above 12 inputs** (31 ms at 20 inputs against
  0.21 ms), which is why the combined algorithm switches to sweeping there.

## 2. Stopping at the First Redundant Value

DLP 57 reports the first redundant value of an operation, so the check can
stop there. Totals for whole libraries:

| library      | every value | stop at the first | operations with a redundant value |
| ------------ | ----------- | ----------------- | --------------------------------- |
| compiles_v10 | 4.01 ms     | 3.97 ms           | 0 of 80                           |
| compiles_v14 | 29.5 ms     | 30.0 ms           | 0 of 73                           |
| fails_v10    | 10.7 ms     | 6.76 ms           | 29 of 80                          |
| fails_v14    | 40.6 ms     | 26.3 ms           | 32 of 73                          |

Stopping changes nothing for operations that compile, which have no first
redundant value, and saves 35–37% on libraries where 40% of the operations
fail. It's worth doing because it's free, but it does nothing for the steady
state.

## 3. Stored Patterns

A _pattern_ is an assignment of an operation's views that showed two of its
values distinct. The check stores the patterns its solver found, and the
next check simulates them before anything else. A pattern is stored only if
it separates values that the patterns stored before it don't, so each one
splits at least one class of values: an operation with n values has at most
n − 1 stored patterns, each one bit per view.

| library      | run                         | total time | SAT calls | patterns stored | most in one operation |
| ------------ | --------------------------- | ---------- | --------- | --------------- | --------------------- |
| compiles_v10 | first check                 | 4.01 ms    | 227       | 57              | 3                     |
| compiles_v10 | unchanged, with patterns    | 2.82 ms    | 0         |                 |                       |
| compiles_v10 | 23 of 80 edited, without    | 4.07 ms    | 253       |                 |                       |
| compiles_v10 | 23 of 80 edited, with       | 3.09 ms    | 42        |                 |                       |
| compiles_v14 | first check                 | 29.5 ms    | 1,330     | 496             | 14                    |
| compiles_v14 | unchanged, with patterns    | 16.0 ms    | 0         |                 |                       |
| compiles_v14 | 20 of 73 edited, without    | 28.5 ms    | 1,297     |                 |                       |
| compiles_v14 | 20 of 73 edited, with       | 16.6 ms    | 112       |                 |                       |
| fails_v14    | first check                 | 40.6 ms    | 1,557     | 496             | 14                    |
| fails_v14    | unchanged, with patterns    | 24.0 ms    | 394       |                 |                       |
| fails_v14    | 20 of 73 edited, with       | 23.2 ms    | 390       |                 |                       |

An edit negates one literal of one `and` in an operation.

- **On an unchanged operation that compiles, no solver call is needed**:
  the stored patterns separate every value. The remaining time (13.1 of the
  16.0 ms at 14 views) is recording each operation's truth table for its
  callers' lookups, which an incremental compiler would also store rather
  than recompute.
- **After edits, the solver is still needed for 8–17% of the calls**: for
  near misses and differences the edit created, and to prove the redundant
  values some edits created (5 operations at 10 views, 3 at 14).
- **Patterns are few**: at most 3 per operation at 10 views (9% of the
  bound) and 14 at 14 views (a third of the bound), so at most 14 × 14 bits.
- **Patterns don't help an operation that fails**: its redundant values
  need proofs, and a pattern can only show values distinct. That doesn't
  matter in the steady state.

## 4. Rechecking Through Calls

An operation needs to be checked again when its own text changes, or when an
operation it executes changes the function of a written view (its truth
table, compared by hash). An edit that keeps the function stops at the
edited operation. Over 400 random edits per library:

| library     | edit               | operations | rechecked: median | 90th percentile | most | time: median | slowest |
| ----------- | ------------------ | ---------- | ----------------- | --------------- | ---- | ------------ | ------- |
| deep_e3_l10 | keeps the function | 91         | 1                 | 1               | 1    | 12.3 µs      | 20.8 µs |
| deep_e3_l10 | changes it         | 91         | 1                 | 3               | 10   | 13.7 µs      | 150 µs  |
| deep_e3_l14 | keeps the function | 113        | 1                 | 1               | 1    | 13.0 µs      | 21.3 µs |
| deep_e3_l14 | changes it         | 113        | 1                 | 3               | 8    | 13.4 µs      | 105 µs  |
| deep_e4_l12 | keeps the function | 106        | 1                 | 1               | 1    | 15.8 µs      | 27.2 µs |
| deep_e4_l12 | changes it         | 106        | 1                 | 4               | 14   | 19.9 µs      | 257 µs  |

With references, a change in an operation's function reaches only its
callers, and each caller checked again is as cheap as the first check of it
(depth doesn't matter). The worst case is an edit to an operation executed by
every operation above it, which rechecks every caller once; with copying,
the same edit would recheck every caller at the cost of its whole copied
graph.

## The Algorithm for Programs That Compile

The combined algorithm doesn't need to change; three additions make the
steady state cheap:

1. **Refer to executions** rather than copying them, with truth-table
   lookups up to 16 views and the hybrid refinement for SAT
   ([references.md](references.md)). This also removes the internal
   equalities that writing registered operations out creates.
2. **Store each operation's patterns and the hash of each written view's
   truth table** with its compiled result, and simulate the patterns first
   on the next check. Unchanged operations that compile then need no solver
   call.
3. **Check again only operations whose text changed, and their callers
   while the function of a written view changes.**

All three rely on every executed operation having passed its own check
already, where it's defined, which means a caller's check is about the
caller's values only, never the executed operation's other values. It
doesn't make an execution's results safe in the caller: with related
arguments, 26–44% of random executions had a result that was redundant
there, so the results are checked like the caller's own values, and the
executed operation's patterns, which are assignments of its own read views,
don't carry over ([references.md](references.md) has the measurements).

With all three, a check after an edit costs about one operation's first
check (tens of microseconds to a millisecond), and the solver runs for the
near misses the edit introduced. Each addition was measured separately here;
the combination is argued from those measurements. Results stay
deterministic, because patterns only speed up the proof of what is already
true: the classes are the same with or without them (`partition_hash` is
identical in every run of the same library).

## What's Measured and What's Argued

Measured: everything in the tables, on generated workloads. Argued: that the
internal equalities on flat operations disappear with references; that the
three additions combine as described; and that real programs have as few
near misses as these workloads (each near miss costs one solver call on the
first check, so a program written with many could cost more, though stored
patterns still remove those calls afterward).
