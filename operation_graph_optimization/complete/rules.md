# Constructing Particle Operation dependencies

These rules describe the whole-program graph. They do not add the separate
Action Parent Rule used for modular analysis. Resolve actual references and
particle identities using the language's serial semantics before applying them.
Replacement particles have distinct identities even when created in the same
position.

## Position information

For each position, remember its setter and readers. Its setter is the most
recent operation that filled or emptied it. Its readers are subsequent operations
that used it as an intermediate position. A child position's initial setter is
its parent particle's Create; other positions initially have no setter.

Moving a particle does not change the relative occupancy, setters, or readers
of its assigned positions.

Before processing a simultaneous destruction, preserve the position information
needed by its destructors. Vacates change ordinary occupancy, not the retained
information used by those destructors and actions they trigger. Those actions
share changes to the same retained position information. They do not get
independent copies. A replacement particle does not use that information.

## Collection for Create, Move, and Vacate

Process these operations in Particle Operation Recency order. Collect:

- The setter of a Create's or Move's target, if one exists.
- The setter of every intermediate position in the actual Position References.
- The readers of a Move's source or the position emptied by a Vacate; collect
  its setter instead when there are no readers.
- The Create of each particle whose assigned qualities those references use.

Combine the candidates before making these omissions:

- Omit a particle's Create if a different collected operation is a setter or
  reader of one of that particle's child positions.
- Omit an intermediate position's setter if a collected operation is one of
  that position's readers.

Use the combined collection to decide all omissions, then perform Comparison.

## Comparison

Initially keep no candidates. Examine candidates with dependent operations before
their dependencies. Keep a candidate unless an already kept candidate depends
on it, directly or indirectly. The kept candidates are the operation's direct
dependencies. This does not change previously calculated edges or require a
transitive reduction of the completed graph.

## Recording

Record the operation as a reader of its intermediate positions. For each
position it fills or empties, replace the setter with this operation and clear
the readers. When recording a reader, earlier readers collected for that
operation may be discarded: the new reader already depends on them, even when
Comparison omitted their direct edges.

Vacates use their statements' Position References, including the statements
implicit in Automatic Destruction and Destruction Contracts. Transitive child
Vacates do not acquire references through their displayed names.
The Vacates selected together do not order each other.

## Collection for Vanish

While processing Creates, Moves, and Vacates, remember for each particle:

- Its Vacate.
- Its most recent direct Move, if any.
- Every operation whose actual Position References use one of its assigned
  qualities, including intermediate references.

Omit a quality-use candidate for a particle when that same operation requires
the particle to occupy an intermediate position using the ordinary occupancy
that its Vacate releases. In that case the position rules already order the use
before the Vacate. This omission does not apply to retained destructor
occupancy. Direct implied and interface uses are not omitted unless the same
operation also requires that ordinary intermediate occupancy.

After all Create, Move, and Vacate dependencies are known, collect the remembered
operations for each selected particle's Vanish and apply Comparison. Vanish does
not change setters or readers and is not a dependency of another Particle
Operation.

All actions contribute actual quality uses, not just destructors. A Move does
not require the continued existence of a selected child merely because that
child moves transitively with its parent.

Successive direct Moves of one particle already form a dependency chain, so its
most recent direct Move covers all earlier ones. Particle-use candidates may
also be discarded when another candidate for that particle depends on them.
In particular, a new use covers its position Collection candidates, including
candidates omitted by Comparison.

## Combining operations

Vacate and Vanish may be combined when the Vacate is the Vanish's only direct
dependency in the resolved graph. The combined operation has the Vacate's
dependencies, and dependents of the Vacate depend on the combined operation.
The reference algorithm keeps the two explicit, so every dependency can be
compared directly across implementations.
