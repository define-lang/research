import Mathlib.Data.List.Sort
import Mathlib.Data.List.Lex
import Mathlib.Data.Multiset.AddSub
import Mathlib.Data.Multiset.Filter
import Mathlib.Data.Multiset.UnionInter
import Mathlib.Data.Finset.Max
import Mathlib.Data.Set.Finite.Basic
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.Order.BigOperators.Group.List

set_option warningAsError true
set_option autoImplicit false

/-!
# Fixing a program always terminates

This file formalizes `termination.md`: every fix that DLP 57 and DLP 59 allow
lowers a measure, so fixing never returns to a program it has left
(`prog_no_cycle`), and an infinite sequence of fixes would have to visit
infinitely many programs within fixed bounds on their sizes
(`prog_terminates`).

A value operation's boolean statements are given by their terms (`Term`)
and how many of their values are constant (`Stmt`). An input is a `leaf`,
and a statement is a `node` applying an operation to the terms of the values
it reads. A term's code (`ser`) writes it out in DLP 58's rank order: `[1, i]`
for leaf `i`, and for a statement `2`, then the codes of its values (sorted
when the operation's views are interchangeable), then `0` and the operation.
Comparing codes lexicographically is the rank order: values first, a
shorter list first, then the operation.

One value operation's measure (`OpLt`) is C, the number of constant values
(`constCount`), then the number of statements, then the multiset of the
executions' (negations, AIG nodes, declared order) (`triples`), then the
multiset of the statements' codes (`codes`), with multisets in the
Dershowitz–Manna order (`DMLt`). Its fixes (`OpFix`):

- `simplify`: a constant value v is simplified away. v's statement is gone,
  the statements it reached are replaced by new ones with no constant value,
  and every other statement keeps its functions.
- `redundant`: a redundant value v. Every statement of the result is one of
  the others, rewritten, with the same functions.
- `ordinary`: an ordinary match. The result is the statements that survive
  and the one or two added, which aren't constant, and more are removed than
  added.
- `spelling`: a single execution v respelled as the execution v', with
  higher precedence (`KeyLt`). Every other statement's term has v's term
  replaced by v''s (`subst`); some may become dead. No other statement has
  v's term, because redundant values are fixed first.

A program (`Program`) is a fixed number of value operations, each present or
removed, with its number of written views. It's ordered by Φ, the sum of C
and the written views (`phi`), and then pointwise (`ProgLt`). Its fixes
(`ProgStep`) are a fix inside one value operation, and removing a constant
written view, which also lowers C in every value operation that executes it.

The semantics (which fixes exist) never matter: the theorems hold for every
fix of these shapes.

`opFix_lt`, `progStep_lt`, `prog_no_cycle`, and `prog_terminates` state the
result.
-/

namespace Define.BooleanEqualityChecking.Termination

inductive Term where
  | leaf (i : ℕ)
  | node (op : ℕ) (args : List Term)

noncomputable instance : DecidableEq Term := Classical.decEq _

structure Signature where
  /-- All of an operation's views are interchangeable. -/
  symmetric : ℕ → Bool
  /-- The operation is `not`. -/
  isNot : ℕ → Bool
  /-- The operation is a registered boolean operation. -/
  registered : ℕ → Bool
  /-- AIG nodes of a registered operation's own logic. -/
  nodes : ℕ → ℕ
  /-- A registered operation's place in the declared order. -/
  position : ℕ → ℕ
  position_injective : ∀ o p, registered o = true → registered p = true →
    position o = position p → o = p

variable (sig : Signature)

def arrange (o : ℕ) (codes : List (List ℕ)) : List (List ℕ) :=
  if sig.symmetric o then codes.insertionSort (· ≤ ·) else codes

theorem arrange_perm (o : ℕ) (codes : List (List ℕ)) : List.Perm (arrange sig o codes) codes := by
  unfold arrange
  split
  · exact List.perm_insertionSort _ _
  · exact List.Perm.refl _

def ser : Term → List ℕ
  | .leaf i => [1, i]
  | .node o args => [2] ++ (arrange sig o (args.attach.map fun a => ser a.1)).flatten ++ [0, o]
termination_by t => sizeOf t
decreasing_by
  have := List.sizeOf_lt_of_mem a.2
  simp_wf
  omega

theorem ser_leaf (i : ℕ) : ser sig (.leaf i) = [1, i] := by
  rw [ser]

theorem ser_node (o : ℕ) (args : List Term) :
    ser sig (.node o args) = 2 :: ((arrange sig o (args.map (ser sig))).flatten ++ [0, o]) := by
  rw [ser, List.attach_map_val]
  rfl

theorem Term.induct {P : Term → Prop} (leaf : ∀ i, P (.leaf i))
    (node : ∀ o args, (∀ a ∈ args, P a) → P (.node o args)) : ∀ t, P t
  | .leaf i => leaf i
  | .node o args => node o args fun a _ => Term.induct leaf node a
termination_by t => sizeOf t
decreasing_by
  have := List.sizeOf_lt_of_mem ‹a ∈ args›
  simp_wf
  omega

/-- Every code starts with 1 or 2, never with the end marker 0. -/
theorem ser_head (t : Term) : ∃ c r, ser sig t = c :: r ∧ c ≠ 0 := by
  cases t with
  | leaf i => exact ⟨1, [i], ser_leaf sig i, by omega⟩
  | node o args => exact ⟨2, _, ser_node sig o args, by omega⟩

/-- Two lists that are each a prefix of something, one after the other. -/
def Comparable (a b : List ℕ) : Prop := a <+: b ∨ b <+: a

theorem comparable_of_append {a b s s' : List ℕ} (h : Comparable (a ++ s) (b ++ s')) :
    Comparable a b := by
  rcases h with h | h
  · exact List.prefix_or_prefix_of_prefix ((List.prefix_append a s).trans h)
      (List.prefix_append b s')
  · exact List.prefix_or_prefix_of_prefix (List.prefix_append a s)
      ((List.prefix_append b s').trans h)

theorem comparable_cons {c d : ℕ} {r s : List ℕ} (h : Comparable (c :: r) (d :: s)) :
    c = d ∧ Comparable r s := by
  rcases h with h | h
  · exact ⟨(List.cons_prefix_cons.1 h).1, .inl (List.cons_prefix_cons.1 h).2⟩
  · exact ⟨(List.cons_prefix_cons.1 h).1.symm, .inr (List.cons_prefix_cons.1 h).2⟩

/-- Codes that start with a nonzero symbol, followed by the end marker, parse
uniquely when each code of the first list is prefix-free against the second. -/
theorem parse {A B : List (List ℕ)} {x y : List ℕ}
    (hA : ∀ a ∈ A, ∀ b ∈ B, Comparable a b → a = b)
    (hA0 : ∀ a ∈ A, ∃ c r, a = c :: r ∧ c ≠ 0) (hB0 : ∀ b ∈ B, ∃ c r, b = c :: r ∧ c ≠ 0)
    (h : Comparable (A.flatten ++ 0 :: x) (B.flatten ++ 0 :: y)) :
    A = B ∧ Comparable x y := by
  induction A generalizing B with
  | nil =>
    cases B with
    | nil => exact ⟨rfl, (comparable_cons (by simpa using h)).2⟩
    | cons b B =>
      obtain ⟨c, r, rfl, hc⟩ := hB0 b (by simp)
      exact absurd (comparable_cons (by simpa using h)).1.symm hc
  | cons a A ih =>
    cases B with
    | nil =>
      obtain ⟨c, r, rfl, hc⟩ := hA0 a (by simp)
      exact absurd (comparable_cons (by simpa using h)).1 hc
    | cons b B =>
      have hab : a = b := by
        refine hA a (by simp) b (by simp) (comparable_of_append (s := A.flatten ++ 0 :: x)
          (s' := B.flatten ++ 0 :: y) ?_)
        simpa [List.append_assoc] using h
      subst hab
      have h' : Comparable (A.flatten ++ 0 :: x) (B.flatten ++ 0 :: y) := by
        rcases h with h | h
        · exact .inl (List.prefix_append_right_inj a |>.1 (by simpa [List.append_assoc] using h))
        · exact .inr (List.prefix_append_right_inj a |>.1 (by simpa [List.append_assoc] using h))
      obtain ⟨hAB, hxy⟩ := ih (fun a' ha' b' hb' => hA a' (by simp [ha']) b' (by simp [hb']))
        (fun a' ha' => hA0 a' (by simp [ha'])) (fun b' hb' => hB0 b' (by simp [hb'])) h'
      exact ⟨by rw [hAB], hxy⟩

/-- Codes are prefix-free: two comparable codes are equal. -/
theorem ser_prefix_free : ∀ t u, Comparable (ser sig t) (ser sig u) → ser sig t = ser sig u := by
  intro t
  induction t using Term.induct with
  | leaf i =>
    intro u h
    cases u with
    | leaf j =>
      rw [ser_leaf, ser_leaf] at h ⊢
      obtain ⟨-, h⟩ := comparable_cons h
      obtain ⟨hij, -⟩ := comparable_cons h
      rw [hij]
    | node o args =>
      rw [ser_leaf, ser_node] at h
      exact absurd (comparable_cons h).1 (by omega)
  | node o args ih =>
    intro u h
    cases u with
    | leaf j =>
      rw [ser_node, ser_leaf] at h
      exact absurd (comparable_cons h).1 (by omega)
    | node p brgs =>
      rw [ser_node, ser_node] at h ⊢
      obtain ⟨-, h⟩ := comparable_cons h
      have hA : ∀ a ∈ arrange sig o (args.map (ser sig)), ∀ b ∈ arrange sig p (brgs.map (ser sig)),
          Comparable a b → a = b := by
        intro a ha b hb hab
        obtain ⟨t, ht, rfl⟩ := List.mem_map.1 ((arrange_perm sig o _).mem_iff.1 ha)
        obtain ⟨u, -, rfl⟩ := List.mem_map.1 ((arrange_perm sig p _).mem_iff.1 hb)
        exact ih t ht u hab
      have h0 : ∀ (q : ℕ) (cs : List Term), ∀ a ∈ arrange sig q (cs.map (ser sig)),
          ∃ c r, a = c :: r ∧ c ≠ 0 := by
        intro q cs a ha
        obtain ⟨t, -, rfl⟩ := List.mem_map.1 ((arrange_perm sig q _).mem_iff.1 ha)
        exact ser_head sig t
      obtain ⟨hAB, hop⟩ := parse hA (h0 o args) (h0 p brgs) h
      obtain ⟨hop, -⟩ := comparable_cons hop
      rw [hAB, hop]

/-! ### The order on codes -/

theorem append_lt_append_left (a : List ℕ) {x y : List ℕ} (h : x < y) : a ++ x < a ++ y := by
  induction a with
  | nil => simpa using h
  | cons c a ih => exact List.Lex.cons ih

theorem append_le_append_left (a : List ℕ) {x y : List ℕ} (h : x ≤ y) : a ++ x ≤ a ++ y := by
  rcases lt_or_eq_of_le h with h | rfl
  · exact le_of_lt (append_lt_append_left a h)
  · exact le_refl _

/-- A code below another and not a prefix of it stays below, whatever follows. -/
theorem lt_append_of_lt {a' a : List ℕ} (h : a' < a) (hp : ¬ a' <+: a) (x y : List ℕ) :
    a' ++ x < a ++ y := by
  have h' : List.Lex (· < ·) a' a := h
  clear h
  induction h' with
  | nil => exact absurd (List.nil_prefix) hp
  | cons h ih =>
    exact List.Lex.cons (ih (fun hp' => hp (List.cons_prefix_cons.2 ⟨rfl, hp'⟩)))
  | rel h => exact List.Lex.rel h

theorem lt_append_of_lt_of_comparable_eq {a' a : List ℕ} (h : a' < a)
    (hpf : Comparable a' a → a' = a) (x y : List ℕ) : a' ++ x < a ++ y :=
  lt_append_of_lt h (fun hp => (ne_of_lt h) (hpf (.inl hp))) x y

/-- Lists of codes, each at most the one in the same place, concatenate to at
most. -/
theorem flatten_le {A' A : List (List ℕ)} (h : List.Forall₂ (· ≤ ·) A' A)
    (hpf : ∀ a' ∈ A', ∀ a ∈ A, Comparable a' a → a' = a) (z : List ℕ) :
    A'.flatten ++ z ≤ A.flatten ++ z := by
  induction h with
  | nil => exact le_refl _
  | @cons a' a A' A hle _ ih =>
    have ih' := ih (fun b' hb' b hb => hpf b' (by simp [hb']) b (by simp [hb]))
    simp only [List.flatten_cons, List.append_assoc]
    rcases lt_or_eq_of_le hle with hlt | rfl
    · exact le_of_lt (lt_append_of_lt_of_comparable_eq hlt
        (hpf a' (by simp) a (by simp)) _ _)
    · exact append_le_append_left a' ih'

/-- A list of codes below another, followed by the end marker, concatenates
to below. -/
theorem flatten_lt {A' A : List (List ℕ)} (h : A' < A)
    (hpf : ∀ a' ∈ A', ∀ a ∈ A, Comparable a' a → a' = a)
    (h0 : ∀ a ∈ A, ∃ c r, a = c :: r ∧ c ≠ 0) (z : List ℕ) :
    A'.flatten ++ 0 :: z < A.flatten ++ 0 :: z := by
  have h' : List.Lex (· < ·) A' A := h
  clear h
  induction h' with
  | @nil a A =>
    obtain ⟨c, r, rfl, hc⟩ := h0 a (by simp)
    exact List.Lex.rel (Nat.pos_of_ne_zero hc)
  | @cons a A' A _ ih =>
    simp only [List.flatten_cons, List.append_assoc]
    exact append_lt_append_left a (ih (fun b' hb' b hb => hpf b' (by simp [hb']) b (by simp [hb]))
      (fun b hb => h0 b (by simp [hb])))
  | @rel a' A' a A hlt =>
    simp only [List.flatten_cons, List.append_assoc]
    exact lt_append_of_lt_of_comparable_eq hlt (hpf a' (by simp) a (by simp)) _ _

/-! ### Sorting keeps pointwise order -/

theorem orderedInsert_of_forall_le {b : List ℕ} {t : List (List ℕ)} (h : ∀ x ∈ t, b ≤ x) :
    t.orderedInsert (· ≤ ·) b = b :: t := by
  cases t with
  | nil => rfl
  | cons c t => exact List.orderedInsert_cons_of_le _ _ (h c (by simp))

theorem orderedInsert_mono : ∀ {s' s : List (List ℕ)}, List.Pairwise (· ≤ ·) s' →
    List.Pairwise (· ≤ ·) s → List.Forall₂ (· ≤ ·) s' s → ∀ {a' a : List ℕ}, a' ≤ a →
    List.Forall₂ (· ≤ ·) (s'.orderedInsert (· ≤ ·) a') (s.orderedInsert (· ≤ ·) a)
  | [], [], _, _, _, a', a, h => by simpa using h
  | b' :: t', b :: t, hs', hs, .cons hb ht, a', a, h => by
    have hs't := List.pairwise_cons.1 hs'
    have hst := List.pairwise_cons.1 hs
    by_cases h1 : a' ≤ b' <;> by_cases h2 : a ≤ b
    · rw [List.orderedInsert_cons_of_le _ _ h1, List.orderedInsert_cons_of_le _ _ h2]
      exact .cons h (.cons hb ht)
    · rw [List.orderedInsert_cons_of_le _ _ h1, List.orderedInsert_of_not_le _ _ h2]
      have hba : b' ≤ a := le_trans hb (le_of_lt (lt_of_not_ge h2))
      refine .cons (le_trans h1 hb) ?_
      rw [← orderedInsert_of_forall_le hs't.1]
      exact orderedInsert_mono hs't.2 hst.2 ht hba
    · rw [List.orderedInsert_of_not_le _ _ h1, List.orderedInsert_cons_of_le _ _ h2]
      have hb'a : b' ≤ a := le_trans (le_of_lt (lt_of_not_ge h1)) h
      refine .cons hb'a ?_
      rw [← orderedInsert_of_forall_le hst.1]
      exact orderedInsert_mono hs't.2 hst.2 ht (le_trans h h2)
    · rw [List.orderedInsert_of_not_le _ _ h1, List.orderedInsert_of_not_le _ _ h2]
      exact .cons hb (orderedInsert_mono hs't.2 hst.2 ht h)

theorem insertionSort_mono {l' l : List (List ℕ)} (h : List.Forall₂ (· ≤ ·) l' l) :
    List.Forall₂ (· ≤ ·) (l'.insertionSort (· ≤ ·)) (l.insertionSort (· ≤ ·)) := by
  induction h with
  | nil => exact .nil
  | cons hab _ ih =>
    exact orderedInsert_mono (List.pairwise_insertionSort _ _) (List.pairwise_insertionSort _ _)
      ih hab

theorem arrange_mono (o : ℕ) {l' l : List (List ℕ)} (h : List.Forall₂ (· ≤ ·) l' l) :
    List.Forall₂ (· ≤ ·) (arrange sig o l') (arrange sig o l) := by
  unfold arrange
  split
  · exact insertionSort_mono h
  · exact h

/-! ### Replacing a value -/

/-- Every subterm with code `sv` becomes `v'`. -/
def subst (sv : List ℕ) (v' : Term) : Term → Term
  | .leaf i => if [1, i] = sv then v' else .leaf i
  | .node o args =>
      if ser sig (.node o args) = sv then v' else .node o (args.attach.map fun a => subst sv v' a.1)
termination_by t => sizeOf t
decreasing_by
  have := List.sizeOf_lt_of_mem a.2
  simp_wf
  omega

variable {sig}

theorem subst_of_ser {sv : List ℕ} {v' : Term} {t : Term} (h : ser sig t = sv) :
    subst sig sv v' t = v' := by
  cases t with
  | leaf i => rw [subst, if_pos (by rwa [ser_leaf] at h)]
  | node o args => rw [subst, if_pos h]

theorem subst_leaf_of_ne {sv : List ℕ} {v' : Term} {i : ℕ} (h : ser sig (.leaf i) ≠ sv) :
    subst sig sv v' (.leaf i) = .leaf i := by
  rw [subst, if_neg (by rwa [ser_leaf] at h)]

theorem subst_node_of_ne {sv : List ℕ} {v' : Term} {o : ℕ} {args : List Term}
    (h : ser sig (.node o args) ≠ sv) :
    subst sig sv v' (.node o args) = .node o (args.map (subst sig sv v')) := by
  rw [subst, if_neg h, List.attach_map_val]

theorem forall₂_map {α : Type} {f g : α → List ℕ} :
    ∀ {l : List α}, (∀ a ∈ l, f a ≤ g a) → List.Forall₂ (· ≤ ·) (l.map f) (l.map g)
  | [], _ => .nil
  | a :: l, h => .cons (h a (by simp)) (forall₂_map fun b hb => h b (by simp [hb]))

theorem mem_arrange_ser {o : ℕ} {args : List Term} {c : List ℕ}
    (h : c ∈ arrange sig o (args.map (ser sig))) : ∃ t, ser sig t = c := by
  obtain ⟨t, -, rfl⟩ := List.mem_map.1 ((arrange_perm sig o _).mem_iff.1 h)
  exact ⟨t, rfl⟩

/-- Lemma 7: replacing a subterm with a smaller one never makes a term larger. -/
theorem ser_subst_le {sv : List ℕ} {v' : Term} (hv : ser sig v' < sv) :
    ∀ t, ser sig (subst sig sv v' t) ≤ ser sig t := by
  intro t
  induction t using Term.induct with
  | leaf i =>
    by_cases h : ser sig (.leaf i) = sv
    · rw [subst_of_ser h, h]
      exact le_of_lt hv
    · rw [subst_leaf_of_ne h]
  | node o args ih =>
    by_cases h : ser sig (.node o args) = sv
    · rw [subst_of_ser h, h]
      exact le_of_lt hv
    · rw [subst_node_of_ne h, ser_node, ser_node, List.map_map]
      refine append_le_append_left [2] (flatten_le (arrange_mono sig o (forall₂_map ih)) ?_ _)
      intro a' ha' a ha hc
      obtain ⟨t', rfl⟩ := mem_arrange_ser (args := args.map (subst sig sv v'))
        (by rw [List.map_map]; exact ha')
      obtain ⟨t, rfl⟩ := mem_arrange_ser ha
      exact ser_prefix_free sig t' t hc

/-! ### Negations and triples -/

variable (sig) in
/-- The value is a `not`. -/
def isNotTerm : Term → Bool
  | .leaf _ => false
  | .node o _ => sig.isNot o

theorem ser_getLast_node (o : ℕ) (args : List Term) :
    (ser sig (.node o args)).getLast? = some o := by
  rw [ser_node]
  have h : ∀ X : List ℕ, 2 :: (X ++ [0, o]) = ((2 :: X) ++ [0]) ++ [o] := by simp
  rw [h, List.getLast?_concat]

theorem isNotTerm_of_ser_eq {t u : Term} (h : ser sig t = ser sig u) :
    isNotTerm sig t = isNotTerm sig u := by
  cases t with
  | leaf i =>
    cases u with
    | leaf j => rfl
    | node p brgs =>
      rw [ser_leaf, ser_node] at h
      exact absurd (List.cons.inj h).1 (by omega)
  | node o args =>
    cases u with
    | leaf j =>
      rw [ser_node, ser_leaf] at h
      exact absurd (List.cons.inj h).1 (by omega)
    | node p brgs =>
      have := congrArg List.getLast? h
      rw [ser_getLast_node, ser_getLast_node] at this
      cases Option.some.inj this
      rfl

theorem isNotTerm_subst {sv : List ℕ} {v' : Term}
    (hsv : ∀ a, ser sig a = sv → isNotTerm sig a = false) (hv' : isNotTerm sig v' = false)
    (a : Term) : isNotTerm sig (subst sig sv v' a) = isNotTerm sig a := by
  by_cases h : ser sig a = sv
  · rw [subst_of_ser h, hv', hsv a h]
  · cases a with
    | leaf i => rw [subst_leaf_of_ne h]
    | node o args => rw [subst_node_of_ne h]; rfl

variable (sig) in
/-- (negations, AIG nodes, declared order) of an execution. -/
def tripleL : Term → List ℕ
  | .leaf _ => []
  | .node o args => [args.countP (isNotTerm sig ·), sig.nodes o, sig.position o]

variable (sig) in
/-- The triple of an execution of a registered operation, and nothing for
other statements. -/
def tripleOf : Term → Option (List ℕ)
  | .leaf _ => none
  | .node o args => if sig.registered o then some (tripleL sig (.node o args)) else none

theorem tripleOf_subst {sv : List ℕ} {v' : Term}
    (hsv : ∀ a, ser sig a = sv → isNotTerm sig a = false) (hv' : isNotTerm sig v' = false)
    {t : Term} (ht : ser sig t ≠ sv) : tripleOf sig (subst sig sv v' t) = tripleOf sig t := by
  cases t with
  | leaf i => rw [subst_leaf_of_ne ht]
  | node o args =>
    rw [subst_node_of_ne ht]
    simp only [tripleOf, tripleL, List.countP_map]
    congr 3
    exact List.countP_congr fun a _ => by simp [isNotTerm_subst hsv hv' a]

/-! ### Programs, fixes, and the measure -/

variable (sig) in
/-- The value executes a registered operation, not `not`. -/
def IsExec (t : Term) : Prop :=
  ∃ o args, t = .node o args ∧ sig.registered o = true ∧ sig.isNot o = false

variable (sig) in
/-- The values an execution is given, in rank order within each
interchangeable group, as codes. -/
def argCodes : Term → List (List ℕ)
  | .leaf _ => []
  | .node o args => arrange sig o (args.map (ser sig))

variable (sig) in
/-- DLP 59's precedence between spellings: negations, AIG nodes, declared
order, then the values in rank order. -/
def KeyLt (v' v : Term) : Prop :=
  tripleL sig v' < tripleL sig v ∨ (tripleL sig v' = tripleL sig v ∧ argCodes sig v' < argCodes sig v)

variable (sig) in
def codes (P : List Term) : Multiset (List ℕ) := (P.map (ser sig) : Multiset (List ℕ))

variable (sig) in
def triples (P : List Term) : Multiset (List ℕ) := (P.filterMap (tripleOf sig) : Multiset (List ℕ))

/-- The Dershowitz–Manna order on multisets. -/
def DMLt (M N : Multiset (List ℕ)) : Prop :=
  ∃ X Y Z, Z ≠ 0 ∧ M = X + Y ∧ N = X + Z ∧ ∀ y ∈ Y, ∃ z ∈ Z, y < z

variable (sig) in
/-- The measure of termination.md, compared lexicographically. -/
def MeasureLt (Q P : List Term) : Prop :=
  Q.length < P.length ∨ (Q.length = P.length ∧ DMLt (triples sig Q) (triples sig P)) ∨
    (Q.length = P.length ∧ triples sig Q = triples sig P ∧ DMLt (codes sig Q) (codes sig P))

/-! ### The Dershowitz–Manna order -/

theorem DMLt.trans {M N K : Multiset (List ℕ)} : DMLt M N → DMLt N K → DMLt M K := by
  classical
  rintro ⟨X₁, Y₁, Z₁, -, rfl, rfl, hYZ₁⟩ ⟨X₂, Y₂, Z₂, hZ₂, hXZXY, rfl, hYZ₂⟩
  rw [add_comm X₁, add_comm X₂] at hXZXY
  refine ⟨X₁ ∩ X₂, Y₁ + (Y₂ - Z₁), Z₂ + (Z₁ - Y₂), ?_, ?_, ?_, ?_⟩
  · exact fun h => hZ₂ (Multiset.le_zero.1 (h ▸ Multiset.le_add_right _ _))
  · rwa [← add_assoc, add_right_comm, Multiset.inter_add_sub_of_add_eq_add]
  · rw [← add_assoc, add_right_comm, add_left_inj, Multiset.inter_comm,
      Multiset.inter_add_sub_of_add_eq_add]
    rwa [eq_comm]
  simp only [Multiset.mem_add, or_imp, forall_and]
  refine ⟨fun y hy => ?_, fun y hy => ?_⟩
  · obtain ⟨z, hz, hyz⟩ := hYZ₁ y hy
    by_cases z_in : z ∈ Y₂
    · obtain ⟨w, hw, hzw⟩ := hYZ₂ z z_in
      exact ⟨w, .inl hw, hyz.trans hzw⟩
    · exact ⟨z, .inr <| by rwa [Multiset.mem_sub, Multiset.count_eq_zero_of_notMem z_in,
        Multiset.count_pos], hyz⟩
  · obtain ⟨z, hz, hyz⟩ := hYZ₂ y <| Multiset.mem_of_le (Multiset.sub_le_self ..) hy
    exact ⟨z, .inl hz, hyz⟩

theorem DMLt.irrefl (M : Multiset (List ℕ)) : ¬ DMLt M M := by
  rintro ⟨X, Y, Z, hZ, h1, h2, hYZ⟩
  have hY : Y = Z := add_left_cancel (h1.symm.trans h2)
  subst hY
  classical
  have hne : Y.toFinset.Nonempty := by
    obtain ⟨y, hy⟩ := Multiset.exists_mem_of_ne_zero hZ
    exact ⟨y, Multiset.mem_toFinset.2 hy⟩
  obtain ⟨z, hz, hlt⟩ := hYZ _ (Multiset.mem_toFinset.1 (Y.toFinset.max'_mem hne))
  exact absurd (Y.toFinset.le_max' z (Multiset.mem_toFinset.2 hz)) (not_le.2 hlt)

theorem dm_single (X : Multiset (List ℕ)) {a' a : List ℕ} (h : a' < a) :
    DMLt (a' ::ₘ X) (a ::ₘ X) :=
  ⟨X, {a'}, {a}, Multiset.singleton_ne_zero a,
    by rw [← Multiset.singleton_add, add_comm], by rw [← Multiset.singleton_add, add_comm],
    fun y hy => ⟨a, Multiset.mem_singleton_self a, (Multiset.mem_singleton.1 hy) ▸ h⟩⟩

/-- Replacing every element with one at most as large, and one with a smaller
one, goes down. -/
theorem dm_pointwise (M : Multiset Term) (f g : Term → List ℕ) (hfg : ∀ x ∈ M, f x ≤ g x)
    {a' a : List ℕ} (h : a' < a) : DMLt (a' ::ₘ M.map f) (a ::ₘ M.map g) := by
  classical
  have hsplit := Multiset.filter_add_not (fun x => f x = g x) M
  set E := M.filter (fun x => f x = g x)
  set N := M.filter (fun x => ¬ f x = g x)
  have hE : E.map f = E.map g :=
    Multiset.map_congr rfl fun x hx => (Multiset.mem_filter.1 hx).2
  refine ⟨E.map g, a' ::ₘ N.map f, a ::ₘ N.map g, Multiset.cons_ne_zero, ?_, ?_, ?_⟩
  · rw [← hsplit, Multiset.map_add, hE, Multiset.add_cons]
  · rw [← hsplit, Multiset.map_add, Multiset.add_cons]
  · intro y hy
    rcases Multiset.mem_cons.1 hy with rfl | hy
    · exact ⟨a, Multiset.mem_cons_self a _, h⟩
    · obtain ⟨x, hx, rfl⟩ := Multiset.mem_map.1 hy
      have hxM := Multiset.mem_of_mem_filter hx
      exact ⟨g x, Multiset.mem_cons_of_mem (Multiset.mem_map_of_mem g hx),
        lt_of_le_of_ne (hfg x hxM) (Multiset.mem_filter.1 hx).2⟩

theorem MeasureLt.trans {R Q P : List Term} (h₁ : MeasureLt sig R Q) (h₂ : MeasureLt sig Q P) :
    MeasureLt sig R P := by
  rcases h₁ with h₁ | ⟨e₁, t₁⟩ | ⟨e₁, t₁, c₁⟩ <;> rcases h₂ with h₂ | ⟨e₂, t₂⟩ | ⟨e₂, t₂, c₂⟩
  all_goals first
    | exact .inl (by omega)
    | skip
  · exact .inr (.inl ⟨by omega, t₁.trans t₂⟩)
  · exact .inr (.inl ⟨by omega, t₂ ▸ t₁⟩)
  · exact .inr (.inl ⟨by omega, t₁ ▸ t₂⟩)
  · exact .inr (.inr ⟨by omega, t₁.trans t₂, c₁.trans c₂⟩)

theorem MeasureLt.irrefl (P : List Term) : ¬ MeasureLt sig P P := by
  rintro (h | ⟨-, h⟩ | ⟨-, -, h⟩)
  · exact lt_irrefl _ h
  · exact DMLt.irrefl _ h
  · exact DMLt.irrefl _ h

/-! ### Every fix lowers the measure -/

/-- Lemmas 4–6: a spelling lowers the measure of the statements' terms. P is
v's statement and the others, E; the result is v' and some of the others,
with v's term replaced by v''s. -/
theorem spelling_measure {P Q E rest : List Term} {v v' : Term} (hP : List.Perm P (v :: E))
    (hexec : IsExec sig v) (hexec' : IsExec sig v') (hkey : KeyLt sig v' v)
    (hdistinct : ∀ u ∈ E, ser sig u ≠ ser sig v) (hQ : List.Perm Q (v' :: rest))
    (hrest : List.Subperm rest (E.map (subst sig (ser sig v) v'))) : MeasureLt sig Q P := by
  have hlenP : E.length + 1 = P.length := by
    rw [hP.length_eq]
    rfl
  have hlenQ : Q.length = rest.length + 1 := by
    rw [hQ.length_eq]
    rfl
  have hsub : rest.length ≤ E.length := by
    simpa using hrest.length_le
  by_cases hlt : rest.length < E.length
  · left
    omega
  have hperm : List.Perm rest (E.map (subst sig (ser sig v) v')) :=
    hrest.perm_of_length_le (by simp; omega)
  have hQ' := hQ.trans (hperm.cons v')
  have hP' : List.Perm P (v :: E) := hP
  obtain ⟨o, args, rfl, hreg, hnot⟩ := hexec
  obtain ⟨o', args', rfl, hreg', hnot'⟩ := hexec'
  have hsv : ∀ a, ser sig a = ser sig (.node o args) → isNotTerm sig a = false :=
    fun a ha => (isNotTerm_of_ser_eq ha).trans hnot
  have hv'n : isNotTerm sig (.node o' args') = false := hnot'
  have hT0 : (E.map (subst sig (ser sig (.node o args)) (.node o' args'))).filterMap
      (tripleOf sig) = E.filterMap (tripleOf sig) := by
    rw [List.filterMap_map]
    exact List.filterMap_congr fun u hu => tripleOf_subst hsv hv'n (hdistinct u hu)
  have hTQ : triples sig Q =
      tripleL sig (.node o' args') ::ₘ (E.filterMap (tripleOf sig) :
        Multiset (List ℕ)) := by
    unfold triples
    rw [Multiset.coe_eq_coe.2 (hQ'.filterMap _), List.filterMap_cons, tripleOf, if_pos hreg', hT0]
    rfl
  have hTP : triples sig P =
      tripleL sig (.node o args) ::ₘ (E.filterMap (tripleOf sig) :
        Multiset (List ℕ)) := by
    unfold triples
    rw [Multiset.coe_eq_coe.2 (hP'.filterMap _), List.filterMap_cons, tripleOf, if_pos hreg]
    rfl
  have hcQ : codes sig Q = ser sig (.node o' args') ::ₘ
      ((E : Multiset Term).map
        (ser sig ∘ subst sig (ser sig (.node o args)) (.node o' args'))) := by
    unfold codes
    rw [Multiset.coe_eq_coe.2 (hQ'.map _), List.map_cons, List.map_map, Multiset.map_coe]
    rfl
  have hcP : codes sig P = ser sig (.node o args) ::ₘ
      ((E : Multiset Term).map (ser sig)) := by
    unfold codes
    rw [Multiset.coe_eq_coe.2 (hP'.map _), List.map_cons, Multiset.map_coe]
    rfl
  rcases hkey with hk | ⟨hk, hargs⟩
  · right
    left
    refine ⟨by omega, ?_⟩
    rw [hTQ, hTP]
    exact dm_single _ hk
  · right
    right
    refine ⟨by omega, by rw [hTQ, hTP, hk], ?_⟩
    have hpos : sig.position o' = sig.position o := by
      simp only [tripleL, List.cons.injEq] at hk
      exact hk.2.2.1
    obtain rfl : o' = o := sig.position_injective _ _ hreg' hreg hpos
    have hser : ser sig (.node o' args') < ser sig (.node o' args) := by
      rw [ser_node, ser_node]
      refine append_lt_append_left [2] (flatten_lt hargs ?_ ?_ [o'])
      · intro a' ha' a ha hc
        obtain ⟨t', rfl⟩ := mem_arrange_ser ha'
        obtain ⟨t, rfl⟩ := mem_arrange_ser ha
        exact ser_prefix_free sig t' t hc
      · intro a ha
        obtain ⟨t, rfl⟩ := mem_arrange_ser ha
        exact ser_head sig t
    rw [hcQ, hcP]
    exact dm_pointwise _ _ _ (fun x _ => ser_subst_le hser x) hser

/-! ### One value operation -/

/-- A statement: its term, and how many of its values are constant. -/
abbrev Stmt := Term × ℕ

/-- C: the number of constant values. -/
def constCount (P : List Stmt) : ℕ := (P.map Prod.snd).sum

/-- Rewriting a statement's term keeps its functions, so how many of its
values are constant. -/
def keepConst (f : Term → Term) (s : Stmt) : Stmt := (f s.1, s.2)

theorem constCount_map_keepConst (f : Term → Term) (P : List Stmt) :
    constCount (P.map (keepConst f)) = constCount P := by
  simp [constCount, keepConst, List.map_map, Function.comp_def]

theorem constCount_perm {P Q : List Stmt} (h : List.Perm P Q) : constCount P = constCount Q :=
  (h.map Prod.snd).sum_eq

theorem constCount_subperm {P Q : List Stmt} (h : List.Subperm P Q) :
    constCount P ≤ constCount Q := by
  obtain ⟨l, hl, hsub⟩ := h
  rw [← constCount_perm hl]
  exact (hsub.map Prod.snd).sum_le_sum fun _ _ => Nat.zero_le _

theorem constCount_append (P Q : List Stmt) :
    constCount (P ++ Q) = constCount P + constCount Q := by
  simp [constCount]

theorem constCount_cons (s : Stmt) (P : List Stmt) : constCount (s :: P) = s.2 + constCount P := by
  simp [constCount]

theorem constCount_erase {P : List Stmt} {v : Stmt} (hv : v ∈ P) :
    constCount P = v.2 + constCount (P.erase v) := by
  rw [constCount_perm (List.perm_cons_erase hv), constCount_cons]

theorem constCount_zero {P : List Stmt} (h : ∀ a ∈ P, a.2 = 0) : constCount P = 0 := by
  induction P with
  | nil => rfl
  | cons a P ih =>
    rw [constCount_cons, h a (by simp), ih fun b hb => h b (by simp [hb])]

variable (sig) in
/-- The fixes inside one value operation, on its statements. -/
inductive OpFix : List Stmt → List Stmt → Prop
  /-- Simplifying a constant value v: v is gone, the statements it reached
  are replaced by new ones with no constant value, and every other statement
  keeps its functions. -/
  | simplify {P Q : List Stmt} (v : Stmt) (hv : v ∈ P) (hconst : 1 ≤ v.2) (added survivors : List Stmt)
      (rw : Term → Term) (hQ : List.Perm Q (added ++ survivors))
      (hs : List.Subperm survivors ((P.erase v).map (keepConst rw)))
      (hadded : ∀ a ∈ added, a.2 = 0) : OpFix P Q
  /-- A redundant value v: reading w instead makes v's statement dead, and
  every other statement keeps its functions. -/
  | redundant {P Q : List Stmt} (v : Stmt) (hv : v ∈ P) (rw : Term → Term)
      (hQ : List.Subperm Q ((P.erase v).map (keepConst rw))) : OpFix P Q
  /-- An ordinary match: the statements that survive, and the one or two
  added, none of them constant, with more removed than added. -/
  | ordinary {P Q : List Stmt} (v : Stmt) (hv : v ∈ P) (added survivors : List Stmt)
      (rw : Term → Term) (hQ : List.Perm Q (added ++ survivors))
      (hs : List.Subperm survivors ((P.erase v).map (keepConst rw)))
      (hadded : ∀ a ∈ added, a.2 = 0)
      (hrestrict : survivors.length + added.length + 1 ≤ P.length) : OpFix P Q
  /-- A spelling: v becomes v', with the same functions, and every other
  statement has v's term replaced by v''s. -/
  | spelling {P Q : List Stmt} (v v' : Term) (c : ℕ) (rest : List Stmt) (hv : (v, c) ∈ P)
      (hexec : IsExec sig v) (hexec' : IsExec sig v') (hkey : KeyLt sig v' v)
      (hdistinct : ∀ u ∈ ((P.erase (v, c)).map Prod.fst), ser sig u ≠ ser sig v)
      (hQ : List.Perm Q ((v', c) :: rest))
      (hrest : List.Subperm rest ((P.erase (v, c)).map (keepConst (subst sig (ser sig v) v')))) :
      OpFix P Q

variable (sig) in
/-- The measure of one value operation: C, then the statements' measure. -/
def OpLt (Q P : List Stmt) : Prop :=
  constCount Q < constCount P ∨
    (constCount Q = constCount P ∧ MeasureLt sig (Q.map Prod.fst) (P.map Prod.fst))

theorem OpLt.trans {R Q P : List Stmt} (h₁ : OpLt sig R Q) (h₂ : OpLt sig Q P) : OpLt sig R P := by
  rcases h₁ with h₁ | ⟨e₁, m₁⟩ <;> rcases h₂ with h₂ | ⟨e₂, m₂⟩
  · exact .inl (by omega)
  · exact .inl (by omega)
  · exact .inl (by omega)
  · exact .inr ⟨by omega, m₁.trans m₂⟩

theorem OpLt.irrefl (P : List Stmt) : ¬ OpLt sig P P := by
  rintro (h | ⟨-, h⟩)
  · exact lt_irrefl _ h
  · exact MeasureLt.irrefl _ h

theorem length_map_fst (P : List Stmt) : (P.map Prod.fst).length = P.length := List.length_map _

theorem opFix_constCount_le {P Q : List Stmt} (h : OpFix sig P Q) : constCount Q ≤ constCount P := by
  cases h with
  | simplify v hv _ added survivors rw hQ hs hadded =>
    rw [constCount_perm hQ, constCount_append, constCount_zero hadded, constCount_erase hv]
    have := (constCount_subperm hs).trans (constCount_map_keepConst rw _).le
    omega
  | redundant v hv rw hQ =>
    rw [constCount_erase hv]
    have := (constCount_subperm hQ).trans (constCount_map_keepConst rw _).le
    omega
  | ordinary v hv added survivors rw hQ hs hadded _ =>
    rw [constCount_perm hQ, constCount_append, constCount_zero hadded, constCount_erase hv]
    have := (constCount_subperm hs).trans (constCount_map_keepConst _ _).le
    omega
  | spelling v v' c rest hv _ _ _ _ hQ hrest =>
    rw [constCount_perm hQ, constCount_cons, constCount_erase hv]
    have := (constCount_subperm hrest).trans (constCount_map_keepConst _ _).le
    simp only at this ⊢
    omega

/-- Theorem 1: every fix in a value operation lowers its measure. -/
theorem opFix_lt {P Q : List Stmt} (h : OpFix sig P Q) : OpLt sig Q P := by
  have hC := opFix_constCount_le h
  rcases Nat.lt_or_eq_of_le hC with hlt | heq
  · exact .inl hlt
  refine .inr ⟨heq, ?_⟩
  cases h with
  | simplify v hv hconst added survivors rw hQ hs hadded =>
    exfalso
    rw [constCount_perm hQ, constCount_append, constCount_zero hadded, constCount_erase hv] at heq
    have := (constCount_subperm hs).trans (constCount_map_keepConst rw _).le
    omega
  | redundant v hv rw hQ =>
    left
    have h1 := hQ.length_le
    have h2 := List.length_erase_of_mem hv
    have h3 := List.length_pos_of_mem hv
    simp only [List.length_map] at h1 ⊢
    omega
  | ordinary v hv added survivors rw hQ hs hadded hrestrict =>
    left
    rw [length_map_fst, length_map_fst, hQ.length_eq, List.length_append]
    omega
  | spelling v v' c rest hv hexec hexec' hkey hdistinct hQ hrest =>
    refine spelling_measure (E := (P.erase (v, c)).map Prod.fst) (rest := rest.map Prod.fst)
      ?_ hexec hexec' hkey hdistinct (by simpa using hQ.map Prod.fst) ?_
    · simpa using (List.perm_cons_erase hv).map Prod.fst
    · obtain ⟨l, hl, hsub⟩ := hrest
      refine ⟨l.map Prod.fst, hl.map _, ?_⟩
      simpa [keepConst, List.map_map, Function.comp_def] using hsub.map Prod.fst

/-- A fix that keeps C adds no statement. -/
theorem opFix_length_le {P Q : List Stmt} (h : OpFix sig P Q)
    (hC : constCount Q = constCount P) : Q.length ≤ P.length := by
  rcases opFix_lt h with hlt | ⟨-, hm⟩
  · omega
  rcases hm with hl | ⟨hl, -⟩ | ⟨hl, -⟩ <;> simp only [List.length_map] at hl <;> omega

/-! ### A program -/

/-- A value operation: its boolean statements, and its number of written views. -/
structure OpState where
  stmts : List Stmt
  views : ℕ

/-- A program of `n` value operations; `none` is one that was removed. -/
abbrev Program (n : ℕ) := Fin n → Option OpState

/-- C plus the number of written views. -/
def weight : Option OpState → ℕ
  | none => 0
  | some A => constCount A.stmts + A.views

/-- Φ. -/
def phi {n : ℕ} (p : Program n) : ℕ := ∑ a, weight (p a)

variable (sig) in
/-- One value operation's state below another: removed is below every value
operation, and otherwise, the same written views and a lower measure. -/
def OptLt : Option OpState → Option OpState → Prop
  | none, some _ => True
  | some A', some A => A'.views = A.views ∧ OpLt sig A'.stmts A.stmts
  | _, none => False

theorem OptLt.trans {x y z : Option OpState} (h₁ : OptLt sig x y) (h₂ : OptLt sig y z) :
    OptLt sig x z := by
  match x, y, z, h₁, h₂ with
  | none, some _, some _, _, _ => trivial
  | some _, some _, some _, ⟨e₁, m₁⟩, ⟨e₂, m₂⟩ => exact ⟨e₁.trans e₂, m₁.trans m₂⟩

theorem OptLt.irrefl (x : Option OpState) : ¬ OptLt sig x x := by
  match x with
  | none => exact id
  | some A => exact fun h => OpLt.irrefl A.stmts h.2

variable (sig) in
/-- Programs, ordered by Φ and then pointwise. -/
def ProgLt {n : ℕ} (q p : Program n) : Prop :=
  phi q < phi p ∨
    (phi q = phi p ∧ (∀ a, q a = p a ∨ OptLt sig (q a) (p a)) ∧ ∃ a, OptLt sig (q a) (p a))

theorem ProgLt.trans {n : ℕ} {r q p : Program n} (h₁ : ProgLt sig r q) (h₂ : ProgLt sig q p) :
    ProgLt sig r p := by
  rcases h₁ with h₁ | ⟨e₁, le₁, ⟨a, lt₁⟩⟩ <;> rcases h₂ with h₂ | ⟨e₂, le₂, -⟩
  · exact .inl (by omega)
  · exact .inl (by omega)
  · exact .inl (by omega)
  · refine .inr ⟨by omega, fun b => ?_, ⟨a, ?_⟩⟩
    · rcases le₁ b with h | h <;> rcases le₂ b with h' | h'
      · exact .inl (h.trans h')
      · exact .inr (h ▸ h')
      · exact .inr (h' ▸ h)
      · exact .inr (h.trans h')
    · rcases le₂ a with h' | h'
      · exact h' ▸ lt₁
      · exact lt₁.trans h'

theorem ProgLt.irrefl {n : ℕ} (p : Program n) : ¬ ProgLt sig p p := by
  rintro (h | ⟨-, -, ⟨a, h⟩⟩)
  · exact lt_irrefl _ h
  · exact OptLt.irrefl _ h

variable (sig) in
/-- The fixes of a program. -/
inductive ProgStep {n : ℕ} : Program n → Program n → Prop
  /-- A fix inside value operation `a`, which keeps its written views; the
  others don't change. -/
  | local {p q : Program n} (a : Fin n) (A A' : OpState) (ha : p a = some A) (hqa : q a = some A')
      (hfix : OpFix sig A.stmts A'.stmts) (hviews : A'.views = A.views)
      (hrest : ∀ b, b ≠ a → q b = p b) : ProgStep p q
  /-- Removing a constant written view of `a` (Lemma 8): `a` has one fewer
  written view and no more constant values, or it's removed if that was its
  only one; every value operation in `callers` executes it, keeps its written
  views, and has fewer constant values; the others don't change. -/
  | dropView {p q : Program n} (a : Fin n) (A : OpState) (ha : p a = some A)
      (hcallee : (q a = none ∧ A.views = 1) ∨
        ∃ A', q a = some A' ∧ A'.views + 1 = A.views ∧ constCount A'.stmts ≤ constCount A.stmts)
      (callers : Finset (Fin n)) (hnot : a ∉ callers)
      (hcallers : ∀ b ∈ callers, ∃ B B', p b = some B ∧ q b = some B' ∧ B'.views = B.views ∧
        constCount B'.stmts < constCount B.stmts)
      (hrest : ∀ b, b ≠ a → b ∉ callers → q b = p b) : ProgStep p q

theorem weight_local {A A' : OpState} (hviews : A'.views = A.views) :
    weight (some A') + constCount A.stmts = weight (some A) + constCount A'.stmts := by
  simp only [weight, hviews]
  omega

theorem local_phi_le {n : ℕ} {p q : Program n} {a : Fin n} {A A' : OpState} (ha : p a = some A)
    (hqa : q a = some A') (hviews : A'.views = A.views)
    (hC : constCount A'.stmts ≤ constCount A.stmts) (hrest : ∀ b, b ≠ a → q b = p b) :
    ∀ b ∈ Finset.univ, weight (q b) ≤ weight (p b) := by
  intro b _
  by_cases hb : b = a
  · subst hb
    rw [ha, hqa]
    have := weight_local hviews
    omega
  · rw [hrest b hb]

theorem local_phi_lt {n : ℕ} {p q : Program n} {a : Fin n} {A A' : OpState} (ha : p a = some A)
    (hqa : q a = some A') (hviews : A'.views = A.views)
    (hC : constCount A'.stmts < constCount A.stmts) (hrest : ∀ b, b ≠ a → q b = p b) :
    phi q < phi p := by
  refine Finset.sum_lt_sum (local_phi_le ha hqa hviews hC.le hrest) ⟨a, Finset.mem_univ _, ?_⟩
  rw [ha, hqa]
  have := weight_local hviews
  omega

theorem dropView_phi_lt {n : ℕ} {p q : Program n} {a : Fin n} {A : OpState} (ha : p a = some A)
    (hcallee : (q a = none ∧ A.views = 1) ∨
      ∃ A', q a = some A' ∧ A'.views + 1 = A.views ∧ constCount A'.stmts ≤ constCount A.stmts)
    {callers : Finset (Fin n)}
    (hcallers : ∀ b ∈ callers, ∃ B B', p b = some B ∧ q b = some B' ∧ B'.views = B.views ∧
      constCount B'.stmts < constCount B.stmts)
    (hrest : ∀ b, b ≠ a → b ∉ callers → q b = p b) : phi q < phi p := by
  classical
  have hle : ∀ b ∈ Finset.univ, weight (q b) ≤ weight (p b) := by
    intro b _
    by_cases hb : b = a
    · subst hb
      rw [ha]
      rcases hcallee with ⟨hq, -⟩ | ⟨A', hq, hv, hc⟩
      · rw [hq]
        exact Nat.zero_le _
      · rw [hq]
        simp only [weight]
        omega
    · by_cases hc : b ∈ callers
      · obtain ⟨B, B', hp, hq, hv, hlt⟩ := hcallers b hc
        rw [hp, hq]
        simp only [weight, hv]
        omega
      · rw [hrest b hb hc]
  refine Finset.sum_lt_sum hle ⟨a, Finset.mem_univ _, ?_⟩
  rw [ha]
  rcases hcallee with ⟨hq, hv⟩ | ⟨A', hq, hv, hc⟩
  · rw [hq]
    simp only [weight]
    omega
  · rw [hq]
    simp only [weight]
    omega

/-- Theorem 2: every fix of a program lowers it. -/
theorem progStep_lt {n : ℕ} {p q : Program n} (h : ProgStep sig p q) : ProgLt sig q p := by
  cases h with
  | «local» a A A' ha hqa hfix hviews hrest =>
    rcases Nat.lt_or_eq_of_le (opFix_constCount_le hfix) with hC | hC
    · exact .inl (local_phi_lt ha hqa hviews hC hrest)
    · right
      refine ⟨Finset.sum_congr rfl fun b _ => ?_, fun b => ?_, ⟨a, ?_⟩⟩
      · by_cases hb : b = a
        · subst hb
          rw [ha, hqa]
          have := weight_local hviews
          omega
        · rw [hrest b hb]
      · by_cases hb : b = a
        · subst hb
          rw [ha, hqa]
          exact .inr ⟨hviews, opFix_lt hfix⟩
        · exact .inl (hrest b hb)
      · rw [ha, hqa]
        exact ⟨hviews, opFix_lt hfix⟩
  | dropView a A ha hcallee callers hnot hcallers hrest =>
    exact .inl (dropView_phi_lt ha hcallee hcallers hrest)

theorem transGen_progLt {n : ℕ} {p q : Program n} (h : Relation.TransGen (ProgStep sig) p q) :
    ProgLt sig q p := by
  induction h with
  | single h => exact progStep_lt h
  | tail _ h ih => exact (progStep_lt h).trans ih

/-- Fixing a program never returns to a program it has left. -/
theorem prog_no_cycle {n : ℕ} {p : Program n} (h : Relation.TransGen (ProgStep sig) p p) : False :=
  ProgLt.irrefl p (transGen_progLt h)

theorem transGen_of_lt {n : ℕ} (f : ℕ → Program n) (hstep : ∀ k, ProgStep sig (f k) (f (k + 1))) :
    ∀ {i j : ℕ}, i < j → Relation.TransGen (ProgStep sig) (f i) (f j)
  | i, j + 1, h => by
    rcases Nat.lt_succ_iff_lt_or_eq.1 h with h | rfl
    · exact (transGen_of_lt f hstep h).tail (hstep j)
    · exact .single (hstep i)

/-- The number of statements of a value operation, or 0 if it was removed. -/
def size : Option OpState → ℕ
  | none => 0
  | some A => A.stmts.length

/-- A fix that keeps Φ adds no statement anywhere. -/
theorem progStep_size_le {n : ℕ} {p q : Program n} (h : ProgStep sig p q) (hphi : phi q = phi p)
    (b : Fin n) : size (q b) ≤ size (p b) := by
  cases h with
  | «local» a A A' ha hqa hfix hviews hrest =>
    by_cases hb : b = a
    · subst hb
      rw [ha, hqa]
      simp only [size]
      rcases Nat.lt_or_eq_of_le (opFix_constCount_le hfix) with hC | hC
      · exact absurd hphi (ne_of_lt (local_phi_lt ha hqa hviews hC hrest))
      · exact opFix_length_le hfix hC
    · rw [hrest b hb]
  | dropView a A ha hcallee callers hnot hcallers hrest =>
    exact absurd hphi (ne_of_lt (dropView_phi_lt ha hcallee hcallers hrest))

/-- Fixing a program terminates: in an infinite sequence of fixes, Φ stops
going down, after which no value operation grows, so if only finitely many
programs within those bounds occur, some program repeats, which can't
happen. -/
theorem prog_terminates {n : ℕ} (f : ℕ → Program n) (hstep : ∀ k, ProgStep sig (f k) (f (k + 1)))
    (hfin : ∀ bound : Fin n → ℕ,
      {p | (∃ k, f k = p) ∧ ∀ a, size (p a) ≤ bound a}.Finite) : False := by
  have hanti : ∀ k, phi (f (k + 1)) ≤ phi (f k) := fun k => by
    rcases progStep_lt (hstep k) with h | ⟨h, -⟩ <;> omega
  -- Φ takes its least value at some k₀ and keeps it.
  obtain ⟨k₀, hk₀⟩ : ∃ k₀, ∀ k, phi (f k₀) ≤ phi (f k) := by
    classical
    let m := Nat.find (⟨phi (f 0), 0, rfl⟩ : ∃ m, ∃ k, phi (f k) = m)
    obtain ⟨k₀, hk⟩ := Nat.find_spec (⟨phi (f 0), 0, rfl⟩ : ∃ m, ∃ k, phi (f k) = m)
    exact ⟨k₀, fun k => hk ▸ Nat.find_min' _ ⟨k, rfl⟩⟩
  have hmono : ∀ i j, i ≤ j → phi (f j) ≤ phi (f i) := by
    intro i j hij
    induction hij with
    | refl => exact le_refl _
    | step _ ih => exact (hanti _).trans ih
  have hconst : ∀ k, k₀ ≤ k → phi (f (k + 1)) = phi (f k) := fun k hk =>
    le_antisymm (hanti k) ((hmono k₀ k hk).trans (hk₀ (k + 1)))
  have hsize : ∀ k, k₀ ≤ k → ∀ a, size (f k a) ≤ size (f k₀ a) := by
    intro k hk
    induction hk with
    | refl => exact fun _ => le_refl _
    | step hk ih => exact fun a => (progStep_size_le (hstep _) (hconst _ hk) a).trans (ih a)
  let g : ℕ → Program n := fun k => f (k₀ + k)
  have hinj : Function.Injective g := by
    intro i j hij
    change f (k₀ + i) = f (k₀ + j) at hij
    by_contra hne
    rcases Nat.lt_or_gt_of_ne hne with h | h
    · have := transGen_of_lt f hstep (by omega : k₀ + i < k₀ + j)
      rw [hij] at this
      exact prog_no_cycle this
    · have := transGen_of_lt f hstep (by omega : k₀ + j < k₀ + i)
      rw [hij] at this
      exact prog_no_cycle this
  exact Set.infinite_of_injective_forall_mem (s := {p | (∃ k, f k = p) ∧
      ∀ a, size (p a) ≤ size (f k₀ a)}) hinj
    (fun k => ⟨⟨k₀ + k, rfl⟩, hsize (k₀ + k) (by omega)⟩) (hfin _)

end Define.BooleanEqualityChecking.Termination
