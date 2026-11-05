"""Boolean value operations as programs, and applying DLP 58's fixes to them.

A program has `inputs` boolean inputs and a list of statements, each an
operation (`and`, `not`, or a registered operation) and the values it reads:
an input `i` is value `i`, and statement `k` is value `inputs + k`. Statements
only read earlier values. The written views are `outputs`.

`canonical` puts a program in DLP 58's one order: values that are given to
interchangeable views go in rank order, and each statement comes right
before the statement that first reads it, starting from the written views
in order. Two programs are the same program when their canonical forms are
identical.

`fix` applies the fix that the compiler's report asks for, again and again,
until the program compiles: for the first redundant value, use the value it
always equals instead, or the `not` of the value it's always the opposite of;
otherwise, for the reported match (the largest, then
the one whose value comes first, then by operation name, then by its values
in rank order), replace its value with an execution of the registered
operation (and a `not` of it for an opposite result). The matches come from
`beq match --how resub`, through a callback.
"""

from __future__ import annotations

import functools
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import random
    from collections.abc import Callable

# Registered operations: views and which of them are interchangeable.
REGISTERED = {
    "or": (2, [[0, 1]]),
    "xor": (2, [[0, 1]]),
    "eq": (2, [[0, 1]]),
    "implies": (2, []),
    "mux": (3, []),
    "maj": (3, [[0, 1, 2]]),
}
OPS = {"and": (2, [[0, 1]]), "not": (1, []), **REGISTERED}


@dataclass
class Program:
    """One boolean value operation."""

    inputs: int
    statements: list[tuple[str, tuple[int, ...]]] = field(default_factory=list)
    outputs: list[int] = field(default_factory=list)

    def add(self, op: str, *args: int) -> int:
        """Append a statement and return its value."""
        self.statements.append((op, args))
        return self.inputs + len(self.statements) - 1


def evaluate_op(op: str, args: list[int], mask: int) -> int:
    """Return the truth table of an operation on the tables of its values."""
    if op == "and":
        return args[0] & args[1]
    if op == "not":
        return args[0] ^ mask
    a, b = args[0], args[1]
    if op == "or":
        return a | b
    if op == "xor":
        return a ^ b
    if op == "eq":
        return (a ^ b) ^ mask
    if op == "implies":
        return (a ^ mask) | b
    c = args[2]
    if op == "mux":
        return (a & b) | ((a ^ mask) & c)
    if op == "maj":
        return (a & b) | (a & c) | (b & c)
    raise ValueError(op)


@functools.cache
def input_tables(inputs: int) -> tuple[int, ...]:
    """Return the truth table of each input over all of them."""
    size = 1 << inputs
    out = []
    for i in range(inputs):
        period = 1 << (i + 1)
        # One period is 2^i zeros then 2^i ones; repeat it by multiplying by
        # 1 + 2^period + 2^(2 period) + ....
        unit = ((1 << (1 << i)) - 1) << (1 << i)
        repeat = ((1 << size) - 1) // ((1 << period) - 1)
        out.append(unit * repeat)
    return tuple(out)


def tables(p: Program) -> list[int]:
    """Return the truth table of every value, inputs first."""
    mask = (1 << (1 << p.inputs)) - 1
    out = list(input_tables(p.inputs))
    for op, args in p.statements:
        out.append(evaluate_op(op, [out[a] for a in args], mask))
    return out


def first_redundant(p: Program) -> tuple[int, int | str, bool] | None:
    """Return the first redundant value, its other value, and whether opposite.

    The other value is the one it always equals or is always the opposite
    of. A value that's always the opposite of an earlier one is redundant unless
    its statement is the `not` of that value.
    """
    t = tables(p)
    mask = (1 << (1 << p.inputs)) - 1
    first: dict[int, int] = {}
    for v in range(p.inputs):
        first.setdefault(t[v], v)
    for v in range(p.inputs, len(t)):
        if t[v] in (0, mask):
            return v, "true" if t[v] else "false", False
        if t[v] in first:
            return v, first[t[v]], False
        opposite = first.get(t[v] ^ mask)
        if opposite is not None and p.statements[v - p.inputs] != ("not", (opposite,)):
            return v, opposite, True
        first[t[v]] = v
    return None


def rank_keys(p: Program) -> list[tuple]:
    """Return a key per value whose order is DLP 58's rank order."""
    keys: list[tuple] = [(0, i) for i in range(p.inputs)]
    for op, args in p.statements:
        ordered = ordered_args(op, args, keys)
        keys.append((1, tuple(keys[a] for a in ordered), op))
    return keys


def ordered_args(op: str, args: tuple[int, ...], keys: list[tuple]) -> tuple[int, ...]:
    """Return the values in view order, interchangeable views in rank order."""
    out = list(args)
    for group in OPS[op][1]:
        values = sorted((out[i] for i in group), key=lambda a: keys[a])
        for i, a in zip(group, values, strict=True):
            out[i] = a
    return tuple(out)


def canonical(p: Program) -> Program:
    """Return the program in DLP 58's statement order and argument order."""
    keys = rank_keys(p)
    out = Program(p.inputs)
    new: dict[int, int] = {i: i for i in range(p.inputs)}

    def visit(v: int) -> None:
        stack = [(v, False)]
        while stack:
            value, ready = stack.pop()
            if value in new:
                continue
            op, args = p.statements[value - p.inputs]
            ordered = ordered_args(op, args, keys)
            if ready:
                new[value] = out.add(op, *[new[a] for a in ordered])
                continue
            stack.append((value, True))
            stack.extend((a, False) for a in reversed(ordered) if a not in new)

    for o in p.outputs:
        visit(o)
    out.outputs = [new[o] for o in p.outputs]
    return out


def text(p: Program) -> str:
    """Return the canonical program as text, to compare programs."""
    c = canonical(p)

    def name(v: int) -> str:
        return f"i{v}" if v < c.inputs else f"s{v - c.inputs}"

    lines = [f"{op} {' '.join(name(a) for a in args)}" for op, args in c.statements]
    lines.append("out " + " ".join(name(o) for o in c.outputs))
    return "\n".join(lines)


def from_text(inputs: int, program: str) -> Program:
    """Return the program that `text` wrote."""
    p = Program(inputs)

    def value(name: str) -> int:
        return int(name[1:]) + (inputs if name[0] == "s" else 0)

    for line in program.splitlines():
        op, *args = line.split()
        if op == "out":
            p.outputs = [value(a) for a in args]
        else:
            p.add(op, *[value(a) for a in args])
    return p


def substitute(p: Program, old: int, replacement: int) -> Program:
    """Return the program with every use of `old` replaced."""
    out = Program(p.inputs)
    out.statements = [
        (op, tuple(replacement if a == old else a for a in args))
        for op, args in p.statements
    ]
    out.outputs = [replacement if o == old else o for o in p.outputs]
    return out


# Two-view functions over (a, b), bit a + 2b, written with the operations.
TWO_VIEW = {
    0x8: [("and", 0, 1)],
    0xE: [("or", 0, 1)],
    0x6: [("xor", 0, 1)],
    0x9: [("eq", 0, 1)],
    0xD: [("implies", 0, 1)],
    0xB: [("implies", 1, 0)],
    0x2: [("not", 1), ("and", 0, "t0")],
    0x4: [("not", 0), ("and", "t0", 1)],
    0x1: [("not", 0), ("not", 1), ("and", "t0", "t1")],
    0x7: [("and", 0, 1), ("not", "t0")],
}


def substitute_constant(p: Program, old: int, *, value: bool) -> Program | None:
    """Return the program with a constant value removed, as a programmer would.

    Every statement that reads a constant is replaced by what it computes on
    its other values: a constant, one of them, its `not`, or one statement.
    Returns None if a written view is constant, which can't be written.
    """
    out = Program(p.inputs)
    new: dict[int, int | bool] = {i: i for i in range(p.inputs)}
    for k, (op, args) in enumerate(p.statements):
        v = p.inputs + k
        if v == old:
            new[v] = value
            continue
        x = [new[a] for a in args]
        if not any(isinstance(a, bool) for a in x):
            new[v] = out.add(op, *x)  # type: ignore[arg-type]
            continue
        free = [a for a in x if not isinstance(a, bool)]
        # The residual function over the remaining values, bit per minterm.
        residual = 0
        for m in range(1 << len(free)):
            bits = iter((m >> i) & 1 for i in range(len(free)))
            given = [int(a) if isinstance(a, bool) else next(bits) for a in x]
            if evaluate_op(op, given, 1):
                residual |= 1 << m
        size = 1 << len(free)
        if residual in (0, (1 << size) - 1):
            new[v] = bool(residual)
        elif len(free) == 1:
            new[v] = free[0] if residual == 0b10 else out.add("not", free[0])  # type: ignore[arg-type]
        elif residual in (0b1010, 0b1100):
            new[v] = free[0 if residual == 0b1010 else 1]  # type: ignore[assignment]
        elif residual in (0b0101, 0b0011):
            new[v] = out.add("not", free[0 if residual == 0b0101 else 1])  # type: ignore[arg-type]
        else:
            temps: list[int] = []
            for st_op, *st_args in TWO_VIEW[residual]:
                resolved = [
                    temps[int(a[1:])] if isinstance(a, str) else free[a]
                    for a in st_args
                ]
                temps.append(out.add(st_op, *resolved))  # type: ignore[arg-type]
            new[v] = temps[-1]
    if any(isinstance(new[o], bool) for o in p.outputs):
        return None
    out.outputs = [new[o] for o in p.outputs]  # type: ignore[misc]
    return out


def write_aig(p: Program, base: str) -> dict[int, int]:
    """Write BASE.aag and BASE.statements for `beq match`; return lit to value.

    Each statement becomes the AND nodes that compute it, in statement order,
    so a statement's literal is that of its last node (or its argument's,
    negated, for `not`).
    """
    lits = [2 * (i + 1) for i in range(p.inputs)]
    ands: list[tuple[int, int, int]] = []

    def node(a: int, b: int) -> int:
        lhs = 2 * (p.inputs + 1 + len(ands))
        ands.append((lhs, a, b))
        return lhs

    def or_(a: int, b: int) -> int:
        return node(a ^ 1, b ^ 1) ^ 1

    for op, args in p.statements:
        x = [lits[a] for a in args]
        if op == "and":
            lit = node(x[0], x[1])
        elif op == "not":
            lit = x[0] ^ 1
        elif op == "or":
            lit = or_(x[0], x[1])
        elif op == "implies":
            lit = node(x[0], x[1] ^ 1) ^ 1
        elif op in ("xor", "eq"):
            both = node(x[0], x[1])
            neither = node(x[0] ^ 1, x[1] ^ 1)
            lit = node(both ^ 1, neither ^ 1) ^ (op == "eq")
        elif op == "mux":
            lit = or_(node(x[0], x[1]), node(x[0] ^ 1, x[2]))
        else:
            both = node(x[0], x[1])
            either = node(x[0] ^ 1, x[1] ^ 1) ^ 1
            lit = or_(both, node(x[2], either))
        lits.append(lit)
    m = p.inputs + len(ands)
    with open(base + ".aag", "w", encoding="ascii") as f:
        f.write(f"aag {m} {p.inputs} 0 {len(p.outputs)} {len(ands)}\n")
        f.writelines(f"{2 * (i + 1)}\n" for i in range(p.inputs))
        f.writelines(f"{lits[o]}\n" for o in p.outputs)
        f.writelines(f"{lhs} {a} {b}\n" for lhs, a, b in ands)
    with open(base + ".statements", "w", encoding="ascii") as f:
        for k, (op, args) in enumerate(p.statements):
            words = [str(lits[p.inputs + k]), op, *[str(lits[a]) for a in args]]
            f.write(" ".join(words) + "\n")
    return {lit: v for v, lit in enumerate(lits)}


@dataclass
class Match:
    """A match as `beq match --dump_raw` reports it, in program values."""

    value: int
    op: str
    opposite: bool
    size: int
    args: tuple[int, ...]
    # A way of writing a value that is already an execution, or a `not` of
    # one, for the precedence rule; not a match by itself.
    spelling: bool = False


def reported(p: Program, matches: list[Match], policy: str = "largest") -> Match | None:
    """Return the match DLP 58 reports: largest, earliest, by name, by rank.

    A match's size is the number of statements fixing it removes, as `beq`
    reports it; `beq` reports only matches of at least two statements, and
    never an execution and its `not` as an opposite result. Other policies,
    for comparison: "earliest" (the first value, then the largest) and
    "smallest".
    """
    keys = rank_keys(p)
    best = None
    for m in matches:
        ranked = tuple(keys[a] for a in m.args)
        if policy == "largest":
            key = (-m.size, m.value, m.op, ranked)
        elif policy == "earliest":
            key = (m.value, -m.size, m.op, ranked)
        else:
            key = (m.size, m.value, m.op, ranked)
        if best is None or key < best[0]:
            best = (key, m)
    return None if best is None else best[1]


def apply_match(p: Program, m: Match) -> Program:
    """Replace the match's value with an execution of its operation."""
    q = Program(p.inputs, list(p.statements[: m.value - p.inputs]), [])
    replacement = q.add(m.op, *m.args)
    if m.opposite:
        replacement = q.add("not", replacement)
    shift = replacement - m.value
    for op, args in p.statements[m.value - p.inputs + 1 :]:
        q.add(op, *[_moved(a, m.value, replacement, shift) for a in args])
    q.outputs = [_moved(o, m.value, replacement, shift) for o in p.outputs]
    return q


def _moved(a: int, old: int, replacement: int, shift: int) -> int:
    if a == old:
        return replacement
    return a + shift if a > old else a


def _op_table(op: str, arity: int, negated: int = 0) -> int:
    """Return an operation's table, bit m for minterm m, with views negated."""
    out = 0
    for m in range(1 << arity):
        bits = [((m >> i) & 1) ^ ((negated >> i) & 1) for i in range(arity)]
        if evaluate_op(op, bits, 1):
            out |= 1 << m
    return out


def plain_argument(p: Program) -> Program | None:
    """Rewrite the first execution given a `not` that needn't be.

    An execution of a registered operation given `not y` is rewritten to
    execute a registered operation that computes the same thing from y, as
    `or(x, not y)` becomes `implies(y, x)`. This is a candidate rule, not
    DLP 58's: it makes the polarity of arguments canonical.
    """
    import itertools

    for k, (op, args) in enumerate(p.statements):
        if op not in REGISTERED:
            continue
        arity = len(args)
        negated = 0
        plain = list(args)
        for i, a in enumerate(args):
            if a >= p.inputs and p.statements[a - p.inputs][0] == "not":
                negated |= 1 << i
                plain[i] = p.statements[a - p.inputs][1][0]
        if not negated:
            continue
        target = _op_table(op, arity, negated)
        for name in sorted(REGISTERED):
            if REGISTERED[name][0] != arity:
                continue
            for perm in itertools.permutations(range(arity)):
                table = 0
                for m in range(1 << arity):
                    bits = [(m >> perm[i]) & 1 for i in range(arity)]
                    if evaluate_op(name, bits, 1):
                        table |= 1 << m
                if table == target:
                    q = Program(p.inputs, list(p.statements), list(p.outputs))
                    q.statements[k] = (
                        name,
                        tuple(plain[perm[i]] for i in range(arity)),
                    )
                    return q
    return None


# AIG nodes of each registered operation's own logic, structurally hashed.
AIG_NODES = {"or": 1, "implies": 1, "xor": 3, "eq": 3, "mux": 3, "maj": 4}


def spelling_key(
    p: Program,
    op: str,
    args: tuple[int, ...],
    keys: list[tuple],
    *,
    opposite: bool,
    order: list[str],
) -> tuple:
    """Return a spelling's precedence: lower comes first.

    Fewest negations (values given that are a `not`, and a `not` of the
    result), then fewest AIG nodes, then the declared order, then the
    values in rank order.
    """
    negations = int(opposite) + sum(
        1 for a in args if a >= p.inputs and p.statements[a - p.inputs][0] == "not"
    )
    ranked = tuple(keys[a] for a in ordered_args(op, args, keys))
    return (negations, AIG_NODES[op], order.index(op), ranked)


def precedence_match(
    p: Program, spellings: list[Match], order: list[str], *, strict: bool = False
) -> Match | None:
    """Return the first value that's written with a lower-precedence spelling.

    The value is an execution of a registered operation, or a `not` of one,
    and another execution (or a `not` of one) over earlier values computes
    it with higher precedence. Returns the highest-precedence spelling.
    With `strict`, as DLP 60 adopted it, only single executions are
    respelled, and only by single executions.
    """
    keys = rank_keys(p)
    # An opposite spelling computes the value's `not` and then the value; if
    # the program already has the value's `not`, that execution would be a
    # redundant value.
    negated = {args[0] for op, args in p.statements if op == "not"}
    negations = {p.inputs + k for k, (op, _) in enumerate(p.statements) if op == "not"}
    by_value: dict[int, list[Match]] = {}
    for m in spellings:
        if m.opposite and (strict or m.value in negated or m.value in negations):
            continue
        by_value.setdefault(m.value, []).append(m)
    for v in sorted(by_value):
        op, args = p.statements[v - p.inputs]
        opposite = op == "not"
        # DLP 60 respells only single executions, never a `not` of one.
        if opposite and strict:
            continue
        if opposite:
            op, args = p.statements[args[0] - p.inputs]
        current = spelling_key(p, op, args, keys, opposite=opposite, order=order)
        best = min(
            by_value[v],
            key=lambda m: spelling_key(
                p, m.op, m.args, keys, opposite=m.opposite, order=order
            ),
        )
        if (
            spelling_key(
                p, best.op, best.args, keys, opposite=best.opposite, order=order
            )
            < current
        ):
            return best
    return None


@dataclass
class Outcome:
    """What fixing one program did."""

    final: Program
    rounds: int
    redundant_fixes: int
    match_fixes: int
    status: str
    sizes: list[int] = field(default_factory=list)
    precedence_fixes: int = 0


def fix(
    p: Program,
    find_matches: Callable[[Program], list[Match]],
    max_rounds: int = 400,
    policy: str = "largest",
    seconds: float = 30,
    *,
    plain_arguments: bool = False,
    precedence: list[str] | None = None,
    strict: bool = False,
    observe: Callable[[Program, Program, str], None] | None = None,
) -> Outcome:
    """Apply the reported fix until the program compiles.

    With `precedence`, a declared order of the registered operations, a
    value written with a lower-precedence spelling than one over earlier
    values is an error too, after every other match. Gives up with the
    status "timeout" after `seconds`, checks included. With `strict`, every
    fix makes the program smaller or, for the precedence rule, keeps its
    size: a match has to remove more statements than its fix adds.
    """
    deadline = time.monotonic() + seconds
    p = canonical(p)
    seen = {text(p)}
    redundant_fixes = match_fixes = precedence_fixes = 0
    sizes = [len(p.statements)]

    def outcome(status: str, rounds: int) -> Outcome:
        return Outcome(
            p, rounds, redundant_fixes, match_fixes, status, sizes, precedence_fixes
        )

    for rounds in range(max_rounds):
        if time.monotonic() > deadline:
            return outcome("timeout", rounds)
        before = p
        kind = ""
        found = first_redundant(p)
        if found is not None:
            value, equals, opposite = found
            if isinstance(equals, str):
                q = substitute_constant(p, value, value=equals == "true")
                if q is None:
                    return outcome("constant output", rounds)
                p = canonical(q)
                kind = "constant"
            elif opposite:
                q = Program(p.inputs, list(p.statements), list(p.outputs))
                q.statements[value - p.inputs] = ("not", (equals,))
                p = canonical(q)
                kind = "opposite value"
            else:
                p = canonical(substitute(p, value, equals))
                kind = "redundant"
            redundant_fixes += 1
        elif plain_arguments and (q := plain_argument(p)) is not None:
            p = canonical(q)
            match_fixes += 1
        else:
            found_matches = find_matches(p)
            regular = [
                x
                for x in found_matches
                if not x.spelling and (not strict or x.size >= 2 + x.opposite)
            ]
            m = reported(p, regular, policy)
            if m is not None and precedence:
                # The fix uses the highest-precedence spelling among the
                # matches of the same value and size.
                keys = rank_keys(p)
                m = min(
                    (x for x in regular if x.value == m.value and x.size == m.size),
                    key=lambda x: spelling_key(
                        p, x.op, x.args, keys, opposite=x.opposite, order=precedence
                    ),
                )
            if m is not None:
                p = canonical(apply_match(p, m))
                match_fixes += 1
                kind = "opposite match" if m.opposite else "match"
            else:
                spelled = [x for x in found_matches if x.spelling]
                m = (
                    precedence_match(p, spelled, precedence, strict=strict)
                    if precedence
                    else None
                )
                if m is None:
                    return outcome("ok", rounds)
                p = canonical(apply_match(p, m))
                precedence_fixes += 1
                kind = "spelling"
        if observe is not None:
            observe(before, p, kind)
        sizes.append(len(p.statements))
        t = text(p)
        if t in seen:
            return outcome("cycle", rounds + 1)
        seen.add(t)
    return outcome("rounds", max_rounds)


# Generating families of programs that compute the same functions.


def base_program(rng: random.Random, inputs: int, statements: int) -> Program:
    """Return a random program of `and`, `not`, and registered operations.

    Statements whose value is constant or one the program already has are
    rejected. A value can still be the opposite of an earlier one, which is
    a redundant value that fixing removes.
    """
    p = Program(inputs)
    t = tables(p)
    mask = (1 << (1 << inputs)) - 1
    seen = set(t) | {0, mask}
    weights = {
        "and": 30,
        "not": 8,
        "or": 20,
        "xor": 6,
        "eq": 6,
        "implies": 6,
        "mux": 10,
        "maj": 4,
    }
    names = list(weights)
    while len(p.statements) < statements:
        op = rng.choices(names, [weights[n] for n in names])[0]
        arity = OPS[op][0]
        values = inputs + len(p.statements)
        # Mostly recent values, so the program is a deep dataflow.
        args: set[int] = set()
        while len(args) < arity:
            args.add(values - 1 - min(int(rng.expovariate(1 / 12)), values - 1))
        ordered = rng.sample(sorted(args), arity)
        table = evaluate_op(op, [t[a] for a in ordered], mask)
        if table in seen:
            continue
        seen.add(table)
        t.append(table)
        p.add(op, *ordered)
    used = {a for _, args in p.statements for a in args}
    sinks = [v for v in range(inputs, inputs + statements) if v not in used]
    p.outputs = sinks[-4:] or [inputs + statements - 1]
    return p


class Rewriter:
    """Writes a program again, statement by statement, in other ways."""

    def __init__(self, base: Program, rng: random.Random, kinds: set[str]) -> None:
        """Rewrite `base` with the given kinds of rewrites."""
        self.base = base
        self.rng = rng
        self.kinds = kinds
        self.out = Program(base.inputs)
        self.nots: dict[int, int] = {}
        self.map: dict[int, int] = {i: i for i in range(base.inputs)}
        self.uses: dict[int, int] = {}
        for _, args in base.statements:
            for a in args:
                self.uses[a] = self.uses.get(a, 0) + 1

    def not_(self, a: int) -> int:
        """Return the `not` of a value, computing it once."""
        if a not in self.nots:
            self.nots[a] = self.out.add("not", a)
        return self.nots[a]

    def and_(self, a: int, b: int) -> int:
        """Return a new `and` of two values."""
        return self.out.add("and", a, b)

    def or_(self, a: int, b: int) -> int:
        """Return `or` written out with `and` and `not`."""
        return self.not_(self.and_(self.not_(a), self.not_(b)))

    def expand(self, op: str, x: list[int]) -> int:
        """Write a registered operation out with `and` and `not`."""
        r = self.rng.random()
        if op == "or":
            return self.or_(x[0], x[1])
        if op == "implies":
            return self.not_(self.and_(x[0], self.not_(x[1])))
        if op in ("xor", "eq"):
            if r < 0.5:
                both = self.and_(x[0], x[1])
                neither = self.and_(self.not_(x[0]), self.not_(x[1]))
                if op == "eq":
                    return self.or_(both, neither)
                return self.and_(self.not_(both), self.not_(neither))
            one = self.and_(x[0], self.not_(x[1]))
            other = self.and_(self.not_(x[0]), x[1])
            xor = self.or_(one, other)
            return self.not_(xor) if op == "eq" else xor
        if op == "mux":
            if r < 0.5:
                return self.or_(self.and_(x[0], x[1]), self.and_(self.not_(x[0]), x[2]))
            return self.out.add(
                "or", self.and_(x[0], x[1]), self.and_(self.not_(x[0]), x[2])
            )
        # maj
        if r < 0.5:
            either = self.or_(x[0], x[1])
            return self.or_(self.and_(x[0], x[1]), self.and_(x[2], either))
        ab = self.and_(x[0], x[1])
        ac = self.and_(x[0], x[2])
        bc = self.and_(x[1], x[2])
        return self.or_(self.or_(ab, ac), bc)

    def statement(self, op: str, args: tuple[int, ...]) -> int:
        """Write one statement of the base program, maybe another way."""
        x = [self.map[a] for a in args]
        k = self.kinds
        p = self.rng.random
        if op in REGISTERED and "expand" in k and p() < 0.6:
            return self.expand(op, x)
        if op == "and" and "demorgan" in k and p() < 0.4:
            return self.not_(self.out.add("or", self.not_(x[0]), self.not_(x[1])))
        if op == "and" and "reassociate" in k and p() < 0.6:
            inner = (
                self.base.statements[args[0] - self.base.inputs]
                if args[0] >= self.base.inputs
                else None
            )
            if inner and inner[0] == "and" and self.uses.get(args[0], 0) == 1:
                a, b = (self.map[y] for y in inner[1])
                return self.and_(a, self.and_(b, x[1]))
        if (
            op == "and"
            and "distribute" in k
            and p() < 0.6
            and args[1] >= self.base.inputs
        ):
            inner = self.base.statements[args[1] - self.base.inputs]
            if inner[0] == "or":
                b, c = (self.map[y] for y in inner[1])
                return self.out.add("or", self.and_(x[0], b), self.and_(x[0], c))
        if op == "not":
            return self.not_(x[0])
        return self.out.add(op, *x)

    def run(self) -> Program:
        """Return the rewritten program."""
        for k, (op, args) in enumerate(self.base.statements):
            v = self.base.inputs + k
            self.map[v] = self.statement(op, args)
            if "duplicate" in self.kinds and self.rng.random() < 0.15:
                # Compute the value a second time; later statements read
                # either copy.
                again = self.statement(op, args)
                if self.rng.random() < 0.5:
                    self.map[v] = again
        self.out.outputs = [self.map[o] for o in self.base.outputs]
        return self.out
