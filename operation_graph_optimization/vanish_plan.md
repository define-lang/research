# Vanish collection investigation

Preserve the archived position-dependency implementation and measurements. Add
Vanish experiments as separate files; do not modify the compiler or spec.

1. Specify resolved particle-use inputs and the exact Vanish result.
2. Compare deferred collection, incremental antichains, and local dependency
   pruning. Charge collection and maintenance time, not just final Comparison.
3. Check exact dependencies against an independent reachability oracle. Exercise
   real Define source, implied and interface access, retained destructor state,
   direct movement, replacements, and simultaneous Vacates.
4. Generate reproducible, randomized valid operation orders at large scale.
   Separate generation and validation from timed graph construction; measure
   total construction, Vanish overhead, final edges, and peak resident memory.
5. Preserve raw repeated measurements and explain trade-offs. Deliver a rule
   description and a standalone implemented algorithm, without claiming a
   universal fastest algorithm from benchmark wins.
6. Run formatting, lint, types, integration checks, and coverage. Leave all
   investigation changes uncommitted.

## Completed

The result is `vanish_rules.md` and `vanish_algorithm.py`. The investigation
compared deferred collection, direct pruning, incremental antichains, last-Move
summaries, and ordinary-occupancy coverage. `vanish_experiments.md` records the
trade-offs, failed and interrupted experiments, reproduction commands, and
limits of the optimality claim.

The research repository's four test targets pass, including 144 Vanish cases.
The final algorithm has full line and branch coverage. Source snapshots and raw
measurements are preserved. The compiler and spec were not changed, and nothing
was committed.
