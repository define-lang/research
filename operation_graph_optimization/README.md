# Operation graph rule investigation

## Vacate/Vanish combination experiment

[Early combination](combination_experiments.md) tests skipping lifetime tracking
when ordinary occupancy already orders every particle requirement before Vacate.
It compares that shortcut with combination at finalization and with the explicit
complete graph. The experimental implementation is `combination_algorithm.py`;
the previous `complete/` deliverables remain unchanged.

## Vanish follow-up

[Vanish collection](vanish_rules.md) extends the investigation to particle
lifetimes. The standalone result is [vanish_algorithm.py](vanish_algorithm.py);
it shares the position graph without changing its dependencies. Competing
strategies remain in [vanish.py](vanish.py). See
[the experiments](vanish_experiments.md) for measurements, limitations, and
reproduction commands. The historical results below do not include Vanish.

## Position dependency investigation

Start with [the rules](rules.md). The standalone implementation is
[algorithm.py](algorithm.py); [graph.py](graph.py) supplies compact storage and
bounded reachability indexing. Neither file uses the compiler's graph builder.

[The derivation](analysis.md) explains the specializations, correctness
arguments, costs, and rejected alternatives. The result preserves the specified
requirements and constructs transitively minimal dependencies directly. It does
not calculate a redundant complete graph and then minimize it.

[Measurements and reproduction commands](benchmarks.md) cover eleven workload
families across three seeds, with [raw results](benchmark_results.json).

[State-driven workloads](state_workloads.md) add freely mixed valid caller
statements, exhaustive choice checks on small visited states, and independent
input-order randomization. Their broader distributions expose performance
limitations that the earlier structured families did not exercise. See
[the measurements and failures](state_benchmarks.md), with
[complete raw records](state_benchmark_results.json).

[Follow-up optimization experiments](optimization_experiments.md) describe the
the earlier optimization stages, their performance trade-offs, and validation.
The earlier measurements above remain records of the baseline.

[Cache sizing](cache_sizing.md) measures byte-budget trade-offs, actual
allocation, and eviction pressure, and explains why the default remains 64 MiB.

[Target-count sizing](target_sizing.md) compares target ceilings across the
workloads, including byte-only limiting, and supports retaining 1,024 targets.

[Threshold measurements](thresholds.md) describe the current optional-work
limits and Comparison crossover, including fine-grained and large-input checks.

[Parent-Create collection experiments](collection_experiments.md) compare
inserting then removing covered Creates with skipping their insertion. They
preserve all repetitions, source snapshots, and replay instructions, and
distinguish the measured algorithm from the later, correctness-tested but
unbenchmarked simplification of simultaneous Vacates.

## Input and use

The caller resolves valid Define source into `Operation` requirements. Position
identifiers preserve defining-particle identity and distinguish retained
destructor state from ordinary occupancy. Particle requirements identify their
Create occurrences. See the precise
[input contract](rules.md#implementation-boundary).

Use `Calculator.add` for an ordinary operation, `retain` before simultaneous
vacancies when destructors need the original state, and `simultaneous` for a
group of vacancies. All users of retained state use the same retained position
identifiers. `forget` releases records only after the caller proves no future
access is possible. The result is `calculator.graph`; `dependencies(i)` reads
the dependencies of occurrence `i`.

Source resolution, action expansion, destructor interaction analysis, and
reclamation are not implemented here. In particular, an ordinary vacancy is not
a particle's reclamation event. Costs count expanded occurrences and resolved
requirements, not just written statements.

## Checks and benchmarks

[Integration tests](algorithm_integration_test.py) validate real generated
Define source, compare against an independent full-history
[reference](reference.py), and test exact particle identities in randomized
execution schedules. The compiler validates source but does not supply expected
graphs. [Workloads](workloads.py) include repeated movement, old vacancy reuse,
simultaneous destruction, and shared dependencies. [Validation](validation.py)
is separate from the timed rule calculation.

Run the checks:

```sh
bazelisk test --noshow_progress --ui_event_filters=-info //operation_graph_optimization/...
```

For local Python, use the archive's locked dependencies:

```sh
uv sync --frozen
uv run --frozen -m operation_graph_optimization.benchmark --workload overlapping --steps 1000000 --width 1000 --seed 17
```

The benchmark reports generation, calculation, and randomized schedule-check
time separately, plus cumulative peak resident memory at each phase. Its default
process limits are 2 GiB of virtual address space and 120 CPU seconds. Use
`--cache-targets 0` to measure the uncached implementation. The defaults allow
1,024 cached targets sharing a 64-MiB logical byte budget; `--cache-mib` changes
that budget. These settings change only reachability acceleration, not the
rules.

For `--workload deep`, `--width` specifies written-reference depth. That
workload also renders matching source during generation; it does not time
compilation. The reported requirement counts distinguish long references from
large counts of short operations.

To collect coverage of the archived Python implementation:

```sh
bazelisk coverage --noshow_progress --ui_event_filters=-info --combined_report=lcov '--instrumentation_filter=^//operation_graph_optimization[/:]' //...
```

See [repository instructions](../AGENTS.md) for pre-commit checks. Commands in historical
reports describe the original Define checkout and may refer to tools not copied
into this archive.

The Lean theorem in [rule_equivalence.lean](rule_equivalence.lean) checks the
candidate-subset correspondence used by the specialized rules. It is not a
formal verification of the Python implementation.

Validation outcomes for the current implementation are recorded with the
follow-up experiments. Benchmark runs are separate from coverage and never time
source generation, reordering, or execution checking as graph construction.

## Complete graph follow-up

[complete/](complete/) contains the standalone integrated algorithm and complete
rules for Create, Move, Vacate, and Vanish. It supersedes the separate position
algorithm plus Vanish collector as the recommended reference implementation.
The earlier files and measurements remain historical research artifacts.

[The integrated experiment report](integrated_experiments.md) compares complete
construction time, memory, and graph equality across the alternatives.

## Meaning of optimality

The graph is transitively minimal and preserves maximum safe concurrency for the
chosen permitted conflict orientation. Those are correctness properties, not
claims that its calculation is universally fastest.

The implementation optimizes time subject to bounded auxiliary indexing and
linear graph storage. Collection has a linear accounting bound in requirements,
collected candidates, and retained-use copies. Reachability work is additional;
the bounded cache does not establish a linear worst-case total. No matching
lower bound for all valid Define inputs has been proved. Measurements can select
an implementation among tested alternatives, but cannot close that mathematical
optimality gap.
