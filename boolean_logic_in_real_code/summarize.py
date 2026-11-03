"""Print Markdown tables of the analyzer's results.

Usage: summarize.py RESULT.json ...
"""

from __future__ import annotations

import json
import sys

SECTIONS = [
    ("scope1_pieces", "Scope 1 (within a function), per piece of logic"),
    ("scope1_functions", "Scope 1 (within a function), per function"),
    ("scope2_pieces", "Scope 2 (across calls), per piece of logic"),
    ("scope2_functions", "Scope 2 (across calls), per function"),
]


def dist(d: dict) -> str:
    """Format a distribution."""
    return f"{d['median']} / {d['p90']} / {d['p99']} / {d['p999']} / {d['max']}"


def share(count: int, total: int) -> str:
    """Format a count with its percentage."""
    return f"{count} ({100 * count / total:.2f}%)" if total else "0"


def main() -> None:
    """Print the tables."""
    results = []
    for path in [a for a in sys.argv[1:] if not a.startswith("--")]:
        with open(path) as f:
            results.append(json.load(f))
    print(
        "| Codebase | Functions | With boolean logic | Pure boolean functions | Calls in logic resolved |"
    )
    print("|---|---:|---:|---:|---:|")
    for r in results:
        calls = r["calls_in_logic_resolved"] + r["calls_in_logic_unresolved"]
        print(
            f"| {r['name']} | {r['functions']} | {r['functions_with_logic']} | {r['pure_boolean_functions']} "
            f"| {share(r['calls_in_logic_resolved'], calls)} of {calls} |"
        )
    for key, title in SECTIONS:
        print(f"\n#### {title}\n")
        print(
            "Inputs and statements are median / 90th / 99th / 99.9th percentile / max.\n"
        )
        cap = key.startswith("scope2")
        header = "| Codebase | Units | Inputs | Statements | > 20 inputs | > 256 statements | Either |"
        rule = "|---|---:|---|---|---:|---:|---:|"
        if cap:
            header += " Depth cap | Recursion stop | Size cap | Expansion depth |"
            rule += "---:|---:|---:|---|"
        print(header)
        print(rule)
        for r in results:
            s = r[key]
            n = s["inputs"]["n"]
            if not n:
                continue
            row = (
                f"| {r['name']} | {n} | {dist(s['inputs'])} | {dist(s['stmts'])} | {share(s['over_inputs'], n)} "
                f"| {share(s['over_stmts'], n)} | {share(s['over_either'], n)} |"
            )
            if cap:
                row += (
                    f" {share(s['depth_capped'], n)} | {share(s['recursion_capped'], n)} "
                    f"| {share(s['size_capped'], n)} | {dist(s['depth'])} |"
                )
            print(row)
    if "--examples" in sys.argv:
        for r in results:
            for key, title in SECTIONS:
                s = r[key]
                print(f"\n{r['name']} {title}")
                for inputs, stmts, where in s["top_by_inputs"][:6]:
                    print(f"  inputs={inputs} stmts={stmts} {where}")
                for inputs, stmts, where in s["top_by_stmts"][:6]:
                    print(f"  stmts={stmts} inputs={inputs} {where}")


if __name__ == "__main__":
    main()
