// What a boolean value operation checked with BDDs records for the operations
// that execute it: its written view's reduced ordered binary decision
// diagram, without complement edges, over its read views in its own order.
// Level 0 is asked first.
#pragma once

#include <cstdint>
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

 private:
  uint32_t levels_;
  std::vector<uint32_t> level_;
  std::vector<Node> lo_, hi_;
  std::vector<Node> unique_;
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
