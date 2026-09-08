# Complete Particle Operation graph algorithm

Copy `algorithm.py` and `graph.py` together into the operation graph design
directory. They use a relative import and have no dependency on the research
harness or archived algorithms. They are reference artifacts, not a replacement
for compiler source analysis.

[rules.md](rules.md) describes the complete rule set, including Vanish.

## Input

`Calculator.add(Operation(...))` receives one resolved Create, Move, or Vacate.
Operation occurrences are numbered from zero in processing order. A particle's
identity is its Create occurrence. Positions have separate integer identities.
Replacing a particle does not reuse the original particle's identity or its
assigned positions' identities.

The fields describe actual resolved requirements, not every spatial ancestor:

| Field | Meaning |
| --- | --- |
| `occupied` | Intermediate positions in the actual Position References. |
| `fill` | The Create's or Move's target position, if any. |
| `empty` | The Move's source or the position emptied by Vacate, if any. |
| `quality_particles` | Distinct particles whose assigned qualities the actual references use. Their Create occurrences supply both Create requirements and lifetime identities. |
| `defines` | Assigned positions made available by this Create. |
| `ordinary_occupants` | Particles observed in ordinary intermediate occupancy released by their Vacates; exclude retained destructor occupancy. |
| `moved` | The directly moved particle, if any; not its transitive children. |
| `vacated` | The original particle selected by this Vacate, if any. |

The input is valid resolved Define code. Source analysis has combined repeated
references to the same position and identified all actual quality requirements.
It has chosen a permitted serial ordering of conflicting destructor operations.
The calculator does not validate source or choose that ordering.

Before applying selected Vacates, `retain({ordinary: retained, ...})` preserves
the position information needed by destructors. Every destructor accessing the
same original position must use the same retained identity. Preserve it once,
not once per destructor. Subsequent accesses share its changing state.
The ordinary and retained identifiers select different dependency information
for the same original position; retaining information does not create a new
position.
`forget(...)` may release position information once it has no future uses.

`simultaneous(...)` accepts the Vacates selected together. Their inputs have only
their actual Position References; a transitive child Vacate has no references
through its displayed name. Enumeration does not add execution dependencies.

## Completion and graph access

Call `finish()` once, after all Create, Move, and Vacate requirements are known.
Do not add operations afterward. It returns the particle-to-Vanish mapping.
Only particles with an observed Vacate receive a Vanish; a partial input may
leave particles alive.

The completed `calculator.graph` contains every explicit operation and edge.
`dependencies(occurrence)` returns direct dependencies.
`reaches(following, previous)` tests strict dependency reachability, including
queries involving Vanishes. Vacate/Vanish combination is not performed.

Vanishes have no dependents. The graph therefore stores their dependencies but
does not add them to its reverse construction-time reachability index. This
changes storage and query implementation, not the graph.

Comparison uses `reaches_indexed(...)`: none of its candidates can be a Vanish.
This avoids terminal-operation checks during graph construction. General queries
on the completed graph use `reaches(...)`.

## Implementation choices

Position Collection and particle-use maintenance share the same candidates.
A collected candidate already precedes the new operation even when Comparison
does not retain its direct edge. Bounded optional pruning can therefore reuse
that collection without querying or copying the newly stored graph row.

Only non-covered quality uses require particle-use sets. Vacates and the most
recent direct Moves are remembered separately. Finalization reuses the Vacate
mapping for Vanish occurrences and releases position and particle-use state.

The existing bounded reachability cache and comparison thresholds are retained.
The cache is an optional speed optimization, not transitive-closure storage.
See [the experiment report](../integrated_experiments.md) for measurements,
alternatives, and limits of the recommendation.
