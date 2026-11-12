"""Whole Define programs of value operations, for the full-algorithm study.

A program is a list of value operations in dependency order (every
operation comes after the operations it executes), and the project's
`booleans.defcl`: the set of registered boolean operations. This module generates programs (`generate`) and reads and writes
them in this text format:

    registered NAME ...          the booleans.defcl set, in any order (first line)
    op NAME bool VIEWS           a boolean value operation with VIEWS read views
    op NAME mixed NBOOL NNUM     a value operation that isn't purely boolean:
                                 NBOOL boolean read views, then NNUM numeric ones
    STATEMENT                    one per line, in statement order
    out V ...                    the written views, in the order they're defined
    end

Values are numbered from 1 in each operation: its read views first (for a
mixed operation the boolean ones, then the numeric ones), then one value per
statement, in order, except that `run` gives one value per written view of
the operation it executes. An argument is a value number, or a literal: `T`
or `F` (boolean) or `#TEXT` (numeric).

Statements:

    and A B        boolean statement: `standard:/boolean/and`
    not A          boolean statement: `standard:/boolean/not`
    call OP A ...  boolean statement: an execution of the boolean value
                   operation OP (registered or not), one argument per read
                   view of OP, in OP's view order; its value is OP's one
                   written view
    copy A         View Setting Statement: a new view holding A's value
                   (DLP 55). It's only used to give one value to two views
                   of the next execution, which reads both A and the copy.
                   Every rule treats the copy as the value A.
    cmp NAME A ... a statement that isn't boolean (a comparison, `NAME`)
                   reading numeric values or numeric literals; its value is
                   boolean, so it's a boolean input
    num NAME A ... a statement that isn't boolean, reading any values or
                   literals; its value is numeric
    run OP A ...   a statement that isn't boolean: an execution of the mixed
                   operation OP, one argument per read view of OP (boolean
                   views first); its values are OP's written views, which
                   are boolean inputs where they're boolean

A boolean value operation has only `and`, `not`, `call`, and `copy`
statements, reads only boolean views, and writes exactly one view (DLP 59).
A mixed operation writes any number of views, boolean or numeric.

Semantics, per operation:

- The boolean inputs are the boolean read views, the values of `cmp`, and the
  boolean values of `run`, in value order. Boolean statements are `and`,
  `not`, and `call`. A boolean value's function is over the boolean inputs,
  which are independent; a `call`'s is OP's written view's function of its
  arguments' functions (executions are whole: they refer to the executed
  operation's recorded function, and nothing inside it is a value here).
- The exits are the written views and the values that `num`, `cmp`, and
  `run` statements read. A statement nothing reads, directly or through
  other boolean statements, from an exit is dead.

The rules (DLPs 59, 60, and 61), each reported at its first violation:

- `limits`: more than 256 boolean statements, or more than 20 boolean inputs.
- `cycle`: an execution that leads, through other value operations, back to
  the operation it's in (DLP 9).
- `literal`: a boolean statement given a literal.
- `wrapper`: a boolean value operation whose only boolean statement is an
  `and`, a `not`, or a `call` of a registered operation.
- `redundant`: the first boolean statement whose value is always true or
  always false, always the same as a boolean input or an earlier boolean
  statement's value, or always the opposite of one, unless the statement is
  the `not` of that value. A value that's the same as one value and the
  opposite of another is reported as the same.
- `dead`: every boolean statement whose value reaches no exit.
- `unused_view`: every read view of a boolean value operation its written
  view doesn't depend on.
- `order_arguments`: a boolean statement whose arguments to a group of
  interchangeable views aren't in rank order, the lowest to the view
  defined first. Two views of an operation are interchangeable when swapping
  them doesn't change its written view's function; groups are the classes
  of that relation (it's transitive). `and`'s two views are one group.
- `order_statements`: the statements aren't in DLP 60's order: for each
  statement that isn't boolean, in order, the boolean statements computing
  the boolean values it reads that haven't come yet, each preceded by the
  same for its own arguments (in view order), then the statement itself;
  then the same for the written views in order. A `copy` comes right before
  the execution that reads it and isn't otherwise ordered.
- `match`: a boolean statement's value v and a registered operation R
  (`and` and `not` included; when checking a registered operation's
  definition, only `and`, `not`, and the ones with smaller keys) with
  arguments: at most four
  distinct values that come before v (boolean inputs and earlier boolean
  statements' values), given to R's views in some order, every one
  mattering, with v always R of them, or always its opposite when no
  registered operation computes R's opposite. Not a match: v is already an
  execution of R on those arguments, or for the opposite, a `not` of one.
  The statements of a match are v's and every statement nothing reads once
  v comes from the execution; there must be at least two, or three for an
  opposite. The reported one removes the most statements, then has the
  earliest value, then R first (`and`, `not`, then by key), then the
  arguments first in rank order.
- `spelling`: a `call` of a registered operation, single execution, whose
  value another single execution of a registered operation on values before
  it also computes, with a key that comes first: (number of arguments that
  are the value of a `not` statement, the operation's place: `and`, `not`,
  then by key, the arguments' ranks in view order). `and` and `not`
  statements are spellings too.

A registered operation's key (DLP 61) is the fewest `and`s in any
and-inverter graph computing its function (`src/min_ands.hpp`, found by
`min_ands_experiment.py`), then its number of read views, then its truth
table as a number, view 1 the lowest bit of the row. No two registered
operations compute the same function, so keys are distinct.

Ranks (DLP 60): read views first, in order; then literals, by value quality
(`boolean` before `number`) and text; then statement values, compared by
their arguments' ranks in view order, a shorter list first, then by the
executed operation's name (`standard:/boolean/and`, `standard:/boolean/not`,
OP for `call` and `run`, NAME for `cmp` and `num`), then by which of its
written views. A copy ranks as its source.

The checker is `beq program` (`src/program.hpp`); `program_check.py` is an
independent implementation for small programs.
"""

from __future__ import annotations

import functools
import random
from dataclasses import dataclass, field

# booleans.defcl, a set: the order is by key (DLP 61).
REGISTERED = ["implies", "or", "xor", "eq", "mux", "maj"]
# The registered operations' definitions, each after the ones it executes:
# (views, statements, written view). These are the forms the fix loop
# reaches from definitions written with `and` and `not` only: each one
# follows `and`, `not`, and the registered operations with smaller keys
# (implies, or, xor, eq, mux, maj: the fewest `and`s, then views, then
# the truth table), so `or` is written with `implies`, `xor` with `or`,
# `eq` is the `not` of `xor`, and `maj` is a `mux`.
DEFINITIONS = {
    "implies": (2, ["not 2", "and 1 3", "not 4"], 5),
    "or": (2, ["not 1", "call implies 3 2"], 4),
    "xor": (2, ["not 2", "and 1 3", "not 1", "and 2 5", "call or 4 6"], 7),
    "eq": (2, ["call xor 1 2", "not 3"], 4),
    "mux": (3, ["and 1 2", "not 1", "and 3 5", "call or 4 6"], 7),
    "maj": (3, ["call or 1 2", "and 1 2", "call mux 3 4 5"], 6),
}
FUNCTIONS = {
    "or": lambda a, b: a | b,
    "implies": lambda a, b: ~a | b,
    "xor": lambda a, b: a ^ b,
    "eq": lambda a, b: ~(a ^ b),
    "mux": lambda s, a, b: (s & a) | (~s & b),
    "maj": lambda a, b, c: (a & b) | (c & (a | b)),
}


@dataclass
class Settings:
    """How a program is generated."""

    levels: int = 10
    boolean_per_level: int = 100
    mixed_per_level: int = 25
    views: tuple[int, int] = (3, 8)
    statements: tuple[int, int] = (8, 40)
    # Statements of a mixed operation: comparisons, boolean statements.
    comparisons: tuple[int, int] = (1, 5)
    mixed_statements: tuple[int, int] = (5, 30)
    # Weights of the kinds of boolean statements.
    weights: dict[str, float] = field(
        default_factory=lambda: {"and": 45, "not": 12, "registered": 25, "user": 15}
    )
    # Values that track their functions, rejecting constants and values the
    # operation already has. Off for wide operations, where the fix loop
    # removes them instead.
    tracked: bool = True
    # The rate of a deliberate error in the programs the fix loop starts
    # from. Literals and values that never change are the programmer's to
    # fix (DLP 59), so the programs have none.
    wrapper_rate: float = 0.005
    copy_rate: float = 0.05


class Builder:
    """One operation being written: its lines, and its values' functions."""

    def __init__(self, name: str, header: str, inputs: int, *, tracked: bool) -> None:
        """Start an operation whose boolean inputs number `inputs`."""
        self.name = name
        self.header = header
        self.lines: list[str] = []
        self.next = 1
        self.inputs = inputs
        # Past SAMPLED_INPUTS inputs, a function is its values on SAMPLES
        # random input combinations instead of all 2^inputs: every
        # statement is bitwise, so the same code computes either. Equal
        # functions are equal on the samples, so a value the operation
        # already has is still never added; two different ones that agree
        # on every sample only make the generator try another statement.
        self.mask = (1 << (SAMPLES if inputs > SAMPLED_INPUTS else 1 << inputs)) - 1
        self.tracked = tracked
        self.tables: dict[int, int] = {}
        self.seen: set[int] = {0, self.mask}
        self.input_count = 0
        self.boolean: list[int] = []
        self.unused: list[int] = []
        self.nots: dict[int, int] = {}
        self.users: dict[str, UserOp] = {}

    def projection(self) -> int:
        """Return the function of the next boolean input."""
        i = self.input_count
        self.input_count += 1
        if not self.tracked:
            return 0
        if self.inputs > SAMPLED_INPUTS:
            return sampled_projection(self.inputs, i)
        return projection(self.inputs, i)

    def value(self) -> int:
        """Return the next value's number."""
        v = self.next
        self.next += 1
        return v

    def view(self, *, boolean: bool) -> int:
        """Add a read view."""
        v = self.value()
        if boolean:
            self.tables[v] = self.projection()
            self.seen.add(self.tables[v])
            self.boolean.append(v)
        return v

    def new(self, table: int, *, allow_opposite: bool = False) -> bool:
        """Whether a boolean value with this function is new to the operation."""
        if not self.tracked:
            return True
        t = table & self.mask
        return t not in self.seen and (
            allow_opposite or (t ^ self.mask) not in self.seen
        )

    def emit(self, line: str, table: int | None) -> int:
        """Add a statement with one value; boolean when it has a table."""
        self.lines.append(line)
        v = self.value()
        if table is not None:
            t = table & self.mask
            self.tables[v] = t
            self.seen.add(t)
            self.boolean.append(v)
            self.unused.append(v)
        return v

    def use(self, v: int) -> None:
        """Note that a value is read."""
        if v in self.unused:
            self.unused.remove(v)

    def text(self, outs: list[str]) -> str:
        """Return the operation in the program format."""
        return "\n".join([self.header, *self.lines, "out " + " ".join(outs), "end"])


SAMPLED_INPUTS = 12
SAMPLES = 4096


@functools.cache
def sampled_projection(inputs: int, i: int) -> int:
    """Return input i's values on the sampled input combinations."""
    rng = random.Random(inputs)  # noqa: S311 - The same samples every time.
    out = 0
    for k in range(SAMPLES):
        if rng.getrandbits(inputs) >> i & 1:
            out |= 1 << k
    return out


@functools.cache
def projection(inputs: int, i: int) -> int:
    """Return input i's function over `inputs` inputs."""
    out = ((1 << (1 << i)) - 1) << (1 << i)
    length = 1 << (i + 1)
    while length < (1 << inputs):
        out |= out << length
        length *= 2
    return out


def compose(table: int, views: int, args: list[int], mask: int) -> int:
    """Return an operation's function of its arguments' functions (Shannon)."""

    def go(lo: int, k: int) -> int:
        if k == 0:
            return mask if (table >> lo) & 1 else 0
        a = args[k - 1]
        return (a & go(lo + (1 << (k - 1)), k - 1)) | (~a & mask & go(lo, k - 1))

    return go(0, views)


@dataclass
class UserOp:
    """A generated boolean value operation: its name, views, and function.

    Operations with many views also keep their statements, since composing
    their table costs 2^views steps while evaluating their statements on the
    arguments' functions costs one step per statement.
    """

    name: str
    views: int
    table: int | None
    body: list[tuple[str, str, list[int]]] = field(default_factory=list)
    out: int = 0


def evaluate(op: UserOp, args: list[int], mask: int, users: dict[str, UserOp]) -> int:
    """Return what a user operation computes from its arguments' functions."""
    if op.views <= 10 and op.table is not None:
        return compose(op.table, op.views, args, mask)
    values = dict(enumerate(args, start=1))
    values[-1] = mask
    v = op.views + 1
    for kind, name, a in op.body:
        x = [values[i] for i in a]
        if kind == "and":
            values[v] = x[0] & x[1]
        elif kind == "not":
            values[v] = ~x[0] & mask
        elif kind == "copy":
            values[v] = x[0]
        elif name in FUNCTIONS:
            values[v] = FUNCTIONS[name](*x) & mask
        else:
            values[v] = evaluate(users[name], x, mask, users)
        v += 1
    return values[op.out]


def unused_views(op: UserOp, users: dict[str, UserOp]) -> list[int]:
    """Return the read views (from 0) the written view doesn't depend on.

    Past SAMPLED_INPUTS views, on the samples: negating a view's values
    leaves the written view's the same.
    """
    if op.views <= SAMPLED_INPUTS:
        full = (1 << (1 << op.views)) - 1
        out = []
        for i in range(op.views):
            p = projection(op.views, i)
            if (op.table & p) >> (1 << i) == op.table & ~p & full:
                out.append(i)
        return out
    mask = (1 << SAMPLES) - 1
    views = [sampled_projection(op.views, i) for i in range(op.views)]
    out = []
    for i in range(op.views):
        flipped = list(views)
        flipped[i] ^= mask
        if evaluate(op, flipped, mask, users) == op.table:
            out.append(i)
    return out


def _pick(b: Builder, rng: random.Random, k: int) -> list[int] | None:
    """Choose k distinct boolean values, preferring ones nothing reads yet."""
    pool = b.boolean
    if len(pool) < k:
        return None
    out: list[int] = []
    while len(out) < k:
        if b.unused and rng.random() < 0.5:
            v = rng.choice(b.unused)
        else:
            v = pool[len(pool) - 1 - min(int(rng.expovariate(1 / 10)), len(pool) - 1)]
        if v not in out:
            out.append(v)
    return out


def _boolean_statement(
    b: Builder,
    rng: random.Random,
    s: Settings,
    users: list[UserOp],
) -> None:
    """Add one boolean statement of a random kind, if one fits."""
    kinds = list(s.weights)
    kind = rng.choices(kinds, [s.weights[k] for k in kinds])[0]
    if kind == "user" and not users:
        kind = "and"
    for _ in range(20):
        if kind == "not":
            args = _pick(b, rng, 1)
            if args is None or args[0] in b.nots:
                kind = "and"
                continue
            table = ~b.tables[args[0]] if b.tracked else 0
            v = b.emit(f"not {args[0]}", table)
            b.nots[args[0]] = v
            b.use(args[0])
            return
        if kind == "and":
            args = _pick(b, rng, 2)
            if args is None:
                return
            table = b.tables[args[0]] & b.tables[args[1]] if b.tracked else 0
            if not b.new(table):
                continue
            b.emit(f"and {args[0]} {args[1]}", table)
        elif kind == "registered":
            name = rng.choice(REGISTERED)
            arity = DEFINITIONS[name][0]
            args = _pick(b, rng, arity)
            if args is None:
                return
            table = FUNCTIONS[name](*(b.tables[a] for a in args)) if b.tracked else 0
            if not b.new(table):
                continue
            b.emit(f"call {name} " + " ".join(map(str, args)), table)
        else:
            callee = rng.choice(users)
            args = _pick(b, rng, callee.views)
            if args is None:
                kind = "and"
                continue
            copy_line = None
            if callee.views >= 2 and rng.random() < s.copy_rate:
                # One value given to two views, through a copy (DLP 55).
                copy_line = args[0]
                args = args[:-1]
            tables = [b.tables[a] for a in args]
            if copy_line is not None:
                tables.append(b.tables[copy_line])
            table = evaluate(callee, tables, b.mask, b.users) if b.tracked else 0
            if not b.new(table):
                continue
            if copy_line is not None:
                b.lines.append(f"copy {copy_line}")
                args.append(b.value())
            b.emit(f"call {callee.name} " + " ".join(map(str, args)), table)
        for a in args:
            if a in b.tables:
                b.use(a)
        return


def _close(b: Builder) -> int:
    """Combine the values nothing reads into one, which the operation writes."""
    while len(b.unused) > 1:
        x, y = b.unused[-2], b.unused[-1]
        names = ["and", "or", "xor", "implies", "eq"]
        tables = {}
        for name in names:
            if not b.tracked:
                tables[name] = 0
            elif name == "and":
                tables[name] = b.tables[x] & b.tables[y]
            else:
                tables[name] = FUNCTIONS[name](b.tables[x], b.tables[y])
        # A value that never changes is the programmer's to fix (DLP 59), so
        # none is made; if no other combination is new, the last one that
        # changes is a redundant value.
        changing = [n for n in names if tables[n] & b.mask not in (0, b.mask)] or names
        for name in names:
            table = tables[name]
            # Every value is read, so there are no dead statements.
            if b.new(table) or name == changing[-1]:
                line = f"and {x} {y}" if name == "and" else f"call {name} {x} {y}"
                b.use(x)
                b.use(y)
                b.emit(line, table)
                break
    return b.unused[0] if b.unused else b.boolean[-1]


def boolean_operation(
    name: str,
    rng: random.Random,
    s: Settings,
    users: list[UserOp],
    known: dict[str, UserOp],
) -> tuple[str, UserOp]:
    """Return a random boolean value operation and what it computes."""
    views = rng.randint(*s.views)
    b = Builder(name, f"op {name} bool {views}", views, tracked=s.tracked)
    b.users = known
    for _ in range(views):
        b.view(boolean=True)
    b.unused = list(b.boolean)
    if rng.random() < s.wrapper_rate:
        reg = rng.choice(["or", "implies", "xor", "eq"])
        v = b.emit(
            f"call {reg} 1 2",
            FUNCTIONS[reg](b.tables[1], b.tables[2]) if b.tracked else 0,
        )
        table = b.tables[v] if b.tracked else None
        return b.text([str(v)]), UserOp(name, views, table, [("call", reg, [1, 2])], v)
    target = rng.randint(*s.statements)
    while len(b.lines) < target:
        _boolean_statement(b, rng, s, users)
    out = _close(b)
    if b.tracked:
        # Random statements often leave a read view that doesn't matter,
        # an error the generator would make by accident: `xor` of the
        # written view with each such view makes it matter.
        so_far = UserOp(name, views, b.tables[out], _body(b.lines), out)
        for i in unused_views(so_far, known):
            table = FUNCTIONS["xor"](b.tables[out], b.tables[i + 1])
            out = b.emit(f"call xor {out} {i + 1}", table)
    table = b.tables.get(out) if b.tracked else None
    return b.text([str(out)]), UserOp(name, views, table, _body(b.lines), out)


def _body(lines: list[str]) -> list[tuple[str, str, list[int]]]:
    """Return an operation's statements as UserOp.body has them."""
    body = []
    for line in lines:
        kind, *rest = line.split()
        callee = rest.pop(0) if kind == "call" else ""
        body.append((kind, callee, [-1 if x == "T" else int(x) for x in rest]))
    return body


@dataclass
class MixedOp:
    """A generated mixed operation: its name and read and written views."""

    name: str
    nbool: int
    nnum: int
    outs: list[bool]  # boolean or not, per written view


def mixed_operation(
    name: str,
    rng: random.Random,
    s: Settings,
    users: list[UserOp],
    mixed: list[MixedOp],
    known: dict[str, UserOp],
) -> tuple[str, MixedOp]:
    """Return a value operation that isn't purely boolean.

    It interleaves boolean logic with comparisons and numeric statements,
    and executes other mixed operations.
    """
    nbool = rng.randint(0, 3)
    nnum = rng.randint(1, 4)
    runs = [rng.choice(mixed)] if mixed and rng.random() < 0.5 else []
    run_inputs = sum(sum(m.outs) for m in runs)
    # DLP 59's limit of twenty boolean inputs.
    comparisons = min(rng.randint(*s.comparisons), 20 - nbool - run_inputs)
    inputs = nbool + comparisons + run_inputs
    b = Builder(name, f"op {name} mixed {nbool} {nnum}", inputs, tracked=s.tracked)
    b.users = known
    for _ in range(nbool):
        b.view(boolean=True)
    numeric = [b.view(boolean=False) for _ in range(nnum)]
    for _ in range(comparisons):
        args = [
            rng.choice(numeric),
            f"#{rng.randint(0, 9)}" if rng.random() < 0.5 else rng.choice(numeric),
        ]
        b.lines.append(
            f"cmp {rng.choice(['lt', 'eq', 'gt'])} " + " ".join(map(str, args))
        )
        v = b.value()
        b.tables[v] = b.projection()
        b.seen.add(b.tables[v])
        b.boolean.append(v)
    for m in runs:
        args = []
        for _ in range(m.nbool):
            args.append(str(rng.choice(b.boolean)) if b.boolean else "T")
        for _ in range(m.nnum):
            args.append(str(rng.choice(numeric)))
        b.lines.append(f"run {m.name} " + " ".join(args))
        for out in m.outs:
            v = b.value()
            if out:
                b.tables[v] = b.projection()
                b.seen.add(b.tables[v])
                b.boolean.append(v)
            else:
                numeric.append(v)
    b.unused = list(b.boolean)
    target = rng.randint(*s.mixed_statements)
    weights = dict(s.weights)
    weights["user"] *= 2
    mixed_settings = Settings(**{**s.__dict__, "weights": weights})
    outs: list[str] = []
    out_kinds: list[bool] = []
    while len(b.lines) < target:
        _boolean_statement(b, rng, mixed_settings, users)
        if b.unused and rng.random() < 0.08:
            # A numeric statement that reads a boolean value.
            x = b.unused[-1]
            b.use(x)
            b.lines.append(f"num sel {x} {rng.choice(numeric)} {rng.choice(numeric)}")
            numeric.append(b.value())
    bool_outs = rng.randint(0, 2)
    for _ in range(bool_outs):
        if b.unused:
            v = b.unused.pop()
            outs.append(str(v))
            out_kinds.append(True)
    while b.unused:
        x = b.unused.pop()
        b.lines.append(f"num sel {x} {rng.choice(numeric)} {rng.choice(numeric)}")
        numeric.append(b.value())
    outs.append(str(numeric[-1]))
    out_kinds.append(False)
    return b.text(outs), MixedOp(name, nbool, nnum, out_kinds)


def generate(rng: random.Random, s: Settings) -> str:
    """Return a whole program in the text format above."""
    parts = ["registered " + " ".join(REGISTERED)]
    for name, (views, statements, out) in DEFINITIONS.items():
        parts.append(
            "\n".join([f"op {name} bool {views}", *statements, f"out {out}", "end"])
        )
    users: list[UserOp] = []
    known: dict[str, UserOp] = {}
    mixed: list[MixedOp] = []
    recent: list[list[UserOp]] = []
    for level in range(s.levels):
        current: list[UserOp] = []
        callees = [u for group in recent[-3:] for u in group]
        for k in range(s.boolean_per_level):
            text, op = boolean_operation(f"b{level}_{k}", rng, s, callees, known)
            parts.append(text)
            current.append(op)
            known[op.name] = op
        for k in range(s.mixed_per_level):
            text, op = mixed_operation(
                f"m{level}_{k}", rng, s, callees + current, mixed[-200:], known
            )
            parts.append(text)
            mixed.append(op)
        users.extend(current)
        recent.append(current)
    return "\n".join(parts) + "\n"


def main() -> None:
    """Write a program: `program.py OUT SEED [key=value ...]` for Settings."""
    import sys

    out, seed, *pairs = sys.argv[1:]
    s = Settings()
    for pair in pairs:
        key, value = pair.split("=")
        current = getattr(s, key)
        if isinstance(current, tuple):
            setattr(s, key, tuple(int(x) for x in value.split(",")))
        elif isinstance(current, bool):
            setattr(s, key, value == "1")
        else:
            setattr(s, key, type(current)(value))
    with open(out, "w", encoding="ascii") as f:
        f.write(generate(random.Random(int(seed)), s))  # noqa: S311 - Reproducible workloads.


if __name__ == "__main__":
    main()
