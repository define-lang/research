# Working on Operation Graph Proofs

Validate existing and new proof work against the
[conceptual definitions and model-correspondence checks](definitions/definitions.md#conceptual-meaning-of-particles-positions-and-operations).

For the Particle Operation proofs, the Action Parent Rule is excluded. No
ordering between individual destructions may be added beyond what the spec's
Particle Operation Dependency Graph rules derive, including dependencies arising
from destructors accessing contracted positions. In particular, neither parent
and child names nor an enumeration used by the proof supplies an execution
order.

Prove minimality and completeness independently: neither proof may assume the
other's result. Combine them in characterization; derive maximum safe
concurrency afterward, not as a premise of the graph proofs.

The specified construction must itself produce transitive minimality. Never add
a generic transitive minimization algorithm as a construction step; a
cover-graph characterization is a proof about the result, not an additional
calculation.
