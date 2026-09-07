# State-driven randomized workloads

[state_workloads.py](state_workloads.py) chooses the next statement from the
current occupancy, not from a predetermined sequence or from the graph being
tested. Creates, Moves, and Destroy statements can occur anywhere in the random
region where they are valid. A Destroy may select several simultaneous Destroys.
There is no creation phase, movement phase, or destruction phase.

Large runs measure the generated prefix of operations. They stop after the
requested number of caller statements, potentially with particles still present,
rather than adding an automatic end-of-action destruction phase. The schedule
checker verifies that same final occupancy. These are construction benchmarks
for valid prefixes, not timings for compiling complete applications.

## What programs it generates

The fixture has several position constraint shapes, numbered by `rank`. This is
generator metadata, not a Define language concept. A particle created at rank
`r` defines `branching` positions of rank `r - 1`, unless `r` is zero. There are
`width` initially empty positions of each rank, through the configured `depth`.

Each rank also assigns a distinct constructor action. These qualities make
different ranks incompatible, including leaves: a particle cannot move to a
position requiring a different rank's constructor. Every occupied position can
therefore supply a Move to every empty position of the same rank. That includes
Moves between different particles' child positions and between child and local
positions, not just predetermined pairs. Moving a particle changes where it is;
its child positions keep their identities and occupancy.

Each constructor creates and destroys a particle at a local temporary position.
Those two real callee operations are included in the generated operation list.
They are not choices available to the caller, nor are they extra sampler rules
requiring a randomly created particle to be destroyed next. They contribute no
extra wait for the caller's Create under the whole-program graph rules used in
this investigation. Reported `steps` count sampled caller statements; reported
operations additionally count constructor work and transitive Destroys.

With `--access local`, references begin at local positions. With
`--access implied`, they begin at qualities implied by the current action. The
latter includes an initial Create representing that action's particle and
requires its existence, without requiring it to occupy any particular position.
References to further child positions still need their intermediate positions
occupied.

The sampler covers all Create, Move, and Destroy statements available to the
caller **within this declared fixture**. It is not a generator for every valid
Define program. In particular, it does not randomize arbitrary action contracts,
Moves that discard some position constraints, or destructor bodies interacting
with retained particles. The current action's own particle is not moved by the
caller. The earlier targeted workloads remain useful for those other access
patterns, especially direct implied access to a moving particle's qualities and
shared destructor state.

## Selection without an ordering bias

For each rank, two indexed collections hold its empty and occupied positions.
Selecting a list index is uniform. Removal swaps in the last item, so removal
cost is constant; the changed storage order does not favor any eligible choice.

For `E` empty and `O` occupied positions of a rank there are:

- `E` possible Creates;
- `O * E` possible Moves;
- `O` possible Destroy statements.

An integer ticket selects any member of each collection of choices. A Move's
ticket selects both its source and destination without enumerating their
Cartesian product. Counting and decoding cost scales with the configured number
of ranks, not with the number of possible Moves. No eligible choice is removed
because it would produce an inconvenient graph.

The distributions deliberately answer different questions:

- `concrete`: every valid caller statement has equal probability at that step.
- `balanced`: every available operation kind has equal probability, then every
  choice of that kind has equal probability.
- `growth`: operation-kind weights of 8 Create, 4 Move, 1 Destroy.
- `movement`: weights of 1 Create, 12 Move, 1 Destroy.
- `destruction`: weights of 4 Create, 1 Move, 4 Destroy.

Unavailable kinds receive zero weight; every available kind has positive weight.
These are conditional distributions at the current state, not uniform
distributions over whole programs. Even uniform selection among concrete
statements can strongly favor Moves because there may be far more valid Moves
than Creates or Destroy statements.

## Independent checks

[The integration tests](state_workloads_integration_test.py) use five seeds and
all five distributions with both local and implied access. At every sampled
state they enumerate the full set of valid caller choices from position
occupancy, independently of the maintained collections. They compare that set
with every selectable ticket and check that no choice is duplicated. They also
shuffle the collections and repeat the check. This checks every choice in each
visited state, not every possible state of an unbounded program.

The tests render actual Define source, including constraints and constructors,
and require the compiler to accept it with no exceptions or diagnostics. A
source-only epilogue exercises declarations and constraints that the random
region might never use. It does not influence earlier sampling and is not part
of the large performance workloads.

The resulting graphs are compared with the independent full-history reference.
Random runtime schedules check exact particle identities, vacancies, and Create
dependencies. Successful performance runs perform that execution check too; they
do not merely time construction of an unchecked graph.

## Independent input-order randomization

[order_variants.py](order_variants.py) constructs a separate conflict graph for
the supplied operations. It preserves occupancy changes, uses before emptying,
and particle-existence requirements. It does not call the rule algorithm, use
its calculated graph, or perform transitive minimization. Redundant edges are
acceptable in this benchmark-only graph because they do not change the permitted
orderings.

The reorderer repeatedly selects a random ready statement. Simultaneous Destroy
groups remain whole, and Create occurrence identifiers are remapped. The
integration tests verify the reordered graph against the original graph after
mapping operation identities, and validate the reordered caller source with the
compiler. Random ready selection does not claim uniform sampling over all
topological orders.

Use `--reorder-seed` with either the state-driven or the earlier targeted
workloads. Reordering time is reported separately from generation and rule
calculation. Its temporary memory is included in the process's cumulative peak;
that peak must not be mistaken for the rule algorithm's isolated memory use.

## Reproduction

After the local development setup described in the [README](README.md):

```sh
uv run -m operation_graph_optimization.benchmark --workload state --steps 1000000 --width 100 --depth 4 --branching 2 --distribution concrete --seed 17
uv run -m operation_graph_optimization.benchmark --workload state --steps 1000000 --width 100 --depth 4 --branching 2 --distribution balanced --access implied --reorder-seed 41 --seed 17
uv run -m operation_graph_optimization.benchmark --workload overlapping --steps 1000000 --width 1000 --seed 17 --reorder-seed 41
```

The benchmark retains its resource limits: 2 GiB virtual address space and 120
CPU seconds by default. Resource-limit failures are experimental results, not
successful validations. [Measurements and failures](state_benchmarks.md) are
recorded separately from the older structured-workload results.
