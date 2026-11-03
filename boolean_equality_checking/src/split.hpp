// The split check (`beq program --split 1`): DLP 57's rules on values,
// checked statement by statement instead of with truth tables over every
// boolean input of the operation.
//
// A statement whose arguments read no common inputs, each argument a value
// that changes, depends on every input any argument reads, when every view
// of its operation matters: with all but one argument's inputs fixed, the
// other arguments are still free, so whatever input changes that argument
// can change the result. So each value depends on exactly the inputs it
// reads as written, except at statements whose arguments share inputs, and
// only those statements need an exact check. The check is a truth table
// over the values below the statement that read inputs nothing else in the
// check reads (its leaves): those are independent and each one changes, so
// the statement's function of them is exact. Two values can only be the
// same or opposite if they depend on the same inputs, so values are
// grouped by those inputs and each group of two or more is checked the same
// way, or, when its values are written with `and` and `not` alone over
// disjoint inputs, compared by a fixed form instead.
#pragma once

#include <algorithm>
#include <cstdint>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "aig.hpp"

namespace beq {

struct SplitNode {
  std::vector<Lit> args;  // none for the constant (node 0) and the inputs
  // An execution: whether every view of the executed operation matters.
  bool all_views_matter = true;
  // An associative and commutative operation of two views: 1 `and`, 2
  // `or`, 3 `xor`, 4 `xnor`; 0 for any other.
  int chain = 0;
  bool is_and = false;
};

class SplitCheck {
 public:
  using Word = std::function<uint64_t(Lit, size_t)>;
  // An execution's truth table over a check's leaves, from its arguments'.
  using CallEval = std::function<void(uint32_t node, const std::vector<Lit>& args, size_t words, const Word& word,
                                      uint64_t* row)>;
  static constexpr size_t kInputLimit = 20, kStatementLimit = 256;
  // The most leaves of one part or group (DLP 57's input limit unless
  // methods_experiment.py raises it).
  size_t input_limit = kInputLimit;

  SplitCheck(std::vector<SplitNode> nodes, uint32_t inputs, CallEval eval)
      : nodes_(std::move(nodes)), inputs_(inputs), eval_(std::move(eval)) {
    words_ = (static_cast<size_t>(inputs_) + 1 + 63) / 64;
  }

  // Each node's class up to complement in the high bits and its phase, as
  // tt_keys gives them; or, past the limits, over_limits.
  std::vector<uint64_t> keys;
  bool over_limits = false;
  std::string over_reason;
  size_t parts = 0, parts_max_leaves = 0, groups = 0, groups_fixed_form = 0, groups_max_leaves = 0;

  void run() {
    const size_t n = nodes_.size();
    supp_.assign(n * words_, 0);
    konst_.assign(n, -1);
    read_once_.assign(n, 0);
    konst_[0] = 0;
    for (uint32_t x = 1; x <= inputs_; ++x) {
      set_bit(x, x);
      read_once_[x] = 1;
    }
    for (uint32_t x = inputs_ + 1; x < n; ++x) {
      const SplitNode& node = nodes_[x];
      bool disjoint = node.all_views_matter;
      std::vector<uint64_t> acc(words_, 0);
      std::set<uint32_t> distinct;
      bool ro = node.is_and;
      for (Lit a : node.args) {
        const uint32_t k = node_of(a);
        disjoint &= konst_[k] < 0 && distinct.insert(k).second;
        for (size_t w = 0; w < words_; ++w) {
          disjoint &= (acc[w] & supp(k)[w]) == 0;
          acc[w] |= supp(k)[w];
        }
        ro &= read_once_[k] != 0;
      }
      if (disjoint) {
        std::copy(acc.begin(), acc.end(), supp(x));
        read_once_[x] = ro;
        continue;
      }
      ++parts;
      Region r = region({x});
      parts_max_leaves = std::max(parts_max_leaves, r.leaf_count());
      if (!within(r)) {
        over_limits = true;
        over_reason = "part of " + std::to_string(r.leaf_count()) + " leaves, " + std::to_string(r.expanded.size()) +
                      " statements";
        return;
      }
      size_t tw = 0;
      const Values& value = evaluate(r, tw);
      const std::vector<uint64_t>& t = value.at(x);
      const uint32_t L = static_cast<uint32_t>(r.leaf_count());
      const uint64_t valid = valid_bits(L);
      bool all0 = true, all1 = true;
      for (uint64_t w : t) {
        all0 &= (w & valid) == 0;
        all1 &= (w & valid) == valid;
      }
      if (all0 || all1) {
        konst_[x] = all1 ? 1 : 0;
        continue;
      }
      for (uint32_t j = 0; j < L; ++j)
        if (depends(t, L, j))
          for (size_t w = 0; w < words_; ++w) supp(x)[w] |= r.leaf_supp[j][w];
    }
    group_values();
  }

  // Each of these values' truth tables over the leaves of one check of
  // them, or null past the limits.
  const std::unordered_map<uint32_t, std::vector<uint64_t>>* tables_of(const std::vector<uint32_t>& tops,
                                                                       size_t& words, uint32_t& leaves) {
    // Every value checked needs its own table: no leaves merged.
    Region r = region(tops, false);
    if (!within(r)) return nullptr;
    leaves = static_cast<uint32_t>(r.leaf_count());
    return &evaluate(r, words);
  }

  bool depends_on(uint32_t node, uint32_t input) const { return (supp(node)[input / 64] >> (input % 64)) & 1; }
  bool constant(uint32_t node) const { return konst_[node] >= 0; }

 private:
  struct Region {
    std::vector<uint32_t> tops;
    std::vector<uint32_t> expanded;  // in node order
    std::set<uint32_t> cand;
    std::vector<uint32_t> leaves;  // the leaves that are values, in node order
    std::unordered_set<uint32_t> absorbed;
    // Each chain's operands besides the leaves only it reads, which are one
    // leaf (merged), and whether its absorbed `xor`s negate it.
    std::map<uint32_t, std::vector<Lit>> rest, merged;
    std::map<uint32_t, bool> negated;
    std::vector<std::vector<uint64_t>> leaf_supp;  // leaves, then merged leaves
    size_t leaf_count() const { return leaves.size() + merged.size(); }
  };

  std::vector<SplitNode> nodes_;
  uint32_t inputs_;
  CallEval eval_;
  size_t words_ = 1;
  std::vector<uint64_t> supp_;
  std::vector<int> konst_;
  std::vector<char> read_once_;
  struct Canon {
    int phase = 0;
    bool is_or = false;
    uint64_t sum = 0, hash = 0;
  };
  std::unordered_map<uint32_t, Canon> canon_;
  static constexpr size_t kKeptWords = size_t{1} << 25;
  std::map<std::vector<uint32_t>, std::unordered_map<uint32_t, std::vector<uint64_t>>> kept_;
  size_t kept_words_ = 0;
  std::unordered_map<uint32_t, std::vector<uint64_t>> scratch_;

  uint64_t* supp(uint32_t x) { return &supp_[x * words_]; }
  const uint64_t* supp(uint32_t x) const { return &supp_[x * words_]; }
  void set_bit(uint32_t x, uint32_t bit) { supp(x)[bit / 64] |= 1ULL << (bit % 64); }

  bool within(const Region& r) const {
    return r.leaf_count() <= input_limit && r.expanded.size() <= kStatementLimit;
  }
  static uint64_t valid_bits(uint32_t leaves) { return leaves >= 6 ? ~0ULL : ((1ULL << (1u << leaves)) - 1); }

  static bool depends(const std::vector<uint64_t>& t, uint32_t leaves, uint32_t j) {
    static const uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                     0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
    const uint64_t valid = valid_bits(leaves);
    for (size_t w = 0; w < t.size(); ++w) {
      if (j < 6) {
        if (((t[w] ^ (t[w] >> (1 << j))) & ~kVar[j] & valid) != 0) return true;
      } else {
        const size_t b = size_t{1} << (j - 6);
        if (!(w & b) && t[w] != t[w | b]) return true;
      }
    }
    return false;
  }

  Region region(std::vector<uint32_t> tops, bool merge = true) const {
    Region r;
    r.tops = tops;
    // An input or a constant checked is its own leaf.
    std::set<uint32_t> expanded;
    for (uint32_t t : tops) (t <= inputs_ || konst_[t] >= 0 ? r.cand : expanded).insert(t);
    for (uint32_t t : expanded)
      for (Lit a : nodes_[t].args)
        if (!expanded.count(node_of(a))) r.cand.insert(node_of(a));
    std::vector<uint64_t> seen(words_), multi(words_);
    while (true) {
      std::fill(seen.begin(), seen.end(), 0);
      std::fill(multi.begin(), multi.end(), 0);
      for (uint32_t c : r.cand)
        for (size_t w = 0; w < words_; ++w) {
          multi[w] |= seen[w] & supp(c)[w];
          seen[w] |= supp(c)[w];
        }
      std::vector<uint32_t> overlapping;
      for (uint32_t c : r.cand) {
        if (c <= inputs_ || konst_[c] >= 0) continue;
        bool hit = false;
        for (size_t w = 0; w < words_ && !hit; ++w) hit = (supp(c)[w] & multi[w]) != 0;
        if (hit) overlapping.push_back(c);
      }
      if (overlapping.empty()) break;
      // A value below another that's also replaced needs no replacing
      // itself once the other is gone.
      std::vector<uint32_t> chosen;
      for (uint32_t c : overlapping) {
        bool covered = false;
        for (uint32_t m : overlapping) {
          if (m == c) continue;
          bool subset = true, equal = true;
          for (size_t w = 0; w < words_; ++w) {
            subset &= (supp(c)[w] & supp(m)[w]) == supp(c)[w];
            equal &= supp(c)[w] == supp(m)[w];
          }
          if (subset && (!equal || m > c)) {
            covered = true;
            break;
          }
        }
        if (!covered) chosen.push_back(c);
      }
      for (uint32_t c : chosen) {
        r.cand.erase(c);
        expanded.insert(c);
        for (Lit a : nodes_[c].args)
          if (!expanded.count(node_of(a))) r.cand.insert(node_of(a));
      }
    }
    r.expanded.assign(expanded.begin(), expanded.end());
    std::unordered_map<uint32_t, std::vector<std::pair<uint32_t, bool>>> parents;
    for (uint32_t e : r.expanded)
      for (Lit a : nodes_[e].args) parents[node_of(a)].push_back({e, is_compl(a)});
    const std::set<uint32_t> top_set(tops.begin(), tops.end());
    for (uint32_t e : r.expanded) {
      const int chain = nodes_[e].chain;
      auto it = parents.find(e);
      if (top_set.count(e) || chain == 0 || it == parents.end() || it->second.size() != 1) continue;
      const auto [p, negated] = it->second[0];
      if (nodes_[p].chain == chain && (!negated || chain >= 3)) r.absorbed.insert(e);
    }
    std::set<uint32_t> merged_away;
    for (uint32_t e : r.expanded) {
      if (!merge || r.absorbed.count(e) || nodes_[e].chain == 0) continue;
      std::set<uint32_t> members{e};
      std::vector<Lit> operands;
      bool negated = false;
      std::vector<Lit> stack(nodes_[e].args.begin(), nodes_[e].args.end());
      while (!stack.empty()) {
        const Lit a = stack.back();
        stack.pop_back();
        if (r.absorbed.count(node_of(a))) {
          members.insert(node_of(a));
          negated ^= is_compl(a);
          for (Lit b : nodes_[node_of(a)].args) stack.push_back(b);
        } else {
          operands.push_back(a);
        }
      }
      std::map<uint32_t, int> count;
      for (Lit a : operands) ++count[node_of(a)];
      std::vector<Lit> exclusive, rest;
      for (Lit a : operands) {
        const uint32_t k = node_of(a);
        bool only_here = r.cand.count(k) && konst_[k] < 0 && count[k] == 1;
        for (const auto& [p, unused] : parents[k]) only_here &= members.count(p) > 0;
        (only_here ? exclusive : rest).push_back(a);
      }
      if (exclusive.size() >= 2) {
        r.merged[e] = exclusive;
        for (Lit a : exclusive) merged_away.insert(node_of(a));
      } else {
        rest = operands;
      }
      r.rest[e] = rest;
      r.negated[e] = negated;
    }
    for (uint32_t c : r.cand)
      if (!merged_away.count(c) && konst_[c] < 0) r.leaves.push_back(c);
    for (uint32_t c : r.leaves) r.leaf_supp.emplace_back(supp(c), supp(c) + words_);
    for (const auto& [e, lits] : r.merged) {
      std::vector<uint64_t> m(words_, 0);
      for (Lit a : lits)
        for (size_t w = 0; w < words_; ++w) m[w] |= supp(node_of(a))[w];
      r.leaf_supp.push_back(std::move(m));
    }
    return r;
  }

  static uint64_t apply_chain(int chain, uint64_t a, uint64_t b) {
    switch (chain) {
      case 1:
        return a & b;
      case 2:
        return a | b;
      case 3:
        return a ^ b;
      default:
        return ~(a ^ b);
    }
  }

  using Values = std::unordered_map<uint32_t, std::vector<uint64_t>>;

  // Each top's truth table over the region's leaves (with the tables of the
  // values below it). Without merged leaves, every value's table over the
  // same leaves is the same in any check, so it's kept for the next check
  // with those leaves: in a dense operation, most statements' checks have
  // every input below them as their leaves.
  const Values& evaluate(const Region& r, size_t& words) {
    const uint32_t L = static_cast<uint32_t>(r.leaf_count());
    words = L <= 6 ? 1 : (size_t{1} << (L - 6));
    if (!r.merged.empty()) {
      scratch_ = evaluate_merged(r, words);
      return scratch_;
    }
    if (kept_words_ > kKeptWords) {
      kept_.clear();
      kept_words_ = 0;
    }
    Values& value = kept_[r.leaves];
    auto add = [&](uint32_t x, std::vector<uint64_t> row) {
      kept_words_ += row.size();
      value.emplace(x, std::move(row));
    };
    if (value.empty()) {
      uint32_t j = 0;
      for (uint32_t c : r.leaves) add(c, variable(j++, words));
      add(0, std::vector<uint64_t>(words, 0));
    }
    for (uint32_t c : r.cand)
      if (konst_[c] >= 0 && !value.count(c)) add(c, std::vector<uint64_t>(words, konst_[c] ? ~0ULL : 0));
    Word word = [&](Lit a, size_t w) { return value.at(node_of(a))[w] ^ (is_compl(a) ? ~0ULL : 0); };
    for (uint32_t e : r.expanded) {
      if (value.count(e)) continue;
      std::vector<uint64_t> row(words, 0);
      const SplitNode& node = nodes_[e];
      if (node.chain == 0) {
        eval_(e, node.args, words, word, row.data());
      } else {
        for (size_t w = 0; w < words; ++w) row[w] = apply_chain(node.chain, word(node.args[0], w), word(node.args[1], w));
      }
      add(e, std::move(row));
    }
    return value;
  }

  static std::vector<uint64_t> variable(uint32_t j, size_t words) {
    static const uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                     0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
    std::vector<uint64_t> row(words);
    for (size_t w = 0; w < words; ++w) row[w] = j < 6 ? kVar[j] : (((w >> (j - 6)) & 1) ? ~0ULL : 0);
    return row;
  }

  Values evaluate_merged(const Region& r, size_t words) const {
    Values value;
    auto var = [&](uint32_t j) { return variable(j, words); };
    uint32_t j = 0;
    for (uint32_t c : r.leaves) value[c] = var(j++);
    std::map<uint32_t, std::vector<uint64_t>> merged_value;
    for (const auto& [e, lits] : r.merged) merged_value[e] = var(j++);
    for (uint32_t c : r.cand)
      if (konst_[c] >= 0) value[c] = std::vector<uint64_t>(words, konst_[c] ? ~0ULL : 0);
    if (!value.count(0)) value[0] = std::vector<uint64_t>(words, 0);
    Word word = [&](Lit a, size_t w) { return value.at(node_of(a))[w] ^ (is_compl(a) ? ~0ULL : 0); };
    for (uint32_t e : r.expanded) {
      if (r.absorbed.count(e)) continue;
      std::vector<uint64_t> row(words, 0);
      const SplitNode& node = nodes_[e];
      if (node.chain == 0) {
        eval_(e, node.args, words, word, row.data());
      } else {
        const std::vector<Lit>& rest = r.rest.at(e);
        auto m = merged_value.find(e);
        for (size_t w = 0; w < words; ++w) {
          bool first = true;
          uint64_t acc = 0;
          auto add = [&](uint64_t x) {
            acc = first ? x : apply_chain(node.chain, acc, x);
            first = false;
          };
          for (Lit a : rest) add(word(a, w));
          if (m != merged_value.end()) add(m->second[w]);
          row[w] = r.negated.at(e) ? ~acc : acc;
        }
      }
      value[e] = std::move(row);
    }
    return value;
  }

  // A read-once value of `and`s and `not`s, as a phase and a hash: `and`
  // is the opposite of `or` of the opposites, and an `or` of `or`s is one
  // `or` whose hash adds up its operands' in any order.
  const Canon& canon(uint32_t x) {
    auto it = canon_.find(x);
    if (it != canon_.end()) return it->second;
    Canon c;
    if (x <= inputs_) {
      c.hash = mix64(0x5157ULL + x);
    } else {
      c.phase = 1;
      c.is_or = true;
      for (Lit a : nodes_[x].args) {
        const Canon& k = canon(node_of(a));
        const int p = k.phase ^ static_cast<int>(is_compl(a)) ^ 1;
        c.sum += (p == 0 && k.is_or) ? k.sum : mix64(k.hash ^ (p ? 0x9E3779B97F4A7C15ULL : 0));
      }
      c.hash = mix64(c.sum ^ 0x0123ULL);
    }
    return canon_[x] = c;
  }

  void group_values() {
    const size_t n = nodes_.size();
    keys.assign(n, 0);
    const uint64_t constant_key = mix64(0xC0157A47ULL) & ~1ULL;
    std::map<std::vector<uint64_t>, std::vector<uint32_t>> by_supp;
    for (uint32_t x = 0; x < n; ++x) {
      if (konst_[x] >= 0) {
        keys[x] = constant_key | static_cast<uint64_t>(konst_[x]);
        continue;
      }
      by_supp[std::vector<uint64_t>(supp(x), supp(x) + words_)].push_back(x);
    }
    uint64_t group_id = 0;
    for (const auto& [s, members] : by_supp) {
      ++group_id;
      if (members.size() == 1) {
        keys[members[0]] = mix64(0xD15ULL + 2 * members[0]) & ~1ULL;
        continue;
      }
      ++groups;
      std::vector<uint32_t> statements;
      bool all_read_once = true;
      for (uint32_t m : members) {
        if (m > inputs_) statements.push_back(m);
        all_read_once &= read_once_[m] != 0 && (m <= inputs_ || nodes_[m].is_and);
      }
      Region r = region(statements);
      groups_max_leaves = std::max(groups_max_leaves, r.leaf_count());
      if (!within(r) && all_read_once) {
        ++groups_fixed_form;
        for (uint32_t m : members) {
          const Canon& c = canon(m);
          keys[m] = (mix64(group_id * 0x100000001B3ULL ^ c.hash) & ~1ULL) | static_cast<uint64_t>(c.phase);
        }
        continue;
      }
      if (!within(r)) {
        over_limits = true;
        over_reason = "group of " + std::to_string(members.size()) + " values over " +
                      std::to_string(r.leaf_count()) + " leaves, " + std::to_string(r.expanded.size()) +
                      " statements";
        return;
      }
      size_t words = 1;
      const Values& value = evaluate(r, words);
      const uint64_t valid = valid_bits(static_cast<uint32_t>(r.leaf_count()));
      for (uint32_t m : members) {
        // An input in a group is its group's one input, the one leaf.
        const std::vector<uint64_t>& t = value.at(m);
        const uint64_t phase = t[0] & 1;
        uint64_t h = mix64(0x77 ^ group_id);
        for (uint64_t w : t) h = mix64(h ^ ((w ^ (phase ? ~0ULL : 0)) & valid));
        keys[m] = (h & ~1ULL) | phase;
      }
    }
  }
};

}  // namespace beq
