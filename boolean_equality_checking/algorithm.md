# Reference Algorithm for Boolean Logic Checking

This document specifies the reference algorithm implemented in `src/` (`beq program --method auto`) for checking and fixing Define's boolean logic rules (DLPs 59, 60, and 61). Every compiled component of Define produces a static, finite directed acyclic graph (DAG) with no execution cycles (DLP 9). Checking runs once per value operation in dependency order.

## 1. Input, Representation, and Output

Each value operation is analyzed into its boolean inputs and boolean statements:

- **Boolean inputs (`I`):** the value operation's boolean read views, followed in statement order by the boolean values produced by non-boolean statements (such as comparisons or executions of mixed value operations). Boolean inputs are treated as independent variables.
- **Boolean statements (`S`):** each `standard:/boolean/and`, `standard:/boolean/not`, and execution of a boolean value operation. Every execution of another boolean value operation is treated as a single statement whose function comes from the executed operation's recorded summary (table, compact AIG, or canonical decision diagram). Nothing inside an executed boolean value operation is expanded into the caller's statement list.
- **View Setting Statements (`copy`):** used only to pass one value to multiple read views of a single execution without aliasing (DLP 55). Every rule resolves a copy to its source value.
- **Exits:** the value operation's written views and any boolean values read by non-boolean statements. A boolean statement that reaches no exit is dead.

Because Define forbids execution cycles (DLP 9), the boolean statements of a value operation form a finite topological DAG over the `I` boolean inputs.

For each value operation, the checker deterministically decides:

1. Structural errors: literals passed to boolean statements, single-statement wrappers of registered operations, execution cycles, dead boolean statements, and unused read views of boolean value operations.
2. Canonical ordering errors (DLP 60): argument order within each group of interchangeable read views (by rank) and depth-first statement order.
3. Exact functional redundancy (DLP 59): the first boolean statement whose function is constant (`true` or `false`), equal to a boolean input or earlier boolean statement, or the exact opposite of one (unless the statement is already `not` of that value).
4. Exact registered-operation matches and spellings (DLP 61), checked whenever the value operation has no redundant values.

## 2. Acceptance Rule and Method Dispatch (No Step Budget)

The language acceptance rule uses no heuristic solver budget and no step counter. It depends only on canonical mathematical properties of the value operation's DAG:

1. **Guaranteed envelope (`S ≤ 256` and `I ≤ 20`):** every value operation within at most 256 boolean statements and at most 20 boolean inputs always compiles (within this envelope, truth tables guarantee exact checking regardless of the boolean function).
2. **Canonical shared ROBDD limit past the guaranteed envelope (`S > 256` or `I > 20`):** a value operation is accepted if and only if the canonical shared Reduced Ordered Binary Decision Diagram (ROBDD, with complement edges) of all boolean statements in the value operation, under the deterministic input order below, has at most **4,000,000 reachable non-terminal nodes**.
   - **Fixed input order (`input_order`):** walk the boolean-statement DAG depth-first from each boolean statement that no other boolean statement reads (in statement order), visiting each statement's arguments in written order, and assign each boolean input the level at which it is first reached; any unread boolean inputs come last in input order.
   - **Cross-compiler determinism:** under a fixed variable order and complement-edge canonicalization (uncomplemented `low` edge, `low ≠ high`), the shared ROBDD of a DAG of boolean functions is mathematically unique (Bryant 1986). Its reachable node count is identical on every machine and compiler, regardless of how intermediate operations are scheduled or cached. Raising the node limit in a future version of Define is strictly Forward Compatible.

**Internal engine dispatch (`--method auto`):**

- If `I ≤ 16`, or if `I ≤ 20` and the value operation executes a boolean value operation with more than 6 read views: evaluate with **truth tables**.
- Otherwise: evaluate with **ROBDDs** (constructing with a 2× intermediate node safety cap, then checking `reachable_node_count ≤ 4,000,000`). If a value operation inside the guaranteed envelope (`S ≤ 256` and `I ≤ 20`) hits the ROBDD node limit, fall back to **truth tables** so the guaranteed envelope always compiles.

Because truth tables and ROBDDs are both exact, the dispatch threshold affects only compile time and never changes which programs compile or what errors are reported.

## 3. Truth-Table Engine (`src/program.hpp`)

Every node gets a bit vector of `words = max(1, 2^I / 64)` 64-bit words:

- **Evaluating executions:** if the executed operation has a recorded `Diagram`, evaluate the diagram bottom-up word by word; else if it has a compact recorded AIG (at most `2^k` nodes for `k ≤ 6` or `16k` nodes for `k > 6`), evaluate the AIG word by word; else look up in the recorded truth table:
  - For `k ≤ 6` read views: a branch-free `k`-level word-parallel mux tree (`2^k - 1` selections per word).
  - For `k > 6` read views: an `8 × 8` bit-matrix transpose (`transpose8x8`) over argument bytes extracts 8 minterm indices per group of 8 arguments in `O(k)` bitwise operations per byte, then gathers table bits.
- **Exact functional classes (`tt_keys`):** normalize each node's truth table by bit 0 (its phase), hash into buckets, and verify full word-by-word equality modulo phase inside each bucket. Emit exact canonical class IDs `2 * rep_node + phase` (never raw hashes).
- **Interchangeable read views (`groups_of`):** union-find over read-view pairs using word-parallel swap checks on the recorded truth table.

## 4. ROBDD Engine (`src/bdd.hpp`, `src/diagram.hpp`, `src/methods.hpp`)

- **Complement-edge ROBDD (`Bdd`):** each edge is `2 * node + complement`, with `low` always uncomplemented and `low ≠ high`. Unique-table hashing uses two-step 64-bit mixing (`mix64`) with no level bit-width ceiling.
- **Native operations:** `land`, `lor`, `lxor` (using 4× complement-edge canonicalization `xor(f, g ^ 1) = xor(f, g) ^ 1`), and `ite` (using standard-triple canonicalization). Computed caches rehash on growth rather than wiping active memoization.
- **Table and diagram evaluation (`apply_table`, `compose`, `apply_big`):** standard 1-, 2-, and 3-view operations use direct native `land`/`lor`/`lxor`/`ite` fast paths; arbitrary registered and user tables use Shannon recursion with native `ite` and linear-variable `lxor` detection.
- **Zero-allocation counterexamples (`distinguishing_path`):** when two ROBDD edges differ (`rv ≠ t`), a single top-down lockstep traversal extracts a distinguishing input assignment in `O(I)` time without allocating any BDD nodes or cache entries.
- **Essential-argument checks (`holds`):** standard operations (`and`, `or`, `implies`, `xor`, `eq`, `mux`, `maj`) check essential arguments in `O(1)` via direct edge comparisons; arbitrary `k`-view registered operations compute each view's `(k - 1)`-variable Boolean derivative and check `apply_table(deriv, other) ≠ kFalse`.
- **Recorded diagrams and symmetry detection (`record_bdd`, `diagram_groups`):** boolean value operations checked with ROBDDs record their written view as a reduced uncomplemented `Diagram`. Interchangeable read views are found by:
  1. Computing exact mod-`(2^61 - 1)` biased Chow/Walsh level signatures (`p = 1/3` and `p = 1/5`) and support bits in one `O(|Diagram|)` pass (`Diagram::level_signatures`). All views outside support form one interchangeable group immediately; views inside support can only be interchangeable if their signatures match.
  2. Within each signature bucket of size ≥ 2, filtering pairs with 128 targeted assignments (64 satisfying + 64 falsifying paths sampled from the diagram, re-evaluating only `dep_nodes_[i] ∪ dep_nodes_[j]`).
  3. Confirming surviving pairs with a zero-allocation, fail-fast lockstep symmetry check (`Diagram::are_symmetric`), which checks nodes at level `la` first and aborts in `O(depth)` on the first mismatch without allocating any diagram nodes.

## 5. Registered-Operation Ordering (DLP 61)

Registered boolean operations (at most 4 read views, distinct functions up to view permutation) are ordered purely by what they compute, prioritizing human readability:

1. `standard:/boolean/and`, then `standard:/boolean/not` (always first).
2. **Fewest `and`s** required in any and-inverter graph computing the operation's function (`src/min_ands.hpp`).
3. **Fewest read views** (smaller arity first).
4. **Project-registered operations before standard-library-registered operations** (and a standard-library registered operation's own definition follows only `and`, `not`, and earlier standard-library registered operations).
5. **More symmetric first** (fewer interchangeable-view groups): e.g., symmetric `or` (1 group) precedes asymmetric `implies` (2 groups).
6. **Truth table in counting order** (first read view changing least often, rows from `(0, ..., 0)` to `(1, ..., 1)`, `false < true`): puts zero-preserving operations (`f(0, ..., 0) = false`, such as `or`, `xor`, `mux`, `maj`) before negating ones (`implies`, `eq`, `nor`, `nand`) and breaks all remaining ties uniquely.

For the six standard registered operations, this order is:

`and`, `not`, `or`, `implies`, `xor`, `eq`, `mux`, `maj`

yielding natural definitions: `or(a, b) = not(not a and not b)`, `implies(a, b) = or(not a, b)`, `xor(a, b) = or(a and not b, b and not a)`, `eq(a, b) = not xor(a, b)`, `mux(s, a, b) = or(s and a, b and not s)`, `maj(a, b, c) = mux(c, or(a, b), a and b)`.

## 6. Unified Match and Spelling Search (`src/match.hpp`)

When a value operation has no redundant values, a single `Matcher` instance finds both the reported match and the reported spelling without copying truth tables:

- **Arbitrary-width representation:** input assignments (`Assignment`) and literal-pool bitsets (`allowed_`, `cand_buf_`, `positions_`) are dynamically sized with no 64-input or 8,192-literal cap. Pool deduplication uses exact canonical class IDs (`tt_keys` or `Bdd::Edge + 1`).
- **Sampling and BDD collision splitting:** for `I ≤ 8`, all `2^I` input assignments are used directly (zero refinements). For `I > 8`, 256 deterministic varied-density assignments (all-0, all-1, uniform `p = 0.5`, biased `p ∈ {0.125, 0.25, 0.75, 0.875}`, sparse `k`-hot, dense `(I - k)`-hot) are generated. On the ROBDD path, up to 256 additional guided samples split any colliding pairs of distinct functions (including literals stuck at all-0 or all-1 on initial samples) via deterministic batch `distinguishing_path` bisection in `O(I)` per sample and zero BDD nodes.
- **View ordering and counting bounds:**
  - `xor` and `eq` run a flat direct hash-lookup loop over `signatures_` without recursing or building candidate bitsets.
  - `mux(s, a, b)` searches data inputs first in a sound two-case split: Case 1 searches `(a, b, s)` with `2 · differs(a, v) ≤ M`, and Case 2 searches `(b, a, s)` with `2 · differs(b, v) < M` and `2 · differs(a, v) > M` over the same initial `M`-sample prefix.
  - `maj(a, b, c)` requires `3 · differs(a, v) ≤ M` for the first argument.
  - Arbitrary registered operations place any linear (always-forced) view last so the last-view `signatures_` hash lookup fires.
- **Bitset filtering:** interchangeable views inherit `cand_buf_[prev[j]]`; sample filtering checks newly-forced constraints and high-index (guided/refinement) samples first, exiting immediately when no candidates remain.
- **MFFC-size pruning and best-match modes:**
  - Each statement's maximum fanout-free cone size `mffc_size` is an exact upper bound on the statements any match at that value can remove. Statements with `mffc_size < 2` skip match search; `mffc_size < 3` skips opposite-result matches; `mffc_size == 2` excludes the sole-read child from `allowed_`. Arity-1 `not` is skipped when no redundant values exist.
  - In compiler check mode (`SearchMode::kBestOverall`), candidate statements are searched in descending `mffc_size` order, breaking as soon as `mffc_size < best_removed` (or tied with a later statement index), and rejecting worse candidates by zero-allocation `removed_size` and precomputed `O(1)` integer `rank_of` comparisons before calling `holds()`. Spelling search runs in ascending statement order, tightening `current_key_` as better spellings are found and stopping after the first statement with a strictly better spelling.
  - In refactoring fix mode (`SearchMode::kBestPerValue`), at most one best match per statement is retained (skipping spellings when any match is found).

## 7. Incremental Rechecking and Fixing (`src/program_fix.hpp`)

- **Incremental rechecking:** each compiled value operation stores a 128-bit fingerprint `(hash, hash2)` of its recorded summary and its interchangeable read-view groups. When an operation is edited, callers are rechecked only while a callee's fingerprint or symmetry groups change. When `booleans.defcl` changes, operations are rechecked in `registry_only` mode (skipping ordering and unused-view checks, checking only newly affected registered operations).
- **Refactoring fixes:** fixes apply in priority order (dead statements and canonical order, redundant/opposite values, unused read views, wrappers, non-overlapping largest matches, first better spelling). `drop_views` drops unused views one at a time when a uniform substitution creates a constant (such as `xor(u1, u2)`), and `has_constant_value` dispatches to ROBDDs past the truth-table envelope. Termination of the fix loop for every finite DAG-backed program is formally verified in Lean (`proof/fixing_termination.lean`, theorem `dag_prog_terminates`).

## Appendix: Whole-Program / Legacy SAT-Sweeping Ladder

The earlier single-graph studies (`studies/experiments.md`) evaluated checking a whole flattened AIG with `beq auto` (`src/sweep.hpp`). That legacy ladder remains in `src/sweep.hpp` for whole-program optimization experiments:

1. Structural hashing (`O(n)`).
2. Truth tables for `I ≤ 12`.
3. Otherwise, 1,024-pattern random simulation + SAT sweeping in statement order with a 5-rung per-pair ladder: exhaustive simulation (`≤ 12` cone inputs, `≤ 512` cone nodes) → incremental CDCL SAT (`≤ 1,000` conflicts) → OBDD rescue (`≤ 4M` nodes, using `distinguishing_path`) → whole-graph truth tables (`I ≤ 20`) → unbounded SAT (`--external kissat`).
