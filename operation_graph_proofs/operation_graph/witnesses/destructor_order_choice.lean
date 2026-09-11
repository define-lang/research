import Std

set_option warningAsError true
set_option autoImplicit false

namespace Define.OperationGraph.DestructorOrderChoice

/-!
There is one original particle and three distinct positions. Tracking the
particle's position preserves its identity without introducing replacement
particles or independent copies for the two destructors.
-/

inductive MarkerPosition
  | marker | heldByA | heldByB
  deriving DecidableEq

inductive Operation
  | aOut | aBack | bOut | bBack
  deriving DecidableEq

def source : Operation → MarkerPosition
  | .aOut | .bOut => .marker
  | .aBack => .heldByA
  | .bBack => .heldByB

def destination : Operation → MarkerPosition
  | .aOut => .heldByA
  | .bOut => .heldByB
  | .aBack | .bBack => .marker

def execute : List Operation → MarkerPosition → Option MarkerPosition
  | [], position => some position
  | operation :: remaining, position =>
      if position = source operation then
        execute remaining (destination operation)
      else none

def aFirst : List Operation := [.aOut, .aBack, .bOut, .bBack]
def bFirst : List Operation := [.bOut, .bBack, .aOut, .aBack]
def overlapping : List Operation := [.aOut, .bOut, .aBack, .bBack]

def Respects (schedule : List Operation)
    (dependency : Operation → Operation → Prop) : Prop :=
  ∀ following previous, dependency following previous →
    schedule.idxOf previous < schedule.idxOf following

theorem sources_and_destinations_differ (operation : Operation) :
    source operation ≠ destination operation := by
  cases operation <;> decide

theorem schedules_have_exactly_the_same_operations :
    aFirst.Nodup ∧ bFirst.Nodup ∧ overlapping.Nodup ∧
      ∀ operation : Operation,
        operation ∈ aFirst ∧ operation ∈ bFirst ∧ operation ∈ overlapping := by
  refine ⟨by decide, by decide, by decide, ?_⟩
  intro operation
  cases operation <;> decide

theorem both_serial_orders_restore_original_particle :
    execute aFirst .marker = some .marker ∧
      execute bFirst .marker = some .marker := by
  decide

theorem overlapping_moves_are_not_enabled :
    execute overlapping .marker = none := by
  decide

theorem common_precedence_is_respected_by_overlap
    (previous following : Operation)
    (before_in_a : aFirst.idxOf previous < aFirst.idxOf following)
    (before_in_b : bFirst.idxOf previous < bFirst.idxOf following) :
    overlapping.idxOf previous < overlapping.idxOf following := by
  revert before_in_a before_in_b
  cases previous <;> cases following <;> decide

theorem graph_admitting_both_orders_admits_overlap
    (dependency : Operation → Operation → Prop)
    (admits_a : Respects aFirst dependency)
    (admits_b : Respects bFirst dependency) :
    Respects overlapping dependency := by
  intro following previous edge
  exact common_precedence_is_respected_by_overlap previous following
    (admits_a following previous edge) (admits_b following previous edge)

theorem no_graph_admits_both_orders_and_rejects_overlap :
    ¬∃ dependency : Operation → Operation → Prop,
      Respects aFirst dependency ∧ Respects bFirst dependency ∧
        ¬Respects overlapping dependency := by
  rintro ⟨dependency, admits_a, admits_b, rejects_overlap⟩
  exact rejects_overlap
    (graph_admitting_both_orders_admits_overlap dependency admits_a admits_b)

end Define.OperationGraph.DestructorOrderChoice
