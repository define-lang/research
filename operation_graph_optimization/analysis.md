# Derivation and implementation evidence

## What is being optimized

Time is primary; memory must remain feasible alongside the rest of a large
compilation. The input is valid, resolved operation requirements. Let `N` count
expanded occurrences, `R` count their position and particle requirements plus
supplied position-availability records, `P` count retained position records, and
`E` count the final explicit dependencies. An explicit result has an unavoidable
`Ω(N + E)` construction cost; reading this input also costs `Ω(R)`. These are
not lower bounds for arbitrary reachability queries, and do not prove the
complete algorithm optimal.

## Specialized rules

The rule document retains a common final Comparison but specializes the supply
and use calculation:

- Create supplies the new particle and the initial availability of positions
  defined by its assigned qualities. A later supplier of one of those positions
  already follows that Create. This avoids repeatedly rediscovering creation
  through long implied-operation sequences. The omission applies to the entire
  combined collection, including a Create collected as an occupancy supplier,
  not just a separately collected particle requirement. The initial supplier is
  the Create itself and is not a strict dependency witness.
- Filling consumes an empty-state supplier. There are no occupied uses of that
  empty state to collect.
- Emptying consumes preceding occupied uses; if there are any, their last fill
  is already reached through them. Independent uses cannot be replaced by just
  the most recent use.
- A Move combines its source vacancy and destination fill, plus the actual
  reference requirements. It does not update child-relative occupancy.
- Destroy supplies ordinary vacancy but does not supply retained occupancy or
  represent reclamation. Common-state selection is preserved before recording
  the group's changes.
- Remembered uses can replace earlier uses they provably follow. The
  implementation cheaply removes collected candidates from that position's use
  set when there are at most sixteen candidates. Comparison guarantees that the
  operation follows all of them, including candidates it excludes. For
  simultaneous operations the implementation uses final dependencies instead;
  those are also valid witnesses. Skipping this optional pruning for larger sets
  avoids multiplying a long reference by a large dependency set.
- A remembered use already collected for another reason can replace its fill
  supplier. Omissions are determined before applying them: a removed witness is
  itself reached through a later witness, so finite backward dependency order
  rules out a cycle of unsupported omissions.

For at most sixteen combined candidates, checking whether any candidate belongs
to a required position's remembered uses takes bounded work per requirement.
This recognizes earlier independent uses, not only the latest use. It avoids
repeated reachability questions across independently interleaved child
operations without storing another index. For larger candidate sets, checking
only the latest use is an optional partial shortcut; Comparison resolves
anything left. Both choices satisfy the same candidate-coverage argument.

These optional-work limits and the Comparison crossover are implementation
choices, not language rules. [Threshold measurements](thresholds.md) explain
their bounds, measured trade-offs, and why the values are not exact universal
optima.

None of these specializations requires or changes future value or external-call
semantics. Positions becoming available is not an additional Particle Operation;
the supplying event is the existing Create.

The shared mathematical obligation is: if a smaller candidate set is a subset of
the original, and every original candidate is either in that subset or reached
from a member of it, both sets have exactly the same remaining Comparison
candidates. An original remaining candidate must belong to the subset, since
otherwise its covering member would exclude it. Conversely, a subset candidate
excluded by an original candidate is also excluded by the subset member covering
that original candidate, using transitivity. This is checked in
`rule_equivalence.lean`. The supplier and remembered-use invariants above
discharge its coverage premise; the lemma alone does not supply those semantic
invariants.

The creation invariant follows by induction over calculated operations. A
position made available by Create `C` initially has supplier `C` and no uses. An
occupied use follows its supplier; an occupancy change follows that supplier or
preceding uses that already follow it. Thus each subsequent supplier and use
reaches `C`. Omissions in the current collection use only these previously
proved paths, and Comparison preserves their reachability before the new record
is stored. A supplier distinct from `C`, or any occupied use, therefore supplies
a strict path to `C`; `C` itself supplies no such strict path. Moving the
defining particle leaves these records unchanged, retaining a destructor record
preserves the invariant, and simultaneous collections all use the common prior
records. This justifies removing `C` across collection reasons without assuming
any unproved ordering or adding one.

## Why source geometry alone does not finish Comparison

Movement connects requirements at different positions. A candidate can follow
another through operations at positions not mentioned by the current operation.
The existing
[source example](https://github.com/define-lang/define/blob/c2b03d0faa9dfc6ac12e6eee41538dcbb4afd583/define/testdata/reference_graph/operation_graph_single_action_integration/move_excludes_create_fill_dependency_reached_through_source_dependency/test.dfn)
already exhibits such a connection through `holder`. Operation type and current
position relationships alone do not encode that intervening dependency path.
This does not prove that no stronger specialized rule exists; it rules out
discarding dependency information merely because a candidate's position seems
unrelated.

### Valid operations can express arbitrary dependency reachability

There is a direct construction for any finite directed acyclic graph, writing
`u → v` to mean that `v` must follow `u` (the reverse of a stored dependency).
This is a mathematical construction from the rules, not an assertion that the
arbitrary graphs in the subroutine test are compiler-generated graphs.

For each vertex `v`, create a particle at a distinct local `before_v`, with an
empty compatible local `after_v`. For each edge `e: u → v`, give `u` a distinct
assigned `/send_e` position and `v` a distinct assigned `/receive_e` position.
Initially Create one particle in each `/send_e`; leave each `/receive_e` empty.
The particles moved along edges need no assigned qualities. These initial
Creates precede the following construction in the chosen serial analysis.

Process vertices in topological order. For each incoming edge of `v`, execute:

```define
move the particle in position<after_u>::position</send_e> to position<before_v>::position</receive_e>.
```

Then execute the distinguished operation for `v`:

```define
move the particle in position<before_v> to position<after_v>.
```

Here `u`, `v`, and `e` stand for distinct generated names. Every edge transfer
is valid: its source vertex has already moved, its uniquely selected source
child is occupied, its uniquely selected destination child is empty, and its
destination vertex has not moved. Transferring a child does not move the
particles defining those positions.

The edge transfer requires `after_u` occupied, so it follows the distinguished
Move for `u`. It uses `before_v` occupied, so the distinguished Move for `v`
follows it. Different edge transfers have distinct changed positions; common
parent occupancy requirements are uses, not changes. Initial child Creates add
predecessors but cannot create paths between distinguished Moves. Consequently,
the distinguished Move for `v` depends on that for `u` exactly when the chosen
graph has a path from `u` to `v`. All particles can be automatically destroyed
afterward.

To ask a reachability question between two distinct vertices, reserve another
fresh assigned source position on one particle and destination position on the
other. Initialize its source particle before the distinguished Moves. After all
those Moves, transfer it between the corresponding `after` references. The
collected initial child Create is reached through its defining particle's Move;
the remaining candidates are exactly the two distinguished Moves. Comparison
keeps both precisely when neither reaches the other. Use fresh child positions
for further queries, so their changes do not supply dependencies for each other.

The construction uses `O(V + A + Q)` operations and assigned positions for `V`
vertices, `A` edges, and `Q` queries, with constant-length references. Thus
valid source does not justify assuming a tree, bounded width, or only local
dependency paths. This correspondence does **not** establish a superlinear lower
bound or prove the implemented reachability method optimal.

## Comparison implementation

Graph edges are appended once to compact integer arrays, with reverse links for
finding operations that directly depend on an earlier operation. Heights are one
plus the maximum dependency height. Strict dependency reachability decreases
height, so equal-height candidates are independent.

Collections of zero or one candidate need no reachability question or ordering.
Two candidates need at most one question and no sort. For other small
collections, examine candidates in decreasing height and check them against kept
candidates. Equal-height candidates cannot reach one another, so an entirely
equal-height collection returns immediately. At most 64 candidates use the
pairwise path. Larger collections first omit candidates that are direct
dependencies of other candidates, then expand the union of the remaining
candidate ancestry once. Both omissions satisfy the same candidate-coverage
argument above. The traversal stops below either the minimum candidate height or
minimum occurrence identifier, and can finish as soon as only one candidate has
not been excluded. Every finite nonempty acyclic collection has a maximal
member, so that last candidate cannot be excluded. Large collections need no
candidate sort. Thus a wide set of equal-height uses does not cause pairwise
work. This constructs only the final current row; there is no full-graph
minimization pass.

An operation with no direct consumers cannot be reached from another operation.
Other uncached questions search breadth-first from both ends, alternating one
edge or completed vertex at a time. Meeting proves a path; exhaustion of either
side disproves it. Heights and occurrence identifiers both increase strictly
along forward edges. Bounds from both orders exclude vertices that cannot lie on
the requested path; no physical execution order is inferred from the
identifiers. Work is bounded by a constant multiple of the cheaper of the two
complete directional searches, including visited vertices and scanned edges.
This matters for old vacancies: the former particle may have a short independent
sequence of later operations, while the operation now filling the vacancy has a
very long preceding sequence. A backward-only search repeatedly walks that long
sequence unnecessarily.

The reverse links increase graph storage to approximately `24N + 24E` bytes,
plus array allocation overhead and small object headers. This is a deliberate
time-first trade-off with linear, predictable memory growth.

A reached forward vertex can also supply a reusable question. If an operation
`J` depends on the original target, a positive answer to whether the following
operation depends on `J` proves the original path. A negative answer permits
pruning only the forward paths through `J`, not other paths from the original
target. This is useful when many different targets lead to a common operation
and then to a long independent sequence. Repeatedly memoizing the common
question avoids separately walking that sequence for each original target. The
search considers one such multiple-dependency vertex per expensive query. When
the forward search encounters a cached vertex, a negative answer permits
omitting its continuation. Admitting a new cache entry does not remove vertices
already queued by the breadth-first search. The search never treats a negative
answer about one path as a negative answer about every path.

After three searches for the same target each visit at least 64 vertices, the
target is promoted to a memoized reachability question. A bounded record of the
1,024 most recent expensive targets prevents this admission information from
growing with the graph. Each byte of a column records unknown, false, or true
for one preceding graph vertex. An iterative evaluation derives the answer from
the vertex's dependencies. A positive answer needs one positive dependency; a
negative answer requires all eligible dependencies negative. The target itself
is the positive base case; vertices too low to reach it are excluded by height.

Earlier graph rows never change, so these answers remain valid after appending
operations. While a target's column remains resident, each explored vertex is
completed once and each explored edge is examined only a constant number of
times. Its aggregate discovery cost is `O(N + E)` over the explored portion,
plus constant work per cached query. This matches graph inspection cost for that
memoized evaluation; it is not a lower bound against every possible index.

At most 1,024 target columns are retained, with a 64 MiB total logical byte
budget by default. A column begins at its target's occurrence identifier and
ends at the greatest following occurrence queried for that target. It allocates
neither the prefix before the target nor the unused suffix after the query.
Those earlier occurrences cannot reach the target, because edges point backward
in occurrence identifiers. The target is the positive entry at index zero.
Least-recently-used targets are evicted to fit. If a query's required column
would exceed the budget, searches proceed without caching. Cached answers remain
valid when columns grow or the graph grows. The graph's width does not determine
index size. Bytearray allocator overhead and temporary growth allocations are
additional to the logical budget; they remain bounded by a constant multiple of
that budget. The base graph and position analysis are not charged to the
optional cache budget.

## Alternatives evaluated

The [follow-up experiments](optimization_experiments.md) extend these earlier
experiments with freely mixed valid operation orders. They compare selected-path
witnesses, caching complete ancestor rows, retaining pruned occupancy uses,
depth-first versus breadth-first searches, Comparison thresholds, and target and
byte budgets. The final implementation retains no historical-use set and no
selected-path index. The measurements distinguish their exploratory results from
the final multi-seed matrix.

Promoting a target after just one expensive search regressed random overlapping
Moves: the answer was rarely reused enough to amortize allocating a column.
Three repeated expensive queries admit a shared target while avoiding this cost
for one-off questions.

An eager fixed-number-of-paths index recorded the latest reachable occurrence on
each indexed path. The path correspondence is exact: reaching a path member
implies reaching every earlier member. This is the principle in the simple chain
index described by Bulteau et al.,
[Incremental Reachability Index](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.SEA.2025.9).
Only selected paths were indexed, with search for other targets; therefore its
memory was bounded independently of width. Even with packed counters,
maintaining the index slowed ordinary workloads and could spend its paths on
early short-lived branches. It has been removed from the result implementation.

Remembering occupied uses as immutable linked records made preservation at
destruction cheap, but prevented cheap removal of redundant uses except at the
beginning of a list. Mutable sets with bounded direct-dependency pruning
improved the shared-parent workload's time and memory. Preserving a retained
record copies only that record's use set, not a particle structure or action
graph. Count the total copied entries as `F`; retention costs `O(F)` and cannot
be hidden in a claimed constant-time fork.

Full transitive closure, unbounded path clocks, and expanding a Move into all
transitive child positions were rejected as default representations because
their memory or preprocessing can grow beyond feasible compilation sizes. The
general transitive-reduction result of Aho, Garey, and Ullman
([1972 paper](https://www.cs.tufts.edu/comp/150FP/archive/al-aho/transitive-reduction.pdf))
concerns arbitrary graphs with a particular size measure. It supplies neither a
matching lower bound for these valid-source inputs nor permission to introduce a
prohibited full-graph minimization pass.

## Bounds and scope

Position analysis uses at most `O(P + R + F)` space before any final-use
releases, including the explicitly counted retained-use copies. Collection and
updates cost `O(R + C + F)`, where `C` counts emitted candidate entries,
including inherited uses consumed in retained states. Candidate ordering costs
`O(C)` because only bounded small sets are sorted; searches add their actual
visited vertices and edges, and graph storage costs `O(N + E)`. The bounded
cache does not give a linear worst-case bound when expensive targets continually
change or exceed its memory budget.

These costs count expanded operations and explicit reference lengths. The
algorithm does not flatten an action call graph itself, but neither does it
implement reusable per-action summaries. Source resolution, modular interfaces,
and actual-interaction lifetime analysis remain distinct compiler tasks. Adding
a whole-action barrier to avoid those tasks would change the required result.

## Validation

The reference interpreter orients all earlier conflicts using full per-position
histories, then calculates the necessary current dependencies. It deliberately
does not share last-supplier tracking, use pruning, or the optimized Comparison.
Generated source is validated by the real compiler; its current graph is not the
oracle for these proposed rules.

Checks include flat random Create/Move/Destroy programs, deep written
references, movement of defining particles, implied constructor access versus
written caller access, simultaneous vacancies, and retained destructor movement.
Small examples enumerate schedules and check edge necessity. The benchmark
checker independently constructs a random topological schedule and verifies
exact occupant identities, empty destinations, particle creation requirements,
and final occupancy.

The million-operation experiments include both meaningful randomized source
orders and independent randomized runtime schedules. Timing separates
generation, rule calculation, and verification. Resource limits belong to each
benchmark process, not the compiler or test runner.
