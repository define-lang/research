//! Exact sizes of canonical (compressed and trimmed) SDDs, and searches over vtrees.
//!
//! A Boolean function over m variables is a truth table: bit a is the value at
//! the assignment whose i-th variable is bit i of a. A function at vtree node t
//! is stored over t's leaves in left-to-right order, so the left child's
//! variables are the low bits and the right child's the high bits.
//!
//! The canonical SDD of g at t is computed from its semantic definition: g is
//! decomposed at the deepest vtree node whose variables contain its support,
//! and the primes are the classes of left assignments with equal residuals.
//! The size is the number of elements over all distinct decision nodes.

use std::collections::{HashMap, HashSet};
use std::env;

#[derive(Clone, Debug)]
enum Vt {
    Leaf(usize),
    Node(Box<Vt>, Box<Vt>),
}

impl Vt {
    fn leaves(&self, out: &mut Vec<usize>) {
        match self {
            Vt::Leaf(x) => out.push(*x),
            Vt::Node(a, b) => {
                a.leaves(out);
                b.leaves(out);
            }
        }
    }
    fn size(&self) -> usize {
        match self {
            Vt::Leaf(_) => 1,
            Vt::Node(a, b) => a.size() + b.size(),
        }
    }
    fn show(&self) -> String {
        match self {
            Vt::Leaf(x) => format!("{}", x),
            Vt::Node(a, b) => format!("({} {})", a.show(), b.show()),
        }
    }
}

/// Flattened vtree: nodes with children indices, and number of variables.
struct Flat {
    left: Vec<usize>,
    right: Vec<usize>,
    nvars: Vec<usize>,
    leaf: Vec<bool>,
}

fn flatten(t: &Vt, f: &mut Flat) -> usize {
    match t {
        Vt::Leaf(_) => {
            f.left.push(usize::MAX);
            f.right.push(usize::MAX);
            f.nvars.push(1);
            f.leaf.push(true);
            f.left.len() - 1
        }
        Vt::Node(a, b) => {
            let ia = flatten(a, f);
            let ib = flatten(b, f);
            f.left.push(ia);
            f.right.push(ib);
            f.nvars.push(f.nvars[ia] + f.nvars[ib]);
            f.leaf.push(false);
            f.left.len() - 1
        }
    }
}

type Tt = Vec<u64>;

fn words(m: usize) -> usize {
    if m <= 6 {
        1
    } else {
        1 << (m - 6)
    }
}

fn mask_bits(m: usize) -> u64 {
    if m >= 6 {
        u64::MAX
    } else {
        (1u64 << (1u64 << m)) - 1
    }
}

#[inline]
fn get(t: &Tt, a: usize) -> bool {
    (t[a >> 6] >> (a & 63)) & 1 == 1
}

#[inline]
fn set(t: &mut Tt, a: usize) {
    t[a >> 6] |= 1u64 << (a & 63);
}

fn is_const(t: &Tt, m: usize) -> Option<bool> {
    let mk = mask_bits(m);
    let all0 = t.iter().all(|&w| w == 0);
    if all0 {
        return Some(false);
    }
    let all1 = if m >= 6 { t.iter().all(|&w| w == u64::MAX) } else { t[0] == mk };
    if all1 {
        return Some(true);
    }
    None
}

struct Canon<'a> {
    f: &'a Flat,
    seen: HashSet<(usize, Tt)>,
    size: usize,
    decisions: usize,
    per_node: Vec<usize>,
}

impl<'a> Canon<'a> {
    /// Account for the canonical SDD of g (over node t's variables), normalized.
    fn visit(&mut self, t: usize, g: Tt) {
        let m = self.f.nvars[t];
        if is_const(&g, m).is_some() || self.f.leaf[t] {
            return;
        }
        let l = self.f.left[t];
        let r = self.f.right[t];
        let ml = self.f.nvars[l];
        let mr = self.f.nvars[r];
        // Residuals for each left assignment.
        let mut groups: HashMap<Tt, Vec<usize>> = HashMap::new();
        let mut order: Vec<Tt> = Vec::new();
        for i in 0..(1usize << ml) {
            let mut res = vec![0u64; words(mr)];
            for j in 0..(1usize << mr) {
                if get(&g, i | (j << ml)) {
                    set(&mut res, j);
                }
            }
            let e = groups.entry(res.clone()).or_insert_with(|| {
                order.push(res.clone());
                Vec::new()
            });
            e.push(i);
        }
        if groups.len() == 1 {
            // Independent of the left variables.
            let res = order.pop().unwrap();
            self.visit(r, res);
            return;
        }
        if order.iter().all(|res| is_const(res, mr).is_some()) {
            // Depends only on the left variables.
            let mut p = vec![0u64; words(ml)];
            for res in &order {
                if is_const(res, mr) == Some(true) {
                    for &i in &groups[res] {
                        set(&mut p, i);
                    }
                }
            }
            self.visit(l, p);
            return;
        }
        if !self.seen.insert((t, g)) {
            return;
        }
        self.size += order.len();
        self.decisions += 1;
        self.per_node[t] += 1;
        for res in order {
            let mut p = vec![0u64; words(ml)];
            for &i in &groups[&res] {
                set(&mut p, i);
            }
            self.visit(l, p);
            self.visit(r, res);
        }
    }
}

/// Canonical SDD size (elements, decision nodes) of a global truth table on a vtree.
fn canonical_size(global: &Tt, n: usize, vt: &Vt) -> (usize, usize) {
    let mut order = Vec::new();
    vt.leaves(&mut order);
    let mut local = vec![0u64; words(n)];
    for a in 0..(1usize << n) {
        let mut ag = 0usize;
        for (p, &x) in order.iter().enumerate() {
            if (a >> p) & 1 == 1 {
                ag |= 1 << x;
            }
        }
        if get(global, ag) {
            set(&mut local, a);
        }
    }
    let mut f = Flat { left: vec![], right: vec![], nvars: vec![], leaf: vec![] };
    let root = flatten(vt, &mut f);
    let nn = f.left.len();
    let mut c = Canon { f: &f, seen: HashSet::new(), size: 0, decisions: 0, per_node: vec![0; nn] };
    c.visit(root, local);
    (c.size, c.decisions)
}

/// Per vtree node (postorder): variables, canonical decision nodes, inside rows, outside rows.
fn node_stats(global: &Tt, n: usize, vt: &Vt) -> Vec<(Vec<usize>, usize, usize, usize)> {
    let mut order = Vec::new();
    vt.leaves(&mut order);
    let mut local = vec![0u64; words(n)];
    for a in 0..(1usize << n) {
        let mut ag = 0usize;
        for (p, &x) in order.iter().enumerate() {
            if (a >> p) & 1 == 1 {
                ag |= 1 << x;
            }
        }
        if get(global, ag) {
            set(&mut local, a);
        }
    }
    let mut f = Flat { left: vec![], right: vec![], nvars: vec![], leaf: vec![] };
    let root = flatten(vt, &mut f);
    let nn = f.left.len();
    let mut c = Canon { f: &f, seen: HashSet::new(), size: 0, decisions: 0, per_node: vec![0; nn] };
    c.visit(root, local);
    // Variables of each node, in postorder matching flatten.
    let mut vars_of: Vec<Vec<usize>> = Vec::new();
    fn collect(t: &Vt, out: &mut Vec<Vec<usize>>) -> Vec<usize> {
        match t {
            Vt::Leaf(x) => {
                out.push(vec![*x]);
                vec![*x]
            }
            Vt::Node(a, b) => {
                let mut va = collect(a, out);
                let vb = collect(b, out);
                va.extend(vb);
                out.push(va.clone());
                va
            }
        }
    }
    collect(vt, &mut vars_of);
    let mut out = Vec::new();
    for t in 0..nn {
        let inside: usize = vars_of[t].iter().map(|&x| 1usize << x).sum();
        let rows = |mask: usize| -> usize {
            let others = ((1usize << n) - 1) & !mask;
            let mut set_: HashSet<Vec<bool>> = HashSet::new();
            let mut sub = mask;
            loop {
                let mut row = Vec::new();
                let mut o = others;
                loop {
                    row.push(get(global, sub | o));
                    if o == 0 { break; }
                    o = (o - 1) & others;
                }
                set_.insert(row);
                if sub == 0 { break; }
                sub = (sub - 1) & mask;
            }
            set_.len()
        };
        out.push((vars_of[t].clone(), c.per_node[t], rows(inside), rows(((1usize << n) - 1) & !inside)));
    }
    out
}

fn parse_vt(s: &str) -> Vt {
    fn go(b: &[u8], i: &mut usize) -> Vt {
        while b[*i] == b' ' { *i += 1; }
        if b[*i] == b'(' {
            *i += 1;
            let a = go(b, i);
            let c = go(b, i);
            while b[*i] == b' ' { *i += 1; }
            assert_eq!(b[*i], b')');
            *i += 1;
            Vt::Node(Box::new(a), Box::new(c))
        } else {
            let st = *i;
            while *i < b.len() && b[*i].is_ascii_digit() { *i += 1; }
            Vt::Leaf(std::str::from_utf8(&b[st..*i]).unwrap().parse().unwrap())
        }
    }
    let mut i = 0;
    go(s.as_bytes(), &mut i)
}

fn truth_table(n: usize, func: &dyn Fn(usize) -> bool) -> Tt {
    let mut t = vec![0u64; words(n)];
    for a in 0..(1usize << n) {
        if func(a) {
            set(&mut t, a);
        }
    }
    t
}

fn hwb(n: usize) -> Tt {
    truth_table(n, &|a: usize| {
        let w = a.count_ones() as usize;
        w > 0 && (a >> (w - 1)) & 1 == 1
    })
}

// ---------------------------------------------------------------------------
// Vtrees: enumeration and search
// ---------------------------------------------------------------------------

fn all_vtrees(vars: &[usize]) -> Vec<Vt> {
    if vars.len() == 1 {
        return vec![Vt::Leaf(vars[0])];
    }
    let mut out = Vec::new();
    let k = vars.len();
    for mask in 1..((1usize << k) - 1) {
        let lv: Vec<usize> = (0..k).filter(|i| (mask >> i) & 1 == 1).map(|i| vars[i]).collect();
        let rv: Vec<usize> = (0..k).filter(|i| (mask >> i) & 1 == 0).map(|i| vars[i]).collect();
        let ls = all_vtrees(&lv);
        let rs = all_vtrees(&rv);
        for a in &ls {
            for b in &rs {
                out.push(Vt::Node(Box::new(a.clone()), Box::new(b.clone())));
            }
        }
    }
    out
}

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    fn below(&mut self, k: usize) -> usize {
        (self.next() % (k as u64)) as usize
    }
    fn unit(&mut self) -> f64 {
        (self.next() >> 11) as f64 / (1u64 << 53) as f64
    }
}

fn random_vtree(vars: &mut Vec<usize>, rng: &mut Rng) -> Vt {
    // Random shape by random splits of a shuffled list.
    for i in (1..vars.len()).rev() {
        let j = rng.below(i + 1);
        vars.swap(i, j);
    }
    fn build(v: &[usize], rng: &mut Rng) -> Vt {
        if v.len() == 1 {
            return Vt::Leaf(v[0]);
        }
        let s = 1 + rng.below(v.len() - 1);
        Vt::Node(Box::new(build(&v[..s], rng)), Box::new(build(&v[s..], rng)))
    }
    build(vars, rng)
}

fn count_internal(t: &Vt) -> usize {
    match t {
        Vt::Leaf(_) => 0,
        Vt::Node(a, b) => 1 + count_internal(a) + count_internal(b),
    }
}

/// Apply a random local move to the internal node with preorder index k.
fn mutate(t: &Vt, rng: &mut Rng) -> Vt {
    let n_int = count_internal(t);
    let target = rng.below(n_int.max(1));
    let kind = rng.below(4);
    let mut counter = 0usize;
    fn go(t: &Vt, target: usize, kind: usize, counter: &mut usize) -> Vt {
        match t {
            Vt::Leaf(_) => t.clone(),
            Vt::Node(a, b) => {
                let here = *counter;
                *counter += 1;
                if here == target {
                    match kind {
                        0 => Vt::Node(b.clone(), a.clone()),
                        1 => match (&**a, &**b) {
                            // Rotate right: ((x y) z) -> (x (y z))
                            (Vt::Node(x, y), _) => Vt::Node(x.clone(), Box::new(Vt::Node(y.clone(), b.clone()))),
                            _ => t.clone(),
                        },
                        2 => match (&**a, &**b) {
                            // Rotate left: (x (y z)) -> ((x y) z)
                            (_, Vt::Node(y, z)) => Vt::Node(Box::new(Vt::Node(a.clone(), y.clone())), z.clone()),
                            _ => t.clone(),
                        },
                        _ => match (&**a, &**b) {
                            // Exchange: ((x y) z) -> ((x z) y)
                            (Vt::Node(x, y), _) => Vt::Node(Box::new(Vt::Node(x.clone(), b.clone())), y.clone()),
                            _ => t.clone(),
                        },
                    }
                } else {
                    let na = go(a, target, kind, counter);
                    let nb = go(b, target, kind, counter);
                    Vt::Node(Box::new(na), Box::new(nb))
                }
            }
        }
    }
    let mut out = go(t, target, kind, &mut counter);
    // Occasionally swap two leaf labels.
    if rng.below(3) == 0 {
        let mut leaves = Vec::new();
        out.leaves(&mut leaves);
        let i = rng.below(leaves.len());
        let j = rng.below(leaves.len());
        let (xi, xj) = (leaves[i], leaves[j]);
        fn relabel(t: &Vt, xi: usize, xj: usize) -> Vt {
            match t {
                Vt::Leaf(x) if *x == xi => Vt::Leaf(xj),
                Vt::Leaf(x) if *x == xj => Vt::Leaf(xi),
                Vt::Leaf(_) => t.clone(),
                Vt::Node(a, b) => Vt::Node(Box::new(relabel(a, xi, xj)), Box::new(relabel(b, xi, xj))),
            }
        }
        out = relabel(&out, xi, xj);
    }
    out
}

fn anneal(global: &Tt, n: usize, iters: usize, restarts: usize, seed: u64) -> (usize, Vt) {
    let mut rng = Rng(seed | 1);
    let mut best: Option<(usize, Vt)> = None;
    for _ in 0..restarts {
        let mut vars: Vec<usize> = (0..n).collect();
        let mut cur = random_vtree(&mut vars, &mut rng);
        let mut cur_cost = canonical_size(global, n, &cur).0;
        for it in 0..iters {
            let cand = mutate(&cur, &mut rng);
            let cost = canonical_size(global, n, &cand).0;
            let temp = 2.0 * (1.0 - it as f64 / iters as f64) + 0.01;
            let accept = cost <= cur_cost || rng.unit() < (-((cost - cur_cost) as f64) / (temp * (cur_cost as f64).max(1.0) * 0.05)).exp();
            if accept {
                cur = cand;
                cur_cost = cost;
            }
            if best.as_ref().map_or(true, |(b, _)| cur_cost < *b) {
                best = Some((cur_cost, cur.clone()));
            }
        }
    }
    best.unwrap()
}

fn read_tt(path: &str) -> (usize, Tt) {
    // File format: first line n, second line a string of 2^n characters 0/1.
    let s = std::fs::read_to_string(path).expect("read truth table");
    let mut lines = s.lines();
    let n: usize = lines.next().unwrap().trim().parse().unwrap();
    let bits = lines.next().unwrap().trim().as_bytes().to_vec();
    assert_eq!(bits.len(), 1 << n);
    let mut t = vec![0u64; words(n)];
    for (a, &c) in bits.iter().enumerate() {
        if c == b'1' {
            set(&mut t, a);
        }
    }
    (n, t)
}

fn linear(n: usize, left: bool) -> Vt {
    if left {
        let mut t = Vt::Leaf(0);
        for x in 1..n {
            t = Vt::Node(Box::new(t), Box::new(Vt::Leaf(x)));
        }
        t
    } else {
        let mut t = Vt::Leaf(n - 1);
        for x in (0..n - 1).rev() {
            t = Vt::Node(Box::new(Vt::Leaf(x)), Box::new(t));
        }
        t
    }
}

fn balanced(vars: &[usize]) -> Vt {
    if vars.len() == 1 {
        return Vt::Leaf(vars[0]);
    }
    let h = vars.len() / 2;
    Vt::Node(Box::new(balanced(&vars[..h])), Box::new(balanced(&vars[h..])))
}

fn right_linear_over(items: Vec<Vt>) -> Vt {
    let mut it = items.into_iter().rev();
    let mut t = it.next().unwrap();
    for x in it {
        t = Vt::Node(Box::new(x), Box::new(t));
    }
    t
}

// Right-linear over the pairs (x_1, x_n), (x_2, x_{n-1}), ...
fn pairs(n: usize) -> Vt {
    let mut items: Vec<Vt> = (0..n / 2)
        .map(|i| Vt::Node(Box::new(Vt::Leaf(i)), Box::new(Vt::Leaf(n - 1 - i))))
        .collect();
    if n % 2 == 1 {
        items.push(Vt::Leaf(n / 2));
    }
    right_linear_over(items)
}

// A right spine of `spine` variables taken alternately from both ends, then a
// balanced vtree over the middle variables in order.
fn spine_then_balanced(n: usize, spine: usize) -> Vt {
    let (mut lo, mut hi) = (0, n - 1);
    let mut items = Vec::new();
    for i in 0..spine {
        if i % 2 == 0 {
            items.push(Vt::Leaf(lo));
            lo += 1;
        } else {
            items.push(Vt::Leaf(hi));
            hi -= 1;
        }
    }
    let mid: Vec<usize> = (lo..=hi).collect();
    items.push(balanced(&mid));
    right_linear_over(items)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("help");
    match cmd {
        "hwb-exhaustive" => {
            for n in 2..=args[2].parse::<usize>().unwrap() {
                let g = hwb(n);
                let vars: Vec<usize> = (0..n).collect();
                let mut best = usize::MAX;
                let mut best_t = None;
                let mut count = 0usize;
                for t in all_vtrees(&vars) {
                    count += 1;
                    let (s, _) = canonical_size(&g, n, &t);
                    if s < best {
                        best = s;
                        best_t = Some(t);
                    }
                }
                println!("n={} vtrees={} min_canonical_size={} best_vtree={}", n, count, best, best_t.unwrap().show());
            }
        }
        "hwb-anneal" => {
            let lo: usize = args[2].parse().unwrap();
            let hi: usize = args[3].parse().unwrap();
            let iters: usize = args[4].parse().unwrap();
            let restarts: usize = args[5].parse().unwrap();
            for n in lo..=hi {
                let g = hwb(n);
                let (best, t) = anneal(&g, n, iters, restarts, 0x9e3779b97f4a7c15 ^ n as u64);
                let ll = canonical_size(&g, n, &linear(n, true)).0;
                let rl = canonical_size(&g, n, &linear(n, false)).0;
                println!("n={} best_found={} left_linear={} right_linear={} best_vtree={}", n, best, ll, rl, t.show());
            }
        }
        "tt-anneal" => {
            let (n, g) = read_tt(&args[2]);
            let iters: usize = args[3].parse().unwrap();
            let restarts: usize = args[4].parse().unwrap();
            let (best, t) = anneal(&g, n, iters, restarts, 12345);
            println!("n={} best_found={} best_vtree={}", n, best, t.show());
        }
        "tt-exhaustive" => {
            let (n, g) = read_tt(&args[2]);
            let vars: Vec<usize> = (0..n).collect();
            let mut best = usize::MAX;
            let mut best_t = None;
            for t in all_vtrees(&vars) {
                let (s, _) = canonical_size(&g, n, &t);
                if s < best {
                    best = s;
                    best_t = Some(t);
                }
            }
            println!("n={} min_canonical_size={} best_vtree={}", n, best, best_t.unwrap().show());
        }
        "stats" => {
            let (n, g) = read_tt(&args[2]);
            let vt = parse_vt(&args[3]);
            let (s, d) = canonical_size(&g, n, &vt);
            println!("canonical_size={} decision_nodes={}", s, d);
            for (vars, cn, inr, outr) in node_stats(&g, n, &vt) {
                if vars.len() > 1 {
                    println!("vars={:?} canonical_nodes={} inside_rows={} outside_rows={}", vars, cn, inr, outr);
                }
            }
        }
        "hwb-families" => {
            let lo: usize = args[2].parse().unwrap();
            let hi: usize = args[3].parse().unwrap();
            println!("n right_linear balanced pairs spine2 spine4 spine6");
            for n in lo..=hi {
                let g = hwb(n);
                let vars: Vec<usize> = (0..n).collect();
                let size = |t: &Vt| canonical_size(&g, n, t).0.to_string();
                let spine = |k: usize| if k + 2 <= n { size(&spine_then_balanced(n, k)) } else { "-".to_string() };
                println!(
                    "{} {} {} {} {} {} {}",
                    n,
                    size(&linear(n, false)),
                    size(&balanced(&vars)),
                    size(&pairs(n)),
                    spine(2),
                    spine(4),
                    spine(6)
                );
            }
        }
        "size" => {
            let (n, g) = read_tt(&args[2]);
            let vt = parse_vt(&args[3]);
            let (s, d) = canonical_size(&g, n, &vt);
            println!("{} {}", s, d);
        }
        _ => {
            eprintln!("usage: canon hwb-exhaustive MAXN | hwb-anneal LO HI ITERS RESTARTS | hwb-families LO HI | tt-anneal FILE ITERS RESTARTS | tt-exhaustive FILE | stats FILE VTREE | size FILE VTREE");
        }
    }
    let _ = Vt::Leaf(0).size();
}
