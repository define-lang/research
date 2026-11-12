# Test Cases for the Compiler's Boolean Checks

A complete set of test cases for the boolean checks of DLPs 59–61, as the
DLPs stand now: what each case tests and what the compiler must report.
Each case is small enough to write by hand unless it says otherwise. The
programs are written in the expression form of
`~/projects/define/drafts/boolean-reduction-cases.txt` (read views in the
header, `let` for a value that's read more than once, `and` and `not`, and
executions as calls), which stands for the Define statements one per
operation. "Error R at v" means rule R is reported with v as the value it
names; "no error" means the value operation compiles.

Unless a case says otherwise, booleans.defcl registers `or`, `implies`,
`xor`, `eq`, `mux`, and `maj`, with the definitions of `gen/program.py`
(`DEFINITIONS`), which compile. `and` and `not` are registered for every
value operation without being listed, before the rest, which are ordered by
key (DLP 61): `implies`, `or`, `xor`, `eq`, `mux`, `maj`.

## 1. Boolean Value Operations and One Written View (DLP 59)

| id | case | tests | expected |
| --- | --- | --- | --- |
| V1 | `f(a, b) = a and b` with only boolean views | a boolean value operation | it's boolean; executions of it are boolean statements |
| V2 | an operation with a boolean view and a number view | "every view only booleans" | not a boolean value operation; executing it isn't a boolean statement, and its boolean results are boolean inputs of the caller |
| V3 | a boolean value operation that writes two views | one written view | error: writes more than one view |
| V4 | one that writes no view | the same rule, other side | error (it must write exactly one) |
| V5 | a mixed operation writing a number and two booleans | several views are allowed when it isn't boolean | no error |
| V6 | a statement executing a mixed operation, its boolean result read by `and` | results of non-boolean statements are boolean inputs | the result is an input: never redundant against the caller's other inputs, never a match's statement |
| V7 | a View Setting copy inside a boolean value operation | copies are allowed statements | still boolean |
| V8 | a boolean value operation executing another one | executions are boolean statements | it counts as one statement |

## 2. Redundant Values (DLP 59)

The first redundant value, by statement order, is the one reported, with
the value it's the same as or the opposite of.

| id | case | tests | expected |
| --- | --- | --- | --- |
| R1 | `t = a and not a` | always false | error redundant at t: always false |
| R2 | `t = not(a and not a)` | always true, through a `not` | error at `a and not a` (the first), always false |
| R3 | `f(a, b) = mux(a, b, b)` written out | always the same as an input | error at the value: same as b |
| R4 | `x = a and b; y = b and a` | same as an earlier value, argument order | error at y: same as x (and DLP 60 also reports y's order; see O-cases) |
| R5 | `x = a and b; y = x and b` | same as an earlier value by absorption | error at y: same as x |
| R6 | `x = a and b; y = or(not a, not b)` | opposite of an earlier value | error at y: opposite of x, written `not x` |
| R7 | `x = a and b; y = not x` | the `not` exemption | no error |
| R8 | `x = a and b; n = not a; y = not n` | `not` of a `not` | error at y: same as a |
| R9 | `y = not a; z = not a` | a second `not` of one value | error at z: same as y |
| R10 | `w = not a; v = <something always equal to a>` (v after w) | same as one, opposite of another | error at v: same as a (same is reported over opposite) |
| R11 | `w = not y` where y is earlier, then `v` always equal to y | DLP 59's "same as one value and the opposite of its `not`" | error at v: same as y |
| R12 | `x = a and b; v = not(xor-written-out of x, c)` with an opposite earlier than an equal | the first redundant value | the earlier statement is reported, not the later |
| R13 | two redundant values | reporting only the first | only the first is reported |
| R14 | redundant against a boolean input from a comparison | inputs include non-boolean results | error: same as that input |
| R15 | `y = a and copy_of_a` | copies are the same value | error at y: same as a |
| R16 | `x = g(a, b); y = g(b, a)` where g is symmetric | executions are whole, through references | error at y: same as x |
| R17 | `x = g(a, b); y = h(a, b)` where h is a second way to write g | two user operations with one function | error at y: same as x |
| R18 | g's own statements have a value equal to f's value | only the operation's own values count | no error in f |
| R19 | two inputs from comparisons that happen to be equal (`x < 3`, `x < 3`) | inputs are independent | no error from DLP 59 (only the comparisons know) |
| R20 | 20 inputs, a value equal to an earlier one only on 1 of 2^20 combinations | exactness | no error; changing it to equal on all of them gives the error |
| R21 | `v` always equal to `not w` where w is an input, with no `not w` statement | opposite of an input | error at v: opposite of w |
| R22 | a value always the opposite of a constant | constants count | error: always true or false |

## 3. Literals (DLPs 56 and 59)

| id | case | tests | expected |
| --- | --- | --- | --- |
| L1 | `a and true` | `and` given a literal | error literal (also redundant: same as a) |
| L2 | `g(a, false)` for a user operation g | executions of boolean value operations | error literal |
| L3 | a literal copied into a view, then given to `and` | the copy rule | the copy itself is an error (DLP 55: a copy's source can't be a literal) |
| L4 | `x < 3` (a comparison given a literal) | non-boolean statements can take literals | no error |
| L5 | a mixed operation executed with a literal for a boolean view | executions that aren't boolean statements | no error |
| L6 | an action giving a literal to a boolean value operation | actions | no error |

## 4. Statement Order and Argument Order (DLP 60)

### Argument order

| id | case | tests | expected |
| --- | --- | --- | --- |
| O1 | `b and a` with a, b read views in that order | interchangeable views, rank of read views | error: argument order, `a and b` |
| O2 | `x = a and b; y = x and a` | a read view ranks before a statement value | error at y: `a and x` |
| O3 | `x = a and b; z = a and c; w = z and x` | statement values compared by their arguments | error at w: `x and z` (x's arguments rank first) |
| O4 | `x = a and b; n = not a; w = x and n` | statement values with a common first argument | error: `n and x` (n's argument list is shorter) |
| O4b | `p = g(a, b); q = h(a, b); r = p and q` for two user operations with different functions | the tie broken by operation name | `p and q` if g's full name sorts before h's, otherwise `q and p` |
| O5 | values from a mixed execution's first and second written views, given to `and` | the written-view tie | the first view's value first |
| O6 | `g(c, a, b)` with g = `(x and y) or z` (views {x, y} interchangeable, z not) | mixed groups | error: argument order, `g(a, c, b)` (only the first two views swap) |
| O7 | g with views {x, z} interchangeable and y not (not consecutive) | non-consecutive groups | the group's values in rank order at x and z |
| O8 | g with two groups {x, y} and {z, w} | several groups | each group sorted on its own |
| O9 | g's groups found from its function: `maj` written out | detection by function, one check per pair | all three views one group |
| O10 | g symmetric in (x, y) and (y, z) | transitivity | one group of three |
| O11 | `x and copy_of_x` | a value and its copy tie | no argument-order error (the order between them doesn't matter); still redundant |
| O12 | an execution of a mixed operation with its numeric views out of order | only boolean statements are ordered | no error |
| O13 | literals of two qualities given to one execution | literal ranking | boolean literals before numeric, then by text (only reachable where literals are allowed) |

### Statement order

| id | case | tests | expected |
| --- | --- | --- | --- |
| S1 | `n = not b; m = not a; x = m and n` | inputs come right before, in view order | error: `not a` comes first |
| S2 | a value computed long before its first use | "right before the statement that first uses it" | error: statement order |
| S3 | boolean statements before a comparison they don't feed | grouping before non-boolean statements | error: they belong before the statement that needs them, or at the end |
| S4 | a mixed operation: comparison, the boolean statements it needs, a numeric statement reading them, then the written views' | the canonical interleaving | no error |
| S5 | a boolean statement needed by two non-boolean statements | "only once, where first needed" | it comes before the first |
| S6 | a written view computed early | written views last, in view order | error |
| S7 | two written views of a mixed operation | the order of written views | the first view's statements first |
| S8 | a copy placed away from its execution | copies stay next to their execution | error (DLP 55) |
| S9 | non-boolean statements in any order | only boolean statements move | no error from DLP 60 |

## 5. Matches (DLP 61)

| id | case | tests | expected |
| --- | --- | --- | --- |
| M1 | `not(not a and not b)` with `or` registered | the basic match | error match: `or(a, b)`, 4 statements |
| M2 | the same, with `or`'s arguments computed earlier and read elsewhere | arguments are any earlier values | error match, removing only the statements nothing else reads |
| M3 | `xor` written out over two earlier statement values | arguments that are statements | error match: `xor(x, y)` |
| M4 | a value equal to `or(a, b)` on all but one combination | exactness | no error |
| M5 | `f(a, b, c) = (a and b) or (a and not b)` = a | every argument must matter | not a match for `mux(b, a, a)`; redundant instead (same as a) |
| M6 | a value equal to `or(a, x)` where x doesn't change the result | an argument that doesn't matter | not a match with x |
| M7 | `not or(a, b)` written out, `or` registered, nothing computing `nor` registered | opposite result | error match: `not or(a, b)` when it removes at least 3 statements |
| M8 | an opposite result that removes exactly 2 statements | the 3-statement rule | no error |
| M9 | `not(or(a, b))` written as the `not` of an execution of `or` | an execution and its `not` | no error (never an opposite result) |
| M10 | the same with an operation computing `nor` registered | "match for that operation instead" | error match: `nor(a, b)`, even though it removes 2 statements (an execution and its `not` are a match for the opposite operation) |
| M11 | an opposite result when the opposite operation is also registered | the opposite operation wins | error match for the opposite operation, not `not R` |
| M12 | a value that is already an execution of R on those arguments | not a match | no error |
| M13 | a single statement equal to R of earlier values | a single statement is never a match | no error (unless it's a spelling, P-cases) |
| M14 | `g(a, b)` where g's own statements contain `or` written out | executions are whole | no error in the caller; the error is in g |
| M15 | a value inside an executed operation as an argument | arguments are the operation's own values | not available |
| M16 | `implies`'s own definition written out | a registered operation's definition follows only `and`, `not`, and the ones with smaller keys | no error for `implies` in `implies` (it has the smallest key) |
| M16b | `or` written with `and` and `not` | the definition follows ones with smaller keys: `implies` (1 `and`, 2 views, table 13) before `or` (1, 2, 14) | error match: `implies(not a, b)` |
| M16c | `xor` and `eq` both written out | the motivating case: no cycle | `xor` (key 3, 2, 6) can't use `eq` (3, 2, 9); `eq` is reported as `not xor(a, b)` |
| M16d | a standard-library operation's definition | the standard library's own keys | follows only `and`, `not`, and the standard library operations with smaller keys |
| M16e | a project operation's definition | the project after the standard library | follows `and`, `not`, every standard-library operation, and the project's operations with smaller keys |
| M16f | `xor` defined as `not eq(a, b)`, and `eq` written out | the match in `eq` would make `eq` and `xor` execute each other | the fix first writes out `xor`'s execution of `eq`, then makes `eq` `not xor(a, b)`; `xor` ends written with `or` |
| M16g | booleans.defcl `[maj]`, `maj` defined as `U(a, b, c, or(a, b))`, `U(a, b, c, t)` majority written out `and t` | the same through an unregistered operation | the fix first writes out `U` in `maj`, whose `m and or(a, b)` is then redundant with `m`, then makes `U` `maj(a, b, c) and t`; `maj` ends written out |
| M16h | `eq` executes `xor` and `xor` executes `eq` | DLP 9 forbids execution cycles | error cycle in both, at the execution that leads back; an operation that executes one of them gets no other check |
| M17 | two matches removing 4 and 3 statements | the largest is reported | the 4-statement one |
| M18 | two matches of equal size, different values | the earlier value | the earlier one |
| M19 | two of equal size and value, different operations | the registered operation that comes first | `and`, then `not`, then the project's by key, then the standard library's by key (not alphabetical, not as listed) |
| M28 | `mux(not c, c, b)` | `and` counts as registered | error match: `b and c` (removes the execution and `not c`) |
| M29 | `or(not a, not b)` with `or` registered, where that removes at least 3 statements | opposite results of `and` | error match: `not (a and b)` |
| M30 | `or(not a, not b)` where `not a` is read elsewhere | the 3-statement rule for an opposite of `and` | no error (it would remove only 2) |
| M31 | a value equal to `not x` for an earlier x | a match for `not` | never reported: it's an opposite value first (DLP 59) |
| M20 | equal size, value, and operation, different arguments | rank order of arguments | the lower-ranked arguments |
| M21 | a match whose reported fix uses the first spelling | "names the spelling that comes first" | the message names the highest-precedence spelling of that match |
| M22 | a match of four arguments (a registered four-view operation) | the four-argument limit | found |
| M23 | a registered operation of five views | the registry limit | error in booleans.defcl |
| M24 | a match over values that come after a comparison, used before it | "values that come before it" | only values before v count; an input from a comparison counts only after the comparison (a reading the DLPs leave open) |
| M25 | redundant value and match in one operation | redundant values first | only the redundant value is reported |
| M26 | a value equal to a registered operation applied to a value and its copy | copies are one value | not a match with the same value twice (views may not alias; a copy is the same value) |
| M27 | a value operation whose whole set of statements is a registered operation | "can't compute the same thing" | error match at its written view |

## 6. Spellings (DLP 61)

A spelling is a single execution of a registered operation computing a
value from earlier values. Only the first spelling is allowed.

| id | case | tests | expected |
| --- | --- | --- | --- |
| P1 | `n = not b; or(a, n)` with `implies` registered | fewest negations | error spelling: `implies(b, a)` |
| P2 | two spellings with equal negations, `or` (key: 1 `and`) and `mux` (3) | key | the `or` spelling |
| P3 | equal negations, two operations with the same fewest `and`s | the key's views, then truth table | `implies` before `or`; `xor` before `eq`; `eq` before `mux` (fewer views) |
| P11 | `a and implies(a, b)` | an `and` statement is a spelling too | error spelling: `a and b` (same key until the arguments' ranks) |
| P12 | `mux(a, b, a)` | `and` comes before every other registered operation | error spelling: `a and b` |
| P4 | equal in all three, different arguments | rank order | the lower-ranked arguments |
| P5 | a registered operation's count of `and`s | the fewest in any and-inverter graph computing its function, not its definition | `or` has 1 whether defined as `not (not a and not b)` or as `implies(not a, b)`; `maj` has 4 |
| P6 | a registered operation from the standard library and one from the project with otherwise equal keys | project's, then the standard library's | the project's |
| P7 | a `not` of an execution that another execution could compute, or a `not` that an `and` could compute | a `not` isn't respelled: a value that's the opposite of an earlier one is its `not` (DLP 59) | no spelling error; with w = `x implies (not y)`, `not w` stays though `x and y` computes it |
| P8 | swapping two operations in booleans.defcl | the order is the precedence | values that were first spellings may become errors, everywhere in the project |
| P9 | a spelling over values after v | only earlier values | not a spelling |
| P10 | a user operation (not registered) whose execution computes R(a, b) | spellings are executions of registered operations | no error (one statement isn't a match) |

## 7. Wrappers (DLP 61)

| id | case | tests | expected |
| --- | --- | --- | --- |
| W1 | `f(a, b) = or(a, b)` | a wrapper of a registered operation | error wrapper |
| W2 | `f(a, b) = or(b, a)` | renaming views is still a wrapper | error wrapper |
| W3 | `f(a, b) = a and b` outside the standard library | wrappers of `and` | error: use `operation<standard:/boolean/and>` |
| W4 | `f(a) = not a` | wrappers of `not` | error |
| W5 | executing `operation<standard:/boolean/and>` inside a value operation | the standard wrappers only in actions | error |
| W6 | registering the standard `and` wrapper | never registered | error in booleans.defcl |
| W7 | `f(a, b) = g(a, b)` for an unregistered user operation g | only registered operations | no error |
| W8 | `f(a) = or(a, copy_of_a)` | a would-be wrapper given one value twice | redundant (same as a), reported before the wrapper |
| W9 | an action executing `operation<standard:/boolean/and>` | allowed use | no error |

## 8. Registration (DLP 61)

| id | case | tests | expected |
| --- | --- | --- | --- |
| G1 | `has_booleans` false with a booleans.defcl present | the flag | the file isn't read; no matches |
| G2 | a short-form name | the current project | resolves to this project's operation |
| G3 | a dependency's operation by full global name | adopting a dependency's operation | its matches apply to this project's operations |
| G4 | a dependency's own booleans.defcl | only the project's own and the standard library's | the dependency's registrations don't apply here |
| G5 | a library value operation checked in its own project and as a dependency | the same rules either way | the same errors |
| G6 | a name listed twice | each name once | error |
| G7 | two registered operations computing the same thing up to view order | duplicates by function | error, naming both |
| G7b | a registered operation computing `a and b` (or `not a`) | `and` and `not` are registered already | error: computes the same as `and` |
| G8 | the project registering what the standard library also registers | cross-project duplicate | error (two apply to the same value operation) |
| G9 | a registered operation that isn't a boolean value operation, or writes two views | registry limits | error |
| G10 | a name that doesn't resolve | missing operation | error |
| G11 | changing booleans.defcl | which operations are rechecked | every value operation of the project, for matches and spellings (the standard library's change rechecks every project) |

## 9. Limits (DLP 59)

Generated, not written by hand.

| id | case | tests | expected |
| --- | --- | --- | --- |
| X1 | 256 boolean statements | at the limit | no limit error |
| X2 | 257 boolean statements | past it | error: limits |
| X3 | 256 statements plus copies and non-boolean statements | only boolean statements count | no error |
| X4 | 20 boolean inputs | at the limit | no error |
| X5 | 21 boolean inputs | past it | error: limits |
| X6 | 20 inputs counting comparisons' results and mixed executions' boolean results | what counts as an input | 21 of them is an error |
| X7 | an execution of a 20-view operation given 3 values | executions count their values, not the callee's views | 3 inputs |
| X8 | a registered operation of 4 views, and of 5 | the registry limit | 4 fine, 5 an error |

## 10. The Checking Methods

Every method must give the same classes; these cases make each one decide
something. With the recommended truth tables up to 20 inputs only the last
group applies inside the limits; the others are for value operations checked
past them or as one graph.

| id | case | tests | expected |
| --- | --- | --- | --- |
| C1 | 12 inputs, any logic | truth tables | exact classes |
| C2 | 13–20 inputs with wide executions | truth tables with lookups and written-out executions | same classes as copying every execution |
| C3 | 20 inputs, 256 statements | the worst case | under 100 ms |
| C4 | random logic past 20 inputs with planted equalities | SAT sweeping | every planted pair found |
| C5 | parity of 64–128 inputs written two ways | SAT gives up at 1,000 conflicts, OBDDs decide | equal |
| C6 | 10-bit multipliers written two ways | SAT and OBDDs both hard | equal, by the last rung (Kissat) |
| C7 | hidden weighted bit (HWB) written two ways | OBDDs exponential in every order | equal, by SAT |
| C8 | a pair whose cones read at most 12 inputs inside a larger operation | exhaustive simulation of the pair | decided without SAT |
| C9 | near misses: v or (a cube of 12 inputs) | rare differences | different, with the one counterexample |
| C10 | the same operation checked by every method and with three seeds | determinism | identical classes |

## 11. Incremental Rechecking

| id | case | tests | expected |
| --- | --- | --- | --- |
| I1 | an unchanged program | text hashes | nothing is checked |
| I2 | an edit that keeps an operation's written function | only the operation | it alone is checked |
| I3 | an edit that changes the written function | callers | every operation executing it, transitively while functions change |
| I4 | an edit that changes only a callee's interchangeable views (e.g. it stops depending on order) | groups are recorded too | callers' argument order rechecked |
| I5 | stored patterns | patterns only find counterexamples | the same classes with and without them |
| I6 | a change to booleans.defcl | registrations apply everywhere | every operation, matches and spellings only, for the registered operations added or moved |
| I7 | a dependency's operation changes function | across projects | callers in this project rechecked |
| I8 | an edit introducing an error in a callee | callee errors | the callee reports it; callers use its recorded function |

## 12. The Refactoring Steps (DLP 59's Refactoring Existing Systems)

| id | case | tests | expected |
| --- | --- | --- | --- |
| F1 | `a and true` | literals are errors the programmer fixes | error literal; the tool stops |
| F2 | `g(a, false)` with g = `x or y` | the same through an execution | error literal; the tool stops |
| F3 | redundant value same as w | step 2 | reads use w; statements nothing reads are removed |
| F4 | opposite of w | step 2 | `not w` |
| F5 | `x and not x` | values that never change are errors the programmer fixes | error redundant (constant); the tool stops |
| F7 | a literal given to a statement that isn't boolean | only boolean statements can't take literals | no error |
| F9 | a boolean value operation whose written view is constant | a value that never changes | error; the tool stops |
| F12 | a wrapper | DLP 61's wrapper rule as a fix | callers execute the wrapped operation directly; the wrapper is removed |
| F13 | an operation that only writes one of its views | a projection | callers use the argument |
| F14 | the largest match | matches as fixes | replaced by an execution with its first spelling |
| F15 | an opposite match | adds two statements | execution and `not` |
| F16 | a spelling | 1-for-1 | replaced |
| F17 | order | canonicalizing | statements and arguments sorted, copies inserted where a value goes to two views |
| F18 | a program needing all of the above | termination | it compiles in finitely many rounds (`proof/termination.md`); the measure goes down at every fix |
| F19 | 1,000 random programs | termination in practice | every fix loop ends |
| F21 | dead statements | step 5 | removed |
| F22 | a read view that doesn't matter | step 6 | its reads get the first read view the operation keeps that makes no value constant, then it's removed from the operation and from every execution of it |
| F23 | F22 where the value given to the view was computed only for it | step 6 makes callers' statements dead | they're removed too |
| F24 | F22 where removing the view makes a caller's own view not matter | steps cascade | the caller loses that view in turn |

## 13. Dead Statements and Read Views That Don't Matter (DLP 59)

| id | case | tests | expected |
| --- | --- | --- | --- |
| D1 | `let d = a and c` that nothing reads | a dead statement | error dead: `d` |
| D2 | `let d = a and c; let e = not d`, neither read | every dead statement at once | error dead: `d`, `e` |
| D3 | a statement read only by a dead statement | dead through the statements that read it | dead too |
| D4 | a statement read only by a numeric statement | non-boolean statements are readers | not dead |
| D5 | a statement read only by a written view of a mixed operation | written views are readers | not dead |
| D6 | a match whose arguments' other reader is dead | removal counts only live readers | the dead reader doesn't keep anything alive; the dead statements are reported as well |
| D7 | `g(x, y, z) = x and not y` | a read view that doesn't matter | error unused view: z |
| D8 | g whose statements read z but whose written view doesn't depend on it (`xor(xor(x, z), xor(y, z))`) | "matter" is about the written view's function | error unused view: z |
| D9 | g with two views it doesn't depend on | all of them | error unused view: both |
| D10 | a mixed operation with a numeric view nobody reads | only boolean value operations | no error from this rule |
| D11 | g(x, y) where y matters on exactly one combination of x and y | "for some combination" | no error |
| D12 | callers of g after D7's fix | executions stop giving the view a value | the callers' values given to it can become dead (F23) |
| D13 | D8's fix | every kept view makes a value constant: z := x makes `xor(x, x)` constant, z := y `xor(y, y)` | the error stays; the tool stops |
| D14 | a view that doesn't matter read by an execution | the reads get another kept view, not a literal | the execution stays one execution |
