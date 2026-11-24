"""Reduction cases: complete covering set of value operations and what fixing reduces them to.

Writes `~/projects/define/drafts/boolean-reduction-cases.txt` (its header
explains the line format) from the cases below, each reduced by `beq
program --mode fix --method auto`, and checks every line: the expected program
compiles under `beq` (`auto`, plus `tt` when `I <= 20`) and under the
independent checker (`program_check.py`, when `I <= 12` and `S <= 150`), fixing
it again changes nothing, and reading the line back gives the same case.

Run with `uv run --frozen --python 3.14 python gen/reduction_cases.py OUT 0 200`
and `uv run --frozen --python 3.14 python gen/reduction_cases.py OUT merge`
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

# The fixed global standard boolean operations (DLP 61):
# and, not, or, xor, equal.
ALL = ["or", "xor", "equal"]
LIBRARY = [
    "\n".join([f"op {name} bool {views}", *statements, f"out {out}", "end"])
    for name, (views, statements, out) in program.DEFINITIONS.items()
]
LIBRARY_NAMES = list(program.DEFINITIONS)

HEADER = """\
# Boolean reduction cases: a complete covering test suite of programs and what
# each reduces to once every automated refactoring fix of DLPs 56 and 59-64 is
# applied (DLP 59's redundancy, constant folding, literal propagation, callee
# specialization, dead-statement, unused-view, useless-input, multi-output
# bool-op splitting, and mixed-output extraction rules; DLP 60's argument
# order, statement order, associative grouping, and distributive factoring;
# DLP 61's standard boolean operations, spellings, and wrappers; DLP 62's
# limits).
#
# One case per line:
#
#     PROGRAM => REDUCED
#
# Every case runs under Define's fixed global standard boolean operations
# (DLP 61), in fixed order: `and`, `not`, `or`, `xor`, `equal`, where
# `or(a, b) = not (not a and not b)`, `xor(a, b) = or(a and not b, b and not a)`,
# and `equal(a, b) = not xor(a, b)`, and Define's conservative limits (DLP 62):
#   - <= 20 boolean input interface views per value operation
#   - <= 256 boolean statements per value operation
#   - <= 512 boolean inputs per value operation (21-512 via ROBDDs)
#   - <= 65,536 canonical shared ROBDD reachable nodes past 20 inputs
#     (pure boolean value operations <= 20 views always compile via the
#     guaranteed truth-table floor).
#
# PROGRAM is one or more value operations separated by ` ;; `, each after
# the ones it executes:
#
#     NAME(VIEW, ...) = BODY
#
# The names in parentheses are the input views: the boolean inputs. A view
# written `x: number` is numeric (numeric views come after boolean ones),
# which makes the operation mixed. BODY is `let NAME = EXPR;` statements,
# then the output view's EXPR, or `(EXPR, EXPR, ...)` for a mixed
# operation's output views. In EXPR:
#
# - `a and b`, `not a`: the logical operations (`not` binds tighter);
# - `R(a, ...)`: an execution of the value operation R;
# - `true`, `false`: boolean literals; a bare number is a numeric literal;
# - `cmp.NAME(...)`: a comparison, a statement that isn't boolean and
#   gives a boolean input; `num.NAME(...)`: a numeric statement;
# - `let (p, q) = M(...)`: an execution of a mixed operation M, one name
#   per output view.
#
# Every operator and execution is one statement. A value used more than
# once is a `let`; a value used once is written where it's used. A boolean
# `let`'s statements come right before its first use, so the statement
# order is DLP 60's: each boolean statement right before the statement that
# first reads it, in view order, and the output views' last. A `let` of a
# statement that isn't boolean stays where it is. A `let` nothing reads is
# still a statement: a dead one, written after the output views'. A name
# given to two views of one execution stands for the value and a copy of
# it (DLP 55).
#
# REDUCED is the program after every fix, in the same form, in DLP 60's
# statement, argument, grouping, and factoring order.
# `removed NAME = EXPR` means a fix removed the operation, and its callers
# compute EXPR (over its original views) instead: a constant (`true`/`false`),
# a wrapper (EXPR is the statement it wraps, DLP 61), or an operation whose
# output view is one of its views (DLP 59). `removed NAME view K = EXPR` is
# the same for one output view of a mixed operation (where `outJ` refers to
# the J-th output view of the reduced mixed operation). `dropped NAME VIEW, ...`
# means those input views didn't matter (DLP 59), so they're gone from the
# operation and from every execution of it, which shows NAME's remaining views.
# Dead statements are gone too. `error <reason>` (`literal` when a boolean
# literal or constant expression reaches an opaque non-boolean logical
# operation such as `num.*`, `limits`, `outputs`, `cycle`) means the fixes
# stop and leave the error for the programmer.
#
# Every line was produced by the research repository's
# boolean_equality_checking/gen/reduction_cases.py and checked: REDUCED
# compiles under `beq --method auto` (and `tt` when <= 20 inputs) and under
# the independent checker (`gen/program_check.py`, when <= 12 inputs and
# <= 150 statements), and fixing it again changes nothing.
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
    the statement that first reads it, in view order: DLP 60's order. A
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

    A case can define one of the standard library's operations itself, which
    then replaces the library's. Every operation comes after the ones it
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


def reduce(program_text: str, work: Path) -> tuple[str, list[str]]:
    """Return (REDUCED, the case's own operation names), or ('error ...', [])."""
    blocks, _ = parse_program(program_text)
    raw = work / "case.prog"
    fixed = work / "fixed.prog"
    raw.write_text(case_text(ALL, blocks))
    fails = work / "fails.txt"
    replaced = work / "replaced.txt"
    run_beq(
        raw,
        "--mode",
        "fix",
        "--method",
        "auto",
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
            n in ALL and n in library and fixed_blocks[n] != library[n].splitlines()
        )
        if n in case_names or n not in library or changed:
            own.append(n)
    views = view_names_of(program_text)
    orig_views = {name: list(vs) for name, vs in views.items()}
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
        what = replacement_text(kind, rest, orig_views[name])
        if name in out_names:
            parts.append(f"removed {name} view {int(view) + 1} = {what}")
        else:
            parts.append(f"removed {name} = {what}")
    return " ;; ".join(parts), own


def replacement_text(kind: str, rest: list[str], views: list[str]) -> str:
    """Return what a removed operation's callers compute, over its original views."""

    def arg(a: str) -> str:
        if a in ("T", "F"):
            return "true" if a == "T" else "false"
        if a.startswith("@"):
            return f"out{a[1:]}"
        return views[int(a) - 1]

    if kind == "literal":
        return arg(rest[0])
    if kind == "view":
        return views[int(rest[0]) - 1]
    if kind == "out":
        return arg(rest[0])
    if rest[0] == "and":
        return f"{arg(rest[1])} and {arg(rest[2])}"
    if rest[0] == "not":
        return f"not {arg(rest[1])}"
    return f"{rest[1]}({', '.join(arg(a) for a in rest[2:])})"


def verify(reduced: str, work: Path) -> None:
    """Check a reduced program: it compiles under `auto`, `tt` (when <= 20), and `program_check`."""
    blocks, _ = parse_program(reduced)
    if not blocks:
        return
    path = work / "expected.prog"
    text = case_text(ALL, blocks)
    path.write_text(text)
    names = {b.split()[1] for b in blocks}
    details = work / "details.jsonl"
    run_beq(path, "--mode", "check", "--method", "auto", "--details", str(details))
    max_inputs = 0
    max_stmts = 0
    for line in details.read_text().splitlines():
        row = json.loads(line)
        if row["op"] in names:
            if row["errors"]:
                raise AssertionError(f"beq auto finds {row['errors']} in {reduced}")
            max_inputs = max(max_inputs, row["inputs"])
            max_stmts = max(max_stmts, row["statements"])
    if max_inputs <= 20:
        run_beq(path, "--mode", "check", "--method", "tt", "--details", str(details))
        for line in details.read_text().splitlines():
            row = json.loads(line)
            if row["op"] in names and row["errors"]:
                raise AssertionError(f"beq tt finds {row['errors']} in {reduced}")
    if max_inputs <= 12 and max_stmts <= 150:
        for r in program_check.check_program(text):
            if r["errors"] and r["op"] in names:
                raise AssertionError(f"independent checker: {r} in {reduced}")
    again, _ = reduce(reduced, work)
    kept = " ;; ".join(
        part
        for part in reduced.split(" ;; ")
        if not part.startswith(("removed ", "dropped "))
    )
    if again != kept:
        raise AssertionError(f"not a fixed point: {reduced} => {again}")


# Complete covering test cases under Define's fixed standard boolean operations
# (`and`, `not`, `or`, `xor`, `equal`) and conservative limits.

CASES: list[str] = [
    # --- 1. DLP 59: Redundant values (constants, equal, opposite) ---
    "f(a, b, c) = (a and not a) and b and c",
    "f(a, b, c) = not (a and not a) and b and c",
    "f(a, b, c) = let x = a and b; x and (b and a) and c",
    "f(a, b, c) = let x = a and b; (x and b) and c",
    "f(a, b, c) = let x = a and b; not (not (a and b)) and x and c",
    "f(a, b, c, d) = let x = a and b; (x and not x and c) and d",
    "f(a, b, c) = let y = not a; not y and b and c",
    "f(a, b, c) = let y = not a; let z = not a; y and z and b and c",
    "f(a, b, c) = let u = a and b; or(not a, not b) and c and u",
    "f(a, b, c) = let u = a and b; or(not a, not b) and c",
    "f(a, b, c) = let u = a and b; not (not a and not b) and not u and c",
    "g(a, b) = (a and b) and not (not a and b) ;; f(a, b, c) = let x = g(a, b); let y = g(a, b); x and y and c",
    "g(a, b) = a and not b ;; h(a, b) = not or(not a, b) ;; f(a, b, c) = (g(a, b) and h(a, b)) and c",
    "f(a, b, c) = a and (a and b) and c",
    "f(a, b, c) = (a and b) and (a and c)",
    "f(a, b, c) = (a and or(a, b)) and c",
    "f(a, b, c) = xor(a, equal(a, b)) and c",
    "f(a, b, c) = let n = not a; let x = a and or(a, b); xor(x, c) and n",
    # --- 2. DLP 56 & 59: Literals ---
    "f(a, b, c) = a and true and b and c",
    "f(a, b, c) = ((a and false) and b) and c",
    "f(a, b, c) = not false and a and b and c",
    "f(a, b, c) = or(a, false) and b and c",
    "g(a, b, c) = (a and b) and not c ;; f(a, b, d) = g(a, b, false) and d",
    # --- 3. DLP 59: Dead statements and unused read views ---
    "f(a, b, c) = let d = a and c; (a and b) and c",
    "f(a, b, c) = let d = a and c; let e = not d; (a and b) and c",
    "g(x, y, z, w) = x and not y ;; f(a, b, c, d) = g(a, b, d, c) and c",
    "g(x, y, z) = x and not y ;; f(a, b, c) = g(a, b, not c) and c",
    "h(p, q) = p and not q ;; f(a, b, c) = or(h(a, c), h(a, not c)) and b",
    # Interacting unused views: uniform substitution fails, per-view succeeds.
    "g(a, b, c, u1, u2) = let p = xor(u1, u2); xor(xor(a, p), xor(b, p)) and c",
    # Interacting unused views where every kept-view substitution creates a constant
    # (auto-fixed via false-substitution + literal propagation + callee specialization).
    "g(x, y, z) = xor(xor(x, z), xor(y, z)) and x ;; f(a, b, c) = g(a, b, c) and not c",
    "h(p, q, r) = (p and q) and not r ;; g(x, y, z) = or(h(x, y, z), h(x, y, not z)) ;; f(a, b, c, d) = g(a, b, c) and d",
    # --- 4. DLP 59: Constants across value operations ---
    "g(x) = x and not x ;; f(a, b) = g(a) and b",
    "g(a, b) = (a and b) and not (a and b) ;; f(a, b, c, d) = (not g(a, b) and c) and d",
    "g(a, b) = (a and b) and not (a and b) ;; h(a, b, c, d) = not (not g(a, b) and not c) and d ;; f(a, b, c, d) = h(a, b, c, d) and not a",
    "m(a, x: number) = (num.add(x, 1), a and not a) ;; f(b, c, y: number) = let (p, q) = m(b, y); (num.sel(q, p, y), (b and not q) and c)",
    "g(s, a, b) = (s and not a) and not b ;; f(s, b, c, d) = g(s, s and not s, b) and c and d",
    "g(a, b, c, d) = equal(a, b) and c and not d ;; f(a, b, c) = g(a, b, c, false) and not a",
    # --- 5. DLP 60: Argument order, symmetry groups, and statement order ---
    "f(a, b, c) = (b and a) and c",
    "f(a, b, c) = let x = a and b; c and x",
    "f(a, b, c) = let x = b and c; let y = a and c; x and y",
    "f(a, b, c) = let n = not c; let x = a and b; n and x",
    "f(a, b, c) = let n = not b; let m = not a; (m and n) and c",
    "g(a, b, c) = or(a, b and c) ;; h(a, b, c) = or(b, a and c) ;; f(a, b, c) = h(a, b, c) and g(a, b, c)",
    "m(x: number) = (cmp.lt(x, 1), cmp.gt(x, 2)) ;; f(y: number) = let (p, q) = m(y); (q and p)",
    "g(x, y, z) = or(x and y, z) ;; f(a, b, c) = g(c, a, b) and g(a, c, b)",
    "g(x, y, z) = or(x and z, y) ;; f(a, b, c, d) = g(c, a, b) and d",
    "g(x, y, z, w) = (x and y) and not (z and w) ;; f(a, b, c, d) = g(b, a, d, c) and a",
    "g(x, y, z) = or(x and y, z and or(x, y)) ;; f(a, b, c, d) = g(c, b, a) and d",
    # --- 6. DLP 60: Associative grouping (all 4 ops + shared/edge cases) ---
    "f(a, b, c) = a and (b and c)",
    "f(a, b, c) = (a and c) and b",
    "f(a, b, c, d) = (a and b) and (c and d)",
    "f(a, b, c) = or(a, or(b, c))",
    "f(a, b, c, d) = or(or(a, b), or(c, d))",
    "f(a, b, c, d) = xor(xor(a, b), xor(c, d))",
    "f(a, b, c) = equal(a, equal(b, c))",
    "f(a, b, c, d) = equal(equal(a, b), equal(c, d))",
    # Shared intermediate node must NOT be flattened.
    "f(a, b, c, d) = let t = b and c; or(a and t, d and not t)",
    # Complementary leaves in unfixed associative chain (DLP 59 before regrouping).
    "f(a, b, c) = equal(a, equal(b, not a)) and c",
    # --- 7. DLP 60: Factoring common terms (all 4 distributive pairs + ties + shared) ---
    "f(a, b, c) = or(a and b, a and c)",
    "f(a, b, c) = or(a, b) and or(a, c)",
    "f(a, b, c) = xor(a and b, a and c)",
    "f(a, b, c) = equal(or(a, b), or(a, c))",
    "f(a, b, c, d) = or(or(a and b, a and c), a and d)",
    "f(a, b, c, d) = or(or(a and b, a and c), d)",
    "f(a, b, c, d, e) = or((a and b) and c, (a and d) and e)",
    "f(a, b, c) = or(not a and b, not a and c)",
    # Tie-break 1: most terms removed (b: 3) beats lower rank (a: 2).
    "f(a, b, c, d, e) = or(or(a and b, a and c), or(b and d, b and e))",
    # Tie-break 2: equal term count (a: 2, b: 2) broken by lowest rank (a).
    "f(a, b, c, d) = or(or(a and b, a and c), b and d)",
    # Cascading double factoring.
    "f(a, b, c, d) = or(or(a and c, a and d), or(b and c, b and d))",
    # Shared inner term must NOT be factored.
    "f(a, b, c, d) = let t = a and b; xor(or(t, a and c), t and d)",
    # --- 8. DLP 61: Standard boolean operation matches, opposites, spellings, wrappers ---
    "f(a, b) = not (not a and not b)",
    "f(a, b) = not (not (a and not b) and not (not a and b))",
    "f(a, b) = not (a and not b) and not (not a and b)",
    "f(a, b, c) = xor(a, a and not b) and c",
    "f(a, b, c, d) = let x = a and b; let y = c and d; not (not x and not y) and x",
    "f(a, b, c) = not (not (a and b) and not c)",
    "f(a, b, c) = not a and not b and c",
    "f(a, b, c) = or(not a, not b) and c",
    "f(a, b, c) = (a and b) and not (not a and not c)",
    "g(a, b) = a and not b ;; f(a, b, c) = not (not g(a, b) and not c) and b",
    # Opposite match 3-statement threshold (only 2 statements would be removed -> stays).
    "f(a, b, c) = let n = not a; xor(or(n, not b), c and n)",
    # `not` of standard op stays; direct `equal` beats `not xor`.
    "f(a, b, c) = not or(a, b) and c",
    "f(a, b, c) = (not (a and not b) and not (not a and b)) and c",
    "f(a, b, c) = not xor(a, b) and c",
    # Spellings: fewest negations and fixed order (`and < not < or < xor < equal`).
    "f(a, b, c) = let n = not a; xor(n, b) and c and n",
    "f(a, b, c) = let n = not a; equal(n, b) and c and n",
    "f(a, b, c, d) = let n = not a; let m = not b; xor(xor(n, m), or(c and n, d and m))",
    "f(a, b, c, d) = let n = not a; let m = not b; xor(equal(n, m), or(c and n, d and m))",
    "f(a, b, c) = let n = not a; let m = not b; or(n, m) and c and n and m",
    "f(a, b, c, d) = let x = a and b; let y = c and not a; xor(x, y) and d",
    "f(a, b, c, d) = let x = or(a, b); let y = or(c, not a); equal(x, y) and d",
    "f(a, b, c, d) = let x = a and b; let y = c and not a; (not x and not y) and d",
    # Standard library definitions (fixed order: and, not, or, xor, equal).
    "xor(a, b) = not (not (a and not b) and not (not a and b))",
    "equal(a, b) = not (a and not b) and not (not a and b)",
    # Wrappers (and non-wrappers).
    "w(a, b) = or(a, b) ;; f(a, b, c) = w(a, b) and c and a",
    "w(a, b) = or(b, a) ;; f(a, b, c) = w(c, a) and b and c",
    "w(a, b) = xor(a, b) ;; f(a, b, c) = w(a, b) and c",
    "w(a, b) = equal(a, b) ;; f(a, b, c) = w(a, b) and c",
    "w(a, b) = a and b ;; f(a, b, c) = w(a, b) and not c",
    "w(a) = not a ;; f(a, b, c) = w(a) and b and c",
    "w(a, b) = a ;; f(a, b, c) = w(a, b) and c and b",
    "g(a, b, c) = (a and b) and c ;; f(a, b, c, d) = g(a, b, c) and not d",
    "g(a, b) = a and not b ;; w(a, b) = g(a, b) ;; f(a, b, c) = w(a, b) and c",
    # --- 9. DLP 55: Copies (one value given to two views) ---
    "g(x, y, z) = (x and y) and not z ;; f(a, b, c) = g(a, a, b) and c",
    "g(x, y, z) = (x and not y) and z ;; f(a, b, c) = g(a, b, b) and c",
    "f(a, b, c) = a and a and b and c",
    # --- 10. Mixed operations: comparisons, numeric statements, mixed executions ---
    "f(a, x: number) = let c = cmp.lt(x, 3); (num.sel(not (not a and not c), x, 1))",
    "f(a, x: number) = let c = cmp.lt(x, 3); (num.sel(or(c, a and c), x, 1))",
    "f(x: number) = let c1 = cmp.lt(x, 3); let c2 = cmp.lt(x, 3); (c1 and c2)",
    "f(x: number, y: number) = (num.add(x, y), not (not cmp.eq(x, y) and not cmp.lt(x, y)) and cmp.gt(x, 0))",
    "m(x: number) = (num.add(x, 1), cmp.lt(x, 2) and not cmp.eq(x, 0)) ;; f(b, y: number) = let (p, q) = m(y); (num.sel(q and b, p, y))",
    # DLP 59: boolean literals/constants reaching opaque non-boolean logical ops (`num.*`) stop cleanly;
    # literals reaching a mixed op that simplifies them away specialize cleanly.
    "f(x: number) = (num.sel(true, x, 1))",
    "f(a, x: number) = (num.sel(a and not a, x, 1))",
    "m(a, x: number) = (num.sel(a, x, 1)) ;; f(y: number) = let (p) = m(false, y); (p)",
    "m(a, b, x: number) = (num.sel(a and b, x, 1)) ;; f(b, y: number) = let (p) = m(true, b, y); (p)",
    # DLP 59 Problem 7: written boolean views in non-boolean Value Operations (auto-extracted).
    "f(a, x: number) = (num.add(x, 1), not a)",
    "f(a, x: number, y: number) = (num.add(x, y), a and cmp.lt(x, y))",
    "m(a, x: number, y: number) = (num.add(x, y), a and cmp.lt(x, y)) ;; f(b, u: number, v: number) = let (s, ok) = m(b, u, v); (num.sel(ok, s, u))",
    "f(a, b, x: number) = (num.sel(a and b, x, 1))",
    "f(x: number, y: number) = let c = cmp.lt(x, y); (c, not c)",
    "f(x: number, y: number) = let c = cmp.lt(x, y); let d = cmp.eq(x, y); (c, or(c, d))",
    "f(x: number, y: number) = (cmp.lt(x, y), cmp.gt(x, y))",
    "m(x: number) = (num.add(x, 1), cmp.lt(x, 2)) ;; f(y: number) = let (p, q) = m(y); (p)",
    # DLP 59 Problem 7: useless boolean input in one expression of a mixed operation.
    # Both the simple example and the `xor_and` example auto-fix cleanly.
    "f(a, b, c, x: number, y: number) = let first = num.sel(equal(equal(a, b), equal(b, c)), x, y); (num.sel(b, first, 0))",
    "xor_and(d, p, q) = xor(d, p and q) ;; f(a, b, c, d, e, x: number, y: number) = let first = num.sel(xor(xor_and(d, a, b), xor_and(d, c, e)), x, y); (num.sel(d, first, 0))",
]


def _make_nlfsr(rounds: int, n_views: int = 20) -> str:
    """Return an irreducible 20-view op with `37 + 2 * rounds` statements.

    At `rounds = 109` (255 input statements), its shared ROBDD exceeds 65,536
    nodes and triggers the guaranteed truth-table floor fallback; at
    `rounds = 110` (257 statements) it exceeds the 256-statement limit.
    """
    names = [view_name(i, "abcdefghijklmnopqrstuvwxyz") for i in range(n_views)]
    vals: list[str] = []
    lets: list[str] = []

    def add_let(expr: str) -> None:
        nm = f"u{len(vals)}"
        lets.append(f"let {nm} = {expr};")
        vals.append(nm)

    add_let(f"{names[0]} and {names[1]}")
    for i in range(2, n_views):
        add_let(f"xor({vals[-1]}, {names[i]} and {names[(i + 5) % n_views]})")
    for r in range(rounds):
        add_let(f"xor({vals[-1]}, {vals[-4]} and {names[(r * 7 + 3) % n_views]})")
    body = " ".join(lets[:-1]) + " " + lets[-1].split(" = ", 1)[1][:-1]
    return f"f({', '.join(names)}) = {body}"


def _make_bdd_inner_product(pairs: int) -> str:
    """Return a mixed op with `2 * pairs` boolean inputs whose ROBDD has ~2^(pairs+1) nodes.

    At `pairs = 14` (28 inputs, 40 statements, 32,806 ROBDD nodes) it compiles;
    at `pairs = 15` (30 inputs, 43 statements, > 65,536 ROBDD nodes) it hits
    the canonical shared ROBDD node limit.
    """
    lets = [f"let x{i} = cmp.gt(n, {i});" for i in range(pairs)] + [
        f"let y{i} = cmp.lt(n, {i});" for i in range(pairs)
    ]
    chain_x = "x0"
    for i in range(1, pairs):
        chain_x = f"({chain_x} and x{i})"
    lets.append(f"let s = num.use({chain_x}, n);")
    ip = "x0 and y0"
    for i in range(1, pairs):
        ip = f"xor({ip}, x{i} and y{i})"
    return f"f(n: number) = {' '.join(lets)} (s, {ip})"


def _make_wide_mixed_inputs(n_inputs: int) -> str:
    """Return a mixed op reading `n_inputs` boolean inputs via a 20-view helper.

    At `n_inputs = 512` it compiles via ROBDDs; at `513` it hits `error limits`.
    """
    hviews = [view_name(i, "abcdefghijklmnopqrstuvwxyz") for i in range(20)]
    hbody = hviews[0]
    for v in hviews[1:]:
        hbody = f"xor({hbody}, {v})"
    h_op = f"h20({', '.join(hviews)}) = {hbody}"
    lets = [f"let c{i} = cmp.lt(n, {i});" for i in range(n_inputs)]
    terms = []
    idx = 0
    while idx + 20 <= n_inputs:
        terms.append(f"h20({', '.join(f'c{j}' for j in range(idx, idx + 20))})")
        idx += 20
    while idx < n_inputs:
        terms.append(f"c{idx}")
        idx += 1
    body = terms[0]
    for t in terms[1:]:
        body = f"xor({body}, {t})"
    return f"{h_op} ;; f(n: number) = {' '.join(lets)} ({body})"


def generated_cases(rng: random.Random) -> list[str]:
    """Long and boundary cases: all 4 limits plus ROBDD and TT-fallback paths."""
    out: list[str] = []
    # Random dense ops near/past 256 statements and 20 views.
    for target, views in ((240, 8), (250, 12), (257, 8), (100, 21)):
        s = program.Settings(
            statements=(target, target), views=(views, views), tracked=views <= 12
        )
        s.wrapper_rate = 0.0
        text, _ = program.boolean_operation("f", rng, s, [], {})
        out.append(render_program(text + "\n", ["f"]))
    # Factorable 255-stmt quadratic XOR over 20 views (factors down to 30 stmts),
    # 257-stmt version (`error limits`), and 21-view version (`error limits`).
    for pairs, inputs in ((128, 20), (129, 20), (20, 21)):
        names = [view_name(i, "abcdefghijklmnopqrstuvwxyz") for i in range(inputs)]
        chosen = [(i, j) for i in range(inputs) for j in range(i + 1, inputs)][:pairs]
        terms = [f"{names[i]} and {names[j]}" for i, j in chosen]
        body = terms[0]
        for t in terms[1:]:
            body = f"xor({body}, {t})"
        used = {k for pair in chosen for k in pair}
        for k in range(inputs):
            if k not in used:
                body = f"xor({body}, {names[k]})"
        out.append(f"f({', '.join(names)}) = {body}")
    # Irreducible 20-view op: 255 stmts triggers ROBDD -> TT floor fallback (compiles);
    # 257 stmts hits the statement limit (`error limits`).
    out.append(_make_nlfsr(109, 20))
    out.append(_make_nlfsr(110, 20))
    # Mixed op past 20 inputs (ROBDD backend) with redundancy, factoring, grouping, match.
    lets24 = [f"let c{i} = cmp.lt(n, {i});" for i in range(24)]
    chain24 = "or(c0 and c1, c0 and c2)"
    for i in range(3, 24):
        chain24 = f"xor({chain24}, c{i})"
    out.append(f"f(n: number) = {' '.join(lets24)} (not (not ({chain24}) and not c0))")
    # Canonical shared ROBDD reachable-node limit (<= 65,536 vs > 65,536).
    out.append(_make_bdd_inner_product(14))
    out.append(_make_bdd_inner_product(15))
    # Boolean input limit on mixed ops (512 compiles via ROBDD vs 513 `error limits`).
    out.append(_make_wide_mixed_inputs(512))
    out.append(_make_wide_mixed_inputs(513))
    return out


def main() -> None:
    """Write the lines of cases START to END, or `merge` the parts.

    `reduction_cases.py OUT START END` writes OUT.START; `reduction_cases.py
    OUT merge` writes OUT from the parts, in order.
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
    cases = (CASES + generated_cases(random.Random(5)))[start:end]  # noqa: S311 - Reproducible cases.
    lines = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for text in cases:
            reduced, _ = reduce(text, work)
            if not reduced.startswith("error"):
                verify(reduced, work)
            lines.append(f"{text} => {reduced}")
            print(lines[-1][:160], flush=True)
    Path(f"{target}.{start}").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
