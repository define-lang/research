# Acceptance Rule and Measurements (No Step Budget)

`beq`'s default (`--method auto`) uses **no step budget** (`--step_budget 0` by default):

- **Guaranteed envelope:** every value operation with at most **256 boolean statements** and at most **20 boolean inputs** always compiles (checked with truth tables when `I ≤ 16`, or `I ≤ 20` with a wide execution of more than 6 views, or via fallback to truth tables if ROBDDs exceed the node limit).
- **Canonical shared ROBDD node limit past the guaranteed envelope:** past 256 boolean statements or 20 boolean inputs, a value operation is checked with complement-edge ROBDDs in deterministic first-reached DFS input order (`input_order`) and is accepted if and only if the canonical shared ROBDD of all its boolean statements has at most **4,000,000 reachable non-terminal nodes** (`--bdd_nodes 4000000`).

The acceptance boundary is a pure mathematical property of the value operation's DAG and input order: it is deterministic across machines and compilers, Forward Compatible when raised, and easy to communicate to programmers.

Raw data: `budget_real_steps.jsonl` (all 3,265 real-code units past the old limits, checked with `--method auto` and no step budget). The superseded preliminary step-budget runs (taken before fixing `I ≥ 64` shift UB, ROBDD operations, and `Matcher` search blowups) are archived in `preliminary/budget_real_steps_before_fixes.jsonl` and `preliminary/budget_runs_before_fixes.jsonl.gz`.

## Real programs (all 11 codebases)

Every unit of the real-code study past the old limits (`S > 256` or `I > 20`), checked with `--method auto`, no step budget, 4,000,000 canonical shared ROBDD node limit, and a 10 s / 4 GB safety cap:

- **Total units checked:** 3,265 (376 scope 1 + 2,889 scope 2). All 3,265 ran in 2.5 s total wall time across cores.
- **Completed cleanly:** **3,264 / 3,265 (99.97%)** — **0 timeouts, 0 OOMs**.
  - Median time: **0.35 ms** | 95th percentile: **4.26 ms** | 99th percentile: **21.86 ms** | max: **1.19 s**.
  - Median canonical ROBDD nodes: **124** | 95th percentile: **1,788** | 99th percentile: **20,335** | max passing: **3,893,860**.
- **Hit the 4,000,000 canonical ROBDD node limit:** **1 / 3,265 (0.03%)**:
  - `mypy` scope 2 `mypy/checkexpr.py:3754 visit_comparison_expr` (`I = 2,078`, `S = 2,011`; uncapped ROBDD size 44,412,700 nodes, 9.2 s).
- **All 16 other units that previously exceeded the 1-billion step budget now pass cleanly** (their earlier blowup was caused by `uint64_t` shift UB for `I ≥ 64` collapsing all samples):
  - `go` `buildModeInit` (`I = 286`, `S = 206`): **71 ms**, 3,872 BDD nodes (was > 1e9 steps / 1.6 s).
  - `go` `mem2reg` (`I = 512`, `S = 301`): **162 ms**, 1,116 BDD nodes (was 9.96e8 steps).
  - `go` `serveConn` (`I = 554–558`, `S = 278–279`): **317–323 ms**, 831–836 BDD nodes.
  - `tidb` `scalarExprSupportedByTiDB` (`I = 808`, `S = 415`): **905–912 ms**, 1,566 BDD nodes.
  - `go` `buildDefUses` (`I = 910`, `S = 454`): **1.19 s**, 1,708 BDD nodes.
  - `mypy` `narrow_declared_type` (`I = 1,290`, `S = 1,270`): **749 ms**, 3,893,860 BDD nodes.
  - Largest real-code unit (`go` `loadStoreClass`, `I = 6,851`, `S = 5,315`): **10 ms**, 86,527 BDD nodes.

## Generated and adversarial workloads

All **277** generated workloads in `work/methods/*.prog` (`dense`, `xor_heavy`, `parity`, `read_once`, `long` up to 1,024 statements, `real`, and multipliers up to 28×28) were checked with `--method auto`, no step budget, and the 4,000,000 canonical ROBDD node limit:

- **277 / 277 finished with 0 timeouts and 0 OOMs** (slowest file: `xor_heavy_56_256.prog`, 2.15 s, 319 MB RSS).
- Worst-case `Matcher` benchmarks that previously timed out or used > 500 MB RAM:
  - `dense_8_256.prog`: **1.34 s / 538 MB** → **0.077 s / 17.2 MB**.
  - `dense_48_256.prog`: **> 10 s timeout** → **0.078 s / 42.9 MB**.
  - `xor_heavy_22_256.prog`: **> 10 s timeout** → **0.047 s / 27.0 MB**.
  - `long_62_1024.prog` (3 ops × 1,024 statements): **1.79 s / 89.0 MB**.
- Exponential-BDD workloads (`multiplier_30` through `multiplier_56`, and 5 of 9 `xor_heavy_48..62_256` ops) hit the 4,000,000 canonical ROBDD node limit cleanly in **≤ 0.92 s** and **≤ 320 MB RSS**.

## Whole programs

Checked with `--method auto` (no step budget) on the generated whole programs from `full_algorithm_experiment.py`:

| Program | Check wall time | `tables` | `matches` + `spellings` | Peak RSS |
| --- | --- | --- | --- | --- |
| `ops_15k` (14,897 ops) | **1.34 s** (was 1.89–2.00 s) | 54 ms | 627 ms (was 1.45 s) | 84 MB |
| `ops_2k_wide` (1,995 ops, 16–20 inputs) | **12.26 s** (was 19.6–22.2 s) | 9.17 s (lookups 4.90 s, was 10.0 s) | 1.02 s (was 4.78 s) | 188 MB |

## Verification

- `reference_test.py` verifies exact agreement across `--method tt`, `--method bdd`, `--method auto`, `--plain 1`, and the independent brute-force checker `gen/program_check.py`, plus `I = 64..300`, `I = 4,500` / `> 8,192` pool literals, `drop_views` on `I > 20` and `xor(u1, u2)`, `--mode registry` on `I > 16`, wide `8 × 8` transpose lookups, BDD Chow/Walsh symmetry grouping, and `--mode fix --keep_searches 1 --check_search 1`.
