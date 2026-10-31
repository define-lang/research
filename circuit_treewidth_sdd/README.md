# Circuit Treewidth and SDD Size

## The question

A Boolean circuit C has n inputs, and its graph (inputs and gates as vertices,
wires as edges) has treewidth k. How large must the smallest sentential
decision diagram (SDD, [Darwiche 2011]) over the inputs of C be, as a function
of n and k? In particular, is it n·2^O(k), as for deterministic structured
DNNFs (d-SDNNFs), or must it be larger?

## The answer

**It is n·2^O(k), and the dependence on k is optimal up to the constant in the
exponent.**

- **Upper bound (Theorem 1.1).** For every circuit with n inputs and a tree
  decomposition of width k, there is a vtree over the inputs and an SDD
  respecting it that computes the circuit, with at most n·2^(32k+65) elements
  and at most n·2^(16k+34) decision nodes. The SDD has no auxiliary variables.
  It is _not_ compressed in general. Every gate kind with any fan-in is allowed
  (AND, OR, NOT, constants, negated wires), so AIGs are included; for AIGs only
  the constants change.
- **Pathwidth (Theorem 1.2).** With a path decomposition of width k, the vtree
  can be left-linear (every right child a leaf), with at most n·2^(24k+56)
  elements. In contrast, the best known bound for OBDDs, which are SDDs on
  right-linear vtrees, is doubly exponential in the pathwidth, and whether that
  is needed is open.
- **Unambiguous OBDDs (Corollary 1.3).** If f and ¬f have complete unambiguous
  OBDDs with the same order and width W, then f has an SDD of size O(n·W⁸) on
  the left-linear vtree for that order, with no auxiliary variables. Bollig and
  Buttkus proved a polynomial bound only for vtrees with auxiliary variables.
- **Lower bounds (Proposition 1.4).** There are circuits and AIGs of treewidth
  O(k) with any number of inputs whose SDDs all have size 2^Ω(k) (a known
  theorem of Amarilli, Capelli, Monet, and Senellart for structured DNNFs, which
  SDDs are). An SDD of a function that depends on all n ≥ 2 inputs has at least
  n/2 elements.

So the smallest SDD has size between max(n/2, 2^Ω(k)) and n·2^O(k). Before this
work, the best published bound for SDDs was triple exponential in k (Bova and
Szeider, for canonical SDDs), and Amarilli et al. asked whether their
singly exponential d-SDNNF bound could be extended to SDDs. We did not find
this result in earlier work; section 9 of the proof lists what we found.

The key steps are short: in an RTD (a tree decomposition with the gate
constraints in its bags), the inside assignments consistent with a guessed
state σ form a set Q_t(σ); once the inputs outside a node are fixed, these sets
partition the inside assignments (Lemma 4.4). An SDD decision node needs one
partition for all values of its right side, and the construction uses the
common refinement of the partitions for two fixed outside assignments; two are
always enough after a reshaping of the vtree that gives every internal right
child a leaf as its right child.

## What is proven, checked, and open

| Claim | English proof | Lean | Computation |
| --- | --- | --- | --- |
| Theorem 5.1: an RTD with (S1) and (S2) has an SDD of size (internal nodes)·16^b | yes | **yes, machine-checked** | yes |
| Lemmas 4.2–5.6 (the parts of Theorem 5.1) | yes | yes, as part of Theorem 5.1 | yes |
| Every RTD on a vtree with bags ≤ b has an SDD of size (n − 1)·16^(3b+2) | yes (Theorem 5.1 with Lemma 6.1) | **yes, machine-checked** | yes |
| Lemma 6.1: leaf donation gives (S1) and (S2) | yes | **yes, for the variant of Remark 6.2** (bags ≤ 3b + 2) | yes |
| Lemma 7.1: gate splitting for any fan-in | yes | no | yes |
| Lemma 7.2: normalization to a vtree | yes | no | yes |
| Theorem 1.1 (treewidth) and Theorem 1.2 (pathwidth) | yes | no (composition of the above) | yes |
| Corollary 1.3 (unambiguous OBDDs) | yes | no | no |
| Proposition 1.4, first part (2^Ω(k) lower bound) | cited, with a sketch of the AIG step | no | no |
| Proposition 1.4, second part (n/2) | yes | no | no |
| Compressed (canonical) SDDs of size n·2^O(k) | **open** | | some data only |

Details:

- **Lean.** [sdd_from_decomposition.lean](sdd_from_decomposition.lean) proves,
  with Boolean vertices:
  - `Define.CircuitTreewidthSdd.sdd_of_rtd`, Theorem 5.1. It gives an SDD term
    `S : Sdd R.tree` that is valid (every decision node's primes are
    consistent, mutually exclusive, and exhaustive), computes the RTD's
    function, and has at most (internal nodes)·4^b distinct decision nodes
    with at most 4^b elements each, so its size (elements summed over distinct
    decision nodes) is at most (internal nodes)·16^b, when all bags have at
    most b vertices.
  - `Define.CircuitTreewidthSdd.sdd_of_vtree_rtd`, Theorem 5.1 combined with
    the variant of Lemma 6.1 in Remark 6.2: _every_ RTD on a vtree whose bags
    have at most b vertices has an SDD over the same inputs, respecting a
    vtree over the same inputs, of size at most (n − 1)·16^(3b+2).

  The Lean RTD states the separation properties of Lemma 3.2 directly
  (`DTree.WF`), rather than connectivity, from which Lemma 3.2 derives them in
  English. So what remains unformalized is the passage from a circuit and a
  tree decomposition of its graph to an RTD on a vtree (Lemmas 7.1 and 7.2) and
  Lemma 3.2. The file has no `sorry`, and the axiom test checks that both
  theorems use only `propext`, `Classical.choice`, and `Quot.sound`.
- **English.** [circuit-treewidth-sdd-proof.md](circuit-treewidth-sdd-proof.md)
  has every definition and proof, including the reductions from circuits
  (Lemmas 7.1 and 7.2), the reshaping (Lemma 6.1), and the corollaries.
- **Computation.** [sdd_construction.py](sdd_construction.py) carries out the
  whole construction on small circuits and checks, by brute force over all
  input assignments, every property the proof claims for the intermediate
  objects (connectivity, unique solutions, the shape conditions) and that the
  final object is a valid SDD for the vtree computing the circuit, with every
  pair cell and join node computing its definition and the size within the
  bound of Theorem 5.1. [experiments.py](experiments.py) runs it.
- **Review.** Two independent AI reviews of the English proof found no fatal
  error. They found one real gap, now fixed: the pathwidth proof (Theorem 1.2)
  must root the path decomposition at an end. They also found several smaller
  imprecisions, which have been corrected.
- **Open.** The SDD built here is not compressed. Compressing it merges primes
  into unions of cells at left children, exactly the case the construction
  avoids, and compression can blow up SDDs on a fixed vtree. The best known
  bound for canonical SDDs of circuits of treewidth k remains triple
  exponential. Whether the lower bound can be strengthened to n·2^Ω(k) (rather
  than max(n/2, 2^Ω(k))) is not addressed. The constants in the exponents are
  not optimized.

## Recorded computations

From the repository root, `uv run --frozen --python 3.14 python
circuit_treewidth_sdd/experiments.py COMMAND` (the repository's
`.python-version` asks for Python 3.15, which is not installed here, so the
runs used 3.14). The outputs are in [results/](results/):

- `random_tree_clique.txt`: 1000 random circuits (2–10 inputs, gates of fan-in
  1–3 with random negations), tree decompositions of width up to 6 of the graph
  in which each gate and its inputs form a clique, normalization, leaf
  donation, and the SDD. All checks passed.
- `random_tree_split.txt`: the same pipeline with gate splitting (Lemma 7.1)
  on 40 circuits with fan-in up to 4 and up to 6 inputs. All checks passed.
- `random_path_clique.txt` (1000 circuits) and `random_path_split.txt` (40
  circuits): path decompositions, giving left-linear vtrees (Theorem 1.2),
  with the same checks. All checks passed.
- `scaling.txt`: SDD size per input stays between about 9 and 23 as n grows
  from 4 to 13 at bounded width.
- `index.txt`: the multiplexer x[y] with m address bits and the data bits
  deepest in a left-linear vtree. For m = 3 (11 inputs) the SDD built here has
  1694 elements, while the canonical (compressed) SDD on the same vtree has
  16044.

The "clique" variant decomposes a slightly different graph than Lemma 7.1 (each
gate's scope is a clique, as for fan-in 2 gates), which keeps bags small
enough for brute-force checking; Theorem 5.1 and Lemmas 6.1 and 7.2 apply to
it unchanged.

## Files

- [circuit-treewidth-sdd-proof.md](circuit-treewidth-sdd-proof.md): the English
  proofs.
- [sdd_from_decomposition.lean](sdd_from_decomposition.lean): the Lean proofs of
  Theorem 5.1 and of Theorem 5.1 combined with the leaf donation of Remark 6.2.
- [sdd_construction.py](sdd_construction.py) and [experiments.py](experiments.py):
  the executable construction and the experiments.
- [results/](results/): recorded experiment outputs.

To check the Lean proof, run `bazelisk test //circuit_treewidth_sdd/...` from
the repository root.

These results are largely written by an AI. Rigorous review by an experienced
human would be welcome.
