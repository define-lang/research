# Reference Algorithm for Boolean Logic Checking

This document specifies the reference algorithm implemented in `src/` (`beq program --method auto`) for checking and fixing Define's boolean logic rules (DLPs 59, 60, and 61). Every compiled component of Define produces a static, finite directed acyclic graph (DAG) with no execution cycles (DLP 9). Checking runs once per value operation (and action boolean block) in dependency order.

## 1. Input, Representation, and Output

Each value operation (or action) is analyzed into its boolean inputs and boolean statements:

- **Boolean inputs (`I`):** the value operation's boolean input views, followed in statement order by the boolean values produced by non-boolean statements (such as comparisons or executions of mixed value operations). Boolean inputs are treated as independent variables.
- **Boolean statements (`S`):** each `standard:/boolean/and`, `standard:/boolean/not`, and execution of a boolean value operation. Every execution of another boolean value operation is treated as a single statement whose function comes from the executed operation's recorded summary (table, compact AIG, or canonical decision diagram). Nothing inside an executed boolean value operation is expanded into the caller's statement list.
- **View Setting Statements (`copy`):** used only to pass one value to multiple input views of a single execution without aliasing (DLP 55). Every rule resolves a copy to its source value.
- **Exits:** the value operation's output views and any boolean values read by non-boolean statements. A boolean statement that reaches no exit is dead.

Because Define forbids execution cycles (DLP 9), the boolean statements of a value operation form a finite topological DAG over the `I` boolean inputs.

For each value operation, the checker deterministically decides:

1. **Structural errors and limits:** boolean input view limit (`≤ 20`), boolean statement limit (`≤ 256`), boolean input limit (`≤ 512`), canonical shared ROBDD node limit (`≤ 65,536` past 20 inputs), boolean literals passed to any Abstract Operation (DLP 59), single output view on Boolean Value Operations, independent non-boolean-only boolean output views on non-Boolean Value Operations (DLP 59 Problem 7: no boolean output view's Boolean Sources may include a boolean input view, and no two boolean output views may share a Boolean Source), single-statement wrappers of standard boolean operations, execution cycles, dead Boolean Statements, and useless boolean inputs (every boolean input must appear in the Boolean Sources of at least one boolean output view or non-boolean argument, and for every such boolean output view or non-boolean argument, changing any view in its Boolean Sources must be able to change its value).
2. **Exact functional redundancy (DLP 59):** the first boolean statement whose function is constant (`true` or `false`), equal to a boolean input or earlier boolean statement, or the exact opposite of one (unless the statement is already `not` of that value).
3. **Canonical ordering, associative grouping, and factoring (DLP 60):**
   - Argument order within each group of interchangeable input views (by rank).
   - Depth-first statement order.
   - **Associative grouping (`order_grouping`):** every maximal single-use chain of any commutative, associative binary boolean operation (detected semantically from its 4-bit truth table, covering `and`, `or`, `xor`, `equal`, and user-defined associative commutative operations) must be folded left-to-right in monotonic DLP 60 rank order (`op(v_1, v_2)`, `op(v_3, t_1)`, ..., `op(v_m, t_{m-2})`), with no balanced sub-pairs.
   - **Factoring common terms (`order_factor`):** for any two distinct commutative, associative binary boolean operations where `inner` distributes over `outer` (detected semantically from their 4-bit truth tables, covering `(and, or)`, `(or, and)`, `(and, xor)`, `(or, equal)`), no value `x` may appear in two or more single-use `inner`-chain terms of the same single-use `outer`-chain. The value `x` to factor is chosen by most terms removed, then lowest DLP 60 rank.
4. **Standard boolean operation matches and spellings (DLP 61):** checked only after the operation has no DLP 59 redundant values and no DLP 60 unfactored common terms.

## 2. Acceptance Rule and Method Dispatch (No Step Budget)

The language acceptance rule uses no heuristic solver budget and no step counter. It depends only on syntactic counts and canonical mathematical properties of the value operation's DAG:

1. **Boolean input interface views (`≤ 20` on any Value Operation):** caps every pure boolean Value Operation's exported contract to **≤ 128 KB** (truth table) and **≤ 98,302** ROBDD nodes (with complement edges), and caps DLP 60 symmetry checks to at most `20 × 19 / 2 = 190` pairs.
2. **Boolean statements (`≤ 256` per Value Operation or Action):** bounds match search even on adversarial non-matching chains and guarantees that every pure boolean Value Operation fits unconditionally inside the `(256 statements, 20 inputs)` truth-table floor.
3. **Boolean inputs (`≤ 512` per Value Operation or Action):** bounds the value pool (`N = I + S ≤ 768`) on mixed Value Operations and Actions with many non-boolean comparisons.
4. **Canonical shared ROBDD reachable-node limit (`≤ 65,536` past 20 inputs):** when `21 ≤ I ≤ 512`, a Value Operation or Action is accepted if and only if the canonical shared Reduced Ordered Binary Decision Diagram (ROBDD, with complement edges) of all boolean statements, under the deterministic input order below, has at most **65,536 (`2^16`) reachable non-terminal nodes**.
   - **Fixed input order (`input_order`):** walk the boolean-statement DAG depth-first from each boolean statement that no other boolean statement reads (in statement order), visiting each statement's arguments in written order, and assign each boolean input the level at which it is first reached; any unread boolean inputs come last in input order.
   - **Cross-compiler determinism:** under a fixed variable order and complement-edge canonicalization (uncomplemented `low` edge, `low ≠ high`), the shared ROBDD of a DAG of boolean functions is mathematically unique (Bryant 1986). Its reachable node count is identical on every machine and compiler, regardless of how intermediate operations are scheduled or cached. Raising any of these limits in a future version of Define is strictly Forward Compatible.

**Internal engine dispatch (`--method auto`):**

- If `I ≤ 16`, or if `I ≤ 20` and the value operation executes a boolean value operation with more than 6 input views: evaluate with **truth tables**.
- Otherwise: evaluate with **ROBDDs** (constructing with a 2× intermediate node safety cap of `131,072` nodes — ~5–10 MB per parallel worker — then checking `reachable_node_count ≤ 65,536`). If a value operation inside the guaranteed truth-table floor (`I ≤ 20`, `S ≤ 256`) hits the ROBDD node limit, fall back to **truth tables** so every pure boolean Value Operation always compiles.

Because truth tables and ROBDDs are both exact, the dispatch threshold affects only compile time and never changes which programs compile or what errors are reported.

## 3. Truth-Table Engine (`src/program.hpp`)

Every node gets a bit vector of `words = max(1, 2^I / 64)` 64-bit words (at most 128 KB per node at `I = 20`, and at most 32 MB total for 256 statements):

- **Evaluating executions:** if the executed operation has a recorded `Diagram`, evaluate the diagram bottom-up word by word; else if it has a compact recorded AIG (at most `2^k` nodes for `k ≤ 6` or `16k` nodes for `k > 6`), evaluate the AIG word by word; else look up in the recorded truth table:
  - For `k ≤ 6` input views: a branch-free `k`-level word-parallel mux tree (`2^k - 1` selections per word).
  - For `k > 6` input views: an `8 × 8` bit-matrix transpose (`transpose8x8`) over argument bytes extracts 8 minterm indices per group of 8 arguments in `O(k)` bitwise operations per byte, then gathers table bits.
- **Exact functional classes (`tt_keys`):** normalize each node's truth table by bit 0 (its phase), hash into buckets, and verify full word-by-word equality modulo phase inside each bucket. Emit exact canonical class IDs `2 * rep_node + phase` (never raw hashes).
- **Interchangeable input views (`groups_of`):** union-find over input-view pairs using word-parallel swap checks on the recorded truth table (at most 190 pairs for `k ≤ 20`).
- **Semantic binary properties (`is_assoc_comm_tt`, `distributes_over_tt`):** every binary boolean operation's 4-bit truth table directly determines whether it is commutative and associative (`tt ∈ {0x8 (and), 0xE (or), 0x6 (xor), 0x9 (equal)}`) and whether two distinct operations satisfy `inner(a, outer(b, c)) == outer(inner(a, b), inner(a, c))` across all 8 input triples.

## 4. ROBDD Engine (`src/bdd.hpp`, `src/diagram.hpp`, `src/methods.hpp`)

- **Complement-edge ROBDD (`Bdd`):** each edge is `2 * node + complement`, with `low` always uncomplemented and `low ≠ high`. Unique-table hashing uses two-step 64-bit mixing (`mix64`) with no level bit-width ceiling.
- **Native operations:** `land`, `lor`, `lxor` (using 4× complement-edge canonicalization `xor(f, g ^ 1) = xor(f, g) ^ 1`), and `ite` (using standard-triple canonicalization). Computed caches rehash on growth rather than wiping active memoization.
- **Table and diagram evaluation (`apply_table`, `compose`, `apply_big`):** standard 1- and 2-view operations use direct native `land`/`lor`/`lxor` fast paths; arbitrary user boolean Value Operations compose their recorded `Diagram` or use Shannon recursion with native `ite` and linear-variable `lxor` detection.
- **Zero-allocation counterexamples (`distinguishing_path`):** when two ROBDD edges differ (`rv ≠ t`), a single top-down lockstep traversal extracts a distinguishing input assignment in `O(I)` time without allocating any BDD nodes or cache entries.
- **Essential-argument checks (`holds`):** all standard boolean operations (`and`, `or`, `xor`, `equal`) check essential arguments in `O(1)` via direct edge comparisons (`a ≠ b`, `a ≠ not b`, etc.).
- **Recorded diagrams and symmetry detection (`record_bdd`, `diagram_groups`):** boolean value operations checked with ROBDDs record their output view as a reduced uncomplemented `Diagram`. Interchangeable input views are found by:
  1. Computing exact mod-`(2^61 - 1)` biased Chow/Walsh level signatures (`p = 1/3` and `p = 1/5`) and support bits in one `O(|Diagram|)` pass (`Diagram::level_signatures`). All views outside support form one interchangeable group immediately; views inside support can only be interchangeable if their signatures match.
  2. Within each signature bucket of size ≥ 2, filtering pairs with 128 targeted assignments (64 satisfying + 64 falsifying paths sampled from the diagram, re-evaluating only `dep_nodes_[i] ∪ dep_nodes_[j]`).
  3. Confirming surviving pairs with a zero-allocation, fail-fast lockstep symmetry check (`Diagram::are_symmetric`), which checks nodes at level `la` first and aborts in `O(depth)` on the first mismatch without allocating any diagram nodes.

## 5. Standard Boolean Operations (DLP 61)

Define enforces a single fixed, global set of five standard boolean operations across all projects (there is no project-level registration config):

`and`, `not`, `or`, `xor`, `equal`

Their definitions follow this exact fixed order:

- `standard:/boolean/and` and `standard:/boolean/not` (primitives).
- `standard:/boolean/or(a, b) = not(not a and not b)`.
- `standard:/boolean/xor(a, b) = or(a and not b, b and not a)`.
- `standard:/boolean/equal(a, b) = not xor(a, b)`.

Every standard operation has arity ≤ 2 and is completely symmetric across its input views. (The reference binary `beq` retains configurable operation sets and general `min_ands` ordering for benchmarking and historical experiments, while `gen/program.py` and Define default strictly to `{and, not, or, xor, equal}`.)

## 6. Unified Match and Spelling Search (`src/match.hpp`)

When a value operation has no DLP 59 redundant values and no DLP 60 unfactored common terms, a single `Matcher` instance finds both the reported match and the reported spelling without copying truth tables:

- **Strictly `O(S * (I + S))` complexity for Define's standard set:** because all five standard operations (`and`, `not`, `or`, `xor`, `equal`) have arity ≤ 2 and are symmetric, match search never backtracks over 3- or 4-argument tuples:
  - `xor` and `equal` run a flat `O(1)` direct hash-lookup loop over `signatures_` (`target_word ^ arg0_word`).
  - `and` and `or` perform direct bitset intersection over the single remaining argument's candidate pool.
  - `not` is skipped when no redundant values exist.
- **Arbitrary-width representation:** input assignments (`Assignment`) and literal-pool bitsets (`allowed_`, `cand_buf_`, `positions_`) are dynamically sized with no 64-input or 8,192-literal cap. Pool deduplication uses exact canonical class IDs (`tt_keys` or `Bdd::Edge + 1`).
- **Sampling and BDD collision splitting:** for `I ≤ 8`, all `2^I` input assignments are used directly (zero refinements). For `I > 8`, 256 deterministic varied-density assignments (all-0, all-1, uniform `p = 0.5`, biased `p ∈ {0.125, 0.25, 0.75, 0.875}`, sparse `k`-hot, dense `(I - k)`-hot) are generated. On the ROBDD path, up to 256 additional guided samples split any colliding pairs of distinct functions (including literals stuck at all-0 or all-1 on initial samples) via deterministic batch `distinguishing_path` bisection in `O(I)` per sample and zero BDD nodes.
- **MFFC-size pruning and best-match modes:**
  - Each statement's maximum fanout-free cone size `mffc_size` is an exact upper bound on the statements any match at that value can remove. Statements with `mffc_size < 2` skip match search; `mffc_size < 3` skips opposite-result matches; `mffc_size == 2` excludes the sole-read child from `allowed_`.
  - In compiler check mode (`SearchMode::kBestOverall`), candidate statements are searched in descending `mffc_size` order, breaking as soon as `mffc_size < best_removed` (or tied with a later statement index), and rejecting worse candidates by zero-allocation `removed_size` and precomputed `O(1)` integer `rank_of` comparisons before calling `holds()`. Spelling search runs in ascending statement order, tightening `current_key_` as better spellings are found and stopping after the first statement with a strictly better spelling.
  - In refactoring fix mode (`SearchMode::kBestPerValue`), at most one best match per statement is retained (skipping spellings when any match is found).

## 7. Incremental Rechecking and Complete Automated Refactoring (`src/program_fix.hpp`)

- **Incremental rechecking:** each compiled value operation stores a 128-bit fingerprint `(hash, hash2)` of its recorded summary and its interchangeable input-view groups. When an operation is edited, callers are rechecked only while a callee's fingerprint or symmetry groups change. Because the standard boolean operation set is fixed globally across all projects, there is no project-wide registration-config invalidation pass.
- **Complete automated refactoring (DLP 64):** the refactoring tool (`beq program --mode fix`) automatically resolves every semantically fixable rule violation across whole programs, stopping **only** at opaque non-Boolean Logical Operations (`num.*` / `cmp.*` receiving a boolean literal or constant expression), 0-output boolean value operations (`outputs`), DLP 62 structural/ROBDD limits (`limits`), execution cycles (`cycle`), or registered wrappers/constants. Signature changes (dropped views, multi-output splits, mixed-output extractions, constant/wrapper/view replacements) are tracked compositionally per operation via versioned signature-change histories and replayed onto every caller (`call` and `run`). Fixes apply in strict priority order:
  1. **Multi-output `bool` op splitting (DLP 59 Problem 6):** any boolean value operation with `k > 1` output views is split into `k` single-output boolean value operations (keeping live statements for each output) and callers are updated.
  2. **Dead statements and canonical argument/statement order (DLP 59/60).**
  3. **Literal propagation, constant folding, and acyclic callee specialization (DLP 59):**
     - Any constant boolean statement (`redundant_kind == "constant"`) is replaced with `true`/`false`.
     - `not(true/false)` and `and(x, true/false)` fold directly.
     - `call` (Boolean Value Operation) or `run` (non-Boolean Value Operation) receiving one or more boolean literals specializes the callee into a deduplicated helper op with those boolean input views substituted by literals, fixes and simplifies the specialized op immediately, and rewrites the call site.
     - Boolean value operations simplifying to a constant output (`true`/`false`) are removed and propagate the constant literal into callers; constant boolean output views of mixed value operations are similarly removed and substituted in callers.
     - If a boolean literal or constant reaches an opaque non-Boolean Logical Operation (`num.*` / `cmp.*`), fixing stops cleanly with `literal`.
  4. **Redundant and opposite values, and unused input views on `bool` ops (DLP 59):** `drop_views` tries kept-view substitution (uniform, then per-view, with `has_constant_value` dispatching to ROBDDs past the truth-table envelope). If every kept-view substitution creates a constant (e.g., `xor(xor(x, z), xor(y, z)) and x`), it substitutes `false` for the unused view and lets literal propagation and callee specialization eliminate it cleanly.
  5. **Wrappers of standard boolean operations (DLP 61):** non-registered single-statement wrappers (and identity-view ops) are removed and inlined at call sites.
  6. **Factoring common terms (DLP 60):** `apply_factor` factors the chosen value `x` out of `k ≥ 2` single-use `inner`-chain terms of an `outer`-chain, strictly reducing the operation's statement count (`P.length`).
  7. **Non-overlapping largest standard-operation matches, then first better spelling (DLP 61).**
  8. **Associative regrouping (DLP 60):** `regroup_associative` folds the first non-canonical single-use associative chain into canonical left-to-right rank order, preserving statement count and inserting rebuilt statements immediately before the chain root to maintain topological order. Running regrouping after DLP 59/factor/match ensures it never introduces spurious constant pairs on unfixed operations.
  9. **Useless boolean inputs on `mixed` ops (DLP 59):**
     - If a boolean input `d` is in a target exit `t`'s Boolean Sources yet cannot change `t` (e.g., `xor(xor_and(d, a, b), xor_and(d, c, e))` passed to `num.sel`, while `d` is still read elsewhere), `t`'s boolean sub-DAG is cloned with `d` substituted by `false` (leaving all other reads of `d` untouched), and literal propagation + callee specialization simplify it away.
     - If a boolean input is absent from every exit's Boolean Sources: boolean input interface views are dropped from the mixed op and its `run` callers; pure `cmp` statements are deleted; and unused boolean outputs of a `run` are dropped via deduplicated callee specialization (or the `run` is deleted if all its outputs are unused).
  10. **Mixed-output extraction (DLP 59 Problem 7):** if a non-Boolean Value Operation violates `mixed_bool_view` or `mixed_shared_input`, the boolean logic on top of the non-boolean Boolean Sources is extracted into single-output boolean helper ops (or inlined wrappers in callers), the mixed op returns each distinct needed non-boolean Boolean Source directly at most once, and all `run` callers are updated.

Termination of both the core single-operation/program normalization loop and all DLP 64 automated refactoring phases for every finite DAG-backed program is formally verified in Lean 4 (`proof/fixing_termination.lean`: `dag_prog_terminates`, `structural_terminates`, `specialization_terminates`, `fold_loop_terminates`, `useless_elim_terminates`, and `full_autofix_terminates`, with zero `sorry` and zero custom axioms).

## Appendix: Whole-Program / Legacy SAT-Sweeping Ladder

The earlier single-graph studies (`studies/experiments.md`) evaluated checking a whole flattened AIG with `beq auto` (`src/sweep.hpp`). That legacy ladder remains in `src/sweep.hpp` for whole-program optimization experiments:

1. Structural hashing (`O(n)`).
2. Truth tables for `I ≤ 12`.
3. Otherwise, 1,024-pattern random simulation + SAT sweeping in statement order with a 5-rung per-pair ladder: exhaustive simulation (`≤ 12` cone inputs, `≤ 512` cone nodes) → incremental CDCL SAT (`≤ 1,000` conflicts) → OBDD rescue (`≤ 4M` nodes, using `distinguishing_path`) → whole-graph truth tables (`I ≤ 20`) → unbounded SAT (`--external kissat`).
