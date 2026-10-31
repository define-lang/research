import Mathlib.Data.Fintype.Card
import Mathlib.Data.Fintype.Pi
import Mathlib.Data.Set.Card
import Mathlib.Data.Fintype.EquivFin
import Mathlib.Data.Set.Finite.Range
import Mathlib.Tactic.Linarith
import Mathlib.Algebra.Order.BigOperators.Group.Finset

set_option warningAsError true
set_option autoImplicit false

/-!
# SDDs from relational tree decompositions

This file formalizes Theorem 5.1 of `circuit-treewidth-sdd-proof.md` and a
variant of Lemma 6.1.

- `Define.CircuitTreewidthSdd.sdd_of_rtd` (Theorem 5.1): a relational tree
  decomposition (RTD) whose root's right child is a leaf (S1) and which
  satisfies (S2) at every internal right child has an SDD, respecting its
  vtree, that computes its function, with at most (number of internal
  nodes)·4^b distinct decision nodes of at most 4^b elements each when every
  bag has at most b vertices.
- `Define.CircuitTreewidthSdd.sdd_of_vtree_rtd` (Theorem 5.1 with Lemma 6.1):
  every RTD on a vtree with bags of at most b vertices has an SDD over its
  inputs, respecting a vtree over the same inputs, of size at most (number of
  internal nodes)·16^(3b+2). The leaf donation here merges each cherry's bag
  into its parent's instead of projecting it (Step 1 of Lemma 6.1), which
  gives bags of at most 3b + 2 vertices instead of b + 6.

Differences from the English text:

- Vertices are Boolean. (The English text allows finite domains, which only
  Corollary 1.3 uses.)
- `DTree.WF` states the separation properties of Lemma 3.2 directly, for every
  internal node, instead of the connectivity condition (C) from which Lemma 3.2
  derives them; together with the fact that relations depend only on their
  bags, these are all the uses of (C).
- Valuations are total functions `U → Bool`; a valuation of a set S is any
  function, read only on S.
- SDDs are terms (`Sdd`); a node shared in the SDD appears as equal subterms,
  and `Sdd.decNodes` is the set of distinct decision subterms, whose number of
  elements, summed, is the size of the shared SDD.
- Pair cells and joins are unified as `G t S π`, with S the bag or the
  interface.
-/

namespace Define.CircuitTreewidthSdd

variable {X U : Type} [DecidableEq X] [DecidableEq U]

/-- A vtree whose internal nodes carry a bag of vertices and a relation. -/
inductive DTree (X U : Type) where
  | leaf (x : X)
  | node (bag : Finset U) (rel : (U → Bool) → Prop) (l r : DTree X U)

namespace DTree

variable (inp : X → U)

/-- The bag of a node; a leaf's bag is its input's vertex. -/
def bag : DTree X U → Finset U
  | leaf x => {inp x}
  | node B _ _ _ => B

/-- The inputs at the leaves below a node. -/
def vars : DTree X U → Finset X
  | leaf x => {x}
  | node _ _ l r => l.vars ∪ r.vars

/-- The union of the bags below a node. -/
def ins : DTree X U → Finset U
  | leaf x => {inp x}
  | node B _ l r => B ∪ l.ins ∪ r.ins

/-- All relations below a node hold. -/
def AllRel : DTree X U → (U → Bool) → Prop
  | leaf _, _ => True
  | node _ L l r, ν => L ν ∧ l.AllRel ν ∧ r.AllRel ν

/-- The separation properties that connectivity gives (Lemma 3.2), and that
relations depend only on their bags. -/
def WF : DTree X U → Prop
  | leaf _ => True
  | node B L l r =>
      (∀ ν ν' : U → Bool, (∀ u ∈ B, ν u = ν' u) → (L ν ↔ L ν')) ∧
      Disjoint l.vars r.vars ∧
      l.ins inp ∩ r.ins inp ⊆ B ∧
      l.ins inp ∩ B ⊆ l.bag inp ∧
      r.ins inp ∩ B ⊆ r.bag inp ∧
      l.WF ∧ r.WF

omit [DecidableEq X] in
theorem bag_subset_ins : ∀ t : DTree X U, t.bag inp ⊆ t.ins inp
  | leaf _ => by simp [bag, ins]
  | node B _ l r => by
      intro u hu
      simp only [bag] at hu
      simp [ins, hu]

theorem input_mem_ins : ∀ (t : DTree X U) (x : X), x ∈ t.vars → inp x ∈ t.ins inp
  | leaf y, x, hx => by simp_all [vars, ins]
  | node B _ l r, x, hx => by
      simp only [vars, Finset.mem_union] at hx
      simp only [ins, Finset.mem_union]
      rcases hx with hx | hx
      · exact Or.inl (Or.inr (input_mem_ins l x hx))
      · exact Or.inr (input_mem_ins r x hx)

theorem allRel_congr : ∀ (t : DTree X U), t.WF inp → ∀ ν ν' : U → Bool,
    (∀ u ∈ t.ins inp, ν u = ν' u) → (t.AllRel ν ↔ t.AllRel ν')
  | leaf _, _, _, _, _ => by simp [AllRel]
  | node B L l r, hwf, ν, ν', h => by
      obtain ⟨hL, -, -, -, -, hl, hr⟩ := hwf
      have hB : ∀ u ∈ B, ν u = ν' u := fun u hu => h u (by simp [ins, hu])
      have hl' : ∀ u ∈ l.ins inp, ν u = ν' u := fun u hu => h u (by simp [ins, hu])
      have hr' : ∀ u ∈ r.ins inp, ν u = ν' u := fun u hu => h u (by simp [ins, hu])
      simp only [AllRel]
      rw [hL ν ν' hB, allRel_congr l hl ν ν' hl', allRel_congr r hr ν ν' hr']

end DTree

open DTree

/-- Two valuations agree on a set of vertices. -/
def Agree (S : Finset U) (ν ν' : U → Bool) : Prop := ∀ u ∈ S, ν u = ν' u

omit [DecidableEq X] [DecidableEq U] in
theorem Agree.symm {S : Finset U} {ν ν' : U → Bool} (h : Agree S ν ν') : Agree S ν' ν :=
  fun u hu => (h u hu).symm

omit [DecidableEq X] [DecidableEq U] in
theorem Agree.trans {S : Finset U} {ν ν' ν'' : U → Bool} (h : Agree S ν ν')
    (h' : Agree S ν' ν'') : Agree S ν ν'' :=
  fun u hu => (h u hu).trans (h' u hu)

omit [DecidableEq X] [DecidableEq U] in
theorem Agree.mono {S S' : Finset U} {ν ν' : U → Bool} (h : Agree S ν ν') (hS : S' ⊆ S) :
    Agree S' ν ν' :=
  fun u hu => h u (hS hu)

/-- `Q inp t σ y`: the inputs y below t are consistent with the valuation σ of
t's bag (Definition 4.1). Values outside the bag and outside t's inputs are
ignored. -/
def Q (inp : X → U) (t : DTree X U) (σ : U → Bool) (y : X → Bool) : Prop :=
  ∃ μ : U → Bool, Agree (t.bag inp) μ σ ∧ (∀ x ∈ t.vars, μ (inp x) = y x) ∧ t.AllRel μ

omit [DecidableEq U] in
theorem q_congr_state {inp : X → U} {t : DTree X U} {σ σ' : U → Bool} (h : Agree (t.bag inp) σ σ')
    (y : X → Bool) : Q inp t σ y ↔ Q inp t σ' y := by
  constructor
  · rintro ⟨μ, h₁, h₂, h₃⟩
    exact ⟨μ, h₁.trans h, h₂, h₃⟩
  · rintro ⟨μ, h₁, h₂, h₃⟩
    exact ⟨μ, h₁.trans h.symm, h₂, h₃⟩

omit [DecidableEq U] in
theorem q_congr_input {inp : X → U} {t : DTree X U} (σ : U → Bool) {y y' : X → Bool}
    (h : ∀ x ∈ t.vars, y x = y' x) : Q inp t σ y ↔ Q inp t σ y' := by
  constructor
  · rintro ⟨μ, h₁, h₂, h₃⟩
    exact ⟨μ, h₁, fun x hx => (h₂ x hx).trans (h x hx), h₃⟩
  · rintro ⟨μ, h₁, h₂, h₃⟩
    exact ⟨μ, h₁, fun x hx => (h₂ x hx).trans (h x hx).symm, h₃⟩

/-- Lemma 4.3 (factorization). -/
theorem q_node_iff {inp : X → U} {B : Finset U} {L : (U → Bool) → Prop} {l r : DTree X U}
    (hwf : (DTree.node B L l r).WF inp) (σ : U → Bool) (y : X → Bool) :
    Q inp (.node B L l r) σ y ↔ L σ ∧
      (∃ τ, Agree (l.bag inp ∩ B) τ σ ∧ Q inp l τ y) ∧
      (∃ τ, Agree (r.bag inp ∩ B) τ σ ∧ Q inp r τ y) := by
  obtain ⟨hL, -, hlr, hlB, hrB, hl, hr⟩ := hwf
  constructor
  · rintro ⟨μ, hμσ, hμy, hLμ, hlμ, hrμ⟩
    have hμσ' : Agree B μ σ := hμσ
    refine ⟨(hL μ σ hμσ').1 hLμ, ⟨μ, hμσ'.mono Finset.inter_subset_right, μ, fun _ _ => rfl,
      fun x hx => hμy x (by simp [DTree.vars, hx]), hlμ⟩,
      ⟨μ, hμσ'.mono Finset.inter_subset_right, μ, fun _ _ => rfl,
      fun x hx => hμy x (by simp [DTree.vars, hx]), hrμ⟩⟩
  · rintro ⟨hLσ, ⟨τl, hτl, μl, hμl, hμly, hμlrel⟩, ⟨τr, hτr, μr, hμr, hμry, hμrrel⟩⟩
    let μ : U → Bool := fun u => if u ∈ B then σ u else if u ∈ l.ins inp then μl u else μr u
    have hμB : Agree B μ σ := fun u hu => by simp [μ, hu]
    have hμl_eq : ∀ u ∈ l.ins inp, μ u = μl u := by
      intro u hu
      by_cases huB : u ∈ B
      · have hul : u ∈ l.bag inp := hlB (Finset.mem_inter.2 ⟨hu, huB⟩)
        simp only [μ, huB, if_true]
        exact ((hμl u hul).trans (hτl u (Finset.mem_inter.2 ⟨hul, huB⟩))).symm
      · simp [μ, huB, hu]
    have hμr_eq : ∀ u ∈ r.ins inp, μ u = μr u := by
      intro u hu
      by_cases huB : u ∈ B
      · have hur : u ∈ r.bag inp := hrB (Finset.mem_inter.2 ⟨hu, huB⟩)
        simp only [μ, huB, if_true]
        exact ((hμr u hur).trans (hτr u (Finset.mem_inter.2 ⟨hur, huB⟩))).symm
      · have hul : u ∉ l.ins inp := fun hul => huB (hlr (Finset.mem_inter.2 ⟨hul, hu⟩))
        simp [μ, huB, hul]
    refine ⟨μ, hμB, ?_, (hL μ σ hμB).2 hLσ, ?_, ?_⟩
    · intro x hx
      simp only [DTree.vars, Finset.mem_union] at hx
      rcases hx with hx | hx
      · rw [hμl_eq _ (input_mem_ins inp l x hx)]
        exact hμly x hx
      · rw [hμr_eq _ (input_mem_ins inp r x hx)]
        exact hμry x hx
    · exact (allRel_congr inp l hl μ μl hμl_eq).2 hμlrel
    · exact (allRel_congr inp r hr μ μr hμr_eq).2 hμrrel

/-- A relational tree decomposition whose relations have unique solutions (Definition 3.1). -/
structure RTD (X U : Type) [DecidableEq X] [DecidableEq U] where
  inp : X → U
  tree : DTree X U
  acc : (U → Bool) → Prop
  wf : tree.WF inp
  allVars : ∀ x, x ∈ tree.vars
  unique : ∀ w : X → Bool, ∃! ν : U → Bool, (∀ x, ν (inp x) = w x) ∧ tree.AllRel ν
  accDep : ∀ ν ν' : U → Bool, Agree (tree.bag inp) ν ν' → (acc ν ↔ acc ν')

namespace RTD

variable (R : RTD X U)

/-- The unique solution ν_w. -/
noncomputable def sol (w : X → Bool) : U → Bool := (R.unique w).exists.choose

theorem sol_inputs (w : X → Bool) (x : X) : R.sol w (R.inp x) = w x :=
  (R.unique w).exists.choose_spec.1 x

theorem sol_allRel (w : X → Bool) : R.tree.AllRel (R.sol w) :=
  (R.unique w).exists.choose_spec.2

theorem sol_eq (w : X → Bool) (ν : U → Bool) (h₁ : ∀ x, ν (R.inp x) = w x)
    (h₂ : R.tree.AllRel ν) : ν = R.sol w :=
  (R.unique w).unique ⟨h₁, h₂⟩ ⟨R.sol_inputs w, R.sol_allRel w⟩

/-- The function the decomposition computes. -/
def f (w : X → Bool) : Prop := R.acc (R.sol w)

/-- A context for a subtree t of R.tree: the relations outside t, and t's
interface I(t). -/
structure Ctx (t : DTree X U) where
  out : (U → Bool) → Prop
  iface : Finset U
  iface_sub : iface ⊆ t.bag R.inp
  out_dep : ∀ ν ν' : U → Bool,
    (∀ u, u ∉ t.ins R.inp ∨ u ∈ iface → ν u = ν' u) → (out ν ↔ out ν')
  split : ∀ ν, R.tree.AllRel ν ↔ t.AllRel ν ∧ out ν
  inputs : ∀ x, x ∉ t.vars → R.inp x ∈ t.ins R.inp → R.inp x ∈ iface

/-- The root's context. -/
def rootCtx : R.Ctx R.tree where
  out := fun _ => True
  iface := ∅
  iface_sub := Finset.empty_subset _
  out_dep := fun _ _ _ => Iff.rfl
  split := fun _ => ⟨fun h => ⟨h, trivial⟩, fun h => h.1⟩
  inputs := fun x hx => absurd (R.allVars x) hx

variable {R}

/-- The context of the left child. -/
def Ctx.left {B : Finset U} {L : (U → Bool) → Prop} {l r : DTree X U}
    (c : R.Ctx (.node B L l r)) (hwf : (DTree.node B L l r).WF R.inp) : R.Ctx l where
  out := fun ν => c.out ν ∧ L ν ∧ r.AllRel ν
  iface := l.bag R.inp ∩ B
  iface_sub := Finset.inter_subset_left
  out_dep := by
    obtain ⟨hL, -, hlr, hlB, -, -, hr⟩ := hwf
    intro ν ν' h
    have key : ∀ u, u ∉ l.ins R.inp ∨ u ∈ l.bag R.inp ∩ B → ν u = ν' u := h
    have hB : ∀ u ∈ B, ν u = ν' u := by
      intro u hu
      by_cases hul : u ∈ l.ins R.inp
      · exact key u (Or.inr (Finset.mem_inter.2 ⟨hlB (Finset.mem_inter.2 ⟨hul, hu⟩), hu⟩))
      · exact key u (Or.inl hul)
    have hout : c.out ν ↔ c.out ν' := by
      apply c.out_dep
      intro u hu
      rcases hu with hu | hu
      · apply key u
        left
        intro hul
        exact hu (by simp [DTree.ins, hul])
      · exact hB u (c.iface_sub hu)
    have hrr : r.AllRel ν ↔ r.AllRel ν' := by
      apply allRel_congr R.inp r hr
      intro u hu
      by_cases hul : u ∈ l.ins R.inp
      · exact hB u (hlr (Finset.mem_inter.2 ⟨hul, hu⟩))
      · exact key u (Or.inl hul)
    rw [hout, hL ν ν' hB, hrr]
  split := by
    intro ν
    rw [c.split]
    simp only [DTree.AllRel]
    tauto
  inputs := by
    obtain ⟨-, -, hlr, hlB, -, -, -⟩ := hwf
    intro x hx hxl
    refine Finset.mem_inter.2 ⟨hlB (Finset.mem_inter.2 ⟨hxl, ?_⟩), ?_⟩ <;>
    · by_cases hxr : x ∈ r.vars
      · exact hlr (Finset.mem_inter.2 ⟨hxl, input_mem_ins R.inp r x hxr⟩)
      · have hxt : x ∉ (DTree.node B L l r).vars := by simp [DTree.vars, hx, hxr]
        exact (c.iface_sub (c.inputs x hxt (by simp [DTree.ins, hxl])))

/-- The context of the right child. -/
def Ctx.right {B : Finset U} {L : (U → Bool) → Prop} {l r : DTree X U}
    (c : R.Ctx (.node B L l r)) (hwf : (DTree.node B L l r).WF R.inp) : R.Ctx r where
  out := fun ν => c.out ν ∧ L ν ∧ l.AllRel ν
  iface := r.bag R.inp ∩ B
  iface_sub := Finset.inter_subset_left
  out_dep := by
    obtain ⟨hL, -, hlr, -, hrB, hl, -⟩ := hwf
    intro ν ν' h
    have key : ∀ u, u ∉ r.ins R.inp ∨ u ∈ r.bag R.inp ∩ B → ν u = ν' u := h
    have hB : ∀ u ∈ B, ν u = ν' u := by
      intro u hu
      by_cases hur : u ∈ r.ins R.inp
      · exact key u (Or.inr (Finset.mem_inter.2 ⟨hrB (Finset.mem_inter.2 ⟨hur, hu⟩), hu⟩))
      · exact key u (Or.inl hur)
    have hout : c.out ν ↔ c.out ν' := by
      apply c.out_dep
      intro u hu
      rcases hu with hu | hu
      · apply key u
        left
        intro hur
        exact hu (by simp [DTree.ins, hur])
      · exact hB u (c.iface_sub hu)
    have hll : l.AllRel ν ↔ l.AllRel ν' := by
      apply allRel_congr R.inp l hl
      intro u hu
      by_cases hur : u ∈ r.ins R.inp
      · exact hB u (hlr (Finset.mem_inter.2 ⟨hu, hur⟩))
      · exact key u (Or.inl hur)
    rw [hout, hL ν ν' hB, hll]
  split := by
    intro ν
    rw [c.split]
    simp only [DTree.AllRel]
    tauto
  inputs := by
    obtain ⟨-, -, hlr, -, hrB, -, -⟩ := hwf
    intro x hx hxr
    refine Finset.mem_inter.2 ⟨hrB (Finset.mem_inter.2 ⟨hxr, ?_⟩), ?_⟩ <;>
    · by_cases hxl : x ∈ l.vars
      · exact hlr (Finset.mem_inter.2 ⟨input_mem_ins R.inp l x hxl, hxr⟩)
      · have hxt : x ∉ (DTree.node B L l r).vars := by simp [DTree.vars, hx, hxl]
        exact (c.iface_sub (c.inputs x hxt (by simp [DTree.ins, hxr])))

/-- Replace the inputs below t by y. -/
def upd (t : DTree X U) (w y : X → Bool) : X → Bool :=
  fun x => if x ∈ t.vars then y x else w x

variable (R)

/-- Lemma 4.2: a solution restricted to a subtree is an inner witness. -/
theorem q_sol {t : DTree X U} (c : R.Ctx t) (w : X → Bool) : Q R.inp t (R.sol w) w :=
  ⟨R.sol w, fun _ _ => rfl, fun x _ => R.sol_inputs w x, ((c.split _).1 (R.sol_allRel w)).1⟩

/-- Lemma 4.4 (replacement). -/
theorem replace {t : DTree X U} (c : R.Ctx t) (ht : t.WF R.inp) (w y : X → Bool)
    (τ : U → Bool) (hQ : Q R.inp t τ y) (hτ : Agree c.iface τ (R.sol w)) :
    Agree (t.bag R.inp) (R.sol (upd t w y)) τ := by
  obtain ⟨μ, hμσ, hμy, hμrel⟩ := hQ
  let ν : U → Bool := fun u => if u ∈ t.ins R.inp then μ u else R.sol w u
  have hνt : t.AllRel ν := by
    rw [allRel_congr R.inp t ht ν μ (fun u hu => by simp [ν, hu])]
    exact hμrel
  have hνout : c.out ν := by
    have hsol := ((c.split _).1 (R.sol_allRel w)).2
    rw [c.out_dep ν (R.sol w)]
    · exact hsol
    intro u hu
    rcases hu with hu | hu
    · simp [ν, hu]
    · have hut : u ∈ t.ins R.inp := bag_subset_ins R.inp t (c.iface_sub hu)
      simp only [ν, hut, if_true]
      exact (hμσ u (c.iface_sub hu)).trans (hτ u hu)
  have hνin : ∀ x, ν (R.inp x) = upd t w y x := by
    intro x
    by_cases hx : x ∈ t.vars
    · simp [ν, upd, hx, input_mem_ins R.inp t x hx, hμy x hx]
    · by_cases hxi : R.inp x ∈ t.ins R.inp
      · have hface := c.inputs x hx hxi
        simp only [ν, hxi, if_true, upd, hx, if_false]
        rw [hμσ _ (c.iface_sub hface), hτ _ hface, R.sol_inputs]
      · simp [ν, hxi, upd, hx, R.sol_inputs]
  have hν := R.sol_eq (upd t w y) ν hνin ((c.split ν).2 ⟨hνt, hνout⟩)
  intro u hu
  rw [← hν]
  simp only [ν, bag_subset_ins R.inp t hu, if_true]
  exact hμσ u hu

end RTD


/-! ## SDDs -/

/-- An SDD respecting a vtree, in the strict form of Section 2: a decision node
at an internal node has its primes at the left child and its subs at the right
child. A node shared in the SDD appears as equal subterms; `decNodes` collects
the distinct decision nodes. -/
inductive Sdd : DTree X U → Type where
  | const {t : DTree X U} (b : Bool) : Sdd t
  | lit (x : X) (b : Bool) : Sdd (.leaf x)
  | dec {B : Finset U} {L : (U → Bool) → Prop} {l r : DTree X U} (m : ℕ)
      (p : Fin m → Sdd l) (s : Fin m → Sdd r) : Sdd (.node B L l r)

namespace Sdd

/-- An assignment satisfies the SDD. -/
def Sat : {t : DTree X U} → Sdd t → (X → Bool) → Prop
  | _, const b, _ => b = true
  | _, lit x b, w => w x = b
  | _, dec _ p s, w => ∃ i, (p i).Sat w ∧ (s i).Sat w

/-- Every decision node's primes are consistent, mutually exclusive, and exhaustive. -/
def Valid : {t : DTree X U} → Sdd t → Prop
  | _, const _ => True
  | _, lit _ _ => True
  | _, dec _ p s => (∀ i, (p i).Valid) ∧ (∀ i, (s i).Valid) ∧
      (∀ i, ∃ w, (p i).Sat w) ∧ (∀ w, ∃! i, (p i).Sat w)

/-- The distinct decision nodes of the SDD. -/
def decNodes : {t : DTree X U} → Sdd t → Set (Σ t : DTree X U, Sdd t)
  | _, const _ => ∅
  | _, lit _ _ => ∅
  | _, d@(dec _ p s) => insert ⟨_, d⟩ (⋃ i, ((p i).decNodes ∪ (s i).decNodes))

/-- The number of elements of a decision node. -/
def elems : {t : DTree X U} → Sdd t → ℕ
  | _, dec m _ _ => m
  | _, _ => 0

omit [DecidableEq U] in
/-- An SDD respecting t only reads the inputs below t. -/
theorem sat_congr : ∀ {t : DTree X U} (S : Sdd t) {w w' : X → Bool},
    (∀ x ∈ t.vars, w x = w' x) → (S.Sat w ↔ S.Sat w')
  | _, const _, _, _, _ => Iff.rfl
  | _, lit x _, w, w', h => by
      simp only [Sat]
      rw [h x (by simp [DTree.vars])]
  | _, dec _ p s, w, w', h => by
      simp only [Sat]
      refine exists_congr fun i => and_congr ?_ ?_
      · exact sat_congr (p i) fun x hx => h x (by simp [DTree.vars, hx])
      · exact sat_congr (s i) fun x hx => h x (by simp [DTree.vars, hx])

end Sdd

/-! ## The construction (Section 5) -/

/-- The valuation that equals π on S and is false elsewhere. -/
def canon (S : Finset U) (π : U → Bool) : U → Bool := fun u => if u ∈ S then π u else false

omit [DecidableEq X] in
theorem canon_agree (S : Finset U) (π : U → Bool) : Agree S (canon S π) π :=
  fun u hu => by simp [canon, hu]

omit [DecidableEq X] in
theorem canon_eq_of_agree {S : Finset U} {π π' : U → Bool} (h : Agree S π π') :
    canon S π = canon S π' := by
  funext u
  by_cases hu : u ∈ S <;> simp [canon, hu, h u]

omit [DecidableEq X] in
theorem canon_canon (S : Finset U) (π : U → Bool) : canon S (canon S π) = canon S π :=
  canon_eq_of_agree (canon_agree S π)

/-- The functions computed by pair cells and joins (Definition 5.2), for S the
bag (pair cells) or the interface (joins). -/
def G (inp : X → U) (t : DTree X U) (S : Finset U) (π : Bool → U → Bool) (y : X → Bool) : Prop :=
  ∀ i, ∃ σ, Agree S σ (π i) ∧ Q inp t σ y

namespace RTD

variable (R : RTD X U) [Fintype X] [Fintype U]

/-- A witness pair exists (Definition 5.2). -/
def Realizable (S : Finset U) (π : Bool → U → Bool) : Prop :=
  ∃ w : Bool → X → Bool, ∀ i, Agree S (R.sol (w i)) (π i)

open Classical in
/-- The chosen witness pair. -/
noncomputable def witness (S : Finset U) (π : Bool → U → Bool) : Bool → X → Bool :=
  if h : R.Realizable S π then Classical.choose h else fun _ _ => false

/-- The state pair φ(y) of Lemma 5.3, in canonical form. -/
noncomputable def phi (a : DTree X U) (w : Bool → X → Bool) (y : X → Bool) : Bool → U → Bool :=
  fun i => canon (a.bag R.inp) (R.sol (upd a (w i) y))

open Classical in
/-- The nonempty fibers of φ, by their state pairs. -/
noncomputable def fibers (a : DTree X U) (w : Bool → X → Bool) : Finset (Bool → U → Bool) :=
  Finset.univ.image (R.phi a w)

/-- The condition for the sub of a fiber to be the join rather than ⊥ (τ_i ∈ R_i). -/
def Compat (B : Finset U) (L : (U → Bool) → Prop) (a : DTree X U) (S : Finset U)
    (π : Bool → U → Bool) (τ : Bool → U → Bool) : Prop :=
  ∀ i, ∃ σ, L σ ∧ Agree S σ (π i) ∧ Agree (a.bag R.inp ∩ B) (τ i) σ

open Classical in
/-- The SDD nodes for pair cells and joins (proof of Theorem 5.1). -/
noncomputable def build : (t : DTree X U) → Finset U → (Bool → U → Bool) → Sdd t
  | .leaf x, S, π =>
      if R.inp x ∈ S then
        (if π false (R.inp x) = π true (R.inp x) then .lit x (π false (R.inp x)) else .const false)
      else .const true
  | .node B L a b, S, π =>
      let P := R.fibers a (R.witness S π)
      .dec P.card
        (fun k => build a (a.bag R.inp) (P.equivFin.symm k).1)
        (fun k => if R.Compat B L a S π (P.equivFin.symm k).1 then
            build b (b.bag R.inp ∩ B) (fun i => canon (b.bag R.inp ∩ B) (π i))
          else .const false)

end RTD


/-! ## Correctness of the construction -/

/-- (S2) at a right child t: I(t.r) ⊆ S, where S is t's interface. -/
def RightOK (inp : X → U) : DTree X U → Finset U → Prop
  | .leaf _, _ => True
  | .node B _ _ b, S => b.bag inp ∩ B ⊆ S

/-- (S2) holds at every internal right child. -/
def Shape (inp : X → U) : DTree X U → Prop
  | .leaf _ => True
  | .node B _ a b => Shape inp a ∧ Shape inp b ∧ RightOK inp b (b.bag inp ∩ B)

namespace RTD

omit [DecidableEq U] in
theorem upd_upd (t : DTree X U) (w y z : X → Bool) : upd t (upd t w z) y = upd t w y := by
  funext x
  by_cases hx : x ∈ t.vars <;> simp [upd, hx]

omit [DecidableEq U] in
theorem upd_vars {t : DTree X U} (w y : X → Bool) {x : X} (hx : x ∈ t.vars) : upd t w y x = y x :=
  if_pos hx

omit [DecidableEq U] in
theorem upd_not_vars {t : DTree X U} (w y : X → Bool) {x : X} (hx : x ∉ t.vars) :
    upd t w y x = w x :=
  if_neg hx

variable {R : RTD X U} [Fintype X] [Fintype U]

omit [Fintype X] [Fintype U] in
theorem witness_spec {S : Finset U} {π : Bool → U → Bool} (h : R.Realizable S π) (i : Bool) :
    Agree S (R.sol (R.witness S π i)) (π i) := by
  unfold witness
  rw [dif_pos h]
  exact Classical.choose_spec h i

theorem phi_mem (a : DTree X U) (w : Bool → X → Bool) (y : X → Bool) :
    R.phi a w y ∈ R.fibers a w := by
  classical
  unfold fibers
  convert Finset.mem_image_of_mem (R.phi a w) (Finset.mem_univ y)

theorem mem_fibers {a : DTree X U} {w : Bool → X → Bool} {τ : Bool → U → Bool}
    (hτ : τ ∈ R.fibers a w) : ∃ y, R.phi a w y = τ := by
  classical
  unfold fibers at hτ
  obtain ⟨y, -, hy⟩ := Finset.mem_image.1 (by convert hτ)
  exact ⟨y, hy⟩

/-- Lemma 5.3: each nonempty fiber is the pair cell of its states. -/
theorem fiber_iff {a : DTree X U} (ca : R.Ctx a) (ha : a.WF R.inp) (w : Bool → X → Bool)
    {τ : Bool → U → Bool} (hτ : τ ∈ R.fibers a w) (y : X → Bool) :
    (∀ i, Q R.inp a (τ i) y) ↔ R.phi a w y = τ := by
  obtain ⟨z, rfl⟩ := mem_fibers hτ
  constructor
  · intro h
    funext i
    have hrep := R.replace ca ha (upd a (w i) z) y (R.phi a w z i) (h i)
      ((canon_agree _ _).mono ca.iface_sub)
    rw [upd_upd] at hrep
    simp only [phi] at hrep ⊢
    exact (canon_eq_of_agree hrep).trans (canon_canon _ _)
  · intro h i
    rw [← h, phi, q_congr_state (canon_agree _ _),
      q_congr_input _ (y' := upd a (w i) y) (fun x hx => (upd_vars _ _ hx).symm)]
    exact R.q_sol ca _

omit [Fintype X] [Fintype U] in
theorem phi_canon (a : DTree X U) (w : Bool → X → Bool) (y : X → Bool) (i : Bool) :
    canon (a.bag R.inp) (R.phi a w y i) = R.phi a w y i :=
  canon_canon _ _

/-- The pair cells at a fiber's states are realizable (Lemma 5.3, part 2). -/
theorem fiber_realizable {a : DTree X U} {w : Bool → X → Bool} {τ : Bool → U → Bool}
    (hτ : τ ∈ R.fibers a w) : R.Realizable (a.bag R.inp) τ := by
  obtain ⟨y, rfl⟩ := mem_fibers hτ
  exact ⟨fun i => upd a (w i) y, fun i => (canon_agree _ _).symm⟩

omit [Fintype X] [Fintype U] in
/-- The core of Lemmas 5.4 and 5.5. -/
theorem state_of_compatible {B : Finset U} {L : (U → Bool) → Prop} {a b : DTree X U}
    (c : R.Ctx (.node B L a b)) (hwf : (DTree.node B L a b).WF R.inp) {S : Finset U}
    (hS : c.iface ⊆ S) (hI : b.bag R.inp ∩ B ⊆ S) {π : U → Bool} {w : X → Bool}
    (hw : Agree S (R.sol w) π) {σ τa : U → Bool} {y : X → Bool} (hL : L σ)
    (hσ : Agree S σ π) (hτa : Agree (a.bag R.inp ∩ B) τa σ) (hQ : Q R.inp a τa y) :
    Agree B (R.sol (upd a w y)) σ ∧ Agree (a.bag R.inp) (R.sol (upd a w y)) τa := by
  have hwf' := hwf
  obtain ⟨-, hdisj, -, -, -, ha, hb⟩ := hwf'
  set y' := upd a w y with hy'
  have hQt : Q R.inp (.node B L a b) σ y' := by
    rw [q_node_iff hwf]
    refine ⟨hL, ⟨τa, hτa, (q_congr_input _ fun x hx => (upd_vars _ _ hx).symm).1 hQ⟩,
      ⟨R.sol w, fun u hu => (hw u (hI hu)).trans (hσ u (hI hu)).symm, ?_⟩⟩
    rw [q_congr_input _ (y' := w) fun x hx =>
      upd_not_vars _ _ (Finset.disjoint_right.1 hdisj hx)]
    exact R.q_sol (c.right hwf) w
  have hupd : upd (.node B L a b) w y' = y' := by
    funext x
    by_cases hx : x ∈ (DTree.node B L a b).vars
    · exact upd_vars _ _ hx
    · have hxa : x ∉ a.vars := fun hxa => hx (by simp [DTree.vars, hxa])
      rw [upd_not_vars _ _ hx, hy', upd_not_vars _ _ hxa]
  have h₁ : Agree B (R.sol y') σ := by
    have := R.replace c hwf w y' σ hQt (fun u hu => (hσ u (hS hu)).trans (hw u (hS hu)).symm)
    rwa [hupd] at this
  refine ⟨h₁, ?_⟩
  have h₂ := R.replace (c.left hwf) ha y' y τa hQ
    (fun u hu => (hτa u hu).trans (h₁ u (Finset.mem_inter.1 hu).2).symm)
  simp only [hy', upd_upd] at h₂
  exact h₂

/-- Lemmas 5.4 and 5.5: how a pair cell or join decomposes over a fiber. -/
theorem decide_iff {B : Finset U} {L : (U → Bool) → Prop} {a b : DTree X U}
    (c : R.Ctx (.node B L a b)) (hwf : (DTree.node B L a b).WF R.inp) {S : Finset U}
    (hS : c.iface ⊆ S) (hI : b.bag R.inp ∩ B ⊆ S) {π : Bool → U → Bool}
    {w : Bool → X → Bool} (hw : ∀ i, Agree S (R.sol (w i)) (π i)) (y : X → Bool) :
    G R.inp (.node B L a b) S π y ↔
      R.Compat B L a S π (R.phi a w y) ∧
      G R.inp b (b.bag R.inp ∩ B) (fun i => canon (b.bag R.inp ∩ B) (π i)) y := by
  have hwf' := hwf
  obtain ⟨-, -, -, -, -, ha, -⟩ := hwf'
  have hfib : ∀ i, Q R.inp a (R.phi a w y i) y :=
    (fiber_iff (c.left hwf) ha w (phi_mem a w y) y).2 rfl
  constructor
  · intro h
    refine ⟨fun i => ?_, fun i => ?_⟩
    · obtain ⟨σ, hσ, hQ⟩ := h i
      obtain ⟨hL, ⟨τa, hτa, hQa⟩, -⟩ := (q_node_iff hwf σ y).1 hQ
      have hst := (state_of_compatible c hwf hS hI (hw i) hL hσ hτa hQa).2
      refine ⟨σ, hL, hσ, fun u hu => ?_⟩
      have hua := (Finset.mem_inter.1 hu).1
      simp only [phi, canon, hua, if_true]
      exact (hst u hua).trans (hτa u hu)
    · obtain ⟨σ, hσ, hQ⟩ := h i
      obtain ⟨-, -, ⟨τb, hτb, hQb⟩⟩ := (q_node_iff hwf σ y).1 hQ
      refine ⟨τb, fun u hu => ?_, hQb⟩
      show τb u = canon (b.bag R.inp ∩ B) (π i) u
      rw [canon_agree _ _ u hu]
      exact (hτb u hu).trans (hσ u (hI hu))
  · rintro ⟨hc, hg⟩ i
    obtain ⟨σ, hL, hσ, hτσ⟩ := hc i
    obtain ⟨ρ, hρ, hQb⟩ := hg i
    refine ⟨σ, hσ, (q_node_iff hwf σ y).2 ⟨hL, ⟨_, hτσ, hfib i⟩, ⟨ρ, fun u hu => ?_, hQb⟩⟩⟩
    rw [hρ u hu]
    show canon (b.bag R.inp ∩ B) (π i) u = σ u
    rw [canon_agree _ _ u hu]
    exact (hσ u (hI hu)).symm

/-- The sub of a compatible fiber is a realizable join (Lemmas 5.4 and 5.5). -/
theorem sub_realizable {B : Finset U} {L : (U → Bool) → Prop} {a b : DTree X U}
    (c : R.Ctx (.node B L a b)) (hwf : (DTree.node B L a b).WF R.inp) {S : Finset U}
    (hS : c.iface ⊆ S) (hI : b.bag R.inp ∩ B ⊆ S) {π : Bool → U → Bool}
    {w : Bool → X → Bool} (hw : ∀ i, Agree S (R.sol (w i)) (π i)) (y : X → Bool)
    (hc : R.Compat B L a S π (R.phi a w y)) :
    R.Realizable (b.bag R.inp ∩ B) (fun i => canon (b.bag R.inp ∩ B) (π i)) := by
  have hwf' := hwf
  obtain ⟨-, -, -, -, -, ha, -⟩ := hwf'
  have hfib : ∀ i, Q R.inp a (R.phi a w y i) y :=
    (fiber_iff (c.left hwf) ha w (phi_mem a w y) y).2 rfl
  refine ⟨fun i => upd a (w i) y, fun i => ?_⟩
  obtain ⟨σ, hL, hσ, hτσ⟩ := hc i
  have hst := (state_of_compatible c hwf hS hI (hw i) hL hσ hτσ (hfib i)).1
  intro u hu
  show R.sol (upd a (w i) y) u = canon (b.bag R.inp ∩ B) (π i) u
  rw [canon_agree _ _ u hu, hst u (Finset.mem_inter.1 hu).2]
  exact hσ u (hI hu)

omit [Fintype X] [Fintype U] in
theorem q_leaf_iff (x : X) (σ : U → Bool) (y : X → Bool) :
    Q R.inp (.leaf x) σ y ↔ σ (R.inp x) = y x := by
  constructor
  · rintro ⟨μ, hμσ, hμy, -⟩
    rw [← hμσ (R.inp x) (by simp [DTree.bag])]
    exact hμy x (by simp [DTree.vars])
  · intro h
    exact ⟨σ, fun _ _ => rfl, fun x' hx' => by simp_all [DTree.vars], trivial⟩


theorem build_leaf_valid (x : X) (S : Finset U) (π : Bool → U → Bool) :
    (R.build (.leaf x) S π).Valid := by
  unfold build
  split_ifs <;> trivial

theorem build_leaf_sat (x : X) (S : Finset U) (π : Bool → U → Bool) (y : X → Bool) :
    (R.build (.leaf x) S π).Sat y ↔ G R.inp (.leaf x) S π y := by
  simp only [G, q_leaf_iff]
  unfold build
  by_cases hx : R.inp x ∈ S
  · have hG : (∀ i, ∃ σ : U → Bool, Agree S σ (π i) ∧ σ (R.inp x) = y x) ↔
        ∀ i, π i (R.inp x) = y x :=
      forall_congr' fun i => ⟨fun ⟨σ, hσ, h⟩ => (hσ _ hx).symm.trans h,
        fun h => ⟨π i, fun _ _ => rfl, h⟩⟩
    rw [hG, if_pos hx, Bool.forall_bool]
    by_cases hπ : π false (R.inp x) = π true (R.inp x)
    · rw [if_pos hπ]
      simp only [Sdd.Sat]
      constructor
      · intro h
        exact ⟨h.symm, hπ.symm.trans h.symm⟩
      · intro h
        exact h.1.symm
    · rw [if_neg hπ]
      simp only [Sdd.Sat, Bool.false_eq_true, false_iff, not_and]
      intro h₀ h₁
      exact hπ (h₀.trans h₁.symm)
  · rw [if_neg hx]
    simp only [Sdd.Sat, true_iff]
    intro i
    refine ⟨Function.update (π i) (R.inp x) (y x), fun u hu => ?_, by simp⟩
    have hne : u ≠ R.inp x := fun h => hx (h ▸ hu)
    simp [Function.update, hne]

/-- A prime of a decision node is satisfied exactly on its fiber. -/
theorem prime_sat_iff {a : DTree X U} (ca : R.Ctx a) (ha : a.WF R.inp) (hsha : Shape R.inp a)
    (w : Bool → X → Bool) {τ : Bool → U → Bool} (hτ : τ ∈ R.fibers a w)
    (ih : ∀ (c : R.Ctx a), a.WF R.inp → Shape R.inp a →
      ∀ (S : Finset U) (π : Bool → U → Bool), c.iface ⊆ S → S ⊆ a.bag R.inp →
      RightOK R.inp a S → R.Realizable S π →
      (R.build a S π).Valid ∧ ∀ y, (R.build a S π).Sat y ↔ G R.inp a S π y)
    (y : X → Bool) : (R.build a (a.bag R.inp) τ).Valid ∧
      ((R.build a (a.bag R.inp) τ).Sat y ↔ R.phi a w y = τ) := by
  have hright : RightOK R.inp a (a.bag R.inp) := by
    cases a with
    | leaf _ => trivial
    | node B' _ _ _ => exact Finset.inter_subset_right
  obtain ⟨hv, hs⟩ := ih ca ha hsha (a.bag R.inp) τ ca.iface_sub (subset_refl _) hright
    (fiber_realizable hτ)
  refine ⟨hv, ?_⟩
  rw [hs, ← fiber_iff ca ha w hτ y]
  exact forall_congr' fun i => ⟨fun ⟨σ, hσ, hQ⟩ => (q_congr_state hσ y).1 hQ,
    fun hQ => ⟨τ i, fun _ _ => rfl, hQ⟩⟩

/-- The decision node over the fibers of a is a valid decision whose primes are
the fibers (Lemma 5.3). -/
theorem fibers_partition {a : DTree X U} (ca : R.Ctx a) (ha : a.WF R.inp) (hsha : Shape R.inp a)
    (w : Bool → X → Bool)
    (ih : ∀ (c : R.Ctx a), a.WF R.inp → Shape R.inp a →
      ∀ (S : Finset U) (π : Bool → U → Bool), c.iface ⊆ S → S ⊆ a.bag R.inp →
      RightOK R.inp a S → R.Realizable S π →
      (R.build a S π).Valid ∧ ∀ y, (R.build a S π).Sat y ↔ G R.inp a S π y) :
    let P := R.fibers a w
    (∀ k, (R.build a (a.bag R.inp) (P.equivFin.symm k).1).Valid) ∧
    (∀ k, ∃ y, (R.build a (a.bag R.inp) (P.equivFin.symm k).1).Sat y) ∧
    (∀ y, ∃! k, (R.build a (a.bag R.inp) (P.equivFin.symm k).1).Sat y) ∧
    (∀ y k, (R.build a (a.bag R.inp) (P.equivFin.symm k).1).Sat y ↔
      k = P.equivFin ⟨R.phi a w y, phi_mem a w y⟩) := by
  intro P
  have key : ∀ y k, (R.build a (a.bag R.inp) (P.equivFin.symm k).1).Sat y ↔
      k = P.equivFin ⟨R.phi a w y, phi_mem a w y⟩ := by
    intro y k
    rw [(prime_sat_iff ca ha hsha w (P.equivFin.symm k).2 ih y).2, ← Equiv.symm_apply_eq,
      Subtype.ext_iff, eq_comm]
  refine ⟨fun k => (prime_sat_iff ca ha hsha w (P.equivFin.symm k).2 ih (fun _ => false)).1,
    fun k => ?_, fun y => ⟨_, (key y _).2 rfl, fun k hk => (key y k).1 hk⟩, key⟩
  obtain ⟨y, hy⟩ := mem_fibers (P.equivFin.symm k).2
  refine ⟨y, (key y k).2 ?_⟩
  rw [← Equiv.symm_apply_eq]
  exact Subtype.ext hy.symm

open Classical in
/-- Theorem 5.1 for pair cells and joins: the node built for (t, S, π) is a
valid SDD computing G t S π. -/
theorem build_correct : ∀ (t : DTree X U) (c : R.Ctx t), t.WF R.inp → Shape R.inp t →
    ∀ (S : Finset U) (π : Bool → U → Bool), c.iface ⊆ S → S ⊆ t.bag R.inp →
    RightOK R.inp t S → R.Realizable S π →
    (R.build t S π).Valid ∧ ∀ y, (R.build t S π).Sat y ↔ G R.inp t S π y
  | .leaf x, _, _, _, S, π, _, _, _, _ =>
      ⟨build_leaf_valid x S π, build_leaf_sat x S π⟩
  | .node B L a b, c, hwf, hsh, S, π, hS, _, hI, hreal => by
      have hwf' := hwf
      obtain ⟨-, -, -, -, -, ha, hb⟩ := hwf'
      obtain ⟨hsha, hshb, hrb⟩ := hsh
      have hw := witness_spec hreal
      have hpart := fibers_partition (c.left hwf) ha hsha (R.witness S π)
        (build_correct a)
      have hsub : ∀ τ ∈ R.fibers a (R.witness S π),
          (if R.Compat B L a S π τ then
            R.build b (b.bag R.inp ∩ B) (fun i => canon (b.bag R.inp ∩ B) (π i))
          else .const false).Valid ∧
          ∀ y, R.phi a (R.witness S π) y = τ →
            ((if R.Compat B L a S π τ then
              R.build b (b.bag R.inp ∩ B) (fun i => canon (b.bag R.inp ∩ B) (π i))
            else .const false).Sat y ↔ G R.inp (.node B L a b) S π y) := by
        intro τ hτ
        obtain ⟨y₀, hy₀⟩ := mem_fibers hτ
        by_cases hc : R.Compat B L a S π τ
        · rw [if_pos hc]
          obtain ⟨hv, hs⟩ := build_correct b (c.right hwf) hb hshb (b.bag R.inp ∩ B) _
            (subset_refl _) Finset.inter_subset_left hrb
            (sub_realizable c hwf hS hI hw y₀ (hy₀ ▸ hc))
          refine ⟨hv, fun y hy => ?_⟩
          rw [hs, decide_iff c hwf hS hI hw y, hy]
          exact ⟨fun h => ⟨hc, h⟩, fun h => h.2⟩
        · rw [if_neg hc]
          refine ⟨trivial, fun y hy => ?_⟩
          rw [decide_iff c hwf hS hI hw y, hy]
          simp only [Sdd.Sat, Bool.false_eq_true, false_iff, not_and]
          exact fun h => absurd h hc
      refine ⟨⟨hpart.1, fun k => (hsub _ ((R.fibers a (R.witness S π)).equivFin.symm k).2).1,
        hpart.2.1, hpart.2.2.1⟩, fun y => ?_⟩
      show (∃ k, _ ∧ _) ↔ _
      constructor
      · rintro ⟨k, hp, hs⟩
        have hk := (hpart.2.2.2 y k).1 hp
        subst hk
        simp only [Equiv.symm_apply_apply] at hs
        exact ((hsub _ (phi_mem a _ y)).2 y rfl).1 hs
      · intro hG
        refine ⟨(R.fibers a (R.witness S π)).equivFin ⟨R.phi a _ y, phi_mem a _ y⟩,
          (hpart.2.2.2 y _).2 rfl, ?_⟩
        simp only [Equiv.symm_apply_apply]
        exact ((hsub _ (phi_mem a _ y)).2 y rfl).2 hG


/-! ## The root (Lemma 5.6) -/

variable (R) in
/-- The context of the root, for a tree equal to the root's. -/
def ctxOfEq {T : DTree X U} (h : R.tree = T) : R.Ctx T where
  out := fun _ => True
  iface := ∅
  iface_sub := Finset.empty_subset _
  out_dep := fun _ _ _ => Iff.rfl
  split := fun ν => by
    rw [h]
    exact ⟨fun hν => ⟨hν, trivial⟩, fun hν => hν.1⟩
  inputs := fun x hx => absurd (h ▸ R.allVars x) hx

variable (R) in
/-- τ_v ∈ R^v in Lemma 5.6. -/
def RootCompat (B : Finset U) (L : (U → Bool) → Prop) (a : DTree X U) (y : X) (v : Bool)
    (τ : Bool → U → Bool) : Prop :=
  ∃ σ, L σ ∧ R.acc σ ∧ (R.inp y ∈ B → σ (R.inp y) = v) ∧ Agree (a.bag R.inp ∩ B) (τ v) σ

open Classical in
variable (R) in
/-- The sub of a fiber at the root: ⊤, y, ¬y, or ⊥. -/
noncomputable def rootSub (B : Finset U) (L : (U → Bool) → Prop) (a : DTree X U) (y : X)
    (τ : Bool → U → Bool) : Sdd (.leaf y : DTree X U) :=
  if R.RootCompat B L a y true τ then
    (if R.RootCompat B L a y false τ then .const true else .lit y true)
  else (if R.RootCompat B L a y false τ then .lit y false else .const false)

omit [Fintype X] [Fintype U] in
theorem rootSub_sat (B : Finset U) (L : (U → Bool) → Prop) (a : DTree X U) (y : X)
    (τ : Bool → U → Bool) (w : X → Bool) :
    (R.rootSub B L a y τ).Sat w ↔ R.RootCompat B L a y (w y) τ := by
  unfold rootSub
  cases hw : w y <;> by_cases h₁ : R.RootCompat B L a y true τ <;>
    by_cases h₀ : R.RootCompat B L a y false τ <;> simp_all [Sdd.Sat]

/-- The witnesses w_v at the root: y = v and every other input 0. -/
def rootWitness (y : X) : Bool → X → Bool := fun v x => if x = y then v else false

variable (R) in
/-- The root decision node (proof of Theorem 5.1). -/
noncomputable def buildRoot (B : Finset U) (L : (U → Bool) → Prop) (a : DTree X U) (y : X) :
    Sdd (.node B L a (.leaf y)) :=
  let P := R.fibers a (rootWitness y)
  .dec P.card (fun k => R.build a (a.bag R.inp) (P.equivFin.symm k).1)
    (fun k => R.rootSub B L a y (P.equivFin.symm k).1)

omit [Fintype X] [Fintype U] in
/-- Lemma 5.6. -/
theorem rootCompat_iff {B : Finset U} {L : (U → Bool) → Prop} {a : DTree X U} {y : X}
    (h : R.tree = .node B L a (.leaf y)) (w : X → Bool) :
    R.RootCompat B L a y (w y) (R.phi a (rootWitness y) w) ↔ R.f w := by
  have hwf : (DTree.node B L a (.leaf y)).WF R.inp := h ▸ R.wf
  have c := R.ctxOfEq h
  have hwf' := hwf
  obtain ⟨-, -, -, -, -, ha, -⟩ := hwf'
  have hupd : upd a (rootWitness y (w y)) w = w := by
    funext x
    by_cases hx : x ∈ a.vars
    · exact upd_vars _ _ hx
    · rw [upd_not_vars _ _ hx]
      have hxy : x = y := by
        have := h ▸ R.allVars x
        simp only [DTree.vars, Finset.mem_union, Finset.mem_singleton] at this
        tauto
      subst hxy
      simp [rootWitness]
  have hphi : R.phi a (rootWitness y) w (w y) = canon (a.bag R.inp) (R.sol w) := by
    simp only [phi, hupd]
  constructor
  · rintro ⟨σ, hL, hacc, hσy, hτσ⟩
    have hQ : Q R.inp (.node B L a (.leaf y)) σ w := by
      rw [q_node_iff hwf]
      refine ⟨hL, ⟨_, hτσ, ?_⟩, ⟨fun _ => w y, fun u hu => ?_, ?_⟩⟩
      · rw [hphi, q_congr_state (canon_agree _ _)]
        exact R.q_sol (c.left hwf) w
      · simp only [DTree.bag, Finset.mem_inter, Finset.mem_singleton] at hu
        obtain ⟨rfl, hu⟩ := hu
        exact (hσy hu).symm
      · exact (q_leaf_iff y _ w).2 rfl
    have hrep := R.replace (R.ctxOfEq h) hwf w w σ hQ (fun _ hu => absurd hu (Finset.notMem_empty _))
    have hww : upd (.node B L a (.leaf y)) w w = w := by
      funext x
      by_cases hx : x ∈ (DTree.node B L a (.leaf y)).vars <;> simp [upd, hx]
    rw [hww] at hrep
    unfold f
    rw [R.accDep (R.sol w) σ (by rw [h]; exact hrep)]
    exact hacc
  · intro hf
    have hall := R.sol_allRel w
    rw [h] at hall
    refine ⟨R.sol w, hall.1, hf, fun _ => R.sol_inputs w y, ?_⟩
    rw [hphi]
    exact (canon_agree _ _).mono Finset.inter_subset_left

/-- The root node is a valid SDD computing f. -/
theorem buildRoot_correct {B : Finset U} {L : (U → Bool) → Prop} {a : DTree X U} {y : X}
    (h : R.tree = .node B L a (.leaf y)) (hsh : Shape R.inp R.tree) :
    (R.buildRoot B L a y).Valid ∧ ∀ w, (R.buildRoot B L a y).Sat w ↔ R.f w := by
  have hwf : (DTree.node B L a (.leaf y)).WF R.inp := h ▸ R.wf
  have hwf' := hwf
  obtain ⟨-, -, -, -, -, ha, -⟩ := hwf'
  rw [h] at hsh
  have hpart := fibers_partition ((R.ctxOfEq h).left hwf) ha hsh.1 (rootWitness y)
    (build_correct a)
  refine ⟨⟨hpart.1, fun _ => ?_, hpart.2.1, hpart.2.2.1⟩, fun w => ?_⟩
  · unfold rootSub
    dsimp only
    split_ifs <;> trivial
  · show (∃ k, _ ∧ _) ↔ _
    rw [← rootCompat_iff h w]
    constructor
    · rintro ⟨k, hp, hs⟩
      have hk := (hpart.2.2.2 w k).1 hp
      subst hk
      simp only [Equiv.symm_apply_apply] at hs
      exact (rootSub_sat B L a y _ w).1 hs
    · intro hc
      refine ⟨(R.fibers a (rootWitness y)).equivFin ⟨R.phi a _ w, phi_mem a _ w⟩,
        (hpart.2.2.2 w _).2 rfl, ?_⟩
      simp only [Equiv.symm_apply_apply]
      exact (rootSub_sat B L a y _ w).2 hc


/-! ## Counting (the size bound of Theorem 5.1) -/

open Classical in
theorem build_node_eq (B : Finset U) (L : (U → Bool) → Prop) (a b : DTree X U) (S : Finset U)
    (π : Bool → U → Bool) :
    R.build (.node B L a b) S π =
      .dec (R.fibers a (R.witness S π)).card
        (fun k => R.build a (a.bag R.inp) ((R.fibers a (R.witness S π)).equivFin.symm k).1)
        (fun k => if R.Compat B L a S π ((R.fibers a (R.witness S π)).equivFin.symm k).1 then
            R.build b (b.bag R.inp ∩ B) (fun i => canon (b.bag R.inp ∩ B) (π i))
          else .const false) := by
  rw [build]

theorem decNodes_build_leaf (x : X) (S : Finset U) (π : Bool → U → Bool) :
    (R.build (.leaf x) S π).decNodes = ∅ := by
  unfold build
  split_ifs <;> rfl

/-- Valuations of S, extended by false. -/
def ext (S : Finset U) (g : Bool → S → Bool) : Bool → U → Bool :=
  fun i u => if hu : u ∈ S then g i ⟨u, hu⟩ else false

omit [DecidableEq X] [Fintype X] [Fintype U] in
theorem exists_ext {S : Finset U} {π : Bool → U → Bool} (h : ∀ i, canon S (π i) = π i) :
    ∃ g, ext S g = π := by
  refine ⟨fun i u => π i u, ?_⟩
  funext i u
  by_cases hu : u ∈ S
  · simp [ext, hu]
  · rw [← h i]
    simp [ext, canon, hu]

variable (R) in
/-- Every pair cell or join node that the construction can create below t. -/
noncomputable def idents : DTree X U → Finset U → Set (Σ t : DTree X U, Sdd t)
  | .leaf _, _ => ∅
  | .node B L a b, S =>
      Set.range (fun g : Bool → S → Bool =>
        (⟨.node B L a b, R.build (.node B L a b) S (ext S g)⟩ : Σ t : DTree X U, Sdd t)) ∪
      idents a (a.bag R.inp) ∪ idents b (b.bag R.inp ∩ B)

theorem fibers_canon {a : DTree X U} {w : Bool → X → Bool} {τ : Bool → U → Bool}
    (hτ : τ ∈ R.fibers a w) (i : Bool) : canon (a.bag R.inp) (τ i) = τ i := by
  obtain ⟨y, rfl⟩ := mem_fibers hτ
  exact phi_canon a w y i

theorem decNodes_build : ∀ (t : DTree X U) (S : Finset U) (π : Bool → U → Bool),
    (∀ i, canon S (π i) = π i) → (R.build t S π).decNodes ⊆ R.idents t S
  | .leaf x, S, π, _ => by
      rw [decNodes_build_leaf]
      exact Set.empty_subset _
  | .node B L a b, S, π, hπ => by
      intro d hd
      rw [build_node_eq] at hd
      simp only [Sdd.decNodes, Set.mem_insert_iff, Set.mem_iUnion, Set.mem_union] at hd
      rcases hd with rfl | ⟨k, hk | hk⟩
      · left
        left
        obtain ⟨g, hg⟩ := exists_ext hπ
        refine ⟨g, ?_⟩
        dsimp only
        rw [hg, build_node_eq]
      · left
        right
        exact decNodes_build a _ _ (fibers_canon ((R.fibers a _).equivFin.symm k).2) hk
      · by_cases hc : R.Compat B L a S π ((R.fibers a (R.witness S π)).equivFin.symm k).1
        · simp only [hc, if_true] at hk
          right
          exact decNodes_build b _ _ (fun i => canon_canon _ _) hk
        · simp only [hc, if_false, Sdd.decNodes, Set.mem_empty_iff_false] at hk

theorem idents_finite : ∀ (t : DTree X U) (S : Finset U), (R.idents t S).Finite
  | .leaf _, _ => Set.finite_empty
  | .node _ _ a b, _ =>
      ((Set.finite_range _).union (idents_finite a _)).union (idents_finite b _)

/-- The bound on the number of pair cell and join nodes below t. -/
def count (inp : X → U) : DTree X U → Finset U → ℕ
  | .leaf _, _ => 0
  | .node B _ a b, S => (2 ^ S.card) ^ 2 + count inp a (a.bag inp) + count inp b (b.bag inp ∩ B)

omit [Fintype U] in
theorem card_fun_pair (S : Finset U) : Nat.card (Bool → S → Bool) = (2 ^ S.card) ^ 2 := by
  rw [Nat.card_eq_fintype_card, Fintype.card_fun, Fintype.card_fun, Fintype.card_bool,
    Fintype.card_coe]

theorem idents_ncard : ∀ (t : DTree X U) (S : Finset U), (R.idents t S).ncard ≤ count R.inp t S
  | .leaf _, _ => by simp [idents, count]
  | .node B L a b, S => by
      unfold idents count
      have hrange : (Set.range (fun g : Bool → S → Bool =>
          (⟨.node B L a b, R.build (.node B L a b) S (ext S g)⟩ : Σ t : DTree X U, Sdd t))).ncard
          ≤ (2 ^ S.card) ^ 2 := by
        rw [← Set.image_univ, ← card_fun_pair S, ← Set.ncard_univ]
        exact Set.ncard_image_le Set.finite_univ
      calc _ ≤ _ := Set.ncard_union_le _ _
        _ ≤ _ := Nat.add_le_add_right (Set.ncard_union_le _ _) _
        _ ≤ _ := Nat.add_le_add (Nat.add_le_add hrange (idents_ncard a _)) (idents_ncard b _)

/-- Every bag of an internal node has at most b vertices. -/
def Bounded (inp : X → U) (b : ℕ) : DTree X U → Prop
  | .leaf _ => True
  | .node B _ l r => B.card ≤ b ∧ Bounded inp b l ∧ Bounded inp b r

/-- The number of internal nodes. -/
def internalCount : DTree X U → ℕ
  | .leaf _ => 0
  | .node _ _ l r => 1 + internalCount l + internalCount r

omit [Fintype X] [Fintype U] in
theorem bag_card_le {b : ℕ} (hb1 : 1 ≤ b) : ∀ (t : DTree X U), Bounded R.inp b t →
    (t.bag R.inp).card ≤ b
  | .leaf _, _ => by simpa [DTree.bag] using hb1
  | .node _ _ _ _, h => h.1

omit [Fintype X] [Fintype U] in
theorem count_le {b : ℕ} (hb1 : 1 ≤ b) : ∀ (t : DTree X U) (S : Finset U), Bounded R.inp b t →
    S.card ≤ b → count R.inp t S ≤ internalCount t * (2 ^ b) ^ 2
  | .leaf _, _, _, _ => by simp [count]
  | .node B _ a b', S, ⟨hB, ha, hb'⟩, hS => by
      have h₁ : (2 ^ S.card) ^ 2 ≤ (2 ^ b) ^ 2 :=
        Nat.pow_le_pow_left (Nat.pow_le_pow_right Nat.zero_lt_two hS) 2
      have h₂ := count_le hb1 a (a.bag R.inp) ha (bag_card_le hb1 a ha)
      have h₃ := count_le hb1 b' (b'.bag R.inp ∩ B) hb'
        ((Finset.card_le_card Finset.inter_subset_left).trans (bag_card_le hb1 b' hb'))
      simp only [count, internalCount]
      nlinarith

theorem fibers_card_le (a : DTree X U) (w : Bool → X → Bool) :
    (R.fibers a w).card ≤ (2 ^ (a.bag R.inp).card) ^ 2 := by
  classical
  have hsub : R.fibers a w ⊆ (Finset.univ : Finset (Bool → a.bag R.inp → Bool)).image
      (ext (a.bag R.inp)) := by
    intro τ hτ
    obtain ⟨g, hg⟩ := exists_ext (fibers_canon hτ)
    exact Finset.mem_image.2 ⟨g, Finset.mem_univ _, hg⟩
  calc _ ≤ _ := Finset.card_le_card hsub
    _ ≤ _ := Finset.card_image_le
    _ = _ := by
      rw [Finset.card_univ, Fintype.card_fun, Fintype.card_fun, Fintype.card_bool,
        Fintype.card_coe]

theorem idents_elems {b : ℕ} (hb1 : 1 ≤ b) : ∀ (t : DTree X U) (S : Finset U),
    Bounded R.inp b t → ∀ d ∈ R.idents t S, d.2.elems ≤ (2 ^ b) ^ 2
  | .leaf _, _, _, _, hd => absurd hd (Set.notMem_empty _)
  | .node B L a b', S, ⟨_, ha, hb'⟩, d, hd => by
      unfold idents at hd
      rcases hd with (⟨g, rfl⟩ | hd) | hd
      · dsimp only
        rw [build_node_eq]
        exact (fibers_card_le a _).trans
          (Nat.pow_le_pow_left (Nat.pow_le_pow_right Nat.zero_lt_two (bag_card_le hb1 a ha)) 2)
      · exact idents_elems hb1 a _ ha d hd
      · exact idents_elems hb1 b' _ hb' d hd


theorem decNodes_buildRoot (B : Finset U) (L : (U → Bool) → Prop) (a : DTree X U) (y : X) :
    (R.buildRoot B L a y).decNodes ⊆ insert ⟨_, R.buildRoot B L a y⟩ (R.idents a (a.bag R.inp)) := by
  intro d hd
  unfold buildRoot at hd ⊢
  simp only [Sdd.decNodes, Set.mem_insert_iff, Set.mem_iUnion, Set.mem_union] at hd
  rcases hd with rfl | ⟨k, hk | hk⟩
  · exact Set.mem_insert _ _
  · exact Set.mem_insert_of_mem _
      (decNodes_build a _ _ (fibers_canon ((R.fibers a _).equivFin.symm k).2) hk)
  · exfalso
    unfold rootSub at hk
    split_ifs at hk <;> simp [Sdd.decNodes] at hk

end RTD

open RTD

/-- **Theorem 5.1.** An RTD whose root's right child is a leaf (S1) and that
satisfies (S2) at every internal right child has an SDD respecting its vtree
that computes its function. If every bag has at most b vertices, the SDD has at
most (number of internal nodes)·4^b distinct decision nodes, each with at most
4^b elements, so its size is at most (number of internal nodes)·16^b. -/
theorem sdd_of_rtd (R : RTD X U) [Fintype X] [Fintype U] {B : Finset U}
    {L : (U → Bool) → Prop} {a : DTree X U} {y : X} (h : R.tree = .node B L a (.leaf y))
    (hsh : Shape R.inp R.tree) {b : ℕ} (hb1 : 1 ≤ b) (hb : Bounded R.inp b R.tree) :
    ∃ S : Sdd R.tree, S.Valid ∧ (∀ w, S.Sat w ↔ R.f w) ∧ ∃ hfin : S.decNodes.Finite,
      S.decNodes.ncard ≤ internalCount R.tree * (2 ^ b) ^ 2 ∧
      (∀ d ∈ S.decNodes, d.2.elems ≤ (2 ^ b) ^ 2) ∧
      ∑ d ∈ hfin.toFinset, d.2.elems ≤ internalCount R.tree * (2 ^ b) ^ 2 * (2 ^ b) ^ 2 := by
  have hcorrect := buildRoot_correct h hsh
  rw [h] at hb ⊢
  obtain ⟨-, ha, -⟩ := hb
  let S := R.buildRoot B L a y
  have hsub := decNodes_buildRoot (R := R) B L a y
  have hfin : S.decNodes.Finite := ((idents_finite a _).insert _).subset hsub
  have hM : 1 ≤ (2 ^ b) ^ 2 := Nat.one_le_pow _ _ (Nat.pow_pos Nat.zero_lt_two)
  have hcard : S.decNodes.ncard ≤ internalCount (DTree.node B L a (.leaf y)) * (2 ^ b) ^ 2 := by
    calc S.decNodes.ncard ≤ (insert ⟨_, S⟩ (R.idents a (a.bag R.inp))).ncard :=
          Set.ncard_le_ncard hsub ((idents_finite a _).insert _)
      _ ≤ (R.idents a (a.bag R.inp)).ncard + 1 := Set.ncard_insert_le _ _
      _ ≤ count R.inp a (a.bag R.inp) + 1 := Nat.add_le_add_right (idents_ncard a _) _
      _ ≤ internalCount a * (2 ^ b) ^ 2 + 1 :=
          Nat.add_le_add_right (count_le hb1 a _ ha (bag_card_le hb1 a ha)) _
      _ ≤ _ := by simp only [internalCount]; nlinarith
  have helems : ∀ d ∈ S.decNodes, d.2.elems ≤ (2 ^ b) ^ 2 := by
    intro d hd
    rcases hsub hd with rfl | hd
    · exact (fibers_card_le a _).trans
        (Nat.pow_le_pow_left (Nat.pow_le_pow_right Nat.zero_lt_two (bag_card_le hb1 a ha)) 2)
    · exact idents_elems hb1 a _ ha d hd
  refine ⟨S, hcorrect.1, hcorrect.2, hfin, hcard, helems, ?_⟩
  calc ∑ d ∈ hfin.toFinset, d.2.elems ≤ hfin.toFinset.card • (2 ^ b) ^ 2 :=
        Finset.sum_le_card_nsmul _ _ _ fun d hd => helems d ((Set.Finite.mem_toFinset hfin).1 hd)
    _ = S.decNodes.ncard * (2 ^ b) ^ 2 := by
        rw [nsmul_eq_mul, Nat.cast_id, Set.ncard_eq_toFinset_card _ hfin]
    _ ≤ _ := Nat.mul_le_mul_right _ hcard


/-! ## Leaf donation (Lemma 6.1, a variant) -/

namespace DTree

/-- The rightmost input below a node. -/
def rightmost : DTree X U → X
  | leaf x => x
  | node _ _ _ r => r.rightmost

omit [DecidableEq X] [DecidableEq U] in
theorem rightmost_mem [DecidableEq X] : ∀ t : DTree X U, t.rightmost ∈ t.vars
  | leaf x => by simp [rightmost, vars]
  | node _ _ _ r => by
      simp only [rightmost, vars, Finset.mem_union]
      exact Or.inr (rightmost_mem r)

variable (inp : X → U)

/-- Step 2 of Lemma 6.1: the structure S(w), with the relation and bag of a
cherry that still have to be placed above. -/
def donate : DTree X U → Option (DTree X U) × ((U → Bool) → Prop) × Finset U
  | leaf _ => (none, fun _ => True, ∅)
  | node B L a b =>
      let y := a.rightmost
      let bag₁ := B ∪ {inp y, inp b.rightmost} ∪ (donate a).2.2 ∪ (donate b).2.2
      let rel₁ : (U → Bool) → Prop := fun ν => L ν ∧ (donate a).2.1 ν ∧ (donate b).2.1 ν
      match (donate a).1, (donate b).1 with
      | some A, some B' =>
          (some (node bag₁ rel₁ A (node bag₁ (fun _ => True) B' (leaf y))), fun _ => True, ∅)
      | none, some B' => (some (node bag₁ rel₁ B' (leaf y)), fun _ => True, ∅)
      | some A, none => (some (node bag₁ rel₁ A (leaf y)), fun _ => True, ∅)
      | none, none => (some (leaf y), L, B)

/-- The vtree of Lemma 6.1. -/
def donated (t : DTree X U) : DTree X U :=
  match donate inp t with
  | (some S, P, BP) => node (t.bag inp ∪ {inp t.rightmost} ∪ BP) P S (leaf t.rightmost)
  | (none, _, _) => t



/-- What Step 2 of Lemma 6.1 guarantees for an internal node w with image S. -/
structure Spec (b : ℕ) (w S : DTree X U) (P : (U → Bool) → Prop) (BP : Finset U) : Prop where
  vars_eq : S.vars = w.vars.erase w.rightmost
  ins_sub : S.ins inp ⊆ w.ins inp
  allRel : ∀ ν, S.AllRel ν ∧ P ν ↔ w.AllRel ν
  pdep : ∀ ν ν' : U → Bool, (∀ u ∈ BP, ν u = ν' u) → (P ν ↔ P ν')
  bp_sub : BP ⊆ w.bag inp
  wf : S.WF inp
  shape : Shape inp S
  bounded : RTD.Bounded inp (3 * b + 2) S
  top : (∃ x, S = leaf x) ∨ (w.bag inp ∪ {inp w.rightmost} ⊆ S.bag inp ∧ BP = ∅)

theorem spec_part {b : ℕ} {c S : DTree X U} {P : (U → Bool) → Prop} {BP : Finset U}
    (h : Spec inp b c S P BP) (M : Finset U)
    (hM : ∀ u ∈ M, u ∈ c.ins inp → u ∈ c.bag inp ∨ u = inp c.rightmost) :
    S.ins inp ∩ M ⊆ S.bag inp := by
  intro u hu
  obtain ⟨huS, huM⟩ := Finset.mem_inter.1 hu
  rcases h.top with ⟨x, rfl⟩ | ⟨htop, -⟩
  · exact huS
  · rcases hM u huM (h.ins_sub huS) with h' | h'
    · exact htop (Finset.mem_union_left _ h')
    · exact htop (Finset.mem_union_right _ (by simp [h']))


omit [DecidableEq X] in
theorem donate_leaf (x : X) :
    donate inp (leaf x : DTree X U) = (none, fun _ => True, ∅) := rfl

/-- The facts H1 and H2 used for the separation conditions at the new nodes. -/
theorem bag₁_part {B : Finset U} {L : (U → Bool) → Prop} {a c : DTree X U}
    (hwf : (node B L a c).WF inp) {BPa BPc : Finset U} (ha : BPa ⊆ a.bag inp)
    (hc : BPc ⊆ c.bag inp) :
    (∀ u ∈ B ∪ {inp a.rightmost, inp c.rightmost} ∪ BPa ∪ BPc, u ∈ a.ins inp →
      u ∈ a.bag inp ∨ u = inp a.rightmost) ∧
    (∀ u ∈ B ∪ {inp a.rightmost, inp c.rightmost} ∪ BPa ∪ BPc, u ∈ c.ins inp →
      u ∈ c.bag inp ∨ u = inp c.rightmost) := by
  obtain ⟨-, -, hac, haB, hcB, -, -⟩ := hwf
  have hya : inp a.rightmost ∈ a.ins inp := input_mem_ins inp a _ (rightmost_mem a)
  have hzc : inp c.rightmost ∈ c.ins inp := input_mem_ins inp c _ (rightmost_mem c)
  have hBa : ∀ u, u ∈ a.ins inp → u ∈ c.ins inp → u ∈ a.bag inp := fun u h₁ h₂ =>
    haB (Finset.mem_inter.2 ⟨h₁, hac (Finset.mem_inter.2 ⟨h₁, h₂⟩)⟩)
  have hBc : ∀ u, u ∈ a.ins inp → u ∈ c.ins inp → u ∈ c.bag inp := fun u h₁ h₂ =>
    hcB (Finset.mem_inter.2 ⟨h₂, hac (Finset.mem_inter.2 ⟨h₁, h₂⟩)⟩)
  constructor
  · intro u hu hua
    simp only [Finset.mem_union, Finset.mem_insert, Finset.mem_singleton] at hu
    rcases hu with ((hu | hu | hu) | hu) | hu
    · exact Or.inl (haB (Finset.mem_inter.2 ⟨hua, hu⟩))
    · exact Or.inr hu
    · exact Or.inl (hBa u hua (hu ▸ hzc))
    · exact Or.inl (ha hu)
    · exact Or.inl (hBa u hua (bag_subset_ins inp c (hc hu)))
  · intro u hu huc
    simp only [Finset.mem_union, Finset.mem_insert, Finset.mem_singleton] at hu
    rcases hu with ((hu | hu | hu) | hu) | hu
    · exact Or.inl (hcB (Finset.mem_inter.2 ⟨huc, hu⟩))
    · exact Or.inl (hBc u (hu ▸ hya) huc)
    · exact Or.inr hu
    · exact Or.inl (hBc u (bag_subset_ins inp a (ha hu)) huc)
    · exact Or.inl (hc hu)


theorem card_bag₁_le {B BPa BPc : Finset U} {p q : U} {b : ℕ} (hB : B.card ≤ b)
    (ha : BPa.card ≤ b) (hc : BPc.card ≤ b) :
    (B ∪ {p, q} ∪ BPa ∪ BPc).card ≤ 3 * b + 2 := by
  have h₁ := Finset.card_union_le (B ∪ {p, q} ∪ BPa) BPc
  have h₂ := Finset.card_union_le (B ∪ {p, q}) BPa
  have h₃ := Finset.card_union_le B {p, q}
  have h₄ : ({p, q} : Finset U).card ≤ 2 := Finset.card_le_two
  omega

theorem bag₁_sub_ins {B : Finset U} {L : (U → Bool) → Prop} {a c : DTree X U} {BPa BPc : Finset U}
    (ha : BPa ⊆ a.bag inp) (hc : BPc ⊆ c.bag inp) :
    B ∪ {inp a.rightmost, inp c.rightmost} ∪ BPa ∪ BPc ⊆ (node B L a c).ins inp := by
  intro u hu
  have hya : inp a.rightmost ∈ a.ins inp := input_mem_ins inp a _ (rightmost_mem a)
  have hzc : inp c.rightmost ∈ c.ins inp := input_mem_ins inp c _ (rightmost_mem c)
  simp only [Finset.mem_union, Finset.mem_insert, Finset.mem_singleton] at hu
  simp only [ins, Finset.mem_union]
  rcases hu with ((hu | rfl | rfl) | hu) | hu
  · exact Or.inl (Or.inl hu)
  · exact Or.inl (Or.inr hya)
  · exact Or.inr hzc
  · exact Or.inl (Or.inr (bag_subset_ins inp a (ha hu)))
  · exact Or.inr (bag_subset_ins inp c (hc hu))

/-- Step 2 of Lemma 6.1: the invariant of `donate` at internal nodes. -/
theorem donate_spec (b : ℕ) : ∀ (w : DTree X U), w.WF inp → RTD.Bounded inp b w →
    (∀ x, w ≠ leaf x) →
    ∃ S, (donate inp w).1 = some S ∧ Spec inp b w S (donate inp w).2.1 (donate inp w).2.2
  | leaf x, _, _, h => absurd rfl (h x)
  | node B L (leaf y) (leaf z), hwf, hb, _ => by
      obtain ⟨hL, hdisj, -, -, -, -, -⟩ := hwf
      have hyz : y ≠ z := fun h => Finset.disjoint_left.1 hdisj (by simp [vars] : y ∈ (leaf y : DTree X U).vars)
        (by simp [vars, h])
      refine ⟨leaf y, rfl, ?_⟩
      exact {
        vars_eq := by
          ext x
          simp only [vars, rightmost, Finset.mem_singleton, Finset.mem_erase, Finset.mem_union]
          constructor
          · rintro rfl
            exact ⟨hyz, Or.inl rfl⟩
          · rintro ⟨hx, hx' | hx'⟩
            · exact hx'
            · exact absurd hx' hx
        ins_sub := by
          intro u hu
          simp only [ins, Finset.mem_singleton] at hu
          simp [ins, hu]
        allRel := fun ν => by simp [AllRel, donate]
        pdep := hL
        bp_sub := subset_refl _
        wf := trivial
        shape := trivial
        bounded := trivial
        top := Or.inl ⟨y, rfl⟩ }
  | node B L (leaf y) (node Bc Lc c₁ c₂), hwf, hb, _ => by
      have hwf' := hwf
      obtain ⟨hL, hdisj, hac, haB, hcB, -, hwfc⟩ := hwf'
      obtain ⟨hB, -, hbc⟩ := hb
      obtain ⟨C, hC, sC⟩ := donate_spec b (node Bc Lc c₁ c₂) hwfc hbc (fun _ h => by cases h)
      set c := node Bc Lc c₁ c₂ with hc
      set bag₁ := B ∪ {inp y, inp c.rightmost} ∪ ∅ ∪ (donate inp c).2.2 with hbag₁
      set rel₁ : (U → Bool) → Prop := fun ν => L ν ∧ True ∧ (donate inp c).2.1 ν with hrel₁
      have hd : donate inp (node B L (leaf y) c) =
          (some (node bag₁ rel₁ C (leaf y)), fun _ => True, ∅) := by
        simp only [donate]
        rw [hC]
        rfl
      rw [hd]
      have hyc : y ∉ c.vars := fun h => Finset.disjoint_left.1 hdisj (by simp [vars]) h
      have hzc : c.rightmost ∈ c.vars := rightmost_mem c
      have hparts := bag₁_part inp hwf (BPa := ∅) (Finset.empty_subset _) sC.bp_sub
      refine ⟨_, rfl, ?_⟩
      exact {
        vars_eq := by
          simp only [vars, rightmost]
          rw [sC.vars_eq]
          ext x
          simp only [Finset.mem_union, Finset.mem_erase, Finset.mem_singleton]
          constructor
          · rintro (⟨hx, hx'⟩ | rfl)
            · exact ⟨hx, Or.inr hx'⟩
            · exact ⟨fun h => hyc (h ▸ hzc), Or.inl rfl⟩
          · rintro ⟨hx, rfl | hx'⟩
            · exact Or.inr rfl
            · exact Or.inl ⟨hx, hx'⟩
        ins_sub := by
          intro u hu
          simp only [ins, Finset.mem_union, Finset.mem_singleton] at hu
          rcases hu with (hu | hu) | rfl
          · exact bag₁_sub_ins inp (Finset.empty_subset _) sC.bp_sub hu
          · simp only [ins, Finset.mem_union]
            exact Or.inr (sC.ins_sub hu)
          · simp [ins]
        allRel := fun ν => by
          simp only [AllRel, rel₁, and_true, true_and]
          rw [← sC.allRel ν]
          tauto
        pdep := fun _ _ _ => Iff.rfl
        bp_sub := Finset.empty_subset _
        wf := by
          refine ⟨fun ν ν' h => ?_, ?_, ?_, ?_, ?_, sC.wf, trivial⟩
          · simp only [rel₁]
            rw [hL ν ν' fun u hu => h u (by simp [bag₁, hu]),
              sC.pdep ν ν' fun u hu => h u (by simp [bag₁, hu])]
          · rw [sC.vars_eq]
            simp only [vars, Finset.disjoint_singleton_right, Finset.mem_erase, not_and]
            exact fun _ h => hyc h
          · intro u hu
            simp only [ins, Finset.mem_inter, Finset.mem_singleton] at hu
            rw [hu.2]
            simp [bag₁]
          · exact spec_part inp sC bag₁ hparts.2
          · intro u hu
            simp only [ins, Finset.mem_inter, Finset.mem_singleton] at hu
            simp [bag, hu.1]
        shape := ⟨sC.shape, trivial, trivial⟩
        bounded := ⟨card_bag₁_le hB (by simp) ((Finset.card_le_card sC.bp_sub).trans hbc.1),
          sC.bounded, trivial⟩
        top := Or.inr ⟨by
          intro u hu
          simp only [bag, rightmost, Finset.mem_union, Finset.mem_singleton] at hu
          rcases hu with hu | rfl
          · simp [bag, bag₁, hu]
          · simp [bag, bag₁, c], rfl⟩ }
  | node B L (node Ba La a₁ a₂) (leaf z), hwf, hb, _ => by
      have hwf' := hwf
      obtain ⟨hL, hdisj, hac, haB, hcB, hwfa, -⟩ := hwf'
      obtain ⟨hB, hba, -⟩ := hb
      obtain ⟨A, hA, sA⟩ := donate_spec b (node Ba La a₁ a₂) hwfa hba (fun _ h => by cases h)
      set a := node Ba La a₁ a₂ with ha
      set bag₁ := B ∪ {inp a.rightmost, inp z} ∪ (donate inp a).2.2 ∪ ∅ with hbag₁
      set rel₁ : (U → Bool) → Prop := fun ν => L ν ∧ (donate inp a).2.1 ν ∧ True with hrel₁
      have hd : donate inp (node B L a (leaf z)) =
          (some (node bag₁ rel₁ A (leaf a.rightmost)), fun _ => True, ∅) := by
        simp only [donate]
        rw [hA]
        rfl
      rw [hd]
      have hza : z ∉ a.vars := fun h => Finset.disjoint_right.1 hdisj (by simp [vars]) h
      have hya : a.rightmost ∈ a.vars := rightmost_mem a
      have hparts := bag₁_part inp hwf (BPc := ∅) sA.bp_sub (Finset.empty_subset _)
      refine ⟨_, rfl, ?_⟩
      exact {
        vars_eq := by
          simp only [vars, rightmost]
          rw [sA.vars_eq]
          ext x
          simp only [Finset.mem_union, Finset.mem_erase, Finset.mem_singleton]
          constructor
          · rintro (⟨hx, hx'⟩ | rfl)
            · exact ⟨fun h => hza (h ▸ hx'), Or.inl hx'⟩
            · exact ⟨fun h => hza (h ▸ hya), Or.inl hya⟩
          · rintro ⟨hx, hx' | rfl⟩
            · by_cases hxy : x = a.rightmost
              · exact Or.inr hxy
              · exact Or.inl ⟨hxy, hx'⟩
            · exact absurd rfl hx
        ins_sub := by
          intro u hu
          simp only [ins, Finset.mem_union, Finset.mem_singleton] at hu
          rcases hu with (hu | hu) | rfl
          · exact bag₁_sub_ins inp sA.bp_sub (Finset.empty_subset _) hu
          · simp only [ins, Finset.mem_union]
            exact Or.inl (Or.inr (sA.ins_sub hu))
          · simp only [ins, Finset.mem_union]
            exact Or.inl (Or.inr (input_mem_ins inp a _ hya))
        allRel := fun ν => by
          simp only [AllRel, rel₁, and_true]
          rw [← sA.allRel ν]
          tauto
        pdep := fun _ _ _ => Iff.rfl
        bp_sub := Finset.empty_subset _
        wf := by
          refine ⟨fun ν ν' h => ?_, ?_, ?_, ?_, ?_, sA.wf, trivial⟩
          · simp only [rel₁]
            rw [hL ν ν' fun u hu => h u (by simp [bag₁, hu]),
              sA.pdep ν ν' fun u hu => h u (by simp [bag₁, hu])]
          · rw [sA.vars_eq]
            simp only [vars, Finset.disjoint_singleton_right, Finset.mem_erase, not_and]
            exact fun h => absurd rfl h
          · intro u hu
            simp only [ins, Finset.mem_inter, Finset.mem_singleton] at hu
            rw [hu.2]
            simp [bag₁]
          · exact spec_part inp sA bag₁ hparts.1
          · intro u hu
            simp only [ins, Finset.mem_inter, Finset.mem_singleton] at hu
            simp [bag, hu.1]
        shape := ⟨sA.shape, trivial, trivial⟩
        bounded := ⟨card_bag₁_le hB ((Finset.card_le_card sA.bp_sub).trans hba.1) (by simp),
          sA.bounded, trivial⟩
        top := Or.inr ⟨by
          intro u hu
          simp only [bag, rightmost, Finset.mem_union, Finset.mem_singleton] at hu
          rcases hu with hu | rfl
          · simp [bag, bag₁, hu]
          · simp [bag, bag₁], rfl⟩ }
  | node B L (node Ba La a₁ a₂) (node Bc Lc c₁ c₂), hwf, hb, _ => by
      have hwf' := hwf
      obtain ⟨hL, hdisj, hac, haB, hcB, hwfa, hwfc⟩ := hwf'
      obtain ⟨hB, hba, hbc⟩ := hb
      obtain ⟨A, hA, sA⟩ := donate_spec b (node Ba La a₁ a₂) hwfa hba (fun _ h => by cases h)
      obtain ⟨C, hC, sC⟩ := donate_spec b (node Bc Lc c₁ c₂) hwfc hbc (fun _ h => by cases h)
      set a := node Ba La a₁ a₂ with ha
      set c := node Bc Lc c₁ c₂ with hc
      set bag₁ := B ∪ {inp a.rightmost, inp c.rightmost} ∪ (donate inp a).2.2 ∪
        (donate inp c).2.2 with hbag₁
      set rel₁ : (U → Bool) → Prop := fun ν => L ν ∧ (donate inp a).2.1 ν ∧ (donate inp c).2.1 ν
        with hrel₁
      have hd : donate inp (node B L a c) =
          (some (node bag₁ rel₁ A (node bag₁ (fun _ => True) C (leaf a.rightmost))),
            fun _ => True, ∅) := by
        simp only [donate]
        rw [hA, hC]
      rw [hd]
      have hya : a.rightmost ∈ a.vars := rightmost_mem a
      have hzc : c.rightmost ∈ c.vars := rightmost_mem c
      have hyc : a.rightmost ∉ c.vars := fun h => Finset.disjoint_left.1 hdisj hya h
      have hza : c.rightmost ∉ a.vars := fun h => Finset.disjoint_right.1 hdisj hzc h
      have hparts := bag₁_part inp hwf sA.bp_sub sC.bp_sub
      refine ⟨_, rfl, ?_⟩
      exact {
        vars_eq := by
          simp only [vars, rightmost]
          rw [sA.vars_eq, sC.vars_eq]
          ext x
          simp only [Finset.mem_union, Finset.mem_erase, Finset.mem_singleton]
          constructor
          · rintro (⟨hx, hx'⟩ | (⟨hx, hx'⟩ | rfl))
            · exact ⟨fun h => hza (h ▸ hx'), Or.inl hx'⟩
            · exact ⟨hx, Or.inr hx'⟩
            · exact ⟨fun h => hza (h ▸ hya), Or.inl hya⟩
          · rintro ⟨hx, hx' | hx'⟩
            · by_cases hxy : x = a.rightmost
              · exact Or.inr (Or.inr hxy)
              · exact Or.inl ⟨hxy, hx'⟩
            · exact Or.inr (Or.inl ⟨hx, hx'⟩)
        ins_sub := by
          intro u hu
          simp only [ins, Finset.mem_union, Finset.mem_singleton] at hu
          rcases hu with (hu | hu) | ((hu | hu) | rfl)
          · exact bag₁_sub_ins inp sA.bp_sub sC.bp_sub hu
          · simp only [ins, Finset.mem_union]
            exact Or.inl (Or.inr (sA.ins_sub hu))
          · exact bag₁_sub_ins inp sA.bp_sub sC.bp_sub hu
          · simp only [ins, Finset.mem_union]
            exact Or.inr (sC.ins_sub hu)
          · simp only [ins, Finset.mem_union]
            exact Or.inl (Or.inr (input_mem_ins inp a _ hya))
        allRel := fun ν => by
          simp only [AllRel, rel₁, and_true]
          rw [← sA.allRel ν, ← sC.allRel ν]
          tauto
        pdep := fun _ _ _ => Iff.rfl
        bp_sub := Finset.empty_subset _
        wf := by
          refine ⟨fun ν ν' h => ?_, ?_, ?_, ?_, ?_, sA.wf, ?_⟩
          · simp only [rel₁]
            rw [hL ν ν' fun u hu => h u (by simp [bag₁, hu]),
              sA.pdep ν ν' fun u hu => h u (by simp [bag₁, hu]),
              sC.pdep ν ν' fun u hu => h u (by simp [bag₁, hu])]
          · rw [sA.vars_eq]
            simp only [vars]
            rw [sC.vars_eq, Finset.disjoint_left]
            intro x hx hx'
            simp only [Finset.mem_erase] at hx
            simp only [Finset.mem_union, Finset.mem_erase, Finset.mem_singleton] at hx'
            rcases hx' with ⟨-, hx'⟩ | hx'
            · exact Finset.disjoint_left.1 hdisj hx.2 hx'
            · exact hx.1 hx'
          · intro u hu
            simp only [ins, Finset.mem_inter, Finset.mem_union, Finset.mem_singleton] at hu
            obtain ⟨huA, (hu | hu) | rfl⟩ := hu
            · exact hu
            · exact Finset.mem_union_left _ (Finset.mem_union_left _ (Finset.mem_union_left _
                (hac (Finset.mem_inter.2 ⟨sA.ins_sub huA, sC.ins_sub hu⟩))))
            · simp [bag₁]
          · exact spec_part inp sA bag₁ hparts.1
          · intro u hu
            exact (Finset.mem_inter.1 hu).2
          · refine ⟨fun _ _ _ => Iff.rfl, ?_, ?_, ?_, ?_, sC.wf, trivial⟩
            · rw [sC.vars_eq]
              simp only [vars, Finset.disjoint_singleton_right, Finset.mem_erase, not_and]
              exact fun _ h => hyc h
            · intro u hu
              simp only [ins, Finset.mem_inter, Finset.mem_singleton] at hu
              rw [hu.2]
              simp [bag₁]
            · exact spec_part inp sC bag₁ hparts.2
            · intro u hu
              simp only [ins, Finset.mem_inter, Finset.mem_singleton] at hu
              simp [bag, hu.1]
        shape := ⟨sA.shape, ⟨sC.shape, trivial, trivial⟩, fun u hu => by
          simp only [bag, Finset.mem_inter] at hu
          exact Finset.mem_inter.2 ⟨hu.2, hu.2⟩⟩
        bounded := ⟨card_bag₁_le hB ((Finset.card_le_card sA.bp_sub).trans hba.1)
            ((Finset.card_le_card sC.bp_sub).trans hbc.1), sA.bounded,
          card_bag₁_le hB ((Finset.card_le_card sA.bp_sub).trans hba.1)
            ((Finset.card_le_card sC.bp_sub).trans hbc.1), sC.bounded, trivial⟩
        top := Or.inr ⟨by
          intro u hu
          simp only [bag, rightmost, Finset.mem_union, Finset.mem_singleton] at hu
          rcases hu with hu | rfl
          · simp [bag, bag₁, hu]
          · simp [bag, bag₁, c], rfl⟩ }


/-- What Lemma 6.1 guarantees for the new vtree. -/
theorem donated_spec {b : ℕ} (t : DTree X U) (hwf : t.WF inp) (hb : RTD.Bounded inp b t)
    (ht : ∀ x, t ≠ leaf x) :
    ∃ B L S z, t.donated inp = node B L S (leaf z) ∧ (t.donated inp).WF inp ∧
      (t.donated inp).vars = t.vars ∧ (∀ ν, (t.donated inp).AllRel ν ↔ t.AllRel ν) ∧
      Shape inp (t.donated inp) ∧ RTD.Bounded inp (3 * b + 2) (t.donated inp) ∧
      t.bag inp ⊆ (t.donated inp).bag inp := by
  obtain ⟨S, hS, sS⟩ := donate_spec inp b t hwf hb ht
  have hbag : (t.bag inp).card ≤ b := by
    cases t with
    | leaf x => exact absurd rfl (ht x)
    | node _ _ _ _ => exact hb.1
  have hd : t.donated inp = node (t.bag inp ∪ {inp t.rightmost} ∪ (donate inp t).2.2)
      (donate inp t).2.1 S (leaf t.rightmost) := by
    have h' : donate inp t = (some S, (donate inp t).2.1, (donate inp t).2.2) := by
      rw [← hS]
    unfold donated
    conv_lhs => rw [h']
  have hz := rightmost_mem t
  refine ⟨_, _, S, t.rightmost, hd, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · rw [hd]
    refine ⟨fun ν ν' h => sS.pdep ν ν' fun u hu => h u (by simp [hu]), ?_, ?_, ?_, ?_, sS.wf,
      trivial⟩
    · rw [sS.vars_eq]
      simp [vars]
    · intro u hu
      simp only [ins, Finset.mem_inter, Finset.mem_singleton] at hu
      simp [hu.2]
    · refine spec_part inp sS _ fun u hu _ => ?_
      simp only [Finset.mem_union, Finset.mem_singleton] at hu
      rcases hu with (hu | hu) | hu
      · exact Or.inl hu
      · exact Or.inr hu
      · exact Or.inl (sS.bp_sub hu)
    · intro u hu
      simp only [ins, Finset.mem_inter, Finset.mem_singleton] at hu
      simp [bag, hu.1]
  · rw [hd]
    simp only [vars]
    rw [sS.vars_eq]
    ext x
    simp only [Finset.mem_union, Finset.mem_erase, Finset.mem_singleton]
    constructor
    · rintro (⟨-, hx⟩ | rfl)
      · exact hx
      · exact hz
    · intro hx
      by_cases hxz : x = t.rightmost
      · exact Or.inr hxz
      · exact Or.inl ⟨hxz, hx⟩
  · intro ν
    rw [hd]
    simp only [AllRel, and_true]
    rw [← sS.allRel ν]
    tauto
  · rw [hd]
    exact ⟨sS.shape, trivial, trivial⟩
  · rw [hd]
    refine ⟨?_, sS.bounded, trivial⟩
    have h₁ := Finset.card_union_le (t.bag inp ∪ {inp t.rightmost}) (donate inp t).2.2
    have h₂ := Finset.card_union_le (t.bag inp) {inp t.rightmost}
    have h₃ := (Finset.card_le_card sS.bp_sub)
    simp only [Finset.card_singleton] at h₂
    omega
  · rw [hd]
    intro u hu
    exact Finset.mem_union_left _ (Finset.mem_union_left _ hu)

omit [DecidableEq X] [DecidableEq U] in
theorem internalCount_add_one [DecidableEq X] [DecidableEq U] :
    ∀ t : DTree X U, t.WF inp → RTD.internalCount t + 1 = t.vars.card
  | leaf _, _ => by simp [RTD.internalCount, vars]
  | node _ _ l r, ⟨_, hdisj, _, _, _, hl, hr⟩ => by
      simp only [RTD.internalCount, vars]
      rw [Finset.card_union_of_disjoint hdisj, ← internalCount_add_one l hl,
        ← internalCount_add_one r hr]
      omega

end DTree

open DTree RTD

/-- **Theorem 5.1 with Lemma 6.1.** Every RTD on a vtree, with every bag of at
most b vertices, has an SDD over its inputs, respecting a vtree over the same
inputs, that computes its function, with at most (n − 1)·4^(3b+2) distinct
decision nodes of at most 4^(3b+2) elements each, where n − 1 is the number of
internal nodes. -/
theorem sdd_of_vtree_rtd (R : RTD X U) [Fintype X] [Fintype U] (hT : ∀ x, R.tree ≠ .leaf x)
    {b : ℕ} (hb1 : 1 ≤ b) (hb : Bounded R.inp b R.tree) :
    ∃ T : DTree X U, T.vars = R.tree.vars ∧ T.WF R.inp ∧ ∃ S : Sdd T, S.Valid ∧
      (∀ w, S.Sat w ↔ R.f w) ∧ ∃ hfin : S.decNodes.Finite,
      S.decNodes.ncard ≤ internalCount R.tree * (2 ^ (3 * b + 2)) ^ 2 ∧
      (∀ d ∈ S.decNodes, d.2.elems ≤ (2 ^ (3 * b + 2)) ^ 2) ∧
      ∑ d ∈ hfin.toFinset, d.2.elems ≤
        internalCount R.tree * (2 ^ (3 * b + 2)) ^ 2 * (2 ^ (3 * b + 2)) ^ 2 := by
  obtain ⟨B, L, S₀, z, hshape, hwf, hvars, hrel, hsh, hbd, hbag⟩ :=
    donated_spec R.inp R.tree R.wf hb hT
  let R' : RTD X U :=
    { inp := R.inp
      tree := R.tree.donated R.inp
      acc := R.acc
      wf := hwf
      allVars := fun x => hvars ▸ R.allVars x
      unique := fun w => by
        obtain ⟨ν, hν, huniq⟩ := R.unique w
        refine ⟨ν, ⟨hν.1, (hrel ν).2 hν.2⟩, fun ν' hν' => huniq ν' ⟨hν'.1, (hrel ν').1 hν'.2⟩⟩
      accDep := fun ν ν' h => R.accDep ν ν' (h.mono hbag) }
  have hf : ∀ w, R'.f w ↔ R.f w := by
    intro w
    have : R'.sol w = R.sol w :=
      R.sol_eq w (R'.sol w) (R'.sol_inputs w) ((hrel _).1 (R'.sol_allRel w))
    simp only [RTD.f, R', this]
  have hic : internalCount (R.tree.donated R.inp) = internalCount R.tree := by
    have h₁ := internalCount_add_one R.inp _ hwf
    have h₂ := internalCount_add_one R.inp _ R.wf
    rw [hvars] at h₁
    omega
  have hb1' : 1 ≤ 3 * b + 2 := by omega
  obtain ⟨S, hv, hs, hfin, hcard, helems, hsum⟩ := sdd_of_rtd R' hshape hsh hb1' hbd
  refine ⟨R.tree.donated R.inp, hvars, hwf, S, hv, fun w => (hs w).trans (hf w), hfin, ?_, helems,
    ?_⟩
  · rw [← hic]
    exact hcard
  · rw [← hic]
    exact hsum

end Define.CircuitTreewidthSdd
