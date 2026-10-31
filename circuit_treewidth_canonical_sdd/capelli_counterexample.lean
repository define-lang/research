import Mathlib.Data.Fintype.Card
import Mathlib.Data.Fintype.Pi

set_option warningAsError true
set_option autoImplicit false

/-!
# A counterexample to a step in the proof of Theorem 15 of Capelli et al.

This file formalizes Proposition 4.2 of `canonical-sdd-proof.md`.

The proof of Theorem 15 of Capelli, Choi, Mengel, Muñoz, and Van den Broeck,
"A canonical generalization of OBDD" (arXiv:2604.05537v1), takes an optimal
tree decomposition of a circuit C, adds the output gate to every bag, and
claims: for a node t, if τ and ν are assignments of the variables X≤t whose
input gates appear in bags below t, and every gate in the bag B_t has the same
three-valued partial value (0, 1, or undefined) under τ and under ν, then τ and
ν give the same X≤t-subfunction of C. The argument given for this claim uses
only that the output is in every bag, not that the decomposition was optimal.

Here is a circuit with ten vertices and a tree decomposition with the output
in every bag, a path of three bags R – T – B rooted at R, where the claim
fails:

- inputs y (0), x (1), z (2);
- g1 = ¬y (3), a = g1 ∧ x (4), nx = ¬x (5), ng = ¬g1 (6), b = ng ∧ nx (7),
  g = a ∨ b (8), and the output o = g ∧ z (9);
- R = {y, z, g1, g, o}, T = {g1, g, o}, B = {x, g1, a, nx, ng, b, g, o}.

The circuit computes (x ↔ ¬y) ∧ z. At node T, X≤T = {x}. For x = 0 and x = 1,
all three gates of T are undefined, but the subfunctions are y ∧ z and
¬y ∧ z. This decomposition is not an optimal one with the output added (the
circuit has treewidth 2), so it refutes the argument, not the claim restricted
to optimal decompositions.

`capelli_claim_fails` checks all of this by `decide`.
-/

namespace Define.CircuitTreewidthCanonicalSdd.Capelli

/-- A three-valued value: 0, 1, or undefined. -/
inductive V3 where
  | f
  | t
  | u
  deriving DecidableEq

instance : Fintype V3 := ⟨{.f, .t, .u}, by intro a; cases a <;> decide⟩

def ofBool : Bool → V3
  | false => .f
  | true => .t

/-- Three-valued NOT, AND, and OR, as in the definition of `val` in the proof
of Theorem 15. -/
def not3 : V3 → V3
  | .f => .t
  | .t => .f
  | .u => .u

def and3 (a b : V3) : V3 :=
  if a = .f ∨ b = .f then .f
  else if a = .t ∧ b = .t then .t
  else .u

def or3 (a b : V3) : V3 :=
  if a = .t ∨ b = .t then .t
  else if a = .f ∧ b = .f then .f
  else .u

/-- The gates: an input reading a variable, or a NOT, AND, or OR gate. -/
inductive Gate where
  | input (k : Fin 3)
  | not (a : Fin 10)
  | and (a b : Fin 10)
  | or (a b : Fin 10)
  deriving DecidableEq

/-- The circuit. Every gate's arguments have smaller indices, so it is
acyclic. -/
def gate : Fin 10 → Gate
  | 0 => .input 0
  | 1 => .input 1
  | 2 => .input 2
  | 3 => .not 0
  | 4 => .and 3 1
  | 5 => .not 1
  | 6 => .not 3
  | 7 => .and 6 5
  | 8 => .or 4 7
  | 9 => .and 8 2

def Gate.args : Gate → List (Fin 10)
  | .input _ => []
  | .not a => [a]
  | .and a b => [a, b]
  | .or a b => [a, b]

/-- The three-valued value of a gate given the values of its arguments. -/
def Gate.eval (ν : Fin 10 → V3) (τ : Fin 3 → V3) : Gate → V3
  | .input k => τ k
  | .not a => not3 (ν a)
  | .and a b => and3 (ν a) (ν b)
  | .or a b => or3 (ν a) (ν b)

/-- The three-valued values of all gates under a partial assignment `τ`, in
topological order. -/
def val (τ : Fin 3 → V3) : Fin 10 → V3 :=
  let y := τ 0
  let x := τ 1
  let z := τ 2
  let g1 := not3 y
  let a := and3 g1 x
  let nx := not3 x
  let ng := not3 g1
  let b := and3 ng nx
  let g := or3 a b
  let o := and3 g z
  fun
    | 0 => y
    | 1 => x
    | 2 => z
    | 3 => g1
    | 4 => a
    | 5 => nx
    | 6 => ng
    | 7 => b
    | 8 => g
    | 9 => o

/-- The bags of the tree decomposition, a path R – T – B. -/
def bagR : Finset (Fin 10) := {0, 2, 3, 8, 9}
def bagT : Finset (Fin 10) := {3, 8, 9}
def bagB : Finset (Fin 10) := {1, 3, 4, 5, 6, 7, 8, 9}

/-- The assignment of `x` alone, with `y` and `z` undefined. -/
def onlyX (x : Bool) : Fin 3 → V3
  | 1 => ofBool x
  | _ => .u

/-- A total assignment. -/
def total (y x z : Bool) : Fin 3 → V3
  | 0 => ofBool y
  | 1 => ofBool x
  | 2 => ofBool z

theorem capelli_claim_fails :
    -- `val` is the three-valued evaluation of the circuit, for every partial
    -- assignment, and arguments come before their gates.
    (∀ τ : Fin 3 → V3, ∀ v, val τ v = (gate v).eval (val τ) τ) ∧
    (∀ v, ∀ u ∈ (gate v).args, u < v) ∧
    -- Each variable has exactly one input vertex.
    (∀ v k, gate v = .input k ↔ v = k.castLE (by decide)) ∧
    -- R – T – B is a tree decomposition of the circuit's graph.
    (∀ v, ∀ u ∈ (gate v).args,
      (u ∈ bagR ∧ v ∈ bagR) ∨ (u ∈ bagT ∧ v ∈ bagT) ∨ (u ∈ bagB ∧ v ∈ bagB)) ∧
    (∀ v, v ∈ bagR ∨ v ∈ bagT ∨ v ∈ bagB) ∧
    (∀ v, v ∈ bagR → v ∈ bagB → v ∈ bagT) ∧
    -- The output is in every bag.
    (9 ∈ bagR ∧ 9 ∈ bagT ∧ 9 ∈ bagB) ∧
    -- Rooted at R, the input vertices in bags at or below T are exactly x's.
    (∀ v k, gate v = .input k → (v ∈ bagT ∨ v ∈ bagB) → k = 1) ∧
    gate 1 = .input 1 ∧ (1 : Fin 10) ∈ bagB ∧
    -- x = 0 and x = 1 give the same partial values on bag T...
    (∀ v ∈ bagT, val (onlyX false) v = val (onlyX true) v) ∧
    -- ...but different subfunctions: y ∧ z and ¬y ∧ z.
    (∀ y z, val (total y false z) 9 = ofBool (y && z)) ∧
    (∀ y z, val (total y true z) 9 = ofBool (!y && z)) :=
  ⟨by decide, by decide, by decide, by decide, by decide, by decide, by decide, by decide,
    by decide, by decide, by decide, by decide, by decide⟩

end Define.CircuitTreewidthCanonicalSdd.Capelli
