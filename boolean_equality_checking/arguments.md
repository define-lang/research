# Arguments

These are the parts of the conclusions that come from reasoning rather than
from measurement. Each one says what it depends on. The measurements are in
[studies/experiments.md](studies/experiments.md) and [results/budget.md](results/budget.md).

## No Restriction Makes Exact Checking Polynomial

The task allows restrictions on how programs are written "as long as every
boolean function is still expressible without needing exponentially more code
than it would otherwise take." No such restriction can make exact equality
checking polynomial in the worst case, unless P = coNP.

The argument: deciding whether two AIGs compute the same function is
coNP-complete. Suppose a restriction R keeps every function expressible with
at most polynomially more code, and suppose the rewriting into R-form can be
done in polynomial time (DLP 59's statement order and argument order are of
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
   statements treated as inputs (which DLP 59 already does), then a large
   computation can always be split into several value operations, each small
   enough to check exactly. This keeps every function expressible with linear
   overhead, because it only changes where the boundaries go, but it weakens
   the guarantee: equalities across the boundaries aren't checked.
3. **Changing what "equal" means.** DLP 59's cut-based redundancy rule is
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

## Why a Heuristic Solver or Step Budget Can't Be the Language Rule—and Why Conservative Structural Limits Plus a Canonical ROBDD Limit Can

Run to completion, every exact method gives the same functional equivalence
classes, so which engine the compiler uses only affects compile time. A
heuristic budget changes that: with a SAT conflict limit, the pairs left
undecided depend on the solver's heuristics, its version, and the order of
queries. Likewise, an operational step counter depends on the exact
implementation of every data structure, cache, and search shortcut—any
compiler optimization changes step counts, and raising or changing internal
algorithms risks breaking Forward Compatibility or making compilation
unpredictable to programmers.

By contrast, four conservative structural limits paired with a **canonical shared ROBDD node limit** under a fixed, deterministic variable order (first-reached DFS over the value operation's static, finite DAG) avoid every one of those problems:

1. **Uniqueness and cross-compiler determinism:** a Reduced Ordered Binary
   Decision Diagram (with complement edges, uncomplemented `low` edge, and
   `low ≠ high`) is a mathematically unique representation of a DAG of boolean
   functions under a fixed variable order (Bryant 1986). Its reachable node
   count depends solely on the operation's DAG and input order, never on how a
   compiler builds, caches, or searches it.
2. **Forward Compatibility:** raising any of the four limits (`≤ 20` boolean
   input interface views, `≤ 256` boolean statements, `≤ 512` boolean inputs,
   `≤ 65,536` canonical shared ROBDD reachable nodes) in a future version of
   Define is strictly monotone—every program that compiled before still
   compiles.
3. **Guaranteed syntactic floor and bounded contracts:** capping Value
   Operations at **≤ 20 boolean input interface views** mathematically bounds
   every pure boolean Value Operation's exported contract to **≤ 128 KB**
   (truth table) and **≤ 98,302** ROBDD nodes, and bounds DLP 60 symmetry
   checking to at most 190 view pairs. Together with **≤ 256 boolean
   statements**, every pure boolean Value Operation fits unconditionally inside
   the truth-table floor and can never fail an ROBDD complexity check.
4. **Parallel-build memory and communicability:** capping mixed Value
   Operations and Actions with `21–512` boolean inputs at **65,536 (`2^16`)**
   reachable ROBDD nodes (with a 2× construction cap) bounds each parallel
   compiler worker to **~5–10 MB** of RAM while still covering **100% of
   standalone real-world functions** (376 / 376, max 3,500 nodes) and
   **99.72% of all 3,265 real-code units** even with `scope=2` inlining
   ([results/budget.md](results/budget.md)).

A solver conflict limit remains fine as an internal performance knob when an
exact fallback sits behind it (as in the legacy whole-program SAT-sweeping
ladder in [algorithm.md](algorithm.md)), because it changes only compile time
and never whether a program compiles.

## Why DLP 61 Uses a Fixed Standard Set Instead of Project Registration (`booleans.defcl`)

Restricting DLP 61 to the five fixed standard boolean operations (`and`, `not`,
`or`, `xor`, `equal`) instead of arbitrary user-registered operations in a
project-level `booleans.defcl` has four structural advantages:

1. **Strictly `O(S * (I + S))` match search with zero backtracking:** adversarial
   non-matching chains showed that arity-4 XOR-like operations (`par4`) time
   out (`> 15 s`) even at `S = 256, I = 513` (`O(S * N^3)`), and arity-3
   operations (`mux`, `maj`) scale as `O(S * N^2)` (`0.11 s` at `S = 256`,
   `4.72 s` at `S = 1,024`, timeout at `S = 2,048`). Because all five standard
   operations have arity ≤ 2 and are symmetric, match search drops to `O(S * N)`
   — **0.030 s** total (`11 ms` in `matches`) at `S = 256, I = 513`, and only
   `1.11 s` even at `S = 2,048, I = 4,097`.
2. **One global dialect across all Define projects:** every Define reader sees
   the exact same boolean vocabulary (`and`, `not`, `or`, `xor`, `equal`)
   without having to inspect a project's `booleans.defcl` or learn why one
   project forbids `or(not a, b)` in favor of `implies` while another doesn't.
3. **No conflict with DLP 60 factoring:** factoring `(a and b) or (a and c)` to
   `a and (b or c)` is straightforward when `mux` is not enforced; with `mux`
   registered, expressions like `mux(b, a, a and c)` compete directly with
   factored forms.
4. **Simpler compiler and incremental builds:** eliminating `booleans.defcl`
   removes NPN exact-synthesis tables, `booleans.defcl` validation/ordering,
   cycle-breaking between registered operations and user operations, and
   project-wide recheck invalidation when registration configs change.

## Modular Checking Over Define's Static Finite DAGs Is Enough for the Rule

Every compiled component of Define produces a static, finite DAG with no
execution cycles (DLP 9). DLP 59's rules are about the boolean statements of
one value operation, and they treat an execution of another boolean value
operation as a single statement whose function comes from its recorded
summary. The compiler checks each value operation once in topological
dependency order. A program executing a library operation a million times does
not make the operation's check any larger, and the DAG property also directly
guarantees that the refactoring fix loop visits only finitely many states per
value operation within any statement bound (proved in Lean as
`dag_prog_terminates` in [proof/fixing_termination.lean](proof/fixing_termination.lean)).

What the 256-statement limit doesn't bound is the size of the logic, because
an executed boolean value operation can compute any function of up to twenty
views. A value operation that executes multiplier blocks and small adders
within 256 statements over more than 20 inputs can still construct an
exponentially large ROBDD, which is why the 65,536-node canonical ROBDD
limit is needed past 20 inputs (while pure boolean value operations, capped at
20 boolean input interface views, always finish via truth tables).

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
ROBDD engine already decides 128-input parity in milliseconds, because parity
has a linear-size ROBDD in every order. The cases that stay hard, multipliers,
are hard with exclusive or too: their difficulty comes from the arithmetic,
and the practical answer to them in the literature is algebraic reasoning about
the arithmetic (Kaufmann, Biere, and Kauers, "Verifying Large Multipliers by
Combining SAT and Computer Algebra," FMCAD 2019, from memory), not a different
gate set. Majority or if-then-else primitives don't change any of the costs
measured here either: SAT sweeping, simulation, and OBDDs work the same way on
any gate set. So the measurements give no reason to change DLP 56's choice of
`and` and `not`. This part is argued from the parity and multiplier
measurements, not measured with an XOR-AND graph implementation.
