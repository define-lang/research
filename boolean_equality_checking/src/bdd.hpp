// Reduced ordered BDDs with complement edges. With complement edges, a node and
// its negation share one node, and two functions are equal exactly when their
// edges are equal, so equality modulo complement is a comparison of node ids.
#pragma once

#include <cstdint>
#include <stdexcept>
#include <vector>

#include "aig.hpp"

namespace beq {

// DLP 59's budget: a fixed number of steps of the compiler's own work per
// value operation, never time. A BDD operation past its trivial cases is 6
// steps, a new BDD node 20, a node or a candidate of the match search 1, and
// a value evaluated on a new sample 30: those weights make steps follow time
// (about 2.4 ns a step, half the measured value operations within 9% of it).
// `at` is the value being worked on, as a literal of the value operation's
// graph, for the error.
struct BudgetExceeded : std::runtime_error {
  BudgetExceeded() : std::runtime_error("step budget") {}
};
struct StepBudget {
  enum Kind { kBdd, kSearch, kSample, kNode };
  uint64_t used = 0, limit = UINT64_MAX;
  uint64_t by_kind[4] = {0, 0, 0, 0};
  Lit at = 0;
  static constexpr uint64_t kWeight[4] = {6, 1, 30, 20};
  void spend(uint64_t n, Kind kind) {
    used += n * kWeight[kind];
    by_kind[kind] += n;
    if (used > limit) throw BudgetExceeded();
  }
};

struct BddLimit : std::runtime_error {
  BddLimit() : std::runtime_error("bdd node limit") {}
};

class Bdd {
 public:
  // Edge = 2 * node + complement. Node 0 is the constant true.
  using Edge = uint32_t;
  static constexpr Edge kTrue = 0, kFalse = 1;

  Bdd(uint32_t num_levels, size_t node_limit) : num_levels_(num_levels), node_limit_(node_limit) {
    level_.push_back(num_levels);  // terminal sits below every level
    lo_.push_back(0);
    hi_.push_back(0);
    resize_unique(1u << 12);
    cache_.assign(1u << 16, CacheEntry{UINT32_MAX, 0, 0});
  }

  StepBudget* budget = nullptr;

  Edge var(uint32_t level) { return make(level, kFalse, kTrue); }

  Edge land(Edge f, Edge g) {
    if (f == kFalse || g == kFalse || f == (g ^ 1)) return kFalse;
    if (f == kTrue || f == g) return g;
    if (g == kTrue) return f;
    if (budget) budget->spend(1, StepBudget::kBdd);
    if (f > g) std::swap(f, g);
    const uint64_t key_hash = mix64((static_cast<uint64_t>(f) << 32) | g);
    {
      const CacheEntry& e = cache_[key_hash & (cache_.size() - 1)];
      if (e.f == f && e.g == g) return e.r;
    }
    uint32_t lf = level_[f >> 1], lg = level_[g >> 1];
    uint32_t top = lf < lg ? lf : lg;
    Edge f0, f1, g0, g1;
    cofactors(f, top, f0, f1);
    cofactors(g, top, g0, g1);
    Edge r0 = land(f0, g0);
    Edge r1 = land(f1, g1);
    Edge r = make(top, r0, r1);
    if (num_nodes() > cache_.size() && cache_.size() < (1u << 26)) grow_cache();
    cache_[key_hash & (cache_.size() - 1)] = CacheEntry{f, g, r};
    return r;
  }

  Edge lor(Edge f, Edge g) { return land(f ^ 1, g ^ 1) ^ 1; }

  Edge lxor(Edge f, Edge g) {
    if (f == kFalse) return g;
    if (g == kFalse) return f;
    if (f == kTrue) return g ^ 1;
    if (g == kTrue) return f ^ 1;
    if (f == g) return kFalse;
    if (f == (g ^ 1)) return kTrue;
    if (budget) budget->spend(1, StepBudget::kBdd);
    // xor(f ^ c1, g ^ c2) == xor(f, g) ^ (c1 ^ c2).
    const Edge flip = (f ^ g) & 1u;
    f &= ~1u;
    g &= ~1u;
    if (f > g) std::swap(f, g);
    if (xor_cache_.empty()) xor_cache_.assign(1u << 15, CacheEntry{UINT32_MAX, 0, 0});
    const uint64_t key_hash = mix64((static_cast<uint64_t>(f) << 32) | g);
    {
      const CacheEntry& e = xor_cache_[key_hash & (xor_cache_.size() - 1)];
      if (e.f == f && e.g == g) return e.r ^ flip;
    }
    const uint32_t lf = level_[f >> 1], lg = level_[g >> 1];
    const uint32_t top = lf < lg ? lf : lg;
    Edge f0, f1, g0, g1;
    cofactors(f, top, f0, f1);
    cofactors(g, top, g0, g1);
    const Edge r0 = lxor(f0, g0);
    const Edge r1 = lxor(f1, g1);
    const Edge r = make(top, r0, r1);
    if (num_nodes() > xor_cache_.size() && xor_cache_.size() < (1u << 25)) grow_xor_cache();
    xor_cache_[key_hash & (xor_cache_.size() - 1)] = CacheEntry{f, g, r};
    return r ^ flip;
  }

  Edge ite(Edge c, Edge t, Edge e) {
    if (c == kTrue) return t;
    if (c == kFalse) return e;
    if (t == e) return t;
    if (t == kTrue && e == kFalse) return c;
    if (t == kFalse && e == kTrue) return c ^ 1;
    if (t == kTrue || c == t) return lor(c, e);
    if (t == kFalse || c == (t ^ 1)) return land(c ^ 1, e);
    if (e == kTrue || c == (e ^ 1)) return lor(c ^ 1, t);
    if (e == kFalse || c == e) return land(c, t);
    if (t == (e ^ 1)) return lxor(c ^ 1, t);
    if (budget) budget->spend(1, StepBudget::kBdd);
    if (c & 1u) {
      c ^= 1u;
      std::swap(t, e);
    }
    const Edge out_flip = t & 1u;
    if (out_flip) {
      t ^= 1u;
      e ^= 1u;
    }
    if (ite_cache_.empty()) ite_cache_.assign(1u << 15, IteEntry{UINT32_MAX, 0, 0, 0});
    const uint64_t key_hash =
        mix64(mix64((static_cast<uint64_t>(c) << 32) | t) ^ (static_cast<uint64_t>(e) * 0x9E3779B97F4A7C15ULL));
    {
      const IteEntry& ent = ite_cache_[key_hash & (ite_cache_.size() - 1)];
      if (ent.c == c && ent.t == t && ent.e == e) return ent.r ^ out_flip;
    }
    const uint32_t lc = level_[c >> 1], lt = level_[t >> 1], le = level_[e >> 1];
    const uint32_t top = std::min(lc, std::min(lt, le));
    Edge c0, c1, t0, t1, e0, e1;
    cofactors(c, top, c0, c1);
    cofactors(t, top, t0, t1);
    cofactors(e, top, e0, e1);
    const Edge r0 = ite(c0, t0, e0);
    const Edge r1 = ite(c1, t1, e1);
    const Edge r = make(top, r0, r1);
    if (num_nodes() > ite_cache_.size() && ite_cache_.size() < (1u << 25)) grow_ite_cache();
    ite_cache_[key_hash & (ite_cache_.size() - 1)] = IteEntry{c, t, e, r};
    return r ^ out_flip;
  }

  size_t num_nodes() const { return level_.size(); }

  // Children and level of a node, for walking another manager's OBDD.
  Edge high(uint32_t node) const { return hi_[node]; }
  Edge low(uint32_t node) const { return lo_[node]; }
  uint32_t level_of(uint32_t node) const { return level_[node]; }

  // Calls visit(level, value) along one path from e to the true terminal.
  // e must not be the false constant.
  template <typename Visit>
  void satisfying_path(Edge e, Visit visit, bool prefer_hi = true) const {
    while ((e >> 1) != 0) {
      uint32_t n = e >> 1, c = e & 1;
      Edge hi = hi_[n] ^ c, lo = lo_[n] ^ c;
      bool take_hi = prefer_hi ? (hi != kFalse) : (lo == kFalse);
      visit(level_[n], take_hi);
      e = take_hi ? hi : lo;
    }
  }

  // Calls visit(level, value) along one assignment where a and b differ,
  // in O(num_levels) time with zero node allocations. Precondition: a != b.
  template <typename Visit>
  void distinguishing_path(Edge a, Edge b, Visit visit) const {
    while (a != b) {
      const uint32_t la = level_[a >> 1], lb = level_[b >> 1];
      const uint32_t top = la < lb ? la : lb;
      if (top == num_levels_) break;
      Edge a0, a1, b0, b1;
      cofactors(a, top, a0, a1);
      cofactors(b, top, b0, b1);
      const bool take_hi = (a0 == b0);
      visit(top, take_hi);
      a = take_hi ? a1 : a0;
      b = take_hi ? b1 : b0;
    }
  }

  // Exact number of distinct canonical non-terminal ROBDD nodes reachable from `roots`.
  size_t reachable_node_count(const std::vector<Edge>& roots) const {
    std::vector<char> seen(level_.size(), 0);
    std::vector<uint32_t> stack;
    stack.reserve(roots.size());
    for (Edge e : roots) {
      const uint32_t n = e >> 1;
      if (n != 0 && !seen[n]) {
        seen[n] = 1;
        stack.push_back(n);
      }
    }
    size_t count = 0;
    while (!stack.empty()) {
      const uint32_t n = stack.back();
      stack.pop_back();
      ++count;
      const uint32_t lo = lo_[n] >> 1, hi = hi_[n] >> 1;
      if (lo != 0 && !seen[lo]) {
        seen[lo] = 1;
        stack.push_back(lo);
      }
      if (hi != 0 && !seen[hi]) {
        seen[hi] = 1;
        stack.push_back(hi);
      }
    }
    return count;
  }

  // Nodes reachable from the given edges, per level.
  std::vector<uint32_t> reachable_level_counts(const std::vector<Edge>& roots) const {
    std::vector<char> mark(level_.size(), 0);
    std::vector<uint32_t> stack;
    std::vector<uint32_t> counts(num_levels_ + 1, 0);
    for (Edge r : roots) stack.push_back(r >> 1);
    while (!stack.empty()) {
      uint32_t n = stack.back();
      stack.pop_back();
      if (mark[n]) continue;
      mark[n] = 1;
      ++counts[level_[n]];
      if (n == 0) continue;
      stack.push_back(lo_[n] >> 1);
      stack.push_back(hi_[n] >> 1);
    }
    return counts;
  }
  size_t memory_bytes() const {
    return level_.size() * 12 + unique_.size() * 4 + (cache_.size() + xor_cache_.size()) * sizeof(CacheEntry) +
           ite_cache_.size() * sizeof(IteEntry);
  }

  // Nodes at each level, for width measurements.
  std::vector<uint32_t> level_counts() const {
    std::vector<uint32_t> counts(num_levels_ + 1, 0);
    for (uint32_t lv : level_) ++counts[lv];
    return counts;
  }

 private:
  struct CacheEntry {
    Edge f, g, r;
  };
  struct IteEntry {
    Edge c, t, e, r;
  };

  static uint64_t node_hash(uint32_t level, Edge lo, Edge hi) {
    return mix64(mix64(static_cast<uint64_t>(level) * 0x9E3779B97F4A7C15ULL ^ lo) ^
                 (static_cast<uint64_t>(hi) * 0xBF58476D1CE4E5B9ULL));
  }

  void cofactors(Edge e, uint32_t top, Edge& e0, Edge& e1) const {
    uint32_t n = e >> 1;
    if (level_[n] != top) {
      e0 = e1 = e;
      return;
    }
    uint32_t c = e & 1;
    e0 = lo_[n] ^ c;
    e1 = hi_[n] ^ c;
  }

  // Canonical node: the high edge is never complemented.
  Edge make(uint32_t level, Edge lo, Edge hi) {
    if (lo == hi) return lo;
    uint32_t c = hi & 1;
    lo ^= c;
    hi ^= c;
    size_t mask = unique_.size() - 1;
    size_t slot = node_hash(level, lo, hi) & mask;
    for (;;) {
      uint32_t n = unique_[slot];
      if (n == 0) break;
      if (level_[n] == level && lo_[n] == lo && hi_[n] == hi) return 2 * n + c;
      slot = (slot + 1) & mask;
    }
    if (level_.size() >= node_limit_) throw BddLimit();
    if (budget) budget->spend(1, StepBudget::kNode);
    uint32_t n = static_cast<uint32_t>(level_.size());
    level_.push_back(level);
    lo_.push_back(lo);
    hi_.push_back(hi);
    unique_[slot] = n;
    if (level_.size() * 2 > unique_.size()) resize_unique(unique_.size() * 2);
    return 2 * n + c;
  }

  void resize_unique(size_t size) {
    unique_.assign(size, 0);
    size_t mask = size - 1;
    for (uint32_t n = 1; n < level_.size(); ++n) {
      size_t slot = node_hash(level_[n], lo_[n], hi_[n]) & mask;
      while (unique_[slot] != 0) slot = (slot + 1) & mask;
      unique_[slot] = n;
    }
  }

  void grow_cache() {
    std::vector<CacheEntry> old;
    old.swap(cache_);
    const size_t new_size = old.size() * 2;
    cache_.assign(new_size, CacheEntry{UINT32_MAX, 0, 0});
    const size_t mask = new_size - 1;
    for (const CacheEntry& e : old)
      if (e.f != UINT32_MAX) cache_[mix64((static_cast<uint64_t>(e.f) << 32) | e.g) & mask] = e;
  }

  void grow_xor_cache() {
    std::vector<CacheEntry> old;
    old.swap(xor_cache_);
    const size_t new_size = old.size() * 2;
    xor_cache_.assign(new_size, CacheEntry{UINT32_MAX, 0, 0});
    const size_t mask = new_size - 1;
    for (const CacheEntry& e : old)
      if (e.f != UINT32_MAX) xor_cache_[mix64((static_cast<uint64_t>(e.f) << 32) | e.g) & mask] = e;
  }

  void grow_ite_cache() {
    std::vector<IteEntry> old;
    old.swap(ite_cache_);
    const size_t new_size = old.size() * 2;
    ite_cache_.assign(new_size, IteEntry{UINT32_MAX, 0, 0, 0});
    const size_t mask = new_size - 1;
    for (const IteEntry& ent : old)
      if (ent.c != UINT32_MAX)
        ite_cache_[mix64(mix64((static_cast<uint64_t>(ent.c) << 32) | ent.t) ^
                         (static_cast<uint64_t>(ent.e) * 0x9E3779B97F4A7C15ULL)) &
                   mask] = ent;
  }

  uint32_t num_levels_;
  size_t node_limit_;
  std::vector<uint32_t> level_;
  std::vector<Edge> lo_, hi_;
  std::vector<uint32_t> unique_;
  std::vector<CacheEntry> cache_, xor_cache_;
  std::vector<IteEntry> ite_cache_;
};

}  // namespace beq
