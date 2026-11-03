"""The fewest `and`s computing each boolean function of up to four views.

The cost a registered operation's key starts with is the least number of
`and`s in any and-inverter graph (`and` and `not` only) computing its
function. Every function of four views is in one of 222 NPN classes
(permuting and negating views, negating the result), which share it, so
this finds it once per class by exact synthesis: for k = 1, 2, ... a SAT
instance asks whether k `and`s compute the class's function, and the first
satisfiable k is the minimum (Kojevnikov, Kulikov, and Yaroslavtsev's
encoding, solved by Kissat).

Run with `uv run python min_ands_experiment.py OUT.json [SECONDS [WORKERS]]`,
SECONDS being the limit for one SAT instance and WORKERS how many classes
are solved at once.
"""

from __future__ import annotations

import itertools
import json
import multiprocessing
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import cast

VIEWS = 4
ROWS = 1 << VIEWS
FULL = (1 << ROWS) - 1


def transform(table: int, perm: tuple[int, ...], flips: int, negate: int) -> int:
    """Return the function with views permuted and negated, result negated."""
    out = 0
    for row in range(ROWS):
        source = 0
        for i in range(VIEWS):
            if (row >> i) & 1:
                source |= 1 << perm[i]
        source ^= flips
        if (table >> source) & 1:
            out |= 1 << row
    return out ^ (FULL if negate else 0)


def npn_classes() -> dict[int, list[int]]:
    """Return each class's smallest truth table and its members."""
    transforms = [
        (perm, flips, negate)
        for perm in itertools.permutations(range(VIEWS))
        for flips in range(ROWS)
        for negate in (0, 1)
    ]
    seen: set[int] = set()
    classes: dict[int, list[int]] = {}
    for table in range(1 << ROWS):
        if table in seen:
            continue
        members = {transform(table, *t) for t in transforms}
        seen |= members
        classes[min(members)] = sorted(members)
    return classes


def trivial(table: int) -> bool:
    """Whether no `and` is needed: a constant or one view, maybe negated."""
    if table in (0, FULL):
        return True
    for i in range(VIEWS):
        view = sum(1 << row for row in range(ROWS) if (row >> i) & 1)
        if table in (view, view ^ FULL):
            return True
    return False


def instance(table: int, k: int) -> tuple[int, list[list[int]]]:
    """Return a CNF that's satisfiable when k `and`s compute the function."""
    count = 0

    def var() -> int:
        nonlocal count
        count += 1
        return count

    clauses: list[list[int]] = []
    # x[node][row]: inputs are constants (True/False), gates are variables.
    x: list[list[int | bool]] = [
        [bool((row >> i) & 1) for row in range(ROWS)] for i in range(VIEWS)
    ]
    used: dict[int, list[int]] = {node: [] for node in range(VIEWS + k)}
    choice: dict[int, list[int]] = {}
    for g in range(VIEWS, VIEWS + k):
        x.append([var() for _ in range(ROWS)])
        p, q = var(), var()
        pairs = []
        for j, l in itertools.combinations(range(g), 2):
            s = var()
            pairs.append(s)
            used[j].append(s)
            used[l].append(s)
            for row in range(ROWS):
                for a, b, pa, pb in itertools.product((0, 1), repeat=4):
                    value = (a ^ pa) & (b ^ pb)
                    clause = [-s]
                    skip = False
                    for literal, want in ((x[j][row], a), (x[l][row], b)):
                        if isinstance(literal, bool):
                            if literal != bool(want):
                                skip = True
                        else:
                            clause.append(-literal if want else literal)
                    if skip:
                        continue
                    clause.append(-p if pa else p)
                    clause.append(-q if pb else q)
                    out = x[g][row]
                    clause.append(-out if not value else out)
                    clauses.append(clause)
        clauses.append(pairs)
        choice[g] = pairs
        for s, t in itertools.combinations(pairs, 2):
            clauses.append([-s, -t])
    # Every gate but the last is read by a later one.
    for g in range(VIEWS, VIEWS + k - 1):
        clauses.append(used[g])
    # Two consecutive gates where the second doesn't read the first are in
    # order of their fanin pairs: any graph can be put in that order.
    for g in range(VIEWS, VIEWS + k - 1):
        for a, sa in zip(itertools.combinations(range(g), 2), choice[g], strict=True):
            for b, sb in zip(
                itertools.combinations(range(g + 1), 2), choice[g + 1], strict=True
            ):
                if g not in b and b < a:
                    clauses.append([-sa, -sb])
    negate = var()
    last = x[VIEWS + k - 1]
    for row in range(ROWS):
        want = (table >> row) & 1
        # A gate's row is always a variable; only inputs' are constants.
        out = cast("int", last[row])
        if want:
            clauses += [[out, negate], [-out, -negate]]
        else:
            clauses += [[-out, negate], [out, -negate]]
    return count, clauses


def solve(table: int, k: int, seconds: float, work: Path) -> bool | None:
    """Whether k `and`s compute the function, or None if it ran out of time."""
    count, clauses = instance(table, k)
    path = work / "instance.cnf"
    with path.open("w") as f:
        f.write(f"p cnf {count} {len(clauses)}\n")
        for clause in clauses:
            f.write(" ".join(map(str, clause)) + " 0\n")
    done = subprocess.run(  # noqa: S603 - The system's Kissat.
        [  # noqa: S607 - Found on PATH, like the other tools here.
            "timeout",
            "-s",
            "KILL",
            str(seconds),
            "prlimit",
            f"--as={4 << 30}",
            "kissat",
            "-q",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode == 10:
        return True
    if done.returncode == 20:
        return False
    return None


def support(table: int) -> int:
    """Return how many views the function depends on."""
    count = 0
    for i in range(VIEWS):
        flipped = transform(table, tuple(range(VIEWS)), 1 << i, 0)
        count += flipped != table
    return count


def minimum(job: tuple[int, int, float]) -> dict:
    """Return one class's minimum, starting from support - 1 `and`s."""
    rep, members, seconds = job
    start = time.perf_counter()
    if trivial(rep):
        return {
            "class": rep,
            "members": members,
            "ands": 0,
            "proved_minimum": True,
            "seconds": 0.0,
        }
    k = max(1, support(rep) - 1)
    low, timeouts = k, []
    with tempfile.TemporaryDirectory() as tmp:
        while True:
            answer = solve(rep, k, seconds, Path(tmp))
            if answer is True:
                break
            if answer is None:
                timeouts.append(k)
            else:
                low = k + 1
            k += 1
    return {
        "class": rep,
        "members": members,
        "ands": k,
        "proved_minimum": not timeouts,
        "at_least": low,
        "timed_out_at": timeouts,
        "seconds": time.perf_counter() - start,
    }


def main() -> None:
    """Find every class's minimum, several at once, and write them."""
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    jobs = [(rep, len(members), seconds) for rep, members in npn_classes().items()]
    rows = []
    with multiprocessing.Pool(workers) as pool:
        for row in pool.imap_unordered(minimum, jobs):
            rows.append(row)
            print(json.dumps(row), flush=True)
    rows.sort(key=lambda r: r["class"])
    Path(sys.argv[1]).write_text(json.dumps(rows) + "\n")


if __name__ == "__main__":
    main()
