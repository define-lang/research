# Exact Matching Over Earlier Values

[matching.md](matching.md) found that an exact definition of "writing out a
registered operation" flags a large share of ordinary values, and called
them coincidences. The goal of DLP 58 is that there's only one way to write a
program, and under that goal they aren't coincidences: `(not x) and (not y)`,
where x and y are never both true, really is a second way of writing
`eq(x, y)`. This study takes that definition seriously:

> A value v is a **match** for a registered operation R when, for every
> combination of the value operation's inputs, v equals R(a₁, …, aₖ) for
> available values aᵢ that come before v, every aᵢ matters, and v isn't
> already an execution of R on them.

with DLP 58's other rules: opposite values count (a value whose `not` the
program computes can be given in its place), opposite results count (a
group computing `not R` is a match for R and a `not`, unless an operation
computing `not R` is registered), a match has at least two statements, and
an execution and a `not` of it are only a match for an operation computing
the opposite.

It asks two questions:

1. **Cost:** can a better search make this cost a few milliseconds per
   256-statement value operation, like the other checks?
2. **Convergence:** if equivalent programs are fixed the way the compiler's
   reports say, until they compile, do they reach the same program?

**Short answers.** The search can be made 15–40 times faster than the first
exact search, and on value operations that compile it costs 1.4–5.7 ms at
12–16 inputs and 8–18 ms at 20. Operations full of matches cost more, up to
0.1 s at 256 statements and 20 inputs, because every match is verified on
the whole truth table. Fixing does terminate, in at most 92 rounds here, but
equivalent programs almost never reach the same program, and no order of
fixes changes that: the programs they reach are different programs that
both compile.

The code is `Matcher::run_resub` in `src/match.hpp` (`beq match --how
resub`), the fix loop in `gen/fixpoint.py`, and the drivers
`resub_experiment.py` and `fixpoint_experiment.py`. The results are
`results/resub.jsonl` and `results/fixpoint.jsonl.gz`, summarized in
`results/fixpoint_tables.md` (`summarize.py resub` and `summarize.py
fixpoint`). Every check ran under a limit of 30 s and 4 GB, and every fix
loop under 30 s in all.

## The Size of a Match

DLP 58's cut definition counts a match's statements between its arguments
and its value. With arguments anywhere earlier in the program, many matches'
arguments aren't in the value's cone at all, and counting the cone made the
fixes cycle: `implies(a, b)` was a match for `not implies(c, d)` with the
same function and back again. Here a match's statements are the ones fixing
it removes: its value's, and every statement that nothing reads once the
value is computed from the arguments. A match needs two of them, so a single
statement is never a match, and an execution and a `not` of it are never an
opposite result of another operation (DLP 58's rule, applied to whatever
arguments). With those two rules, every fix loop here terminated.

## Cost

### The search

The first exact search tried values for each view of R in turn and checked
each candidate against sampled input assignments. The new one follows
Boolean resubstitution in logic synthesis, which looks for exactly this: a
node rewritten as a function of existing nodes, its divisors. ABC's `resub`
(Mishchenko and Brayton) keeps divisors in unate and binate lists and caps
them at a window (150 single and 500 pairs in `abcResub.c`); the
simulation-guided version (Lee, Riener, Mishchenko, Brayton, and De Micheli,
"Simulation-Guided Boolean Resubstitution," IWLS 2020, and TCAD 2022) filters
candidates by simulation signatures and refines the patterns with
counterexamples. A window would make the search inexact, so this one keeps
every earlier value and takes the rest:

1. **Every available literal's sample bits are also kept transposed**, as
   one bitset of literals per sampled input assignment. Given the views
   already chosen, the literals view j can take are found for all of them at
   once: and the bitsets of the assignments where R forces view j's value,
   and stop as soon as none are left.
2. **When the last view is forced on every sample**, as for `xor`, the
   candidates come from a hash of sample bits.
3. **For majority, the argument that differs least from v goes to the first
   view.** Wherever `maj(a, b, c)` = v, at most one argument differs from v,
   so that one differs on at most a third of the samples.
4. **A value is skipped when it can't have a match**: a match removes two
   statements, so v must read some statement that nothing else reads.
5. **Each candidate is verified on the full truth table** with the
   operation's own expression, and a difference adds its input assignment
   to the samples.

Every shortcut only removes candidates that can't match, so the result is
exact. With the shortcuts turned off (`--plain 1`), the matches are
identical on all 25 workloads. The first search missed about 1% of the
matches (all of them `mux`; three were checked independently in Python).

On the matching workloads of [matching.md](matching.md), which are close
to passing DLP 58's cut rule and so full of exact matches (best of three
runs; the first search one run):

| size | cuts | resub, median | resub, slowest | first exact search | matches | opposite results | values matched | values skipped |
| ---- | ---- | ------------- | -------------- | ------------------ | ------- | ---------------- | -------------- | -------------- |
| 8 inputs, 64 statements | 483 µs | 2.32 ms | 3.21 ms | 42.8 ms | 332 | 176 | 12 | 47 |
| 12 inputs, 64 statements | 376 µs | 1.57 ms | 2.61 ms | 35.6 ms | 169 | 54 | 9 | 49 |
| 12 inputs, 200 statements | 1.38 ms | 27 ms | 41.7 ms | 641 ms | 743 | 347 | 24 | 143 |
| 16 inputs, 256 statements | 2.36 ms | 44.3 ms | 57.8 ms | 1.5 s | 1130 | 586 | 29 | 190 |
| 20 inputs, 256 statements | 2.9 ms | 90.2 ms | 110 ms | 2.04 s | 708 | 372 | 26 | 188 |

"Matches" counts every match found, "values matched" the values that have
one, and "values skipped" the values step 4 skipped. The resub runs were
timed while a profiling run used another core.

### Value operations that compile

Each random program of 256 statements below was fixed until it compiled
(see Convergence). Checking it then costs:

| Inputs | Statements after fixing | Check of the result | Slowest check while fixing | All checks while fixing | Rounds |
| ------ | ----------------------- | ------------------- | -------------------------- | ----------------------- | ------ |
| 12     | 73–140                  | 1.4–5.7 ms          | 48–104 ms                  | 0.5–1.0 s               | 31–55  |
| 16     | 98–132                  | 2.2–5.1 ms          | 57–79 ms                   | 0.5–1.7 s               | 35–61  |
| 20     | 70–142                  | 8.3–18 ms           | 64–837 ms                  | 0.9–5.5 s               | 29–52  |

The fixed programs of the families below are smaller (median 10, 18, and 33
statements at 8, 12, and 16 inputs) and check in 38 µs, 98 µs, and 466 µs
in the median, 822 µs at most.

### How it grows with the number of inputs

The number of rounds doesn't grow with the number of inputs (29–61 at every
size). What grows is the
cost of each exact verification: a candidate is checked on the whole truth
table, 2^I/64 words, which is 16 times more at 20 inputs than at 16. That's
inherent to verifying on truth tables, and it's why a check at 20 inputs
costs 3–4 times as much as at 16 for a program that compiles (8–18 ms
against 2–5 ms), and up to 0.8 s for a program in the middle of being fixed,
with hundreds of matches. With a limit of 16 inputs every check here stays
within about 6 ms for a program that compiles and 0.1 s for one that
doesn't; with 20, within 18 ms and 0.84 s. Fixing a whole value operation
stays within 6 s either way. Verifying only the candidates that could be the
reported match (largest first, `--first_only 1`) gives the same report and
bounds the cost for programs that don't compile, but saves nothing on these
workloads, where the search dominates.

The 20-input loop first took 239 s, almost all of it in the Python fix
loop: it measured every candidate's size with a walk of the program. With
the sizes computed in `beq`, it takes 1.5–6.8 s.

Programs much larger than DLP 58's limit are a different matter: a random
program of 600 statements over 12 inputs has about 2 million matches, each
check takes 3 s, and fixing it didn't finish within 30 s.


## Convergence

### Families

`gen/fixpoint.py` generates a random base program of `and`, `not`, and the
registered operations, with no redundant values, and four variants that
compute the same written views, written differently by one kind of
rewrite:

- `expand`: registered operations written out with `and` and `not`, in one
  of several ways each.
- `demorgan`: `a and b` written as `not (not a or not b)`.
- `duplicate`: some values computed a second time.
- `reassociate`: `(a and b) and c` written as `a and (b and c)`.
- `distribute`: `a and (b or c)` written as `(a and b) or (a and c)`.
- `mixed`: all of them.

Eight families of each kind at 8, 12, and 16 inputs (16, 30, and 50 base
statements, up to 191 statements in a variant). Each program was fixed until
it compiled: the first redundant value replaced by the value it equals, or
by the `not` of the value it's always the opposite of (a constant one
simplified away), otherwise the reported match replaced by an
execution, then the program put back in DLP 58's statement and argument
order. The results were compared as text in that order. Three ways of
picking the match were tried: DLP 58's (largest, then earliest, then by
name and rank), earliest first, and smallest first.

### Termination

Every one of the 2,520 fix loops ended with a program that compiles: none
cycled, none reached the round limit, and the most rounds any took was 92
(median 1–60, depending on the kind and size). Termination isn't proved:
a match fix removes at least two statements and adds one, or two for an
opposite result, and the case that removes and adds two always leaves an
execution and its `not`, which can only be removed by a fix that adds one.
That suggests the number of statements and of such pairs together always
goes down, but there are cases this argument doesn't cover.

### Results

With DLP 58's order of fixes (the other orders, which differ little, are in `results/fixpoint_tables.md`):

| rewrites | inputs | policy | families that converge | distinct results per family | variants reaching the base's result | rounds, median / most | statuses |
| -------- | ------ | ------ | ---------------------- | --------------------------- | ----------------------------------- | --------------------- | -------- |
| demorgan | 8 | largest | 1/8 | 2.8 | 14/32 | 3 / 9 | ok 40 |
| demorgan | 8 | largest+plain | 0/8 | 2.8 | 13/32 | 4 / 14 | ok 40 |
| demorgan | 12 | largest | 0/8 | 4.1 | 4/32 | 6 / 16 | ok 40 |
| demorgan | 12 | largest+plain | 0/8 | 4.0 | 5/32 | 10 / 19 | ok 40 |
| demorgan | 16 | largest | 0/8 | 4.6 | 3/32 | 12 / 21 | ok 40 |
| demorgan | 16 | largest+plain | 0/8 | 4.8 | 2/32 | 17 / 35 | ok 40 |
| distribute | 8 | largest | 6/8 | 1.4 | 24/32 | 1 / 6 | ok 40 |
| distribute | 12 | largest | 5/8 | 1.6 | 23/32 | 4 / 6 | ok 40 |
| distribute | 16 | largest | 2/8 | 2.4 | 12/32 | 5 / 7 | ok 40 |
| duplicate | 8 | largest | 8/8 | 1.0 | 32/32 | 2 / 4 | ok 40 |
| duplicate | 12 | largest | 8/8 | 1.0 | 32/32 | 4 / 7 | ok 40 |
| duplicate | 16 | largest | 8/8 | 1.0 | 32/32 | 6 / 8 | ok 40 |
| expand | 8 | largest | 1/8 | 3.0 | 15/32 | 6 / 22 | ok 40 |
| expand | 8 | largest+plain | 1/8 | 2.8 | 15/32 | 7 / 25 | ok 40 |
| expand | 12 | largest | 0/8 | 4.6 | 2/32 | 16 / 32 | ok 40 |
| expand | 12 | largest+plain | 0/8 | 4.4 | 3/32 | 16 / 42 | ok 40 |
| expand | 16 | largest | 0/8 | 5.0 | 0/32 | 28 / 47 | ok 40 |
| expand | 16 | largest+plain | 0/8 | 4.9 | 1/32 | 33 / 63 | ok 40 |
| mixed | 8 | largest | 0/8 | 4.6 | 2/32 | 9 / 22 | ok 40 |
| mixed | 8 | largest+plain | 0/8 | 4.8 | 1/32 | 11 / 23 | ok 40 |
| mixed | 12 | largest | 0/8 | 5.0 | 0/32 | 19 / 32 | ok 40 |
| mixed | 12 | largest+plain | 0/8 | 5.0 | 0/32 | 24 / 43 | ok 40 |
| mixed | 16 | largest | 0/8 | 5.0 | 0/32 | 32 / 56 | ok 40 |
| mixed | 16 | largest+plain | 0/8 | 5.0 | 0/32 | 42 / 69 | ok 40 |
| reassociate | 8 | largest | 6/8 | 1.2 | 28/32 | 2 / 4 | ok 40 |
| reassociate | 12 | largest | 4/8 | 1.5 | 21/32 | 4 / 7 | ok 40 |
| reassociate | 16 | largest | 5/8 | 1.5 | 22/32 | 4 / 6 | ok 40 |

- **Values computed twice converge** every time, as the redundant-value rule
  promises.
- **Writing registered operations out doesn't converge**: with `expand`,
  1 of 8 families at 8 inputs and none at 12 or 16 reached one program; at
  16 inputs every variant reached a different program, and none reached the
  base's. With `demorgan` and `mixed` it's the same.
- **Reassociation and distribution mostly converge**, because the rewrites
  apply to few statements, but not always (4–6 of 8 families at most sizes).
- **The order of the fixes doesn't matter.** Earliest first and smallest
  first converge no more often than DLP 58's order (1/8, 1/8, and 2/8
  families with `expand` at 8 inputs).

### How the results differ

Of the variants whose result differs from the base's, about a third have as
many statements, and the rest differ by up to 4 (`expand`) or 9 (`mixed`)
statements. They use different registered operations for the same
functions, chosen by which values the program happens to have: a written-out
`or` that reaches `or(i3, not s2)` in one program reaches `implies(s2, i3)`
in another, because when `not s2` is read elsewhere, neither can be
rewritten into the other without removing two statements. Across all
`expand` variants, the results have 100 more `implies`, 51 more `maj`, and
20 more `mux` than the base's, and 167 fewer `or`.

A candidate rule for that, never giving a registered operation `not y` when
another registered operation computes the same thing from y, didn't help
either (0–1 of 8 families, `largest+plain` in the table).

So no order or tie rule can make these converge: the results are different
programs that compute the same thing and both compile, and an order only
picks among the fixes a program has. Making equivalent programs converge
would take rules that rewrite one compiling program into another, toward a
canonical form determined by the function. Canonical forms that are cheap
to compute, such as a sum of products or an algebraic normal form, can be
exponentially larger than the program, and the smallest program for a
function is a minimization problem that's hard in general, so that isn't a
rule the compiler could check either. This is argued, not measured.

## Recommendations

1. **If DLP 58 adopts the exact definition**, the search here is fast enough
   for value operations that compile (a few milliseconds at 16 inputs, tens
   at 20), with matches counted by the statements fixing them removes, which
   is also what makes the fixes terminate.
2. **It doesn't make there be one way to write a program.** It removes many
   second ways of writing a value from values the program has, but
   equivalent programs still end up as different programs that compile, and
   no order of fixes changes that.
3. **The input limit:** 16 inputs keeps every check within a few
   milliseconds; 20 costs 3–4 times more for a value operation that compiles
   and up to 0.8 s for one with hundreds of matches. Fixing a whole value
   operation takes seconds either way.

## What's Measured and What's Argued

Measured: everything in the tables, on generated programs. Argued: that the
fix loops always terminate, that no rule of fix order could make equivalent
programs converge, and that a canonical form isn't practical to require.
How common such divergence is in real programs is unknown.

