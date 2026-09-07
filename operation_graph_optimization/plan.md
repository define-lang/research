# Operation Graph Optimization Plan

## Additional state-driven experiments

The initial performance families randomized choices within structured patterns;
they did not freely mix all valid operation kinds. The additional experiment
uses a state-driven sampler, with every valid caller choice in its declared
fixture selectable independently of storage order. Small source-based tests
compare all selectable choices against exhaustive enumeration, shuffle the
collections, validate both original and reordered source, and compare exact
graphs with an independent reference. Large runs vary seeds and operation-kind
distributions and include independent input-order randomization.

The generator and checks are implemented in
`operation_graph_optimization/state_workloads.py`,
`operation_graph_optimization/order_variants.py`, and
`operation_graph_optimization/state_workloads_integration_test.py`. Their exact
scope and reproduction commands are in
`operation_graph_optimization/state_workloads.md`.

The growth-heavy distribution exposed slow reachability work in the baseline
algorithm. The follow-up investigation specializes collection across all reasons
for a candidate, reuses collected candidates as pruning witnesses, and improves
Comparison and bounded reachability caching. Its experiments are recorded in
`operation_graph_optimization/optimization_experiments.md`. Preserve the
baseline failures: later successful measurements do not turn those failures into
passes or prove universal time optimality.

## Objective and deliverables

Discover an efficient rule set equivalent to Define's specified Particle
Operation Dependency Graph rules, and implement that rule set in Python. Finish
both the rule derivation and its implementation, rather than stopping after an
interesting intermediate result or waiting for a review checkpoint. Do not
commit the investigation or modify the compiler in this checkout.

The investigation produces:

- `operation_graph_optimization/rules.md`: a concise, human-readable rule set
  suitable for a language specification. Define every new mathematical object
  needed to apply the rules. Explain their scope and correspondence to the
  existing semantics without turning them into implementation instructions.
- `operation_graph_optimization/algorithm.py`: the implemented rule algorithm,
  divided into understandable functions or objects. Put supporting data
  structures and infrastructure in separate Python files where that clarifies
  the algorithm.
- Supporting correctness checks, reproducible workloads, benchmark commands, and
  complexity evidence sufficient to justify the result. These support the two
  deliverables; neither deliverable should be buried in a benchmark harness.

The algorithm only needs to handle valid Define programs. Do not spend its time
or memory rechecking guarantees already supplied by language validation.

## 1. Fix the semantics and define optimality

Read the complete current specification, the conceptual particle and position
definitions, the English proofs, and the shared execution design. Record the
precise input contract and required result before selecting data structures.

Preserve actual reference requirements, particle identity, positions moving with
their defining particles, simultaneous vacancies, shared destructor state, and
destructor lifetime protection. Distinguish an ordinary position requirement
from continued particle existence. Do not introduce ancestor dependencies,
whole-action barriers, per-destructor snapshots, or guarantees from future value
or external-call semantics.

Separate the whole-program rules from the Action Parent Rule used for modular
analysis. Fix a permitted destructor conflict orientation when comparing exact
graphs. Different permitted orientations are separate optimization choices, not
evidence that one implementation is wrong.

Define the cost model and input representation. Track at least:

- Number of distinct source operations and number of expanded operation
  occurrences; do not confuse these when actions are reused.
- Total reference length, active particles and positions, and action-call
  structure size.
- Number of requirements, candidate dependencies, and final dependencies.
- Peak memory, retained analysis state, and temporary allocation volume.

Distinguish unavoidable cost for an explicitly requested graph from unnecessary
expansion. Investigate whether modular or shared results can avoid materializing
all occurrences without changing what the consumer requires.

Optimize time first, subject to memory remaining feasible for real compilation
of very large programs. Extra memory is worthwhile when it improves time and its
growth remains tenable at the intended scale. Do not choose a slower algorithm
solely because it uses less memory, and do not accept an otherwise fast
algorithm whose memory growth makes large compilations impractical. Measure
total resident memory, not just the nominal data-structure size, and account for
the rest of the compiler's memory needs.

Establish lower bounds where possible. An explicit graph requires time to emit
its edges, but its edge count alone is not a proved bound on the work needed to
discover those edges. Do not call a result optimal merely because it is the
fastest implementation tested. An optimality claim must identify its cost model,
input class, and matching lower bound. Where time and memory trade off, identify
the relevant alternatives instead of claiming a universal optimum.

## 2. Build an independent correctness reference

Implement a small, direct interpretation of the existing requirements,
Collection, and Comparison. Favor clarity over speed. Keep it independent from
the optimized algorithm and avoid sharing the logic whose correctness it is
supposed to check.

Use real valid Define programs to exercise the interpretation. The real compiler
may validate source, but its current operation graphs are not a correctness
oracle. Preserve the distinction between source-validation success and
operation-graph correctness. If compiler defects obstruct validation, use a
separate worktree for any compiler changes and check them there.

Validate small graphs independently by examining permissible schedules and
checking operation requirements. Check equality with the reference graph,
acyclicity, completeness, and necessity of each final edge. Brute-force methods
are appropriate for bounded validation, not for the resulting algorithm.

## 3. Derive the necessary information

For each future operation, determine exactly which facts about preceding
operations can change its dependencies. Derive sufficient state, and justify
every proposed deletion, sharing decision, or implicit representation.

Investigate:

- Tracking the most recent occupancy change and preceding uses, including
  particle-creation requirements.
- Representing positions by their defining particles so that a Move need not
  visit all transitive children merely to rename positions.
- Determining whether earlier uses can be kept as a compact dependency frontier
  rather than a full list; prove that pruning preserves all necessary orders.
- Representing simultaneous selections and original shared destructor state
  without copying complete particle structures or confusing saved vacancies with
  current references.
- Releasing analysis records after their final possible use without retaining
  the full program unnecessarily.
- Reusing action analysis and handling large call-graph fan-in and fan-out.
- Separating dependency construction from the analysis needed to retain
  particles through destructor interactions, while accounting for both costs.

For each representation, specify its invariants, updates, ownership, and
complexity. First derive these in English; formalize the important correctness
claims afterward.

## 4. Discover efficient Collection and Comparison rules

Explore alternate rules, not just faster implementations of the current wording.
Consider separate rules for Create, Move, Destroy, filling, emptying, the
availability of defined positions, and the end of their availability. Look for
operation-specific invariants that eliminate general Comparison work. The
current requirement-based formulation is an equivalence reference, not a
restriction on the shape of the result. Adopt a specialized rule only after
deriving its exact correspondence and testing its boundary cases.

Characterize the candidate sets and graphs actually reachable from valid Define
code. Do not assume that they are trees, have bounded width, or belong to any
other convenient graph class without proof.

Investigate whether those constraints permit local summaries, frontiers,
dependency labels, or other compact information to answer Comparison's
questions. Analyze invalidation and maintenance costs, not only query costs.
Compare alternatives against the simple reference. Retain candidate alternatives
only while they answer a concrete unresolved question.

Research established algorithms and lower bounds for the precise mathematical
subproblems found. Reuse results only after matching every hypothesis. Record
whether a valid-source construction can realize a difficult general graph
problem; this determines whether an attractive complexity target is plausible.

The construction must directly produce the transitively minimal dependencies. Do
not create a redundant full graph and then apply a generic transitive
minimization algorithm. An alternate rule formulation is acceptable only with an
equivalence proof, not because examples agree.

## 5. Implement and validate competing algorithms

Implement concrete alternatives outside the compiler, using separate supporting
data structures where useful. Optimize the actual rule algorithm, not a
benchmark-specific approximation. Document the boundary between prevalidated
input and algorithm responsibility.

Use integration-style checks with real Define source for semantic cases.
Additionally use generated operation structures for differential checking and
large-scale experiments. Derive their validity from explicit generation
invariants; arbitrary random directed acyclic graphs are not automatically valid
Define workloads.

Cover direct implied versus written chained access, occupancy reuse, Moves with
concurrent child operations, multiple requirements supplied by the same
operation, candidates implying other candidates through several positions,
simultaneous destruction, replacements, shared destructor modifications,
destructor-created particles and subsequent destruction, and reused actions.

Randomize source-generation choices and permitted operation orders. Compare
graph results by operation identity, not incidental enumeration. For a fixed
semantic input and conflict orientation, randomize processing only where the
input contract permits it. Separately randomize runtime topological schedules to
check their safety. Do not demand the same graph after changing meaningful
serial order or choosing a different destructor orientation.

Minimize every discovered counterexample into an understandable source example
or a justified valid-input construction. Correct the derivation before updating
the optimized implementation or accepting new expected graphs.

## 6. Stress time and memory at the intended scale

Benchmarks may run the standalone algorithms directly; they need not repeatedly
compile Define source. Validate representative source separately and account for
the cost of translating it into the algorithm's representation. Measure both the
rule algorithm alone and the end-to-end representation costs so that work cannot
disappear into preprocessing.

Include enormous operation graphs, reaching millions of operations where the
machine permits, with randomized operation orders and multiple reproducible
seeds. Bound each run by explicit memory and time budgets and increase scale
progressively. A resource-exhausted run is evidence about an algorithm, not a
reason to exhaust the host repeatedly.

Include long chains, wide independent sets, large fan-in and fan-out, layered
graphs, many preceding uses before vacancy, overlapping requirement sets, deep
references, repeated Moves, large simultaneous destruction selections, shared
destructor access, and repeated action calls. Include cases with few final edges
but many candidate or ancestry relationships, and cases with necessarily large
results. Only attribute a workload to Define when its validity is established.

Randomize permitted serial choices, ready-operation selection, independent
branch interleavings, identifier assignments, and data-structure insertion
order. Do not accidentally benchmark only one favorable topological ordering. At
huge scale, use proven generation invariants and scalable checks; reserve
exhaustive schedule enumeration and the slow oracle for smaller instances.

Separate workload generation, source validation, preprocessing, graph
construction, and result verification timings. Measure wall time, peak resident
memory, allocation-heavy behavior, and scaling as each input parameter grows.
Use repeated runs and report distributions, machine details, seeds, and
commands. Check Python-specific constants and garbage collection without letting
favorable small-input timings override an infeasible asymptotic bound.

## 7. Converge on the rule set and implementation

Use counterexamples, proved bounds, and measurements to refine the rules and
their representation together. Repeat derivation, implementation, verification,
and stress testing until no required semantic or algorithmic obligation remains.
Do not pause for user review between alternatives or at an intermediate proof.

If a proposed rule fails, reject or repair it rather than weakening the required
graph. If a performance claim fails, change the algorithm or revise the claim
explicitly. Do not conceal a gap between an upper and lower bound by labeling a
candidate optimal. Investigate that gap and make any eventual claim only for the
model and workload class actually established.

Choose the fastest justified implementation whose memory growth and measured
usage remain feasible at the intended scale. Remove superseded implementations
and speculative abstractions from the final algorithm; retain only the
independent reference and genuinely useful comparison infrastructure separately.

## 8. Completion and handoff

The investigation is complete only when:

- The final rule document is understandable without reading Python and is
  sufficient to determine the required graph for valid input.
- The Python implementation actually implements those rules, with no missing
  algorithm delegated to a placeholder or unspecified oracle.
- Semantic correspondence, independent completeness and minimality, and safe
  concurrency for the chosen orientation are justified.
- Time and memory claims include all representation and maintenance costs.
  Optimality is supported within an explicit model, not asserted universally
  from benchmark wins. Any unresolved optimality claim remains unfinished work.
- Source integration checks, differential checks, randomized schedules, and
  large adversarial benchmarks pass with reproducible evidence.
- Files are formatted, linted, dependency-correct, and verified using the
  repository's applicable build, test, and coverage mechanisms.
- The main checkout's compiler has not been changed by the investigation, and
  the investigation artifacts remain uncommitted.

Deliver the two result locations, their precise guarantees and complexity
bounds, and the validation and benchmark results. Do not substitute a proposed
algorithm or a benchmark report for a completed rule implementation.

## Recorded result

The requested rebase, proof cleanup, package-cache ignore, and proof commit are
complete. The proof commit is `3a2b6a0d4` after the subsequent rebase; its build
wiring and the `proofs/` directory are clean. The backup stash was preserved.

The standalone [rules](operation_graph_optimization/rules.md) and
[implementation](operation_graph_optimization/algorithm.py) are implemented,
with [derivations](operation_graph_optimization/analysis.md), an independent
reference, source integration checks, and
[reproducible measurements](operation_graph_optimization/benchmarks.md). The
investigation has not modified the compiler and remains uncommitted.

The supported conclusion is a semantics-preserving, transitively minimal rule
construction and a measured time-first implementation with bounded auxiliary
indexing. The mathematical lower-bound investigation also gives a valid-source
construction expressing arbitrary directed-acyclic-graph reachability questions.
It does not yield a matching lower bound for the complete implementation.
Universal time optimality therefore remains unproved; the stronger optimality
criterion above is not claimed to have been met merely by winning benchmarks.

The follow-up performance investigation is also complete. Its default uses
creation coverage across collection reasons, collected-candidate use pruning,
equal-height shortcuts, bounded pairwise/shared Comparison, and range-sized
reachability columns. The 1,024-target limit still shares a 64-MiB logical
budget. The previously timing-out million-statement growth workload now
completes graph construction in about 24 seconds; movement-heavy inputs remain
about 6–8% slower than the baseline. These trade-offs and all recorded data are
in
[the follow-up report](operation_graph_optimization/optimization_experiments.md).
The 55-run preliminary matrix and 33-run final matrix passed, as did all 357
repository-wide coverage targets; no actionable investigation branches remained
uncovered. This completes the experimental implementation work, not a claim of
universal time optimality. No investigation changes were committed.
