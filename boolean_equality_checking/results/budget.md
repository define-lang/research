# Acceptance Rule and Measurements (No Step Budget)

`beq`'s default (`--method auto`) uses **no step budget** (`--step_budget 0` by default) and enforces Define's conservative, compiler-independent limits (DLPs 59–62):

- **Boolean input interface views (`--max_views 20`):** at most **20** boolean input interface views on any Value Operation (bounds every pure boolean Value Operation's contract to ≤ 128 KB truth table / ≤ 98,302 ROBDD nodes, and DLP 60 symmetry checking to ≤ 190 pairs).
- **Boolean statements (`--statement_limit 1`):** at most **256** boolean statements per Value Operation or Action (guarantees every pure boolean Value Operation fits unconditionally inside the `(256 statements, 20 inputs)` truth-table floor).
- **Boolean inputs (`--max_inputs 512`):** at most **512** boolean inputs per Value Operation or Action (`I ≤ 16`, or `I ≤ 20` with a wide execution of `> 6` views, via truth tables; `I ≤ 20` otherwise via ROBDDs with automatic truth-table fallback; `21 ≤ I ≤ 512` via ROBDDs).
- **Canonical shared ROBDD reachable-node limit (`--bdd_nodes 65536`):** past 20 boolean inputs (`21 ≤ I ≤ 512`), a Value Operation or Action is accepted if and only if the canonical shared ROBDD of all its boolean statements, under the deterministic first-reached DFS input order (`input_order`), has at most **65,536 (`2^16`) reachable non-terminal nodes** (with a 2× construction cap of 131,072 nodes, ~5–10 MB per parallel worker).
- **Fixed standard boolean operations (DLP 62):** `{and, not, or, xor, equal}` — all arity ≤ 2 and symmetric, reducing worst-case `Matcher` complexity to strictly `O(S * (I + S))` with zero backtracking.

The acceptance boundary is a pure syntactic and mathematical property of the value operation's DAG and input order: it is deterministic across machines and compilers, Forward Compatible when raised, and easy to communicate to programmers.

Raw data: `budget_real_steps.jsonl` (all 3,265 real-code units past the old limits, checked with `--method auto` and no step budget). The superseded preliminary step-budget runs (taken before fixing `I ≥ 64` shift UB, ROBDD operations, and `Matcher` search blowups) are archived in `preliminary/budget_real_steps_before_fixes.jsonl` and `preliminary/budget_runs_before_fixes.jsonl.gz`.

## Real programs (all 11 codebases)

Every unit of the real-code study past the old limits (`S > 256` or `I > 20`), checked with `--method auto`, no step budget, and a 10 s / 4 GB safety cap (`budget_real_steps.jsonl`):

- **Standalone functions (`scope=1`, 376 units):** **376 / 376 (100%)** pass _all_ conservative limits (`S ≤ 256`, `I ≤ 512`, `ROBDD ≤ 65,536`), with max `S = 184`, max `I + S = 358`, max ROBDD nodes **3,500**, and latency `< 1 ms`.
- **All units including `scope=2` inlining (3,265 units):**
  - **Under `ROBDD ≤ 65,536`:** **3,256 / 3,265 (99.72%)** have at most 65,536 canonical ROBDD nodes (only 9 large `scope=2` inlined units exceed 65,536 nodes; max passing under 65,536 is `go` `loadStorePairClass` with 36,919 nodes, 4.5 ms).
  - **Under `ROBDD ≤ 4,000,000` (historical uncapped ceiling check):** **3,264 / 3,265 (99.97%)** completed cleanly — **0 timeouts, 0 OOMs** — median **0.35 ms**, p95 **4.26 ms**, p99 **21.86 ms**, max **1.19 s** (median canonical ROBDD nodes **124**, p95 **1,788**, p99 **20,335**). Only `mypy` `scope=2` `visit_comparison_expr` (`I = 2,078`, `S = 2,011`, 44.4M nodes; 54 nodes as standalone `scope=1`) exceeded 4,000,000 nodes.

## Adversarial `Matcher` scaling (fixed standard set vs. arity-3 / arity-4)

Stress-testing `Matcher` on adversarial linear-BDD chains of `S` calls to an unregistered 3-input operation `u3(a, b, c) = (a and b) xor c` (`I = 2S + 1`, where nothing matches, so `Matcher` must prove no match exists across all `N = I + S` earlier values):

| Statements (`S`) | Inputs (`I`) | Fixed standard set (`and, not, or, xor, equal`) | Old arity-3 set (`+ implies, mux, maj`) | With arity-4 XOR-like op (`par4`) |
| --- | --- | --- | --- | --- |
| **256** | **513** | **0.030 s** (`matches` 11.0 ms, 16 MB RSS) | 0.11 s | Timeout (> 15 s) |
| 512 | 1,025 | **0.078 s** (`matches` 34.6 ms, 16 MB RSS) | 0.64 s | — |
| 1,024 | 2,049 | **0.28 s** (`matches` 135 ms, 17 MB RSS) | 4.72 s | — |
| 2,048 | 4,097 | **1.11 s** (`matches` 560 ms, 28 MB RSS) | Timeout (> 15 s) | — |
| 4,096 | 8,193 | **4.56 s** (`matches` 2.38 s, 56 MB RSS) | — | — |

With the fixed standard set `{and, not, or, xor, equal}`, match search scales strictly as `O(S * (I + S))` (4× time per 2× growth in `S` and `I`), eliminating both the `O(S * N^3)` arity-4 cliff and the `O(S * N^2)` arity-3 scaling.

## Generated and adversarial workloads (`work/methods/`)

All **276** generated workloads in `work/methods/*.prog` (`dense`, `xor_heavy`, `parity`, `read_once`, `long` up to 1,024 statements, `real`, and multipliers up to 28×28) checked with `--method auto`, no step budget, and the **65,536** canonical ROBDD node limit (`--bdd_nodes 65536`):

- **276 / 276 finished in 22.64 s total with 0 timeouts and 0 errors** (slowest file: `long_22_1024.prog`, 3 ops × 1,024 statements, **1.20 s**; peak RSS across all 276 files: **33.7 MB**, down from 319 MB at the 4,000,000-node limit).

## Whole programs

Checked with `--method auto` (no step budget, `--bdd_nodes 65536`, DLP 60 associative grouping, DLP 61 factoring, and DLP 62 fixed standard set `{and, not, or, xor, equal}`) on freshly generated and fixed whole programs (`gen/program.py`):

| Program | Check wall time | `tables` | `order` (incl. grouping & factoring) | `matches` + `spellings` | Peak RSS |
| --- | --- | --- | --- | --- | --- |
| `ops_15k_std` (14,926 ops) | **1.08 s** (was 1.34 s with 6 ops) | 50 ms | 110 ms | **240 ms** (was 627 ms) | 94 MB |
| `ops_2k_wide_std` (1,998 ops, 16–20 inputs) | **12.01 s** (was 12.26 s with 6 ops) | 9.54 s (`lookups` 4.98 s) | 95 ms | **330 ms** (was 1.02 s) | 194 MB |

## Verification

- `reference_test.py` (11 test groups) verifies exact agreement across `--method tt`, `--method bdd`, `--method auto`, `--plain 1`, and the independent brute-force checker `gen/program_check.py`, plus DLP 60 associative grouping, DLP 61 factoring of common terms, conservative limits (`max_views = 20`, `statement_limit = 256`, `max_inputs = 512`, `bdd_nodes = 65536`), `I = 64..300`, `I = 4,500` / `> 8,192` pool literals, `drop_views` on `I > 20` and `xor(u1, u2)`, wide `8 × 8` transpose lookups, BDD Chow/Walsh symmetry grouping, and `--mode fix --keep_searches 1 --check_search 1`.
- `gen/reduction_cases.py` verifies all 87 canonical reduction cases (including associative grouping and distributive factoring) against both `beq` and `gen/program_check.py` plus fixpoint idempotence.
- `bazelisk test //boolean_equality_checking/proof:all` verifies the Lean 4 termination proof (`proof/fixing_termination.lean`, theorem `dag_prog_terminates`, including `OpFix.factor`).
