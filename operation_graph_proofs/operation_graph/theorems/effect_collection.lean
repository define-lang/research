import definitions
import operation_effects

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.ExactEffects

universe u v

variable {Key : Type u} {Value : Type v}

def Effect.Requires (effect : Effect Key Value) (key : Key) : Prop :=
  ∃ value, effect.requires key = some value

def Effect.Changes (effect : Effect Key Value) (key : Key) : Prop :=
  ∃ value, effect.changes key = some value

theorem Effect.changes_requires {effect : Effect Key Value}
    (valid : effect.Valid) {key : Key} (changed : effect.Changes key) :
    effect.Requires key := by
  obtain ⟨after, change⟩ := changed
  obtain ⟨before, requirement, _⟩ := valid key after change
  exact ⟨before, requirement⟩

def ComponentConflict (first second : Effect Key Value) (key : Key) : Prop :=
  first.Requires key ∧ second.Requires key ∧
    (first.Changes key ∨ second.Changes key)

theorem component_conflict_iff {first second : Effect Key Value}
    (first_valid : first.Valid) (second_valid : second.Valid) :
    Conflict first second ↔ ∃ key, ComponentConflict first second key := by
  constructor
  · rintro (⟨key, written, required, change, requirement⟩ |
      ⟨key, written, required, change, requirement⟩)
    · exact ⟨key, first.changes_requires first_valid ⟨written, change⟩,
        ⟨required, requirement⟩, Or.inl ⟨written, change⟩⟩
    · exact ⟨key, ⟨required, requirement⟩,
        second.changes_requires second_valid ⟨written, change⟩,
        Or.inr ⟨written, change⟩⟩
  · rintro ⟨key, ⟨first_value, first_requirement⟩,
      ⟨second_value, second_requirement⟩, first_change | second_change⟩
    · obtain ⟨written, change⟩ := first_change
      exact Or.inl ⟨key, written, second_value, change, second_requirement⟩
    · obtain ⟨written, change⟩ := second_change
      exact Or.inr ⟨key, written, first_value, change, first_requirement⟩

def EarlierConflict (effects : Nat → Effect Key Value) (later earlier : Nat) : Prop :=
  earlier < later ∧ Conflict (effects earlier) (effects later)

def Collected (effects : Nat → Effect Key Value) (later earlier : Nat) : Prop :=
  earlier < later ∧ ∃ key,
    ComponentConflict (effects earlier) (effects later) key ∧
      ∀ middle, earlier < middle → middle < later → ¬(effects middle).Changes key

theorem collected_is_conflict {effects : Nat → Effect Key Value}
    (valid : ∀ operation, (effects operation).Valid) {later earlier : Nat}
    (collected : Collected effects later earlier) : EarlierConflict effects later earlier := by
  obtain ⟨before, key, conflict, _⟩ := collected
  exact ⟨before, (component_conflict_iff (valid earlier) (valid later)).mpr ⟨key, conflict⟩⟩

theorem conflict_reaches_collected {effects : Nat → Effect Key Value}
    (valid : ∀ operation, (effects operation).Valid) {later earlier : Nat}
    (conflict : EarlierConflict effects later earlier) :
    Reaches (Collected effects) later earlier := by
  have build : ∀ distance earlier later, later - earlier = distance →
      EarlierConflict effects later earlier → Reaches (Collected effects) later earlier := by
    intro distance
    induction distance using Nat.strongRecOn with
    | ind distance induction_hypothesis =>
        intro earlier later difference conflict
        obtain ⟨before, shared⟩ := conflict
        obtain ⟨key, first_required, last_required, changed⟩ :=
          (component_conflict_iff (valid earlier) (valid later)).mp shared
        by_cases unchanged : ∀ middle, earlier < middle → middle < later →
            ¬(effects middle).Changes key
        · exact .direct ⟨before, key, ⟨first_required, last_required, changed⟩, unchanged⟩
        · have intermediate : ∃ middle, earlier < middle ∧ middle < later ∧
              (effects middle).Changes key := by
            apply Classical.byContradiction
            intro absent
            apply unchanged
            intro middle after_earlier before_later changes
            exact absent ⟨middle, after_earlier, before_later, changes⟩
          obtain ⟨middle, after_earlier, before_later, middle_changes⟩ := intermediate
          have middle_required := (effects middle).changes_requires (valid middle) middle_changes
          have first_conflict : EarlierConflict effects middle earlier :=
            ⟨after_earlier, (component_conflict_iff (valid earlier) (valid middle)).mpr
              ⟨key, first_required, middle_required, Or.inr middle_changes⟩⟩
          have last_conflict : EarlierConflict effects later middle :=
            ⟨before_later, (component_conflict_iff (valid middle) (valid later)).mpr
              ⟨key, middle_required, last_required, Or.inl middle_changes⟩⟩
          have first_path := induction_hypothesis (middle - earlier) (by omega)
            earlier middle rfl first_conflict
          have last_path := induction_hypothesis (later - middle) (by omega)
            middle later rfl last_conflict
          exact last_path.trans first_path
  exact build (later - earlier) earlier later rfl conflict

theorem collected_reachability_iff {effects : Nat → Effect Key Value}
    (valid : ∀ operation, (effects operation).Valid) {later earlier : Nat} :
    Reaches (Collected effects) later earlier ↔
      Reaches (EarlierConflict effects) later earlier := by
  constructor
  · intro path
    induction path with
    | direct edge => exact .direct (collected_is_conflict valid edge)
    | step edge _ induction_hypothesis =>
        exact .step (collected_is_conflict valid edge) induction_hypothesis
  · intro path
    induction path with
    | direct edge => exact conflict_reaches_collected valid edge
    | step edge _ induction_hypothesis =>
        exact (conflict_reaches_collected valid edge).trans induction_hypothesis

theorem incomparable_collected_independent {effects : Nat → Effect Key Value}
    (valid : ∀ operation, (effects operation).Valid) {first second : Nat}
    (different : first ≠ second)
    (first_not_after : ¬Reaches (Collected effects) first second)
    (second_not_after : ¬Reaches (Collected effects) second first) :
    Independent (effects first) (effects second) := by
  intro conflict
  by_cases first_before : first < second
  · exact second_not_after (conflict_reaches_collected valid ⟨first_before, conflict⟩)
  · have second_before : second < first := by omega
    have reverse_conflict : Conflict (effects second) (effects first) := by
      rcases conflict with change | change
      · exact Or.inr change
      · exact Or.inl change
    exact first_not_after (conflict_reaches_collected valid ⟨second_before, reverse_conflict⟩)

end Define.OperationGraph.ExactEffects
