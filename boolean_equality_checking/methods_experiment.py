"""Where truth tables over every input stop being the fastest exact check.

Every method checks the same operations with `beq program --method M`
(src/methods.hpp): truth tables over every input (`tt`, the current check),
truth tables 2^16 input assignments at a time (`chunk`), OBDDs under four
orders of the inputs (`bdd`), SAT sweeping with beq's CDCL solver (`sat`),
and the split check with truth tables per part (`split`, src/split.hpp).
Each finds the same and opposite values and constants, the read views that
don't matter, and the matches and spellings, and reports the cost of each,
and of what an execution of the operation refers to.

Shapes, for each number of inputs I from 16 up: dense random operations
like the wide program's, operations from the real-code study's IR, read-once
`or` chains like CockroachDB's IsStale, the middle bit of a multiplier,
xor-heavy random operations, and parities of overlapping sets of inputs.

Run with `uv run python methods_experiment.py run SHAPES` (comma-separated)
and `uv run python methods_experiment.py summarize`. Every beq run has 10
seconds and 4 GB; a run past either is recorded as over the cap, and that
method isn't tried at larger I for that shape and statement count.
"""

from __future__ import annotations

import importlib
import json
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "gen"))
sys.path.insert(0, str(HERE))

import program  # pyright: ignore[reportMissingImports]

BEQ = HERE / "src" / "beq"
WORK = HERE / "work" / "methods"
RESULTS = HERE / "results"
SECONDS = 10
MEMORY_GB = 4
OPS_PER_POINT = 3
MAX_STATEMENTS = 256
REPEATS = 3
INPUTS = [*range(16, 25), 26, 28, 30, 32, 36, 40, 48, 56, 62]
METHODS = {
    "tt": [],
    "chunk": [],
    "sat": [],
    "split": [],
    "bdd_dfs": ["--bdd_order", "dfs"],
    "bdd_natural": ["--bdd_order", "natural"],
    "bdd_reverse": ["--bdd_order", "reverse"],
    "bdd_random": ["--bdd_order", "random"],
    "auto": [],
}
# The other orders, only at a few sizes: the order's effect, not a curve.
ORDER_INPUTS = {16, 20, 24, 32, 48}
STATEMENTS = {"dense": [32, 64, 128, 256], "xor_heavy": [64, 256], "parity": [64, 256]}


# ---------------------------------------------------------------------------
# Shapes. Each returns an operation in gen/program.py's format.


def redundant(text: str, inputs: int) -> bool:
    """Whether some value is constant, or the same as or the opposite of an earlier one, on sampled inputs.

    The generators reject such values as they go, except a `not`'s, which
    can still be the same as an earlier value. A match is only searched for
    when an operation has none.
    """
    samples = program.SAMPLES if inputs > program.SAMPLED_INPUTS else 1 << inputs
    mask = (1 << samples) - 1
    proj = (
        program.sampled_projection
        if inputs > program.SAMPLED_INPUTS
        else program.projection
    )
    tables = {i: proj(inputs, i - 1) & mask for i in range(1, inputs + 1)}
    # Each function and its opposite, by the value that has it.
    owner: dict[int, int] = {0: -1, mask: -1}
    for i, t in tables.items():
        owner[t] = owner[t ^ mask] = i
    v = inputs
    for line in text.splitlines()[1:]:
        words = line.split()
        if words[0] in ("out", "end"):
            continue
        v += 1
        if words[0] == "not":
            x = int(words[1])
            t = ~tables[x] & mask
            if owner.get(t, x) != x:
                return True
            tables[v] = t
            continue
        if words[0] == "and":
            t = tables[int(words[1])] & tables[int(words[2])]
        else:
            t = program.FUNCTIONS[words[1]](*(tables[int(x)] for x in words[2:])) & mask
        if t in owner:
            return True
        tables[v] = t
        owner[t] = owner[t ^ mask] = v
    return False


def statement_count(text: str) -> int:
    """Return an operation's number of boolean statements."""
    return sum(
        1 for line in text.splitlines()[1:] if line.split()[0] not in ("out", "end")
    )


def clean(make: Any, inputs: int) -> str:
    """Return the first operation from make() with no redundant value and at most 256 statements, of at most 50."""
    text = make()
    for _ in range(49):
        if not redundant(text, inputs) and statement_count(text) <= MAX_STATEMENTS:
            break
        text = make()
    return text


def dense(name: str, rng: random.Random, inputs: int, statements: int) -> str:
    """Return a random operation like the wide program's."""
    # gen/program.py's mix of statements; closing the operation adds some,
    # and DLP 57 allows 256.
    target = min(statements, MAX_STATEMENTS - 16)
    kinds = [
        ("and", 45),
        ("not", 12),
        *((r, 25 / len(program.REGISTERED)) for r in program.REGISTERED),
    ]
    return clean(lambda: tracked_random(name, rng, inputs, target, kinds), inputs)


def read_once(name: str, inputs: int) -> str:
    """Return an `or` of every input, one at a time, like IsStale."""
    b = program.Builder(name, f"op {name} bool {inputs}", inputs, tracked=False)
    for _ in range(inputs):
        b.view(boolean=True)
    v = 1
    for i in range(2, inputs + 1):
        v = b.emit(f"call or {v} {i}", 0)
    return b.text([str(v)])


def multiplier(name: str, inputs: int, column: int | None = None) -> str:
    """Return bit k (or column) of the product of two k-bit numbers, k = inputs // 2."""
    k = inputs // 2
    top = k if column is None else column
    exprs: list[tuple[str, tuple[int, ...]]] = []
    memo: dict[tuple[str, tuple[int, ...]], int] = {}

    def node(op: str, *args: int) -> int:
        key = (op, args)
        if key not in memo:
            exprs.append(key)
            memo[key] = -len(exprs)
        return memo[key]

    def a(i: int) -> int:
        return i + 1

    def b(j: int) -> int:
        return k + j + 1

    columns: list[list[int]] = [[] for _ in range(top + 1)]
    for i in range(k):
        for j in range(k):
            if i + j <= top:
                columns[i + j].append(node("and", a(i), b(j)))
    for c in range(top + 1):
        bits = columns[c]
        while len(bits) > 1:
            if len(bits) >= 3:
                x, y, z = bits.pop(), bits.pop(), bits.pop()
                bits.insert(0, node("xor", node("xor", x, y), z))
                if c < top:
                    columns[c + 1].append(node("maj", x, y, z))
            else:
                x, y = bits.pop(), bits.pop()
                bits.insert(0, node("xor", x, y))
                if c < top:
                    columns[c + 1].append(node("and", x, y))
    return emit_exprs(name, 2 * k, exprs, columns[top][0])


def emit_exprs(
    name: str, inputs: int, exprs: list[tuple[str, tuple[int, ...]]], out: int
) -> str:
    """Write the cone of out: inputs are 1.., expression i is -(i + 1)."""
    lines: list[str] = []
    number: dict[int, int] = {i: i for i in range(1, inputs + 1)}
    nxt = inputs + 1

    def visit(e: int) -> int:
        nonlocal nxt
        if e in number:
            return number[e]
        op, args = exprs[-e - 1]
        vals = [visit(x) for x in args]
        lines.append(
            (f"{op} " if op == "and" else f"call {op} ") + " ".join(map(str, vals))
        )
        number[e] = nxt
        nxt += 1
        return number[e]

    o = visit(out)
    return "\n".join([f"op {name} bool {inputs}", *lines, f"out {o}", "end"])


def tracked_random(
    name: str,
    rng: random.Random,
    inputs: int,
    statements: int,
    kinds: list[tuple[str, float]],
) -> str:
    """Random statements of these kinds (with weights), no value the operation already has."""
    b = program.Builder(name, f"op {name} bool {inputs}", inputs, tracked=True)
    for _ in range(inputs):
        b.view(boolean=True)
    b.unused = list(b.boolean)
    names = [k for k, _ in kinds]
    weights = [w for _, w in kinds]
    tries = 0
    while len(b.lines) < statements and tries < 50 * statements:
        tries += 1
        kind = rng.choices(names, weights)[0]
        arity = (
            1
            if kind == "not"
            else program.DEFINITIONS[kind][0]
            if kind in program.DEFINITIONS
            else 2
        )
        args = program._pick(b, rng, arity)
        if args is None:
            continue
        if kind == "not":
            # The opposite of a value is never another value of the operation.
            if args[0] in b.nots or not b.new(~b.tables[args[0]], allow_opposite=True):
                continue
            v = b.emit(f"not {args[0]}", ~b.tables[args[0]])
            b.nots[args[0]] = v
            b.use(args[0])
            continue
        if kind == "and":
            table = b.tables[args[0]] & b.tables[args[1]]
            line = f"and {args[0]} {args[1]}"
        else:
            table = program.FUNCTIONS[kind](*(b.tables[x] for x in args))
            line = f"call {kind} " + " ".join(map(str, args))
        if not b.new(table):
            continue
        b.emit(line, table)
        for x in args:
            b.use(x)
    out = program._close(b)
    return b.text([str(out)])


def xor_heavy(name: str, rng: random.Random, inputs: int, statements: int) -> str:
    """Return a random operation of mostly `xor`s and `eq`s."""
    kinds: list[tuple[str, float]] = [("xor", 40), ("eq", 20), ("and", 25), ("not", 15)]
    return clean(lambda: tracked_random(name, rng, inputs, statements, kinds), inputs)


def parity(name: str, rng: random.Random, inputs: int, statements: int) -> str:
    """Parities of random overlapping sets of inputs, combined by `and`s and `or`s."""
    b = program.Builder(name, f"op {name} bool {inputs}", inputs, tracked=True)
    for _ in range(inputs):
        b.view(boolean=True)
    parities: list[int] = []
    tries = 0
    while len(b.lines) < statements * 3 // 4 and tries < 20 * statements:
        tries += 1
        chosen = rng.sample(range(1, inputs + 1), max(2, inputs // 2))
        v = chosen[0]
        for x in chosen[1:]:
            table = b.tables[v] ^ b.tables[x]
            if not b.new(table):
                break
            v = b.emit(f"call xor {v} {x}", table)
        if v not in chosen:
            parities.append(v)
    acc = parities[0]
    for p in parities[1:]:
        op = rng.choice(["and", "or"])
        table = (
            b.tables[acc] & b.tables[p] if op == "and" else b.tables[acc] | b.tables[p]
        )
        if not b.new(table):
            continue
        acc = b.emit(f"and {acc} {p}" if op == "and" else f"call or {acc} {p}", table)
    # Every input read: those no parity read join by `xor`.
    read = {int(w) for line in b.lines for w in line.split()[1:] if w.isdigit()}
    for x in range(1, inputs + 1):
        if x not in read:
            acc = b.emit(f"call xor {acc} {x}", b.tables[acc] ^ b.tables[x])
    return b.text([str(acc)])


def real_ops() -> dict[int, list[str]]:
    """Operations from the real-code study's IR: each unit's largest written cone, by inputs."""
    # split_experiment puts the study's directory on the path.
    se: Any = importlib.import_module("split_experiment")
    analyze: Any = importlib.import_module("analyze")

    by_inputs: dict[int, list[str]] = {}
    for name in [
        "cockroach",
        "tidb",
        "go",
        "kubernetes",
        "mypy",
        "odoo",
        "homeassistant",
    ]:
        cb = analyze.Codebase(str(se.STUDY / "work/ir" / f"{name}.jsonl"))
        for fi in range(len(cb.funcs)):
            pieces, _ = analyze.scope1_pieces(cb, fi)
            for p in pieces:
                if len(p["inputs"]) < 16:
                    continue
                for scope2 in (False, True):
                    b = se.Builder(cb, scope2=scope2)
                    try:
                        ctx = b.top(fi)
                        roots = [b.build(ctx, n) for n in p["members"]]
                    except se.TooBigError:
                        continue
                    text, inputs = cone_op(
                        b.dag, roots, f"r{len(by_inputs.get(0, []))}"
                    )
                    if 16 <= inputs <= 62:
                        by_inputs.setdefault(inputs, []).append(text)
    return by_inputs


def cone_op(dag: Any, roots: list[int], name: str) -> tuple[str, int]:
    """Return the largest root's cone as an operation: `or`, `xor`, `choose` as executions."""
    best: list[int] = []
    root = roots[0]
    for r in roots:
        cone: set[int] = set()
        stack = [r >> 1]
        while stack:
            x = stack.pop()
            if x in cone:
                continue
            cone.add(x)
            stack.extend(k >> 1 for k in dag.kids[x])
        if len(cone) > len(best):
            best = sorted(cone)
            root = r
    inputs = [x for x in best if dag.op[x] == "in"]
    number = {x: i + 1 for i, x in enumerate(inputs)}
    lines: list[str] = []
    nots: dict[int, int] = {}
    nxt = len(inputs) + 1

    def lit(k: int) -> int:
        nonlocal nxt
        v = number[k >> 1]
        if not k & 1:
            return v
        if v not in nots:
            lines.append(f"not {v}")
            nots[v] = nxt
            nxt += 1
        return nots[v]

    for x in best:
        if dag.op[x] == "in":
            continue
        args = [lit(k) for k in dag.kids[x]]
        op = dag.op[x]
        lines.append(
            f"and {args[0]} {args[1]}"
            if op == "and"
            else f"call {'mux' if op == 'choose' else op} " + " ".join(map(str, args))
        )
        number[x] = nxt
        nxt += 1
    o = lit(root)
    return "\n".join([f"op {name} bool {len(inputs)}", *lines, f"out {o}", "end"]), len(
        inputs
    )


def unit_op(dag: Any, roots: list[int], name: str) -> tuple[str, int, int] | None:
    """Return a unit as one operation writing every value nothing else reads, with its inputs and statements."""
    cone: set[int] = set()
    stack = [r >> 1 for r in roots]
    while stack:
        x = stack.pop()
        if x in cone:
            continue
        cone.add(x)
        stack.extend(k >> 1 for k in dag.kids[x])
    nodes = sorted(cone)
    inputs = [x for x in nodes if dag.op[x] == "in"]
    if len(inputs) == len(nodes):
        return None
    number = {x: i + 1 for i, x in enumerate(inputs)}
    lines: list[str] = []
    nots: dict[int, int] = {}
    nxt = len(inputs) + 1

    def lit(k: int) -> int:
        nonlocal nxt
        v = number[k >> 1]
        if not k & 1:
            return v
        if v not in nots:
            lines.append(f"not {v}")
            nots[v] = nxt
            nxt += 1
        return nots[v]

    for x in nodes:
        if dag.op[x] == "in":
            continue
        args = [lit(k) for k in dag.kids[x]]
        op = dag.op[x]
        if op == "and":
            lines.append(f"and {args[0]} {args[1]}")
        else:
            lines.append(
                f"call {'mux' if op == 'choose' else op} " + " ".join(map(str, args))
            )
        number[x] = nxt
        nxt += 1
    outs: list[int] = []
    for r in roots:
        if (r >> 1) in number and dag.op[r >> 1] != "in":
            o = lit(r)
            if o not in outs:
                outs.append(o)
    text = "\n".join(
        [
            f"op {name} mixed {len(inputs)} 0",
            *lines,
            "out " + " ".join(map(str, outs)),
            "end",
        ]
    )
    return text, len(inputs), len(lines)


def real_steps() -> None:
    """Check every real-code unit past the study's limits with DLP 57's rule, without a budget, counting its steps."""
    se: Any = importlib.import_module("split_experiment")
    analyze: Any = importlib.import_module("analyze")
    folder = WORK / "real_units"
    folder.mkdir(parents=True, exist_ok=True)
    out = WORK / "real_steps.jsonl"
    out.unlink(missing_ok=True)
    for name in [
        "cockroach",
        "cpython",
        "django",
        "gitea",
        "go",
        "homeassistant",
        "kubernetes",
        "mypy",
        "odoo",
        "saleor",
        "tidb",
    ]:
        cb = analyze.Codebase(str(se.STUDY / "work/ir" / f"{name}.jsonl"))
        for k, u in enumerate(se.over_limit_units(cb)):
            b = se.Builder(cb, scope2=u["scope"] == 2)
            row: dict[str, Any] = {
                "codebase": name,
                "scope": u["scope"],
                "kind": u["kind"],
                "where": u["where"],
                "study": u["study"],
            }
            try:
                ctx = b.top(u["fi"])
                roots = [b.build(ctx, n) for n in u["starts"]]
            except se.TooBigError:
                row["status"] = "too big to write out"
            else:
                made = unit_op(b.dag, roots, "u")
                if made is None:
                    continue
                text, inputs, statements = made
                row.update(inputs=inputs, statements=statements)
                path = folder / f"{name}_{k}.prog"
                path.write_text("\n".join([*library(), text]) + "\n")
                details = path.with_suffix(".details")
                command = ["timeout", "-s", "KILL", str(SECONDS), "prlimit", f"--as={MEMORY_GB << 30}", str(BEQ), "program",
                           str(path), "--mode", "check", "--details", str(details), "--method", "auto",
                           "--statement_limit", "0"]  # fmt: skip
                start = time.perf_counter()
                done = subprocess.run(  # noqa: S603
                    command, capture_output=True, text=True, check=False
                )
                wall = time.perf_counter() - start
                if done.returncode != 0:
                    row["status"] = "over cap: " + (
                        "time"
                        if done.returncode in (137, -9)
                        else done.stderr.strip()[-120:]
                    )
                    row["wall_s"] = wall
                else:
                    r = next(
                        json.loads(x)
                        for x in details.read_text().splitlines()
                        if x.startswith('{"op":"u"')
                    )
                    st = r["stats"]
                    row.update(status="ok", how=r["how"], steps=st.get("steps"), steps_bdd=st.get("steps_bdd"),
                               steps_search=st.get("steps_search"), steps_sample=st.get("steps_sample"),
                               seconds=r["t"]["total"], errors=r["errors"])  # fmt: skip
                details.unlink(missing_ok=True)
                path.unlink()
            with out.open("a") as f:
                f.write(json.dumps(row) + "\n")
        print(name, flush=True)


def library() -> list[str]:
    """Return booleans.defcl and the registered operations' definitions."""
    parts = ["registered " + " ".join(program.REGISTERED)]
    for name, (views, stmts, out) in program.DEFINITIONS.items():
        parts.append(
            "\n".join([f"op {name} bool {views}", *stmts, f"out {out}", "end"])
        )
    return parts


def point_ops(
    shape: str, inputs: int, statements: int, real: dict[int, list[str]]
) -> list[str]:
    """Return the operations of one point."""
    rng = random.Random(f"{shape}{inputs}{statements}")  # noqa: S311 - Reproducible operations.
    out = []
    for k in range(OPS_PER_POINT):
        name = f"p{k}"
        if shape == "dense":
            out.append(dense(name, rng, inputs, statements))
        elif shape == "read_once":
            out.append(read_once(name, inputs))
            break
        elif shape == "multiplier":
            out.append(multiplier(name, inputs))
            break
        elif shape == "xor_heavy":
            out.append(xor_heavy(name, rng, inputs, statements))
        elif shape == "parity":
            out.append(
                clean(lambda name=name: parity(name, rng, inputs, statements), inputs)
            )
        elif shape == "real":
            texts = real.get(inputs, [])
            if k >= len(texts):
                break
            text = texts[k]
            out.append(text.replace(text.split()[1], name, 1))
    return out


# ---------------------------------------------------------------------------
# Running.


def run_point(path: Path, method: str, *, matches: bool) -> dict[str, Any]:
    """Check one point's program with one method, under the caps; without matches, skip the match search."""
    details = path.with_suffix(f".{method}.details")
    command = [
        "timeout", "-s", "KILL", str(SECONDS), "prlimit", f"--as={MEMORY_GB << 30}",
        str(BEQ), "program", str(path), "--mode", "check", "--details", str(details),
        "--measure_executions", "1", "--input_limit", "62",
        "--method", method.split("_")[0], *METHODS[method], "--matches", "1" if matches else "0",
    ]  # fmt: skip
    start = time.perf_counter()
    done = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    wall = time.perf_counter() - start
    if done.returncode != 0:
        if done.returncode in (137, -9):
            reason = "time"
        elif "bad_alloc" in done.stderr:
            reason = "memory"
        else:
            reason = (
                f"error {done.returncode}: "
                + done.stderr.strip().splitlines()[0][-200:]
                if done.stderr.strip()
                else f"error {done.returncode}"
            )
        done_ops = details.read_text().count("\n") if details.exists() else 0
        details.unlink(missing_ok=True)
        return {
            "status": "over cap",
            "reason": reason,
            "wall_s": wall,
            "stderr": done.stderr[-300:],
            "lines_done": done_ops,
        }
    summary = json.loads(done.stdout.splitlines()[-1])
    ops = []
    for line in details.read_text().splitlines():
        r = json.loads(line)
        if r["op"].startswith("p"):
            ops.append(r)
    details.unlink()
    over = [o for o in ops if "limits" in o["errors"]]
    if over:
        return {
            "status": "over cap",
            "reason": "limits " + json.dumps(over[0]["errors"]["limits"]),
            "wall_s": wall,
            "peak_rss_kb": summary["peak_rss_kb"],
        }
    return {
        "status": "ok",
        "wall_s": wall,
        "peak_rss_kb": summary["peak_rss_kb"],
        "ops": ops,
    }


def run(
    shapes: list[str],
    only_statements: int = 0,
    min_inputs: int = 0,
    inputs_list: list[int] | None = None,
    methods: list[str] | None = None,
    results: str = "results.jsonl",
) -> None:
    """Run every point of these shapes with every method (optionally one statement count, from some I)."""
    WORK.mkdir(parents=True, exist_ok=True)
    real: dict[int, list[str]] = {}
    if "real" in shapes:
        cache = WORK / "real_ops.json"
        if not cache.exists():
            cache.write_text(json.dumps(real_ops()))
        real = {int(k): v for k, v in json.loads(cache.read_text()).items()}
    out = WORK / results
    for shape in shapes:
        for statements in STATEMENTS.get(shape, [0]):
            if only_statements and statements != only_statements:
                continue
            # Methods over a cap with the whole task, and without matches.
            capped: set[str] = set()
            capped_parts: set[str] = set()
            for inputs in inputs_list or INPUTS:
                if inputs < min_inputs:
                    continue
                if shape == "multiplier" and inputs % 2:
                    continue
                ops = point_ops(shape, inputs, statements, real)
                if not ops:
                    continue
                path = WORK / f"{shape}_{inputs}_{statements}.prog"
                path.write_text("\n".join([*library(), *ops]) + "\n")
                for method in methods or METHODS:
                    if (
                        method.startswith("bdd_")
                        and method != "bdd_dfs"
                        and inputs not in ORDER_INPUTS
                    ):
                        continue
                    for matches in (True, False):
                        done = capped if matches else capped_parts
                        # Without matches only once the whole task is over a cap.
                        if method in done or (not matches and method not in capped):
                            continue
                        for repeat in range(REPEATS):
                            r = run_point(path, method, matches=matches)
                            row = {"shape": shape, "inputs": inputs, "statements": statements, "method": method,
                                   "matches": matches, "repeat": repeat, **r}  # fmt: skip
                            with out.open("a") as f:
                                f.write(json.dumps(row) + "\n")
                            if r["status"] != "ok":
                                done.add(method)
                                break
                print(f"{shape} I={inputs} S={statements} done", flush=True)


# ---------------------------------------------------------------------------
# Summarizing.


def op_parts(op: dict[str, Any]) -> dict[str, float]:
    """Return one operation's cost of each part of the task."""
    t = op["t"]
    stats = op.get("stats", {})
    return {
        "classes": t["tables"] + t["redundant"],
        "unused_views": t["structure"],
        "matches": t["matches"],
        "spellings": t["spellings"],
        "executions": t["groups"],
        "total": t["total"],
        "exec_record_bytes": stats.get("exec_record_bytes", 0.0),
        "exec_ns_per_assignment": stats.get("exec_ns_per_assignment", 0.0),
    }


def answers(op: dict[str, Any], *, with_matches: bool = True) -> str:
    """Return what one operation's check found, to compare methods."""
    if not with_matches:
        return json.dumps(
            {k: v for k, v in op["errors"].items() if k not in ("match", "spelling")},
            sort_keys=True,
        )
    return json.dumps(
        [op["errors"], op.get("stats", {}).get("matches_found", 0)], sort_keys=True
    )


def summarize(results: str = "results.jsonl", name: str = "methods") -> None:
    """Write results/NAME.json and results/NAME_tables.md from the runs."""
    rows = [json.loads(line) for line in (WORK / results).read_text().splitlines()]
    points: dict[tuple[str, int, int], dict[str, Any]] = {}
    for r in rows:
        key = (r["shape"], r["statements"], r["inputs"])
        method = r["method"] + ("" if r.get("matches", True) else NO_MATCHES)
        m = points.setdefault(key, {}).setdefault(method, {"runs": [], "over": None})
        if r["status"] == "ok":
            m["runs"].append(r)
        else:
            m["over"] = r["reason"]
    table: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    for (shape, statements, inputs), methods in sorted(points.items()):
        reference = None
        for ref in ("tt", "chunk", "bdd_dfs", "sat"):
            if methods.get(ref, {}).get("runs"):
                reference = ref
                break
        ref_ops = (
            {op["op"]: op for op in methods[reference]["runs"][0]["ops"]}
            if reference
            else {}
        )
        for method, m in methods.items():
            entry: dict[str, Any] = {
                "shape": shape,
                "statements": statements,
                "inputs": inputs,
                "method": method,
            }
            if not m["runs"]:
                entry["over_cap"] = m["over"]
                table.append(entry)
                continue
            totals = [op_parts(op) for run in m["runs"] for op in run["ops"]]
            entry["median_s"] = statistics.median(p["total"] for p in totals)
            entry["worst_s"] = max(p["total"] for p in totals)
            entry["peak_mb"] = (
                statistics.median(run["peak_rss_kb"] for run in m["runs"]) / 1024
            )
            for part in (
                "classes",
                "unused_views",
                "matches",
                "spellings",
                "executions",
                "exec_record_bytes",
                "exec_ns_per_assignment",
            ):
                entry[part] = statistics.median(p[part] for p in totals)
            entry["statements_real"] = statistics.median(
                op["statements"] for op in m["runs"][0]["ops"]
            )
            entry["undecided"] = sum(
                op.get("stats", {}).get("undecided", 0) for op in m["runs"][0]["ops"]
            )
            if reference and method != reference:
                full = not method.endswith(NO_MATCHES)
                for op in m["runs"][0]["ops"]:
                    ref = ref_ops.get(op["op"])
                    if ref and answers(op, with_matches=full) != answers(
                        ref, with_matches=full
                    ):
                        disagreements.append(
                            {
                                "shape": shape,
                                "statements": statements,
                                "inputs": inputs,
                                "method": method,
                                "reference": reference,
                                "op": op["op"],
                                "got": op["errors"],
                                "expected": ref["errors"],
                            }
                        )
            entry["compared_with"] = reference if method != reference else None
            table.append(entry)
    crossovers = crossover(table)
    with (RESULTS / f"{name}.json").open("w") as f:
        json.dump(
            {"points": table, "disagreements": disagreements, "crossovers": crossovers},
            f,
            indent=1,
        )
    (RESULTS / f"{name}_tables.md").write_text(markdown(table, crossovers))
    print(f"{len(table)} entries, {len(disagreements)} disagreements")


PARTS = ["total", "classes", "unused_views", "matches", "spellings"]
NO_MATCHES = " without matches"


def crossover(table: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For each shape, statement count, method and part: the first I where it beats truth tables from then on."""
    by: dict[tuple[str, int], dict[str, dict[int, dict[str, Any]]]] = {}
    for e in table:
        by.setdefault((e["shape"], e["statements"]), {}).setdefault(e["method"], {})[
            e["inputs"]
        ] = e
    out = []
    for (shape, statements), methods in sorted(by.items()):

        def entry(
            method: str,
            inputs: int,
            part: str,
            methods: dict[str, dict[int, dict[str, Any]]] = methods,
        ) -> dict[str, Any] | None:
            # Classes and read views come from the run without matches once
            # the whole task is over a cap.
            e = methods.get(method, {}).get(inputs)
            if (
                e is not None
                and "over_cap" in e
                and part in ("classes", "unused_views")
            ):
                e = methods.get(method + NO_MATCHES, {}).get(inputs, e)
            return e

        for method, points in sorted(methods.items()):
            if method == "tt" or method.endswith(NO_MATCHES):
                continue
            for part in PARTS:
                key = "median_s" if part == "total" else part
                # The smallest I from which the method wins at every larger
                # I where it's within the caps (truth tables over a cap lose).
                first = None
                for inputs in sorted(points):
                    e = entry(method, inputs, part)
                    t = entry("tt", inputs, part)
                    if e is None or "over_cap" in e:
                        continue
                    wins = t is None or "over_cap" in t or e[key] < t[key]
                    if wins and first is None:
                        first = inputs
                    elif not wins:
                        first = None
                out.append(
                    {
                        "shape": shape,
                        "statements": statements,
                        "method": method,
                        "part": part,
                        "beats_tt_from": first,
                    }
                )
    return out


def markdown(table: list[dict[str, Any]], crossovers: list[dict[str, Any]]) -> str:
    """Tables per shape: median and worst seconds and peak MB per method and I."""
    lines = [
        "# Exact methods past truth tables",
        "",
        "Median / worst seconds per operation, peak MB per run (methods_experiment.py).",
        "",
    ]
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for e in table:
        groups.setdefault((e["shape"], e["statements"]), []).append(e)
    for (shape, statements), entries in sorted(groups.items()):
        methods = sorted(
            {e["method"] for e in entries if not e["method"].endswith(NO_MATCHES)},
            key=list(METHODS).index,
        )
        lines += [
            f"## {shape}" + (f", {statements} statements" if statements else ""),
            "",
        ]
        lines.append("| I | " + " | ".join(methods) + " |")
        lines.append("|---|" + "---|" * len(methods))
        for inputs in sorted({e["inputs"] for e in entries}):
            cells = []
            for m in methods:
                e = next(
                    (x for x in entries if x["inputs"] == inputs and x["method"] == m),
                    None,
                )
                if e is None:
                    cells.append("")
                elif "over_cap" in e:
                    p = next(
                        (
                            x
                            for x in entries
                            if x["inputs"] == inputs and x["method"] == m + NO_MATCHES
                        ),
                        None,
                    )
                    parts = (
                        ""
                        if p is None or "over_cap" in p
                        else f"; without matches {p['median_s']:.3g} s, {p['peak_mb']:.0f} MB"
                    )
                    cells.append(f"over cap ({e['over_cap']}){parts}")
                else:
                    cells.append(
                        f"{e['median_s']:.3g} / {e['worst_s']:.3g} s, {e['peak_mb']:.0f} MB"
                    )
            lines.append(f"| {inputs} | " + " | ".join(cells) + " |")
        lines += [
            "",
            "First I from which each method beats truth tables, per part:",
            "",
        ]
        lines.append("| method | " + " | ".join(PARTS) + " |")
        lines.append("|---|" + "---|" * len(PARTS))
        for m in methods:
            if m == "tt":
                continue
            row = [
                str(
                    next(
                        (
                            c["beats_tt_from"]
                            for c in crossovers
                            if c["shape"] == shape
                            and c["statements"] == statements
                            and c["method"] == m
                            and c["part"] == p
                        ),
                        None,
                    )
                )
                for p in PARTS
            ]
            lines.append(f"| {m} | " + " | ".join(row) + " |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Run or summarize."""
    if sys.argv[1] == "real_steps":
        real_steps()
        return
    if sys.argv[1] == "run":
        # run SHAPES [STATEMENTS [MIN_I [I,... [METHODS [RESULTS]]]]]; 0 or - for all.
        extra = (
            [int(x) for x in sys.argv[5].split(",")]
            if len(sys.argv) > 5 and sys.argv[5] != "-"
            else None
        )
        methods = sys.argv[6].split(",") if len(sys.argv) > 6 else None
        results = sys.argv[7] if len(sys.argv) > 7 else "results.jsonl"
        run(
            sys.argv[2].split(","),
            *(int(x) for x in sys.argv[3:5]),
            inputs_list=extra,
            methods=methods,
            results=results,
        )
    else:
        summarize(*sys.argv[2:4])


if __name__ == "__main__":
    main()
