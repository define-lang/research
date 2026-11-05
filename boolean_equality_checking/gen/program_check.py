"""An independent checker for the program format of `program.py`, by brute force.

It shares nothing with `beq program` but the format: it computes functions by
evaluating each executed operation's own statements (never a recorded
table), finds matches and spellings by trying every tuple of arguments in
every view order, finds groups of interchangeable views by trying every
pair, and builds DLP 59's order of statements itself. It's for small
programs: at most 12 boolean inputs and a few dozen values per operation.

    uv run --frozen --python 3.14 python gen/program_check.py FILE.prog
    uv run --frozen --python 3.14 python gen/program_check.py --self-test

prints one JSON line per operation, `{"op": NAME, "errors": {RULE: DETAIL}}`,
with the details described in `check_program`.
"""

from __future__ import annotations

import functools
import itertools
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

BOOLEAN_STATEMENTS = ("and", "not", "call")
NOT_BOOLEAN_STATEMENTS = ("cmp", "num", "run")
SAMPLES = 64


@dataclass
class Statement:
    """One statement: its kind, the operation or name it names, its arguments."""

    kind: str
    name: str | None
    args: list[int | str]


@dataclass
class Operation:
    """One value operation as written."""

    name: str
    kind: str
    boolean_views: int
    numeric_views: int
    statements: list[Statement] = field(default_factory=list)
    outputs: list[int | str] = field(default_factory=list)
    # By value number: ("view", index) or ("statement", index, written view).
    origins: dict[int, tuple] = field(default_factory=dict)
    types: dict[int, str] = field(default_factory=dict)


@dataclass
class Program:
    """A whole program: its operations by name, in order, and booleans.defcl."""

    registered: list[str]
    operations: dict[str, Operation]


def parse_argument(token: str) -> int | str:
    """Return a value number, or a literal as its token."""
    if token in ("T", "F") or token.startswith("#"):
        return token
    return int(token)


def parse(text: str) -> Program:
    """Read a program."""
    lines = [line.split() for line in text.splitlines() if line.strip()]
    if lines[0][0] != "registered":
        raise ValueError("the first line must be `registered`")
    program = Program(lines[0][1:], {})
    current: Operation | None = None
    for words in lines[1:]:
        if words[0] == "op":
            if words[2] == "bool":
                current = Operation(words[1], "bool", int(words[3]), 0)
            else:
                current = Operation(words[1], "mixed", int(words[3]), int(words[4]))
            for i in range(current.boolean_views + current.numeric_views):
                current.origins[i + 1] = ("view", i)
                current.types[i + 1] = "bool" if i < current.boolean_views else "num"
        elif words[0] == "end":
            assert current is not None  # noqa: S101 - The format puts `op` first.
            program.operations[current.name] = current
            current = None
        elif words[0] == "out":
            assert current is not None  # noqa: S101 - The format puts `op` first.
            current.outputs = [parse_argument(w) for w in words[1:]]
        else:
            assert current is not None  # noqa: S101 - The format puts `op` first.
            add_statement(program, current, words)
    return program


def add_statement(program: Program, op: Operation, words: list[str]) -> None:
    """Append one statement and number its values."""
    kind = words[0]
    if kind in ("and", "not", "copy"):
        statement = Statement(kind, None, [parse_argument(w) for w in words[1:]])
    else:
        statement = Statement(kind, words[1], [parse_argument(w) for w in words[2:]])
    index = len(op.statements)
    op.statements.append(statement)
    first = len(op.origins) + 1
    if kind == "run":
        callee = program.operations[statement.name]
        for k, out in enumerate(callee.outputs):
            op.origins[first + k] = ("statement", index, k)
            op.types[first + k] = output_type(callee, out)
        return
    op.origins[first] = ("statement", index, 0)
    if kind == "copy":
        source = statement.args[0]
        op.types[first] = op.types[source] if isinstance(source, int) else "literal"
    else:
        op.types[first] = "num" if kind == "num" else "bool"


def output_type(op: Operation, out: int | str) -> str:
    """Return whether a written view is boolean or numeric."""
    if isinstance(out, str):
        return "num" if out.startswith("#") else "bool"
    return op.types[out]


class Checker:
    """Checks the operations of one program."""

    def __init__(self, program: Program) -> None:
        """Prepare a program for checking."""
        self.program = program
        self.groups_memo: dict[str, list[list[int]]] = {}
        self.function_memo: dict[str, int] = {}
        self.opposite_memo: dict[tuple[str, tuple[str, ...]], bool] = {}

    # Values.

    def resolve(self, op: Operation, arg: int | str) -> int | str:
        """Follow copies to the value they hold."""
        while isinstance(arg, int):
            origin = op.origins[arg]
            if origin[0] != "statement":
                return arg
            statement = op.statements[origin[1]]
            if statement.kind != "copy":
                return arg
            arg = statement.args[0]
        return arg

    def statement_of(self, op: Operation, value: int) -> Statement | None:
        """Return the statement computing a value, or None for a read view."""
        origin = op.origins[value]
        return op.statements[origin[1]] if origin[0] == "statement" else None

    def is_boolean_statement_value(self, op: Operation, value: int | str) -> bool:
        """Return whether a value is computed by a boolean statement."""
        if isinstance(value, str):
            return False
        statement = self.statement_of(op, value)
        return statement is not None and statement.kind in BOOLEAN_STATEMENTS

    def boolean_inputs(self, op: Operation) -> list[int]:
        """Return the boolean inputs in value order."""
        out = []
        for value, origin in sorted(op.origins.items()):
            if op.types[value] != "bool":
                continue
            if origin[0] == "view" or op.statements[origin[1]].kind in ("cmp", "run"):
                out.append(value)
        return out

    # Functions, by evaluating statements.

    def evaluate(
        self, op: Operation, given: dict[int, int], mask: int
    ) -> dict[int, int]:
        """Return the function of every boolean value, from the inputs' functions.

        Executions are evaluated by evaluating the executed operation's own
        statements on the functions given to it.
        """
        tables = dict(given)
        for index, statement in enumerate(op.statements):
            value = self.first_value(op, index)
            if statement.kind == "copy":
                source = self.resolve(op, statement.args[0])
                if isinstance(source, int) and source in tables:
                    tables[value] = tables[source]
                continue
            if statement.kind not in BOOLEAN_STATEMENTS:
                continue
            args = [self.table_of(op, tables, a, mask) for a in statement.args]
            if statement.kind == "and":
                tables[value] = args[0] & args[1]
            elif statement.kind == "not":
                tables[value] = args[0] ^ mask
            else:
                tables[value] = self.call(statement.name, args, mask)
        return tables

    def table_of(
        self, op: Operation, tables: dict[int, int], arg: int | str, mask: int
    ) -> int:
        """Return an argument's function, with a literal as a constant."""
        arg = self.resolve(op, arg)
        if arg == "T":
            return mask
        if arg == "F":
            return 0
        return tables[arg]

    def call(self, name: str, args: list[int], mask: int) -> int:
        """Return the function an execution of a boolean value operation computes."""
        callee = self.program.operations[name]
        given = {i + 1: t for i, t in enumerate(args)}
        tables = self.evaluate(callee, given, mask)
        return self.table_of(callee, tables, callee.outputs[0], mask)

    def first_value(self, op: Operation, index: int) -> int:
        """Return the first value number of a statement."""
        for value, origin in op.origins.items():
            if origin[0] == "statement" and origin[1] == index:
                return value
        raise KeyError(index)

    def key(self, name: str) -> tuple[int, int, int]:
        """Return a registered operation's key (DLP 60).

        The fewest `and`s computing its function, then its number of read
        views, then its truth table as a number.
        """
        views = self.arity(name)
        table = self.own_function(name)
        # Only operations of up to four read views can be registered.
        return (fewest_ands(table, views) if views <= 4 else sys.maxsize, views, table)

    def follows(self, op: Operation) -> list[str]:
        """Return the registered operations an operation follows, in order.

        `and` and `not` come first, then the others by key; a registered
        operation's own definition follows only the ones with smaller keys.
        """
        # One in or executing a cycle has no function to match (DLP 9).
        names = [n for n in self.program.registered if not self.reaches_cycle(n)]
        names.sort(key=self.key)
        if op.name in names:
            names = names[: names.index(op.name)]
        return ["and", "not", *names]

    def arity(self, name: str) -> int:
        """Return how many views a registered operation reads."""
        if name in ("and", "not"):
            return 2 if name == "and" else 1
        return self.program.operations[name].boolean_views

    def own_function(self, name: str) -> int:
        """Return a boolean value operation's function of its own views."""
        if name == "and":
            return 0b1000
        if name == "not":
            return 0b01
        if name not in self.function_memo:
            views = self.program.operations[name].boolean_views
            mask = (1 << (1 << views)) - 1
            self.function_memo[name] = self.call(name, projections(views), mask)
        return self.function_memo[name]

    def op_tables(self, op: Operation) -> tuple[dict[int, int], int, int]:
        """Return every boolean value's function, the mask, and the input count."""
        inputs = self.boolean_inputs(op)
        mask = (1 << (1 << len(inputs))) - 1
        given = dict(zip(inputs, projections(len(inputs)), strict=True))
        return self.evaluate(op, given, mask), mask, len(inputs)

    # Interchangeable views.

    def groups(self, name: str) -> list[list[int]]:
        """Return the groups of interchangeable views of an executed operation."""
        if name == "and":
            return [[0, 1]]
        if name == "not":
            return [[0]]
        if name not in self.groups_memo:
            views = self.program.operations[name].boolean_views
            mask = (1 << (1 << views)) - 1
            base = projections(views)
            function = self.call(name, base, mask)
            parent = list(range(views))
            for i, j in itertools.combinations(range(views), 2):
                swapped = list(base)
                swapped[i], swapped[j] = base[j], base[i]
                if self.call(name, swapped, mask) == function:
                    parent[find(parent, j)] = find(parent, i)
            by_root: dict[int, list[int]] = {}
            for i in range(views):
                by_root.setdefault(find(parent, i), []).append(i)
            self.groups_memo[name] = list(by_root.values())
        return self.groups_memo[name]

    # Ranks.

    def rank_compare(self, op: Operation, a: int | str, b: int | str) -> int:
        """Compare two values (or literals) in DLP 59's rank order."""
        a, b = self.resolve(op, a), self.resolve(op, b)
        if a == b:
            return 0
        ka, kb = self.rank_category(op, a), self.rank_category(op, b)
        if ka[0] != kb[0]:
            return -1 if ka[0] < kb[0] else 1
        if ka[0] < 2:
            return -1 if ka[1:] < kb[1:] else 1
        sa = self.statement_of(op, a)  # type: ignore[arg-type]
        sb = self.statement_of(op, b)  # type: ignore[arg-type]
        assert sa is not None  # noqa: S101 - Category 2 is a statement.
        assert sb is not None  # noqa: S101 - Category 2 is a statement.
        for x, y in zip(sa.args, sb.args, strict=False):
            c = self.rank_compare(op, x, y)
            if c:
                return c
        if len(sa.args) != len(sb.args):
            return -1 if len(sa.args) < len(sb.args) else 1
        na, nb = operation_name(sa), operation_name(sb)
        if na != nb:
            return -1 if na < nb else 1
        wa, wb = op.origins[a][2], op.origins[b][2]  # type: ignore[index]
        return (wa > wb) - (wa < wb)

    def rank_category(self, op: Operation, value: int | str) -> tuple:
        """Return (0, view) for a read view, (1, quality, text) for a literal, or (2,)."""
        if isinstance(value, str):
            if value in ("T", "F"):
                return (1, "boolean", value)
            return (1, "number", value[1:])
        origin = op.origins[value]
        if origin[0] == "view":
            return (0, origin[1])
        return (2,)

    def canonical_arguments(
        self, op: Operation, name: str, args: list[int]
    ) -> list[int]:
        """Return arguments with each group of interchangeable views in rank order."""
        out = list(args)
        key = functools.cmp_to_key(lambda x, y: self.rank_compare(op, x, y))
        for group in self.groups(name):
            for position, value in zip(
                group, sorted((args[i] for i in group), key=key), strict=True
            ):
                out[position] = value
        return out

    def compare_lists(self, op: Operation, a: list[int], b: list[int]) -> int:
        """Compare argument lists element by element in rank order."""
        for x, y in zip(a, b, strict=True):
            c = self.rank_compare(op, x, y)
            if c:
                return c
        return 0

    # The rules.

    def check(self, op: Operation) -> dict[str, object]:
        """Return the first violation of each rule in an operation."""
        errors: dict[str, object] = {}
        boolean = [
            i for i, s in enumerate(op.statements) if s.kind in BOOLEAN_STATEMENTS
        ]
        inputs = self.boolean_inputs(op)
        if len(boolean) > 256:
            errors["limits"] = "statements"
        elif len(inputs) > 20:
            errors["limits"] = "inputs"
        for i in boolean:
            if any(isinstance(self.resolve(op, a), str) for a in op.statements[i].args):
                errors["literal"] = i
                break
        if op.kind == "bool" and len(boolean) == 1:
            only = op.statements[boolean[0]]
            if only.kind in ("and", "not") or only.name in self.program.registered:
                errors["wrapper"] = True
        cycle = self.cycle(op)
        if cycle:
            errors["cycle"] = cycle
        # Past the limits nothing else is checked, nor in an operation whose
        # executions reach a cycle (DLP 9), which has no function.
        if "limits" in errors or self.reaches_cycle(op.name):
            return errors
        found = self.order_arguments(op, boolean)
        if found is not None:
            errors["order_arguments"] = found
        found = self.order_statements(op)
        if found is not None:
            errors["order_statements"] = found
        tables, mask, count = self.op_tables(op)
        redundant = self.redundant(op, boolean, inputs, tables, mask)
        dead = self.dead(op)
        if dead:
            errors["dead"] = dead
        if op.kind == "bool":
            unused = self.unused_views(op)
            if unused:
                errors["unused_view"] = unused
        if redundant is not None:
            errors["redundant"] = redundant
            return errors
        context = Context(op, tables, mask, count, self.available(op, boolean, inputs))
        found = self.match(context, boolean)
        if found is not None:
            errors["match"] = found
        found = self.spelling(context, boolean)
        if found is not None:
            errors["spelling"] = found
        return errors

    def executed(self, name: str) -> list[str]:
        """Return the operations an operation's executions execute, in order."""
        return [
            str(s.name)
            for s in self.program.operations[name].statements
            if s.kind in ("call", "run")
        ]

    def reaches(self, start: str, target: str) -> bool:
        """Return whether an execution in `start` leads, through others, to `target`."""
        seen: set[str] = set()
        stack = self.executed(start)
        while stack:
            name = stack.pop()
            if name == target:
                return True
            if name not in seen:
                seen.add(name)
                stack.extend(self.executed(name))
        return False

    def cycle(self, op: Operation) -> list[int]:
        """Return the values of the executions that lead back to the operation."""
        return [
            self.first_value(op, i)
            for i, s in enumerate(op.statements)
            if s.kind in ("call", "run")
            and (s.name == op.name or self.reaches(str(s.name), op.name))
        ]

    def reaches_cycle(self, name: str) -> bool:
        """Return whether the operation is in a cycle or executes one in."""
        seen: set[str] = set()
        stack = [name]
        while stack:
            current = stack.pop()
            if current not in seen:
                seen.add(current)
                if self.reaches(current, current):
                    return True
                stack.extend(self.executed(current))
        return False

    def dead(self, op: Operation) -> list[int]:
        """Return the values of the boolean statements no exit reads, in order."""
        alive = self.live(op, None, [])
        return [
            self.first_value(op, i)
            for i, s in enumerate(op.statements)
            if s.kind in BOOLEAN_STATEMENTS and i not in alive
        ]

    def unused_views(self, op: Operation) -> list[int]:
        """Return the read views the written view doesn't depend on, from 1."""
        views = op.boolean_views
        mask = (1 << (1 << views)) - 1
        base = projections(views)
        function = self.call(op.name, base, mask)
        out = []
        for i in range(views):
            flipped = list(base)
            flipped[i] ^= mask
            if self.call(op.name, flipped, mask) == function:
                out.append(i + 1)
        return out

    def order_arguments(self, op: Operation, boolean: list[int]) -> int | None:
        """Return the first boolean statement whose groups aren't in rank order."""
        for i in boolean:
            statement = op.statements[i]
            name = statement.name if statement.kind == "call" else statement.kind
            assert name is not None  # noqa: S101 - A `call` names its operation.
            for group in self.groups(name):
                values = [statement.args[k] for k in group]
                for x, y in itertools.pairwise(values):
                    if self.rank_compare(op, x, y) > 0:
                        return self.first_value(op, i)
        return None

    def order_statements(self, op: Operation) -> int | None:
        """Return the first position where the order differs from DLP 59's."""
        placed: set[int] = set()
        canonical: list[int] = []

        def visit(arg: int | str) -> None:
            arg = self.resolve(op, arg)
            if not self.is_boolean_statement_value(op, arg):
                return
            index = op.origins[arg][1]  # type: ignore[index]
            if index in placed:
                return
            placed.add(index)
            for a in op.statements[index].args:
                visit(a)
            canonical.append(index)

        for index, statement in enumerate(op.statements):
            if statement.kind in NOT_BOOLEAN_STATEMENTS:
                for a in statement.args:
                    visit(a)
                canonical.append(index)
        for out in op.outputs:
            visit(out)
        actual = [i for i, s in enumerate(op.statements) if s.kind != "copy"]
        for position, (x, y) in enumerate(zip(actual, canonical, strict=False)):
            if x != y:
                return position
        if len(actual) != len(canonical):
            return min(len(actual), len(canonical))
        return None

    def redundant(
        self,
        op: Operation,
        boolean: list[int],
        inputs: list[int],
        tables: dict[int, int],
        mask: int,
    ) -> list[object] | None:
        """Return the first redundant value, how, and what it's compared with."""
        earlier = list(inputs)
        for i in boolean:
            value = self.first_value(op, i)
            t = tables[value]
            if t in (0, mask):
                return [value, "constant", "T" if t else "F"]
            same = [u for u in earlier if tables[u] == t]
            if same:
                return [value, "same", same[0]]
            statement = op.statements[i]
            for u in earlier:
                if tables[u] != t ^ mask:
                    continue
                if statement.kind == "not" and self.resolve(op, statement.args[0]) == u:
                    continue
                return [value, "opposite", u]
            earlier.append(value)
        return None

    def available(
        self, op: Operation, boolean: list[int], inputs: list[int]
    ) -> dict[int, list[int]]:
        """Return, for each boolean statement's value, the values before it."""
        out = {}
        before = list(range(1, op.boolean_views + 1))
        for value, origin in sorted(op.origins.items()):
            if origin[0] != "statement":
                continue
            if origin[1] in boolean:
                out[value] = list(before)
                before.append(value)
            elif value in inputs:
                before.append(value)
        return out

    def match(self, context: Context, boolean: list[int]) -> list[object] | None:
        """Return the match the compiler reports, or None."""
        op = context.op
        follows = self.follows(op)
        best = None
        for i in boolean:
            value = self.first_value(op, i)
            for name in follows:
                for opposite in (False, True):
                    if opposite and self.opposite_registered(name, follows):
                        continue
                    target = context.tables[value] ^ (context.mask if opposite else 0)
                    for args in self.search(context, value, name, target):
                        if self.is_execution(op, value, name, args, opposite=opposite):
                            continue
                        removed = self.removed(op, value, args)
                        if removed < 2 + int(opposite):
                            continue
                        args = self.canonical_arguments(op, name, args)
                        candidate = (
                            removed,
                            value,
                            follows.index(name),
                            args,
                            opposite,
                        )
                        if best is None or self.better_match(op, candidate, best):
                            best = candidate
        if best is None:
            return None
        removed, value, place, args, opposite = best
        name = follows[place]
        return [value, "not:" + name if opposite else name, removed, args]

    def better_match(self, op: Operation, a: tuple, b: tuple) -> bool:
        """Return whether match a is reported before match b."""
        if a[0] != b[0]:
            return a[0] > b[0]
        if a[1] != b[1]:
            return a[1] < b[1]
        if a[2] != b[2]:
            return a[2] < b[2]
        return self.compare_lists(op, a[3], b[3]) < 0

    def spelling(self, context: Context, boolean: list[int]) -> list[object] | None:
        """Return the first value with a spelling that comes first, and that spelling."""
        op = context.op
        follows = self.follows(op)
        for i in boolean:
            statement = op.statements[i]
            # Every execution of a registered operation, `and` included, is
            # a spelling. A `not` isn't respelled: a value that's the `not`
            # of another is written as that `not` (DLP 58's opposite values).
            if statement.kind == "not":
                continue
            name_of = (
                statement.kind if statement.kind in ("and", "not") else statement.name
            )
            if name_of not in follows:
                continue
            current_args = [self.resolve(op, a) for a in statement.args]
            # An execution given a literal is DLP 58's error, not a spelling.
            if any(isinstance(a, str) for a in current_args):
                continue
            value = self.first_value(op, i)
            current = (
                name_of,
                self.canonical_arguments(op, name_of, current_args),
            )  # type: ignore[arg-type]
            best = current
            for name in follows:
                for args in self.search(context, value, name, context.tables[value]):
                    candidate = (name, self.canonical_arguments(op, name, args))
                    if self.spelling_compare(op, follows, candidate, best) < 0:
                        best = candidate
            if best != current:
                return [value, best[0], best[1]]
        return None

    def spelling_compare(
        self, op: Operation, follows: list[str], a: tuple, b: tuple
    ) -> int:
        """Compare two spellings by DLP 60's precedence."""
        ka = (self.negations(op, a[1]), follows.index(a[0]))
        kb = (self.negations(op, b[1]), follows.index(b[0]))
        if ka != kb:
            return -1 if ka < kb else 1
        return self.compare_lists(op, a[1], b[1])

    def negations(self, op: Operation, args: list[int]) -> int:
        """Return how many arguments are the value of a `not` statement."""
        count = 0
        for a in args:
            statement = self.statement_of(op, a)
            count += statement is not None and statement.kind == "not"
        return count

    def opposite_registered(self, name: str, follows: list[str]) -> bool:
        """Return whether an operation that's followed computes R's opposite."""
        key = (name, tuple(follows))
        if key not in self.opposite_memo:
            self.opposite_memo[key] = self.find_opposite(name, follows)
        return self.opposite_memo[key]

    def find_opposite(self, name: str, follows: list[str]) -> bool:
        """Return whether a followed operation computes R's opposite, by trying all."""
        views = self.arity(name)
        mask = (1 << (1 << views)) - 1
        opposite = self.own_function(name) ^ mask
        base = projections(views)
        for other in follows:
            if self.arity(other) != views:
                continue
            for order in itertools.permutations(base):
                if compose(self.own_function(other), list(order), mask) == opposite:
                    return True
        return False

    def is_execution(
        self, op: Operation, value: int, name: str, args: list[int], *, opposite: bool
    ) -> bool:
        """Return whether the value is already an execution of R on these arguments."""
        statement = self.statement_of(op, value)
        assert statement is not None  # noqa: S101 - Matches are statement values.
        if opposite:
            if statement.kind != "not":
                return False
            inner = self.resolve(op, statement.args[0])
            if not isinstance(inner, int) or self.statement_of(op, inner) is None:
                return False
            statement = self.statement_of(op, inner)
            assert statement is not None  # noqa: S101 - Checked above.
        if (
            statement.kind if statement.kind in ("and", "not") else statement.name
        ) != name:
            return False
        return sorted(self.resolve(op, a) for a in statement.args) == sorted(args)  # type: ignore[type-var]

    def live(self, op: Operation, replaced: int | None, args: list[int]) -> set[int]:
        """Return the boolean statements an exit reads, with one value's arguments replaced."""
        alive: set[int] = set()
        stack: list[int | str] = []
        for statement in op.statements:
            if statement.kind in NOT_BOOLEAN_STATEMENTS:
                stack.extend(statement.args)
        stack.extend(op.outputs)
        while stack:
            arg = self.resolve(op, stack.pop())
            if not self.is_boolean_statement_value(op, arg):
                continue
            index = op.origins[arg][1]  # type: ignore[index]
            if index in alive:
                continue
            alive.add(index)
            stack.extend(args if arg == replaced else op.statements[index].args)
        return alive

    def removed(self, op: Operation, value: int, args: list[int]) -> int:
        """Return how many statements computing v from these arguments removes."""
        before = self.live(op, None, [])
        after = self.live(op, value, args)
        own = op.origins[value][1]
        return 1 + sum(1 for i in before if i not in after and i != own)

    def search(
        self, context: Context, value: int, name: str, target: int
    ) -> list[list[int]]:
        """Return every tuple of distinct values before v with R of them always the target.

        Every argument must matter. The search gives values to R's views in
        order and drops a partial tuple when, on a fixed sample of input
        assignments, no values of the remaining views could give the target:
        a necessary condition, so nothing is missed.
        """
        k = self.arity(name)
        function = self.own_function(name)
        possible = possible_outputs(function, k)
        values = context.before[value]
        out = []
        sample_target = context.sample(target)
        full_sample = (1 << SAMPLES) - 1

        def extend(chosen: list[int]) -> None:
            j = len(chosen)
            for c in range(1 << j):
                positions = full_sample
                for i, a in enumerate(chosen):
                    bits = context.sample(context.tables[a])
                    positions &= bits if (c >> i) & 1 else bits ^ full_sample
                if positions & sample_target and 1 not in possible[j][c]:
                    return
                if positions & ~sample_target & full_sample and 0 not in possible[j][c]:
                    return
            if j == k:
                tables = [context.tables[a] for a in chosen]
                if compose(function, tables, context.mask) == target and all_matter(
                    function, tables, context.mask
                ):
                    out.append(list(chosen))
                return
            for a in values:
                if a not in chosen:
                    extend([*chosen, a])

        extend([])
        return out


@dataclass
class Context:
    """One operation's functions, for the search for matches and spellings."""

    op: Operation
    tables: dict[int, int]
    mask: int
    inputs: int
    before: dict[int, list[int]]
    minterms: list[int] = field(default_factory=list)
    samples: dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Pick the sampled input assignments."""
        rng = random.Random(11)  # noqa: S311 - A fixed sample, not security.
        self.minterms = [rng.randrange(1 << self.inputs) for _ in range(SAMPLES)]

    def sample(self, table: int) -> int:
        """Return a function's bits on the sampled assignments."""
        if table not in self.samples:
            self.samples[table] = self.sample_bits(table)
        return self.samples[table]

    def sample_bits(self, table: int) -> int:
        """Return a function's bits on the sampled assignments, computed."""
        out = 0
        for i, m in enumerate(self.minterms):
            out |= ((table >> m) & 1) << i
        return out


def operation_name(statement: Statement) -> str:
    """Return the full name of what a statement executes, for ranks."""
    if statement.kind in ("and", "not"):
        return "standard:/boolean/" + statement.kind
    assert statement.name is not None  # noqa: S101 - Every other statement names one.
    return statement.name


MIN_ANDS = {
    row["class"]: row["ands"]
    for row in json.loads(
        (Path(__file__).parent.parent / "results" / "min_ands.json").read_text()
    )
}


@functools.cache
def npn_class(table: int) -> int:
    """Return a four-view function's smallest truth table under NPN."""
    best = 0xFFFF
    for perm in itertools.permutations(range(4)):
        for flips in range(16):
            out = 0
            for row in range(16):
                source = sum(1 << perm[i] for i in range(4) if (row >> i) & 1) ^ flips
                out |= ((table >> source) & 1) << row
            best = min(best, out, out ^ 0xFFFF)
    return best


def fewest_ands(table: int, views: int) -> int:
    """Return the fewest `and`s computing a function of up to four views.

    The counts are min_ands_experiment.py's, by NPN class.
    """
    wide = 0
    for row in range(16):
        wide |= ((table >> (row & ((1 << views) - 1))) & 1) << row
    return MIN_ANDS[npn_class(wide)]


def projections(count: int) -> list[int]:
    """Return the function of each of `count` independent inputs."""
    out = []
    for i in range(count):
        t = 0
        for m in range(1 << count):
            if (m >> i) & 1:
                t |= 1 << m
        out.append(t)
    return out


def find(parent: list[int], i: int) -> int:
    """Return the root of i in a union-find forest."""
    while parent[i] != i:
        i = parent[i]
    return i


def compose(function: int, tables: list[int], mask: int) -> int:
    """Return an operation's function applied to its arguments' functions."""
    out = 0
    for c in range(1 << len(tables)):
        if not (function >> c) & 1:
            continue
        term = mask
        for i, t in enumerate(tables):
            term &= t if (c >> i) & 1 else t ^ mask
        out |= term
    return out


def all_matter(function: int, tables: list[int], mask: int) -> bool:
    """Return whether changing each argument changes the result somewhere."""
    result = compose(function, tables, mask)
    for i, t in enumerate(tables):
        flipped = list(tables)
        flipped[i] = t ^ mask
        if compose(function, flipped, mask) == result:
            return False
    return True


def possible_outputs(function: int, k: int) -> list[list[set[int]]]:
    """Return, for each j and each assignment c of views 0..j-1, R's possible results."""
    out = []
    for j in range(k + 1):
        row = []
        for c in range(1 << j):
            results = set()
            for rest in range(1 << (k - j)):
                results.add((function >> (c | (rest << j))) & 1)
            row.append(results)
        out.append(row)
    return out


def check_program(text: str) -> list[dict[str, object]]:
    """Check every operation of a program.

    Each result is {"op": NAME, "errors": {RULE: DETAIL}} with only the
    rules violated. Details: `limits` "statements" or "inputs"; `literal`
    the statement's index; `wrapper` true; `redundant` [value, "constant",
    "T"/"F"] or [value, "same"/"opposite", other value]; `order_arguments`
    the statement's value; `cycle` the values of the executions that lead
    back to the operation (DLP 9); `order_statements` the first differing position
    among statements other than `copy`; `match` [value, R or "not:R",
    statements removed, arguments]; `spelling` [value, R, arguments], with
    arguments in R's view order and each group of R's interchangeable views
    in rank order. Matches and spellings are only looked for when there's
    no redundant value.
    """
    program = parse(text)
    checker = Checker(program)
    out: list[dict[str, object]] = []
    for op in program.operations.values():
        out.append({"op": op.name, "errors": checker.check(op)})
    return out


OR = "op or bool 2\nnot 1\nnot 2\nand 3 4\nnot 5\nout 6\nend\n"
IMPLIES = "op implies bool 2\nnot 2\nand 1 3\nnot 4\nout 5\nend\n"
SELF_TESTS: list[tuple[str, dict[str, dict[str, object]]]] = [
    (
        "registered or\n" + OR + "op f bool 3\ncall or 1 2\nand 3 4\nout 5\nend\n",
        {"or": {}, "f": {}},
    ),
    (
        "registered or\n" + OR + "op w bool 2\ncall or 1 2\nout 3\nend\n",
        {"or": {}, "w": {"wrapper": True}},
    ),
    (
        "registered or\n" + OR + "op l bool 1\nand 1 T\nout 2\nend\n",
        {"or": {}, "l": {"literal": 0, "wrapper": True, "redundant": [2, "same", 1]}},
    ),
    (
        "registered or\n"
        + OR
        + "op m bool 2\nnot 1\nnot 2\nand 3 4\nnot 5\nout 6\nend\n",
        {"or": {}, "m": {"match": [6, "or", 4, [1, 2]]}},
    ),
    (
        "registered or\n"
        + OR
        + "op o mixed 2 0\nand 1 2\nnot 1\nnot 2\ncall or 4 5\nnum f 3 6\nout 7\nend\n",
        {"or": {}, "o": {"redundant": [6, "opposite", 3]}},
    ),
    (
        "registered or\n"
        + OR
        + "op g bool 3\nand 1 2\ncall or 3 4\nout 5\nend\n"
        + "op h bool 3\ncall g 2 1 3\nout 4\nend\n"
        + "op c bool 2\ncopy 1\ncall g 1 3 2\nout 4\nend\n",
        {"or": {}, "g": {}, "h": {"order_arguments": 4}, "c": {}},
    ),
    (
        "registered or\n"
        + OR
        + "op inner mixed 0 2\ncmp lt 1 2\nnum add 1 2\nout 3 4\nend\n"
        + "op outer mixed 1 1\nrun inner 2 #3\nand 1 3\nnum sel 5 4\nout 6\nend\n",
        {"or": {}, "inner": {}, "outer": {}},
    ),
    (
        "registered or\n" + OR + "op s bool 2\nnot 2\nnot 1\nand 4 3\nout 5\nend\n",
        {"or": {}, "s": {"order_statements": 0, "match": [5, "not:or", 3, [1, 2]]}},
    ),
    (
        "registered or implies\n"
        + IMPLIES
        + "op or bool 2\nnot 1\ncall implies 3 2\nout 4\nend\n"
        + "op sp bool 2\nnot 2\ncall or 1 3\nout 4\nend\n",
        {
            # `implies` has the smaller key (the same `and`s and views, a
            # smaller truth table), so `or`'s definition follows it.
            "or": {},
            "implies": {},
            "sp": {
                "match": [4, "implies", 2, [2, 1]],
                "spelling": [4, "implies", [2, 1]],
            },
        },
    ),
    (
        "registered or\n" + OR + "op d bool 2\nand 1 2\nnot 1\nout 3\nend\n",
        {"or": {}, "d": {"dead": [4], "order_statements": 1}},
    ),
    (
        "registered or\n" + OR + "op u bool 3\nand 1 2\nnot 4\nout 5\nend\n",
        {"or": {}, "u": {"unused_view": [3]}},
    ),
    (
        # `eq` and `xor` execute each other, and `f` executes them.
        "registered xor eq\n"
        + OR
        + "op eq bool 2\ncall xor 1 2\nnot 3\nout 4\nend\n"
        + "op xor bool 2\ncall eq 1 2\nnot 3\nout 4\nend\n"
        + "op f bool 3\ncall eq 1 2\nand 3 4\nout 5\nend\n",
        {"or": {}, "eq": {"cycle": [3]}, "xor": {"cycle": [3]}, "f": {}},
    ),
    (
        # `U` written out is a match for `maj`, whose definition executes
        # `U`: fixing it the obvious way would make a cycle.
        "registered maj\n"
        + "op U bool 4\nand 1 2\nnot 1\nnot 2\nand 6 7\nnot 8\nand 3 9\nnot 5\nnot 10\nand 11 12\nnot 13\nand 14 4\nout 15\nend\n"
        + "op maj bool 3\nnot 1\nnot 2\nand 4 5\nnot 6\ncall U 1 2 3 7\nout 8\nend\n",
        {
            "U": {
                "order_arguments": 15,
                "order_statements": 1,
                "match": [14, "maj", 10, [1, 2, 3]],
            },
            "maj": {},
        },
    ),
    (
        "registered or mux\n"
        + OR
        + "op mux bool 3\nand 1 2\nnot 1\nand 3 5\ncall or 4 6\nout 7\nend\n"
        + "op f bool 3\ncall mux 1 T 2\nand 4 3\nout 5\nend\n",
        # An execution given a literal isn't a spelling.
        {"or": {}, "mux": {}, "f": {"literal": 0, "order_arguments": 5}},
    ),
    (
        "registered or\n" + OR + "op x bool 21\nand 1 2\nout 22\nend\n",
        {"or": {}, "x": {"limits": "inputs", "wrapper": True}},
    ),
]


def self_test() -> bool:
    """Check the hand-written programs; print each difference."""
    ok = True
    for text, expected in SELF_TESTS:
        for result in check_program(text):
            want = expected[result["op"]]  # type: ignore[index]
            if result["errors"] != want:
                ok = False
                print(f"{result['op']}: got {result['errors']}, expected {want}")
    print("self-test", "passed" if ok else "failed")
    return ok


def main() -> None:
    """Check a program file, or run the self-test."""
    if sys.argv[1] == "--self-test":
        sys.exit(0 if self_test() else 1)
    with open(sys.argv[1], encoding="ascii") as f:
        for result in check_program(f.read()):
            print(json.dumps(result))


if __name__ == "__main__":
    main()
