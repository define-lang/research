# A Precedence Rule Between Spellings

[earlier_values.md](earlier_values.md) found that fixing equivalent programs
until they compile almost never reaches one program, and that the results
differ partly in which registered operation spells a value: `or(i3, not s2)`
in one program, `implies(s2, i3)` in another, when `not s2` is read
elsewhere. This study adds a rule for that:

> When a value can be computed by more than one execution of a registered
> operation, or a `not` of one, over earlier values, the program must use
> the one with the highest precedence. A value that is an execution of a
> lower-precedence spelling, or a `not` of one, is an error, and its fix
> replaces that statement with the higher-precedence spelling.

Precedence, in order:

1. **Fewest negations:** the values given that are a `not` of another
   value, plus one if the spelling needs a `not` of its result.
2. **Fewest AIG nodes** in the registered operation's own logic: 1 for `or`
   and `implies`, 3 for `xor`, `eq`, and `mux`, 4 for `maj`.
3. **Declared order:** two arbitrary orders, A (`or`, `implies`, `xor`,
   `eq`, `mux`, `maj`) and B (the reverse).
4. **The values in DLP 60's rank order**, for the same operation given
   different values.

When a fix replaces an ordinary match, it uses the highest-precedence
spelling among the matches of that value and size, not just any of them.

These matches are 1-for-1: they replace one statement (or a `not` and an
execution) with an execution, so they don't shrink the program. They're
checked after the other matches.

**Short answers.** As given, the rule makes fixes cycle (125 of 720 fix
loops). One restriction prevents that, and with it all 2,880 fix loops
terminated. But the rule hardly changes convergence: `expand` families
reach one program in 1 of 8 at 8 inputs and 2 of 8 at 12 (1 and 0 of 8
before), and
`demorgan` and `mixed` families still almost never do. Which declared
order is used changes the fixed program in 27–50% of programs, but not how
often families converge. Checking costs about 50% more: 3.5–8 ms for a
compiling value operation at 16 inputs and 8.6–23 ms at 20.

The code is the `--spellings` and `--precedence` options of `beq match
--how resub` (`src/match.hpp`), `precedence_match` in `gen/fixpoint.py`, and
`fixpoint_experiment.py --precedence`. The results are in
`results/fixpoint.jsonl.gz` (policies ending in `|prec:A`, `|prec:A|strict`,
`|prec:B|strict`, and `|strict`), summarized in `results/fixpoint_tables.md`.
Every check ran under 30 s and 4 GB, and every fix loop under 30 s.

These results use DLP 59's current definition of a redundant value, which
includes a value that's always the opposite of an earlier one unless it's
that value's `not`. The runs before that change are in
`results/preliminary/fixpoint_before_opposite_values.jsonl.gz`. With the
restriction, the change moves one family (`expand` at 12 inputs with order
A) to convergence, the most rounds from 83 to 80, and the costs below by
less than their run-to-run spread.

## Termination

As given, 125 of 720 fix loops cycled (57 before opposite values were
redundant), of three kinds:

- **Against an ordinary match.** The precedence rule prefers a spelling
  with fewer negations, such as `not implies(a, b)` over `mux(s, c, d)` with
  two negated values, while an ordinary match prefers fewer statements and
  turns the `not` and the `implies` back into one `mux`.
- **Through a redundant value.** A value `not u` was respelled as the `not`
  of an `or` that reads u itself, which is a redundant value equal to u;
  replacing it restored the original.
- **Against an opposite value.** A `not u` respelled as an execution, such
  as `not s3` as `xor(s1, eq(s1, s3))`, is always the opposite of u, so
  it's a redundant value, and its fix restores `not u`. 32 of the first 40
  cycles were of this kind.

Excluding a value's opposite spellings when the program already has the
value's `not` removes the second kind, but not the first. One restriction,
which this study calls **strict**, removes all three: **no fix may grow the
program.** An ordinary match has to remove more statements than its fix
adds, so a match with an opposite result has to remove at least three; and a
precedence fix can't add a statement, so spellings that need a `not` of
their result don't count.

With it, every one of 2,880 fix loops (720 under each of DLP 59's order,
earliest first, and smallest first with declared order A, and 720 with
order B) ended with a program that compiles, in at most 80 rounds. There's
also an argument that it always terminates: redundant-value fixes and
ordinary matches make the program smaller, and a precedence fix keeps its
size and lowers the precedence key of one value. Other values' keys can
only go down: their statements don't change, and the one value may stop
being a `not` that they're given. So the number of statements, and then
the values' keys, go down at every fix. This is argued, not proved in
detail.

## Convergence

Families that reach one program, out of 8, with DLP 59's order of fixes:

| rewrites | inputs | before | strict only | precedence A, as given | precedence A, strict | precedence B, strict |
| --- | --- | --- | --- | --- | --- | --- |
| expand | 8 | 1/8 | 1/8 | 2/8 (3 cycles) | 1/8 | 1/8 |
| expand | 12 | 0/8 | 0/8 | 2/8 | 2/8 | 1/8 |
| expand | 16 | 0/8 | 0/8 | 0/8 (21 cycles) | 0/8 | 0/8 |
| demorgan | 8 | 1/8 | 1/8 | 1/8 (3 cycles) | 1/8 | 1/8 |
| demorgan | 12 | 0/8 | 0/8 | 0/8 (11 cycles) | 0/8 | 0/8 |
| demorgan | 16 | 0/8 | 0/8 | 0/8 (11 cycles) | 0/8 | 0/8 |
| mixed | 8 | 0/8 | 0/8 | 0/8 (8 cycles) | 0/8 | 0/8 |
| mixed | 12 | 0/8 | 0/8 | 0/8 (8 cycles) | 0/8 | 0/8 |
| mixed | 16 | 0/8 | 0/8 | 0/8 (16 cycles) | 0/8 | 0/8 |
| duplicate | 8 | 8/8 | 8/8 | 8/8 (5 cycles) | 8/8 | 8/8 |
| duplicate | 12 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| duplicate | 16 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| reassociate | 8 | 6/8 | 6/8 | 6/8 (5 cycles) | 6/8 | 6/8 |
| reassociate | 12 | 4/8 | 4/8 | 4/8 (5 cycles) | 4/8 | 4/8 |
| reassociate | 16 | 5/8 | 4/8 | 5/8 (16 cycles) | 4/8 | 4/8 |
| distribute | 8 | 6/8 | 6/8 | 6/8 | 6/8 | 6/8 |
| distribute | 12 | 5/8 | 5/8 | 5/8 (8 cycles) | 5/8 | 5/8 |
| distribute | 16 | 2/8 | 2/8 | 3/8 (5 cycles) | 3/8 | 3/8 |

"Before" is [earlier_values.md](earlier_values.md)'s rule; "strict only"
adds the restriction without precedence. Earliest-first and
smallest-first orders of fixes, with precedence A, converge no more often
(`results/fixpoint_tables.md`).

- **Precedence changes little.** It respells executions, but what still
  differs is which intermediate values the programs have. In one `expand`
  family at 8 inputs, the base's result computes a value as `and(s2, s3)`
  over `s3 = implies(i2, i0)`, and a variant's computes the same written
  views through `mux(s3, i0, s4)` and two more `mux` executions over other
  values. Neither program has a value the other's spelling needs, so the
  rule has nothing to compare.
- **The differences are in the `and` and `not` statements.** Across the
  `expand` variants whose results differ from the base's, the results have
  90 more `not` and 41 more `and`, and 82 fewer `or`, than the base's
  (against 100 more `implies` and 167 fewer `or` before precedence). Two
  thirds of them still differ in size.
- **The declared order changes the result, not the convergence.** Orders A
  and B fixed the same program to the same result in 60–88 of 120 programs
  per kind of rewrite (50–73%), and converged in the same families.

## Cost

The rule needs every spelling of each value that is an execution or a `not`
of one, which the sole-reader shortcut of the match search can't skip.
`beq` lists only spellings that could come before the current one: an
operation is searched only if its smallest possible key (no negated values,
its nodes, its place in the order) comes before the value's current key.
Without that, checks at 20 inputs took up to 2.2 s and one fix loop didn't
finish in 30 s; with it, the fixed programs are identical (24 of 24
programs checked both ways).

Random programs of 256 statements, fixed until they compile (63–143
statements after):

| Inputs | Before | Strict only | Precedence A, strict |
| ------ | ------ | ----------- | -------------------- |
| 12 | 1.1–5.8 ms | 1.1–5 ms | 1.6–9.5 ms |
| 16 | 2.1–5.3 ms | 2.2–6.2 ms | 3.5–8 ms |
| 20 | 8.7–18 ms | 8.8–18 ms | 8.6–23 ms |

The check of the result, best of three. Fixing takes 43–78 rounds instead of
29–70 (7–27 of them precedence fixes), and 1.1–1.9 s at 16 inputs and
2.6–10 s at 20, checks and bookkeeping included; the slowest single check
was 0.70 s at 20 inputs. The families' fixed programs (median 10, 18, and
33 statements at 8, 12, and 16 inputs) check in 50 µs, 140 µs, and 0.6 ms
in the median, 1.1 ms at most.

An earlier run fixed ordinary matches with whichever matching operation
came first rather than the highest-precedence one. Its results, in
`results/preliminary/fixpoint_precedence_before_match_spelling.jsonl.gz`,
converge in exactly the same families; choosing the spelling there only
saves rounds (at most 87 before, 83 with it).

## Recommendations

1. **If the precedence rule is adopted, adopt the restriction with it.**
   As given it cycles; with it, every fix makes the program smaller or,
   for precedence, keeps its size and improves one value, and the fix loops
   terminate.
2. **It doesn't buy convergence.** The remaining differences are in the
   structure of the and-and-not logic, which no rule between spellings of
   one value reaches. Whether it's worth 50% more checking time depends on
   whether consistent spellings matter for their own sake (for reading
   code), not on convergence.
3. **The declared order matters to the result**, so across projects it
   needs the deterministic order the proposal gives.

## What's Measured and What's Argued

Measured: everything in the tables, on generated programs. Argued: that the
strict fix loops always terminate, and that the remaining differences are
beyond any rule between spellings of one value.
