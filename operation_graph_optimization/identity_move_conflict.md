# Competing particle-relationship changes

The valid source in `identity_move_conflict.dfn` creates P in `parent`, Q in P's
`/child`, and R independently in `third`. Q's `/inner` and R's `/end` are empty.

The three Moves have disjoint endpoints:

- A moves Q from P's `/child` to `detached_child`.
- B moves P from `parent` to R's `/end`.
- C moves R from `third` to Q's `/inner`.

Each Move has the expected source occupant and an empty target in any order.
All particles and their positions exist. All orders reach the same final state.
Principle 3 distinguishes the intermediate states: B followed by C, or C
followed by B, before A creates a cycle through P, Q, and R. Either B or C alone
is safe before A. A removes the relationship that prevents both from completing.

With no intervening Vacates, the safe orders are ABC, ACB, BAC, and CAB. BCA and CBA have a circular
intermediate relationship. These are consequences of the DLP 44 principles for
resolved effects, not the execution orders of the current compiler.

## Limit of completion-only Fan In

A completion condition constructed from Fan In (all) and Fan In (any) is
monotone: once it is satisfied, additional completions cannot make it false.
To permit BAC, B's condition must be satisfied before any of the three Moves
finishes. To permit CAB, C's must also be satisfied in that same state. After B
finishes, C's condition remains satisfied, permitting the unsafe BCA prefix.

Thus completion-only Fan In cannot admit every safe order and reject every
unsafe order in this case. A static restriction can be safe, but excludes an
otherwise safe order. Retaining both choices requires coordinating permission
to execute the competing Moves, not merely merging their completion signals.

The atomic primitive used for `FirstArrival` could also select between competing
requests. That would give it a different role: the first request permits its own
Move, whereas the other Move must wait for A. Selection and execution must be
coordinated so both Moves cannot obtain permission before A. This observation
does not establish a general algorithm for arbitrary interacting relationships.

## Checks

`identity_move_conflict_test.py` validates the real source and enumerates all six
Move orders. It also exhaustively tests all 216 assignments of monotone Boolean
completion conditions on the three Moves. None admits exactly the four safe
orders; the largest safe family has three orders.

The full action also permits interleaved Vacates to remove conflicting
relationships. See [the completion experiment](relationship_completion.md).
The four-order result concerns the three-Move interval, not every projection of
a full action execution onto those Moves.

All three research tests passed. The corresponding Define operation graph
integration case uses normal convention-backed testdata and dependency
assertions, with a TODO beside the relationship condition whose representation
is unresolved.
