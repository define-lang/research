import operation_effects
import finite_schedule_order

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.ExactEffects

universe u v w

variable {Occurrence : Type u} {Key : Type v} {Value : Type w}

inductive Execution (effects : Occurrence → Effect Key Value) :
    List Occurrence → (Key → Value) → (Key → Value) → Prop
  | nil (state : Key → Value) : Execution effects [] state state
  | cons {operation : Occurrence} {remaining : List Occurrence}
      {before after : Key → Value}
      (enabled : (effects operation).Enabled before)
      (remaining_execution : Execution effects remaining ((effects operation).apply before) after) :
      Execution effects (operation :: remaining) before after

theorem Execution.swap_head {effects : Occurrence → Effect Key Value}
    {first second : Occurrence} {remaining : List Occurrence}
    {before after : Key → Value}
    (second_valid : (effects second).Valid)
    (independent : Independent (effects first) (effects second))
    (execution : Execution effects (first :: second :: remaining) before after) :
    Execution effects (second :: first :: remaining) before after := by
  cases execution with
  | cons first_enabled tail =>
      cases tail with
      | cons second_enabled rest =>
          obtain ⟨second_first, first_second, equal⟩ :=
            independent_enabled_exchange second_valid independent first_enabled second_enabled
          exact .cons second_first (.cons first_second (equal ▸ rest))

theorem Execution.swap_adjacent {effects : Occurrence → Effect Key Value}
    {first second : Occurrence} {remaining : List Occurrence}
    (schedulePrefix : List Occurrence) {before after : Key → Value}
    (second_valid : (effects second).Valid)
    (independent : Independent (effects first) (effects second))
    (execution : Execution effects (schedulePrefix ++ first :: second :: remaining) before after) :
    Execution effects (schedulePrefix ++ second :: first :: remaining) before after := by
  induction schedulePrefix generalizing before with
  | nil => exact execution.swap_head second_valid independent
  | cons operation schedulePrefix induction_hypothesis =>
      cases execution with
      | cons enabled rest => exact .cons enabled (induction_hypothesis rest)

theorem incomparable_swap_executes {effects : Occurrence → Effect Key Value}
    {precedence : Occurrence → Occurrence → Prop}
    (valid : ∀ operation, (effects operation).Valid)
    (incomparable_independent : ∀ first second,
      first ≠ second → ¬precedence first second → ¬precedence second first →
        Independent (effects first) (effects second))
    {original reordered : List Occurrence} {before after : Key → Value}
    (swap : AdjacentIncomparableSwap precedence original reordered)
    (execution : Execution effects original before after) :
    Execution effects reordered before after := by
  cases swap with
  | swap schedulePrefix first second remaining first_not_after second_not_after =>
      by_cases same : first = second
      · subst second
        exact execution
      · exact execution.swap_adjacent schedulePrefix (valid second)
          (incomparable_independent first second same first_not_after second_not_after)

theorem respecting_permutation_executes {effects : Occurrence → Effect Key Value}
    {precedence : Occurrence → Occurrence → Prop}
    (valid : ∀ operation, (effects operation).Valid)
    (incomparable_independent : ∀ first second,
      first ≠ second → ¬precedence first second → ¬precedence second first →
        Independent (effects first) (effects second))
    {original reordered : List Occurrence} {before after : Key → Value}
    (permuted : original.Perm reordered) (distinct : original.Nodup)
    (original_respects : RespectsPrecedence precedence original)
    (reordered_respects : RespectsPrecedence precedence reordered)
    (execution : Execution effects original before after) :
    Execution effects reordered before after := by
  have exchanges := respecting_permutations_connected permuted distinct
    original_respects reordered_respects
  clear permuted reordered_respects
  induction exchanges with
  | refl => exact execution
  | tail earlier final_swap induction_hypothesis =>
      exact incomparable_swap_executes valid incomparable_independent final_swap induction_hypothesis

theorem Execution.conflicting_swap_impossible {effects : Occurrence → Effect Key Value}
    {first second : Occurrence} {remaining : List Occurrence}
    (schedulePrefix : List Occurrence) {before after : Key → Value}
    (first_valid : (effects first).Valid) (second_valid : (effects second).Valid)
    (conflict : Conflict (effects first) (effects second))
    (execution : Execution effects (schedulePrefix ++ first :: second :: remaining) before after) :
    ∀ finalState,
      ¬Execution effects (schedulePrefix ++ second :: first :: remaining) before finalState := by
  induction schedulePrefix generalizing before with
  | nil =>
      intro finalState reversed
      cases execution with
      | cons first_enabled tail =>
          cases tail with
          | cons second_enabled rest =>
              cases reversed with
              | cons second_first tail =>
                  cases tail with
                  | cons first_second rest =>
                      exact conflicting_enabled_pair_cannot_reverse first_valid second_valid
                        conflict first_enabled second_enabled ⟨second_first, first_second⟩
  | cons operation schedulePrefix induction_hypothesis =>
      intro finalState reversed
      cases execution with
      | cons enabled rest =>
          cases reversed with
          | cons enabled reversed_rest =>
              exact induction_hypothesis rest finalState reversed_rest

theorem conflicting_cover_has_unsafe_reversal
    {effects : Occurrence → Effect Key Value}
    {precedence : Occurrence → Occurrence → Prop}
    (valid : ∀ operation, (effects operation).Valid)
    (incomparable_independent : ∀ first second,
      first ≠ second → ¬precedence first second → ¬precedence second first →
        Independent (effects first) (effects second))
    {schedule : List Occurrence} {before after : Key → Value}
    (distinct : schedule.Nodup) (respects : RespectsPrecedence precedence schedule)
    (execution : Execution effects schedule before after)
    (irreflexive : ∀ operation, ¬precedence operation operation)
    (transitive : ∀ {a b c}, precedence a b → precedence b c → precedence a c)
    {following previous : Occurrence}
    (related : precedence following previous)
    (cover : ∀ middle, precedence following middle → ¬precedence middle previous)
    (following_member : following ∈ schedule) (previous_member : previous ∈ schedule)
    (conflict : Conflict (effects previous) (effects following)) :
    ∃ preceding remaining,
      schedule.Perm (preceding ++ previous :: following :: remaining) ∧
      RespectsPrecedence precedence (preceding ++ previous :: following :: remaining) ∧
      ∀ finalState,
        ¬Execution effects (preceding ++ following :: previous :: remaining) before finalState := by
  obtain ⟨preceding, remaining, permuted, adjacent_respects⟩ :=
    cover_pair_has_adjacent_respecting_permutation distinct respects irreflexive transitive
      related cover following_member previous_member
  have adjacent_execution := respecting_permutation_executes valid incomparable_independent
    permuted distinct respects adjacent_respects execution
  exact ⟨preceding, remaining, permuted, adjacent_respects,
    adjacent_execution.conflicting_swap_impossible preceding
      (valid previous) (valid following) conflict⟩

end Define.OperationGraph.ExactEffects
