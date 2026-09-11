# Dependency Construction Details

These are constructions and optimizations for the
[core rule changes](core_rule_changes.md), not additional semantic premises.
Replace superseded details when discoveries change the construction; retain
experiment history in the research repository.

## Identity and occupancy records

- Resolve operation identities in the serial interpretation, including implied
  and interface positions through Action Contracts. Distinguish each Action
  Execution's local positions from the assigned action's interface positions.
- Keep one setter per identified position. Initially use the Create of the
  particle defining that position, including an action's parent particle.
  Initially available positions without such a Create have no initial setter.
- Collect the setters of positions filled or emptied by an operation. Apply
  Comparison, then replace those setters. Intermediate-position readers are
  unnecessary.
- Preserve successive occupancy order even when an entire earlier occupancy
  could otherwise exchange order with a later one.

## Destruction bookkeeping

- Destructors sharing an original position use its shared, changing occupancy
  and setter, not independent copies. Process their operations in the chosen
  permitted destructor order without ordering unrelated positions.
- Distinguish occupancy visible outside a Simultaneous Transitive Destruction
  from occupancy preserved for its destructors and transitively triggered
  actions.
- Track each selected particle's Vacate and last direct Move during destruction.
  Both must finish before its occupancy preservation ends. Uses of its own child
  positions require its existence, not its occupancy.
- Check the occupied result of a final Move before releasing that occupancy.
  Release does not undo the Move or restore the selected position.

## Incremental relationship construction

- Keep an unfinished ending distinct from a relationship known to continue
  beyond a graph boundary. A later statement can supply a departure dependency
  that forces an earlier entry to wait. A pending record must therefore update
  its existing entry restriction when that ending becomes known.
- Two disjoint exclusions can be connected by their departures' ordinary
  dependencies. In the tested pattern, the second period of each pair needs the
  first period of the other pair to end. The two second-period entries need a
  conditional exclusion until either first period ends; shared ancestry is not
  necessary for this connection.
- The direct two-period comparison also handles joined endings. One ending
  member depending on the other period's beginning rules out that entire reverse
  alternative. Apply ordinary Comparison within an ending Join.

- Record uninterrupted periods of each child-to-parent particle relationship.
  Moves between positions defined by the same particle do not interrupt it. An
  end during destruction can require both a Vacate and a direct Move.
- Derive update rules using ordered direct Moves of each particle, ordered
  occupants of each position, and the acyclic parent relationships in the serial
  interpretation. Records must describe these facts rather than sets of future
  execution orders.
- Determine which relationship removals provide sufficient prerequisites for a
  new relationship, and how later Moves update or release those prerequisites.
  Account for interacting choices without a general search at compilation or
  runtime.
- Immediate absence of a particle cycle is not enough: validate against the
  known legal prefixes that nevertheless prevent required later Moves.
- Enumerating cycles, solving alternative precedences, and caching completed
  operation sets remain independent small-case oracle techniques only. Their
  correctness does not establish an acceptable incremental algorithm.

## Vanish dependencies

- Accumulate operations requiring the particle to exist, its Vacate, and its
  most recent direct Move. Ordinary Comparison can prune candidates dominated by
  another candidate.
- The last-candidate characterization can check minimality in the small-case
  oracle: a candidate is necessary if it can finish after all other candidates.
  Do not turn that characterization into completion queries in the algorithm.
  Derive candidate omissions from the maintained dependency information.
- A Vanish remains terminal: it changes no setter and is not another operation's
  prerequisite. Its terminal nature is essential to the last-candidate argument;
  that argument does not settle minimality of ordinary Move dependencies.

## Evidence and remaining comparisons

- Independent small-state interpreters check complete allowed schedules,
  including intermediate relationships and destruction occupancy.
- Randomized construction benchmarks time source generation separately.
- Benchmark incremental constructions, not variants of the general search.
  Validate each candidate against the same independent small-case semantics.
- Keep exact measurements and unsuccessful variants in the research repository.
  Do not infer universal optimality from passing tests or favorable workloads.
