import Std

set_option warningAsError true
set_option autoImplicit false

/-!
# Finite Schedule Order

This module proves the finite order-theoretic exchange theorem used by the
maximum-safe-concurrency argument. Two duplicate-free schedules containing the
same occurrences and respecting the same precedence relation are connected by
a finite sequence of adjacent exchanges. Every exchanged pair is incomparable
in the precedence relation.

The theorem is independent of Particle Operation occupancy semantics and does
not require the precedence relation to be finite beyond the two schedule lists.
The exact finite-poset correspondence and external citation are in
`external-results.md`. The exchange proof remains here because the available
library results do not supply its constrained sequence of swaps.
-/

namespace Define.OperationGraph

universe u

/--
A schedule respects a precedence relation when no occurrence appears before an
occurrence that the relation requires it to follow.
-/
abbrev RespectsPrecedence {Occurrence : Type u}
    (precedence : Occurrence → Occurrence → Prop) : List Occurrence → Prop :=
  List.Pairwise (fun earlier later => ¬precedence earlier later)

/--
A schedule that respects a relation also respects every subrelation of it.
-/
theorem RespectsPrecedence.mono
    {Occurrence : Type u}
    {precedence weaker : Occurrence → Occurrence → Prop}
    {schedule : List Occurrence}
    (respects : RespectsPrecedence precedence schedule)
    (weaker_is_subrelation :
      ∀ following previous,
        weaker following previous → precedence following previous) :
    RespectsPrecedence weaker schedule :=
  respects.imp (fun unrelated related =>
    unrelated (weaker_is_subrelation _ _ related))

/--
Related occurrences in a finite respecting schedule appear in the order
required by an irreflexive precedence relation.
-/
theorem RespectsPrecedence.index_lt
    {Occurrence : Type u}
    {precedence : Occurrence → Occurrence → Prop}
    {schedule : List Occurrence}
    (respects : RespectsPrecedence precedence schedule)
    (precedence_irreflexive : ∀ occurrence, ¬precedence occurrence occurrence)
    {followingOrder previousOrder : Nat} {following previous : Occurrence}
    (following_at : schedule[followingOrder]? = some following)
    (previous_at : schedule[previousOrder]? = some previous)
    (following_precedence_previous : precedence following previous) :
    previousOrder < followingOrder := by
  obtain ⟨following_bound, following_equal⟩ := List.getElem_of_getElem? following_at
  obtain ⟨previous_bound, previous_equal⟩ := List.getElem_of_getElem? previous_at
  have different : followingOrder ≠ previousOrder := by
    intro equal
    subst previousOrder
    have same : following = previous := following_equal.symm.trans previous_equal
    exact precedence_irreflexive following (same ▸ following_precedence_previous)
  have not_before : ¬followingOrder < previousOrder := by
    intro before
    have unrelated := List.pairwise_iff_getElem.mp respects
      followingOrder previousOrder following_bound previous_bound before
    exact unrelated (following_equal ▸ previous_equal ▸ following_precedence_previous)
  omega

theorem RespectsPrecedence.snoc
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {schedule : List Occurrence} {finalOccurrence : Occurrence}
    (respects : RespectsPrecedence precedence schedule)
    (earlier_does_not_follow_final :
      ∀ earlierOccurrence,
        earlierOccurrence ∈ schedule →
          ¬precedence earlierOccurrence finalOccurrence) :
    RespectsPrecedence precedence (schedule ++ [finalOccurrence]) :=
  List.pairwise_append.mpr ⟨respects, List.pairwise_singleton _ _, by
    simpa using earlier_does_not_follow_final⟩

theorem RespectsPrecedence.sublist
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {shorterSchedule schedule : List Occurrence}
    (shorter_is_sublist : List.Sublist shorterSchedule schedule)
    (respects : RespectsPrecedence precedence schedule) :
    RespectsPrecedence precedence shorterSchedule :=
  List.Pairwise.sublist shorter_is_sublist respects

/--
The second part of a precedence-respecting appended schedule also respects the
relation.
-/
theorem RespectsPrecedence.right_of_append
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (respects :
      RespectsPrecedence precedence (firstSchedule ++ secondSchedule)) :
    RespectsPrecedence precedence secondSchedule :=
  (List.pairwise_append.mp respects).2.1

theorem RespectsPrecedence.append
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (first_respects : RespectsPrecedence precedence firstSchedule)
    (second_respects : RespectsPrecedence precedence secondSchedule)
    (first_does_not_follow_second :
      ∀ firstOccurrence,
        firstOccurrence ∈ firstSchedule →
          ∀ secondOccurrence,
            secondOccurrence ∈ secondSchedule →
              ¬precedence firstOccurrence secondOccurrence) :
    RespectsPrecedence precedence (firstSchedule ++ secondSchedule) :=
  List.pairwise_append.mpr
    ⟨first_respects, second_respects, first_does_not_follow_second⟩

/--
A duplicate-free subcollection of a finite list can be moved to the front while
the relative order of every other occurrence is preserved.
-/
theorem exists_order_preserving_complement
    {Occurrence : Type u} {schedulePrefix referenceSchedule : List Occurrence}
    (prefix_nodup : schedulePrefix.Nodup)
    (prefix_subset :
      ∀ occurrence,
        occurrence ∈ schedulePrefix → occurrence ∈ referenceSchedule) :
    ∃ remaining,
      List.Sublist remaining referenceSchedule ∧
        referenceSchedule.Perm (schedulePrefix ++ remaining) := by
  induction schedulePrefix generalizing referenceSchedule with
  | nil =>
      exact ⟨referenceSchedule, .refl _, by simp⟩
  | cons occurrence schedulePrefix induction_hypothesis =>
      have occurrence_member :=
        prefix_subset occurrence (by simp)
      obtain ⟨before, after, rfl⟩ := List.append_of_mem occurrence_member
      have prefix_nodup_parts := List.nodup_cons.mp prefix_nodup
      have prefix_subset_without_occurrence :
          ∀ remainingOccurrence,
            remainingOccurrence ∈ schedulePrefix →
              remainingOccurrence ∈ before ++ after := by
        intro remainingOccurrence remaining_member
        have remaining_ne_occurrence : remainingOccurrence ≠ occurrence := by
          intro occurrences_equal
          subst remainingOccurrence
          exact prefix_nodup_parts.1 remaining_member
        have remaining_in_reference :=
          prefix_subset remainingOccurrence (by simp [remaining_member])
        simpa [remaining_ne_occurrence] using remaining_in_reference
      rcases
          induction_hypothesis prefix_nodup_parts.2
            prefix_subset_without_occurrence with
        ⟨remaining, remaining_is_sublist, schedules_permuted⟩
      have reference_without_occurrence_is_sublist :
          List.Sublist (before ++ after) (before ++ occurrence :: after) :=
        (List.Sublist.refl before).append
          ((List.Sublist.refl after).cons occurrence)
      refine
        ⟨remaining,
          remaining_is_sublist.trans reference_without_occurrence_is_sublist,
          ?_⟩
      simpa only [List.cons_append] using
        List.perm_middle.trans (schedules_permuted.cons occurrence)

/--
One schedule is obtained from another by exchanging two adjacent occurrences
that are incomparable in the precedence relation.
-/
inductive AdjacentIncomparableSwap {Occurrence : Type u}
    (precedence : Occurrence → Occurrence → Prop) :
    List Occurrence → List Occurrence → Prop where
  | swap (schedulePrefix : List Occurrence)
      (firstOccurrence secondOccurrence : Occurrence)
      (scheduleSuffix : List Occurrence)
      (first_does_not_follow_second :
        ¬precedence firstOccurrence secondOccurrence)
      (second_does_not_follow_first :
        ¬precedence secondOccurrence firstOccurrence) :
      AdjacentIncomparableSwap precedence
        (schedulePrefix ++
          firstOccurrence :: secondOccurrence :: scheduleSuffix)
        (schedulePrefix ++
          secondOccurrence :: firstOccurrence :: scheduleSuffix)

/--
The reflexive transitive closure of adjacent incomparable exchanges.
-/
inductive IncomparableSwapSequence {Occurrence : Type u}
    (precedence : Occurrence → Occurrence → Prop) :
    List Occurrence → List Occurrence → Prop where
  | refl (schedule : List Occurrence) :
      IncomparableSwapSequence precedence schedule schedule
  | tail {firstSchedule middleSchedule finalSchedule : List Occurrence}
      (earlier_exchanges :
        IncomparableSwapSequence precedence firstSchedule middleSchedule)
      (final_exchange :
        AdjacentIncomparableSwap precedence middleSchedule finalSchedule) :
      IncomparableSwapSequence precedence firstSchedule finalSchedule

theorem IncomparableSwapSequence.trans
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule middleSchedule finalSchedule : List Occurrence}
    (first_exchanges :
      IncomparableSwapSequence precedence firstSchedule middleSchedule)
    (remaining_exchanges :
      IncomparableSwapSequence precedence middleSchedule finalSchedule) :
    IncomparableSwapSequence precedence firstSchedule finalSchedule := by
  induction remaining_exchanges with
  | refl => exact first_exchanges
  | tail earlier_exchanges final_exchange induction_hypothesis =>
      exact .tail induction_hypothesis final_exchange

theorem AdjacentIncomparableSwap.cons
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (precedingOccurrence : Occurrence)
    (exchange :
      AdjacentIncomparableSwap precedence firstSchedule secondSchedule) :
    AdjacentIncomparableSwap precedence
      (precedingOccurrence :: firstSchedule)
      (precedingOccurrence :: secondSchedule) := by
  cases exchange with
  | swap schedulePrefix firstOccurrence secondOccurrence scheduleSuffix
      first_does_not_follow_second second_does_not_follow_first =>
      simpa only [List.cons_append] using
        AdjacentIncomparableSwap.swap
          (precedingOccurrence :: schedulePrefix) firstOccurrence
          secondOccurrence scheduleSuffix first_does_not_follow_second
          second_does_not_follow_first

theorem AdjacentIncomparableSwap.perm
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (exchange :
      AdjacentIncomparableSwap precedence firstSchedule secondSchedule) :
    firstSchedule.Perm secondSchedule := by
  cases exchange with
  | swap schedulePrefix firstOccurrence secondOccurrence scheduleSuffix =>
      exact
        (List.Perm.swap secondOccurrence firstOccurrence
          scheduleSuffix).append_left schedulePrefix

theorem IncomparableSwapSequence.cons
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (precedingOccurrence : Occurrence)
    (exchanges :
      IncomparableSwapSequence precedence firstSchedule secondSchedule) :
    IncomparableSwapSequence precedence
      (precedingOccurrence :: firstSchedule)
      (precedingOccurrence :: secondSchedule) := by
  induction exchanges with
  | refl => exact .refl _
  | tail earlier_exchanges final_exchange induction_hypothesis =>
      exact .tail induction_hypothesis (final_exchange.cons precedingOccurrence)

theorem IncomparableSwapSequence.perm
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (exchanges :
      IncomparableSwapSequence precedence firstSchedule secondSchedule) :
    firstSchedule.Perm secondSchedule := by
  induction exchanges with
  | refl => exact .rfl
  | tail earlier_exchanges final_exchange induction_hypothesis =>
      exact induction_hypothesis.trans final_exchange.perm

theorem RespectsPrecedence.swap_head
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstOccurrence secondOccurrence : Occurrence}
    {remaining : List Occurrence}
    (second_does_not_follow_first :
      ¬precedence secondOccurrence firstOccurrence)
    (respects :
      RespectsPrecedence precedence
        (firstOccurrence :: secondOccurrence :: remaining)) :
    RespectsPrecedence precedence
      (secondOccurrence :: firstOccurrence :: remaining) := by
  cases respects with
  | cons first_does_not_follow_remaining after_first =>
      cases after_first with
      | cons second_does_not_follow_remaining remaining_respects =>
          exact
            .cons
              (by
                intro laterOccurrence later_member
                simp only [List.mem_cons] at later_member
                rcases later_member with later_is_first | later_member
                · subst laterOccurrence
                  exact second_does_not_follow_first
                · exact
                    second_does_not_follow_remaining laterOccurrence
                      later_member)
              (.cons
                (fun laterOccurrence later_member =>
                  first_does_not_follow_remaining laterOccurrence
                    (by
                      simp only [List.mem_cons]
                      exact Or.inr later_member))
                remaining_respects)

theorem RespectsPrecedence.swap_adjacent
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstOccurrence secondOccurrence : Occurrence}
    {scheduleSuffix : List Occurrence}
    (schedulePrefix : List Occurrence)
    (second_does_not_follow_first :
      ¬precedence secondOccurrence firstOccurrence)
    (respects :
      RespectsPrecedence precedence
        (schedulePrefix ++
          firstOccurrence :: secondOccurrence :: scheduleSuffix)) :
    RespectsPrecedence precedence
      (schedulePrefix ++
        secondOccurrence :: firstOccurrence :: scheduleSuffix) := by
  induction schedulePrefix with
  | nil => exact respects.swap_head second_does_not_follow_first
  | cons precedingOccurrence schedulePrefix induction_hypothesis =>
      simp only [List.cons_append] at respects ⊢
      cases respects with
      | cons preceding_does_not_follow_remaining remaining_respects =>
          exact
            .cons
              (by
                intro laterOccurrence later_member
                apply
                  preceding_does_not_follow_remaining laterOccurrence
                simpa only [List.mem_append, List.mem_cons, or_comm, or_left_comm,
                  or_assoc] using later_member)
              (induction_hypothesis remaining_respects)

theorem AdjacentIncomparableSwap.preserves_respect
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (exchange :
      AdjacentIncomparableSwap precedence firstSchedule secondSchedule)
    (respects : RespectsPrecedence precedence firstSchedule) :
    RespectsPrecedence precedence secondSchedule := by
  cases exchange with
  | swap schedulePrefix firstOccurrence secondOccurrence scheduleSuffix
      _ second_does_not_follow_first =>
      exact
        respects.swap_adjacent schedulePrefix second_does_not_follow_first

theorem IncomparableSwapSequence.preserves_respect
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {firstSchedule secondSchedule : List Occurrence}
    (exchanges :
      IncomparableSwapSequence precedence firstSchedule secondSchedule)
    (respects : RespectsPrecedence precedence firstSchedule) :
    RespectsPrecedence precedence secondSchedule := by
  induction exchanges with
  | refl => exact respects
  | tail earlier_exchanges final_exchange induction_hypothesis =>
      exact final_exchange.preserves_respect induction_hypothesis

private theorem move_occurrence_to_head
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {desiredOccurrence : Occurrence}
    {scheduleSuffix : List Occurrence}
    (schedulePrefix : List Occurrence)
    (respects :
      RespectsPrecedence precedence
        (schedulePrefix ++ desiredOccurrence :: scheduleSuffix))
    (desired_does_not_follow_prefix :
      ∀ prefixOccurrence,
        prefixOccurrence ∈ schedulePrefix →
          ¬precedence desiredOccurrence prefixOccurrence) :
    IncomparableSwapSequence precedence
      (schedulePrefix ++ desiredOccurrence :: scheduleSuffix)
      (desiredOccurrence :: schedulePrefix ++ scheduleSuffix) := by
  induction schedulePrefix with
  | nil => exact .refl _
  | cons precedingOccurrence schedulePrefix induction_hypothesis =>
      simp only [List.cons_append] at respects ⊢
      cases respects with
      | cons preceding_does_not_follow_remaining remaining_respects =>
          have earlier_exchanges :=
            (induction_hypothesis remaining_respects
              (fun prefixOccurrence prefix_member =>
                desired_does_not_follow_prefix prefixOccurrence
                  (by
                    simp only [List.mem_cons]
                    exact Or.inr prefix_member))).cons precedingOccurrence
          have final_exchange :
              AdjacentIncomparableSwap precedence
                (precedingOccurrence :: desiredOccurrence ::
                  schedulePrefix ++ scheduleSuffix)
                (desiredOccurrence :: precedingOccurrence ::
                  schedulePrefix ++ scheduleSuffix) := by
            exact
              .swap [] precedingOccurrence desiredOccurrence
                (schedulePrefix ++ scheduleSuffix)
                (preceding_does_not_follow_remaining desiredOccurrence
                  (by simp))
                (desired_does_not_follow_prefix precedingOccurrence
                  (by simp))
          exact .tail earlier_exchanges final_exchange

/--
Any two duplicate-free finite schedules containing the same occurrences and
respecting the same precedence relation are connected by adjacent exchanges of
incomparable occurrences.
-/
theorem respecting_permutations_connected
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop} :
    ∀ {firstSchedule secondSchedule : List Occurrence},
      firstSchedule.Perm secondSchedule →
        firstSchedule.Nodup →
          RespectsPrecedence precedence firstSchedule →
            RespectsPrecedence precedence secondSchedule →
              IncomparableSwapSequence precedence firstSchedule
                secondSchedule := by
  intro firstSchedule secondSchedule schedules_permuted first_nodup
    first_respects second_respects
  induction secondSchedule generalizing firstSchedule with
  | nil =>
      have first_is_empty := schedules_permuted.eq_nil
      subst firstSchedule
      exact .refl []
  | cons desiredOccurrence desiredRemaining induction_hypothesis =>
      have desired_member : desiredOccurrence ∈ firstSchedule :=
        schedules_permuted.mem_iff.mpr (by simp)
      obtain ⟨schedulePrefix, scheduleSuffix, first_schedule_shape⟩ :=
        List.append_of_mem desired_member
      subst first_schedule_shape
      have remaining_permuted :
          (schedulePrefix ++ scheduleSuffix).Perm desiredRemaining := by
        exact
          List.Perm.cons_inv
            (List.perm_middle.symm.trans schedules_permuted)
      have desired_does_not_follow_prefix :
          ∀ prefixOccurrence,
            prefixOccurrence ∈ schedulePrefix →
              ¬precedence desiredOccurrence prefixOccurrence := by
        cases second_respects with
        | cons desired_does_not_follow_remaining _ =>
            intro prefixOccurrence prefix_member
            apply desired_does_not_follow_remaining prefixOccurrence
            exact
              remaining_permuted.mem_iff.mp
                (by simp [prefix_member])
      have move_to_head :=
        move_occurrence_to_head schedulePrefix first_respects
          desired_does_not_follow_prefix
      have moved_respects := move_to_head.preserves_respect first_respects
      cases moved_respects with
      | cons _ moved_remaining_respects =>
          cases second_respects with
          | cons _ desired_remaining_respects =>
              have moved_nodup :
                  (desiredOccurrence :: schedulePrefix ++ scheduleSuffix).Nodup :=
                List.perm_middle.nodup first_nodup
              have remaining_exchanges :=
                induction_hypothesis remaining_permuted moved_nodup.tail
                  moved_remaining_respects desired_remaining_respects
              exact move_to_head.trans (remaining_exchanges.cons desiredOccurrence)

/-- A cover pair can be adjacent in a respecting permutation of a finite schedule. -/
theorem cover_pair_has_adjacent_respecting_permutation
    {Occurrence : Type u} {precedence : Occurrence → Occurrence → Prop}
    {schedule : List Occurrence} {following previous : Occurrence}
    (distinct : schedule.Nodup)
    (respects : RespectsPrecedence precedence schedule)
    (irreflexive : ∀ occurrence, ¬precedence occurrence occurrence)
    (transitive : ∀ {a b c}, precedence a b → precedence b c → precedence a c)
    (related : precedence following previous)
    (cover : ∀ middle, precedence following middle → ¬precedence middle previous)
    (following_member : following ∈ schedule) (previous_member : previous ∈ schedule) :
    ∃ preceding remaining,
      schedule.Perm (preceding ++ previous :: following :: remaining) ∧
      RespectsPrecedence precedence (preceding ++ previous :: following :: remaining) := by
  classical
  let preceding := schedule.filter (fun occurrence =>
    decide (precedence following occurrence ∧ occurrence ≠ previous))
  have preceding_iff {occurrence : Occurrence} :
      occurrence ∈ preceding ↔ occurrence ∈ schedule ∧
        precedence following occurrence ∧ occurrence ≠ previous := by
    simp [preceding]
  have preceding_sublist : preceding.Sublist schedule := List.filter_sublist
  have different : previous ≠ following := by
    intro equal
    subst previous
    exact irreflexive following related
  have previous_absent : previous ∉ preceding := by
    intro member
    exact (preceding_iff.mp member).2.2 rfl
  have following_absent : following ∉ preceding := by
    intro member
    exact irreflexive following (preceding_iff.mp member).2.1
  have initial_distinct : (preceding ++ [previous, following]).Nodup := by
    rw [List.nodup_append]
    refine ⟨preceding_sublist.nodup distinct, by simp [different], ?_⟩
    intro a a_member b b_member equal
    subst b
    have alternatives : a = previous ∨ a = following := by simpa using b_member
    rcases alternatives with rfl | rfl
    · exact previous_absent a_member
    · exact following_absent a_member
  have initial_subset : ∀ occurrence,
      occurrence ∈ preceding ++ [previous, following] → occurrence ∈ schedule := by
    intro occurrence member
    have alternatives : occurrence ∈ preceding ∨
        occurrence = previous ∨ occurrence = following := by simpa using member
    rcases alternatives with member | rfl | rfl
    · exact preceding_sublist.subset member
    · exact previous_member
    · exact following_member
  have through_previous : RespectsPrecedence precedence (preceding ++ [previous]) := by
    apply (respects.sublist preceding_sublist).snoc
    intro occurrence member relation
    exact cover occurrence (preceding_iff.mp member).2.1 relation
  have initial_respects :
      RespectsPrecedence precedence (preceding ++ [previous, following]) := by
    have extended := through_previous.snoc (finalOccurrence := following) (by
      intro occurrence member relation
      have alternatives : occurrence ∈ preceding ∨ occurrence = previous := by
        simpa using member
      rcases alternatives with member | rfl
      · exact irreflexive following
          (transitive (preceding_iff.mp member).2.1 relation)
      · exact irreflexive following (transitive related relation))
    simpa [List.append_assoc] using extended
  obtain ⟨remaining, remaining_sublist, permuted⟩ :=
    exists_order_preserving_complement initial_distinct initial_subset
  have disjoint := (List.nodup_append.mp (permuted.nodup distinct)).2.2
  have complete := initial_respects.append (respects.sublist remaining_sublist) (by
    intro a a_member b b_member relation
    have following_before_b : precedence following b := by
      have alternatives : a ∈ preceding ∨ a = previous ∨ a = following := by
        simpa using a_member
      rcases alternatives with member | rfl | rfl
      · exact transitive (preceding_iff.mp member).2.1 relation
      · exact transitive related relation
      · exact relation
    have b_initial : b ∈ preceding ++ [previous, following] := by
      by_cases equal : b = previous
      · simp [equal]
      · exact List.mem_append_left _ (preceding_iff.mpr
          ⟨remaining_sublist.subset b_member, following_before_b, equal⟩)
    exact disjoint b b_initial b b_member rfl)
  exact ⟨preceding, remaining, by simpa [List.append_assoc] using permuted,
    by simpa [List.append_assoc] using complete⟩

end Define.OperationGraph
