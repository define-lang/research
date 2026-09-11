# Symbolic execution without runtime position rearrangement

## Result

For a finite, resolved program with deterministic symbolic reads and writes,
fixed particle storage, and no position-observing runtime effects, particle
identity, symbolic access dependencies, computation dependencies, and storage
lifetime requirements suffice to preserve the serial symbolic behavior.
Moves do not need runtime instructions or dependency arrivals. Actions do not
need entry or completion barriers merely because they are actions.

This is a conditional result about a proposed extension, not a proof that the
current spec contains symbolic semantics or permits replacing its literal
Particle Operation Dependency Graph. No compiler, spec, or DLP changes are part
of this experiment.

## Assumptions

- Serial Define analysis resolves the identity of each particle read or written,
  including through callees, implied positions, interface positions, child
  positions, and destruction. All positions retain their actual parent particle
  in that analysis, including local positions whose parent is the action's
  parent particle. Generated operands do not repeat mutable position lookups.
- Each particle has one mutable symbol storage location. There are no hidden
  versions of that symbol or copies introduced to avoid conflicting accesses.
- Read, write, and arithmetic events have defined granularity. Capturing the
  operand of an arithmetic operation is ordinary evaluation, not retaining a
  second mutable version. An overwrite waits until the conflicting read has
  captured its value, not necessarily until subsequent arithmetic finishes.
- The action executions that occur are known independently of symbol values.
  Each execution has its own local particle identities and completion events.
  Modular code can use parameterized identities; they need not all be constants
  in one expanded program. Identity availability must precede its consumer.
- Arithmetic is deterministic and has no observable exceptions, external calls,
  position inspection, address inspection, or hidden shared state. Those would
  require additional effect dependencies, not necessarily action barriers.
- Storage exists before access and remains available through the last access.
  Physical relocation and reuse are excluded from the baseline. Reuse based only
  on non-overlap in the serial source could introduce an unnecessary dependency.
- A legal serial ordering of destructors has been chosen when one is needed.
  This does not assume that every legal choice has the same symbolic result.

Initialization is a write if it produces a symbol value. An uninitialized read
must be rejected or given semantics by the future symbol proposal. The exhaustive
test gives all particles an initial value so it does not assume uninitialized
reads are legal Define.

## Why the reduction works

Resolve a valid serial program, including its triggered actions and destructor
effects. Associate each symbolic event with actual particle identities. Keep
each same-particle access pair in serial order when at least one access writes,
and keep the dependencies between arithmetic and its inputs and result writes.

For a read, its preceding write must finish first. Every subsequent write to
that particle must follow the read. Therefore it observes exactly the same
write as in the serial program. Writes to a particle retain their serial order,
so the final write is unchanged. Deterministic arithmetic receives the same
operands and consequently writes the same results. Allocation precedes access;
reclamation follows it. This argument applies regardless of action boundaries.

Equivalently, a permitted reordering exchanges only independent accesses or
read/read pairs, while respecting computation dependencies. These exchanges
leave the symbolic behavior unchanged. A Move changes the serial name-to-particle
association but is not an event on symbol storage, so erasing it adds no symbolic
conflict. The serial analysis still validates all intermediate relationships.
Erasure does not execute a forbidden particle cycle; it emits no runtime
relationship updates at all.

If logical relationships themselves must be observable at every physical
execution step, that erasure argument is not applicable. Position inspection,
address identity, physical relocation, or control flow driven by symbols would
need separate analysis. The experiment does not silently discard those effects.

The construction permits exactly the orders preserving same-particle conflicting
access order and explicit computation dependencies. This is not an unconditional
optimality claim for mathematical computations: equal-value writes, dead writes,
or provably commuting updates may permit further optimization. Nor does it claim
minimal edge counts or optimal compiler complexity.

## Modular composition without whole-action barriers

An independently analyzed action can expose, for each resolved particle it
accesses:

1. Reads before its first write.
2. Its first write, if any.
3. Its last write, if any.
4. Reads after its last write, or all reads if there are no writes.

These are event identities or interfaces to events, not waits for the whole
action. Internal dependencies remain with the action. For successive summaries:

- Connect the earlier last write to the later leading reads.
- Connect earlier trailing reads to the later first write.
- If there are no earlier trailing reads and no later leading reads, connect
  the earlier last write to the later first write.
- Export the combined first/last writes and leading/trailing reads.

Each particle's serial accesses consist of read groups separated by writes.
These rules connect exactly the groups at the boundary. Thus composition has
the same reachability as processing all accesses individually; the merged
boundary has the same meaning, permitting induction through nested calls.
Cross-particle arithmetic dependencies are retained independently.

Read-only callees do not consume exclusive permission. A later writer waits for
the relevant caller and callee reads, not for unrelated callee operations. A
caller can consume one callee result while the callee computes another result.
Repeated calls share dependencies only where their actual particles are shared.

The test materializes event edges to compare with an independent whole-program
oracle. That is not a recommendation to copy or flatten action graphs in the
compiler. A production modular implementation would preserve stable interfaces
to internal events and execution-specific bindings. Canonical particle identity
must be resolved before summarizing; assuming two names are distinct particles
and merging them after dependency calculation is not justified by this result.

## Correspondence to current action and destruction rules

The spec references below are sections of `define/spec/spec.md` in the Define
repository. They constrain this investigation, but do not define symbol effects.

- **Action Triggering Semantics:** serial occupancy changes determine which
  action executions occur, including retriggering. Erasing physical Moves must
  preserve those executions; it must not remove their symbolic work or retrigger
  actions by inspecting a reordered runtime arrangement.
- **Requirements Follow Particles** and **Automatic Action Guarantees:** the
  contracts preserve particle identity through moves and distinguish a returned
  incoming particle from a fresh one. These facts remain necessary even if the
  Particle Operation scheduling graph is absent from runtime code.
- **Concurrency Between Actions** and **The Action Parent Rule:** the spec does
  not make actions atomic and does not automatically make a trigger operation
  a dependency. Symbolic events likewise need only their actual prerequisites.
  Current occupancy contracts alone do not summarize symbolic effects: a callee
  can leave every position unchanged while modifying a surviving particle.
- **When Constructors Run:** constructor ordering supplies a serial baseline
  for conflicting symbol accesses. Unrelated constructor work does not justify
  delaying every later computation until all constructors finish.
- **Simultaneous Transitive Destruction:** identify the original particles and
  distinguish them from replacements. A replacement's symbol storage is not the
  old particle's storage. Reusing it early would be a separate allocation choice,
  not a dependency required by using the same written position name.
- **Destructors and Destruction Ordering:** a destructor's retained particles
  must remain available while needed. For symbol-only effects, track actual
  accesses. Finishing arithmetic from a captured operand need not retain the
  particle from which the operand was read, if that is the only remaining use.
- **Destruction Contracts:** caller-known destructors are analyzed at the logical
  destruction site, not appended after all caller work. Their symbol effects
  must participate there too. A callee that destroys an incoming particle needs
  a composable destruction interface for effects supplied by its callers; an
  ordinary read/write summary omitting those effects is insufficient.
- **Destructor Action Guarantees:** restoring occupancy, particle identities,
  and qualities does not imply restoring symbol values. Two destructors may
  conflict even when their existing occupancy guarantees are unchanged.
- **Ending Define Programs:** all required symbolic effects must finish before
  termination. Global completion does not imply a barrier between actions.

## A future semantic choice exposed by destructors

Two destructors may access the same surviving particle through an implied
position. Suppose one writes 1 and the other writes 2; ordinary code reads that
particle afterward. The compiler's currently permitted choice of destructor
order can change the observed value. This is not a deadlock or a demand for a
whole-destructor barrier.

For a chosen legal order, the access rules above correctly preserve its result.
If Define must have the same symbolic result across all such choices, the symbol
extension needs an additional policy: for example, prescribe conflicting access
order or disallow otherwise ambiguous effects. The current occupancy guarantee
does not settle this. This experiment makes no choice for the language designer.

## Evidence

`dependencies_test.py` checks:

- All 256 four-access programs over two initialized particles, with every one
  of their 24 event permutations: 6,144 schedule checks. Acceptance agrees both
  with an independent pairwise-conflict oracle and with observed read origins,
  final writes, and per-particle write order.
- 1,000 reproducible 24-access programs over five particles, including
  computation dependencies and randomly nested summary composition. The modular
  construction has exactly the whole-program oracle's reachability and exactly
  the same exported summary as individual processing.
- Early caller use of one callee result; callee work preceding an unrelated
  caller write; read/read overlap across a call; overwrite after input capture
  but before arithmetic completion; distinct repeated-call locals; caller-known
  destructor effects; independent replacement writes; and lifetime completion
  that does not wait for unrelated destructor arithmetic.
- A counterexample showing that exchanging conflicting destructor writes changes
  a later observation.

All nine tests pass through Bazel. Ruff and basedpyright report no issues. These
are executable-model tests, not compiler integration tests: symbolic statements
do not yet exist in Define. They do not establish whole-language source
correspondence, a production modular ABI, or performance of a runtime scheduler.

## Implication for DLP 44

The semantics and analysis that identify particles, select actions, validate
contracts, and preserve destruction information remain useful. The generic
idea of fine-grained modular continuations also remains useful. Their runtime
interfaces would need symbolic effects, rather than merely occupancy completion.

For the assumptions above, no particle-relationship arbitration is required to
execute the symbolic program. The difficult cyclic-Move examples concern
executing relationship mutations; they do not require arbitration when those
mutations are absent from generated code. Maximum runtime concurrency of symbol
accesses therefore does not require first solving maximum concurrency of all
Particle Operations.

The literal C design already distinguishes compiler position associations from
particle storage. It also records that optimized serial examples disappear,
while scheduled examples retain pthread and synchronization work. Absence of
symbolic effects does not itself make that scheduling machinery disappear. An
optimizing backend can use an erasure proof; the current literal execution
design explicitly requires representing the resolved Particle Operation Graph.
This investigation does not modify that design or its implementation.
