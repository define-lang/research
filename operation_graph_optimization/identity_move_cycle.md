# Resolved Move Identities and Circular Relationships

The source in `identity_move_cycle.dfn` is valid. Its two Creates introduce a
particle P in `parent` and a particle Q in P's `/child` position. Q defines an
initially empty `/inner` position.

The first Move puts Q in `detached`. The second puts P in Q's `/inner` position.
The Moves affect four distinct actual positions. Both particles exist throughout
either ordering, both sources have the selected particles, and both targets are
empty. The actual position identities do not change between the two orderings.

Nevertheless, executing the second Move first makes P occupy Q's `/inner` while
Q still occupies P's `/child`. The intermediate parent relationships are
circular. Executing the first Move afterward removes that cycle. Both orderings
reach exactly the same final relative occupancy.

`identity_move_cycle_test.py` checks source validity and enumerates both Move
orders, including every intermediate state. It demonstrates that endpoint
occupancy, selected identity, and particle lifetime alone do not imply acyclic
parent relationships. A proof that claims acyclicity needs an additional
argument or requirement.

The spec's source-prefix restriction rejects a written Move from `parent` to
`parent::/child::/inner`. It does not reject this valid source, whose second Move
uses `detached::/inner` after Q has left `parent::/child`. Reordering resolved
identities removes the occupancy dependency that previously made that source
restriction sufficient to preserve acyclicity during execution.

This example distinguishes preserving acyclicity at every execution step from
preserving it in the serial interpretation and completed effects. It does not
show that ordinary parent Moves must order all operations on child positions.
