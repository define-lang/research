"""Split value operations as written to check boolean logic past 20 inputs.

A statement whose operands read no common inputs, each operand non-constant,
depends on every input either operand reads when every one of its views
matters (`and`, `or`, `xor`, `xnor`, `choose`): fixing all but one operand's
inputs leaves the other operands free, so whatever input changes that
operand can change the result. So reading each value's inputs as written
gives the inputs it depends on, except at statements whose operands share
inputs. Only those need an exact check, of the statement's value over the
values below it that read inputs nothing else in the check reads (its
leaves), and two values can only be the same or opposite if they depend on
the same inputs, so only groups of values with the same inputs need one.

Each check's leaves are found by starting from the values checked and
replacing each value below them that shares an input with another by its
operands, until no two share one; operands of one `and`, `or` or `xor`
chain that only that chain reads become one leaf. A group of values whose
statements all read disjoint inputs (read-once values) is compared by a
fixed form instead: `and`s as `not`s of `or`s, chains of one operation
flattened and sorted, `not`s moved out of `xor`s and `choose`s.

Run with `uv run python split_experiment.py measure OUT.json NAME...` for
the real-code study's over-limit units (from its work/ir/NAME.jsonl), or
`uv run python split_experiment.py verify OUT.json SEED COUNT` to compare
against truth tables over every input (and past 16 inputs, against a BDD over
every input).
"""

from __future__ import annotations

import json
import random
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

STUDY = Path.home() / "projects/research/boolean_logic_in_real_code"
sys.path.insert(0, str(STUDY))

import analyze  # pyright: ignore[reportMissingImports]

INPUT_LIMIT = 20
STMT_LIMIT = 256
DAG_CAP = 200_000
BDD_CAP = 100_000
BDD_SECONDS = 2.0

Lit = int
# An `xor` operand standing for a negated `xor` written out into a chain.
NEGATE = -1


class TooBigError(Exception):
    """A unit grew past DAG_CAP nodes."""


class BlowupError(Exception):
    """A BDD grew past BDD_CAP nodes."""


class Dag:
    """Boolean statements over inputs, `not`s as negated literals."""

    def __init__(self) -> None:
        """Start with no nodes."""
        self.op: list[str] = []
        self.kids: list[tuple[Lit, ...]] = []
        self.inputs: dict[object, int] = {}

    def input(self, key: object) -> Lit:
        """Return the input with this key, adding it the first time."""
        node = self.inputs.get(key)
        if node is None:
            node = len(self.op)
            self.op.append("in")
            self.kids.append(())
            self.inputs[key] = node
        return 2 * node

    def stmt(self, op: str, kids: tuple[Lit, ...]) -> Lit:
        """Add a statement and return its literal."""
        if len(self.op) >= DAG_CAP:
            raise TooBigError
        self.op.append(op)
        self.kids.append(kids)
        return 2 * (len(self.op) - 1)


class Bdd:
    """A reduced ordered BDD without complement edges: 0 false, 1 true."""

    def __init__(self) -> None:
        """Start with the two constants."""
        self.var: list[int] = [1 << 30, 1 << 30]
        self.lo: list[int] = [0, 1]
        self.hi: list[int] = [0, 1]
        self.unique: dict[tuple[int, int, int], int] = {}
        self.deadline = float("inf")
        self.cache: dict[tuple[str, int, int], int] = {}

    def mk(self, v: int, lo: int, hi: int) -> int:
        """Return the node for v ? hi : lo."""
        if lo == hi:
            return lo
        key = (v, lo, hi)
        found = self.unique.get(key)
        if found is None:
            if len(self.var) >= BDD_CAP or (
                len(self.var) % 4096 == 0 and time.perf_counter() > self.deadline
            ):
                raise BlowupError
            found = len(self.var)
            self.var.append(v)
            self.lo.append(lo)
            self.hi.append(hi)
            self.unique[key] = found
        return found

    def variable(self, v: int) -> int:
        """Return the BDD of variable v."""
        return self.mk(v, 0, 1)

    def apply(self, op: str, f: int, g: int) -> int:
        """Return f op g."""
        if op == "and":
            if f == 0 or g == 0:
                return 0
            if f == 1:
                return g
            if g == 1 or f == g:
                return f
        elif op == "or":
            if f == 1 or g == 1:
                return 1
            if f == 0:
                return g
            if g == 0 or f == g:
                return f
        else:
            if f == 0:
                return g
            if g == 0:
                return f
            if f == g:
                return 0
        if f > g:
            f, g = g, f
        key = (op, f, g)
        found = self.cache.get(key)
        if found is not None:
            return found
        v = min(self.var[f], self.var[g])
        f0, f1 = (self.lo[f], self.hi[f]) if self.var[f] == v else (f, f)
        g0, g1 = (self.lo[g], self.hi[g]) if self.var[g] == v else (g, g)
        found = self.mk(v, self.apply(op, f0, g0), self.apply(op, f1, g1))
        self.cache[key] = found
        return found

    def negate(self, f: int) -> int:
        """Return not f."""
        return self.apply("xor", f, 1)

    def support(self, f: int) -> set[int]:
        """Return the variables f depends on."""
        out: set[int] = set()
        seen: set[int] = set()
        stack = [f]
        while stack:
            n = stack.pop()
            if n < 2 or n in seen:
                continue
            seen.add(n)
            out.add(self.var[n])
            stack.append(self.lo[n])
            stack.append(self.hi[n])
        return out


class Region:
    """One exact check: the values checked, the statements below them, and their leaves."""

    def __init__(self, checker: Checker, tops: list[int]) -> None:
        """Find the leaves of a check of these values."""
        c = checker
        self.tops = tops
        expanded = set(tops)
        cand: set[int] = set()
        for t in tops:
            for k in c.dag.kids[t]:
                if k >> 1 not in expanded:
                    cand.add(k >> 1)
        self.capped = False
        while True:
            if not c.use_bdd and len(expanded) > STMT_LIMIT:
                # Past the statement limit already; only a BDD would check it.
                self.capped = True
                break
            seen = 0
            multi = 0
            for n in cand:
                s = c.supp[n]
                multi |= seen & s
                seen |= s
            overlapping = [
                n
                for n in cand
                if c.dag.op[n] != "in" and c.const[n] is None and c.supp[n] & multi
            ]
            if not overlapping:
                break
            # A value below another that's also replaced needs no replacing
            # itself once the other is gone.
            chosen = []
            for n in overlapping:
                s = c.supp[n]
                covered = False
                for m in overlapping:
                    if m != n:
                        t = c.supp[m]
                        if (s & t) == s and (s != t or m > n):
                            covered = True
                            break
                if not covered:
                    chosen.append(n)
            for n in chosen:
                cand.discard(n)
                expanded.add(n)
                for k in c.dag.kids[n]:
                    if k >> 1 not in expanded:
                        cand.add(k >> 1)
        self.expanded = sorted(expanded)
        self.leaf_nodes = cand
        parents: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for e in self.expanded:
            for k in c.dag.kids[e]:
                parents[k >> 1].append((e, k & 1))
        top_set = set(tops)
        absorbed: set[int] = set()
        for e in self.expanded:
            op = c.dag.op[e]
            ps = parents.get(e, [])
            if (
                e not in top_set
                and op in ("and", "or", "xor")
                and len(ps) == 1
                and c.dag.op[ps[0][0]] == op
                and (ps[0][1] == 0 or op == "xor")
            ):
                absorbed.add(e)
        self.absorbed = absorbed
        # Each chain's leaf operands that only it reads, as one leaf.
        self.merged: dict[int, list[Lit]] = {}
        self.chain_rest: dict[int, list[Lit]] = {}
        merged_away: set[int] = set()
        for e in self.expanded:
            if e in absorbed or c.dag.op[e] not in ("and", "or", "xor"):
                continue
            members = {e}
            operands: list[Lit] = []
            stack = list(c.dag.kids[e])
            while stack:
                k = stack.pop()
                if k >> 1 in absorbed:
                    members.add(k >> 1)
                    stack.extend(c.dag.kids[k >> 1])
                    if k & 1:
                        operands.append(NEGATE)
                else:
                    operands.append(k)
            counts: dict[int, int] = defaultdict(int)
            for k in operands:
                if k != NEGATE:
                    counts[k >> 1] += 1
            exclusive = []
            rest = []
            for k in operands:
                n = k >> 1
                if (
                    k != NEGATE
                    and n in cand
                    and c.const[n] is None
                    and counts[n] == 1
                    and all(p in members for p, _ in parents[n])
                ):
                    exclusive.append(k)
                else:
                    rest.append(k)
            if len(exclusive) >= 2 and len(exclusive) + len(rest) > 1:
                self.merged[e] = exclusive
                merged_away.update(k >> 1 for k in exclusive)
            else:
                rest = operands
            self.chain_rest[e] = rest
        self.leaves = [
            n for n in sorted(cand) if n not in merged_away and c.const[n] is None
        ]
        self.leaf_count = len(self.leaves) + len(self.merged)
        self.stmts = len(self.expanded)

    def within_limits(self) -> bool:
        """Whether the check is within DLP 59's limits."""
        return (
            not self.capped
            and self.leaf_count <= INPUT_LIMIT
            and self.stmts <= STMT_LIMIT
        )

    def evaluate(self, c: Checker, backend: Backend) -> dict[int, Any]:
        """Each top's function over the leaves, in the backend's representation."""
        value: dict[int, Any] = {}
        order = 0
        for n in self.leaves:
            value[n] = backend.var(order)
            order += 1
        merged_value: dict[int, Any] = {}
        for e, lits in self.merged.items():
            # A merged leaf is the chain's operation over its leaves; it's a
            # fresh leaf of the check.
            merged_value[e] = backend.var(order)
            order += 1
            del lits
        for n in self.leaf_nodes:
            b = c.const[n]
            if b is not None:
                value[n] = backend.constant(b)

        def lit(k: Lit) -> Any:
            if k == NEGATE:
                return backend.constant(1)
            v = value[k >> 1]
            return backend.negate(v) if k & 1 else v

        for e in self.expanded:
            if e in self.absorbed:
                continue
            op = c.dag.op[e]
            if op == "choose":
                cnd, a, b = (lit(k) for k in c.dag.kids[e])
                value[e] = backend.choose(cnd, a, b)
                continue
            parts = [lit(k) for k in self.chain_rest[e]]
            if e in self.merged:
                parts.append(merged_value[e])
            acc = parts[0]
            for p in parts[1:]:
                acc = backend.apply(op, acc, p)
            value[e] = acc
        return {t: value[t] for t in self.tops}


class Tables:
    """Truth tables over the leaves as Python integers."""

    def __init__(self, leaves: int) -> None:
        """Tables of 2^leaves rows."""
        self.rows = 1 << leaves
        self.mask = (1 << self.rows) - 1

    def var(self, j: int) -> int:
        """Return leaf j's table."""
        half = 1 << j
        unit = ((1 << half) - 1) << half
        return unit * (self.mask // ((1 << (2 * half)) - 1))

    def constant(self, b: int) -> int:
        """Return a constant's table."""
        return self.mask if b else 0

    def negate(self, f: int) -> int:
        """Return not f."""
        return f ^ self.mask

    def apply(self, op: str, f: int, g: int) -> int:
        """Return f op g."""
        if op == "and":
            return f & g
        if op == "or":
            return f | g
        return f ^ g

    def choose(self, cnd: int, a: int, b: int) -> int:
        """Return cnd ? a : b."""
        return (cnd & a) | (~cnd & b & self.mask)

    def depends(self, f: int, j: int) -> bool:
        """Whether f depends on leaf j."""
        v = self.var(j)
        return ((f & v) >> (1 << j)) != (f & ~v & self.mask)

    def key(self, f: int) -> tuple[int, int]:
        """Return f's class key (up to complement) and phase."""
        return (f ^ self.mask, 1) if f & 1 else (f, 0)


class BddBackend:
    """BDDs over the leaves, leaves in order."""

    def __init__(self) -> None:
        """Start with an empty BDD."""
        self.bdd = Bdd()

    def var(self, j: int) -> int:
        """Return leaf j's BDD."""
        return self.bdd.variable(j)

    def constant(self, b: int) -> int:
        """Return a constant's BDD."""
        return b

    def negate(self, f: int) -> int:
        """Return not f."""
        return self.bdd.negate(f)

    def apply(self, op: str, f: int, g: int) -> int:
        """Return f op g."""
        return self.bdd.apply(op, f, g)

    def choose(self, cnd: int, a: int, b: int) -> int:
        """Return cnd ? a : b."""
        return self.bdd.apply(
            "or",
            self.bdd.apply("and", cnd, a),
            self.bdd.apply("and", self.negate(cnd), b),
        )

    def key(self, f: int) -> tuple[int, int]:
        """Return f's class key (up to complement) and phase."""
        g = self.negate(f)
        return (f, 0) if f < g else (g, 1)


Backend = Tables | BddBackend


class Checker:
    """The split check of one unit's statements."""

    def __init__(self, dag: Dag, roots: list[Lit], *, use_bdd: bool) -> None:
        """Prepare to check the values below roots."""
        self.dag = dag
        self.use_bdd = use_bdd
        self.deadline = float("inf")
        n = len(dag.op)
        cone = [False] * n
        stack = [r >> 1 for r in roots]
        while stack:
            x = stack.pop()
            if cone[x]:
                continue
            cone[x] = True
            stack.extend(k >> 1 for k in dag.kids[x])
        self.nodes = [x for x in range(n) if cone[x]]
        self.supp = [0] * n
        self.const: list[int | None] = [None] * n
        self.read_once = [False] * n
        self.bit: dict[int, int] = {}
        self.bit_node: list[int] = []
        self.top_fi = -1
        self.input_key: dict[int, object] = {}
        self.stats: dict[str, Any] = {
            "inputs": 0,
            "stmts": 0,
            "disjoint": 0,
            "overlap": 0,
            "overlap_over": 0,
            "overlap_max_leaves": 0,
            "overlap_max_stmts": 0,
            "groups": 0,
            "group_max_members": 0,
            "group_max_leaves": 0,
            "groups_read_once": 0,
            "groups_one_input": 0,
            "group_over": 0,
            "bdd_regions": 0,
            "bdd_max_nodes": 0,
            "unresolved": 0,
            "timeout": 0,
            "constants": 0,
            "redundant": 0,
            "reasons": [],
        }
        self.same: list[tuple[int, int, int]] = []
        self.canon_memo: dict[int, tuple[int, Any]] = {}

    def run(self) -> None:
        """Find every value's inputs, the constants, and the same and opposite values."""
        s = self.stats
        d = self.dag
        for x in self.nodes:
            if time.perf_counter() > self.deadline:
                s["unresolved"] += 1
                s["timeout"] = 1
                return
            if d.op[x] == "in":
                self.bit[x] = len(self.bit)
                self.bit_node.append(x)
                self.supp[x] = 1 << self.bit[x]
                self.read_once[x] = True
                s["inputs"] += 1
                continue
            s["stmts"] += 1
            kids = d.kids[x]
            nodes = [k >> 1 for k in kids]
            disjoint = len(set(nodes)) == len(nodes) and all(
                self.const[k] is None for k in nodes
            )
            union = 0
            for k in nodes:
                if union & self.supp[k]:
                    disjoint = False
                union |= self.supp[k]
            if disjoint:
                s["disjoint"] += 1
                self.supp[x] = union
                self.read_once[x] = all(self.read_once[k] for k in nodes)
                continue
            s["overlap"] += 1
            region = Region(self, [x])
            s["overlap_max_leaves"] = max(s["overlap_max_leaves"], region.leaf_count)
            s["overlap_max_stmts"] = max(s["overlap_max_stmts"], region.stmts)
            if not region.within_limits():
                s["overlap_over"] += 1
                s["reasons"].append(
                    (
                        "overlap",
                        region.leaf_count,
                        region.stmts,
                        self.shared_kinds(nodes),
                    )
                )
            f = self.check_region(region)
            if f is None:
                self.supp[x] = union
                continue
            backend, value = f
            g = value[x]
            if isinstance(backend, Tables):
                if g in (0, backend.mask):
                    self.const[x] = 1 if g else 0
                deps = [j for j in range(region.leaf_count) if backend.depends(g, j)]
            else:
                if g in (0, 1):
                    self.const[x] = g
                deps = sorted(backend.bdd.support(g))
            if self.const[x] is not None:
                s["constants"] += 1
            sup = 0
            leaf_supp = [self.supp[n] for n in region.leaves]
            for e, lits in region.merged.items():
                del e
                m = 0
                for k in lits:
                    m |= self.supp[k >> 1]
                leaf_supp.append(m)
            for j in deps:
                sup |= leaf_supp[j]
            self.supp[x] = sup
        self.groups()

    def shared_kinds(self, nodes: list[int]) -> dict[str, int]:
        """Count the kinds of inputs a statement's operands both read."""
        if not self.input_key:
            self.input_key = {v: k for k, v in self.dag.inputs.items()}
        shared = 0
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 :]:
                shared |= self.supp[a] & self.supp[b]
        kinds: dict[str, int] = defaultdict(int)
        j = 0
        while shared:
            if shared & 1:
                kinds[input_kind(self.input_key[self.bit_node[j]], self.top_fi)] += 1
            shared >>= 1
            j += 1
        return dict(kinds)

    def check_region(self, region: Region) -> tuple[Backend, dict[int, Any]] | None:
        """Return the check's backend and its tops' functions, or None if it can't be decided."""
        if region.capped:
            self.stats["unresolved"] += 1
            return None
        if region.leaf_count <= INPUT_LIMIT:
            backend: Backend = Tables(region.leaf_count)
            return backend, region.evaluate(self, backend)
        if not self.use_bdd:
            self.stats["unresolved"] += 1
            return None
        self.stats["bdd_regions"] += 1
        bb = BddBackend()
        bb.bdd.deadline = self.deadline
        try:
            value = region.evaluate(self, bb)
        except BlowupError:
            self.stats["unresolved"] += 1
            return None
        self.stats["bdd_max_nodes"] = max(self.stats["bdd_max_nodes"], len(bb.bdd.var))
        return bb, value

    def groups(self) -> None:
        """Check each group of values that depend on the same inputs."""
        s = self.stats
        by_supp: dict[int, list[int]] = defaultdict(list)
        for x in self.nodes:
            if self.const[x] is None:
                by_supp[self.supp[x]].append(x)
        for sup, members in by_supp.items():
            if len(members) < 2:
                continue
            s["groups"] += 1
            s["group_max_members"] = max(s["group_max_members"], len(members))
            if sup & (sup - 1) == 0:
                s["groups_one_input"] += 1
                first = members[0]
                for m in members[1:]:
                    self.note_same(first, m, -1)
                continue
            if all(self.read_once[m] for m in members):
                s["groups_read_once"] += 1
                keys = {m: self.canon(2 * m)[1] for m in members}
                self.classes(members, keys)
                continue
            region = Region(self, members)
            s["group_max_leaves"] = max(s["group_max_leaves"], region.leaf_count)
            if not region.within_limits():
                s["group_over"] += 1
                s["reasons"].append(
                    ("group", region.leaf_count, region.stmts, len(members))
                )
            f = self.check_region(region)
            if f is None:
                continue
            backend, value = f
            try:
                keys = {m: backend.key(value[m])[0] for m in members}
            except BlowupError:
                self.stats["unresolved"] += 1
                continue
            self.classes(members, keys)

    def classes(self, members: list[int], keys: dict[int, Any]) -> None:
        """Note the members whose keys are equal as the same or opposite."""
        first: dict[Any, int] = {}
        for m in members:
            k = keys[m]
            if k in first:
                self.note_same(first[k], m, 0)
            else:
                first[k] = m

    def note_same(self, a: int, b: int, how: int) -> None:
        """Note two values that are the same or opposite."""
        self.stats["redundant"] += 1
        self.same.append((a, b, how))

    def canon(self, k: Lit) -> tuple[int, Any]:
        """Return a read-once value's fixed form: its phase and a structure."""
        x = k >> 1
        found = self.canon_memo.get(x)
        if found is None:
            found = self.canon_node(x)
            self.canon_memo[x] = found
        return (found[0] ^ (k & 1), found[1])

    def canon_node(self, x: int) -> tuple[int, Any]:
        """Return a read-once node's fixed form."""
        d = self.dag
        op = d.op[x]
        if op == "in":
            return (0, ("v", self.bit[x]))
        kids = [self.canon(k) for k in d.kids[x]]
        if op == "choose":
            (pc, sc), a, b = kids
            if pc:
                a, b = b, a
            phase = a[0]
            if phase:
                a = (0, a[1])
                b = (b[0] ^ 1, b[1])
            return (phase, ("mux", sc, a[1], b))
        if op == "xor":
            phase = 0
            parts: list[Any] = []
            for p, st in kids:
                phase ^= p
                if st[0] == "xor":
                    parts.extend(st[1])
                else:
                    parts.append(st)
            return (phase, ("xor", tuple(sorted(parts, key=repr))))
        # and(a, b) is not or(not a, not b).
        flip = 1 if op == "and" else 0
        parts = []
        for p, st in kids:
            p ^= flip
            if p == 0 and st[0] == "or":
                parts.extend(st[1])
            else:
                parts.append((p, st))
        return (flip, ("or", tuple(sorted(parts, key=repr))))


# ---------------------------------------------------------------------------
# The real-code study's units.


class Ctx:
    """One function written out at one call, or the unit's own function."""

    __slots__ = ("args", "caller", "cid", "depth", "fi", "method", "recv")

    def __init__(
        self,
        cid: int,
        fi: int,
        caller: Ctx | None,
        args: list[int],
        recv: int,
        *,
        method: bool,
        depth: int,
    ) -> None:
        """Start a function written out at one call."""
        self.cid = cid
        self.fi = fi
        self.caller = caller
        self.args = args
        self.recv = recv
        self.method = method
        self.depth = depth


class Builder:
    """Turns the study's intermediate form into a Dag, calls written out in scope 2."""

    def __init__(self, cb: analyze.Codebase, *, scope2: bool) -> None:
        """Start an empty unit."""
        self.cb = cb
        self.scope2 = scope2
        self.dag = Dag()
        self.memo: dict[tuple[int, int], Lit] = {}
        self.busy: set[tuple[int, int]] = set()
        self.instances: dict[tuple[int, str], Lit] = {}
        self.next_cid = 0
        self.literals = 0
        self.merges = 0
        self.cycles = 0

    def top(self, fi: int) -> Ctx:
        """Return the context of the unit's own function."""
        self.next_cid += 1
        return Ctx(
            self.next_cid, fi, None, [], -1, method=False, depth=analyze.DEPTH_CAP
        )

    def local_input(self, ctx: Ctx, text: str, *, reads_params: bool) -> Lit:
        """Return an input of the function, per call when it reads parameters."""
        if reads_params and ctx.caller is not None:
            return self.dag.input(("call", ctx.cid, text))
        return self.dag.input(("local", ctx.fi, text))

    def build(self, ctx: Ctx, n: int) -> Lit:
        """Return a node's literal, written out once per context."""
        key = (ctx.cid, n)
        found = self.memo.get(key)
        if found is not None:
            return found
        if key in self.busy:
            self.cycles += 1
            return self.dag.input(("cycle", ctx.cid, n))
        self.busy.add(key)
        found = self.build_node(ctx, n)
        self.busy.discard(key)
        self.memo[key] = found
        return found

    def build_node(self, ctx: Ctx, n: int) -> Lit:
        """Write out one node of the intermediate form."""
        fn = self.cb.funcs[ctx.fi]
        nodes = fn["nodes"]
        node = nodes[n]
        kind = node[0]
        d = self.dag
        if kind == "s":
            op = node[1]
            kids = [self.build(ctx, c) for c in node[2]]
            if op == "not":
                return kids[0] ^ 1
            if op == "choose":
                return d.stmt("choose", (kids[0], kids[1], kids[2]))
            base = "xor" if op == "xnor" else op
            acc = kids[0]
            for k in kids[1:]:
                acc = d.stmt(base, (acc, k))
            return acc ^ 1 if op == "xnor" else acc
        if kind == "v":
            _, is_logic_var = self.cb.classify(ctx.fi)
            transparent = is_logic_var[n] or (
                self.scope2
                and any(
                    nodes[x][0] == "p"
                    or (
                        nodes[x][0] == "c"
                        and self.cb.resolve(ctx.fi, nodes[x][3]) is not None
                    )
                    for x in node[2]
                )
            )
            if not transparent:
                return d.input(("local", ctx.fi, "var:" + node[1]))
            defs = [self.build(ctx, x) for x in node[2]]
            if len(defs) == 1:
                return defs[0]
            # Definitions in different places: which one holds depends on
            # control flow, a condition the study doesn't record.
            self.merges += 1
            acc = defs[-1]
            for j in range(len(defs) - 2, -1, -1):
                sel = d.input(("phi", ctx.cid, n, j))
                acc = d.stmt("choose", (sel, defs[j], acc))
            return acc
        if kind == "p":
            j = node[1]
            if ctx.caller is None:
                return d.input(("param", ctx.fi, j))
            if ctx.method:
                arg = (
                    ctx.recv
                    if j == 0
                    else (ctx.args[j - 1] if j - 1 < len(ctx.args) else -1)
                )
            else:
                arg = ctx.args[j] if j < len(ctx.args) else -1
            if arg == -1:
                return d.input(("call", ctx.cid, "param", j))
            return self.build(ctx.caller, arg)
        if kind == "l":
            return self.local_input(ctx, node[1], reads_params=node[2])
        if kind == "k":
            self.literals += 1
            return d.input(("literal", ctx.cid, n))
        text, dep, info, args, recv = node[1], node[2], node[3], node[4], node[5]
        if not self.scope2:
            return self.local_input(ctx, text, reads_params=dep)
        callee = self.cb.resolve(ctx.fi, info)
        if (
            callee is None
            or self.cb.component[callee] == self.cb.component[ctx.fi]
            or ctx.depth == 0
        ):
            return self.local_input(ctx, text, reads_params=dep)
        ikey = (ctx.cid, text)
        found = self.instances.get(ikey)
        if found is not None:
            return found
        self.next_cid += 1
        cfn = self.cb.funcs[callee]
        cctx = Ctx(
            self.next_cid,
            callee,
            ctx,
            args,
            recv,
            method=cfn["method"],
            depth=ctx.depth - 1,
        )
        rets = [self.build(cctx, r) for r in cfn["rets"]]
        guards = [self.build(cctx, g) for g in cfn["guards"]]
        if not rets:
            found = self.local_input(ctx, text, reads_params=dep)
        else:
            # Each condition that decides which return statement runs
            # chooses between the returned values.
            acc = rets[-1]
            for j in range(len(rets) - 2, -1, -1):
                sel = guards[j] if j < len(guards) else d.input(("guard", cctx.cid, j))
                acc = d.stmt("choose", (sel, rets[j], acc))
            for j in range(len(rets) - 1, len(guards)):
                acc = d.stmt(
                    "choose", (guards[j], d.input(("other", cctx.cid, j)), acc)
                )
            found = acc
        self.instances[ikey] = found
        return found


def input_kind(key: object, top_fi: int) -> str:
    """Return the kind of input a Builder key stands for, for the reasons a check stays large."""
    if not isinstance(key, tuple):
        return "input"
    tag = key[0]
    if tag == "local":
        return "local" if key[1] == top_fi else "callee input not reading parameters"
    if tag == "call":
        return "callee input reading parameters"
    if tag == "param":
        return "parameter"
    return tag


def unit_record(
    cb: analyze.Codebase, fi: int, starts: list[int], *, scope2: bool
) -> dict[str, Any]:
    """Build one unit and check it, with BDDs for what's left past the limits."""
    b = Builder(cb, scope2=scope2)
    start = time.perf_counter()
    try:
        ctx = b.top(fi)
        roots = [b.build(ctx, n) for n in starts]
    except TooBigError:
        return {"too_big": True}
    built = time.perf_counter()
    rec: dict[str, Any] = {
        "literals": b.literals,
        "merges": b.merges,
        "cycles": b.cycles,
        "build_s": built - start,
    }
    c = Checker(b.dag, roots, use_bdd=False)
    c.top_fi = fi
    t0 = time.perf_counter()
    c.run()
    rec["split"] = dict(c.stats, seconds=time.perf_counter() - t0)
    if c.stats["overlap_over"] or c.stats["group_over"]:
        # What's left: checked exactly with BDDs, within a deadline.
        c = Checker(b.dag, roots, use_bdd=True)
        c.top_fi = fi
        t0 = time.perf_counter()
        c.deadline = t0 + BDD_SECONDS
        c.run()
        rec["bdd"] = dict(c.stats, seconds=time.perf_counter() - t0)
    if time.perf_counter() - start > 1:
        print(
            f"slow unit: fn {fi} {cb.funcs[fi]['name']} scope {2 if scope2 else 1} "
            f"nodes {len(b.dag.op)} build {rec['build_s']:.1f}s split {rec['split']['seconds']:.1f}s "
            f"bdd {rec.get('bdd', {}).get('seconds', 0):.1f}s",
            file=sys.stderr,
            flush=True,
        )
    return rec


def over_limit_units(
    cb: analyze.Codebase, part: int = 0, parts: int = 1
) -> Iterator[dict[str, Any]]:
    """Yield the study's units past its limits: the function, where to start, and what the study counted."""
    for fi, fn in enumerate(cb.funcs):
        if fi % parts != part:
            continue
        pieces, lone = analyze.scope1_pieces(cb, fi)
        if not pieces and not lone:
            continue
        where = f"{fn['file']}:{fn['line']} {fn['name']}"
        all_members: list[int] = []
        fn_inputs: set[str] = set()
        for p in pieces:
            all_members.extend(p["members"])
            fn_inputs |= p["inputs"]
            if len(p["inputs"]) > INPUT_LIMIT or p["stmts"] > STMT_LIMIT:
                yield {"fi": fi, "starts": p["members"], "scope": 1, "kind": "piece", "where": where,
                       "study": (len(p["inputs"]), p["stmts"])}  # fmt: skip
        if pieces:
            stmts = sum(p["stmts"] for p in pieces)
            if len(fn_inputs) > INPUT_LIMIT or stmts > STMT_LIMIT:
                yield {"fi": fi, "starts": all_members, "scope": 1, "kind": "function", "where": where,
                       "study": (len(fn_inputs), stmts)}  # fmt: skip
        all_starts: list[int] = []
        for p in pieces:
            e = cb.expand(fi, p["members"], analyze.DEPTH_CAP)
            all_starts.extend(p["members"])
            if e.big or e.input_count() > INPUT_LIMIT or e.stmts > STMT_LIMIT:
                yield {"fi": fi, "starts": p["members"], "scope": 2, "kind": "piece", "where": where,
                       "study": (e.input_count(), e.stmts), "big": e.big}  # fmt: skip
        for r in lone:
            e = cb.expand(fi, [r], analyze.DEPTH_CAP)
            all_starts.append(r)
            if (e.stmts or e.big) and (
                e.big or e.input_count() > INPUT_LIMIT or e.stmts > STMT_LIMIT
            ):
                yield {"fi": fi, "starts": [r], "scope": 2, "kind": "piece", "where": where + " (lone call)",
                       "study": (e.input_count(), e.stmts), "big": e.big}  # fmt: skip
        e = cb.expand(fi, all_starts, analyze.DEPTH_CAP)
        if (e.stmts or e.big) and (
            e.big or e.input_count() > INPUT_LIMIT or e.stmts > STMT_LIMIT
        ):
            yield {"fi": fi, "starts": all_starts, "scope": 2, "kind": "function", "where": where,
                   "study": (e.input_count(), e.stmts), "big": e.big}  # fmt: skip


def measure(out_path: str, names: list[str]) -> None:
    """Check every over-limit unit of the named codebases and write the records."""
    report: dict[str, Any] = {}
    for spec in names:
        # NAME, or NAME:PART:PARTS for the functions whose index is PART mod PARTS.
        name, part, parts = [*spec.split(":"), "0", "1"][:3]
        t_load = time.perf_counter()
        cb = analyze.Codebase(str(STUDY / "work/ir" / f"{name}.jsonl"))
        units: list[dict[str, Any]] = []
        for u in over_limit_units(cb, int(part), int(parts)):
            rec = unit_record(cb, u["fi"], u["starts"], scope2=u["scope"] == 2)
            units.append(
                dict(rec, **{k: v for k, v in u.items() if k not in ("fi", "starts")})
            )
        report[spec] = {"seconds": time.perf_counter() - t_load, "units": units}
        print(
            f"{spec}: {len(units)} units, {report[spec]['seconds']:.1f}s",
            file=sys.stderr,
            flush=True,
        )
        with open(out_path, "w") as f:
            json.dump(report, f, indent=0)


# ---------------------------------------------------------------------------
# Exactness against a check over every input.


def random_dag(rng: random.Random, inputs: int, stmts: int) -> tuple[Dag, list[Lit]]:
    """Return a random operation's statements and the values it checks."""
    d = Dag()
    lits = [d.input(i) for i in range(inputs)]
    rng.shuffle(lits)
    pool = list(lits)
    for _ in range(stmts):
        op = rng.choice(["and", "and", "or", "or", "xor", "choose"])

        # Mostly recent values, so long chains read disjoint inputs and
        # some read shared ones.
        def pick() -> Lit:
            if rng.random() < 0.7:
                k = pool[max(0, len(pool) - 1 - int(rng.expovariate(0.3)))]
            else:
                k = rng.choice(pool)
            return k ^ (1 if rng.random() < 0.3 else 0)

        arity = 3 if op == "choose" else 2
        kids = tuple(pick() for _ in range(arity))
        lit = d.stmt(op, kids)
        pool.append(lit)
        if rng.random() < 0.2:
            pool.append(lits[rng.randrange(inputs)])
    return d, [pool[-1], pool[-2], pool[-3], *lits]


def random_tree(rng: random.Random, leaves: list[Lit]) -> Any:
    """Return a random read-once formula over the leaves."""
    if len(leaves) == 1:
        return ("leaf", leaves[0] ^ (1 if rng.random() < 0.3 else 0))
    op = rng.choice(
        ["and", "or", "xor", "choose"] if len(leaves) >= 3 else ["and", "or", "xor"]
    )
    parts = 3 if op == "choose" else rng.randint(2, min(4, len(leaves)))
    cuts = sorted(rng.sample(range(1, len(leaves)), parts - 1))
    groups = [
        leaves[a:b] for a, b in zip([0, *cuts], [*cuts, len(leaves)], strict=True)
    ]
    return (op, [random_tree(rng, g) for g in groups])


def emit_tree(d: Dag, rng: random.Random, t: Any, *, mutate: bool = False) -> Lit:
    """Write a tree out as statements, regrouped and respelled at random but the same function."""
    if t[0] == "leaf":
        return t[1]
    op = t[0]
    if mutate and rng.random() < 0.3 and op in ("and", "or"):
        op = "or" if op == "and" else "and"
        mutate = False
    kids = [emit_tree(d, rng, c, mutate=mutate) for c in t[1]]
    if op == "choose":
        c, a, b = kids
        r = rng.random()
        if r < 0.33:
            return d.stmt("choose", (c, a, b))
        if r < 0.66:
            return d.stmt("choose", (c ^ 1, b, a))
        return d.stmt("choose", (c, a ^ 1, b ^ 1)) ^ 1
    rng.shuffle(kids)
    while len(kids) > 1:
        i = rng.randrange(len(kids) - 1)
        a, b = kids[i], kids[i + 1]
        r = rng.random()
        if op == "xor":
            lit = d.stmt("xor", (a, b)) if r < 0.5 else d.stmt("xor", (a ^ 1, b)) ^ 1
        elif r < 0.5:
            lit = d.stmt(op, (a, b))
        else:
            lit = d.stmt("or" if op == "and" else "and", (a ^ 1, b ^ 1)) ^ 1
        kids[i : i + 2] = [lit]
    return kids[0]


def random_read_once_dag(rng: random.Random, inputs: int) -> tuple[Dag, list[Lit]]:
    """Return random read-once formulas, each written out in several ways."""
    d = Dag()
    lits = [d.input(i) for i in range(inputs)]
    roots: list[Lit] = []
    for _ in range(rng.randint(2, 4)):
        chosen = rng.sample(lits, rng.randint(2, inputs))
        t = random_tree(rng, chosen)
        for _ in range(rng.randint(1, 3)):
            roots.append(emit_tree(d, rng, t, mutate=rng.random() < 0.3))
    for _ in range(rng.randint(0, 3)):
        a, b = rng.sample(roots, 2)
        roots.append(
            d.stmt(rng.choice(["and", "or", "xor"]), (a, b ^ rng.randint(0, 1)))
        )
    return d, roots + lits


def reference(
    d: Dag, roots: list[Lit], *, bdd: bool
) -> tuple[dict[int, int], dict[int, int | None], dict[int, Any]]:
    """Every value's inputs, constant, and key from one check over every input."""
    c = Checker(d, roots, use_bdd=False)
    nodes = c.nodes
    bit = {}
    for x in nodes:
        if d.op[x] == "in":
            bit[x] = len(bit)
    backend: Backend = BddBackend() if bdd else Tables(len(bit))
    value: dict[int, Any] = {}

    def lit(k: Lit) -> Any:
        v = value[k >> 1]
        return backend.negate(v) if k & 1 else v

    for x in nodes:
        if d.op[x] == "in":
            value[x] = backend.var(bit[x])
        elif d.op[x] == "choose":
            a, b, e = (lit(k) for k in d.kids[x])
            value[x] = backend.choose(a, b, e)
        else:
            k0, k1 = d.kids[x]
            value[x] = backend.apply(d.op[x], lit(k0), lit(k1))
    supp: dict[int, int] = {}
    const: dict[int, int | None] = {}
    key: dict[int, Any] = {}
    for x in nodes:
        f = value[x]
        if isinstance(backend, Tables):
            const[x] = (1 if f else 0) if f in (0, backend.mask) else None
            deps = [j for j in range(len(bit)) if backend.depends(f, j)]
        else:
            const[x] = f if f in (0, 1) else None
            deps = sorted(backend.bdd.support(f))
        s = 0
        for j in deps:
            s |= 1 << j
        supp[x] = s
        key[x] = backend.key(f)[0]
    return supp, const, key


def compare(d: Dag, roots: list[Lit], *, bdd: bool) -> list[str]:
    """Return where the split check and a check over every input disagree."""
    c = Checker(d, roots, use_bdd=True)
    c.run()
    supp, const, key = reference(d, roots, bdd=bdd)
    problems = []
    for x in c.nodes:
        if c.const[x] != const[x]:
            problems.append(f"constant {x}: split {c.const[x]} reference {const[x]}")
        elif const[x] is None and c.supp[x] != supp[x]:
            problems.append(f"inputs {x}")
    # The same and opposite values: classes of non-constant values.
    ref_classes: dict[Any, list[int]] = defaultdict(list)
    for x in c.nodes:
        if const[x] is None:
            ref_classes[key[x]].append(x)
    parent = {x: x for x in c.nodes}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, _ in c.same:
        parent[find(a)] = find(b)
    for members in ref_classes.values():
        roots_seen = {find(m) for m in members}
        if len(roots_seen) != 1:
            problems.append(f"missed same or opposite among {members}")
    seen_root: dict[int, Any] = {}
    for x in c.nodes:
        if const[x] is None:
            r = find(x)
            if r in seen_root and seen_root[r] != key[x]:
                problems.append(f"wrong same or opposite {x}")
            seen_root[r] = key[x]
    return problems


def verify(out_path: str, seed: int, count: int) -> None:
    """Compare the split check with a check over every input on random operations."""
    rng = random.Random(seed)  # noqa: S311 - Reproducible cases.
    results: dict[str, Any] = {
        "small": 0,
        "large": 0,
        "large_skipped": 0,
        "problems": [],
        "stats": defaultdict(int),
    }
    for i in range(count):
        large = i % 2 == 1
        inputs = rng.randint(24, 60) if large else rng.randint(3, 14)
        if i % 4 >= 2:
            d, roots = random_read_once_dag(rng, inputs)
        else:
            d, roots = random_dag(rng, inputs, rng.randint(inputs, 3 * inputs))
        try:
            problems = compare(d, roots, bdd=large)
        except BlowupError:
            results["large_skipped"] += 1
            continue
        results["large" if large else "small"] += 1
        c = Checker(d, roots, use_bdd=True)
        c.run()
        for k in (
            "disjoint",
            "overlap",
            "groups",
            "groups_read_once",
            "bdd_regions",
            "unresolved",
            "redundant",
            "constants",
        ):
            results["stats"][k] += c.stats[k]
        for p in problems:
            results["problems"].append((seed, i, p))
    with open(out_path, "w") as f:
        json.dump(results, f, indent=1)
    print(
        f"{results['small']} small, {results['large']} large ({results['large_skipped']} skipped), "
        f"{len(results['problems'])} problems",
        file=sys.stderr,
    )


def main() -> None:
    """Run a mode: measure, verify, or summarize."""
    mode = sys.argv[1]
    sys.setrecursionlimit(1_000_000)
    threading.stack_size(1 << 29)
    if mode == "summarize":
        rows = summarize(sys.argv[3:])
        if sys.argv[2] == "-":
            json.dump(rows, sys.stdout, indent=1)
        else:
            with open(sys.argv[2], "w") as f:
                json.dump(rows, f, indent=1)
        return
    if mode == "measure":
        target = lambda: measure(sys.argv[2], sys.argv[3:])
    else:
        target = lambda: verify(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    t = threading.Thread(target=target)
    t.start()
    t.join()


def summarize(paths: list[str]) -> dict[str, Any]:
    """Per scope and kind of unit: how many come under the limits, what's left, and the check times."""
    rows: dict[str, Any] = {}
    for path in paths:
        with open(path) as f:
            report = json.load(f)
        for units in (r["units"] for r in report.values()):
            for u in units:
                row = rows.setdefault(
                    f"scope{u['scope']}_{u['kind']}s",
                    {
                        "units": 0,
                        "too_big": 0,
                        "all_disjoint": 0,
                        "under_limits": 0,
                        "left_overlap": 0,
                        "left_group": 0,
                        "left_resolved_by_bdd": 0,
                        "left_unresolved": 0,
                        "parts": 0,
                        "groups": 0,
                        "groups_read_once": 0,
                        "max_part_leaves": 0,
                        "max_group_leaves": 0,
                        "split_seconds": [],
                        "bdd_seconds": [],
                        "with_literals": 0,
                        "with_merges": 0,
                        "examples": [],
                    },
                )
                row["units"] += 1
                if u.get("too_big"):
                    row["too_big"] += 1
                    continue
                b = u["split"]
                row["parts"] += b["overlap"]
                row["groups"] += b["groups"]
                row["groups_read_once"] += b["groups_read_once"]
                row["max_part_leaves"] = max(
                    row["max_part_leaves"], b["overlap_max_leaves"]
                )
                row["max_group_leaves"] = max(
                    row["max_group_leaves"], b["group_max_leaves"]
                )
                row["split_seconds"].append(u["split"]["seconds"])
                row["bdd_seconds"].append(u["bdd"]["seconds"] if "bdd" in u else 0.0)
                row["with_literals"] += u["literals"] > 0
                row["with_merges"] += u["merges"] > 0
                if b["overlap"] == 0:
                    row["all_disjoint"] += 1
                if b["overlap_over"] == 0 and b["group_over"] == 0:
                    row["under_limits"] += 1
                    continue
                row["left_overlap"] += b["overlap_over"] > 0
                row["left_group"] += b["group_over"] > 0
                if u["bdd"]["unresolved"]:
                    row["left_unresolved"] += 1
                else:
                    row["left_resolved_by_bdd"] += 1
                row["examples"].append(
                    (u["where"], u["study"], b["reasons"][:3], u["bdd"]["unresolved"])
                )
    for row in rows.values():
        for k in ("split_seconds", "bdd_seconds"):
            v = sorted(row[k])
            row[k] = {
                "total": round(sum(v), 2),
                "median": round(v[len(v) // 2], 4) if v else 0,
                "max": round(v[-1], 3) if v else 0,
            }
        row["examples"] = row["examples"][:15]
    return rows


if __name__ == "__main__":
    main()
