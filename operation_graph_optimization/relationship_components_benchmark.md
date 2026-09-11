# Restricting relationship analysis to interacting particles

Environment: AMD Ryzen 9 9950X, Linux 7.1.8, CPython 3.14.6 free-threading
build. These are wall-clock measurements with three repetitions. Workload
generation and correctness checks are outside the timed intervals. These are
isolated relationship calculations, not complete graph-construction timings.

## Acyclic ancestry

The workload is a chain of parent relationships, numbered so that the original
cycle collector repeatedly follows each remaining suffix. No cycle condition
is needed. The operation order creates each defining parent before its child.

The original source is preserved in
`relationship_periods_before_components.txt`. Its three collection samples at
1,000 particles were 1.016139, 1.012647, and 1.044877 seconds; its certificate
checks took 0.027901, 0.027860, and 0.027844 seconds. At 200 particles its
collection samples were 0.011688, 0.011589, and 0.011503 seconds; at 500 they
were 0.143886, 0.141920, and 0.142376 seconds.

The revised calculation first finds strongly connected components of possible
parent relationships. A cycle cannot leave its component and return. Removing
cross-component periods therefore preserves every condition and every detected
violation, while preventing these repeated acyclic walks.

| Particles | Collection median (seconds) | Certificate median (seconds) |
| ---: | ---: | ---: |
| 1,000 | 0.000620 | 0.000493 |
| 10,000 | 0.006369 | 0.005247 |
| 100,000 | 0.076752 | 0.063696 |
| 1,000,000 | 0.873328 | 0.670095 |

This improves an avoidable acyclic cost. It does not bound cycle enumeration
within a mutually reachable group, or the exact search needed for jointly
constrained groups. It changes no semantic rule.

## One choice among unrelated operations

The second workload has one two-operation choice and otherwise unrelated
operations. Factoring the choice calculation prevents a reachability closure
over all the unrelated operations. Local completion orders are composed with
ordinary precedence to produce one checked certificate. The extra certificate
edges are not installed as mandatory runtime dependencies.

| Operations | Completion median (seconds) |
| ---: | ---: |
| 1,000 | 0.001326 |
| 10,000 | 0.013355 |
| 100,000 | 0.162746 |
| 1,000,000 | 1.862599 |

Reproduce the revised measurements with:

```sh
uv run --frozen python -m operation_graph_optimization.relationship_benchmark --sizes 1000 10000 100000 1000000 --repeats 3
```

All raw revised samples are in `relationship_components_results.json`.
The benchmark represents finite mathematical inputs, not a claim that these
measurements include Define parsing, identity resolution, ordinary dependency
construction, or lifetime collection. Memory was not measured in this run.

## Correctness checks

The factored certificate is checked against all total orders of 150 seeded
six-event constraint systems, including randomly chosen prefixes. Existing
retained-state tests compare eager and discovered cycle conditions against
independent operation-state exploration. An action-boundary case additionally
starts with a parent relationship already present and requires both of its end
events before the reverse relationship can begin.
