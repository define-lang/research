# Linear Interpolation Has No Single-Use Form

This note proves that linear interpolation,

> f(a, b, t) = a + t·(b − a),

cannot be computed by any arithmetic single-use expression (SUE), even if the
expression only has to agree with f on some small open region of inputs.

Single-use expressions matter for range evaluation: if each input appears only
once, then evaluating the expression with interval arithmetic gives the exact
range of the result. Lorkowski, Kosheleva, and Kreinovich proved that every
function computable by an arithmetic SUE is a ratio of two multilinear functions
([Every Function Computable by an Arithmetic SUE Expression is a Ratio of Two Multi-Linear Functions](https://www.cs.utep.edu/vladik/2014/tr14-77a.pdf),
University of Texas at El Paso technical report UTEP-CS-14-77a). Linear
interpolation is itself multilinear: it is a polynomial of degree at most one in
each of a, b, and t. So their theorem does not rule it out, and a separate
argument is needed. This note gives one.

## Scope

The proof covers exactly the expressions in the paper's definition: finite
sequences of binary +, −, ×, and ÷ operations whose operands are constants,
inputs, or earlier results. It also allows the constants to be any real numbers,
not only rational numbers, which makes the result slightly stronger.

It does not cover expressions that also use other operations, for example
powers, roots, absolute value, minimum, maximum, exponentials, conditionals, or
a built-in ternary operation such as fused multiply-add. Nothing here says
whether linear interpolation has a single-use form when such operations are
allowed.

It also does not cover agreement on sets that are not open. For example, on the
plane a = 0, linear interpolation equals t·b, which is single-use.

## Definitions

Throughout, the inputs are the three real variables a, b, and t, and a point is
a triple (a, b, t) in R³.

**Arithmetic expression.** An arithmetic expression is a finite sequence of
rules

> s₁ := u₁ ⊙₁ v₁, s₂ := u₂ ⊙₂ v₂, …, s_N := u_N ⊙_N v_N,

where each operation ⊙ᵢ is +, −, ×, or ÷, and each operand uᵢ or vᵢ is a real
constant, one of the inputs a, b, t, or an earlier result s_k with k < i. This
is Definition 1 of the paper, with real constants in place of rational ones.

**Value and domain.** At a point x, the expression's value is s_N, computed by
performing every rule in order. The expression is _defined_ at x if no rule
divides by zero there. The _domain_ of the expression is the set of points at
which it is defined. The paper evaluates every rule, not only the ones s_N
depends on, so a rule whose result is never used can still shrink the domain.
That only makes the domain smaller, and the proof below never needs it to be
larger.

**Single-use expression (SUE).** An arithmetic expression is a SUE if each input
and each result s_k appears at most once among all the operands u₁, v₁, …, u_N,
v_N. This is Definition 2 of the paper.

**Computing a function on a set.** An expression _computes_ a function F _on_ a
set U if the expression is defined at every point of U and its value equals F(x)
at every point x of U.

The paper's Definition 3 asks the value to equal F "for each tuple", and its own
example, 1/(1 + x₂/x₁), is accepted only "at least for x₁ ≠ 0". So the paper in
effect means equality wherever the expression is defined. Lemma 1 shows that the
domain of an expression is open. So if a SUE equals linear interpolation
wherever it is defined, and it is defined anywhere at all, then it computes
linear interpolation on a nonempty open set. The theorem below rules this out,
so it also rules out the paper's notion of equivalence.

Agreement on a nonempty open set is the weakest kind of agreement that is still
useful for range evaluation, because the input ranges of interest are boxes with
nonzero width in each input.

**Expression tree.** The tree of a rule sᵢ := uᵢ ⊙ᵢ vᵢ is a node labeled ⊙ᵢ with
two children: the tree of uᵢ and the tree of vᵢ. The tree of a constant or an
input is a single leaf with that label. The _inputs of_ a tree are the inputs
that label its leaves. A tree whose inputs are empty is a _constant tree_.

**Möbius map.** A Möbius map is a function of one real variable of the form

> M(u) = (α·u + β) / (γ·u + δ), with α·δ − β·γ ≠ 0.

The number α·δ − β·γ is its _determinant_. The map is defined wherever γ·u + δ
≠ 0.

**Partial derivatives.** For a function g of the three inputs, g_x is its
partial derivative with respect to the input x, and g_xy is the mixed second
partial derivative with respect to x and then y.

The derivatives of linear interpolation are:

| Derivative | Value |
| ---------- | ----- |
| f_a        | 1 − t |
| f_b        | t     |
| f_t        | b − a |
| f_at       | −1    |
| f_bt       | 1     |

## Theorem

There is no arithmetic SUE that computes linear interpolation f(a, b, t) = a +
t·(b − a) on any nonempty open subset of R³.

## Lemmas

### Lemma 1: Domains are open, and values are smooth.

For every arithmetic expression, the domain of each result sᵢ (the set of points
where the rules s₁ … sᵢ are all defined) is open, and sᵢ is infinitely
differentiable there. So is the domain of the whole expression.

_Proof._ By induction on i. A constant or an input is defined and infinitely
differentiable everywhere. If uᵢ and vᵢ have open domains and are infinitely
differentiable there, then uᵢ + vᵢ, uᵢ − vᵢ, and uᵢ × vᵢ are infinitely
differentiable on the intersection of those domains, which is open. For uᵢ ÷ vᵢ,
the domain is also limited to the points where vᵢ ≠ 0. Because vᵢ is continuous,
that set is open, and the quotient is infinitely differentiable on it. The whole
expression's domain is the intersection of the finitely many domains of its
rules, so it is open. ∎

### Lemma 2: A SUE's top result is a tree that uses each input at most once.

In a SUE, the tree of s_N has no repeated nodes, each input labels at most one
of its leaves, and the value of s_N at a point depends only on the inputs of
that tree.

_Proof._ Each result s_k and each input appears at most once as an operand, so
it has at most one parent in the tree. So no node is reached twice, and each
input is at most one leaf. The value of a tree is computed only from its leaves,
so it depends only on the inputs that label them. ∎

### Lemma 3: A polynomial that vanishes on a nonempty open set is zero.

If a real polynomial P in the variables a, b, t is 0 at every point of a
nonempty open set U, then every coefficient of P is 0.

_Proof._ Choose a point c in U. Every partial derivative of P is also 0 at c,
because P is 0 on a neighborhood of c. The coefficients of P, written as a
polynomial in (a − c_a), (b − c_b), (t − c_t), are its partial derivatives at c
divided by factorials, so they are all 0. So P is the zero polynomial, and its
coefficients in a, b, t are also all 0. ∎

### Lemma 4: Linear interpolation depends on every input on every open set.

Let U be a nonempty open set. If a function g equals f on U, then g is not
constant on U, and for each input x in {a, b, t}, g_x is not 0 everywhere on U.

_Proof._ On U, g_a = 1 − t, g_b = t, and g_t = b − a. Each of these is a nonzero
polynomial, so by Lemma 3 none of them is 0 everywhere on U. If g were constant
on U, all three would be 0 on U. ∎

### Lemma 5: Peeling off constants leaves a Möbius map of a two-sided node.

Suppose a SUE computes f on a nonempty open set U. Then there are:

- a node of the tree of s_N with operation ⊙ ∈ {+, −, ×, ÷}, whose two children
  are trees φ and ψ with nonempty inputs S₁ and S₂, where S₁ and S₂ do not
  overlap and together are {a, b, t}; and
- a Möbius map M(u) = (α·u + β)/(γ·u + δ),

such that, writing h for the value of that node, h is defined on U, γ·h + δ ≠ 0
on U, and f = M(h) on U.

_Proof._ If an input x were not among the inputs of the tree of s_N, then by
Lemma 2 the value s_N would not depend on x, so (s_N)_x = 0 on U. Since s_N = f
on U, that contradicts Lemma 4. So the tree of s_N has a, b, and t among its
inputs.

Walk down from the top node of the tree. At each node w = u ⊙ v visited so far,
the inputs of w are all of {a, b, t}. If both children have inputs, stop. If
both children are constant trees, then w has no inputs, which is impossible.
Otherwise exactly one child is a constant tree. Its value is a fixed real number
c, because it does not depend on the point, and it is defined, because U is
nonempty and lies in the domain. Then w = σ(w′), where w′ is the other child and
σ is one of the _steps_

> σ(u) = c + u, u + c, c − u, u − c, c·u, u·c, u/c, or c/u.

Continue down to w′, which has the same inputs as w. This walk ends, because the
tree is finite. It cannot end at a leaf, because a leaf has at most one input.
So it ends at a node whose children both have inputs. Call that node's value h.
By Lemma 2, its two children use different inputs, so their input sets S₁ and S₂
do not overlap, and together they are {a, b, t}.

No step is degenerate. If a step were c·u or u·c with c = 0, or c/u with c = 0,
then every node above it, including s_N, would be constant on U. That
contradicts Lemma 4. If a step were u/c with c = 0, the expression would be
undefined everywhere, so U would be empty.

So each step has c ≠ 0 when its operation is × or ÷. Each step is then a Möbius
map. When a step σ is applied to a Möbius map (α·u + β)/(γ·u + δ), the result is
the Möbius map in this table:

| Step σ       | New α, β, γ, δ   | New determinant |
| ------------ | ---------------- | --------------- |
| c + u, u + c | α+cγ, β+cδ, γ, δ | αδ − βγ         |
| c − u        | cγ−α, cδ−β, γ, δ | −(αδ − βγ)      |
| u − c        | α−cγ, β−cδ, γ, δ | αδ − βγ         |
| c·u, u·c     | cα, cβ, γ, δ     | c·(αδ − βγ)     |
| u/c          | α, β, cγ, cδ     | c·(αδ − βγ)     |
| c/u          | cγ, cδ, α, β     | −c·(αδ − βγ)    |

Start with the identity map (α, β, γ, δ) = (1, 0, 0, 1), whose value at h is h,
and apply the steps from the bottom of the walk to the top. At each step the
determinant stays nonzero, because c ≠ 0 wherever it multiplies the determinant.
The new denominator is still nonzero at every point of U. For every step except
c/u, it is the old denominator or c times it. For c/u it is α·h + β, the old
numerator, which is nonzero because the step divides by the old value there.
After the last step, the Möbius map M gives s_N = M(h) on U, and s_N = f on U. ∎

### Lemma 6: The two-sided node is a Möbius map of linear interpolation.

With M and h as in Lemma 5, let

> N(u) = (p·u + q)/(r·u + s), where p = δ, q = −β, r = −γ, s = α.

Then N has determinant D = p·s − q·r = α·δ − β·γ ≠ 0, r·f + s ≠ 0 on U, and h =
N(f) on U.

_Proof._ The determinant is δ·α − (−β)·(−γ) = α·δ − β·γ. On U, f·(γ·h + δ) =
α·h + β, so h·(γ·f − α) = β − δ·f. Suppose γ·f − α = 0 at some point of U. Then
β − δ·f = 0 there too. If γ ≠ 0, then f = α/γ, so β = δ·α/γ, and α·δ − β·γ = 0.
If γ = 0, then α = 0, and α·δ − β·γ = 0. Both contradict Lemma 5. So r·f + s = α
− γ·f ≠ 0 on U, and h = (δ·f − β)/(α − γ·f) = N(f). ∎

### Lemma 7: The two-sided node is separable.

Let h, ⊙, S₁, and S₂ be as in Lemma 5, and let x be an input in S₁ and y an
input in S₂. Then on U:

- if ⊙ is + or −, then h_xy = 0; and
- if ⊙ is × or ÷, then h·h_xy − h_x·h_y = 0.

_Proof._ Let g₁ and g₂ be the values of the trees φ and ψ. By Lemma 1, both are
infinitely differentiable on U. By Lemma 2, g₁ depends only on the inputs in S₁,
and g₂ only on the inputs in S₂. So (g₁)_y = 0 and (g₂)_x = 0 on U.

If h = g₁ ± g₂, then h_x = (g₁)_x, which does not depend on y, so h_xy = 0.

If h = g₁·k, where k is g₂ (for ×) or 1/g₂ (for ÷; g₂ ≠ 0 on U because U lies in
the domain), then k depends only on the inputs in S₂, and h_x = (g₁)_x·k, h_y =
g₁·k_y, and h_xy = (g₁)_x·k_y. So h·h_xy = g₁·k·(g₁)_x·k_y = h_x·h_y.

The same argument works when the children are in the other order, for example
h = g₂ − g₁ or h = g₂/g₁, with the roles of x and y exchanged. ∎

This lemma uses only the forward direction: separable implies the derivative
equation. It does not need the converse, so it does not need U to be connected
or h to be nonzero.

### Lemma 8: The separability equations in terms of linear interpolation.

Let N, p, q, r, s, and D be as in Lemma 6, let h = N(f) on U, and let x and y be
inputs. Define the polynomials

> A_xy = −2·r·f_x·f_y + (r·f + s)·f_xy
>
> B_xy = −(2·p·r·f + p·s + q·r)·f_x·f_y + (p·f + q)·(r·f + s)·f_xy.

Then on U,

> h_xy = D·A_xy/(r·f + s)³ and h·h_xy − h_x·h_y = D·B_xy/(r·f + s)⁴.

_Proof._ By the chain rule, h_x = N′(f)·f_x and h_xy = N″(f)·f_x·f_y +
N′(f)·f_xy, where N′(u) = D/(r·u + s)² and N″(u) = −2·r·D/(r·u + s)³. That gives
the first equation. For the second,

> h·h_xy − h_x·h_y = (N(f)·N″(f) − N′(f)²)·f_x·f_y + N(f)·N′(f)·f_xy.

Here N·N″ − N′² = −D·(2·r·(p·u + q) + D)/(r·u + s)⁴, and 2·r·(p·u + q) + D =
2·p·r·u + p·s + q·r. Also N·N′ = D·(p·u + q)·(r·u + s)/(r·u + s)⁴. Substituting
u = f gives the second equation. ∎

### Lemma 9: Neither equation can hold for the pairs (a, t) and (b, t).

If D ≠ 0, then A_at, B_at, A_bt, and B_bt are all nonzero polynomials in a, b,
t.

_Proof._ Recall f = a − a·t + b·t, so f has no constant term, no term that is
only b, and the term a. Also

> (p·f + q)·(r·f + s) = p·r·f² + (p·s + q·r)·f + q·s.

The terms of f² all have degree 2, so this has constant term q·s and the term
(p·s + q·r)·a, and no term that is only b.

- A_at = −2·r·(1 − t)·(b − a) − (r·f + s). Its constant term is −s. Its
  coefficient of b is −2·r.
- B_at = −(2·p·r·f + p·s + q·r)·(1 − t)·(b − a) − (p·f + q)·(r·f + s). Its
  constant term is −q·s. Its coefficient of b is −(p·s + q·r).
- A_bt = −2·r·t·(b − a) + (r·f + s). Its constant term is s. Its coefficient of
  a is r.
- B_bt = −(2·p·r·f + p·s + q·r)·t·(b − a) + (p·f + q)·(r·f + s). Its constant
  term is q·s. Its coefficient of a is p·s + q·r.

If A_at or A_bt is zero, then r = s = 0, so D = p·s − q·r = 0.

If B_at or B_bt is zero, then q·s = 0 and p·s + q·r = 0. If q = 0, then D =
p·s = p·s + q·r = 0. If q ≠ 0, then s = 0, so q·r = 0 and r = 0, and again
D = 0.

Each case contradicts D ≠ 0. ∎

### Lemma 10: Every split separates t from a or from b.

If {a, b, t} is divided into two nonempty sets S₁ and S₂ that do not overlap,
then the set that does not contain t contains a or b.

_Proof._ That set is nonempty and does not contain t. ∎

## Proof of the Theorem

Suppose a SUE computes f on a nonempty open set U. Lemma 5 gives a node with
operation ⊙, input sets S₁ and S₂, value h, and Möbius map M. Lemma 6 gives the
map N with determinant D ≠ 0, r·f + s ≠ 0 on U, and h = N(f) on U.

By Lemma 10, there is an input x ∈ {a, b} that is in a different set from t.
Apply Lemma 7 to x and t.

- If ⊙ is + or −, then h_xt = 0 on U. By Lemma 8, D·A_xt/(r·f + s)³ = 0 on U,
  and since D ≠ 0 and r·f + s ≠ 0, A_xt = 0 on U.
- If ⊙ is × or ÷, then h·h_xt − h_x·h_t = 0 on U, and in the same way B_xt = 0
  on U.

By Lemma 3, that polynomial is the zero polynomial. That contradicts Lemma 9. So
no such SUE exists. ∎

## Machine Checks

### Lean

The whole theorem is formalized in Lean 4 with Mathlib in
[linear_interpolation.lean](linear_interpolation.lean). Its main theorem,
`Define.SingleUseExpression.linear_interpolation_has_no_single_use_form`, says:
for every arithmetic expression that is well formed (it has at least one rule,
and each result operand names an earlier rule) and single-use, and for every
nonempty open set U in R³, the expression does not compute linear
interpolation on U. The Lean definitions follow the paper's Definitions 1 and 2
directly: an expression is a sequence of rules, its value is the value of its
last rule, it is defined at a point when no rule divides by zero there, and
single use means that two operand positions holding the same input or the same
result are the same position.

`#print axioms` for the main theorem reports only Lean's three standard axioms:

```text
'Define.SingleUseExpression.linear_interpolation_has_no_single_use_form' depends on axioms: [propext,
 Classical.choice,
 Quot.sound]
```

The file also proves `lerpExpression_computes`: the three-rule expression
s₀ := b − a, s₁ := t × s₀, s₂ := a + s₁ is well formed, computes linear
interpolation everywhere, and is not single-use. This shows that the
definitions are not vacuous, and that single use is what the theorem excludes.

To check the proof, run this from the repository root:

```console
bazelisk test //single_use_expression_proofs/...
```

That builds the proof, which fails on any `sorry`, and runs an axiom test that
fails if either theorem depends on any axiom other than `propext`,
`Classical.choice`, and `Quot.sound`.

The Lean proof follows the same plan as this note, with these differences in
technique:

- **Lemma 2.** Instead of building trees, the Lean proof works on the sequence
  itself. It defines when one rule is reached from another, and proves that two
  rules reached from the same rule are reached from each other in one
  direction or the other, because each result has at most one parent. From
  this it proves that the two operands of every rule have no inputs in common.
- **Lemma 5.** The peeling is an induction on the rules. Instead of walking
  down and composing the steps from the bottom up, it keeps a Möbius map M and
  replaces M by M ∘ σ at each step. The steps and their determinants are the
  same as in the table.
- **Lemmas 1, 7, and 8.** Lean's division is total (u/0 = 0), and an operand
  that does not use an input gives the same value for any two points that
  differ only in that input, everywhere. So Lean needs no smoothness for the
  operands, and it differentiates only N(f), which is explicit. With the third
  input fixed, the additive case shows that the derivative of N(f) with
  respect to x does not depend on t, and the multiplicative case shows that
  N(f)·∂ₓ∂ₜN(f) − ∂ₓN(f)·∂ₜN(f) = 0 at each point. The equations it gets are
  exactly A_xt = 0 and B_xt = 0 from Lemma 8, for x = a and x = b.
- **Lemmas 3, 4, and 9.** Instead of the general fact about polynomials, the
  Lean proof evaluates the equations at a grid of points with spacing ε/3 in
  the ball. The mixed difference in x and t isolates r in A, and the
  second-order differences in x and t isolate p·r in B. The rest of Lemma 9
  then follows as written. Lemma 4 is checked the same way, with four points.

### SymPy

Before the Lean proof was written, every algebraic step was also checked
symbolically with SymPy 1.14.0. The scripts were run once and are not kept in
this repository. They checked:

- **Lemma 5:** each row of the step table. For each step σ, the script checked
  that σ applied to (α·u + β)/(γ·u + δ) simplifies to the Möbius map in the
  table, and that the table's determinant is correct.
- **Lemma 6:** M(N(u)) simplifies to u, and N's determinant equals M's.
- **Lemma 7:** for symbolic functions φ(x) and ψ(y), the mixed partial of φ + ψ
  and φ − ψ is 0, and h·h_xy − h_x·h_y is 0 for h = φ·ψ and h = φ/ψ.
- **Lemma 8:** with N(f) for symbolic p, q, r, s, the formulas for N′ and N″,
  and both equations, for every pair of inputs in different sets of every split
  (six pairs in all).
- **Lemma 9:** the full lists of coefficients of A_xy and B_xy for those six
  pairs. The coefficients stated in Lemma 9 match the computed ones. As an
  independent check of the case analysis, for each polynomial the script
  computed a Gröbner basis of its coefficients together with D·z − 1, where z is
  a new variable. A basis of {1} means the coefficients cannot all be 0 when D
  is invertible, that is, when D ≠ 0. The basis was {1} for every polynomial
  except A_ab for the split {a, t} | {b} and A_ba for the split {b, t} | {a},
  which are 2·r·t·(t − 1). Those two are zero when r = 0 because f_ab = 0, which
  is why the proof uses the pairs (a, t) and (b, t) instead.
- **Lean grid steps:** the finite differences used by the Lean proof, which are
  −r·h² for A and ±4·p·r·h⁴ for B, and the form that B takes when p·r = 0.

## Summary

This note proved that no arithmetic SUE computes linear interpolation a + t·(b −
a) on any nonempty open set of inputs. An arithmetic SUE is a sequence of binary
+, −, ×, and ÷ operations on real constants, inputs, and earlier results, in
which each input and each result is used at most once. The proof peels the
constants off the top of the expression, which leaves a Möbius map of a single
node that combines two parts with no inputs in common. It then shows that no
Möbius map of linear interpolation is additively or multiplicatively separable
between t and a, or between t and b. The whole proof is checked in Lean, with
Mathlib and only Lean's standard axioms.

It did not prove anything about expressions that also use other operations, such
as powers, roots, absolute value, minimum, maximum, or conditionals. It also did
not prove anything about agreement on sets that are not open, such as a plane on
which one input is fixed.
