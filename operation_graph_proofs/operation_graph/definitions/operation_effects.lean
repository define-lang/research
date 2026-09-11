import Std

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.ExactEffects

universe u v

structure Effect (Key : Type u) (Value : Type v) where
  requires : Key → Option Value
  changes : Key → Option Value

variable {Key : Type u} {Value : Type v}

def Effect.Valid (effect : Effect Key Value) : Prop :=
  ∀ key after, effect.changes key = some after →
    ∃ before, effect.requires key = some before ∧ after ≠ before

def Effect.Enabled (effect : Effect Key Value) (state : Key → Value) : Prop :=
  ∀ key value, effect.requires key = some value → state key = value

def Effect.apply (effect : Effect Key Value) (state : Key → Value) : Key → Value :=
  fun key => (effect.changes key).getD (state key)

def Conflict (first second : Effect Key Value) : Prop :=
  (∃ key written required,
    first.changes key = some written ∧ second.requires key = some required) ∨
  (∃ key written required,
    second.changes key = some written ∧ first.requires key = some required)

def Independent (first second : Effect Key Value) : Prop := ¬Conflict first second

theorem independent_symm {first second : Effect Key Value}
    (independent : Independent first second) : Independent second first := by
  rintro (conflict | conflict)
  · exact independent (Or.inr conflict)
  · exact independent (Or.inl conflict)

theorem unchanged_required_component {first second : Effect Key Value}
    (independent : Independent first second) {key : Key} {required : Value}
    (requirement : second.requires key = some required) : first.changes key = none := by
  cases change : first.changes key with
  | none => rfl
  | some written => exact False.elim (independent (Or.inl ⟨key, written, required, change, requirement⟩))

theorem independent_apply_commutes {first second : Effect Key Value}
    (second_valid : second.Valid) (independent : Independent first second)
    (state : Key → Value) :
    second.apply (first.apply state) = first.apply (second.apply state) := by
  funext key
  cases first_change : first.changes key with
  | none => simp [Effect.apply, first_change]
  | some written =>
      cases second_change : second.changes key with
      | none => simp [Effect.apply, second_change]
      | some other_written =>
          obtain ⟨required, requirement, _⟩ := second_valid key other_written second_change
          exact False.elim (independent (Or.inl ⟨key, written, required, first_change, requirement⟩))

theorem independent_enabled_exchange {first second : Effect Key Value}
    (second_valid : second.Valid) (independent : Independent first second)
    {state : Key → Value} (first_enabled : first.Enabled state)
    (second_enabled : second.Enabled (first.apply state)) :
    second.Enabled state ∧ first.Enabled (second.apply state) ∧
      second.apply (first.apply state) = first.apply (second.apply state) := by
  refine ⟨?_, ?_, independent_apply_commutes second_valid independent state⟩
  · intro key value requirement
    have unchanged := unchanged_required_component independent requirement
    simpa [Effect.apply, unchanged] using second_enabled key value requirement
  · intro key value requirement
    have unchanged := unchanged_required_component (independent_symm independent) requirement
    simpa [Effect.apply, unchanged] using first_enabled key value requirement

theorem conflicting_enabled_pair_cannot_reverse {first second : Effect Key Value}
    (first_valid : first.Valid) (second_valid : second.Valid)
    (conflict : Conflict first second) {state : Key → Value}
    (first_enabled : first.Enabled state)
    (second_enabled : second.Enabled (first.apply state)) :
    ¬(second.Enabled state ∧ first.Enabled (second.apply state)) := by
  rintro ⟨second_first, first_second⟩
  rcases conflict with ⟨key, written, required, change, requirement⟩ |
      ⟨key, written, required, change, requirement⟩
  · obtain ⟨before, first_requirement, different⟩ := first_valid key written change
    have original := first_enabled key before first_requirement
    have required_original := second_first key required requirement
    have changed : written = required := by
      simpa [Effect.apply, change] using second_enabled key required requirement
    exact different (changed.trans (required_original.symm.trans original))
  · obtain ⟨before, second_requirement, different⟩ := second_valid key written change
    have original := first_enabled key required requirement
    have required_original := second_first key before second_requirement
    have changed : written = required := by
      simpa [Effect.apply, change] using first_second key required requirement
    exact different (changed.trans (original.symm.trans required_original))

def Effect.product {Index : Type} (effects : Index → Effect Key Value) :
    Effect (Index × Key) Value where
  requires component := (effects component.1).requires component.2
  changes component := (effects component.1).changes component.2

theorem product_valid {Index : Type} {effects : Index → Effect Key Value}
    (valid : ∀ index, (effects index).Valid) : (Effect.product effects).Valid := by
  intro component value changed
  exact valid component.1 component.2 value changed

theorem product_enabled_iff {Index : Type} {effects : Index → Effect Key Value}
    {state : Index × Key → Value} :
    (Effect.product effects).Enabled state ↔
      ∀ index, (effects index).Enabled (fun key => state (index, key)) := by
  constructor
  · intro enabled index key value requirement
    exact enabled (index, key) value requirement
  · intro enabled component value requirement
    exact enabled component.1 component.2 value requirement

theorem product_apply {Index : Type} (effects : Index → Effect Key Value)
    (state : Index × Key → Value) (index : Index) (key : Key) :
    (Effect.product effects).apply state (index, key) =
      (effects index).apply (fun other => state (index, other)) key := rfl

end Define.OperationGraph.ExactEffects
