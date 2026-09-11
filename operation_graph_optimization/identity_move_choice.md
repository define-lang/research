# Alternative prerequisites for reversing particle relationships

The valid source in [identity_move_choice.dfn](identity_move_choice.dfn) creates
P, Q, and R. Q occupies P's `/child`; R occupies Q's `/inner`; R's `/end` is
empty. After the Creates, the three Moves have these resolved effects:

| Move | Particle | Source position | Target position |
| --- | --- | --- | --- |
| A | Q | P's `/child` | `detached_child` |
| B | R | Q's `/inner` | `detached_grandchild` |
| C | P | `parent` | R's `/end` |

All six endpoint positions are distinct. Each Move has its selected particle at
its source and an empty target in every permutation. All particles and positions
exist throughout these Moves. All permutations produce the same final
occupancy.

If C executes first, P occupies a transitive child position of itself: P defines
the position occupied by Q, Q defines the position occupied by R, and R defines
the position now occupied by P. Either A or B removes that cycle. Either A or B
executing before C prevents it from arising. The safe orders are therefore
exactly ABC, ACB, BAC, and BCA. CAB and CBA violate principle 3 immediately after
C.

This result uses the five DLP 44 principles as design requirements. It is not a
claim that the existing specification's dependency construction permits these
four orders.

## What a fixed dependency graph can express

A graph with A preceding C admits ABC, ACB, and BAC. A graph with B preceding C
admits ABC, BAC, and BCA. Either is safe. Requiring both predecessors admits only
ABC and BAC and unnecessarily orders work.

No fixed dependency DAG can admit all four safe orders while excluding both
unsafe orders. Each pair of Moves occurs in both relative orders among the four
safe executions. A graph admitting all four therefore cannot require precedence
between any pair. Without such a requirement it admits CAB and CBA as well.

Additional fixed prerequisite nodes cannot express the missing alternative:
projecting a fixed DAG onto its Move nodes still gives a partial order. A
prerequisite that completes after either A or B requires a choice mechanism,
not the ordinary requirement that all incoming dependencies finish.

Both one-edge graphs are maximally permissive safe DAGs for these Moves; neither
admits every safe execution. The distinction is between choosing a maximally
permissive fixed graph and retaining the runtime choice of either sufficient
prerequisite. The latter changes the dependency model, not the five principles.

## Validation

[identity_move_choice_test.py](identity_move_choice_test.py) validates the real
Define source, enumerates all six Move orders and their intermediate
relationships, and checks all 64 directed edge subsets on the three Move nodes.
The largest safe schedule families expressible by those graphs have three
orders each, and are exactly the two families described above.

Command:

```sh
bazelisk test --noshow_progress --ui_event_filters=-info //operation_graph_optimization:identity_move_choice_test
```

All three tests passed. The compiler check establishes source validity only;
the schedule and graph enumeration do not use its dependency graph as an
oracle.
