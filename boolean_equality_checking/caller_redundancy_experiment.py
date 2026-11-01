"""Count how often executed operations' values are redundant in their callers.

Runs `gen/caller_redundancy.py` on a few library shapes, each under the time
and memory limits. Run with `uv run --frozen --python 3.14 python
caller_redundancy_experiment.py`; results go to
`results/caller_redundancy.jsonl`.
"""

from __future__ import annotations

import json
import subprocess
import sys

from experiments import HERE, MEMORY_GB, RESULTS, OutOfMemoryError, run_limited

SHAPES = [
    {"levels": 6, "views": 10, "executions": 3},
    {"levels": 6, "views": 10, "executions": 4},
    {"levels": 6, "views": 6, "executions": 3},
    {"levels": 4, "views": 12, "executions": 3, "attempts": 20},
]


def main() -> None:
    """Run every shape and record its counts."""
    with (RESULTS / "caller_redundancy.jsonl").open("a", encoding="utf-8") as out:
        for shape in SHAPES:
            command = [sys.executable, str(HERE / "gen" / "caller_redundancy.py")]
            for name, value in shape.items():
                command += [f"--{name}", str(value)]
            try:
                done = run_limited(command, 30, MEMORY_GB, cwd=HERE / "gen")
                record = json.loads(done.stdout)
            except subprocess.TimeoutExpired:
                record = {**shape, "status": "timeout"}
            except OutOfMemoryError:
                record = {**shape, "status": "out of memory"}
            out.write(json.dumps(record) + "\n")
            out.flush()
            print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
