# Retained relationships after the last destructor use

The bounded relationship-completion experiments do not model destruction state
preserved for destructors. Extending them requires specifying when such a
relationship ceases to count for the prohibition on a particle occupying its
own transitive child position.

## Valid source witness

The Define integration fixture is
`operation_graph_relationship_integration/destructor_local_moves_preserve_parent_relationship`.
Its source passes structural and reference validation. Its graph assertion uses
provisional notation for a Join within a FirstArrival.

Initially P occupies `parent`, Q occupies P's `/child`, and R occupies Q's
`/leaf`. R defines `/return`. The ordinary statements are:

```define
move the particle in position<parent>::position</child>::position</leaf> to position<detached>.
move the particle in position<parent> to position<detached>::position</return>.
```

Call these A and B. At the end of the action, automatic destruction selects
R, P, and Q. P has a destructor whose statements are:

```define
define the position<held>.
move the particle in position</child> to position<held>.
move the particle in position<held> to position</child>.
```

Both `/child` and `held` are relative to P: `held` belongs to an action assigned
to P. Neither destructor Move detaches Q from P. Treating that local position as
relative to an unrelated stationary particle gives the wrong answer.

## Ending preservation without ending existence

Consider the prefix consisting of the three Creates, Q's Vacate, and both
destructor Moves, before A or B. Q cannot yet Vanish because A requires the
position `/leaf` that Q defines.

The accepted interpretation ends retained occupancy once both its Vacate and
its last required destruction use have finished. Q can cease to be P's child
while remaining alive for A. B can then run before A. Neither destructor Move
alone releases the relationship: both preserve Q's parent particle.

For this witness, B needs A or the combination of Q's Vacate and the last
destructor Move. Requiring Q's Vanish would unnecessarily require A first.
After B, Q's `/leaf` holds R and R's `/return` holds P; Q does not occupy P's
`/child`. That is a chain, not a cycle. A then removes R from Q's `/leaf`.

This is the semantic choice accepted during the redesign, not a claim that the
existing retained-state proof already formalizes it. Extending the model must
include all remaining occupancy uses from every sharing destructor. A use of
Q's own `/leaf` protects Q's existence but not its occupancy in P's `/child`.
Whether a final Move must have a separate occupied result before preservation
ends is not determined by this witness. The additional case below distinguishes
that interpretation from one combined effect.

## Bounded validation

`retained_relationship_test.py` enumerates every reachable completed-operation
set for the full thirteen-operation example, including Creates, Vacates, and
Vanishes. It checks the relationship alternative at every reachable prefix,
not merely the two selected schedules. Different schedules reaching the same
completed set must agree on occupancy and live particles. Occupied positions
must retain their defining particles throughout.

Additional cases check that the last destructor use without Vacation does not
release occupancy, that the Move to a same-parent local position does not
release it, and that two sharing destructors must both finish using occupancy.
Each destructor has its own local position identity. A separate normal Define
integration case records the sharing-destructor dependency; its source also
passes compiler validation.

This model checks the specified finite effects directly. It is not the full
algorithm, a graph-construction benchmark, or a proof of source correspondence
for arbitrary destructor programs.

## The last Move and the end of preservation

The valid Define integration case
`operation_graph_relationship_integration/last_destructor_move_and_occupancy_release`
adds a particle in `parent::/helper`, defining `/hold`. Instead of a local
`held` position, the destructor moves `/child` to `/helper::/hold` and back.

The helper particle can vacate while staying alive for access to its `/hold`.
After that vacancy and the first destructor Move, the child is no longer a
transitive child of the original parent. The ordinary Move of `parent` into the
leaf particle's `/return` can execute before the leaf Move.

The final destructor Move would then restore the child to a position of its
own transitive child particle. The Move must perform its written effect without
creating that cycle. Ending the child's occupancy preservation afterward does
not excuse the cycle, even though its Vacate has already occurred.

Either the leaf Move or the original parent's Vacate can break the cycle before
the return Move. The original parent must still exist for access to its
`/child`; its Vacate, not its Vanish, provides this alternative.

`test_final_move_observation_changes_the_allowed_schedule` preserves the rejected
shortcut as a comparison: omitting the check of the Move's occupied result
accepts the invalid schedule despite producing the same final state. It is not
an alternative semantics for the construction. A separate full-schedule test
checks that the parent's Vacate can permit the return before the leaf Move.
