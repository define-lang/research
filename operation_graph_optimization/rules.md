# Requirement-based dependency construction

These rules describe the whole-program Particle Operation Dependency Graph. The
separate Action Parent Rule is unchanged. They use the position and particle
requirements in the specification; they do not replace actual references with
all spatial parent positions.

For every position, its current **supplier** is the operation that last filled
or emptied it. Remember also the operations that have required it occupied since
its last fill without emptying it. Initially there may be no supplier or uses.

When a Create makes a particle's assigned positions available, that Create is
their initial supplier. Every later supplier or occupied use of such a position
already depends on its defining particle's Create. Collecting one of those
operations therefore also satisfies that particle requirement. Moving the
defining particle does not change this supplier or make its positions newly
available.

For each Particle Operation:

1. Collect the Create of every particle whose assigned qualities its references
   use.
2. For a position being filled, collect its current supplier, when one exists.
   For an occupied position used without emptying it, collect its supplier. For
   a position being emptied, collect its preceding occupied uses, or its
   supplier if there are no such uses.
3. Combine these candidates for the entire operation, including both references
   of a Move. A candidate appearing for several reasons is still one operation.
   If a collected supplier or occupied use of a particle's assigned position is
   not that particle's Create, it already depends on that Create. Omit the
   Create from the collection, even if it was collected for another reason. If a
   collected operation is a preceding use of a required occupied position, that
   use also satisfies the requirement to follow that position's last fill; omit
   the separate fill candidate. Apply these omissions using the combined
   collection before any omissions are made.
4. Examine candidates from later to earlier in any order consistent with their
   already calculated dependencies. Keep a candidate unless a candidate already
   kept depends on it, directly or indirectly. The kept candidates are the
   operation's dependencies.
5. Record the operation as a use of the positions it requires occupied without
   emptying them. For every position it changes, replace the last change with
   this operation and clear the preceding uses. A preceding use may be forgotten
   when another remembered use depends on it. Retaining it is also correct;
   Comparison will exclude it when necessary.

For simultaneous Destroys, perform the collection for every selected particle
before recording any of their changes. No member of that group is a preceding
use or supplier for another member. Only the explicitly written target has the
statement's intermediate-reference requirements.

Destructors share the original particles' changing position state. Preserve its
last changes and preceding ordinary uses at destruction. The simultaneous
vacancies update ordinary occupancy, not that retained state. All destructors
accessing the same original position continue with the same retained record;
replacements do not use it. Apply the same rules to destructor operations, their
callees, and further destruction. The compiler may choose a permitted serial
destructor ordering to orient conflicts.

Positions defined by a particle move with it. A Move does not update their
relative occupancy records. Continued particle existence and the destruction
lifetime requirements remain separate from vacancy dependencies.

## Why the examination order works

Every occupied use already follows the last fill. Therefore collecting the uses
instead of both the uses and the fill preserves candidate reachability. A
forgotten use is likewise reached through the remembered use that replaced it.
This invariant also survives preserving the record for destruction, provided the
remembered uses and supplier are preserved together. Independent uses must not
be replaced by just the most recent use.

The same reasoning applies when a Create is collected for more than one reason.
A later supplier or occupied use of a position defined by that particle reaches
its Create regardless of why the Create was collected. The initial supplier is
the Create itself and cannot justify removing itself. When several omissions use
one another as witnesses, their strict backward dependency paths cannot form a
cycle: each removed candidate is eventually reached from one that remains. These
shortcuts change the work needed for Comparison, not its result.

Every dependency points earlier in a topological order of the calculated graph.
Suppose an excluded candidate would exclude another candidate. A kept candidate
already reaches the first, and therefore reaches the second too. Thus examining
only kept candidates gives exactly the specification's Comparison, including its
requirement that excluded candidates participate. The examination does not
change earlier rows or perform a later graph-minimization pass.

Every removed candidate is reached from a kept one, so no candidate ordering is
lost. Independently, an alternative path for a kept edge would begin with
another kept edge reaching its target, contradicting retention. These establish
reachability preservation and transitive minimality separately. Semantic safety
and edge necessity follow from the existing
[requirement construction](https://github.com/define-lang/define/blob/c2b03d0faa9dfc6ac12e6eee41538dcbb4afd583/proofs/operation_graph/theorems/requirement-construction.md)
and
[scheduling proof](https://github.com/define-lang/define/blob/c2b03d0faa9dfc6ac12e6eee41538dcbb4afd583/proofs/operation_graph/theorems/requirement-scheduling-proof.md).

## Implementation boundary

The standalone algorithm consumes resolved requirements, not source text or
compiler Operation Graph objects. Position identifiers distinguish the defining
particle or Action Execution and the relevant declaration. Retained occupancy
uses distinct record identifiers while all its users share those identifiers.
Its input must preserve written references and valid serial execution; graph
calculation cannot recover requirements discarded by source resolution.

An operation provides occupied uses, at most one filled position, at most one
emptied position, and the Create occurrences supplying its particle
requirements. Create has only a filled position, Destroy only an emptied
position, and Move has both. Filled and emptied positions are distinct and
disjoint from the occupied-use list. Repeated access to a position within one
operation is represented once. Overlapping candidate operations are possible
across these different requirements and are identical occurrences, which is why
their collection is a set.

A Create also identifies any positions made available by that new particle's
qualities. Recording a position can be delayed until its first possible use;
there is no requirement to enumerate unused qualities or every transitive child.
Each such record begins with the defining particle's Create as its supplier. An
initial local position with no supplying Create instead has no supplier.

The graph stores explicit occurrences. It is not an implementation of modular
action resolution, source validation, or reclamation. Its cost must be measured
against expanded occurrences, not just the number of written statements.
