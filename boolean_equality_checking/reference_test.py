"""Regression and cross-check test suite for the boolean_equality_checking reference implementation.

Verifies every correctness fix, edge case, and algorithmic optimization:
1. DLP 62 human-readable registered-operation order (or before implies, xor
   before eq, project before stdlib, symmetry & counting-order tie-breaks).
2. Arbitrary-width inputs (I = 64, 65, 91, 128, 200, 300) with no shift UB,
   cross-checking optimized Matcher against --plain 1.
3. Dynamic pool sizing (> 8,192 literals) and > 4,096 inputs for Bdd/Diagram
   unique-table hash mixing.
4. drop_views on I > 20 (BDD dispatch in has_constant_value) and interacting
   unused views like xor(u1, u2).
5. --mode registry with --method auto on I > 16 (registry_only threading).
6. Wide table lookup (k > 6, 8x8 bit-matrix transpose) cross-checked against BDD.
7. BDD Chow/Walsh level_signatures + diagram_groups symmetry detection on I > 20.
8. Deep and/or chains (I = 100) exercising BDD-guided polarity seeding.
9. Random programs cross-checked across --method tt, --method bdd, --method auto,
   --plain 1, and gen/program_check.py, plus --mode fix with --keep_searches 1
   --check_search 1.

Run with:
    uv run --frozen python boolean_equality_checking/reference_test.py
    uv run --frozen python boolean_equality_checking/reference_test.py --beq /tmp/beq_san
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "gen"))

import program as gen_program
import program_check


def run_beq(
    beq: Path, args: list[str], *, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    """Run beq and fail loudly on non-zero exit."""
    res = subprocess.run(  # noqa: S603 - Runs this directory's own beq binary.
        [str(beq), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if res.returncode != 0:
        raise AssertionError(
            f"beq failed ({res.returncode}): {args}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        )
    return res


def check_details(beq: Path, prog_text: str, extra_args: list[str]) -> dict[str, dict]:
    """Run beq program --mode check and return {op_name: report_json}."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.prog"
        d = Path(td) / "details.jsonl"
        p.write_text(prog_text, encoding="ascii")
        run_beq(
            beq,
            ["program", str(p), "--mode", "check", "--details", str(d), *extra_args],
        )
        out: dict[str, dict] = {}
        for line in d.read_text(encoding="ascii").splitlines():
            row = json.loads(line)
            out[row["op"]] = row
        return out


def lib_header(
    registered: list[str] | None = None, std_registered: list[str] | None = None
) -> str:
    """Build program header with standard registered definitions."""
    regs = registered if registered is not None else list(gen_program.REGISTERED)
    lines = ["registered " + " ".join(regs)]
    if std_registered:
        lines.append("std_registered " + " ".join(std_registered))
    for name, (views, stmts, out) in gen_program.DEFINITIONS.items():
        lines.append(f"op {name} bool {views}")
        lines.extend(stmts)
        lines.append(f"out {out}")
        lines.append("end")
    return "\n".join(lines) + "\n"


def test_dlp62_order(beq: Path) -> None:
    """Verify human-readable DLP 62 order and project-before-stdlib rule."""
    # Standard operations compile cleanly in their canonical definitions.
    prog = lib_header()
    py_res = {r["op"]: r["errors"] for r in program_check.check_program(prog)}
    for name in gen_program.REGISTERED:
        assert py_res[name] == {}, f"{name} failed program_check: {py_res[name]}"
    for extra in (
        ["--method", "tt"],
        ["--method", "bdd"],
        ["--method", "auto"],
        ["--method", "tt", "--plain", "1"],
    ):
        c_res = check_details(beq, prog, extra)
        for name in gen_program.REGISTERED:
            assert c_res[name]["errors"] == {}, (
                f"{name} failed beq {extra}: {c_res[name]['errors']}"
            )

    # Project-registered op (nor) precedes stdlib-registered op (or) of same (ands, views).
    nor_prog = (
        "registered or nor\n"
        "std_registered or\n"
        "op or bool 2\nnot 1\nnot 2\nand 3 4\nnot 5\nout 6\nend\n"
        "op nor bool 2\nnot 1\nnot 2\nand 3 4\nout 5\nend\n"
        # f computes nor(1, 2) via not(or(1, 2)): should match nor (project) over or (stdlib).
        "op f bool 2\ncall or 1 2\nnot 3\nout 4\nend\n"
    )
    py_nor = {r["op"]: r["errors"] for r in program_check.check_program(nor_prog)}
    c_nor = check_details(beq, nor_prog, ["--method", "tt"])
    c_nor_bdd = check_details(beq, nor_prog, ["--method", "bdd"])
    assert py_nor["or"] == {}, (
        f"stdlib or should not follow project nor: {py_nor['or']}"
    )
    assert c_nor["or"]["errors"] == py_nor["or"]
    assert c_nor["f"]["errors"] == py_nor["f"]
    assert c_nor_bdd["f"]["errors"] == py_nor["f"]
    # nor is project-registered before stdlib or, so nor's own definition doesn't follow or.
    assert py_nor["nor"] == {}, f"project nor should precede stdlib or: {py_nor['nor']}"
    assert c_nor["nor"]["errors"] == {}


def test_wide_inputs_no_ub(beq: Path) -> None:
    """Test I = 64, 65, 91, 128, 200, 300 with planted matches across bit >= 64."""
    for n_inputs in (64, 65, 91, 128, 200, 300):
        # Build a chain touching every input, plus planted matches on high-index inputs.
        stmts = []
        nxt = n_inputs + 1
        # Plant an xor(x, y) written out using high-index inputs (n_inputs-1, n_inputs).
        a, b = n_inputs - 1, n_inputs
        stmts.append(f"not {b}")
        nb = nxt
        nxt += 1
        stmts.append(f"and {a} {nb}")
        t1 = nxt
        nxt += 1
        stmts.append(f"not {a}")
        na = nxt
        nxt += 1
        stmts.append(f"and {b} {na}")
        t2 = nxt
        nxt += 1
        stmts.append(f"call or {t1} {t2}")
        x_val = nxt
        nxt += 1
        # Combine with remaining inputs via an or-chain so all inputs are used.
        acc = x_val
        for i in range(1, n_inputs - 1):
            stmts.append(f"call or {i} {acc}")
            acc = nxt
            nxt += 1
        prog = (
            lib_header()
            + f"op big_{n_inputs} bool {n_inputs}\n"
            + "\n".join(stmts)
            + f"\nout {acc}\nend\n"
        )
        override = [
            "--method",
            "auto",
            "--step_budget",
            "0",
            "--max_views",
            "0",
            "--max_inputs",
            "0",
            "--statement_limit",
            "0",
        ]
        fast = check_details(beq, prog, override)[f"big_{n_inputs}"]
        plain = check_details(beq, prog, [*override, "--plain", "1"])[f"big_{n_inputs}"]
        assert fast["errors"] == plain["errors"], (
            f"I={n_inputs} mismatch:\n  fast ={fast['errors']}\n  plain={plain['errors']}"
        )
        assert "match" in fast["errors"], (
            f"I={n_inputs} missed planted match: {fast['errors']}"
        )
        assert fast["errors"]["match"][1] == "xor", (
            f"I={n_inputs} expected xor match, got {fast['errors']['match']}"
        )
        assert fast["errors"]["match"][3] == [a, b], (
            f"I={n_inputs} wrong args: {fast['errors']['match']}"
        )


def test_deep_chain_guided_seeding(beq: Path) -> None:
    """Test a 100-input pure and-chain + planted match (all-0 under uniform random samples)."""
    n_inputs = 100
    stmts = []
    nxt = n_inputs + 1
    acc = 1
    for i in range(2, n_inputs - 1):
        stmts.append(f"and {acc} {i}")
        acc = nxt
        nxt += 1
    # Plant an or(acc, n_inputs) written out via De Morgan at the top of the 98-deep and-chain.
    stmts.append(f"not {acc}")
    na = nxt
    nxt += 1
    stmts.append(f"not {n_inputs}")
    nb = nxt
    nxt += 1
    stmts.append(f"and {na} {nb}")
    t = nxt
    nxt += 1
    stmts.append(f"not {t}")
    out_v = nxt
    nxt += 1
    # Unused input n_inputs - 1 is avoided by combining with it.
    stmts.append(f"and {n_inputs - 1} {out_v}")
    final_v = nxt
    prog = (
        lib_header()
        + f"op deep_and bool {n_inputs}\n"
        + "\n".join(stmts)
        + f"\nout {final_v}\nend\n"
    )
    override = ["--method", "auto", "--step_budget", "0", "--max_views", "0"]
    fast = check_details(beq, prog, override)["deep_and"]
    plain = check_details(beq, prog, [*override, "--plain", "1"])["deep_and"]
    assert fast["errors"] == plain["errors"], (
        f"deep_and mismatch: {fast['errors']} vs {plain['errors']}"
    )
    assert fast["errors"]["match"][1] == "or", f"expected or match: {fast['errors']}"
    assert fast["t"]["total"] < 1.0, f"deep_and too slow: {fast['t']}"


def test_dynamic_pool_and_4096_inputs(beq: Path) -> None:
    """Test > 8,192 literals in Matcher pool and > 4,096 inputs in Bdd/Diagram."""
    n_inputs = 4500
    stmts = []
    num_view = n_inputs + 1
    nxt = n_inputs + 2
    # Balanced binary tree of xor/and combining all 4,500 inputs (> 8,999 literals, > 4,096 BDD levels).
    layer = list(range(1, n_inputs + 1))
    depth = 0
    while len(layer) > 1:
        next_layer = []
        op_kind = "call xor" if (depth % 2 == 0) else "and"
        for i in range(0, len(layer) - 1, 2):
            stmts.append(f"{op_kind} {layer[i]} {layer[i + 1]}")
            next_layer.append(nxt)
            nxt += 1
        if len(layer) % 2 == 1:
            next_layer.append(layer[-1])
        layer = next_layer
        depth += 1
    acc = layer[0]
    stmts.append(f"num sel {acc} {num_view} {num_view}")
    out_num = nxt
    prog = (
        lib_header(["or", "xor"])
        + f"op huge mixed {n_inputs} 1\n"
        + "\n".join(stmts)
        + f"\nout {out_num}\nend\n"
    )
    # Verify both BDD building (> 4096 levels) and Matcher pool (> 8192 literals) succeed cleanly.
    res = check_details(
        beq,
        prog,
        [
            "--method",
            "auto",
            "--step_budget",
            "0",
            "--max_views",
            "0",
            "--max_inputs",
            "0",
            "--statement_limit",
            "0",
            "--bdd_nodes",
            "4000000",
        ],
    )["huge"]
    assert "limits" not in res["errors"], f"unexpected limit error: {res['errors']}"
    assert set(res["errors"]) <= {
        "order_arguments",
        "order_statements",
        "order_grouping",
    }, f"unexpected errors on huge op: {res['errors']}"


def test_drop_views_wide_and_interacting(beq: Path) -> None:
    """Test drop_views on I > 20 (no OOM) and interacting unused views xor(u1, u2)."""
    # Part A: I = 24 with 2 unused views (23, 24).
    n_inputs = 24
    stmts = []
    nxt = n_inputs + 1
    acc = 1
    for i in range(2, 23):
        stmts.append(f"and {acc} {i}")
        acc = nxt
        nxt += 1
    prog_wide = (
        lib_header()
        + f"op wide_unused bool {n_inputs}\n"
        + "\n".join(stmts)
        + f"\nout {acc}\nend\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "wide.prog"
        out_p = Path(td) / "wide_fixed.prog"
        p.write_text(prog_wide, encoding="ascii")
        res = run_beq(
            beq,
            [
                "program",
                str(p),
                "--mode",
                "fix",
                "--max_views",
                "0",
                "--out",
                str(out_p),
            ],
        )
        summary = json.loads(res.stdout)
        assert summary["statuses"].get("ok", 0) == len(gen_program.DEFINITIONS) + 1, (
            summary
        )
        assert summary["ops_with_errors_after"] == 0, summary

    # Part B: interacting unused views u1 (3), u2 (4) via xor(3, 4) with kept views 1, 2.
    # Uniform substitution u1=u2=1 or u1=u2=2 makes xor(u1, u2) constant false!
    # Per-view substitution u1=1, u2=2 avoids constants and succeeds.
    prog_xor = (
        lib_header() + "op interact bool 4\n"
        "call xor 3 4\n"  # 5 = u1 ^ u2
        "and 1 5\n"  # 6 = k1 & (u1 ^ u2)
        "not 5\n"  # 7 = ~(u1 ^ u2)
        "and 1 7\n"  # 8 = k1 & ~(u1 ^ u2)
        "call or 2 6\n"  # 9 = k2 | (k1 & (u1 ^ u2))
        "call or 2 8\n"  # 10 = k2 | (k1 & ~(u1 ^ u2))
        "call or 9 10\n"  # 11 = k1 | k2 (u1, u2 unused!)
        "out 11\nend\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "interact.prog"
        out_p = Path(td) / "interact_fixed.prog"
        p.write_text(prog_xor, encoding="ascii")
        res = run_beq(
            beq,
            [
                "program",
                str(p),
                "--mode",
                "fix",
                "--max_views",
                "0",
                "--out",
                str(out_p),
            ],
        )
        summary = json.loads(res.stdout)
        assert summary["statuses"].get("unused view", 0) == 0, (
            f"drop_views failed on xor(u1, u2): {summary}"
        )
        assert summary["ops_with_errors_after"] == 0, summary


def test_registry_mode_wide(beq: Path) -> None:
    """Verify --mode registry respects registry_only on I > 16 (--method auto)."""
    # Build a 20-input op with an order_arguments violation (views 2, 1 swapped on `and`)
    # and an unused view (20). In --mode registry, neither should be reported!
    stmts = ["and 2 1"]  # order_arguments violation (2 before 1)
    nxt = 21
    acc = 21
    for i in range(3, 20):
        stmts.append(f"and {acc} {i}")
        nxt += 1
        acc = nxt
    prog = (
        lib_header(["or"])
        + "op wide_reg bool 20\n"
        + "\n".join(stmts)
        + f"\nout {acc}\nend\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "reg.prog"
        p.write_text(prog, encoding="ascii")
        res_auto = json.loads(
            run_beq(
                beq,
                [
                    "program",
                    str(p),
                    "--mode",
                    "registry",
                    "--register",
                    "xor",
                    "--method",
                    "auto",
                ],
            ).stdout
        )
        res_tt = json.loads(
            run_beq(
                beq,
                [
                    "program",
                    str(p),
                    "--mode",
                    "registry",
                    "--register",
                    "xor",
                    "--method",
                    "tt",
                ],
            ).stdout
        )
        assert res_auto["errors"] == res_tt["errors"], (
            f"auto vs tt registry mismatch: {res_auto['errors']} vs {res_tt['errors']}"
        )
        assert "order_arguments" not in res_auto["errors"], res_auto["errors"]
        assert "unused_view" not in res_auto["errors"], res_auto["errors"]


def test_wide_lookup_transpose(beq: Path) -> None:
    """Cross-check wide lookup (k = 10 > 6) bit-matrix transpose against BDD."""
    # Define a 10-view op whose AIG exceeds limit (or just a 10-view parity/complex op),
    # then call it inside a 14-input op and compare --method tt vs --method bdd.
    callee_stmts = []
    nxt = 11
    # Build enough xors so record_aig exceeds limit (16 * 10 = 160 nodes) or mixes all 10 views.
    acc = 1
    for i in range(2, 11):
        callee_stmts.append(f"call xor {acc} {i}")
        acc = nxt
        nxt += 1
    # Add non-linear interactions to exceed AIG limit and force table lookup.
    for i in range(1, 10):
        for j in range(i + 1, 11):
            callee_stmts.append(f"and {i} {j}")
            pair = nxt
            nxt += 1
            callee_stmts.append(f"call xor {acc} {pair}")
            acc = nxt
            nxt += 1
    callee = "op wide10 bool 10\n" + "\n".join(callee_stmts) + f"\nout {acc}\nend\n"
    caller = (
        "op caller14 bool 14\n"
        "and 1 2\n"  # 15
        "call or 3 4\n"  # 16
        "call xor 5 6\n"  # 17
        "call wide10 15 16 17 7 8 9 10 11 12 13\n"  # 18
        "call xor 18 14\n"  # 19
        "out 19\nend\n"
    )
    prog = lib_header() + callee + caller
    r_tt = check_details(beq, prog, ["--method", "tt"])["caller14"]
    r_bdd = check_details(beq, prog, ["--method", "bdd"])["caller14"]
    assert r_tt["errors"] == r_bdd["errors"], (
        f"wide lookup mismatch: {r_tt['errors']} vs {r_bdd['errors']}"
    )


def test_bdd_symmetry_groups(beq: Path) -> None:
    """Verify diagram_groups + Chow/Walsh level_signatures on a 22-input op."""
    # Views {1, 2, 3, 4} symmetric (all OR'd), {5, 6, 7} symmetric (all AND'd),
    # {8..19} asymmetric chain, {20, 21, 22} unused (symmetric with each other).
    stmts = [
        "call or 1 2",  # 23
        "call or 3 23",  # 24
        "call or 4 24",  # 25 = 1|2|3|4
        "and 5 6",  # 26
        "and 7 26",  # 27 = 5&6&7
        "not 8",  # 28
        "call or 9 28",  # 29
        "and 10 29",  # 30
        "call or 11 30",  # 31
        "not 12",  # 32
        "call or 31 32",  # 33
        "and 13 33",  # 34
        "call or 14 34",  # 35
        "not 15",  # 36
        "call or 35 36",  # 37
        "and 16 37",  # 38
        "call or 17 38",  # 39
        "not 18",  # 40
        "call or 39 40",  # 41
        "and 19 41",  # 42
        "and 25 27",  # 43
        "call xor 42 43",  # 44
    ]
    prog = lib_header() + "op sym22 bool 22\n" + "\n".join(stmts) + "\nout 44\nend\n"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "sym.prog"
        p.write_text(prog, encoding="ascii")
        res = run_beq(
            beq,
            [
                "program",
                str(p),
                "--mode",
                "groups",
                "--method",
                "auto",
                "--max_views",
                "0",
            ],
        )
        groups_line = next(
            ln for ln in res.stdout.splitlines() if ln.startswith("sym22 ")
        )
        labels = [int(x) for x in groups_line.split()[1:]]
        assert len(labels) == 22, labels
        # Group {0,1,2,3} equal
        assert len(set(labels[0:4])) == 1, labels
        # Group {4,5,6} equal and distinct from {0..3}
        assert len(set(labels[4:7])) == 1, labels
        assert labels[4] != labels[0], labels
        # Unused views {19,20,21} equal and distinct from used views
        assert len(set(labels[19:22])) == 1, labels
        assert labels[19] not in set(labels[0:19]), labels
        # Asymmetric views 7..18 distinct from {0..3}, {4..6}, and mostly distinct from each other
        assert len(set(labels[7:19])) == 12, labels


def test_random_crosscheck_and_fix(beq: Path) -> None:
    """Cross-check random programs across tt, bdd, auto, plain, and program_check.py."""
    for seed in (1, 2, 3, 4, 5):
        settings = gen_program.Settings(
            levels=4,
            boolean_per_level=6,
            mixed_per_level=2,
            views=(2, 6),
            statements=(4, 16),
            comparisons=(1, 3),
            mixed_statements=(3, 10),
        )
        text = gen_program.generate(random.Random(seed), settings)  # noqa: S311 - Reproducible test seed.
        py_res = {r["op"]: r["errors"] for r in program_check.check_program(text)}
        c_tt = check_details(beq, text, ["--method", "tt"])
        c_bdd = check_details(beq, text, ["--method", "bdd"])
        c_auto = check_details(beq, text, ["--method", "auto"])
        c_plain = check_details(beq, text, ["--method", "tt", "--plain", "1"])
        for op_name, want in py_res.items():
            for label, got in (
                ("tt", c_tt[op_name]["errors"]),
                ("bdd", c_bdd[op_name]["errors"]),
                ("auto", c_auto[op_name]["errors"]),
                ("plain", c_plain[op_name]["errors"]),
            ):
                assert got == want, (
                    f"seed={seed} op={op_name} mode={label} mismatch:\n  got ={got}\n  want={want}"
                )
        # Also test --mode fix with --keep_searches 1 --check_search 1.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "rand.prog"
            out_p = Path(td) / "rand_fixed.prog"
            p.write_text(text, encoding="ascii")
            res = run_beq(
                beq,
                [
                    "program",
                    str(p),
                    "--mode",
                    "fix",
                    "--keep_searches",
                    "1",
                    "--check_search",
                    "1",
                    "--out",
                    str(out_p),
                ],
            )
            summary = json.loads(res.stdout)
            allowed_unfixable = summary["statuses"].get("literal", 0)
            assert summary["ops_with_errors_after"] == allowed_unfixable, (
                f"seed={seed} fix left unexpected errors: {summary}"
            )
            py_after = program_check.check_program(out_p.read_text(encoding="ascii"))
            unfixable_seen = 0
            for row in py_after:
                if row["errors"]:
                    assert set(row["errors"]) == {"literal"}, (
                        f"seed={seed} fixed op {row['op']} failed program_check: {row['errors']}"
                    )
                    unfixable_seen += 1
            assert unfixable_seen == allowed_unfixable, (
                f"seed={seed} unfixable count mismatch: {unfixable_seen} vs {allowed_unfixable}"
            )


def test_dlp60_grouping_and_factoring(beq: Path) -> None:
    """Verify DLP 60 associative grouping and DLP 61 distributive factoring + fixes."""
    prog = (
        lib_header()
        # 1. Non-canonical associative grouping: a & (b & c) -> must fold (a, b) first.
        + "op g_bad3 bool 3\nand 2 3\nand 1 4\nout 5\nend\n"
        # 2. Balanced tree: (a & b) & (c & d) -> must flatten to left-fold.
        + "op g_bal4 bool 4\nand 1 2\nand 3 4\nand 5 6\nout 7\nend\n"
        # 3. Canonical left-fold: (a & b) & c then & d -> clean!
        + "op g_ok4 bool 4\nand 1 2\nand 3 5\nand 4 6\nout 7\nend\n"
        # 4. Shared intermediate (a & b) read twice: not single-use, allowed!
        + "op g_shared bool 4\nand 1 2\nand 3 4\ncall or 5 6\nand 5 7\nout 8\nend\n"
        # 5. Distributive factoring: (a & b) | (a & c) -> factor a -> a & (b | c).
        + "op f_and_or bool 3\nand 1 2\nand 1 3\ncall or 4 5\nout 6\nend\n"
        # 6. Dual factoring: (a | b) & (a | c) -> factor a -> a | (b & c).
        + "op f_or_and bool 3\ncall or 1 2\ncall or 1 3\nand 4 5\nout 6\nend\n"
        # 7. Distributive and over xor: (a & b) ^ (a & c) -> a & (b ^ c).
        + "op f_and_xor bool 3\nand 1 2\nand 1 3\ncall xor 4 5\nout 6\nend\n"
        # 8. Multi-term factoring: (a & b) | (a & c) | (a & d) -> a & (b | c | d).
        + "op f_multi bool 4\nand 1 2\nand 1 3\ncall or 5 6\nand 1 4\ncall or 7 8\nout 9\nend\n"
        # 9. Tie-break: (a & b) | (a & c) | (b & d) -> both a and b appear twice; a < b wins.
        + "op f_tie bool 4\nand 1 2\nand 1 3\ncall or 5 6\nand 2 4\ncall or 7 8\nout 9\nend\n"
    )
    py_res = {r["op"]: r["errors"] for r in program_check.check_program(prog)}
    c_tt = check_details(beq, prog, ["--method", "tt"])
    c_bdd = check_details(beq, prog, ["--method", "bdd"])
    c_auto = check_details(beq, prog, ["--method", "auto"])
    for name in (
        "g_bad3",
        "g_bal4",
        "g_ok4",
        "f_and_or",
        "f_or_and",
        "f_and_xor",
        "f_multi",
        "f_tie",
    ):
        assert c_tt[name]["errors"] == py_res[name], (
            f"{name} tt mismatch: {c_tt[name]['errors']} vs {py_res[name]}"
        )
        assert c_bdd[name]["errors"] == py_res[name], (
            f"{name} bdd mismatch: {c_bdd[name]['errors']} vs {py_res[name]}"
        )
        assert c_auto[name]["errors"] == py_res[name], (
            f"{name} auto mismatch: {c_auto[name]['errors']} vs {py_res[name]}"
        )
    assert "order_grouping" in py_res["g_bad3"], py_res["g_bad3"]
    assert "order_grouping" in py_res["g_bal4"], py_res["g_bal4"]
    assert py_res["g_ok4"] == {}, py_res["g_ok4"]
    assert py_res["f_and_or"] == {"order_factor": [6, 1]}, py_res["f_and_or"]
    assert py_res["f_or_and"] == {"order_factor": [6, 1]}, py_res["f_or_and"]
    assert py_res["f_and_xor"] == {"order_factor": [6, 1]}, py_res["f_and_xor"]
    assert py_res["f_multi"]["order_factor"] == [9, 1], py_res["f_multi"]
    assert py_res["f_tie"]["order_factor"] == [9, 1], py_res["f_tie"]

    # Fix all of them and verify the fixed output passes both beq and program_check!
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "dlp60.prog"
        out_p = Path(td) / "dlp60_fixed.prog"
        p.write_text(prog, encoding="ascii")
        res = run_beq(beq, ["program", str(p), "--mode", "fix", "--out", str(out_p)])
        summary = json.loads(res.stdout)
        assert summary["ops_with_errors_after"] == 0, summary
        fixed_text = out_p.read_text(encoding="ascii")
        for row in program_check.check_program(fixed_text):
            assert row["errors"] == {}, f"fixed {row['op']} failed: {row['errors']}"


def test_conservative_limits(beq: Path) -> None:
    """Verify default DLP 59 conservative caps: 20 views, 256 stmts, 512 inputs, 65,536 BDD nodes."""
    # 1. > 20 boolean input interface views -> limits: views
    p_views = lib_header() + "op v21 bool 21\nand 1 2\nout 22\nend\n"
    r_views = check_details(beq, p_views, ["--method", "auto"])["v21"]
    assert r_views["errors"].get("limits") == "views", r_views["errors"]

    # 2. > 256 boolean statements -> limits: statements
    stmts257 = ["not 1"] + [f"and {i % 10 + 1} {(i + 1) % 10 + 1}" for i in range(256)]
    p_stmts = (
        lib_header() + "op s257 bool 10\n" + "\n".join(stmts257) + "\nout 267\nend\n"
    )
    r_stmts = check_details(beq, p_stmts, ["--method", "auto"])["s257"]
    assert r_stmts["errors"].get("limits") == "statements", r_stmts["errors"]

    # 3. Mixed op with 60 comparisons (21..512 inputs) and small BDD -> compiles cleanly!
    cmp_lines = [f"cmp c{i} 1 #{i}" for i in range(60)]
    nxt = 62
    acc = 2
    for i in range(3, 62):
        cmp_lines.append(f"call or {acc} {i}")
        acc = nxt
        nxt += 1
    p_mix60 = (
        lib_header()
        + "op mix60 mixed 0 1\n"
        + "\n".join(cmp_lines)
        + f"\nout {acc}\nend\n"
    )
    r_mix60 = check_details(beq, p_mix60, ["--method", "auto"])["mix60"]
    assert "limits" not in r_mix60["errors"], r_mix60["errors"]

    # 4. Mixed op with 520 comparisons (> 512 boolean inputs) -> limits: inputs
    cmp520 = [f"cmp c{i} 1 #{i}" for i in range(520)] + ["and 2 3"]
    p_mix520 = (
        lib_header() + "op mix520 mixed 0 1\n" + "\n".join(cmp520) + "\nout 522\nend\n"
    )
    r_mix520 = check_details(beq, p_mix520, ["--method", "auto"])["mix520"]
    assert r_mix520["errors"].get("limits") == "inputs", r_mix520["errors"]


def test_dlp59_literals_and_mixed_outputs(beq: Path) -> None:
    """Verify broadened boolean-literal rule and DLP 59 Problem 7 on TT and BDD paths."""
    prog = (
        lib_header()
        # 1. Boolean literal on non-boolean `num` -> literal error.
        + "op lit_num mixed 0 1\nnum sel T 1 #0\nout 2\nend\n"
        # 2. Numeric literal on `cmp` is still allowed.
        + "op lit_cmp_ok mixed 0 1\ncmp lt 1 #3\nout 2\nend\n"
        # 3. Boolean literal on `run` -> literal error.
        + "op callee_m mixed 1 1\nnum sel 1 2 #0\nout 3\nend\n"
        + "op lit_run mixed 0 1\nrun callee_m F 1\nout 2\nend\n"
        # 4. Mixed op with pure boolean output -> mixed_bool_view.
        + "op mix_pure mixed 1 1\nnum add 2 #1\nnot 1\nout 3 4\nend\n"
        # 5. Mixed op with boolean interface view ANDed with comparison -> mixed_bool_view.
        + "op mix_gate mixed 1 2\ncmp lt 2 3\nand 1 4\nout 5\nend\n"
        # 6. Mixed op with boolean interface view feeding `num` only -> valid!
        + "op mix_num_ok mixed 2 1\nand 1 2\nnum sel 4 3 #0\nout 5\nend\n"
        # 7. Mixed op with shared non-boolean input across two written boolean views -> mixed_shared_input.
        + "op mix_corr mixed 0 2\ncmp lt 1 2\nnot 3\nout 3 4\nend\n"
        # 8. Mixed op with two disjoint boolean output views -> valid!
        + "op mix_disjoint_ok mixed 0 2\ncmp lt 1 2\ncmp gt 1 2\nout 3 4\nend\n"
        # 9. Forwarding two distinct boolean outputs of one non-boolean op -> valid!
        + "op mix_forward_ok mixed 0 2\nrun mix_disjoint_ok 1 2\nout 3 4\nend\n"
        # 10. Cancelling-out boolean input view traced backward -> mixed_bool_view!
        + "op mix_cancel_bad mixed 1 2\ncmp lt 2 3\ncmp gt 2 3\ncall equal 1 4\ncall equal 1 5\ncall equal 6 7\nnum sel 1 2 3\nout 8 9\nend\n"
        # 11. Useless boolean input in non-Boolean Value Operation (b cancels out in num.sel).
        + "op mix_useless_view mixed 3 1\ncall equal 1 2\ncall equal 2 3\ncall equal 5 6\nnum sel 7 4 #0\nout 8\nend\n"
        # 12. Useless comparison input in non-Boolean Value Operation (c2 cancels out in output).
        + "op mix_useless_cmp mixed 0 1\ncmp lt 1 #1\ncmp lt 1 #2\ncmp lt 1 #3\ncall equal 2 3\ncall equal 3 4\ncall equal 5 6\nout 7\nend\n"
        # 13. Problem 7 xor_and example: `d` cancels out in `cond`, yet `d` is still passed to a second `num sel`.
        + "op xor_and bool 3\nand 2 3\ncall xor 1 4\nout 5\nend\n"
        + "op mix_per_expr_useless mixed 5 2\ncall xor_and 5 1 2\ncall xor_and 5 3 4\ncall xor 8 9\nnum sel 10 6 7\nnum sel 5 11 #0\nout 12\nend\n"
    )
    py_res = {r["op"]: r["errors"] for r in program_check.check_program(prog)}
    for extra in (["--method", "tt"], ["--method", "bdd"], ["--method", "auto"]):
        c_res = check_details(beq, prog, extra)
        for name, want in py_res.items():
            assert c_res[name]["errors"] == want, (
                f"{name} {extra} mismatch: {c_res[name]['errors']} vs {want}"
            )
    assert py_res["lit_num"].get("literal") == 0, py_res["lit_num"]
    assert py_res["lit_cmp_ok"] == {}, py_res["lit_cmp_ok"]
    assert py_res["lit_run"].get("literal") == 0, py_res["lit_run"]
    assert py_res["mix_pure"].get("mixed_bool_view") == [2], py_res["mix_pure"]
    assert py_res["mix_gate"].get("mixed_bool_view") == [1], py_res["mix_gate"]
    assert py_res["mix_num_ok"] == {}, py_res["mix_num_ok"]
    assert py_res["mix_corr"].get("mixed_shared_input") == [3], py_res["mix_corr"]
    assert py_res["mix_disjoint_ok"] == {}, py_res["mix_disjoint_ok"]
    assert py_res["mix_forward_ok"] == {}, py_res["mix_forward_ok"]
    assert py_res["mix_cancel_bad"].get("mixed_bool_view") == [1], py_res[
        "mix_cancel_bad"
    ]
    assert py_res["mix_useless_view"].get("useless_input") == [2], py_res[
        "mix_useless_view"
    ]
    assert py_res["mix_useless_cmp"].get("useless_input") == [3], py_res[
        "mix_useless_cmp"
    ]
    assert py_res["mix_per_expr_useless"] == {"useless_input": [5]}, py_res[
        "mix_per_expr_useless"
    ]

    # 9. Verify B1 + B2 on the ROBDD path (I = 25 > 20).
    cmps = [f"cmp lt 2 #{i}" for i in range(24)]
    # 1 = bool view, 2 = num view, 3..26 = 24 comparisons.
    stmts = [*cmps, "and 1 3", "not 4"]
    prog_bdd = (
        lib_header()
        + "op mix_bdd_bad mixed 1 1\n"
        + "\n".join(stmts)
        + "\nout 27 4 28\nend\n"
    )
    r_bdd = check_details(beq, prog_bdd, ["--method", "auto"])["mix_bdd_bad"]["errors"]
    assert r_bdd.get("mixed_bool_view") == [1], r_bdd
    assert r_bdd.get("mixed_shared_input") == [4], r_bdd


def fix_and_verify(beq: Path, prog_text: str) -> tuple[dict, str, str]:
    """Run `beq --mode fix`, assert 0 remaining errors across auto/tt/program_check, return (summary, fixed, replacements)."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "in.prog"
        out_p = Path(td) / "out.prog"
        rep_p = Path(td) / "rep.txt"
        fail_p = Path(td) / "fail.txt"
        p.write_text(prog_text, encoding="ascii")
        res = run_beq(
            beq,
            [
                "program",
                str(p),
                "--mode",
                "fix",
                "--out",
                str(out_p),
                "--replacements",
                str(rep_p),
                "--failures",
                str(fail_p),
            ],
        )
        summary = json.loads(res.stdout)
        fixed_text = out_p.read_text(encoding="ascii")
        rep_text = rep_p.read_text(encoding="ascii")
        fail_text = fail_p.read_text(encoding="ascii")
        assert fail_text == "", f"unexpected fix failures:\n{fail_text}\n{summary}"
        assert summary["ops_with_errors_after"] == 0, summary
        for row in program_check.check_program(fixed_text):
            assert row["errors"] == {}, (
                f"fixed {row['op']} failed program_check: {row['errors']}\n{fixed_text}"
            )
        for extra in (["--method", "auto"], ["--method", "tt"]):
            c_res = check_details(beq, fixed_text, extra)
            for op_name, info in c_res.items():
                assert info["errors"] == {}, (
                    f"fixed {op_name} failed beq {extra}: {info['errors']}\n{fixed_text}"
                )
        return summary, fixed_text, rep_text


def fix_expect_failure(beq: Path, prog_text: str, expected_status: str) -> dict:
    """Run `beq --mode fix` and assert it stops cleanly with `expected_status`."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "in.prog"
        out_p = Path(td) / "out.prog"
        fail_p = Path(td) / "fail.txt"
        p.write_text(prog_text, encoding="ascii")
        res = run_beq(
            beq,
            [
                "program",
                str(p),
                "--mode",
                "fix",
                "--out",
                str(out_p),
                "--failures",
                str(fail_p),
            ],
        )
        summary = json.loads(res.stdout)
        fails = [ln.split() for ln in fail_p.read_text(encoding="ascii").splitlines()]
        assert any(f[1] == expected_status for f in fails), (
            f"expected failure {expected_status!r}, got {fails}\n{summary}"
        )
        return summary


def test_full_autofix(beq: Path) -> None:
    """Verify full DLP 65 automated refactoring: literals, constants, specialization, useless inputs, structural rewrites."""
    # 1. Constant folding & literal propagation through `and`, `not`, `call` (specialization), and `run` (specialization).
    prog_lit = (
        lib_header()
        # Non-trivial specialized helper `g__L4F(a, b, c) = equal(a, b) and c` stays in program.
        + "op g bool 4\ncall equal 1 2\nand 5 3\nnot 4\nand 6 7\nout 8\nend\n"
        + "op f_call bool 3\ncall g 1 2 3 F\nnot 1\nand 4 5\nout 6\nend\n"
        # Mixed callee specialization where boolean literal simplifies away cleanly.
        + "op m_spec mixed 2 1\nand 1 2\nnum sel 4 3 #1\nout 5\nend\n"
        + "op f_run mixed 1 1\nrun m_spec T 1 2\nout 3\nend\n"
        # Constant bool op propagating across callers (g_c -> f_c).
        + "op g_c bool 2\nand 1 2\nnot 3\nand 3 4\nout 5\nend\n"
        + "op f_c bool 4\ncall g_c 1 2\nnot 5\nand 6 3\nand 7 4\nout 8\nend\n"
    )
    _, fixed_lit, rep_lit = fix_and_verify(beq, prog_lit)
    assert "op g__L4F bool 3" in fixed_lit, fixed_lit
    assert "op m_spec__L1T mixed 1 1" in fixed_lit, fixed_lit
    assert "g_c 0 literal F" in rep_lit, rep_lit

    # 2. Interacting unused views that fail kept-view substitution (`false`-substitution + specialization).
    prog_unused = (
        lib_header()
        + "op g_u bool 3\ncall xor 1 3\ncall xor 2 3\ncall xor 4 5\nand 6 1\nout 7\nend\n"
        + "op f_u bool 3\ncall g_u 1 2 3\nnot 3\nand 4 5\nout 6\nend\n"
        + "op h_u bool 3\nand 1 2\nnot 3\nand 4 5\nout 6\nend\n"
        + "op g2_u bool 3\ncall h_u 1 2 3\nnot 3\ncall h_u 1 2 5\ncall or 4 6\nout 7\nend\n"
        + "op f2_u bool 4\ncall g2_u 1 2 3\nand 5 4\nout 6\nend\n"
    )
    _, _, rep_unused = fix_and_verify(beq, prog_unused)
    assert "g_u - dropped 3" in rep_unused, rep_unused
    assert "g2_u - dropped 3" in rep_unused, rep_unused

    # 3. Per-expression useless inputs in mixed ops (`xor_and`, `or(c, a and c)`, dead `cmp`, unused `run` output, `mix_cancel_bad`).
    prog_useless = (
        lib_header()
        + "op xor_and bool 3\nand 2 3\ncall xor 1 4\nout 5\nend\n"
        + "op mix_xor_and mixed 5 2\ncall xor_and 5 1 2\ncall xor_and 5 3 4\ncall xor 8 9\nnum sel 10 6 7\nnum sel 5 11 #0\nout 12\nend\n"
        + "op mix_absorb mixed 1 1\ncmp lt 2 #3\nand 1 3\ncall or 3 4\nnum sel 5 2 #1\nout 6\nend\n"
        + "op mix_dead_cmp mixed 0 1\ncmp lt 1 #1\ncmp lt 1 #2\ncmp lt 1 #3\ncall equal 2 3\ncall equal 3 4\ncall equal 5 6\nout 7\nend\n"
        + "op m_two mixed 0 1\nnum add 1 #1\ncmp lt 1 #2\nout 2 3\nend\n"
        + "op f_drop_run mixed 0 1\nrun m_two 1\nout 2\nend\n"
        + "op mix_cancel mixed 1 2\ncmp lt 2 3\ncmp gt 2 3\ncall equal 1 4\ncall equal 1 5\ncall equal 6 7\nnum sel 1 2 3\nout 8 9\nend\n"
    )
    _, fixed_useless, rep_useless = fix_and_verify(beq, prog_useless)
    assert "mix_absorb - dropped 1" in rep_useless, rep_useless
    assert "op m_two__D2 mixed 0 1" in fixed_useless, fixed_useless

    # 4. Structural rewrites: multi-output bool op splitting + mixed_bool_view / mixed_shared_input extraction with callers.
    prog_struct = (
        lib_header()
        # Multi-output bool op with a caller using `run`.
        + "op multi bool 3\nand 1 2\ncall or 2 3\nout 4 5\nend\n"
        + "op caller_multi bool 3\nrun multi 1 2 3\ncall xor 4 5\nout 6\nend\n"
        # mixed_bool_view (pure bool output + combined bool/cmp output) with callers.
        + "op m_pure mixed 1 1\nnum add 2 #1\nnot 1\nout 3 4\nend\n"
        + "op c_pure mixed 1 1\nrun m_pure 1 2\nnum sel 4 3 #0\nout 5\nend\n"
        + "op m_gate mixed 1 2\nnum add 2 3\ncmp lt 2 3\nand 1 5\nout 4 6\nend\n"
        + "op c_gate mixed 1 2\nrun m_gate 1 2 3\nnum sel 5 4 2\nout 6\nend\n"
        # Complex 2-statement extracted boolean helper op (stays as m_complex__bool2).
        + "op m_complex mixed 2 2\nnum add 3 4\ncmp lt 3 4\ncall xor 1 6\nnot 2\nand 7 8\nout 5 9\nend\n"
        + "op c_complex mixed 2 2\nrun m_complex 1 2 3 4\nnum sel 6 5 3\nout 7\nend\n"
        # mixed_shared_input (`(c, not c)` and `(c, or(c, d))`) with callers.
        + "op m_corr mixed 0 2\ncmp lt 1 2\nnot 3\nout 3 4\nend\n"
        + "op c_corr mixed 0 2\nrun m_corr 1 2\nnum sel 3 1 2\nnum sel 4 5 #0\nout 6\nend\n"
        + "op m_shared mixed 0 2\ncmp lt 1 2\ncmp eq 1 2\ncall or 3 4\nout 3 5\nend\n"
        + "op c_shared mixed 0 2\nrun m_shared 1 2\nnum sel 3 1 2\nnum sel 4 5 #0\nout 6\nend\n"
    )
    _, fixed_struct, rep_struct = fix_and_verify(beq, prog_struct)
    assert "op m_complex__bool2 bool 3" in fixed_struct, fixed_struct
    assert "op m_pure mixed 0 1" in fixed_struct, fixed_struct
    assert "op m_gate mixed 0 2" in fixed_struct, fixed_struct
    assert "m_pure - dropped 1" in rep_struct, rep_struct
    assert "m_gate - dropped 1" in rep_struct, rep_struct
    assert "m_corr 1 statement not @1" in rep_struct, rep_struct

    # 5. Opaque non-boolean logical op (`num`) boundary and 0-output bool op still stop cleanly.
    fix_expect_failure(
        beq,
        lib_header() + "op num_lit mixed 0 1\nnum sel T 1 #1\nout 2\nend\n",
        "literal",
    )
    fix_expect_failure(
        beq,
        lib_header()
        + "op num_const mixed 1 1\nnot 1\nand 1 3\nnum sel 4 2 #1\nout 5\nend\n",
        "literal",
    )
    fix_expect_failure(
        beq,
        lib_header()
        + "op m_opaque mixed 1 1\nnum sel 1 2 #1\nout 3\nend\n"
        + "op call_opaque mixed 0 1\nrun m_opaque F 1\nout 2\nend\n",
        "literal",
    )
    fix_expect_failure(
        beq,
        lib_header() + "op empty_bool bool 2\nand 1 2\nout\nend\n",
        "outputs",
    )


def main() -> None:
    """Run all regression and cross-check tests."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--beq", type=Path, default=HERE / "src" / "beq")
    args = parser.parse_args()
    tests = [
        ("dlp62_order", test_dlp62_order),
        ("dlp60_grouping_and_factoring", test_dlp60_grouping_and_factoring),
        ("dlp59_literals_and_mixed_outputs", test_dlp59_literals_and_mixed_outputs),
        ("full_autofix", test_full_autofix),
        ("conservative_limits", test_conservative_limits),
        ("wide_inputs_no_ub", test_wide_inputs_no_ub),
        ("deep_chain_guided_seeding", test_deep_chain_guided_seeding),
        ("dynamic_pool_and_4096_inputs", test_dynamic_pool_and_4096_inputs),
        ("drop_views_wide_and_interacting", test_drop_views_wide_and_interacting),
        ("registry_mode_wide", test_registry_mode_wide),
        ("wide_lookup_transpose", test_wide_lookup_transpose),
        ("bdd_symmetry_groups", test_bdd_symmetry_groups),
        ("random_crosscheck_and_fix", test_random_crosscheck_and_fix),
    ]
    for name, fn in tests:
        fn(args.beq)
        print(f"PASS {name}")
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
