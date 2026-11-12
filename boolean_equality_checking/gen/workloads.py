"""Workload families for equality checking.

Each family returns a Builder whose planted pairs are equal by construction.
`value_operation` imitates Define value operations: statements executing `and`,
`not`, and standard-library compositions on comparisons and earlier values,
with each composition available in several equivalent ways of writing it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aig_builder import Builder

if TYPE_CHECKING:
    import random

FALSE = 0
TRUE = 1


def and_c(b: Builder, x: int, y: int) -> int:
    """Return `x and y`, folding constants, for building cofactors."""
    if FALSE in (x, y) or x == y ^ 1:
        return FALSE
    if x == TRUE:
        return y
    if y == TRUE or x == y:
        return x
    return b.and2(x, y)


def or_c(b: Builder, x: int, y: int) -> int:
    """Return `x or y`, folding constants."""
    return and_c(b, x ^ 1, y ^ 1) ^ 1


# Ways of writing each standard-library composition. Every variant of an
# operation computes the same function of its arguments.
Impl = Callable[[Builder, Sequence[int]], int]


def _xor_variants() -> list[Impl]:
    return [
        lambda b, a: or_c(b, and_c(b, a[0], a[1] ^ 1), and_c(b, a[0] ^ 1, a[1])),
        lambda b, a: and_c(b, or_c(b, a[0], a[1]), and_c(b, a[0], a[1]) ^ 1),
        lambda b, a: or_c(b, and_c(b, a[0], a[1]), and_c(b, a[0] ^ 1, a[1] ^ 1)) ^ 1,
        lambda b, a: and_c(b, or_c(b, a[0], a[1]), or_c(b, a[0] ^ 1, a[1] ^ 1)),
    ]


def _mux_variants() -> list[Impl]:
    def via_xor(b: Builder, a: Sequence[int]) -> int:
        inner = or_c(b, and_c(b, a[1], a[2] ^ 1), and_c(b, a[1] ^ 1, a[2]))
        sel = and_c(b, a[0], inner)
        return or_c(b, and_c(b, a[2], sel ^ 1), and_c(b, a[2] ^ 1, sel))

    return [
        lambda b, a: or_c(b, and_c(b, a[0], a[1]), and_c(b, a[0] ^ 1, a[2])),
        lambda b, a: and_c(b, or_c(b, a[0] ^ 1, a[1]), or_c(b, a[0], a[2])),
        lambda b, a: or_c(
            b,
            or_c(b, and_c(b, a[0], a[1]), and_c(b, a[0] ^ 1, a[2])),
            and_c(b, a[1], a[2]),
        ),
        via_xor,
    ]


def _maj_variants() -> list[Impl]:
    return [
        lambda b, a: or_c(b, and_c(b, a[0], a[1]), and_c(b, a[2], or_c(b, a[0], a[1]))),
        lambda b, a: or_c(
            b, or_c(b, and_c(b, a[0], a[1]), and_c(b, a[0], a[2])), and_c(b, a[1], a[2])
        ),
        lambda b, a: and_c(b, or_c(b, a[0], a[1]), or_c(b, a[2], and_c(b, a[0], a[1]))),
        lambda b, a: and_c(
            b, and_c(b, or_c(b, a[0], a[1]), or_c(b, a[0], a[2])), or_c(b, a[1], a[2])
        ),
    ]


def _negated(f: Impl) -> Impl:
    return lambda b, a: f(b, a) ^ 1


OPS: dict[str, tuple[int, list[Impl]]] = {
    "and": (2, [lambda b, a: and_c(b, a[0], a[1]), lambda b, a: and_c(b, a[1], a[0])]),
    "or": (2, [lambda b, a: or_c(b, a[0], a[1]), lambda b, a: or_c(b, a[1], a[0])]),
    "xor": (2, _xor_variants()),
    "eq": (2, [_negated(f) for f in _xor_variants()]),
    "implies": (
        2,
        [
            lambda b, a: or_c(b, a[0] ^ 1, a[1]),
            lambda b, a: or_c(b, a[0] ^ 1, and_c(b, a[0], a[1])),
        ],
    ),
    "mux": (3, _mux_variants()),
    "maj": (3, _maj_variants()),
    "and3": (
        3,
        [
            lambda b, a: and_c(b, and_c(b, a[0], a[1]), a[2]),
            lambda b, a: and_c(b, a[0], and_c(b, a[1], a[2])),
            lambda b, a: and_c(b, and_c(b, a[0], a[2]), a[1]),
        ],
    ),
    "or3": (
        3,
        [
            lambda b, a: or_c(b, or_c(b, a[0], a[1]), a[2]),
            lambda b, a: or_c(b, a[0], or_c(b, a[1], a[2])),
            lambda b, a: or_c(b, or_c(b, a[0], a[2]), a[1]),
        ],
    ),
}

# How often realistic code uses each operation, by weight.
OP_WEIGHTS = {
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
class Value:
    """A value of the high-level program: an input, or an operation on values."""

    lit: int
    op: str = ""
    args: tuple[int, ...] = ()  # indices of argument values
    negate: tuple[bool, ...] = ()  # whether each argument is negated first
    variant: int = 0
    input_index: int = -1


class Program:
    """A value operation's statements, at the level of standard-library calls."""

    def __init__(self, num_inputs: int, rng: random.Random, *, legal: bool) -> None:
        """Start a program reading num_inputs boolean inputs.

        When legal is set, statements whose value looks redundant on random
        simulation (constant, equal to an input, or equal to an earlier value)
        are rejected, so the only redundant values are the planted ones.
        """
        self.b = Builder(num_inputs)
        self.rng = rng
        self.values = [Value(self.b.input(i), input_index=i) for i in range(num_inputs)]
        self.used = [False] * num_inputs
        self.constants: list[int] = []
        self.legal = legal
        self.signatures: set[int] = set()
        if legal:
            self.b.enable_simulation(256, rng.getrandbits(32))
            self.signatures.add(0)
            self.signatures.add(self.b.sim_mask)
            for value in self.values:
                self.signatures.add(self.b.sim(value.lit))

    def try_apply(
        self, op: str, args: Sequence[int], negate: Sequence[bool], variant: int
    ) -> int | None:
        """Apply op unless the program must be legal and its value is redundant."""
        before = len(self.b.fanin0)
        was_used = [self.used[a] for a in args if a < len(self.used)]
        index = self.apply(op, args, negate, variant)
        if not self.legal:
            return index
        signature = self.b.sim(self.values[index].lit)
        if signature in self.signatures:
            self.values.pop()
            self.b.truncate(before)
            for a, used in zip(
                [a for a in args if a < len(self.used)], was_used, strict=True
            ):
                self.used[a] = used
            return None
        self.signatures.add(signature)
        return index

    def apply(
        self, op: str, args: Sequence[int], negate: Sequence[bool], variant: int
    ) -> int:
        """Append a call of op on the given values and return the new value's index."""
        _, variants = OPS[op]
        lits = [self.values[a].lit ^ int(n) for a, n in zip(args, negate, strict=True)]
        lit = variants[variant](self.b, lits)
        for a in args:
            if a < len(self.used):
                self.used[a] = True
        self.values.append(Value(lit, op, tuple(args), tuple(negate), variant))
        return len(self.values) - 1

    def rebuild(
        self,
        index: int,
        choose: Callable[[str, int], int],
        subst: dict[int, int],
        memo: dict[int, int],
    ) -> int:
        """Re-implement value `index` and its cone, returning a literal.

        `choose(op, variant)` picks the variant used for each call, and `subst`
        replaces inputs (by value index) with literals, such as constants.
        """
        stack = [index]
        while stack:
            v = stack[-1]
            if v in memo:
                stack.pop()
                continue
            value = self.values[v]
            if not value.op:
                memo[v] = subst.get(v, value.lit)
                stack.pop()
                continue
            missing = [a for a in value.args if a not in memo]
            if missing:
                stack.extend(missing)
                continue
            _, variants = OPS[value.op]
            lits = [
                memo[a] ^ int(n) for a, n in zip(value.args, value.negate, strict=True)
            ]
            memo[v] = variants[choose(value.op, value.variant)](self.b, lits)
            stack.pop()
        return memo[index]

    def support(self, index: int) -> set[int]:
        """Return the input value indices in the cone of value `index`."""
        seen: set[int] = set()
        out: set[int] = set()
        stack = [index]
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            value = self.values[v]
            if not value.op:
                out.add(v)
            stack.extend(value.args)
        return out

    def depth(self, index: int, memo: dict[int, int]) -> int:
        """Return the number of calls on the longest path to an input."""
        stack = [index]
        while stack:
            v = stack[-1]
            if v in memo:
                stack.pop()
                continue
            value = self.values[v]
            if not value.op:
                memo[v] = 0
                stack.pop()
                continue
            missing = [a for a in value.args if a not in memo]
            if missing:
                stack.extend(missing)
                continue
            memo[v] = 1 + max(memo[a] for a in value.args)
            stack.pop()
        return memo[index]


def _pick_operand(p: Program, window: int, input_rate: float) -> int:
    rng = p.rng
    num_inputs = p.b.num_inputs
    unused = [i for i in range(num_inputs) if not p.used[i]]
    if len(p.values) == num_inputs or rng.random() < input_rate:
        # Comparisons are read near where they are computed, so prefer one not
        # used yet, the way straight-line code reads new inputs as it goes.
        if unused and rng.random() < 0.7:
            return unused[0]
        return rng.randrange(num_inputs)
    low = max(num_inputs, len(p.values) - window)
    return rng.randrange(low, len(p.values))


def value_operation(
    rng: random.Random,
    num_inputs: int,
    num_statements: int,
    plant_rate: float = 0.08,
    window: int = 8,
    input_rate: float = 0.35,
    *,
    legal: bool = True,
    near_miss_rate: float = 0.0,
    cube_size: int = 12,
) -> Builder:
    """Return a value operation like realistic code, with planted equalities.

    Statements call `and`, `or`, and other standard compositions on recent
    values and on comparisons (the inputs). With probability plant_rate a step
    instead writes an existing value a second way: one call rewritten, a whole
    cone rewritten, a case split on an input, an absorption that gives back a
    value or an input, or a contradiction that is always false.

    With probability near_miss_rate a step adds a near miss instead: `v or c`
    for an earlier value v and an `and` c of cube_size inputs, which differs
    from v on at most a 2^-cube_size fraction of the input combinations.
    Simulation would wrongly reject it as redundant, so it isn't checked.
    """
    p = Program(num_inputs, rng, legal=legal)
    names = list(OP_WEIGHTS)
    weights = [OP_WEIGHTS[n] for n in names]
    statements = 0
    attempts = 0
    # Few inputs have few distinct functions, so give up when legal statements
    # run out.
    while statements < num_statements and attempts < 50 * num_statements:
        attempts += 1
        composite = len(p.values) - num_inputs
        if composite > 4 and rng.random() < plant_rate:
            statements += _plant(p, window)
            continue
        if composite > 4 and num_inputs >= cube_size and rng.random() < near_miss_rate:
            target = rng.randrange(num_inputs, len(p.values))
            cube = TRUE
            for i in rng.sample(range(num_inputs), cube_size):
                cube = and_c(p.b, cube, p.b.input(i) ^ int(rng.random() < 0.5))
            lit = or_c(p.b, p.values[target].lit, cube)
            # Recorded as a leaf, so rebuilding a cone that reads it keeps it.
            p.values.append(Value(lit))
            statements += 1
            continue
        op = rng.choices(names, weights)[0]
        arity, variants = OPS[op]
        args: list[int] = []
        while len(args) < arity:
            a = _pick_operand(p, window, input_rate)
            if a not in args:
                args.append(a)
        negate = [rng.random() < 0.25 for _ in args]
        if p.try_apply(op, args, negate, rng.randrange(len(variants))) is not None:
            statements += 1
    sinks = _sinks(p)
    p.b.outputs = [p.values[v].lit for v in sinks] + p.constants
    return p.b.reorder_first_need(p.b.outputs)


def _sinks(p: Program) -> list[int]:
    used = [False] * len(p.values)
    for value in p.values:
        for a in value.args:
            used[a] = True
    return [v for v in range(p.b.num_inputs, len(p.values)) if not used[v]]


def _plant(p: Program, window: int) -> int:
    """Write one existing value a second way; return the statements it took."""
    rng = p.rng
    num_inputs = p.b.num_inputs
    low = max(num_inputs, len(p.values) - 4 * window)
    target = rng.randrange(low, len(p.values))
    value = p.values[target]
    kind = rng.choices(
        [
            "shallow",
            "deep",
            "shannon",
            "absorb",
            "absorb_input",
            "contradiction",
            "duplicate",
        ],
        [3, 4, 2, 1, 1, 1, 1],
    )[0]
    before = len(p.b.fanin0)

    def other_variant(op: str, variant: int) -> int:
        count = len(OPS[op][1])
        return rng.randrange(count) if count > 1 else variant

    if kind == "duplicate":
        lit = p.values[p.apply(value.op, value.args, value.negate, value.variant)].lit
        p.b.plant(value.lit, lit, "duplicate")
    elif kind == "shallow":
        count = len(OPS[value.op][1])
        variant = (
            (value.variant + 1 + rng.randrange(count - 1)) % count
            if count > 1
            else value.variant
        )
        lit = p.values[p.apply(value.op, value.args, value.negate, variant)].lit
        p.b.plant(value.lit, lit, "shallow")
    elif kind == "deep":
        lit = p.rebuild(target, other_variant, {}, {})
        p.values.append(Value(lit, value.op, value.args, value.negate, value.variant))
        p.b.plant(value.lit, lit, "deep")
    elif kind == "shannon":
        support = sorted(p.support(target))
        x = rng.choice(support)
        x_lit = p.values[x].lit
        hi = p.rebuild(target, other_variant, {x: TRUE}, {})
        lo = p.rebuild(target, other_variant, {x: FALSE}, {})
        lit = or_c(p.b, and_c(p.b, x_lit, hi), and_c(p.b, x_lit ^ 1, lo))
        p.values.append(Value(lit, value.op, value.args, value.negate, value.variant))
        p.b.plant(value.lit, lit, "shannon")
    elif kind == "absorb":
        # target and (copy or other): the copy is a rewrite of the cone, so
        # the absorption is only visible functionally.
        copy = p.rebuild(target, other_variant, {}, {})
        other = p.values[_pick_operand(p, window, 0.3)].lit
        lit = and_c(p.b, value.lit, or_c(p.b, copy, other))
        p.values.append(Value(lit, value.op, value.args, value.negate, value.variant))
        p.b.plant(value.lit, lit, "absorb")
    elif kind == "absorb_input":
        x = rng.choice(sorted(p.support(target)))
        x_lit = p.values[x].lit
        lit = and_c(p.b, x_lit, or_c(p.b, x_lit, value.lit))
        # It is recorded as `x and x`, which rebuilds to x itself.
        p.values.append(Value(lit, "and", (x, x), (False, False), 0))
        p.b.plant(x_lit, lit, "absorb_input")
    else:
        copy = p.rebuild(target, other_variant, {}, {})
        lit = and_c(p.b, value.lit, copy ^ 1)
        p.b.plant(FALSE, lit, "contradiction")
        # A constant is never used again, so it is not added as a value.
        p.constants.append(lit)
    return max(1, (len(p.b.fanin0) - before) // 2)


def ripple_add(
    b: Builder, x: Sequence[int], y: Sequence[int], carry: int = FALSE
) -> list[int]:
    """Return the sum bits of x + y + carry, least significant first."""
    xor = _xor_variants()[0]
    maj = _maj_variants()[0]
    out = []
    for xi, yi in zip(x, y, strict=True):
        out.append(xor(b, [xor(b, [xi, yi]), carry]))
        carry = maj(b, [xi, yi, carry])
    out.append(carry)
    return out


def kogge_stone_add(b: Builder, x: Sequence[int], y: Sequence[int]) -> list[int]:
    """Return the sum bits of x + y with a parallel-prefix carry network."""
    xor = _xor_variants()[1]
    n = len(x)
    g = [and_c(b, xi, yi) for xi, yi in zip(x, y, strict=True)]
    p = [xor(b, [xi, yi]) for xi, yi in zip(x, y, strict=True)]
    gg, pp = g[:], p[:]
    dist = 1
    while dist < n:
        ng, np_ = gg[:], pp[:]
        for i in range(dist, n):
            ng[i] = or_c(b, gg[i], and_c(b, pp[i], gg[i - dist]))
            np_[i] = and_c(b, pp[i], pp[i - dist])
        gg, pp = ng, np_
        dist *= 2
    out = [p[0]]
    out.extend(xor(b, [p[i], gg[i - 1]]) for i in range(1, n))
    out.append(gg[n - 1])
    return out


def less_than_ripple(b: Builder, x: Sequence[int], y: Sequence[int]) -> int:
    """Return x < y, scanning from the least significant bit."""
    lt = FALSE
    for xi, yi in zip(x, y, strict=True):
        lt = or_c(
            b,
            and_c(b, xi ^ 1, yi),
            and_c(b, or_c(b, and_c(b, xi, yi), and_c(b, xi ^ 1, yi ^ 1)), lt),
        )
    return lt


def less_than_msb_first(b: Builder, x: Sequence[int], y: Sequence[int]) -> int:
    """Return x < y as an `or` over each bit where the higher bits are equal."""
    terms = []
    prefix_equal = TRUE
    for xi, yi in reversed(list(zip(x, y, strict=True))):
        terms.append(and_c(b, prefix_equal, and_c(b, xi ^ 1, yi)))
        eq = or_c(b, and_c(b, xi, yi), and_c(b, xi ^ 1, yi ^ 1))
        prefix_equal = and_c(b, prefix_equal, eq)
    result = FALSE
    for t in terms:
        result = or_c(b, result, t)
    return result


def comparators(rng: random.Random, bits: int, count: int) -> Builder:
    """Return `count` comparisons x < y and sums x + y, each written two ways.

    The operands are chosen from a shared pool of inputs, like comparisons of
    fields that a program reads.
    """
    pool = 4 * bits
    b = Builder(pool)
    for _ in range(count):
        chosen = rng.sample(range(pool), 2 * bits)
        x = [b.input(i) for i in chosen[:bits]]
        y = [b.input(i) for i in chosen[bits:]]
        b.plant(less_than_ripple(b, x, y), less_than_msb_first(b, x, y), "less_than")
        for s1, s2 in zip(ripple_add(b, x, y), kogge_stone_add(b, x, y), strict=True):
            b.plant(s1, s2, "adder")
    b.outputs = [p.a for p in b.planted] + [p.b for p in b.planted]
    return b.reorder_first_need(b.outputs)


def array_multiply(b: Builder, x: Sequence[int], y: Sequence[int]) -> list[int]:
    """Return the product bits of x * y by adding shifted rows in order."""
    n = len(x)
    acc = [and_c(b, x[0], yj) for yj in y] + [FALSE] * n
    for i in range(1, n):
        row = [and_c(b, x[i], yj) for yj in y]
        s = ripple_add(b, acc[i : i + n], row)
        acc[i : i + n + 1] = s
    return acc[: 2 * n]


def multipliers(bits: int, kind: str) -> Builder:
    """Return two multipliers whose product bits are planted as equal.

    `commuted` multiplies y * x with the same array design, the classic hard
    case for SAT. `kogge` uses parallel-prefix adders for the second one.
    """
    b = Builder(2 * bits)
    x = [b.input(i) for i in range(bits)]
    y = [b.input(bits + i) for i in range(bits)]
    first = array_multiply(b, x, y)
    if kind == "commuted":
        second = array_multiply(b, y, x)
    else:
        n = bits
        acc = [and_c(b, y[0], xj) for xj in x] + [FALSE] * n
        for i in range(1, n):
            row = [and_c(b, y[i], xj) for xj in x]
            s = kogge_stone_add(b, acc[i : i + n], row)
            acc[i : i + n + 1] = s
        second = acc[: 2 * n]
    for k, (s1, s2) in enumerate(zip(first, second, strict=True)):
        b.plant(s1, s2, f"product_bit_{k}" if k in (bits - 1, bits) else "product_bit")
    b.outputs = first + second
    return b.reorder_first_need(b.outputs)


def parity(rng: random.Random, num_inputs: int, copies: int) -> Builder:
    """Return parity of the inputs written as chains in different orders.

    The first is a chain in input order, then a balanced tree, then chains in
    random orders, each `xor` written in a random one of its four ways.
    """
    b = Builder(num_inputs)
    variants = _xor_variants()
    lits = [b.input(i) for i in range(num_inputs)]

    def chain(order: Sequence[int]) -> int:
        acc = order[0]
        for lit in order[1:]:
            acc = rng.choice(variants)(b, [acc, lit])
        return acc

    def tree(items: Sequence[int]) -> int:
        if len(items) == 1:
            return items[0]
        mid = len(items) // 2
        return rng.choice(variants)(b, [tree(items[:mid]), tree(items[mid:])])

    first = chain(lits)
    others = [tree(lits)]
    for _ in range(copies - 1):
        order = lits[:]
        rng.shuffle(order)
        others.append(chain(order))
    for other in others:
        b.plant(first, other, "parity")
    b.outputs = [first, *others]
    return b.reorder_first_need(b.outputs)


def _popcount_chain(b: Builder, x: Sequence[int], width: int) -> list[int]:
    count = [FALSE] * width
    for xi in x:
        count = ripple_add(b, count, [xi] + [FALSE] * (width - 1))[:width]
    return count


def _popcount_tree(b: Builder, x: Sequence[int], width: int) -> list[int]:
    def go(items: Sequence[int]) -> list[int]:
        if len(items) == 1:
            return [items[0]] + [FALSE] * (width - 1)
        mid = len(items) // 2
        return kogge_stone_add(b, go(items[:mid]), go(items[mid:]))[:width]

    return go(x)


def hidden_weighted_bit(num_inputs: int) -> Builder:
    """Return the hidden weighted bit function written two ways.

    hwb(x) is x[k - 1] where k is the number of true inputs (false when k = 0).
    Every OBDD for it is exponentially large under every input order.
    """
    b = Builder(num_inputs)
    x = [b.input(i) for i in range(num_inputs)]
    width = num_inputs.bit_length()
    count_a = _popcount_chain(b, x, width)
    count_b = _popcount_tree(b, x, width)

    # First way: a multiplexer tree on the count bits.
    table = [FALSE] + x + [FALSE] * ((1 << width) - num_inputs - 1)
    level = table
    for bit in range(width):
        level = [
            or_c(
                b,
                and_c(b, count_a[bit], level[2 * i + 1]),
                and_c(b, count_a[bit] ^ 1, level[2 * i]),
            )
            for i in range(len(level) // 2)
        ]
    first = level[0]

    # Second way: an `or` over each k of (count == k and x[k - 1]).
    second = FALSE
    for k in range(1, num_inputs + 1):
        match = TRUE
        for bit in range(width):
            match = and_c(b, match, count_b[bit] ^ (0 if (k >> bit) & 1 else 1))
        second = or_c(b, second, and_c(b, match, x[k - 1]))
    b.plant(first, second, "hwb")
    b.outputs = [first, second]
    return b.reorder_first_need(b.outputs)


def tangle(
    rng: random.Random, num_inputs: int, num_statements: int, plant_rate: float = 0.05
) -> Builder:
    """Return a value operation whose statements read values from anywhere.

    With no locality, many values stay live across the whole operation, so its
    width is large.
    """
    return value_operation(
        rng, num_inputs, num_statements, plant_rate, window=10**9, input_rate=0.2
    )


@dataclass
class Template:
    """One value operation, written several equivalent ways, ready to inline.

    Each way of writing it is a pair of fanin arrays over local literals (node
    0 false, nodes 1..num_inputs the inputs) plus its output literals.
    """

    num_inputs: int
    ways: list[tuple[list[int], list[int], list[int]]]


def make_template(
    rng: random.Random, num_inputs: int, num_statements: int, num_ways: int
) -> Template:
    """Return a legal value operation and num_ways equivalent ways to write it."""
    p = Program(num_inputs, rng, legal=True)
    names = list(OP_WEIGHTS)
    weights = [OP_WEIGHTS[n] for n in names]
    statements = 0
    attempts = 0
    while statements < num_statements and attempts < 50 * num_statements:
        attempts += 1
        op = rng.choices(names, weights)[0]
        arity, variants = OPS[op]
        args: list[int] = []
        while len(args) < arity:
            a = _pick_operand(p, 6, 0.4)
            if a not in args:
                args.append(a)
        negate = [rng.random() < 0.25 for _ in args]
        if p.try_apply(op, args, negate, rng.randrange(len(variants))) is not None:
            statements += 1
    # Value operations write one to three views.
    sinks = _sinks(p)[-rng.randint(1, 3) :]
    ways = []
    for way in range(num_ways):
        if way == 0:
            b = p.b
            outputs = [p.values[v].lit for v in sinks]
        else:
            q = Program(num_inputs, rng, legal=False)
            q.values = p.values
            memo: dict[int, int] = {}
            outputs = [
                q.rebuild(v, lambda op, _v: rng.randrange(len(OPS[op][1])), {}, memo)
                for v in sinks
            ]
            b = q.b
        ordered = Builder(
            num_inputs, b.fanin0, b.fanin1, outputs=outputs
        ).reorder_first_need(outputs, keep_unneeded=False)
        ways.append((list(ordered.fanin0), list(ordered.fanin1), ordered.outputs))
    return Template(num_inputs, ways)


def make_library(rng: random.Random, num_templates: int) -> list[Template]:
    """Return the library of value operations that programs execute."""
    return [
        make_template(rng, rng.randint(3, 10), rng.randint(6, 40), 3)
        for _ in range(num_templates)
    ]


def library_files(rng: random.Random, num_templates: int) -> list[Builder]:
    """Return each library operation with its three ways of writing it side by side."""
    out = []
    for t in make_library(rng, num_templates):
        b = Builder(t.num_inputs)
        first: list[int] = []
        for way, (fanin0, fanin1, outputs) in enumerate(t.ways):
            local = list(range(0, 2 * (1 + t.num_inputs), 2)) + [0] * len(fanin0)
            for j, (f0, f1) in enumerate(zip(fanin0, fanin1, strict=True)):
                local[1 + t.num_inputs + j] = b.and2(
                    local[f0 >> 1] ^ (f0 & 1), local[f1 >> 1] ^ (f1 & 1)
                )
            outs = [local[o >> 1] ^ (o & 1) for o in outputs]
            if way == 0:
                first = outs
            else:
                for o_first, o in zip(first, outs, strict=True):
                    b.plant(o_first, o, "rewrite")
            b.outputs.extend(outs)
        out.append(b)
    return out


def program(
    rng: random.Random,
    num_templates: int,
    num_calls: int,
    rewrite_rate: float = 0.02,
    repeat_rate: float = 0.02,
    fresh_rate: float = 0.3,
    window: int = 64,
    *,
    legal: bool = True,
    region_calls: int = 0,
) -> Builder:
    """Return a whole program with every value operation call inlined.

    Calls execute templates (value operations from a library, each used many
    times) on recent values and fresh comparisons. With probability
    rewrite_rate a call repeats an earlier call's operation and values, written
    a different way, and with probability repeat_rate it repeats one exactly.
    Both are planted. The number of inputs grows with the program, the way
    comparisons do.

    With region_calls set, calls come in regions of that many calls, like the
    actions of a program: a call only reads values computed in its own region,
    and half of its fresh inputs are comparisons already read elsewhere.
    """
    library = make_library(rng, num_templates)
    # Zipf-like popularity, so a few operations are executed most of the time.
    popularity = [1.0 / (k + 1) for k in range(num_templates)]
    calls: list[tuple[int, list[int], list[int]]] = []
    pool: list[int] = []
    # Inputs are numbered up front; generate the call structure first.
    plan: list[tuple[int, list[int | tuple[str, int]], int, int]] = []
    num_inputs = 0
    num_values = 0
    region_start = 0
    for call in range(num_calls):
        if region_calls and call % region_calls == 0:
            region_start = num_values
        r = rng.random()
        if plan and r < rewrite_rate + repeat_rate:
            earlier = rng.randrange(len(plan))
            t, args, way, _ = plan[earlier]
            new_way = way if r < repeat_rate else (way + rng.randrange(1, 3)) % 3
            plan.append((t, args, new_way, earlier))
            num_values += len(library[t].ways[0][2])
            continue
        t = rng.choices(range(num_templates), popularity)[0]
        args: list[int | tuple[str, int]] = []
        while len(args) < library[t].num_inputs:
            if num_values == region_start or rng.random() < fresh_rate:
                if region_calls and num_inputs > 0 and rng.random() < 0.5:
                    args.append(("in", rng.randrange(num_inputs)))
                else:
                    args.append(("in", num_inputs))
                    num_inputs += 1
            else:
                args.append(
                    (
                        "value",
                        rng.randrange(
                            max(region_start, num_values - window), num_values
                        ),
                    )
                )
        plan.append((t, args, 0, -1))
        num_values += len(library[t].ways[0][2])
    b = Builder(num_inputs)
    del calls, pool
    if legal:
        b.enable_simulation(64, rng.getrandbits(32))
        assert b.sims is not None  # noqa: S101 - Simulation was just turned on.
        signatures = {0, b.sim_mask, *b.sims[1:]}
    # Literal of each planned value, or -1 when its call was rejected as
    # redundant; arguments that refer to one use the closest earlier value.
    value_lits: list[int] = []
    accepted: list[int] = []
    call_outputs: list[list[int]] = []
    call_args: list[list[int]] = []
    for t, args, way, earlier in plan:
        num_outs = len(library[t].ways[0][2])
        if earlier >= 0 and not call_outputs[earlier]:
            call_args.append([])
            call_outputs.append([])
            value_lits.extend([-1] * num_outs)
            continue
        fanin0, fanin1, outputs = library[t].ways[way]
        k = library[t].num_inputs
        local = [0] * (1 + k + len(fanin0))
        for i, arg in enumerate(args):
            assert not isinstance(arg, int)  # noqa: S101 - Planned arguments are tagged.
            if earlier >= 0:
                local[1 + i] = call_args[earlier][i]
            elif arg[0] == "in":
                local[1 + i] = b.input(arg[1])
            else:
                lit = value_lits[arg[1]]
                if lit < 0:
                    lit = (
                        accepted[-1 - (arg[1] % min(len(accepted), 8))]
                        if accepted
                        else b.input(0)
                    )
                local[1 + i] = lit
        call_args.append(local[1 : 1 + k])
        if len(set(local[1 : 1 + k])) < k:
            call_outputs.append([])
            value_lits.extend([-1] * num_outs)
            continue

        def lit_of(x: int, local: list[int] = local) -> int:
            return local[x >> 1] ^ (x & 1)

        before = len(b.fanin0)
        for j, (f0, f1) in enumerate(zip(fanin0, fanin1, strict=True)):
            local[1 + k + j] = b.and2(lit_of(f0), lit_of(f1))
        outs = [lit_of(o) for o in outputs]
        if legal and earlier < 0:
            new = [b.sim(o) for o in outs]
            if len(set(new)) < len(new) or any(
                sig in signatures or sig ^ b.sim_mask in signatures for sig in new
            ):
                # A redundant call: drop its nodes, as a program that passes
                # DLP 59 would not have it.
                b.truncate(before)
                call_outputs.append([])
                value_lits.extend([-1] * num_outs)
                continue
            signatures.update(new)
        if earlier >= 0:
            kind = "call_repeat" if way == plan[earlier][2] else "call_rewrite"
            for o_new, o_old in zip(outs, call_outputs[earlier], strict=True):
                b.plant(o_old, o_new, kind)
        call_outputs.append(outs)
        value_lits.extend(outs)
        accepted.extend(outs)
    values = accepted
    b.outputs = values
    return b


def multiplexer(address_bits: int) -> Builder:
    """Return `data[address]` written as a multiplexer tree and as a decoder.

    The inputs are the address bits, then the data bits. The tree reads one
    address bit per level, so the logic is tree-shaped, but its OBDD is
    exponential when the data bits come before the address bits.
    """
    size = 1 << address_bits
    b = Builder(address_bits + size)
    address = [b.input(i) for i in range(address_bits)]
    data = [b.input(address_bits + i) for i in range(size)]
    level = data
    for bit in range(address_bits):
        level = [
            or_c(
                b,
                and_c(b, address[bit], level[2 * i + 1]),
                and_c(b, address[bit] ^ 1, level[2 * i]),
            )
            for i in range(len(level) // 2)
        ]
    tree = level[0]
    decoded = FALSE
    for k in range(size):
        match = TRUE
        for bit in range(address_bits):
            match = and_c(b, match, address[bit] ^ (0 if (k >> bit) & 1 else 1))
        decoded = or_c(b, decoded, and_c(b, match, data[k]))
    b.plant(tree, decoded, "multiplexer")
    b.outputs = [tree, decoded]
    return b.reorder_first_need(b.outputs)
