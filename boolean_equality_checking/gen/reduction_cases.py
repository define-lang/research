"""Reduction cases: value operations and what fixing them reduces them to.

Writes `~/projects/define/drafts/boolean-reduction-cases.txt` (its header
explains the line format) from the cases below, each reduced by `beq
program --mode fix`, and checks every line: the expected program compiles
under `beq` and under the independent checker (`program_check.py`), fixing
it again changes nothing, and reading the line back gives the same case.

Run with `uv run --frozen --python 3.14 python gen/reduction_cases.py OUT`
from the study's directory.
"""

from __future__ import annotations

import json
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import program
import program_check

HERE = Path(__file__).resolve().parent.parent
BEQ = HERE / "src" / "beq"
LIMIT = ["timeout", "-s", "KILL", "60", "prlimit", f"--as={4 << 30}"]

# The library every case starts from: the registered operations'
# definitions (gen/program.py), which every case has whether or not its
# booleans.defcl registers them.
LIBRARY = [
    "\n".join([f"op {name} bool {views}", *statements, f"out {out}", "end"])
    for name, (views, statements, out) in program.DEFINITIONS.items()
]
LIBRARY_NAMES = list(program.DEFINITIONS)

HEADER = """\
# Boolean reduction cases: a program, and the program it reduces to once
# every fix of DLPs 58-60 is applied (DLP 58's refactoring steps, DLP 59's
# order, DLP 60's matches, spellings, and wrappers), as the research
# repository's fix loop applies them: one reported error at a time, the
# first redundant value before the largest match, each match with its first
# spelling, until the program compiles.
#
# One case per line:
#
#     [REGISTERED] PROGRAM => REDUCED
#
# REGISTERED is booleans.defcl, in order. `and` and `not` are registered
# for every value operation without being listed, and come first (DLP 60).
# Every case also has the library of `or`, `implies`, `xor`, `eq`, `mux`,
# and `maj`, defined as the fixes leave them when they're registered in
# that order, each following `and`, `not`, and the ones before it: `or` is
# `not (not a and not b)`, `implies` is `not (a and not b)`, `xor` is
# `or(a and not b, not a and b)`, `eq` is `not xor(a, b)`, `mux` is
# `or(s and a, b and not s)`, and `maj` is `mux(c, or(a, b), a and b)`.
# They're in every case whether or not they're registered; an unregistered
# one is executed like any value operation.
#
# PROGRAM is one or more value operations separated by ` ;; `, each after
# the ones it executes:
#
#     NAME(VIEW, ...) = BODY
#
# The names in parentheses are the read views: the boolean inputs. A view
# written `x: number` is numeric (numeric views come after boolean ones),
# which makes the operation mixed. BODY is `let NAME = EXPR;` statements,
# then the written view's EXPR, or `(EXPR, EXPR, ...)` for a mixed
# operation's written views. In EXPR:
#
# - `a and b`, `not a`: the logical operations (`not` binds tighter);
# - `R(a, ...)`: an execution of the value operation R;
# - `true`, `false`: boolean literals; a bare number is a numeric literal;
# - `cmp.NAME(...)`: a comparison, a statement that isn't boolean and
#   gives a boolean input; `num.NAME(...)`: a numeric statement;
# - `let (p, q) = M(...)`: an execution of a mixed operation M, one name
#   per written view.
#
# Every operator and execution is one statement. A value used more than
# once is a `let`; a value used once is written where it's used. A boolean
# `let`'s statements come right before its first use, so the statement
# order is DLP 59's: each boolean statement right before the statement that
# first reads it, in view order, and the written views' last. A `let` of a
# statement that isn't boolean stays where it is. A `let` nothing reads is
# still a statement: a dead one, written after the written views'. A name
# given to two views of one execution stands for the value and a copy of
# it (DLP 55).
#
# REDUCED is the program after every fix, in the same form, in DLP 59's
# statement and argument order. It also shows each registered library
# operation whose definition the fixes changed: another order in
# booleans.defcl changes what it has to be, and when a match's fix would
# make an execution cycle (DLP 9), because the registered operation's
# definition executes the value operation the match is in, the executions
# that lead back are written out in that definition first.
# `removed NAME = EXPR` means a fix removed
# the operation, and its callers compute EXPR (over its views) instead: a
# wrapper (EXPR is the statement it wraps, DLP 60), or an operation whose
# written view is a constant or one of its views (DLP 58's refactoring step
# 4). `removed NAME view K = EXPR` is the same for one written view of a
# mixed operation. `dropped NAME VIEW, ...` means those read views didn't
# matter (DLP 58), so they're gone from the operation and from every
# execution of it, which shows NAME's remaining views. Dead statements are
# gone too. `error limits` instead means the fixes can't make the
# program compile: it has more than 256 boolean statements or 20 boolean
# inputs.
#
# Every line was produced by the research repository's
# boolean_equality_checking/gen/reduction_cases.py (the long ones from
# gen/program.py's generator) and checked: REDUCED compiles under `beq`
# and under the independent checker (gen/program_check.py), and fixing it
# again changes nothing. The independent checker tries every tuple of
# arguments, which is too slow past 12 inputs or about 150 statements, so
# the one REDUCED program that large (255 statements at 20 inputs) is
# checked by `beq` with truth tables and with SAT sweeping instead.
"""


# Parsing the expression form into gen/program.py's format.


@dataclass
class Op:
    """One value operation being translated."""

    name: str
    bool_views: list[str]
    num_views: list[str]
    lines: list[str] = field(default_factory=list)
    names: dict[str, int] = field(default_factory=dict)
    kinds: dict[int, str] = field(default_factory=dict)
    next: int = 1
    outs: list[str] = field(default_factory=list)

    def value(self, kind: str) -> int:
        """Return the next value's number."""
        v = self.next
        self.next += 1
        self.kinds[v] = kind
        return v


TOKEN = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_.]*|\d+|[(),=;:])")


def tokens(text: str) -> list[str]:
    """Split an expression into tokens."""
    out = []
    pos = 0
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError(f"can't read {text[pos:]!r}")
        out.append(m.group(1))
        pos = m.end()
    return out


class Parser:
    """Reads one value operation's body into statements.

    Expressions are read into trees first. A boolean `let`'s statements are
    written at its first use, so every boolean statement comes right before
    the statement that first reads it, in view order: DLP 59's order. A
    `let` of a statement that isn't boolean is written where it stands.
    """

    def __init__(self, op: Op, outputs: dict[str, list[bool]]) -> None:
        """Parse into `op`; `outputs` gives each mixed operation's written views."""
        self.op = op
        self.outputs = outputs
        self.toks: list[str] = []
        self.i = 0
        self.lazy: dict[str, tuple] = {}

    def peek(self) -> str:
        """Return the next token, or ''."""
        return self.toks[self.i] if self.i < len(self.toks) else ""

    def take(self, expected: str | None = None) -> str:
        """Consume a token."""
        t = self.peek()
        if expected is not None and t != expected:
            raise ValueError(f"expected {expected!r}, got {t!r} in {self.op.name}")
        self.i += 1
        return t

    def body(self, text: str) -> None:
        """Parse `let` statements and the written views."""
        self.toks = tokens(text)
        while self.peek() == "let":
            self.take()
            if self.peek() == "(":
                self.take()
                names = [self.take()]
                while self.peek() == ",":
                    self.take()
                    names.append(self.take())
                self.take(")")
                self.take("=")
                callee = self.take()
                args = [self.emit(a) for a in self.args()]
                self.op.lines.append(f"run {callee} " + " ".join(args))
                for name, boolean in zip(names, self.outputs[callee], strict=True):
                    self.op.names[name] = self.op.value("b" if boolean else "n")
            else:
                name = self.take()
                self.take("=")
                tree = self.expr()
                if tree[0] in ("cmp", "num"):
                    self.op.names[name] = int(self.emit(tree))
                else:
                    self.lazy[name] = tree
            self.take(";")
        if self.peek() == "(" and self.op.num_views:
            self.take()
            trees = [self.expr()]
            while self.peek() == ",":
                self.take()
                trees.append(self.expr())
            self.take(")")
        else:
            trees = [self.expr()]
        self.op.outs = [self.emit(t) for t in trees]
        # A `let` nothing read is a dead statement.
        for name in list(self.lazy):
            self.emit(("name", name))
        if self.peek():
            raise ValueError(f"unexpected {self.peek()!r} in {self.op.name}")

    def emit(self, tree: tuple) -> str:
        """Write an expression's statements; return its value as an argument."""
        kind = tree[0]
        if kind == "lit":
            return tree[1]
        if kind == "name":
            name = tree[1]
            if name in self.lazy:
                self.op.names[name] = int(self.emit(self.lazy.pop(name)))
            if name not in self.op.names:
                raise ValueError(f"unknown name {name!r} in {self.op.name}")
            return str(self.op.names[name])
        if kind == "and":
            left, right = self.emit(tree[1]), self.emit(tree[2])
            self.op.lines.append(f"and {left} {right}")
            return str(self.op.value("b"))
        if kind == "not":
            x = self.emit(tree[1])
            self.op.lines.append(f"not {x}")
            return str(self.op.value("b"))
        args = [self.emit(a) for a in tree[2]]
        if kind == "cmp":
            self.op.lines.append(f"cmp {tree[1]} " + " ".join(args))
            return str(self.op.value("b"))
        if kind == "num":
            self.op.lines.append(f"num {tree[1]} " + " ".join(args))
            return str(self.op.value("n"))
        # A value given to two views goes to the second through a copy.
        seen: set[str] = set()
        final = []
        for a in args:
            if a in seen and not a.startswith(("#", "T", "F")):
                self.op.lines.append(f"copy {a}")
                a = str(self.op.value(self.op.kinds.get(int(a), "b")))
            seen.add(a)
            final.append(a)
        self.op.lines.append(f"call {tree[1]} " + " ".join(final))
        return str(self.op.value("b"))

    def expr(self) -> tuple:
        """Parse `a and b and ...` into a tree."""
        left = self.unary()
        while self.peek() == "and":
            self.take()
            left = ("and", left, self.unary())
        return left

    def unary(self) -> tuple:
        """Parse `not x`, an execution, a name, a literal, or parentheses."""
        t = self.peek()
        if t == "not":
            self.take()
            return ("not", self.unary())
        if t == "(":
            self.take()
            x = self.expr()
            self.take(")")
            return x
        self.take()
        if t in ("true", "false"):
            return ("lit", "T" if t == "true" else "F")
        if t.isdigit():
            return ("lit", "#" + t)
        if self.peek() == "(":
            args = self.args()
            if t.startswith("cmp."):
                return ("cmp", t[4:], args)
            if t.startswith("num."):
                return ("num", t[4:], args)
            return ("call", t, args)
        return ("name", t)

    def args(self) -> list[tuple]:
        """Parse `(e, e, ...)`."""
        self.take("(")
        out = [self.expr()]
        while self.peek() == ",":
            self.take()
            out.append(self.expr())
        self.take(")")
        return out


def view_names_of(text: str) -> dict[str, list[str]]:
    """Return each operation's read view names in a PROGRAM."""
    out = {}
    for part in text.split(" ;; "):
        if part.startswith(("removed ", "dropped ")):
            continue
        head = part.split(" = ", 1)[0]
        name, views = re.fullmatch(r"\s*(\w+)\((.*)\)\s*", head).groups()  # type: ignore[union-attr]
        out[name] = [v.split(":")[0].strip() for v in views.split(",") if v.strip()]
    return out


def parse_program(text: str) -> tuple[list[str], dict[str, list[bool]]]:
    """Return the operations of a PROGRAM in gen/program.py's format."""
    blocks = []
    outputs: dict[str, list[bool]] = {}
    for part in text.split(" ;; "):
        if part.startswith(("removed ", "dropped ")):
            continue
        head, body = part.split(" = ", 1)
        name, views = re.fullmatch(r"\s*(\w+)\((.*)\)\s*", head).groups()  # type: ignore[union-attr]
        bool_views, num_views = [], []
        for v in (x.strip() for x in views.split(",") if x.strip()):
            if v.endswith(": number"):
                num_views.append(v.split(":")[0].strip())
            else:
                bool_views.append(v)
        op = Op(name, bool_views, num_views)
        for v in bool_views:
            op.names[v] = op.value("b")
        for v in num_views:
            op.names[v] = op.value("n")
        Parser(op, outputs).body(body)
        kind = (
            f"mixed {len(bool_views)} {len(num_views)}"
            if num_views
            else f"bool {len(bool_views)}"
        )
        blocks.append(
            "\n".join(
                [f"op {name} {kind}", *op.lines, "out " + " ".join(op.outs), "end"]
            )
        )
        if num_views:
            outputs[name] = [
                not o.startswith("#")
                and op.kinds.get(int(o) if o.isdigit() else 0, "b") == "b"
                for o in op.outs
            ]
    return blocks, outputs


# Writing gen/program.py's format back in the expression form.


def render_program(
    text: str, names: list[str], views: dict[str, list[str]] | None = None
) -> str:
    """Return the named operations of a program file, in the expression form."""
    ops = read_ops(text)
    out = []
    for name in names:
        if name in ops:
            out.append(render_op(ops[name], ops, (views or {}).get(name)))
    return " ;; ".join(out)


def read_ops(text: str) -> dict[str, dict]:
    """Read a program file into operations, in order."""
    ops: dict[str, dict] = {}
    cur: dict | None = None
    for line in text.splitlines():
        w = line.split()
        if not w or w[0] == "registered":
            continue
        if w[0] == "op":
            cur = {"name": w[1], "mixed": w[2] == "mixed", "stmts": [], "outs": []}
            cur["nbool"] = int(w[3])
            cur["nnum"] = int(w[4]) if w[2] == "mixed" else 0
            ops[w[1]] = cur
        elif w[0] == "out":
            cur["outs"] = w[1:]  # type: ignore[index]
        elif w[0] == "end":
            cur = None
        else:
            cur["stmts"].append(w)  # type: ignore[index]
    return ops


def render_op(op: dict, ops: dict[str, dict], names: list[str] | None = None) -> str:
    """Return one operation in the expression form."""
    nbool, nnum = op["nbool"], op["nnum"]
    letters = "abcdefghijklmnopqrstuvwxyz"
    view_names = names or [view_name(i, letters) for i in range(nbool + nnum)]
    # Value numbers: views, then each statement's values.
    source: dict[int, int] = {}
    v = nbool + nnum + 1
    for s in op["stmts"]:
        count = len(ops[s[1]]["outs"]) if s[0] == "run" else 1
        for _ in range(count):
            if s[0] == "copy":
                source[v] = int(s[1])
            v += 1
    reads: dict[int, int] = {}

    def resolve(a: str) -> str:
        if a.isdigit() and int(a) in source:
            return str(source[int(a)])
        return a

    for s in op["stmts"]:
        if s[0] == "copy":
            continue
        args = s[2:] if s[0] in ("call", "run", "cmp", "num") else s[1:]
        for a in args:
            a = resolve(a)
            if a.isdigit():
                reads[int(a)] = reads.get(int(a), 0) + 1
    for o in op["outs"]:
        o = resolve(o)
        if o.isdigit():
            reads[int(o)] = reads.get(int(o), 0) + 1
    text_of: dict[int, str] = {}
    # An `and` written in place needs parentheses as an operand.
    operand_of: dict[int, str] = {}
    lets: list[str] = []
    let_count = 0
    v = nbool + nnum + 1
    for s in op["stmts"]:
        if s[0] == "copy":
            v += 1
            continue
        if s[0] == "run":
            names = []
            for _ in ops[s[1]]["outs"]:
                let_count += 1
                text_of[v] = f"t{let_count}"
                names.append(text_of[v])
                v += 1
            args = ", ".join(arg_text(resolve(a), text_of, view_names) for a in s[2:])
            lets.append(f"let ({', '.join(names)}) = {s[1]}({args})")
            continue
        if s[0] == "and":
            e = f"{arg_text(resolve(s[1]), _operand(text_of, operand_of), view_names)} and {arg_text(resolve(s[2]), _operand(text_of, operand_of), view_names)}"
        elif s[0] == "not":
            e = f"not {arg_text(resolve(s[1]), _operand(text_of, operand_of), view_names)}"
        else:
            prefix = {"call": "", "cmp": "cmp.", "num": "num."}[s[0]]
            args = ", ".join(arg_text(resolve(a), text_of, view_names) for a in s[2:])
            e = f"{prefix}{s[1]}({args})"
        # Statements that aren't boolean keep their place: always a let.
        if reads.get(v, 0) == 1 and s[0] not in ("cmp", "num"):
            text_of[v] = e
            if s[0] == "and":
                operand_of[v] = f"({e})"
        else:
            let_count += 1
            name = f"t{let_count}"
            lets.append(f"let {name} = {e}")
            text_of[v] = name
        v += 1
    outs = [arg_text(resolve(o), text_of, view_names) for o in op["outs"]]
    views = view_names[:nbool] + [f"{n}: number" for n in view_names[nbool:]]
    result = outs[0] if not op["mixed"] else "(" + ", ".join(outs) + ")"
    body = "".join(f"{x}; " for x in lets) + result
    return f"{op['name']}({', '.join(views)}) = {body}"


def view_name(i: int, letters: str) -> str:
    """Return the i-th read view's name: a ... z, then a1, b1, ..."""
    return letters[i % 26] + (str(i // 26) if i >= 26 else "")


def _operand(text_of: dict[int, str], operand_of: dict[int, str]) -> dict[int, str]:
    """Return each value's text as an operand of `and` or `not`."""
    return {**text_of, **operand_of}


def arg_text(a: str, text_of: dict[int, str], view_names: list[str]) -> str:
    """Return an argument as text."""
    if a == "T":
        return "true"
    if a == "F":
        return "false"
    if a.startswith("#"):
        return a[1:]
    n = int(a)
    if n <= len(view_names):
        return view_names[n - 1]
    return text_of[n]


# Reducing a case with beq.


def run_beq(path: Path, *args: str) -> dict:
    """Run `beq program` under the caps; return its last JSON line."""
    done = subprocess.run(  # noqa: S603 - This directory's own beq.
        [*LIMIT, str(BEQ), "program", str(path), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(done.stdout.splitlines()[-1])


def case_text(registered: list[str], blocks: list[str]) -> str:
    """Return a whole program file for a case.

    A case can define one of the library's operations itself, which then
    replaces the library's. Every operation comes after the ones it
    executes, otherwise in library-then-case order.
    """
    own = {b.split()[1]: b for b in blocks}
    by_name = {**dict(zip(LIBRARY_NAMES, LIBRARY, strict=True)), **own}
    order = [*LIBRARY_NAMES, *(name for name in own if name not in LIBRARY_NAMES)]
    placed: list[str] = []

    def place(name: str) -> None:
        if name in placed:
            return
        for line in by_name[name].splitlines():
            words = line.split()
            if words[0] in ("call", "run") and words[1] in by_name:
                place(words[1])
        placed.append(name)

    for name in order:
        place(name)
    text = [by_name[name] for name in placed]
    return "\n".join(["registered " + " ".join(registered), *text]) + "\n"


def reduce(
    registered: list[str], program_text: str, work: Path
) -> tuple[str, list[str]]:
    """Return (REDUCED, the case's own operation names), or ('error ...', [])."""
    blocks, _ = parse_program(program_text)
    raw = work / "case.prog"
    fixed = work / "fixed.prog"
    raw.write_text(case_text(registered, blocks))
    fails = work / "fails.txt"
    replaced = work / "replaced.txt"
    run_beq(
        raw,
        "--mode",
        "fix",
        "--out",
        str(fixed),
        "--failures",
        str(fails),
        "--replacements",
        str(replaced),
    )
    bad = [line.split() for line in fails.read_text().splitlines()]
    if bad:
        return "error " + bad[0][1], []
    text = fixed.read_text()
    out_names = [
        w[1] for w in (line.split() for line in text.splitlines()) if w and w[0] == "op"
    ]
    case_names = [b.split()[1] for b in blocks]
    # A registered library operation the fixes changed is shown too: other
    # orders in booleans.defcl change what its definition has to be, and
    # a match whose fix would make a cycle writes out executions in it.
    library = dict(zip(LIBRARY_NAMES, LIBRARY, strict=True))
    fixed_blocks: dict[str, list[str]] = {}
    for line in text.splitlines():
        words = line.split()
        if words and words[0] == "op":
            current = fixed_blocks.setdefault(words[1], [])
        if words and words[0] != "registered":
            current.append(line)
    own = []
    for n in out_names:
        changed = (
            n in registered
            and n in library
            and fixed_blocks[n] != library[n].splitlines()
        )
        if n in case_names or n not in library or changed:
            own.append(n)
    views = view_names_of(program_text)
    replacements = replaced.read_text().splitlines()
    dropped_parts = []
    for line in replacements:
        name, view, kind, *rest = line.split()
        if kind != "dropped" or name not in views:
            continue
        gone = {int(k) for k in rest}
        dropped_parts.append(
            f"dropped {name} {', '.join(views[name][k - 1] for k in sorted(gone))}"
        )
        views[name] = [v for i, v in enumerate(views[name], start=1) if i not in gone]
    parts = [render_program(text, own, views)] if own else []
    parts += dropped_parts
    for line in replacements:
        name, view, kind, *rest = line.split()
        if name not in case_names or kind == "dropped":
            continue
        what = replacement_text(kind, rest, views[name])
        if name in out_names:
            parts.append(f"removed {name} view {int(view) + 1} = {what}")
        else:
            parts.append(f"removed {name} = {what}")
    return " ;; ".join(parts), own


def replacement_text(kind: str, rest: list[str], views: list[str]) -> str:
    """Return what a removed operation's callers compute, over its views."""

    def arg(a: str) -> str:
        if a in ("T", "F"):
            return "true" if a == "T" else "false"
        return views[int(a) - 1]

    if kind == "literal":
        return arg(rest[0])
    if kind == "view":
        return views[int(rest[0]) - 1]
    if rest[0] == "and":
        return f"{arg(rest[1])} and {arg(rest[2])}"
    if rest[0] == "not":
        return f"not {arg(rest[1])}"
    return f"{rest[1]}({', '.join(arg(a) for a in rest[2:])})"


def verify(registered: list[str], reduced: str, work: Path) -> None:
    """Check a reduced program: it compiles under both checkers, and is fixed."""
    blocks, _ = parse_program(reduced)
    if not blocks:
        return
    path = work / "expected.prog"
    text = case_text(registered, blocks)
    path.write_text(text)
    # Only the case's own operations: an unregistered library operation is
    # a value operation like any other, which the case doesn't show.
    names = {b.split()[1] for b in blocks}
    details = work / "details.jsonl"
    run_beq(path, "--mode", "check", "--how", "tt", "--details", str(details))
    for line in details.read_text().splitlines():
        row = json.loads(line)
        if row["op"] in names and row["errors"]:
            raise AssertionError(f"beq finds {row['errors']} in {reduced}")
    # The independent checker tries every tuple of arguments, which takes
    # too long past 12 inputs or about 150 statements; those programs are
    # checked by beq's SAT sweeping as well as its truth tables instead.
    largest = max(len(b.splitlines()) for b in blocks)
    inputs = max(
        int(b.split()[3]) + (int(b.split()[4]) if b.split()[2] == "mixed" else 0)
        for b in blocks
    )
    if inputs > 12 or largest > 150:
        run_beq(path, "--mode", "check", "--how", "auto", "--details", str(details))
        for line in details.read_text().splitlines():
            row = json.loads(line)
            if row["op"] in names and row["errors"]:
                raise AssertionError(
                    f"beq's SAT check finds {row['errors']} in {reduced}"
                )
    else:
        for r in program_check.check_program(text):
            if r["errors"] and r["op"] in names:
                raise AssertionError(f"independent checker: {r} in {reduced}")
    again, _ = reduce(registered, reduced, work)
    kept = " ;; ".join(
        part
        for part in reduced.split(" ;; ")
        if not part.startswith(("removed ", "dropped "))
    )
    if again != kept:
        raise AssertionError(f"not a fixed point: {reduced} => {again}")


# The cases: (registered operations, program).

ALL = ["or", "implies", "xor", "eq", "mux", "maj"]
CASES: list[tuple[list[str], str]] = [
    # Redundant values: constants, the same value, the opposite. Each case
    # reads more views than it needs, so what it reduces to is still a value
    # operation and not a wrapper.
    ([], "f(a, b, c) = (a and not a) and b and c"),
    ([], "f(a, b, c) = not (a and not a) and b and c"),
    ([], "f(a, b, c) = let x = a and b; x and (b and a) and c"),
    ([], "f(a, b, c) = let x = a and b; (x and b) and c"),
    ([], "f(a, b, c) = let x = a and b; not (not (a and b)) and x and c"),
    ([], "f(a, b, c, d) = let x = a and b; (x and not x and c) and d"),
    ([], "f(a, b, c) = let y = not a; not y and b and c"),
    ([], "f(a, b, c) = let y = not a; let z = not a; y and z and b and c"),
    (["or"], "f(a, b, c) = let u = a and b; or(not a, not b) and c and u"),
    (["or"], "f(a, b, c) = let u = a and b; or(not a, not b) and c"),
    ([], "f(a, b, c) = let u = a and b; not (not a and not b) and not u and c"),
    (
        ALL,
        "g(a, b) = (a and b) and not (not a and b) ;; f(a, b, c) = let x = g(a, b); let y = g(a, b); x and y and c",
    ),
    (ALL, "f(a, b, c) = a and (a and b) and c"),
    (ALL, "f(a, b, c) = (a and b) and (a and c)"),
    (ALL, "f(a, b, c) = let n = not a; mux(a, b, c) and not mux(n, c, b)"),
    # Literals.
    ([], "f(a, b, c) = a and true and b and c"),
    ([], "f(a, b, c) = ((a and false) and b) and c"),
    ([], "f(a, b, c) = not false and a and b and c"),
    (["or"], "g(a, b) = not (not a and not b) ;; f(a, b, c) = g(a, false) and b and c"),
    (ALL, "g(a, b, c) = (a and b) and not c ;; f(a, b, d) = g(a, b, false) and d"),
    # Matches.
    (["or"], "f(a, b) = not (not a and not b)"),
    (["implies"], "f(a, b) = not (a and not b)"),
    (["or", "implies"], "f(a, b) = not (not a and not b)"),
    (["xor"], "f(a, b) = not (not (a and not b) and not (not a and b))"),
    (["eq"], "f(a, b) = not (a and not b) and not (not a and b)"),
    (["mux"], "f(s, a, b) = not (not (s and a) and not (not s and b))"),
    (["maj"], "f(a, b, c) = not (not (a and b) and not (c and not (not a and not b)))"),
    (
        ALL,
        "f(a, b, c, d) = let x = a and b; let y = c and d; not (not x and not y) and x",
    ),
    (["or"], "f(a, b, c) = not (not (a and b) and not c)"),
    (["or"], "f(a, b, c) = not a and not b and c"),
    (["or"], "f(a, b, c) = (a and b) and not (not a and not c)"),
    (
        ["or", "implies"],
        "g(a, b) = not (not a and not b) and not (a and b) ;; f(a, b, c) = g(a, b) and c",
    ),
    (ALL, "g(a, b) = a and not b ;; f(a, b, c) = not (not g(a, b) and not c) and b"),
    # Opposite results: three statements, and the two-statement exception.
    (["implies"], "f(a, b, c) = (a and not b) and c"),
    (["implies"], "f(a, b, c) = let n = not b; (a and n) and c and n"),
    (["or"], "f(a, b, c) = not or(a, b) and c"),
    (["or", "nor"], "nor(a, b) = not or(a, b) ;; f(a, b, c) = not or(a, b) and c"),
    (["xor", "eq"], "f(a, b, c) = (not (a and not b) and not (not a and b)) and c"),
    (["eq"], "f(a, b, c) = not xor(a, b) and c"),
    # Spellings.
    (["or", "implies"], "f(a, b, c) = let n = not b; or(a, n) and c and n"),
    (["implies", "or"], "f(a, b, c) = let n = not b; or(a, n) and c and n"),
    (["or", "mux"], "f(a, b, c) = let n = not a; mux(a, c, b) and n"),
    (["mux", "or"], "f(a, b, c) = mux(a, a, b) and c"),
    (ALL, "f(a, b, c) = let n = not a; let m = not b; or(n, m) and c and n and m"),
    (ALL, "f(a, b, c) = let n = not c; implies(c, a) and or(a, n) and b"),
    # Wrappers.
    (["or"], "w(a, b) = or(a, b) ;; f(a, b, c) = w(a, b) and c and a"),
    (["or"], "w(a, b) = or(b, a) ;; f(a, b, c) = w(c, a) and b and c"),
    ([], "w(a, b) = a and b ;; f(a, b, c) = w(a, b) and not c"),
    ([], "w(a) = not a ;; f(a, b, c) = w(a) and b and c"),
    ([], "w(a, b) = a ;; f(a, b, c) = w(a, b) and c and b"),
    (["or"], "g(a, b) = a and b ;; f(a, b, c) = g(a, b) and not c"),
    (["or"], "g(a, b, c) = (a and b) and c ;; f(a, b, c, d) = g(a, b, c) and not d"),
    # Argument order and statement order (DLP 59).
    ([], "f(a, b, c) = (b and a) and c"),
    ([], "f(a, b, c) = let x = a and b; c and x"),
    ([], "f(a, b, c) = let x = b and c; let y = a and c; x and y"),
    ([], "f(a, b, c) = let n = not c; let x = a and b; n and x"),
    (ALL, "g(x, y, z) = or(x and y, z) ;; f(a, b, c) = g(c, a, b) and g(a, c, b)"),
    (ALL, "g(x, y, z) = or(x and z, y) ;; f(a, b, c, d) = g(c, a, b) and d"),
    (
        ALL,
        "g(x, y, z, w) = (x and y) and not (z and w) ;; f(a, b, c, d) = g(b, a, d, c) and a",
    ),
    (ALL, "f(a, b, c) = maj(c, b, a) and not a"),
    # Copies: one value given to two views.
    (ALL, "g(x, y, z) = (x and y) and not z ;; f(a, b, c) = g(a, a, b) and c"),
    (ALL, "g(x, y, z) = (x and not y) and z ;; f(a, b, c) = g(a, b, b) and c"),
    ([], "f(a, b, c) = a and a and b and c"),
    # Mixed operations: comparisons, numeric statements, mixed executions.
    (
        ALL,
        "f(a, x: number) = let c = cmp.lt(x, 3); (num.sel(not (not a and not c), x, 1))",
    ),
    (
        ALL,
        "f(a, x: number, y: number) = (num.add(x, y), not (not a and not cmp.eq(x, y)) and cmp.lt(x, y))",
    ),
    (
        ALL,
        "m(a, x: number) = (num.add(x, 1), (a and cmp.lt(x, 2)) and not cmp.eq(x, 0)) ;; f(b, y: number) = let (p, q) = m(b, y); (num.sel(q and b, p, y))",
    ),
    # Constants across value operations (DLP 58's step 4).
    (
        ALL,
        "g(a, b) = (a and b) and not (a and b) ;; f(a, b, c, d) = (not g(a, b) and c) and d",
    ),
    (
        ALL,
        "g(a, b) = (a and b) and not (a and b) ;; h(a, b, c, d) = not (not g(a, b) and not c) and d ;; f(a, b, c, d) = h(a, b, c, d) and not a",
    ),
    (
        ALL,
        "m(a, x: number) = (num.add(x, 1), a and not a) ;; f(b, c, y: number) = let (p, q) = m(b, y); (num.sel(q, p, y), (b and not q) and c)",
    ),
    (
        ALL,
        "g(s, a, b) = (s and not a) and not b ;; f(s, b, c, d) = g(s, s and not s, b) and c and d",
    ),
    (
        ALL,
        "g(a, b, c, d) = maj(a, b, c) and not d ;; f(a, b, c) = g(a, b, c, false) and not a",
    ),
]

# The rules DLPs 58 and 60 added: a registered operation's own definition
# follows only `and`, `not`, and the ones listed before it; `and` and `not`
# are registered everywhere and come first; read views that don't matter;
# dead statements; and, for the fix loop, writing out the executions that
# would make a match's fix an execution cycle.
NEW_RULES: list[tuple[list[str], str]] = [
    (["xor", "eq"], "eq(a, b) = not (a and not b) and not (not a and b)"),
    (["eq", "xor"], "xor(a, b) = not (not (a and not b) and not (not a and b))"),
    (
        ["or", "implies"],
        "or(a, b) = not (not a and not b) ;; f(a, b, c) = or(a, b) and c",
    ),
    (
        ["implies", "or"],
        "or(a, b) = not (not a and not b) ;; f(a, b, c) = or(a, b) and c",
    ),
    (ALL, "f(a, b, c) = mux(not c, c, b) and a"),
    (["or"], "f(a, b, c) = or(not a, not b) and c"),
    (["implies"], "f(a, b, c) = let i = implies(a, b); (a and i) and c"),
    ([], "f(a, b, c) = let n = not a; let m = not b; not (n and m) and c"),
    (ALL, "g(x, y, z, w) = x and not y ;; f(a, b, c, d) = g(a, b, d, c) and c"),
    (ALL, "g(x, y, z) = x and not y ;; f(a, b, c) = g(a, b, not c) and c"),
    (
        ALL,
        "g(x, y, z) = xor(xor(x, z), xor(y, z)) and x ;; f(a, b, c) = g(a, b, c) and not c",
    ),
    ([], "f(a, b, c) = let d = a and c; (a and b) and c"),
    ([], "f(a, b, c) = let d = a and c; let e = not d; (a and b) and c"),
    # A read view that doesn't matter, given to executions: its reads get
    # another read view the operation keeps, so the executions stay.
    (ALL, "h(p, q) = p and not q ;; f(a, b, c) = or(h(a, c), h(a, not c)) and b"),
    (
        ["or"],
        "h(p, q, r) = (p and q) and not r ;; g(x, y, z) = or(h(x, y, z), h(x, y, not z)) ;; f(a, b, c, d) = g(a, b, c) and d",
    ),
    # With no read view left to give its reads, the written view is a
    # constant.
    ([], "g(x) = x and not x ;; f(a, b) = g(a) and b"),
    # A match whose fix would make an execution cycle (DLP 9): the
    # executions that lead back are written out first.
    (
        ["maj"],
        "U(a, b, c, t) = not (not (a and b) and not (c and not (not a and not b))) and t ;; maj(a, b, c) = U(a, b, c, or(a, b))",
    ),
    (
        ["eq", "xor"],
        "xor(a, b) = not (not (a and not b) and not (not a and b)) ;; eq(a, b) = not xor(a, b) ;; f(a, b, c) = eq(a, b) and c",
    ),
]


def generated_cases(rng: random.Random) -> list[tuple[list[str], str]]:
    """Long cases: near and past 256 boolean statements and 20 inputs."""
    out = []
    for target, views in ((240, 8), (250, 12), (257, 8), (100, 21)):
        s = program.Settings(
            statements=(target, target), views=(views, views), tracked=views <= 12
        )
        s.wrapper_rate = 0.0
        text, _ = program.boolean_operation("f", rng, s, [], {})
        out.append((ALL, render_program(text + "\n", ["f"])))
    # Programs that already compile at the limits: an `xor` chain of `and`s
    # of pairs of inputs has no redundant value, match, or spelling, so it
    # reduces to itself in DLP 59's order. 128 pairs over 20 inputs is 255
    # statements; 129 is 257, and 21 inputs is one too many.
    for pairs, inputs in ((128, 20), (129, 20), (20, 21)):
        names = [view_name(i, "abcdefghijklmnopqrstuvwxyz") for i in range(inputs)]
        chosen = [(i, j) for i in range(inputs) for j in range(i + 1, inputs)][:pairs]
        terms = [f"{names[i]} and {names[j]}" for i, j in chosen]
        body = terms[0]
        for t in terms[1:]:
            body = f"xor({body}, {t})"
        # Every input is read.
        used = {k for pair in chosen for k in pair}
        rest = [names[k] for k in range(inputs) if k not in used]
        for r in rest:
            body = f"xor({body}, {r})"
        out.append((ALL, f"f({', '.join(names)}) = {body}"))
    return out


def main() -> None:
    """Write the lines of cases START to END (`all`, or `merge` the parts).

    `reduction_cases.py OUT START END` writes OUT.START; `reduction_cases.py
    OUT merge` writes OUT from the parts, in order. Each part runs under its
    own time limit.
    """
    target = Path(sys.argv[1])
    if sys.argv[2] == "merge":
        parts = sorted(
            target.parent.glob(target.name + ".*"), key=lambda p: int(p.suffix[1:])
        )
        lines = [line for part in parts for line in part.read_text().splitlines()]
        target.write_text(HEADER + "\n" + "\n".join(lines) + "\n")
        for part in parts:
            part.unlink()
        return
    start, end = int(sys.argv[2]), int(sys.argv[3])
    cases = (CASES + NEW_RULES + generated_cases(random.Random(5)))[start:end]  # noqa: S311 - Reproducible cases.
    lines = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for registered, text in cases:
            reduced, _ = reduce(registered, text, work)
            if not reduced.startswith("error"):
                verify(registered, reduced, work)
            lines.append(f"[{', '.join(registered)}] {text} => {reduced}")
            print(lines[-1][:160], flush=True)
    Path(f"{target}.{start}").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
