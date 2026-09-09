# Contract composition and registration

## Result

Child Vacates are not needed as runtime events merely to compose dependency
information. Substituting connections preserves the ordering of the remaining
operations, even with shared prerequisites, several callers, or completions that
precede consumer registration. A connection can be a collection of actual
operation completions, with no completion event of its own.

However, this alone is not a complete implementation design:

- Substitution preserves concurrency, but not necessarily transitive minimality.
  Vanish Comparison remains necessary during graph construction.
- Completion-aware registration prevents missed notifications, but cannot make
  work run before that work has been registered. Setup must not be postponed
  until a parent Vacate or a shared child-readiness event.
- Every prerequisite of an operation must be registered before it is published
  to the scheduler. In particular, a Vanish cannot be released while some
  caller-contributed destructor requirements remain unknown.

These are not arguments for restoring child Vacates. They are obligations that
a full static action planner must satisfy. This experiment does not yet supply
that planner for arbitrary Define source.

## General composition argument

Assume the resolved operation graph is acyclic, and that a removable child
Vacate has no necessary runtime effect on a subsequently accessed position.
Preserve its prerequisite information for the Vanish consumers that still need
it. Keep the original particle and position identities.

Replace the removable node with a connection denoting its predecessors. For
every consumer of that connection, require those predecessors directly. A path
through the removed node becomes a path through its connection; conversely, an
edge obtained by expanding a connection corresponds to a path through the
removed node. Reachability between remaining operations is therefore unchanged.

This argument works for each substitution and hence for any finite acyclic
composition. Forwarding through another module substitutes the same connection
again and cannot change its meaning. If two imported paths identify the same
operation occurrence, requiring that occurrence twice is equivalent to requiring
it once. The implementation removes precisely these duplicate identities; it
does not merge different operations that happen to have the same name.

Reachability determines the permitted execution orders. Therefore substitution
introduces no new ordering between the remaining operations. This is a
conditional graph argument: it does not independently establish that the
prerequisites derived from arbitrary Define source are correct, or that every
transitive child Vacate satisfies the stated removability condition.

## Why Comparison is still needed

Consider these prerequisites, written as `consumer: prerequisites`:

```text
a:             none
b:             a
child Vacate:  a
Vanish:        child Vacate, b
```

After substituting the child Vacate's connection, Vanish has candidates `a` and
`b`. Its direct dependency should be only `b`, since `b` already requires `a`.
Simple connection forwarding does not discover that relationship.

Keeping both edges does not lose concurrency, but it fails the separate goal
of a transitively minimal graph. The experiment explicitly detects this case;
it does not hide a generic transitive reduction in its implementation. Existing
Vanish Comparison must resolve the candidates before the final action plan is
generated. Demonstrating a modular, efficient way to do that with arbitrary
caller-dependent relationships remains outside this prototype.

## Registration protocol

`registration.py` distinguishes allocating an operation, registering all its
prerequisites, and publishing it. Registration and prerequisite completion share
a lock protecting only metadata. Actual operation bodies execute without that
lock.

For each prerequisite, registration either sees that it has completed or
subscribes to its future completion. The lock makes those alternatives atomic.
There is no interval in which a completion can be missed. Each distinct
unfinished prerequisite increments the consumer's counter once; completion
decrements it once. A published operation is runnable exactly when that counter
is zero.

Before publication, no operation is runnable even if its currently registered
counter is zero. That protects partially wired operations, but it is not a
license to delay setup: if a logically runnable operation is not published,
execution misses an opportunity for concurrency. The negative-control tests
demonstrate both unsafe early publication and delay caused by late publication.

The lock is an experimental correctness mechanism, not a recommendation for a
global lock in the compiler's production runtime. No new Particle Operation or
child-readiness arrival is counted by this protocol.

## Tests

`composition_integration_test.py` adds 148 cases to the original 70:

- 80 seeded dependency graphs, each with 96 ordinary operations, 12 removed
  selection nodes, and 12 terminal operations. Random local module boundaries
  exercise direct imports and exports. Complete reachability is checked against
  the explicit-node graph, and runnable sets are checked after all modules have
  been registered. Execution is also interleaved with registration.
- 24 generated valid Define sources exercise caller-only destructors, 1–8
  branches, up to 20 forwarding levels, duplicate imported paths, and late
  consumer registration. These retain the first experiment's source-specific
  dependency derivation. Their actual registered edges match the independent
  whole-program algorithm exactly, and particle-state checks pass.
- 40 real two-thread registration/completion races verify that an arrival is
  neither lost nor counted twice.
- One reusable callee plan is bound to identical, ordered, independent, and
  multiple predecessor occurrences without changing the plan.
- Three negative controls cover redundant edges, premature publication, and
  delayed setup.

The arbitrary graphs test the composition algebra; they are not presented as
valid Define programs. Their local requirements originate in the generated
graph, not in independent source compilation. The source tests provide the
separate connection to Define semantics, within the documented source family.

`composition.py` never traverses a caller or callee graph. It substitutes direct
imports into local dependency expressions and allocates only actual operation
tasks. It does not invoke the oracle, reachability analysis, or minimization.
This does not prove that a compiler can derive all those local expressions
without additional analysis.

No performance conclusion is drawn. The prototype retains dependencies for
inspection, and forwards explicit predecessor collections. Large-contract
memory usage and an optimized static representation would need separate work.

Run both suites with:

```sh
bazelisk test --noshow_progress --ui_event_filters=-info //operation_graph_optimization/transitive_destruction/contracts:all
```
