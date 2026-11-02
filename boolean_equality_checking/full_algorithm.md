# The Full Algorithm on Whole Programs

The earlier studies measured each rule of DLPs 57–59 on its own, on
workloads that were simpler than Define programs in several ways. This study
first makes the workloads and tools follow the rules as they now stand,
then runs every check together on whole generated programs: order
(including which views are interchangeable), redundant values with
opposites, literals, dead statements, read views that don't matter,
matches, spellings (with `and` and `not` registered for every value
operation), wrappers, and execution cycles, with executions as references,
stored patterns, and incremental rechecking.

The code is `gen/program.py` (programs, and their text format, which its
docstring defines along with every rule), `src/program.hpp` (the checks),
`src/program_fix.hpp` (the fixes), `src/program_main.hpp` (`beq program`),
`gen/program_check.py` (an independent implementation of every rule), and
`full_algorithm_experiment.py`. The results are in
`results/full_algorithm.jsonl`, summarized by `summarize.py
full-algorithm`.

## Results

Three programs: about 15,000 and 150,000 value operations of up to 10
boolean inputs (a fifth of them mixed), and about 2,000 of 16–20 inputs.
Every step ran under a cap, one at a time on an otherwise busy machine:
60 s for each compiler step, 300 s for the fix loop (including its check
of the program it writes), 120 s for generating a program and for the
independent checker, 4 GB for `beq` (8 GB for the tools), and 20 minutes
for a whole run. Generating took 7.2 s, 83.7 s, and 74.3 s. Every step
uses the current `beq`, and the check is truth tables up to 20 inputs
(`auto`, DLP 57's limit), so there's no SAT in any row.

#### The programs, fixed until they compile

| program | operations | boolean | boolean statements | executions of user operations | copies | operations before fixing | rounds, median / most | fixing | memory | fixes | statuses |
| ------- | ---------- | ------- | ------------------ | ----------------------------- | ------ | ------------------------ | --------------------- | ------ | ------ | ----- | -------- |
| ops_15k | 14,770 | 11,770 | 150,507 | 18,281 | 7,066 | 15,006 | 2 / 17 | 15.5 s | 165 MB | constant 199, dead 158, match 33,449, opposite match 7,673, opposite value 474, redundant 5,496, spelling 11,547, unused view 190, wrapper 111 | ok 15,006 |
| ops_150k | 147,685 | 117,685 | 1,519,207 | 186,564 | 70,248 | 150,006 | 2 / 21 | 159 s | 1.59 GB | constant 2,227, dead 2,129, literal 2, match 335,647, opposite match 76,498, opposite value 4,748, redundant 56,932, spelling 119,472, unused view 1,774, wrapper 1,140 | ok 150,006 |
| ops_2k_wide | 1,978 | 1,578 | 81,781 | 11,454 | 3,101 | 2,006 | 7 / 42 | 54.9 s | 428 MB | constant 22, dead 3, match 4,799, opposite match 625, opposite value 16, redundant 1,033, spelling 12,406, unused view 28, wrapper 7 | ok 2,006 |

#### Checking every operation

| program | run | wall | structure | tables | groups | order | redundant | matches | spellings | per operation, median | 99th percentile | slowest | truth tables / SAT | memory | operations with errors |
| ------- | --- | ---- | --------- | ------ | ------ | ----- | --------- | ------- | --------- | --------------------- | --------------- | ------- | ------------------ | ------ | ---------------------- |
| ops_15k | first | 1.85 s | 48.2 ms | 61.6 ms | 3.18 ms | 35.1 ms | 17 ms | 855 ms | 565 ms | 84 µs | 394 µs | 701 µs | 14,770 / 0 | 82.1 MB | 0 |
| ops_150k | first | 18.6 s | 479 ms | 733 ms | 31.8 ms | 360 ms | 176 ms | 8.53 s | 5.65 s | 83.6 µs | 396 µs | 8.18 ms | 147,685 / 0 | 782 MB | 0 |
| ops_2k_wide | first | 19.9 s | 45.8 ms | 13.1 s | 99.2 ms | 56.4 ms | 1.56 s | 2.7 s | 2.2 s | 4.98 ms | 66.1 ms | 106 ms | 1,978 / 0 | 229 MB | 0 |

#### Checking again

| program | change | time | operations checked | slowest edit | most checked |
| ------- | ------ | ---- | ------------------ | ------------ | ------------ |
| ops_15k | unchanged, by hashes | 24.9 ms | 0 |  |  |
| ops_15k | 200 random edits | 116 µs median | 1 median | 3.79 ms | 22 |
| ops_15k | booleans.defcl: swap or implies | 579 ms | 14,770 |  | 448 with errors |
| ops_15k | booleans.defcl: register b0_797 | 2.12 s | 14,770 |  | 1,917 with errors |
| ops_150k | unchanged, by hashes | 264 ms | 0 |  |  |
| ops_150k | 200 random edits | 115 µs median | 1 median | 3.33 ms | 16 |
| ops_150k | booleans.defcl: swap or implies | 5.9 s | 147,685 |  | 4,499 with errors |
| ops_150k | booleans.defcl: register b0_7743 | 11 s | 147,685 |  | 17,580 with errors |
| ops_2k_wide | unchanged, by hashes | 14.7 ms | 0 |  |  |
| ops_2k_wide | 200 random edits | 7.12 ms median | 1 median | 2.24 s | 138 |
| ops_2k_wide | booleans.defcl: swap or implies | 16.7 s | 1,978 |  | 196 with errors |

#### Time per operation by boolean inputs (first check)

| program | inputs | operations | mean | slowest |
| ------- | ------ | ---------- | ---- | ------- |
| ops_15k | 1 | 87 | 17 µs | 22.1 µs |
| ops_15k | 2 | 257 | 38.3 µs | 103 µs |
| ops_15k | 3 | 2,344 | 39.5 µs | 129 µs |
| ops_15k | 4 | 2,518 | 69.4 µs | 304 µs |
| ops_15k | 5 | 2,544 | 99 µs | 430 µs |
| ops_15k | 6 | 2,529 | 123 µs | 511 µs |
| ops_15k | 7 | 2,225 | 152 µs | 546 µs |
| ops_15k | 8 | 2,210 | 180 µs | 701 µs |
| ops_15k | 9 | 48 | 90.5 µs | 254 µs |
| ops_15k | 10 | 8 | 89 µs | 140 µs |
| ops_150k | 1 | 1,025 | 16.4 µs | 34.6 µs |
| ops_150k | 2 | 2,580 | 37.5 µs | 130 µs |
| ops_150k | 3 | 23,045 | 38.9 µs | 1.75 ms |
| ops_150k | 4 | 25,180 | 69 µs | 671 µs |
| ops_150k | 5 | 25,764 | 98.5 µs | 4.34 ms |
| ops_150k | 6 | 24,623 | 126 µs | 3.82 ms |
| ops_150k | 7 | 23,087 | 153 µs | 3.7 ms |
| ops_150k | 8 | 21,792 | 183 µs | 8.18 ms |
| ops_150k | 9 | 508 | 97 µs | 721 µs |
| ops_150k | 10 | 81 | 106 µs | 245 µs |
| ops_2k_wide | 2 | 4 | 35 µs | 56.6 µs |
| ops_2k_wide | 3 | 2 | 34.9 µs | 35.2 µs |
| ops_2k_wide | 10 | 10 | 356 µs | 648 µs |
| ops_2k_wide | 11 | 20 | 377 µs | 844 µs |
| ops_2k_wide | 12 | 39 | 370 µs | 765 µs |
| ops_2k_wide | 13 | 49 | 502 µs | 1.08 ms |
| ops_2k_wide | 14 | 50 | 622 µs | 1.44 ms |
| ops_2k_wide | 15 | 52 | 1.13 ms | 2.63 ms |
| ops_2k_wide | 16 | 374 | 2.52 ms | 7.24 ms |
| ops_2k_wide | 17 | 386 | 4.28 ms | 14.4 ms |
| ops_2k_wide | 18 | 349 | 8.09 ms | 26.6 ms |
| ops_2k_wide | 19 | 325 | 15.5 ms | 49.5 ms |
| ops_2k_wide | 20 | 318 | 28.9 ms | 106 ms |

#### The slowest operations (first check)

| program | operation | inputs | statements | redundant values by | total | checks taking 10% or more | match search nodes |
| ------- | --------- | ------ | ---------- | ------------------- | ----- | ------------------------- | ------------------ |
| ops_15k | b5_150 | 8 | 35 | tt | 701 µs | matches 537 µs, spellings 130 µs | 5,434 |
| ops_15k | b4_448 | 8 | 38 | tt | 625 µs | matches 374 µs, spellings 195 µs | 3,606 |
| ops_15k | b3_528 | 8 | 37 | tt | 608 µs | matches 368 µs, spellings 190 µs | 3,692 |
| ops_15k | b4_347 | 8 | 36 | tt | 596 µs | matches 336 µs, spellings 224 µs | 3,123 |
| ops_15k | b8_423 | 8 | 31 | tt | 579 µs | matches 351 µs, spellings 171 µs | 3,124 |
| ops_150k | m6_1620 | 8 | 2 | tt | 8.18 ms | tables 8.14 ms | 0 |
| ops_150k | b3_5226 | 5 | 6 | tt | 4.34 ms | tables 4.27 ms | 231 |
| ops_150k | b5_6448 | 8 | 30 | tt | 4.19 ms | spellings 3.93 ms | 2,243 |
| ops_150k | b1_7325 | 6 | 15 | tt | 3.82 ms | spellings 3.72 ms | 737 |
| ops_150k | m0_1105 | 7 | 17 | tt | 3.7 ms | matches 3.62 ms | 741 |
| ops_2k_wide | b4_307 | 20 | 75 | tt | 106 ms | tables 90.9 ms | 5,304 |
| ops_2k_wide | b4_285 | 20 | 68 | tt | 98.6 ms | tables 86.9 ms | 3,431 |
| ops_2k_wide | b4_28 | 20 | 70 | tt | 91 ms | tables 77.6 ms | 10,327 |
| ops_2k_wide | b3_313 | 20 | 69 | tt | 90.3 ms | tables 55.4 ms, spellings 26.1 ms | 6,829 |
| ops_2k_wide | b4_300 | 20 | 56 | tt | 81.1 ms | tables 71.1 ms | 4,710 |

ops_15k: the independent checker checked 1,200 operations (300 sampled and what they execute) in 53.4 s; 0 fail it, 0 fail `beq`.

ops_150k: the independent checker checked 1,200 operations (300 sampled and what they execute) in 55.5 s; 0 fail it, 0 fail `beq`.

- **Checking is linear in the program.** The full check takes 1.85 s for
  15k operations and 18.6 s for 150k (10×, for 10× the statements), 84 µs
  per operation in the median at both sizes, with the same 99th percentile
  (about 395 µs). Matches take 46% and spellings 30%. The few operations
  at 4–8 ms at 150k are single outliers, not a heavier tail.
- **The fix loop is linear too:** 1.03 ms per operation at 15k (15.5 s for
  15,006) and 1.06 ms at 150k (159 s for 150,006), in a median of 2 rounds
  and at most 21, and every fixed program compiles when read back (0
  operations with errors; the check of the written program takes 1.9 s,
  18.9 s, and 19.9 s, inside the fix step's cap). It adds no value
  operation, and removes wrappers and operations that only name a
  constant or a view (about 1.5%).
- **Rechecking an unchanged program costs only hashing:** 25 ms at 15k
  and 264 ms at 150k (10.6×); nothing is checked.
- **Random edits** check the edited operation and, when its written view's
  function or interchangeable views change, every operation that executes
  it: a median of 0.12 ms and one operation at 15k and 150k, at most 16–22
  operations. In the wide program one edit cascades to 138 operations
  (2.2 s).
- **An edit to booleans.defcl** checks every operation again, but only for
  matches and spellings of the registered operations it added or moved:
  5.9 s at 150k for swapping two, and 11 s for registering a new one,
  against 18.6 s for a full check.

### The wide program

With 16–20 inputs, the time is in truth tables: 13.1 s of a 19.9 s check
(66%), of which 9.8 s is executions of operations too big to write out,
looked up minterm by minterm in their recorded tables, and 3.0 s
executions that are written out (at most 16 nodes per view). Matches take
2.7 s, spellings 2.2 s, and redundant values 1.6 s. An execution of a
k-view operation in a caller with I inputs costs 2^I lookups of k bits
each, about 20 million bit operations at 20 inputs. The fix loop takes
54.9 s for 2,006 operations (median 7 rounds, at most 42) and the check of
what it writes 20 s.

Earlier runs checked redundant values with SAT above 12 inputs. With no
stored patterns that took 69 s uncapped, against 1.5 s with truth tables,
and matching needs every value's truth table anyway, so SAT saved only the
grouping of tables by function. The compiler's default now uses truth
tables up to 20 inputs, and SAT only past them, where DLP 57's limit
makes an operation an error anyway. The truth tables of every value
aren't stored for a recheck (about 9 MB per operation here); each
operation's recorded table is, and an unchanged operation isn't checked.

## Where Fixing Spends Its Time

`beq program --mode fix` reports the seconds spent in each part of fixing
(`phase_s`, `check_t`, `write_s`, and `ands_s` in its summary). On a quiet
machine:

| part | ops_15k | ops_150k | ops_2k_wide |
| ---- | ------- | -------- | ----------- |
| fixing, in all | 15.5 s | 159 s | 54.9 s |
| checks | 14.2 s (91%) | 144 s (91%) | 53.6 s (98%) |
| of which the match search | 9.5 s | 96.3 s | 18.0 s |
| of which the spelling search | 1.4 s | 14.8 s | 11.4 s |
| of which truth tables | 0.28 s | 3.2 s | 17.9 s (10.9 s lookups, 3.5 s written out) |
| of which redundant values, order, structure, groups | 0.57 s | 5.7 s | 4.9 s |
| of which the rest of a check (reading the operation, recording it) | 2.4 s | 24 s | 1.4 s |
| canonicalizing | 0.64 s (4%) | 6.8 s (4%) | 1.1 s (2%) |
| choosing and applying matches | 0.30 s (2%) | 3.0 s (2%) | 0.05 s |
| replacements, write-outs, settling, finishing | 0.13 s | 2.0 s | 0.05 s |
| counting registered operations' `and`s | 0 | 0 | 0 |
| checks, and checks per operation | 57,944, 3.9 | 584,157, 3.9 | 18,339, 9.1 |
| reading / writing the program | 0.13 / 0.04 s | 1.1 / 0.42 s | 0.04 / 0.02 s |
| checking the written program | 1.8 s | 18.4 s | 20.0 s |

Choosing each match's spelling analyzes the operation once per round, not
once per comparison, and a check in the fix loop skips the searches whose
results that round can't use: spellings when there's a match, and both
when there's a literal or a read view that doesn't matter.

**The checks are the time, and within them the match and spelling
searches**, not equality: a check in the fix loop costs about 250 µs at
15k and 150k, three times a check of the fixed program (84 µs), because
an operation with errors has many more matches to find and verify (every
one, so that the non-overlapping ones can be applied together), and an
operation takes about four checks. The slowest operations are the same:
b2_56 in the wide program takes 0.46 s, all of it checks (tables 0.11 s,
matches 0.12 s, spellings 0.19 s); the slowest in the 150k program, m6_223,
takes 10 ms, 8 ms of it the match search.

**Other ways of deciding equality wouldn't help.** The search enumerates
candidate arguments for each value and filters them by their values on
random input combinations (simulation, already), then confirms the few
left against the truth tables; the exact confirmations were about 2% of
the 15k fix in a profile (`perf`). SAT or OBDDs would only replace those confirmations, a word or
16 words compared at up to 10 inputs, with much slower ones, and for the
wide program SAT was measured slower than truth tables (above). What would
cut the time is fewer or smaller searches: a search after a fix that
reuses the previous round's matches for the values the fix didn't touch,
which needs care, since a fix changes which values come before others and
what a match removes.

## What Changed to Match Define

1. **One written view.** `gen/hierarchy.py` made operations that write one or
   two views. DLP 57 now allows exactly one for a boolean value operation, so
   it writes one. The new programs follow the same rule: a boolean value
   operation writes one view, and only mixed operations (below) write several.
2. **Programs that compile follow every rule.** A program counted as
   compiling only had no redundant values before. Here a program is
   generated as a programmer might first write it, then fixed until it
   compiles (`beq program --mode fix`), and checked again as written. The
   fixes are DLP 57's refactoring steps, DLP 58's order, and DLP 59's
   matches (with the restriction that no fix grows the program), first
   spellings, and wrappers. An independent checker (`gen/program_check.py`),
   which shares no code with `beq`, confirms the result (Verification,
   below).
3. **Mixed value operations.** About a fifth of each program's operations
   aren't purely boolean: comparisons (`cmp`) turn numeric views into
   boolean inputs, numeric statements (`num`) read boolean values, and
   operations execute other mixed operations (`run`), whose boolean written
   views are boolean inputs of the caller. Statement order follows DLP 58:
   before each statement that isn't boolean come the boolean statements it
   needs, in view order, and the written views' come last.
4. **Matching through references.** Operations execute user-defined boolean
   value operations (11% of boolean statements), not only registered ones.
   Each execution is one statement whose function is looked up in the
   executed operation's recorded table, as "Executions are whole" says: it
   counts as one statement removed, and nothing inside it is a value or an
   argument. The matcher (`src/match.hpp`) takes the tables directly instead
   of computing them from an and-inverter graph. The independent checker
   computes the same functions by copying every executed operation's
   statements instead, so the two agree only if referring is exact.
5. **Interchangeable views.** Every boolean value operation's views are
   split into groups by one equality check per pair of read views, on its
   recorded table, a word at a time; groups can be mixed and needn't be
   consecutive, like `{a, b}` in `(a and b) or c`. Argument order, the fix
   loop's sorting, and the matcher's symmetry all use these groups, and the
   Lean proof now covers them (`Signature.group` and `sortAt` in
   `proof/fixing_termination.lean`; `proof/termination.md`).
6. **View Setting copies.** Wherever an execution is given one value twice,
   the program gives it through a copy right before the execution (DLP 55),
   and every rule reads the copy as its source.
7. **The older results** came from `beq` before the redundancy count
   included opposites (636ad0b). Nothing older is rerun; every result here
   uses the current `beq`.
8. **Constants.** The fix loop simplifies a constant the way DLP 57's
   refactoring steps 1 and 3 do: a literal given to a boolean statement is a
   constant; `x and false` is false, `x and true` is x, the `not` of a
   constant is the other one, and an execution given a constant computes
   what the executed operation computes with it, written as a constant, one
   of its other values or its `not`, an `and` of two of them (either
   negated), an execution of a registered operation it follows (or its
   `not`), or otherwise the executed operation's statements written out in
   place with the constant, which simplifying then shrinks. Writing out
   can pass DLP 57's limit of 256 statements on the way, so the fix loop
   checks past it; an operation written past it stays an error. A statement that
   isn't boolean keeps the literal. Step 4 is new: a boolean value operation
   whose written view is constant is removed, and so is one that only names
   one of its views or wraps one statement, and each caller gets the
   constant, the argument, or the wrapped statement; a mixed operation's
   constant boolean written view is removed and its callers' values from it
   become constants, which they simplify in turn. The Python fix loop of
   `gen/fixpoint.py` matches steps 1 and 3 for the operations it handles
   (it never has literals or user executions), but stops with "constant
   output" where step 4 removes the view.
9. **Dead statements and read views that don't matter** are errors (DLP
   57). The fix loop removes dead statements, and removes a read view that
   doesn't matter from the operation and from every execution of it, which
   can leave statements dead in the callers. Its reads in the operation get
   another read view the operation keeps: the written view doesn't depend
   on it, so any value will do, and a constant would make every execution
   that reads it an execution given a constant, written out with
   everything it executes. Giving them `false` turns one view in a
   60-statement operation of the wide program into 914 statements and
   about 100 more rounds, and the wide program's fix past its 300 s cap.
10. **`and` and `not` are registered** for every value operation, before
    the others, so matches can be `and`s and `not`s and every `and` is a
    spelling; and a registered operation's own definition follows only
    `and`, `not`, and the ones listed before it (DLP 59).
11. **Execution cycles.** DLP 9 forbids them, and both checkers report one
    at each execution that leads back. A match or spelling can make one:
    with `maj` defined as `U(a, b, c, or(a, b))` and `U` written out as
    majority `and t`, `U` is a match for `maj`, whose definition executes
    `U`. So before such a fix, the fix loop writes out the executions in
    the registered operation's definition that lead back (`maj` gets `U`'s
    statements, and `m and or(a, b)` is then redundant with `m`), and
    then makes `U` `maj(a, b, c) and t`. Rewriting a registered definition
    changes what writing it out costs, and so every operation's spellings,
    so the fix loop fixes the registered operations and everything they
    execute first, until they compile, and the rest after. The proof
    covers this order (fix 8 in `proof/termination.md`).
12. **The generator.** Random statements often leave a read view that
    doesn't matter (`(x and y) or y`): 1,042 of the wide program's 2,006
    operations have one when nothing prevents it, where a real program
    would rarely. The generator makes the written view the `xor` of
    itself with each such view (`gen/program.py`, `unused_views`), which
    leaves 28. Past 12 inputs it
    tracks each value's function on 4,096 fixed random input combinations
    instead of all 2^20, since every statement is bitwise and equal
    functions are equal on the samples: generating the wide program takes
    74 s, against over 120 s with whole truth tables. And a mixed
    operation's boolean written view is made constant on purpose at the
    boolean rate (1%).
13. **Fewer checks per fix.** After one check, the fix loop fixes every
    redundant value, up to an opposite value that's already a `not`, and
    every match, largest first, whose statements and arguments don't
    overlap one already chosen, rather than one per check (each is still a
    fix after the others, which keep every function), and, while it works on one
    operation, keeps each execution's table, the matcher's exact checks,
    and table hashes by value, since a value keeps its function from one
    fix to the next, and the matcher filters candidates a candidate at a
    time or a sample position at a time, whichever is fewer words. All of
    these leave the fixed programs byte for byte the same; fixing several
    at once is what keeps the most rounds at 17 on the 15k program.

## Verification

Two independent checks agree with `beq` everywhere they were run:

- **The independent checker** computes every function by copying executed
  operations' statements, finds matches and spellings by trying every tuple
  of arguments, and builds DLP 58's order, ranks, and groups from the
  definitions. Under the current rules, over its self-tests, 20 random
  programs and 10 with booleans.defcl reordered (`eq xor mux maj or
  implies`, so registered definitions execute ones listed after them and
  the fix loop has to write them out), each raw and fixed, and the maj/U
  and literal cases, its reports and `beq`'s agree on all 1,876 operations
  compared, rule by rule and detail by detail, and every fixed program
  compiles. (Before these rules, 8,056 operations over 84 files agreed.)
  On the fixed whole programs, a sample of each compiles under both:
  up to 300 operations chosen at random, each with everything it
  executes, while that stays within 1,200 operations (the independent
  checker's time is about linear in what it checks). An operation whose
  dependencies would pass that is skipped, which favors the shallow
  levels, but every level is in the sample: on the 150k program, 76 of
  the 300 are at level 0 and 5 at level 11, and 29,437 were skipped.
  The 15k program's sample took 53.4 s and the 150k program's 55.5 s;
  0 operations fail either checker.
- **The wide program** isn't sampled: its operations read more inputs
  than the independent checker handles in time. Earlier runs checked it by
  comparing truth tables with SAT sweeping; with truth tables the check
  up to 20 inputs (below), that cross-check is gone. Truth tables are
  exact, so the independent checker on the other programs' samples is the
  cross-check that matters.

Comparing them found these bugs in `beq`, all fixed before any result here:

1. **The matcher missed matches** (`src/match.hpp`). When a view's value is
   forced on every sample, candidates are the values with exactly the
   target's sample bits; if one of them failed the full check, it added a
   sample, and the rest of that bucket were then compared with bits that
   didn't have it, so a match among them was skipped. That's the one
   operation the independent checker failed in the first 15k run
   (`b2_114`: `b1_30(31, 14, 28)` is `eq(14, 28)`, two statements). Now
   only the samples the bits came from are compared. The earlier studies'
   `beq match --how resub` had the same bug; it only matters when two
   candidates share sample bits and the first fails, and nothing earlier
   was rerun.
2. **The sole-reader shortcut** skipped a value given one argument twice
   (through a copy), whose statement then counted as read twice.
3. **A literal given to a statement** entered the matcher's values as
   constant false or true.
4. **The fix loop** removed the wrong written view of a mixed operation when
   it rewrote a caller twice, so the program it wrote couldn't be read back.
   Fixing now ends by reading the written program back and checking it.
5. **An execution given a literal** (`mux(a, T, b)`) was taken as a
   spelling to compare, which crashed both checkers on the 150k program.
   It's DLP 57's literal error, not a spelling, in both now.
6. **The fix loop's count of a registered operation's `and`s** (its
   definition written out, the spelling key's second part) was kept after
   a later fix rewrote a definition it executes, so spellings were chosen
   by a stale count; with booleans.defcl reordered, 1–4 operations per
   program were left with spelling errors. The count is now recomputed
   whenever a definition it depends on changes.


## What DLPs 57–59 Do Here That the Earlier Studies Didn't Show

- **Registered operations' definitions are forced into each other.**
  Each definition follows only `and`, `not`, and the registered operations
  listed before it, so the first one listed is written out and the later
  ones execute the earlier ones: with `or`, `implies`, `xor`, `eq`, `mux`,
  and `maj` registered in that order, `xor` is `or(a and not b, not a and
  b)`, `eq` is `not xor(a, b)`, and `maj` is `mux(c, or(a, b), a and b)`
  (`gen/program.py`, `DEFINITIONS`). With `[eq, xor]` instead, `eq` has to
  be written out and `xor` is `not eq(a, b)`. The match rules and DLP 9
  together force that: nothing else compiles. A program written the other
  way doesn't, and fixing it needs the write-out order above; every
  reordered program the comparisons fixed compiles.
- **An edit to booleans.defcl is a change to the whole project.**
  Registering one user operation of three views made 13% of the 15k program
  and 12% of the 150k program fail (`match`, then `spelling`), and swapping
  the first two registered operations made 3.0% fail with spelling
  errors. A compiler has to check every operation again for them, which is
  linear in the program (below).
- **Views a function doesn't depend on are interchangeable** with each
  other, so DLP 58's argument order applies to the values given to them.
  A fix that removes a value's last use of a view can make that happen in
  every operation that executes it.
- **Two readings the DLPs leave open**, both chosen to match the
  independent checker: a boolean input from a statement that isn't boolean
  (a comparison's result) is a value "that comes before" a match only after
  that statement, and a statement nothing reads still reads its arguments
  when counting what a match removes (which only matters in a program whose
  order is wrong).

## What Doesn't Scale

- **Truth tables with wide executions** (above): the cost of an execution
  is 2^I times the executed operation's views when it's too big to write
  out, so a caller at 20 inputs that executes several 16–20-view operations
  takes 25–80 ms, against well under 1 ms for an operation of 8 inputs.
  That's within DLP 57's limits but sets the cost of the largest
  operations, and writing out larger operations makes it slower, not
  faster.
- **SAT for redundant values with no stored patterns**, on operations that
  execute wide ones (above): the reason to use truth tables up to 20
  inputs.
- **Writing out an execution given a constant can cascade.** When an
  operation's boolean written view is constant (DLP 57's step 4), each
  caller's execution given that constant is written out, and the
  executions in the copy that are given a constant in turn, so 20–40
  statements can become thousands. Each copy is simplified by itself
  before it's inlined, and every redundant value and non-overlapping match
  is fixed after one check, but the rest still takes one check per round
  at the copy's size. In the wide program as first generated, with five
  times as many constant written views as now, four mixed operations took
  228 s of the fix: m4_32 then took 141 rounds and 37.7 s, and **ended
  with 344 boolean statements, past DLP 57's limit of 256, with no other
  error**, so the fix loop can't make it compile. The fixes check past the
  limit on the way to a smaller operation, but nothing brings this one
  back under it. A read view that doesn't matter no longer starts a
  cascade: its reads get another read view the operation keeps.
- **An edit to booleans.defcl is linear in the whole project**, not in what
  the edit touches: the registered operations apply to every value
  operation, so each one's tables are computed again and searched for the
  changed operations, 6–11 s at 150k and 17 s for the wide program. Storing
  every value's truth table would avoid the tables but not the search, and
  costs far more memory than it saves time.
- **Edits to a widely executed operation cascade** to every operation that
  executes it when its function changes (up to 138 operations here); that's
  what incremental checking has to do, since their functions change too.
- **Memory** is no constraint: 782 MB to check 150k operations, 1.59 GB to
  fix them, 229 MB to check the wide program and 428 MB to fix it.
- Everything else (the structural rules, order, ranks, interchangeable
  views, redundant values by truth tables, and hashing) is linear and small.
