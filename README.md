# Define Research

This is a record of various research work that I do during the development of [Define](/define-lang/define). This repo is mostly an archive of research that was interesting but not worth preserving permanently as part of the main Define repo.

To run the Python type checks, first run
`bazelisk build --build_runfile_links //...`, then
`uv run --frozen basedpyright`. Basedpyright uses the project's `.venv` for
installed dependencies and Bazel's test runfiles for the Define compiler,
including its generated parser. Rebuild if those runfiles are missing or stale.

The [complete Particle Operation algorithm simplification experiments](operation_graph_optimization/simplification_experiments.md)
compare broad Vanish recording, separate Vacates and Vanishes, and the existing
Collection and Comparison optimizations, with correctness checks and preserved
benchmark data.

The [single-use expression proofs](single_use_expression_proofs/README.md) prove,
in English and in Lean, that linear interpolation has no single-use arithmetic
form.

The [circuit treewidth SDD proofs](circuit_treewidth_sdd/README.md) show, in
English and partly in Lean, that circuits of treewidth k have sentential
decision diagrams of size n·2^O(k) over their inputs.

The [circuit treewidth canonical SDD study](circuit_treewidth_canonical_sdd/README.md)
asks the same question for canonical (compressed) SDDs: it gives the best known
bounds and the gap between them, and shows, partly in Lean, that OBDDs for
circuits of pathwidth k need doubly exponential width.

The [boolean equality checking study](boolean_equality_checking/README.md)
measures how the Define compiler can find, exactly, which boolean values are
always equal, constant, or equal to an input, and recommends one combined
algorithm that checks each value operation once, with executions of other
value operations as references.
