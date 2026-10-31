# Circuits of Treewidth k Have SDDs of Size n·2^O(k)

This note proves that every Boolean circuit whose graph has treewidth k can be
represented, over its n inputs only, by a sentential decision diagram (SDD) of
size n·2^O(k). The SDD respects a vtree built from a tree decomposition of the
circuit, uses no auxiliary variables, and is not compressed in general. The
dependence on k is optimal up to the constant in the exponent, by a known lower
bound. For circuits of pathwidth k, the vtree can be taken left-linear.

## 1. Results

Throughout, a _circuit_ has n input vertices and gates of three kinds: AND and
OR gates of any fan-in (an AND or OR with no wires is the constant 1 or 0), and
NOT gates of fan-in 1. Wires may also carry negations, so And-Inverter Graphs
(AIGs) are a special case. The circuit's _graph_ has the inputs and gates as
vertices and an undirected edge for each wire. Section 2 gives the precise
definitions of treewidth, vtrees, SDDs, and their size.

**Theorem 1.1.** Let C be a circuit with n inputs whose graph has a tree
decomposition of width k. Then there is a vtree T over the inputs of C and an
SDD respecting T that computes C, with at most n·2^(32k+65) elements and at
most n·2^(16k+34) decision nodes. Every decision node at a vtree node t has
its primes at the left child of t and its subs at the right child of t (or
constant subs).

The constants are not optimized. For AIGs nothing changes but the constants:
the theorem already covers them, and the lower bound below is attained by
AIGs.

**Theorem 1.2 (pathwidth).** If the graph of C has a path decomposition of
width k, then the vtree in Theorem 1.1 can be chosen _left-linear_ (every right
child is a leaf), with at most n·2^(24k+56) elements.

**Corollary 1.3 (unambiguous OBDDs).** Let f be a Boolean function over
x₁, …, xₙ. Suppose that f and ¬f are computed by complete unambiguous
nondeterministic OBDDs with the order x₁, …, xₙ and with at most W nodes in each
layer. Then f has an SDD of size O(n·W⁸) that respects the left-linear vtree
for x₁, …, xₙ.

Corollary 1.3 removes the auxiliary variables from a theorem of Bollig and
Buttkus (see Section 9). Bollig and Buttkus do not require completeness; a uOBDD can
be made complete at a cost polynomial in n, so the corollary also gives a
polynomial bound in their setting.

**Proposition 1.4 (lower bounds).** There is a constant c > 0 such that for
every k there are circuits (and AIGs) of treewidth O(k), with arbitrarily many
inputs, every SDD of which has size at least 2^(ck). Every SDD for a function
that depends on all n ≥ 2 of its inputs has at least n/2 elements.

The first statement of Proposition 1.4 is a known result of Amarilli, Capelli,
Monet, and Senellart, quoted here, not re-proved; Section 9 explains it.

Together, Theorem 1.1 and Proposition 1.4 say that the smallest SDD for a
circuit of treewidth k has size between max(n/2, 2^Ω(k)) and n·2^O(k), so the
singly exponential dependence on k cannot be improved beyond the constant in
the exponent. The question of whether _compressed_
(canonical) SDDs also have size n·2^O(k) is not settled here; Section 9
discusses it.

### What is new

Bova and Szeider showed that bounded circuit treewidth gives bounded SDD width,
with a bound triple exponential in k for canonical SDDs. Amarilli et al. gave a
singly exponential bound for deterministic structured DNNFs (d-SDNNFs) and
asked whether it could be extended to SDDs. Bollig and Farenholtz showed how to
turn d-SDNNFs for f and ¬f over the same vtree into an SDD, but only over a
vtree with auxiliary variables. Theorem 1.1 answers the question of Amarilli et
al. positively for SDDs without auxiliary variables, with a singly exponential
dependence on k. Section 9 gives references.

### The idea

Fix a vtree node t. As in d-SDNNF constructions, the construction guesses a
valuation σ of a separator bag at t and considers the set Q_t(σ) of
assignments of the inputs below t that are consistent with σ. These sets
overlap, so they cannot be the primes of an SDD. But once the inputs outside t
are fixed, each inside assignment is consistent with exactly one of the states
that occur with those outside inputs (Lemma 4.4 and Corollary 4.5), so for one
fixed outside assignment the sets Q_t(σ) do partition the inside assignments.

An SDD decision node at t needs a single partition of its left side that works
for every value of its right side. The construction uses _pair cells_
Q_t(σ₀) ∩ Q_t(σ₁), the cells of the common refinement of the partitions for
two fixed outside assignments, and shows that two outside assignments are
always enough:

- A pair cell at t is a product of a left part and a right part, and fixing the
  right part to any assignment consistent with σ_i gives one outside assignment
  per state for the left child. So a pair cell decomposes into pair cells at
  the left child (Lemma 5.4).
- Gates that are in the bag of a right child but not in its parent's bag give
  unions of cells (_joins_). The shape condition (S2) makes the right part of
  such a union the same for all its cells, so again one outside assignment per
  state suffices (Lemma 5.5).
- At the root, the function is a union of cells. The shape condition (S1)
  makes the root's right child a single input, whose two values give the two
  outside assignments (Lemma 5.6). This is why pairs appear at all.

Any tree decomposition can be reshaped to satisfy (S1) and (S2) by moving
inputs up the tree, so that every internal right child gets a leaf as its right
child (Lemma 6.1).

## 2. Definitions

**Assignments.** For a finite set S of variables, {0,1}^S is the set of
assignments of S. For disjoint S and S′, (a, b) denotes the union of a ∈
{0,1}^S and b ∈ {0,1}^S′. A _Boolean function over S_ is a subset of {0,1}^S
(its set of models). When S ⊆ S′, a function over S is also viewed as a
function over S′ that ignores the other variables.

**Circuits.** A circuit C has a set X of n input vertices and a set G of gates,
with a directed acyclic set of wires. Each gate is an AND gate or an OR gate,
and each wire is plain or negated; a NOT gate is an AND gate with one negated
wire, and constants are AND and OR gates with no wires. One vertex o is the
output. For an assignment x ∈ {0,1}^X, val_x(v) is the value of vertex v,
computed in the usual way, and C computes the function {x : val_x(o) = 1}.

**Treewidth.** A tree decomposition of a graph H is a tree T with a bag β(t) ⊆
V(H) for each node t such that every vertex is in some bag, the ends of every
edge are together in some bag, and for every vertex v the nodes whose bags
contain v form a connected subtree of T. Its width is max_t |β(t)| − 1. The
treewidth of H is the least width of a tree decomposition, and the pathwidth is
the least width of a tree decomposition whose tree is a path. The treewidth of
a circuit is the treewidth of its graph.

**Vtrees.** A vtree over a finite set X is a rooted binary tree in which every
internal node has an ordered pair of children (left, right) and whose leaves are
in one-to-one correspondence with X. For a node t, T_t is the subtree rooted at
t and V_t ⊆ X is the set of variables at the leaves of T_t. For an internal
node t, t.l and t.r are its children. A vtree is _left-linear_ if every right
child is a leaf.

**SDDs.** This note uses Darwiche's definition [Darwiche 2011], in the strict
form in which a decision node is attached to one vtree node and its primes and
subs to that node's children. Let T be a vtree. An _SDD node respecting a vtree
node t_ is one of:

- a constant ⊥ or ⊤ (respecting every node), computing ∅ or {0,1}^{V_t};
- a literal x or ¬x, where t is the leaf for x;
- a decision node {(p₁, s₁), …, (p_m, s_m)} with m ≥ 1, where t is internal,
  each p_i (a _prime_) is an SDD node respecting t.l, each s_i (a _sub_) is an
  SDD node respecting t.r, and the functions computed by p₁, …, p_m are
  nonempty, pairwise disjoint, and cover {0,1}^{V_{t.l}}. It computes the
  union of the products p_i × s_i. Each pair (p_i, s_i) is an _element_.

An SDD is a finite set of such nodes, shared as in a directed acyclic graph,
with a root node respecting the root of T. Its _size_ is the total number of
elements of its decision nodes [Darwiche 2011]. Darwiche's definition also
lets a prime or sub respect a descendant of the child; every SDD in the strict
form is an SDD in that sense, so upper bounds for the strict form hold for
SDDs in general, and the lower bounds quoted in Section 9 hold for all SDDs. An
SDD is _compressed_ if the subs of every decision node compute distinct
functions; the SDDs built here are not compressed in general.

## 3. Relational tree decompositions

The construction does not use the circuit directly. It uses a structure that
records a tree decomposition together with the gate constraints placed in the
bags. Let X be the set of inputs.

**Definition 3.1.** A _relational tree decomposition_ (RTD) for a function f
over X is a tuple (U, T, B, L, Acc) where:

- U is a finite set of _vertices_ with X ⊆ U, and each vertex u has a finite
  domain D_u, with D_x = {0,1} for x ∈ X. A _valuation_ of a set S ⊆ U assigns
  to each u ∈ S a value in D_u; val(S) is the set of valuations of S.
- T is a vtree over X.
- B assigns to each node t of T a _bag_ B(t) ⊆ U, with B(ℓ) = {x} for the leaf
  ℓ of each input x.
- L assigns to each node t a _relation_ L(t) ⊆ val(B(t)), with L(ℓ) = val({x})
  at leaves.
- Acc ⊆ val(B(r)) for the root r of T.

and the following hold.

- (C) Connectivity. Every vertex lies in some bag, and for every vertex u the
  nodes t with u ∈ B(t) form a connected subtree of T.
- (U) Unique solutions. A _solution_ for x ∈ {0,1}^X is a valuation ν of U
  with ν(x′) = x(x′) for every input x′ and ν|B(t) ∈ L(t) for every node t.
  For every x there is exactly one solution, written ν_x.
- (F) For every x, f(x) = 1 if and only if ν_x|B(r) ∈ Acc.

The _state count_ of a set S ⊆ U is |val(S)| = ∏_{u∈S} |D_u|; for Boolean
vertices it is 2^|S|. For a node t, st_t(x) := ν_x|B(t) is the _state_ of t on
x.

**Notation.** For a node t let In(t) := ⋃_{s ∈ T_t} B(s) and Out(t) :=
⋃_{s ∉ T_t} B(s). For a non-root node t with parent p, the _interface_ of t is
I(t) := B(t) ∩ B(p). For valuations σ of B(t) and τ of B(t′) where t′ is a
child of t, write τ ≈ σ if τ and σ agree on I(t′). For x ∈ {0,1}^X and
y ∈ {0,1}^{V_t}, x[t ← y] is the assignment that equals y on V_t and x
elsewhere. For a node t and x ∈ {0,1}^X, x|_t denotes the restriction of x to
V_t.

**Lemma 3.2 (separation).** In an RTD:

1. For an internal node t: In(t) = In(t.l) ∪ In(t.r) ∪ B(t), In(t.l) ∩ In(t.r)
   ⊆ B(t), and In(t.l) ∩ B(t) = I(t.l) (likewise for t.r).
2. For a non-root node t and any node s ∉ T_t: B(s) ∩ In(t) ⊆ I(t).
3. For any node t: V_t ⊆ In(t), and every input in In(t) \ V_t lies in I(t).

_Proof._ Each claim follows from (C), because the path in T between a node of
T_t and a node outside T_t passes through t and its parent, and the path
between a node of T_{t.l} and a node of T_{t.r} passes through t.

1. The first equation holds by definition. If u ∈ In(t.l) ∩ In(t.r), then u is
   in a bag of T_{t.l} and in a bag of T_{t.r}, so u ∈ B(t). If u ∈ In(t.l) ∩
   B(t), then u is in a bag of T_{t.l} and in B(t), so u ∈ B(t.l), and u ∈
   B(t.l) ∩ B(t) = I(t.l).
2. If u ∈ B(s) ∩ In(t), then u is in B(s) with s ∉ T_t and in a bag of T_t, so
   u ∈ B(t) and u ∈ B(parent of t).
3. The leaf of every x ∈ V_t is in T_t and has bag {x}. If x ∈ In(t) \ V_t,
   the leaf of x is outside T_t and its bag contains x, so x ∈ I(t) by part 2.
   ∎

## 4. Inner witnesses

**Definition 4.1.** Let t be a node and σ ∈ val(B(t)). An _inner witness_ for
(t, σ, y), where y ∈ {0,1}^{V_t}, is a valuation μ of In(t) with μ|B(t) = σ,
μ(x) = y(x) for x ∈ V_t, and μ|B(s) ∈ L(s) for every s ∈ T_t. Let

> Q_t(σ) := {y ∈ {0,1}^{V_t} : some inner witness exists for (t, σ, y)}.

At a leaf ℓ for input x, In(ℓ) = {x} and Q_ℓ(σ) = {σ(x)}, the literal that
sets x to σ(x).

**Lemma 4.2 (restriction).** For every node t and x ∈ {0,1}^X,
x|_t ∈ Q_t(st_t(x)), and st_t(x) ∈ L(t).

_Proof._ ν_x restricted to In(t) is an inner witness. ∎

**Lemma 4.3 (factorization).** Let t be internal with children a = t.l and
b = t.r, and σ ∈ val(B(t)). Then (y_a, y_b) ∈ Q_t(σ) if and only if σ ∈ L(t),
y_a ∈ A_σ, and y_b ∈ D_σ, where

> A_σ := ⋃ {Q_a(τ) : τ ∈ val(B(a)), τ ≈ σ},  D_σ := ⋃ {Q_b(τ) : τ ∈ val(B(b)), τ ≈ σ}.

_Proof._ If μ is an inner witness for (t, σ, (y_a, y_b)), then σ = μ|B(t) ∈
L(t), μ restricted to In(a) is an inner witness for (a, μ|B(a), y_a) with
μ|B(a) ≈ σ, and likewise for b.

Conversely, let μ_a and μ_b be inner witnesses for (a, τ_a, y_a) and
(b, τ_b, y_b) with τ_a ≈ σ and τ_b ≈ σ. Define μ on In(t) = In(a) ∪ In(b) ∪
B(t) by μ := σ on B(t), μ := μ_a on In(a) \ B(t), and μ := μ_b on
In(b) \ B(t). This is well defined because In(a) ∩ In(b) ⊆ B(t) (Lemma 3.2).
On In(a) the valuation μ equals μ_a: the only vertices of In(a) where μ is
defined by σ are those of In(a) ∩ B(t) = I(a), where μ_a = τ_a = σ. Likewise μ
equals μ_b on In(b). So μ satisfies L(s) for every s in T_a or T_b, it
satisfies L(t) because μ|B(t) = σ, and it agrees with (y_a, y_b) on V_t =
V_a ∪ V_b. ∎

**Lemma 4.4 (replacement).** Let t be a node, w ∈ {0,1}^X, τ ∈ val(B(t)), and
y ∈ Q_t(τ). If t is not the root, assume also that τ agrees with st_t(w) on
I(t). Then st_t(w[t ← y]) = τ, and ν_{w[t←y]} agrees with ν_w on every vertex
outside In(t).

_Proof._ Let μ be an inner witness for (t, τ, y). Define ν := μ on In(t) and
ν := ν_w elsewhere. We show that ν is a solution for w[t ← y]; by (U) it is
then ν_{w[t←y]}, and both claims follow.

For s ∈ T_t, B(s) ⊆ In(t), so ν|B(s) = μ|B(s) ∈ L(s). For s ∉ T_t, every
vertex of B(s) ∩ In(t) is in I(t) (Lemma 3.2), where μ = τ = ν_w; so ν|B(s) =
ν_w|B(s) ∈ L(s). (If t is the root, every s is in T_t.) For inputs: on V_t, ν =
μ = y. An input x′ ∉ V_t is either outside In(t), where ν(x′) = ν_w(x′) =
w(x′), or in In(t) \ V_t ⊆ I(t) (Lemma 3.2), where ν(x′) = τ(x′) = ν_w(x′) =
w(x′). ∎

**Corollary 4.5.** Let t be a node, w ∈ {0,1}^X, and y ∈ {0,1}^{V_t}. If
y ∈ Q_t(τ) and τ agrees on I(t) with st_t(w[t ← y′]) for some y′ ∈
{0,1}^{V_t} (no condition at the root), then τ = st_t(w[t ← y]).

_Proof._ Apply Lemma 4.4 to w[t ← y′], noting (w[t ← y′])[t ← y] = w[t ← y].
∎

Corollary 4.5 is the partition property. Fix the inputs outside t (those of
w). Then each inside assignment y lies in Q_t(τ) for exactly one τ among the
states that occur with these outside inputs, namely τ = st_t(w[t ← y]).

## 5. The SDD construction

**Theorem 5.1.** Let (U, T, B, L, Acc) be an RTD for f such that

- (S1) the right child of the root of T is a leaf, and
- (S2) for every internal node t that is the right child of its parent p,
  B(t) ∩ B(t.r) ⊆ B(p); equivalently, I(t.r) ⊆ I(t).

Then f has an SDD respecting T, in the strict form of Section 2, whose number
of elements is at most

> |val(B(r.l))|² + Σ_{t internal, t ≠ r} N(t) · |val(B(t.l))|²,

where r is the root, N(t) := |val(B(t))|² if t is a left child, and N(t) :=
|val(I(t))|² if t is a right child. The number of decision nodes is at most
1 + Σ_{t internal, t ≠ r} N(t).

(The two equivalent forms of (S2): I(t.r) = B(t.r) ∩ B(t), and B(t.r) ∩ B(t) ⊆
B(p) means B(t.r) ∩ B(t) ⊆ B(t) ∩ B(p) = I(t).)

The rest of this section proves Theorem 5.1. Fix the RTD.

**Definition 5.2.** For a node t and σ₀, σ₁ ∈ val(B(t)), the _pair cell_ is

> Cell_t(σ₀, σ₁) := Q_t(σ₀) ∩ Q_t(σ₁),

a function over V_t. For a non-root node t and π₀, π₁ ∈ val(I(t)), the _join_
is

> Join_t(π₀, π₁) := J_t(π₀) ∩ J_t(π₁), where J_t(π) := ⋃ {Q_t(σ) : σ ∈ val(B(t)), σ|I(t) = π}.

A _witness pair_ for a pair cell (t, σ₀, σ₁) is a pair (w₀, w₁) of
assignments of X with st_t(w_i) = σ_i; for a join (t, π₀, π₁) it is a pair
with st_t(w_i)|I(t) = π_i. A pair cell or join with a witness pair is
_realizable_.

**Lemma 5.3 (fibers).** Let a be a node and (w₀, w₁) ∈ ({0,1}^X)². For
y ∈ {0,1}^{V_a}, let φ(y) := (st_a(w₀[a ← y]), st_a(w₁[a ← y])). Then:

1. The nonempty fibers φ⁻¹(τ₀, τ₁) are pairwise disjoint and cover
   {0,1}^{V_a}.
2. Each nonempty fiber φ⁻¹(τ₀, τ₁) equals Cell_a(τ₀, τ₁), and
   (w₀[a ← y], w₁[a ← y]) is a witness pair for it, for any y in the fiber.

_Proof._ Part 1 holds for the fibers of any map. For part 2, let z be in the
fiber, so st_a(w_i[a ← z]) = τ_i. Then z ∈ Q_a(τ_i) by Lemma 4.2, so the fiber
is contained in the cell, and the witness pair claim holds by definition.
Conversely let y ∈ Cell_a(τ₀, τ₁). Then y ∈ Q_a(τ_i), and τ_i agrees with
st_a(w_i[a ← z]) = τ_i on I(a), so Corollary 4.5 (with y′ = z) gives
τ_i = st_a(w_i[a ← y]). So φ(y) = (τ₀, τ₁). ∎

**Lemma 5.4 (deciding a pair cell).** Let t be internal with a = t.l,
b = t.r, and let (w₀, w₁) be a witness pair for the pair cell (t, σ₀, σ₁). Let
φ be as in Lemma 5.3 for a and (w₀, w₁). Let y_a be in a nonempty fiber
φ⁻¹(τ₀, τ₁). Then for every y_b ∈ {0,1}^{V_b}:

> (y_a, y_b) ∈ Cell_t(σ₀, σ₁) ⟺ [τ₀ ≈ σ₀ and τ₁ ≈ σ₁] and y_b ∈ Join_b(σ₀|I(b), σ₁|I(b)).

Moreover, if τ₀ ≈ σ₀ and τ₁ ≈ σ₁, then (w₀[a ← y_a], w₁[a ← y_a]) is a
witness pair for the join (b, σ₀|I(b), σ₁|I(b)).

_Proof._ By Lemma 4.3, (y_a, y_b) ∈ Q_t(σ_i) iff σ_i ∈ L(t), y_a ∈ A_{σ_i},
and y_b ∈ D_{σ_i}. Here σ_i = st_t(w_i) ∈ L(t) by Lemma 4.2. Also D_{σ_i} =
J_b(σ_i|I(b)), because τ ≈ σ_i for τ ∈ val(B(b)) means τ|I(b) = σ_i|I(b). So
it remains to show y_a ∈ A_{σ_i} ⟺ τ_i ≈ σ_i.

If τ_i ≈ σ_i, then y_a ∈ Q_a(τ_i) ⊆ A_{σ_i} by Lemma 5.3. Conversely, suppose
y_a ∈ Q_a(τ) with τ ≈ σ_i. On I(a) ⊆ B(t) ∩ B(a), τ agrees with σ_i = ν_{w_i}|B(t),
hence with st_a(w_i) = st_a(w_i[a ← w_i|_a]). Corollary 4.5 gives τ =
st_a(w_i[a ← y_a]) = τ_i, so τ_i ≈ σ_i.

For the witness pair, suppose τ_i ≈ σ_i. Let w′_i := w_i[a ← y_a]. The pair
(y_a, w_i|_b) lies in Q_t(σ_i) by Lemma 4.3: σ_i ∈ L(t), y_a ∈ A_{σ_i}, and
w_i|_b ∈ Q_b(st_b(w_i)) ⊆ D_{σ_i}, because st_b(w_i) agrees with σ_i on I(b)
(both are restrictions of ν_{w_i}). Lemma 4.4 applied to t, w_i, σ_i, and
(y_a, w_i|_b) gives st_t(w′_i) = σ_i, since w_i[t ← (y_a, w_i|_b)] = w′_i.
Hence st_b(w′_i)|I(b) = ν_{w′_i}|I(b) = σ_i|I(b). ∎

**Lemma 5.5 (deciding a join).** Let t be an internal node that is a right
child, with a = t.l and b = t.r, and assume (S2) at t: I(b) ⊆ I(t). Let
(w₀, w₁) be a witness pair for the join (t, π₀, π₁), and φ be as in Lemma 5.3
for a and (w₀, w₁). For i ∈ {0, 1} let

> R_i := {τ ∈ val(B(a)) : τ ≈ σ for some σ ∈ L(t) with σ|I(t) = π_i}.

Let y_a be in a nonempty fiber φ⁻¹(τ₀, τ₁). Then for every y_b:

> (y_a, y_b) ∈ Join_t(π₀, π₁) ⟺ [τ₀ ∈ R₀ and τ₁ ∈ R₁] and y_b ∈ Join_b(π₀|I(b), π₁|I(b)).

Moreover, if τ₀ ∈ R₀ and τ₁ ∈ R₁, then (w₀[a ← y_a], w₁[a ← y_a]) is a
witness pair for the join (b, π₀|I(b), π₁|I(b)).

_Proof._ Fix i and write π = π_i. By Lemma 4.3,

> J_t(π) = ⋃ {A_σ × D_σ : σ ∈ L(t), σ|I(t) = π}.

For every σ in this union, σ|I(b) = π|I(b) because I(b) ⊆ I(t), so D_σ =
J_b(π|I(b)) is the same set for all of them. Hence

> J_t(π) = (⋃ {Q_a(τ) : τ ∈ R_i}) × J_b(π|I(b)).

(If no σ qualifies, both sides are empty.) So it remains to show that y_a ∈
⋃_{τ ∈ R_i} Q_a(τ) ⟺ τ_i ∈ R_i.

If τ_i ∈ R_i, then y_a ∈ Q_a(τ_i) by Lemma 5.3. Conversely, suppose y_a ∈
Q_a(τ) with τ ≈ σ, σ ∈ L(t), and σ|I(t) = π. First, w_i|_b ∈ D_σ: by Lemma 4.2,
w_i|_b ∈ Q_b(st_b(w_i)), and st_b(w_i) agrees with σ on I(b), because on
I(b) ⊆ I(t) both equal π (st_b(w_i) and st_t(w_i) are restrictions of
ν_{w_i}, and st_t(w_i)|I(t) = π). So (y_a, w_i|_b) ∈ Q_t(σ) by Lemma 4.3.
Second, σ agrees with st_t(w_i) on I(t), since both restrict to π there. So
Lemma 4.4 gives st_t(w′_i) = σ for w′_i := w_i[a ← y_a] = w_i[t ← (y_a, w_i|_b)].
Then τ agrees with σ = ν_{w′_i}|B(t), and so with st_a(w′_i), on I(a), and
Corollary 4.5 (with y′ = y_a) gives τ = st_a(w′_i) = τ_i. So τ_i = τ ∈ R_i.

For the witness pair, suppose τ_i ∈ R_i with σ as in the definition of R_i.
The argument just given, applied to τ = τ_i, shows st_t(w′_i) = σ, so
st_b(w′_i)|I(b) = σ|I(b) = π|I(b). ∎

**Lemma 5.6 (deciding the root).** Let r be the root, a = r.l, and let r.r be
the leaf of input y, by (S1). For v ∈ {0, 1} let w_v ∈ {0,1}^X be any
assignment with w_v(y) = v, and let φ be as in Lemma 5.3 for a and (w₀, w₁).
Let

> R^v := {τ ∈ val(B(a)) : τ ≈ σ for some σ ∈ L(r) ∩ Acc with y ∉ B(r) or σ(y) = v}.

Let y_a be in a nonempty fiber φ⁻¹(τ₀, τ₁). Then f(y_a, v) = 1 iff τ_v ∈ R^v,
for both values v of y.

_Proof._ Since V_r = V_a ∪ {y}, the assignment (y_a, v) is w_v[a ← y_a], and
its state at a is τ_v.

If f(y_a, v) = 1, let σ := st_r(y_a, v). Then σ ∈ Acc by (F), σ ∈ L(r) by
Lemma 4.2, τ_v ≈ σ (both are restrictions of the same solution), and if
y ∈ B(r) then σ(y) = v. So τ_v ∈ R^v.

Conversely, let τ_v ∈ R^v with σ as in the definition. Then (y_a, v) ∈ Q_r(σ)
by Lemma 4.3: σ ∈ L(r); y_a ∈ Q_a(τ_v) ⊆ A_σ by Lemma 5.3; and v ∈ D_σ,
because the leaf of y has Q(ρ) = {ρ(y)} and ρ := (y ↦ v) agrees with σ on
I(r.r) = {y} ∩ B(r). Lemma 4.4 at the root (no condition) gives
st_r(y_a, v) = σ ∈ Acc, so f(y_a, v) = 1 by (F). ∎

**Proof of Theorem 5.1.** For every realizable pair cell (t, σ₀, σ₁) with t a
left child, and every realizable join (t, π₀, π₁) with t a right child, fix one
witness pair. Define SDD nodes as follows, for t internal unless stated.

- **Pair cells at leaves.** If t is the leaf of x and Cell_t(σ₀, σ₁) ≠ ∅, then
  σ₀(x) = σ₁(x) and the cell is the literal x = σ₀(x).
- **Joins at leaves.** If t is the leaf of x and a right child,
  J_t(π) = {π(x)} if x ∈ I(t) and J_t(π) = {0,1} otherwise, so Join_t(π₀, π₁)
  is a literal, ⊤, or ⊥.
- **Pair cells.** For a realizable pair cell (t, σ₀, σ₁) with its witness pair,
  form φ for a = t.l. The node C[t, σ₀, σ₁] is the decision node with one
  element for each nonempty fiber φ⁻¹(τ₀, τ₁): its prime is the node for
  Cell_a(τ₀, τ₁), and its sub is the node for Join_b(σ₀|I(b), σ₁|I(b)) if
  τ₀ ≈ σ₀ and τ₁ ≈ σ₁, and ⊥ otherwise, where b = t.r.
- **Joins.** For a realizable join (t, π₀, π₁) with t a right child, the node
  J[t, π₀, π₁] has one element per nonempty fiber φ⁻¹(τ₀, τ₁): its prime is
  the node for Cell_a(τ₀, τ₁), and its sub is the node for
  Join_b(π₀|I(b), π₁|I(b)) if τ₀ ∈ R₀ and τ₁ ∈ R₁, and ⊥ otherwise.
- **The root.** With w₀, w₁ as in Lemma 5.6 (for example, all inputs 0 except
  y), the root node has one element per nonempty fiber φ⁻¹(τ₀, τ₁): its prime
  is the node for Cell_{r.l}(τ₀, τ₁), and its sub is ⊤, y, ¬y, or ⊥ according
  to whether f(·, 1) and f(·, 0) are 1 on the fiber, which Lemma 5.6 determines
  from (τ₀, τ₁).

Every prime referred to here is a realizable pair cell at a left child or a
leaf (Lemma 5.3), and every sub is ⊥, ⊤, a literal, or a realizable join at a
right child (Lemmas 5.4 and 5.5). So the definition only refers to nodes that
are defined, and it is well founded because primes and subs are attached to
children.

**Claim.** Each node respects its vtree node and computes its intended
function: Cell_t(σ₀, σ₁), Join_t(π₀, π₁), or f at the root.

By induction on the height of t. Leaves were handled above. For C[t, σ₀, σ₁],
the primes are the nonempty fibers, which are nonempty, pairwise disjoint,
cover {0,1}^{V_{t.l}}, and are computed by their nodes (Lemma 5.3 and
induction). The function computed is the union over fibers F of F × sub(F),
which is Cell_t(σ₀, σ₁) by Lemma 5.4 and induction. The joins are the same
with Lemma 5.5, using (S2) at t, and the root with Lemma 5.6. The primes
respect t.l and the subs respect t.r by induction, so each decision node
respects t.

**Count.** Decision nodes are attached to internal nodes. At a left child t
there are at most |val(B(t))|² pair cell nodes, and at a right child t at most
|val(I(t))|² join nodes; at the root there is one node. A decision node at t
has at most one element per pair (τ₀, τ₁) ∈ val(B(t.l))². This gives the
stated bounds. ∎

## 6. Getting the shape

**Lemma 6.1 (leaf donation).** Let (U, T, B, L, Acc) be an RTD in which every
bag has at most b vertices and the output vertex o (the one Acc depends on;
see below) is in the root's bag, and n ≥ 2. Then there is an RTD
(U′, T′, B′, L′, Acc′) with U′ ⊆ U and X ∪ {o} ⊆ U′, whose solutions are the
restrictions of the old ones, for the same function, on a vtree T′ over the same inputs, that satisfies (S1)
and (S2) and whose bags have at most b + 6 vertices, all new vertices in bags
being inputs.

In Lemma 6.1, Acc is assumed to depend only on o: Acc = {σ : σ(o) ∈ D}
for a set D ⊆ D_o. This is the case for circuits (Section 7), where o is
Boolean and D = {1}.

_Proof._ If the root of T has two leaf children, (S1) and (S2) already hold
(after swapping the children, if needed, so that the right child is a leaf).
Otherwise, proceed in two steps.

**Step 1 (cherries).** A _cherry_ is an internal node whose two children are
leaves. For each cherry c with leaves for inputs x_c, y_c and with parent p,
replace B(c) by B′(c) := (B(c) ∩ B(p)) ∪ {x_c, y_c} and L(c) by the set of
valuations of B′(c) whose restriction to B(c) ∩ B′(c) extends to a valuation
in L(c) (the inputs x_c, y_c are unconstrained by it if they were not in B(c)),
remove the deleted vertices from U, and add x_c and y_c to B(p), extending L(p) to the larger bag by
leaving the new vertices unconstrained. The vertices removed from B(c) occur in
no other bag: a vertex of B(c) \ B(p) other than x_c, y_c is not in the bags
of the leaves below c, so by (C) it is only in B(c). Removing a vertex that
occurs in a single bag, and projecting that bag's relation, preserves (U): the
solutions of the new RTD are the restrictions of the old ones. Adding an input
x_c to B(p) preserves (C), because x_c is also in B(c), a neighbor of p, and
it preserves (U) because the solutions are unchanged. Now every cherry's bag
is contained in its parent's bag. A parent has at most two cherry children, so
bags grow by at most 4.

**Step 2 (donation).** Write d(t) for the rightmost leaf below a node t (the
leaf reached by always going right). Define, for each node w of T, a structure
S(w), which is either empty, a single leaf, or a binary tree whose leaves are
the leaves of T_w other than d(w):

- If w is a leaf, S(w) is empty.
- If w has children a and b, let A := S(a), B := S(b), and y := d(a). Then
  - if A and B are nonempty, S(w) := X_w = (A, Y_w) with Y_w = (B, y);
  - if A is empty and B is not, S(w) := Y_w = (B, y);
  - if B is empty and A is not, S(w) := X′_w = (A, y);
  - if both are empty (w is a cherry), S(w) is the single leaf y.

Here (P, Q) denotes a new internal node with left child P and right child Q.
By induction, S(w) contains every leaf of T_w except d(w), since d(w) = d(b).
The new vtree is T′ := (S(root), d(root)), with a new root node.

_Bags and relations._ Each internal node created for w (X_w, Y_w, or X′_w)
gets the bag B′ := B(w) ∪ {d(a), d(b)}. Leaves keep the bags {x}. The new root
gets {o, d(root)}. The relation L(w) is placed on the topmost node created for
w; the relation of a cherry c (whose bag is now inside its parent's) is placed
on the topmost node created for its parent p, which exists because S(c) is a
leaf and so S(p) has an internal node. All other nodes get the full relation.
Every relation is placed on a node whose bag contains its old bag. So U, the
set of relations, and therefore the solutions, are unchanged, and (U) and (F)
hold with Acc′ := {σ ∈ val({o, d(root)}) : σ(o) ∈ D}. Bags grow by at most 2.

_Connectivity._ For a node u of T that is not a cherry, the nodes created for
u are adjacent to each other (when there are two) and have the same bag; the
topmost node of S(c), for a non-cherry child c of u, is a child of a node
created for u. So for a vertex v that is not an input moved by the
construction, the nodes of T′ whose bags contain v are the nodes created for
the non-cherry nodes of T whose bags contain v; these form a connected
subtree, because the non-cherry nodes containing v are connected in T (a
cherry is a leaf of the tree of internal nodes, and a cherry's bag is contained
in its parent's). The root of T′ contains o and is adjacent to the topmost node
of S(root), whose bag contains B(root) ∋ o.

Now consider an input x. In T, x's leaf is d(u) for the nodes u on the path
from the leaf up to the highest node u* with d(u*) = x; then x = d(a) where w*
is the parent of u* and a = u* is its left child (or u* is the root and x =
d(root)). In T′, the leaf of x is the right child of Y_{w*} or X′_{w*}, or the
leaf S(w*) when w* is a cherry, or the right child of the new root. Every node
created for a node on the path from x's old leaf to w* contains x in its bag:
for u strictly above x's old leaf and strictly below w* on the path,
x = d(u.r), and for w*, x = d(w*.l). If x = o, the new root's bag also
contains x, and it is adjacent to the topmost node of S(root), whose bag
contains B(root) ∋ o. The
old occurrences of x are on nodes whose created nodes contain x, and they are
connected to the path in T. So the bags containing x form a connected subtree
of T′, including the new leaf: if w* is a cherry, the leaf S(w*) = x is a child
of a node created for the parent of w*, whose bag contains x by Step 1.

_Shape._ The right child of the root of T′ is the leaf d(root), so (S1) holds.
The internal nodes of T′ that are right children are exactly the nodes Y_w
with A nonempty (each S(·) is used only as a left child, and the right
children of X′_w, Y_w, and the root are leaves). For such a Y_w, with parent
X_w and right child the leaf of y = d(a): B′(Y_w) ∩ B′(leaf) ⊆ {y} ⊆ B′(X_w),
so (S2) holds.

Together the two steps add at most 6 vertices to every bag. ∎

**Remark 6.2 (the variant checked in Lean).** Step 1 can be replaced by
merging: leave cherries unchanged, and when S(c) is a leaf for a child c of w
(c is a cherry), add B(c) to the bag of the nodes created for w and put L(c) on
the topmost of them. Bags then have at most 3b + 2 vertices instead of b + 6.
This variant avoids projections, and it is the one formalized in Lean. With
it, the bags in the proof of Theorem 1.1 have at most 3(8k + 10) + 2 = 24k + 32
vertices, so the machine-checked part, combined with Lemmas 7.1 and 7.2, gives
the weaker bound n·2^(96k+128) instead of n·2^(32k+65); both are n·2^O(k). The
Lean theorem is `sdd_of_vtree_rtd`, where all of Lemma 6.1's claims (connectivity in the form
of Lemma 3.2, the shape conditions, the unchanged solutions, and the bag bound)
are checked.

## 7. From circuits to relational tree decompositions

**Lemma 7.1 (gate splitting).** Let C be a circuit with inputs X and output o,
and let (T, β) be a tree decomposition of its graph of width k, rooted at a
node whose bag contains o, in which every node has at most two children. Then there is an RTD-like structure
(U, T, B, L) on the tree T, with Boolean vertices, satisfying (C) and (U)
(with solutions defined in the same way), in which X ⊆ U, every bag has at
most 4(k + 1) vertices, and a vertex ô ∈ U lies in the bags of every node
whose β-bag contains o, with ν_x(ô) = val_x(o) for every x.

Here "RTD-like" means that T is an arbitrary rooted tree, not yet a vtree over
X; Lemma 7.2 turns it into an RTD.

_Proof._ For a gate g, let T_g be the subtree of nodes whose bags contain g, and top(g) its root. For every wire
e = (u → g), choose a node t(e) whose bag contains u and g.

The vertex set U consists of X and a vertex g@t for every gate g and every
t ∈ T_g. Write ĝ := g@top(g) for a gate g, and x̂ := x for an input x. The
intended value of g@t is the AND (or OR, following g) of the literals of the
wires e of g with t(e) = t, where the literal of e = (u → g) is û or ¬û as the
wire is plain or negated, and of the vertices g@t′ for the children t′ of t in
T_g. Every wire of g has t(e) ∈ T_g, so by associativity ĝ computes g.

Let B(t) consist of the inputs in β(t) and, for each gate g ∈ β(t), the
vertices g@t, ĝ, and g@t′ for the children t′ of t in T_g. Since t has at most
two children, |B(t)| ≤ 4|β(t)| ≤ 4(k + 1). Let L(t) be the set of valuations of
B(t) in which, for every gate g ∈ β(t), g@t equals the AND or OR of its
literals as above. Each such constraint mentions only vertices in B(t): for a
wire e = (u → g) with t(e) = t, u ∈ β(t), so û ∈ B(t).

(C): for t ≠ top(g), g@t lies in B(t) and, if the parent p of t is in T_g,
in B(p), and in no other bag. ĝ lies exactly in the bags of T_g. An input lies in the same bags
as in β. These sets are connected.

(U): Given x, consider the gates in topological order. When g is reached, the
values of û are determined for every wire (u → g). The constraints for g then
determine g@t for every t ∈ T_g, bottom-up in T_g, and ĝ = val_x(g). So there
is exactly one solution, and it gives ĝ the value val_x(g). Finally, ô
(which is o itself if the output is an input) lies in every bag of T_o, which
includes the root. ∎

**Lemma 7.2 (normalization).** Let (U, T, B, L) be as in Lemma 7.1, with bags
of at most b vertices and with ô in the root's bag, and suppose n ≥ 2. Then
there is an RTD for the function of C, on a vtree over X, with Acc = {σ :
σ(ô) = 1}, whose bags have at most 2b + 2 vertices and contain ô at the root.
If T is a path rooted at one of its ends, then every internal node of the
vtree has a leaf child.

_Proof._ The proof applies a sequence of operations, each of which preserves
(C) and (U), keeps ô in the root's bag, and does not remove inputs or ô from
U. Two facts are used repeatedly.

- (Projection.) If a vertex u ∉ X ∪ {ô} occurs only in bags of a set of nodes
  that are merged into one node, then u can be removed from that node's bag,
  and the relation projected, without affecting (U): solutions of the new
  structure are exactly the restrictions of the old solutions, because u
  occurs in no other relation.
- (Adding an input.) Adding an input x to the bag of a node adjacent to a node
  whose bag contains x, with the relation extended so that x is
  unconstrained there, preserves (C) and (U).

The operations are:

1. _Input leaves._ For each input x, add a new leaf with bag {x} and full
   relation, as a child of a node whose bag contains x.
2. _Pruning._ While some leaf is not one of these input leaves, delete it: if
   ℓ has parent p, replace L(p) by the set of σ ∈ L(p) whose restriction to
   B(ℓ) ∩ B(p) extends to a valuation in L(ℓ). The vertices of B(ℓ) \ B(p)
   occur only in B(ℓ) by (C); none is an input (an input is also in its input
   leaf, so it would be in B(p)) or ô (which is in the root's bag). Solutions
   of the new structure are exactly the restrictions of the old ones. Bags do
   not grow.
3. _Binarization._ Replace each node t with m ≥ 3 children c₁, …, c_m by a
   chain of copies t = t₁, t₂, …, t_{m−1} with the bag B(t), where t_i has
   children c_i and t_{i+1}, and t_{m−1} has children c_{m−1}, c_m. Put L(t) on
   t₁ and the full relation on the copies. List leaf children first, so that a
   node with a leaf child still has one after the split. Bags do not grow.
4. _Chains above leaves._ For every maximal chain u₁, …, u_m of nodes with
   one child each, ending above an input leaf ℓ for x (so u_m is the parent
   of ℓ), let q be the parent of u₁; q exists since n ≥ 2, and q has two
   children. Delete u₁, …, u_m, make ℓ a child of q, add x to B(q), and
   intersect L(q) with the projection of L(u₁) ⋈ ⋯ ⋈ L(u_m) onto
   (B(u₁) ∩ B(q)) ∪ {x}. The vertices that disappear occur only in the chain;
   the vertices of the chain shared with q are in B(u₁) ∩ B(q), and those
   shared with ℓ are x. Each node q gains at most two inputs.
5. _Other chains._ For every maximal chain u₁, …, u_m of nodes with one child
   each that ends above a node c with two children, replace the chain and c by
   one node with c's children, with bag B(c) ∪ (B(u₁) ∩ B(p)) where p is the
   parent of u₁ (or with B(c) ∪ ({ô} ∩ B(u₁)) if u₁ is the root), and with the
   projection of L(u₁) ⋈ ⋯ ⋈ L(u_m) ⋈ L(c) as relation. The vertices that
   disappear occur only in the chain. The new bag has at most
   (b + 2) + b vertices.

Afterwards, every internal node has two children and the leaves are exactly the
input leaves, so the tree is a vtree over X. The root's bag contains ô in each
case. (F) holds with Acc = {σ : σ(ô) = 1} because ν_x(ô) = val_x(o).

If T is a path rooted at an end, then after steps 1 and 2 every node has at most one child that
is not an input leaf. So after step 3, which lists leaf children first, every
node with two children has a leaf child: a copy t_i with i < m − 1 has the leaf
c_i, and the last copy has children c_{m−1} and c_m, at most one of which is
not a leaf. Step 4 replaces a child of q by an input leaf, and step 5 keeps the
children of c. So every internal node of the final vtree has a leaf child. ∎

**Proof of Theorem 1.1.** Let (T, β) be a tree decomposition of the graph of C
of width k. Root it at a node whose bag contains o, and make every node have at
most two children by replacing a node with m ≥ 3 children by a chain of m − 1
copies of it, as in step 3 of Lemma 7.2; this keeps the width. If n = 1, the function is a
constant or a literal and the theorem is trivial, so let n ≥ 2. Lemma 7.1 gives
bags of at most 4(k + 1) vertices, Lemma 7.2 an RTD with bags of at most
8(k + 1) + 2 = 8k + 10 vertices, and Lemma 6.1 an RTD satisfying (S1) and (S2)
with bags of at most 8k + 16 Boolean vertices. A vtree over n inputs has n − 1
internal nodes. By Theorem 5.1 the SDD has at most

> 4^(8k+16) + (n − 2)·4^(8k+16)·4^(8k+16) ≤ n·2^(32k+64)

elements, which is within the stated bound, and at most 1 + (n − 2)·4^(8k+16) ≤
n·2^(16k+32) decision nodes. ∎

## 8. Pathwidth and unambiguous OBDDs

**Proof of Theorem 1.2.** Add the output o to every bag of the path
decomposition; this is a path decomposition of width k + 1 in which the bags
at both ends contain o. Root the path at one end, as Lemma 7.1 requires. Each
node then has at most one child, so in Lemma 7.1 a gate contributes at most three vertices (g@t, ĝ,
and g@t′ for the one child), and bags have at most 3(k + 2) vertices. By Lemma
7.2 the bags of the RTD have at most 6k + 14 vertices and every internal node
of the vtree has a leaf child. Swap children so that this leaf is the right
child. Then every right child is a leaf, so the vtree is left-linear, (S1)
holds, and (S2) holds vacuously. Theorem 5.1 gives at most
n·4^(6k+14)·4^(6k+14) = n·2^(24k+56) elements. ∎

(Rooting the path at an end matters: rooted in the middle, the path becomes a
tree with two branches at the root, and the root need not have a leaf child.)

**Proof of Corollary 1.3.** A complete unambiguous nondeterministic OBDD
(uOBDD) with the order x₁, …, xₙ is a layered graph with layers S₀ = {source},
S₁, …, Sₙ ∋ sink, where every edge from layer j − 1 to layer j is labeled with
a value of x_j, and f(x) = 1 if and only if exactly one path from the source to
the sink follows the labels of x, and none otherwise. Take such diagrams for f
and ¬f, rename their nodes apart, and let S_j be the union of their layers j.
For every x there is then exactly one accepting path in the union.

Build an RTD on the left-linear vtree w₁ = leaf x₁, w_j = (w_{j−1}, leaf x_j).
The vertices are the inputs and state vertices s₀, …, sₙ with domains S₀, …,
Sₙ. For j ≥ 3, B(w_j) = {s_{j−1}, x_j, s_j}, and B(w₂) = {s₀, x₁, s₁, x₂, s₂}.
The relation of w_j allows exactly the valuations where (s_{j−1}, x_j, s_j) is
an edge of the union; L(w₂) also requires s₀ to be a source and contains the
edge relation for x₁. The relation of the root wₙ also requires sₙ to be a
sink. Let Acc require sₙ to be the sink of the diagram for f. (C) holds: s_j
lies in the bags of w_j and w_{j+1}, and x_j in the bags of w_j and its leaf.
(U) holds because solutions are exactly accepting paths. (S1) holds and (S2)
is vacuous. The state counts are at most 8W² for j ≥ 3 and 32W² for w₂, so
Theorem 5.1 gives an SDD of size O(n·W⁸). ∎

## 9. Lower bounds, limits, and prior work

**Proof of Proposition 1.4.** Amarilli, Capelli, Monet, and Senellart
[Connecting Knowledge Compilation Classes and Width Parameters, Theory of
Computing Systems 64 (2020), Corollary 7.6] prove: for every monotone CNF φ of
bounded arity and degree, every structured DNNF computing φ has size
2^Ω(tw(φ))/poly(|var(φ)|), where tw(φ) is the treewidth of the hypergraph of φ
(their proof goes through a completion lemma that costs a factor polynomial in
the number of variables). Every SDD of size s is a structured DNNF with O(s)
gates. The monotone 2-CNF φ_k with a clause x_u ∨ x_v for each edge of the
k × k grid has degree at most 4 and treewidth k, so its structured DNNFs have
size 2^Ω(k)/poly(k) = 2^Ω(k). To get arbitrarily many inputs, let
f := φ_k ∧ z₁ ∧ ⋯ ∧ z_m with fresh inputs z_i. Setting every z_i to 1 in a
structured DNNF for f (replacing the literals of z_i by constants) gives a
structured DNNF for φ_k, for the vtree with the z leaves removed, of no larger
size; so every SDD for f has size 2^Ω(k). The same paper shows that φ has a circuit of
treewidth at most tw(φ) + 2 (an OR gate per clause and one AND gate); adding
the z_i as further inputs of the AND gate adds at most 1. To get an
AIG, split the AND gate along a tree decomposition as in Lemma 7.1, assigning
each clause to one bag that contains its variables. A bag then receives at most
(k + 1)·4 clauses, so each partial AND gate has fan-in O(k) and can be
replaced by a chain of fan-in-2 gates placed in its own bag. This gives an AIG
of treewidth O(k). This part of Proposition 1.4 is the cited theorem together
with this standard transformation; it is not re-proved in full here.

For the second statement: let n ≥ 2. If f depends on all n inputs, every
input occurs as
a literal node in the SDD, distinct inputs give distinct literal nodes, and
each element refers to at most two nodes. So there are at least n/2 elements.
∎

**What known lower-bound methods can show.** The SDD lower-bound techniques we know of go
through structured d-DNNFs and communication complexity: an SDD for f of size s
gives, for a balanced partition of the variables induced by its vtree, an
unambiguous protocol of cost log s for f [Beame and Liew 2015], and since SDDs
can be negated in linear size [Darwiche 2011], also for ¬f, as Vinall-Smeeth
[2024] uses. For a circuit
of treewidth k, both f and ¬f have d-SDNNFs of size n·2^O(k) over one vtree
[Amarilli et al.], so such a partition with cheap unambiguous protocols for f
and ¬f exists, and these methods cannot prove a lower bound above n·2^O(k).
Theorem 1.1 shows that this is in fact the truth for SDDs as well.

**Compressed SDDs.** The SDD of Theorem 5.1 is not compressed. Every pair cell
node has at most two distinct subs, a join and ⊥. Compressing it would merge
its primes into Join_{t.l}(σ₀|I(t.l), σ₁|I(t.l)) and its complement, that is,
into a union of cells at a _left_ child, and deciding such unions is exactly
what needs more than two outside assignments. Compression can blow up SDDs
exponentially on a fixed vtree [Van den Broeck and Darwiche 2015]. The best
bound known for canonical (compressed and trimmed) SDDs of circuits of
treewidth k is still the triple exponential bound of Bova and Szeider [Circuit
Treewidth, Sentential Decision, and Query Compilation, PODS 2017]. Whether
canonical SDDs, for a well-chosen vtree, have size n·2^O(k) is open; this note
does not settle it. The experiment in README.md shows the canonical SDD on the
vtree of Theorem 1.2 growing faster than the SDD of Theorem 5.1 on the
multiplexer.

**OBDDs.** OBDDs are SDDs on right-linear vtrees (every left child a leaf).
For circuits of pathwidth k, the best known OBDD bound is n·2^(2^O(k)) [Jha and
Suciu 2012, made constructive by Amarilli, Bourhis, and Senellart 2016], and
whether the double exponential is needed is open [Amarilli et al. 2020].
Theorem 1.2 shows that moving to the mirror-image (left-linear) vtree already
gives n·2^O(k). For treewidth, no OBDD bound of the form f(k)·n^O(1) is
possible: Razgon [On OBDDs for CNFs of Bounded Treewidth, KR 2014] gives CNFs of
primal treewidth k, hence circuits of treewidth k + 2, whose OBDDs need size
n^Ω(k).

**Prior work.**

- Darwiche [SDD: A New Canonical Representation of Propositional Knowledge
  Bases, IJCAI 2011] proves a bound of O(n·2^w) for CNFs of primal treewidth w,
  over the CNF's variables. For a circuit, the Tseitin CNF has gate variables,
  which would have to be forgotten; the present note avoids them.
- Bova and Szeider [PODS 2017] prove that circuit treewidth k gives canonical
  SDD width triple exponential in k, and that SDD width w gives circuit
  treewidth O(w). De Colnet, Ordyniak, and Szeider [OBDDs, SDDs, and Circuits
  of Bounded Width: Completeness Matters, Artificial Intelligence 351 (2026)]
  show that the converse direction needs smoothness.
- Amarilli, Capelli, Monet, and Senellart [Theory of Computing Systems 2020]
  give complete d-SDNNFs of width 2^O(k) and uOBDDs of width 2^O(k) for
  pathwidth k, and ask whether the d-SDNNF bound extends to SDDs.
- Bollig and Buttkus [On the Relative Succinctness of Sentential Decision
  Diagrams, Theory of Computing Systems 2019] turn uOBDDs for f and ¬f with the
  same order into an SDD of polynomial size over a linear vtree with
  auxiliary variables, and Bollig and Farenholtz [On the Relation between
  Structured d-DNNFs and SDDs, Theory of Computing Systems 2021] do the same
  for structured d-DNNFs over the same vtree. Combined with the result of
  Amarilli et al., this already gives SDDs of size poly(n)·2^O(k) for circuits
  of treewidth k, but over vtrees with auxiliary variables, which is not an SDD
  over the circuit's inputs; whether the auxiliary variables can be removed
  was left open. Corollary 1.3 removes them for uOBDDs.
- Kučera and Martinek [Parameterized Complexity of Representing Models of MSO
  Formulas, arXiv 2604.08707, 2026] build SDDs of size f(k, |φ|)·n for MSO
  formulas on graphs of treewidth k, via deterministic tree automata and dummy
  variables in the vtree; for circuits their f is at least doubly exponential.
- Vinall-Smeeth [Structured d-DNNF Is Not Closed Under Negation, IJCAI 2024]
  separates SDDs from structured d-DNNFs quasipolynomially. Theorem 1.1 shows
  that this separation cannot come from functions of small circuit treewidth.

No earlier work that we found states a bound of n·2^O(k), or any bound singly
exponential in k, for SDDs over the inputs of a circuit of treewidth k.
