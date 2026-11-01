"""Summarize recorded results as Markdown tables.

Run with `uv run --frozen --python 3.14 python summarize.py EXPERIMENT`. The
tables in the writeups were produced this way from `results/*.jsonl`.
"""

from __future__ import annotations

import collections
import gzip
import json
import pathlib
import re
import statistics

import click

RESULTS = pathlib.Path(__file__).resolve().parent / "results"
EXACT = (
    "tt",
    "bdd_first_use",
    "bdd_natural",
    "sweep",
    "sweep_unscoped",
    "sweep_exhaustive",
    "sweep_bdd_rescue",
    "portfolio",
)


def load(name: str) -> list[dict]:
    """Return every record of one experiment.

    Results too large to keep uncompressed are in `NAME.jsonl.gz`; a later
    run appends to `NAME.jsonl`, and both are read.
    """
    records = []
    compressed = RESULTS / f"{name}.jsonl.gz"
    if compressed.exists():
        with gzip.open(compressed, "rt", encoding="utf-8") as f:
            records += [json.loads(line) for line in f]
    plain = RESULTS / f"{name}.jsonl"
    if plain.exists():
        with plain.open(encoding="utf-8") as f:
            records += [json.loads(line) for line in f]
    return records


def fmt_time(seconds: float) -> str:
    """Format a time with a unit that keeps three significant digits."""
    if seconds < 1e-3:
        return f"{seconds * 1e6:.3g} µs"
    if seconds < 1:
        return f"{seconds * 1e3:.3g} ms"
    return f"{seconds:.3g} s"


def fmt_bytes(kb: float) -> str:
    """Format kilobytes."""
    if kb < 1024:
        return f"{kb:.0f} KB"
    if kb < 1024 * 1024:
        return f"{kb / 1024:.3g} MB"
    return f"{kb / 1024 / 1024:.3g} GB"


def exact_merged(records: list[dict]) -> dict[str, int]:
    """Return the number of redundant nodes in each instance, from exact methods."""
    out: dict[str, int] = {}
    for r in records:
        if r["config"] in EXACT and r["status"] == "ok":
            previous = out.setdefault(r["instance"], r["merged"])
            if previous != r["merged"]:
                raise click.ClickException(f"exact methods disagree on {r['instance']}")
    return out


def table(header: list[str], rows: list[list[str]]) -> str:
    """Return a Markdown table."""
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("-" * len(h) for h in header) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def summary_cell(group: list[dict], what: str) -> str:
    """Summarize one group of runs of one method on similar instances."""
    ok = [r for r in group if r["status"] == "ok"]
    failed = len(group) - len(ok)
    if not ok:
        return "fails" if failed else ""
    if what == "time":
        text = fmt_time(statistics.median(r["time_s"] for r in ok))
        if failed:
            text += f" ({failed} of {len(group)} fail)"
        return text
    if what == "max_time":
        text = fmt_time(max(r["time_s"] for r in ok))
        if failed:
            text += f" ({failed} fail)"
        return text
    if what == "memory":
        return fmt_bytes(max(r["peak_rss_kb"] - r["rss_after_parse_kb"] for r in ok))
    raise ValueError(what)


@click.group()
def cli() -> None:
    """Summarize experiments."""


def _bucket_operations(
    records: list[dict], methods: list[str], what: str, key: str
) -> str:
    groups: dict[tuple[int, int], dict[str, list[dict]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for r in records:
        m = re.match(r"op_i(\d+)_s(\d+)_", r["instance"])
        assert m  # noqa: S101 - Every operation is named this way.
        groups[(int(m[1]), int(m[2]))][r["config"]].append(r)
    rows = []
    for (inputs, statements), by_method in sorted(groups.items()):
        if key == "statements" and statements != 256:
            continue
        sample = next(iter(by_method.values()))[0]
        ands = statistics.median(
            r["ands"] for g in by_method.values() for r in g if "ands" in r
        )
        width = statistics.median(
            r["width"] for g in by_method.values() for r in g if "width" in r
        )
        rows.append(
            [
                str(inputs),
                str(statements),
                f"{ands:.0f}",
                f"{width:.0f}",
                *[summary_cell(by_method[m], what) for m in methods],
            ]
        )
        del sample
    return table(["inputs", "statements", "`and` nodes", "width", *methods], rows)


@cli.command()
def operations() -> None:
    """Tables for the realistic value operations."""
    records = load("operations")
    exact = exact_merged(records)
    methods = [
        "strash",
        "norm_single",
        "norm_all",
        "cuts4",
        "tt",
        "bdd_first_use",
        "bdd_natural",
        "sweep",
        "sweep_exhaustive",
        "sweep_bdd_rescue",
        "portfolio",
    ]
    print("### Median time\n")
    print(_bucket_operations(records, methods, "time", "all"))
    print("\n### Slowest run\n")
    print(_bucket_operations(records, methods, "max_time", "all"))
    print("\n### Largest memory above the parsed graph\n")
    print(_bucket_operations(records, methods, "memory", "all"))

    print("\n### What each method finds\n")
    rows = []
    for m in methods:
        rs = [r for r in records if r["config"] == m and r["status"] == "ok"]
        planted = sum(r["planted_found"] for r in rs)
        planted_total = sum(r["planted_total"] for r in rs)
        merged = sum(r["merged"] for r in rs)
        merged_total = sum(exact[r["instance"]] for r in rs if r["instance"] in exact)
        kinds: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
        for r in rs:
            for kind, (found, total) in r["planted_by_kind"].items():
                kinds[kind][0] += found
                kinds[kind][1] += total
        kind_text = ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(kinds.items()))
        rows.append(
            [
                m,
                str(len(rs)),
                f"{planted}/{planted_total} ({100 * planted / max(planted_total, 1):.1f}%)",
                f"{merged}/{merged_total} ({100 * merged / max(merged_total, 1):.1f}%)",
                kind_text,
            ]
        )
    print(
        table(
            [
                "method",
                "instances finished",
                "planted pairs found",
                "redundant nodes found",
                "by kind",
            ],
            rows,
        )
    )

    print("\n### OBDD size in first-use order against the width bound\n")
    rows = []
    for r in sorted(records, key=lambda r: (r.get("inputs", 0), r.get("ands", 0))):
        if (
            r["config"] != "bdd_first_use"
            or r["status"] != "ok"
            or not r["instance"].endswith("_0")
        ):
            continue
        s = r["stats"]
        rows.append(
            [
                r["instance"],
                str(r["inputs"]),
                str(r["ands"]),
                str(r["width"]),
                f"{s['bdd_shared_size']:.0f}",
                f"{s['bdd_widest_level']:.0f}",
                fmt_time(r["time_s"]),
            ]
        )
    print(
        table(
            [
                "instance",
                "inputs",
                "`and` nodes",
                "width",
                "OBDD nodes",
                "widest level",
                "time",
            ],
            rows,
        )
    )


@cli.command("operations-compact")
def operations_compact() -> None:
    """Print the median and slowest times at 16, 256, and 1,024 statements, as in experiments.md."""
    records = load("operations")
    groups: dict[tuple[int, int], dict[str, list[dict]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for r in records:
        m = re.match(r"op_i(\d+)_s(\d+)_", r["instance"])
        assert m  # noqa: S101 - Every operation is named this way.
        groups[(int(m[1]), int(m[2]))][r["config"]].append(r)
    methods = [
        "strash",
        "norm_all",
        "cuts4",
        "tt",
        "bdd_first_use",
        "sweep",
        "portfolio",
    ]
    for statements in (16, 256, 1024):
        print(f"\n{statements:,} statements:\n")
        rows = []
        for (inputs, s), by_method in sorted(groups.items()):
            if s != statements:
                continue
            cells = []
            for m in methods:
                ok = [r for r in by_method[m] if r["status"] == "ok"]
                if not ok:
                    cells.append("—")
                    continue
                failed = len(by_method[m]) - len(ok)
                cell = f"{fmt_time(statistics.median(r['time_s'] for r in ok))} / {fmt_time(max(r['time_s'] for r in ok))}"
                cells.append(cell + (f" ({failed} fails)" if failed else ""))
            ands = statistics.median(r["ands"] for r in by_method["strash"])
            width = statistics.median(r["width"] for r in by_method["strash"])
            rows.append([str(inputs), f"{ands:.0f}", f"{width:.0f}", *cells])
        print(
            table(
                ["Inputs", "`and` nodes", "Width", *[f"`{m}`" for m in methods]], rows
            )
        )


@cli.command()
def adversarial() -> None:
    """Tables for the adversarial workloads."""
    records = load("adversarial")
    methods = [
        "strash",
        "norm_single",
        "cuts4",
        "tt",
        "bdd_first_use",
        "bdd_natural",
        "sweep",
        "sweep_exhaustive",
        "sweep_bdd_rescue",
        "portfolio",
    ]
    by_instance: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    for r in records:
        by_instance[r["instance"]][r["config"]] = r

    def sort_key(name: str) -> tuple[str, int, str]:
        return (
            name.split("_")[0] + name.split("_")[1]
            if name.startswith("mult")
            else name.split("_")[0],
            int(re.findall(r"\d+", name)[0]),
            name,
        )

    rows = []
    for name in sorted(by_instance, key=sort_key):
        rs = by_instance[name]
        any_r = (
            next(r for r in rs.values() if "ands" in r)
            if any("ands" in r for r in rs.values())
            else {}
        )
        cells = []
        for m in methods:
            r = rs.get(m)
            if r is None:
                cells.append("")
            elif r["status"] == "timeout":
                cells.append("timeout")
            elif r["status"] != "ok":
                cells.append("limit")
            else:
                found = (
                    f" {r['planted_found']}/{r['planted_total']}"
                    if r["planted_found"] < r["planted_total"]
                    else ""
                )
                cells.append(fmt_time(r["time_s"]) + found)
        rows.append(
            [
                name,
                str(any_r.get("inputs", "")),
                str(any_r.get("ands", "")),
                str(any_r.get("width", "")),
                *cells,
            ]
        )
    print(table(["instance", "inputs", "`and` nodes", "width", *methods], rows))


@cli.command()
def program() -> None:
    """Tables for whole programs."""
    records = load("program")
    rows = []
    for r in sorted(
        records,
        key=lambda r: (int(re.findall(r"c(\d+)", r["instance"])[0]), r["config"]),
    ):
        if r["status"] != "ok":
            rows.append([r["instance"], r["config"], r["status"], "", "", "", "", ""])
            continue
        s = r["stats"]
        rows.append(
            [
                r["instance"],
                r["config"],
                f"{r['ands']:,}",
                fmt_time(r["time_s"]),
                fmt_bytes(r["peak_rss_kb"]),
                f"{r['merged']:,}",
                f"{r['planted_found']}/{r['planted_total']}",
                ", ".join(
                    f"{k}={s[k]:.0f}"
                    for k in ("sat_calls", "sat_different", "cex_flushes")
                    if k in s
                ),
            ]
        )
    print(
        table(
            [
                "instance",
                "method",
                "`and` nodes",
                "time",
                "peak memory",
                "redundant nodes",
                "planted found",
                "SAT",
            ],
            rows,
        )
    )


@cli.command("auto")
def auto_summary() -> None:
    """Compare the combined algorithm with the fastest exact method per instance."""
    exact = (
        "tt",
        "bdd_first_use",
        "bdd_natural",
        "sweep",
        "sweep_exhaustive",
        "sweep_bdd_rescue",
        "portfolio",
    )
    for name in ("operations", "adversarial", "library", "program"):
        records = load(name)
        by: dict[str, dict[str, dict]] = collections.defaultdict(dict)
        for r in records:
            by[r["instance"]][r["config"]] = r
        rows = []
        paths: collections.Counter[str] = collections.Counter()
        ratios = []
        auto_unfinished = []
        for instance, rs in sorted(by.items()):
            auto = rs.get("auto")
            if auto is None:
                continue
            finished = [r for m, r in rs.items() if m in exact and r["status"] == "ok"]
            if auto["status"] != "ok":
                auto_unfinished.append(instance)
                continue
            paths[auto["chosen"]] += 1
            if not finished:
                continue
            best = min(finished, key=lambda r: r["time_s"])
            ratio = auto["time_s"] / max(best["time_s"], 1e-9)
            ratios.append(
                (ratio, instance, best["config"], auto["time_s"], best["time_s"])
            )
            if auto["planted_found"] != auto["planted_total"]:
                rows.append(
                    f"{instance}: auto found {auto['planted_found']}/{auto['planted_total']}"
                )
        ratios.sort()
        if not ratios:
            continue

        def at(q: float, ratios: list = ratios) -> str:
            return f"{ratios[min(len(ratios) - 1, int(q * len(ratios)))][0]:.2f}"

        worst = ratios[-3:]
        print(f"\n### {name}\n")
        print(
            f"{len(ratios)} instances; auto / fastest exact method: median {at(0.5)}, 90th percentile {at(0.9)}, "
            f"max {ratios[-1][0]:.2f}"
        )
        print(
            f"auto faster than or equal to every exact method on {sum(1 for r in ratios if r[0] <= 1.0)}"
        )
        print(f"paths taken: {dict(paths)}; unfinished: {auto_unfinished}")
        for ratio, instance, best, t_auto, t_best in worst:
            print(
                f"- {instance}: {ratio:.2f} times ({fmt_time(t_auto)} against {best} {fmt_time(t_best)})"
            )
        for row in rows:
            print(f"- {row}")


@cli.command()
def sdd() -> None:
    """Table comparing SDDs with OBDDs on the sample."""
    records = load("sdd")
    by: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    order: list[str] = []
    for r in records:
        if r["instance"] not in by:
            order.append(r["instance"])
        by[r["instance"]][r["engine"]] = r
    rows = []
    disagreements = 0
    for name in order:
        rs = by[name]
        obdd = rs["obdd"]
        cells = [name, str(obdd.get("inputs", "")), f"{obdd.get('ands', 0):,}"]
        cells.append(
            f"{obdd['size']:,.0f}, {fmt_time(obdd['time_s'])}"
            if obdd["status"] == "ok"
            else obdd["status"]
        )
        for engine in ("sdd_right", "sdd_balanced", "sdd_dynamic"):
            r = rs.get(engine, {"status": "not run"})
            if r["status"] != "ok":
                cells.append(r["status"])
                continue
            disagreements += r["agrees_with_beq"] is False
            cells.append(
                f"{r['live_count']:,}, {fmt_time(r['time_s'])}, {fmt_bytes(r['rss_increase_kb'])}"
            )
        rows.append(cells)
    print(
        table(
            [
                "instance",
                "inputs",
                "`and` nodes",
                "OBDD nodes, time",
                "SDD right-linear (nodes, time, memory)",
                "SDD balanced",
                "SDD balanced + minimization",
            ],
            rows,
        )
    )
    print(f"\nRuns whose classes differ from beq's OBDD: {disagreements}")


@cli.command("abc")
def abc_summary() -> None:
    """Tables comparing ABC with the combined algorithm on the same instances."""
    abc = load("abc")
    commands = ("abc_&fraig", "abc_&fraig_x", "abc_fraig", "abc_&cec")
    auto: dict[str, dict] = {}
    for name in ("operations", "adversarial", "library", "program"):
        for r in load(name):
            if r["config"] == "auto":
                auto[r["instance"]] = r

    def cell(r: dict | None) -> str:
        if r is None:
            return ""
        if r["status"] != "ok":
            return r["status"]
        if r["config"] == "abc_&cec":
            proved = r["proved"]
            return f"{fmt_time(r['time_s'] / r['instances'])}, {proved}/{r['instances']} proved"
        missed = r["planted_total"] - r["planted_found"]
        return fmt_time(r["time_s"] / r["instances"]) + (
            f", {r['planted_found']}/{r['planted_total']}" if missed else ""
        )

    by: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    for r in abc:
        by[r["group"]][r["config"]] = r

    print("### Value operations and the library: time per instance\n")
    rows = []
    for group, rs in by.items():
        if not (group.startswith("op_") or group == "library"):
            continue
        if group == "library":
            members = [a for i, a in auto.items() if i.startswith("library_")]
        else:
            members = [
                a for i, a in auto.items() if re.sub(r"_w8_\d+$", "", i) == group
            ]
        mine = (
            fmt_time(sum(a["time_s"] for a in members) / max(len(members), 1))
            if members
            else ""
        )
        rows.append([group, mine, *[cell(rs.get(c)) for c in commands]])
    print(table(["group", "auto", *commands], rows))

    print("\n### Adversarial instances and programs\n")
    rows = []
    for group, rs in by.items():
        if group.startswith("op_") or group == "library":
            continue
        a = auto.get(group)
        mine = (
            ""
            if a is None
            else (a["status"] if a["status"] != "ok" else fmt_time(a["time_s"]))
        )
        memory = "/".join(
            fmt_bytes(rs[c]["peak_rss_kb"])
            for c in ("abc_&fraig",)
            if c in rs and "peak_rss_kb" in rs[c]
        )
        rows.append([group, mine, *[cell(rs.get(c)) for c in commands], memory])
    print(table(["instance", "auto", *commands, "`&fraig` memory"], rows))


@cli.command()
def native() -> None:
    """Table for native CaDiCaL and Kissat on the hardest pairs."""
    records = load("native")
    auto = {r["instance"]: r for r in load("adversarial") if r["config"] == "auto"}
    by: dict[str, dict[str, list[dict]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for r in records:
        by[r["instance"]][r["solver"]].append(r)

    def key(name: str) -> tuple[str, int]:
        return (re.sub(r"\d+", "", name), int(re.findall(r"\d+", name)[0]))

    rows = []
    for name in sorted(by, key=key):
        cells = [name]
        for solver in ("cadical", "kissat"):
            rs = by[name][solver]
            timeouts = sum(1 for r in rs if r["status"] == "timeout")
            slowest = max(r["time_s"] for r in rs)
            text = f"{fmt_time(slowest)}" + (
                f" ({timeouts} of {len(rs)} time out)" if timeouts else ""
            )
            cells.append(text)
        a = auto.get(name)
        cells.append(
            ""
            if a is None
            else (a["status"] if a["status"] != "ok" else fmt_time(a["time_s"]))
        )
        rows.append(cells)
    print(
        table(
            [
                "instance",
                "CaDiCaL 2.2.1, slowest pair",
                "Kissat 4.0.4, slowest pair",
                "auto, all pairs",
            ],
            rows,
        )
    )


@cli.command()
def matching() -> None:
    """Tables for finding written-out registered operations."""
    records = load("matching")
    groups: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in records:
        m = re.search(r"match_i(\d+)_s(\d+)_", r["file"])
        assert m  # noqa: S101 - Every matching workload is named this way.
        groups[(f"{m[1]} inputs, {m[2]} statements", r["config"])].append(r)
    sizes = sorted(
        {k[0] for k in groups}, key=lambda t: (int(t.split()[2]), int(t.split()[0]))
    )
    configs = [
        "cuts",
        "cuts_negated",
        "cut_values",
        "exact_cone",
        "exact_support",
        "exact_any",
    ]
    print(
        "### Time (median per operation) and values flagged (not planted, per operation)\n"
    )
    rows = []
    for size in sizes:
        cells = [size]
        for c in configs:
            rs = [r for r in groups.get((size, c), []) if r["status"] == "ok"]
            if not rs:
                cells.append("")
                continue
            cells.append(
                f"{fmt_time(statistics.median(r['time_s'] for r in rs))}, "
                f"{statistics.mean(r['flagged_unplanted'] for r in rs):.1f} of {statistics.mean(r['statements'] for r in rs):.0f}"
            )
        rows.append(cells)
    print(table(["size", *configs], rows))
    print("\n### Planted matches found\n")
    rows = []
    for c in configs:
        kinds: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
        for r in records:
            if r["config"] == c and r["status"] == "ok":
                for kind, (found, total) in r["planted_by_kind"].items():
                    kinds[kind][0] += found
                    kinds[kind][1] += total
        rows.append([c, *[f"{kinds[k][0]}/{kinds[k][1]}" for k in ("local", "sop")]])
    print(table(["method", "local", "sop"], rows))
    print("\n### Cost against the arity limit (200- and 256-statement operations)\n")
    rows = []
    for k in (4, 5, 6):
        cells = [str(k)]
        for c in ("cuts", "exact_cone"):
            rs = [r for r in records if r["config"] == f"{c}_arity{k}"]
            ok = [r for r in rs if r["status"] == "ok"]
            if not rs:
                cells.append("not run")
                continue
            if not ok:
                cells.append("timeout")
                continue
            text = f"median {fmt_time(statistics.median(r['time_s'] for r in ok))}, slowest {fmt_time(max(r['time_s'] for r in ok))}"
            if c == "cuts":
                text += f", {statistics.median(r['stats']['total_cuts'] for r in ok):,.0f} cuts"
            if len(ok) < len(rs):
                text += f" ({len(rs) - len(ok)} time out)"
            cells.append(text)
        rows.append(cells)
    print(table(["arity limit", "cuts", "exact (cone)"], rows))


@cli.command()
def hierarchy() -> None:
    """Tables comparing references with copying."""
    records = [r for r in load("hierarchy") if "op" in r]
    by: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in records:
        by[(r["library"], r["how"])].append(r)
    libraries = sorted(
        {r["library"] for r in records},
        key=lambda n: (n.split("_")[0], [int(x) for x in re.findall(r"\d+", n)]),
    )
    methods = ["tt", "bdd", "sat", "sat_clauses", "sat_hybrid", "copy"]
    print("### Deepest level: median time per operation, and the copy's flat graph\n")
    rows = []
    for lib in libraries:
        cells = [lib]
        deepest_level = max(
            int(re.match(r"L(\d+)", r["op"])[1]) for r in records if r["library"] == lib
        )
        for m in methods:
            rs = [
                r
                for r in by[(lib, m)]
                if int(re.match(r"L(\d+)", r["op"])[1]) == deepest_level
            ]
            ok = [r for r in rs if r["status"] == "ok"]
            if not rs:
                cells.append("timeout")
                continue
            if not ok:
                cells.append("limit")
                continue
            text = fmt_time(statistics.median(r["time_s"] for r in ok))
            if m == "copy":
                text += f", {statistics.median(r['flat_nodes'] for r in ok):,.0f} nodes"
            if len(ok) < len(rs):
                text += f" ({len(rs) - len(ok)} of {len(rs)} past the limit)"
            cells.append(text)
        rows.append(cells)
    print(table(["library", *methods], rows))
    print("\n### Whole library: total time, SAT refinements, and agreement\n")
    rows = []
    for lib in libraries:
        cells = [lib]
        hashes = set()
        for m in methods:
            rs = by[(lib, m)]
            ok = [r for r in rs if r["status"] == "ok"]
            # Runs that hit their time limit only checked some operations.
            if len(ok) == len(rs) and rs and all(r["run_status"] == "ok" for r in rs):
                hashes.add("".join(r["partition_hash"] for r in rs))
            if rs and rs[0]["run_status"] != "ok":
                cells.append(f"stopped after {len(rs)} operations")
                continue
            total = fmt_time(sum(r["time_s"] for r in ok)) if ok else ""
            if m.startswith("sat") and ok:
                total += f", {sum(r['stats'].get('refinements', 0) for r in ok):,.0f} refinements"
            cells.append(
                total
                + (f" ({len(rs) - len(ok)} unfinished)" if len(ok) < len(rs) else "")
            )
        planted = sum(r["planted_total"] for r in by[(lib, "tt")])
        found = sum(r["planted_found"] for r in by[(lib, "tt")])
        cells.append(f"{len(hashes) <= 1}, planted {found}/{planted}")
        rows.append(cells)
    print(table(["library", *methods, "methods that finished agree"], rows))


@cli.command()
def steady() -> None:
    """Tables for value operations that compile."""
    records = load("steady_state")
    flat = [r for r in records if r["part"] == "flat"]
    print("### Flat value operations, combined algorithm (median / slowest of 5)\n")
    groups: dict[tuple[int, int, str, str], list[dict]] = collections.defaultdict(list)
    for r in flat:
        groups[(r["inputs_n"], r["statements_n"], r["variant"], r["method"])].append(r)
    rows = []
    for (i, n, variant, method), rs in sorted(groups.items()):
        if method != "auto":
            continue
        ok = [r for r in rs if r["status"] == "ok"]
        rows.append(
            [
                str(i),
                str(n),
                variant,
                fmt_time(statistics.median(r["time_s"] for r in ok)),
                fmt_time(max(r["time_s"] for r in ok)),
                f"{statistics.median(r['stats'].get('sat_calls', 0) for r in ok):.0f}",
                f"{statistics.median(r['stats'].get('sat_different', 0) for r in ok):.0f}",
                fmt_time(
                    statistics.median(
                        r["time_s"] for r in groups[(i, n, variant, "tt")]
                    )
                ),
            ]
        )
    print(
        table(
            [
                "inputs",
                "statements",
                "operations",
                "median",
                "slowest",
                "SAT calls",
                "counterexamples",
                "truth tables, median",
            ],
            rows,
        )
    )
    refs = [r for r in records if r["part"] == "refs"]
    print("\n### Libraries with references (SAT with the hybrid refinement)\n")
    by: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in refs:
        by[(r["library"], r["run"])].append(r)
    rows = []
    for (lib, run), rs in sorted(by.items()):
        ok = [r for r in rs if r["status"] == "ok"]
        st = [r.get("stats", {}) for r in ok]
        rows.append(
            [
                lib,
                run,
                str(len(ok)),
                fmt_time(sum(r["time_s"] for r in ok)),
                f"{sum(x.get('sat_calls', 0) for x in st):.0f}",
                f"{sum(x.get('patterns_added', 0) for x in st):.0f}",
                f"{max((x.get('patterns_added', 0) for x in st), default=0):.0f}",
                str(
                    sum(
                        r["redundant"] > 0 or "stopped_at" in r.get("stats", {})
                        for r in ok
                    )
                ),
                str(rs[0].get("edited_ops", "")),
            ]
        )
    print(
        table(
            [
                "library",
                "run",
                "operations",
                "total time",
                "SAT calls",
                "patterns stored",
                "most in one operation",
                "operations with a redundant value",
                "operations edited",
            ],
            rows,
        )
    )
    edits = [r for r in records if r["part"] == "edits"]
    print("\n### Rechecking after one edit\n")
    rows = []
    for lib in sorted({r["library"] for r in edits}):
        for keep in (True, False):
            rs = [
                r for r in edits if r["library"] == lib and r["keeps_function"] == keep
            ]
            c = sorted(r["checked"] for r in rs)
            rows.append(
                [
                    lib,
                    "keeps the function" if keep else "changes it",
                    str(rs[0]["library_ops"]),
                    f"{statistics.median(c):.0f}",
                    str(c[int(0.9 * len(c))]),
                    str(c[-1]),
                    f"{statistics.mean(c):.2f}",
                    fmt_time(statistics.median(r["time_s"] for r in rs)),
                    fmt_time(max(r["time_s"] for r in rs)),
                ]
            )
    print(
        table(
            [
                "library",
                "edit",
                "operations",
                "rechecked: median",
                "90th percentile",
                "most",
                "mean",
                "time: median",
                "slowest",
            ],
            rows,
        )
    )


@cli.command()
def cadical() -> None:
    """Table for CaDiCaL on each planted pair of the adversarial instances."""
    records = load("cadical")
    by: dict[str, list[dict]] = collections.defaultdict(list)
    for r in records:
        by[pathlib.Path(r["file"]).stem].append(r)

    def key(name: str) -> tuple[str, int]:
        return (re.sub(r"\d+", "", name), int(re.findall(r"\d+", name)[0]))

    rows = []
    for name in sorted(by, key=key):
        pairs = [r for r in by[name] if r["status"] != "file_timeout"]
        unfinished = any(r["status"] == "file_timeout" for r in by[name])
        if not pairs:
            rows.append([name, "0", "yes", "", "", ""])
            continue
        rows.append(
            [
                name,
                str(len(pairs)),
                "yes" if unfinished else "",
                fmt_time(max(r["time_s"] for r in pairs)),
                fmt_time(sum(r["time_s"] for r in pairs)),
                f"{max(r['conflicts'] for r in pairs):,}",
            ]
        )
    print(
        table(
            [
                "instance",
                "pairs decided",
                "ran out of 600 s",
                "slowest pair",
                "all pairs decided",
                "most conflicts",
            ],
            rows,
        )
    )


@cli.command()
def library() -> None:
    """Table for checking each library operation once."""
    records = load("library")
    rows = []
    for m in ("strash", "cuts4", "tt", "bdd_first_use", "sweep", "portfolio"):
        rs = [r for r in records if r["config"] == m]
        ok = [r for r in rs if r["status"] == "ok"]
        rows.append(
            [
                m,
                f"{len(ok)}/{len(rs)}",
                fmt_time(sum(r["time_s"] for r in ok)),
                fmt_time(max(r["time_s"] for r in ok)),
                f"{sum(r['planted_found'] for r in ok)}/{sum(r['planted_total'] for r in ok)}",
            ]
        )
    ands = [r["ands"] for r in records if r["config"] == "strash"]
    print(
        f"{len(ands)} operations, {sum(ands)} `and` nodes in all, largest {max(ands)}\n"
    )
    print(
        table(
            ["method", "finished", "total time", "slowest", "planted pairs found"], rows
        )
    )


@cli.command()
def limits() -> None:
    """Tables for conflict limits and seeds."""
    records = load("limits")
    by: dict[str, list[dict]] = collections.defaultdict(list)
    for r in records:
        by[r.get("extra", "")].append(r)
    rows = []
    for extra, rs in sorted(by.items()):
        ok = [r for r in rs if r["status"] == "ok"]
        undecided = sum(r["stats"]["sat_undecided"] for r in ok)
        missed = sum(r["planted_total"] - r["planted_found"] for r in ok)
        affected = sum(1 for r in ok if r["stats"]["sat_undecided"] > 0)
        rows.append(
            [
                extra,
                str(len(rs)),
                str(len(ok)),
                str(affected),
                str(undecided),
                str(missed),
                fmt_time(sum(r["time_s"] for r in rs)),
            ]
        )
    print(
        table(
            [
                "options",
                "instances",
                "finished",
                "instances with undecided pairs",
                "undecided pairs",
                "planted pairs missed",
                "total time",
            ],
            rows,
        )
    )
    # Exact runs with different seeds must find identical classes.
    hashes: dict[str, set[str]] = collections.defaultdict(set)
    for r in records:
        if r["config"] == "portfolio" and r["status"] == "ok":
            hashes[r["instance"]].add(r["partition_hash"])
    differing = [name for name, hs in hashes.items() if len(hs) > 1]
    print(
        f"\nInstances finished with every seed: {len(hashes)}; with differing classes: {len(differing)}"
    )


if __name__ == "__main__":
    cli()
