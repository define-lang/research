"""Emit the boolean logic graph of every Python function in a codebase.

Usage: py_frontend.py SOURCE_ROOT OUTPUT.jsonl [SUBDIR ...]

Each output line describes one function (or one module's top-level code) in
the intermediate form that analyze.py reads. See README.md for the form.
"""

from __future__ import annotations

import ast
import collections
import concurrent.futures
import json
import os
import re
import sys

BOOL_CALL_NAMES = frozenset(
    {
        "isinstance",
        "issubclass",
        "hasattr",
        "callable",
        "all",
        "any",
        "bool",
        "startswith",
        "endswith",
        "exists",
        "isdisjoint",
        "issubset",
        "issuperset",
    }
)
BOOL_CALL_PREFIX = re.compile(r"^(is_|has_|can_|should_|is[a-z]+$)")
SKIP_DIR_NAMES = frozenset(
    {"tests", "test", "testing", "testdata", "node_modules", ".git"}
)


class Function:
    """The boolean logic graph of one function, built from its AST."""

    def __init__(
        self,
        ctx: FileContext,
        name: str,
        cls: str | None,
        line: int,
        node: ast.AST | None,
    ) -> None:
        """Start a function's graph from its parameters."""
        self.ctx = ctx
        self.name = name
        self.cls = cls
        self.line = line
        self.params: list[str] = []
        self.bool_params: set[str] = set()
        self.method = False
        self.nodes: list[list] = []
        self.memo: dict[int, int] = {}
        self.in_progress: dict[int, int | None] = {}
        self.var_nodes: dict[str, int] = {}
        self.defs: dict[str, list[ast.expr | tuple]] = {}
        self.bool_locals: set[str] = set()
        self.nonlocal_names: set[str] = set()
        self.truthy_names: set[str] = set()
        self.truthy_uses: collections.Counter[str] = collections.Counter()
        self.roots: list[int] = []
        self.rets: list[int] = []
        self.simple_body = True
        self.returns_bool = False
        self.all_returns_booly = True
        self.guards: list[int] = []
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            args = node.args
            all_args = [*args.posonlyargs, *args.args]
            is_static = any(
                isinstance(d, ast.Name) and d.id == "staticmethod"
                for d in node.decorator_list
            )
            self.method = cls is not None and not is_static and bool(all_args)
            for a in [*all_args, *args.kwonlyargs]:
                self.params.append(a.arg)
                if is_bool_annotation(a.annotation):
                    self.bool_params.add(a.arg)
            for a in (args.vararg, args.kwarg):
                if a is not None:
                    self.params.append(a.arg)
            self.returns_bool = is_bool_annotation(node.returns)

    def add(self, node: list) -> int:
        """Append a node and return its number."""
        self.nodes.append(node)
        return len(self.nodes) - 1

    def text(self, e: ast.AST) -> str:
        """Return the source text that identifies an input."""
        return ast.unparse(e)

    def refs_params(self, e: ast.AST) -> bool:
        """Whether e reads a parameter, so its value depends on the caller."""
        if not self.params:
            return False
        return any(isinstance(n, ast.Name) and n.id in self.params for n in ast.walk(e))

    def is_local(self, name: str) -> bool:
        """Whether name is a local variable with definitions in this function."""
        return name in self.defs and name not in self.nonlocal_names

    def booly(self, e: ast.expr, seen: frozenset[str] = frozenset()) -> bool:
        """Whether e evidently has a boolean value."""
        match e:
            case ast.Compare() | ast.UnaryOp(op=ast.Not()):
                return True
            case ast.Constant(value=bool()):
                return True
            case ast.BoolOp(values=values):
                return any(self.booly(v, seen) for v in values)
            case (
                ast.Call(func=ast.Name(id=name))
                | ast.Call(func=ast.Attribute(attr=name))
            ):
                return name in BOOL_CALL_NAMES or bool(BOOL_CALL_PREFIX.match(name))
            case ast.Name(id=name):
                if name in self.bool_params or name in self.bool_locals:
                    return True
                if name in seen:
                    return True
                if self.is_local(name) and name not in self.params:
                    defs = self.defs[name]
                    return all(
                        isinstance(d, ast.expr) and self.booly(d, seen | {name})
                        for d in defs
                    )
                return False
            case ast.IfExp(body=body, orelse=orelse):
                return self.booly(body, seen) and self.booly(orelse, seen)
        return False

    def leaf(self, e: ast.expr) -> int:
        """Add a boolean input node for e."""
        return self.add(["l", self.text(e), self.refs_params(e)])

    def expr(self, e: ast.expr, *, truthy: bool) -> int:
        """Return the node of e, building it the first time."""
        key = id(e)
        found = self.memo.get(key)
        if found is not None:
            return found
        if key in self.in_progress:
            # A local variable's definition reads the variable, as in
            # `done = done or x` in a loop, so the definition refers to
            # itself through a placeholder.
            placeholder = self.in_progress[key]
            if placeholder is None:
                placeholder = self.add(["v", "", []])
                self.in_progress[key] = placeholder
            return placeholder
        self.in_progress[key] = None
        result = self.build(e, truthy=truthy)
        placeholder = self.in_progress.pop(key)
        if placeholder is not None:
            self.nodes[placeholder][2] = [result]
        self.memo[key] = result
        return result

    def stmt(self, op: str, children: list[int], line: int) -> int:
        """Add a boolean statement node."""
        return self.add(["s", op, children, line])

    def build(self, e: ast.expr, *, truthy: bool) -> int:
        """Build the node of e; truthy says only e's truth value is used."""
        line = getattr(e, "lineno", 0)
        match e:
            case ast.BoolOp(op=op, values=values):
                if truthy or any(self.booly(v) for v in values):
                    opname = "and" if isinstance(op, ast.And) else "or"
                    current = self.expr(values[0], truthy=truthy)
                    for v in values[1:]:
                        current = self.stmt(
                            opname, [current, self.expr(v, truthy=truthy)], line
                        )
                    return current
                return self.leaf(e)
            case ast.UnaryOp(op=ast.Not(), operand=operand):
                return self.stmt("not", [self.expr(operand, truthy=True)], line)
            case ast.IfExp(test=test, body=body, orelse=orelse):
                if truthy or (self.booly(body) and self.booly(orelse)):
                    return self.stmt(
                        "choose",
                        [
                            self.expr(test, truthy=True),
                            self.expr(body, truthy=truthy),
                            self.expr(orelse, truthy=truthy),
                        ],
                        line,
                    )
                return self.leaf(e)
            case ast.Compare(left=left, ops=[op], comparators=[right]) if (
                isinstance(op, ast.Eq | ast.NotEq | ast.Is | ast.IsNot)
                and self.is_logic(left)
                and self.is_logic(right)
            ):
                opname = "xnor" if isinstance(op, ast.Eq | ast.Is) else "xor"
                return self.stmt(
                    opname,
                    [self.expr(left, truthy=True), self.expr(right, truthy=True)],
                    line,
                )
            case ast.BinOp(left=left, op=op, right=right) if (
                isinstance(op, ast.BitAnd | ast.BitOr | ast.BitXor)
                and self.booly(left)
                and self.booly(right)
            ):
                opname = {ast.BitAnd: "and", ast.BitOr: "or", ast.BitXor: "xor"}[
                    type(op)
                ]
                return self.stmt(
                    opname,
                    [self.expr(left, truthy=True), self.expr(right, truthy=True)],
                    line,
                )
            case ast.Constant():
                return self.add(["k"])
            case ast.NamedExpr(target=ast.Name(id=name)):
                return self.var(name)
            case ast.Name(id=name):
                if self.is_local(name):
                    return self.var(name)
                if name in self.params:
                    return self.add(["p", self.params.index(name)])
                return self.leaf(e)
            case ast.Call():
                return self.call(e)
        return self.leaf(e)

    def is_logic(self, e: ast.expr) -> bool:
        """Whether e is itself boolean logic, so that == on it is xnor rather than a comparison."""
        match e:
            case ast.BoolOp() | ast.UnaryOp(op=ast.Not()):
                return self.booly(e)
            case ast.Compare():
                return True
            case ast.Name(id=name):
                return self.booly(e) and (
                    name in self.bool_params or self.is_local(name)
                )
        return False

    def call(self, e: ast.Call) -> int:
        """Add a call node with what the analyzer needs to find the callee."""
        recv = -1
        match e.func:
            case ast.Name(id=name):
                imported = self.ctx.from_imports.get(name)
                if imported is not None:
                    info = ["bare", imported[1], imported[0]]
                else:
                    info = ["bare", name, ""]
            case ast.Attribute(value=ast.Name(id=base), attr=attr) if (
                base in ("self", "cls") and self.cls
            ):
                info = ["self", attr, ""]
                recv = self.expr(e.func.value, truthy=False)
            case ast.Attribute(value=ast.Name(id=base), attr=attr) if (
                base in self.ctx.module_aliases
                and not self.is_local(base)
                and base not in self.params
            ):
                info = ["mod", attr, self.ctx.module_aliases[base]]
            case ast.Attribute(value=value, attr=attr):
                info = ["attr", attr, ""]
                recv = self.expr(value, truthy=False)
            case _:
                info = ["dyn", "", ""]
        args = [
            self.expr(a, truthy=False) for a in e.args if not isinstance(a, ast.Starred)
        ]
        return self.add(["c", self.text(e), self.refs_params(e), info, args, recv])

    def var(self, name: str) -> int:
        """Return the node of a local variable, joined to its definitions."""
        found = self.var_nodes.get(name)
        if found is not None:
            return found
        index = self.add(["v", name, []])
        self.var_nodes[name] = index
        truthy = name in self.truthy_names
        defs: list[int] = []
        if name in self.params:
            defs.append(self.add(["p", self.params.index(name)]))
        for d in self.defs[name]:
            if isinstance(d, tuple):
                if d[0] == "aug" and self.booly(d[2]):
                    _, opname, rhs, line = d
                    defs.append(
                        self.stmt(opname, [index, self.expr(rhs, truthy=True)], line)
                    )
                else:
                    defs.append(self.add(["l", "var:" + name, False]))
            else:
                defs.append(self.expr(d, truthy=truthy))
        self.nodes[index][2] = defs
        return index

    def collect(self, body: list[ast.stmt]) -> None:
        """Collect local bindings, then walk the body to build nodes."""
        stmts = list(iter_local_nodes(body))
        for n in stmts:
            match n:
                case ast.Global(names=names) | ast.Nonlocal(names=names):
                    self.nonlocal_names.update(names)
                case ast.Assign(targets=targets, value=value):
                    for t in targets:
                        self.bind_target(t, value)
                case ast.AnnAssign(
                    target=ast.Name(id=name), annotation=ann, value=value
                ):
                    if is_bool_annotation(ann):
                        self.bool_locals.add(name)
                    if value is not None:
                        self.defs.setdefault(name, []).append(value)
                case ast.AugAssign(target=ast.Name(id=name), op=op, value=value):
                    if isinstance(op, ast.BitAnd | ast.BitOr | ast.BitXor):
                        opname = {
                            ast.BitAnd: "and",
                            ast.BitOr: "or",
                            ast.BitXor: "xor",
                        }[type(op)]
                        self.defs.setdefault(name, []).append(
                            ("aug", opname, value, n.lineno)
                        )
                    else:
                        self.defs.setdefault(name, []).append(("opaque",))
                case ast.NamedExpr(target=ast.Name(id=name), value=value):
                    self.defs.setdefault(name, []).append(value)
                case (
                    ast.For(target=t)
                    | ast.AsyncFor(target=t)
                    | ast.comprehension(target=t)
                ):
                    self.bind_opaque(t)
                case ast.withitem(optional_vars=t) if t is not None:
                    self.bind_opaque(t)
                case ast.ExceptHandler(name=name) if name:
                    self.defs.setdefault(name, []).append(("opaque",))
                case ast.Import(names=names) | ast.ImportFrom(names=names):
                    for a in names:
                        self.defs.setdefault(
                            (a.asname or a.name).split(".")[0], []
                        ).append(("opaque",))
                case (
                    ast.FunctionDef(name=name)
                    | ast.AsyncFunctionDef(name=name)
                    | ast.ClassDef(name=name)
                ):
                    self.defs.setdefault(name, []).append(("opaque",))
                case ast.MatchAs(name=name) | ast.MatchStar(name=name) if name:
                    self.defs.setdefault(name, []).append(("opaque",))
        for n in stmts:
            test = None
            match n:
                case (
                    ast.If(test=t)
                    | ast.While(test=t)
                    | ast.Assert(test=t)
                    | ast.IfExp(test=t)
                ):
                    test = t
                case ast.match_case(guard=g) if g is not None:
                    test = g
            if test is not None:
                self.mark_truthy(test)
            if isinstance(n, ast.comprehension):
                for t in n.ifs:
                    self.mark_truthy(t)
        # A variable whose value is also used as a value, not only as a
        # condition, holds a value rather than boolean logic.
        loads = collections.Counter(
            n.id
            for n in stmts
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        )
        self.truthy_names = {
            name for name, count in self.truthy_uses.items() if count == loads[name]
        }
        for n in stmts:
            if isinstance(n, ast.stmt) and not isinstance(
                n,
                ast.Return
                | ast.If
                | ast.Assign
                | ast.AnnAssign
                | ast.AugAssign
                | ast.Pass
                | ast.Expr,
            ):
                self.simple_body = False
            match n:
                case ast.If(test=t) | ast.While(test=t):
                    self.roots.append(self.expr(t, truthy=True))
                    if any(
                        isinstance(m, ast.Return)
                        for m in iter_local_nodes([*n.body, *n.orelse])
                    ):
                        self.guards.append(self.roots[-1])
                case ast.IfExp(test=t):
                    self.expr(n, truthy=False)
                    self.roots.append(self.expr(t, truthy=True))
                case ast.Assert(test=t):
                    self.roots.append(self.expr(t, truthy=True))
                case ast.match_case(guard=g) if g is not None:
                    self.roots.append(self.expr(g, truthy=True))
                case ast.comprehension(ifs=ifs):
                    for t in ifs:
                        self.roots.append(self.expr(t, truthy=True))
                case ast.Return(value=v):
                    if v is None:
                        self.all_returns_booly = False
                    else:
                        self.all_returns_booly &= self.booly(v)
                        self.rets.append(self.expr(v, truthy=self.returns_bool))
                case (
                    ast.Assign(targets=[ast.Name(id=name)], value=v)
                    | ast.AnnAssign(target=ast.Name(id=name), value=v)
                ) if v is not None and self.is_local(name) and is_logic_shaped(v):
                    self.expr(v, truthy=name in self.truthy_names)
                case (
                    ast.BoolOp()
                    | ast.UnaryOp(op=ast.Not())
                    | ast.Compare()
                    | ast.BinOp()
                ) if is_logic_shaped(n):
                    self.expr(n, truthy=False)

    def mark_truthy(self, e: ast.expr) -> None:
        """Count the variables that a condition uses only for their truth value."""
        match e:
            case ast.Name(id=name):
                self.truthy_uses[name] += 1
            case ast.BoolOp(values=values):
                for v in values:
                    self.mark_truthy(v)
            case ast.UnaryOp(op=ast.Not(), operand=operand):
                self.mark_truthy(operand)

    def bind_target(self, t: ast.expr, value: ast.expr) -> None:
        """Record the definitions an assignment makes."""
        match t:
            case ast.Name(id=name):
                self.defs.setdefault(name, []).append(value)
            case ast.Tuple(elts=elts) | ast.List(elts=elts):
                if isinstance(value, ast.Tuple | ast.List) and len(value.elts) == len(
                    elts
                ):
                    for sub, v in zip(elts, value.elts, strict=True):
                        self.bind_target(sub, v)
                else:
                    self.bind_opaque(t)

    def bind_opaque(self, t: ast.expr) -> None:
        """Record definitions whose values the analysis does not follow."""
        for n in ast.walk(t):
            if isinstance(n, ast.Name):
                self.defs.setdefault(n.id, []).append(("opaque",))

    def record(self) -> dict:
        """Return the function's intermediate form."""
        bool_params_only = (
            bool(self.params)
            and all(
                p in self.bool_params for p in self.params[1 if self.method else 0 :]
            )
            and len(self.params) > (1 if self.method else 0)
        )
        return {
            "file": self.ctx.path,
            "line": self.line,
            "name": self.name,
            "module": self.ctx.module,
            "cls": self.cls,
            "method": self.method,
            "params": self.params,
            "nres": 1,
            "pure_candidate": bool_params_only and self.simple_body and bool(self.rets),
            "nodes": self.nodes,
            "roots": self.roots,
            "rets": self.rets,
            "guards": self.guards,
            "returns_bool": self.returns_bool
            or (self.all_returns_booly and bool(self.rets)),
        }


def is_logic_shaped(e: ast.AST) -> bool:
    """Whether e has the form of boolean logic, if its operands are boolean."""
    match e:
        case ast.BoolOp() | ast.UnaryOp(op=ast.Not()) | ast.IfExp():
            return True
        case ast.BinOp(op=op):
            return isinstance(op, ast.BitAnd | ast.BitOr | ast.BitXor)
        case ast.Compare(ops=[op]):
            return isinstance(op, ast.Eq | ast.NotEq | ast.Is | ast.IsNot)
    return False


def is_bool_annotation(a: ast.expr | None) -> bool:
    """Whether a type annotation is bool."""
    match a:
        case ast.Name(id="bool") | ast.Constant(value="bool"):
            return True
    return False


def iter_local_nodes(body: list[ast.stmt]):
    """Yield every AST node of a body except the bodies of nested functions."""
    stack: list[ast.AST] = list(reversed(body))
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef):
            stack.extend(reversed(n.decorator_list))
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(n))))


class FileContext:
    """Imports and naming of one source file."""

    def __init__(self, path: str, module: str, tree: ast.Module) -> None:
        """Read the imports of one file."""
        self.path = path
        self.module = module
        self.module_aliases: dict[str, str] = {}
        self.from_imports: dict[str, tuple[str, str]] = {}
        package = module if path.endswith("__init__.py") else module.rpartition(".")[0]
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    if a.asname:
                        self.module_aliases[a.asname] = a.name
                    else:
                        top = a.name.split(".")[0]
                        self.module_aliases[top] = top
            elif isinstance(n, ast.ImportFrom):
                base = n.module or ""
                if n.level:
                    parts = package.split(".")
                    parts = (
                        parts[: len(parts) - (n.level - 1)] if n.level > 1 else parts
                    )
                    base = ".".join([*parts, base] if base else parts)
                for a in n.names:
                    local = a.asname or a.name
                    self.from_imports[local] = (base, a.name)
                    self.module_aliases[local] = f"{base}.{a.name}"


def analyze_file(args: tuple[str, str]) -> list[str]:
    """Return the JSON lines of every function in one file."""
    root, rel = args
    with open(os.path.join(root, rel), "rb") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError, ValueError:
        return ["#error " + rel]
    module = rel[:-3].replace("/", ".")
    module = module.removesuffix(".__init__")
    ctx = FileContext(rel, module, tree)
    out: list[str] = []

    def emit(fn: Function, body: list[ast.stmt]) -> None:
        fn.collect(body)
        out.append(json.dumps(fn.record(), separators=(",", ":")))

    emit(Function(ctx, "<module>", None, 1, None), tree.body)

    def visit(node: ast.AST, cls: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, child.name)
            elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                emit(Function(ctx, child.name, cls, child.lineno, child), child.body)
                visit(child, None)
            else:
                visit(child, cls)

    visit(tree, None)
    return out


def iter_files(root: str, subdirs: list[str]):
    """Yield the non-test Python files under the given directories."""
    for sub in subdirs or ["."]:
        for dirpath, dirnames, filenames in os.walk(os.path.join(root, sub)):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIR_NAMES)
            for name in sorted(filenames):
                if (
                    not name.endswith(".py")
                    or name.startswith("test_")
                    or name.endswith("_test.py")
                ):
                    continue
                if name in ("conftest.py",):
                    continue
                yield os.path.relpath(os.path.join(dirpath, name), root)


def main() -> None:
    """Write the intermediate form of a whole codebase."""
    root, output, *subdirs = sys.argv[1:]
    files = list(iter_files(root, subdirs))
    errors = 0
    with open(output, "w") as out, concurrent.futures.ProcessPoolExecutor(8) as pool:
        for lines in pool.map(analyze_file, [(root, f) for f in files], chunksize=16):
            for line in lines:
                if line.startswith("#error"):
                    errors += 1
                else:
                    out.write(line + "\n")
    print(f"files={len(files)} parse_errors={errors}", file=sys.stderr)


if __name__ == "__main__":
    main()
