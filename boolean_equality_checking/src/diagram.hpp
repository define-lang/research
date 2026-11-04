// Decision diagrams (DLP 57's Limits): canonical reduced ordered binary
// decision diagrams without complement edges, so a value and its opposite
// are different nodes and the number of nodes of a set of values depends
// only on the functions and the order of the inputs. Levels are the order:
// level 0 is asked first.
#pragma once

#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <unordered_map>
#include <vector>

#include "aig.hpp"

namespace beq {

class Diagram {
 public:
  using Node = uint32_t;
  static constexpr Node kFalse = 0, kTrue = 1;
  // An argument: a node, doubled, plus whether it's negated.
  using Arg = uint32_t;
  static Arg arg(Node n, bool negated = false) { return 2 * n + (negated ? 1u : 0u); }

  // Thrown by make() when the diagram would have more than node_limit nodes.
  struct LimitError : std::runtime_error {
    LimitError() : std::runtime_error("decision diagram node limit") {}
  };

  explicit Diagram(uint32_t levels) : levels_(levels) {
    level_ = {levels, levels};
    lo_ = {0, 1};
    hi_ = {0, 1};
    unique_.assign(size_t{1} << 12, 0);
    cache_.assign(size_t{1} << 14, CacheEntry{});
  }

  size_t node_limit = SIZE_MAX;

  Node var(uint32_t level) { return make(level, kFalse, kTrue); }
  uint32_t level(Node n) const { return level_[n]; }
  Node lo(Node n) const { return lo_[n]; }
  Node hi(Node n) const { return hi_[n]; }
  static bool terminal(Node n) { return n <= 1; }
  // Nodes made, not counting the two answers.
  size_t size() const { return level_.size() - 2; }
  uint32_t levels() const { return levels_; }
  size_t memory_bytes() const {
    return level_.size() * 12 + unique_.size() * 4 + cache_.size() * sizeof(CacheEntry) + 8 * mark_.size();
  }

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
    if (size() >= node_limit) throw LimitError();
    const Node n = static_cast<Node>(level_.size());
    level_.push_back(level);
    lo_.push_back(lo);
    hi_.push_back(hi);
    unique_[slot] = n;
    if (level_.size() * 2 > unique_.size()) resize_unique(unique_.size() * 2);
    if (level_.size() > cache_.size() && cache_.size() < (size_t{1} << 24)) cache_.assign(cache_.size() * 2, CacheEntry{});
    return n;
  }

  // The function given by a truth table of k arguments (row m: argument i
  // is bit i of m; k up to 6 in one word, more in table[]), of these
  // arguments.
  Node apply(const uint64_t* table, uint32_t k, const std::vector<Arg>& args) {
    if (k <= 3) {
      Arg a[3] = {0, 0, 0};
      for (uint32_t i = 0; i < k; ++i) a[i] = args[i];
      return apply_small(table[0], k, a);
    }
    std::unordered_map<std::vector<Arg>, Node, VectorHash> memo;
    return apply_large(table, k, args, memo);
  }
  Node apply(uint64_t table, uint32_t k, const std::vector<Arg>& args) { return apply(&table, k, args); }
  Node negate(Node f) { return apply(0x1, 1, {arg(f)}); }
  Node land(Arg a, Arg b) { return apply(0x8, 2, {a, b}); }

  // The function of another diagram's root, its levels given the
  // arguments in args_of_level.
  Node compose(const Diagram& callee, Node root, const std::vector<Arg>& args_of_level) {
    std::unordered_map<std::vector<Arg>, Node, VectorHash> memo;
    std::vector<Arg> state(args_of_level.size() + 1);
    return compose_rec(callee, root, args_of_level, memo, state);
  }

  // f with two levels fixed.
  Node restrict2(Node f, uint32_t la, bool va, uint32_t lb, bool vb) {
    ++stamp_;
    return restrict_rec(f, la, va, lb, vb);
  }

  // The levels f depends on.
  std::vector<char> support(Node f) const {
    std::vector<char> in(levels_, 0);
    std::vector<char> seen(level_.size(), 0);
    std::vector<Node> stack{f};
    while (!stack.empty()) {
      const Node n = stack.back();
      stack.pop_back();
      if (terminal(n) || seen[n]) continue;
      seen[n] = 1;
      in[level_[n]] = 1;
      stack.push_back(lo_[n]);
      stack.push_back(hi_[n]);
    }
    return in;
  }

  // Marks the nodes of f and returns how many were new: the shared
  // diagram's size grows by that.
  size_t mark(Node f) {
    if (mark_.size() < level_.size()) mark_.resize(level_.size(), 0);
    size_t added = 0;
    std::vector<Node> stack{f};
    while (!stack.empty()) {
      const Node n = stack.back();
      stack.pop_back();
      if (terminal(n) || mark_[n]) continue;
      mark_[n] = 1;
      ++added;
      stack.push_back(lo_[n]);
      stack.push_back(hi_[n]);
    }
    return added;
  }

  // An assignment of the levels (bit per level) on which f and g differ.
  std::vector<char> difference(Node f, Node g) const {
    std::vector<char> at(levels_, 0);
    while (f != g && !(terminal(f) && terminal(g))) {
      const uint32_t l = std::min(level_[f], level_[g]);
      const Node f0 = level_[f] == l ? lo_[f] : f, f1 = level_[f] == l ? hi_[f] : f;
      const Node g0 = level_[g] == l ? lo_[g] : g, g1 = level_[g] == l ? hi_[g] : g;
      if (f0 != g0) {
        f = f0;
        g = g0;
      } else {
        at[l] = 1;
        f = f1;
        g = g1;
      }
    }
    return at;
  }

  // Hashes of each node's function and of its opposite, for classes up to
  // complement; nodes are made after their children, so in index order.
  void hashes(std::vector<uint64_t>& h, std::vector<uint64_t>& opposite) const {
    h.assign(level_.size(), 0);
    opposite.assign(level_.size(), 0);
    h[0] = opposite[1] = 0x5EED0;
    h[1] = opposite[0] = 0x5EED1;
    for (size_t n = 2; n < level_.size(); ++n) {
      h[n] = mix64(mix64(level_[n] * 0x9E3779B97F4A7C15ULL ^ h[lo_[n]]) ^ (h[hi_[n]] * 31));
      opposite[n] = mix64(mix64(level_[n] * 0x9E3779B97F4A7C15ULL ^ opposite[lo_[n]]) ^ (opposite[hi_[n]] * 31));
    }
  }

  // The value of f on one assignment of the levels.
  bool evaluate(Node f, const std::vector<char>& at) const {
    while (!terminal(f)) f = at[level_[f]] ? hi_[f] : lo_[f];
    return f == kTrue;
  }

 private:
  struct CacheEntry {
    uint64_t table = 0;
    uint32_t k = UINT32_MAX;
    Arg a[3] = {0, 0, 0};
    Node r = 0;
  };
  struct VectorHash {
    size_t operator()(const std::vector<Arg>& v) const {
      uint64_t h = 0x12345;
      for (Arg a : v) h = mix64(h ^ a);
      return h;
    }
  };

  uint32_t levels_;
  std::vector<uint32_t> level_;
  std::vector<Node> lo_, hi_;
  std::vector<Node> unique_;
  std::vector<CacheEntry> cache_;
  std::vector<char> mark_;
  std::vector<uint32_t> memo_stamp_;
  std::vector<Node> memo_;
  uint32_t stamp_ = 0;

  static uint64_t slot_of(uint32_t level, Node lo, Node hi) {
    return mix64((static_cast<uint64_t>(level) << 52) ^ (static_cast<uint64_t>(lo) << 26) ^ hi);
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

  uint32_t level_of(Arg a) const { return level_[a >> 1]; }
  Arg cofactor(Arg a, uint32_t l, bool v) const {
    const Node n = a >> 1;
    if (terminal(n) || level_[n] != l) return a;
    return 2 * (v ? hi_[n] : lo_[n]) + (a & 1);
  }
  // R's answer once these arguments are answers, if it no longer depends
  // on the others: -1 when it does.
  static int constant_part(uint64_t table, uint32_t k, const Arg* a, bool all_answers) {
    uint32_t fixed = 0, value = 0;
    for (uint32_t i = 0; i < k; ++i)
      if ((a[i] >> 1) <= 1) {
        fixed |= 1u << i;
        value |= (((a[i] >> 1) ^ (a[i] & 1)) & 1u) << i;
      }
    if (all_answers) return static_cast<int>((table >> value) & 1);
    if (!fixed) return -1;
    int seen = -1;
    for (uint32_t m = 0; m < (1u << k); ++m) {
      if ((m & fixed) != value) continue;
      const int b = static_cast<int>((table >> m) & 1);
      if (seen < 0) seen = b;
      else if (seen != b) return -1;
    }
    return seen;
  }

  Node apply_small(uint64_t table, uint32_t k, const Arg* a) {
    // An argument given twice, or with its opposite: the function of fewer
    // arguments.
    for (uint32_t i = 0; i < k; ++i)
      for (uint32_t j = i + 1; j < k; ++j) {
        if ((a[i] >> 1) != (a[j] >> 1)) continue;
        const uint32_t flip = (a[i] ^ a[j]) & 1;
        uint64_t reduced = 0;
        for (uint32_t m = 0; m < (1u << (k - 1)); ++m) {
          // m over the arguments other than j; j's bit is i's, flipped.
          const uint32_t low = m & ((1u << j) - 1), high = m >> j;
          const uint32_t bit_i = (m >> i) & 1;
          const uint32_t full = low | ((bit_i ^ flip) << j) | (high << (j + 1));
          reduced |= ((table >> full) & 1) << m;
        }
        Arg rest[3] = {0, 0, 0};
        for (uint32_t x = 0, y = 0; x < k; ++x)
          if (x != j) rest[y++] = a[x];
        return apply_small(reduced, k - 1, rest);
      }
    bool all = true;
    for (uint32_t i = 0; i < k; ++i) all &= (a[i] >> 1) <= 1;
    const int c = constant_part(table, k, a, all);
    if (c >= 0) return c ? kTrue : kFalse;
    const size_t slot = mix64(table * 0x9E37 ^ (uint64_t{k} << 60) ^ (uint64_t{a[0]} << 40) ^ (uint64_t{a[1]} << 20) ^ a[2]) &
                        (cache_.size() - 1);
    const CacheEntry& e = cache_[slot];
    if (e.k == k && e.table == table && e.a[0] == a[0] && e.a[1] == a[1] && e.a[2] == a[2]) return e.r;
    uint32_t top = levels_;
    for (uint32_t i = 0; i < k; ++i)
      if ((a[i] >> 1) > 1) top = std::min(top, level_of(a[i]));
    Arg lo[3] = {0, 0, 0}, hi[3] = {0, 0, 0};
    for (uint32_t i = 0; i < k; ++i) {
      lo[i] = cofactor(a[i], top, false);
      hi[i] = cofactor(a[i], top, true);
    }
    const Node r0 = apply_small(table, k, lo);
    const Node r1 = apply_small(table, k, hi);
    const Node r = make(top, r0, r1);
    CacheEntry& w = cache_[mix64(table * 0x9E37 ^ (uint64_t{k} << 60) ^ (uint64_t{a[0]} << 40) ^ (uint64_t{a[1]} << 20) ^ a[2]) &
                           (cache_.size() - 1)];
    w.table = table;
    w.k = k;
    w.a[0] = a[0];
    w.a[1] = a[1];
    w.a[2] = a[2];
    w.r = r;
    return r;
  }

  Node apply_large(const uint64_t* table, uint32_t k, const std::vector<Arg>& a,
                   std::unordered_map<std::vector<Arg>, Node, VectorHash>& memo) {
    bool all = true;
    for (Arg x : a) all &= (x >> 1) <= 1;
    if (k <= 6) {
      const int c = constant_part(table[0], k, a.data(), all);
      if (c >= 0) return c ? kTrue : kFalse;
    } else if (all) {
      uint64_t m = 0;
      for (uint32_t i = 0; i < k; ++i) m |= uint64_t{((a[i] >> 1) ^ (a[i] & 1)) & 1u} << i;
      return ((table[m >> 6] >> (m & 63)) & 1) ? kTrue : kFalse;
    }
    auto it = memo.find(a);
    if (it != memo.end()) return it->second;
    uint32_t top = levels_;
    for (Arg x : a)
      if ((x >> 1) > 1) top = std::min(top, level_of(x));
    std::vector<Arg> lo(k), hi(k);
    for (uint32_t i = 0; i < k; ++i) {
      lo[i] = cofactor(a[i], top, false);
      hi[i] = cofactor(a[i], top, true);
    }
    const Node r0 = apply_large(table, k, lo, memo);
    const Node r1 = apply_large(table, k, hi, memo);
    const Node r = make(top, r0, r1);
    memo.emplace(a, r);
    return r;
  }

  Node compose_rec(const Diagram& callee, Node c, const std::vector<Arg>& args,
                   std::unordered_map<std::vector<Arg>, Node, VectorHash>& memo, std::vector<Arg>& state) {
    // Follow the callee while the argument it asks for is an answer.
    while (!terminal(c)) {
      const Arg x = args[callee.level(c)];
      if ((x >> 1) > 1) break;
      c = (((x >> 1) ^ (x & 1)) & 1) ? callee.hi(c) : callee.lo(c);
    }
    if (terminal(c)) return c;
    std::vector<Arg> key(args.size() + 1);
    key[0] = c;
    std::copy(args.begin(), args.end(), key.begin() + 1);
    auto it = memo.find(key);
    if (it != memo.end()) return it->second;
    uint32_t top = levels_;
    for (Arg x : args)
      if ((x >> 1) > 1) top = std::min(top, level_of(x));
    std::vector<Arg> lo(args.size()), hi(args.size());
    for (size_t i = 0; i < args.size(); ++i) {
      lo[i] = cofactor(args[i], top, false);
      hi[i] = cofactor(args[i], top, true);
    }
    const Node r0 = compose_rec(callee, c, lo, memo, state);
    const Node r1 = compose_rec(callee, c, hi, memo, state);
    const Node r = make(top, r0, r1);
    memo.emplace(std::move(key), r);
    return r;
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

// What a boolean value operation past twenty inputs records for the
// operations that execute it: its written view's decision diagram, levels
// in its own order of its read views.
struct RecordedDiagram {
  Diagram dd{0};
  Diagram::Node root = Diagram::kFalse;
  std::vector<uint32_t> view_of_level;  // read views from 0
};

}  // namespace beq
