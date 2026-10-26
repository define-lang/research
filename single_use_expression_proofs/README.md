# Single-Use Expression Proofs

This directory holds proofs of claims made in Define's
[background research notes](https://github.com/define-lang/define/tree/main/define/proposals/background),
which back the Define Language Proposals.

- [Linear Interpolation Has No Single-Use Form](linear-interpolation-has-no-single-use-form.md)
  proves that a + t·(b − a) cannot be computed by an arithmetic expression
  that uses each input only once. Its Lean formalization is
  [linear_interpolation.lean](linear_interpolation.lean).

To check the Lean proofs, run `bazelisk test //single_use_expression_proofs/...`
from the repository root. Bazel fetches the Lean toolchain and the Mathlib
modules the proofs import. The build fails on any `sorry`, and the axiom test
fails if a main theorem uses any axiom other than Lean's standard three.

These proofs are not normative. The Define Language Proposals and the language
specification say what Define is.

These proofs are largely written by an AI, with some light review by a human.
Rigorous review by a more experienced human would be welcome.
