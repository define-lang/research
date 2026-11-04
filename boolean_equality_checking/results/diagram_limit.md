# The Decision Diagram Limit

DLP 57's limit past twenty boolean inputs: a decision diagram of at most 1,048,576 nodes, counted canonically (`src/diagram.hpp`, `beq program --method diagram|auto`). Raw runs: `diagram_runs.jsonl.gz`, `diagram_real_counts.jsonl`; per-method tables: `diagram_tables.md`.

## Real programs

Every unit of the real-code study past its limits (split_experiment.over_limit_units), written as one operation writing every value nothing else reads, counted with `--method diagram --diagram_limit 67108864 --statement_limit 0 --matches 0`.

| Scope | Units | Past 20 inputs | At most 256 statements | Within 2^20 nodes | Median / p90 / p99 / max nodes | Largest |
|---|---|---|---|---|---|---|
| 1 | 376 | 376 | 376 | 376 (all 376 of those within 256 statements: 376) | 46 / 113 / 527 / 3495 | cockroach pkg/sql/opt/memo/memo.go:485 IsStale: 91 inputs, 88 statements, 3495 nodes; within 256 statements: cockroach pkg/sql/opt/memo/memo.go:485 IsStale, 91 inputs, 88 statements, 3495 nodes |
| 2 | 2889 | 2888 | 2802 | 2887 (all 2802 of those within 256 statements: 2802) | 144 / 1136 / 28110 / 5896430 | mypy mypy/meet.py:118 narrow_declared_type: 1290 inputs, 1270 statements, 5896430 nodes; within 256 statements: go log/slog/handler.go:561 appendTwoStrings, 162 inputs, 132 statements, 30340 nodes |

Over the 10 s cap to count: 1 (mypy mypy/checkexpr.py:3754 visit_comparison_expr).

Scope 1 is each function's own boolean logic, scope 2 has the functions it calls written out (pieces and functions both counted, as in the study). Scope 1 has 376 units, not the study's 377: one has no boolean statement once written out.

## Generated value operations

Each point is three value operations (one for the read-once chain and the multiplier), checked three times; `diagram_tables.md` has every method at every point. Diagram nodes over the first run's operations, and the slowest whole check of a value operation within the limit:

| Shape | Nodes median / p90 / max | Slowest check within the limit | Over the 10 s cap (3 operations) |
|---|---|---|---|
| dense, 32 statements | 356 / 638 / 875 | 0.04 s (62 inputs, 394 nodes) | |
| dense, 64 statements | 1,896 / 3,393 / 6,687 | 0.12 s (48 inputs) | |
| dense, 128 statements | 6,368 / 50,905 / 351,030 | 6.1 s (62 inputs, 351,030 nodes) | |
| dense, 256 statements | 9,900 / 49,561 / 92,991 | 6.5 s (30 inputs, 67,158 nodes) | 48 inputs (50,487–570,559 nodes) |
| parity, 64 statements | 1,475 / 3,333 / 4,318 | 0.01 s | |
| parity, 256 statements | 51,607 / 140,642 / 199,137 | 0.12 s | |
| read-once `or` chain | 350 / 1,595 / 1,952 | 0.03 s | |
| real-code cones | 189 / 406 / 527 | 0.01 s | |
| xor-heavy, 64 statements | 5,915 / 11,142 / 26,310 | 0.3 s | |
| xor-heavy, 256 statements | 42,212 / 179,592 / 213,117 | 2.0 s (19 inputs) | 22 inputs (74,860–302,005 nodes) |
| middle bit of a product | 174,098 at 20 inputs, 879,749 at 22 | 0.87 s (22 inputs) | |

Building and counting the diagram took at most 0.15 s within the limit (the 22-input product bit); the rest of each slow check is the search for matches.

## Products

| Operation | Inputs | Statements | Nodes |
|---|---|---|---|
| bit 10 of 11 × 11 | 22 | 201 | 299,465 |
| bit 11 of 11 × 11 | 22 | 239 | 879,749 |
| bits 10 and 11 of 11 × 11, `and` | 22 | 241 | 1,141,850 (past the limit at statement 240, the `xor` that finishes bit 11) |
| bit 12 of 11 × 11 | 22 | 275 | 1,973,720 |
| bit 11 of 12 × 12 | 24 | 243 | 802,475 |
| bit 12 of 12 × 12 | 24 | 285 | 3,602,300 |

Partial products with `and`, columns reduced with `xor` for sums and `maj` (or `and`) for carries, statements in the order the generator writes them (`methods_experiment.multiplier`).

## The budget from 17 to 20 inputs

Per operation, the decision diagram's check time over the truth tables', by nodes for each 64 combinations of the boolean inputs (127 operations at 16–20 inputs):

| Budget (nodes per 64 combinations) | Operations under it | Slower than tables | Total, 17–20 inputs |
|---|---|---|---|
| tables only | | | 11.62 s |
| 0.5 | 58 | 8 | 10.15 s |
| 1 | 73 | 12 | 9.94 s |
| 2 | 84 | 18 | 8.10 s |
| 4 | 103 | 26 | 7.88 s |
| the faster method for each | | | 7.57 s |

At 2, every operation slower with the diagram took under 10 ms, within 1.6 times; the big losses (the product bits, xor-heavy at 256 statements) are at 10–70 nodes per 64 combinations. `beq` uses 2 (`--diagram_budget`), and keeps operations that execute value operations of more than six views on truth tables.

## Exactness

- `diagram` and `auto` against truth tables (`--input_limit 26`) and SAT sweeping on every shape: 1,164 operation comparisons in the final runs, 582 in the earlier one, 208 for `auto` at 16–24 inputs, 0 disagreements.
- Executions of value operations past twenty inputs: three generated programs (`gen/program.py`, 3 levels, 21–24 views), 198 operations with 559 executions of operations past twenty inputs, recorded as diagrams with interchangeable views from them, against truth tables up to 26 inputs, which record tables: 0 disagreements.

## Whole programs, with `--method auto`

| Program | Check, tables / auto | Median edit | Fix |
|---|---|---|---|
| 14,897 value operations | 1.89 / 1.85 s | 0.11 / 0.11 ms | 15.8 / 16.4 s |
| 148,858 value operations | 19.4 / 18.6 s | 0.10 / 0.11 ms | 159.9 / 164.2 s |
| 1,995 value operations, mostly 16–20 inputs | 20.1 / 20.0 s | 9.3 / 8.5 ms | 54.1 / 56.9 s |

Fixing wrote the same programs, and every fixed program compiles. On the wide program 255 of the 1,995 value operations use the diagram.
