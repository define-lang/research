# Test Cases for the Compiler's Boolean Checks

A complete covering set of test cases for the boolean checks of DLPs 56 and
59–61: what each case tests and what the compiler must report. Each case is
small enough to write by hand unless it says otherwise. The executable
end-to-end reduction suite lives in
`~/projects/define/drafts/boolean-reduction-cases.txt` (generated and verified
by `gen/reduction_cases.py`). "Error R at v" means rule R is reported with v as
the value it names; "no error" means the value operation compiles.

Every case runs under Define's fixed global standard boolean operations
(DLP 61), in fixed order: `and`, `not`, `or`, `xor`, `equal`, where
`or(a, b) = not (not a and not b)`, `xor(a, b) = or(a and not b, b and not a)`,
and `equal(a, b) = not xor(a, b)`, and Define's conservative limits (DLP 59):
at most **20** boolean input interface views per value operation, **256**
boolean statements, **512** boolean inputs, and **65,536** canonical shared
ROBDD reachable nodes past 20 inputs.

## 1. Boolean Value Operations and One Written View (DLP 59)

| id | case | tests | expected |
| --- | --- | --- | --- |
| V1 | `f(a, b) = a and b` with only boolean views | a boolean value operation | it's boolean; executions of it are boolean statements |
| V2 | an operation with a boolean view and a number view | "every view only booleans" | not a boolean value operation; executing it isn't a boolean statement, and its boolean results are boolean inputs of the caller |
| V3 | a boolean value operation that writes two views | one output view | error: writes more than one view |
| V4 | one that writes no view | the same rule, other side | error (it must write exactly one) |
| V5 | a mixed operation writing a number and two booleans | several views are allowed when it isn't boolean | no error |
| V6 | a statement executing a mixed operation, its boolean result read by `and` | results of non-boolean statements are boolean inputs | the result is an input: never redundant against the caller's other inputs, never a match's statement |
| V7 | a View Setting copy inside a boolean value operation | copies are allowed statements | still boolean |
| V8 | a boolean value operation executing another one | executions are boolean statements | it counts as one statement |

## 2. Redundant Values (DLP 59)

The first redundant value, by statement order, is the one reported, with the
value it's the same as or the opposite of. DLP 59 runs before DLP 61.

| id | case | tests | expected |
| --- | --- | --- | --- |
| R1 | `t = a and not a` | always false | error redundant at t: always false |
| R2 | `t = not(a and not a)` | always true, through a `not` | error at `a and not a` (the first), always false |
| R3 | `f(a, b) = a and or(a, b)` | always the same as an input | error at the value: same as a |
| R4 | `x = a and b; y = b and a` | same as an earlier value, argument order | error at y: same as x (and DLP 60 also reports y's order) |
| R5 | `x = a and b; y = x and b` | same as an earlier value by absorption | error at y: same as x |
| R6 | `x = a and b; y = or(not a, not b)` | opposite of an earlier value | error at y: opposite of x, written `not x` |
| R7 | `x = a and b; y = not x` | the `not` exemption | no error |
| R8 | `x = a and b; n = not a; y = not n` | `not` of a `not` | error at y: same as a |
| R9 | `y = not a; z = not a` | a second `not` of one value | error at z: same as y |
| R10 | `w = not a; v = a and or(a, b)` (v after w) | same as one, opposite of another | error at v: same as a (same is reported over opposite) |
| R11 | `w = not y` where y is earlier, then `v` always equal to y | DLP 59's "same as one value and the opposite of its `not`" | error at v: same as y |
| R12 | `x = a and b; v = ...` with an opposite earlier than an equal | the first redundant value | the earlier statement is reported, not the later |
| R13 | two redundant values | reporting only the first | only the first is reported |
| R14 | `let c = cmp.lt(x, 3); or(c, a and c)` | redundant against a comparison input | error: same as `c` |
| R15 | `y = a and copy_of_a` | copies are the same value | error at y: same as a |
| R16 | `x = g(a, b); y = g(b, a)` where g is symmetric | executions are whole, through references | error at y: same as x |
| R17 | `x = g(a, b); y = h(a, b)` where h computes the same function as g | two user operations with one function | error at y: same as x |
| R18 | g's own statements have a value equal to f's value | only the operation's own values count | no error in f |
| R19 | two inputs from comparisons that happen to be equal (`cmp.lt(x, 3)`, `cmp.lt(x, 3)`) | inputs are independent | no error from DLP 59 |
| R20 | 20 inputs, a value equal to an earlier one on all but 1 of `2^20` combinations | exactness | no error; changing it to equal on all of them gives the error |
| R21 | `xor(a, equal(a, b))` (always `not b`, with no `not b` statement) | opposite of an input | error: opposite of b |
| R22 | a value always the opposite of a constant | constants count | error: always true or false |

## 3. Literals (DLPs 56 and 59)

| id | case | tests | expected |
| --- | --- | --- | --- |
| L1 | `a and true`, `a and false`, `not false` | `and`/`not` given a literal | error literal |
| L2 | `or(a, false)`, `g(a, b, false)` | executions of boolean value operations | error literal |
| L3 | a literal copied into a view, then given to `and` | the copy rule | error (DLP 55: a copy's source can't be a literal) |
| L4 | `cmp.lt(x, 3)` (a comparison given a literal) | non-boolean statements can take literals | no error |
| L5 | a mixed operation executed with a literal for a boolean view | executions that aren't boolean statements | no error |
| L6 | an action giving a literal to a boolean value operation | actions | no error |

## 4. Order, Associative Grouping, and Factoring (DLP 60)

### Argument order

| id | case | tests | expected |
| --- | --- | --- | --- |
| O1 | `b and a` with a, b input views in that order | interchangeable views, rank of input views | error: argument order, `a and b` |
| O2 | `x = a and b; y = x and c` | an input view ranks before a statement value | error at y: `c and x` |
| O3 | `x = a and c; z = b and c; w = z and x` | statement values compared by their arguments | error at w: `x and z` |
| O4 | `x = a and b; n = not c; w = n and x` | shorter argument list ranks first (`not` before `and`) | error: `x and n` vs `n and x` by first arg rank, then shorter list (`not a` before `a and b`) |
| O4b | `g(a, b, c) = or(a, b and c); h(a, b, c) = or(b, a and c); h(a, b, c) and g(a, b, c)` | tie broken by operation name | error: `g(a, b, c) and h(a, b, c)` |
| O5 | `let (p, q) = m(y); q and p` | tie broken by output-view index | error: `p and q` |
| O6 | `g(c, a, b)` with `g(x, y, z) = or(z, x and y)` | partial symmetry `{x, y}` | error: argument order, `g(a, c, b)` |
| O7 | `g(c, a, b)` with `g(x, y, z) = or(y, x and z)` | non-consecutive interchangeable views `{x, z}` | error: argument order, `g(b, a, c)` |
| O8 | `g(b, a, d, c)` with `g(x, y, z, w) = (x and y) and not (z and w)` | multiple symmetry groups `{x, y}` and `{z, w}` | error: argument order, `g(a, b, c, d)` |
| O9 | `g(c, b, a)` with `g(x, y, z) = or(x and y, z and or(x, y))` | 3-way symmetry detected semantically from function | error: argument order, `g(a, b, c)` |
| O10 | `x and copy_of_x` | a value and its copy tie | no argument-order error; still redundant |
| O11 | an execution of a mixed operation with its numeric views out of order | only boolean statements are ordered | no error |

### Statement order

| id | case | tests | expected |
| --- | --- | --- | --- |
| S1 | `n = not b; m = not a; x = m and n` | inputs come right before, in view order | error: `not a` comes first |
| S2 | a value computed long before its first use | "right before the statement that first uses it" | error: statement order |
| S3 | boolean statements before a comparison they don't feed | grouping before non-boolean statements | error: belong before the consumer or at the end |
| S4 | a mixed operation: `cmp`, boolean statements feeding `num`, then output views' | canonical interleaving | no error |
| S5 | a boolean statement needed by two non-boolean statements | "only once, where first needed" | comes before the first |
| S6 | an output view computed early | output views last, in view order | error |
| S7 | two output views of a mixed operation | order of output views | first view's statements first |
| S8 | a copy placed away from its execution | copies stay next to their execution | error (DLP 55) |
| S9 | non-boolean statements in any order | only boolean statements move | no error from DLP 60 |

### Associative grouping

Detected semantically from the 4-bit binary truth table (covers `and`, `or`,
`xor`, `equal`). Every maximal single-use chain of `m ≥ 3` leaves folds
left-to-right in monotonic DLP 60 rank order: `op(v_1, v_2)`, `op(v_3, t_1)`,
..., `op(v_m, t_{m-2})`.

| id | case | tests | expected |
| --- | --- | --- | --- |
| A1 | `a and (b and c)` | right-associated `and` | error grouping: `c and (a and b)` |
| A2 | `(a and c) and b` | left-folded but non-monotonic leaf rank | error grouping: `c and (a and b)` |
| A3 | `(a and b) and (c and d)` | balanced `and` pair | error grouping: `d and (c and (a and b))` |
| A4 | `or(a, or(b, c))`, `or(or(a, b), or(c, d))` | `or` right-associated and balanced | error grouping: `or(c, or(a, b))`, `or(d, or(c, or(a, b)))` |
| A5 | `xor(xor(a, b), xor(c, d))` | balanced `xor` | error grouping: `xor(d, xor(c, xor(a, b)))` |
| A6 | `equal(a, equal(b, c))`, `equal(equal(a, b), equal(c, d))` | `equal` right-associated and balanced | error grouping: `equal(c, equal(a, b))`, `equal(d, equal(c, equal(a, b)))` |
| A7 | `let t = b and c; or(a and t, d and not t)` | shared intermediate (`readers[t] == 2`) | no grouping error (`t` stays intact) |
| A8 | `equal(a, equal(b, not a)) and c` | complementary leaves in unfixed chain | DLP 59 redundancy runs before regrouping (no spurious constant) |

### Factoring common terms

Detected semantically from 4-bit binary truth tables (covers `(and, or)`,
`(or, and)`, `(and, xor)`, `(or, equal)`). Checked and fixed before DLP 61
matches.

| id | case | tests | expected |
| --- | --- | --- | --- |
| T1 | `or(a and b, a and c)` | `(and, or)` factoring | error factor: `a and or(b, c)` |
| T2 | `or(a, b) and or(a, c)` | `(or, and)` factoring | error factor: `or(a, b and c)` |
| T3 | `xor(a and b, a and c)` | `(and, xor)` factoring | error factor: `a and xor(b, c)` |
| T4 | `equal(or(a, b), or(a, c))` | `(or, equal)` factoring | error factor: `or(a, equal(b, c))` |
| T5 | `or(or(a and b, a and c), a and d)` | 3-term factoring | error factor: `a and or(d, or(b, c))` |
| T6 | `or(or(a and b, a and c), d)` | partial factoring (untouched term remains) | error factor: `or(d, a and or(b, c))` |
| T7 | `or((a and b) and c, (a and d) and e)` | multi-factor inner chains | error factor: `a and or(b and c, d and e)` |
| T8 | `or(not a and b, not a and c)` | negated common factor | error factor: `not a and or(b, c)` |
| T9 | `or(or(a and b, a and c), or(b and d, b and e))` | tie-break: most terms removed (`b`: 3) beats lower rank (`a`: 2) | factors `b` first: `or(a and c, b and or(e, or(a, d)))` |
| T10 | `or(or(a and b, a and c), b and d)` | tie-break: equal term count (2 each) broken by lowest rank (`a`) | factors `a`: `or(a and or(b, c), b and d)` |
| T11 | `or(or(a and c, a and d), or(b and c, b and d))` | cascading factoring | reduces to `or(a, b) and or(c, d)` |
| T12 | `let t = a and b; xor(or(t, a and c), t and d)` | shared inner term (`readers[t] == 2`) | no factoring error (`t` stays intact) |

## 5. Standard Boolean Operations: Matches, Spellings, and Wrappers (DLP 61)

DLP 61 checks run only when the operation has no DLP 59 redundant values and no
DLP 60 unfactored common terms. The fixed global standard set is
`and`, `not`, `or`, `xor`, `equal` (in that exact precedence order).

### Matches

| id | case | tests | expected |
| --- | --- | --- | --- |
| M1 | `not (not a and not b)` | `or` match (4 statements) | error match: `or(a, b)` |
| M2 | `not (not (a and not b) and not (not a and b))` | `xor` match | error match: `xor(a, b)` |
| M3 | `not (a and not b) and not (not a and b)` | `equal` match | error match: `equal(a, b)` |
| M4 | `xor(a, a and not b) and c` | `and` counts as standard | error match: `a and b` |
| M5 | `not (not (a and b) and not c)` | match over earlier statement values | error match: `or(c, a and b)` |
| M6 | `not a and not b and c` | opposite match of `or` (removes ≥ 3 statements) | error match: `not or(a, b)` |
| M7 | `or(not a, not b) and c` | opposite match of `and` (removes ≥ 3 statements) | error match: `not (a and b)` |
| M8 | `let n = not a; xor(or(n, not b), c and n)` | opposite match removing only 2 statements (`n` shared) | no error (3-statement threshold) |
| M9 | `not or(a, b) and c` | `not` of standard op stays (`nor` is not standard) | no error |
| M10 | `not xor(a, b) and c` | direct `equal` match beats `not xor` | error match: `equal(a, b)` |
| M11 | `let x = a and b; let y = c and not a; (not x and not y) and d` | match over correlated earlier values (`equal` beats `not or`) | error match: `equal(x, y)` |
| M12 | `xor(a, b)` own definition written with `and`/`not` | standard op definition uses only earlier standard ops | reduces to `or(a and not b, b and not a)` |
| M13 | `equal(a, b)` own definition written out | `equal` follows `and`, `not`, `or`, `xor` | reduces to `not xor(a, b)` |
| M14 | redundant value and match in one operation | DLP 59 before DLP 61 | only the redundant value is reported |
| M15 | unfactored common term and match in one operation | DLP 60 factoring before DLP 61 | factoring is reported/applied first |

### Spellings

| id | case | tests | expected |
| --- | --- | --- | --- |
| P1 | `let n = not a; xor(n, b) and c and n` | fewest negated arguments | error spelling: `equal(a, b)` |
| P2 | `let n = not a; equal(n, b) and c and n` | fewest negated arguments | error spelling: `xor(a, b)` |
| P3 | `let n = not a; let m = not b; xor(n, m) ...` / `equal(n, m) ...` | two negated arguments eliminated | error spelling: `xor(a, b)` / `equal(a, b)` |
| P4 | `let x = a and b; let y = c and not a; xor(x, y) and d` | mutually exclusive `x, y`: `or` precedes `xor` | error spelling: `or(x, y)` |
| P5 | `let x = or(a, b); let y = or(c, not a); equal(x, y) and d` | never both false `x, y`: `and` precedes `equal` | error spelling: `x and y` |
| P6 | `let x = a and b; not x` | `not` is never respelled | no spelling error |

### Wrappers

| id | case | tests | expected |
| --- | --- | --- | --- |
| W1 | `w(a, b) = or(a, b)`, `xor(a, b)`, `equal(a, b)` | wrappers of standard operations | error wrapper |
| W2 | `w(a, b) = or(b, a)` | renaming/swapping views is still a wrapper | error wrapper |
| W3 | `w(a, b) = a and b`, `w(a) = not a` outside standard library | wrappers of `and`/`not` | error wrapper |
| W4 | executing `operation<standard:/boolean/and>` inside a value operation | standard `and`/`not` wrappers are only for actions | error |
| W5 | `g(a, b) = a and not b; w(a, b) = g(a, b)` | wrapper of non-standard user operation | no wrapper error |
| W6 | `w(a, b) = a` | projection/identity op | drops `b`, removes `w` |
| W7 | `g(a, b, c) = c and (a and b)` | 2-statement op is not a wrapper | no wrapper error |

## 6. Dead Statements and Input Views That Don't Matter (DLP 59)

| id | case | tests | expected |
| --- | --- | --- | --- |
| D1 | `let d = a and c; (a and b) and c` | dead statement | error dead: `d` |
| D2 | `let d = a and c; let e = not d; (a and b) and c` | chained dead statements | error dead: `d`, `e` |
| D3 | `g(x, y, z, w) = x and not y` | unreferenced unused input views | drops `z, w` |
| D4 | `h(p, q) = p and not q; f(a, b, c) = or(h(a, c), h(a, not c)) and b` | unused view referenced via callee | drops `c`, simplifies `f` to `a and b` |
| D5 | `g(a, b, c, u1, u2) = let p = xor(u1, u2); xor(xor(a, p), xor(b, p)) and c` | interacting unused views (`u1 := a, u2 := a` makes `p` constant; per-view `u1 := a, u2 := b` succeeds) | drops `u1, u2`, reduces to `c and xor(a, b)` |
| D6 | `g(x, y, z) = xor(xor(x, z), xor(y, z)) and x` | unused view where every kept-view substitution creates a constant (`false`-substitution fallback) | drops `z`, reduces to `x and not y` |

## 7. Conservative Limits and Checking Backends (DLP 59)

Generated and verified in `gen/reduction_cases.py` and `reference_test.py`:

| id | case | tests | expected |
| --- | --- | --- | --- |
| X1 | pure boolean op with 20 boolean input views, ≤ 256 statements | at the interface-view limit | compiles (truth-table floor) |
| X2 | pure boolean op with 21 boolean input views | past the 20-view limit | `error limits` |
| X3 | irreducible 20-view op with 255 statements whose ROBDD exceeds 65,536 nodes | statement limit + guaranteed truth-table floor fallback (`bdd` → `tt`) | compiles cleanly via `tt` |
| X4 | 257 boolean statements (both random and irreducible) | past the 256-statement limit | `error limits` |
| X5 | mixed op with 24 boolean inputs (with redundancy, factoring, grouping, match) | ROBDD backend (`21 ≤ I ≤ 512`) | compiles cleanly via `bdd` |
| X6 | mixed op with 512 boolean inputs (via 20-view helper `h20`) | at the 512-input limit | compiles cleanly via `bdd` |
| X7 | mixed op with 513 boolean inputs | past the 512-input limit | `error limits` |
| X8 | mixed op with 14-pair inner product (`I = 28, S = 40`, 32,806 ROBDD nodes) | under 65,536 canonical ROBDD nodes | compiles cleanly via `bdd` |
| X9 | mixed op with 15-pair inner product (`I = 30, S = 43`, > 65,536 ROBDD nodes) | past the 65,536 canonical ROBDD node limit | `error limits` |
| X10 | every `I ≤ 20` case checked with both `--method auto` and `--method tt`, plus `program_check.py` for `I ≤ 12` | exact backend agreement & determinism | identical results |

## 8. Incremental Rechecking & Refactoring Termination

| id | case | tests | expected |
| --- | --- | --- | --- |
| I1 | unchanged program | text/contract hashes | nothing rechecked |
| I2 | edit preserving callee's boolean function and symmetry partition | 128-bit contract fingerprint | callers not rechecked |
| I3 | edit changing callee's boolean function or symmetry partition | incremental propagation | callers rechecked transitively while contracts change |
| F1 | program combining dead statements, redundant values, unused views, factoring, matches, spellings, and regrouping | Lean 4 termination proof (`dag_prog_terminates`, incl. `OpFix.factor`) | converges in finitely many rounds to a fixed point |
