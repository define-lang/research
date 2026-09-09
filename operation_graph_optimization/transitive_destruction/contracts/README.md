# Destruction Contracts without transitive child Vacates

The later [small interface experiments](../interfaces/README.md) derive the
information to expose from action descriptions, rather than supplying producer
exports by hand. They compare retaining child Vacates, lowering them away, and
using only contract records.

The [composition follow-up](COMPOSITION.md) extends this initial experiment with
arbitrary dependency graphs, aliased imports, and completion-aware registration.
It also identifies what simple forwarding does not solve: transitive minimality
and timely setup of operations that are already logically runnable.

## Question and result

Does removing transitive child Vacates force Destruction Contracts to recreate
equivalent runtime events?

Not in the cases tested here. A reusable callee plan can export separate
dependency connections for caller-supplied destructor operations. Connecting
those operations directly requires metadata, but no additional scheduled
operation. A single shared child-readiness event is not an equivalent substitute:
it can remove concurrency.

This is a bounded modular-execution experiment, not an implementation of a
general Define Destruction Contract compiler.

## The problematic design

A child particle has positions `/branch0` and `/branch1`. The callee moves each
branch particle away and back, then issues destruction of the parent. The
child's destructor, known only to the caller, also moves each branch particle
away and back using implied positions.

The first destructor Move on `/branch0` needs the callee's last Move on
`/branch0`. It does not need the callee's last Move on `/branch1`. Waiting for a
single child-readiness event that combines both prerequisites adds that second
dependency. Waiting for the parent Vacate would also delay this work.

The negative-control test withholds the callee's first Move on `/branch1`.
Direct connections permit the destructor's `/branch0` work to finish. A shared
child hook prevents it. A separate test runs real worker threads: the withheld
branch waits for the other destructor branch to finish, and direct connections
complete successfully.

The negative control is a possible contract design, **not** a claim that the
existing explicit-child-Vacate algorithm gates destructor operations this way.

## Construction

- `cases.py` generates valid Define source, a separate resolved-operation model,
  and local action plans. The callee does not know the caller-added destructor.
- `planning.py` compiles symbolic local dependencies into integer references.
  Caller construction uses the callee's exports without changing its plan.
- Instantiation attaches consumers directly to their prerequisite tasks.
  Forwarding connections add no task. Destruction selection adds no child
  Vacate task in this model.
- Execution uses dependency counters. There is no graph analysis or generic
  transitive minimization during instantiation or execution.
- The previous whole-program algorithm is used only as a test oracle, after
  the modular construction. Its dependency sets must match the actual runtime
  connections exactly.

The callee exports a separate connection for each branch. Combining all of
these into one prerequisite set would lose information needed to preserve
concurrency. Removing child Vacate operations therefore does not remove the
need to communicate position-specific dependency information across contracts.

## Why direct connections preserve the supplied ordering

Initially, an operation's counter equals its number of prerequisites. Each
prerequisite completion decrements it exactly once. Consequently the counter
equals the number of unfinished prerequisites throughout execution. An
operation becomes runnable exactly when all its prerequisites have completed.

Thus, given exact prerequisite connections, this executor adds no ordering to
the supplied graph. A connection itself has no completion event. This argument
does not depend on which runnable operation the executor chooses next.

## Validation

The integration suite has 70 cases:

- 27 combinations of 1, 2, or 8 branches; 0, 1, or 20 forwarding levels; and no,
  one, or all active destructor branches. Every generated source is validated
  by the real Define compiler, and every runtime edge matches the independent
  whole-program calculation.
- 40 randomized executions compare the complete runnable set against the
  oracle after every operation.
- The shared-hook negative control and the real-thread concurrency witness.
- Twelve independent caller instances reuse the identical callee plan, with
  different caller-supplied destructor requirements and no shared runtime
  connections.

Operation bodies check original particle identities, vacancy for Creates and
Moves, and the lifetime of required particles. The parent may finish while
destructor work on the old child remains. Child positions are accessed by their
original identities, not by looking up a written chain through that parent.

Run with:

```sh
bazelisk test --noshow_progress --ui_event_filters=-info //operation_graph_optimization/transitive_destruction/contracts:runtime_integration_test
```

## Limits and remaining design obligations

The symbolic dependencies are derived specifically for this source family, not
automatically from arbitrary source. The experiment demonstrates local
composition, but does not prove a general contract-summary construction. In
particular, a summary that preserves only the union of a child's prerequisites
is insufficient; the relevant operation-specific information must survive.

All runtime instances and connections are constructed before execution starts.
This does not establish correctness for connections registered after some
prerequisites have completed. A real implementation must either arrange wiring
before execution or implement completion-aware registration without inserting
an extra semantic dependency.

The supplied predecessor lists are distinct and exact in this family. General
composition must account for two imported connections referring to the same
operation, and for prerequisites made redundant by other imported connections.
This experiment supplies neither a general solution nor a hidden runtime
minimization pass for that problem.

Repeated instances here have independent state. Forwarding levels exercise
connection composition, not additional source-level calls. The state checker is
not a physical memory allocator, and its short mutations use a lock. The
threaded witness tests dependency concurrency rather than parallel memory
throughput. No performance advantage over the previous algorithm is claimed
by this experiment.
