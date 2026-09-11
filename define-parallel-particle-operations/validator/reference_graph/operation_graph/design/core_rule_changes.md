# Candidate Incremental Dependency Rules

This is a working hypothesis, not an accepted replacement for the spec. The
occupancy and lifetime calculations below are explicit; general composition of
relationship restrictions remains incomplete. In particular, the two-period rule
below must not be mistaken for a complete relationship algorithm.

## 1. Identify the affected particles and positions

Walk valid source in its serial interpretation. Identify the particular particle
selected by each operation and the actual positions it fills or empties. Keep
these identities through Moves; do not traverse written references again during
execution. A replacement particle supplies different child positions.

Resolve implied and interface positions through Action Contracts. Distinguish
each Action Execution's local positions; repeated executions do not supply new
copies of the assigned action's interface positions.

## 2. Keep occupancy, lifetime, and relationship records separately

- For each actual position, keep its most recent filling or emptying operation,
  called its setter. Its initial setter is the Create of the particle defining
  it, including the parent particle of an action defining the position. An
  initially available position without such a Create has no initial setter.
- For each particle, keep its Create, accumulated lifetime candidates, selected
  Vacate, and most recent direct Move.
- For each particle, keep its current parent relationship and the operation
  beginning that relationship. Moving between positions defined by the same
  parent particle does not begin a different relationship.

Do not keep intermediate-position readers. A written ancestor name supplies no
occupancy or lifetime dependency by itself.

## 3. Collect ordinary dependencies

| Operation | Collect the setters of          | Record a lifetime use of                                      |
| --------- | ------------------------------- | ------------------------------------------------------------- |
| Create    | Its target position             | The particle defining its target position                     |
| Move      | Its source and target positions | The moved particle and particles defining its two positions   |
| Vacate    | Its selected position           | The selected particle and the particle defining that position |

Where an action defines a position, its parent particle supplies the existence
requirement. An endpoint setter already follows its defining particle's Create;
an occupied source also supplies the selected particle's creation. Do not add
those Creates a second time.

Combine candidates, examine them in reverse topological order, and retain a
candidate only if no already retained candidate depends on it. This is the
ordinary Comparison calculation, not a subsequent transitive reduction pass.

## 4. Record each operation's effects

- **Create:** make it the target's setter; record the new particle's Create and
  initial parent relationship.
- **Move:** make it both endpoint setters and the particle's last direct Move.
  If the defining parent changes, end the old relationship at this Move and
  begin the new one. Do not update its child positions' setters.
- **Vacate:** record the selected particle's Vacate and update its position's
  ordinary setter. End its unpreserved occupancy at this Vacate.

Add the operation to each particle's lifetime candidates identified in step 3. A
candidate already ordered before another candidate may be omitted using ordinary
Comparison.

## 5. Preserve destruction state without adding a destruction barrier

Select the particles of a Simultaneous Transitive Destruction together. Give
each its own Vacate; do not order these Vacates by parent relationships.

Keep the original occupancy and setter information needed by destructors
separate from the vacancy available outside that destruction. Destructors
sharing an original position use one changing record, not separate copies.
Process their operations in the compiler's chosen permitted destructor order.

A selected particle's incoming occupancy is released after both its Vacate and
the last direct destruction Move requiring that occupancy. Its own
child-position uses extend its existence, not that incoming occupancy. A final
Move must still produce a legal occupied target before release; release does not
undo the Move.

Record a joined relationship end when both the Vacate and a direct Move are
needed. A use from a transitively triggered action is treated like any other
use, not as an action-wide completion barrier.

## 6. Compare two opposite parent relationships

This rule applies to two periods: one in which P occupies a position defined by
Q, and another in which Q occupies a position defined by P. Write their
beginnings and endings as A, a and B, b, with the first period occurring earlier
in the serial interpretation. An ending can require several operations together,
as with a Vacate and a direct Move.

They cannot overlap. Calculate their restriction as follows:

1. If B already depends on every member of a, record nothing: separation is
   already supplied.
2. Otherwise, if any member of b depends on A, collect a for B. The reverse
   separation, b before A, is impossible.
3. Otherwise retain an exclusion between the periods: either all of a finishes
   before B begins, or all of b finishes before A begins. Do not select one
   direction at compilation or require both endings before either beginning.

Omit ending operations already supplied by the beginning's dependencies; apply
ordinary Comparison to the remaining ending candidates. An ordered Vacate and
Move need only their later member; independent members require a Join.

An initially present first relationship cannot execute after the second period;
likewise, a second period with no end cannot execute before the first. These
cases also collect a as a prerequisite of B.

For an isolated exclusion, coordinate its two beginning operations so only one
period is active at a time. Its ending releases that exclusion; ending either
period does not cancel the other. Ordinary prerequisites still apply.

Register an unfinished period when its beginning is processed and complete its
record when its ending is encountered. An ending not encountered yet is not the
same as a relationship known to continue beyond the construction boundary. Any
restriction needing that ending remains pending rather than guessing it.

## 7. Compose a circular departure dependency

For two exclusions with single ending operations, write the periods as A to a
versus B to b, and C to c versus D to d. If b requires c and d requires a, add
this conditional restriction between B and D: until either a or c completes, at
most one of B and D may begin. Keep each original exclusion too. Completion of a
or c releases the additional restriction; it does not cancel operations.

This follows from the endpoints, without searching orders. If both B and D
preceded both a and c, the original exclusions would require b before A and d
before C. The resulting required chain is c before b before A before a before d
before C before c, which is impossible.

Register this connection through dependencies of the ending operations even when
the two particle pairs are disjoint. This is a derived rule for this specific
pattern, not yet a general rule for every interacting set of exclusions.

## 8. Complete particle lifetimes

For each Vanish, collect its particle's lifetime candidates, its Vacate, and its
last direct Move, if any. Apply ordinary Comparison and make the remaining
candidates its dependencies. A Vanish updates no setter and supplies no other
operation's prerequisite.

This is the explicit lifetime baseline. It does not establish semantic
minimality when relationship restrictions imply additional ordering. A direct
replacement for those redundant candidates must be derived from the completed
relationship construction, not from a search for the last possible use.

## 9. Apply the records across action boundaries

Substitute the caller's identified particles and positions for the callee's
contracted positions. Pass the corresponding occupancy, lifetime, and
relationship records through that substitution. Preserve shared records and
distinct local positions. Requirements and Guarantees do not reset these records
or add whole-action barriers.

Do not finalize an incomplete relationship or lifetime record merely because an
action boundary was reached. A modular summary must expose its unfinished
contributions to the caller. The exact sufficient summary remains an obligation
of the modular construction.

## Missing rules before this becomes a complete candidate

- Incrementally construct restrictions involving longer transitive parent
  relationships, without enumerating every possible cycle or execution order.
- Compose overlapping exclusions and ordinary dependencies. Independent
  permissions can admit a prefix from which required Moves cannot finish;
  checking the current particle arrangement alone does not prevent this.
- Define updates to earlier dependency records when a later ending supplies new
  information, including rechecking implications used by existing exclusions.
- Derive combined dependency omissions, including lifetime omissions, directly
  from those records. Ordinary transitive minimality does not establish
  minimality of a graph containing alternative prerequisites.

These are algorithm gaps, not missing permission to change Define's semantics.
The complete rule set must fill them with explicit incremental calculations.
