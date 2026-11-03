"""Print which calls a function's scope 2 expansion writes out, and their sizes.

Usage: show_calls.py INPUT.jsonl FILE NAME [LEVELS]
"""

from __future__ import annotations

import sys

import analyze


def calls_of(cb: analyze.Codebase, fi: int, starts: list[int]) -> list[tuple[str, int]]:
    """Find the calls that scope 2 writes out from the given nodes."""
    nodes = cb.funcs[fi]["nodes"]
    seen: set[int] = set()
    stack = list(starts)
    found = []
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        node = nodes[n]
        if node[0] in ("s", "v"):
            stack.extend(node[2])
        elif node[0] == "c":
            callee = cb.resolve(fi, node[3])
            if callee is not None and cb.component[callee] != cb.component[fi]:
                found.append((node[1], callee))
                stack.extend(node[4])
    return found


def show(
    cb: analyze.Codebase, fi: int, starts: list[int], r: int, indent: str, levels: int
) -> None:
    """Print each written-out call and, for some levels, the calls it writes out."""
    for text, callee in calls_of(cb, fi, starts):
        summary = cb.summary(callee, r - 1)
        g = cb.funcs[callee]
        size = (
            "BIG"
            if summary is analyze.BIG
            else f"{summary.stmts} statements, {summary.input_count()} inputs"
        )
        print(
            f"{indent}{text[:70]} -> {g['file']}:{g['line']} {g['name']}: {size}, {len(g['guards'])} guards"
        )
        if levels > 1:
            show(cb, callee, g["rets"] + g["guards"], r - 1, indent + "  ", levels - 1)


def main() -> None:
    """Print the written-out calls of one function."""
    path, file, name, *rest = sys.argv[1:]
    levels = int(rest[0]) if rest else 2
    cb = analyze.Codebase(path)
    for fi, fn in enumerate(cb.funcs):
        if fn["file"] == file and fn["name"] == name:
            pieces, lone = analyze.scope1_pieces(cb, fi)
            print(f"{fn['file']}:{fn['line']} {fn['name']}")
            starts = [m for p in pieces for m in p["members"]] + lone
            show(cb, fi, starts, analyze.DEPTH_CAP, "  ", levels)


if __name__ == "__main__":
    main()
