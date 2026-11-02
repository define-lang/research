"""Libraries of boolean value operations that execute each other.

Each operation reads up to `views` views and writes one view (DLP 57). It has
`and` statements (with `not` as negated literals) and executions of
operations from the level below, so copying every execution into its caller
multiplies the size by the number of executions at each level. Every value is
tracked by its exact truth table over the operation's views, and statements
whose value is constant, a view, or an earlier value (or the negation of one)
are rejected, so the libraries compile under DLP 57.

Some operations have a twin: the same function written as an irredundant sum
of products of its truth table. A `planted` statement executes the twin on
the same values as an earlier execution of the original, so the two results
are equal, which only reasoning about functions finds.

The text format, one operation per block:

    op NAME VIEWS
    and A B                  (a value: the `and` of two literals)
    exec CALLEE OUTPUTS A ...  (OUTPUTS values: CALLEE's written views)
    out A ...                (the written views)
    planted A B              (two literals that are equal by construction)
    end

Literals are `2 * value + negated`; value 0 is false, values 1..VIEWS the
views, and then one value per `and` and per output of an `exec`, in order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from matching import _isop

if TYPE_CHECKING:
    import random


@dataclass
class Op:
    """One boolean value operation."""

    name: str
    views: int
    statements: list[tuple] = field(default_factory=list)
    outputs: list[int] = field(default_factory=list)
    planted: list[tuple[int, int]] = field(default_factory=list)
    # Truth table of each value over the views, as an integer.
    tables: list[int] = field(default_factory=list)

    def mask(self) -> int:
        """Return the all-true table."""
        return (1 << (1 << self.views)) - 1

    def table_of(self, lit: int) -> int:
        """Return the truth table of a literal."""
        t = self.tables[lit >> 1]
        return t ^ self.mask() if lit & 1 else t

    def output_tables(self) -> list[int]:
        """Return the truth tables of the written views."""
        return [self.table_of(o) for o in self.outputs]


def _projection(views: int, i: int) -> int:
    out = 0
    for m in range(1 << views):
        if (m >> i) & 1:
            out |= 1 << m
    return out


def _new_op(name: str, views: int, *, checked: bool = True) -> Op:
    op = Op(name, views)
    # Unchecked, tables are placeholders that only count values.
    op.tables = [0] + [_projection(views, i) if checked else 0 for i in range(views)]
    return op


def _apply(callee: Op, arg_tables: list[int], views: int) -> list[int]:
    """Return the tables of an execution's results, by lookup per combination."""
    outs = callee.output_tables()
    results = [0] * len(outs)
    for m in range(1 << views):
        index = 0
        for i, t in enumerate(arg_tables):
            index |= ((t >> m) & 1) << i
        for j, o in enumerate(outs):
            if (o >> index) & 1:
                results[j] |= 1 << m
    return results


def _seen(op: Op) -> set[int]:
    out = set()
    for t in op.tables:
        out.add(t)
        out.add(t ^ op.mask())
    return out


def _try_and(op: Op, a: int, b: int, *, checked: bool = True) -> int | None:
    if not checked:
        op.statements.append(("and", a, b))
        op.tables.append(0)
        return 2 * (len(op.tables) - 1)
    t = op.table_of(a) & op.table_of(b)
    if t in _seen(op):
        return None
    op.statements.append(("and", a, b))
    op.tables.append(t)
    return 2 * (len(op.tables) - 1)


def _try_exec(
    op: Op, callee: Op, args: list[int], *, legal: bool = True, checked: bool = True
) -> list[int] | None:
    if not checked:
        op.statements.append(("exec", callee.name, len(callee.outputs), *args))
        first = len(op.tables)
        op.tables.extend([0] * len(callee.outputs))
        return [2 * v for v in range(first, len(op.tables))]
    results = _apply(callee, [op.table_of(a) for a in args], op.views)
    if legal:
        seen = _seen(op)
        for t in results:
            if t in seen:
                return None
            seen.add(t)
            seen.add(t ^ op.mask())
    op.statements.append(("exec", callee.name, len(results), *args))
    lits = []
    for t in results:
        op.tables.append(t)
        lits.append(2 * (len(op.tables) - 1))
    return lits


def _isop_twin(original: Op, name: str) -> Op | None:
    """Return a one-output operation computing the original's first output as an ISOP."""
    twin = _new_op(name, original.views)
    target = original.output_tables()[0]

    class Recording:
        """Collects `and` statements the ISOP builds."""

        def __init__(self) -> None:
            self.by_function: dict[int, int] = {}

        def and2(self, a: int, b: int) -> int:
            # Reuse an earlier value with the same function, so the twin has
            # no redundant values of its own.
            t = twin.table_of(a) & twin.table_of(b)
            for lit in (2 * v for v in range(len(twin.tables))):
                if twin.table_of(lit) == t:
                    return lit
                if twin.table_of(lit ^ 1) == t:
                    return lit ^ 1
            twin.statements.append(("and", a, b))
            twin.tables.append(t)
            return 2 * (len(twin.tables) - 1)

    builder = Recording()
    lits = [2 * (i + 1) for i in range(original.views)]
    out = _isop(builder, target, target, lits, original.views)  # type: ignore[arg-type]
    if twin.table_of(out) != target or out >> 1 <= original.views:
        return None
    twin.outputs = [out]
    return twin


def _near_miss(
    op: Op, rng: random.Random, available: list[int], cube_size: int, *, checked: bool
) -> int | None:
    """Add `v or (a cube of cube_size views)`, which differs from v rarely."""
    if len(available) <= op.views:
        return None
    v = rng.choice(available[op.views :])
    cube = None
    for view in rng.sample(range(op.views), cube_size):
        lit = 2 * (view + 1) ^ int(rng.random() < 0.5)
        cube = lit if cube is None else _try_and(op, cube, lit, checked=checked)
        if cube is None:
            return None
    result = _try_and(op, v ^ 1, cube ^ 1, checked=checked)
    return None if result is None else result ^ 1


def library(
    rng: random.Random,
    levels: int,
    per_level: int,
    views: int,
    executions: int,
    ands: int,
    twin_rate: float = 0.3,
    *,
    checked: bool = True,
    near_misses: int = 0,
    cube_size: int = 8,
) -> list[Op]:
    """Return a library of `levels` levels of `per_level` operations each.

    Unchecked, nothing is tracked or rejected and there are no twins, which
    is how libraries with many views are generated. Each operation can also
    get near-miss values: `v or (a cube of cube_size views)`, distinct from v
    but equal to it on all but a few combinations.
    """
    ops: list[Op] = []
    twins: dict[str, Op] = {}
    previous: list[Op] = []
    for level in range(levels):
        current: list[Op] = []
        k = 0
        while len(current) < per_level:
            op = _new_op(f"L{level}_{k}", views, checked=checked)
            k += 1
            available = [2 * (i + 1) for i in range(views)]
            steps = 0
            attempts = 0
            target_execs = executions if previous else 0
            execs = 0
            while (execs < target_execs or steps < ands) and attempts < 400:
                attempts += 1
                if (
                    previous
                    and execs < target_execs
                    and (steps >= ands or rng.random() < 0.5)
                ):
                    callee = rng.choice(previous)
                    args = (
                        rng.sample(available, callee.views)
                        if len(available) >= callee.views
                        else None
                    )
                    if args is None:
                        continue
                    args = [a ^ int(rng.random() < 0.2) for a in args]
                    lits = _try_exec(op, callee, args, checked=checked)
                    if lits is None:
                        continue
                    available.extend(lits)
                    execs += 1
                    # Sometimes execute the twin on the same values: a planted
                    # equality.
                    twin = twins.get(callee.name)
                    if checked and twin is not None and rng.random() < twin_rate:
                        planted = _try_exec(op, twin, args, legal=False)
                        assert planted is not None  # noqa: S101 - Not checked for legality.
                        op.planted.append((lits[0], planted[0]))
                else:
                    a, b = rng.sample(available[-8:] + available[:views], 2)
                    lit = _try_and(
                        op,
                        a ^ int(rng.random() < 0.25),
                        b ^ int(rng.random() < 0.25),
                        checked=checked,
                    )
                    if lit is None:
                        continue
                    available.append(lit)
                    steps += 1
            for _ in range(near_misses):
                lit = _near_miss(op, rng, available, cube_size, checked=checked)
                if lit is not None:
                    available.append(lit)
            if len(op.tables) <= views + 1:
                continue
            op.outputs = [2 * (len(op.tables) - 1)]
            current.append(op)
            ops.append(op)
            if checked and rng.random() < 0.5:
                twin = _isop_twin(op, op.name + "_twin")
                if twin is not None:
                    ops.append(twin)
                    twins[op.name] = twin
        previous = current
    return ops


def write(ops: list[Op], path: str) -> None:
    """Write a library in the text format above."""
    with open(path, "w", encoding="ascii") as out:
        for op in ops:
            out.write(f"op {op.name} {op.views}\n")
            out.writelines(" ".join(str(x) for x in st) + "\n" for st in op.statements)
            out.write("out " + " ".join(str(o) for o in op.outputs) + "\n")
            out.writelines(f"planted {a} {b}\n" for a, b in op.planted)
            out.write("end\n")
