# DLP 57's Budget

`beq`'s default. Truth tables up to 16 boolean inputs; past 16, OBDDs with complement edges within a budget of steps (`beq program --method auto`, `StepBudget` in `src/bdd.hpp`): a BDD operation past its trivial cases is 6 steps, a node or candidate of the match search 1, a value evaluated on a new sample 40. The budget is 40,000,000,000 steps. Raw: `budget_real_steps.jsonl` (real code), `budget_runs.jsonl.gz` (generated shapes, run without a budget).

## Steps against time

Least squares on every generated value operation checked with OBDDs taking at least 2 ms, weighted by relative error: a BDD operation 16.3 ns, a search node 2.6 ns, a sampled value 110 ns; with the weights 6, 1, 40 a step is about 2.6 ns, relative error median 10%, 90th percentile 31%, at most 89%.

## Real programs

Every unit of the real-code study past its limits (`split_experiment.over_limit_units`), as one operation writing every value nothing else reads, checked with the rule and no budget. Units of at most 16 inputs are on truth tables and aren't counted.

| Scope | Units | Steps median / 99th percentile / most | Slowest | Over 1e9 steps | Over 4e9 |
|---|---|---|---|---|---|
| 1 | 376 | 3.91e+05 / 3.28e+06 / 2.02e+07 | go debug/pe/file.go:485 readOptionalHeader: 58 inputs, 112 statements, 0.06 s | 0 | 0 |
| 2 | 2802 | 4.53e+05 / 3.37e+08 / 3.84e+09 | go cmd/go/internal/work/init.go:215 buildModeInit: 286 inputs, 206 statements, 8.47 s | 9 | 0 |

At most 256 statements only. Eight more took longer than the 10 s cap; all have more than 256 statements (278–2,011) and 512–2,078 inputs.

## Generated value operations

| Shape | Value operations | Steps median / most | Most steps: inputs, seconds | ns per step, median |
|---|---|---|---|---|
| dense, 32 statements | 51 | 9.29e+05 / 7.33e+06 | 62, 0.02 s | 2.6 |
| dense, 64 statements | 51 | 2.32e+06 / 9.27e+06 | 62, 0.03 s | 2.8 |
| dense, 128 statements | 51 | 2.3e+07 / 5.98e+08 | 62, 5.38 s | 2.7 |
| dense, 256 statements | 33 | 3.89e+08 / 1.73e+09 | 30, 6.84 s | 2.8 |
| multiplier | 3 | 2.52e+07 / 9.1e+07 | 22, 0.75 s | 3.5 |
| parity, 64 statements | 51 | 1.28e+06 / 2.94e+06 | 62, 0.02 s | 2.7 |
| parity, 256 statements | 51 | 1.58e+07 / 3.15e+07 | 28, 0.10 s | 2.6 |
| read_once | 17 | 9.47e+05 / 1.28e+07 | 62, 0.03 s | 2.2 |
| real | 20 | 6.52e+05 / 2.91e+06 | 28, 0.01 s | 2.2 |
| xor_heavy, 64 statements | 51 | 1.72e+06 / 1.69e+07 | 62, 0.10 s | 2.8 |
| xor_heavy, 256 statements | 15 | 3.14e+08 / 6.29e+08 | 20, 1.26 s | 2.4 |

The middle bit of the product of two 11-bit numbers (22 inputs, 239 statements): 9.1e7 steps, 0.75 s; bits 10 and 11 joined by `and` (241 statements): 1.09e8 steps, 0.96 s. Nothing measured within 256 statements and the 10 s cap for three value operations reached the budget.

## Exactness

- The rule against truth tables (up to 26 inputs) and SAT sweeping on every shape, the same value operations: 603 value operations compared, 0 disagreements (without a budget).
- Executions of value operations past 16 inputs, recorded as diagrams, with interchangeable views from them: three generated programs (3 levels, 17–24 views), 198 value operations, 606 executions of operations checked with OBDDs, against truth tables up to 26 inputs: 0 disagreements.
- The budget's error, with a budget of 10,000,000 steps: every value operation of a 24-input point went over at a statement of its own.

## Whole programs

| Program | Check, tables / rule | Median edit | Fix |
|---|---|---|---|
| 14,897 value operations | 1.89 / 1.96 s | 0.11 / 0.11 ms | 15.7 / 15.8 s |
| 148,858 value operations | 19.1 / 19.1 s | 0.10 / 0.11 ms | 158.8 / 160.1 s |
| 1,995 value operations, mostly 16–20 inputs | 19.7 / 46.5 s, 228 MB / 1.2 GB | 9.3 ms / over the 60 s cap | 53.9 s / over the 300 s cap |

The first two have at most 10 inputs per value operation, and fixing them wrote the same programs. The third has 1,271 value operations of 17–20 inputs, most executing value operations of 16–20 views. No value operation went over the budget.
