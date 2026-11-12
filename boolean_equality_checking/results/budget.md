# DLP 59's Budget

`beq`'s default, `--method auto`:

- truth tables up to 16 boolean inputs, and up to 20 for a value operation that executes one of more than six views;
- OBDDs with complement edges otherwise, inputs in first-reached order;
- a budget of 1,000,000,000 steps per value operation (`StepBudget` in `src/bdd.hpp`, `--step_budget`);
- a value operation of at most 256 boolean statements and 20 inputs whose OBDDs go over the budget is checked with truth tables instead, so it always compiles.

Raw: `budget_real_steps.jsonl` (real code, with the budget), `budget_runs.jsonl.gz` (generated shapes, without a budget, and again with it).

## The step unit

| Work | Steps |
|---|---|
| A BDD operation on two diagrams that aren't answers, equal, or opposite | 6 |
| A new BDD node | 20 |
| A node or candidate of the match search | 1 |
| A value evaluated on a new sample | 30 |
| A word of truth tables compared in an exact check, or two computed | 1 |

Least squares on 341 generated value operations checked with OBDDs, weighted by relative error: a BDD operation 14.6 ns, a new node 52.5 ns, a search node 2.5 ns, a sampled value 69 ns. With the weights above a step is 2.4 ns at the median (5th–95th percentile 2.0–6.0 ns), half within 9%. The slow tail is diagrams of tens of millions of nodes: mypy's `visit_comparison_expr` (2,011 statements) spent its 1e9 steps in 8.5 s. On truth tables, a 384-statement value operation at 16 inputs spent them in 3.7 s.

## Real programs

Every unit of the real-code study past its limits, as one operation writing every value nothing else reads, checked with the rule and the budget.

- Each function's own logic (scope 1): 376 units, all compile; the most was CockroachDB's IsStale (91 inputs, 88 statements), 3.1e7 steps, 0.18 s.
- With called functions written out (scope 2): 2,889 units, 2,872 compile (the largest 1,290 inputs and 1,270 statements at 9.97e8 steps, 5.6 s), 17 go over:
  - within 256 statements (9): CockroachDB `CanMergeAggs` (214 inputs, 106 statements); Go `elimIf` (203, 127), `exprCheckPtr` (206, 129), `buildDefUses` (lone call, 303, 151), `getLatticeCell` (303, 152; 304, 152), `visitValue` (303, 152), `buildModeInit` (286, 206); TiDB `getModifyColumnType` (221, 151);
  - past 256 statements (8): Go `serveConn` (554, 278; 558, 279), `mem2reg` (512, 301), `buildDefUses` (606, 303; 910, 454); TiDB `scalarExprSupportedByTiKV` (808, 415, twice); mypy `visit_comparison_expr` (2,078, 2,011).
- Of the 87 units past 256 statements, 79 compile, up to 5,315 statements (Go `loadStore`, 6,851 inputs, 0.06 s).
- The budget error at its real size: Go `buildModeInit` stops with `["budget", 387]` after 1.6 s.

## Generated value operations

Past the old limits, these went over: the middle bit of 13 × 13 and 14 × 14 products (26 and 28 inputs, 335 and 389 statements); one of three random value operations of 256 statements at 30 inputs, and at 32; two of three random ones of about 380 statements at 17 inputs, and one of 384 statements at 16 inputs (on truth tables). The middle bit of 12 × 12 (24 inputs, 285 statements) compiles at 6.7e8 steps, 5.8 s; of 11 × 11, 9.1e7; bits 10 and 11 of 11 × 11 joined by `and`, 1.09e8. `budget_runs.jsonl.gz` has every shape's steps by kind and times.

## Exactness

- The rule against truth tables (up to 26 inputs) and SAT sweeping on every shape: 521 value operations compared with the budget and 554 without, 0 disagreements.
- Falling back: value operations of 18–20 inputs given a budget of 1,000 steps were checked with truth tables and found the same errors; ones of 24 inputs stopped with the budget's error.
- Executions of value operations checked with OBDDs (17–24 views), recorded as diagrams with interchangeable views from them: three programs, 198 value operations, against truth tables: 0 disagreements.
- The 96 reduction cases fix the same as with `--method tt`.

## Whole programs

| Program | Check, tables / rule | Median edit | Fix |
|---|---|---|---|
| 14,897 value operations | 1.89 / 2.00 s | 0.11 / 0.12 ms | 15.7 / 16.3 s |
| 148,858 value operations | 19.1 / 19.9 s | 0.10 / 0.10 ms | 158.8 / 160.6 s |
| 1,995 value operations, mostly 16–20 inputs | 19.7 / 22.2 s, 228 / 208 MB | 9.3 / 10.8 ms | 53.9 / 54.2 s |

Fixing wrote the same programs as with truth tables, and every fixed program compiles. On the third, 255 value operations use OBDDs and 1,740 truth tables; none went over the budget.
