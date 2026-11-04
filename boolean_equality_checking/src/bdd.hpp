// Reduced ordered BDDs with complement edges. With complement edges, a node and
// its negation share one node, and two functions are equal exactly when their
// edges are equal, so equality modulo complement is a comparison of node ids.
#pragma once

#include <cstdint>
#include <stdexcept>
#include <vector>

#include "aig.hpp"

namespace beq {

// DLP 57's budget: a fixed number of steps of the compiler's own work per
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
    size_t slot = mix64((static_cast<uint64_t>(f) << 32) | g) & (cache_.size() - 1);
    CacheEntry& e = cache_[slot];
    if (e.f == f && e.g == g) return e.r;
    uint32_t lf = level_[f >> 1], lg = level_[g >> 1];
    uint32_t top = lf < lg ? lf : lg;
    Edge f0, f1, g0, g1;
    cofactors(f, top, f0, f1);
    cofactors(g, top, g0, g1);
    Edge r0 = land(f0, g0);
    Edge r1 = land(f1, g1);
    Edge r = make(top, r0, r1);
    CacheEntry& e2 = cache_[slot];
    e2 = CacheEntry{f, g, r};
    if (num_nodes() > cache_.size() && cache_.size() < (1u << 26)) grow_cache();
    return r;
  }

  size_t num_nodes() const { return level_.size(); }

  // Children and level of a node, for walking another manager's OBDD.
  Edge high(uint32_t node) const { return hi_[node]; }
  Edge low(uint32_t node) const { return lo_[node]; }
  uint32_t level_of(uint32_t node) const { return level_[node]; }

  // Calls visit(level, value) along one path from e to the true terminal.
  // e must not be the false constant.
  template <typename Visit>
  void satisfying_path(Edge e, Visit visit) const {
    while ((e >> 1) != 0) {
      uint32_t n = e >> 1, c = e & 1;
      Edge hi = hi_[n] ^ c, lo = lo_[n] ^ c;
      bool take_hi = hi != kFalse;
      visit(level_[n], take_hi);
      e = take_hi ? hi : lo;
    }
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
    return level_.size() * 12 + unique_.size() * 4 + cache_.size() * sizeof(CacheEntry);
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
    size_t slot = mix64((static_cast<uint64_t>(level) << 52) ^ (static_cast<uint64_t>(lo) << 26) ^ hi) & mask;
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
      size_t slot = mix64((static_cast<uint64_t>(level_[n]) << 52) ^ (static_cast<uint64_t>(lo_[n]) << 26) ^ hi_[n]) & mask;
      while (unique_[slot] != 0) slot = (slot + 1) & mask;
      unique_[slot] = n;
    }
  }

  void grow_cache() {
    std::vector<CacheEntry> old;
    old.swap(cache_);
    cache_.assign(old.size() * 2, CacheEntry{UINT32_MAX, 0, 0});
  }

  uint32_t num_levels_;
  size_t node_limit_;
  std::vector<uint32_t> level_;
  std::vector<Edge> lo_, hi_;
  std::vector<uint32_t> unique_;
  std::vector<CacheEntry> cache_;
};

}  // namespace beq
