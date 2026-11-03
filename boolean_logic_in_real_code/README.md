# Boolean Logic in Real Code

DLP 57 limits each value operation to 20 boolean inputs and 256 boolean
statements. The numbers behind those limits came from generated programs. This
study measures how big boolean logic is in eleven large open-source codebases,
and how much of it would fit under those limits.

## Summary

- **Within a function, real code fits.** Of about 144,000 connected pieces of
  boolean logic, 10 have more than 20 inputs, all of them in Go code, and none
  has more than 256 statements. No Python piece has more than 19 inputs. The 99.9th percentile is at most 10 inputs and 13 statements in
  every codebase. Counted per function, the unit that DLP 57 limits, 0% to 1.7%
  of the functions that have boolean logic go over 20 inputs, and none goes over
  256 statements. The largest has 190.
- **Across calls, a few percent don't fit.** When every call to a
  boolean-returning function of the same codebase is written out in place, 0.05%
  to 7.7% of functions go over 20 inputs, and 0% to 0.6% go over 256 statements.
  The Go toolchain and mypy have the most. Saleor, Django and CPython have
  almost none.
- **The input limit is always the one that matters.** In real code a piece of
  logic has about as many statements as inputs, because nearly all of it is
  `and`/`or` chains over distinct comparisons. No unit with 20 or fewer inputs
  has more than 68 statements, so a unit over 256 statements is always over 20
  inputs too.
- **What produces the largest logic:**
  - classification tables, where one value is compared against many constants
    (instruction operand classes, which SQL functions a storage engine
    supports);
  - change or staleness checks that `||` together a comparison for every field
    or setting;
  - compiler and type checker predicates that call other predicates
    (type identity, "same expression", "types overlap");
  - long validators and request handlers, which are over the limit only per
    function, as many separate small conditions.

## Codebases

The study uses two languages, because each has a parser in its standard library
that gives a dependable syntax tree: Python (`ast`) and Go (`go/ast`).
Tree-sitter is not installed, so there is no Java, C or TypeScript.

| Codebase | Kind | Analyzed | Commit |
|---|---|---|---|
| CPython `Lib/` | standard library | 705 files | `3945eaf2fcd9` |
| Django | web framework | `django/`, 900 files | `b501b8493f31` |
| mypy | compiler (type checker) | `mypy/`, `mypyc/`, 252 files | `ccbf32bd4c8d` |
| Saleor | e-commerce application | `saleor/`, 2,627 files | `dfbf13948fa0` |
| Odoo | business applications (ERP) | `odoo/`, `addons/`, 6,708 files | `b0828a870297` |
| Home Assistant | home automation, device integrations | `homeassistant/`, 10,953 files | `4317ce263009` |
| Go `src/` | compiler, toolchain, runtime, standard library | 4,228 files | `7b2766511192` |
| CockroachDB | distributed SQL database | `pkg/`, 6,070 files | `d30c905fff79` |
| TiDB | distributed SQL database | `pkg/`, `br/`, `cmd/`, `dumpling/`, `lightning/`, 2,422 files | `e343a53e558f` |
| Kubernetes | systems, container orchestration | `pkg/`, `cmd/`, `staging/`, `plugin/`, 9,215 files | `8b2d0e51804e` |
| Gitea | Git forge, web application | `models/`, `modules/`, `routers/`, `services/`, `cmd/`, 1,791 files | `12b20c7c9962` |

The file counts leave out tests (`*_test.go`; `test_*.py`, `*_test.py`, and
directories named `test`, `tests` or `testing`), `testdata`, `vendor` and
`third_party` directories, and generated Go files (those marked
`// Code generated ... DO NOT EDIT.`: 470 in Go, 187 in CockroachDB, 46 in TiDB,
3,559 in Kubernetes and 1 in Gitea). Two Go files don't parse with Go 1.26's
parser, because they use generic methods, and are skipped:
`math/rand/v2/rand.go` in Go and `services/context/context.go` in Gitea.

## Method

### What is counted

A **boolean statement** is one of these:

- `and`/`&&`, `or`/`||` and `not`/`!`. A Python chain `a and b and c` is two
  statements.
- `==` or `!=` between two values that are themselves boolean logic or boolean
  variables (xnor and xor), and Python `&`, `|`, `^` between two evidently
  boolean operands.
- A Python conditional expression `x if c else y` whose result is boolean, which
  counts as one statement.
- A call to a **pure boolean function**: one whose parameters are all declared
  `bool`, that returns `bool`, whose body is only assignments, `if`s and
  `return`s, and whose returned logic reads only its parameters. Only 7 of the
  roughly 354,000 functions are pure boolean functions: 4 in CockroachDB, 2 in
  TiDB and 1 in Kubernetes.

A **boolean input** is a value that boolean statements read but that no boolean
statement computes: a comparison (`x < 3`, `a == b`), a parameter, a field or
other expression, a call that isn't to a pure boolean function, and a local
variable none of whose definitions is boolean logic. Inputs are distinct by
source text within a function, so `x > 0 && y` and `x > 0 || z` share the input
`x > 0`. Literals aren't inputs.

In Python, `a or b` is boolean logic when it is used as a condition (`if`,
`while`, `assert`, a comprehension's `if`, an operand of `not`, a conditional
expression's test, a `match` guard, or the definition of a variable that is used
only as a condition), when at least one operand is evidently boolean, or when the
function is annotated `-> bool`. Otherwise, as in `name = given or default`, it
picks a value and isn't counted. A value is evidently boolean if it is a
comparison, a `not`, `True` or `False`, a call to `isinstance`, `issubclass`,
`hasattr`, `callable`, `all`, `any`, `bool`, `startswith` or `endswith`, a call
to a name that starts with `is_`, `has_`, `can_` or `should_`, a parameter or
local annotated `bool`, or a local whose definitions are all evidently boolean.

### Pieces and functions

Each frontend turns every function into a graph of boolean statements, inputs
and local variables. A local variable read joins the reader to every definition
of that variable in the function (flow-insensitively), so `ok = a and b` followed
by `if ok or c:` is one piece with inputs `a`, `b` and `c`, and
`done = done or x > 3` in a loop is one piece that refers to itself.

A **piece** is a maximal connected set of boolean statements, connected through
operands and through variables that hold boolean logic. A **function total** is
the union of a function's pieces: their statements added up and their inputs
counted once. Python top-level module code counts as one function per file.
Closures and lambdas count as part of the function they are in.

### Scope 2: across calls

Scope 2 writes out, in place, each call whose result feeds a piece's logic, when
the call goes to a function of the same codebase that returns a boolean (Go:
its one result is `bool`; Python: it is annotated `-> bool`, or every `return`
gives an evidently boolean value). What the callee writes out is:

- the logic of its return values;
- the condition of every `if`, `while`/`for` condition, or tagless `switch` case
  that contains a `return`, each one adding one statement for choosing among the
  return values. A tagged Go `switch` that contains a `return` adds one input
  `tag == value` and one statement per case value;
- the logic of the caller's argument for each parameter that this logic reads,
  so the argument's own logic joins the piece.

The callee's other inputs become new inputs of the caller, distinct per call
text, so two identical calls are one written-out copy, and calls with different
arguments are separate copies, the same as inlining. This repeats through the
callee's own calls.

A call that the frontend can't tie to exactly one function stays an input. Calls
are found by name, without types:

- `f(...)`: a function `f` of the same Python module or Go package, or
  the module a Python `from m import f` names;
- `self.m(...)` or a Go method's receiver `r.m(...)`: method `m` of the same
  class or receiver type, and otherwise the one method named `m` in the
  codebase;
- `pkg.F(...)`: function `F` of the imported module or package;
- `x.m(...)` otherwise: the one method named `m` in the codebase, if exactly one
  exists. In Python, names of methods of built-in types (`str.startswith`,
  `dict.get`, ...) aren't resolved this way.

Expansion stops in three places, and the tables count the units where each one
happened:

- **Recursion stop:** a call to a function in the same strongly connected
  component of the call graph is recursive, so it stays an input.
- **Depth cap:** at most 8 calls deep. No unit reached it; the deepest expansion
  was 7.
- **Size cap:** a callee that writes out to more than 10,000 statements or 2,000
  inputs stays an input, and the unit counts as over both limits. This happened
  once, in Go's `loadStoreClass`.

A unit that stopped for recursion has at least the size shown.

### What this approximates

- No types. Booleans are recognized syntactically, as above, and calls are
  resolved by name. Some untyped Python `and`/`or` logic is missed, and a few
  calls resolve to the wrong method of the same name.
- No alias analysis. Fields, globals and anything reached through a pointer or
  attribute are inputs.
- Local variables are flow-insensitive and ignore scoping, so a variable joins
  all of its definitions, even when a later one replaces an earlier one, and a
  name reused in two blocks is one variable.
- Within a function, only data flow is followed, not control flow: in
  `ok := false; if c { ok = true }`, `ok` doesn't depend on `c`. Only scope 2's
  written-out callees include the conditions that decide which `return` runs.
- Identical source text is one input, even if its operands change in between.
- Every `not` is a statement, even directly on an input.
- Only positional arguments are matched to parameters. A Python keyword
  argument's parameter becomes one input.
- Python `match` statements contribute only their guards.
- Scope 2 writes out every boolean-returning function, not only pure boolean
  ones. DLP 57 counts only executions of boolean value operations as what they
  compute, and real code has almost no pure boolean functions, so scope 1 is
  the closer match to how DLP 57 counts a program written the way these
  codebases are written. Scope 2 shows how big the logic is when every
  boolean helper counts as what it computes.

## Results

The units are the pieces, and the functions that have at least one boolean
statement. Shares are of those units. Between a sixth and a third of all
functions have boolean logic, so as a share of all functions, each share is
that much smaller.

| Codebase | Functions | With boolean logic | Pure boolean functions | Calls in logic resolved |
|---|---:|---:|---:|---:|
| cpython | 17878 | 3793 | 0 | 968 (28.27%) of 3424 |
| django | 10115 | 2219 | 0 | 445 (21.11%) of 2108 |
| mypy | 8721 | 2384 | 0 | 2239 (42.43%) of 5277 |
| saleor | 10438 | 2046 | 0 | 333 (41.62%) of 800 |
| odoo | 39464 | 11954 | 0 | 2611 (30.20%) of 8646 |
| homeassistant | 77662 | 12771 | 0 | 1922 (32.91%) of 5840 |
| go | 38522 | 9721 | 0 | 10851 (77.72%) of 13962 |
| cockroach | 63589 | 13792 | 4 | 8164 (53.74%) of 15193 |
| tidb | 37974 | 9881 | 2 | 6176 (67.94%) of 9090 |
| kubernetes | 37933 | 8647 | 1 | 4961 (58.03%) of 8549 |
| gitea | 12188 | 3230 | 0 | 2881 (68.81%) of 4187 |

### Scope 1 (within a function), per piece of logic

Inputs and statements are median / 90th / 99th / 99.9th percentile / max.

| Codebase | Units | Inputs | Statements | > 20 inputs | > 256 statements | Either |
|---|---:|---|---|---:|---:|---:|
| cpython | 6493 | 2 / 2 / 4 / 9 / 19 | 1 / 2 / 4 / 9 / 21 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |
| django | 3596 | 2 / 3 / 5 / 9 / 11 | 1 / 3 / 5 / 10 / 13 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |
| mypy | 5358 | 2 / 3 / 6 / 10 / 12 | 1 / 3 / 7 / 13 / 19 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |
| saleor | 2889 | 1 / 2 / 4 / 6 / 16 | 1 / 2 / 4 / 9 / 21 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |
| odoo | 20855 | 2 / 3 / 5 / 9 / 19 | 1 / 3 / 6 / 10 / 24 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |
| homeassistant | 18388 | 2 / 3 / 5 / 7 / 14 | 1 / 2 / 5 / 10 / 16 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |
| go | 21402 | 2 / 3 / 6 / 10 / 32 | 1 / 3 / 6 / 13 / 57 | 5 (0.02%) | 0 (0.00%) | 5 (0.02%) |
| cockroach | 25212 | 2 / 2 / 5 / 10 / 83 | 1 / 2 / 5 / 13 / 83 | 5 (0.02%) | 0 (0.00%) | 5 (0.02%) |
| tidb | 18309 | 2 / 3 / 5 / 10 / 20 | 1 / 2 / 5 / 11 / 24 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |
| kubernetes | 15376 | 2 / 2 / 4 / 8 / 14 | 1 / 2 / 4 / 9 / 20 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |
| gitea | 5715 | 2 / 3 / 5 / 9 / 17 | 1 / 2 / 5 / 11 / 18 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |

### Scope 1 (within a function), per function

Inputs and statements are median / 90th / 99th / 99.9th percentile / max.

| Codebase | Units | Inputs | Statements | > 20 inputs | > 256 statements | Either |
|---|---:|---|---|---:|---:|---:|
| cpython | 3793 | 2 / 5 / 13 / 21 / 33 | 1 / 4 / 12 / 24 / 32 | 5 (0.13%) | 0 (0.00%) | 5 (0.13%) |
| django | 2219 | 2 / 5 / 13 / 24 / 38 | 1 / 5 / 14 / 30 / 61 | 5 (0.23%) | 0 (0.00%) | 5 (0.23%) |
| mypy | 2384 | 3 / 9 / 24 / 40 / 45 | 2 / 8 / 25 / 44 / 50 | 40 (1.68%) | 0 (0.00%) | 40 (1.68%) |
| saleor | 2046 | 2 / 4 / 8 / 15 / 19 | 1 / 3 / 9 / 14 / 21 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) |
| odoo | 11954 | 2 / 6 / 15 / 29 / 43 | 2 / 5 / 15 / 32 / 57 | 45 (0.38%) | 0 (0.00%) | 45 (0.38%) |
| homeassistant | 12771 | 2 / 4 / 11 / 21 / 63 | 1 / 4 / 10 / 22 / 51 | 14 (0.11%) | 0 (0.00%) | 14 (0.11%) |
| go | 9721 | 2 / 8 / 24 / 57 / 174 | 2 / 7 / 25 / 60 / 190 | 138 (1.42%) | 0 (0.00%) | 138 (1.42%) |
| cockroach | 13792 | 2 / 5 / 14 / 34 / 91 | 1 / 5 / 15 / 38 / 186 | 55 (0.40%) | 0 (0.00%) | 55 (0.40%) |
| tidb | 9881 | 2 / 6 / 16 / 34 / 59 | 2 / 5 / 17 / 38 / 111 | 35 (0.35%) | 0 (0.00%) | 35 (0.35%) |
| kubernetes | 8647 | 2 / 5 / 13 / 26 / 60 | 1 / 5 / 12 / 28 / 52 | 23 (0.27%) | 0 (0.00%) | 23 (0.27%) |
| gitea | 3230 | 2 / 6 / 14 / 25 / 41 | 2 / 5 / 14 / 35 / 46 | 7 (0.22%) | 0 (0.00%) | 7 (0.22%) |

### Scope 2 (across calls), per piece of logic

Inputs and statements are median / 90th / 99th / 99.9th percentile / max.

| Codebase | Units | Inputs | Statements | > 20 inputs | > 256 statements | Either | Depth cap | Recursion stop | Size cap | Expansion depth |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| cpython | 6651 | 2 / 3 / 7 / 15 / 28 | 1 / 2 / 8 / 20 / 32 | 3 (0.05%) | 0 (0.00%) | 3 (0.05%) | 0 (0.00%) | 4 (0.06%) | 0 (0.00%) | 0 / 0 / 2 / 3 / 4 |
| django | 3668 | 2 / 3 / 6 / 11 / 21 | 1 / 3 / 7 / 15 / 31 | 2 (0.05%) | 0 (0.00%) | 2 (0.05%) | 0 (0.00%) | 21 (0.57%) | 0 (0.00%) | 0 / 0 / 2 / 2 / 3 |
| mypy | 5910 | 2 / 6 / 43 / 350 / 429 | 1 / 7 / 57 / 602 / 693 | 146 (2.47%) | 14 (0.24%) | 146 (2.47%) | 0 (0.00%) | 83 (1.40%) | 0 (0.00%) | 0 / 1 / 3 / 5 / 6 |
| saleor | 2976 | 1 / 3 / 6 / 8 / 16 | 1 / 3 / 9 / 16 / 21 | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 1 (0.03%) | 0 (0.00%) | 0 / 0 / 2 / 3 / 3 |
| odoo | 21334 | 2 / 3 / 10 / 16 / 29 | 1 / 3 / 11 / 21 / 73 | 7 (0.03%) | 0 (0.00%) | 7 (0.03%) | 0 (0.00%) | 7 (0.03%) | 0 (0.00%) | 0 / 0 / 3 / 4 / 5 |
| homeassistant | 18844 | 2 / 3 / 6 / 14 / 35 | 1 / 3 / 7 / 15 / 42 | 10 (0.05%) | 0 (0.00%) | 10 (0.05%) | 0 (0.00%) | 10 (0.05%) | 0 (0.00%) | 0 / 0 / 2 / 3 / 6 |
| go | 23777 | 2 / 5 / 39 / 164 / 334 | 1 / 6 / 48 / 303 / 769 | 585 (2.46%) | 25 (0.11%) | 585 (2.46%) | 0 (0.00%) | 639 (2.69%) | 0 (0.00%) | 0 / 2 / 4 / 5 / 7 |
| cockroach | 26958 | 2 / 3 / 11 / 45 / 157 | 1 / 3 / 14 / 53 / 254 | 116 (0.43%) | 0 (0.00%) | 116 (0.43%) | 0 (0.00%) | 221 (0.82%) | 0 (0.00%) | 0 / 1 / 3 / 4 / 7 |
| tidb | 19652 | 2 / 4 / 17 / 54 / 820 | 1 / 4 / 20 / 69 / 841 | 154 (0.78%) | 4 (0.02%) | 154 (0.78%) | 0 (0.00%) | 274 (1.39%) | 0 (0.00%) | 0 / 1 / 3 / 4 / 6 |
| kubernetes | 16839 | 2 / 3 / 10 / 34 / 43 | 1 / 4 / 12 / 39 / 54 | 41 (0.24%) | 0 (0.00%) | 41 (0.24%) | 0 (0.00%) | 84 (0.50%) | 0 (0.00%) | 0 / 1 / 2 / 4 / 6 |
| gitea | 6067 | 2 / 4 / 10 / 19 / 36 | 1 / 4 / 13 / 21 / 47 | 4 (0.07%) | 0 (0.00%) | 4 (0.07%) | 0 (0.00%) | 13 (0.21%) | 0 (0.00%) | 0 / 1 / 3 / 4 / 5 |

### Scope 2 (across calls), per function

Inputs and statements are median / 90th / 99th / 99.9th percentile / max.

| Codebase | Units | Inputs | Statements | > 20 inputs | > 256 statements | Either | Depth cap | Recursion stop | Size cap | Expansion depth |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| cpython | 3854 | 2 / 6 / 16 / 33 / 42 | 1 / 5 / 18 / 35 / 58 | 21 (0.54%) | 0 (0.00%) | 21 (0.54%) | 0 (0.00%) | 6 (0.16%) | 0 (0.00%) | 0 / 1 / 2 / 3 / 4 |
| django | 2253 | 2 / 6 / 16 / 27 / 48 | 2 / 5 / 17 / 37 / 80 | 12 (0.53%) | 0 (0.00%) | 12 (0.53%) | 0 (0.00%) | 19 (0.84%) | 0 (0.00%) | 0 / 1 / 2 / 2 / 3 |
| mypy | 2492 | 3 / 16 / 103 / 422 / 1200 | 2 / 17 / 146 / 1043 / 2110 | 193 (7.74%) | 15 (0.60%) | 193 (7.74%) | 0 (0.00%) | 62 (2.49%) | 0 (0.00%) | 0 / 2 / 3 / 5 / 6 |
| saleor | 2094 | 2 / 4 / 10 / 17 / 21 | 1 / 4 / 11 / 21 / 26 | 1 (0.05%) | 0 (0.00%) | 1 (0.05%) | 0 (0.00%) | 2 (0.10%) | 0 (0.00%) | 0 / 1 / 2 / 3 / 3 |
| odoo | 12163 | 2 / 7 / 18 / 34 / 64 | 2 / 7 / 20 / 42 / 81 | 82 (0.67%) | 0 (0.00%) | 82 (0.67%) | 0 (0.00%) | 7 (0.06%) | 0 (0.00%) | 0 / 1 / 3 / 4 / 5 |
| homeassistant | 12980 | 2 / 5 / 12 / 27 / 64 | 1 / 4 / 12 / 30 / 101 | 32 (0.25%) | 0 (0.00%) | 32 (0.25%) | 0 (0.00%) | 10 (0.08%) | 0 (0.00%) | 0 / 1 / 2 / 3 / 6 |
| go | 10304 | 3 / 16 / 69 / 355 / 2005 | 2 / 16 / 85 / 378 / 5314 | 795 (7.72%) | 23 (0.22%) | 795 (7.72%) | 0 (0.00%) | 403 (3.91%) | 1 (0.01%) | 0 / 2 / 4 / 6 / 7 |
| cockroach | 14374 | 2 / 7 / 29 / 83 / 162 | 2 / 7 / 33 / 108 / 268 | 239 (1.66%) | 2 (0.01%) | 239 (1.66%) | 0 (0.00%) | 194 (1.35%) | 0 (0.00%) | 0 / 1 / 3 / 4 / 7 |
| tidb | 10284 | 2 / 9 / 40 / 94 / 821 | 2 / 8 / 50 / 153 / 842 | 293 (2.85%) | 7 (0.07%) | 293 (2.85%) | 0 (0.00%) | 193 (1.88%) | 0 (0.00%) | 0 / 1 / 3 / 5 / 6 |
| kubernetes | 9182 | 2 / 7 / 23 / 44 / 107 | 2 / 8 / 27 / 55 / 169 | 113 (1.23%) | 0 (0.00%) | 113 (1.23%) | 0 (0.00%) | 61 (0.66%) | 0 (0.00%) | 0 / 1 / 3 / 4 / 6 |
| gitea | 3355 | 3 / 8 / 23 / 43 / 61 | 2 / 9 / 25 / 65 / 73 | 41 (1.22%) | 0 (0.00%) | 41 (1.22%) | 0 (0.00%) | 11 (0.33%) | 0 (0.00%) | 0 / 2 / 4 / 5 / 5 |

## The Largest Logic

### Within a function: pieces

Every piece over 20 inputs is one long `||` or `&&` chain:

- `pkg/sql/opt/memo/memo.go:490` `IsStale` (CockroachDB): 83 inputs, 83
  statements. The cached plan is stale if any of about 80 session settings
  differs from the one it was planned with:
  `m.reorderJoinsLimit != ... || m.zigzagJoinEnabled != ... || ...`.
- `reflect/value.go:1778` `isZero` (Go): 32 inputs, 31 statements, an unrolled
  `w[0] != 0 || w[1] != 0 || ... || w[31] != 0`.
- `debug/pe/file.go:531` and `:585` `readOptionalHeader` (Go): 29 and 28 inputs,
  57 and 55 statements, `!read(&oh32.MajorLinkerVersion) || !read(...) || ...`
  for each header field.
- `cmd/internal/obj/x86/asm6.go:1912` `fusedJump` (Go): 28 inputs, 31
  statements, over opcode comparisons.
- `pkg/sql/roleoption/role_option.go:332` `CheckRoleOptionConflicts`
  (CockroachDB): 29 inputs, 29 statements, one `a && b` per pair of
  conflicting role options, `||`'d together.
- `pkg/util/ulid/ulid.go:161` `parse` (CockroachDB): 27 inputs, 26 statements,
  `dec[v[0]] == 0xFF || ... || dec[v[25]] == 0xFF`.

### Within a function: totals

Functions over 20 inputs have many separate conditions, each small:

- `cmd/internal/obj/arm64/asm7.go:3689` `asmout` (Go): 174 inputs, 190
  statements, the arm64 instruction encoder, one large `switch` with its own
  conditions in each case.
- `cmd/compile/internal/ssacompile/regalloc.go:955` `regalloc` (Go): 84 inputs,
  99 statements.
- `pkg/sql/opt/memo/memo.go:485` `IsStale` (CockroachDB): 91 inputs, 88
  statements, and `pkg/storage/sst.go:468` `CheckSSTConflicts`: 69 inputs, 186
  statements.
- `homeassistant/helpers/device_registry.py:3274` `_async_update_device`: 63
  inputs, 51 statements.
- `pkg/kubelet/apis/config/validation/validation.go:57`
  `ValidateKubeletConfiguration` (Kubernetes): 60 inputs, 52 statements, one
  check per configuration field.
- `pkg/executor/statement_ru_plan_walk.go:538`
  `calculateStatementRUPlanChildFirst` (TiDB): 59 inputs, 111 statements.
- `addons/account/models/account_move.py:6157` `_post` (Odoo): 43 inputs.
- `routers/api/v1/repo/repo.go:721` `updateRepoUnits` (Gitea): 41 inputs, 46
  statements, a request handler that checks each repository option.
- `django/db/backends/base/schema.py:984` `_alter_field` (Django): 38 inputs, 61
  statements, one condition per kind of column change.

### Across calls

Written-out calls grow the logic most where predicates call other predicates,
and where one value is compared against long tables of constants:

- `cmd/internal/obj/arm64/asm7.go:2077` `loadStoreClass` (Go): hits the size
  cap, with over 2,000 inputs and 5,000 statements. It calls `cmp(a, b)` with
  many different arguments, and `cmp` (line 2431) is a `switch` that compares
  two operand classes against about 140 constants, 378 statements written out.
  `oplook` (line 2320) writes out to 638 inputs and 1,590 statements the same
  way.
- `pkg/expression/infer_pushdown.go:111` `canScalarFuncPushDown` (TiDB): 821
  inputs, 842 statements. It calls `scalarExprSupportedByTiDB`,
  `scalarExprSupportedByTiKV` and `scalarExprSupportedByFlash`, each a `switch`
  over hundreds of SQL function names.
- `mypy/checkexpr.py:3754` `visit_comparison_expr` (mypy): 1,200 inputs, 2,110
  statements per function, and 429 inputs, 693 statements in one piece, through
  `dangerous_comparison` and `is_overlapping_types` (601 statements written
  out).
- `cmd/compile/internal/walk/range.go:41` `walkRange` (Go): one `if
  isMapClear(n)` writes out to 334 inputs and 355 statements, through
  `ir.SameSafeExpr`, `types.Identical` and `constant.Compare`.
- `pkg/sql/opt/idxconstraint/index_constraints.go:1104` `simplifyFilter`
  (CockroachDB): 162 inputs, 259 statements, through `makeSpansForExpr` (253
  statements written out).
- `staging/src/k8s.io/code-generator/cmd/validation-gen/generators/validation.go:1226`
  `emitValidationForChild` (Kubernetes): 107 inputs, 169 statements.

The application codebases (Saleor, Odoo, Home Assistant, Gitea, Django) grow
little across calls: their largest function writes out to 26 to 101 statements.
Their boolean helpers are mostly one comparison or one field.

### What the inputs are

In the largest logic, most inputs are comparisons of one value against a
constant: `b == C_REG`, `op == AADD`, `sf.FuncName.L == ast.Cast`. Each such
comparison is a separate boolean input, though all of them read the same value.
`cmp`'s 142 inputs are comparisons of just two integers, and most of TiDB's
821 compare the SQL function's name, `sf.FuncName.L`, against a constant
(`switch` case values).

## Files

- `clone.sh` fetches each codebase into `work/` at the commit measured.
- `go_frontend/` and `py_frontend.py` write the intermediate form of each
  function, one JSON object per line, into `work/ir/`.
- `analyze.py` reads that form and writes `results/<codebase>.json`: the
  distributions, the counts over each limit, how expansion stopped, and up to
  400 units over a limit with their `file:line`.
- `summarize.py` prints the tables above from `results/`.
- `show.py` and `show_calls.py` print one function's pieces, or the calls that
  scope 2 writes out from it, for checking the analysis by hand.
- `run.sh` runs the frontends and the analyzer for the named codebases, each
  under `timeout -s KILL 120 prlimit --as=4294967296`. Every frontend run took
  under 4 seconds and every analysis under 2; all eleven codebases take about 15
  seconds in total.

To reproduce:

```sh
./clone.sh
./run.sh cpython django mypy saleor odoo homeassistant go cockroach tidb kubernetes gitea
uv run --frozen python -I summarize.py results/{cpython,django,mypy,saleor,odoo,homeassistant,go,cockroach,tidb,kubernetes,gitea}.json
```

### The intermediate form

Each function is `{file, line, name, module, cls, method, params, nres,
pure_candidate, returns_bool, nodes, roots, rets, guards}`. `nodes` is a list
in which each node is one of:

- `["s", op, children, line]`: a boolean statement;
- `["v", name, definitions]`: a local variable and its definitions;
- `["l", text, reads_params]`: an input;
- `["p", index]`: a parameter;
- `["c", text, reads_params, [kind, name, qualifier], arguments, receiver]`: a
  call;
- `["k"]`: a literal.

`roots` are the conditions of `if`, `while`, `for`, `assert` and similar,
`rets` the returned values, and `guards` the conditions that decide which
`return` runs.
