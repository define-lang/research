"""Measure whether the combined algorithm should try a whole-graph OBDD first.

`beq auto --bdd_budget F` tries an OBDD in first-use order within F nodes per
graph node before SAT sweeping. This runs F = 0 (no OBDD first), 4, 16, and
64 on the 256-statement value operations, thirty 1,024-statement ones, and
the adversarial instances that finish, and prints total times, the worst
ratio to the best budget for each instance, and whether the classes agree.
Run with `uv run --frozen --python 3.14 python dispatch_budget.py >
results/dispatch_budget.txt` after `experiments.py` has generated `work/`.
"""

from __future__ import annotations

import collections
import json

from experiments import BEQ, MEMORY_GB, WORK, run_limited

BUDGETS = (0, 4, 16, 64)


def main() -> None:
    """Run every budget on every instance and print the comparison."""
    files = sorted((WORK / "operations").glob("op_*_s256_*.aag"))
    files += sorted((WORK / "operations").glob("op_*_s1024_*.aag"))[:30]
    files += [
        f
        for f in sorted((WORK / "adversarial").glob("*.aag"))
        if "b11" not in f.name and "b12" not in f.name
    ]
    results: dict[str, dict[int, tuple[float, str, str]]] = collections.defaultdict(
        dict
    )
    for f in files:
        for budget in BUDGETS:
            command = [
                str(BEQ),
                "auto",
                str(f),
                "--bdd_budget",
                str(budget),
                "--repeat",
                "3",
            ]
            done = run_limited(command, 300, MEMORY_GB)
            d = json.loads(done.stdout)
            results[f.name][budget] = (d["time_s"], d["chosen"], d["partition_hash"])
    for budget in BUDGETS:
        total = sum(r[budget][0] for r in results.values())
        operations = sum(
            r[budget][0] for name, r in results.items() if name.startswith("op_")
        )
        worst = max(
            r[budget][0] / min(r[b][0] for b in BUDGETS) for r in results.values()
        )
        paths = collections.Counter(r[budget][1] for r in results.values())
        print(
            f"budget {budget}: total {total:.3f} s, operations {operations:.4f} s, adversarial {total - operations:.3f} s,"
            f" worst ratio to the best budget {worst:.1f}, paths {dict(paths)}"
        )
    agree = all(len({r[b][2] for b in BUDGETS}) == 1 for r in results.values())
    print(f"{len(results)} instances; identical classes with every budget: {agree}")


if __name__ == "__main__":
    main()
