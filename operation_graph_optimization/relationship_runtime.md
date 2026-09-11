# Atomic relationship permission experiment

`relationship_runtime.c` implements the three competing Moves from
`identity_move_conflict.dfn`, together with their Vacates and Vanishes. The
three supplying Creates have already completed. This is a manually written
runtime experiment, not compiler-generated C or a general relationship solver.

Initially Q occupies P's child position. A moves Q away, B moves P to a child
position of R, and C moves R to a child position of Q. Before any Vacates,
the permitted Move orders are ABC, ACB, BAC, and CAB. BCA and CBA would make
P, Q, and R circular parents of each other.

The additional permission for B is: A completed, or C has not completed, or
R's Vacate completed. The additional permission for C is: A completed, or B
has not completed, or P's Vacate completed. Ordinary prerequisites still
apply. In particular each Vacate follows the Move supplying its selected
position. The Vacate alternatives allow B then P's Vacate then C before A,
and C then R's Vacate then B before A.

One atomic state transition checks the permission and publishes the logical
effect. A competing Move cannot act on an earlier permission decision. The
test records this atomic order and independently checks position occupancy,
parent relationships, and particle lifetimes. Each operation receives two
arrivals, with exactly one claiming execution. Synchronization metadata remains
alive until every arrival thread has finished, including losing arrivals.

Particle objects are actually allocated and freed. Operations read the
particles they require before publishing completion, and do not use them
afterward. This checks the proposed lifetime edges; it does not model mutable
particle values or external calls.

Validation used Clang 22.1.8 with `-Wall -Wextra -Werror`, pthreads, and separate
AddressSanitizer/UndefinedBehaviorSanitizer/LeakSanitizer and ThreadSanitizer
builds. Each build passed 206 schedules: four forced Move orders, the two
Vacate-mediated orders, and 200 racing runs with duplicate arrivals. The
Python test
`test_specialized_runtime_permissions_match_every_reachable_state` separately
compares these permission formulas with the particle-state interpreter at
every reachable state of this example.

These results support correctness for this finite example. They do not compare
atomic instruction costs or establish the best runtime representation for
larger interacting groups.
