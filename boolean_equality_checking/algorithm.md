# The Combined Algorithm

This is the one algorithm the measurements recommend, written so it could be
implemented in the compiler. It's `beq auto` in `src/main.cpp` and
`src/sweep.hpp`. Its measured performance is in
[experiments.md](experiments.md), Experiment 10.

## Input and Output

The input is the boolean statements of one value operation as an
And-Inverter Graph in DLP 57's statement order: one `and` node per `and`
statement, `not` as a complemented edge, executed boolean value operations
inlined (or replaced by what they compute), and every input (interface view
or result of a non-boolean statement) as a graph input. The same algorithm
runs on a whole program, but DLP 57 only needs it per value operation.

The output is the partition of the nodes into classes of equal functions,
modulo complement, with a phase for each node. A node's representative is
the smallest node in its class (the constant false node 0 counts, and so do
inputs). From that, a node is constant when its representative is node 0,
equal to an input when its representative is an input, and equal to an
earlier value when its representative is an earlier `and` node.

## Steps

Let I be the number of inputs and n the number of nodes.

1. **Read with structural hashing.** Each `and` of two literals that are the
   same as an earlier `and`'s (in either order), or that a trivial rule
   settles (`x and x`, `x and not x`, constants), is merged as it's read.
   Cost: O(n) with one hash table.
2. **Dispatch on I.** I is known from the statement list, so measuring it
   costs nothing.
   - **I ≤ 12: truth tables.** Compute every node's truth table over all I
     inputs (at most 64 words per node) and group nodes by their table,
     normalized so that the first bit is 0, with an exact comparison inside
     each hash bucket. Done. Cost: O(n · 2^I / 64) word operations, at most
     64 per node.
   - **I > 12: SAT sweeping**, the rest of the steps.
3. **Simulate.** 1,024 random input patterns (16 words), from a fixed seed.
   Each node gets a signature, normalized for complement. Only nodes with
   equal signatures can be equal. Cost: O(16 n).
4. **Sweep in statement order.** For each node v, build it in the reduced
   graph from its fanins' representatives (structural hashing again). If
   that finds an existing node, v is merged. Otherwise, for each earlier
   representative r with v's signature, skipping any r that a pending
   counterexample already separates from v, decide whether v = r (with the
   phase the signatures give) by the ladder in step 5. On "equal", v is
   merged into r and later nodes are built on r. On "different", the
   counterexample becomes a pending pattern; every 64 of them are simulated
   on the whole graph and the groups are rebuilt.
5. **The ladder for one pair.** Each rung either answers exactly or passes
   the pair on:
   1. If the cones of v and r read at most 12 inputs and have at most 512
      nodes, simulate every assignment of those inputs (exhaustive
      simulation). Answers always. The walk that measures the cones stops
      at the 13th input or the 513th node.
   2. SAT on the two cones in the reduced graph, with one incremental
      solver, up to 1,000 conflicts. The solver branches only on variables
      of the two cones when they have at most 4,096 nodes, and it's replaced
      by a fresh one past 100,000 variables (after which the threshold is
      four times what the first question needs).
   3. OBDDs of the two cones, inputs in first-use order, up to 4M nodes.
   4. If I ≤ 20, stop sweeping and go back to step 2's truth tables for the
      whole graph (at most 16,384 words per node).
   5. Otherwise, SAT with no limit on the two cones. The recommended solver
      here is Kissat (`--external kissat`, the CNF of the two cones in a
      temporary file): the built-in solver doesn't finish 11-bit multipliers
      in 120 s, while with Kissat they take 134–156 s and 12-bit ones
      878–1,150 s. Only 9 to 11 pairs per multiplier reach this step.
      With the limit of 20 boolean inputs per value operation (README.md,
      Decision 2), this step is never reached inside a value operation:
      step 5.4 always applies, so the worst case is the truth tables'.
      The Kissat timings above were measured before the rule that no check
      takes more than about 30 seconds, and only show what happens without
      the limit.

## Thresholds

| Threshold                     | Value     | Why                                                                                                                                                |
| ----------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Truth tables for the graph    | I ≤ 12    | Fastest exact method up to 12 inputs; at 16 inputs and 256 statements truth tables take 1.9 ms against 0.25 ms for sweeping (Experiment 1).       |
| Exhaustive simulation of a pair | ≤ 12 inputs | 8 to 12 was a tie; 16 made realistic operations slower (Experiment 1, `sweep_exhaustive`).                                                          |
| SAT before OBDDs              | 1,000 conflicts | The hardest call in any realistic operation needed 93 conflicts, so this never fires on them (Experiment 6), while it stops parity after milliseconds. |
| OBDD rescue                   | 4M nodes  | Large enough for 128-input parity and 10-bit multiplier cones; small enough to fail in seconds.                                                    |
| Truth tables as the last resort | I ≤ 20  | At most 52 ms for 256 statements and 120 ms for 1,024 at 20 inputs (Experiment 1); 24 inputs costs 0.5–2 s and up to 1.9 GB.                      |
| Scoped decisions              | ≤ 4,096 cone nodes | Walking larger cones on every call costs more than it saves (Experiment 5).                                                                |
| Solver recycling              | 100,000 variables, then 4× the first question | Only matters for whole programs (Experiment 5).                                                                              |

Trying an OBDD of the whole graph before sweeping was measured and rejected:
with a budget of 64 nodes per graph node it cuts the worst ratio to the best
budget from 249 to 9, but doubles the total time of realistic operations
(`results/dispatch_budget.txt`), and the cases it rescues (parity) cost only
milliseconds either way.

## How the Parts Combine

Every rung answers the same question, "is v equal to r with this phase, as
a function of the inputs?", exactly, or declines. Answers from different
rungs go into the same union-find and the same reduced graph, so a merge
proved by an OBDD is used by later SAT calls exactly like one proved by SAT,
and a counterexample found by any rung splits groups for all later pairs.
The truth-table switch in step 5.4 throws away the sweep's partial result
and recomputes everything with truth tables, which is simpler than merging
and costs at most what the truth tables cost anyway.

## Why the Result Is Deterministic

The partition of nodes into classes of equal functions is a property of the
graph alone. Every path through the algorithm computes it exactly: truth
tables, exhaustive simulation, and OBDDs are complete for what they decide,
SAT is run to completion on the last rung, and no rung ever merges two nodes
without a proof or separates two without a counterexample. The reported
representative of a class is its smallest node, which doesn't depend on the
order in which merges happened. So the thresholds, the seed, the solver, and
which rung decided each pair change only the time, never the answer.

The checks behind this: eleven exact configurations, including the combined
algorithm, the combined algorithm forced through its truth-table switch on
every hard pair, solver recycling every 300 variables, and every single
engine, gave identical classes on 300 random instances; three seeds gave
identical classes on all 113 instances that finished; every OBDD-first
budget gave identical classes on 143 instances; and every exact run of each
whole program agreed.

Time isn't deterministic in the same way: which rung a pair reaches depends
on conflict counts, which depend on the solver. That only matters if the
language bounds compile time by counting work, which these results argue it
shouldn't (see [arguments.md](arguments.md)). With a limit of about 20
inputs per value operation, the worst case is bounded by the truth-table
cost instead.

## Cost of Measuring and Choosing

- **Choosing between truth tables and sweeping** reads I, which is free.
- **Counting a pair's cone inputs** for exhaustive simulation walks the cones
  until the 13th input or the 513th node. With it and the OBDD rescue, the
  ladder makes sweeping faster, not slower, on realistic value operations
  (32 µs against 46 µs median at up to 256 statements), because simulating
  every assignment of a small cone is cheaper than a SAT call.
- **Failed rungs** cost what they spent before giving up: at most 1,000
  conflicts of SAT before the OBDD rescue (a few milliseconds), and an OBDD
  of up to 4M nodes before the next rung (up to a few seconds, only on
  multipliers here).

## Executions and Later Checks

The steps above take executed boolean value operations as inlined. The
follow-up studies measured two additions for a compiler that checks each
value operation once and keeps its result:

- **Refer to executions instead of inlining them** ([references.md](references.md)).
  Truth tables look up each execution's results in the executed operation's
  recorded table, and SAT treats an execution as an unknown function,
  refined where the solver's model disagrees with the recorded table: one
  clause for each of an execution's first four disagreements, then the
  executed operation's statements. Every refinement is exact, so the classes
  are the same as with inlining.
- **Store each operation's patterns** (the assignments of its views that
  showed two values distinct, at most one per value) and the hash of each
  written view's truth table, and simulate the patterns before step 4 on the
  next check ([steady_state.md](steady_state.md)). Check an operation again
  only when its text changes or the function of a written view of an
  operation it executes changes. Patterns only find counterexamples, so they
  change the time, never the classes.
