"""Measure the boolean logic pieces of a codebase from a frontend's JSONL.

Usage: analyze.py NAME INPUT.jsonl OUTPUT.json

Scope 1 measures each function on its own. Scope 2 also writes out, as if
inlined, the boolean result of every call to a function of the same codebase
that feeds boolean logic, up to DEPTH_CAP calls deep.
"""

from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict

DEPTH_CAP = 8
STMT_CAP = 10_000
INPUT_CAP = 2_000
INPUT_LIMIT = 20
STMT_LIMIT = 256
TOP = 12

BIG = "big"

# A Python method call on a value of unknown type is far more often a call
# to a method of a built-in type, such as str.startswith, than to the one
# method of that name that the codebase defines.
BUILTIN_METHOD_NAMES = frozenset(
    name
    for t in (
        str,
        bytes,
        bytearray,
        int,
        float,
        complex,
        list,
        tuple,
        dict,
        set,
        frozenset,
        object,
        memoryview,
        range,
    )
    for name in dir(t)
)


class Codebase:
    """All functions of one codebase, with the indexes that resolve calls."""

    def __init__(self, path: str) -> None:
        """Load the functions a frontend emitted and index them by name."""
        self.funcs: list[dict] = []
        with open(path) as f:
            for line in f:
                self.funcs.append(json.loads(line))
        self.by_mod_name: dict[tuple, list[int]] = defaultdict(list)
        self.by_mod_cls_name: dict[tuple, list[int]] = defaultdict(list)
        self.methods_by_name: dict[str, list[int]] = defaultdict(list)
        for i, fn in enumerate(self.funcs):
            if fn["name"] == "<module>":
                continue
            if fn["cls"] is None:
                self.by_mod_name[(fn["module"], fn["name"])].append(i)
            else:
                self.by_mod_cls_name[(fn["module"], fn["cls"], fn["name"])].append(i)
                self.methods_by_name[fn["name"]].append(i)
        self.resolve_memo: dict[tuple, int | None] = {}
        self.pure = [self.is_pure(i) for i in range(len(self.funcs))]
        self.summary_memo: dict[tuple[int, int], object] = {}
        self.classify_memo: dict[int, tuple[list[bool], list[bool]]] = {}
        self.component = self.call_graph_components()

    def call_graph_components(self) -> list[int]:
        """Return the strongly connected component number of each function in the call graph.

        A call within one component is recursive, so writing it out would never end.
        """
        edges: list[list[int]] = []
        for fi, fn in enumerate(self.funcs):
            targets = set()
            for node in fn["nodes"]:
                if node[0] == "c":
                    callee = self.resolve(fi, node[3])
                    if callee is not None:
                        targets.add(callee)
            edges.append(sorted(targets))
        count = len(self.funcs)
        index = [-1] * count
        low = [0] * count
        on_stack = [False] * count
        component = [-1] * count
        stack: list[int] = []
        next_index = 0
        next_component = 0
        for start in range(count):
            if index[start] != -1:
                continue
            work = [(start, 0)]
            index[start] = low[start] = next_index
            next_index += 1
            stack.append(start)
            on_stack[start] = True
            while work:
                v, i = work[-1]
                if i < len(edges[v]):
                    work[-1] = (v, i + 1)
                    w = edges[v][i]
                    if index[w] == -1:
                        index[w] = low[w] = next_index
                        next_index += 1
                        stack.append(w)
                        on_stack[w] = True
                        work.append((w, 0))
                    elif on_stack[w]:
                        low[v] = min(low[v], index[w])
                    continue
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[v])
                if low[v] == index[v]:
                    while True:
                        w = stack.pop()
                        on_stack[w] = False
                        component[w] = next_component
                        if w == v:
                            break
                    next_component += 1
        return component

    def is_pure(self, i: int) -> bool:
        """Whether a function is purely boolean logic over its boolean parameters."""
        fn = self.funcs[i]
        if not fn["pure_candidate"]:
            return False
        nodes = fn["nodes"]
        seen: set[int] = set()
        stack = list(fn["rets"])
        has_statement = False
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            node = nodes[n]
            kind = node[0]
            if kind in ("l", "c"):
                return False
            if kind == "s":
                has_statement = True
                stack.extend(node[2])
            elif kind == "v":
                stack.extend(node[2])
        return has_statement

    def resolve(self, fi: int, info: list[str]) -> int | None:
        """Find the one boolean-returning function of the codebase that a call calls."""
        fn = self.funcs[fi]
        kind, name, qual = info
        key = (fn["module"], fn["cls"], kind, name, qual)
        if key in self.resolve_memo:
            return self.resolve_memo[key]
        candidates: list[int] = []
        if kind == "bare":
            candidates = self.by_mod_name.get((fn["module"], name), [])
            if not candidates and qual:
                candidates = self.by_mod_name.get((qual, name), [])
        elif kind == "self":
            candidates = self.by_mod_cls_name.get((fn["module"], fn["cls"], name), [])
            if not candidates:
                candidates = self.methods_by_name.get(name, [])
        elif kind == "mod":
            candidates = self.by_mod_name.get((qual, name), [])
        elif kind == "attr" and not (
            fn["file"].endswith(".py") and name in BUILTIN_METHOD_NAMES
        ):
            candidates = self.methods_by_name.get(name, [])
        result = None
        if len(candidates) == 1 and self.funcs[candidates[0]]["returns_bool"]:
            result = candidates[0]
        self.resolve_memo[key] = result
        return result

    def classify(self, fi: int) -> tuple[list[bool], list[bool]]:
        """Find which nodes are boolean statements and which variables hold boolean logic."""
        found = self.classify_memo.get(fi)
        if found is not None:
            return found
        nodes = self.funcs[fi]["nodes"]
        count = len(nodes)
        is_stmt = [False] * count
        for i, node in enumerate(nodes):
            if node[0] == "s":
                is_stmt[i] = True
            elif node[0] == "c":
                callee = self.resolve(fi, node[3])
                if callee is not None and self.pure[callee]:
                    is_stmt[i] = True
        is_logic_var = [False] * count
        changed = True
        while changed:
            changed = False
            for i, node in enumerate(nodes):
                if (
                    node[0] == "v"
                    and not is_logic_var[i]
                    and any(is_stmt[d] or is_logic_var[d] for d in node[2])
                ):
                    is_logic_var[i] = True
                    changed = True
        found = (is_stmt, is_logic_var)
        self.classify_memo[fi] = found
        return found

    def summary(self, gi: int, r: int) -> object:
        """Write out what a function returns, at most r calls deep, or BIG."""
        key = (gi, r)
        found = self.summary_memo.get(key)
        if found is None:
            fn = self.funcs[gi]
            found = self.expand(gi, fn["rets"] + fn["guards"], r)
            # Writing out a function chooses among its return values with
            # each condition that decides which return statement runs.
            found.stmts += len(fn["guards"])
            if found.big:
                found = BIG
            self.summary_memo[key] = found
        return found

    def expand(self, fi: int, starts: list[int], r: int) -> Expansion:
        """Collect the statements and inputs reachable from starts, writing out calls."""
        fn = self.funcs[fi]
        nodes = fn["nodes"]
        result = Expansion()
        _, is_logic_var = self.classify(fi)
        seen: set[int] = set()
        calls_seen: set[str] = set()
        stack = list(starts)
        prefix = f"{fi}|"

        def add_local(key: str, *, refs_params: bool) -> None:
            result.inputs.add((key, True) if refs_params else (prefix + key, False))

        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            node = nodes[n]
            kind = node[0]
            if kind == "s":
                result.stmts += 1
                stack.extend(node[2])
            elif kind == "v":
                if is_logic_var[n] or any(
                    nodes[d][0] == "p"
                    or (
                        nodes[d][0] == "c" and self.resolve(fi, nodes[d][3]) is not None
                    )
                    for d in node[2]
                ):
                    stack.extend(node[2])
                else:
                    add_local(f"var:{node[1]}", refs_params=False)
            elif kind == "p":
                result.used.add(node[1])
            elif kind == "l":
                add_local(node[1], refs_params=node[2])
            elif kind == "c":
                call_key, dep, info, args, recv = (
                    node[1],
                    node[2],
                    node[3],
                    node[4],
                    node[5],
                )
                callee = self.resolve(fi, info)
                if callee is None:
                    result.unresolved_calls += 1
                    add_local(call_key, refs_params=dep)
                    continue
                if call_key in calls_seen:
                    continue
                calls_seen.add(call_key)
                result.resolved_calls += 1
                if self.component[callee] == self.component[fi]:
                    result.recursion_capped = True
                    add_local(call_key, refs_params=dep)
                    continue
                if r == 0:
                    result.depth_capped = True
                    add_local(call_key, refs_params=dep)
                    continue
                summary = self.summary(callee, r - 1)
                if not isinstance(summary, Expansion):
                    result.size_capped = True
                    result.big = True
                    add_local(call_key, refs_params=dep)
                    continue
                result.stmts += summary.stmts
                result.depth = max(result.depth, summary.depth + 1)
                result.depth_capped |= summary.depth_capped
                result.recursion_capped |= summary.recursion_capped
                for k, k_dep in summary.inputs:
                    if k_dep:
                        add_local(f"{call_key}::{k}", refs_params=dep)
                    else:
                        result.inputs.add((k, False))
                is_method = self.funcs[callee]["method"]
                for j in summary.used:
                    if is_method:
                        arg = (
                            recv
                            if j == 0
                            else (args[j - 1] if j - 1 < len(args) else -1)
                        )
                    else:
                        arg = args[j] if j < len(args) else -1
                    if arg == -1:
                        add_local(f"{call_key}::param{j}", refs_params=dep)
                    else:
                        stack.append(arg)
            if result.stmts > STMT_CAP or len(result.inputs) > INPUT_CAP:
                result.big = True
                result.size_capped = True
                break
        return result


class Expansion:
    """The boolean statements and inputs reached from some starting nodes."""

    __slots__ = (
        "big",
        "depth",
        "depth_capped",
        "inputs",
        "recursion_capped",
        "resolved_calls",
        "size_capped",
        "stmts",
        "unresolved_calls",
        "used",
    )

    def __init__(self) -> None:
        """Start with nothing reached."""
        self.stmts = 0
        self.inputs: set[tuple[str, bool]] = set()
        self.used: set[int] = set()
        self.depth = 0
        self.depth_capped = False
        self.recursion_capped = False
        self.size_capped = False
        self.big = False
        self.resolved_calls = 0
        self.unresolved_calls = 0

    def input_count(self) -> int:
        """Count the distinct boolean inputs, including parameters."""
        return len(self.inputs) + len(self.used)


def scope1_pieces(cb: Codebase, fi: int) -> tuple[list[dict], list[int]]:
    """Split a function's boolean logic into maximal connected pieces.

    Returns the pieces and the nodes of test positions that hold a lone call.
    """
    fn = cb.funcs[fi]
    nodes = fn["nodes"]
    count = len(nodes)
    is_stmt, is_logic_var = cb.classify(fi)
    parent = list(range(count))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def children(i: int) -> list[int]:
        node = nodes[i]
        if node[0] == "c":
            return node[4]
        return node[2]

    for i in range(count):
        if is_stmt[i] or is_logic_var[i]:
            for c in children(i):
                if is_stmt[c] or is_logic_var[c]:
                    parent[find(c)] = find(i)
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(count):
        if is_stmt[i]:
            groups[find(i)].append(i)
    pieces = []
    for members in groups.values():
        inputs: set[str] = set()
        seen: set[int] = set()
        stack = list(members)
        line = 0
        stmts = 0
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            node = nodes[n]
            kind = node[0]
            if is_stmt[n]:
                stmts += 1
                if kind == "s" and node[3] and (line == 0 or node[3] < line):
                    line = node[3]
                stack.extend(children(n))
            elif is_logic_var[n]:
                stack.extend(node[2])
            elif kind == "v":
                inputs.add(f"var:{node[1]}")
            elif kind == "p":
                inputs.add(f"param:{node[1]}")
            elif kind in ("l", "c"):
                inputs.add(node[1])
        pieces.append(
            {
                "stmts": stmts,
                "inputs": inputs,
                "line": line or fn["line"],
                "members": members,
            }
        )
    in_piece = set()
    for p in pieces:
        in_piece.update(p["members"])
    lone = []
    for r in fn["roots"]:
        if (
            nodes[r][0] == "c"
            and r not in in_piece
            and cb.resolve(fi, nodes[r][3]) is not None
        ):
            lone.append(r)
    return pieces, lone


def percentiles(values: list[int]) -> dict:
    """Summarize a distribution by nearest-rank percentiles."""
    if not values:
        return {"n": 0}
    values = sorted(values)
    n = len(values)

    def rank(p: float) -> int:
        return values[max(0, math.ceil(p / 100 * n) - 1)]

    return {
        "n": n,
        "median": rank(50),
        "p90": rank(90),
        "p99": rank(99),
        "p999": rank(99.9),
        "max": values[-1],
    }


class Collector:
    """The measurements of one kind of unit (piece or function) in one scope."""

    def __init__(self) -> None:
        """Start with no units."""
        self.inputs: list[int] = []
        self.stmts: list[int] = []
        self.examples: list[tuple[int, int, str]] = []
        self.over_inputs = 0
        self.over_stmts = 0
        self.over_either = 0
        self.depth_capped = 0
        self.recursion_capped = 0
        self.size_capped = 0
        self.depths: list[int] = []

    def add(
        self, inputs: int, stmts: int, where: str, expansion: Expansion | None = None
    ) -> None:
        """Record one unit's sizes, and how its expansion stopped."""
        big = expansion is not None and expansion.big
        self.inputs.append(inputs)
        self.stmts.append(stmts)
        over_i = inputs > INPUT_LIMIT or big
        over_s = stmts > STMT_LIMIT or big
        self.over_inputs += over_i
        self.over_stmts += over_s
        self.over_either += over_i or over_s
        if expansion is not None:
            self.depth_capped += expansion.depth_capped
            self.recursion_capped += expansion.recursion_capped
            self.size_capped += expansion.size_capped
            self.depths.append(expansion.depth)
        if over_i or over_s:
            self.examples.append(
                (inputs, stmts, where + (" (size cap)" if big else ""))
            )

    def report(self) -> dict:
        """Summarize the measurements for the JSON report."""
        n = len(self.inputs)
        by_inputs = sorted(self.examples, key=lambda e: (-e[0], -e[1]))[:TOP]
        by_stmts = sorted(self.examples, key=lambda e: (-e[1], -e[0]))[:TOP]
        return {
            "inputs": percentiles(self.inputs),
            "stmts": percentiles(self.stmts),
            "max_stmts_within_input_limit": max(
                (
                    stmts
                    for inputs, stmts in zip(self.inputs, self.stmts, strict=True)
                    if inputs <= INPUT_LIMIT
                ),
                default=0,
            ),
            "over_inputs": self.over_inputs,
            "over_stmts": self.over_stmts,
            "over_either": self.over_either,
            "share_over_either": self.over_either / n if n else 0.0,
            "depth_capped": self.depth_capped,
            "recursion_capped": self.recursion_capped,
            "size_capped": self.size_capped,
            "depth": percentiles(self.depths),
            "top_by_inputs": by_inputs,
            "top_by_stmts": by_stmts,
            "all_over": sorted(self.examples, key=lambda e: (-e[0], -e[1]))[:400],
        }


def main() -> None:
    """Measure one codebase and write its report."""
    name, input_path, output_path = sys.argv[1:]
    start = time.monotonic()
    cb = Codebase(input_path)
    loaded = time.monotonic()
    s1_pieces, s1_funcs, s2_pieces, s2_funcs = (
        Collector(),
        Collector(),
        Collector(),
        Collector(),
    )
    grown_pieces = 0
    total_resolved = 0
    total_unresolved = 0
    for fi, fn in enumerate(cb.funcs):
        pieces, lone = scope1_pieces(cb, fi)
        if not pieces and not lone:
            continue
        where_fn = f"{fn['file']}:{fn['line']} {fn['name']}"
        if pieces:
            function_inputs: set[str] = set()
            for p in pieces:
                s1_pieces.add(
                    len(p["inputs"]),
                    p["stmts"],
                    f"{fn['file']}:{p['line']} {fn['name']}",
                )
                function_inputs |= p["inputs"]
            s1_funcs.add(
                len(function_inputs), sum(p["stmts"] for p in pieces), where_fn
            )
        all_starts: list[int] = []
        for p in pieces:
            e = cb.expand(fi, p["members"], DEPTH_CAP)
            total_resolved += e.resolved_calls
            total_unresolved += e.unresolved_calls
            s2_pieces.add(
                e.input_count(), e.stmts, f"{fn['file']}:{p['line']} {fn['name']}", e
            )
            if e.input_count() != len(p["inputs"]) or e.stmts != p["stmts"]:
                grown_pieces += 1
            all_starts.extend(p["members"])
        for root in lone:
            e = cb.expand(fi, [root], DEPTH_CAP)
            total_resolved += e.resolved_calls
            total_unresolved += e.unresolved_calls
            all_starts.append(root)
            if e.stmts or e.big:
                grown_pieces += 1
                s2_pieces.add(
                    e.input_count(),
                    e.stmts,
                    f"{fn['file']}:{fn['line']} {fn['name']} (lone call)",
                    e,
                )
        e = cb.expand(fi, all_starts, DEPTH_CAP)
        if e.stmts or e.big:
            s2_funcs.add(e.input_count(), e.stmts, where_fn, e)
    report = {
        "name": name,
        "functions": len(cb.funcs),
        "functions_with_logic": len(s1_funcs.inputs),
        "pure_boolean_functions": sum(cb.pure),
        "scope1_pieces": s1_pieces.report(),
        "scope1_functions": s1_funcs.report(),
        "scope2_pieces": s2_pieces.report(),
        "scope2_functions": s2_funcs.report(),
        "scope2_grown_pieces": grown_pieces,
        "calls_in_logic_resolved": total_resolved,
        "calls_in_logic_unresolved": total_unresolved,
        "load_seconds": round(loaded - start, 1),
        "analyze_seconds": round(time.monotonic() - loaded, 1),
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=1)
    print(
        f"{name}: {report['load_seconds']}s load, {report['analyze_seconds']}s analyze",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
