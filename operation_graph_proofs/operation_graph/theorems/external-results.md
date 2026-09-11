# Correspondence with Established Mathematics

These correspondences supply mathematical results, not additional premises about
Define. The source-requirement and incremental Comparison arguments remain
separate obligations.

## Cover relations

For a strict precedence relation, `CoverPair precedence following previous` is
the standard cover relation: the endpoints are related and there is no strictly
intermediate element. In chronological order, `previous` is covered by
`following`. Our dependency arrows point in the opposite direction.

The Lean definition uses mathlib's
[`CovBy`](https://github.com/leanprover-community/mathlib4/blob/v4.32.2/Mathlib/Order/Defs/PartialOrder.lean),
with its `<` relation set to `precedence`. This reverses the conventional
chronological order and preserves our argument order. `CovBy` requires only an
`LT` instance, so this replacement also preserves the generic definition's scope
for arbitrary relations. Transitivity and irreflexivity are proved separately
wherever the order-theoretic interpretation needs them.

## Finite transitive reduction

Use Theorem 1 of Aho, Garey, and Ullman,
[_The Transitive Reduction of a Directed Graph_](https://www.cs.tufts.edu/comp/150FP/archive/al-aho/transitive-reduction.pdf),
1972, p. 132. For a finite acyclic directed graph, it gives the unique
inclusion-minimal graph having the same reachability, contained in every graph
with that reachability. Consequently it is also the unique fewest-edge graph.

The correspondence takes the finite occurrence set as the vertex set and the
dependency relation as the edge set. Our `Reaches` is their positive-length path
relation: in an acyclic graph a path cannot repeat an edge or vertex. Strictly
decreasing occurrence ranks exclude cycles and loops, satisfying their
acyclicity hypothesis. Independently proved completeness and minimality identify
the calculated graph with their unique graph. The theorem is used only to
characterize the result, not to add a minimization step to Comparison.

This citation replaces the finite uniqueness argument, not the unbounded
rank-difference argument in `cover_graph.lean`. Mathlib's
`lt_iff_transGen_covBy` requires locally finite order intervals; our generic
rank map need not be injective and does not imply that hypothesis. Those generic
proofs therefore remain.

## Finite schedules and adjacent exchanges

Use the connectivity result proved with Lemma 2.2 of Mareike Massow,
[_Linear Extension Graphs and Linear Extension Diameter_](https://page.math.tu-berlin.de/~felsner/Diplomarbeiten/diss_massow_genehmigt.pdf),
2009, p. 25: the linear extensions of a finite poset are connected by adjacent
exchanges of incomparable elements.

For a finite occurrence set `S`, define `a < b` to mean `precedence b a`.
Conflict reachability is transitive, and strictly decreasing ranks make it
irreflexive. Adding equality therefore gives a partial order on `S`. A
duplicate-free schedule listing exactly `S` respects precedence precisely when
it is a linear extension of this order. Massow's edges are exactly our adjacent
incomparable exchanges. This discharges the hypotheses for the finite scheduling
arguments; it does not prove that an exchange preserves Define execution.

`RespectsPrecedence precedence` uses Lean's standard
[`List.Pairwise`](https://github.com/leanprover/lean4/blob/v4.32.2/src/Init/Data/List/Pairwise.lean)
with relation `fun earlier later => ¬precedence earlier later`. Its empty and
cons cases exactly express our schedule condition, without requiring an order
instance. Its helper results reuse `List.Pairwise.sublist`, `List.Pairwise.imp`,
`List.pairwise_append`, and `List.pairwise_iff_getElem`. No matching
adjacent-incomparable connectivity theorem was found in Lean, Batteries, or
mathlib v4.32.2, so `respecting_permutations_connected` retains its checked
proof. It also permits arbitrary precedence relations, unlike the cited poset
formulation.

## Limits of the other correspondences

Trace theory identifies sequences modulo independent adjacent exchanges. It does
not by itself prove our exact-effect enabledness, source correspondence, or
necessity results. Likewise, read/write noninterference conditions do not alone
prove that reversing a conflicting pair is invalid. The proofs of genuine
changes, exact required values, and Define-specific interference remain here;
neither analogy is used as a substitute for those arguments.
