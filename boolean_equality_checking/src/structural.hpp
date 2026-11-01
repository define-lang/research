// Methods that only look at structure: structural hashing, the normalized
// AND-of-literal-sets form, and DLP 57's cuts of at most four values.
#pragma once

#include <algorithm>
#include <array>
#include <map>
#include <unordered_map>
#include <string>
#include <vector>

#include "aig.hpp"
#include "hashmap.hpp"

namespace beq {

using Stats = std::vector<std::pair<std::string, double>>;

// Applies the rules every method uses for a two-input `and` of literals that
// already stand for their classes. Returns UINT32_MAX when no rule applies.
inline Lit trivial_and(Lit a, Lit b) {
  if (a == 0 || b == 0 || a == (b ^ 1)) return 0;
  if (a == 1) return b;
  if (b == 1 || a == b) return a;
  return UINT32_MAX;
}

inline Classes run_strash(const Aig& g, Stats& stats) {
  Classes classes(g.num_nodes());
  std::vector<Lit> map(g.num_nodes());
  for (uint32_t n = 0; n <= g.num_inputs; ++n) map[n] = make_lit(n);
  U64Map table(g.num_nodes());
  for (uint32_t n = g.num_inputs + 1; n < g.num_nodes(); ++n) {
    Lit a = map[node_of(g.fanin0[n])] ^ is_compl(g.fanin0[n]);
    Lit b = map[node_of(g.fanin1[n])] ^ is_compl(g.fanin1[n]);
    Lit r = trivial_and(a, b);
    if (r == UINT32_MAX) {
      if (a > b) std::swap(a, b);
      auto [slot, inserted] = table.insert((static_cast<uint64_t>(a) << 32) | b, n);
      r = make_lit(*slot);
    }
    map[n] = r;
    if (node_of(r) != n) classes.merge(n, node_of(r), is_compl(r));
  }
  stats.emplace_back("table_bytes", static_cast<double>(table.memory_bytes()));
  return classes;
}

// Each `and` becomes an `and` of a sorted set of literals. Non-inverted `and`
// inputs are flattened into the set when flatten_all is set, or otherwise only
// when the input has exactly one user.
inline Classes run_normalize(const Aig& g, bool flatten_all, size_t literal_budget, Stats& stats) {
  const uint32_t n = g.num_nodes();
  Classes classes(n);
  std::vector<uint32_t> fanout = fanout_counts(g);
  std::vector<Lit> map(n);
  for (uint32_t v = 0; v <= g.num_inputs; ++v) map[v] = make_lit(v);
  // Set of each node that is the representative of its set, as a slice of
  // `pool`. Nodes whose set is a single literal or a constant have no slice.
  std::vector<uint64_t> begin(n, 0), end(n, 0);
  std::vector<Lit> pool;
  std::vector<Lit> scratch;
  // Hash of a set to the list of nodes with that hash.
  std::unordered_map<uint64_t, std::vector<uint32_t>> table;
  size_t max_set = 0;
  for (uint32_t v = g.num_inputs + 1; v < n; ++v) {
    scratch.clear();
    bool is_false = false;
    for (Lit f : {g.fanin0[v], g.fanin1[v]}) {
      Lit m = map[node_of(f)] ^ is_compl(f);
      uint32_t u = node_of(m);
      if (m == 1) continue;
      if (m == 0) {
        is_false = true;
        break;
      }
      bool flatten = !is_compl(m) && g.is_and(u) && end[u] > begin[u] &&
                     (flatten_all || fanout[node_of(f)] == 1);
      if (flatten)
        scratch.insert(scratch.end(), pool.begin() + static_cast<long>(begin[u]), pool.begin() + static_cast<long>(end[u]));
      else
        scratch.push_back(m);
    }
    Lit result;
    if (is_false) {
      result = 0;
    } else {
      std::sort(scratch.begin(), scratch.end());
      scratch.erase(std::unique(scratch.begin(), scratch.end()), scratch.end());
      bool contradiction = false;
      for (size_t i = 1; i < scratch.size(); ++i)
        if (scratch[i] == (scratch[i - 1] ^ 1)) contradiction = true;
      if (contradiction) {
        result = 0;
      } else if (scratch.empty()) {
        result = 1;
      } else if (scratch.size() == 1) {
        result = scratch[0];
      } else {
        uint64_t h = 0x1234567;
        for (Lit l : scratch) h = mix64(h ^ l);
        std::vector<uint32_t>& bucket = table[h];
        result = UINT32_MAX;
        for (uint32_t u : bucket) {
          if (end[u] - begin[u] == scratch.size() &&
              std::equal(scratch.begin(), scratch.end(), pool.begin() + static_cast<long>(begin[u]))) {
            result = make_lit(u);
            break;
          }
        }
        if (result == UINT32_MAX) {
          bucket.push_back(v);
          begin[v] = pool.size();
          pool.insert(pool.end(), scratch.begin(), scratch.end());
          end[v] = pool.size();
          max_set = std::max(max_set, scratch.size());
          result = make_lit(v);
          if (pool.size() > literal_budget) throw std::runtime_error("normalized form exceeded literal budget");
        }
      }
    }
    map[v] = result;
    if (node_of(result) != v) classes.merge(v, node_of(result), is_compl(result));
  }
  stats.emplace_back("pool_literals", static_cast<double>(pool.size()));
  stats.emplace_back("max_set", static_cast<double>(max_set));
  return classes;
}

// DLP 57's cuts: every union of one cut of each input with at most four values,
// plus the cut holding only the node. A node is redundant if, over one of its
// cuts, it is constant, equals one of the cut's values, or equals an earlier
// node over the same cut.
struct Cut {
  uint32_t leaves[4];
  uint8_t size;
  uint16_t tt;
};

inline uint16_t expand_tt(const Cut& sub, const Cut& merged) {
  // position of each sub leaf in the merged cut
  int pos[4];
  for (int i = 0; i < sub.size; ++i)
    for (int j = 0; j < merged.size; ++j)
      if (merged.leaves[j] == sub.leaves[i]) pos[i] = j;
  uint16_t out = 0;
  for (int m = 0; m < 16; ++m) {
    int idx = 0;
    for (int i = 0; i < sub.size; ++i) idx |= ((m >> pos[i]) & 1) << i;
    if ((sub.tt >> idx) & 1) out |= static_cast<uint16_t>(1u << m);
  }
  return out;
}

inline uint16_t full_mask(int size) { return size >= 4 ? 0xffff : static_cast<uint16_t>((1u << (1u << size)) - 1); }

inline Classes run_cuts4(const Aig& g, size_t cut_budget, Stats& stats) {
  const uint32_t n = g.num_nodes();
  Classes classes(n);
  std::vector<std::vector<Cut>> cuts(n);
  static const uint16_t kProj[4] = {0xAAAA, 0xCCCC, 0xF0F0, 0xFF00};
  for (uint32_t v = 1; v <= g.num_inputs; ++v) cuts[v].push_back(Cut{{v, 0, 0, 0}, 1, 0x2});
  // (leaves, normalized table) -> earliest node with that function of them.
  std::map<std::pair<std::array<uint32_t, 5>, uint16_t>, std::pair<uint32_t, bool>> seen;
  size_t total = 0, max_cuts = 0;
  for (uint32_t v = g.num_inputs + 1; v < n; ++v) {
    std::vector<Cut>& out = cuts[v];
    const uint32_t c0 = node_of(g.fanin0[v]), c1 = node_of(g.fanin1[v]);
    const bool p0 = is_compl(g.fanin0[v]), p1 = is_compl(g.fanin1[v]);
    for (const Cut& a : cuts[c0]) {
      for (const Cut& b : cuts[c1]) {
        Cut m{};
        uint32_t tmp[8];
        int k = 0;
        std::merge(a.leaves, a.leaves + a.size, b.leaves, b.leaves + b.size, tmp);
        int total_in = a.size + b.size;
        for (int i = 0; i < total_in; ++i)
          if (k == 0 || tmp[k - 1] != tmp[i]) tmp[k++] = tmp[i];
        if (k > 4) continue;
        for (int i = 0; i < k; ++i) m.leaves[i] = tmp[i];
        m.size = static_cast<uint8_t>(k);
        bool duplicate = false;
        for (const Cut& c : out)
          if (c.size == m.size && std::equal(c.leaves, c.leaves + c.size, m.leaves)) duplicate = true;
        if (duplicate) continue;
        uint16_t ta = expand_tt(a, m), tb = expand_tt(b, m);
        uint16_t mask = full_mask(k);
        if (p0) ta = static_cast<uint16_t>(~ta & mask);
        if (p1) tb = static_cast<uint16_t>(~tb & mask);
        m.tt = static_cast<uint16_t>(ta & tb & mask);
        out.push_back(m);
      }
    }
    for (const Cut& c : out) {
      uint16_t mask = full_mask(c.size);
      bool phase = c.tt & 1;
      uint16_t t = phase ? static_cast<uint16_t>(~c.tt & mask) : c.tt;
      if (t == 0) {
        classes.merge(v, 0, phase);
        continue;
      }
      bool is_leaf = false;
      for (int i = 0; i < c.size; ++i) {
        if (t == (kProj[i] & mask)) {
          classes.merge(v, c.leaves[i], phase);
          is_leaf = true;
        }
      }
      if (is_leaf) continue;
      std::array<uint32_t, 5> key{c.leaves[0], c.leaves[1], c.leaves[2], c.leaves[3], c.size};
      auto [it, inserted] = seen.try_emplace({key, t}, std::make_pair(v, phase));
      if (!inserted && it->second.first != v) classes.merge(v, it->second.first, phase ^ it->second.second);
    }
    // The cut holding only the node itself.
    out.push_back(Cut{{v, 0, 0, 0}, 1, 0x2});
    total += out.size();
    max_cuts = std::max(max_cuts, out.size());
    if (total > cut_budget) throw std::runtime_error("cut budget exceeded");
  }
  stats.emplace_back("total_cuts", static_cast<double>(total));
  stats.emplace_back("max_cuts", static_cast<double>(max_cuts));
  return classes;
}

}  // namespace beq
