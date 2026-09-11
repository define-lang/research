import operation_effects

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.RetainedRequirements

inductive Observation where
  | ordinary
  | original
  deriving DecidableEq

abbrev State := Observation → Option Nat

/-!
These are component effects on one selected original position, not additional
Define operations. A Particle Operation combines all its component effects.
`retained-state-proof.md` derives their source meaning and inherited uses.
-/
inductive Component where
  | earlierUse (particle : Nat)
  | ordinaryFill (particle : Nat)
  | ordinaryEmpty (particle : Nat)
  | supplyOccupied (particle : Nat)
  | supplyEmpty (particle : Nat)
  | ordinaryUse (particle : Nat)
  | vacancy (particle : Nat)
  | retainedUse (particle : Nat)
  | retainedFill (particle : Nat)
  | retainedEmpty (particle : Nat)

def Component.required : Component → Observation → Option (Option Nat)
  | .earlierUse particle, .ordinary => some (some particle)
  | .earlierUse _, .original => none
  | .ordinaryFill _, .ordinary => some none
  | .ordinaryFill _, .original => none
  | .ordinaryEmpty particle, .ordinary => some (some particle)
  | .ordinaryEmpty _, .original => none
  | .supplyOccupied _, _ => some none
  | .supplyEmpty particle, _ => some (some particle)
  | .ordinaryUse particle, _ => some (some particle)
  | .vacancy particle, .ordinary => some (some particle)
  | .vacancy _, .original => none
  | .retainedUse _, .ordinary => none
  | .retainedUse particle, .original => some (some particle)
  | .retainedFill _, .ordinary => none
  | .retainedFill _, .original => some none
  | .retainedEmpty _, .ordinary => none
  | .retainedEmpty particle, .original => some (some particle)

def Component.changed : Component → Observation → Option (Option Nat)
  | .earlierUse _, _ => none
  | .ordinaryFill particle, .ordinary => some (some particle)
  | .ordinaryFill _, .original => none
  | .ordinaryEmpty _, .ordinary => some none
  | .ordinaryEmpty _, .original => none
  | .supplyOccupied particle, _ => some (some particle)
  | .supplyEmpty _, _ => some none
  | .ordinaryUse _, _ => none
  | .vacancy _, .ordinary => some none
  | .vacancy _, .original => none
  | .retainedUse _, _ => none
  | .retainedFill _, .ordinary => none
  | .retainedFill particle, .original => some (some particle)
  | .retainedEmpty _, .ordinary => none
  | .retainedEmpty _, .original => some none

def Component.effect (component : Component) : ExactEffects.Effect Observation (Option Nat) where
  requires := component.required
  changes := component.changed

def Component.Enabled (state : State) : Component → Prop
  | .earlierUse particle => state .ordinary = some particle
  | .ordinaryFill _ => state .ordinary = none
  | .ordinaryEmpty particle => state .ordinary = some particle
  | .supplyOccupied _ => state .ordinary = none ∧ state .original = none
  | .supplyEmpty particle => state .ordinary = some particle ∧ state .original = some particle
  | .ordinaryUse particle => state .ordinary = some particle ∧ state .original = some particle
  | .vacancy particle => state .ordinary = some particle
  | .retainedUse particle => state .original = some particle
  | .retainedFill _ => state .original = none
  | .retainedEmpty particle => state .original = some particle

def Component.execute : Component → State → State
  | .earlierUse _, state => state
  | .ordinaryFill particle, state => fun observation =>
      match observation with
      | .ordinary => some particle
      | .original => state .original
  | .ordinaryEmpty _, state => fun observation =>
      match observation with
      | .ordinary => none
      | .original => state .original
  | .supplyOccupied particle, _ => fun _ => some particle
  | .supplyEmpty _, _ => fun _ => none
  | .ordinaryUse _, state => state
  | .vacancy _, state => fun observation =>
      match observation with
      | .ordinary => none
      | .original => state .original
  | .retainedUse _, state => state
  | .retainedFill particle, state => fun observation =>
      match observation with
      | .ordinary => state .ordinary
      | .original => some particle
  | .retainedEmpty _, state => fun observation =>
      match observation with
      | .ordinary => state .ordinary
      | .original => none

theorem component_apply_eq_execute (component : Component) (state : State) :
    component.effect.apply state = component.execute state := by
  funext observation
  cases component <;> cases observation <;> rfl

theorem forall_observation {predicate : Observation → Prop} :
    (∀ observation, predicate observation) ↔ predicate .ordinary ∧ predicate .original := by
  constructor
  · intro holds
    exact ⟨holds .ordinary, holds .original⟩
  · rintro ⟨ordinary, original⟩ observation
    cases observation
    · exact ordinary
    · exact original

theorem component_enabled_iff_effect_enabled (component : Component) (state : State) :
    component.Enabled state ↔ component.effect.Enabled state := by
  cases component <;>
    simp [Component.Enabled, ExactEffects.Effect.Enabled, Component.effect,
      forall_observation, Component.required]

theorem component_effect_valid (component : Component) : component.effect.Valid := by
  intro observation after changed
  cases component <;> cases observation <;>
    simp_all [Component.effect, Component.changed, Component.required] <;> grind

theorem vacancy_preserves_original (particle : Nat) (state : State) :
    (Component.vacancy particle).effect.apply state .original = state .original := by
  rfl

theorem vacancy_independent_retained_empty (vacating moved : Nat) :
    ExactEffects.Independent (Component.vacancy vacating).effect (Component.retainedEmpty moved).effect := by
  rintro (⟨observation, written, required, change, requirement⟩ |
    ⟨observation, written, required, change, requirement⟩) <;>
    cases observation <;>
    simp_all [Component.effect, Component.changed, Component.required]

theorem ordinary_use_conflicts_with_retained_empty (observed moved : Nat) :
    ExactEffects.Conflict (Component.ordinaryUse observed).effect (Component.retainedEmpty moved).effect := by
  exact Or.inr ⟨.original, none, some observed, rfl, rfl⟩

def operationEffect {Position : Type} (components : Position → Option Component) :
    ExactEffects.Effect (Position × Observation) (Option Nat) :=
  ExactEffects.Effect.product fun position =>
    match components position with
    | none => ⟨fun _ => none, fun _ => none⟩
    | some component => component.effect

theorem operation_effect_valid {Position : Type} (components : Position → Option Component) :
    (operationEffect components).Valid := by
  apply ExactEffects.product_valid
  intro position
  cases selected : components position with
  | none => simp [ExactEffects.Effect.Valid]
  | some component => exact component_effect_valid component

theorem operation_enabled_iff {Position : Type} (components : Position → Option Component)
    (state : Position × Observation → Option Nat) :
    (operationEffect components).Enabled state ↔
      ∀ position component, components position = some component →
        component.Enabled (fun observation => state (position, observation)) := by
  rw [operationEffect, ExactEffects.product_enabled_iff]
  constructor
  · intro enabled position component selected
    have at_position := enabled position
    rw [selected] at at_position
    exact (component_enabled_iff_effect_enabled component _).mpr at_position
  · intro enabled position
    cases selected : components position with
    | none => simp [ExactEffects.Effect.Enabled]
    | some component =>
        exact (component_enabled_iff_effect_enabled component _).mp
          (enabled position component selected)

def operationExecute {Position : Type} (components : Position → Option Component)
    (state : Position × Observation → Option Nat) : Position × Observation → Option Nat :=
  fun entry => match components entry.1 with
    | none => state entry
    | some component => component.execute (fun observation => state (entry.1, observation)) entry.2

theorem operation_apply_eq_execute {Position : Type} (components : Position → Option Component)
    (state : Position × Observation → Option Nat) :
    (operationEffect components).apply state = operationExecute components state := by
  funext entry
  cases selected : components entry.1 with
  | none => simp [operationEffect, ExactEffects.Effect.product, ExactEffects.Effect.apply,
      operationExecute, selected]
  | some component =>
      have equal := congrFun
        (component_apply_eq_execute component (fun observation => state (entry.1, observation))) entry.2
      simpa [operationEffect, ExactEffects.Effect.product, ExactEffects.Effect.apply,
        operationExecute, selected] using equal

end Define.OperationGraph.RetainedRequirements
