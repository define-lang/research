"""Value operations with written-out registered operations, for matching.

The registered operations are small standard compositions. A value operation
executes them (an execution is legitimate) and also writes some of them out
with `and` and `not` statements (a match, which DLP 59 forbids). Three ways of
writing one out are planted:

- `local`: another way of writing the operation directly on its arguments,
  which DLP 59's cuts of at most four values can see.
- `sop`: a sum of products over the inputs of the arguments' cones, so one
  argument that the operation already has is never computed again. Cuts see
  the inputs, not the argument.
- `split`: a case split on an unrelated value `c`, written as
  `(c and R(args)) or (not c and R(args))` with the operation written a
  different way on each side. Every cut that reaches the arguments includes
  `c`.

Besides the AIGER file, `write` produces `.statements` (one line per value a
statement computes: its literal, the operation it executes or `and`, and the
literals it was given) and `.planted` (the value, the registered operation, and
its arguments in view order).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from workloads import (
    FALSE,
    OPS,
    TRUE,
    Program,
    Value,
    _pick_operand,
    _sinks,
    and_c,
    or_c,
)

if TYPE_CHECKING:
    import random
    from collections.abc import Callable, Sequence

    from aig_builder import Builder


def _table(arity: int, f: Callable[..., int]) -> int:
    """Return the truth table of f over `arity` views, bit m for minterm m."""
    out = 0
    for m in range(1 << arity):
        if f(*[(m >> i) & 1 for i in range(arity)]):
            out |= 1 << m
    return out


# Registered operations: arity, truth table over the views in order, and the
# key of their implementations in workloads.OPS.
REGISTERED: dict[str, tuple[int, int, str]] = {
    "or": (2, _table(2, lambda a, b: a | b), "or"),
    "xor": (2, _table(2, lambda a, b: a ^ b), "xor"),
    "eq": (2, _table(2, lambda a, b: 1 - (a ^ b)), "eq"),
    "implies": (2, _table(2, lambda a, b: (1 - a) | b), "implies"),
    "mux": (3, _table(3, lambda c, t, e: t if c else e), "mux"),
    "maj": (3, _table(3, lambda a, b, c: int(a + b + c >= 2)), "maj"),
}

# Operations that aren't registered, executed as they are.
UNREGISTERED = {"and": 2, "and3": 3, "or3": 3}

WEIGHTS = {
    "and": 30,
    "or": 22,
    "implies": 4,
    "xor": 5,
    "eq": 6,
    "mux": 12,
    "maj": 2,
    "and3": 10,
    "or3": 9,
}


@dataclass
class Statement:
    """One value a statement computes."""

    lit: int
    op: str
    args: tuple[int, ...]


@dataclass
class Recorder:
    """Statements and planted matches of a value operation being generated."""

    statements: list[Statement] = field(default_factory=list)
    planted: list[tuple[int, str, tuple[int, ...], str]] = field(default_factory=list)


def _record_ands(b: Builder, rec: Recorder, before: int) -> None:
    """Record every `and` node built since `before` as an `and` statement."""
    first = b.num_inputs + 1
    for k in range(before, len(b.fanin0)):
        rec.statements.append(
            Statement(2 * (first + k), "and", (b.fanin0[k], b.fanin1[k]))
        )


def _isop(b: Builder, on: int, off_or_dc: int, lits: Sequence[int], n: int) -> int:
    """Build an irredundant sum of products for a function over `lits`.

    `on` is the truth table where the function must be true, and
    `off_or_dc` where it may be true (on plus don't cares), over n variables.
    This is the Minato-Morreale recursion on truth tables.
    """
    full = (1 << (1 << n)) - 1
    # mask[v]: the combinations where variable v is true.
    mask = [0] * n
    for v in range(n):
        block = ((1 << (1 << v)) - 1) << (1 << v)
        period = 1 << (v + 1)
        for start in range(0, 1 << n, period):
            mask[v] |= block << start

    def cof(t: int, v: int, val: int) -> int:
        # The cofactor, as a table over all variables that ignores v.
        shift = 1 << v
        if val:
            half = t & mask[v]
            return half | (half >> shift)
        half = t & ~mask[v] & full
        return half | (half << shift)

    memo: dict[tuple[int, int, int], tuple[int, list[list[tuple[int, int]]]]] = {}

    def go(lo: int, hi: int, var: int) -> tuple[int, list[list[tuple[int, int]]]]:
        if lo == 0:
            return 0, []
        if hi == full:
            return full, [[]]
        key = (lo, hi, var)
        if key in memo:
            return memo[key]
        v = var
        lo0, lo1, hi0, hi1 = cof(lo, v, 0), cof(lo, v, 1), cof(hi, v, 0), cof(hi, v, 1)
        f0, c0 = go(lo0 & ~hi1 & full, hi0, var + 1)
        f1, c1 = go(lo1 & ~hi0 & full, hi1, var + 1)
        rest_lo = ((lo0 & ~f0) | (lo1 & ~f1)) & full
        f2, c2 = go(rest_lo, hi0 & hi1, var + 1)
        f = (f0 & ~mask[v]) | (f1 & mask[v]) | f2
        cubes = [[(v, 0), *c] for c in c0] + [[(v, 1), *c] for c in c1] + c2
        memo[key] = (f & full, cubes)
        return memo[key]

    _, cubes = go(on, off_or_dc, 0)
    result = FALSE
    for cube in cubes:
        term = TRUE
        for v, val in cube:
            term = and_c(b, term, lits[v] ^ (0 if val else 1))
        result = or_c(b, result, term)
    return result


def _signature_ok(p: Program, lits: Sequence[int]) -> bool:
    """Return whether none of these new values looks redundant on simulation."""
    seen = set(p.signatures)
    for lit in lits:
        sig = p.b.sim(lit)
        if sig in seen or sig ^ p.b.sim_mask in seen:
            return False
        seen.add(sig)
    return True


def _support(p: Program, index: int) -> list[int]:
    return sorted(p.support(index))


def _function_over(p: Program, index: int, leaves: Sequence[int]) -> int:
    """Truth table of value `index` over input values `leaves`, by evaluation."""
    out = 0
    n = len(leaves)
    for m in range(1 << n):
        assignment = {leaf: (m >> i) & 1 for i, leaf in enumerate(leaves)}
        memo: dict[int, int] = {}

        def ev(
            v: int, memo: dict[int, int] = memo, assignment: dict[int, int] = assignment
        ) -> int:
            if v in memo:
                return memo[v]
            value = p.values[v]
            if not value.op:
                r = assignment[v]
            else:
                args = [
                    ev(a) ^ int(neg)
                    for a, neg in zip(value.args, value.negate, strict=True)
                ]
                r = _evaluate(value.op, args)
            memo[v] = r
            return r

        if ev(index):
            out |= 1 << m
    return out


def _evaluate(op: str, args: Sequence[int]) -> int:
    if op in REGISTERED:
        _, table, _ = REGISTERED[op]
        return (table >> sum(a << i for i, a in enumerate(args))) & 1
    if op in ("and", "and3"):
        return int(all(args))
    if op == "or3":
        return int(any(args))
    raise ValueError(op)


def matching_operation(
    rng: random.Random, num_inputs: int, num_statements: int, plant_rate: float = 0.15
) -> tuple[Builder, Recorder]:
    """Return a legal value operation with planted written-out operations."""
    p = Program(num_inputs, rng, legal=True)
    rec = Recorder()
    names = list(WEIGHTS)
    weights = [WEIGHTS[n] for n in names]
    statements = 0
    attempts = 0
    while statements < num_statements and attempts < 50 * num_statements:
        attempts += 1
        composite = len(p.values) - num_inputs
        if composite > 4 and rng.random() < plant_rate and _plant(p, rec):
            statements += 1
            continue
        op = rng.choices(names, weights)[0]
        arity = REGISTERED[op][0] if op in REGISTERED else UNREGISTERED[op]
        args: list[int] = []
        while len(args) < arity:
            a = _pick_operand(p, 8, 0.35)
            if a not in args:
                args.append(a)
        # Giving a negated value to a registered operation is usually a match
        # of another one (`or(not a, b)` is `implies(a, b)`), which DLP 59
        # rejects, so only unregistered ones get negated values.
        negate = [op not in REGISTERED and rng.random() < 0.25 for _ in args]
        variants = OPS[op][1]
        index = p.try_apply(op, args, negate, rng.randrange(len(variants)))
        if index is None:
            continue
        lits = tuple(
            p.values[a].lit ^ int(n) for a, n in zip(args, negate, strict=True)
        )
        rec.statements.append(Statement(p.values[index].lit, op, lits))
        statements += 1
    p.b.outputs = [p.values[v].lit for v in _sinks(p)]
    return p.b, rec


def _plant(p: Program, rec: Recorder) -> bool:
    """Write out one registered operation on available values, if legal."""
    rng = p.rng
    num_inputs = p.b.num_inputs
    name = rng.choice(list(REGISTERED))
    arity, table, impl = REGISTERED[name]
    kind = rng.choice(["local", "sop", "split"])
    low = max(0, len(p.values) - 40)
    pool = list(range(low, len(p.values)))
    args = rng.sample(pool, arity) if len(pool) >= arity else None
    if args is None:
        return False
    arg_lits = [p.values[a].lit for a in args]
    before = len(p.b.fanin0)
    variants = OPS[impl][1]
    if kind == "local":
        lit = variants[rng.randrange(len(variants))](p.b, arg_lits)
    elif kind == "split":
        others = [v for v in pool if v not in args]
        if not others:
            return False
        c = p.values[rng.choice(others)].lit
        one = variants[rng.randrange(len(variants))](p.b, arg_lits)
        two = variants[rng.randrange(len(variants))](p.b, arg_lits)
        lit = or_c(p.b, and_c(p.b, c, one), and_c(p.b, c ^ 1, two))
    else:
        # Leaves: each argument that's an input stays; a composite argument is
        # replaced by its own inputs, so it isn't computed again.
        if all(not p.values[a].op for a in args):
            return False
        leaves = sorted(
            {leaf for a in args for leaf in (_support(p, a) if p.values[a].op else [a])}
        )
        if len(leaves) > 8:
            return False
        tables = []
        for a in args:
            if p.values[a].op:
                tables.append(_function_over(p, a, leaves))
            else:
                position = leaves.index(a)
                tables.append(_table(len(leaves), lambda *x, i=position: x[i]))
        on = 0
        for m in range(1 << len(leaves)):
            idx = sum(((t >> m) & 1) << i for i, t in enumerate(tables))
            if (table >> idx) & 1:
                on |= 1 << m
        lit = _isop(p.b, on, on, [p.values[leaf].lit for leaf in leaves], len(leaves))
    new = [2 * (num_inputs + 1 + k) for k in range(before, len(p.b.fanin0))]
    # Every plant must compute R(args); check it on the simulation patterns.
    sims = [p.b.sim(a) for a in arg_lits]
    expected = 0
    for m in range(1 << arity):
        if (table >> m) & 1:
            term = p.b.sim_mask
            for i, s in enumerate(sims):
                term &= s if (m >> i) & 1 else s ^ p.b.sim_mask
            expected |= term
    if p.b.sim(lit) != expected:
        raise AssertionError(f"planted {kind} {name} doesn't compute it")
    if not new or lit >> 1 != new[-1] >> 1 or not _signature_ok(p, [*new[:-1], lit]):
        p.b.truncate(before)
        return False
    _record_ands(p.b, rec, before)
    if lit & 1:
        # The value is the `not` of the last `and`.
        rec.statements.append(Statement(lit, "not", (lit ^ 1,)))
    # The statement that computes the value itself might be the negation of
    # the last `and`.
    for value in [*new[:-1], lit]:
        p.signatures.add(p.b.sim(value))
    rec.planted.append((lit, name, tuple(arg_lits), kind))
    p.values.append(Value(lit))
    return True


def write(b: Builder, rec: Recorder, path: str) -> None:
    """Write the AIG in DLP 59's statement order, with its statements and plants."""
    order = b.reorder_first_need(b.outputs + [p[0] for p in rec.planted])
    mapping = order.node_map
    assert mapping is not None  # noqa: S101 - Set by reorder_first_need.

    def remap(lit: int) -> int:
        return 2 * mapping[lit >> 1] + (lit & 1)

    order.write(path)
    base = path.removesuffix(".aag")
    with open(base + ".statements", "w", encoding="ascii") as out:
        out.writelines(
            " ".join([str(remap(st.lit)), st.op, *[str(remap(a)) for a in st.args]])
            + "\n"
            for st in rec.statements
        )
    with open(base + ".planted", "w", encoding="ascii") as out:
        out.writelines(
            " ".join([str(remap(lit)), name, kind, *[str(remap(a)) for a in args]])
            + "\n"
            for lit, name, args, kind in rec.planted
        )
