# Incremental relationship exclusions

The construction experiments in `relationship_exclusion.py` use ordinary
dependency reachability, not a search over schedules. Exhaustive enumeration
appears only in the independent tests. This is a derivation of components, not
a complete replacement algorithm or a proof about the unchanged Define spec.

## Two opposite relationships

Let one relationship have beginning A and ending a, and its opposite have
beginning B and ending b. Source execution places A through a before B through
b. Each ending may be a conjunction of operations.

The relationships cannot overlap. Their restriction is that all of a precedes
B, or all of b precedes A.

- If ordinary dependencies already put all of a before B, nothing is added.
- If any member of b follows A, putting all of b before A would give a cycle.
  Only the first direction remains: collect a for B.
- Otherwise retain the exclusion, rather than selecting one direction.

These tests are exact for this one exclusion. Adding edges from all members of
b to A creates a cycle exactly when A already reaches one of those members.
Any new cycle must enter A through one such edge and leave through an existing
path. Conversely that existing path and the added edge exhibit a cycle.
Source order supplies the other direction's consistency.

For a joined ending, omit members already preceding its target beginning, then
apply ordinary Comparison to the remaining members. This removes only
prerequisites supplied by another retained prerequisite. It does not establish
minimality through other exclusions.

The original deadlock example is `future_moves_must_remain_executable` in
Define's normal operation graph testdata. Its earlier visit begins when visitor
enters parent's `/landing` and ends when visitor leaves. The opposite visit ends
when parent can move to `other`. That ending depends on the earlier visit's
beginning through two vacancies, so the opposite visit must wait.

The paired fixture `independent_departure_preserves_both_visit_orders` changes
that last destination to the initially empty `result`. Both directions then
remain possible.

## Information encountered later in the serial walk

The two source variants have the same entry operations. Their difference is in
the later departure. The compiler therefore cannot irrevocably finalize the
entry restriction when it first encounters that entry.

Register the relationship record at its beginning and connect its ending when
that operation is processed. An unfinished ending is not an ending known to be
absent at a boundary. Updating a pending restriction is different from revisiting
possible execution orders. How those updates maintain minimality in dependent
records is still an obligation of the full construction.

## Two disjoint exclusions connected by departure dependencies

The fixture `disjoint_relationship_visits_share_departure_dependencies` has
particles P and Q created at `first` and `second`, and R and S created at
`third` and `fourth`. Its significant statements are:

```define
move the particle in position<first> to position<second>::position</child>.
move the particle in position<second>::position</child> to position<handoff_to_fourth>.
move the particle in position<handoff_to_fourth> to position<first>.
move the particle in position<third> to position<fourth>::position</child>.
move the particle in position<fourth>::position</child> to position<handoff_to_second>.
move the particle in position<handoff_to_second> to position<third>.
# Each reverse visit can happen early, but they cannot both happen early.
move the particle in position<second> to position<first>::position</child>.
move the particle in position<first>::position</child> to position<handoff_to_second>.
move the particle in position<fourth> to position<third>::position</child>.
move the particle in position<third>::position</child> to position<handoff_to_fourth>.
destroy the particle in position<first>.
destroy the particle in position<third>.
destroy the particle in position<handoff_to_second>.
destroy the particle in position<handoff_to_fourth>.
```

Starting after the four Creates, the problematic prefix is:

| Step | Operation | P | Q | R | S |
| --- | --- | --- | --- | --- | --- |
| 0 | All four Creates have completed | `first` | `second` | `third` | `fourth` |
| 1 | `test.move(second, first::/child)` | `first` | `first::/child` | `third` | `fourth` |
| 2 | `test.move(fourth, third::/child)` | `first` | `first::/child` | `third` | `third::/child` |

There is no particle cycle. But P cannot enter Q's child position while Q is
P's child, and R cannot enter S's while S is R's child. Q cannot leave until R
completes the earlier occupancy of `handoff_to_second`. S cannot leave until P
completes the earlier occupancy of `handoff_to_fourth`. The positions being
initially empty does not permit swapping their successive occupants' complete
uses. Final Vacates depend on those last Moves and cannot rescue this prefix.

For the derivation, call the forward P/Q visit A to a and the reverse B to b.
Call the forward R/S visit C to c and the reverse D to d. Ordinary departures
give c before b and a before d. If B and D both precede a and c, the original
exclusions give b before A and d before C. Together these require:

```text
c < b < A < a < d < C < c
```

Therefore at most one of B and D may begin until a or c completes. Either
completion removes this additional exclusion. This is a necessary derived
restriction, not an additional semantic requirement or an arbitrary fixed order.

The independent particle interpreter finds 177 reachable completed sets,
including exactly one from which execution cannot complete: the two early
reverse entries. The conditional rule accepts exactly all transitions between
the other 176 sets. Each reverse entry alone remains permitted.

## Scope and evidence

- All sixteen four-event ordinary dependency graphs for one exclusion agree
  with the direct rule over every order.
- One hundred six-event ordinary graphs also test paths through other events.
- One thousand generated two-particle programs compare every permitted prefix
  with the independent completion oracle, including final Vacates.
- Joined-ending cases test independent members, ordered members, an already
  supplied member, and an impossible reverse alternative.
- The four-particle composition case includes all final Vacates. Particle
  existence is retained throughout this small model; its full source fixture
  separately records Vanish requirements.

These results do not prove general composition, minimality across exclusions,
or modular summary sufficiency. The next construction question is how to record
and compose departure dependencies directly, rather than enumerate cycle
conditions or search combinations of their alternatives.
