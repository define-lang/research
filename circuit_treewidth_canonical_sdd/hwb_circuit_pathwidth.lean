import Mathlib.Data.Fintype.Card
import Mathlib.Data.Set.Card
import Mathlib.Tactic.Linarith
import Mathlib.Algebra.Order.BigOperators.Group.Finset

set_option warningAsError true
set_option autoImplicit false
set_option linter.unnecessarySeqFocus false

/-!
# A circuit of logarithmic pathwidth for the hidden weighted bit function

This file formalizes Theorem 3.1 of `canonical-sdd-proof.md`: for every n ≥ 1,
the hidden weighted bit function HWB_n has a Boolean circuit with AND, OR, and
NOT gates of fan-in at most 2, one input vertex per variable, at most
n·(5L + 3) + L + 2 vertices, and a path decomposition of its graph whose bags
have at most 8L + 6 vertices, for every L with n < 2^L (`hwb_circuit`); such an
L exists with 2^L ≤ 2n (`exists_bits`).

The circuit adds the inputs one at a time into an L-bit counter, so after
the last input the counter holds the weight w. The vertices holding w are put
into every bag, which lets the second half of each step compare w with the
step's index and keep x_i if they are equal.

`Define.CircuitTreewidthCanonicalSdd.hwb_circuit` and
`Define.CircuitTreewidthCanonicalSdd.exists_bits` state the whole result.

Conventions:

- `x k` is the value of variable x_{k+1}; the circuit's vertex `V.inp i`
  (for 1 ≤ i ≤ n) is the input vertex of x_i.
- A circuit is a gate for each vertex (`gate`) on the finite vertex set
  `verts`. Its graph has an edge between each gate and each of its arguments.
- The semantics is given by consistency: a valuation of the vertices is
  consistent with an input if every vertex has the value its gate computes
  from the values of its arguments. The circuit is acyclic (`gate_rank_lt`),
  so it has exactly one consistent valuation for each input.
- A path decomposition is given by an interval of bag indices for each vertex
  (`lo` to `hi`); bag p holds the vertices whose interval contains p. So each
  vertex's bags are consecutive by construction.
-/

namespace Define.CircuitTreewidthCanonicalSdd

/-- `popc x i` is the number of `k < i` with `x k`. -/
def popc (x : ℕ → Bool) : ℕ → ℕ
  | 0 => 0
  | i + 1 => popc x i + (x i).toNat

/-- The hidden weighted bit function of `x 0, ..., x (n - 1)`. -/
def hwb (n : ℕ) (x : ℕ → Bool) : Bool :=
  decide (0 < popc x n) && x (popc x n - 1)

/-- The vertices of the circuit. For step `i` and bit `j`: `carry i (j + 1)`
is the carry out of bit `j`, `cnt i j` is bit `j` of the count after `i`
inputs, `orG` and `nand` are the other two gates of the sum bit, `nw j` is the
negation of bit `j` of the final count, `e i j` says that bits `0..j` of the
final count equal those of `i`, `t i` keeps `x_i` if the final count is `i`,
and `o i` is the disjunction of `t 1, ..., t i`. -/
inductive V where
  | inp (i : ℕ)
  | nx0
  | zero
  | carry (i j : ℕ)
  | orG (i j : ℕ)
  | nand (i j : ℕ)
  | cnt (i j : ℕ)
  | nw (j : ℕ)
  | e (i j : ℕ)
  | t (i : ℕ)
  | o (i : ℕ)
  deriving DecidableEq

/-- A gate: an input reading a variable, or a NOT, AND, or OR gate. -/
inductive Gate where
  | input (k : ℕ)
  | not (a : V)
  | and (a b : V)
  | or (a b : V)

/-- The arguments of a gate. -/
def Gate.args : Gate → List V
  | .input _ => []
  | .not a => [a]
  | .and a b => [a, b]
  | .or a b => [a, b]

/-- The value of a gate, given the values `ν` of its arguments. -/
def Gate.eval (ν : V → Bool) (x : ℕ → Bool) : Gate → Bool
  | .input k => x k
  | .not a => !ν a
  | .and a b => ν a && ν b
  | .or a b => ν a || ν b

section Circuit

variable (n L : ℕ)

/-- Bit `j` of the count after `i` inputs; the count after no inputs is the
constant `zero`. -/
def cntV (i j : ℕ) : V := if i = 0 then .zero else .cnt i j

/-- The carry into bit `j` of step `i`; the carry into bit 0 is `x_i`. -/
def carryV (i j : ℕ) : V := if j = 0 then .inp i else .carry i j

/-- The literal of bit `j` of the final count that is true when that bit
equals bit `j` of `i`. -/
def lit (i j : ℕ) : V := if i.testBit j then .cnt n j else .nw j

/-- Bits `0..j` of the final count equal those of `i`. -/
def eqV (i j : ℕ) : V := if j = 0 then lit n i 0 else .e i j

/-- The disjunction of `t 1, ..., t i`; for `i = 0` it is `zero`. -/
def outV (i : ℕ) : V := if i = 0 then .zero else .o i

/-- The gate of each vertex. -/
def gate : V → Gate
  | .inp i => .input (i - 1)
  | .nx0 => .not (.inp 1)
  | .zero => .and (.inp 1) .nx0
  | .carry i j => .and (cntV (i - 1) (j - 1)) (carryV i (j - 1))
  | .orG i j => .or (cntV (i - 1) j) (carryV i j)
  | .nand i j => .not (.carry i (j + 1))
  | .cnt i j => .and (.orG i j) (.nand i j)
  | .nw j => .not (.cnt n j)
  | .e i j => .and (eqV n i (j - 1)) (lit n i j)
  | .t i => .and (.inp i) (eqV n i (L - 1))
  | .o i => .or (outV (i - 1)) (.t i)

/-- The vertices of the circuit. -/
def Valid : V → Prop
  | .inp i => 1 ≤ i ∧ i ≤ n
  | .nx0 => True
  | .zero => True
  | .carry i j => 1 ≤ i ∧ i ≤ n ∧ 1 ≤ j ∧ j ≤ L
  | .orG i j => 1 ≤ i ∧ i ≤ n ∧ j < L
  | .nand i j => 1 ≤ i ∧ i ≤ n ∧ j < L
  | .cnt i j => 1 ≤ i ∧ i ≤ n ∧ j < L
  | .nw j => j < L
  | .e i j => 1 ≤ i ∧ i ≤ n ∧ 1 ≤ j ∧ j < L
  | .t i => 1 ≤ i ∧ i ≤ n
  | .o i => 1 ≤ i ∧ i ≤ n

/-- The numbers `1..m`. -/
def pos (m : ℕ) : Finset ℕ := (Finset.range m).image (· + 1)

/-- The vertex set, as a finite set. -/
def verts : Finset V :=
  (pos n).image V.inp ∪ {V.nx0, V.zero} ∪
    ((pos n) ×ˢ (pos L)).image (fun p => V.carry p.1 p.2) ∪
    ((pos n) ×ˢ (Finset.range L)).image (fun p => V.orG p.1 p.2) ∪
    ((pos n) ×ˢ (Finset.range L)).image (fun p => V.nand p.1 p.2) ∪
    ((pos n) ×ˢ (Finset.range L)).image (fun p => V.cnt p.1 p.2) ∪
    (Finset.range L).image V.nw ∪
    ((pos n) ×ˢ ((Finset.range L).filter (1 ≤ ·))).image (fun p => V.e p.1 p.2) ∪
    (pos n).image V.t ∪ (pos n).image V.o

/-- The first bag that contains each vertex. -/
def lo : V → ℕ
  | .inp i => i
  | .nx0 => 1
  | .zero => 1
  | .carry i _ => i
  | .orG i _ => i
  | .nand i _ => i
  | .cnt i _ => if i = n then 1 else i
  | .nw _ => 1
  | .e i _ => i
  | .t i => i
  | .o i => i

/-- The last bag that contains each vertex. -/
def hi : V → ℕ
  | .inp i => i
  | .nx0 => 1
  | .zero => 1
  | .carry i _ => i
  | .orG i _ => i
  | .nand i _ => i
  | .cnt i _ => if i = n then n else i + 1
  | .nw _ => n
  | .e i _ => i
  | .t i => i
  | .o i => if i = n then n else i + 1

/-- Bag `p` of the path decomposition. -/
def bag (p : ℕ) : Finset V := (verts n L).filter (fun v => lo n v ≤ p ∧ p ≤ hi n v)

/-- A valuation of the vertices is consistent with the input `x` if every
vertex has the value its gate computes. -/
def Consistent (x : ℕ → Bool) (ν : V → Bool) : Prop :=
  ∀ v, Valid n L v → ν v = (gate n L v).eval ν x

end Circuit

/-! ## The vertex set -/

theorem mem_pos (a m : ℕ) : a ∈ pos m ↔ 1 ≤ a ∧ a ≤ m := by
  simp only [pos, Finset.mem_image, Finset.mem_range]
  constructor
  · rintro ⟨b, hb, rfl⟩; omega
  · intro h; exact ⟨a - 1, by omega, by omega⟩

theorem mem_verts (n L : ℕ) (v : V) : v ∈ verts n L ↔ Valid n L v := by
  cases v <;> simp [verts, Valid, mem_pos] <;> omega

/-! ## The circuit is well formed -/

theorem args_valid (n L : ℕ) (hn : 1 ≤ n) (hL : 1 ≤ L) (v : V) (hv : Valid n L v) :
    ∀ u ∈ (gate n L v).args, Valid n L u := by
  cases v with
  | inp i => simp [gate, Gate.args]
  | nx0 => simp [gate, Gate.args, Valid]; omega
  | zero => simp [gate, Gate.args, Valid]; omega
  | carry i j =>
    simp only [Valid] at hv
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u (rfl | rfl)
    · unfold cntV; split_ifs <;> simp [Valid] <;> omega
    · unfold carryV; split_ifs <;> simp [Valid] <;> omega
  | orG i j =>
    simp only [Valid] at hv
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u (rfl | rfl)
    · unfold cntV; split_ifs <;> simp [Valid] <;> omega
    · unfold carryV; split_ifs <;> simp [Valid] <;> omega
  | nand i j => simp only [Valid] at hv; simp [gate, Gate.args, Valid]; omega
  | cnt i j => simp only [Valid] at hv; simp [gate, Gate.args, Valid]; omega
  | nw j => simp only [Valid] at hv; simp [gate, Gate.args, Valid]; omega
  | e i j =>
    simp only [Valid] at hv
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u (rfl | rfl)
    · unfold eqV lit; split_ifs <;> simp [Valid] <;> omega
    · unfold lit; split_ifs <;> simp [Valid] <;> omega
  | t i =>
    simp only [Valid] at hv
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u (rfl | rfl)
    · simp [Valid]; omega
    · unfold eqV lit; split_ifs <;> simp [Valid] <;> omega
  | o i =>
    simp only [Valid] at hv
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u (rfl | rfl)
    · unfold outV; split_ifs <;> simp [Valid] <;> omega
    · simp [Valid]; omega

/-- A rank that decreases from each gate to its arguments. -/
def rank (L : ℕ) : V → ℕ × ℕ × ℕ
  | .inp _ => (0, 0, 0)
  | .nx0 => (1, 0, 0)
  | .zero => (1, 0, 1)
  | .carry i j => (2, i, 3 * j)
  | .orG i j => (2, i, 3 * j + 1)
  | .nand i j => (2, i, 3 * j + 4)
  | .cnt i j => (2, i, 3 * j + 5)
  | .nw _ => (3, 0, 0)
  | .e i j => (4, i, j)
  | .t i => (4, i, L)
  | .o i => (4, i, L + 1)

/-- The lexicographic order on ranks. -/
def RankLt : ℕ × ℕ × ℕ → ℕ × ℕ × ℕ → Prop := Prod.Lex (· < ·) (Prod.Lex (· < ·) (· < ·))

theorem rankLt_wf : WellFounded RankLt :=
  WellFounded.prod_lex wellFounded_lt (WellFounded.prod_lex wellFounded_lt wellFounded_lt)

theorem rankLt_iff (a b : ℕ × ℕ × ℕ) :
    RankLt a b ↔ a.1 < b.1 ∨ a.1 = b.1 ∧ (a.2.1 < b.2.1 ∨ a.2.1 = b.2.1 ∧ a.2.2 < b.2.2) := by
  simp [RankLt, Prod.lex_def]

/-- The circuit is acyclic: every argument of a gate has a smaller rank. -/
theorem gate_rank_lt (n L : ℕ) (v : V) (hv : Valid n L v) :
    ∀ u ∈ (gate n L v).args, RankLt (rank L u) (rank L v) := by
  cases v with
  | inp i => simp [gate, Gate.args]
  | nx0 => simp [gate, Gate.args, rank, rankLt_iff]
  | zero => simp [gate, Gate.args, rank, rankLt_iff]
  | carry i j =>
    simp only [Valid] at hv
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u (rfl | rfl)
    · unfold cntV; split_ifs <;> simp [rank, rankLt_iff] <;> omega
    · unfold carryV; split_ifs <;> simp [rank, rankLt_iff] <;> omega
  | orG i j =>
    simp only [Valid] at hv
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u (rfl | rfl)
    · unfold cntV; split_ifs <;> simp [rank, rankLt_iff] <;> omega
    · unfold carryV; split_ifs <;> simp [rank, rankLt_iff]
  | nand i j =>
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u rfl
    exact Prod.Lex.right _ (Prod.Lex.right _ (by omega))
  | cnt i j => simp [gate, Gate.args, rank, rankLt_iff]
  | nw j => simp [gate, Gate.args, rank, rankLt_iff]
  | e i j =>
    simp only [Valid] at hv
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u (rfl | rfl)
    · unfold eqV lit; split_ifs <;> simp [rank, rankLt_iff] <;> omega
    · unfold lit; split_ifs <;> simp [rank, rankLt_iff]
  | t i =>
    simp only [Valid] at hv
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u (rfl | rfl)
    · simp [rank, rankLt_iff]
    · unfold eqV lit; split_ifs <;> simp [rank, rankLt_iff] <;> omega
  | o i =>
    simp only [Valid] at hv
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false]
    rintro u (rfl | rfl)
    · unfold outV; split_ifs <;> simp [rank, rankLt_iff] <;> omega
    · simp [rank, rankLt_iff]

/-- Each variable is read by exactly one vertex, its input vertex. -/
theorem gate_input_iff (n L : ℕ) (v : V) (hv : Valid n L v) (k : ℕ) :
    gate n L v = .input k ↔ v = .inp (k + 1) := by
  cases v <;> simp [gate, Valid] at hv ⊢ <;> omega

theorem eval_congr (x : ℕ → Bool) (g : Gate) (ν ν' : V → Bool) (h : ∀ u ∈ g.args, ν u = ν' u) :
    g.eval ν x = g.eval ν' x := by
  cases g <;> simp_all [Gate.eval, Gate.args]

/-- An acyclic circuit has at most one consistent valuation for each input. -/
theorem consistent_unique (n L : ℕ) (hn : 1 ≤ n) (hL : 1 ≤ L) (x : ℕ → Bool) (ν ν' : V → Bool)
    (h : Consistent n L x ν) (h' : Consistent n L x ν') : ∀ v, Valid n L v → ν v = ν' v := by
  intro v
  induction v using (InvImage.wf (rank L) rankLt_wf).induction with
  | h v ih =>
    intro hv
    rw [h v hv, h' v hv]
    exact eval_congr x _ ν ν' fun u hu =>
      ih u (gate_rank_lt n L v hv u hu) (args_valid n L hn hL v hv u hu)

/-! ## The circuit computes HWB_n -/

/-- The carry into bit `j` when adding the bit `b` to `m`. -/
def carryVal (m : ℕ) (b : Bool) : ℕ → Bool
  | 0 => b
  | j + 1 => carryVal m b j && m.testBit j

theorem carryVal_succ_half (m : ℕ) (b : Bool) (j : ℕ) :
    carryVal m b (j + 1) = carryVal (m / 2) (b && m.testBit 0) j := by
  induction j with
  | zero => simp [carryVal]
  | succ j ih =>
    rw [carryVal, ih, carryVal, Nat.testBit_succ]

theorem add_bit_half (m : ℕ) (b : Bool) :
    (m + b.toNat) / 2 = m / 2 + (b && m.testBit 0).toNat := by
  rcases Nat.mod_two_eq_zero_or_one m with h | h <;> cases b <;> simp [Nat.testBit_zero, h] <;>
    omega

/-- Ripple-carry addition of one bit. -/
theorem testBit_add_bit (m : ℕ) (b : Bool) (j : ℕ) :
    (m + b.toNat).testBit j = xor (m.testBit j) (carryVal m b j) := by
  induction j generalizing m b with
  | zero =>
    rcases Nat.mod_two_eq_zero_or_one m with h | h <;> cases b <;>
      simp [carryVal, Nat.testBit_zero, h, Nat.add_mod]
  | succ j ih =>
    rw [Nat.testBit_succ, add_bit_half, ih, carryVal_succ_half, Nat.testBit_succ]

/-- Bit `j` of the final count `w` equals bit `j` of `i`. -/
def litVal (w i j : ℕ) : Bool := if i.testBit j then w.testBit j else !w.testBit j

/-- Bits `0..j` of `w` equal those of `i`. -/
def eqVal (w i : ℕ) : ℕ → Bool
  | 0 => litVal w i 0
  | j + 1 => eqVal w i j && litVal w i (j + 1)

theorem eqVal_iff (w i j : ℕ) : eqVal w i j = true ↔ ∀ j' ≤ j, w.testBit j' = i.testBit j' := by
  induction j with
  | zero =>
    simp only [eqVal, litVal]
    constructor
    · intro h j' hj'
      obtain rfl : j' = 0 := by omega
      split_ifs at h with hb <;> simp_all
    · intro h
      have := h 0 le_rfl
      split_ifs with hb <;> simp_all
  | succ j ih =>
    simp only [eqVal, Bool.and_eq_true, ih, litVal]
    constructor
    · rintro ⟨h1, h2⟩ j' hj'
      rcases Nat.lt_or_ge j' (j + 1) with hlt | hge
      · exact h1 j' (by omega)
      · obtain rfl : j' = j + 1 := by omega
        split_ifs at h2 with hb <;> simp_all
    · intro h
      refine ⟨fun j' hj' => h j' (by omega), ?_⟩
      have := h (j + 1) le_rfl
      split_ifs with hb <;> simp_all

theorem eqVal_eq_decide (L w i : ℕ) (hL : 1 ≤ L) (hw : w < 2 ^ L) (hi : i < 2 ^ L) :
    eqVal w i (L - 1) = decide (w = i) := by
  have high : ∀ m, m < 2 ^ L → ∀ j, L ≤ j → m.testBit j = false := fun m hm j hj =>
    Nat.testBit_lt_two_pow (lt_of_lt_of_le hm (Nat.pow_le_pow_right (by norm_num) hj))
  by_cases hwi : w = i
  · subst hwi
    simpa using (eqVal_iff w w (L - 1)).2 fun _ _ => rfl
  · simp only [hwi, decide_false]
    by_contra hne
    apply hwi
    apply Nat.eq_of_testBit_eq
    intro j
    rcases Nat.lt_or_ge j L with hj | hj
    · exact (eqVal_iff w i (L - 1)).1 (by simpa using hne) j (by omega)
    · rw [high w hw j hj, high i hi j hj]

/-- `t 1 ∨ ... ∨ t i`, where `t k` is `x_k ∧ w = k`. -/
def outVal (x : ℕ → Bool) (w : ℕ) : ℕ → Bool
  | 0 => false
  | i + 1 => outVal x w i || (x i && decide (w = i + 1))

theorem outVal_eq (x : ℕ → Bool) (w : ℕ) (i : ℕ) :
    outVal x w i = decide (1 ≤ w ∧ w ≤ i ∧ x (w - 1) = true) := by
  induction i with
  | zero => simp [outVal]; omega
  | succ i ih =>
    rw [outVal, ih]
    by_cases hw : w = i + 1
    · subst hw; simp
    · have : (w ≤ i + 1) ↔ (w ≤ i) := by omega
      simp [hw, this]

theorem popc_le (x : ℕ → Bool) (i : ℕ) : popc x i ≤ i := by
  induction i with
  | zero => simp [popc]
  | succ i ih => simp only [popc]; cases x i <;> simp <;> omega

/-- The value of every vertex of the circuit. -/
def val (n L : ℕ) (x : ℕ → Bool) : V → Bool
  | .inp i => x (i - 1)
  | .nx0 => !x 0
  | .zero => false
  | .carry i j => carryVal (popc x (i - 1)) (x (i - 1)) j
  | .orG i j => (popc x (i - 1)).testBit j || carryVal (popc x (i - 1)) (x (i - 1)) j
  | .nand i j => !carryVal (popc x (i - 1)) (x (i - 1)) (j + 1)
  | .cnt i j => (popc x i).testBit j
  | .nw j => !(popc x n).testBit j
  | .e i j => eqVal (popc x n) i j
  | .t i => x (i - 1) && eqVal (popc x n) i (L - 1)
  | .o i => outVal x (popc x n) i

theorem val_cntV (n L : ℕ) (x : ℕ → Bool) (i j : ℕ) :
    val n L x (cntV i j) = (popc x i).testBit j := by
  unfold cntV; split_ifs with h
  · subst h; simp [val, popc]
  · rfl

theorem val_carryV (n L : ℕ) (x : ℕ → Bool) (i j : ℕ) :
    val n L x (carryV i j) = carryVal (popc x (i - 1)) (x (i - 1)) j := by
  unfold carryV; split_ifs with h
  · subst h; rfl
  · rfl

theorem val_lit (n L : ℕ) (x : ℕ → Bool) (i j : ℕ) :
    val n L x (lit n i j) = litVal (popc x n) i j := by
  unfold lit litVal; split_ifs <;> rfl

theorem val_eqV (n L : ℕ) (x : ℕ → Bool) (i j : ℕ) :
    val n L x (eqV n i j) = eqVal (popc x n) i j := by
  unfold eqV; split_ifs with h
  · subst h; rw [val_lit]; rfl
  · rfl

theorem val_outV (n L : ℕ) (x : ℕ → Bool) (i : ℕ) :
    val n L x (outV i) = outVal x (popc x n) i := by
  unfold outV; split_ifs with h
  · subst h; rfl
  · rfl

/-- The values `val` are consistent with the input. -/
theorem val_consistent (n L : ℕ) (hL : 1 ≤ L) (hnL : n < 2 ^ L) (x : ℕ → Bool) :
    Consistent n L x (val n L x) := by
  intro v hv
  cases v with
  | inp i => rfl
  | nx0 => rfl
  | zero => simp [gate, Gate.eval, val]
  | carry i j =>
    simp only [Valid] at hv
    obtain ⟨j, rfl⟩ : ∃ j', j = j' + 1 := ⟨j - 1, by omega⟩
    simp only [gate, Gate.eval, val_cntV, val_carryV, Nat.add_sub_cancel]
    simp only [val, carryVal, Bool.and_comm]
  | orG i j => simp only [gate, Gate.eval, val_cntV, val_carryV]; rfl
  | nand i j => rfl
  | cnt i j =>
    simp only [Valid] at hv
    obtain ⟨i, rfl⟩ : ∃ i', i = i' + 1 := ⟨i - 1, by omega⟩
    simp only [gate, Gate.eval, val, popc, Nat.add_sub_cancel, testBit_add_bit, carryVal]
    cases (popc x i).testBit j <;> cases carryVal (popc x i) (x i) j <;> rfl
  | nw j => rfl
  | e i j =>
    simp only [Valid] at hv
    obtain ⟨j, rfl⟩ : ∃ j', j = j' + 1 := ⟨j - 1, by omega⟩
    simp only [gate, Gate.eval, val_eqV, val_lit, Nat.add_sub_cancel]
    rfl
  | t i => simp only [gate, Gate.eval, val_eqV]; rfl
  | o i =>
    simp only [Valid] at hv
    obtain ⟨i, rfl⟩ : ∃ i', i = i' + 1 := ⟨i - 1, by omega⟩
    simp only [gate, Gate.eval]
    rw [val_outV]
    simp only [Nat.add_sub_cancel, val, outVal]
    rw [eqVal_eq_decide L _ _ hL (lt_of_le_of_lt (popc_le x n) hnL) (by omega)]

/-- The circuit computes HWB_n: every consistent valuation gives the output
vertex `o n` the value HWB_n(x), and a consistent valuation exists. -/
theorem computes_hwb (n L : ℕ) (hn : 1 ≤ n) (hnL : n < 2 ^ L) (x : ℕ → Bool) :
    Consistent n L x (val n L x) ∧
      ∀ ν, Consistent n L x ν → ν (.o n) = hwb n x := by
  have hL : 1 ≤ L := by
    rcases Nat.eq_zero_or_pos L with h | h
    · subst h; simp at hnL; omega
    · exact h
  refine ⟨val_consistent n L hL hnL x, fun ν hν => ?_⟩
  rw [consistent_unique n L hn hL x ν (val n L x) hν (val_consistent n L hL hnL x) (.o n)
    (by simp [Valid]; omega)]
  simp only [val, outVal_eq, hwb]
  have := popc_le x n
  by_cases h : 0 < popc x n
  · simp [h, this]; omega
  · simp [h]; omega

/-! ## The path decomposition -/

/-- Every vertex is in a bag: its interval is nonempty and lies in `1..n`. -/
theorem interval_valid (n L : ℕ) (hn : 1 ≤ n) (v : V) (hv : Valid n L v) :
    1 ≤ lo n v ∧ lo n v ≤ hi n v ∧ hi n v ≤ n := by
  cases v <;> simp only [Valid] at hv <;> simp only [lo, hi] <;> (repeat' split_ifs) <;> omega

/-- Closes a goal about the intervals of a gate and an argument at bag `p`. -/
macro "interval_tac" : tactic =>
  `(tactic| ((try simp only [cntV, carryV, eqV, lit, outV]) <;> (repeat' split_ifs) <;>
    (try simp only [lo, hi]) <;> (repeat' split_ifs) <;> omega))

/-- Every edge of the circuit's graph is in a bag. -/
theorem edge_in_bag (n L : ℕ) (hn : 1 ≤ n) (v : V) (hv : Valid n L v) :
    ∀ u ∈ (gate n L v).args, ∃ p, lo n u ≤ p ∧ p ≤ hi n u ∧ lo n v ≤ p ∧ p ≤ hi n v := by
  cases v <;> simp only [Valid] at hv <;>
    simp only [gate, Gate.args, List.mem_cons, List.not_mem_nil, or_false, forall_eq_or_imp,
      forall_eq, IsEmpty.forall_iff, implies_true]
  case nx0 => exact ⟨1, by interval_tac⟩
  case zero => exact ⟨⟨1, by interval_tac⟩, ⟨1, by interval_tac⟩⟩
  case carry i j => exact ⟨⟨i, by interval_tac⟩, ⟨i, by interval_tac⟩⟩
  case orG i j => exact ⟨⟨i, by interval_tac⟩, ⟨i, by interval_tac⟩⟩
  case nand i j => exact ⟨i, by interval_tac⟩
  case cnt i j => exact ⟨⟨i, by interval_tac⟩, ⟨i, by interval_tac⟩⟩
  case nw j => exact ⟨n, by interval_tac⟩
  case e i j => exact ⟨⟨i, by interval_tac⟩, ⟨i, by interval_tac⟩⟩
  case t i => exact ⟨⟨i, by interval_tac⟩, ⟨i, by interval_tac⟩⟩
  case o i => exact ⟨⟨i, by interval_tac⟩, ⟨i, by interval_tac⟩⟩

theorem mem_bag (n L p : ℕ) (v : V) :
    v ∈ bag n L p ↔ Valid n L v ∧ lo n v ≤ p ∧ p ≤ hi n v := by
  simp [bag, mem_verts]

/-- The bags containing a vertex are consecutive. -/
theorem bag_consecutive (n L : ℕ) (v : V) (p q r : ℕ) (hp : v ∈ bag n L p) (hq : v ∈ bag n L q)
    (hpr : p ≤ r) (hrq : r ≤ q) : v ∈ bag n L r := by
  rw [mem_bag] at *
  exact ⟨hp.1, by omega, by omega⟩

/-- The vertices that may be in bag `p`. -/
def cands (n L p : ℕ) : Finset V :=
  [V.inp p, V.nx0, V.zero, V.t p, V.o p, V.o (p - 1)].toFinset ∪
    (Finset.range L).image (fun j => V.carry p (j + 1)) ∪ (Finset.range L).image (V.orG p) ∪
    (Finset.range L).image (V.nand p) ∪ (Finset.range L).image (V.cnt p) ∪
    (Finset.range L).image (V.cnt (p - 1)) ∪ (Finset.range L).image (V.cnt n) ∪
    (Finset.range L).image V.nw ∪ (Finset.range L).image (V.e p)

theorem bag_subset_cands (n L p : ℕ) : bag n L p ⊆ cands n L p := by
  intro v hv
  rw [mem_bag] at hv
  obtain ⟨hv, hlo, hhi⟩ := hv
  cases v <;> simp only [Valid, lo, hi] at hv hlo hhi <;> simp [cands]
  case carry i j => exact ⟨j - 1, by omega, by omega, by omega⟩
  case cnt i j => split_ifs at hlo hhi <;> omega
  case o i => split_ifs at hhi <;> omega
  all_goals omega

theorem card_union_le_of {s t : Finset V} {a b : ℕ} (hs : s.card ≤ a) (ht : t.card ≤ b) :
    (s ∪ t).card ≤ a + b :=
  (Finset.card_union_le s t).trans (Nat.add_le_add hs ht)

theorem card_cands (n L p : ℕ) : (cands n L p).card ≤ 8 * L + 6 := by
  have h6 : [V.inp p, V.nx0, V.zero, V.t p, V.o p, V.o (p - 1)].toFinset.card ≤ 6 :=
    List.toFinset_card_le _
  have himg : ∀ f : ℕ → V, ((Finset.range L).image f).card ≤ L := fun f =>
    Finset.card_image_le.trans (by simp)
  have key : (cands n L p).card ≤ 6 + L + L + L + L + L + L + L + L := by
    unfold cands
    exact card_union_le_of (card_union_le_of (card_union_le_of (card_union_le_of
      (card_union_le_of (card_union_le_of (card_union_le_of (card_union_le_of h6
        (himg _)) (himg _)) (himg _)) (himg _)) (himg _)) (himg _)) (himg _)) (himg _)
  omega

theorem card_pos (m : ℕ) : (pos m).card ≤ m :=
  Finset.card_image_le.trans (by simp)

theorem card_prod_image_le {A B : Finset ℕ} {a b : ℕ} (f : ℕ × ℕ → V) (hA : A.card ≤ a)
    (hB : B.card ≤ b) : ((A ×ˢ B).image f).card ≤ a * b :=
  Finset.card_image_le.trans ((Finset.card_product A B).le.trans (Nat.mul_le_mul hA hB))

theorem card_verts (n L : ℕ) : (verts n L).card ≤ n * (5 * L + 3) + L + 2 := by
  have h2 : ({V.nx0, V.zero} : Finset V).card ≤ 2 := Finset.card_le_two
  have hr : (Finset.range L).card ≤ L := by simp
  have hf : ((Finset.range L).filter (1 ≤ ·)).card ≤ L := (Finset.card_filter_le _ _).trans hr
  have key : (verts n L).card ≤
      n + 2 + n * L + n * L + n * L + n * L + L + n * L + n + n := by
    unfold verts
    exact card_union_le_of (card_union_le_of (card_union_le_of (card_union_le_of
      (card_union_le_of (card_union_le_of (card_union_le_of (card_union_le_of
        (card_union_le_of (Finset.card_image_le.trans (card_pos n)) h2)
        (card_prod_image_le _ (card_pos n) (card_pos L)))
        (card_prod_image_le _ (card_pos n) hr)) (card_prod_image_le _ (card_pos n) hr))
        (card_prod_image_le _ (card_pos n) hr)) (Finset.card_image_le.trans hr))
        (card_prod_image_le _ (card_pos n) hf)) (Finset.card_image_le.trans (card_pos n)))
      (Finset.card_image_le.trans (card_pos n))
  nlinarith [key]

/-- A number of bits that can hold `n`, with `2^L ≤ 2n`, so `L ≤ log₂ n + 1`. -/
theorem exists_bits (n : ℕ) (hn : 1 ≤ n) : ∃ L, n < 2 ^ L ∧ 2 ^ L ≤ 2 * n := by
  induction n using Nat.strong_induction_on with
  | _ n ih =>
    by_cases h : n = 1
    · subst h
      exact ⟨1, by norm_num, by norm_num⟩
    · obtain ⟨L, h1, h2⟩ := ih (n / 2) (by omega) (by omega)
      refine ⟨L + 1, ?_, ?_⟩ <;> rw [pow_succ] <;> omega

/-- **Theorem 3.1.** For every n ≥ 1 and every L with n < 2^L, HWB_n has a
circuit with gates of fan-in at most 2, one input vertex per variable, at most
n·(5L + 3) + L + 2 vertices, and a path decomposition into bags `1..n` of at
most 8L + 6 vertices each. With `exists_bits`, L can be chosen with
2^L ≤ 2n, so the pathwidth (and treewidth) is at most 8·log₂ n + 13. -/
theorem hwb_circuit (n L : ℕ) (hn : 1 ≤ n) (hnL : n < 2 ^ L) :
    (∀ v, v ∈ verts n L ↔ Valid n L v) ∧
      (∀ v, Valid n L v → ∀ u ∈ (gate n L v).args, Valid n L u) ∧
      (∀ v, Valid n L v → ∀ u ∈ (gate n L v).args, RankLt (rank L u) (rank L v)) ∧
      (∀ v, Valid n L v → ∀ k, gate n L v = .input k ↔ v = .inp (k + 1)) ∧
      (∀ x, Consistent n L x (val n L x) ∧
        ∀ ν, Consistent n L x ν → ν (.o n) = hwb n x) ∧
      (∀ v, Valid n L v → ∃ p, v ∈ bag n L p) ∧
      (∀ v p, v ∈ bag n L p → 1 ≤ p ∧ p ≤ n) ∧
      (∀ v, Valid n L v → ∀ u ∈ (gate n L v).args, ∃ p, u ∈ bag n L p ∧ v ∈ bag n L p) ∧
      (∀ v p q r, v ∈ bag n L p → v ∈ bag n L q → p ≤ r → r ≤ q → v ∈ bag n L r) ∧
      (∀ p, (bag n L p).card ≤ 8 * L + 6) ∧
      (verts n L).card ≤ n * (5 * L + 3) + L + 2 := by
  have hL : 1 ≤ L := by
    rcases Nat.eq_zero_or_pos L with h | h
    · subst h; simp at hnL; omega
    · exact h
  refine ⟨mem_verts n L, fun v hv => args_valid n L hn hL v hv,
    fun v hv => gate_rank_lt n L v hv, fun v hv k => gate_input_iff n L v hv k,
    fun x => computes_hwb n L hn hnL x, ?_, ?_, ?_, ?_, ?_, card_verts n L⟩
  · intro v hv
    have := interval_valid n L hn v hv
    exact ⟨lo n v, (mem_bag n L _ v).2 ⟨hv, le_rfl, this.2.1⟩⟩
  · intro v p hp
    rw [mem_bag] at hp
    have := interval_valid n L hn v hp.1
    omega
  · intro v hv u hu
    obtain ⟨p, h1, h2, h3, h4⟩ := edge_in_bag n L hn v hv u hu
    exact ⟨p, (mem_bag n L p u).2 ⟨args_valid n L hn hL v hv u hu, h1, h2⟩,
      (mem_bag n L p v).2 ⟨hv, h3, h4⟩⟩
  · exact fun v p q r => bag_consecutive n L v p q r
  · exact fun p => (Finset.card_le_card (bag_subset_cands n L p)).trans (card_cands n L p)

end Define.CircuitTreewidthCanonicalSdd
