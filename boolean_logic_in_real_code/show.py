"""Print the pieces of logic of one function, to check the analysis by hand.

Usage: show.py INPUT.jsonl FILE NAME [LINE]
"""

from __future__ import annotations

import sys

import analyze


def main() -> None:
    """Print one function's pieces in both scopes."""
    path, file, name, *line = sys.argv[1:]
    cb = analyze.Codebase(path)
    for fi, fn in enumerate(cb.funcs):
        if (
            fn["file"] != file
            or fn["name"] != name
            or (line and fn["line"] != int(line[0]))
        ):
            continue
        pieces, lone = analyze.scope1_pieces(cb, fi)
        print(f"{fn['file']}:{fn['line']} {fn['name']} params={fn['params']}")
        for p in pieces:
            e = cb.expand(fi, p["members"], analyze.DEPTH_CAP)
            print(
                f"  piece line {p['line']}: scope 1 {p['stmts']} statements, {len(p['inputs'])} inputs"
            )
            for key in sorted(p["inputs"]):
                print(f"      {key}")
            print(
                f"    scope 2: {e.stmts} statements, {e.input_count()} inputs, depth {e.depth}"
            )
            for key, _dep in sorted(e.inputs):
                print(f"      {key}")
            for j in sorted(e.used):
                print(f"      param:{j}")
        for root in lone:
            print(f"  lone call {fn['nodes'][root][1]}")


if __name__ == "__main__":
    main()
