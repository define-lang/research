// What a boolean value operation checked with BDDs records for the operations
// that execute it: its written view's reduced ordered binary decision
// diagram, without complement edges, over its read views in its own order.
// Level 0 is asked first.
#pragma once

#include <algorithm>
#include <cstdint>
#include <functional>
#include <tuple>
#include <unordered_set>
#include <vector>

#include "aig.hpp"

namespace beq {

class Diagram {
 public:
  using Node = uint32_t;
  static constexpr Node kFalse = 0, kTrue = 1;

  explicit Diagram(uint32_t levels) : levels_(levels) {
    level_ = {levels, levels};
    lo_ = {0, 1};
    hi_ = {0, 1};
    unique_.assign(size_t{1} << 12, 0);
  }

  uint32_t level(Node n) const { return level_[n]; }
  Node lo(Node n) const { return lo_[n]; }
  Node hi(Node n) const { return hi_[n]; }
  static bool terminal(Node n) { return n <= 1; }
  // Nodes made, not counting the two answers.
  size_t size() const { return level_.size() - 2; }

  Node make(uint32_t level, Node lo, Node hi) {
    if (lo == hi) return lo;
    size_t mask = unique_.size() - 1;
    size_t slot = slot_of(level, lo, hi) & mask;
    for (;;) {
      const Node n = unique_[slot];
      if (n == 0) break;
      if (level_[n] == level && lo_[n] == lo && hi_[n] == hi) return n;
      slot = (slot + 1) & mask;
    }
    const Node n = static_cast<Node>(level_.size());
    level_.push_back(level);
    lo_.push_back(lo);
    hi_.push_back(hi);
    unique_[slot] = n;
    if (level_.size() * 2 > unique_.size()) resize_unique(unique_.size() * 2);
    return n;
  }

  // f with two levels fixed.
  Node restrict2(Node f, uint32_t la, bool va, uint32_t lb, bool vb) {
    ++stamp_;
    return restrict_rec(f, la, va, lb, vb);
  }

  // A hash of f's function: nodes are made after their children.
  uint64_t hash(Node f) const {
    std::vector<uint64_t> h(level_.size(), 0);
    h[0] = 0x5EED0;
    h[1] = 0x5EED1;
    for (size_t n = 2; n <= f && n < level_.size(); ++n)
      h[n] = mix64(mix64(level_[n] * 0x9E3779B97F4A7C15ULL ^ h[lo_[n]]) ^ (h[hi_[n]] * 31));
    return h[f];
  }

  // The value of f on one assignment of the levels.
  bool evaluate(Node f, const std::vector<char>& at) const {
    while (!terminal(f)) f = at[level_[f]] ? hi_[f] : lo_[f];
    return f == kTrue;
  }

  // Exact O(|Diagram|) symmetry signature per level, invariant under any
  // permutation of interchangeable views: whether the level is in f's
  // support, and Pr_p[f|_{x_l=1}] - Pr_p[f|_{x_l=0}] mod (2^61 - 1) for two
  // i.i.d. input biases p = 1/3 and p = 1/5.
  struct LevelSig {
    bool in_support = false;
    uint64_t w1 = 0, w2 = 0;
    bool operator==(const LevelSig& o) const { return in_support == o.in_support && w1 == o.w1 && w2 == o.w2; }
    bool operator<(const LevelSig& o) const {
      return std::tie(in_support, w1, w2) < std::tie(o.in_support, o.w1, o.w2);
    }
  };

  std::vector<LevelSig> level_signatures(Node root) const {
    std::vector<LevelSig> sig(levels_);
    if (terminal(root)) return sig;
    // Collect nodes reachable from root; nodes are created after children so
    // sorting by node id gives bottom-up order, and reverse gives top-down.
    std::vector<char> seen(level_.size(), 0);
    std::vector<Node> stack{root}, nodes;
    while (!stack.empty()) {
      const Node n = stack.back();
      stack.pop_back();
      if (terminal(n) || seen[n]) continue;
      seen[n] = 1;
      nodes.push_back(n);
      sig[level_[n]].in_support = true;
      stack.push_back(lo_[n]);
      stack.push_back(hi_[n]);
    }
    std::sort(nodes.begin(), nodes.end());
    static constexpr uint64_t kMod = (uint64_t{1} << 61) - 1;
    auto add_mod = [](uint64_t a, uint64_t b) {
      uint64_t s = a + b;
      return s >= kMod ? s - kMod : s;
    };
    auto sub_mod = [](uint64_t a, uint64_t b) { return a >= b ? a - b : a + kMod - b; };
    auto mul_mod = [](uint64_t a, uint64_t b) {
      const __uint128_t prod = static_cast<__uint128_t>(a) * b;
      uint64_t r = static_cast<uint64_t>(prod & kMod) + static_cast<uint64_t>(prod >> 61);
      return r >= kMod ? r - kMod : r;
    };
    // 1/3 and 1/5 mod (2^61 - 1).
    static constexpr uint64_t kInv3 = (2 * kMod + 1) / 3;
    static constexpr uint64_t kInv5 = (4 * kMod + 1) / 5;
    auto pass = [&](uint64_t p) {
      const uint64_t q = sub_mod(1, p);
      std::vector<uint64_t> prob(level_.size(), 0), reach(level_.size(), 0);
      prob[kTrue] = 1;
      for (Node n : nodes) prob[n] = add_mod(mul_mod(q, prob[lo_[n]]), mul_mod(p, prob[hi_[n]]));
      reach[root] = 1;
      std::vector<uint64_t> w(levels_, 0);
      for (size_t i = nodes.size(); i-- > 0;) {
        const Node n = nodes[i];
        const uint64_t r = reach[n];
        if (r == 0) continue;
        const uint64_t diff = sub_mod(prob[hi_[n]], prob[lo_[n]]);
        w[level_[n]] = add_mod(w[level_[n]], mul_mod(r, diff));
        reach[lo_[n]] = add_mod(reach[lo_[n]], mul_mod(q, r));
        reach[hi_[n]] = add_mod(reach[hi_[n]], mul_mod(p, r));
      }
      return w;
    };
    const std::vector<uint64_t> w1 = pass(kInv3), w2 = pass(kInv5);
    for (uint32_t l = 0; l < levels_; ++l) {
      sig[l].w1 = w1[l];
      sig[l].w2 = w2[l];
    }
    return sig;
  }

  // Exact zero-allocation lockstep check of whether levels `la` and `lb` are
  // interchangeable in `root`: f|_{la=0, lb=1} == f|_{la=1, lb=0}.
  // Fails fast in O(1)/O(depth) on non-symmetric pairs without walking levels < la.
  bool are_symmetric(Node root, uint32_t la, uint32_t lb) {
    if (la == lb || terminal(root)) return true;
    if (la > lb) std::swap(la, lb);
    ensure_level_nodes(root);
    if (sym_top_stamp_.size() < level_.size()) sym_top_stamp_.resize(level_.size(), 0);
    if (++sym_stamp_ == 0) {
      std::fill(sym_top_stamp_.begin(), sym_top_stamp_.end(), 0);
      sym_stamp_ = 1;
    }
    sym_eq_seen_.clear();
    std::function<bool(Node, Node)> eq = [&](Node a, Node b) -> bool {
      if (!terminal(a) && level_[a] == lb) a = hi_[a];
      if (!terminal(b) && level_[b] == lb) b = lo_[b];
      const uint32_t lv_a = terminal(a) ? levels_ : level_[a];
      const uint32_t lv_b = terminal(b) ? levels_ : level_[b];
      if (lv_a > lb && lv_b > lb) return a == b;
      const uint64_t key = (static_cast<uint64_t>(a) << 32) | b;
      if (!sym_eq_seen_.insert(key).second) return true;
      const uint32_t top = std::min(lv_a, lv_b);
      const Node a0 = (lv_a == top) ? lo_[a] : a;
      const Node a1 = (lv_a == top) ? hi_[a] : a;
      const Node b0 = (lv_b == top) ? lo_[b] : b;
      const Node b1 = (lv_b == top) ? hi_[b] : b;
      return eq(a0, b0) && eq(a1, b1);
    };
    // Fast fail: check nodes directly at level `la` first (avoids walking 0..la-1).
    for (Node u : level_nodes_[la])
      if (!eq(lo_[u], hi_[u])) return false;
    // Also check edges skipping level `la` (only reached if every node at `la` passed!).
    std::function<bool(Node)> walk = [&](Node u) -> bool {
      if (terminal(u)) return true;
      const uint32_t lu = level_[u];
      if (lu > la) return eq(u, u);
      if (lu == la) return true;  // already checked above
      if (sym_top_stamp_[u] == sym_stamp_) return true;
      sym_top_stamp_[u] = sym_stamp_;
      return walk(lo_[u]) && walk(hi_[u]);
    };
    return walk(root);
  }

  // Generate `count` deterministic assignments of levels 0..levels_-1 that
  // evaluate `root` to `want_true` (empty if `root` is the opposite constant).
  std::vector<std::vector<char>> sample_paths(Node root, bool want_true, size_t count, Rng& rng) const {
    const Node bad = want_true ? kFalse : kTrue;
    if (root == bad) return {};
    std::vector<std::vector<char>> out;
    out.reserve(count);
    for (size_t s = 0; s < count; ++s) {
      std::vector<char> at(levels_, 0);
      for (uint32_t l = 0; l < levels_; ++l) at[l] = static_cast<char>(rng.next() & 1);
      Node u = root;
      while (!terminal(u)) {
        const Node l = lo_[u], h = hi_[u];
        bool pick_hi;
        if (l == bad)
          pick_hi = true;
        else if (h == bad)
          pick_hi = false;
        else
          pick_hi = (rng.next() & 1) != 0;
        at[level_[u]] = pick_hi ? 1 : 0;
        u = pick_hi ? h : l;
      }
      out.push_back(std::move(at));
    }
    return out;
  }

 private:
  uint32_t levels_;
  std::vector<uint32_t> level_;
  std::vector<Node> lo_, hi_;
  std::vector<Node> unique_;
  std::vector<uint32_t> memo_stamp_;
  std::vector<Node> memo_;
  uint32_t stamp_ = 0;
  std::vector<uint32_t> sym_top_stamp_;
  uint32_t sym_stamp_ = 0;
  std::unordered_set<uint64_t> sym_eq_seen_;
  Node level_nodes_root_ = UINT32_MAX;
  std::vector<std::vector<Node>> level_nodes_;

  void ensure_level_nodes(Node root) {
    if (level_nodes_root_ == root) return;
    level_nodes_root_ = root;
    level_nodes_.assign(levels_, {});
    std::vector<char> seen(level_.size(), 0);
    std::vector<Node> stack{root};
    while (!stack.empty()) {
      const Node u = stack.back();
      stack.pop_back();
      if (terminal(u) || seen[u]) continue;
      seen[u] = 1;
      level_nodes_[level_[u]].push_back(u);
      stack.push_back(lo_[u]);
      stack.push_back(hi_[u]);
    }
  }

  static uint64_t slot_of(uint32_t level, Node lo, Node hi) {
    return mix64(mix64(static_cast<uint64_t>(level) * 0x9E3779B97F4A7C15ULL ^ lo) ^
                 (static_cast<uint64_t>(hi) * 0xBF58476D1CE4E5B9ULL));
  }
  void resize_unique(size_t size) {
    unique_.assign(size, 0);
    const size_t mask = size - 1;
    for (Node n = 2; n < level_.size(); ++n) {
      size_t slot = slot_of(level_[n], lo_[n], hi_[n]) & mask;
      while (unique_[slot] != 0) slot = (slot + 1) & mask;
      unique_[slot] = n;
    }
  }

  Node restrict_rec(Node f, uint32_t la, bool va, uint32_t lb, bool vb) {
    if (terminal(f)) return f;
    // Below both levels nothing changes.
    if (level_[f] > la && level_[f] > lb) return f;
    if (level_[f] == la) return restrict_rec(va ? hi_[f] : lo_[f], la, va, lb, vb);
    if (level_[f] == lb) return restrict_rec(vb ? hi_[f] : lo_[f], la, va, lb, vb);
    if (memo_stamp_.size() <= f) {
      memo_stamp_.resize(level_.size(), 0);
      memo_.resize(level_.size(), 0);
    }
    if (memo_stamp_[f] == stamp_) return memo_[f];
    const Node lo = restrict_rec(lo_[f], la, va, lb, vb);
    const Node hi = restrict_rec(hi_[f], la, va, lb, vb);
    const Node r = make(level_[f], lo, hi);
    if (memo_stamp_.size() <= f) {
      memo_stamp_.resize(level_.size(), 0);
      memo_.resize(level_.size(), 0);
    }
    memo_stamp_[f] = stamp_;
    memo_[f] = r;
    return r;
  }
};

struct RecordedDiagram {
  Diagram dd{0};
  Diagram::Node root = Diagram::kFalse;
  std::vector<uint32_t> view_of_level;  // read views from 0
};

}  // namespace beq
