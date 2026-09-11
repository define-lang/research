# Completion of relationship changes

`relationship_completion_test.py` explores resolved Moves and Vacates in a
bounded, destructor-free fragment. Particles already exist, and their Vanishes
are postponed until after all uses. Local positions belong to a stationary
action parent outside the particles being moved. The model omits that common
parent because none of the tested operations moves it or enters one of its
ancestor positions. This is not a model of arbitrary action or destructor
execution.

Each position retains the source order of operations that change its occupancy.
Moves select their original particle, source, and target. A Vacate removes its
selected occupancy; it does not free the particle or its assigned positions.
The test checks the particle relationships after every operation. A completed
operation set determines a unique state in these examples, which the exploration
also checks when different paths reach that set.

## Vacates can release a relationship conflict

Use the particles and three Moves from `identity_move_conflict.dfn`:

- A moves Q from P's `/child` to `detached_child`.
- B moves P from `parent` to R's `/end`.
- C moves R from `third` to Q's `/inner`.

Before any Vacates, B and C cannot both execute before A. In the full action,
however, B, Vacate(P), C, A is safe; so is C, Vacate(R), B, A. The Vacate removes
one of the relationships that would complete the cycle. P and R remain alive
for later operations on their positions. A controller that insists on A before
the second competing Move would therefore lose concurrency.

This does not show that a Vacate erases relationships used by destructors. The
experiment has no destructors and makes no claim about preserved destruction
state.

## An acyclic prefix can prevent completion

The normal Define integration fixture
`future_moves_must_remain_executable/test.dfn` supplies the source example.
P, Q, and R begin in `parent`, `other`, and `visitor`. The five Moves are:

- A moves R to P's `/landing`.
- B moves R from P's `/landing` to Q's `/landing`.
- C moves P to R's `/inner`.
- D moves Q to `visitor`.
- E moves P from R's `/inner` to `other`.

C alone is acyclic, but then A would create a cycle. B needs A to supply its
source occupant. D needs A to empty `visitor`. E needs D to empty `other`.
Each terminal Vacate needs the last Move of its selected particle. No operation
can release the obstruction.

Consequently C must follow B. The exhaustive check includes all three final
Vacates and confirms that C leaves a completable state exactly when B has
finished. The source fixture also has independent temporary child particles to
exercise its required qualities. Completing their operations changes none of
the positions or particles in this cycle, so omitting them does not manufacture
the obstruction.

## Exact finite reference calculation

Explore every state reachable through occupancy-ordered operations that leave
acyclic particle relationships. Working backward from the fully completed set,
mark a state when one of its successors is marked. An operation can start only
if its successor is marked.

For this finite model, the marking has a direct induction on the number of
remaining operations: a state is marked exactly when some complete legal
execution extends it. Keeping every transition between marked states preserves
all complete legal orders and excludes choices that cannot finish. This is a
reference calculation, not a proposed scalable implementation or a proof of
correspondence for the full Define specification. It can visit exponentially
many completed-operation sets, even for entirely independent work.

The three initial tests pass: conflict release by Vacates, the acyclic dead end,
and preservation of successive occupants' source order. These tests constrain
candidate algorithms; passing them is not a proof of a general construction.
