# Dependency Redesign Plan

## Working rules

- **Do not commit or push any work.**
- **Do not edit the spec. The user will update it after this plan is complete.**
- **Construct the minimal graph incrementally while walking serial Define code.
  Do not use general search, enumerate execution orders, or resolve combinations
  of possible orders in compilation or at runtime.** Exhaustive search belongs
  only in independent small-case test oracles. Derive maintained records and
  operation-specific update rules, including rules for alternative prerequisites
  and their coordination. This restriction also applies to Vanish construction.
- Maintain [core_rule_changes.md](core_rule_changes.md) as a concise, complete
  list of necessary rule changes. After each discovery, reconsider and rewrite
  the whole set rather than appending corrections or historical alternatives.
  Describe concrete replacements or additions to the spec's algorithm, including
  how to calculate dependencies and relationship conditions, not merely the
  properties the result must satisfy.
- Maintain
  [dependency_construction_details.md](dependency_construction_details.md)
  separately for constructions, optimizations, bookkeeping, and their evidence.
  Replace superseded details; do not inflate the core changes with them. Both
  documents are temporary working artifacts; do not list them in README.md.
- **Do not modify DLP 44 unless the user explicitly requests that edit.**
- **Once execution begins, continue through the entire plan without review
  checkpoints or voluntary pauses. Stop only when the user's input is
  necessary**, for example to resolve a semantic choice, an unavoidable scope
  change, or a genuine external blocker.
- Preserve unrelated work in both repositories.
- Develop each English argument before its Lean formalization.
- Do not change production compiler behavior or existing graph expectations
  until the complete replacement rules have been derived and validated.
- Requirements describe semantics; implementation choices must not supply
  additional semantic premises.
- Treat the five
  [Principles in DLP 44](../../../../../proposals/00044-deterministic-automatic-concurrency.md#principles)
  exactly as written as the governing design requirements. Derive additional
  constraints rather than silently introducing additional principles.
- Before asking for input, investigate the root cause and resolve it from the
  principles and specified semantics where possible. Ask for a language-design
  decision only when they leave a genuine choice unresolved.
- For semantic questions, show the Define source first, with explanatory
  comments above the relevant statements. Follow it with complete scheduling
  tables using integration-test operation names and a column for each particle's
  current position after every step. Distinguish retained occupancy, detached
  particles, particles not yet created, and Vanished particles. Define any
  particle-relative notation needed when no local position name can describe a
  particle's position.

- Preserve alternative sufficient prerequisites with Fan In (any), alongside Fan
  In (all) and Fan Out. The runtime names are `FirstArrival`, `Join`, and
  `Fanout`. Do not replace an alternative with an arbitrary fixed predecessor.
- For every newly encountered situation, check for a pre-existing operation
  graph integration test. If none covers it, add a case under `define/testdata`
  with an owning operation graph integration test, using only the normal
  testdata fixtures and dependency assertions. Do not add custom
  schedule-enumeration helpers or alternate integration-test machinery. Track
  unsupported behavior explicitly rather than accepting the existing compiler's
  graph as the expected result. For new constructs, use provisional dependency
  notation or put a TODO beside the dependency that cannot yet be expressed; do
  not defer the test or invent custom test machinery. Put comments directly
  above the relevant expected dependencies, explaining the concurrency behavior
  being tested for a human reading the assertion. Custom experiments and test
  machinery are permitted in the research repository; this restriction applies
  to compiler integration tests.

## Execution sequence

Establish the requirements, then state candidate rule changes in the core-rule
document and explicit constructions in the construction-details document before
attempting to prove them. Develop English proofs and algorithms together,
refining these documents as either line of work reveals problems. Steps 3
through 6 form this refinement loop, not separate phases that postpone algorithm
research until the proofs are complete. Complete Lean formalization after the
English proofs, rules, and implementation have settled, then verify their final
correspondence.

If formalization or final validation exposes a defect, return to the relevant
step, correct the proposed rules and English argument first, and update the
affected implementation, formalization, and measurements. Do not leave that work
for a later project.

## 1. Establish the complete semantic requirements

Review [dependency_requirements.md](dependency_requirements.md) against the five
DLP 44 principles and the whole spec. Distinguish the principles themselves from
consequences that must be derived using the specified operation effects. Resolve
every relevant case:

- Particle identity, position identity, assigned qualities, and replacement
  particles.
- Creates, direct Moves, ancestor Moves, Vacates, and Vanishes.
- Source ordering of successive occupants of the same actual position, including
  complete Create/Vacate pairs. Preserving selected particle identities and
  final vacancy alone does not permit those pairs to exchange order.
- Empty child positions and arbitrarily long reference chains.
- Local, implied, and interface positions.
- Action Requirements, Guarantees, action identity, and repeated Action
  Executions.
- Simultaneous Transitive Destruction, shared retained state, overlapping
  destructor access, nested destruction, and temporary particles.
- End occupancy preservation after the selected Vacate and the last required
  destruction use, without waiting for Vanish or unrelated uses of the
  particle's own positions. Check overlapping destructors and the actual effects
  of the operation that completes that last use.
- Creation and Vanishment of particles providing positions or actions.
- Changes to transitive parent/child relationships, including Moves with
  disjoint endpoints that would violate principle 3 in one execution order.
- Locally permitted relationship changes that would prevent completion of later
  required operations. Include Automatic Destruction in this analysis; do not
  infer deadlock from a subset of the operation graph.

Define precisely which positions each operation changes or observes and which
particles it requires alive. Establish when an intermediate reference identifies
something without imposing an occupancy or lifetime requirement of its own.

Do not make occupancy and existence an exhaustive independence criterion.
Principle 2 preserves the relationship of child positions to their defining
particle, not a fixed relationship between parent and child particles. Derive
the consequences of principle 3 for each execution step and of principle 5 for
the logical result. Include local positions through their action and its parent
particle without assuming a lifetime rule from that association alone.

Keep storage addresses, runtime identity delivery, allocation, and scheduling
mechanisms in implementation design.

**Completion condition:** every operation and relevant reference form has
explicit requirements, with no undefined "actual use" or implicit
ancestor-retention rule, and every additional constraint has a derivation from
the principles and specified operation effects.

## 2. State candidate changes and define their mathematical model

Use the requirements from step 1 to maintain the two design documents. The
core-rule document lists only necessary changes to rules, written concisely for
a human reader. Put the explicit candidate construction, representation choices,
and optimizations in the construction-details document.

Construct a precise mathematical model from the unchanged spec together with the
explicitly listed proposed changes. Distinguish proposed premises from rules
already in the spec. Proofs about the replacement construction must state that
scope; they must not claim that the unchanged spec already permits its
additional concurrency. Existing claims about the current spec remain subject to
the proof instructions' current-spec-only rule.

Make all premises explicit before relying on them. A reference to DLP 44, an
implementation choice, or a passing test does not discharge correspondence.

Specify:

- Initial state, operation enabledness, state transitions, particle lifetimes,
  and preserved destruction state.
- How reference resolution identifies the same positions across Moves and
  different positions across replacement.
- Which operation orders are semantically prescribed and which the compiler may
  choose.
- Exactly what maximum concurrency means when alternative safe dependency
  orientations exist.
- The semantics of alternative sufficient prerequisites, their combination with
  mandatory prerequisites, and exactly-once continuation. Distinguish an allowed
  choice of destructor ordering from an unnecessary compile-time choice between
  sufficient arrivals.

Revisit the existing destructor-order witness under the revised model. Do not
assume its previous conclusion still holds.

Candidate changes are hypotheses to investigate, not results established by
writing them down. Prove their correspondence to the governing requirements, and
distinguish that result from correspondence to the unchanged specification.

## 3. Complete the English semantic proofs

Begin these arguments alongside the algorithm research in steps 5 and 6. Check
them against each revision of the two design documents, rather than waiting
until performance experiments have selected an implementation.

Audit and revise every relevant definition and theorem, including:

| Area                  | Required proof work                                                                                                                                                                     |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source correspondence | Derive resolved identities and effects from valid source; prove that executing those effects preserves the intended meaning without requiring repeated traversal of written references. |
| Reference shape       | Preserve legal particle/position relationships, including the prohibition on invalid movement relationships, without unnecessary ancestor occupancy.                                    |
| Ordinary operations   | Prove Create and Move enabledness, effects, identity preservation, and the independence of child operations from ancestor Moves where applicable.                                       |
| Action boundaries     | Prove correspondence through Requirements, Guarantees, implied positions, interface positions, and distinct Action Executions without whole-action barriers.                            |
| Destruction           | Prove simultaneous selection, independent Vacates, replacement separation, shared retained state, nested destruction, and interaction with constructor and destructor operations.       |
| Lifetime              | Derive every required Create-before-use and use-before-Vanish relationship; show that no unnecessary ancestor lifetime is retained.                                                     |
| Exchanges             | Prove when adjacent operations commute and when exchanging them violates a genuine requirement, including cases involving destruction.                                                  |
| Unbounded execution   | Revisit the existing unbounded scheduling results and state any fairness or finiteness assumptions explicitly; do not infer termination from acyclicity alone.                          |

Discharge all semantic hypotheses. Examples, compiler behavior, and passing
tests cannot substitute for these proofs.

Prove preservation of principle 3 for intermediate execution states separately
from equality of logical results. Distinguish acyclicity of particle
relationships from acyclicity of the dependency graph; neither is a proof of the
other. Derive selective ordering for relationship changes without assuming that
all parent Moves must order child-position work.

Do not assume that all legal orders can be obtained from source order through
adjacent exchanges that remain legal. Two opposing Move-and-return pairs can
each run first while neither pair can overlap the other; their two legal Move
orders are disconnected under such exchanges. Establish the full set of legal
orders directly. Algebraic exchanges used only to prove equality of final
effects must not be presented as executable intermediate schedules.

## 4. Refine and prove the complete graph-construction rules

Refine the initial construction using both the English arguments and algorithm
experiments. Explore constructions organized around position occupancy,
relative-position relationships, and particle lifetime, including specialized
handling of individual operation types where useful. Update the two design
documents before proving a changed construction, and revisit all affected
semantic correspondence arguments.

For the chosen construction, prove:

1. **Invariant preservation:** every maintained record has its claimed meaning.
2. **Termination and acyclicity.**
3. **Completeness:** every required precedence is represented by a path.
4. **Transitive minimality, independently of completeness.**
5. **Characterization:** the constructed graph represents exactly the required
   ordering within the permitted orientation.
6. **Schedule safety:** every allowed execution preserves all five principles,
   including legal particle relationships at intermediate steps, and relevant
   action/destruction semantics.
7. **Dependency necessity:** each retained ordering has a valid semantic
   justification; necessity witnesses must correspond to reachable valid
   situations.
8. **Maximum concurrency:** derive it from the preceding results, rather than
   assume it.
9. **Modular correspondence:** per-action construction and composition preserve
   the same necessary ordering as whole-program analysis, without hidden
   barriers.
10. **Optimization equivalence:** every omission, pruning shortcut, deferred
    calculation, or combination preserves the claimed graph or execution
    semantics.

For Fan In (any), prove that each alternative is sufficient and remains so
through other permitted operations. Check whether all required scheduling
conditions can be expressed by completion signals with Fan In (any) and Fan In
(all); do not assume this merely because the three-Move witness permits it.
Define dependency minimality semantically for the resulting construction.
Ordinary DAG transitive reduction does not characterize redundancy through
alternative prerequisites. Reuse cover-relation results only where their
hypotheses still correspond exactly to the construction.

The construction must produce dependency minimality directly. **No generic
transitive-minimization pass is permitted.**

Keep the Action Parent Rule excluded from the central Particle Operation proofs,
as required by their instructions.

## 5. Research algorithms and representations

Work in the research repository, alongside the derivation and proofs.

Implement candidates from the explicit proposed construction and feed
correctness failures, complexity problems, and performance results back into
steps 2 through 4. Distinguish an implementation optimization that preserves the
specified graph from a different construction that requires revised rules and
proofs. Do not finish optimizing a candidate before investigating its safety and
concurrency.

Build an independent semantic reference and compare complete graphs, not
isolated Vanish calculations. A generic reduction algorithm may be used in the
test oracle, never in the candidate implementation.

The semantic oracle must check the principles throughout each tested execution,
not merely endpoint enabledness or final occupancy. Enumerate execution orders
for small cases to expose intermediate violations. Include the valid-source
relationship-reversal witness and longer transitive cases; also check that
independent child-position work retains its concurrency.

Investigate:

- Identity resolution across long chains of ancestor Moves.
- Occupancy and lifetime bookkeeping.
- Selective ordering of changes to transitive particle relationships.
- Uninterrupted parent relationships across Moves between positions defined by
  the same particle. Do not mistake such a Move for removing that relationship.
- Joint satisfiability of alternative precedence conditions. Test propagation
  through incrementally maintained records against an exact finite test oracle;
  independently possible alternatives need not have a compatible combination. Do
  not implement that obligation as a general satisfiability search.
- Alternative prerequisite representation, simplification, and exactly-once
  continuation.
- Simpler equivalents of the readiness joins and arbiter in DLP 44's
  "Arbitrating Changes to Parent and Child Relationships" example. Do not assume
  that its diagram is structurally minimal. For the three Moves before any
  Vacates, preserve all four safe orders: ABC, ACB, BAC, and CAB, while
  rejecting BCA and CBA. Also examine interleaved Vacates that can remove the
  conflicting relationships; do not apply the Move-only restriction to those
  executions. Distinguish necessity of the behavioral restriction from necessity
  of particular nodes or edges, and prove execution-order equivalence for each
  accepted simplification. Check composition with other dependencies, not just
  the isolated example.
- Action-contract composition.
- Destruction-state representation.
- Candidate collection, pruning, reachability, and storage.
- Whether simpler rules permit faster implementations without sacrificing
  concurrency.

Test progressively generated valid operations with randomized choices and
valid-order randomization. Include independent generators and targeted
adversarial families to avoid overfitting.

Cover large and small workloads, including:

- Long Move chains and deep references.
- Child creation, child movement, and replacement.
- Wide independent branches and large joins.
- Heavy position reuse.
- Implied/interface access and action boundaries.
- Shared destructor state and nested destruction.
- Million-operation graphs and very large fan-in/fan-out.

Time graph construction separately from workload generation. Also measure
identity-resolution costs separately and report total relevant construction
costs so work cannot disappear from the comparison merely by moving into
preprocessing.

Record repeated timings, memory measurements, environment, source snapshots,
correctness results, and unsuccessful experiments.

## 6. Validate useful runtime concurrency

Use the literal C experiments to test representative relaxed graphs.

Verify that generated execution can preserve resolved identities without
restoring the removed dependencies through lookups, storage reuse, or
scheduling.

Validate:

- Actual overlap between formerly serialized branches.
- Balanced and unbalanced work.
- Cases where literal operations optimize away.
- Lifetime and memory-safety consequences.
- `FirstArrival` versus `Join`, including simultaneous and late arrivals, mixed
  mandatory/alternative prerequisites, and retention of synchronization state
  until every potential arrival has finished accessing it.
- Simpler implementations of arbitration, including combining readiness and
  permission state or incorporating coordination into Move execution paths.
  Verify exactly-once execution and absence of missed notifications for all
  arrival orders, including A finishing before, during, or after the competing
  requests. Do not replace runtime choice with a fixed ordering that excludes a
  safe execution.

Instead of comparing runtime atomic operations, scheduling overhead, and memory
use, add a note to the literal C design documents recording that this
performance investigation remains to be done. Include decrement versus
test-and-set for `FirstArrival` and the cost of alternative arbitration
implementations, under both contention and no contention. Do not perform those
comparisons as part of this plan. This deferral does not remove runtime
correctness validation or the graph-construction algorithm measurements in
step 5.

Keep simulated work clearly distinguished from actual Define semantics. Do not
treat scheduler improvements as proof of semantic correctness.

Select the best-supported algorithm using evidence and complexity analysis.
Prioritize compilation time while keeping memory feasible for very large
programs. Report workload-dependent tradeoffs and distinguish proven bounds from
empirical results; do not claim universal implementation optimality without a
proof.

## 7. Complete all Lean formalization

Once the refinement loop has produced settled proposed rules, complete English
proofs, and a validated implementation, complete their Lean formalization.

Audit every file under `proofs/`, not just the main graph theorem. Update or
replace the models and proofs for:

- Definitions and operation effects.
- Particle, retained-state, and Vanish requirements.
- Collection and Comparison.
- Graph construction and Vanish insertion.
- Cover relations and edge-count results.
- Finite and unbounded scheduling.
- Destructor-order witnesses.
- Fan In (any) semantics, sufficient alternatives, dependency minimality, and
  exactly-once continuation, including composition with Fan In (all).
- Source and action-boundary correspondence.

Formalize the relevant source-semantic fragment and its correspondence
sufficiently to discharge the semantic hypotheses of the graph theorems. **Do
not leave the essential correspondence argument English-only while presenting
conditional Lean results as a complete formal proof.** A verified parser or
entire compiler is outside this task.

Reuse existing mathematical library results only with exact correspondence and
all hypotheses discharged. Use normal Lean package management.

Audit for:

- `sorry`, added axioms, circular arguments, and hidden assumptions.
- Structure fields that assume the desired result.
- Unproved source-validity or reachability conditions.
- Differences between English claims and Lean theorem scope.
- Obsolete results, terminology, and documentation.

**Completion condition:** every necessary proof obligation has an English
derivation and the required formalization; no essential gap is merely documented
as future work.

## 8. Complete the proposed rules and their correspondence

Review the complete core-rule changes and construction details for readability,
consistency, and sufficiency. Keep the distinction between semantic changes and
implementation choices explicit. Do not edit the specification.

Perform a final proof pass against the unchanged spec plus the exact proposed
changes. Connect each construction phase to the English and Lean models,
discharge all semantic hypotheses, and verify that the selected algorithm
implements that construction or a proved equivalent. State precisely which
current-spec graph rules the proposal replaces. Return to the refinement loop if
any of these disagree.

Only then update reference algorithms, relevant documentation, and graph
expectations. Validate compiler changes, if needed for investigation, in an
isolated worktree.

## 9. Final validation and completion

Before declaring completion:

- Build all Lean proofs and run every axiom check.
- Run differential, integration, adversarial, and randomized validation.
- Run formatting, dependency checks, lint, type checks, and appropriate
  coverage.
- Confirm that the final algorithm is the version actually benchmarked.
- Confirm that the unchanged spec plus the proposed changes, requirements,
  English proofs, Lean proofs, reference implementation, and expectations agree.
- Verify that the spec itself has no agent edits.
- Check correspondence with each of the five DLP 44 principles, without
  strengthening them through an unproved invariant or weakening them to a check
  of final results alone.
- Remove obsolete explanations and temporary status notes.
- Verify that all required proof obligations are closed and all claimed
  optimizations are justified.
- Leave all work **uncommitted**.

## 10. Review and clean up the proofs for commit readiness

Review everything in `proofs/`, including the English arguments, Lean
formalizations, definitions, examples, and navigation documents. Make the proof
work commit-ready without committing it.

- State the resulting facts directly. Remove transitional language, progress
  reports, descriptions of superseded approaches, and obsolete qualifications.
- Remove redundant or unnecessary text and proof machinery without weakening the
  results or concealing assumptions.
- Preserve precise statements of theorem scope and genuinely necessary
  hypotheses; these are not transitional language.
- Fix every issue found rather than merely reporting it or adding a TODO.
- Rebuild the affected proofs and rerun their axiom checks after changes.

## 11. Review and simplify the two rule documents

Review both documents from the viewpoint of the human who will update the spec.

- Rewrite the core changes as one concise, coherent set of necessary changes,
  without accumulated history, redundant restatements, or bookkeeping.
- Keep constructions, optimizations, and evidence in the separate details
  document. Identify which details are necessary for correctness and which are
  optional optimizations.
- Remove obsolete alternatives and unnecessary terminology.
- Fix problems rather than merely listing suggested edits.
- Recheck correspondence with the English proofs, Lean formalization, and
  algorithm after editing. If a simplification changes meaning, correct all
  affected work and rerun the relevant validation before finishing.
- Leave all specification edits to the user.

The final handoff should identify the resulting rules and implementation,
summarize performance tradeoffs, and state the exact proved scope, without
leaving required proof or cleanup work for a later phase. Leave everything
uncommitted.
