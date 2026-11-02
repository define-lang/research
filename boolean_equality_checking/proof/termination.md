# Fixing a Value Operation Always Terminates

DLP 59 adopts a precedence rule between spellings of a value, with the
restriction from [precedence.md](../precedence.md) that no fix grows the
program, and DLP 57 now gives boolean statements no literals: a constant is
simplified away instead. DLP 57 also makes a value that's always the
opposite of an earlier one redundant, unless it's that value's `not`. This
proves that fixing a program, one reported error at a time, always ends.

## The Model

### Programs

Fix a finite set of **inputs** (the value operation's boolean inputs), the
primitive operations `and` (two views) and `not` (one view), and a finite
set of **registered operations**. DLP 59 makes `and` and `not` registered
for every value operation, before the others, so an `and` is an execution
of a registered operation like any other (it has a triple, below, and can
be respelled), and a match can be written with an `and` or a `not`; `not`
statements are still left out of the executions that are respelled. Which
registered operations a value operation follows (a registered operation's
own definition follows only the ones listed before it) only decides which
fixes exist, which the proof never needs. Each registered operation R has an arity
of at most four, a number of **AIG nodes** nodes(R) ≥ 1, a **position**
ord(R) in the declared order (distinct operations have distinct positions),
and a partition of its views into **interchangeable groups**, which need
not be consecutive views: in `(a and b) or c` as one operation, a and b are
one group and c is another. `and` has one group of both views.

A value operation's boolean part is a list of **statements** s₁ … sₙ and a
list of **exits**: its written views, and the values its non-boolean
statements read. Each statement executes an operation on **values**: inputs
or earlier statements, never a literal. A statement's value is the
statement itself: DLP 57 makes a boolean value operation write exactly one
view, so an execution of one has one value. It's **canonical** when:

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
   simplified away. An execution given a constant whose result is no
   simpler function is replaced by the executed operation's own statements
   written out with the constant, and those are simplified the same way, so
   the fix stays inside the value operation and adds no value operation.
   Then canonicalize.
1. **Redundant value.** A statement v whose function equals an input's or
   an earlier statement's, w. The fix replaces every read of v (by
   statements and exits) with w, then canonicalizes. (DLP 57 reports the
   first such v, but any will do here.)
2. **Opposite value.** A statement v whose function is the opposite of an
   input's or an earlier statement's, w, when v's statement isn't
   `not w`. The fix replaces v's statement with `not w`, then
   canonicalizes; every read of v reads the `not`. After `u = a and b`, it
   turns `(not a) or (not b)` into `not u`, removing three statements and
   adding one, and a registered `nand` of a and b into `not u`, one
   statement for one.
3. **Ordinary match.** A statement v, a registered operation R, and values
   a₁ … aₖ earlier than v, distinct, with v's function equal to R of
   theirs (**ordinary result**) or its `not` (**opposite result**). The fix
   replaces v's statement with an execution of R on a₁ … aₖ (and, for an
   opposite result, a `not` of it), makes every read of v read the new
   value, and canonicalizes. Let D be the statements that P has and the
   result doesn't: v's old statement and those that became dead. **The
   restriction:** |D| ≥ 2 for an ordinary result, which adds one statement,
   and |D| ≥ 3 for an opposite result, which adds two.
4. **Spelling.** A statement v that executes a registered operation R on
   values a, and a registered operation R′ with values a′ earlier than v,
   with R′ of a′ having v's function, and key(R′, a′) < key(R, a). The fix
   replaces v's statement with an execution of R′ on a′ and canonicalizes.
   Here

   key(R, a) = (neg(a), nodes(R), ord(R), the terms of a in rank order),

   compared lexicographically, where neg(a) counts the values in a that are
   statements executing `not`.

5. **Dead statements.** Boolean statements whose values reach no exit
   (DLP 57 makes them an error). They're removed; every other statement
   stays as it is.

DLP 57 reports redundant values, constant ones included, before matches,
so **the value of a match or a spelling is never constant**. DLP 57 also
reports the first redundant value, so **the value of an opposite-value fix
isn't a `not`**: if v were `not x`, with x not w, then x and w would have
the same function, and since both come before v and inputs have different
functions, the later of x and w would be a redundant value before v. Those
are the only things the proof needs about the order of fixes. The second
one matters: if x and w are both read elsewhere, `not x` and `not w` are
each an opposite value of the other's argument, and fixing either one gives
the other, forever. Every fix keeps each statement's and each exit's
function, and since every new statement reads only values earlier than v,
the result is a program (no statement reads itself).

### Programs of value operations

A **program** is a set of value operations; a boolean statement can execute
another value operation, and DLP 9 forbids execution cycles, so the call
graph is acyclic. Besides the fixes above inside any one value operation,
there are three more:

6. **A constant written view.** A written view of a value operation A whose
   value is constant. It's removed from A, or A is removed if it was A's only
   written view. In every value operation that executes A, that execution's
   value from the view becomes the constant, which is simplified as in fix
   0 (an execution left with no values disappears).
7. **A read view that doesn't matter.** A read view of a boolean value
   operation A that A's written view doesn't depend on (DLP 57 makes it an
   error). Its reads in A are given another read view A keeps, and then
   the view is removed. A's written view doesn't depend on it, so this
   keeps the written view's function; values that read it can compute
   something else, and can become constant, like `y and not y`, which then
   take the usual fixes. (Giving the reads a constant instead makes every
   execution that reads the view one given a constant, written out with
   everything it executes; the fix loop does that only when A keeps no
   other read view.) Every execution of A stops giving it a value; a
   statement that only that value read is then dead, and it's removed (fix
   5). Every execution of A computes what it did.
8. **A match or spelling that would make a cycle.** A match or a spelling
   (fixes 3 and 4) in a value operation A whose new execution is of a
   registered operation R whose definition executes A, directly or through
   other value operations. Executing R in A would make an execution cycle,
   which DLP 9 forbids, so first, in R's definition, the execution that
   leads back to A is written out: it's replaced by the executed
   operation's own statements, its views given the execution's values, as
   fix 0 writes out an execution given a constant, and the copied
   statements' constant values are simplified as in fix 0. That's repeated
   until nothing in R's definition leads back to A, which ends: each
   execution written out is replaced by executions of what it executed,
   lower in the acyclic call graph. Then the match or spelling in A is
   applied. R's written and read views and its function don't change, and
   neither does any other value operation's; R's statements can grow. It
   adds no match in R for R: a definition only follows the registered
   operations listed before it.

   R always comes after A in a fixed **priority** order: value operations
   that aren't registered first, then the registered ones from the last
   listed in booleans.defcl to the first. If A is registered, R is a
   registered operation A follows, listed before A; if A isn't, R is
   registered. Fixes 0–7 keep the call graph acyclic, since the only new
   executions they add are of registered operations or of what an
   operation already executes, so a program the fixes reach from one
   without cycles has none.

   The fix loop (`src/program_fix.hpp`, `write_out_leading_back`) copies
   the statements as they are and leaves their constant values to R's own
   fixes, which come first when R is fixed again; the proof takes the copy
   and those simplifications as one step.

## The Measure

### For one value operation

For the boolean part P of a value operation, let

- C(P) be the number of its values that are constant,
- S(P) be its number of statements,
- K(P) be the number of its statements that aren't a `not`,
- T(P) be the multiset of (neg(a), nodes(R), ord(R)) over its statements
  that execute a registered operation R on values a, and
- R(P) be the multiset of its statements' terms.

Order measures lexicographically: first C, S, and K as numbers, then T in
the multiset order over lexicographically ordered triples, then R in the
multiset order over <ᵣ. The multiset order (Dershowitz and Manna) puts M′
below M when M′ ≠ M and M′ is M with some elements X removed and some
elements Y added, with every element of Y below some element of X. The
multiset order of a strict order is a strict order, so this lexicographic
order is a strict order.

**Theorem 1.** Every fix in a value operation takes P to P′ with a smaller
measure. A simplification lowers C; every other fix keeps C or lowers it,
and keeps S or lowers it.

### For a program

For a program Π, let V(Π) be the number of read views over its value
operations, and Φ(Π) the sum, over its value operations, of C plus the
number of written views. Order programs first by V, then by Φ, then
**pointwise**:
Π′ is below Π when no value operation's measure went up (a removed value
operation counts as below every value operation), and one went down.

**Theorem 2.** No fix adds a read view, so none raises V, and removing a
read view that doesn't matter lowers it. Every other fix keeps V, and keeps
Φ or lowers it: simplifying and removing a constant written view lower it.
Every other fix that keeps Φ changes one value operation,
whose measure goes down and whose statements don't grow, except fix 8,
which also changes R, after it in the priority order, keeping R's views
and not raising C(R). Without fix 8, every fix lowers the program in this
order.

Fix 8 can make R bigger, so the program order doesn't go down at fix 8,
and the bound on each value operation's statements in the corollary
doesn't hold for R. The corollary is proved by the priority order instead.

**Corollary.** Fixing a program terminates. V is a number that never goes
up, so it goes down only finitely often, at every removed read view. After
that, Φ never goes up, so it goes down only finitely often, at every
simplification and every removed written view. After the last time either
goes down, every fix is a redundant value, an
opposite value, an ordinary match, a spelling, removing dead statements in
one value operation, or fix 8, and by induction along the priority order,
every value operation eventually stops changing:

- Once every value operation before B in the priority order has stopped
  changing, B can only change by a fix in B itself: fix 8 changes a value
  operation only together with one before it, which would change too. A
  fix in B lowers B's measure and adds no statement (Theorem 1, with C the
  same since Φ is), so B's statements stay within a bound. There are
  finitely many states of a value operation within that bound (the
  counting fact below), and the measure is a strict order, so B never
  returns to a state it left and changes only finitely often.

After all of them stop, no fix happens, but every fix changes something,
so the sequence ends. The counting fact: a value operation with at most a
given number of statements, over finitely many inputs and operations,
every value an earlier one, has finitely many states.

**When it ends, the program compiles**, if every error has a fix. They all
do except these, which the programmer has to fix: an operation past DLP
57's limits as written (the fixes may pass the statement limit on the way
to a smaller operation, and the fix loop checks past it), an execution
cycle in the program as written (DLP 9; the fixes never make one), a
registered operation whose definition is a wrapper (it can't be removed
like another wrapper), and a fix 8 whose execution leading back is of a
mixed operation (`run`), which the fix loop doesn't write out.

## Proof

**Lemma 1 (canonicalizing).** Re-sorting changes none of C, S, K, T, and R:
they're three counts and two multisets, and neither a statement's term, its
function, nor whether a value is a `not` depends on the order. Removing dead
statements removes elements from both multisets and lowers C or keeps it,
and lowers S.

**Lemma 0 (simplification).** v's value is constant, and it's gone. Every
statement that's replaced is replaced by a constant (it was constant
itself), by one of its values, or by new statements none of whose values is
constant, and every other statement keeps its function. So C(P′) ≤ C(P) − 1.
S can go up: see [Simplification Can Add Statements](#simplification-can-add-statements).

Every other fix adds no constant value: a redundant-value fix adds nothing,
the new execution of a match or a spelling and the `not` of an opposite
value have v's function, which isn't constant, and the `not` of an opposite
result has its opposite. Every other statement keeps its function. So for
Lemmas 2–6 and 9, C(P′) ≤ C(P), and if C went down, the measure did.

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
statement of P is in P′ with the same operation and the same values. v
executes a registered operation before and after, so K(P′) = K(P). The
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
most t's, by induction. Sorting each group among its own views keeps that,
position by position, and leaves the other views alone: the k-th
smallest of the new group is at most the k-th smallest of the old one,
because the k smallest old elements became k elements that are each at most
the k-th smallest old element. Lexicographic comparison of two lists of the
same length that are position by position at most each other gives at
most, and with the same operation, t′ ≤ᵣ t.

In P′, a statement's term is built from the terms of the values it reads,
which are earlier, so by induction over P′'s order every statement's new
term is its old term with v's term replaced by a smaller one: Lemma 7
applies.

**Lemma 9 (opposite values).** S(P′) = S(P) − |D| + 1, where D is v's old
statement and those that became dead, so S(P′) ≤ S(P), and if anything else
became dead, S went down. Otherwise S(P′) = S(P). v's old statement isn't a
`not` and its new one is, and every other statement executes the same
operation as before (its values' terms may change), so K(P′) = K(P) − 1.

T can go up here, which is why K comes before it. After `u = a and b`,
turning `v = nand(a, b)` into `not u` makes `xor(v, c)` an `xor` given a
`not`, with triple (1, nodes(xor), ord(xor)), above both triples it
replaces, `nand`'s and `xor`'s old one, whose negation counts are 0.

**Lemma 11 (dead statements).** At least one statement is removed and every
other is unchanged, so S(P′) ≤ S(P) − 1 and C(P′) ≤ C(P).

Lemmas 0, 2–6, 9, and 11 cover every fix, which proves Theorem 1. ∎

**Lemma 8 (removing a constant written view).** A's number of written views
goes down by one, and C(A) doesn't go up (the view's statements may become
dead), or A is removed. In each value operation B that executes A, the
execution's value from the view was constant and isn't a value any more,
and the simplification that follows adds no constant value (Lemma 0), so
C(B) goes down. A's and B's read views don't change, and every other value
operation is unchanged. So V doesn't go up (it goes down if A is
removed), and Φ goes down.

**Lemma 10 (removing a read view that doesn't matter).** A's number of read
views goes down by one, so V goes down. C(A) can go up, which is why V
comes before Φ. A's written view keeps its function over its remaining
views, so each value operation B that executes A computes the same
functions; B only loses statements left dead, and B's read views stay.
Every other value operation is unchanged.

**Lemma 12 (a match or spelling that would make a cycle).** The match or
spelling in A is fix 3 or 4, so A's measure goes down and its statements
don't grow when Φ stays (Theorem 1). Writing out an execution in R keeps
R's written and read views. It doesn't raise C(R): the execution's value
was R's value before, with the same function, and every copied value that's
constant is simplified away (Lemma 0), so the values left that are constant
were constant before. Every other value operation is unchanged. So Φ
doesn't go up. R comes after A in the priority order, as fix 8 says.

**Proof of Theorem 2.** A fix inside one value operation changes only that
one: fixes keep the functions of written views, so callers see the same
functions, and a caller's statement executing A is the same statement. A
simplification lowers C, so Φ. Any other fix keeps C or lowers it, and
keeps the number of written views, so it keeps Φ or lowers it; if it keeps
Φ, it kept C, and that value operation's measure went down (Theorem 1)
while the others didn't change. Lemma 8 covers removing a constant written
view, Lemma 10 removing a read view that doesn't matter, and Lemma 12 a
match or spelling that would make a cycle. ∎

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
- **Opposite values against matches, spellings, and opposite results.**
  An opposite-value fix turns an execution into a `not`, which can raise
  the negation counts of the statements that read it (Lemma 9), and a
  spelling can then lower them again. Neither undoes the other: the
  opposite value lowers K, and a spelling keeps S and K. An ordinary match
  or an opposite result can add an execution that's the opposite of a value
  the program has, whose fix then removes it again; the match lowered S,
  and the opposite value keeps or lowers it. The `not` an opposite result
  adds is the `not` of its own execution, so it's never an opposite value.
  The measure goes down at every one of these fixes, so no sequence of
  them repeats a program.
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

- **Order of fixes.** The only things assumed about DLP 57's order of
  reports are that a constant value is simplified before it could be
  matched or respelled, and that an opposite value is the first redundant
  value. Nothing assumes the largest match first, or the highest-precedence
  spelling for an ordinary fix. The opposite value only matters in that it
  isn't a `not` (fix 2).
- **Several fixes at once.** After one check, the fix loop applies every
  redundant value up to an opposite value that's already a `not`, and
  every match whose statements and arguments don't overlap a match chosen
  before it. Each is still a fix of the program the ones before it leave:
  fixes keep every function, a match's arguments survive and the
  statements it removes can only grow, and an opposite value it applies
  isn't a `not`. So a batch is a sequence of fixes, which the theorems
  cover.
- **Simplification's own steps.** Simplifying one constant is one fix here,
  through all the statements it reaches. The rule that a non-boolean
  statement takes the literal, and that a constant written view is left
  for fix 6, only matter in that they end the simplification.
- **The bound** is the number of canonical value operations with at most
  as many statements as each has once V, Φ, and the value operations before it
  stop changing, which is finite but huge. It says nothing about how many
  rounds fixing takes in practice (at most 92 in the experiments).

## Checked Against the Fix Loop

`measure_check.py` runs the Python fix loop of `gen/fixpoint.py`, which
handles one value operation at a time and simplifies constants the way fix 0
does, with DLP 59's rules (`strict` and `precedence`, both declared orders) on all 144
families of [precedence.md](../precedence.md) and computes the measure after
every fix, without C (statements, then statements that aren't a `not`,
then triples, then terms). These numbers are from before `and` and `not`
counted as registered and before dead statements and read views that
don't matter were errors; the check hasn't been run under those rules. Over 13,116 fixes (3,408 redundant values, 126
opposite values, 174 simplifications, 6,100 ordinary matches, 1,076
opposite results, and 2,232 spellings) it went down every time, so none of
those simplifications added a statement, and all 1,440 fix loops ended.

Without K, 42 of the 126 opposite values don't lower the measure: 70 of
them keep the number of statements, and in 40 of those, T goes up.

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
- **`progStep_lt`**: every fix of a program other than fix 8 lowers it,
  by V (`vsum`), then Φ (`phi`), then pointwise (Theorem 2).
- **`ProgFix`**: every fix, fix 8 included (`ProgFix.writeOut`, given a
  priority `rank`), with `progFix_vsum_le` (no fix raises V),
  `progFix_phi_le` (when V stays, no fix raises Φ), and `progFix_change`
  (when V and Φ stay, a value operation that changes is the
  one fixed, whose measure goes down and whose statements don't grow, or
  one before it in the priority order changed too).
- **`prog_terminates`**: there's no infinite sequence of fixes, if each
  value operation has finitely many states within any bound on its number
  of statements (the corollary, by induction along the priority order,
  with the counting fact as a hypothesis; see below). `stabilizes` is its
  step: a value operation whose states lie in a finite set and only go
  down stops changing.
- **`prog_no_cycle`**: no sequence of one or more fixes leads back to the
  program it started from, derived from `prog_terminates` by going round
  the cycle forever.

The lemmas match the English proof: `opFix_constCount_le` is the first part
of Lemma 0 and of what follows it (no fix raises C, and simplifying lowers
it), `tripleOf_subst` is Lemma 4's claim that other statements keep their
triples, `dm_single` is Lemma 5, `dm_pointwise` is Lemma 6's multiset step,
`spelling_measure` puts Lemmas 4–6 together, `ser_subst_le` is Lemma 7, with
`insertionSort_mono` and `arrange_mono` its step about sorting each group,
`dropView_phi_lt` and `dropView_vsum_le` are Lemma 8, `dropRead_vsum_lt`
is Lemma 10 (with `ProgStep.dropRead`, which lets C(A) go up),
`local_vsum_eq` is the claim that a fix inside one value operation keeps V, `OpFix.dead` is fix 5 (Lemma 11),
`opposite_measure` is Lemma 9, with `isNotTerm_subst_of_isNot` its claim
that no other statement stops being a `not`,
`progStep_size_le` is the claim that a fix that keeps V and Φ adds no
statement, `eventually_const` the step that finds when V and then Φ stop
going down,
`writeOut_weight_le` is Lemma 12's claim about Φ, and `DMLt`, `MeasureLt`, `OpLt`, `OptLt`, and
`ProgLt` are proved to be strict orders. `DMLt` is Mathlib's
`Multiset.IsDershowitzMannaLT`, whose transitivity Mathlib proves. Mathlib's
proof that it's well-founded needs a well-founded order on the elements,
which the rank order on all terms isn't (point 7 below), so it isn't used.

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
4. **Removing a constant written view, and a read view that doesn't
   matter, are given by their effects** (Lemmas 8 and 10): the value
   operation loses a written view (or is removed) and doesn't gain a
   constant value or a read view, or it loses a read view, with any
   constant values; each value operation that
   executes it keeps its written and read views, and has fewer constant
   values or no more; the others don't change. The call graph isn't
   modeled, and doesn't need to be. Fix 8 is given by its effects too
   (Lemma 12): a fix in A, and any new statements for R, which comes after
   A in the priority order, with the same views and no more constant
   values.
5. **Interchangeable groups are given by a label for each view**
   (`Signature.group`): views with the same label are one group, so any
   partition of an operation's views, consecutive or not, is covered.
   `arrange` sorts each group's codes among that group's views (`sortAt`,
   one group at a time), leaving every other view's code where it is, and
   `arrange_perm` and `arrange_mono` are the two facts the proof uses: it
   keeps the codes, and it keeps a position-by-position order.
6. **The rank order is the lexicographic order of codes** (`ser`): `[1, i]`
   for an input, and for a statement 2, its values' codes in view order
   (each group's codes sorted among its views), 0, and the operation. That this is DLP 58's rank
   order rests on codes being prefix-free (`ser_prefix_free`), so that
   comparing codes compares the values first, then a shorter list first,
   then the operation; the correspondence with DLP 58's wording is argued
   here, not formalized. A registered operation has one written view, so
   DLP 58's last tie (which written view) doesn't arise.
7. **The counting fact is a hypothesis.** `prog_terminates` assumes that
   the states each value operation takes in the sequence, within any bound
   on its number of statements, are finitely many. That's the counting
   argument of the corollary: finitely many inputs and operations, and
   every value an earlier one. The model alone doesn't give
   it: a spelling's new term can be any term, and the rank order on all
   terms isn't well-founded (for example `f(x₁, x₁) > f(x₀, f(x₁, x₁)) >
   f(x₀, f(x₀, f(x₁, x₁))) > …`).
8. **A spelling requires that no other statement has v's term**, and matches
   and spellings add only non-constant statements, both of which hold
   because DLP 57 reports redundant values, constant ones included, before
   matches. An opposite value requires that v isn't a `not`, which holds
   because DLP 57 reports the first redundant value.
9. **A statement has one value**, which is exact: DLP 57 makes writing more
   than one view an error for a boolean value operation, so no boolean
   statement is an execution with several values.
