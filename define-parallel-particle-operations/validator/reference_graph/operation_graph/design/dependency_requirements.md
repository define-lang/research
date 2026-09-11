# Particle Operation Dependency Requirements

## Governing principles

The
[Principles in DLP 44](../../../../../proposals/00044-deterministic-automatic-concurrency.md#principles)
are the foundation of the dependency requirements, exactly as written:

1. A particle occupies at most one position, and a position contains at most one
   particle.
2. Positions exist only relative to the _particle_ that defines them. Moving a
   "parent" particle preserves the relative relationships between child
   positions and their parent particle.
3. A particle cannot occupy one of its own transitive child positions.
4. An operation requires the particles and positions it acts on to exist.
5. A program run in parallel must have the same logical result as a program run
   serially as written in code.

The requirements below apply these principles to the operations specified by
Define. They do not introduce additional principles. Each dependency needs a
derivation from these principles and the specified operation effects; a chosen
representation or graph algorithm cannot supply a semantic requirement.

## Identify particles and positions before choosing an execution order

Use the valid program's specified serial interpretation to determine which
particular particles and positions each operation means. This determines the
operation's effects; it does not require the generated program to perform a
fresh lookup through the same names when the operation executes.

A position belongs to the particle or action that defines it. Moving a particle
moves its assigned positions, including empty ones, without replacing them or
changing their occupancy relative to that particle. Consequently,
`source::/child` before a parent Move and `destination::/child` afterward can
refer to the same position. Conversely, a replacement particle has its own
assigned positions: repeated uses of `parent::/child` can refer to different
positions when the particle in `parent` changes.

Resolve identity for each use, not once per written name. This applies to local,
implied, interface, and chained references alike.

## What operations need

Occupancy and existence give two kinds of requirements:

- **Position requirements:** An actual position must exist and have the required
  particular occupant, or be empty. These requirements concern the position
  being used, not every position named along the reference that identified it.
- **Particle requirements:** A particular particle must exist when an operation
  uses it or accesses its assigned qualities. Those qualities include positions
  and actions. Existence does not require the particle to remain at a particular
  position.

These are not a complete test for independence. Operations must also preserve
principle 3 and the logical result required by principle 5.

The requirements of each Particle Operation are:

| Operation | Requirement                                                                                                                                   |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Create    | Its actual target position exists and is empty. It creates the particular new particle identified for this operation.                         |
| Move      | Its actual source holds the selected particle, and its actual target exists and is empty. The selected particle exists.                       |
| Vacate    | It releases the selected particle's occupancy, respecting the distinction between ordinary occupancy and the state preserved for destruction. |
| Vanish    | The selected particle has vacated, and all operations that require that particle to exist have finished.                                      |

### Which particles an operation requires

Determine the required positions from the operation's effects:

- A Create requires its target position.
- A Move requires its source and target positions, and the selected particle.
- A Vacate requires the selected position and particle. This includes a
  transitive Vacate even though it has no written Position Reference.
- A Vanish ends the selected particle's existence; it does not access a position
  merely because that particle previously occupied it.

Apply principle 4 to the particles and positions the operation acts on. Account
for local positions through their action and its parent particle, as well as
assigned and interface positions. Neither treating local positions as unrelated
to particles nor assuming that every ancestor must remain alive is a substitute
for deriving the operation's existence requirements.

Distinguish existence from occupancy: requiring a particle to exist does not
require it to remain at the position through which a written reference
identified it. Any requirement on an intermediate position or another particle
needs its own justification from the principles and operation effects.

For example, creating or vacating a particle in `parent::/child` needs the
actual child position and the particle that defines it. It need not keep that
defining particle at `parent`. For a longer chain, accessing the final position
does not automatically access every intermediate position.

## Preserve occupancy where it is actually used

Operations must preserve the specified occupancy changes of each actual
position. A Create or Move cannot fill it before the previous occupant vacates
or moves out. Successive occupants retain their order from the serial
interpretation: completing one particle's entire use of a position does not
permit that use to exchange order with a later particle's use. This order
concerns the same actual position, not different positions with the same written
name. A Move or Vacate cannot remove a different particle from the one selected
for it. Operations that genuinely observe occupancy must observe the required
particle or vacancy, and changes that would invalidate that observation must be
ordered accordingly.

Using a particle's assigned qualities is not itself an observation of the
occupancy of the position where that particle was found. Several operations may
use different child positions of the same particle concurrently. Operations that
conflict on the same actual child position still need ordering.

A parent Move changes its own source and target occupancy. It does not fill,
empty, or replace its child positions. Therefore it does not inherently order
operations on those positions, whether their references are direct implied or
interface references or written chains through the Move's source or destination.
The Move still has its own source, target, and particle requirements.

## Preserve relative positions

Principle 2 concerns the relationship between child positions and their defining
particle. It does not require the same child particles to keep occupying those
positions: another operation may move a child particle away or fill an empty
child position. A parent Move does not itself perform either of those effects.

Principle 3 applies throughout execution, not just to the final result. A Move
can change which particles are transitive children of which others without
sharing a source or target position with another Move. Therefore disjoint
endpoints and satisfied existence requirements do not by themselves justify
concurrency.

For example, suppose Q occupies a child position of P. One Move takes Q to a
local position; another puts P in a child position of Q. The first removes the
relationship that would make the second violate principle 3. The reverse order
violates that principle even though both orders have the same final result.

Derive the necessary ordering from the relationships that operations change. Do
not replace this obligation with a general requirement that parent Moves wait
for operations on child positions.

## Alternative prerequisites

When completion of either of several operations is sufficient to satisfy a
requirement, preserve that alternative. Do not choose one predecessor at compile
time or require all of them merely to represent the requirement with ordinary
dependency edges.

Fan In (any) permits continuation after the first sufficient arrival and only
once. Fan In (all) requires every prerequisite. These can be combined: a Move
may require a particular Create and also either of two operations that remove a
prohibited transitive relationship. The other operations still execute; the
first arrival does not cancel them.

An alternative prerequisite is justified only if satisfying it remains
sufficient when other permitted operations execute. Completing an operation is
permanent; the particle relationship it changed need not be. Derive that
distinction from the specified effects when identifying sufficient arrivals.

## Competing relationship changes

Two operations can each preserve the principles in the same state while their
combined effects would violate principle 3. Permit either operation to proceed
first when its other requirements are satisfied. Coordinate permission before
the operations change the relationships; observing their completions afterward
cannot prevent the prohibited arrangement.

Do not select a fixed order during compilation when that would exclude a safe
execution order. When another operation removes the conflicting relationship,
release that restriction without imposing an order between the previously
competing operations. Completion-only Fan In does not express a permission that
can cease to be valid when a competing operation proceeds.

Permissions for overlapping conflicts must be consistent with each other and
with the operation's other requirements. Independently winning one conflict is
not sufficient to execute an operation subject to another. Coordination must
neither allow a prohibited intermediate arrangement nor prevent the program from
completing its specified operations.

These requirements specify allowed executions, not a required number of joins,
arbiters, runtime objects, or atomic operations. A simpler representation is
equally valid if it preserves exactly those executions.

## Preserve particle lifetime without preserving location

An operation requiring a particle must follow that particle's creation and
precede its Vanishment. In particular, this protects accesses to its assigned
positions even when it moves or vacates the position through which those
positions were identified.

Account for every actual use, including uses in constructors, destructors, and
transitively triggered actions. A direct Move uses the particle it moves; moving
a parent does not, by itself, use each transitive child's occupancy or require
every child particle to remain alive.

Do not assume that ordinary operations finish using a particle's qualities
before its Vacate merely because their written references name an intermediate
position. Removing that occupancy requirement makes their particle-lifetime
requirements independently important. Neither the absence of destructors nor the
spelling of a reference justifies omitting those requirements.

## Destruction and replacement

Vacation and Vanishment remain different events. Reusing a vacated position does
not require its old particle to vanish. Replacing a parent also does not reuse
the old parent's assigned child positions: the new particle has different ones,
even when their written names are identical.

Simultaneous Transitive Destruction selects particular particles together. Their
Vacates have identical recency; the selection does not impose an order between
parent and child Vacates or manufacture fresh references through parent
positions. Derive lifetime dependencies from what each operation actually uses,
not merely from membership in the same simultaneous destruction.

Destructors access the original particles' shared, changing state, not copies
and not replacement particles. Vacation for ordinary code does not erase the
occupancy preserved for destruction work. Operations accessing that preserved
state still have occupancy and particle requirements. Where destructors
conflict, the compiler may choose their ordering as permitted by the spec;
independent work need not wait for an entire destructor to finish.

Preserving occupancy for destruction is not the same as preserving particle
existence. Once a selected particle has vacated and no destruction work still
requires its occupancy, that occupancy need not persist until its Vanish.
Operations on the particle's own child positions can still require the particle
to exist without requiring its former parent relationship. Account for all
destructors sharing that occupancy, not just one destructor's final use.

A destructor Move still changes actual source and target occupancy. Moving to a
local position of an action assigned to the same parent particle does not detach
the moved particle from that parent. Ending preservation must not erase an
occupancy requirement of a pending Move. Apply the principles to the effects of
each Move, including its filling of the target position. Ending occupancy
preservation afterward does not permit the Move to put a particle in one of its
own transitive child positions. Nor may the dependency construction replace that
Move with an operation that only empties its source.

## What the dependency construction must establish

Every execution allowed by the graph must preserve all five principles. Check
the arrangement after each operation as well as the program's logical result;
matching final occupancy alone is insufficient. The logical result includes the
specified particle identities, Action Contracts, and the shared state used
during destruction.

Order operations only where those requirements need it. A shared ancestor,
written reference prefix, action boundary, or place in the serial enumeration is
not independently a reason to serialize work. Recency identifies the specified
serial interpretation; the resulting dependencies determine execution order.

Maximum concurrency and dependency minimality are separate obligations. Removing
redundant edges cannot recover concurrency lost by requiring both alternatives
or enforcing unnecessary intermediate-position occupancy. Derive redundancy
using the meaning of Fan In (any) and Fan In (all), not ordinary graph
reachability alone. The construction must produce its minimal dependencies
directly, without a generic graph-minimization pass afterward.
