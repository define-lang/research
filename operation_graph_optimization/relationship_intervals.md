# Parent relationships as intervals

This construction concerns the finite resolved Move/Vacate model in
[the completion experiment](relationship_completion.md). It is not yet a
source-correspondence proof for Define or a specification of destructor state.

## Collection

For each particle, record each uninterrupted period in which it occupies a
position defined by one particular parent particle. The period begins with the
operation that makes that relationship and ends with the operation that removes
it. An initial relationship has no beginning operation; a final relationship
has no ending operation. Moving between two positions defined by the same
particle does not interrupt the relationship.

For each possible simple cycle of parent relationships, collect the alternatives
that an ending operation of one period precedes a beginning operation of another
period in that cycle. Ignore an alternative with a missing endpoint. Require at
least one of those alternatives for every such cycle.

These alternatives are constraints on complete orders, not yet permissions to
execute an operation. A current state can be acyclic without having a legal
completion.

## Correspondence with acyclic arrangements in the finite model

Fix a total operation order that respects each position's occupancy sequence.
Represent a relationship period as a half-open interval: present after its
beginning operation and absent after its ending operation. Initial and final
relationships extend to the corresponding ends of the execution.

A spatial cycle exists after some operation exactly when all periods of some
simple cycle intersect. A finite collection of intervals on a line has empty
common intersection exactly when one interval ends no later than another
begins: compare the earliest ending with the latest beginning. In this model,
one Move affects one particle's direct parent relationship, so distinct periods
in a simple cycle cannot share that same operation as an end and a beginning.
The endpoint comparison is therefore strict precedence between distinct
operations.

Thus the collected alternatives characterize precisely the complete
occupancy-ordered executions with no spatial cycle. This argument does not show
that enumerating all possible cycles is efficient, that the resulting clauses
are irredundant, or that local propagation decides their joint satisfiability.

## Simplification and exact finite reference

An alternative is already satisfied when its precedence follows from the known
ordering. It is impossible when the reverse precedence follows. Drop satisfied
clauses, discard impossible alternatives, and add a precedence when it is the
only alternative left in a clause. Repeat these steps after adding precedence.
An empty clause or a precedence cycle indicates inconsistency.

This propagation is sound but incomplete. The checked witness in
`test_propagation_alone_can_miss_incompatible_alternatives` leaves several
multi-alternative clauses, although no complete order satisfies them together.
It includes all final Vacates and merges continuous same-parent relationships.
That witness is a resolved-state experiment; no claim of valid Define source is
made for it.

The exact reference branches on one unresolved clause, trying each alternative
and propagating again. Each branch satisfies at least that clause, so the search
terminates. If it reaches an acyclic precedence relation with every clause
satisfied, every topological order of that relation satisfies the constraints.
Conversely, any satisfying total order chooses at least one alternative in the
selected clause, and the search includes that branch. Induction on the number
of unresolved clauses establishes exactness for this finite model.

To check an execution prefix, include its order and require every completed
operation to precede every unfinished operation. The exact reference then
answers whether that prefix has a complete legal continuation. The implementation
uses the last prefix operation for these latter edges, since the prefix chain
already orders its earlier operations.

This calculation provides an independent reference alongside state exploration.
Its worst-case branching and cycle enumeration are not acceptable as an assumed
cost for large compilation units. A production construction needs further
research into factorization, symbolic representation, and unavoidable costs;
the reference does not settle those questions.

## Rejected completion shortcuts

Two cheaper completion checks are not exact, even in this bounded model:

- Executing the unfinished operations in their original source order can fail
  from a prefix that has a legal completion in another order.
- Repeatedly choosing the earliest currently executable unfinished operation
  can enter a dead end from a state that has a legal completion.

Both witnesses include every terminal Vacate. The regression tests preserve
the concrete operations and prefixes. These are failures of candidate
algorithms in the resolved-state model, not additional proposed Define rules.

## Discovering only violated cycle constraints

The lazy reference starts with the ordinary occupancy ordering and the proposed
prefix. It chooses a total order satisfying its collected constraints and checks
the resulting particle arrangements. On finding a cycle, it adds that cycle's
interval clause and tries again. On finding an acyclic complete execution, it
returns that execution as a certificate. If the collected constraints have no
solution, the prefix has no legal completion.

Each added clause is necessary for every legal completion and false in the order
that exposed it. It therefore excludes that order without excluding a legal
one. A clause already satisfied by the chosen order cannot be added again as a
violation. There are finitely many candidate total orders, so this process
terminates and is exact for the finite model. Unlike exhaustive cycle
collection, it need not materialize unrelated possible cycles merely to confirm
an already legal order. This is still an exact reference, not a claim of a
polynomial worst-case runtime.

## Factoring independent choice calculations

Let the ordinary requirements form an acyclic precedence relation. Partition
operations so that every alternative clause refers only to operations in one
part. Form a directed graph of parts, adding an edge for each ordinary
precedence edge between parts. Merge the strongly connected components of that
graph. The resulting graph of parts is acyclic.

The alternative choices can now be solved independently within each resulting
part, retaining its ordinary precedence edges. A path that leaves one part
cannot return to it, since that would make a cycle in the graph of parts. Thus
no ordinary precedence between two operations in one part is lost by keeping
only its internal edges. Each chosen alternative is also internal to one part.
If the chosen precedences are acyclic within every part, their union with the
ordinary edges is acyclic: a cycle crossing parts would project to a cycle in
the graph of parts. Conversely, any global satisfying order restricts to a
satisfying order for every part.

This remains exact after a legal ordinary-operation prefix. In each part,
preserve the prefix's local order and put its completed operations before its
unfinished operations. No local solution then orders an unfinished operation
before a completed one. No ordinary edge does so either, because the prefix
respects ordinary precedence. Adding the global prefix order and putting all
completed operations before all unfinished ones cannot create a new cycle:
within completed operations the prefix is an order, within unfinished operations
the preceding acyclicity argument applies, and no edge goes back from unfinished
to completed. Therefore a global prefix has a legal completion exactly when
each part's prefix does.

For parent-relationship clauses, an initial partition can be obtained without
enumerating cycles: group the particles by strongly connected components of
their possible direct-parent relationships. Every possible spatial cycle lies
in one such component, and both endpoints of a particle's relationship period
are operations on that particle. Ordinary precedence can still couple different
components; the second merging step must not be omitted. This factorization
avoids a whole-program choice barrier. It does not bound the size of an
individual interacting component.

## Ending a retained relationship at a Join

Under the accepted destruction interpretation in
[retained relationship release](retained_relationship_release.md), an occupied
period can end when both the selected Vacate and the last required destruction
use have completed. Its end is therefore the later of these completions, not
necessarily one fixed operation in every execution order.

For a beginning operation to follow that end, it must follow every member of
the Join. Replace that interval alternative by a conjunction of precedences;
do not replace it by separate alternatives. The interval intersection argument
then still applies to a fixed total order, provided the periods accurately
describe the actual operation effects. This does not by itself establish that
all destructor behavior has such a period decomposition.

`precedence_choice.py` is a finite reference for these generalized clauses.
It drops a clause when one whole alternative follows from known precedence,
discards an alternative when any of its precedences is impossible, and adds all
precedences in a sole remaining alternative. It branches over alternatives,
not over the individual members of a conjunction. Internal contradictions in
an alternative are rejected by the subsequent acyclicity check.

The same finite-search proof applies: each branch satisfies the selected clause;
every satisfying total order satisfies some branch; each recursive branch
removes at least that clause after propagation. Termination and equivalence do
not depend on the size of a conjunction. The implementation does not perform
transitive reduction and makes no claim that the clauses are irredundant.

The regression tests compare the calculation with all 720 total orders for
each of 150 seeded six-operation constraint systems, including execution-prefix
constraints. These are mathematical constraint tests, not a claim that randomly
generated clauses all arise from valid Define source.

The generalized reference also factors constraints before solving them. Every
clause's operations initially share a part; ordinary precedence between parts
can require merging their strongly connected components as above. Each final
part gets local operation indices, so solving a small independent part does not
allocate a reachability matrix sized for the entire problem. Exhaustive tests
compare the factored and unfactored answers, and a targeted case requires
ordinary precedence to merge otherwise separate clauses.

## Preserving the last Move's occupied result

The selected interpretation checks each Move's occupied result before ending
preservation. Even if a final relationship begins and ends during that same
operation, it must not create a cycle. Treat the Move effect and the subsequent
end of preservation as ordered observations, not two interchangeable operations.

For a total order with operation ranks numbered by integers, place a Move's
effect at twice its rank and the end of preservation after its final required
event at twice that event's rank plus one. This gives a final restoration a
nonempty interval even when its Vacate has already occurred. For periods of
distinct particles in a simple cycle, an end precedes another beginning exactly
when every end event strictly precedes that beginning operation. One operation
does not directly move two different particles. Thus the conjunction alternatives
remain exact, and an operation cannot count its own later release as preceding
its own Move effect.

`relationship_periods.py` collects these clauses from given uninterrupted
relationships. The retained-state experiment derives the relationships from its
Create and Move effects, preserving same-parent continuity and giving the final
relationship the Vacate and required destruction uses as its end events. On the
helper example, the mechanically collected clauses and endpoint/lifetime
precedences agree with state exploration at every reachable prefix. That check
includes the final Move's occupied result and the parent's Vacate alternative;
the constraints are not hand-written specifically for the two displayed orders.

The collector enumerates possible simple cycles. It is a correctness reference,
not a scalable whole-program implementation. Source correspondence and an
efficient complete construction remain separate obligations.

## Legal orders need not be connected by legal adjacent exchanges

The valid Define integration case
`operation_graph_relationship_integration/relationship_excursions_can_run_in_either_order`
creates two particles, each defining an empty `/child`. One pair of Moves puts
the first particle in the second particle's `/child` and returns it. The other
pair puts the second particle in the first particle's `/child` and returns it.

Either pair can run first, but both temporary relationships cannot coexist.
Consequently the four Moves have exactly two legal orders: the first pair then
the second, or the second pair then the first. No adjacent exchange connects
these orders through other legal orders. Each actual position's occupants stay
source-ordered; the two `/child` positions belong to different particles.
The source passes compiler validation, and the research test includes the
final Vacates and Vanishes rather than inferring a whole-program restriction
from an incomplete graph.

The interval construction gives the alternative that either pair's return
precedes the other's beginning. A proof that only exchanges adjacent independent
operations from one fixed source order would miss the other legal order.
Final-effect equality can still be proved separately from each position's
ordered effects; intermediate algebraic states in such a proof must not be
claimed to be valid executions.

The same test verifies that Vacation of a particle after its own pair does not
prevent the other pair from using its defined `/child`; its Vanish waits for
that use. This is distinct from swapping successive occupants of one actual
position, which is not permitted.

## Redundancy is not just pairwise comparison

`precedence_choice.necessary_precedences` is a bounded exact oracle for the
precedences shared by every satisfying total order. It finds one satisfying
order and tries the reverse of each pair in that order. A reverse with no
satisfying completion proves that pair necessary. This is not the production
construction: it makes a quadratic number of satisfiability queries.

Extracting those precedences does not make all remaining cycle conditions
irredundant. For 100 generated three-particle histories with twelve ordinary
Moves, seed 931571, the collector finds 502 conditions. Of these, 137 follow
from ordinary precedence alone, 77 follow from the other conditions together
with ordinary precedence, and 288 have a violating order when individually
removed. These are logical classification counts, not construction timings or
a claim that every generated destructor is expressible in Define.

The reduced, source-validated integration case `joint_relationship_conditions`
uses eight ordinary Moves and no destructors. It has two possible two-particle
cycles and one possible three-particle cycle. The two smaller conditions and
the position-reuse ordering jointly imply the larger condition. Neither smaller
condition alone implies it, even after including every universally necessary
precedence.

The same-parent Move between `/second_right` and `/second_left` is important:
it preserves the parent relationship but waits for the previous occupant of
`/second_left`. That ordinary vacancy ordering connects the two cycle
conditions. A hypothetical check that ignored same-parent Moves entirely would
lose this information.

The regression in `test_two_cycle_conditions_jointly_imply_a_three_particle_condition`
checks all three implications with the exact finite oracle. Strict-order
negation is tested separately, including self-precedences and empty alternatives.
The source fixture validates with the real compiler; only its graph assertion
is an expected failure.

This refutes the proposed shortcut of obtaining complete semantic minimality
just by extracting necessary edges and comparing each condition with one other
condition. It does not change the permitted execution orders or add a semantic
requirement. Collecting an implied condition is redundant work, not a loss of
concurrency.

## Complete identity-based collection

`identity_algorithm.py` derives ordinary position and lifetime candidates and
relationship periods from resolved Creates, Moves, Vacates, and Vanishes. It
uses the existing `complete.algorithm.compare` and compact graph storage rather
than introducing a later graph reduction. Its input includes the supplying
Creates; open relationships need not have a Vacate or Vanish.

For each simultaneous destruction, the selected particle identities determine
whether its Vacate changes the position setter used by destruction work.
Nested destruction of a temporary particle does not select its surviving
defining particle, so that vacancy still supplies subsequent reuse of the same
position. No per-destructor copy is created.

The differential test checks both ordinary reachability and logical equivalence
of the complete relationship conditions against the independent finite model,
for the targeted witnesses and forty generated histories. Additional cases
check unended relationships, interface reuse across action executions, distinct
execution-local positions, and nested temporary-particle reuse. The last two
have normal Define integration fixtures as well.

This implementation collects the ordinary graph and relationship periods. The
exact relationship search remains a separate research implementation. These
checks do not establish complete modular construction, combined semantic
minimality, or an optimal performance bound.

### Two-setter ordinary collection

The identity construction needs at most two ordinary candidates: the setters of
the positions it fills or empties. An unused position's initial setter is its
defining particle's Create. Every later setter follows that initial setter.
An occupied source's filler also supplies the selected particle's Create,
directly or through earlier direct Moves. Explicitly collecting those Creates
again therefore leaves the same Comparison result.

The differential tests compare this reduced collection with the oracle that
still explicitly adds all existence requirements. Both have identical ordinary
reachability. When recording a lifetime use, the construction can also remove
old uses appearing in these at-most-two candidates: the new use already
depends on them. This bounded pruning needs no empirical cutoff. It does not
bound the potentially large final Vanish collection or the relationship-choice
calculation.

## Alternative paths and universally necessary cover pairs

The source-validated integration fixture
`alternative_paths_imply_a_lifetime_order` gives another obstruction to reducing
the complete construction to an ordinary partial order. Two particles each make
a temporary visit to the other's `/child`. Both begin by leaving a position of
`parent`; both end in positions defined by `helper`. Their temporary parent
relationships cannot coexist.

Whichever excursion completes first must use `helper` before the other begins.
Both must begin before `parent` can Vanish. Thus `create(helper)` necessarily
precedes `vanish(parent)`, although the ordinary graph has no path between them.
There is also no fixed operation necessarily between them: either beginning can
precede the Create, and either ending can follow the Vanish in some safe order.

The research regression verifies this with the exact oracle on the complete
sixteen-operation input, including all Vacates and Vanishes. The normal Define
integration fixture passes source validation and tracks the missing conditional
graph behavior with a complete ordinary dependency assertion and a nearby TODO.

The pair is therefore a cover of universally necessary precedence, but adding
it as an edge would duplicate what the alternative paths already enforce.
Extracting the intersection of all safe orders and building its ordinary cover
graph does not solve minimality of the combined representation.
