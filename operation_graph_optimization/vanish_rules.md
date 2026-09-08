# Vanish dependencies

This investigation starts from the current Define rules, including the
distinction between Vacate and Vanish. It does not reinterpret the archived
Destroy measurements as measurements of Vanish.

## Required graph

For a particle selected for destruction, Vanish follows its Vacate, every Move
that directly moves that particle, and every operation whose actual Position
References use a quality assigned to that particle. This includes direct implied
and interface access and each intermediate reference. Mere transitive movement
does not prolong a particle's lifetime. Apply Comparison to these candidates.

Vanish has no dependents and changes no position's setter or readers. This
leaves all existing Create, Move, and Vacate dependencies unchanged. Process
Vanishes only once their complete candidate collections are known.

## Equivalent Collection wording

After calculating Create, Move, and Vacate dependencies, collect for each
particle's Vanish:

- Its Vacate.
- The most recent Move whose source particle is that particle, if there is one.
- Every Create, Move, or Vacate whose Position References use a quality assigned
  to that particle, including qualities used through intermediate positions.

Use the original particle identities determined for those operations, including
operations in all actions. Apply Comparison to the collected candidates.
Do not collect a Move solely because it moves the particle transitively with
another particle. Vanish changes no position's setter or readers and becomes
no other operation's dependency.

The specialization argument below justifies replacing all direct Moves by the
most recent one. This wording is a result of the research; the Define spec has
not been edited to adopt it.

A quality-use candidate may also be omitted for a particle when the same
operation requires that particle to occupy an intermediate position using the
ordinary occupancy that its Vacate releases. This omission does not apply to
accesses using retained destructor state, whose occupancy is not released by
that Vacate. The argument below establishes the dependency already supplied by
the position rules.

## Resolved input

`vanish_algorithm.Calculator.observe` receives the calculated occurrence, the
distinct particle identities whose qualities its actual references use, the
directly moved particle (if any), and the particle selected for Vacation (if
any). Particle identities here are their Create occurrences; replacing a
particle does not reuse its identity. The selected particle's Vacate is added
once even if it also uses its own quality. The caller has already resolved valid
source, including shared destructor state.

The optional `ordinary_occupants` tuple identifies particles selected by
intermediate references using ordinary occupancy. Do not include particles
selected from retained destructor records. This is a fact about the resolved
reference and occupancy record, not an input assertion about reachability. An
empty tuple remains correct when the caller elects not to use the optimization.

`finish` appends a Vanish for each particle whose Vacate was observed. Particles
still alive at the end of a partial input have no Vanish. The return mapping
identifies each new occurrence. No fusion is performed: comparison measurements
need the same explicit graph from each strategy.

## Equivalent collection strategies

- **Deferred:** retain every candidate and apply Comparison at the end.
- **Direct pruning:** when a new candidate directly depends on an earlier
  candidate for the same particle, discard the earlier candidate immediately.
  Apply Comparison to what remains at the end.
- **Incremental antichain:** after each candidate, remove every earlier
  candidate reachable from it. The final collection is already an antichain.

For either pruning strategy, every discarded candidate is reached from its
replacement. If that replacement is later discarded, transitivity preserves
the same property. Induction gives a retained candidate reaching every removed
candidate. Consequently final Comparison selects exactly the same maximal
candidates as deferred collection. Processing occurs in dependency order, so an
earlier candidate cannot depend on a newly processed one.

This is local collection maintenance, not a transitive-reduction pass over the
constructed graph. It changes neither the required dependencies nor their
concurrency. Incremental antichains can make up to a quadratic number of
reachability queries for independent uses, even though the final graph is small.
Direct pruning costs the sum of the examined direct dependency counts over
particle requirements; it is not automatically linear in the number of uses.
Deferred storage is linear in the number of distinct particle-use incidences.
All strategies additionally pay the existing graph's storage and reachability
costs and the cost of emitting Vanish edges.

## Specializing direct movement

Retain only the last direct Move of each particle as a movement candidate.
Maintain quality-use and Vacate candidates separately, using direct pruning.
At the end, combine these candidates with the last Move and apply Comparison.

Why this is equivalent: after a direct Move, the particle is at its destination.
The next direct Move must use that same particle's current position as its
source. Its required occupancy comes from the previous Move, or from an
operation that depends on that Move. Readers do not supply a different
occupant. A selected Vacate does not create a second movable copy: retained
destructor operations share the original occupancy record, whose setter also
preserves this dependency. Consequently successive direct Moves of one particle
form a dependency chain. Its last Move reaches every earlier direct Move.

Replacing that chain by its last member therefore preserves the maximal
candidates. This does not treat quality uses as a chain, does not order
simultaneous Vacates, and does not infer any lifetime requirement from transitive
movement. It applies to directly moved particles during destruction too.

The summary uses one occurrence per directly moved particle and constant work
per direct Move, without a reachability query for movement collection. Quality
collection still has the direct-pruning bound above. Comparison remains necessary
between the last Move, Vacate, and independent quality accesses. This
specialization changes Collection's representation, not the required graph.

## Uses already ordered before Vacate

Suppose an operation uses a quality of particle P and, in that same operation,
requires P to occupy intermediate position Q using ordinary occupancy. Until
P first leaves Q, that operation is a reader of Q or is reached from a retained
reader. Clearing readers is permitted only after an operation that depends on
them. If P next Vacates Q, its Vacate therefore depends on the quality use.

If P instead Moves from Q, that Move depends on the reader. Every later direct
Move of P follows that Move, by the movement-chain argument. P's eventual Vacate
of its ordinary position follows the final supplying Move, or readers that
depend on that Move. Thus in either case P's Vacate reaches the quality use.

Since the Vacate is already a Vanish candidate, this quality-use candidate is
redundant without asking a reachability question. Omitting it preserves the
maximal candidate set. The reasoning uses the existing position rules rather
than assuming that ordinary actions finish before destruction.

The ordinary-occupancy condition is essential. A reference through a retained
destructor record can access the original P after its ordinary Vacate; that
Vacate does not clear the retained record's readers. Such a use must remain a
lifetime candidate. Direct implied and interface access likewise cannot be
omitted unless the same operation independently observes P through ordinary
occupancy. No whole-action barrier is introduced.

An explicit result requires writing every retained dependency. This lower bound
does not prove that any tested algorithm is universally time-optimal.
