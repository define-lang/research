# Arguments

These are the parts of the conclusions that come from reasoning rather than
from measurement. Each one says what it depends on. The measurements are in
[experiments.md](experiments.md).

## No Restriction Makes Exact Checking Polynomial

The task allows restrictions on how programs are written "as long as every
boolean function is still expressible without needing exponentially more code
than it would otherwise take." No such restriction can make exact equality
checking polynomial in the worst case, unless P = coNP.

The argument: deciding whether two AIGs compute the same function is
coNP-complete. Suppose a restriction R keeps every function expressible with
at most polynomially more code, and suppose the rewriting into R-form can be
done in polynomial time (DLP 57's statement order and argument order are of
that kind: the compiler itself refactors programs into the required form). Then any two AIGs can be
rewritten into R-form in polynomial time, without changing their functions,
and an exact equality check on R-form programs decides the original question.
So equality checking on R-form programs is still coNP-hard.

This leaves three kinds of restriction that do bound the cost:

1. **Restrictions that give up succinctness.** A bound on width, on OBDD
   size in a fixed input order, or on the number of inputs, makes some
   functions need exponentially more code, or makes them impossible to write
   in one value operation (a multiplier's middle bit needs an OBDD of
   exponential size under every order, by Bryant, IEEE Transactions on
   Computers, 1991, from memory). The task rules these out as a general
   restriction, but they can be used as a limit on one value operation,
   because the programmer can split the logic across value operations that
   are opaque to each other (next point).
2. **Restrictions on what is compared.** If equality is only guaranteed
   within one value operation, with the outputs of other non-boolean
   statements treated as inputs (which DLP 57 already does), then a large
   computation can always be split into several value operations, each small
   enough to check exactly. This keeps every function expressible with linear
   overhead, because it only changes where the boundaries go, but it weakens
   the guarantee: equalities across the boundaries aren't checked.
3. **Changing what "equal" means.** DLP 57's cut-based redundancy rule is
   exact for a local definition (equal over a cut of at most four values),
   and it's cheap, but it doesn't find equalities that only show up over
   larger parts of the program. The measurements show how many it misses.

## Why Width Doesn't Bound the Work in Practice

The draft's bound is right: with inputs in first-use order, the OBDD has at
most 2^w nodes at each level when w values are live at each cut. But it only
helps if w is small, and in the generated value operations it's 17 to 74 for
256 statements and 32 to 133 for 1,024, because every comparison that's read
again later stays live from its first use to its last. A limit k that keeps
2^k small (k around 12 to 16) would send almost every realistic operation
above the limit. Meanwhile the OBDDs themselves are thousands to hundreds of
thousands of nodes, where the bound allows 2^40 or more per level. So width is a poor predictor
of OBDD size for this kind of logic, and it isn't needed to choose a method.

Width would be a good predictor for logic that reads each input once in a
long chain, which is the case the draft had in mind, but the generated code
reuses conditions the way real code plausibly does (a flag tested in several
places). Real Define code would have to be measured to know for sure.

## Why a Solver Budget Can't Be the Language Rule

Run to completion, every exact method gives the same classes, so which engine
the compiler uses only affects time. A budget changes that: with a conflict
limit, the pairs left undecided depend on the solver's heuristics, its
version, and the order of the queries. The measurements show the undecided
pairs appearing and disappearing as the limit changes. A language rule has
to give the same answer in every compiler, so a budget would have to name a
specific solver, version, and query order, which is not something a
specification can reasonably fix.

A budget is fine as a performance knob when something exact sits behind it.
That's what the portfolio does: the OBDD rescue starts after 1,000 conflicts
and SAT without a limit after that. Whether the rescue happens only changes
the time.

## Modular Checking Is Enough for the Rule

DLP 57's rules are about the statements of one value operation, and they
treat an execution of another value operation as one statement. So the
compiler checks each value operation once, with each executed boolean value
operation replaced by what it computes. A program executing a library
operation a million times doesn't make the operation's check any larger.
The total work is the sum over value operation definitions, and each one is
bounded by DLP 57's limit of 256 boolean statements.

What the 256-statement limit doesn't bound is the size of the logic, because
an executed boolean value operation can compute any function of up to twelve
views. A value operation that executes 6-by-6 multiplier blocks (twelve
inputs each) and small adders needs on the order of a hundred statements per
24-bit multiplication, so it can write two of them, with operands swapped,
within 256 statements. Their results are equal, and nothing measured here
decides that in reasonable time (this construction wasn't built; the 12-bit
multipliers already don't finish). So, within DLP
57's limits, exact checking of one value operation still has an exponential
worst case. The measured multipliers show where it starts.

## When the Hard Cases Arise

The hard cases in the measurements are bit-level arithmetic: multipliers,
adders, comparators built from bits. In Define, numbers have their own
logical operations (DLP 55), so a comparison like `x < 3` is a non-boolean
statement whose result is one input to the boolean logic. Bit-level
arithmetic only reaches the boolean logic when a program works on bit
vectors as booleans: hashing, checksums, bit fields, or cryptography. The
ordinary use of boolean values, conditions combining comparisons, is the
easy case for every exact method.

## Primitive Operations

Exclusive or as a primitive (an XOR-AND graph) would let structural
normalization treat a parity written in different orders as the same set of
values, so the parity workloads would need no solver at all. But the
portfolio already decides 128-input parity in 21 ms through the OBDD rescue,
because parity has a linear-size OBDD in every order. The cases that stay
hard, multipliers, are hard with exclusive or too: their difficulty comes
from the arithmetic, and the practical answer to them in the literature is
algebraic reasoning about the arithmetic (Kaufmann, Biere, and Kauers,
"Verifying Large Multipliers by Combining SAT and Computer Algebra," FMCAD
2019, from memory), not a different gate set. Majority or if-then-else
primitives don't change any of the costs measured here either: SAT sweeping,
simulation, and OBDDs work the same way on any gate set. So the measurements
give no reason to change DLP 56's choice of `and` and `not`. This part is
argued from the parity and multiplier measurements, not measured with an
XOR-AND graph implementation.
