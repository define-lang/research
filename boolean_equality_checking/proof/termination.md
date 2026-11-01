# Fixing a Value Operation Always Terminates

DLP 59 adopts a precedence rule between spellings of a value, with the
restriction from [precedence.md](../precedence.md) that no fix grows the
program, and DLP 57 now gives boolean statements no literals: a constant is
simplified away instead. This proves that fixing a program, one reported
error at a time, always ends.

## The Model

### Programs

Fix a finite set of **inputs** (the value operation's boolean inputs), the
primitive operations `and` (two views) and `not` (one view), and a finite
set of **registered operations**. Each registered operation R has an arity
of at most four, a number of **AIG nodes** nodes(R) ≥ 1, a **position**
ord(R) in the declared order (distinct operations have distinct positions),
and a partition of its views into **interchangeable groups**. `and` has one
group of both views.

A value operation's boolean part is a list of **statements** s₁ … sₙ and a
list of **exits**: its written views, and the values its non-boolean
statements read. Each statement executes an operation on **values**: inputs
or earlier statements, never a literal. A statement's value is the
statement itself (an execution of a value operation with several written
views has a value for each). It's **canonical** when:

- every statement is read, directly or through other statements, by an
  exit (there are no **dead** statements), and
- the statements are in DLP 58's order, and every statement gives the
  values of each interchangeable group in rank order.

Every program is turned into a canonical one by **canonicalizing**: removing
dead statements and re-sorting. All programs the fixes see are canonical.

**Ranks** are DLP 58's. A value's **term** is its expression: an input or
constant is itself, and a statement is its operation applied to the terms
of the values it reads, with each interchangeable group sorted by rank. The
rank order <ᵣ compares terms: inputs first, in a fixed order; a statement's term after them; two statement terms by their
argument terms, in order, as DLP 58 defines, with a shorter list first, and
then by operation. It's a strict total order on terms, by induction on their
size. Terms don't depend on the program, so values of different programs
can be compared.

### Semantics

A set F of functions with decidable equality, containing the two constant
functions, a function for each input, and for each operation a map from its
views' functions to a function. A value's function follows by induction. A
value is **constant** when its function is one of the two constants. The
proof uses the semantics only through which values are constant.

### The fixes

Let P be canonical. "Earlier than v" means before v in P's statement order.

0. **Simplification.** A statement v whose value is constant, c. Every read
   of v is replaced by c, and then, until no boolean statement reads a
   constant: a boolean statement reading one is replaced by statements that
   compute what it computes from its other values (`x and false` is false,
   `x and true` is x, `not` of a constant is the other constant, and in
   general the statement's function with c put in), so it's either replaced
   by a constant, read as one of its values, or rewritten as new
   statements; a non-boolean statement takes the literal; a written view is
   left constant. New statements are written so that none of their values
   is constant, which is always possible: a constant one would itself be
   simplified away. Then canonicalize.
1. **Redundant value.** A statement v whose function equals an input's or
   an earlier statement's, w. The fix replaces every read of v (by
   statements and exits) with w, then canonicalizes. (DLP 57 reports the
   first such v, but any will do here.)
2. **Ordinary match.** A statement v, a registered operation R, and values
   a₁ … aₖ earlier than v, distinct, with v's function equal to R of
   theirs (**ordinary result**) or its `not` (**opposite result**). The fix
   replaces v's statement with an execution of R on a₁ … aₖ (and, for an
   opposite result, a `not` of it), makes every read of v read the new
   value, and canonicalizes. Let D be the statements that P has and the
   result doesn't: v's old statement and those that became dead. **The
   restriction:** |D| ≥ 2 for an ordinary result, which adds one statement,
   and |D| ≥ 3 for an opposite result, which adds two.
3. **Spelling.** A statement v that executes a registered operation R on
   values a, and a registered operation R′ with values a′ earlier than v,
   with R′ of a′ having v's function, and key(R′, a′) < key(R, a). The fix
   replaces v's statement with an execution of R′ on a′ and canonicalizes.
   Here

   key(R, a) = (neg(a), nodes(R), ord(R), the terms of a in rank order),

   compared lexicographically, where neg(a) counts the values in a that are
   statements executing `not`.

DLP 57 reports redundant values, constant ones included, before matches,
so **the value of a match or a spelling is never constant**; that's the only
thing the proof needs about the order of fixes. Every fix keeps each
statement's and each exit's function, and since every new statement reads
only values earlier than v, the result is a program (no statement reads
itself).

### Programs of value operations

A **program** is a set of value operations; a boolean statement can execute
another value operation, and the call graph is acyclic (which only matters
for the semantics). Besides the fixes above inside any one value operation,
there's one more:

4. **A constant written view.** A written view of a value operation A whose
   value is constant. It's removed from A, or A is removed if it was A's only
   written view. In every value operation that executes A, that execution's
   value from the view becomes the constant, which is simplified as in fix
   0 (an execution left with no values disappears).

## The Measure

### For one value operation

For the boolean part P of a value operation, let

- C(P) be the number of its values that are constant,
- S(P) be its number of statements,
- T(P) be the multiset of (neg(a), nodes(R), ord(R)) over its statements
  that execute a registered operation R on values a, and
- R(P) be the multiset of its statements' terms.

Order measures lexicographically: first C and then S as numbers, then T in
the
multiset order over lexicographically ordered triples, then R in the
multiset order over <ᵣ. The multiset order (Dershowitz and Manna) puts M′
below M when M′ ≠ M and M′ is M with some elements X removed and some
elements Y added, with every element of Y below some element of X. The
multiset order of a strict order is a strict order, so this lexicographic
order is a strict order.

**Theorem 1.** Every fix in a value operation takes P to P′ with a smaller
measure. A simplification lowers C; every other fix keeps C or lowers it,
and keeps S or lowers it.

### For a program

For a program Π, let Φ(Π) be the sum, over its value operations, of C plus
the number of written views. Order programs first by Φ, then **pointwise**:
Π′ is below Π when no value operation's measure went up (a removed value
operation counts as below every value operation), and one went down.

**Theorem 2.** Every fix of a program lowers it in this order. Simplifying
and removing a constant written view lower Φ; every other fix keeps Φ or
lowers it, and changes only one value operation, whose measure goes down.

**Corollary.** Fixing a program terminates. Φ is a number that never goes
up, so it goes down only finitely often, and it goes down at every
simplification and every removed written view. After the last time it goes
down, every fix is a redundant value, an ordinary match, or a spelling in
one value operation, and none of those adds a statement, so each value
operation has at most as many statements as it had then. There are finitely many programs with
those bounds, and a sequence that goes down in a strict order never
repeats a program, so it ends.

## Proof

**Lemma 1 (canonicalizing).** Re-sorting changes none of C, S, T, and R:
they're two counts and two multisets, and neither a statement's term, its
function, nor whether a value is a `not` depends on the order. Removing dead
statements removes elements from both multisets and lowers C or keeps it,
and lowers S.

**Lemma 0 (simplification).** v's value is constant, and it's gone. Every
statement that's replaced is replaced by a constant (it was constant
itself), by one of its values, or by new statements none of whose values is
constant, and every other statement keeps its function. So C(P′) ≤ C(P) − 1.
S can go up: see [Simplification Can Add Statements](#simplification-can-add-statements).

Every other fix adds no constant value: a redundant-value fix adds nothing,
and the new execution of a match or a spelling has v's function, which isn't
constant, and the `not` of an opposite result has its opposite. Every other
statement keeps its function. So for Lemmas 2–6, C(P′) ≤ C(P), and if C
went down, the measure did.

**Lemma 2 (redundant values).** Every read of v reads w instead, so v's
statement is dead and is removed, and no statement is added. So S(P′) ≤
S(P) − 1.

**Lemma 3 (ordinary matches).** S(P′) = S(P) − |D| + 1 for an ordinary
result and S(P) − |D| + 2 for an opposite one, so the restriction gives
S(P′) ≤ S(P) − 1.

**Lemma 4 (spelling, fewer statements).** S(P′) = S(P) − |D| + 1, and D
contains v's old statement, so S(P′) ≤ S(P). If any other statement
became dead, S went down.

Otherwise D = {v's old statement}, so S(P′) = S(P), and every other
statement of P is in P′ with the same operation and the same values. The
only statement whose triple can change is v's: the others execute the same
operations on the same values, and whether each of those values is a `not`
is unchanged, because v is an execution before and after. Two cases:

**Lemma 5 (spelling, a better triple).** If v's new triple is below its old
one, T(P′) is T(P) with the old triple replaced by a smaller one, which is
smaller in the multiset order.

**Lemma 6 (spelling, the same triple).** Otherwise the triples are equal,
since the key went down. Then ord(R′) = ord(R), so R′ = R, T(P′) = T(P),
and the key went down in its last part: the terms of a′ in rank order are
lexicographically below those of a. They're exactly the argument terms of
v's new and old terms (same operation, groups sorted; the values in a′ are
earlier than v, so they don't read v and their terms are the same in P′),
so v's new term is below its old one.

For any other statement u, u's new term is at most its old one (Lemma 7).
So R(P′) is R(P) with each term replaced by one at most as large, and v's
by a strictly smaller one. Taking X as the terms that changed and Y as
their replacements, every element of Y is below the element of X it
replaced, so R(P′) is below R(P) in the multiset order.

**Lemma 7 (monotonicity).** If a term t′ is t with some occurrences of a
subterm s replaced by s′ <ᵣ s, and its interchangeable groups re-sorted, then
t′ ≤ᵣ t. By induction on t. If t is s, t′ = s′. If t is an input or
constant, t′ = t. Otherwise t′'s arguments, before re-sorting, are each at
most t's, by induction. Sorting keeps that, position by position: the k-th
smallest of the new group is at most the k-th smallest of the old one,
because the k smallest old elements became k elements that are each at most
the k-th smallest old element. Lexicographic comparison of two lists of the
same length that are position by position at most each other gives at
most, and with the same operation, t′ ≤ᵣ t.

In P′, a statement's term is built from the terms of the values it reads,
which are earlier, so by induction over P′'s order every statement's new
term is its old term with v's term replaced by a smaller one: Lemma 7
applies.

Lemmas 0 and 2–6 cover every fix, which proves Theorem 1. ∎

**Lemma 8 (removing a constant written view).** A's number of written views
goes down by one, and C(A) doesn't go up (the view's statements may become
dead), or A is removed. In each value operation B that executes A, the
execution's value from the view was constant and isn't a value any more,
and the simplification that follows adds no constant value (Lemma 0), so
C(B) goes down. Every other value operation is unchanged. So Φ goes down.

**Proof of Theorem 2.** A fix inside one value operation changes only that
one: fixes keep the functions of written views, so callers see the same
functions, and a caller's statement executing A is the same statement. A
simplification lowers C, so Φ. Any other fix keeps C or lowers it, and
keeps the number of written views, so it keeps Φ or lowers it; if it keeps
Φ, it kept C, and that value operation's measure went down (Theorem 1)
while the others didn't change. Lemma 8 covers removing a constant written
view. ∎

## Simplification Can Add Statements

`mux(s, false, b)` computes `(not s) and b`. No single statement computes
that from s and b: `and`, `or`, `xor`, `eq`, and `implies` in either order
don't (checked by enumerating the 4-bit truth tables), and `mux` and `maj`
need three distinct values. So it's either `and(not s, b)` or
`not(implies(b, s))`, two statements, unless the value operation already
has `not s`. `and(not s, b)` is allowed: as the opposite result of
`implies(b, s)`, it removes two statements and would add two, so it's not a
match.

The smallest value operation where simplifying adds a statement:

    n  = not x
    c  = x and n          (always false)
    v₁ = mux(s₁, c, b₁)
    v₂ = mux(s₂, c, b₂)
    v₃ = mux(s₃, c, b₃)   (written views v₁, v₂, v₃)

c is the first error. Simplifying it removes c and n, and rewrites each vᵢ
as `and(not sᵢ, bᵢ)`, two statements: five statements become six. Across
value operations it takes less: if `k` is a constant written view of an
executed value operation, a caller's `mux(s, k, b)` becomes two statements
while the execution stays, because the executed value operation has other
written views.

That's why C comes first in the measure: simplification lowers C, whatever
it does to S, and no other fix raises C.

## The Cases the Earlier Argument Didn't Cover

- **New values as arguments of later fixes.** A fix's new execution can be
  an argument of a later match or spelling. That changes which fixes exist
  later, not the measure, which depends only on the program at hand: the
  theorem holds for every fix of every program.
- **Removed values shrinking option sets.** Likewise: removing a statement
  can make a spelling unavailable, but the measure doesn't count options.
- **Redundant-value fixes.** Lemma 2. They never add a statement, so they
  lower S.
- **Re-sorting.** The measure is a count and two multisets, which re-sorting
  doesn't change (Lemma 1). "Earlier" only decides which fixes exist.
- **Other values' keys changing.** A spelling fix can change other values'
  terms, and so their rank order, but only downward (Lemma 7), and it never
  changes another value's triple (Lemma 4), because a spelling fix never
  turns a value into a `not` or out of one. That's why DLP 59's rule that
  only single executions are respelled matters: respelling a `not` of an
  execution as an execution would turn a `not` into an execution, adding a
  triple, and could make other values' negation counts go down while their
  terms go up.

## What This Covers and What It Doesn't

- **Order of fixes.** The only thing assumed about DLP 57's order of
  reports is that a constant value is simplified before it could be matched
  or respelled. Nothing assumes the largest match first, or the
  highest-precedence spelling for an ordinary fix.
- **Simplification's own steps.** Simplifying one constant is one fix here,
  through all the statements it reaches. The rule that a non-boolean
  statement takes the literal, and that a constant written view is left
  for fix 4, only matter in that they end the simplification.
- **The bound** is the number of canonical programs with at most S(P)
  statements, which is finite but huge. It says nothing about how many
  rounds fixing takes in practice (at most 92 in the experiments).

## Checked Against the Fix Loop

`measure_check.py` runs the Python fix loop of `gen/fixpoint.py`, which
handles one value operation at a time and simplifies constants the way fix 0
does, with DLP 59's rules (`strict` and `precedence`, both declared orders) on all 144
families of [precedence.md](../precedence.md) and computes the measure after
every fix, without C (statements, then triples, then terms). Over 13,031
fixes (3,410 redundant values, 174 simplifications, 6,112 ordinary matches,
1,091 opposite results, and 2,244 spellings) it went down every time, so
none of those simplifications added a statement, and all 1,440 fix loops
ended.

The Python loop also respelled a `not` of an execution as an execution
until this check; that isn't part of DLP 59, and it was removed.

## The Lean Proof

`fixing_termination.lean`, built and checked by the Bazel targets in
`BUILD.bazel` (`bazelisk test //boolean_equality_checking/proof:all`),
formalizes Theorems 1 and 2 and the corollary. It has no `sorry` or `admit`,
and the axiom test checks that its theorems use only `propext`,
`Classical.choice`, and `Quot.sound`:

- **`opFix_lt`**: every fix in a value operation lowers its measure
  (Theorem 1).
- **`progStep_lt`**: every fix of a program lowers it, by Φ and then
  pointwise (Theorem 2).
- **`prog_no_cycle`**: no sequence of one or more fixes leads back to the
  program it started from.
- **`prog_terminates`**: an infinite sequence of fixes would visit
  infinitely many programs within fixed bounds on each value operation's
  number of statements (the corollary, with the counting fact as a
  hypothesis; see below).

The lemmas match the English proof: `opFix_constCount_le` is the first part
of Lemma 0 and of what follows it (no fix raises C, and simplifying lowers
it), `tripleOf_subst` is Lemma 4's claim that other statements keep their
triples, `dm_single` is Lemma 5, `dm_pointwise` is Lemma 6's multiset step,
`spelling_measure` puts Lemmas 4–6 together, `ser_subst_le` is Lemma 7, with
`insertionSort_mono` its step about sorting, `dropView_phi_lt` is Lemma 8,
`progStep_size_le` is the corollary's claim that once Φ stops going down no
value operation grows, and `DMLt`, `MeasureLt`, `OpLt`, `OptLt`, and
`ProgLt` are proved to be strict orders.

What the Lean model leaves out, or states differently:

1. **A value operation is its statements' terms and constant counts**, a
   list of (`Term`, number of constant values), rather than a graph in DLP
   58's order. Re-sorting isn't modeled: the measure doesn't depend on the
   order (Lemma 1), and "earlier" only decides which fixes exist.
2. **The semantics aren't modeled**, except through which values are
   constant. A fix is given by its shape: every statement that survives a
   fix is rewritten (`keepConst`) but keeps its number of constant values,
   because fixes keep functions, and every new statement has none. The
   conditions on functions that decide whether a fix exists only make there
   be fewer fixes, so the theorems hold for every fix of these shapes.
3. **Redundant values, ordinary matches, and simplifications are given by
   which statements survive** (rewritten) and which are added, with the
   restriction on ordinary matches as a count. A spelling fix is given in
   full: v's term becomes v''s, every other statement's term has v's
   replaced by v''s and its groups re-sorted, and some statements may
   become dead.
4. **Removing a constant written view is given by its effect** (Lemma 8):
   the value operation loses a written view and doesn't gain a constant
   value, or is removed; each value operation that executes it keeps its
   written views and has fewer constant values; the others don't change.
   The call graph isn't modeled, and doesn't need to be.
5. **Interchangeable groups are all of an operation's views or none.** That
   covers `and`, `or`, `xor`, `eq`, `maj`, `implies`, `mux`, and `not`, but
   not a registered operation with some views interchangeable and others
   not, which DLP 58 allows.
6. **The rank order is the lexicographic order of codes** (`ser`): `[1, i]`
   for an input, and for a statement 2, its values' codes (sorted for
   interchangeable views), 0, and the operation. That this is DLP 58's rank
   order rests on codes being prefix-free (`ser_prefix_free`), so that
   comparing codes compares the values first, then a shorter list first,
   then the operation; the correspondence with DLP 58's wording is argued
   here, not formalized. A registered operation has one written view, so
   DLP 58's last tie (which written view) doesn't arise.
7. **The counting fact is a hypothesis.** `prog_terminates` assumes that
   the programs the sequence visits, within any bounds on each value
   operation's number of statements, are finitely many. For programs it's
   the counting argument of the corollary: finitely many inputs and
   operations, and every value an earlier one. The model alone doesn't give
   it: a spelling's new term can be any term, and the rank order on all
   terms isn't well-founded (for example `f(x₁, x₁) > f(x₀, f(x₁, x₁)) >
   f(x₀, f(x₀, f(x₁, x₁))) > …`).
8. **A spelling requires that no other statement has v's term**, and matches
   and spellings add only non-constant statements, both of which hold
   because DLP 57 reports redundant values, constant ones included, before
   matches.
