# Canonical SDDs of Circuits of Bounded Treewidth

This document continues [circuit_treewidth_sdd](../circuit_treewidth_sdd/),
which showed that every circuit of treewidth k with n inputs has an
(uncompressed) SDD of size n·2^O(k). Here the question is the same for
_canonical_ SDDs, the compressed and trimmed SDDs that are unique for each
vtree. Definitions not repeated here (vtrees, SDDs, tree decompositions of
circuits) are those of section 2 of
[circuit-treewidth-sdd-proof.md](../circuit_treewidth_sdd/circuit-treewidth-sdd-proof.md).

## 1. Results

A _circuit_ has input vertices (one per variable) and AND, OR, and NOT gates
of any fan-in; its graph has the inputs and gates as vertices and the wires as
edges. For n ≥ 1 and k ≥ 1 let

- C(n, k) be the largest, over circuits with n inputs whose graph has
  treewidth at most k, of the smallest canonical SDD of the circuit's function
  over its n inputs, minimized over all vtrees;
- C_pw(n, k) be the same with pathwidth in place of treewidth.

The size of an SDD is the number of elements of its distinct decision nodes.

**Theorem 1.1 (the bounds).** There are constants c, c' > 0 such that

    max(n/2, 2^(c·k))  ≤  C(n, k)  ≤  min( n · 2^(2^(2^(c'·k))),  n^(2^(c'·k)) ),
    max(n/2, 2^(c·k))  ≤  C_pw(n, k)  ≤  n · 2^(2^(c'·k)),

where n/2 needs n ≥ 2 and 2^(c·k) holds for k up to a constant times n.

- The lower bounds are those of uncompressed SDDs, since a canonical SDD is an
  SDD (Proposition 6.1, which extends Proposition 1.4 of the first study to
  every k up to a constant times n and to pathwidth).
- The first upper bound is Bova and Szeider's (2017); section 5.2 explains it.
- The second upper bound, n^(2^O(k)), is Theorem 5.4, which goes through
  OBDDs, the canonical SDDs on right-linear vtrees. It is essentially Jha and
  Suciu's argument (2012). They state the weaker OBDD bound
  n^(2^((k+1)·2^(k+1))) for a decomposition of width below k, and their
  recursion would give n^((k+1)·2^(k+1)) except that it halves the number of
  variables at each step without accounting for the variables shared through
  a bag. Theorem 5.4 is a complete proof.
- The pathwidth upper bound is Jha and Suciu's OBDD bound (Theorem 5.5).

So neither aim of this study was reached: there is no bound n·g(k) or
poly(n)·g(k) with g better than triple exponential, and no lower bound beyond
2^O(k)·poly(n). Theorem 6.2 says what a lower bound beyond 2^O(k)·poly(n)
would mean:

**Theorem 6.2 (the gap).** If C(n, k) or C_pw(n, k) is not bounded by
2^(a·k)·n^a for any constant a, then there are functions whose smallest
canonical SDDs are superpolynomially larger than their smallest SDDs (both
minimized over vtrees).

Whether canonical SDDs are superpolynomially larger than SDDs for some
functions is a known open question: Bova (2016) writes that general SDDs "are
believed (despite not known) to be exponentially more succinct than
compressed SDDs". So proving the lower bound that the first aim asks for is
at least as hard as settling that question.

The rest of the results explain why the known routes to an upper bound stop
where they do, and identify one concrete function on which the question
turns.

**Theorem 3.1 (machine-checked).** The hidden weighted bit function HWB_n
(x_w, where w = x_1 + ⋯ + x_n, and 0 if w = 0) has a circuit with AND, OR,
and NOT gates of fan-in at most 2, one input vertex per variable, at most
n·(5L + 3) + L + 2 vertices, and pathwidth at most 8L + 5, where L is any
number with n < 2^L ≤ 2n. So HWB_n has circuit pathwidth at most
8·log₂ n + 13.

Its consequences (section 4):

- **Corollary 4.1 (OBDDs).** There are circuits of pathwidth k all of whose
  OBDDs have width 2^(2^Ω(k)). Jha and Suciu's upper bound 2^((k+2)·2^(k+2))
  for OBDD width is therefore tight up to a constant factor in the inner
  exponent. Amarilli, Capelli, Monet, and Senellart (2020) asked whether that
  doubly exponential bound is tight; the first study's README also listed it
  as open. Any upper bound for canonical SDDs that goes through OBDDs is
  therefore at least doubly exponential.
- **Corollary 4.3 (factor width and TDDs).** Theorem 15 of Capelli, Choi,
  Mengel, Muñoz, and Van den Broeck (arXiv:2604.05537v1; factor width at most
  3^(k+2)) and their Theorem 16 (TDDs of width 2^O(k), built in time
  2^O(k)·|X|·|C|) contradict their own Theorem 19 (factor width and TDD size
  2^Ω(n) for HWB_n on every vtree) on this circuit. If Theorem 19 holds, as
  its classical proof idea suggests, then Theorems 15 and 16 are false and the
  doubly exponential bound on factor width for circuits of treewidth k (Bova
  and Szeider) is tight up to the constant. Independently of Theorem 19, the
  argument in the proof of Theorem 15 fails: **Proposition 4.2
  (machine-checked)** gives a ten-vertex counterexample to one of its steps,
  and on the path decomposition of Theorem 3.1 the argument's conclusion would
  give HWB_n OBDDs of polynomial width, contradicting Bryant's lower bound.

HWB_n is also the function on which the question turns: Bova (2016) asked
whether HWB_n has superpolynomial canonical SDDs on every vtree. If it has
canonical SDDs of size at least 2^(n^ε) on every vtree, then by Theorem 3.1,
C_pw(n, k) ≥ 2^(2^(ε·⌊(k − 13)/8⌋)) for n = 2^⌊(k − 13)/8⌋, a lower bound of
the form 2^(2^Ω(k)), which matches the form of the pathwidth upper bound. If it
has polynomial canonical SDDs on some vtree, then HWB is not a separating
example and Bova's question is answered negatively for HWB.

**Computations (section 7).** The smallest canonical SDD of HWB_n over all
vtrees is 0, 2, 10, 22, 34, 56 for n = 2, …, 7 (exhaustive over all vtrees)
and at most 82, 113, 152, 201, 254, 318, 425, 531 for n = 8, …, 15 (simulated
annealing). These numbers fit a polynomial of degree about 2 as well as an
exponential with base about 1.3, so they do not decide the question.
Proposition 6.3 shows how misleading such data can be: on one vtree family,
HWB_n's canonical SDDs provably have about 2^(n/5) decision nodes, yet the
computed sizes for n ≤ 22 grow like n³.

### What is proven, checked, and computed

| Claim | Status |
| --- | --- |
| Theorem 3.1: HWB_n has a circuit of pathwidth ≤ 8·log₂ n + 13 | English proof; **Lean, machine-checked** (`hwb_circuit`); also checked by brute force for n ≤ 14 |
| Proposition 4.2: a false step in the proof of Capelli et al.'s Theorem 15 | English; **Lean, machine-checked by `decide`** (`capelli_claim_fails`) |
| Corollary 4.1: OBDD width 2^(2^Ω(k)) needed for pathwidth k | English, from Theorem 3.1 and Bryant's OBDD lower bound for HWB (cited) |
| Corollary 4.3: Capelli et al.'s Theorems 15 and 16 contradict their Theorem 19; if Theorem 19 holds, factor width 2^(2^Ω(k)) is needed | English, from Theorem 3.1 and Capelli et al.'s Theorem 19 (cited, not re-proved) |
| The argument for Theorem 15 fails on the circuit of Theorem 3.1 | English, from Theorem 3.1 and Bryant's lower bound (cited) |
| Theorem 5.4: canonical SDDs (and OBDDs) of size n^(2^O(k)) | English proof (a complete version of Jha and Suciu's argument) |
| Upper bound n·2^(2^(2^O(k))) | Bova and Szeider (cited); section 5.2 gives the argument |
| Pathwidth upper bound n·2^(2^O(k)) | Jha and Suciu (cited); Theorem 5.5 re-derives it |
| Lower bounds max(n/2, 2^Ω(k)) | Proposition 6.1, from Amarilli et al.'s structured DNNF lower bound (cited) |
| Theorem 6.2: a stronger lower bound separates canonical and uncompressed SDDs | English, from the first study's Theorem 1.1 |
| Proposition 6.3: one vtree family is exponential for HWB_n | English proof |
| HWB_n canonical sizes, n ≤ 15 | computed (exhaustive n ≤ 7; annealing n ≤ 15, upper bounds only) |
| Tree automata reach every set of states at one vtree node | computed |
| Whether C(n, k) or C_pw(n, k) exceeds 2^O(k)·poly(n) | **open** |
| Whether HWB_n has polynomial canonical SDDs on some vtree | **open** |

## 2. Canonical SDDs

An SDD is _compressed_ if the subs of every decision node are distinct, and
_trimmed_ if no decision node has the form {(⊤, s)} or {(p, ⊤), (¬p, ⊥)}.
Darwiche (2011) proved that for every vtree and every function there is
exactly one compressed and trimmed SDD respecting the vtree, up to sharing of
equal nodes; we call it the _canonical_ SDD. Bova and Szeider's SDD width,
and the "compressed SDDs" of Bova (2016) and of Van den Broeck and Darwiche
(2015), are about these canonical SDDs.

**Lemma 2.1 (semantic description).** Let g be a function whose variables are
among those of a vtree T. If g is constant or a literal, its canonical SDD is
that terminal. Otherwise let u be the deepest node of T whose variables
contain every variable g depends on, and let l and r be u's children. The
canonical SDD of g is a decision node at u with one element (p, s) for each
distinct function s = g|_(x_l) of the variables below r, where x_l ranges over
assignments of the variables below l; its prime p is the set of x_l with
g|_(x_l) = s. Primes and subs are again represented canonically.

This is the standard description (compression puts all x_l with the same
residual into one prime; trimming means g sits at the deepest node that
contains its support). The canonical SDD's size is the sum, over the distinct
functions g that get a decision node, of the number of distinct residuals
g|_(x_l). The tool `canon` (section 7) computes exactly this.

Two consequences used below:

- **Right steps restrict.** If u is a decision node for g and r is u's right
  child, then every non-constant restriction g|_(x_l) appears in the canonical
  SDD (as a literal or a decision node). So the canonical SDD of f contains
  every non-constant restriction f|_ρ, where ρ assigns the variables of the
  left children along a path of right steps from the root.
- **Distinct functions are distinct nodes.** Each distinct non-constant,
  non-literal function in the SDD is a decision node with at least two
  elements.

**Lemma 2.2 (OBDDs).** A reduced OBDD with m internal nodes for order
x_1, …, x_n gives the canonical SDD on the right-linear vtree
(x_1 (x_2 (⋯ x_n))) with at most 2m elements.

_Proof._ On a right-linear vtree, the left child of every internal node is a
single variable x_i, so by Lemma 2.1 every decision node has at most two
elements, (x_i, g|_(x_i = 1)) and (¬x_i, g|_(x_i = 0)), or one element if the
two residuals are equal, in which case the node is trimmed away and g moves
down. The decision nodes are thus distinct subfunctions of f that depend on
the first variable they test, so they are among the internal nodes of the
reduced OBDD (Bryant 1986). ∎

## 3. A circuit of logarithmic pathwidth for HWB

**Theorem 3.1.** For every n ≥ 1 and every L with n < 2^L, HWB_n has a
circuit with AND, OR, and NOT gates of fan-in at most 2, one input vertex per
variable, at most n·(5L + 3) + L + 2 vertices, and a path decomposition with
bags B_1, …, B_n of at most 8L + 6 vertices each. Such an L exists with
2^L ≤ 2n, so the pathwidth is at most 8·log₂ n + 13.

_Construction._ Write w_i = x_1 + ⋯ + x_i, so w = w_n. The circuit has two
parts.

1. _Counting._ For i = 1, …, n, the gates cnt(i, j), j < L, hold bit j of
   w_i. Step i adds the bit x_i to w_(i−1) with a ripple-carry chain: with
   c(i, 0) = x_i,

   - carry(i, j + 1) = cnt(i − 1, j) ∧ c(i, j) (this is c(i, j + 1)),
   - or(i, j) = cnt(i − 1, j) ∨ c(i, j),
   - nand(i, j) = ¬carry(i, j + 1),
   - cnt(i, j) = or(i, j) ∧ nand(i, j), which is cnt(i − 1, j) ⊕ c(i, j).

   For i = 1, the bits cnt(0, j) are a constant gate zero = x_1 ∧ nx0 with
   nx0 = ¬x_1.
2. _Selecting._ Let nw(j) = ¬cnt(n, j). For i = 1, …, n, let lit(i, j) be
   cnt(n, j) if bit j of i is 1 and nw(j) otherwise; e(i, 0) = lit(i, 0),
   e(i, j) = e(i, j − 1) ∧ lit(i, j) for 1 ≤ j < L; t(i) = x_i ∧ e(i, L − 1);
   o(i) = o(i − 1) ∨ t(i) with o(0) = zero. The output is o(n).

_Correctness._ By induction on j, c(i, j) is x_i ∧ (bits 0..j−1 of w_(i−1)
are all 1), and bit j of w_(i−1) + x_i is bit j of w_(i−1) XOR c(i, j); so by
induction on i, cnt(i, j) is bit j of w_i. Since w ≤ n < 2^L and i < 2^L,
e(i, L − 1) is true exactly when w = i. So o(n) = ⋁_i (x_i ∧ w = i), which is
x_w if w ≥ 1 and 0 if w = 0.

_Path decomposition._ Give every vertex an interval of bag indices: x_i and
every gate of step i in both parts get [i, i], except that cnt(i, j) for
i < n gets [i, i + 1] (it is used in step i + 1), cnt(n, j) and nw(j) get
[1, n] (they are used by every step's selecting part), o(i) for i < n gets
[i, i + 1], and zero and nx0 get [1, 1]. Bag p is the set of vertices whose
interval contains p, so the bags containing a vertex are consecutive. Every
wire joins two vertices whose intervals share the index of the gate's step
(n for nw(j)). Bag p holds at most x_p, nx0, zero, t(p), o(p), o(p − 1), and
for each j < L at most carry(p, j + 1), or(p, j), nand(p, j), cnt(p, j),
cnt(p − 1, j), cnt(n, j), nw(j), e(p, j): at most 8L + 6 vertices.

Finally, an L with n < 2^L ≤ 2n exists by induction (take L = 1 for n = 1 and
one more than the L for ⌊n/2⌋ otherwise). ∎

[hwb_circuit_pathwidth.lean](hwb_circuit_pathwidth.lean) proves Theorem 3.1
in Lean (`Define.CircuitTreewidthCanonicalSdd.hwb_circuit`, for every n ≥ 1
and every L with n < 2^L, and `exists_bits` for an L with 2^L ≤ 2n). The Lean
statement gives the circuit as a gate for each vertex of a finite vertex set
and proves: arguments are vertices; the circuit is acyclic (a rank that
decreases along every wire); each variable is read by exactly one vertex; for
every input there is a consistent valuation, and every consistent valuation
gives the output the value HWB_n(x); every vertex is in some bag, every bag
index is in 1..n, every wire is in some bag, the bags of each vertex are
consecutive, and every bag has at most 8L + 6 vertices; the vertex count is at
most n·(5L + 3) + L + 2. [hwb_circuit.py](hwb_circuit.py) builds the same
circuit and checks it against HWB_n on all inputs for n ≤ 14 and on random
inputs up to n = 1024; the measured width is 8L + 2 for n ≥ 2
([results/hwb_circuit.txt](results/hwb_circuit.txt)).

The construction is simple, and the fact may be folklore; we did not find it
stated.

## 4. Consequences of Theorem 3.1

**Corollary 4.1.** For every k ≥ 21 there is a circuit of pathwidth at most k,
with n = 2^⌊(k − 13)/8⌋ inputs, whose OBDDs (for every variable order) all
have width at least 2^(n/5)/O(n) = 2^(2^(k/8 − O(1))).

_Proof._ Bryant (1991) proved that every OBDD for HWB_n has 2^Ω(n) nodes; the
form quoted by Bollig and Farenholtz (2019) is Ω(2^(n/5)) for n divisible by
10 [also Wegener, _Branching Programs and Binary Decision Diagrams_, Theorem
4.10.2]; since setting x_n = 0 in HWB_n gives HWB_(n−1), it holds with a floor
for every n. An OBDD with width W has at most n·W + 2 nodes. Apply Theorem 3.1
with L = log₂ n + 1, so 8·log₂ n + 13 ≤ k. ∎

Jha and Suciu [Corollary 2.13] give OBDD width at most 2^((k+1)·2^(k+1)) for
an expression path decomposition of width below k, that is, 2^(2^(k + O(log k))).
Corollary 4.1 shows that the inner exponent k cannot be lowered below k/8 −
O(1): the OBDD width of circuits of pathwidth k is 2^(2^Θ(k)) in the worst
case. Amarilli, Capelli, Monet, and Senellart [_Connecting Knowledge
Compilation Classes and Width Parameters_, ToCS 2020, section 8] asked whether
this doubly exponential dependence is tight. Since reduced OBDDs are canonical
SDDs (Lemma 2.2), upper bounds for canonical SDDs obtained through OBDDs cannot
be better than doubly exponential in the pathwidth, and the uncompressed SDDs
of the first study (n·2^O(k)) are exponentially smaller than every OBDD for
these circuits.

**Proposition 4.2.** The proof of Theorem 15 of Capelli, Choi, Mengel, Muñoz,
and Van den Broeck [_A canonical generalization of OBDD_, arXiv:2604.05537v1,
appendix] takes an optimal tree decomposition, adds the output gate to every
bag, and claims: "for τ, ν ∈ 2^(X≤t), if b_τ = b_ν, then τ and ν define the
same X≤t-subfunction", where X≤t is the set of variables whose input gates
appear in bags below t, and b_τ maps each gate in the bag B_t to its
three-valued partial value (0, 1, or ⊥) under τ. The argument given for this
claim uses only that the output is in every bag, and for such tree
decompositions the claim is false.

_Counterexample._ Inputs y, x, z; gates g1 = ¬y, a = g1 ∧ x, nx = ¬x,
ng = ¬g1, b = ng ∧ nx, g = a ∨ b, and the output o = g ∧ z. So
o = (x ↔ ¬y) ∧ z. The tree decomposition is the path R – T – B, rooted at R,
with R = {y, z, g1, g, o}, T = {g1, g, o}, B = {x, g1, a, nx, ng, b, g, o}; it
covers every wire, each vertex's bags are connected, and o is in every bag.
At t = T, X≤t = {x}. Under x = 0: g1 = ⊥, a = 0, b = ⊥, g = ⊥, o = ⊥. Under
x = 1: g1 = ⊥, a = ⊥, b = 0, g = ⊥, o = ⊥. So b_τ = b_ν, but the
subfunctions are y ∧ z and ¬y ∧ z. ∎

This decomposition is not an optimal one with the output added: the circuit
has treewidth 2, so such a decomposition has bags of at most 4 vertices, while
B has 8. So the
counterexample refutes the argument rather than the claim restricted to
optimal decompositions; Corollary 4.3 deals with the statement.

The proof's argument fails at its last step: it finds a gate g ∈ B_t on a
path P2 along which the values under τ are undefined, and concludes that g
contradicts the choice of a deepest gate v0 with
val(v0, τ × σ) ≠ val(v0, ν × σ); but gates on P2 need not differ under τ × σ
and ν × σ. [capelli_counterexample.lean](capelli_counterexample.lean) checks
the counterexample by `decide` (`capelli_claim_fails`): the three-valued
evaluation, acyclicity, that the bags form a tree decomposition with the
output in every bag, that X≤T = {x}, that the partial values on T agree, and
that the two subfunctions are y ∧ z and ¬y ∧ z.

The argument also fails at full scale. Add the output o(n) to every bag of the
path decomposition of Theorem 3.1 and root it at bag n. Bag p then has the
bags 1..p below it, whose input vertices are x_1, …, x_p. The claim of
Proposition 4.2 would give HWB_n at most 3^(8L+7) = poly(n) distinct
subfunctions after fixing x_1, …, x_p, for every p, so an OBDD of polynomial
width in the natural order, contradicting Bryant's lower bound.

**Corollary 4.3.** Theorems 15 and 16 of Capelli et al. (arXiv:2604.05537v1)
contradict their Theorem 19. If Theorem 19 holds, Theorems 15 and 16 are
false, and for circuits of treewidth k the best factor width over all vtrees
can be 2^(2^Ω(k)).

_Proof._ Their Theorem 19 states that for n a multiple of 7, every vtree has
factor width at least 2^(cn) for HWB_n, and every TDD computing HWB_n has size
at least 2^(cn). By Theorem 3.1, HWB_n has a circuit C of treewidth
k ≤ 8·log₂ n + 13 with |C| = O(n log n) and n variables. Theorem 15 would give
a vtree of factor width at most 3^(k+2) ≤ 3^15·n^(8 log₂ 3) = poly(n). Theorem
16 would give a TDD of width 2^O(k) = poly(n), so of size poly(n) (it is built
in time 2^O(k)·|X|·|C|). Both contradict Theorem 19 for large n. The last
statement is Theorem 19 with k = Θ(log n). ∎

We have not re-proved Theorem 19; its proof adapts a classical lemma about HWB
(Wegener, Lemma 4.10.1). Proposition 4.2 and the paragraph after it show that
the argument for Theorem 15 is wrong, so Theorem 15 is the likely culprit. The
results of that paper for CNF formulas (Theorem 14) do not use Theorem 15 and
are not affected. If Theorem 19 holds, Bova and Szeider's doubly exponential
bound on factor width for circuits is tight up to the constant in the inner
exponent.

## 5. Upper bounds

### 5.1 Types through a separator

**Lemma 5.1.** Let C be a circuit computing f, and let I, B, O partition its
vertices so that no wire joins I and O and the output is in B ∪ O. Let S be a
set of variables whose input vertices are all in I ∪ B, with every other input
vertex in B ∪ O. Then f has at most 2^(2^(2|B|)) distinct subfunctions
f|_(x_S).

_Proof._ For a gate g ∈ B, split its arguments into those in I and the rest,
and let h_g be the gate's operation applied to its arguments in I (the neutral
element 1 for AND or 0 for OR if there are none; for a NOT gate, h_g is its
argument's value if the argument is in I and the constant 0, unused,
otherwise). Then g's value is the gate's
operation applied to h_g and its other arguments (for AND and OR, by
associativity). The constraints of the circuit, given an input x, fall into
two groups: the inner group (the input vertices in I ∪ B whose variable is in
S, every gate in I, and the definition of each h_g), which mentions only
vertices in I ∪ B, the h_g, and x_S; and the outer group (the remaining input
vertices, every gate in O, and each gate g ∈ B in terms of h_g and its
arguments outside I), which mentions only vertices in B ∪ O, the h_g, and the
other variables. Let R(x_S) be the set of values of (B, (h_g)_(g∈B)) that
extend to a solution of the inner group; it is a subset of {0,1}^(2|B|). A
circuit has exactly one consistent valuation for each input, so f(x_S, x') = 1
exactly when some element of R(x_S) extends to a solution of the outer group
for x' with output 1. So f|_(x_S) depends only on R(x_S). ∎

For a tree decomposition of C with the output added to every bag (width k + 1),
a node Y with bag B, and a set of children of Y, let I be the vertices that
appear only in bags of Y's subtree outside those children's subtrees and are
not in B, and O the rest. No wire joins I and O, since a vertex appearing both
in such a bag and outside must be in B. So Lemma 5.1 applies with |B| ≤ k + 2
to every set S that contains the variables of all input vertices in I and
otherwise only variables of input vertices in B, giving at most
E := 2^(2^(2k+4)) subfunctions f|_(x_S).

### 5.2 Bova and Szeider's bound

Bova and Szeider [_Circuit Treewidth, Sentential Decision, and Query
Compilation_, PODS 2017] prove that a circuit of treewidth k has canonical SDDs
of width (decision nodes per vtree node) at most triple exponential in k, so of
size n·2^(2^(2^O(k))). The heart of it is this:

**Lemma 5.2.** In the canonical SDD of f on any vtree, every function g that
has a decision node at vtree node t is a union of classes of the equivalence
x_t ~ x'_t ⟺ f|_(x_t) = f|_(x'_t) on the assignments of the variables below
t.

_Proof._ The functions arriving at t are obtained from f by steps from a node
to a child: a right step restricts by an assignment of the left child's
variables, a left step takes a prime, which is a class of left assignments with
equal residuals. By induction along the path, every function h arriving at a
node s satisfies: if x_t ~ x'_t for a node t below s, then h does not
distinguish them (for any values of the other variables). This holds for f,
and it is preserved by restriction and by taking a class: if
h(x_t, y, z) = h(x'_t, y, z) for all y, z, then (x_t, y) and (x'_t, y) have
the same residual under h, so they are in the same prime. ∎

With the vtree of a tree decomposition, Lemma 5.1 bounds the number of classes
at t by E = 2^(2^O(k)), so there are at most 2^E functions at t, each a decision
node with at most E elements, giving n·2^(2^(2^O(k))). In the language of
automata: the class of x_t is a _type_, the type at a node is determined by the
types at its children, and a function at t is a set of types.
[tree_automaton_functions.py](tree_automaton_functions.py) computes canonical
SDDs at the level of types for random automata with up to 10 states on
complete binary vtrees of depth up to 11 (2048 variables), using one automaton
at every node; for every state count up to 6, some automaton has all
2^m − 2 non-constant sets of types as decision nodes at one vtree node, so
for these vtrees the count 2^E in the argument is attained (section 7). An
improvement over triple exponential therefore has to choose the vtree
differently or use more about circuits than the type count.

### 5.3 Through OBDDs

**Theorem 5.4.** Every circuit with n ≥ 1 inputs and a tree decomposition of
width k has an OBDD of width at most 2^(4k+8)·E^(log_(4/3) n + 1), where
E = 2^(2^(2k+4)), so of size n^(2^O(k)). Hence C(n, k) ≤ n^(2^O(k)).

_Proof._ Add the output to every bag. For a node Y let Var(Y) be the variables
whose input vertices appear in bags of Y's subtree, and m(Y) = |Var(Y)|. Order
each node's children by decreasing m, and order the variables by the
traversal that visits, at each node Y, its first child's subtree, then the
variables first seen at Y, then the other children's subtrees in order. Every
variable is assigned the first time it is seen.

Consider a prefix P of this order, ending with the variable v, and the path
from the root to the node Y_v where v is first seen. At a node Y on this path
whose next node is its i-th child with i ≥ 2 (a _light step_), the prefix
contains every variable first seen in Y's first i − 1 children's subtrees or at
Y itself; call this set S_Y. Let Y* be the first node on the path with
m(Y*) ≤ 4(k + 2), if there is one. The variables of P not in any S_Y with Y
above Y* are of one of two kinds:

- if Y* exists, the variables of P first seen in Y*'s subtree;
- if not, the set S_end of variables first seen in Y_v's first child's subtree
  together with those first seen at Y_v that precede v.

Each block has few types:

- By Lemma 5.1 (with I the vertices appearing only in bags of Y and its first
  i − 1 children's subtrees, minus the bag of Y), S_Y has at most E types.
- The variables of P first seen in Y*'s subtree number at most 4(k + 2), so
  they take at most 2^(4k+8) values.
- S_end has at most E types, by Lemma 5.1 with I the vertices appearing only in
  bags of Y_v's first child's subtree, minus the bag of Y_v; S_end may contain
  any of the input vertices in that bag.
- If x_S and x'_S have the same type, f(x_S, y) = f(x'_S, y) for all y, so
  replacing one block of the prefix assignment by another of the same type
  does not change f|_P. So f has at most 2^(4k+8)·E^(h+1) subfunctions f|_P,
  where h is the number of light steps from nodes Y with m(Y) > 4(k + 2).
- At such a light step from Y into its i-th child Y': the variables of two
  different children's subtrees are shared only through Y's bag, so
  m(Y_1) + m(Y') ≤ m(Y) + (k + 2) for the first child Y_1, and m(Y') ≤ m(Y_1).
  So m(Y') ≤ (m(Y) + k + 2)/2 < 3m(Y)/4, and h ≤ log_(4/3) n.

The number of nodes of the reduced OBDD at a level is at most the number of
distinct subfunctions f|_P for the prefix P before that level. By Lemma 2.2,
the canonical SDD on the right-linear vtree for this order has at most twice
as many elements as the OBDD has nodes. Finally E^(log_(4/3) n) =
n^(2^(2k+4)/log₂(4/3)) = n^(2^O(k)). ∎

Jha and Suciu [_On the tractability of query compilation and bounded
treewidth_, ICDT 2012, Corollary 2.14] use the same traversal and state width
n^(2^((k+1)·2^(k+1))). Their induction multiplies the width by their Lemma
2.12's count 2^((k+1)·2^(k+1)) at each halving of the number of variables,
which would give n^((k+1)·2^(k+1)), but the halving ignores the variables
shared through a bag. Theorem 5.4 is a complete proof of an n^(2^O(k)) bound;
its exponent, 2^(2k+4)/log₂(4/3), is smaller than their stated
2^((k+1)·2^(k+1)) but larger than the (k+1)·2^(k+1) their recursion would
give. Razgon
(2014) showed that some CNFs of primal treewidth k, which have circuits of
treewidth O(k), need OBDDs of size n^Ω(k), so the polynomial degree must
depend on k for OBDDs; for canonical SDDs it need not, by Bova and Szeider.

**Theorem 5.5 (Jha and Suciu, Corollary 2.13).** A circuit with a path
decomposition of width k has OBDDs, and so canonical SDDs, of size
n·2^(2^O(k)).

_Proof (with Lemma 5.1)._ Order the variables by the first bag they appear in.
A prefix consists of the variables first seen in bags 1..p − 1, which have at
most E types by Lemma 5.1 (I is the vertices appearing only in bags before p,
B is bag p), and some of the variables first seen in bag p, at most 2^(k+2)
values. ∎

By Corollary 4.1, doubly exponential is the best possible for OBDDs.

## 6. Lower bounds and the gap

**Proposition 6.1.** There are constants c, c' > 0 with
C(n, k) ≥ C_pw(n, k) ≥ max(n/2, 2^(ck)) for n ≥ 2 and k ≤ c'·n.

_Proof._ A canonical SDD is an SDD. The n/2 bound is the second part of
Proposition 1.4 of the first study. For the other, the first study uses the
monotone 2-CNF of the k × k grid, which has k² variables; to cover k up to a
constant times n, use instead the monotone 2-CNF φ with a clause x_u ∨ x_v for
each edge of a 3-regular expander on N vertices. It has bounded arity and
degree and treewidth and pathwidth Θ(N), so by Amarilli, Capelli, Monet, and
Senellart [ToCS 2020, Corollary 7.6] its structured DNNFs, and so its SDDs,
have size 2^Ω(N). Their circuit for φ (an OR gate per clause and one AND
gate) has O(N) vertices, so pathwidth O(N). Padding with fresh
inputs z_i in the AND gate, as in the first study, gives every n ≥ N with the
same bound. ∎

**Theorem 6.2.** If there is no constant a with C(n, k) ≤ 2^(a·k)·n^a for all
n and k, then for every constant b there is a function whose smallest
canonical SDD (over all vtrees) is larger than s^b, where s is the size of its
smallest SDD (over all vtrees). The same holds for C_pw.

_Proof._ Theorem 1.1 of the first study gives, for every circuit with n inputs
and treewidth k, an SDD of size s ≤ n·2^(32k+65). If the canonical SDDs of
every such circuit had size at most s^b ≤ n^b·2^(b(32k+65)), then
C(n, k) ≤ 2^(a·k)·n^a for a = 97b, since 32k + 65 ≤ 97k for k ≥ 1. ∎

So a lower bound beyond 2^O(k)·poly(n) is a superpolynomial separation of
canonical from uncompressed SDDs, which is open. The converse does not
follow: a separating family need not have small circuit treewidth.

**Proposition 6.3.** Let P_n be the vtree that is right-linear over the pairs
(x_1, x_n), (x_2, x_(n−1)), … (with x_((n+1)/2) last if n is odd). The
canonical SDD of HWB_n on P_n has at least 2^(⌊a/2⌋) − 2n decision nodes,
where a = ⌊2n/5⌋.

_Proof._ By the first consequence of Lemma 2.1, the canonical SDD contains
every restriction f|_ρ where ρ assigns the first a pairs, that is, x_1..x_a
and x_(n−a+1)..x_n. Let s = ⌈a/2⌉. For each pattern π ∈ {0,1}^(a−s), let ρ_π
set x_(s+1)..x_a to π, set s − |π| of x_1..x_s to 1 and the rest to 0
(possible since |π| ≤ a − s ≤ s), and set x_(n−a+1)..x_n to 0, so ρ_π has
weight s. For
an assignment y of the m = n − 2a middle variables, f|_(ρ_π)(y) = x_(s+|y|).
For j ∈ [s + 1, a], taking |y| = j − s (possible since a − s ≤ m when
a ≤ 2n/5) gives the value π_j, so different patterns give 2^(a−s) different
restrictions, all functions of the middle variables. At most 2m + 2 of them
are constants or literals; each of the others is a decision node (the second
consequence of Lemma 2.1). ∎

So HWB_n needs about 2^(n/5) decision nodes on P_n. Yet the computed sizes on
P_n for n = 4..22 are 16, 30, 46, 73, 93, 144, 170, 238, 291, 372, 466, 577,
707, 891, 1056, 1331, 1583, 1921, 2351, growing about like n³
([results/hwb_vtree_families.txt](results/hwb_vtree_families.txt)): at
n = 22 the bound 2^4 − 44 says nothing. The minima over all vtrees for n ≤ 15 are
equally unable to distinguish polynomial from exponential growth.

## 7. Computations

All programs are in this directory; the outputs are in [results/](results/).

- **`canon`** (Rust, [canon/](canon/)) computes exact canonical SDD sizes
  from Lemma 2.1, on truth tables, for a given vtree; it enumerates all vtrees
  for small n, and runs simulated annealing over vtrees (moves: swapping
  children, rotations, exchanging subtrees, relabeling leaves). Build with
  `cargo build --release` in `canon/`.
- **HWB, exhaustive**
  ([results/hwb_exhaustive.txt](results/hwb_exhaustive.txt)): the smallest
  canonical SDD over all vtrees for n = 2..7 is 0, 2, 10, 22, 34, 56 (665280
  vtrees for n = 7).
- **HWB, annealing** ([results/hwb_anneal.txt](results/hwb_anneal.txt), 4
  restarts of 3000 steps): best found for n = 8..15 is 82, 113, 152, 201, 254,
  318, 425, 531, against 1252 for the right-linear and 95554 for the
  left-linear vtree in the natural order at n = 15. The best vtrees found are a short
  right spine of variables taken from both ends, followed by a nearly
  right-linear vtree over small blocks. These are upper bounds on the minimum.
- **HWB, vtree families**
  ([results/hwb_vtree_families.txt](results/hwb_vtree_families.txt)) for
  n = 4..22: right-linear, balanced, the pairs vtree P_n, and right spines of
  2, 4, or 6 end variables above a balanced vtree. P_n is the smallest of these
  from n = 12 on.
- **Tree automata** ([results/tree_automata.txt](results/tree_automata.txt)):
  for random automata with m = 3, 4, 5, 6, 8, 10 states (40 per m) on complete
  binary vtrees of depth 2..11, the largest number of decision nodes at one
  vtree node reaches 2^m − 2 (every non-constant set of states) for m ≤ 6, and
  242 of 254 for m = 8 and 884 of 1022 for m = 10. Before it saturates it
  grows by a factor between about 1.5 and 8 per level. The computation was checked
  against `canon` on the truth tables of 200 random automata of depth 3.
- **HWB circuit** ([results/hwb_circuit.txt](results/hwb_circuit.txt)): the
  circuit of Theorem 3.1 is correct on all inputs for n ≤ 14 and on 2000
  random inputs for n up to 1024, and its decomposition has width 8L + 2.

## 8. What is new, and what is cited

To our knowledge the following are new: Theorem 3.1 (though it may be
folklore), Corollary 4.1 (answering the question of Amarilli et al.),
Proposition 4.2, the failure of the argument for Theorem 15 on the circuit of
Theorem 3.1, and Corollary 4.3 (about arXiv:2604.05537v1; we checked only that
version), and Proposition 6.3. Theorem 5.4 is a complete proof of a bound that
Jha and Suciu's argument essentially gives. Theorem 6.2 is immediate from the
first study. Bova and Szeider's triple-exponential bound, Jha and Suciu's
pathwidth bound, Bryant's OBDD lower bound for HWB, Capelli et al.'s Theorem
19, and the lower bound of Amarilli et al. are cited, not re-proved.

## 9. Open problems

1. Is C(n, k) ≤ 2^O(k)·poly(n), or even n·2^O(k), as for uncompressed SDDs?
   By Theorem 6.2, a negative answer separates canonical from uncompressed
   SDDs.
2. Does HWB_n have polynomial canonical SDDs on some vtree (Bova's question)?
   A negative answer with size 2^(n^ε) would give C_pw(n, k) ≥ 2^(2^Ω(k)) by
   Theorem 3.1, matching the form of the pathwidth upper bound.
3. Is there an upper bound poly(n)·g(k) with g doubly exponential? The OBDD
   route cannot give better than doubly exponential (Corollary 4.1), nor can
   the factor-width route if Capelli et al.'s Theorem 19 holds (Corollary 4.3).
   The only known FPT bound is triple exponential. For tree automata with up
   to 6 states on balanced vtrees, every non-constant set of states appears as
   a decision node at one vtree node (section 5.2), so the last exponential of
   that count is reached there; this was computed for automata, not
   circuits.

## References

- R. E. Bryant. Graph-based algorithms for Boolean function manipulation.
  IEEE Trans. Computers 35(8), 1986.
- R. E. Bryant. On the complexity of VLSI implementations and graph
  representations of Boolean functions with application to integer
  multiplication. IEEE Trans. Computers 40(2), 1991.
- A. Darwiche. SDD: A new canonical representation of propositional knowledge
  bases. IJCAI 2011.
- A. K. Jha and D. Suciu. On the tractability of query compilation and bounded
  treewidth. ICDT 2012.
- I. Razgon. On OBDDs for CNFs of bounded treewidth. KR 2014.
- G. Van den Broeck and A. Darwiche. On the role of canonicity in knowledge
  compilation. AAAI 2015.
- S. Bova. SDDs are exponentially more succinct than OBDDs. AAAI 2016.
- S. Bova and S. Szeider. Circuit treewidth, sentential decision, and query
  compilation. PODS 2017.
- B. Bollig and M. Farenholtz. On the relation between structured d-DNNFs and
  SDDs. Theory of Computing Systems 65, 2021 (arXiv:1912.01430).
- A. Amarilli, F. Capelli, M. Monet, and P. Senellart. Connecting knowledge
  compilation classes and width parameters. Theory of Computing Systems 64,
  2020.
- F. Capelli, Y. Choi, S. Mengel, M. Muñoz, and G. Van den Broeck. A canonical
  generalization of OBDD. arXiv:2604.05537v1, 2026.
- I. Wegener. Branching Programs and Binary Decision Diagrams. SIAM, 2000.
