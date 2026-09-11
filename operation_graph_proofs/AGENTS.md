# Working on Define Proofs

## Inviolable proof principles

These principles govern every proof in this directory, both its English argument
and its formalization:

- Develop and correct the English argument before updating its Lean
  formalization.
- The only premises about Define are the rules in the current
  [specification](../define/spec/spec.md) and results already proved from those
  rules. Intuition, compiler behavior, examples, and passing tests are not
  additional semantic premises.
- Previously proved mathematical theorems from outside this repository may be
  used when they correspond exactly to the construction needed. Establish that
  correspondence and discharge every hypothesis; an analogy or a similar result
  is not enough. Such theorems do not supply additional rules about Define.
- The proof must model the specified rules themselves, including their
  individual phases. Do not replace them with a different calculation or add
  restrictions merely because doing so makes a desired theorem provable.
- Definitions, structure fields, and helper-theorem hypotheses must not conceal
  unproved properties of Define. A conditional theorem establishes a result
  about the spec only after its semantic hypotheses have been derived from the
  spec or previously established results. Formal verification of the conditional
  theorem alone does not discharge those obligations.
- Do not assume the intended conclusion, directly or indirectly. Every claimed
  consequence must have a non-circular derivation, and the formal theorem must
  establish the property and scope claimed by the English proof.
- If an argument fails, identify and correct the invalid step or exhibit a
  counterexample. Do not repair it by inventing a language rule, silently
  narrowing the claim, or presenting an unresolved obligation as proved.
