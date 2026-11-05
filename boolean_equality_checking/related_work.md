# Related Work: Exact Boolean Redundancy Checking as a Language Rule

> **Written by an AI agent (Claude) and not yet reviewed.** Citations were
> checked as described under each item. "Read" means I read the primary text
> (the whole paper or the named sections). "Abstract only" means I saw only
> the abstract or bibliographic record. "Secondary" means the claim comes from
> a search summary, a citing paper, or a third-party page. I didn't verify
> anything marked secondary or abstract-only beyond that level.

This surveys prior work related to DLP 58 (No Redundant Boolean Values), DLP
59 (One Order for Boolean Logic), DLP 60 (Registered Boolean Operations), and
the algorithms in `drafts/boolean-logic-in-the-compiler.md` in the Define
repository. The question is whether any existing system or paper does
something like them, and how close each one comes.

## Short Answer

I found no language, compiler, or paper that rejects a program because some
boolean value in it is, exactly and over all inputs, constant, equal to an
input, or equal to an earlier value. I also found none that rejects a program
for writing out a library operation, or for not using the preferred spelling
of one. The nearest enforced rules are either syntactic (Go's unused variables,
Elm's redundant patterns, clang-tidy's identical operands) or semantic but
undecidable and checked only approximately (MISRA C:2012 Rule 2.2, "no dead
code"). The nearest exact boolean tools (Clippy's `nonminimal_bool` and
`overly_complex_bool_expr`) are optional lints that look at one expression at a
time.

Almost every algorithmic piece is standard in logic synthesis and
verification:

- **The invariant DLP 58 enforces is a FRAIG.** A functionally reduced AIG is
  an AIG in which no two nodes compute the same function or complementary
  functions (Mishchenko, Jiang, Chatterjee, and Brayton). That's DLP 58's rule
  as a data-structure property. The difference is that a FRAIG merges the
  duplicates instead of rejecting them, and FRAIG construction allows resource
  limits that leave some duplicates unmerged.
- **DLP 60's matches are k-resubstitution against a gate library,** with
  ABC's own acceptance rule: replacing a node with k new nodes is accepted
  only if its maximum fanout-free cone (MFFC) has at least k+1 nodes. DLP 60's
  "removes at least two statements" (one new execution) and "at least three"
  (an execution and a `not`) are that rule with k = 1 and k = 2.
- **The checking stack** (structural hashing, random simulation, SAT sweeping,
  BDD fallback, and counterexamples fed back into simulation) is Kuehlmann et
  al. (2002) and the FRAIG construction.
- **Storing simulation patterns across compiles** is the "expressive
  simulation patterns" idea of Lee, Riener, Mishchenko, Brayton, and De
  Micheli (TCAD 2022), which reuses patterns across runs and after small edits.
- **Computing interchangeable views from the function** is symmetry detection
  from Boolean matching for library binding.
- **The termination proof** uses a standard technique: a lexicographic
  combination of counts and Dershowitz–Manna multiset orders.
- **Non-confluence is expected.** Socher-Ambrosius (RTA 1991) proved that
  Boolean algebra has no convergent term rewriting system. That's secondary
  here: I couldn't get the full text.

What seems new is the combination:

1. Treating exact functional redundancy and library matching as
   **well-formedness rules that decide which programs compile**, not as
   optimizations or warnings.
2. Making those rules **decidable and solver-independent** by bounding the
   domain (20 boolean inputs, 256 statements) so that a complete fallback
   always exists. In EDA, the same methods run under resource limits whose
   results depend on the budget, and that's acceptable there because they're
   optimizations.
3. Matching **over every earlier value** instead of a window or a cut, with a
   **user-facing spelling precedence** and a **proof that the fix loop
   terminates**.

The closest prior work overall is the FRAIG paper for DLP 58, and
Mishchenko–Brayton resubstitution plus Boolean-matching library binding for
DLP 60. For the language-design side ("redundancy is an error, not a
warning"), the closest are Go's no-warnings policy and MISRA C Rule 2.2.

## The Pieces Being Compared

To keep the comparisons specific, Define's system is split into these pieces:

| #   | Piece                                                                                                                                                                                             | Source                     |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| P1  | A boolean value that's exactly constant, equal to an input, or equal to an earlier value is a compile error.                                                                                       | DLP 58                     |
| P2  | No literal may be given to a boolean statement.                                                                                                                                                    | DLP 58                     |
| P3  | A value equal to a registered operation, or its negation, over at most 4 earlier values is an error when replacing it removes at least 2 statements (3 for a negation). The largest match is reported. | DLP 60                     |
| P4  | One spelling among single executions: fewest negated arguments, then fewest ANDs, then declared order, then rank order.                                                                            | DLP 60                     |
| P5  | Interchangeable views come from the function, and values go to them in a fixed rank order.                                                                                                        | DLP 59                     |
| P6  | One statement order: inputs right before first use, depth-first from the consumers.                                                                                                                | DLP 59                     |
| P7  | No wrappers. Exactly one standard wrapper for each of `and` and `not`.                                                                                                                             | DLP 60                     |
| P8  | Exact, deterministic checking: AIG with structural hashing, then truth tables, simulation, SAT with a conflict limit, OBDDs, and whole-operation truth tables.                                    | draft                      |
| P9  | One check per definition with executions referenced, not inlined. CEGAR refinement, truth-table hashes for incremental rechecks, and stored counterexample patterns.                             | draft                      |
| P10 | The fix loop provably terminates (lexicographic order with Dershowitz–Manna multisets, in Lean). It isn't confluent.                                                                               | draft, `proof/`            |
| P11 | Limits (20 inputs, 256 statements) that make P1 and P3 decidable within a bounded worst case.                                                                                                      | DLP 58                     |

## 1. Languages and Standards That Reject Redundant Code

### Go: Unused Variables and Imports Are Errors; No Warnings

- **What:** Go refuses to compile programs with unused local variables or
  imports. The FAQ explains the policy that the compiler has errors and no
  warnings: "if it's worth complaining about, it's worth fixing in the code.
  (Conversely, if it's not worth fixing, it's not worth mentioning.)" It also
  says compiler options "should not affect the semantics of the language."
- **Citation:** Go FAQ, "Can I stop these complaints about my unused
  variable/import?", <https://go.dev/doc/faq>.
- **Matches:** The language-design stance behind P1 and P11: redundancy is a
  compile error, the same on every compiler, with no flag to turn it off.
- **Differs:** It's purely syntactic (a name that's never used). No semantic
  equivalence is involved.
- **Verified:** Read the FAQ entry.

### Zig: Unused Locals Are Errors

- **What:** Zig rejects unused local constants and variables ("unused local
  constant"), and requires `_ = x;` to discard a value.
- **Citation:** No primary source checked. Tutorials and forum posts:
  <https://www.luisllamas.es/en/zig-variables-constants/>,
  <https://openmymind.net/learning_zig/style_guide>.
- **Matches and differs:** The same as Go: an enforced, syntactic rule.
- **Verified:** Secondary only.

### Elm: Redundant Patterns Are Compile Errors

- **What:** The Elm compiler reports a `REDUNDANT PATTERN` error: "Any value
  with this shape will be handled by a previous pattern, so it should be
  removed."
- **Citation:** `compiler/src/Reporting/Error/Pattern.hs` in
  <https://github.com/elm/compiler> (master).
- **Matches:** This is the closest enforced semantic redundancy rule I found
  in a general-purpose language. Pattern redundancy is a property of what the
  patterns cover, not of how they're written, and it's an error, not a
  warning. It's structurally like "always the same as an earlier value": an
  earlier pattern already covers it.
- **Differs:** Pattern coverage over algebraic data types is a much easier,
  structurally decidable problem than Boolean functional equivalence. Nothing
  like P3 or P4 exists.
- **Verified:** Read the source file.

### MISRA C:2012 Rule 2.2: "There Shall Be No Dead Code"

- **What:** A required rule in a safety-critical coding standard. It defines
  dead code as "any operation that is executed but whose removal would not
  affect program behaviour." This is a semantic redundancy rule, defined over
  behavior and not syntax.
- **Citations:**
  - MISRA C:2012 itself, which I didn't read (it isn't freely available).
  - Bagnara, Bagnara, and Hill, "Coding Guidelines and Undecidability," arXiv
    2212.13933 (2022), <https://arxiv.org/abs/2212.13933>.
  - MathWorks Polyspace documentation,
    <https://www.mathworks.com/help/bugfinder/ref/misrac2012rule2.2.html>.
- **Matches:** This is the closest precedent for P1 as a mandatory rule that
  decides compliance. It's defined by what removing an operation does, not by
  syntax.
- **Differs:** Bagnara et al. argue that Rule 2.2 "is the only undecidable
  MISRA C:2012 rule that is also unprovable." Proving compliance would mean
  answering exponentially many program-equivalence questions, so tools check
  only common cases. Polyspace's page describes what it checks as the "most
  common" situations. Define avoids this by restricting the rule to bounded
  boolean logic, where equivalence is decidable and the worst case is bounded
  (P11). In that sense, P1 plus P11 is a decidable version of Rule 2.2 for one
  kind of value.
- **Verified:** Read Bagnara et al.'s Rule 2.2 section (including the
  quotation of the rule's definition). Read the Polyspace page through a
  fetch tool's summary.

### Python's "One Obvious Way" and gofmt

- **What:** PEP 20 says "There should be one-- and preferably only one
  --obvious way to do it." gofmt gives Go one canonical layout.
- **Citations:** Tim Peters, PEP 20, <https://peps.python.org/pep-0020/>.
  "go fmt your code," <https://go.dev/blog/gofmt>.
- **Matches:** The goal behind all of DLPs 58–60.
- **Differs:** PEP 20 is an aspiration and isn't enforced. gofmt is a
  formatter whose use is a convention, enforced by hooks and not by the
  compiler (according to the blog post), and it only covers layout.
- **Verified:** Read both pages through a fetch tool.

### Dhall: Semantic Hashes of Normal Forms

- **What:** Every Dhall expression has a normal form because the language
  isn't Turing-complete. Its integrity checks hash the normal form, so
  "refactoring code or adding/removing whitespace/comments won't disturb the
  hash."
- **Citation:** Dhall wiki, "Safety guarantees,"
  <https://github.com/dhall-lang/dhall-lang/wiki/Safety-guarantees>.
- **Matches:** Like the truth-table hash that P9 uses for incremental checks,
  identity comes from meaning, not text. Both rely on a total language with a
  canonical form.
- **Differs:** Dhall normalizes; it doesn't reject. Two different source
  programs with the same normal form both compile. Dhall's normal form is
  beta-normalization, not Boolean functional equivalence.
- **Verified:** Read the wiki page through a fetch tool. I didn't read the
  Dhall standard.

### Unison: Content-Addressed Definitions

- **What:** "Each Unison definition is identified by a hash of its syntax
  tree." Names are metadata, arguments are numbered by position, and
  dependencies are replaced by their hashes.
- **Citation:** "The big idea," <https://www.unison-lang.org/docs/the-big-idea/>.
- **Matches:** Like P9, a definition is identified once and referenced by
  callers, and a rename doesn't change identity.
- **Differs:** The hash is structural. Two definitions that compute the same
  thing in different ways get different hashes. Nothing is rejected for being
  equivalent to something else.
- **Verified:** Read the page through a fetch tool. I didn't find documentation
  of what UCM does when a definition's hash already exists.

## 2. Linters and Static Analyzers for Redundant Logic

### Clippy: `nonminimal_bool` and `overly_complex_bool_expr`

- **What:** Two Rust lints in one pass. `overly_complex_bool_expr` "checks for
  boolean expressions that contain terminals that can be eliminated" (example:
  `a && b || a`, which is `a`), as "most likely a logic bug."
  `nonminimal_bool` checks for boolean expressions "that can be written more
  concisely," such as `a && true`. Both minimize with the `quine_mc_cluskey`
  crate, over at most 32 terminals.
- **Citation:** `clippy_lints/src/booleans.rs` in
  <https://github.com/rust-lang/rust-clippy> (master).
- **Matches:** This is the closest programming-language tool to P1 and P2. It
  minimizes the boolean function exactly and flags expressions whose
  minimized form drops a terminal or literal.
- **Differs:**
  - They're lints in the `pedantic` group (off by default), not errors. The
    source warns that they create "a big toll on performance, **only enable
    sporadically**."
  - They look at one expression tree at a time. They don't compare values
    across statements and don't use earlier values.
  - They ignore short-circuiting and `|`, `&`, and `^`.
  - There's nothing like P3 or P4.
- **Verified:** Read the lint source.

### clang-tidy `misc-redundant-expression`

- **What:** Flags redundant expressions "typically errors due to copy-paste,"
  like `(x+1) | (x+1)`, `p->x == p->x`, and `speed - speed + 1 == 12`.
- **Citation:** <https://clang.llvm.org/extra/clang-tidy/checks/misc/redundant-expression.html>.
- **Matches:** The same category of mistake as P1.
- **Differs:** It's syntactic: it compares identical operands, and doesn't
  check functional equivalence. It's a warning.
- **Verified:** Read the documentation page through a fetch tool.

### Xie and Engler, "Using Redundancies to Find Errors"

- **What:** Five redundancy checkers: idempotent operations, unread
  assignments, dead code, redundant conditionals, and redundant computations
  across abstraction boundaries. Run on Linux, OpenBSD, and PostgreSQL. The
  redundant-conditionals checker "uses path-sensitive analysis to detect
  redundant (always true or always false) conditionals." Files with
  redundancies were "roughly 45% to 100% more likely" to have hard errors.
- **Citation:** Yichen Xie and Dawson Engler, FSE 2002. Extended version in
  IEEE TSE 29(10), 2003, <https://web.stanford.edu/~engler/tse-redundant.pdf>.
- **Matches:** Empirical support for the premise of P1, that redundant logic
  often signals a mistake, not just a style problem.
- **Differs:** A bug finder with false positives (52 false out of 101
  inspected in Linux for redundant conditionals). It isn't a language rule and
  isn't exact.
- **Verified:** Read the TSE version's abstract, introduction, and
  redundant-conditionals section.

### Always-True Condition Checks in Commercial Analyzers

- **What:**
  - PVS-Studio's V547 flags conditions that are always true or always false,
    and "diagnoses only those cases when an error is highly probable."
  - Simulink Design Verifier's dead-logic detection finds decision and
    condition outcomes that can't occur. Its exhaustive mode also reports
    "undecided objectives."
  - Verilator has HDL lint warnings like `CMPCONST` ("comparing a value in a
    way that will always be constant") and `NOEFFECT`.
- **Citations:** <https://pvs-studio.com/en/docs/warnings/v547/>,
  <https://www.mathworks.com/help/sldv/ug/detect-dead-logic.html>,
  <https://veripool.org/guide/latest/warnings.html>.
- **Matches:** P1's "always true or always false." Design Verifier uses formal
  analysis on models, which comes closest to exact.
- **Differs:**
  - All three are warnings or reports, not rules that decide compilation.
  - Design Verifier explicitly has undecided results, which DLP 58 rules out.
  - None of them compares a value to earlier values or to library functions.
  - I found no SpyGlass documentation on redundant-logic rules.
- **Verified:** Read each page through a fetch tool.

## 3. Equivalence Checking and Functional Reduction

### FRAIGs: Functionally Reduced AND-Inverter Graphs

- **What:** "A functionally reduced AIG (FRAIG) is an AIG, in which, for any
  pair of nodes, n1 and n2, f_n1(x) ≠ f_n2(x) and f_n1(x) ≠ ¬f_n2(x)." The
  paper builds FRAIGs on the fly:
  - trivial cases (`x and x`, `x and not x`, constants);
  - argument ordering "to ensure that swapping of fanins does not create a new
    node";
  - one-level structural hashing;
  - simulation classes, with a SAT check against each candidate in the new
    node's class.

  The paper calls FRAIGs "semi-canonical": each node is functionally unique,
  but the same function can still have different FRAIGs.
- **Citation:** Alan Mishchenko, Jie-Hong Roland Jiang, Satrajit Chatterjee,
  and Robert Brayton, "FRAIGs: Functionally Reduced AND-INV Graphs." It's a
  draft on the group's page, listed as "to be submitted to DAC '05"; I didn't
  find a final venue. <https://people.eecs.berkeley.edu/~alanmi/research/fraigs/index.htm>.
  Copy read: <https://courses.e-ce.uth.gr/ECE431/papers/fraigs03.pdf>.
- **Matches:** This is the closest prior work for P1 and P8:
  - DLP 58's invariant, applied to a value operation's AIG, is the FRAIG
    property except for complements (below).
  - The construction is the draft's first steps: hashed ANDs with sorted
    literals, the trivial rules, then simulation candidates proved in
    construction order. "Report the first redundant value in statement order"
    corresponds to FRAIG checking each new node against the earlier nodes in
    its class.
  - The paper also notes that FRAIGs aren't canonical. This is the same
    reason the draft's "One program for each function" open question stays
    open.
- **Differs:**
  - A FRAIG **merges** an equivalent node instead of rejecting the program.
  - Exactness is conditional: of BDD sweeping the paper says "As long as all
    BDDs can be built within the resource limits, the result is a FRAIG."
    Define's last-resort truth tables (P11) remove that condition.
  - **FRAIGs also exclude complements.** DLP 58, as written, only counts a
    value that's always the **same** as an earlier value or input. See
    Observations, below.
- **Verified:** Read the paper (abstract, definitions, Sections 2–4,
  conclusions).

### Kuehlmann, Paruthi, Krohm, and Ganai: Robust Boolean Reasoning

- **What:** "A combination of techniques for Boolean reasoning based on BDDs,
  structural transformations, an SAT procedure, and random simulation natively
  working on a shared graph representation."
- **Citation:** IEEE TCAD 21(12):1377–1394, 2002,
  [10.1109/TCAD.2002.804386](https://doi.org/10.1109/TCAD.2002.804386).
- **Matches:** P8's ladder of methods, which the draft already cites.
- **Differs:** It's built for verification under resource limits. Define's
  difference is the exact final rung and treating the result as a language
  rule.
- **Verified:** Read the abstract and introduction. I didn't re-read the
  algorithm sections for this report.

### Simulation-Guided Logic Synthesis and Reusable Patterns

- **What:** Lee, Riener, Mishchenko, Brayton, and De Micheli generate
  "expressive simulation patterns" to filter resubstitution candidates and
  reduce SAT calls. The TCAD version stores patterns "to be reused in multiple
  runs of optimization and verification," including "after network function
  modifications" (ECOs). Counterexamples from SAT are added to the patterns.
- **Citations:**
  - "Simulation-Guided Boolean Resubstitution," IWLS 2020, arXiv 2007.02579,
    <https://arxiv.org/abs/2007.02579>.
  - "A Simulation-Guided Paradigm for Logic Synthesis and Verification," IEEE
    TCAD 41(8), 2022,
    [10.1109/TCAD.2021.3108704](https://doi.org/10.1109/TCAD.2021.3108704).
- **Matches:** P9's stored patterns (counterexamples saved with a definition
  and reused after edits) and P8's counterexamples-to-patterns loop. This is
  direct prior art for both.
- **Differs:** Patterns are an optimization in both, and both still need SAT
  for exactness. In Define the patterns are stored per definition in the
  build, not per design flow.
- **Verified:** Read the IWLS paper (Sections 1–3, 6) and the TCAD abstract
  and Section 3.

## 4. Library Matching: Resubstitution, Rewriting, Technology Mapping

### Boolean Resubstitution (Mishchenko and Brayton, and Successors)

- **What:** "Resubstitution expresses the function of a node using other
  nodes (called divisors) already present in the network." The paper's
  definitions:
  - a 0-resubstitution replaces a node with "a constant or equal (up to
    complementation)" divisor and frees its MFFC;
  - "k-resubstitution ... adds exactly k new nodes to the AIG and reduces the
    AIG size if the node's MFFC has at least k+1 nodes";
  - a `UseZeroCost` option also accepts replacements that don't change the
    size.

  In Lee et al., divisors are collected from the transitive fanin and "can be
  extended to the whole circuit, excluding only nodes in the TFO of n or in
  its MFFC," but "in practice ... the number of collected divisors is
  limited." Legality uses the global input-output relation, so don't-cares
  count.
- **Citations:**
  - Mishchenko and Brayton, "Scalable Logic Synthesis using a Simple Circuit
    Structure," IWLS 2006, pp. 15–22,
    <https://people.eecs.berkeley.edu/~alanmi/publications/2006/iwls06_sls.pdf>.
  - Lee et al. (above).
  - Mishchenko, Miyasaka, Wawrzynek, and Brayton, "Standardizing Boolean
    Transforms" (2024), which reviews resubstitution variants,
    <https://people.eecs.berkeley.edu/~alanmi/publications/2024/tech24_resub.pdf>.
- **Matches:** P3 is resubstitution:
  - DLP 60's "statements of a match" are the MFFC.
  - Its arguments are divisors.
  - "Removes at least two statements, or three for an opposite result" is the
    k+1 rule with k = 1 and k = 2.
  - "Opposite results count" matches resubstitution "up to complementation."
  - The spelling rule (P4) is a zero-cost replacement with a strict order on
    the result, which is what makes it terminate when ABC's `UseZeroCost`
    alone wouldn't.
  - DLP 58's redundant values are 0-resubstitutions.
- **Differs:**
  - The dependency functions are registered library operations of up to four
    views, not small AND/OR gates.
  - Divisors are **all** earlier values in Define's statement order, with no
    window or limit.
  - Equality is exact over all inputs, with no don't-cares.
  - A match is an error naming the fix, not a rewrite.
  - Define reports one largest match globally per compile, instead of
    rewriting greedily node by node.
- **Verified:** Read IWLS 2006 Section 3.2, Lee et al. Sections 2 and 6, and
  the 2024 paper's abstract.

### DAG-Aware AIG Rewriting

- **What:** Rewriting with 4-input cuts. Each cut's function is classified
  into one of the 222 NPN classes of 4-input functions, and replaced with a
  precomputed subgraph when that reduces size. With zero-cost replacement on,
  replacements that don't increase size are accepted too.
- **Citation:** Mishchenko, Chatterjee, and Brayton, DAC 2006,
  [10.1145/1146909.1147048](https://doi.org/10.1145/1146909.1147048).
- **Matches:** DLP 60's bound of four read views and its "largest match"
  choice. Rewriting picks "the one that leads to the largest improvement at a
  node" (IWLS 2006 description).
- **Differs:** It's cut-based. The draft measured cut-based matches and
  rejected them because they leave second spellings legal when the arguments
  aren't in the value's cut.
- **Verified:** Read the abstract and Section 3 (NPN classes and the
  4-feasible cuts).

### Boolean Matching for Library Binding (Technology Mapping)

- **What:** "Boolean matching means solving this task [whether a cell can
  implement a portion of the network] using a formalism based on Boolean
  algebra." In its simplest form, it's a tautology check. Input permutation
  and polarity are handled with canonical forms and **symmetry sets**, groups
  of inputs that can be permuted without changing the function. The survey
  calls binding with selection "computationally intractable." Keutzer's DAGON
  covers trees optimally with dynamic programming; secondary sources say DAG
  covering is NP-hard.
- **Citations:**
  - Benini and De Micheli, "A Survey of Boolean Matching Techniques for
    Library Binding," ACM TODAES 2(3), 1997,
    [10.1145/264995.264996](https://doi.org/10.1145/264995.264996),
    [PDF](https://si2.epfl.ch/demichel/publications/archive/1997/TODAESvol2iss3Jul97pg193.pdf).
  - Mailhot and De Micheli, IEEE TCAD 12(5), 1993 (secondary only).
  - Keutzer, "DAGON," DAC 1987 (secondary only).
  - Mishchenko, "Fast Computation of Symmetries in Boolean Functions," IEEE
    TCAD 2003, [10.1109/TCAD.2003.818371](https://doi.org/10.1109/TCAD.2003.818371)
    (metadata only).
- **Matches:**
  - P3 is Boolean matching of each value against a library (the registered
    operations), with argument permutation ("given to the registered
    operation's read views in some order") and output polarity (opposite
    results).
  - P5's interchangeable views are symmetry sets, computed from the function,
    as in matching.
  - DLP 60's reason for reporting one match at a time instead of choosing the
    best set ("which is NP-hard") is the same hardness as cover selection in
    mapping.
- **Differs:**
  - Mapping covers the whole network to minimize cost. Define only requires
    that no single match remains.
  - Mapping chooses and rewrites. Define reports and makes the programmer
    rewrite.
  - Define's precedence (P4) is a fixed user-facing order, not area or delay.
- **Verified:** Read the Benini–De Micheli survey (introduction and Sections
  3.1–3.3). Mailhot and DAGON from search summaries only. Mishchenko 2003
  metadata only.

### Functional Recognition of Library Blocks (Reverse Engineering)

- **What:** Subramanyan et al. identify "all nodes in the circuit that match
  functions from a bitslice library" with 6-feasible cuts and
  permutation-independent Boolean matching. BoolE (Yin et al., 2025) uses
  equality saturation to recover full adders and other blocks in netlists.
- **Citations:**
  - Subramanyan et al., "Reverse Engineering Digital Circuits Using Structural
    and Functional Analyses," IEEE TETC 2(1), 2014,
    <https://cse.iitk.ac.in/users/spramod/papers/tetc14.pdf>.
  - Yin, Song, Chen, Hu, and Yu, "BoolE: Exact Symbolic Reasoning via Boolean
    Equality Saturation," arXiv 2504.05577, <https://arxiv.org/abs/2504.05577>.
- **Matches:** This is P3's question asked for analysis: which values in this
  logic are a known library function written out?
- **Differs:** Both are cut-bounded or rule-bounded and heuristic. Neither
  rejects anything.
- **Verified:** Read Subramanyan Section 2.1. Read the BoolE abstract only.

## 5. Superoptimization and Program Synthesis

### Souper

- **What:** A synthesizing superoptimizer for LLVM IR. It finds a
  cost-minimizing right-hand side equivalent to a left-hand side. It "first
  attempts to synthesize a zero-cost RHS (no new instructions are generated
  —the RHS may only use a constant or an input), then a cost-one RHS," using
  CEGIS with an SMT solver. Solver calls "often result in the solver being
  killed when a timeout expires," so results are cached.
- **Citation:** Sasnauskas, Chen, Collingbourne, Ketema, Lup, Taneja, and
  Regehr, "Souper: A Synthesizing Superoptimizer," arXiv 1711.04422 (2017),
  <https://arxiv.org/abs/1711.04422>.
- **Matches:** A zero-cost RHS is DLP 58's redundant value: the value is
  constant or equal to an existing value. A cost-one RHS that is one
  instruction over existing values is DLP 60's match against a single
  registered operation.
- **Differs:**
  - It's an optimizer with timeouts, so its results depend on the solver
    budget.
  - It works over bitvectors, not bounded boolean inputs.
  - Its "inputs" are the leaves of a harvested left-hand side, not all
    earlier values.
  - Its hand-implemented optimizations shipped in LLVM and MSVC, but it never
    rejects source programs.
- **Verified:** Read Section 2.8 (synthesis) and the caching section.

### Massalin, STOKE, and Alive

- **Massalin**, "Superoptimizer: A Look at the Smallest Program," ASPLOS 1987,
  [10.1145/36206.36194](https://doi.org/10.1145/36206.36194). It finds the
  shortest program for a function, using a probabilistic test to make
  exhaustive search practical. Abstract only.
- **STOKE** (Schkufza, Sharma, and Aiken), "Stochastic Superoptimization,"
  ASPLOS 2013, [10.1145/2451116.2451150](https://doi.org/10.1145/2451116.2451150).
  It uses MCMC search and "sacrifices completeness." Abstract only.
- **Alive** (Lopes, Menendez, Nagarakatte, and Regehr), "Provably Correct
  Peephole Optimizations with Alive," PLDI 2015,
  [10.1145/2737924.2737965](https://doi.org/10.1145/2737924.2737965). It
  verifies peephole rewrites with SMT. Metadata only.
- **Relation:** They share Define's tools (exhaustive or SMT equivalence over
  small fragments). None makes equivalence a rule for source programs. STOKE
  is explicitly incomplete.

### Code Clones Found by Behavior

- **What:** Jiang and Su's EqMiner extracts candidate code fragments and
  "random inputs are generated to partition the code fragments based on their
  output values."
- **Citation:** Jiang and Su, "Automatic Mining of Functionally Equivalent
  Code Fragments via Random Testing," ISSTA 2009,
  [10.1145/1572272.1572283](https://doi.org/10.1145/1572272.1572283).
- **Matches:** It's the software analogue of P8's simulation signatures: group
  values by their behavior on random inputs to find candidate equalities.
- **Differs:** The equivalence it finds is only up to the tests it ran, and
  it's a mining tool.
- **Verified:** Secondary (search summary quoting the abstract).

## 6. E-Graphs and Equality Saturation

- **What:** Equality saturation adds equalities to an e-graph and then
  extracts one program with a cost function. In egg, extraction "selects an
  optimal represented term from an e-class." With a local cost function, this
  is a fixed-point traversal, and the process stops at saturation "or a
  timeout." Extraction with DAG cost (shared subterms counted once) is NP-hard
  and hard to approximate within any constant ratio. Ruler infers rewrite
  rules from e-graphs, seeding e-classes with sample values ("characteristic
  vectors") to propose equalities. E-Syn applies e-graphs to logic synthesis
  with technology-aware costs.
- **Citations:**
  - Tate, Stepp, Tatlock, and Lerner, "Equality Saturation: A New Approach to
    Optimization," POPL 2009,
    [10.1145/1480881.1480915](https://doi.org/10.1145/1480881.1480915).
  - Willsey et al., "egg," POPL 2021,
    [10.1145/3434304](https://doi.org/10.1145/3434304).
  - Goharshady, Lam, and Parreaux, "Fast and Optimal Extraction for Sparse
    Equality Graphs," OOPSLA 2024,
    [10.1145/3689801](https://doi.org/10.1145/3689801).
  - Nandi et al., "Rewrite Rule Inference Using Equality Saturation," OOPSLA
    2021, [10.1145/3485496](https://doi.org/10.1145/3485496).
  - Chen et al., "E-Syn," DAC 2024, arXiv 2403.14242.
- **Matches:**
  - Extraction with a lexicographic cost is the closest PL analogue of P4's
    spelling precedence: pick one representative per equivalence class by a
    cost order.
  - Ruler's characteristic vectors are P8's simulation signatures.
- **Differs:**
  - Equality saturation finds only the equalities its rules derive before
    saturation or a timeout. P1 needs functional equality, decided
    semantically.
  - Extraction rewrites; it doesn't reject.
  - Extraction can choose a **whole** program per class. DLP 60 doesn't try:
    it reports one match at a time, and the draft records that equivalent
    programs don't converge.
- **Verified:** Read egg's Section 6 and the extraction overview. Read the
  Tate et al., egg, and Ruler abstracts. Read the Goharshady et al. abstract
  via its page. E-Syn from a search summary of its abstract.

## 7. Canonical Order

- **What:**
  - Binary AIGER requires each AND gate to satisfy `lhs > rhs0 >= rhs1`, a
    fixed order on statements and on the two fanins.
  - The FRAIG construction orders the arguments of each AND "to ensure that
    swapping of fanins does not create a new node."
  - LLVM's Reassociate pass ranks values (constants 0, arguments next, then
    instructions in order) and sorts the operands of commutative expressions
    by rank.
- **Citations:**
  - AIGER format, <https://fmv.jku.at/aiger/FORMAT>.
  - FRAIG paper (above).
  - `llvm/lib/Transforms/Scalar/Reassociate.cpp` in
    <https://github.com/llvm/llvm-project>.
- **Matches:** P5's rank order and P6's single statement order. Define's rank
  (interface views, then literals, then computed values compared by their
  arguments) is the same kind of rule as Reassociate's.
- **Differs:** These orders are internal normalizations or file-format
  requirements, not rules on source programs. Define's order is a
  depth-first, first-use order from the consumers. That's a standard traversal
  (topological DFS post-order), but I found no language that requires it in
  source.
- **Verified:** Read the AIGER format text (ordering section) and the
  Reassociate source header and rank code. The background document
  `define/proposals/background/boolean-logic-representations.md` already
  covers more canonicalization prior art (hash-consing, global value
  numbering, Maude, Z3, cvc5).

## 8. Termination and Confluence of Fixing

### Dershowitz–Manna Multiset Ordering

- **What:** The well-founded ordering on finite multisets that P10's measure
  uses.
- **Citation:** Dershowitz and Manna, "Proving Termination with Multiset
  Orderings," CACM 22(8):465–476, 1979,
  [10.1145/359138.359142](https://doi.org/10.1145/359138.359142).
- **Matches:** P10's termination argument (counts, then multisets of keys and
  of expressions) is the standard way to prove termination of rewriting.
  Nothing in it is new as a technique. What's new is the system it's applied
  to.
- **Note:** Mathlib now has `Multiset.IsDershowitzMannaLT` and
  `Multiset.wellFounded_isDershowitzMannaLT` (`Mathlib/Data/Multiset/DershowitzManna.lean`,
  2024). `proof/fixing_termination.lean` defines its own `DMLt`.
- **Verified:** Bibliographic only for the paper. Read the Mathlib file header.

### No Convergent Rewriting System for Boolean Algebra

- **What:** Socher-Ambrosius proved that "although there exists a normal form
  for boolean algebra terms, the so called set of prime implicants, there does
  not exist a convergent term rewriting system for the theory of boolean
  algebra." Hsiang (1985) gave a canonical rewriting system for Boolean
  **rings**, with associativity and commutativity built in. Knuth–Bendix
  completion is the standard procedure for turning equations into a
  convergent system, and it can fail to terminate.
- **Citations:**
  - Rolf Socher-Ambrosius, "Boolean Algebra Admits No Convergent Term
    Rewriting System," RTA 1991, LNCS 488, pp. 264–274,
    [10.1007/3-540-53904-2_102](https://doi.org/10.1007/3-540-53904-2_102).
  - Hsiang, "Refutational Theorem Proving Using Term-Rewriting Systems,"
    Artificial Intelligence 25, 1985,
    [10.1016/0004-3702(85)90074-8](https://doi.org/10.1016/0004-3702(85)90074-8).
  - Knuth and Bendix, "Simple Word Problems in Universal Algebras," in
    Leech (ed.), _Computational Problems in Abstract Algebra_, Pergamon, 1970.
- **Matches:** P10's non-confluence. A fix system for and/not programs that
  keeps their structure, instead of rewriting to a normal form like a
  polynomial over a Boolean ring or an OBDD, shouldn't be expected to be
  confluent. DLPs 58 and 60 already say that canonical forms that would make
  it confluent can be exponentially large.
- **Differs:** These results are about rewriting terms to normal forms modulo
  equations. Define's fixes are driven by semantic checks and a cost order. So
  this is an analogy, not a theorem about Define's system.
- **Verified:** Secondary for all three. The Socher-Ambrosius quote came from
  a search summary of the report's abstract. The Saarland repository copy
  (<https://publikationen.sulb.uni-saarland.de/handle/20.500.11880/37665>)
  blocked automated download, and the Springer page needs a login. The Hsiang
  and Knuth–Bendix details are bibliographic.

## 9. Modular Checking With Function Summaries

- **What:** P9 treats an execution as a reference to a recorded function
  (truth table or OBDD) and refines it in SAT only when a counterexample
  disagrees with it. That's counterexample-guided abstraction refinement
  (CEGAR) with uninterpreted, then expanded, sub-functions. The
  truth-table-hash invalidation is a semantic version of content-addressed
  rebuilding (compare Dhall's normal-form hashes and Unison's structural
  hashes, above).
- **Citation:** Clarke, Grumberg, Jha, Lu, and Veith,
  "Counterexample-Guided Abstraction Refinement," CAV 2000, LNCS 1855. This
  is bibliographic from memory; I didn't verify it this session, and a lookup
  attempt was rate-limited.
- **Matches:** The technique in P9.
- **Differs:** P9's hybrid (clauses for an execution's first four
  disagreements, then expand it) is a specific refinement policy. I didn't
  search for that exact policy.
- **Verified:** Not verified.

## Summary Table

| Piece                                                                                      | Closest prior work                                                                       | Standard?                                     | What's different in Define                                                                                                 |
| ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| P1 Redundant value is an error                                                             | FRAIG property; MISRA C Rule 2.2; Clippy `overly_complex_bool_expr`; Elm redundant patterns | The invariant is standard (FRAIG)             | A compile error, exact with no resource-limit loophole, over a whole value operation                                       |
| P2 No literals                                                                             | Clippy `nonminimal_bool` (`a && true`); FRAIG trivial cases                             | Standard simplification                       | An error instead of folding; it covers every boolean value operation                                                        |
| P3 Matches against registered operations                                                   | k-resubstitution (MFFC ≥ k+1); Boolean matching for library binding; Souper cost-one RHS | The algorithm and gain rule are standard      | Library = project registrations; all earlier values as divisors; exact, with no don't-cares; reported, not applied          |
| P4 Spelling precedence                                                                     | E-graph extraction with a cost function; zero-cost replacement in ABC                    | The idea of a cost order is standard          | A fixed, user-facing lexicographic order that also guarantees termination                                                   |
| P5 Interchangeable views                                                                   | Symmetry sets in Boolean matching; FRAIG/AIGER fanin order; LLVM Reassociate ranks       | Standard                                      | Required in source                                                                                                         |
| P6 Statement order                                                                         | AIGER topological order; DFS post-order                                                  | Standard traversal                            | Required in source                                                                                                         |
| P7 No wrappers                                                                             | None found                                                                               | Not found                                     | Seems specific to Define's split between actions and value operations                                                       |
| P8 Exact deterministic check                                                               | Kuehlmann et al. 2002; FRAIG construction; simulation-guided resubstitution             | Standard methods                              | A complete final rung (bounded truth tables), so the answer doesn't depend on the solver                                    |
| P9 References, incremental checks, stored patterns                                         | CEGAR; Lee et al. reusable patterns; content-addressed builds                            | Each piece is standard                        | The combination, per definition, in a compiler                                                                             |
| P10 Fixing terminates, isn't confluent                                                     | Dershowitz–Manna; Socher-Ambrosius                                                       | Standard technique; non-confluence expected   | The specific measure and a Lean proof for this fix system                                                                  |
| P11 Limits that make the rule decidable                                                    | Bagnara et al. on undecidable coding rules                                               | I found no precedent for this use             | Turns a MISRA-2.2-style rule into a decidable one with a bounded worst case                                                |

## Conclusion

**Is the combination novel?** As far as this search found, yes. The novelty
isn't in any one algorithm. It's in turning logic-synthesis invariants (a
FRAIG with no duplicate functions, and a network with no profitable
resubstitution against a given library) into **rules about which programs
compile**. That has three parts:

- they're exact and deterministic, through bounded inputs;
- each rule has one diagnostic and a mechanical fix;
- the fix loop is proved to terminate.

The searches that turned up nothing related were these:

- "programming language that rejects programs not in canonical form";
- semantic redundancy as a compile error in any language;
- SMT-based redundant-condition detection used as a rule rather than a
  warning;
- library-match errors in any language.

All four found only warnings, optimizers, or internal canonicalization.

**What's standard:**

- AIGs with structural hashing and the trivial AND rules;
- the FRAIG invariant and its construction;
- SAT sweeping with simulation, BDD fallback, and counterexample patterns;
- reusing simulation patterns across runs and edits;
- k-resubstitution with the MFFC gain rule, and zero-cost replacement;
- Boolean matching with permutation, polarity, and symmetry sets;
- cut-based 4-input NPN rewriting;
- canonical fanin and operand ordering by rank;
- CEGAR over function summaries;
- Dershowitz–Manna termination arguments;
- the absence of a convergent rewriting system for Boolean algebra.

**Closest prior work:**

- **For DLP 58 (P1, P2, P8):** Mishchenko, Jiang, Chatterjee, and Brayton,
  "FRAIGs," which defines and builds exactly the invariant DLP 58 enforces,
  as a data structure and not a rule.
- **For DLP 60 (P3, P4):** Mishchenko and Brayton's k-resubstitution (IWLS
  2006), whose gain rule DLP 60 reproduces, and Boolean-matching library
  binding (Benini and De Micheli's survey).
- **For DLP 59 (P5, P6):** symmetry detection in Boolean matching, and the
  operand ordering in FRAIG construction, AIGER, and LLVM's Reassociate.
- **For the language-design stance:** Go's errors-only policy, Elm's
  redundant-pattern error, and MISRA C:2012 Rule 2.2. The last is the only
  mandatory semantic redundancy rule I found, and Bagnara et al. argue it's
  unprovable in general. Define's limits are what make its version decidable.

## Observations for the Proposals

- **Complements aren't redundant values in DLP 58 as written.**
  - **Prior art counts them.** Every source here treats a node that's always
    the opposite of another as redundant: FRAIG's definition, 0-resubstitution
    "up to complementation," and Lee et al.'s `resub-0` (which tries `¬d`).
  - **What DLP 58 says.** It only counts a value that's always the *same* as
    an earlier value or input. The draft's candidates are "the earlier nodes
    with the same signature," which doesn't include the complemented
    signature.
  - **Example.** With `u = a and b` computed, a value written out as
    `or(not a, not b)` is always `not u`. As far as I can tell, it's not a
    redundant value, and not a DLP 60 match either, since `not u` isn't an
    execution of a registered operation. So it would compile, even though
    `not u` is one statement against three.
  - **Possibly intended.** DLP 60 handles opposites only for registered
    operations, so this may be on purpose. I'm reporting it because every
    prior system treats it the other way.
- **The termination proof could use Mathlib's Dershowitz–Manna order.**
  Mathlib's `Multiset.IsDershowitzMannaLT` with its well-foundedness theorem
  could replace the local `DMLt` in `proof/fixing_termination.lean`. That's
  optional, and I didn't check whether the definitions match.

## Searches That Found Nothing Usable

- SpyGlass or other commercial HDL lint documentation on redundant logic.
- Any published policy on preventing cycles in zero-cost replacement beyond
  ABC's options.
- A primary source for Zig's unused-variable rule, and for Unison's behavior
  when a new definition's hash already exists.
- The full text of Socher-Ambrosius (1991) and Hsiang (1985).
