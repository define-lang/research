# Completed-set continuation search

`relationship_state.py` answers the same finite continuation question as
`relationship_periods.completion_order`. It explores legal next effects and
caches success or failure by the set of completed operations. A successful
entry holds one next operation rather than a copy of the entire suffix.

The correspondence rests on a semantic property: two legal prefixes with the
same completed operations have identical occupancy, lifetime, and preserved
destruction state. Therefore they allow the same suffixes. The independent
particle-state exploration checks this property and the search's answers for
every reachable state of 40 generated examples. Returned suffixes are replayed
through that interpreter, including the occupied result of a destructor's final
restoration before preservation ends.

## Repeated-query experiment

The generator is `retained_relationship_test.generated_example`, with seed
480161. For each row, generate 20 examples with three particles, nine possible
positions, the indicated number of random ordinary Moves, zero or two
destructor Moves, and three each of Create, Vacate, and Vanish. Generate four
random legal walks per example, choosing uniformly among currently permitted
effects. Query every distinct completed set encountered, including any dead-end
prefix. All workload generation and query construction precede timing.

The clause implementation receives ordinary edges plus the completed-before-
unfinished prefix edges. The state implementation prepares one search per
example and shares its results between queries. Both preparation and search
are timed. Results remain alive until timing ends. Three repetitions gave:

| Ordinary Moves | Queries | Cached sets | Clause-search median (s) | State-search median (s) |
| --- | --- | --- | --- | --- |
| 4 | 752 | 1096 | 0.010640 | 0.001708 |
| 8 | 898 | 1342 | 0.022035 | 0.002450 |
| 16 | 1061 | 1497 | 0.040950 | 0.003603 |
| 32 | 1294 | 2034 | 0.135776 | 0.007810 |

Raw seconds, in repetition order:

| Ordinary Moves | Clause search | State search |
| --- | --- | --- |
| 4 | 0.010640012, 0.010585761, 0.010665163 | 0.001708427, 0.001728638, 0.001635986 |
| 8 | 0.022516245, 0.022034997, 0.022025907 | 0.002449990, 0.002320488, 0.002534091 |
| 16 | 0.041746246, 0.040950203, 0.040787261 | 0.003626499, 0.003562108, 0.003603158 |
| 32 | 0.130715268, 0.136256687, 0.135775660 | 0.007934839, 0.007810037, 0.007784886 |

Both implementations agreed on every answer in every repetition. Environment:
AMD Ryzen 9 9950X, Linux 7.1.8, CPython 3.14.6 free-threading build, as in the
other identity-construction experiments.

This measures batches of continuation questions on small interacting examples,
not million-operation graph construction or runtime atomics. It favors reuse
between nearby prefixes; the clause implementation does not retain information
between queries. There can still be exponentially many completed sets. The
result does not justify applying this search to an entire large program or
claiming a generally optimal cache policy.

## Isolating interacting choices

`PartitionedSearch` groups the boundaries of possible cyclic relationships and
ordinary paths that can couple those groups. Its search state excludes other
operations; their ordinary dependencies remain in the execution graph. The
constructor can reuse the compact graph's existing dependency and nonterminal
dependent indexes. `from_edges` builds adjacency only for tests and inputs that
do not already supply it.

The first implementation grouped every operation, including isolated ones. For
two independent four-event choices and otherwise unrelated operations, grouping
took 0.000528, 0.005876, 0.064193, and 0.718828 seconds at 1,000, 10,000, 100,000,
and 1,000,000 operations (medians of three). That work was unnecessary:
grouping now visits ordinary paths from and to boundary events using existing
adjacency. An operation outside every such path cannot couple the choices.

Tests compare local and global continuation answers at every legal prefix of
independent groups and groups coupled by an ordinary path through another
operation. They also check one-way predecessors and successors, an acyclic
possible-relationship graph, and the valid-source acyclic dead-end example.

## Full construction on the random-tree family

`identity_benchmark --sizes 1000 10000 200000 --repeats 3` includes the ordinary
graph, lifetime calculation, relationship periods, and local-search preparation.
Inputs and complete dependency comparisons are outside the timer. Raw results
are in `identity_partitioned_results.json`.

| Operations | Including local-search preparation (s) | Prior backend (s) |
| --- | --- | --- |
| 5,000 | 0.007666 | 0.009238 |
| 50,000 | 0.078270 | 0.115181 |
| 1,000,000 | 2.661197 | 2.939555 |

This family has no possible relationship cycles, so it verifies the inexpensive
no-search path, not the cost of solving a large coupled group. The 50,000-event
samples were noticeably noisier than the other sizes; do not treat their ratio
as a precise improvement claim. The prior backend's construction behavior is
unchanged; its graph now additionally exposes the existing nonterminal dependent
index for the new constructor.
