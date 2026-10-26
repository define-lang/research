import Mathlib.Analysis.Calculus.Deriv.Add
import Mathlib.Analysis.Calculus.Deriv.Inv
import Mathlib.Analysis.Calculus.Deriv.Mul
import Mathlib.Analysis.Calculus.Deriv.Pow
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.LinearCombination
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity

set_option warningAsError true
set_option autoImplicit false

/-!
# Linear interpolation has no single-use form

This file formalizes the English proof in
`linear-interpolation-has-no-single-use-form.md`. The main theorem is
`Define.SingleUseExpression.linear_interpolation_has_no_single_use_form`.

Arithmetic expressions follow Definitions 1 and 2 of Lorkowski, Kosheleva,
and Kreinovich, "Every Function Computable by an Arithmetic SUE Expression is
a Ratio of Two Multi-Linear Functions": a sequence of rules
`sᵢ := uᵢ ⊙ᵢ vᵢ`, where each operand is a real constant, an input, or an
earlier result. Rules are numbered from 0, and the expression's value is the
value of its last rule. The inputs are `x 0 = a`, `x 1 = b`, and `x 2 = t`.
-/

namespace Define.SingleUseExpression

noncomputable section

/-- One of the four arithmetic operations. -/
inductive Op where
  | add
  | sub
  | mul
  | div

/-- Lean's division is total, with `u / 0 = 0`. `DefinedAt` excludes those
points, so the value at a division by zero is never used. -/
def Op.apply : Op → ℝ → ℝ → ℝ
  | .add, u, v => u + v
  | .sub, u, v => u - v
  | .mul, u, v => u * v
  | .div, u, v => u / v

/-- An operand: a real constant, one of the three inputs, or an earlier result. -/
inductive Operand where
  | const (c : ℝ)
  | input (j : Fin 3)
  | result (k : ℕ)

/-- A rule `u ⊙ v`. -/
structure Rule where
  op : Op
  left : Operand
  right : Operand

/-- The left operand for `true` and the right operand for `false`. -/
def Rule.operand (rule : Rule) : Bool → Operand
  | true => rule.left
  | false => rule.right

/-- The rules `rule 0, …, rule (length - 1)`. Rules at larger indices are
ignored. -/
structure Expression where
  length : ℕ
  rule : ℕ → Rule

/-- A point of `ℝ³`: `x 0 = a`, `x 1 = b`, and `x 2 = t`. -/
abbrev Point := Fin 3 → ℝ

/-- Linear interpolation `a + t * (b - a)`. -/
def lerp (x : Point) : ℝ := x 0 + x 2 * (x 1 - x 0)

/-- The value of an operand of rule `i`, given the values of the earlier rules. -/
def evalOperand (x : Point) (i : ℕ) (earlier : (k : ℕ) → k < i → ℝ) : Operand → ℝ
  | .const c => c
  | .input j => x j
  | .result k => if h : k < i then earlier k h else 0

/-- The value `sᵢ` at the point `x`. -/
def value (e : Expression) (x : Point) (i : ℕ) : ℝ :=
  (e.rule i).op.apply
    (evalOperand x i (fun k _ => value e x k) (e.rule i).left)
    (evalOperand x i (fun k _ => value e x k) (e.rule i).right)
termination_by i
decreasing_by all_goals assumption

/-- The value of an operand of rule `i`. -/
def operandValue (e : Expression) (x : Point) (i : ℕ) (o : Operand) : ℝ :=
  evalOperand x i (fun k _ => value e x k) o

theorem value_eq (e : Expression) (x : Point) (i : ℕ) :
    value e x i =
      (e.rule i).op.apply (operandValue e x i (e.rule i).left)
        (operandValue e x i (e.rule i).right) := by
  rw [value]
  rfl

/-- The inputs of an operand of rule `i`, given the inputs of the earlier rules. -/
def operandInputsWith (i : ℕ) (earlier : (k : ℕ) → k < i → Finset (Fin 3)) :
    Operand → Finset (Fin 3)
  | .const _ => ∅
  | .input j => {j}
  | .result k => if h : k < i then earlier k h else ∅

/-- The inputs that label the leaves of the tree of `sᵢ`. -/
def inputs (e : Expression) (i : ℕ) : Finset (Fin 3) :=
  operandInputsWith i (fun k _ => inputs e k) (e.rule i).left ∪
    operandInputsWith i (fun k _ => inputs e k) (e.rule i).right
termination_by i
decreasing_by all_goals assumption

/-- The inputs of an operand of rule `i`. -/
def operandInputs (e : Expression) (i : ℕ) (o : Operand) : Finset (Fin 3) :=
  operandInputsWith i (fun k _ => inputs e k) o

theorem inputs_eq (e : Expression) (i : ℕ) :
    inputs e i = operandInputs e i (e.rule i).left ∪ operandInputs e i (e.rule i).right := by
  rw [inputs]
  rfl

/-- Every result operand of rule `i` names an earlier rule, and there is at
least one rule. -/
def Expression.WellFormed (e : Expression) : Prop :=
  0 < e.length ∧ ∀ i < e.length, ∀ side k, (e.rule i).operand side = .result k → k < i

/-- Definition 2: each input and each result appears at most once among all
the operands. -/
def Expression.SingleUse (e : Expression) : Prop :=
  (∀ i < e.length, ∀ i' < e.length, ∀ side side' j,
      (e.rule i).operand side = .input j → (e.rule i').operand side' = .input j →
        i = i' ∧ side = side') ∧
    ∀ i < e.length, ∀ i' < e.length, ∀ side side' k,
      (e.rule i).operand side = .result k → (e.rule i').operand side' = .result k →
        i = i' ∧ side = side'

/-- The expression is defined at `x` when no rule divides by zero there. As in
the paper, every rule is performed, including rules whose results are unused. -/
def Expression.DefinedAt (e : Expression) (x : Point) : Prop :=
  ∀ i < e.length, (e.rule i).op = .div → operandValue e x i (e.rule i).right ≠ 0

/-- The expression's value: the value of its last rule. -/
def Expression.result (e : Expression) (x : Point) : ℝ :=
  value e x (e.length - 1)

/-- The expression computes `F` on `U`: it is defined at every point of `U`
and equals `F` there. -/
def Expression.ComputesOn (e : Expression) (F : Point → ℝ) (U : Set Point) : Prop :=
  ∀ x ∈ U, e.DefinedAt x ∧ e.result x = F x

/-! ## Dependence on inputs -/

/-- `F` does not depend on input `m`. -/
def Ignores (F : Point → ℝ) (m : Fin 3) : Prop :=
  ∀ x y : Point, (∀ i, i ≠ m → x i = y i) → F x = F y

theorem value_congr (e : Expression) (x y : Point) :
    ∀ i, (∀ j ∈ inputs e i, x j = y j) → value e x i = value e y i := by
  intro i
  induction i using Nat.strong_induction_on with
  | _ i ih =>
    intro hxy
    have operand_congr : ∀ o : Operand, (∀ j ∈ operandInputs e i o, x j = y j) →
        operandValue e x i o = operandValue e y i o := by
      intro o ho
      cases o with
      | const c => rfl
      | input j =>
        simp only [operandValue, evalOperand]
        exact ho j (by simp [operandInputs, operandInputsWith])
      | result k =>
        simp only [operandValue, evalOperand]
        split_ifs with hk
        · apply ih k hk
          intro j hj
          apply ho j
          simp [operandInputs, operandInputsWith, hk, hj]
        · rfl
    rw [inputs_eq] at hxy
    rw [value_eq, value_eq,
      operand_congr _ (fun j hj => hxy j (Finset.mem_union_left _ hj)),
      operand_congr _ (fun j hj => hxy j (Finset.mem_union_right _ hj))]

theorem operandValue_congr (e : Expression) (x y : Point) (i : ℕ) (o : Operand)
    (h : ∀ j ∈ operandInputs e i o, x j = y j) :
    operandValue e x i o = operandValue e y i o := by
  cases o with
  | const c => rfl
  | input j =>
    simp only [operandValue, evalOperand]
    exact h j (by simp [operandInputs, operandInputsWith])
  | result k =>
    simp only [operandValue, evalOperand]
    split_ifs with hk
    · apply value_congr e x y k
      intro j hj
      apply h j
      simp [operandInputs, operandInputsWith, hk, hj]
    · rfl

theorem operandValue_ignores (e : Expression) (i : ℕ) (o : Operand) (m : Fin 3)
    (hm : m ∉ operandInputs e i o) : Ignores (fun x => operandValue e x i o) m := by
  intro x y hxy
  apply operandValue_congr
  intro j hj
  apply hxy
  rintro rfl
  exact hm hj

/-! ## Single use makes the two operands of a rule use different inputs -/

/-- `Reaches e m y`: rule `y` is in the tree of rule `m`. -/
inductive Reaches (e : Expression) : ℕ → ℕ → Prop where
  | refl (m : ℕ) : Reaches e m m
  | step {m parent child : ℕ} (side : Bool) :
      Reaches e m parent → (e.rule parent).operand side = .result child → Reaches e m child

theorem Reaches.le {e : Expression} (hwf : e.WellFormed) {m y : ℕ} (hm : m < e.length)
    (h : Reaches e m y) : y ≤ m := by
  induction h with
  | refl => exact le_rfl
  | step side _ hchild ih =>
    have := hwf.2 _ (lt_of_le_of_lt ih hm) side _ hchild
    omega

theorem Reaches.prepend {e : Expression} {m k r : ℕ} (side : Bool)
    (hk : (e.rule m).operand side = .result k) (h : Reaches e k r) : Reaches e m r := by
  induction h with
  | refl => exact Reaches.step side (Reaches.refl m) hk
  | step side' _ hchild ih => exact Reaches.step side' ih hchild

theorem Reaches.last_step {e : Expression} {m y : ℕ} (h : Reaches e m y) (hne : m ≠ y) :
    ∃ parent side, Reaches e m parent ∧ (e.rule parent).operand side = .result y := by
  cases h with
  | refl => exact absurd rfl hne
  | step side hparent hchild => exact ⟨_, side, hparent, hchild⟩

theorem mem_inputs {e : Expression} (m : ℕ) :
    ∀ j ∈ inputs e m, ∃ r side, Reaches e m r ∧ (e.rule r).operand side = .input j := by
  induction m using Nat.strong_induction_on with
  | _ m ih =>
    intro j hj
    rw [inputs_eq, Finset.mem_union] at hj
    have operand_case : ∀ side : Bool, j ∈ operandInputs e m ((e.rule m).operand side) →
        ∃ r side, Reaches e m r ∧ (e.rule r).operand side = .input j := by
      intro side hside
      cases ho : (e.rule m).operand side with
      | const c => simp [ho, operandInputs, operandInputsWith] at hside
      | input j' =>
        rw [ho] at hside
        simp only [operandInputs, operandInputsWith, Finset.mem_singleton] at hside
        subst hside
        exact ⟨m, side, Reaches.refl m, ho⟩
      | result k =>
        rw [ho] at hside
        simp only [operandInputs, operandInputsWith] at hside
        split_ifs at hside with hk
        · obtain ⟨r, side', hr, hro⟩ := ih k hk j hside
          exact ⟨r, side', Reaches.prepend side ho hr, hro⟩
        · simp at hside
    rcases hj with hj | hj
    · exact operand_case true hj
    · exact operand_case false hj

theorem Reaches.total {e : Expression} (hwf : e.WellFormed) (hsu : e.SingleUse)
    {m₁ r : ℕ} (hm₁ : m₁ < e.length) (h₁ : Reaches e m₁ r) :
    ∀ {m₂}, m₂ < e.length → Reaches e m₂ r → Reaches e m₁ m₂ ∨ Reaches e m₂ m₁ := by
  induction h₁ with
  | refl => intro m₂ _ h₂; exact Or.inr h₂
  | @step parent child side hparent hchild ih =>
    intro m₂ hm₂ h₂
    cases h₂ with
    | refl => exact Or.inl (Reaches.step side hparent hchild)
    | step side' hparent' hchild' =>
      have hp : parent < e.length := lt_of_le_of_lt (hparent.le hwf hm₁) hm₁
      have hp' := lt_of_le_of_lt (hparent'.le hwf hm₂) hm₂
      obtain ⟨rfl, -⟩ := hsu.2 _ hp _ hp' side side' child hchild hchild'
      exact ih hm₂ hparent'

theorem operandInputs_disjoint {e : Expression} (hwf : e.WellFormed) (hsu : e.SingleUse)
    {i : ℕ} (hi : i < e.length) :
    Disjoint (operandInputs e i (e.rule i).left) (operandInputs e i (e.rule i).right) := by
  rw [Finset.disjoint_left]
  intro j hjl hjr
  have hl : (e.rule i).operand true = (e.rule i).left := rfl
  have hr : (e.rule i).operand false = (e.rule i).right := rfl
  -- An input `j` of a result operand `k` occurs at some rule reached from `k`.
  have via_result : ∀ side k, (e.rule i).operand side = .result k →
      j ∈ operandInputs e i (.result k) →
        k < i ∧ ∃ r side', Reaches e k r ∧ (e.rule r).operand side' = .input j := by
    intro side k hk hj
    have hki := hwf.2 i hi side k hk
    simp only [operandInputs, operandInputsWith, hki, dite_true] at hj
    exact ⟨hki, mem_inputs k j hj⟩
  -- A rule reached from an earlier rule `k` is not `i`.
  have not_reach_i : ∀ k, k < i → ¬ Reaches e k i := by
    intro k hki hreach
    have := hreach.le hwf (lt_trans hki hi)
    omega
  -- An input `j` used directly by rule `i` cannot also occur below a result operand.
  have input_and_result : ∀ side side' k, side ≠ side' →
      (e.rule i).operand side = .input j → (e.rule i).operand side' = .result k →
        j ∈ operandInputs e i (.result k) → False := by
    intro side side' k _ hin hres hj
    obtain ⟨hki, r, side'', hreach, hro⟩ := via_result side' k hres hj
    have hr : r < e.length := lt_of_le_of_lt (hreach.le hwf (lt_trans hki hi)) (lt_trans hki hi)
    obtain ⟨rfl, -⟩ := hsu.1 r hr i hi side'' side j hro hin
    exact not_reach_i k hki hreach
  cases hL : (e.rule i).left with
  | const c => simp [hL, operandInputs, operandInputsWith] at hjl
  | input jl =>
    rw [hL] at hjl
    simp only [operandInputs, operandInputsWith, Finset.mem_singleton] at hjl
    subst hjl
    cases hR : (e.rule i).right with
    | const c => simp [hR, operandInputs, operandInputsWith] at hjr
    | input jr =>
      rw [hR] at hjr
      simp only [operandInputs, operandInputsWith, Finset.mem_singleton] at hjr
      subst hjr
      have := (hsu.1 i hi i hi true false _ (hl.trans hL) (hr.trans hR)).2
      exact Bool.noConfusion this
    | result k =>
      rw [hR] at hjr
      exact input_and_result true false k (by decide) (hl.trans hL) (hr.trans hR) hjr
  | result kl =>
    rw [hL] at hjl
    cases hR : (e.rule i).right with
    | const c => simp [hR, operandInputs, operandInputsWith] at hjr
    | input jr =>
      rw [hR] at hjr
      simp only [operandInputs, operandInputsWith, Finset.mem_singleton] at hjr
      subst hjr
      exact input_and_result false true kl (by decide) (hr.trans hR) (hl.trans hL) hjl
    | result kr =>
      rw [hR] at hjr
      obtain ⟨hkl, rl, sl, hreachl, hrol⟩ := via_result true kl (hl.trans hL) hjl
      obtain ⟨hkr, rr, sr, hreachr, hror⟩ := via_result false kr (hr.trans hR) hjr
      have hkl' : kl < e.length := lt_trans hkl hi
      have hkr' : kr < e.length := lt_trans hkr hi
      have hrl : rl < e.length := lt_of_le_of_lt (hreachl.le hwf hkl') hkl'
      have hrr : rr < e.length := lt_of_le_of_lt (hreachr.le hwf hkr') hkr'
      obtain ⟨rfl, -⟩ := hsu.1 rl hrl rr hrr sl sr j hrol hror
      by_cases hk : kl = kr
      · subst hk
        have := (hsu.2 i hi i hi true false _ (hl.trans hL) (hr.trans hR)).2
        exact Bool.noConfusion this
      -- One of the two results is reached from the other, so its parent, which is
      -- rule `i`, would be reached from an earlier rule.
      rcases Reaches.total hwf hsu hkl' hreachl hkr' hreachr with h | h
      · obtain ⟨parent, side, hp, hpc⟩ := h.last_step hk
        have hpl : parent < e.length := lt_of_le_of_lt (hp.le hwf hkl') hkl'
        obtain ⟨rfl, -⟩ := hsu.2 parent hpl i hi side false kr hpc (hr.trans hR)
        exact not_reach_i kl hkl hp
      · obtain ⟨parent, side, hp, hpc⟩ := h.last_step (Ne.symm hk)
        have hpr : parent < e.length := lt_of_le_of_lt (hp.le hwf hkr') hkr'
        obtain ⟨rfl, -⟩ := hsu.2 parent hpr i hi side true kl hpc (hl.trans hL)
        exact not_reach_i kr hkr hp

/-! ## Möbius maps of linear interpolation -/

/-- `(α · w + β) / (γ · w + δ)` equals linear interpolation at every point of
`V`, with a nonzero denominator. -/
def MobiusMatches (w : Point → ℝ) (α β γ δ : ℝ) (V : Set Point) : Prop :=
  ∀ x ∈ V, γ * w x + δ ≠ 0 ∧ (α * w x + β) / (γ * w x + δ) = lerp x

theorem MobiusMatches.transform {V : Set Point} {w w' k : Point → ℝ}
    {α β γ δ α' β' γ' δ' : ℝ} (h : MobiusMatches w α β γ δ V) (hk : ∀ x ∈ V, k x ≠ 0)
    (hnum : ∀ x ∈ V, α' * w' x + β' = k x * (α * w x + β))
    (hden : ∀ x ∈ V, γ' * w' x + δ' = k x * (γ * w x + δ)) :
    MobiusMatches w' α' β' γ' δ' V := by
  intro x hx
  obtain ⟨h1, h2⟩ := h x hx
  rw [hnum x hx, hden x hx]
  exact ⟨mul_ne_zero (hk x hx) h1, by rw [mul_div_mul_left _ _ (hk x hx)]; exact h2⟩

/-- Lemma 6: inverting `f = (α · w + β) / (γ · w + δ)`. -/
theorem invert_mobius {α β γ δ w f : ℝ} (hdet : α * δ - β * γ ≠ 0) (hden : γ * w + δ ≠ 0)
    (hf : (α * w + β) / (γ * w + δ) = f) :
    -γ * f + α ≠ 0 ∧ w = (δ * f + -β) / (-γ * f + α) := by
  rw [div_eq_iff hden] at hf
  have key : α * δ - β * γ = (-γ * f + α) * (γ * w + δ) := by linear_combination (-γ) * hf
  have hne : -γ * f + α ≠ 0 := by
    intro h
    apply hdet
    rw [key, h, zero_mul]
  refine ⟨hne, ?_⟩
  rw [eq_div_iff hne]
  linear_combination hf

/-! ## Points near a center -/

theorem near (c ε : ℝ) (hε : 0 < ε) (k : ℝ) (hk0 : 0 ≤ k) (hk : k < 3) :
    c + k * (ε / 3) ∈ Metric.ball c ε := by
  rw [Metric.mem_ball, Real.dist_eq, add_sub_cancel_left, abs_of_nonneg (by positivity)]
  nlinarith

theorem vec_mem_ball {c : Point} {ε : ℝ} (hε : 0 < ε) {x₀ x₁ x₂ : ℝ}
    (h₀ : x₀ ∈ Metric.ball (c 0) ε) (h₁ : x₁ ∈ Metric.ball (c 1) ε)
    (h₂ : x₂ ∈ Metric.ball (c 2) ε) : ![x₀, x₁, x₂] ∈ Metric.ball c ε := by
  rw [Metric.mem_ball, dist_pi_lt_iff hε]
  intro i
  fin_cases i
  · exact h₀
  · exact h₁
  · exact h₂

/-- Lemma 4: on any ball, linear interpolation depends on `a` and on `t`. -/
theorem lerp_depends {c : Point} {ε : ℝ} (hε : 0 < ε) (m : Fin 3) (hm : m = 0 ∨ m = 2)
    (hF : ∀ x ∈ Metric.ball c ε, ∀ y ∈ Metric.ball c ε, (∀ i, i ≠ m → x i = y i) →
      lerp x = lerp y) : False := by
  have m0 := near (c 0) ε hε 0 le_rfl (by norm_num)
  have m1 := near (c 1) ε hε 0 le_rfl (by norm_num)
  have m2 := near (c 2) ε hε 0 le_rfl (by norm_num)
  have n0 := near (c 0) ε hε 1 (by norm_num) (by norm_num)
  have n2 := near (c 2) ε hε 1 (by norm_num) (by norm_num)
  set h := ε / 3 with hh
  have hpos : 0 < h := by positivity
  rcases hm with rfl | rfl
  · have e1 := hF _ (vec_mem_ball hε n0 m1 m2) _ (vec_mem_ball hε m0 m1 m2)
      (by intro i hi; fin_cases i <;> simp_all)
    have e2 := hF _ (vec_mem_ball hε n0 m1 n2) _ (vec_mem_ball hε m0 m1 n2)
      (by intro i hi; fin_cases i <;> simp_all)
    simp only [lerp, Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.cons_val_two,
      Matrix.head_cons, Matrix.tail_cons] at e1 e2
    have : h * h = 0 := by linear_combination e1 - e2
    nlinarith
  · have e1 := hF _ (vec_mem_ball hε m0 m1 n2) _ (vec_mem_ball hε m0 m1 m2)
      (by intro i hi; fin_cases i <;> simp_all)
    have e2 := hF _ (vec_mem_ball hε n0 m1 n2) _ (vec_mem_ball hε n0 m1 m2)
      (by intro i hi; fin_cases i <;> simp_all)
    simp only [lerp, Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.cons_val_two,
      Matrix.head_cons, Matrix.tail_cons] at e1 e2
    have : h * h = 0 := by linear_combination e1 - e2
    nlinarith

theorem MobiusMatches.not_ignores {c : Point} {ε : ℝ} (hε : 0 < ε) {w : Point → ℝ}
    {α β γ δ : ℝ} (h : MobiusMatches w α β γ δ (Metric.ball c ε)) (m : Fin 3)
    (hm : m = 0 ∨ m = 2) (hw : Ignores w m) : False := by
  apply lerp_depends hε m hm
  intro x hx y hy hxy
  rw [← (h x hx).2, ← (h y hy).2, hw x y hxy]

theorem MobiusMatches.not_const {c : Point} {ε : ℝ} (hε : 0 < ε) {w : Point → ℝ}
    {α β γ δ : ℝ} (h : MobiusMatches w α β γ δ (Metric.ball c ε)) (κ : ℝ)
    (hw : ∀ x ∈ Metric.ball c ε, w x = κ) : False := by
  apply lerp_depends hε 2 (Or.inr rfl)
  intro x hx y hy _
  rw [← (h x hx).2, ← (h y hy).2, hw x hx, hw y hy]

/-! ## Derivatives -/

/-- `p · s - q · r`, the determinant of `(p · u + q) / (r · u + s)`. -/
def det (p q r s : ℝ) : ℝ := p * s - q * r

/-- `P + Q · ξ + R · τ + S · ξ · τ`. Linear interpolation is of this form in two
inputs when the third is fixed. -/
def bilin (P Q R S ξ τ : ℝ) : ℝ := P + Q * ξ + R * τ + S * ξ * τ

theorem hasDerivAt_mobius_affine (p q r s a b y : ℝ) (hden : r * (a + b * y) + s ≠ 0) :
    HasDerivAt (fun y => (p * (a + b * y) + q) / (r * (a + b * y) + s))
      (det p q r s * b / (r * (a + b * y) + s) ^ 2) y := by
  have hu : HasDerivAt (fun y => a + b * y) b y :=
    HasDerivAt.congr_deriv (HasDerivAt.const_add a (HasDerivAt.const_mul b (hasDerivAt_id' y)))
      (mul_one b)
  have hn := HasDerivAt.add_const q (HasDerivAt.const_mul p hu)
  have hd := HasDerivAt.add_const s (HasDerivAt.const_mul r hu)
  refine HasDerivAt.congr_deriv (HasDerivAt.div hn hd hden) ?_
  unfold det
  ring

theorem hasDerivAt_weight (D Q S r s a m τ : ℝ) (hden : r * (a + m * τ) + s ≠ 0) :
    HasDerivAt (fun τ => D * (Q + S * τ) / (r * (a + m * τ) + s) ^ 2)
      (D * (S * (r * (a + m * τ) + s) - 2 * r * m * (Q + S * τ)) /
        (r * (a + m * τ) + s) ^ 3) τ := by
  have hu : HasDerivAt (fun τ => a + m * τ) m τ :=
    HasDerivAt.congr_deriv (HasDerivAt.const_add a (HasDerivAt.const_mul m (hasDerivAt_id' τ)))
      (mul_one m)
  have hn : HasDerivAt (fun τ => D * (Q + S * τ)) (D * S) τ :=
    HasDerivAt.congr_deriv
      (HasDerivAt.const_mul D
        (HasDerivAt.const_add Q (HasDerivAt.const_mul S (hasDerivAt_id' τ))))
      (by ring)
  have hd := HasDerivAt.fun_pow (HasDerivAt.add_const s (HasDerivAt.const_mul r hu)) 2
  refine HasDerivAt.congr_deriv (HasDerivAt.div hn hd (pow_ne_zero 2 hden)) ?_
  rw [show (2 : ℕ) - 1 = 1 from rfl, pow_one]
  push_cast
  field_simp

theorem hasDerivAt_xi (p q r s P Q R S ξ τ : ℝ) (hden : r * bilin P Q R S ξ τ + s ≠ 0) :
    HasDerivAt (fun ξ => (p * bilin P Q R S ξ τ + q) / (r * bilin P Q R S ξ τ + s))
      (det p q r s * (Q + S * τ) / (r * bilin P Q R S ξ τ + s) ^ 2) ξ := by
  have hform : ∀ ξ, bilin P Q R S ξ τ = (P + R * τ) + (Q + S * τ) * ξ := by
    intro ξ; unfold bilin; ring
  simp only [hform] at hden ⊢
  exact hasDerivAt_mobius_affine p q r s _ _ ξ hden

theorem hasDerivAt_tau (p q r s P Q R S ξ τ : ℝ) (hden : r * bilin P Q R S ξ τ + s ≠ 0) :
    HasDerivAt (fun τ => (p * bilin P Q R S ξ τ + q) / (r * bilin P Q R S ξ τ + s))
      (det p q r s * (R + S * ξ) / (r * bilin P Q R S ξ τ + s) ^ 2) τ := by
  have hform : ∀ τ, bilin P Q R S ξ τ = (P + Q * ξ) + (R + S * ξ) * τ := by
    intro τ; unfold bilin; ring
  simp only [hform] at hden ⊢
  exact hasDerivAt_mobius_affine p q r s _ _ τ hden

theorem hasDerivAt_weight_tau (p q r s P Q R S ξ τ : ℝ) (hden : r * bilin P Q R S ξ τ + s ≠ 0) :
    HasDerivAt (fun τ => det p q r s * (Q + S * τ) / (r * bilin P Q R S ξ τ + s) ^ 2)
      (det p q r s * (S * (r * bilin P Q R S ξ τ + s) - 2 * r * (R + S * ξ) * (Q + S * τ)) /
        (r * bilin P Q R S ξ τ + s) ^ 3) τ := by
  have hform : ∀ τ, bilin P Q R S ξ τ = (P + Q * ξ) + (R + S * ξ) * τ := by
    intro τ; unfold bilin; ring
  simp only [hform] at hden ⊢
  exact hasDerivAt_weight _ Q S r s _ _ τ hden

/-! ## Lemmas 7 and 8: the separability equations -/

/-- The additive separability equation `A`, divided by a nonzero factor. -/
def condAdd (r s P Q R S ξ τ : ℝ) : ℝ :=
  S * (r * bilin P Q R S ξ τ + s) - 2 * r * (R + S * ξ) * (Q + S * τ)

/-- The multiplicative separability equation `B`, divided by a nonzero factor. -/
def condMul (p q r s P Q R S ξ τ : ℝ) : ℝ :=
  (p * bilin P Q R S ξ τ + q) * condAdd r s P Q R S ξ τ -
    det p q r s * (R + S * ξ) * (Q + S * τ)

theorem additive_condition {p q r s P Q R S ξc τc ε : ℝ} (hD : det p q r s ≠ 0)
    {α β : ℝ → ℝ}
    (hden : ∀ ξ ∈ Metric.ball ξc ε, ∀ τ ∈ Metric.ball τc ε, r * bilin P Q R S ξ τ + s ≠ 0)
    (hsep : ∀ ξ ∈ Metric.ball ξc ε, ∀ τ ∈ Metric.ball τc ε,
      (p * bilin P Q R S ξ τ + q) / (r * bilin P Q R S ξ τ + s) = α ξ + β τ)
    {ξ₀ τ₀ : ℝ} (hξ₀ : ξ₀ ∈ Metric.ball ξc ε) (hτ₀ : τ₀ ∈ Metric.ball τc ε) :
    condAdd r s P Q R S ξ₀ τ₀ = 0 := by
  set E : ℝ → ℝ := fun τ => det p q r s * (Q + S * τ) / (r * bilin P Q R S ξ₀ τ + s) ^ 2
    with hE
  have hα : ∀ τ ∈ Metric.ball τc ε, HasDerivAt α (E τ) ξ₀ := by
    intro τ hτ
    have hG := HasDerivAt.sub_const (β τ) (hasDerivAt_xi p q r s P Q R S ξ₀ τ (hden ξ₀ hξ₀ τ hτ))
    apply HasDerivAt.congr_of_eventuallyEq hG
    filter_upwards [Metric.isOpen_ball.mem_nhds hξ₀] with ξ hξ
    rw [hsep ξ hξ τ hτ]
    ring
  have hconst : ∀ τ ∈ Metric.ball τc ε, E τ = E τ₀ := fun τ hτ =>
    HasDerivAt.unique (hα τ hτ) (hα τ₀ hτ₀)
  have hE₀ : HasDerivAt E 0 τ₀ := by
    apply HasDerivAt.congr_of_eventuallyEq (hasDerivAt_const τ₀ (E τ₀))
    filter_upwards [Metric.isOpen_ball.mem_nhds hτ₀] with τ hτ using hconst τ hτ
  have h₀ := HasDerivAt.unique (hasDerivAt_weight_tau p q r s P Q R S ξ₀ τ₀ (hden ξ₀ hξ₀ τ₀ hτ₀)) hE₀
  have hd := hden ξ₀ hξ₀ τ₀ hτ₀
  rw [div_eq_zero_iff] at h₀
  rcases h₀ with h₀ | h₀
  · rcases mul_eq_zero.1 h₀ with h | h
    · exact absurd h hD
    · unfold condAdd
      exact h
  · exact absurd ((pow_eq_zero_iff (by norm_num)).1 h₀) hd

theorem weight_not_zero {p q r s P Q R S ξ₀ τc ε : ℝ} (hε : 0 < ε) (hD : det p q r s ≠ 0)
    (hS : S ≠ 0)
    (h : ∀ τ ∈ Metric.ball τc ε,
      det p q r s * (Q + S * τ) / (r * bilin P Q R S ξ₀ τ + s) ^ 2 = 0)
    (hden : ∀ τ ∈ Metric.ball τc ε, r * bilin P Q R S ξ₀ τ + s ≠ 0) : False := by
  have m0 := near τc ε hε 0 le_rfl (by norm_num)
  have m1 := near τc ε hε 1 (by norm_num) (by norm_num)
  have zero_at : ∀ τ ∈ Metric.ball τc ε, Q + S * τ = 0 := by
    intro τ hτ
    have := h τ hτ
    rw [div_eq_zero_iff] at this
    rcases this with h' | h'
    · exact (mul_eq_zero.1 h').resolve_left hD
    · exact absurd ((pow_eq_zero_iff (by norm_num)).1 h') (hden τ hτ)
  have e0 := zero_at _ m0
  have e1 := zero_at _ m1
  have : S * (ε / 3) = 0 := by linear_combination e1 - e0
  rcases mul_eq_zero.1 this with h' | h'
  · exact hS h'
  · linarith

theorem multiplicative_condition {p q r s P Q R S ξc τc ε : ℝ} (hε : 0 < ε)
    (hD : det p q r s ≠ 0) (hS : S ≠ 0) {α β : ℝ → ℝ}
    (hden : ∀ ξ ∈ Metric.ball ξc ε, ∀ τ ∈ Metric.ball τc ε, r * bilin P Q R S ξ τ + s ≠ 0)
    (hsep : ∀ ξ ∈ Metric.ball ξc ε, ∀ τ ∈ Metric.ball τc ε,
      (p * bilin P Q R S ξ τ + q) / (r * bilin P Q R S ξ τ + s) = α ξ * β τ)
    {ξ₀ τ₀ : ℝ} (hξ₀ : ξ₀ ∈ Metric.ball ξc ε) (hτ₀ : τ₀ ∈ Metric.ball τc ε) :
    condMul p q r s P Q R S ξ₀ τ₀ = 0 := by
  set E : ℝ → ℝ := fun τ => det p q r s * (Q + S * τ) / (r * bilin P Q R S ξ₀ τ + s) ^ 2
    with hE
  have hG : ∀ τ ∈ Metric.ball τc ε, HasDerivAt
      (fun ξ => (p * bilin P Q R S ξ τ + q) / (r * bilin P Q R S ξ τ + s)) (E τ) ξ₀ :=
    fun τ hτ => hasDerivAt_xi p q r s P Q R S ξ₀ τ (hden ξ₀ hξ₀ τ hτ)
  have hden₀ : ∀ τ ∈ Metric.ball τc ε, r * bilin P Q R S ξ₀ τ + s ≠ 0 :=
    fun τ hτ => hden ξ₀ hξ₀ τ hτ
  -- Some `β τ₁` is nonzero, because otherwise the weight `E` would vanish.
  obtain ⟨τ₁, hτ₁, hβ₁⟩ : ∃ τ₁ ∈ Metric.ball τc ε, β τ₁ ≠ 0 := by
    by_contra hall
    simp only [not_exists, not_and, not_not] at hall
    apply weight_not_zero hε hD hS _ hden₀
    intro τ hτ
    apply HasDerivAt.unique (hG τ hτ)
    apply HasDerivAt.congr_of_eventuallyEq (hasDerivAt_const ξ₀ (0 : ℝ))
    filter_upwards [Metric.isOpen_ball.mem_nhds hξ₀] with ξ hξ
    rw [hsep ξ hξ τ hτ, hall τ hτ, mul_zero]
  have hα : HasDerivAt α (E τ₁ / β τ₁) ξ₀ := by
    apply HasDerivAt.congr_of_eventuallyEq (HasDerivAt.div_const (hG τ₁ hτ₁) (β τ₁))
    filter_upwards [Metric.isOpen_ball.mem_nhds hξ₀] with ξ hξ
    rw [hsep ξ hξ τ₁ hτ₁, mul_div_cancel_right₀ _ hβ₁]
  set α' := E τ₁ / β τ₁ with hα'
  have hEβ : ∀ τ ∈ Metric.ball τc ε, E τ = α' * β τ := by
    intro τ hτ
    apply HasDerivAt.unique (hG τ hτ)
    apply HasDerivAt.congr_of_eventuallyEq (HasDerivAt.mul_const hα (β τ))
    filter_upwards [Metric.isOpen_ball.mem_nhds hξ₀] with ξ hξ
    rw [hsep ξ hξ τ hτ]
  have hα'ne : α' ≠ 0 := by
    intro h0
    apply weight_not_zero hε hD hS _ hden₀
    intro τ hτ
    have := hEβ τ hτ
    rw [h0, zero_mul] at this
    exact this
  set κ := α ξ₀ / α' with hκ
  have hGκ : ∀ τ ∈ Metric.ball τc ε,
      (p * bilin P Q R S ξ₀ τ + q) / (r * bilin P Q R S ξ₀ τ + s) = κ * E τ := by
    intro τ hτ
    rw [hsep ξ₀ hξ₀ τ hτ, hEβ τ hτ, hκ]
    field_simp
  have hτd := hasDerivAt_tau p q r s P Q R S ξ₀ τ₀ (hden₀ τ₀ hτ₀)
  have hκd := HasDerivAt.const_mul κ
    (hasDerivAt_weight_tau p q r s P Q R S ξ₀ τ₀ (hden₀ τ₀ hτ₀))
  have hderiv := HasDerivAt.unique hτd (HasDerivAt.congr_of_eventuallyEq hκd (by
    filter_upwards [Metric.isOpen_ball.mem_nhds hτ₀] with τ hτ
    exact hGκ τ hτ))
  have hval := hGκ τ₀ hτ₀
  simp only [hE] at hval
  have hd := hden₀ τ₀ hτ₀
  have zero :
      (p * bilin P Q R S ξ₀ τ₀ + q) / (r * bilin P Q R S ξ₀ τ₀ + s) *
          (det p q r s * (S * (r * bilin P Q R S ξ₀ τ₀ + s) -
            2 * r * (R + S * ξ₀) * (Q + S * τ₀)) / (r * bilin P Q R S ξ₀ τ₀ + s) ^ 3) -
        det p q r s * (R + S * ξ₀) / (r * bilin P Q R S ξ₀ τ₀ + s) ^ 2 *
          (det p q r s * (Q + S * τ₀) / (r * bilin P Q R S ξ₀ τ₀ + s) ^ 2) = 0 := by
    rw [hval, hderiv]
    ring
  have ident :
      (p * bilin P Q R S ξ₀ τ₀ + q) / (r * bilin P Q R S ξ₀ τ₀ + s) *
          (det p q r s * (S * (r * bilin P Q R S ξ₀ τ₀ + s) -
            2 * r * (R + S * ξ₀) * (Q + S * τ₀)) / (r * bilin P Q R S ξ₀ τ₀ + s) ^ 3) -
        det p q r s * (R + S * ξ₀) / (r * bilin P Q R S ξ₀ τ₀ + s) ^ 2 *
          (det p q r s * (Q + S * τ₀) / (r * bilin P Q R S ξ₀ τ₀ + s) ^ 2) =
      det p q r s * condMul p q r s P Q R S ξ₀ τ₀ / (r * bilin P Q R S ξ₀ τ₀ + s) ^ 4 := by
    unfold condMul condAdd
    field_simp
  rw [ident, div_eq_zero_iff] at zero
  rcases zero with h | h
  · exact (mul_eq_zero.1 h).resolve_left hD
  · exact absurd ((pow_eq_zero_iff (by norm_num)).1 h) hd

/-! ## Lemma 9: the equations force a zero determinant -/

/-- Linear interpolation with `ξ = a`, `ζ = b`, and `τ = t`. -/
theorem lerp_slice_a (ξ ζ τ : ℝ) : lerp ![ξ, ζ, τ] = bilin 0 1 ζ (-1) ξ τ := by
  simp only [lerp, bilin, Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.cons_val_two,
    Matrix.head_cons, Matrix.tail_cons]
  ring

/-- Linear interpolation with `ξ = b`, `ζ = a`, and `τ = t`. -/
theorem lerp_slice_b (ξ ζ τ : ℝ) : lerp ![ζ, ξ, τ] = bilin ζ 0 (-ζ) 1 ξ τ := by
  simp only [lerp, bilin, Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.cons_val_two,
    Matrix.head_cons, Matrix.tail_cons]
  ring

/-- The nine-point second difference in `ξ` and `τ` of a function on a grid with
spacing `h`. -/
def grid9 (g : ℝ → ℝ → ℝ) (ξ τ h : ℝ) : ℝ :=
  g ξ τ - 2 * g ξ (τ + h) + g ξ (τ + 2 * h) -
    2 * (g (ξ + h) τ - 2 * g (ξ + h) (τ + h) + g (ξ + h) (τ + 2 * h)) +
    (g (ξ + 2 * h) τ - 2 * g (ξ + 2 * h) (τ + h) + g (ξ + 2 * h) (τ + 2 * h))

theorem det_zero_of_add {p q r s ξc τc ζc ε : ℝ} (hε : 0 < ε) (P Q R S : ℝ → ℝ)
    (hcross : ∀ ζ ξ τ h, condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) (ξ + h) (τ + h) -
      condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) (ξ + h) τ -
      condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ (τ + h) +
      condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ = -(r * h ^ 2))
    (hzero : ∀ ζ ξ τ, r = 0 → condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ = S ζ * s)
    (hS : ∀ ζ, S ζ ≠ 0)
    (H : ∀ ξ ∈ Metric.ball ξc ε, ∀ τ ∈ Metric.ball τc ε, ∀ ζ ∈ Metric.ball ζc ε,
      condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ = 0) :
    det p q r s = 0 := by
  have a0 := near ξc ε hε 0 le_rfl (by norm_num)
  have a1 := near ξc ε hε 1 (by norm_num) (by norm_num)
  have t0 := near τc ε hε 0 le_rfl (by norm_num)
  have t1 := near τc ε hε 1 (by norm_num) (by norm_num)
  have z0 := near ζc ε hε 0 le_rfl (by norm_num)
  simp only [zero_mul, add_zero, one_mul] at a0 a1 t0 t1 z0
  have hcr := hcross ζc ξc τc (ε / 3)
  rw [H _ a1 _ t1 _ z0, H _ a1 _ t0 _ z0, H _ a0 _ t1 _ z0, H _ a0 _ t0 _ z0] at hcr
  have hh : ε / 3 ≠ 0 := by positivity
  have hr : r = 0 := by
    have : r * (ε / 3) ^ 2 = 0 := by linarith
    exact (mul_eq_zero.1 this).resolve_right (pow_ne_zero 2 hh)
  have e := H _ a0 _ t0 _ z0
  rw [hzero _ _ _ hr] at e
  have hs : s = 0 := (mul_eq_zero.1 e).resolve_left (hS ζc)
  unfold det
  rw [hr, hs]
  ring

theorem det_zero_of_mul {p q r s ξc τc ζc ε : ℝ} (hε : 0 < ε) (P Q R S : ℝ → ℝ)
    (σ₁ σ₂ : ℝ) (hσ₁ : σ₁ ≠ 0) (hσ₂ : σ₂ ≠ 0)
    (hgrid : ∀ ζ ξ τ h,
      grid9 (fun ξ τ => condMul p q r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ) ξ τ h =
        σ₁ * 4 * h ^ 4 * (p * r))
    (hreduced : ∀ ζ ξ τ, p * r = 0 →
      condMul p q r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ = σ₂ * ((p * s + q * r) * ζ + q * s))
    (H : ∀ ξ ∈ Metric.ball ξc ε, ∀ τ ∈ Metric.ball τc ε, ∀ ζ ∈ Metric.ball ζc ε,
      condMul p q r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ = 0) :
    det p q r s = 0 := by
  have a0 := near ξc ε hε 0 le_rfl (by norm_num)
  have a1 := near ξc ε hε 1 (by norm_num) (by norm_num)
  have a2 := near ξc ε hε 2 (by norm_num) (by norm_num)
  have t0 := near τc ε hε 0 le_rfl (by norm_num)
  have t1 := near τc ε hε 1 (by norm_num) (by norm_num)
  have t2 := near τc ε hε 2 (by norm_num) (by norm_num)
  have z0 := near ζc ε hε 0 le_rfl (by norm_num)
  have z1 := near ζc ε hε 1 (by norm_num) (by norm_num)
  simp only [zero_mul, add_zero, one_mul] at a0 a1 t0 t1 z0 z1
  have hh : ε / 3 ≠ 0 := by positivity
  have hg := hgrid ζc ξc τc (ε / 3)
  unfold grid9 at hg
  beta_reduce at hg
  rw [H _ a0 _ t0 _ z0, H _ a0 _ t1 _ z0, H _ a0 _ t2 _ z0, H _ a1 _ t0 _ z0,
    H _ a1 _ t1 _ z0, H _ a1 _ t2 _ z0, H _ a2 _ t0 _ z0, H _ a2 _ t1 _ z0,
    H _ a2 _ t2 _ z0] at hg
  have hpr : p * r = 0 := by
    have h4 : σ₁ * 4 * (ε / 3) ^ 4 ≠ 0 :=
      mul_ne_zero (mul_ne_zero hσ₁ four_ne_zero) (pow_ne_zero 4 hh)
    have : σ₁ * 4 * (ε / 3) ^ 4 * (p * r) = 0 := by linarith
    exact (mul_eq_zero.1 this).resolve_left h4
  have e0 := H _ a0 _ t0 _ z0
  have e1 := H _ a0 _ t0 _ z1
  rw [hreduced _ _ _ hpr] at e0 e1
  have e0' := (mul_eq_zero.1 e0).resolve_left hσ₂
  have e1' := (mul_eq_zero.1 e1).resolve_left hσ₂
  have hsum : p * s + q * r = 0 := by
    have : (p * s + q * r) * (ε / 3) = 0 := by linear_combination e1' - e0'
    exact (mul_eq_zero.1 this).resolve_right hh
  have hqs : q * s = 0 := by linear_combination e0' - ζc * hsum
  have hsq : det p q r s ^ 2 = 0 := by
    unfold det
    linear_combination (p * s + q * r) * hsum - 4 * (q * s) * hpr
  exact pow_eq_zero_iff (by norm_num) |>.1 hsq

/-! ## Lemmas 7 through 10 for one split -/

theorem slice_contra {p q r s : ℝ} (hD : det p q r s ≠ 0) {ξc τc ζc ε : ℝ} (hε : 0 < ε)
    (P Q R S : ℝ → ℝ) (hS : ∀ ζ, S ζ ≠ 0)
    (hcross : ∀ ζ ξ τ h, condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) (ξ + h) (τ + h) -
      condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) (ξ + h) τ -
      condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ (τ + h) +
      condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ = -(r * h ^ 2))
    (hzero : ∀ ζ ξ τ, r = 0 → condAdd r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ = S ζ * s)
    (σ₁ σ₂ : ℝ) (hσ₁ : σ₁ ≠ 0) (hσ₂ : σ₂ ≠ 0)
    (hgrid : ∀ ζ ξ τ h,
      grid9 (fun ξ τ => condMul p q r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ) ξ τ h =
        σ₁ * 4 * h ^ 4 * (p * r))
    (hreduced : ∀ ζ ξ τ, p * r = 0 →
      condMul p q r s (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ = σ₂ * ((p * s + q * r) * ζ + q * s))
    (α β : ℝ → ℝ → ℝ)
    (hden : ∀ ξ ∈ Metric.ball ξc ε, ∀ τ ∈ Metric.ball τc ε, ∀ ζ ∈ Metric.ball ζc ε,
      r * bilin (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ + s ≠ 0)
    (hsep : (∀ ξ ∈ Metric.ball ξc ε, ∀ τ ∈ Metric.ball τc ε, ∀ ζ ∈ Metric.ball ζc ε,
        (p * bilin (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ + q) / (r * bilin (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ + s) =
          α ζ ξ + β ζ τ) ∨
      (∀ ξ ∈ Metric.ball ξc ε, ∀ τ ∈ Metric.ball τc ε, ∀ ζ ∈ Metric.ball ζc ε,
        (p * bilin (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ + q) / (r * bilin (P ζ) (Q ζ) (R ζ) (S ζ) ξ τ + s) =
          α ζ ξ * β ζ τ)) : False := by
  rcases hsep with hsep | hsep
  · apply hD
    apply det_zero_of_add hε P Q R S hcross hzero hS
    intro ξ hξ τ hτ ζ hζ
    exact additive_condition hD (fun ξ hξ τ hτ => hden ξ hξ τ hτ ζ hζ)
      (fun ξ hξ τ hτ => hsep ξ hξ τ hτ ζ hζ) hξ hτ
  · apply hD
    apply det_zero_of_mul hε P Q R S σ₁ σ₂ hσ₁ hσ₂ hgrid hreduced
    intro ξ hξ τ hτ ζ hζ
    exact multiplicative_condition hε hD (hS ζ) (fun ξ hξ τ hτ => hden ξ hξ τ hτ ζ hζ)
      (fun ξ hξ τ hτ => hsep ξ hξ τ hτ ζ hζ) hξ hτ

theorem pr_cases {p r : ℝ} {goal : Prop} (hpr : p * r = 0) (h₁ : p = 0 → goal)
    (h₂ : r = 0 → goal) : goal :=
  (mul_eq_zero.1 hpr).elim h₁ h₂

/-- The proof of the theorem once Lemma 5 has produced a node that combines a
part without `t` and a part without input `j`, where `j` is `a` or `b`. -/
theorem separable_contra {p q r s : ℝ} (hD : det p q r s ≠ 0) {c : Point} {ε : ℝ}
    (hε : 0 < ε) {W A B : Point → ℝ} (j : Fin 3) (hj : j = 0 ∨ j = 1)
    (hA : Ignores A 2) (hB : Ignores B j)
    (hW : (∀ x, W x = A x + B x) ∨ (∀ x, W x = A x * B x))
    (hN : ∀ x ∈ Metric.ball c ε,
      r * lerp x + s ≠ 0 ∧ W x = (p * lerp x + q) / (r * lerp x + s)) : False := by
  rcases hj with rfl | rfl
  · have hmem : ∀ ξ ∈ Metric.ball (c 0) ε, ∀ τ ∈ Metric.ball (c 2) ε,
        ∀ ζ ∈ Metric.ball (c 1) ε, ![ξ, ζ, τ] ∈ Metric.ball c ε :=
      fun ξ hξ τ hτ ζ hζ => vec_mem_ball hε hξ hζ hτ
    have hAeq : ∀ ξ ζ τ, A ![ξ, ζ, τ] = A ![ξ, ζ, c 2] := fun ξ ζ τ =>
      hA _ _ (by intro i hi; fin_cases i <;> simp_all)
    have hBeq : ∀ ξ ζ τ, B ![ξ, ζ, τ] = B ![c 0, ζ, τ] := fun ξ ζ τ =>
      hB _ _ (by intro i hi; fin_cases i <;> simp_all)
    apply slice_contra hD hε (fun _ => 0) (fun _ => 1) (fun ζ => ζ) (fun _ => -1)
      (fun _ => by norm_num)
      (by intro ζ ξ τ h; unfold condAdd bilin; ring)
      (by intro ζ ξ τ hr; subst hr; unfold condAdd bilin; ring)
      1 (-1) one_ne_zero (by norm_num)
      (by intro ζ ξ τ h; unfold grid9 condMul condAdd bilin det; ring)
      (by
        intro ζ ξ τ hpr
        apply pr_cases hpr <;> intro h0 <;> subst h0 <;> unfold condMul condAdd bilin det <;> ring)
      (fun ζ ξ => A ![ξ, ζ, c 2]) (fun ζ τ => B ![c 0, ζ, τ])
    · intro ξ hξ τ hτ ζ hζ
      rw [← lerp_slice_a]
      exact (hN _ (hmem ξ hξ τ hτ ζ hζ)).1
    · rcases hW with hW | hW
      · left
        intro ξ hξ τ hτ ζ hζ
        rw [← lerp_slice_a, ← (hN _ (hmem ξ hξ τ hτ ζ hζ)).2, hW, hAeq, hBeq]
      · right
        intro ξ hξ τ hτ ζ hζ
        rw [← lerp_slice_a, ← (hN _ (hmem ξ hξ τ hτ ζ hζ)).2, hW, hAeq, hBeq]
  · have hmem : ∀ ξ ∈ Metric.ball (c 1) ε, ∀ τ ∈ Metric.ball (c 2) ε,
        ∀ ζ ∈ Metric.ball (c 0) ε, ![ζ, ξ, τ] ∈ Metric.ball c ε :=
      fun ξ hξ τ hτ ζ hζ => vec_mem_ball hε hζ hξ hτ
    have hAeq : ∀ ξ ζ τ, A ![ζ, ξ, τ] = A ![ζ, ξ, c 2] := fun ξ ζ τ =>
      hA _ _ (by intro i hi; fin_cases i <;> simp_all)
    have hBeq : ∀ ξ ζ τ, B ![ζ, ξ, τ] = B ![ζ, c 1, τ] := fun ξ ζ τ =>
      hB _ _ (by intro i hi; fin_cases i <;> simp_all)
    apply slice_contra hD hε (fun ζ => ζ) (fun _ => 0) (fun ζ => -ζ) (fun _ => 1)
      (fun _ => by norm_num)
      (by intro ζ ξ τ h; unfold condAdd bilin; ring)
      (by intro ζ ξ τ hr; subst hr; unfold condAdd bilin; ring)
      (-1) 1 (by norm_num) one_ne_zero
      (by intro ζ ξ τ h; unfold grid9 condMul condAdd bilin det; ring)
      (by
        intro ζ ξ τ hpr
        apply pr_cases hpr <;> intro h0 <;> subst h0 <;> unfold condMul condAdd bilin det <;> ring)
      (fun ζ ξ => A ![ζ, ξ, c 2]) (fun ζ τ => B ![ζ, c 1, τ])
    · intro ξ hξ τ hτ ζ hζ
      rw [← lerp_slice_b]
      exact (hN _ (hmem ξ hξ τ hτ ζ hζ)).1
    · rcases hW with hW | hW
      · left
        intro ξ hξ τ hτ ζ hζ
        rw [← lerp_slice_b, ← (hN _ (hmem ξ hξ τ hτ ζ hζ)).2, hW, hAeq, hBeq]
      · right
        intro ξ hξ τ hτ ζ hζ
        rw [← lerp_slice_b, ← (hN _ (hmem ξ hξ τ hτ ζ hζ)).2, hW, hAeq, hBeq]

/-! ## Lemma 5 and the proof of the theorem -/

theorem Ignores.comp {F : Point → ℝ} {m : Fin 3} (hF : Ignores F m) (g : ℝ → ℝ) :
    Ignores (fun x => g (F x)) m := by
  intro x y hxy
  simp only [hF x y hxy]

/-- The value of a node whose operands use disjoint inputs: `F` does not use
`t`, and `G` does not use input `j`. -/
theorem split_forms (op : Op) {F G : Point → ℝ} {j : Fin 3} (hF : Ignores F 2)
    (hG : Ignores G j) :
    (∃ A B : Point → ℝ, Ignores A 2 ∧ Ignores B j ∧
      ((∀ x, op.apply (F x) (G x) = A x + B x) ∨ (∀ x, op.apply (F x) (G x) = A x * B x))) ∧
    (∃ A B : Point → ℝ, Ignores A 2 ∧ Ignores B j ∧
      ((∀ x, op.apply (G x) (F x) = A x + B x) ∨ (∀ x, op.apply (G x) (F x) = A x * B x))) := by
  cases op with
  | add =>
    exact ⟨⟨F, G, hF, hG, Or.inl fun x => rfl⟩,
      ⟨F, G, hF, hG, Or.inl fun x => add_comm _ _⟩⟩
  | sub =>
    refine ⟨⟨F, fun x => -G x, hF, hG.comp _, Or.inl fun x => sub_eq_add_neg _ _⟩,
      ⟨fun x => -F x, G, hF.comp _, hG, Or.inl fun x => ?_⟩⟩
    simp only [Op.apply]
    ring
  | mul =>
    exact ⟨⟨F, G, hF, hG, Or.inr fun x => rfl⟩,
      ⟨F, G, hF, hG, Or.inr fun x => mul_comm _ _⟩⟩
  | div =>
    refine ⟨⟨F, fun x => (G x)⁻¹, hF, hG.comp _, Or.inr fun x => div_eq_mul_inv _ _⟩,
      ⟨fun x => (F x)⁻¹, G, hF.comp _, hG, Or.inr fun x => ?_⟩⟩
    simp only [Op.apply]
    rw [div_eq_mul_inv, mul_comm]

/-- Lemma 5, as an induction on the rules: no Möbius map of any result equals
linear interpolation on the ball. -/
theorem no_mobius_match {e : Expression} (hwf : e.WellFormed) (hsu : e.SingleUse) {c : Point}
    {ε : ℝ} (hε : 0 < ε) (hdef : ∀ x ∈ Metric.ball c ε, e.DefinedAt x) :
    ∀ i < e.length, ∀ α β γ δ : ℝ, α * δ - β * γ ≠ 0 →
      ¬ MobiusMatches (fun x => value e x i) α β γ δ (Metric.ball c ε) := by
  intro i
  induction i using Nat.strong_induction_on with
  | _ i ih =>
  intro hi α β γ δ hdet hM
  have hc : c ∈ Metric.ball c ε := Metric.mem_ball_self hε
  have operand_claim : ∀ side : Bool, ∀ α β γ δ : ℝ, α * δ - β * γ ≠ 0 →
      ¬ MobiusMatches (fun x => operandValue e x i ((e.rule i).operand side)) α β γ δ
        (Metric.ball c ε) := by
    intro side α β γ δ hdet hM
    cases ho : (e.rule i).operand side with
    | const κ =>
      rw [ho] at hM
      exact hM.not_const hε κ (fun x _ => rfl)
    | input j =>
      rw [ho] at hM
      by_cases hj : j = 2
      · subst hj
        exact hM.not_ignores hε 0 (Or.inl rfl) (fun x y hxy => hxy 2 (by decide))
      · exact hM.not_ignores hε 2 (Or.inr rfl) (fun x y hxy => hxy j hj)
    | result k =>
      have hk := hwf.2 i hi side k ho
      rw [ho] at hM
      have hfun : (fun x => operandValue e x i (.result k)) = fun x => value e x k := by
        funext x
        simp [operandValue, evalOperand, hk]
      rw [hfun] at hM
      exact ih k hk (lt_trans hk hi) α β γ δ hdet hM
  set oL : Point → ℝ := fun x => operandValue e x i (e.rule i).left with hoL
  set oR : Point → ℝ := fun x => operandValue e x i (e.rule i).right with hoR
  have claimL : ∀ α β γ δ : ℝ, α * δ - β * γ ≠ 0 →
      ¬ MobiusMatches oL α β γ δ (Metric.ball c ε) := operand_claim true
  have claimR : ∀ α β γ δ : ℝ, α * δ - β * γ ≠ 0 →
      ¬ MobiusMatches oR α β γ δ (Metric.ball c ε) := operand_claim false
  have hW : (fun x => value e x i) = fun x => (e.rule i).op.apply (oL x) (oR x) := by
    funext x
    exact value_eq e x i
  rw [hW] at hM
  have hdiv : (e.rule i).op = .div → ∀ x ∈ Metric.ball c ε, oR x ≠ 0 :=
    fun hop x hx => hdef x hx i hi hop
  by_cases hLe : operandInputs e i (e.rule i).left = ∅
  · -- The left operand is constant, so `value = σ(oR)` for a Möbius step `σ`.
    set κ := oL c with hκdef
    have hκ : ∀ x, oL x = κ := fun x =>
      operandValue_congr e x c i _ (by rw [hLe]; simp)
    cases hop : (e.rule i).op with
    | add =>
      simp only [hop, Op.apply, hκ] at hM
      exact claimR α (α * κ + β) γ (γ * κ + δ) (by intro h; apply hdet; linear_combination h)
        (hM.transform (k := fun _ => 1) (fun _ _ => one_ne_zero)
          (fun x _ => by ring) (fun x _ => by ring))
    | sub =>
      simp only [hop, Op.apply, hκ] at hM
      exact claimR (-α) (α * κ + β) (-γ) (γ * κ + δ)
        (by intro h; apply hdet; linear_combination -h)
        (hM.transform (k := fun _ => 1) (fun _ _ => one_ne_zero)
          (fun x _ => by ring) (fun x _ => by ring))
    | mul =>
      simp only [hop, Op.apply, hκ] at hM
      by_cases hκ0 : κ = 0
      · exact hM.not_const hε 0 (fun x _ => by rw [hκ0, zero_mul])
      exact claimR (α * κ) β (γ * κ) δ
        (by
          intro h; apply hdet
          have : κ * (α * δ - β * γ) = 0 := by linear_combination h
          exact (mul_eq_zero.1 this).resolve_left hκ0)
        (hM.transform (k := fun _ => 1) (fun _ _ => one_ne_zero)
          (fun x _ => by ring) (fun x _ => by ring))
    | div =>
      have hR0 := hdiv hop
      simp only [hop, Op.apply, hκ] at hM
      by_cases hκ0 : κ = 0
      · exact hM.not_const hε 0 (fun x _ => by rw [hκ0, zero_div])
      exact claimR β (α * κ) δ (γ * κ)
        (by
          intro h; apply hdet
          have : κ * (α * δ - β * γ) = 0 := by linear_combination -h
          exact (mul_eq_zero.1 this).resolve_left hκ0)
        (hM.transform (k := oR) hR0
          (fun x hx => by field_simp [hR0 x hx]; ring)
          (fun x hx => by field_simp [hR0 x hx]; ring))
  by_cases hRe : operandInputs e i (e.rule i).right = ∅
  · -- The right operand is constant, so `value = σ(oL)` for a Möbius step `σ`.
    set κ := oR c with hκdef
    have hκ : ∀ x, oR x = κ := fun x =>
      operandValue_congr e x c i _ (by rw [hRe]; simp)
    cases hop : (e.rule i).op with
    | add =>
      simp only [hop, Op.apply, hκ] at hM
      exact claimL α (α * κ + β) γ (γ * κ + δ) (by intro h; apply hdet; linear_combination h)
        (hM.transform (k := fun _ => 1) (fun _ _ => one_ne_zero)
          (fun x _ => by ring) (fun x _ => by ring))
    | sub =>
      simp only [hop, Op.apply, hκ] at hM
      exact claimL α (β - α * κ) γ (δ - γ * κ) (by intro h; apply hdet; linear_combination h)
        (hM.transform (k := fun _ => 1) (fun _ _ => one_ne_zero)
          (fun x _ => by ring) (fun x _ => by ring))
    | mul =>
      simp only [hop, Op.apply, hκ] at hM
      by_cases hκ0 : κ = 0
      · exact hM.not_const hε 0 (fun x _ => by rw [hκ0, mul_zero])
      exact claimL (α * κ) β (γ * κ) δ
        (by
          intro h; apply hdet
          have : κ * (α * δ - β * γ) = 0 := by linear_combination h
          exact (mul_eq_zero.1 this).resolve_left hκ0)
        (hM.transform (k := fun _ => 1) (fun _ _ => one_ne_zero)
          (fun x _ => by ring) (fun x _ => by ring))
    | div =>
      have hκ0 : κ ≠ 0 := by rw [hκdef]; exact hdiv hop c hc
      simp only [hop, Op.apply, hκ] at hM
      exact claimL α (β * κ) γ (δ * κ)
        (by
          intro h; apply hdet
          have : κ * (α * δ - β * γ) = 0 := by linear_combination h
          exact (mul_eq_zero.1 this).resolve_left hκ0)
        (hM.transform (k := fun _ => κ) (fun _ _ => hκ0)
          (fun x _ => by field_simp) (fun x _ => by field_simp))
  -- Both operands have inputs, and by single use they have different inputs.
  have hdisj := operandInputs_disjoint hwf hsu hi
  have hN : ∀ x ∈ Metric.ball c ε, -γ * lerp x + α ≠ 0 ∧
      (e.rule i).op.apply (oL x) (oR x) = (δ * lerp x + -β) / (-γ * lerp x + α) :=
    fun x hx => invert_mobius hdet (hM x hx).1 (hM x hx).2
  have hD : det δ (-β) (-γ) α ≠ 0 := by
    unfold det
    intro h
    apply hdet
    linear_combination h
  by_cases h2L : (2 : Fin 3) ∈ operandInputs e i (e.rule i).left
  · obtain ⟨j, hj⟩ := Finset.nonempty_iff_ne_empty.2 hRe
    have hj2 : j ≠ 2 := by
      rintro rfl
      exact Finset.disjoint_left.1 hdisj h2L hj
    have hjL : j ∉ operandInputs e i (e.rule i).left :=
      fun h => Finset.disjoint_left.1 hdisj h hj
    have h2R : (2 : Fin 3) ∉ operandInputs e i (e.rule i).right :=
      fun h => Finset.disjoint_left.1 hdisj h2L h
    obtain ⟨A, B, hA, hB, hform⟩ :=
      (split_forms (e.rule i).op (operandValue_ignores e i _ 2 h2R)
        (operandValue_ignores e i _ j hjL)).2
    exact separable_contra hD hε j (by fin_cases j <;> simp_all) hA hB
      (hform.imp (fun h x => h x) (fun h x => h x)) hN
  by_cases h2R : (2 : Fin 3) ∈ operandInputs e i (e.rule i).right
  · obtain ⟨j, hj⟩ := Finset.nonempty_iff_ne_empty.2 hLe
    have hj2 : j ≠ 2 := by
      rintro rfl
      exact Finset.disjoint_left.1 hdisj hj h2R
    have hjR : j ∉ operandInputs e i (e.rule i).right :=
      fun h => Finset.disjoint_left.1 hdisj hj h
    obtain ⟨A, B, hA, hB, hform⟩ :=
      (split_forms (e.rule i).op (operandValue_ignores e i _ 2 h2L)
        (operandValue_ignores e i _ j hjR)).1
    exact separable_contra hD hε j (by fin_cases j <;> simp_all) hA hB
      (hform.imp (fun h x => h x) (fun h x => h x)) hN
  -- Neither operand uses `t`, so the value does not depend on `t`.
  have hign : Ignores (fun x => (e.rule i).op.apply (oL x) (oR x)) 2 := by
    intro x y hxy
    have h1 := operandValue_ignores e i _ 2 h2L x y hxy
    have h2 := operandValue_ignores e i _ 2 h2R x y hxy
    simp only at h1 h2
    simp only [hoL, hoR, h1, h2]
  exact hM.not_ignores hε 2 (Or.inr rfl) hign

/-- No arithmetic single-use expression computes linear interpolation
`a + t · (b - a)` on any nonempty open subset of `ℝ³`. -/
theorem linear_interpolation_has_no_single_use_form (e : Expression) (hwf : e.WellFormed)
    (hsu : e.SingleUse) (U : Set Point) (hU : IsOpen U) (hne : U.Nonempty) :
    ¬ e.ComputesOn lerp U := by
  intro hcomp
  obtain ⟨c, hc⟩ := hne
  obtain ⟨ε, hε, hball⟩ := Metric.isOpen_iff.1 hU c hc
  apply no_mobius_match hwf hsu hε (fun x hx => (hcomp x (hball hx)).1) (e.length - 1)
    (by have := hwf.1; omega) 1 0 0 1 (by norm_num)
  intro x hx
  refine ⟨by norm_num, ?_⟩
  simp only [one_mul, add_zero, zero_mul, zero_add, div_one]
  exact (hcomp x (hball hx)).2

/-! ## The definitions are not vacuous -/

/-- `s₀ := b - a`, `s₁ := t × s₀`, `s₂ := a + s₁`, which uses `a` twice. -/
def lerpExpression : Expression where
  length := 3
  rule
    | 0 => ⟨.sub, .input 1, .input 0⟩
    | 1 => ⟨.mul, .input 2, .result 0⟩
    | _ => ⟨.add, .input 0, .result 1⟩

/-- Linear interpolation does have an arithmetic expression that uses an input
twice, so the single-use hypothesis of the main theorem is what excludes it. -/
theorem lerpExpression_computes :
    lerpExpression.WellFormed ∧ ¬ lerpExpression.SingleUse ∧
      lerpExpression.ComputesOn lerp Set.univ := by
  refine ⟨⟨by decide, ?_⟩, ?_, ?_⟩
  · intro i hi side k hk
    change i < 3 at hi
    obtain _ | _ | _ | i := i <;> cases side <;>
      simp_all [lerpExpression, Rule.operand] <;> omega
  · intro hsu
    have := hsu.1 0 (by decide) 2 (by decide) false true 0 rfl rfl
    omega
  · intro x _
    refine ⟨?_, ?_⟩
    · intro i hi hop
      change i < 3 at hi
      obtain _ | _ | _ | i := i <;> simp [lerpExpression] at hop
    · have v0 : value lerpExpression x 0 = x 1 - x 0 := by
        rw [value_eq]
        rfl
      have v1 : value lerpExpression x 1 = x 2 * value lerpExpression x 0 := by
        rw [value_eq]
        simp [operandValue, evalOperand, lerpExpression, Op.apply]
      have v2 : value lerpExpression x 2 = x 0 + value lerpExpression x 1 := by
        rw [value_eq]
        simp [operandValue, evalOperand, lerpExpression, Op.apply]
      show value lerpExpression x 2 = lerp x
      rw [v2, v1, v0]
      unfold lerp
      ring

end

end Define.SingleUseExpression
