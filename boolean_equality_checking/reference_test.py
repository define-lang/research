"""Regression and cross-check test suite for the boolean_equality_checking reference implementation.

Verifies every correctness fix, edge case, and algorithmic optimization:
1. DLP 61 human-readable registered-operation order (or before implies, xor
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


def test_dlp61_order(beq: Path) -> None:
    """Verify human-readable DLP 61 order and project-before-stdlib rule."""
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
        # Also plant a mux(s, p, q) on high-index inputs.
        s, p, q = n_inputs - 4, n_inputs - 3, n_inputs - 2
        stmts.append(f"and {s} {p}")
        mp1 = nxt
        nxt += 1
        stmts.append(f"not {s}")
        ns = nxt
        nxt += 1
        stmts.append(f"and {q} {ns}")
        mp2 = nxt
        nxt += 1
        stmts.append(f"call or {mp1} {mp2}")
        m_val = nxt
        nxt += 1
        # Combine with remaining inputs via an or-chain so all inputs are used.
        acc = x_val
        stmts.append(f"and {acc} {m_val}")
        acc = nxt
        nxt += 1
        for i in range(1, n_inputs - 4):
            stmts.append(f"call or {i} {acc}")
            acc = nxt
            nxt += 1
        prog = (
            lib_header()
            + f"op big_{n_inputs} bool {n_inputs}\n"
            + "\n".join(stmts)
            + f"\nout {acc}\nend\n"
        )
        fast = check_details(beq, prog, ["--method", "auto", "--step_budget", "0"])[
            f"big_{n_inputs}"
        ]
        plain = check_details(
            beq, prog, ["--method", "auto", "--step_budget", "0", "--plain", "1"]
        )[f"big_{n_inputs}"]
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
    fast = check_details(beq, prog, ["--method", "auto", "--step_budget", "0"])[
        "deep_and"
    ]
    plain = check_details(
        beq, prog, ["--method", "auto", "--step_budget", "0", "--plain", "1"]
    )["deep_and"]
    assert fast["errors"] == plain["errors"], (
        f"deep_and mismatch: {fast['errors']} vs {plain['errors']}"
    )
    assert fast["errors"]["match"][1] == "or", f"expected or match: {fast['errors']}"
    assert fast["t"]["total"] < 1.0, f"deep_and too slow: {fast['t']}"


def test_dynamic_pool_and_4096_inputs(beq: Path) -> None:
    """Test > 8,192 literals in Matcher pool and > 4,096 inputs in Bdd/Diagram."""
    n_inputs = 4500
    stmts = []
    nxt = n_inputs + 1
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
    prog = (
        lib_header(["or", "xor"])
        + f"op huge mixed {n_inputs} 0\n"
        + "\n".join(stmts)
        + f"\nout {acc}\nend\n"
    )
    # Verify both BDD building (> 4096 levels) and Matcher pool (> 8192 literals) succeed cleanly.
    res = check_details(beq, prog, ["--method", "auto", "--step_budget", "0"])["huge"]
    assert "limits" not in res["errors"], f"unexpected limit error: {res['errors']}"
    assert set(res["errors"]) <= {"order_arguments", "order_statements"}, (
        f"unexpected errors on huge op: {res['errors']}"
    )


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
        res = run_beq(beq, ["program", str(p), "--mode", "fix", "--out", str(out_p)])
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
        res = run_beq(beq, ["program", str(p), "--mode", "fix", "--out", str(out_p)])
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
        "call implies 8 9",  # 28
        "and 10 28",  # 29
        "call or 11 29",  # 30
        "call implies 12 30",  # 31
        "and 13 31",  # 32
        "call or 14 32",  # 33
        "call implies 15 33",  # 34
        "and 16 34",  # 35
        "call or 17 35",  # 36
        "call implies 18 36",  # 37
        "and 19 37",  # 38
        "and 25 27",  # 39
        "call xor 38 39",  # 40
    ]
    prog = lib_header() + "op sym22 bool 22\n" + "\n".join(stmts) + "\nout 40\nend\n"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "sym.prog"
        p.write_text(prog, encoding="ascii")
        res = run_beq(beq, ["program", str(p), "--mode", "groups", "--method", "auto"])
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
            assert summary["ops_with_errors_after"] == 0, (
                f"seed={seed} fix left errors: {summary}"
            )
            py_after = program_check.check_program(out_p.read_text(encoding="ascii"))
            for row in py_after:
                assert row["errors"] == {}, (
                    f"seed={seed} fixed op {row['op']} failed program_check: {row['errors']}"
                )


def main() -> None:
    """Run all regression and cross-check tests."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--beq", type=Path, default=HERE / "src" / "beq")
    args = parser.parse_args()
    tests = [
        ("dlp61_order", test_dlp61_order),
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
