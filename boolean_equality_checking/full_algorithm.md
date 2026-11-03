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
for a whole run. Generating took 8.7 s, 85.7 s, and 69.9 s. Every step
uses the current `beq`, and the check is truth tables up to 20 inputs
(`auto`, DLP 57's limit), so there's no SAT in any row.

#### The programs, fixed until they compile

| program | operations | boolean | boolean statements | executions of user operations | copies | operations before fixing | rounds, median / most | fixing | memory | fixes | statuses |
| ------- | ---------- | ------- | ------------------ | ----------------------------- | ------ | ------------------------ | --------------------- | ------ | ------ | ----- | -------- |
| ops_15k | 14,897 | 11,897 | 153,130 | 18,892 | 7,209 | 15,006 | 2 / 17 | 16.4 s | 168 MB | dead 94, match 33,793, opposite match 7,616, opposite value 455, redundant 5,634, spelling 12,049, unused view 66, wrapper 109 | ok 15,006 |
| ops_150k | 148,858 | 118,858 | 1,529,990 | 188,677 | 70,388 | 150,006 | 2 / 21 | 164 s | 1.6 GB | dead 1,236, match 339,427, opposite match 76,839, opposite value 4,497, redundant 54,999, spelling 120,561, unused view 588, wrapper 1,148 | ok 150,006 |
| ops_2k_wide | 1,995 | 1,595 | 81,363 | 11,393 | 3,186 | 2,006 | 7 / 43 | 55.7 s | 417 MB | dead 12, match 4,926, opposite match 605, opposite value 15, redundant 1,084, spelling 12,415, unused view 11, wrapper 11 | ok 2,006 |

#### Checking every operation

| program | run | wall | structure | tables | groups | order | redundant | matches | spellings | per operation, median | 99th percentile | slowest | truth tables / SAT | memory | operations with errors |
| ------- | --- | ---- | --------- | ------ | ------ | ----- | --------- | ------- | --------- | --------------------- | --------------- | ------- | ------------------ | ------ | ---------------------- |
| ops_15k | first | 1.89 s | 50.6 ms | 61.5 ms | 3.27 ms | 36.1 ms | 17.5 ms | 877 ms | 572 ms | 84.5 µs | 402 µs | 762 µs | 14,897 / 0 | 83 MB | 0 |
| ops_150k | first | 18.1 s | 471 ms | 717 ms | 31.6 ms | 351 ms | 165 ms | 8.37 s | 5.44 s | 80.8 µs | 380 µs | 8.42 ms | 148,858 / 0 | 787 MB | 0 |
| ops_2k_wide | first | 19.6 s | 47 ms | 13 s | 102 ms | 54.3 ms | 1.5 s | 2.6 s | 2.18 s | 4.57 ms | 72.8 ms | 98.2 ms | 1,995 / 0 | 223 MB | 0 |

#### Checking again

| program | change | time | operations checked | slowest edit | most checked |
| ------- | ------ | ---- | ------------------ | ------------ | ------------ |
| ops_15k | unchanged, by hashes | 27.1 ms | 0 |  |  |
| ops_15k | 200 random edits | 118 µs median | 1 median | 2.15 ms | 16 |
| ops_15k | booleans.defcl: register b0_21 | 1.25 s | 14,897 |  | 4,205 with errors |
| ops_150k | unchanged, by hashes | 274 ms | 0 |  |  |
| ops_150k | 200 random edits | 109 µs median | 1 median | 3.58 ms | 33 |
| ops_150k | booleans.defcl: register b0_5919 | 10.3 s | 148,858 |  | 17,505 with errors |
| ops_2k_wide | unchanged, by hashes | 14.2 ms | 0 |  |  |
| ops_2k_wide | 100 random edits | 8.82 ms median | 1 median | 1.34 s | 80 |

#### Time per operation by boolean inputs (first check)

| program | inputs | operations | mean | slowest |
| ------- | ------ | ---------- | ---- | ------- |
| ops_15k | 1 | 124 | 16.9 µs | 23.6 µs |
| ops_15k | 2 | 268 | 37.8 µs | 71.3 µs |
| ops_15k | 3 | 2,309 | 40.1 µs | 146 µs |
| ops_15k | 4 | 2,512 | 69.3 µs | 347 µs |
| ops_15k | 5 | 2,571 | 99.1 µs | 431 µs |
| ops_15k | 6 | 2,440 | 127 µs | 588 µs |
| ops_15k | 7 | 2,368 | 152 µs | 762 µs |
| ops_15k | 8 | 2,231 | 183 µs | 628 µs |
| ops_15k | 9 | 63 | 91.8 µs | 244 µs |
| ops_15k | 10 | 11 | 114 µs | 237 µs |
| ops_150k | 1 | 1,030 | 16 µs | 22.2 µs |
| ops_150k | 2 | 2,465 | 35.9 µs | 96.1 µs |
| ops_150k | 3 | 23,224 | 37.7 µs | 3.31 ms |
| ops_150k | 4 | 25,257 | 66.5 µs | 387 µs |
| ops_150k | 5 | 25,701 | 96.1 µs | 8.42 ms |
| ops_150k | 6 | 25,171 | 122 µs | 1.9 ms |
| ops_150k | 7 | 23,455 | 147 µs | 3.22 ms |
| ops_150k | 8 | 21,920 | 175 µs | 3.65 ms |
| ops_150k | 9 | 540 | 87.8 µs | 280 µs |
| ops_150k | 10 | 95 | 105 µs | 239 µs |
| ops_2k_wide | 2 | 4 | 31.6 µs | 50.8 µs |
| ops_2k_wide | 3 | 2 | 32.2 µs | 33.7 µs |
| ops_2k_wide | 10 | 7 | 207 µs | 374 µs |
| ops_2k_wide | 11 | 12 | 283 µs | 518 µs |
| ops_2k_wide | 12 | 44 | 328 µs | 998 µs |
| ops_2k_wide | 13 | 40 | 445 µs | 1.01 ms |
| ops_2k_wide | 14 | 53 | 601 µs | 1.74 ms |
| ops_2k_wide | 15 | 52 | 983 µs | 2.67 ms |
| ops_2k_wide | 16 | 401 | 2.41 ms | 6.94 ms |
| ops_2k_wide | 17 | 382 | 4.05 ms | 11.8 ms |
| ops_2k_wide | 18 | 361 | 7.26 ms | 23 ms |
| ops_2k_wide | 19 | 308 | 13.9 ms | 57.2 ms |
| ops_2k_wide | 20 | 329 | 30.3 ms | 98.2 ms |

#### The slowest operations (first check)

| program | operation | inputs | statements | redundant values by | total | checks taking 10% or more | match search nodes |
| ------- | --------- | ------ | ---------- | ------------------- | ----- | ------------------------- | ------------------ |
| ops_15k | b6_620 | 7 | 39 | tt | 762 µs | matches 481 µs, spellings 247 µs | 4,318 |
| ops_15k | b5_928 | 8 | 32 | tt | 628 µs | matches 407 µs, spellings 186 µs | 3,596 |
| ops_15k | b6_531 | 7 | 33 | tt | 615 µs | matches 412 µs, spellings 172 µs | 3,982 |
| ops_15k | b5_580 | 8 | 33 | tt | 608 µs | matches 331 µs, spellings 238 µs | 3,175 |
| ops_15k | b9_880 | 7 | 32 | tt | 608 µs | matches 409 µs, spellings 164 µs | 4,240 |
| ops_150k | m6_885 | 5 | 11 | tt | 8.42 ms | tables 8.32 ms | 370 |
| ops_150k | b3_4876 | 8 | 7 | tt | 3.65 ms | tables 3.58 ms | 255 |
| ops_150k | b5_8574 | 8 | 21 | tt | 3.46 ms | matches 3.35 ms | 1,109 |
| ops_150k | b9_3719 | 3 | 2 | tt | 3.31 ms | matches 3.29 ms | 34 |
| ops_150k | b2_1951 | 7 | 28 | tt | 3.22 ms | spellings 2.98 ms | 1,786 |
| ops_2k_wide | b4_245 | 20 | 65 | tt | 98.2 ms | tables 86 ms | 1,827 |
| ops_2k_wide | b3_183 | 20 | 78 | tt | 94.6 ms | tables 80.9 ms | 1,207 |
| ops_2k_wide | b4_285 | 20 | 54 | tt | 89.9 ms | tables 81.3 ms | 2,036 |
| ops_2k_wide | b2_213 | 20 | 79 | tt | 89.6 ms | tables 76.7 ms | 1,495 |
| ops_2k_wide | b4_9 | 20 | 69 | tt | 87.5 ms | tables 76.4 ms | 4,403 |

ops_15k: the independent checker checked 1,200 operations (300 sampled and what they execute) in 57.2 s; 0 fail it, 0 fail `beq`.

ops_150k: the independent checker checked 1,200 operations (300 sampled and what they execute) in 51.9 s; 0 fail it, 0 fail `beq`.

- **Checking is linear in the program.** The full check takes 1.89 s for
  15k operations and 18.1 s for 150k (10×, for 10× the statements), 81–85
  µs per operation in the median at both sizes, with about the same 99th
  percentile (380–400 µs). Matches take 46% and spellings 30%. The few operations
  at 4–8 ms at 150k are single outliers, not a heavier tail.
- **The fix loop is linear too:** 1.09 ms per operation at 15k (16.4 s for
  15,006) and 1.09 ms at 150k (164 s for 150,006), in a median of 2 rounds
  and at most 21, and every fixed program compiles when read back (0
  operations with errors; the check of the written program takes 1.9 s,
  18.3 s, and 19.9 s, inside the fix step's cap). It adds no value
  operation, and removes wrappers and operations that only name a view.
- **Rechecking an unchanged program costs only hashing:** 27 ms at 15k
  and 274 ms at 150k (10×); nothing is checked.
- **Random edits** check the edited operation and, when its written view's
  function or interchangeable views change, every operation that executes
  it: a median of 0.11–0.12 ms and one operation at 15k and 150k, at most
  16–33 operations. The wide program's edits cascade further, so it gets
  100 edits instead of 200, which with undoing each fit the step's cap;
  one cascades to 80 operations (1.3 s).
- **Registering an operation** checks every operation again, but only for
  matches and spellings of the one added; the order is by key, so how
  booleans.defcl lists them changes nothing: 1.25 s at 15k and 10.3 s at
  150k, against 1.89 s and 18.1 s for a full check. (No wide operation has
  the two to four views an operation needs to be registered.)

### The wide program

With 16–20 inputs, the time is in truth tables: 13.0 s of a 19.6 s check
(66%), of which 10.0 s is executions of operations too big to write out,
looked up minterm by minterm in their recorded tables, and 2.8 s
executions that are written out (at most 16 nodes per view). Matches take
2.6 s, spellings 2.2 s, and redundant values 1.5 s. An execution of a
k-view operation in a caller with I inputs costs 2^I lookups of k bits
each, about 20 million bit operations at 20 inputs. The fix loop takes
55.7 s for 2,006 operations (median 7 rounds, at most 43) and the check of
what it writes 20 s.

SAT sweeping for redundant values with no stored patterns took 69 s on
this program, uncapped, against 1.5 s with truth tables, and matching
needs every value's truth table anyway, so SAT saves only the grouping of
tables by function. So the compiler's default uses truth tables up to 20
inputs, and SAT only past them, where DLP 57's limit makes an operation an
error anyway. The truth tables of every value aren't stored for a recheck
(about 9 MB per operation here); each operation's recorded table is, and
an unchanged operation isn't checked.

## Where Fixing Spends Its Time

`beq program --mode fix` reports the seconds spent in each part of fixing
(`phase_s`, `check_t`, and `write_s` in its summary). In the runs above:

| part | ops_15k | ops_150k | ops_2k_wide |
| ---- | ------- | -------- | ----------- |
| fixing, in all | 16.4 s | 164 s | 55.7 s |
| checks | 14.8 s (90%) | 147 s (90%) | 54.5 s (98%) |
| of which the match search | 9.9 s | 98.5 s | 18.7 s |
| of which the spelling search | 1.5 s | 14.9 s | 11.2 s |
| of which truth tables | 0.29 s | 3.2 s | 18.3 s (11.5 s lookups, 3.3 s written out) |
| of which redundant values, order, structure, groups | 0.59 s | 5.8 s | 5.0 s |
| of which the rest of a check (reading the operation, recording it) | 2.5 s | 24.8 s | 1.4 s |
| canonicalizing | 0.66 s (4%) | 6.8 s (4%) | 1.1 s (2%) |
| choosing and applying matches | 0.57 s | 5.8 s | 0.08 s |
| replacements, write-outs, settling, finishing, everything else | 0.12 s | 1.9 s | 0.06 s |
| checks, and checks per operation | 58,573, 3.9 | 584,974, 3.9 | 18,463, 9.2 |
| reading / writing the program | 0.10 s / 0.04 s | 1.1 s / 0.42 s | 0.03 s / 0.02 s |
| checking the written program | 1.9 s | 18.3 s | 19.9 s |

Choosing each match's spelling analyzes the operation once per round, not
once per comparison, and a check in the fix loop skips the searches whose
results that round can't use: spellings when there's a match, and both
when there's a literal or a read view that doesn't matter.

**The checks are the time, and within them the match and spelling
searches**, not equality: a check in the fix loop costs about 250 µs at
15k and 150k, three times a check of the fixed program (about 83 µs),
because an operation with errors has many more matches to find and verify
(every one, so that the non-overlapping ones can be applied together), and
an operation takes about four checks. The slowest operations are the same:
b1_68 in the wide program takes 0.23 s over 43 checks, 37 of them for
spellings, and the slowest in the 150k program, b9_1022, takes 13 ms.

**Other ways of deciding equality wouldn't help.** The search enumerates
candidate arguments for each value and filters them by their values on
random input combinations (simulation, already), then confirms the few
left against the truth tables; the exact confirmations were about 2% of
the 15k fix in a profile (`perf`). SAT or OBDDs would only replace those
confirmations, a word or 16 words compared at up to 10 inputs, with much
slower ones, and for the
wide program SAT was measured slower than truth tables (above). What would
cut the time is fewer or smaller searches: a search after a fix that
reuses the previous round's matches for the values the fix didn't touch.

**Reusing the previous round's search** is an optimization of this
research fix loop, measured here and not part of the recommended
algorithm (`beq program --mode fix --keep_searches 1`,
`Matcher::SearchCache`). A value's search reaches the same candidates
whenever its function, the operations searched, and the values available
before it are the same, with whether each of those is a `not`, which a
spelling's key counts; for a spelling, the key of the value's own spelling
has to be the same too. Values keep their functions while the fix loop
works on one operation, so when those are unchanged from the previous
check, it replays the candidates that search reached, and decides
everything else again: what a match removes (which depends on the
statements that read the value, which a fix can change), whether the
execution already exists, and the exact check. So the removal never stops
a reuse; it's decided again on every replay. It's off for the registered
operations and what they execute, whose rewriting changes what writing a
registered operation out costs, and emptied when a read view is dropped.
With `--check_search 1` as well, every check also searches again and
stops if the two differ; slices of all three programs (2,000, 3,000, and
700 operations) pass, and on the whole programs the fixed programs are
byte for byte the same and compile. On a quiet machine, without and with
it:

| program | values reused | match search | spelling search | fixing |
| ------- | ------------- | ------------ | --------------- | ------ |
| ops_15k | 35% | 9.44 → 9.30 s | 1.45 → 1.18 s | 15.6 → 15.4 s |
| ops_150k | 35% | 95.9 → 96.5 s | 14.5 → 12.1 s | 159.3 → 160.1 s |
| ops_2k_wide | 76% | 18.0 → 12.5 s | 10.8 → 6.5 s | 53.6 → 44.8 s |

It saves time where an operation takes many checks: the wide program's
operations take about nine, and its fix is 16% faster. The 15k and 150k
programs' take about four, and what's reused there is mostly the cheap
searches, of the values early in an operation, so the fix is 1% faster at
15k and no faster at 150k, against what it costs to compare each value's
values before it. The runs were back to back on a quiet machine (load
under 1.2).

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
8. **Constants are errors.** A literal given to a boolean statement, a
   value that never changes, and a written view that never changes are
   reported (DLP 57), and the fix loop stops at them: the programmer fixes
   them. The generator makes none. A statement that isn't boolean can still
   be given a literal. A boolean value operation that only names one of its
   views or wraps one statement is removed, and each caller gets the
   argument or the wrapped statement. A mixed operation keeps its written
   views: a caller's values from a `run` are boolean inputs there, and
   giving the caller the value instead would change its functions, and
   could make one never change.
9. **Dead statements and read views that don't matter** are errors (DLP
   57). The fix loop removes dead statements, and removes a read view that
   doesn't matter from the operation and from every execution of it, which
   can leave statements dead in the callers. Its reads in the operation get
   the first read view the operation keeps that makes none of its values
   constant: the written view doesn't depend on it, so any value keeps what
   the operation writes. When every kept view makes a value constant, the
   error stays: in `g(x, y, z) = xor(xor(x, z), xor(y, z)) and x`, z
   doesn't matter, but z := x makes `xor(x, x)` constant and z := y makes
   `xor(y, y)` constant. Whether the tool should give the reads some other
   value of the operation instead, which fixes more cases but not every
   one, is open.
10. **`and` and `not` are registered** for every value operation, before
    the others, so matches can be `and`s and `not`s and every `and` is a
    spelling (a `not` isn't respelled: a value that's the opposite of an
    earlier one has to be its `not`, DLP 57). The other registered
    operations are ordered by **key** (DLP 59): the fewest `and`s in any
    and-inverter graph computing the function, then fewer read views, then
    the truth table as a number. A registered operation's own definition
    follows `and`, `not`, and the ones with smaller keys; spellings come
    in order of negated arguments, then key, then rank; and the largest
    match's tiebreak uses the same order. booleans.defcl is a set. For the
    six standard operations the keys put `implies` (1 `and`, 2 views,
    table 13) before `or` (1, 2, 14), then `xor` (3), `eq` (3), `mux` (3,
    3 views), and `maj` (4), so `or` is `implies(not a, b)`.
11. **Execution cycles.** DLP 9 forbids them, and both checkers report one
    at each execution that leads back. A match or spelling can make one:
    with `maj` defined as `U(a, b, c, or(a, b))` and `U` written out as
    majority `and t`, `U` is a match for `maj`, whose definition executes
    `U`. So before such a fix, the fix loop writes out the executions in
    the registered operation's definition that lead back (`maj` gets `U`'s
    statements, and `m and or(a, b)` is then redundant with `m`), and
    then makes `U` `maj(a, b, c) and t`. Only a match in a registered
    operation or something it executes can write out executions in a
    registered definition, so the fix loop fixes those first, until they
    compile, and the rest after. The proof covers this (fix 7 in
    `proof/termination.md`). A write-out can make a value that never
    changes, when the copied statements are given a value and its `not`;
    that's left as an error, and how the tool should handle it is open.
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

### The fewest `and`s

`min_ands_experiment.py` finds the fewest `and`s computing every function of
up to four views, once per NPN class (222 classes), by exact synthesis: a SAT
instance (Kojevnikov, Kulikov, and Yaroslavtsev's encoding, with every gate
read and consecutive independent gates in fanin order) for k = support − 1,
support, …, solved by Kissat, the first satisfiable k being the minimum. All
222 are proved, in 3,803 s of CPU (about 13 minutes on eight workers): 214 in
under a minute each, and the four that need ten `and`s in 5–12 minutes each,
most of it proving nine impossible. The counts by class: 0 for 2, 1 for 1, 2
for 2, 3 for 7, 4 for 9, 5 for 24, 6 for 30, 7 for 61, 8 for 45, 9 for 37,
and 10 for 4 (`results/min_ands.json`). They agree with the known minima (`or`
1, `implies` 1, `xor` 3, `eq` 3, `mux` 3, `maj` 4, three-way `xor` 6,
four-way `xor` 9), and with an exhaustive enumeration of every graph of up to
four `and`s on all 3,590 functions whose minimum is at most four.
`gen/min_ands_table.py` writes them into `src/min_ands_table.hpp`, so a
registered operation's count costs one canonicalization (768 permutations and
negations of a 16-bit table) and a lookup. Past four views it wouldn't be a
table: five views have 616,126 NPN classes, and exact synthesis already takes
minutes for the hardest four-view ones.

## Verification

The independent checker agrees with `beq` everywhere it was run:

- **The independent checker** computes every function by copying executed
  operations' statements, finds matches and spellings by trying every tuple
  of arguments, and builds DLP 58's order, ranks, and groups from the
  definitions. Over its self-tests and 30 random programs (10 of them
  with booleans.defcl listed in another order, which changes nothing),
  each raw and fixed, its reports and `beq`'s agree on all 1,922
  operations compared, rule by rule and detail by detail, and every fixed program
  compiles. It takes the fewest `and`s from the same table
  (`results/min_ands.json`), by its own canonicalization.
  On the fixed whole programs, a sample of each compiles under both:
  up to 300 operations chosen at random, each with everything it
  executes, while that stays within 1,200 operations (the independent
  checker's time is about linear in what it checks). An operation whose
  dependencies would pass that is skipped, which favors the shallow
  levels, but every level is in the sample: on the 150k program, 76 of
  the 300 are at level 0 and 11 at level 11, and 24,509 were skipped.
  The 15k program's sample took 57.2 s and the 150k program's 51.9 s;
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


## What DLPs 57–59 Do Here That the Earlier Studies Didn't Show

- **Registered operations' definitions are forced into each other.**
  Each definition follows only `and`, `not`, and the registered operations
  with smaller keys, so the one with the smallest key is written out and
  the others execute ones before them: with the six standard operations,
  `or` is `implies(not a, b)`, `xor` is `or(a and not b, not a and b)`,
  `eq` is `not xor(a, b)`, and `maj` is `mux(c, or(a, b), a and b)`
  (`gen/program.py`, `DEFINITIONS`). The match rules and DLP 9 together
  force that: nothing else compiles. A program written another way
  doesn't, and fixing it needs the write-out order above.
- **A key that depends only on what an operation computes keeps the
  spellings independent of how booleans.defcl is written.** An order taken
  from the list would make the count of `and`s in each definition written
  out depend on the list: fixing the six standard definitions under all 720
  list orders, with the list deciding what each definition follows
  (`registration_order_experiment.py`, `results/registration_order_list.json`),
  gives `or` 1, 3, 5, or 8 `and`s, `xor` and `eq`
  3 or 6, `mux` 3, 5, or 8, and `maj` 4, 5, 7, or 11, in 14 different sets,
  and with `[xor, eq, mux, or, implies, maj]` a value that's `or(u, w)` in
  the standard order has to become `xor(u, w)` in
  `f(a, b, c, x: number) = let u = a and b; let w = not a and c;
  (num.sel(u, x, 1), num.sel(w, x, 2), or(u, w))`. The fewest `and`s of a
  function doesn't depend on any definition or list: with the key, all 720
  orders give the same six definitions (`results/registration_order.json`).
- **An edit to booleans.defcl is a change to the whole project.**
  Registering one user operation of three views made 28% of the 15k program
  (4,205 operations) and 12% of the 150k program (17,505) fail (`match`,
  then `spelling`). A compiler has to check every operation again for them, which is
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
- **The table of fewest `and`s stops at four views**: five views have
  616,126 NPN classes, and the hardest four-view classes already take
  minutes of exact synthesis, so registered operations stay at four views
  (DLP 59).
- **An edit to booleans.defcl is linear in the whole project**, not in what
  the edit touches: the registered operations apply to every value
  operation, so each one's tables are computed again and searched for the
  added operation, 10.3 s at 150k. Storing
  every value's truth table would avoid the tables but not the search, and
  costs far more memory than it saves time.
- **Edits to a widely executed operation cascade** to every operation that
  executes it when its function changes (up to 80 operations here); that's
  what incremental checking has to do, since their functions change too.
- **Memory** is no constraint: 787 MB to check 150k operations, 1.6 GB to
  fix them, 223 MB to check the wide program and 417 MB to fix it.
- Everything else (the structural rules, order, ranks, interchangeable
  views, redundant values by truth tables, and hashing) is linear and small.
