"""Whether the order of booleans.defcl changes registered operations' definitions.

For every order of the standard registrations, this fixes the six
definitions, each first written with `and` and `not` only, with `beq program
--mode fix`, and counts each one's different `and`s with every execution
written out, structurally hashed. With DLP 60's key, what a definition
follows doesn't depend on the order, so every order gives the same
definitions (`results/registration_order.json`). With the order taken from
the list, as `beq` did at commit 28daf75, a definition followed the
operations listed before it, and the counts changed with the order
(`results/registration_order_list.json`).

Run with `uv run python registration_order_experiment.py OUT.json`.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "gen"))
import program

HERE = Path(__file__).parent
BEQ = HERE / "src" / "beq"
LIMIT = ["timeout", "-s", "KILL", "60", "prlimit", f"--as={4 << 30}"]


def parse(text: str) -> dict[str, tuple[int, list[list[str]], str]]:
    """Return each operation's views, statements, and written view."""
    ops: dict[str, tuple[int, list[list[str]], str]] = {}
    for block in text.split("\nend")[:-1]:
        lines = [line.split() for line in block.strip().splitlines()]
        if lines[0][0] == "registered":
            lines = lines[1:]
        header, *body = lines
        ops[header[1]] = (int(header[3]), body[:-1], body[-1][1])
    return ops


def written_out(name: str) -> str:
    """Return a library operation's definition with only `and` and `not`."""
    views, statements, out = program.DEFINITIONS[name]
    lines: list[str] = []
    value = {str(v): str(v) for v in range(1, views + 1)}
    next_value = views + 1

    def emit(line: str) -> str:
        nonlocal next_value
        lines.append(line)
        next_value += 1
        return str(next_value - 1)

    def expand(op: str, args: list[str]) -> str:
        v, body, o = program.DEFINITIONS[op]
        local = {str(i + 1): a for i, a in enumerate(args)}
        k = v + 1
        for statement in body:
            words = statement.split()
            if words[0] == "call":
                local[str(k)] = expand(words[1], [local[a] for a in words[2:]])
            else:
                local[str(k)] = emit(
                    " ".join([words[0], *(local[a] for a in words[1:])])
                )
            k += 1
        return local[str(o)]

    k = views + 1
    for statement in statements:
        words = statement.split()
        if words[0] == "call":
            value[str(k)] = expand(words[1], [value[a] for a in words[2:]])
        else:
            value[str(k)] = emit(" ".join([words[0], *(value[a] for a in words[1:])]))
        k += 1
    return "\n".join(
        [f"op {name} bool {views}", *lines, f"out {value[str(out)]}", "end"]
    )


def ands(name: str, ops: dict[str, tuple[int, list[list[str]], str]]) -> int:
    """Return an operation's different `and`s, every execution written out."""
    strash: dict[tuple[int, int], int] = {}
    count = [0]

    def lits(op: str, args: list[int]) -> int:
        views, body, out = ops[op]
        value = {i + 1: a for i, a in enumerate(args)}
        k = views + 1
        for words in body:
            given = [value[int(a)] for a in words[2 if words[0] == "call" else 1 :]]
            if words[0] == "and":
                a, b = sorted(given)
                if (a, b) not in strash:
                    count[0] += 1
                    strash[(a, b)] = 2 * (1000 + count[0])
                value[k] = strash[(a, b)]
            elif words[0] == "not":
                value[k] = given[0] ^ 1
            elif words[0] == "copy":
                value[k] = given[0]
            else:
                value[k] = lits(words[1], given)
            k += 1
        return value[int(out)]

    views = ops[name][0]
    lits(name, [2 * (i + 1) for i in range(views)])
    return count[0]


def main() -> None:
    """Fix the library under every order and write each one's counts."""
    names = list(program.DEFINITIONS)
    library = "\n".join(written_out(n) for n in names)
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        raw, fixed = Path(tmp) / "raw.prog", Path(tmp) / "fixed.prog"
        fails = Path(tmp) / "fails.txt"
        for order in itertools.permutations(names):
            raw.write_text("registered " + " ".join(order) + "\n" + library + "\n")
            subprocess.run(  # noqa: S603 - This directory's own beq.
                [
                    *LIMIT,
                    str(BEQ),
                    "program",
                    str(raw),
                    "--mode",
                    "fix",
                    "--out",
                    str(fixed),
                    "--failures",
                    str(fails),
                ],
                capture_output=True,
                check=True,
            )
            ops = parse(fixed.read_text())
            rows.append(
                {
                    "order": order,
                    "failures": fails.read_text().split(),
                    "ands": {n: ands(n, ops) for n in names},
                    "definitions": {n: [" ".join(w) for w in ops[n][1]] for n in names},
                }
            )
    Path(sys.argv[1]).write_text(json.dumps(rows) + "\n")


if __name__ == "__main__":
    main()
