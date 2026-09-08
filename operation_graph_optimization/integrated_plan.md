# Integrated operation graph investigation

Preserve the earlier source snapshots and measurements. Do not change the
compiler, spec, or commit files.

1. Compare complete implementations, not just Vanish collectors: reuse position
   Collection or Comparison for lifetime pruning, compare no lifetime pruning,
   and avoid indexing terminal Vanishes for future reachability queries.
2. Validate every position edge against the independent full-history interpreter
   and every Vanish against all actual particle requirements. Exercise real
   Define source, retained destructor state, replacements, implied and interface
   access, simultaneous Vacates, and randomized valid orders.
3. Measure entire construction in isolated processes, excluding input generation
   and conversion. Use repeated randomized trials, million-operation workloads,
   completed growth, wide independent uses, and chains of names. Compare full
   graph digests and report failures and time/memory trade-offs.
4. Deliver self-contained complete/algorithm.py and complete/graph.py for
   the design directory, with no dependency on the archived implementations.
   Keep experimental machinery separate from those deliverables.
5. Run formatting, type checking, integration tests, and repository coverage.
   Record evidence and limitations rather than claiming universal optimality.

## Completed

The deliverables are in `complete/`; `integrated_experiments.md` records the
alternatives, measurements, source-workload correction, and trade-offs.
All 523 measurements succeeded with matching per-input graphs. The 444-case
integrated suite passes, and both standalone production files have full line
and branch coverage. No compiler/spec files were changed and nothing was
committed.
