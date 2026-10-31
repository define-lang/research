# Circuit Treewidth and Canonical SDD Size

## The question

A Boolean circuit has n inputs, and its graph has treewidth k. How large must
the smallest _canonical_ (compressed and trimmed) SDD over its inputs be, as a
function of n and k, minimized over vtrees? The earlier study
[circuit_treewidth_sdd](../circuit_treewidth_sdd/) answered this for
uncompressed SDDs: n·2^O(k), which is optimal up to the constant. The aim here
was either an upper bound n·g(k) or poly(n)·g(k) for canonical SDDs with g
better than triple exponential, or a lower bound beyond 2^O(k)·poly(n) on every
vtree, or else the tightest bounds on each side and a precise statement of the
gap.

## The answer

Neither aim was reached. The tightest bounds are (Theorem 1.1 of
[canonical-sdd-proof.md](canonical-sdd-proof.md)):

    max(n/2, 2^Ω(k))  ≤  canonical size  ≤  min( n·2^(2^(2^O(k))),  n^(2^O(k)) )

and for pathwidth k the upper bound is n·2^(2^O(k)). The upper bounds are
Bova and Szeider's (triple exponential, FPT), an OBDD bound that is
essentially Jha and Suciu's (given here a complete proof), and Jha and
Suciu's OBDD bound for pathwidth.

**The gap.** By the earlier study, every such circuit has an uncompressed SDD
of size n·2^O(k). So any lower bound beyond 2^O(k)·poly(n) would show that
canonical SDDs are superpolynomially larger than SDDs for some functions
(Theorem 6.2), which is a known open question (Bova 2016: SDDs "are believed
(despite not known)" to be exponentially more succinct than compressed SDDs).

**What the study adds.** These results explain where the known routes stop and
pin the question to one function:

- **HWB has a circuit of logarithmic pathwidth (Theorem 3.1, machine-checked
  in Lean).** The hidden weighted bit function HWB_n has a fan-in-2 circuit of
  pathwidth at most 8·log₂ n + 13.
- **OBDDs need doubly exponential width in the pathwidth (Corollary 4.1).**
  Since every OBDD for HWB_n has 2^Ω(n) nodes (Bryant), there are circuits of
  pathwidth k whose OBDDs all have width 2^(2^Ω(k)). This shows Jha and
  Suciu's 2^(2^O(k)) bound is tight up to the constant, answering a question
  of Amarilli, Capelli, Monet, and Senellart (2020) that the earlier study's
  README listed as open. Upper bounds through OBDDs therefore cannot beat
  doubly exponential.
- **A recent paper's circuit theorems conflict with its own lower bound
  (Corollary 4.3, Proposition 4.2).** Theorems 15 and 16 of Capelli, Choi,
  Mengel, Muñoz, and Van den Broeck (arXiv:2604.05537v1) claim factor width
  3^(k+2) and TDDs of size 2^O(k)·poly. On HWB's circuit they contradict the
  paper's own Theorem 19.
  - The argument for Theorem 15 is wrong. A ten-vertex counterexample to one
    of its steps is machine-checked in Lean.
  - On HWB's circuit, the argument would give polynomial-width OBDDs, which
    Bryant's lower bound rules out.
  - If Theorem 19 holds, factor width 2^(2^Ω(k)) is needed, so the factor-width
    route also cannot beat doubly exponential.
- **HWB is where the question turns.** Bova asked whether HWB_n has
  superpolynomial canonical SDDs on every vtree.
  - If it needs size 2^(n^ε) on every vtree, Theorem 3.1 gives circuits of
    pathwidth k needing canonical SDDs of size 2^(2^Ω(k)). That is the lower
    bound the second aim asks for, with the same form as the pathwidth upper
    bound.
  - Computation (exact over all vtrees for n ≤ 7, simulated annealing upper
    bounds for n ≤ 15) cannot tell polynomial from exponential growth. Proposition 6.3 proves that one vtree family needs about 2^(n/5),
    yet its computed sizes look cubic up to n = 22.
- **On balanced vtrees, small tree automata reach every set of states**
  (computed for up to 6 states): every non-constant set of states appears as
  a decision node at one vtree node, which is the last exponential of Bova and
  Szeider's count. This is for automata, not circuits; it suggests that an
  FPT improvement must choose vtrees differently or use more than the number
  of types.

## What is proven, checked, computed, and open

| Claim | English proof | Lean | Computation |
| --- | --- | --- | --- |
| Theorem 3.1: HWB_n has a circuit of pathwidth ≤ 8·log₂ n + 13 (fan-in 2, size O(n log n)) | yes | **yes, machine-checked** (`hwb_circuit`, `exists_bits`) | yes: all inputs for n ≤ 14, random inputs to n = 1024 |
| Proposition 4.2: a step in the proof of Capelli et al.'s Theorem 15 fails (for decompositions with the output in every bag) | yes | **yes, by `decide`** (`capelli_claim_fails`) | yes (same check) |
| The argument for Theorem 15 fails on HWB's circuit | yes (uses Bryant's bound, cited) | no | no |
| Corollary 4.1: OBDD width 2^(2^Ω(k)) needed for pathwidth k | yes (uses Bryant's bound, cited) | no | no |
| Corollary 4.3: Capelli et al.'s Theorems 15, 16 contradict their Theorem 19 | yes (Theorem 19 cited, not re-proved) | no | no |
| Theorem 5.4: canonical SDDs and OBDDs of size n^(2^O(k)) | yes | no | no |
| Upper bound n·2^(2^(2^O(k))) | cited (Bova and Szeider), argument sketched | no | no |
| Pathwidth upper bound n·2^(2^O(k)) | cited (Jha and Suciu), re-derived | no | no |
| Lower bound max(n/2, 2^Ω(k)) | yes, from Amarilli et al. (cited) | no | no |
| Theorem 6.2: a stronger lower bound separates canonical and uncompressed SDDs | yes | no | no |
| Proposition 6.3: one vtree family needs about 2^(n/5) for HWB_n | yes | no | sizes computed to n = 22 |
| Smallest canonical SDD of HWB_n | — | — | exhaustive for n ≤ 7; annealing (upper bounds) for n ≤ 15 |
| Tree automata: all non-constant state sets appear at one vtree node | — | — | yes, for 3 to 6 states |
| Canonical size ≤ 2^O(k)·poly(n)? | **open**; a negative answer would separate canonical from uncompressed SDDs (Theorem 6.2) | | |
| Does HWB_n have polynomial canonical SDDs on some vtree? | **open** (Bova 2016) | | inconclusive |

Details:

- **Lean.** [hwb_circuit_pathwidth.lean](hwb_circuit_pathwidth.lean) defines
  the circuit as a gate for each vertex and proves that it is well formed and
  acyclic, reads each variable once, computes HWB_n (every consistent
  valuation gives the output HWB_n(x)), and has a path decomposition, given by
  an interval of bags per vertex, with every bag at most 8L + 6 vertices for
  every L with n < 2^L. `exists_bits` gives such an L with 2^L ≤ 2n.
  [capelli_counterexample.lean](capelli_counterexample.lean) checks the
  counterexample by `decide`: the three-valued evaluation of the paper, the
  tree decomposition with the output in every bag, equal partial values on
  the bag, and different subfunctions. Neither file has `sorry`, and the axiom
  tests check that the theorems use only `propext`, `Classical.choice`, and
  `Quot.sound`.
  - The counterexample's decomposition is not an optimal one with the output
    added, while the paper's proof starts from an optimal decomposition. The
    argument never uses optimality, so the counterexample refutes the
    argument, not that restricted claim.
- **English.** [canonical-sdd-proof.md](canonical-sdd-proof.md) has the
  definitions, every proof, the citations, and the open problems. Two
  independent AI reviews (one of the proofs, one of the Lean statements)
  found errors, which are corrected:
  - an overstated novelty claim for Theorem 5.4 over Jha and Suciu;
  - a missing case in Theorem 5.4;
  - wrong weights in Proposition 6.3;
  - an unconditional claim that rested on the cited Theorem 19;
  - the range of k in the lower bound;
  - a constant in Theorem 6.2;
  - smaller fixes in Lemmas 2.1, 2.2, and 5.1;
  - a Lean statement that was existential in L where the text said "every L";
  - the optimality caveat above.
- **Computation.** [canon/](canon/) is a Rust program that computes exact
  canonical SDD sizes from their semantic definition (Lemma 2.1), enumerates
  vtrees, and runs simulated annealing over vtrees.
  [hwb_circuit.py](hwb_circuit.py) checks the circuit of Theorem 3.1.
  [tree_automaton_functions.py](tree_automaton_functions.py) computes
  canonical SDDs of tree automata at the level of types; it was checked
  against `canon` on 200 random automata.

## Recorded computations

From the repository root (the `canon` binary is built with
`cargo build --release` in `canon/`):

- [results/hwb_exhaustive.txt](results/hwb_exhaustive.txt): `canon
  hwb-exhaustive 7`. The smallest canonical SDD of HWB_n over all vtrees for
  n = 2..7: 0, 2, 10, 22, 34, 56.
- [results/hwb_anneal.txt](results/hwb_anneal.txt): `canon hwb-anneal 8 15
  3000 4`. The best found for n = 8..15: 82, 113, 152, 201, 254, 318, 425,
  531, with the vtrees.
- [results/hwb_vtree_families.txt](results/hwb_vtree_families.txt): `canon
  hwb-families 4 22`. Several vtree families up to n = 22.
- [results/tree_automata.txt](results/tree_automata.txt): `uv run --frozen
  python circuit_treewidth_canonical_sdd/tree_automaton_functions.py --check
  PATH_TO_CANON`.
- [results/hwb_circuit.txt](results/hwb_circuit.txt): `uv run --frozen python
  circuit_treewidth_canonical_sdd/hwb_circuit.py`.

## Files

- [canonical-sdd-proof.md](canonical-sdd-proof.md): the English proofs.
- [hwb_circuit_pathwidth.lean](hwb_circuit_pathwidth.lean) and
  [capelli_counterexample.lean](capelli_counterexample.lean): the Lean proofs.
- [hwb_circuit.py](hwb_circuit.py), [tree_automaton_functions.py](tree_automaton_functions.py),
  and [canon/](canon/): the programs.
- [results/](results/): recorded outputs.

To check the Lean proofs, run `bazelisk test //circuit_treewidth_canonical_sdd/...`
from the repository root.

These results are largely written by an AI. Rigorous review by an experienced
human would be welcome.
