# Fixing a Value Operation Always Terminates

DLP 60 adopts a precedence rule between spellings of a value, with the
restriction from [precedence.md](../precedence.md) that no fix grows the
program, and orders registered operations by a key computed from what they
compute. DLP 58 makes a value that's always the opposite of an earlier one
redundant, unless it's that value's `not`, and makes literals given to
boolean statements, values that never change, and written views that never
change errors that the programmer fixes, not the refactoring tool. This
proves that fixing a program, one reported error at a time, always ends.

## The Model

### Programs

Fix a finite set of **inputs** (the value operation's boolean inputs), the
primitive operations `and` (two views) and `not` (one view), and a finite
set of **registered operations**. DLP 60 makes `and` and `not` registered
for every value operation, before the others, so an `and` is an execution
of a registered operation like any other (it has a pair, below, and can be
respelled), and a match can be written with an `and` or a `not`; `not`
statements are still left out of the executions that are respelled. Each
registered operation R has an arity of at most four, a **key** key(R) (the
fewest `and`s in any and-inverter graph computing its function, then fewer
read views, then its truth table as a number; distinct operations have
distinct keys, and `and` and `not` come before every other), and a
partition of its views into **interchangeable groups**, which need not be
consecutive views: in `(a and b) or c` as one operation, a and b are one
group and c is another. `and` has one group of both views. Which
registered operations a value operation follows (a registered operation's
own definition follows `and`, `not`, and the ones with smaller keys) only
decides which fixes exist, which the proof never needs.

A value operation's boolean part is a list of **statements** s₁ … sₙ and a
list of **exits**: its written views, and the values its non-boolean
statements read. Each statement executes an operation on **values**: inputs
or earlier statements, never a literal. A statement's value is the
statement itself: DLP 58 makes a boolean value operation write exactly one
view, so an execution of one has one value. It's **canonical** when:

- every statement is read, directly or through other statements, by an
  exit (there are no **dead** statements), and
- the statements are in DLP 59's order, and every statement gives the
  values of each interchangeable group in rank order.

Every program is turned into a canonical one by **canonicalizing**: removing
dead statements and re-sorting. All programs the fixes see are canonical.

**Ranks** are DLP 59's. A value's **term** is its expression: an input is
itself, and a statement is its operation applied to the terms of the values
it reads, with each interchangeable group sorted by rank. The rank order <ᵣ
compares terms: inputs first, in a fixed order; a statement's term after
them; two statement terms by their argument terms, in order, as DLP 59
defines, with a shorter list first, and then by operation. It's a strict
total order on terms, by induction on their size. Terms don't depend on the
program, so values of different programs can be compared.

### Semantics

A set F of functions with decidable equality, containing the two constant
functions, a function for each input, and for each operation a map from its
views' functions to a function. A value's function follows by induction. A
value **never changes** when its function is one of the two constants. The
proof uses the semantics only through which values never change.

### The fixes

Let P be canonical. "Earlier than v" means before v in P's statement order.

1. **Redundant value.** A statement v whose function equals an input's or
   an earlier statement's, w. The fix replaces every read of v (by
   statements and exits) with w, then canonicalizes. (DLP 58 reports the
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
   with R′ of a′ having v's function, and spell(R′, a′) < spell(R, a). The
   fix replaces v's statement with an execution of R′ on a′ and
   canonicalizes. Here

   spell(R, a) = (neg(a), key(R), the terms of a in rank order),

   compared lexicographically, where neg(a) counts the values in a that are
   statements executing `not`.

5. **Dead statements.** Boolean statements whose values reach no exit
   (DLP 58 makes them an error). They're removed; every other statement
   stays as it is.

A value that never changes is an error, reported before matches, which the
fixes leave to the programmer: DLP 58 reports redundant values, those that
never change included, first, and a fix only applies while there's none. So
**the value of a match or a spelling never changes**. DLP 58 also reports
the first redundant value, so **the value of an opposite-value fix isn't a
`not`**: if v were `not x`, with x not w, then x and w would have the same
function, and since both come before v and inputs have different functions,
the later of x and w would be a redundant value before v. Those are the only
things the proof needs about the order of fixes. The second one matters: if
x and w are both read elsewhere, `not x` and `not w` are each an opposite
value of the other's argument, and fixing either one gives the other,
forever. Every fix keeps each statement's and each exit's function, and
since every new statement reads only values earlier than v, the result is a
program (no statement reads itself).

### Programs of value operations

A **program** is a set of value operations; a boolean statement can execute
another value operation, and DLP 9 forbids execution cycles, so the call
graph is acyclic. Besides the fixes above inside any one value operation,
there are two more:

6. **A read view that doesn't matter.** A read view of a boolean value
   operation A that A's written view doesn't depend on (DLP 58 makes it an
   error). Its reads in A are given the first read view A keeps that makes
   none of A's values one that never changes, and then the view is removed;
   when no kept read view will do, the fix doesn't apply and the error
   stays. A's written view doesn't depend on the removed view, so this
   keeps the written view's function; values that read it can compute
   something else, but none of them never changes. Every execution of A
   stops giving the view a value; a statement that only that value read is
   then dead, and it's removed (fix 5). Every execution of A computes what
   it did.
7. **A match or spelling that would make a cycle.** A match or a spelling
   (fixes 3 and 4) in a value operation A whose new execution is of a
   registered operation R whose definition executes A, directly or through
   other value operations. Executing R in A would make an execution cycle,
   which DLP 9 forbids, so first, in R's definition, the execution that
   leads back to A is written out: it's replaced by the executed
   operation's own statements, its views given the execution's values.
   That's repeated until nothing in R's definition leads back to A, which
   ends: each execution written out is replaced by executions of what it
   executed, lower in the acyclic call graph. Then the match or spelling in
   A is applied. R's written and read views and its function don't change,
   and neither does any other value operation's; R's statements can grow.
   It adds no match in R for R: a definition only follows the registered
   operations with smaller keys.

   R always comes after A in a fixed **priority** order: value operations
   that aren't registered first, then the registered ones from the largest
   key to the smallest. If A is registered, R is a registered operation A
   follows, with a smaller key; if A isn't, R is registered. Fixes 1–6
   keep the call graph acyclic, since the only new executions they add are
   of registered operations, so a program the fixes reach from one without
   cycles has none.

No fix changes a value operation's written views, so the program's written
views stay as they are.

## The Measure

### For one value operation

For the boolean part P of a value operation, let

- S(P) be its number of statements,
- K(P) be the number of its statements that aren't a `not`,
- T(P) be the multiset of (neg(a), key(R)) over its statements that
  execute a registered operation R on values a, and
- R(P) be the multiset of its statements' terms.

Order measures lexicographically: first S and K as numbers, then T in the
multiset order over lexicographically ordered pairs, then R in the multiset
order over <ᵣ. The multiset order (Dershowitz and Manna) puts M′ below M
when M′ ≠ M and M′ is M with some elements X removed and some elements Y
added, with every element of Y below some element of X. The multiset order
of a strict order is a strict order, so this lexicographic order is a
strict order.

**Theorem 1.** Every fix in a value operation takes P to P′ with a smaller
measure, and no more statements.

### For a program

For a program Π, let V(Π) be the number of read views over its value
operations. Order programs first by V, then **pointwise**: Π′ is below Π
when no value operation's measure went up (a removed value operation counts
as below every value operation), and one went down.

**Theorem 2.** No fix adds a read view, so none raises V, and removing a
read view that doesn't matter lowers it. Every other fix keeps V and
changes one value operation, whose measure goes down and whose statements
don't grow, except fix 7, which also changes R, after it in the priority
order, keeping R's views. Without fix 7, every fix lowers the program in
this order.

Fix 7 can make R bigger, so the program order doesn't go down at fix 7, and
the bound on each value operation's statements in the corollary doesn't
hold for R. The corollary is proved by the priority order instead.

**Corollary.** Fixing a program terminates. V is a number that never goes
up, so it goes down only finitely often, at every removed read view. After
the last time it goes down, every fix is a redundant value, an opposite
value, an ordinary match, a spelling, removing dead statements in one value
operation, or fix 7, and by induction along the priority order, every value
operation eventually stops changing:

- Once every value operation before B in the priority order has stopped
  changing, B can only change by a fix in B itself: fix 7 changes a value
  operation only together with one before it, which would change too. A
  fix in B lowers B's measure and adds no statement (Theorem 1), so B's
  statements stay within a bound. There are finitely many states of a
  value operation within that bound (the counting fact below), and the
  measure is a strict order, so B never returns to a state it left and
  changes only finitely often.

After all of them stop, no fix happens, but every fix changes something,
so the sequence ends. The counting fact: a value operation with at most a
given number of statements, over finitely many inputs and operations,
every value an earlier one, has finitely many states.

**When it ends, the program compiles**, if every error has a fix. They all
do except these, which the programmer has to fix: a literal given to a
boolean statement, a value or written view that never changes, a read view
that doesn't matter whose removal would make a value that never changes
(fix 6), an operation past DLP 58's limits as written (the fixes may pass
the statement limit on the way to a smaller operation, and the fix loop
checks past it), an execution cycle in the program as written (DLP 9; the
fixes never make one), a registered operation whose definition is a
wrapper (it can't be removed like another wrapper), and a fix 7 whose
execution leading back is of a mixed operation (`run`), which the fix loop
doesn't write out.

## Proof

**Lemma 0 (no fix makes a value that never changes, except fix 7).** A
redundant-value fix replaces v's reads with w, an earlier value with the
same function, and adds nothing. An opposite-value fix makes v `not w`, the
opposite of w's function, which changes because w's does. A match or a
spelling writes v's function with a new execution (and, for an opposite
result, a `not` of it), and v's function changes. Removing dead statements
adds nothing. Fix 6 chooses the view given to the removed view's reads so
that no value never changes. Removing a boolean value operation that only
names one of its views or wraps one statement gives each caller an
execution's function directly, so it keeps every function. Every other
statement keeps its function. Fix 7 can make one in R: a copied statement
is given R's values, which can make it one that never changes (`x and y`
given a value and its `not`), and R then has an error the fixes leave
alone; whether the tool should handle that is an open question. So outside fix 7, a program without
values that never change only reaches programs without them. The measure
doesn't count them either way: no fix's termination argument needs them.

**Lemma 1 (canonicalizing).** Re-sorting changes none of S, K, T, and R:
they're two counts and two multisets, and neither a statement's term nor
whether a value is a `not` depends on the order. Removing dead statements
removes elements from both multisets and lowers S.

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
only statement whose pair can change is v's: the others execute the same
operations on the same values, and whether each of those values is a `not`
is unchanged, because v is an execution before and after. Two cases:

**Lemma 5 (spelling, a better pair).** If v's new pair is below its old
one, T(P′) is T(P) with the old pair replaced by a smaller one, which is
smaller in the multiset order.

**Lemma 6 (spelling, the same pair).** Otherwise the pairs are equal,
since spell went down. Then key(R′) = key(R), so R′ = R, T(P′) = T(P), and
spell went down in its last part: the terms of a′ in rank order are
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
t′ ≤ᵣ t. By induction on t. If t is s, t′ = s′. If t is an input, t′ = t.
Otherwise t′'s arguments, before re-sorting, are each at most t's, by
induction. Sorting each group among its own views keeps that, position by
position, and leaves the other views alone: the k-th smallest of the new
group is at most the k-th smallest of the old one, because the k smallest
old elements became k elements that are each at most the k-th smallest old
element. Lexicographic comparison of two lists of the same length that are
position by position at most each other gives at most, and with the same
operation, t′ ≤ᵣ t.

In P′, a statement's term is built from the terms of the values it reads,
which are earlier, so by induction over P′'s order every statement's new
term is its old term with v's term replaced by a smaller one: Lemma 7
applies.

**Lemma 8 (opposite values).** S(P′) = S(P) − |D| + 1, where D is v's old
statement and those that became dead, so S(P′) ≤ S(P), and if anything else
became dead, S went down. Otherwise S(P′) = S(P). v's old statement isn't a
`not` and its new one is, and every other statement executes the same
operation as before (its values' terms may change), so K(P′) = K(P) − 1.

T can go up here, which is why K comes before it. After `u = a and b`,
turning `v = nand(a, b)` into `not u` makes `xor(v, c)` an `xor` given a
`not`, with pair (1, key(xor)), above both pairs it replaces, `nand`'s and
`xor`'s old one, whose negation counts are 0.

**Lemma 10 (dead statements).** At least one statement is removed and every
other is unchanged, so S(P′) ≤ S(P) − 1.

Lemmas 2–8 and 10 cover every fix, which proves Theorem 1. ∎

**Lemma 9 (removing a read view that doesn't matter).** A's number of read
views goes down by one, so V goes down. A's written view keeps its function
over its remaining views, so each value operation B that executes A
computes the same functions; B only loses statements left dead, and B's
read views stay. Every other value operation is unchanged.

**Lemma 11 (a match or spelling that would make a cycle).** The match or
spelling in A is fix 3 or 4, so A's measure goes down and its statements
don't grow (Theorem 1). Writing out an execution in R keeps R's written and
read views, so V stays. Every other value operation is unchanged. R comes
after A in the priority order, as fix 7 says.

**Proof of Theorem 2.** A fix inside one value operation changes only that
one: fixes keep the functions of written views, so callers see the same
functions, and a caller's statement executing A is the same statement. It
keeps the read views, so V, and that value operation's measure goes down
(Theorem 1) while the others don't change. Lemma 9 covers removing a read
view that doesn't matter, and Lemma 11 a match or spelling that would make
a cycle. ∎

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
  the negation counts of the statements that read it (Lemma 8), and a
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
  changes another value's pair (Lemma 4), because a spelling fix never
  turns a value into a `not` or out of one. That's why DLP 60's rule that
  only single executions are respelled matters: respelling a `not` of an
  execution as an execution would turn a `not` into an execution, adding a
  pair, and could make other values' negation counts go down while their
  terms go up.

## What This Covers and What It Doesn't

- **Order of fixes.** The only things assumed about DLP 58's order of
  reports are that no fix applies while a value never changes, and that an
  opposite value is the first redundant value. Nothing assumes the largest match first, or the highest-precedence
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
- **The bound** is the number of canonical value operations with at most
  as many statements as each has once V and the value operations before it
  stop changing, which is finite but huge. It says nothing about how many
  rounds fixing takes in practice (at most 92 in the experiments).

## Checked Against the Fix Loop

`measure_check.py` runs the Python fix loop of `gen/fixpoint.py`, which
handles one value operation at a time, with an earlier form of DLP 60's
precedence (declared orders, and AIG nodes in place of the key), on all 144
families of [precedence.md](../precedence.md), and computes the measure
after every fix (statements, then statements that aren't a `not`, then the
executions' negations and precedence, then terms). That loop also
simplifies values that never change, which the fix loop here leaves to the
programmer, and doesn't have `and` and `not` registered, dead statements,
or read views that don't matter. Over 13,116 fixes (3,408 redundant
values, 126 opposite values, 174 simplifications, 6,100 ordinary matches,
1,076 opposite results, and 2,232 spellings) the measure went down every
time, and all 1,440 fix loops ended; the check hasn't been run under the
present rules.

Without K, 42 of the 126 opposite values don't lower the measure: 70 of
them keep the number of statements, and in 40 of those, the negations
and precedence go up.

The Python loop also respelled a `not` of an execution as an execution
until this check; that isn't part of DLP 60, and it was removed.

## The Lean Proof

`fixing_termination.lean`, built and checked by the Bazel targets in
`BUILD.bazel` (`bazelisk test //boolean_equality_checking/proof:all`),
formalizes Theorems 1 and 2 and the corollary. It has no `sorry` or `admit`,
and the axiom test checks that its theorems use only `propext`,
`Classical.choice`, and `Quot.sound`:

- **`opFix_lt`**: every fix in a value operation lowers its measure
  (Theorem 1), and `opFix_length_le`: no fix adds a statement.
- **`progStep_lt`**: every fix of a program other than fix 7 lowers it,
  by V (`vsum`) and then pointwise (Theorem 2).
- **`ProgFix`**: every fix, fix 7 included (`ProgFix.writeOut`, given a
  priority `rank`), with `progFix_vsum_le` (no fix raises V) and
  `progFix_change` (when V stays, a value operation that changes is the
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

The lemmas match the English proof: `pairOf_subst` is Lemma 4's claim that
other statements keep their pairs, `dm_single` is Lemma 5, `dm_pointwise`
is Lemma 6's multiset step, `spelling_measure` puts Lemmas 4–6 together,
`ser_subst_le` is Lemma 7, with `insertionSort_mono` and `arrange_mono` its
step about sorting each group, `opposite_measure` is Lemma 8, with
`isNotTerm_subst_of_isNot` its claim that no other statement stops being a
`not`, `dropRead_vsum_lt` is Lemma 9 (with `ProgStep.dropRead`),
`OpFix.dead` is fix 5 (Lemma 10), `local_vsum_eq` is the claim that a fix
inside one value operation keeps V, `progStep_size_le` the claim that a fix
that keeps V adds no statement, `eventually_const` the step that finds when
V stops going down, and `DMLt`, `MeasureLt`, `OpLt`, `OptLt`, and `ProgLt`
are proved to be strict orders. `DMLt` is Mathlib's
`Multiset.IsDershowitzMannaLT`, whose transitivity Mathlib proves. Mathlib's
proof that it's well-founded needs a well-founded order on the elements,
which the rank order on all terms isn't (point 7 below), so it isn't used.

What the Lean model leaves out, or states differently:

1. **A value operation is its statements' terms**, a list of `Term`,
   rather than a graph in DLP 59's order. Re-sorting isn't modeled: the
   measure doesn't depend on the order (Lemma 1), and "earlier" only
   decides which fixes exist. Values that never change aren't modeled
   (Lemma 0): no part of the measure counts them.
2. **The semantics aren't modeled.** A fix is given by its shape: every
   statement that survives a fix is rewritten, because fixes keep
   functions. The conditions on functions that decide whether a fix exists
   only make there be fewer fixes, so the theorems hold for every fix of
   these shapes.
3. **Redundant values and ordinary matches are given by which statements
   survive** (rewritten) and which are added, with the restriction on
   ordinary matches as a count. A spelling fix is given in full: v's term
   becomes v''s, every other statement's term has v's replaced by v''s and
   its groups re-sorted, and some statements may become dead.
4. **Removing a read view that doesn't matter is given by its effects**
   (Lemma 9): the value operation loses a read view, with any statements;
   each value operation that executes it keeps its written and read views;
   the others don't change. The call graph isn't modeled, and doesn't need
   to be. Fix 7 is given by its effects too (Lemma 11): a fix in A, and any
   new statements for R, which comes after A in the priority order, with
   the same views. A registered operation's key enters only as its place in
   the order of keys (`Signature.key`), distinct for distinct operations.
5. **Interchangeable groups are given by a label for each view**
   (`Signature.group`): views with the same label are one group, so any
   partition of an operation's views, consecutive or not, is covered.
   `arrange` sorts each group's codes among that group's views (`sortAt`,
   one group at a time), leaving every other view's code where it is, and
   `arrange_perm` and `arrange_mono` are the two facts the proof uses: it
   keeps the codes, and it keeps a position-by-position order.
6. **The rank order is the lexicographic order of codes** (`ser`): `[1, i]`
   for an input, and for a statement 2, its values' codes in view order
   (each group's codes sorted among its views), 0, and the operation. That this is DLP 59's rank
   order rests on codes being prefix-free (`ser_prefix_free`), so that
   comparing codes compares the values first, then a shorter list first,
   then the operation; the correspondence with DLP 59's wording is argued
   here, not formalized. A registered operation has one written view, so
   DLP 59's last tie (which written view) doesn't arise.
7. **The counting fact is a hypothesis.** `prog_terminates` assumes that
   the states each value operation takes in the sequence, within any bound
   on its number of statements, are finitely many. That's the counting
   argument of the corollary: finitely many inputs and operations, and
   every value an earlier one. The model alone doesn't give
   it: a spelling's new term can be any term, and the rank order on all
   terms isn't well-founded (for example `f(x₁, x₁) > f(x₀, f(x₁, x₁)) >
   f(x₀, f(x₀, f(x₁, x₁))) > …`).
8. **A spelling requires that no other statement has v's term**, which holds
   because DLP 58 reports redundant values before matches. An opposite
   value requires that v isn't a `not`, which holds because DLP 58 reports
   the first redundant value.
9. **A statement has one value**, which is exact: DLP 58 makes writing more
   than one view an error for a boolean value operation, so no boolean
   statement is an execution with several values.
