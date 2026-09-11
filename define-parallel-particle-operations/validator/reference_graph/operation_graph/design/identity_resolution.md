# Implementing Resolved Particle and Position Identities

The [dependency requirements](dependency_requirements.md) specify which
particles and positions an operation means and what state it requires. Generated
code must preserve those identities without adding ordering merely because of
its chosen representation.

## Make identities available without repeating written lookups

Statically known identities may become generated storage addresses or indexes.
When an identity depends on an Action Execution or a runtime choice, supply or
select it before its consumer executes. Validation alone does not supply a
runtime identity.

Do not make an operation wait for a Move merely to look through its destination
when the same identity is available independently. A lookup through a mutable
position is unsuitable if the dependency graph allows that position to change
before the lookup. Retain the identity instead, or choose a representation that
does not need the lookup.

An action's interface must provide the identities its operations require without
making all its operations wait for unrelated caller or callee work. Obtaining an
identity does not remove the occupancy or lifetime requirements of using the
corresponding position or particle.

## Preserve independent storage lifetimes

Storage may be reused only when execution orders allowed by the graph cannot
overlap uses of its old and new contents. Non-overlap in serial source order is
not sufficient.

Choose a memory representation that lets independent operations access their
state concurrently. A storage layout or lookup strategy that introduces extra
conflicts does not justify adding semantic dependencies to the graph.
