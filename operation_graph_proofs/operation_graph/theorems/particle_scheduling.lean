import effect_graph
import particle_requirements
import retained_requirements

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.ParticleRequirements

inductive Execution (qualities : Nat → Nat → Prop) (operations : Nat → Operation) :
    List Nat → State → State → Prop
  | nil (state : State) : Execution qualities operations [] state state
  | cons {occurrence : Nat} {remaining : List Nat} {before after : State}
      (enabled : (operations occurrence).Enabled qualities before)
      (rest : Execution qualities operations remaining ((operations occurrence).execute before) after) :
      Execution qualities operations (occurrence :: remaining) before after

def effectsFor (operations : Nat → Operation) (original : Nat → State) :
    Nat → ExactEffects.Effect Key (Option Nat) :=
  fun occurrence => (operations occurrence).effect (original occurrence)

theorem execution_iff_effect_execution {qualities : Nat → Nat → Prop}
    {operations : Nat → Operation} {original : Nat → State}
    (valid : ∀ occurrence, (operations occurrence).Enabled qualities (original occurrence))
    {schedule : List Nat} {before after : State} :
    Execution qualities operations schedule before after ↔
      ExactEffects.Execution (effectsFor operations original) schedule before after := by
  constructor
  · intro execution
    induction execution with
    | nil state => exact .nil state
    | @cons occurrence remaining before after enabled rest induction_hypothesis =>
        apply ExactEffects.Execution.cons (effects := effectsFor operations original)
          ((operation_enabled_iff_effect_enabled _ (valid occurrence)).mp enabled)
        simpa only [effectsFor, effect_apply_eq_execute _ (valid occurrence)] using induction_hypothesis
  · intro execution
    induction execution with
    | nil state => exact .nil state
    | @cons occurrence remaining before after enabled rest induction_hypothesis =>
        apply Execution.cons
          ((operation_enabled_iff_effect_enabled _ (valid occurrence)).mpr enabled)
        simpa only [effectsFor, effect_apply_eq_execute _ (valid occurrence)] using induction_hypothesis

theorem calculated_schedule_executes {qualities : Nat → Nat → Prop}
    {operations : Nat → Operation} {original : Nat → State}
    (valid : ∀ occurrence, (operations occurrence).Enabled qualities (original occurrence))
    {serial reordered : List Nat} {before after : State}
    (permuted : serial.Perm reordered) (distinct : serial.Nodup)
    (serial_respects : RespectsPrecedence
      (Reaches (ExactEffects.Calculated (effectsFor operations original))) serial)
    (reordered_respects : RespectsPrecedence
      (Reaches (ExactEffects.Calculated (effectsFor operations original))) reordered)
    (execution : Execution qualities operations serial before after) :
    Execution qualities operations reordered before after := by
  apply (execution_iff_effect_execution valid).mpr
  exact ExactEffects.calculated_respecting_permutation_executes
    (fun occurrence => operation_effect_valid _ (valid occurrence))
    permuted distinct serial_respects reordered_respects
    ((execution_iff_effect_execution valid).mp execution)

theorem calculated_edge_has_invalid_reversal {qualities : Nat → Nat → Prop}
    {operations : Nat → Operation} {original : Nat → State}
    (valid : ∀ occurrence, (operations occurrence).Enabled qualities (original occurrence))
    {schedule : List Nat} {before after : State}
    (distinct : schedule.Nodup)
    (respects : RespectsPrecedence
      (Reaches (ExactEffects.Calculated (effectsFor operations original))) schedule)
    (execution : Execution qualities operations schedule before after)
    {following previous : Nat}
    (edge : ExactEffects.Calculated (effectsFor operations original) following previous)
    (following_member : following ∈ schedule) (previous_member : previous ∈ schedule) :
    ∃ preceding remaining,
      schedule.Perm (preceding ++ previous :: following :: remaining) ∧
      RespectsPrecedence (Reaches (ExactEffects.Calculated (effectsFor operations original)))
        (preceding ++ previous :: following :: remaining) ∧
      ∀ finalState,
        ¬Execution qualities operations
          (preceding ++ following :: previous :: remaining) before finalState := by
  obtain ⟨preceding, remaining, permuted, ordered, invalid⟩ :=
    ExactEffects.calculated_edge_has_unsafe_reversal
      (fun occurrence => operation_effect_valid _ (valid occurrence))
      distinct respects ((execution_iff_effect_execution valid).mp execution)
      edge following_member previous_member
  exact ⟨preceding, remaining, permuted, ordered,
    fun finalState execution => invalid finalState ((execution_iff_effect_execution valid).mp execution)⟩

theorem increasing_schedule_respects_calculation
    (effects : Nat → ExactEffects.Effect Key (Option Nat)) {schedule : List Nat}
    (increasing : schedule.Pairwise (fun first second => first < second)) :
    RespectsPrecedence (Reaches (ExactEffects.Calculated effects)) schedule := by
  induction increasing with
  | nil => exact .nil
  | @cons occurrence remaining earlier _ remaining_respects =>
      apply List.Pairwise.cons ?_ remaining_respects
      intro later member path
      have backward : PointsBackward (fun operation : Nat => operation)
          (ExactEffects.Calculated effects) :=
        fun _ _ edge => (ExactEffects.calculated_iff_reduced.mp edge).1.1
      exact Nat.lt_asymm (earlier later member) (reaches_decreases_order backward path)

end Define.OperationGraph.ParticleRequirements

namespace Define.OperationGraph.RetainedRequirements

inductive Execution {Position : Type} (operations : Nat → Position → Option Component) :
    List Nat → (Position × Observation → Option Nat) →
      (Position × Observation → Option Nat) → Prop
  | nil (state : Position × Observation → Option Nat) : Execution operations [] state state
  | cons {occurrence : Nat} {remaining : List Nat}
      {before after : Position × Observation → Option Nat}
      (enabled : ∀ position component, operations occurrence position = some component →
        component.Enabled (fun observation => before (position, observation)))
      (rest : Execution operations remaining (operationExecute (operations occurrence) before) after) :
      Execution operations (occurrence :: remaining) before after

def effectsFor {Position : Type} (operations : Nat → Position → Option Component) :=
  fun occurrence => operationEffect (operations occurrence)

theorem execution_iff_effect_execution {Position : Type}
    {operations : Nat → Position → Option Component}
    {schedule : List Nat} {before after : Position × Observation → Option Nat} :
    Execution operations schedule before after ↔
      ExactEffects.Execution (effectsFor operations) schedule before after := by
  constructor
  · intro execution
    induction execution with
    | nil state => exact .nil state
    | @cons occurrence remaining before after enabled rest induction_hypothesis =>
        apply ExactEffects.Execution.cons (effects := effectsFor operations)
          ((operation_enabled_iff _ _).mpr enabled)
        simpa only [effectsFor, operation_apply_eq_execute] using induction_hypothesis
  · intro execution
    induction execution with
    | nil state => exact .nil state
    | @cons occurrence remaining before after enabled rest induction_hypothesis =>
        apply Execution.cons ((operation_enabled_iff _ _).mp enabled)
        simpa only [effectsFor, operation_apply_eq_execute] using induction_hypothesis

theorem calculated_schedule_executes {Position : Type}
    {operations : Nat → Position → Option Component}
    {serial reordered : List Nat} {before after : Position × Observation → Option Nat}
    (permuted : serial.Perm reordered) (distinct : serial.Nodup)
    (serial_respects : RespectsPrecedence (Reaches (ExactEffects.Calculated (effectsFor operations))) serial)
    (reordered_respects : RespectsPrecedence (Reaches (ExactEffects.Calculated (effectsFor operations))) reordered)
    (execution : Execution operations serial before after) :
    Execution operations reordered before after := by
  apply execution_iff_effect_execution.mpr
  exact ExactEffects.calculated_respecting_permutation_executes
    (fun occurrence => operation_effect_valid (operations occurrence))
    permuted distinct serial_respects reordered_respects
    (execution_iff_effect_execution.mp execution)

theorem calculated_edge_has_invalid_reversal {Position : Type}
    {operations : Nat → Position → Option Component}
    {schedule : List Nat} {before after : Position × Observation → Option Nat}
    (distinct : schedule.Nodup)
    (respects : RespectsPrecedence (Reaches (ExactEffects.Calculated (effectsFor operations))) schedule)
    (execution : Execution operations schedule before after)
    {following previous : Nat}
    (edge : ExactEffects.Calculated (effectsFor operations) following previous)
    (following_member : following ∈ schedule) (previous_member : previous ∈ schedule) :
    ∃ preceding remaining,
      schedule.Perm (preceding ++ previous :: following :: remaining) ∧
      RespectsPrecedence (Reaches (ExactEffects.Calculated (effectsFor operations)))
        (preceding ++ previous :: following :: remaining) ∧
      ∀ finalState, ¬Execution operations
        (preceding ++ following :: previous :: remaining) before finalState := by
  obtain ⟨preceding, remaining, permuted, ordered, invalid⟩ :=
    ExactEffects.calculated_edge_has_unsafe_reversal
      (fun occurrence => operation_effect_valid (operations occurrence))
      distinct respects (execution_iff_effect_execution.mp execution)
      edge following_member previous_member
  exact ⟨preceding, remaining, permuted, ordered,
    fun finalState execution => invalid finalState (execution_iff_effect_execution.mp execution)⟩

end Define.OperationGraph.RetainedRequirements
