import Mathlib.Data.List.Sort
import Mathlib.Data.List.Lex
import Mathlib.Data.Multiset.AddSub
import Mathlib.Data.Multiset.DershowitzManna
import Mathlib.Data.Multiset.Filter
import Mathlib.Data.Multiset.UnionInter
import Mathlib.Data.Finset.Max
import Mathlib.Data.Set.Finite.Basic
import Mathlib.Order.WellFoundedSet
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.Order.BigOperators.Group.List

set_option warningAsError true
set_option autoImplicit false

/-!
# Fixing a program always terminates

This file formalizes `termination.md`: fixing never returns to a program it
has left (`prog_no_cycle`), and an infinite sequence of fixes would have to
visit infinitely many states of one value operation within a fixed bound on
its size (`prog_terminates`).

A value operation's boolean statements are given by their terms (`Term`)
and how many of their values are constant (`Stmt`). Each statement has one
value, its term, which is exact: DLP 57 makes a boolean value operation
write exactly one view, so no execution has several values. An input is a `leaf`,
and a statement is a `node` applying an operation to the terms of the values
it reads. A term's code (`ser`) writes it out in DLP 58's rank order: `[1, i]`
for leaf `i`, and for a statement `2`, then the codes of its values in view
order, with each group of interchangeable views given its group's codes in
sorted order (`arrange`), then `0` and the operation.
Comparing codes lexicographically is the rank order: values first, a
shorter list first, then the operation.

One value operation's measure (`OpLt`) is C, the number of constant values
(`constCount`), then the number of statements, then the number of them that
aren't a `not` (`others`), then the multiset of the executions' (negations,
AIG nodes, declared order) (`triples`), then the multiset of the statements'
codes (`codes`), with multisets in Mathlib's Dershowitz–Manna order
(`Multiset.IsDershowitzMannaLT`). Its fixes (`OpFix`):

- `simplify`: a constant value v is simplified away. v's statement is gone,
  the statements it reached are replaced by new ones with no constant value,
  and every other statement keeps its functions.
- `redundant`: a redundant value v that's the same as another. Every
  statement of the result is one of the others, rewritten, with the same
  functions.
- `dead`: dead statements are removed; every other statement is unchanged.
- `opposite`: a redundant value v that's the opposite of another, w, and
  isn't a `not`. v's statement becomes `not w`, and every other statement's
  term has v's term replaced by `not w`'s; some may become dead.
- `ordinary`: an ordinary match. The result is the statements that survive
  and the one or two added, which aren't constant, and more are removed than
  added.
- `spelling`: a single execution v respelled as the execution v', with
  higher precedence (`KeyLt`). Every other statement's term has v's term
  replaced by v''s (`subst`); some may become dead. No other statement has
  v's term, because redundant values are fixed first.

A program (`Program`) is a fixed number of value operations, each present or
removed, with its numbers of written and read views. V is the number of
read views of all of them (`vsum`), and Φ the sum of C and the written views
(`phi`). Its fixes (`ProgStep`) are a fix inside one value operation,
removing a constant written view, which also lowers C in every value
operation that executes it, and removing a read view that doesn't matter,
whose reads are given another read view (which can raise C) and which can
leave statements dead (and removed) where it's executed; each lowers V,
or keeps it and lowers Φ, or keeps both and lowers the program pointwise
(`ProgLt`). `ProgFix` adds writing out: a match or spelling in one value
operation whose execution would make a cycle first writes out executions in
the registered operation's definition, which can grow without bound, but
comes later in a fixed priority (`rank`). V never goes up, nor Φ while V
stays, and once both stop going down, each value operation stops changing
after the ones before it in priority have.

`and` and `not` are registered operations for every value operation
(`Signature.registered` is true for both; `IsExec` still leaves out `not`),
so executions of `and` have triples and can be respelled.

The semantics (which fixes exist) never matter: the theorems hold for every
fix of these shapes.

`opFix_lt`, `progStep_lt`, `prog_no_cycle`, and `prog_terminates` state the
result; the last two are about `ProgFix`.
-/

namespace Define.BooleanEqualityChecking.Termination

inductive Term where
  | leaf (i : ℕ)
  | node (op : ℕ) (args : List Term)

noncomputable instance : DecidableEq Term := Classical.decEq _

structure Signature where
  /-- The group of each of an operation's views: views in the same group are
  interchangeable. -/
  group : ℕ → ℕ → ℕ
  /-- The operation is `not`. -/
  isNot : ℕ → Bool
  /-- The operation is a registered boolean operation (`and` and `not` are, for
  every value operation). -/
  registered : ℕ → Bool
  /-- AIG nodes of a registered operation's own logic. -/
  nodes : ℕ → ℕ
  /-- A registered operation's place in the declared order. -/
  position : ℕ → ℕ
  position_injective : ∀ o p, registered o = true → registered p = true →
    position o = position p → o = p

variable (sig : Signature)

/-- The codes at the views `p` holds for, from view `i` on. -/
def extract (p : ℕ → Bool) : List (List ℕ) → ℕ → List (List ℕ)
  | [], _ => []
  | x :: l, i => if p i then x :: extract p l (i + 1) else extract p l (i + 1)

/-- The codes at the other views, from view `i` on. -/
def keep (p : ℕ → Bool) : List (List ℕ) → ℕ → List (List ℕ)
  | [], _ => []
  | x :: l, i => if p i then keep p l (i + 1) else x :: keep p l (i + 1)

/-- The codes with those at the views `p` holds for, from view `i` on,
replaced by `q`'s in order. -/
def place (p : ℕ → Bool) : List (List ℕ) → List (List ℕ) → ℕ → List (List ℕ)
  | [], _, _ => []
  | x :: l, q, i => if p i then q.headD x :: place p l q.tail (i + 1) else x :: place p l q (i + 1)

/-- The codes with those at the views `p` holds for sorted among those views. -/
def sortAt (p : ℕ → Bool) (l : List (List ℕ)) : List (List ℕ) :=
  place p l ((extract p l 0).insertionSort (· ≤ ·)) 0

/-- An execution's codes in view order, with each group's codes sorted among
the group's views. -/
def arrange (o : ℕ) (codes : List (List ℕ)) : List (List ℕ) :=
  (List.range codes.length).foldl
    (fun acc i => sortAt (fun j => sig.group o j == sig.group o i) acc) codes

theorem perm_extract_keep (p : ℕ → Bool) :
    ∀ (l : List (List ℕ)) (i : ℕ), List.Perm l (extract p l i ++ keep p l i)
  | [], _ => by simp [extract, keep]
  | x :: l, i => by
    cases h : p i
    · simp only [extract, keep, h, Bool.false_eq_true, ↓reduceIte]
      exact ((perm_extract_keep p l (i + 1)).cons x).trans List.perm_middle.symm
    · simp only [extract, keep, h, ↓reduceIte]
      exact (perm_extract_keep p l (i + 1)).cons x

theorem place_perm (p : ℕ → Bool) : ∀ (l q : List (List ℕ)) (i : ℕ),
    q.length = (extract p l i).length → List.Perm (place p l q i) (keep p l i ++ q)
  | [], q, i, h => by
    have hq : q = [] := by simpa [extract] using h
    subst hq
    simp [place, keep]
  | x :: l, q, i, h => by
    cases hp : p i
    · simp only [extract, hp, Bool.false_eq_true, ↓reduceIte] at h
      simp only [place, keep, hp, Bool.false_eq_true, ↓reduceIte]
      exact (place_perm p l q (i + 1) h).cons x
    · simp only [extract, hp, ↓reduceIte, List.length_cons] at h
      obtain ⟨y, q, rfl⟩ := List.exists_cons_of_length_eq_add_one h
      simp only [place, keep, hp, ↓reduceIte, List.headD_cons, List.tail_cons]
      exact ((place_perm p l q (i + 1) (by simpa using h)).cons y).trans List.perm_middle.symm

theorem sortAt_perm (p : ℕ → Bool) (l : List (List ℕ)) : List.Perm (sortAt p l) l :=
  (place_perm p l _ 0 (List.perm_insertionSort _ _).length_eq).trans
    (((List.perm_insertionSort _ _).append_left _).trans
      (List.perm_append_comm.trans (perm_extract_keep p l 0).symm))

theorem foldl_sortAt_perm (o : ℕ) : ∀ (is : List ℕ) (acc : List (List ℕ)),
    List.Perm (is.foldl (fun acc i => sortAt (fun j => sig.group o j == sig.group o i) acc) acc) acc
  | [], _ => List.Perm.refl _
  | _ :: is, acc => (foldl_sortAt_perm o is _).trans (sortAt_perm _ acc)

theorem arrange_perm (o : ℕ) (codes : List (List ℕ)) : List.Perm (arrange sig o codes) codes :=
  foldl_sortAt_perm sig o _ codes

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

theorem extract_mono (p : ℕ → Bool) : ∀ {l' l : List (List ℕ)} (i : ℕ),
    List.Forall₂ (· ≤ ·) l' l → List.Forall₂ (· ≤ ·) (extract p l' i) (extract p l i)
  | [], [], _, .nil => .nil
  | _ :: _, _ :: _, i, .cons hx hl => by
    have ih := extract_mono p (i + 1) hl
    cases h : p i
    · simpa only [extract, h, Bool.false_eq_true, ↓reduceIte] using ih
    · simpa only [extract, h, ↓reduceIte] using List.Forall₂.cons hx ih

theorem place_mono (p : ℕ → Bool) : ∀ {l' l q' q : List (List ℕ)} (i : ℕ),
    List.Forall₂ (· ≤ ·) l' l → List.Forall₂ (· ≤ ·) q' q →
      List.Forall₂ (· ≤ ·) (place p l' q' i) (place p l q i)
  | [], [], _, _, _, .nil, _ => .nil
  | _ :: _, _ :: _, _, _, i, .cons hx hl, hq => by
    cases h : p i
    · simp only [place, h, Bool.false_eq_true, ↓reduceIte]
      exact .cons hx (place_mono p (i + 1) hl hq)
    · simp only [place, h, ↓reduceIte]
      cases hq with
      | nil => exact .cons hx (place_mono p (i + 1) hl .nil)
      | cons hy ht => exact .cons hy (place_mono p (i + 1) hl ht)

theorem sortAt_mono (p : ℕ → Bool) {l' l : List (List ℕ)} (h : List.Forall₂ (· ≤ ·) l' l) :
    List.Forall₂ (· ≤ ·) (sortAt p l') (sortAt p l) :=
  place_mono p 0 h (insertionSort_mono (extract_mono p 0 h))

theorem foldl_sortAt_mono (o : ℕ) : ∀ (is : List ℕ) {acc' acc : List (List ℕ)},
    List.Forall₂ (· ≤ ·) acc' acc →
      List.Forall₂ (· ≤ ·)
        (is.foldl (fun acc i => sortAt (fun j => sig.group o j == sig.group o i) acc) acc')
        (is.foldl (fun acc i => sortAt (fun j => sig.group o j == sig.group o i) acc) acc)
  | [], _, _, h => h
  | _ :: is, _, _, h => foldl_sortAt_mono o is (sortAt_mono _ h)

theorem arrange_mono (o : ℕ) {l' l : List (List ℕ)} (h : List.Forall₂ (· ≤ ·) l' l) :
    List.Forall₂ (· ≤ ·) (arrange sig o l') (arrange sig o l) := by
  unfold arrange
  rw [h.length_eq]
  exact foldl_sortAt_mono sig o _ h

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

variable (sig) in
/-- The number of statements that aren't a `not`. -/
def others (P : List Term) : ℕ := P.countP (fun t => !isNotTerm sig t)

/-- The Dershowitz–Manna order on multisets of codes. -/
abbrev DMLt (M N : Multiset (List ℕ)) : Prop := Multiset.IsDershowitzMannaLT M N

variable (sig) in
/-- The measure of termination.md, compared lexicographically. -/
def MeasureLt (Q P : List Term) : Prop :=
  Q.length < P.length ∨ (Q.length = P.length ∧ others sig Q < others sig P) ∨
    (Q.length = P.length ∧ others sig Q = others sig P ∧
      DMLt (triples sig Q) (triples sig P)) ∨
    (Q.length = P.length ∧ others sig Q = others sig P ∧ triples sig Q = triples sig P ∧
      DMLt (codes sig Q) (codes sig P))

/-! ### The Dershowitz–Manna order

Mathlib proves the order transitive. Its proof that the order is
well-founded needs a well-founded order on the elements, which the rank
order on all terms isn't (see termination.md), so irreflexivity is proved
here. -/

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
  rcases h₁ with h₁ | ⟨e₁, k₁⟩ | ⟨e₁, k₁, t₁⟩ | ⟨e₁, k₁, t₁, c₁⟩ <;>
    rcases h₂ with h₂ | ⟨e₂, k₂⟩ | ⟨e₂, k₂, t₂⟩ | ⟨e₂, k₂, t₂, c₂⟩
  all_goals first
    | exact .inl (by omega)
    | exact .inr (.inl ⟨by omega, by omega⟩)
    | skip
  · exact .inr (.inr (.inl ⟨by omega, by omega, Multiset.IsDershowitzMannaLT.trans t₁ t₂⟩))
  · exact .inr (.inr (.inl ⟨by omega, by omega, t₂ ▸ t₁⟩))
  · exact .inr (.inr (.inl ⟨by omega, by omega, t₁ ▸ t₂⟩))
  · exact .inr (.inr (.inr ⟨by omega, by omega, t₁.trans t₂,
      Multiset.IsDershowitzMannaLT.trans c₁ c₂⟩))

theorem MeasureLt.irrefl (P : List Term) : ¬ MeasureLt sig P P := by
  rintro (h | ⟨-, h⟩ | ⟨-, -, h⟩ | ⟨-, -, -, h⟩)
  · exact lt_irrefl _ h
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
  have hK : others sig Q = others sig P := by
    have hE : (E.map (subst sig (ser sig (.node o args)) (.node o' args'))).countP
        (fun t => !isNotTerm sig t) = E.countP (fun t => !isNotTerm sig t) := by
      rw [List.countP_map]
      exact List.countP_congr fun a _ => by simp [isNotTerm_subst hsv hv'n a]
    unfold others
    rw [hQ'.countP_eq, hP'.countP_eq, List.countP_cons, List.countP_cons, hE]
    simp [isNotTerm, hnot, hnot']
  rcases hkey with hk | ⟨hk, hargs⟩
  · right
    right
    left
    refine ⟨by omega, hK, ?_⟩
    rw [hTQ, hTP]
    exact dm_single _ hk
  · right
    right
    right
    refine ⟨by omega, hK, by rw [hTQ, hTP, hk], ?_⟩
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

theorem isNotTerm_subst_of_isNot {sv : List ℕ} {v' : Term} (hv' : isNotTerm sig v' = true)
    {a : Term} (ha : isNotTerm sig a = true) : isNotTerm sig (subst sig sv v' a) = true := by
  by_cases h : ser sig a = sv
  · rw [subst_of_ser h]
    exact hv'
  · cases a with
    | leaf i => simp [isNotTerm] at ha
    | node o args =>
      rw [subst_node_of_ne h]
      exact ha

/-- Lemma 9: an opposite value lowers the measure of the statements' terms. P
is v's statement and the others, E; the result is `not w` (v') and some of
the others, with v's term replaced by v''s. -/
theorem opposite_measure {P Q E rest : List Term} {v v' : Term} (hP : List.Perm P (v :: E))
    (hnot : isNotTerm sig v = false) (hv' : isNotTerm sig v' = true)
    (hQ : List.Perm Q (v' :: rest)) (hrest : List.Subperm rest (E.map (subst sig (ser sig v) v'))) :
    MeasureLt sig Q P := by
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
  right
  left
  refine ⟨by omega, ?_⟩
  have hle : E.countP ((fun t => !isNotTerm sig t) ∘ subst sig (ser sig v) v') ≤
      E.countP (fun t => !isNotTerm sig t) := by
    refine List.countP_mono_left fun a _ h => ?_
    cases ha : isNotTerm sig a
    · rfl
    · simp [isNotTerm_subst_of_isNot hv' ha] at h
  unfold others
  rw [hQ'.countP_eq, hP.countP_eq, List.countP_cons, List.countP_cons, List.countP_map]
  simp only [hnot, hv', Bool.not_true, Bool.not_false, Bool.false_eq_true, if_false, if_true]
  omega

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
  /-- A redundant value v that's the same as w: reading w instead makes v's
  statement dead, and every other statement keeps its functions. -/
  | redundant {P Q : List Stmt} (v : Stmt) (hv : v ∈ P) (rw : Term → Term)
      (hQ : List.Subperm Q ((P.erase v).map (keepConst rw))) : OpFix P Q
  /-- Removing dead statements: v's, and maybe others; every statement left
  is unchanged. -/
  | dead {P Q : List Stmt} (v : Stmt) (hv : v ∈ P) (hQ : List.Subperm Q (P.erase v)) : OpFix P Q
  /-- A redundant value v that's the opposite of w, and isn't a `not`: v's
  statement becomes `not w` (`o` is `not`), with the same functions, and
  every other statement has v's term replaced by `not w`'s. -/
  | opposite {P Q : List Stmt} (v w : Term) (o c : ℕ) (rest : List Stmt) (hv : (v, c) ∈ P)
      (hnot : isNotTerm sig v = false) (ho : sig.isNot o = true)
      (hQ : List.Perm Q ((.node o [w], c) :: rest))
      (hrest : List.Subperm rest
        ((P.erase (v, c)).map (keepConst (subst sig (ser sig v) (.node o [w]))))) :
      OpFix P Q
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
  | dead v hv hQ =>
    rw [constCount_erase hv]
    have := constCount_subperm hQ
    omega
  | opposite v w o c rest hv _ _ hQ hrest =>
    rw [constCount_perm hQ, constCount_cons, constCount_erase hv]
    have := (constCount_subperm hrest).trans (constCount_map_keepConst _ _).le
    simp only at this ⊢
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
  | dead v hv hQ =>
    left
    have h1 := hQ.length_le
    have h2 := List.length_erase_of_mem hv
    have h3 := List.length_pos_of_mem hv
    simp only [List.length_map]
    omega
  | opposite v w o c rest hv hnot ho hQ hrest =>
    refine opposite_measure (E := (P.erase (v, c)).map Prod.fst) (rest := rest.map Prod.fst)
      ?_ hnot (show isNotTerm sig (.node o [w]) = true from ho) (by simpa using hQ.map Prod.fst) ?_
    · simpa using (List.perm_cons_erase hv).map Prod.fst
    · obtain ⟨l, hl, hsub⟩ := hrest
      refine ⟨l.map Prod.fst, hl.map _, ?_⟩
      simpa [keepConst, List.map_map, Function.comp_def] using hsub.map Prod.fst
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
  rcases hm with hl | ⟨hl, -⟩ | ⟨hl, -⟩ | ⟨hl, -⟩ <;> simp only [List.length_map] at hl <;> omega

/-! ### A program -/

/-- A value operation: its boolean statements, and its numbers of written and
read views. -/
structure OpState where
  stmts : List Stmt
  views : ℕ
  reads : ℕ

/-- A program of `n` value operations; `none` is one that was removed. -/
abbrev Program (n : ℕ) := Fin n → Option OpState

/-- C plus the number of written views. -/
def weight : Option OpState → ℕ
  | none => 0
  | some A => constCount A.stmts + A.views

/-- Φ. -/
def phi {n : ℕ} (p : Program n) : ℕ := ∑ a, weight (p a)

/-- The number of read views, or 0 for a removed value operation. -/
def readCount : Option OpState → ℕ
  | none => 0
  | some A => A.reads

/-- V: the read views of every value operation. -/
def vsum {n : ℕ} (p : Program n) : ℕ := ∑ a, readCount (p a)

variable (sig) in
/-- One value operation's state below another: removed is below every value
operation, and otherwise, the same written and read views and a lower
measure. -/
def OptLt : Option OpState → Option OpState → Prop
  | none, some _ => True
  | some A', some A => A'.views = A.views ∧ A'.reads = A.reads ∧ OpLt sig A'.stmts A.stmts
  | _, none => False

theorem OptLt.trans {x y z : Option OpState} (h₁ : OptLt sig x y) (h₂ : OptLt sig y z) :
    OptLt sig x z := by
  match x, y, z, h₁, h₂ with
  | none, some _, some _, _, _ => trivial
  | some _, some _, some _, ⟨e₁, r₁, m₁⟩, ⟨e₂, r₂, m₂⟩ => exact ⟨e₁.trans e₂, r₁.trans r₂, m₁.trans m₂⟩

theorem OptLt.irrefl (x : Option OpState) : ¬ OptLt sig x x := by
  match x with
  | none => exact id
  | some A => exact fun h => OpLt.irrefl A.stmts h.2.2

variable (sig) in
/-- Programs, ordered by V, then Φ, and then pointwise. -/
def ProgLt {n : ℕ} (q p : Program n) : Prop :=
  vsum q < vsum p ∨ (vsum q = vsum p ∧ phi q < phi p) ∨
    (vsum q = vsum p ∧ phi q = phi p ∧ (∀ a, q a = p a ∨ OptLt sig (q a) (p a)) ∧
      ∃ a, OptLt sig (q a) (p a))

theorem ProgLt.trans {n : ℕ} {r q p : Program n} (h₁ : ProgLt sig r q) (h₂ : ProgLt sig q p) :
    ProgLt sig r p := by
  rcases h₁ with h₁ | ⟨v₁, h₁⟩ | ⟨v₁, e₁, le₁, ⟨a, lt₁⟩⟩ <;>
    rcases h₂ with h₂ | ⟨v₂, h₂⟩ | ⟨v₂, e₂, le₂, -⟩
  all_goals first
    | exact .inl (by omega)
    | exact .inr (.inl ⟨by omega, by omega⟩)
    | skip
  refine .inr (.inr ⟨by omega, by omega, fun b => ?_, ⟨a, ?_⟩⟩)
  · rcases le₁ b with h | h <;> rcases le₂ b with h' | h'
    · exact .inl (h.trans h')
    · exact .inr (h ▸ h')
    · exact .inr (h' ▸ h)
    · exact .inr (h.trans h')
  · rcases le₂ a with h' | h'
    · exact h' ▸ lt₁
    · exact lt₁.trans h'

theorem ProgLt.irrefl {n : ℕ} (p : Program n) : ¬ ProgLt sig p p := by
  rintro (h | ⟨-, h⟩ | ⟨-, -, -, ⟨a, h⟩⟩)
  · exact lt_irrefl _ h
  · exact lt_irrefl _ h
  · exact OptLt.irrefl _ h

variable (sig) in
/-- The fixes of a program. -/
inductive ProgStep {n : ℕ} : Program n → Program n → Prop
  /-- A fix inside value operation `a`, which keeps its written and read
  views; the others don't change. -/
  | local {p q : Program n} (a : Fin n) (A A' : OpState) (ha : p a = some A) (hqa : q a = some A')
      (hfix : OpFix sig A.stmts A'.stmts) (hviews : A'.views = A.views) (hreads : A'.reads = A.reads)
      (hrest : ∀ b, b ≠ a → q b = p b) : ProgStep p q
  /-- Removing a constant written view of `a` (Lemma 8): `a` has one fewer
  written view, no more read views, and no more constant values, or it's
  removed if that was its only one; every value operation in `callers`
  executes it, keeps its written and read views, and has fewer constant
  values; the others don't change. -/
  | dropView {p q : Program n} (a : Fin n) (A : OpState) (ha : p a = some A)
      (hcallee : (q a = none ∧ A.views = 1) ∨
        ∃ A', q a = some A' ∧ A'.views + 1 = A.views ∧ A'.reads ≤ A.reads ∧
          constCount A'.stmts ≤ constCount A.stmts)
      (callers : Finset (Fin n)) (hnot : a ∉ callers)
      (hcallers : ∀ b ∈ callers, ∃ B B', p b = some B ∧ q b = some B' ∧ B'.views = B.views ∧
        B'.reads = B.reads ∧ constCount B'.stmts < constCount B.stmts)
      (hrest : ∀ b, b ≠ a → b ∉ callers → q b = p b) : ProgStep p q
  /-- Removing a read view of `a` that doesn't matter (Lemma 10): `a` has one
  fewer read view and the same written views, and any statements, since its
  reads are given another read view; every value operation in `callers`
  executes it, keeps its written and read views, and has no more constant
  values (it only loses statements left dead); the others don't change. -/
  | dropRead {p q : Program n} (a : Fin n) (A A' : OpState) (ha : p a = some A) (hqa : q a = some A')
      (hreads : A'.reads + 1 = A.reads) (hviews : A'.views = A.views)
      (callers : Finset (Fin n)) (hnot : a ∉ callers)
      (hcallers : ∀ b ∈ callers, ∃ B B', p b = some B ∧ q b = some B' ∧ B'.views = B.views ∧
        B'.reads = B.reads ∧ constCount B'.stmts ≤ constCount B.stmts)
      (hrest : ∀ b, b ≠ a → b ∉ callers → q b = p b) : ProgStep p q

theorem weight_local {A A' : OpState} (hviews : A'.views = A.views) (_hreads : A'.reads = A.reads) :
    weight (some A') + constCount A.stmts = weight (some A) + constCount A'.stmts := by
  simp only [weight, hviews]
  omega

theorem local_phi_le {n : ℕ} {p q : Program n} {a : Fin n} {A A' : OpState} (ha : p a = some A)
    (hqa : q a = some A') (hviews : A'.views = A.views) (hreads : A'.reads = A.reads)
    (hC : constCount A'.stmts ≤ constCount A.stmts) (hrest : ∀ b, b ≠ a → q b = p b) :
    ∀ b ∈ Finset.univ, weight (q b) ≤ weight (p b) := by
  intro b _
  by_cases hb : b = a
  · subst hb
    rw [ha, hqa]
    have := weight_local hviews hreads
    omega
  · rw [hrest b hb]

theorem local_phi_lt {n : ℕ} {p q : Program n} {a : Fin n} {A A' : OpState} (ha : p a = some A)
    (hqa : q a = some A') (hviews : A'.views = A.views) (hreads : A'.reads = A.reads)
    (hC : constCount A'.stmts < constCount A.stmts) (hrest : ∀ b, b ≠ a → q b = p b) :
    phi q < phi p := by
  refine Finset.sum_lt_sum (local_phi_le ha hqa hviews hreads hC.le hrest) ⟨a, Finset.mem_univ _, ?_⟩
  rw [ha, hqa]
  have := weight_local hviews hreads
  omega

theorem dropView_phi_lt {n : ℕ} {p q : Program n} {a : Fin n} {A : OpState} (ha : p a = some A)
    (hcallee : (q a = none ∧ A.views = 1) ∨
      ∃ A', q a = some A' ∧ A'.views + 1 = A.views ∧ A'.reads ≤ A.reads ∧
        constCount A'.stmts ≤ constCount A.stmts)
    {callers : Finset (Fin n)}
    (hcallers : ∀ b ∈ callers, ∃ B B', p b = some B ∧ q b = some B' ∧ B'.views = B.views ∧
      B'.reads = B.reads ∧ constCount B'.stmts < constCount B.stmts)
    (hrest : ∀ b, b ≠ a → b ∉ callers → q b = p b) : phi q < phi p := by
  classical
  have hle : ∀ b ∈ Finset.univ, weight (q b) ≤ weight (p b) := by
    intro b _
    by_cases hb : b = a
    · subst hb
      rw [ha]
      rcases hcallee with ⟨hq, -⟩ | ⟨A', hq, hv, hr, hc⟩
      · rw [hq]
        exact Nat.zero_le _
      · rw [hq]
        simp only [weight]
        omega
    · by_cases hc : b ∈ callers
      · obtain ⟨B, B', hp, hq, hv, -, hlt⟩ := hcallers b hc
        rw [hp, hq]
        simp only [weight, hv]
        omega
      · rw [hrest b hb hc]
  refine Finset.sum_lt_sum hle ⟨a, Finset.mem_univ _, ?_⟩
  rw [ha]
  rcases hcallee with ⟨hq, hv⟩ | ⟨A', hq, hv, hr, hc⟩
  · rw [hq]
    simp only [weight]
    omega
  · rw [hq]
    simp only [weight]
    omega

/-- A fix inside one value operation keeps V. -/
theorem local_vsum_eq {n : ℕ} {p q : Program n} {a : Fin n} {A A' : OpState} (ha : p a = some A)
    (hqa : q a = some A') (hreads : A'.reads = A.reads) (hrest : ∀ b, b ≠ a → q b = p b) :
    vsum q = vsum p := by
  refine Finset.sum_congr rfl fun b _ => ?_
  by_cases hb : b = a
  · subst hb
    rw [ha, hqa]
    simp only [readCount, hreads]
  · rw [hrest b hb]

/-- Removing a constant written view doesn't raise V. -/
theorem dropView_vsum_le {n : ℕ} {p q : Program n} {a : Fin n} {A : OpState} (ha : p a = some A)
    (hcallee : (q a = none ∧ A.views = 1) ∨
      ∃ A', q a = some A' ∧ A'.views + 1 = A.views ∧ A'.reads ≤ A.reads ∧
        constCount A'.stmts ≤ constCount A.stmts)
    {callers : Finset (Fin n)}
    (hcallers : ∀ b ∈ callers, ∃ B B', p b = some B ∧ q b = some B' ∧ B'.views = B.views ∧
      B'.reads = B.reads ∧ constCount B'.stmts < constCount B.stmts)
    (hrest : ∀ b, b ≠ a → b ∉ callers → q b = p b) : vsum q ≤ vsum p := by
  classical
  refine Finset.sum_le_sum fun b _ => ?_
  by_cases hb : b = a
  · subst hb
    rw [ha]
    rcases hcallee with ⟨hq, -⟩ | ⟨A', hq, -, hr, -⟩
    · rw [hq]
      exact Nat.zero_le _
    · rw [hq]
      exact hr
  · by_cases hc : b ∈ callers
    · obtain ⟨B, B', hp, hq, -, hr, -⟩ := hcallers b hc
      rw [hp, hq]
      simp only [readCount, hr, le_refl]
    · rw [hrest b hb hc]

/-- Lemma 10: removing a read view that doesn't matter lowers V. -/
theorem dropRead_vsum_lt {n : ℕ} {p q : Program n} {a : Fin n} {A A' : OpState} (ha : p a = some A)
    (hqa : q a = some A') (hreads : A'.reads + 1 = A.reads) {callers : Finset (Fin n)}
    (hcallers : ∀ b ∈ callers, ∃ B B', p b = some B ∧ q b = some B' ∧ B'.views = B.views ∧
      B'.reads = B.reads ∧ constCount B'.stmts ≤ constCount B.stmts)
    (hrest : ∀ b, b ≠ a → b ∉ callers → q b = p b) : vsum q < vsum p := by
  classical
  have hle : ∀ b ∈ Finset.univ, readCount (q b) ≤ readCount (p b) := by
    intro b _
    by_cases hb : b = a
    · subst hb
      rw [ha, hqa]
      simp only [readCount]
      omega
    · by_cases hc : b ∈ callers
      · obtain ⟨B, B', hp, hq, -, hr, -⟩ := hcallers b hc
        rw [hp, hq]
        simp only [readCount, hr, le_refl]
      · rw [hrest b hb hc]
  refine Finset.sum_lt_sum hle ⟨a, Finset.mem_univ _, ?_⟩
  rw [ha, hqa]
  simp only [readCount]
  omega

/-- Theorem 2: every fix of a program lowers it. -/
theorem progStep_lt {n : ℕ} {p q : Program n} (h : ProgStep sig p q) : ProgLt sig q p := by
  cases h with
  | «local» a A A' ha hqa hfix hviews hreads hrest =>
    have hv := local_vsum_eq ha hqa hreads hrest
    rcases Nat.lt_or_eq_of_le (opFix_constCount_le hfix) with hC | hC
    · exact .inr (.inl ⟨hv, local_phi_lt ha hqa hviews hreads hC hrest⟩)
    · right
      right
      refine ⟨hv, Finset.sum_congr rfl fun b _ => ?_, fun b => ?_, ⟨a, ?_⟩⟩
      · by_cases hb : b = a
        · subst hb
          rw [ha, hqa]
          have := weight_local hviews hreads
          omega
        · rw [hrest b hb]
      · by_cases hb : b = a
        · subst hb
          rw [ha, hqa]
          exact .inr ⟨hviews, hreads, opFix_lt hfix⟩
        · exact .inl (hrest b hb)
      · rw [ha, hqa]
        exact ⟨hviews, hreads, opFix_lt hfix⟩
  | dropView a A ha hcallee callers hnot hcallers hrest =>
    rcases Nat.lt_or_eq_of_le (dropView_vsum_le ha hcallee hcallers hrest) with hv | hv
    · exact .inl hv
    · exact .inr (.inl ⟨hv, dropView_phi_lt ha hcallee hcallers hrest⟩)
  | dropRead a A A' ha hqa hreads hviews callers hnot hcallers hrest =>
    exact .inl (dropRead_vsum_lt ha hqa hreads hcallers hrest)

/-- The number of statements of a value operation, or 0 if it was removed. -/
def size : Option OpState → ℕ
  | none => 0
  | some A => A.stmts.length

/-- A fix that keeps Φ adds no statement anywhere. -/
theorem progStep_size_le {n : ℕ} {p q : Program n} (h : ProgStep sig p q) (hv : vsum q = vsum p)
    (hphi : phi q = phi p) (b : Fin n) : size (q b) ≤ size (p b) := by
  cases h with
  | «local» a A A' ha hqa hfix hviews hreads hrest =>
    by_cases hb : b = a
    · subst hb
      rw [ha, hqa]
      simp only [size]
      rcases Nat.lt_or_eq_of_le (opFix_constCount_le hfix) with hC | hC
      · exact absurd hphi (ne_of_lt (local_phi_lt ha hqa hviews hreads hC hrest))
      · exact opFix_length_le hfix hC
    · rw [hrest b hb]
  | dropView a A ha hcallee callers hnot hcallers hrest =>
    exact absurd hphi (ne_of_lt (dropView_phi_lt ha hcallee hcallers hrest))
  | dropRead a A A' ha hqa hreads hviews callers hnot hcallers hrest =>
    exact absurd hv (ne_of_lt (dropRead_vsum_lt ha hqa hreads hcallers hrest))

/-! ### Writing out an execution that would make a cycle -/

variable (sig) in
/-- The fixes of a program, with value operations given a priority `rank`:
every unregistered value operation has 0, and registered ones come after,
the last one listed in booleans.defcl first. Besides the fixes of
`ProgStep`, a match or spelling in `a` whose execution of the registered
operation `r` would make an execution cycle first writes out, in `r`'s
definition, the executions that lead back to `a`: `a` gets the fix, and `r`
gets any statements, with the same written and read views and no more
constant values. `r` comes after `a` in priority: a registered `a` follows
`r`, so `r` is listed before it, and an unregistered `a` comes before every
registered operation. -/
inductive ProgFix {n : ℕ} (rank : Fin n → ℕ) : Program n → Program n → Prop
  | step {p q : Program n} (h : ProgStep sig p q) : ProgFix rank p q
  | writeOut {p q : Program n} (a r : Fin n) (hrank : rank a < rank r) (A A' R R' : OpState)
      (ha : p a = some A) (hqa : q a = some A') (hfix : OpFix sig A.stmts A'.stmts)
      (hviews : A'.views = A.views) (hreads : A'.reads = A.reads)
      (hr : p r = some R) (hqr : q r = some R') (hRviews : R'.views = R.views)
      (hRreads : R'.reads = R.reads) (hRC : constCount R'.stmts ≤ constCount R.stmts)
      (hrest : ∀ b, b ≠ a → b ≠ r → q b = p b) : ProgFix rank p q

theorem writeOut_weight_le {n : ℕ} {p q : Program n} {a r : Fin n} {A A' R R' : OpState}
    (ha : p a = some A) (hqa : q a = some A') (hfix : OpFix sig A.stmts A'.stmts)
    (hviews : A'.views = A.views) (_hreads : A'.reads = A.reads)
    (hr : p r = some R) (hqr : q r = some R') (hRviews : R'.views = R.views)
    (_hRreads : R'.reads = R.reads) (hRC : constCount R'.stmts ≤ constCount R.stmts)
    (hrest : ∀ b, b ≠ a → b ≠ r → q b = p b) : ∀ b ∈ Finset.univ, weight (q b) ≤ weight (p b) := by
  intro b _
  by_cases hb : b = a
  · subst hb
    rw [ha, hqa]
    have := opFix_constCount_le hfix
    simp only [weight, hviews]
    omega
  · by_cases hbr : b = r
    · subst hbr
      rw [hr, hqr]
      simp only [weight, hRviews]
      omega
    · rw [hrest b hb hbr]

/-- No fix raises V. -/
theorem progFix_vsum_le {n : ℕ} {rank : Fin n → ℕ} {p q : Program n} (h : ProgFix sig rank p q) :
    vsum q ≤ vsum p := by
  cases h with
  | step h => rcases progStep_lt h with h | ⟨h, -⟩ | ⟨h, -⟩ <;> omega
  | writeOut a r _ A A' R R' ha hqa hfix hviews hreads hr hqr hRviews hRreads hRC hrest =>
    refine Finset.sum_le_sum fun b _ => ?_
    by_cases hb : b = a
    · subst hb
      rw [ha, hqa]
      simp only [readCount, hreads, le_refl]
    · by_cases hbr : b = r
      · subst hbr
        rw [hr, hqr]
        simp only [readCount, hRreads, le_refl]
      · rw [hrest b hb hbr]

/-- No fix that keeps V raises Φ. -/
theorem progFix_phi_le {n : ℕ} {rank : Fin n → ℕ} {p q : Program n} (h : ProgFix sig rank p q)
    (hv : vsum q = vsum p) : phi q ≤ phi p := by
  cases h with
  | step h => rcases progStep_lt h with h | ⟨-, h⟩ | ⟨-, h, -⟩ <;> omega
  | writeOut a r _ A A' R R' ha hqa hfix hviews hreads hr hqr hRviews hRreads hRC hrest =>
    exact Finset.sum_le_sum
      (writeOut_weight_le ha hqa hfix hviews hreads hr hqr hRviews hRreads hRC hrest)

theorem opFix_ne {A A' : OpState} (hfix : OpFix sig A.stmts A'.stmts) : A' ≠ A := by
  rintro rfl
  exact OpLt.irrefl _ (opFix_lt hfix)

/-- Every fix changes the program. -/
theorem progFix_ne {n : ℕ} {rank : Fin n → ℕ} {p q : Program n} (h : ProgFix sig rank p q) :
    q ≠ p := by
  cases h with
  | step h =>
    rintro rfl
    exact ProgLt.irrefl _ (progStep_lt h)
  | writeOut a r _ A A' R R' ha hqa hfix _ _ _ _ _ _ _ _ =>
    intro he
    have := congrFun he a
    rw [ha, hqa] at this
    exact opFix_ne hfix (Option.some.inj this)

/-- Once V and Φ stop going down, a value operation that a fix changes either
gets the fix, which lowers its measure and adds no statement, or has its
definition written out for a fix of a value operation before it in
priority, which changes too. -/
theorem progFix_change {n : ℕ} {rank : Fin n → ℕ} {p q : Program n} (h : ProgFix sig rank p q)
    (hv : vsum q = vsum p) (hphi : phi q = phi p) (b : Fin n) (hb : q b ≠ p b) :
    (OptLt sig (q b) (p b) ∧ size (q b) ≤ size (p b)) ∨ ∃ a, rank a < rank b ∧ q a ≠ p a := by
  cases h with
  | step h =>
    left
    refine ⟨?_, progStep_size_le h hv hphi b⟩
    rcases progStep_lt h with hlt | ⟨-, hlt⟩ | ⟨-, -, hle, -⟩
    · omega
    · omega
    · exact (hle b).resolve_left hb
  | writeOut a r hrank A A' R R' ha hqa hfix hviews hreads hr hqr hRviews hRreads hRC hrest =>
    have hle := writeOut_weight_le ha hqa hfix hviews hreads hr hqr hRviews hRreads hRC hrest
    have heq := (Finset.sum_eq_sum_iff_of_le hle).1 hphi
    by_cases hba : b = a
    · subst hba
      left
      rw [ha, hqa]
      refine ⟨⟨hviews, hreads, opFix_lt hfix⟩, ?_⟩
      have hw := heq b (Finset.mem_univ _)
      rw [ha, hqa] at hw
      simp only [weight, hviews] at hw
      exact opFix_length_le hfix (by omega)
    · by_cases hbr : b = r
      · subst hbr
        right
        refine ⟨a, hrank, ?_⟩
        rw [ha, hqa]
        exact fun he => opFix_ne hfix (Option.some.inj he)
      · exact absurd (hrest b hba hbr) hb

/-- A sequence of states, each the one before or below it, within a finite
set, stops changing. -/
theorem stabilizes {g : ℕ → Option OpState} (S : Set (Option OpState)) (hS : S.Finite)
    (hmem : ∀ k, g k ∈ S) (hstep : ∀ k, g (k + 1) = g k ∨ OptLt sig (g (k + 1)) (g k)) :
    ∃ K, ∀ k, K ≤ k → g (k + 1) = g k := by
  haveI : IsStrictOrder (Option OpState) (OptLt sig) :=
    { irrefl := OptLt.irrefl, trans := fun _ _ _ => OptLt.trans }
  have wf := Set.wellFoundedOn_iff.1 (hS.wellFoundedOn (r := OptLt sig))
  obtain ⟨_, ⟨K, rfl⟩, hmin⟩ := wf.has_min (Set.range g) ⟨g 0, 0, rfl⟩
  have hK : ∀ k, K ≤ k → g k = g K := by
    intro k hk
    induction k, hk using Nat.le_induction with
    | base => rfl
    | succ k _ ih =>
      rcases hstep k with h | h
      · exact h.trans ih
      · rw [ih] at h
        exact absurd ⟨h, hmem _, hmem _⟩ (hmin _ ⟨k + 1, rfl⟩)
  exact ⟨K, fun k hk => (hK (k + 1) (by omega)).trans (hK k hk).symm⟩

/-- A sequence of numbers that never goes up from K on is constant from
some K' ≥ K on. -/
theorem eventually_const (u : ℕ → ℕ) (K : ℕ) (h : ∀ k, K ≤ k → u (k + 1) ≤ u k) :
    ∃ K', K ≤ K' ∧ ∀ k, K' ≤ k → u (k + 1) = u k := by
  classical
  have hex : ∃ m, ∃ k, K ≤ k ∧ u k = m := ⟨u K, K, le_rfl, rfl⟩
  obtain ⟨K', hK', hm⟩ := Nat.find_spec hex
  have hmin : ∀ k, K ≤ k → u K' ≤ u k := fun k hk => hm ▸ Nat.find_min' hex ⟨k, hk, rfl⟩
  have hmono : ∀ i j, K ≤ i → i ≤ j → u j ≤ u i := by
    intro i j hi hij
    induction hij with
    | refl => exact le_rfl
    | step hij ih => exact (h _ (le_trans hi hij)).trans ih
  exact ⟨K', hK', fun k hk => le_antisymm (h k (le_trans hK' hk))
    ((hmono K' k hK' hk).trans (hmin (k + 1) (by omega)))⟩

/-- Fixing a program terminates. V and then Φ stop going down; after that, by
induction on priority, each value operation stops changing once the ones
before it have: it then changes only by its own fixes, which lower its
measure and add no statement, among finitely many states. Then nothing
changes, but every fix changes something. -/
theorem prog_terminates {n : ℕ} (rank : Fin n → ℕ) (f : ℕ → Program n)
    (hstep : ∀ k, ProgFix sig rank (f k) (f (k + 1)))
    (hfin : ∀ (a : Fin n) (bound : ℕ), {A | (∃ k, f k a = A) ∧ size A ≤ bound}.Finite) : False := by
  -- V is constant from some k₀ on, and then Φ from some k₁ on.
  obtain ⟨k₀, -, hvc⟩ := eventually_const (fun k => vsum (f k)) 0
    (fun k _ => progFix_vsum_le (hstep k))
  obtain ⟨k₁, hk₁, hconst⟩ := eventually_const (fun k => phi (f k)) k₀
    (fun k hk => progFix_phi_le (hstep k) (hvc k hk))
  have key : ∀ j, ∃ K, k₁ ≤ K ∧ ∀ k, K ≤ k → ∀ b, rank b < j → f (k + 1) b = f k b := by
    intro j
    induction j with
    | zero => exact ⟨k₁, le_rfl, fun _ _ _ hb => absurd hb (Nat.not_lt_zero _)⟩
    | succ j ih =>
      obtain ⟨K, hK₀, hK⟩ := ih
      have one : ∀ b, ∃ Kb, K ≤ Kb ∧ (rank b = j → ∀ k, Kb ≤ k → f (k + 1) b = f k b) := by
        intro b
        by_cases hbj : rank b = j
        · let g : ℕ → Option OpState := fun k => f (K + k) b
          have hg : ∀ k, g (k + 1) = g k ∨
              (OptLt sig (g (k + 1)) (g k) ∧ size (g (k + 1)) ≤ size (g k)) := by
            intro k
            by_cases he : f (K + k + 1) b = f (K + k) b
            · exact .inl he
            · right
              rcases progFix_change (hstep (K + k)) (hvc _ (by omega)) (hconst _ (by omega)) b he
                with h | ⟨a, ha, hne⟩
              · exact h
              · exact absurd (hK (K + k) (by omega) a (hbj ▸ ha)) hne
          have hsize : ∀ k, size (g k) ≤ size (g 0) := by
            intro k
            induction k with
            | zero => exact le_rfl
            | succ k ih =>
              rcases hg k with h | h
              · rw [h]
                exact ih
              · exact h.2.trans ih
          obtain ⟨K', hK'⟩ := stabilizes (sig := sig) {A | (∃ k, f k b = A) ∧ size A ≤ size (g 0)}
            (hfin b _) (fun k => ⟨⟨K + k, rfl⟩, hsize k⟩) (fun k => (hg k).imp id And.left)
          refine ⟨K + K', by omega, fun _ k hk => ?_⟩
          have h := hK' (k - K) (by omega)
          have e1 : K + (k - K + 1) = k + 1 := by omega
          have e2 : K + (k - K) = k := by omega
          simp only [e1, e2] at h
          exact h
        · exact ⟨K, le_rfl, fun h => absurd h hbj⟩
      classical
      choose Kb hKb using one
      refine ⟨max K (Finset.univ.sup Kb), le_trans hK₀ (le_max_left _ _), fun k hk b hb => ?_⟩
      rcases Nat.lt_succ_iff_lt_or_eq.1 hb with hb | hb
      · exact hK k (le_trans (le_max_left _ _) hk) b hb
      · exact (hKb b).2 hb k
          (le_trans (Finset.le_sup (f := Kb) (Finset.mem_univ b)) (le_trans (le_max_right _ _) hk))
  obtain ⟨K, -, hK⟩ := key (Finset.univ.sup rank + 1)
  exact progFix_ne (hstep K) (funext fun b =>
    hK K le_rfl b (Nat.lt_succ_of_le (Finset.le_sup (f := rank) (Finset.mem_univ b))))

/-- A sequence of one or more steps, as a finite sequence. -/
theorem transGen_seq {α : Type} {r : α → α → Prop} {a c : α} (h : Relation.TransGen r a c) :
    ∃ (m : ℕ) (s : ℕ → α), s 0 = a ∧ s (m + 1) = c ∧ ∀ i ≤ m, r (s i) (s (i + 1)) := by
  classical
  induction h with
  | @single b h =>
    refine ⟨0, fun i => if i = 0 then a else b, by simp, by simp, fun i hi => ?_⟩
    obtain rfl : i = 0 := by omega
    simpa using h
  | @tail b c _ hbc ih =>
    obtain ⟨m, s, h0, hm, hs⟩ := ih
    refine ⟨m + 1, fun i => if i ≤ m + 1 then s i else c, by simp [h0], by simp, fun i hi => ?_⟩
    rcases Nat.lt_or_eq_of_le hi with hi | rfl
    · simp only [if_pos (show i ≤ m + 1 by omega), if_pos (show i + 1 ≤ m + 1 by omega)]
      exact hs i (by omega)
    · simp only [le_refl, if_pos, if_neg (show ¬ m + 1 + 1 ≤ m + 1 by omega), hm]
      exact hbc

/-- Fixing a program never returns to a program it has left: going around
the cycle forever would be an infinite sequence of fixes among finitely
many programs. -/
theorem prog_no_cycle {n : ℕ} (rank : Fin n → ℕ) {p : Program n}
    (h : Relation.TransGen (ProgFix sig rank) p p) : False := by
  obtain ⟨m, s, h0, hm, hs⟩ := transGen_seq h
  have hmod : ∀ k, (k + 1) % (m + 1) = if k % (m + 1) = m then 0 else k % (m + 1) + 1 := by
    intro k
    have hlt := Nat.mod_lt k (by omega : 0 < m + 1)
    conv_lhs => rw [← Nat.div_add_mod k (m + 1), Nat.add_assoc, Nat.mul_add_mod]
    split_ifs with he
    · rw [he, Nat.mod_self]
    · exact Nat.mod_eq_of_lt (by omega)
  refine prog_terminates (sig := sig) rank (fun k => s (k % (m + 1))) (fun k => ?_) (fun a bound => ?_)
  · show ProgFix sig rank (s (k % (m + 1))) (s ((k + 1) % (m + 1)))
    rw [hmod k]
    split_ifs with he
    · rw [he]
      have := hs m le_rfl
      rwa [hm, ← h0] at this
    · exact hs _ (by have := Nat.mod_lt k (by omega : 0 < m + 1); omega)
  · refine (Set.finite_range (fun i : Fin (m + 1) => s i a)).subset ?_
    rintro A ⟨⟨k, rfl⟩, -⟩
    exact ⟨⟨k % (m + 1), Nat.mod_lt _ (by omega : 0 < m + 1)⟩, rfl⟩

end Define.BooleanEqualityChecking.Termination
