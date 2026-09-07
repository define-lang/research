set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraphOptimization

def Kept (reaches : Nat → Nat → Prop) (candidates : Nat → Prop) (candidate : Nat) : Prop :=
  candidates candidate ∧ ∀ other, candidates other → ¬reaches other candidate

theorem same_kept_of_covered
    (reaches : Nat → Nat → Prop) (original smaller : Nat → Prop)
    (transitive : ∀ {first middle last}, reaches first middle → reaches middle last → reaches first last)
    (subset : ∀ candidate, smaller candidate → original candidate)
    (covered : ∀ candidate, original candidate →
      ∃ other, smaller other ∧ (other = candidate ∨ reaches other candidate))
    (candidate : Nat) :
    Kept reaches original candidate ↔ Kept reaches smaller candidate := by
  constructor
  · rintro ⟨present, maximal⟩
    obtain ⟨other, in_smaller, equal | path⟩ := covered candidate present
    · subst other
      exact ⟨in_smaller, fun preceding member => maximal preceding (subset preceding member)⟩
    · exact False.elim (maximal other (subset other in_smaller) path)
  · rintro ⟨present, maximal⟩
    refine ⟨subset candidate present, ?_⟩
    intro preceding in_original path
    obtain ⟨other, in_smaller, equal | earlier_path⟩ := covered preceding in_original
    · subst other
      exact maximal preceding in_smaller path
    · exact maximal other in_smaller (transitive earlier_path path)

end Define.OperationGraphOptimization
