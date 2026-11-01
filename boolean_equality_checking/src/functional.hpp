// Exact methods that compute every node's whole function: truth tables over
// all inputs, and OBDDs.
#pragma once

#include <cstring>
#include <unordered_map>
#include <vector>

#include "aig.hpp"
#include "bdd.hpp"
#include "structural.hpp"

namespace beq {

// Truth tables over every input. A node's table is freed after its last user
// unless it is the first node of its class, which later nodes compare against.
inline Classes run_truth_tables(const Aig& g, uint32_t max_inputs, Stats& stats) {
  const uint32_t n = g.num_nodes();
  const uint32_t num_in = g.num_inputs;
  if (num_in > max_inputs) throw std::runtime_error("too many inputs for truth tables");
  const size_t words = num_in <= 6 ? 1 : (size_t{1} << (num_in - 6));
  const uint64_t last_mask = num_in >= 6 ? ~0ULL : ((1ULL << (1u << num_in)) - 1);
  Classes classes(n);
  std::vector<uint32_t> users = fanout_counts(g);
  std::vector<uint64_t*> table(n, nullptr);
  std::vector<char> keep(n, 0);
  std::vector<std::vector<uint64_t>> storage_free;
  size_t live_bytes = 0, peak_bytes = 0;
  auto alloc = [&]() {
    live_bytes += words * 8;
    peak_bytes = std::max(peak_bytes, live_bytes);
    return new uint64_t[words];
  };
  auto release = [&](uint32_t v) {
    if (table[v] && !keep[v]) {
      delete[] table[v];
      table[v] = nullptr;
      live_bytes -= words * 8;
    }
  };
  // Normalized hash -> first nodes of classes with that hash.
  std::unordered_map<uint64_t, std::vector<uint32_t>> buckets;
  auto lookup_or_add = [&](uint32_t v) {
    const uint64_t* t = table[v];
    bool phase = t[0] & 1;
    uint64_t flip = phase ? ~0ULL : 0;
    uint64_t h = 0x9e37;
    for (size_t w = 0; w < words; ++w) h = mix64(h ^ ((t[w] ^ flip) & (w + 1 == words ? last_mask : ~0ULL)));
    std::vector<uint32_t>& bucket = buckets[h];
    for (uint32_t r : bucket) {
      const uint64_t* tr = table[r];
      uint64_t flip_r = (tr[0] & 1) ? ~0ULL : 0;
      bool same = true;
      for (size_t w = 0; w < words && same; ++w) {
        uint64_t mask = w + 1 == words ? last_mask : ~0ULL;
        same = ((t[w] ^ flip) & mask) == ((tr[w] ^ flip_r) & mask);
      }
      if (same) {
        classes.merge(v, r, phase ^ static_cast<bool>(tr[0] & 1));
        return;
      }
    }
    bucket.push_back(v);
    keep[v] = 1;
  };
  table[0] = alloc();
  std::memset(table[0], 0, words * 8);
  lookup_or_add(0);
  for (uint32_t i = 1; i <= num_in; ++i) {
    uint64_t* t = table[i] = alloc();
    uint32_t bit = i - 1;
    for (size_t w = 0; w < words; ++w) {
      if (bit < 6) {
        static const uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                         0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
        t[w] = kVar[bit];
      } else {
        t[w] = ((w >> (bit - 6)) & 1) ? ~0ULL : 0;
      }
    }
    lookup_or_add(i);
  }
  for (uint32_t v = num_in + 1; v < n; ++v) {
    uint64_t* t = table[v] = alloc();
    const uint64_t* a = table[node_of(g.fanin0[v])];
    const uint64_t* b = table[node_of(g.fanin1[v])];
    uint64_t fa = is_compl(g.fanin0[v]) ? ~0ULL : 0, fb = is_compl(g.fanin1[v]) ? ~0ULL : 0;
    for (size_t w = 0; w < words; ++w) t[w] = (a[w] ^ fa) & (b[w] ^ fb);
    for (Lit f : {g.fanin0[v], g.fanin1[v]})
      if (--users[node_of(f)] == 0 && node_of(f) > num_in) release(node_of(f));
    lookup_or_add(v);
    if (users[v] == 0) release(v);
  }
  stats.emplace_back("table_words", static_cast<double>(words));
  stats.emplace_back("peak_table_bytes", static_cast<double>(peak_bytes));
  for (uint32_t v = 0; v < n; ++v)
    if (table[v]) delete[] table[v];
  return classes;
}

// OBDDs for every node, with the given input order (order[k] is the input at
// level k). Throws BddLimit past node_limit nodes.
inline Classes run_bdd(const Aig& g, const std::vector<uint32_t>& order, size_t node_limit, Stats& stats) {
  const uint32_t n = g.num_nodes();
  Classes classes(n);
  Bdd bdd(g.num_inputs, node_limit);
  std::vector<Bdd::Edge> edge(n);
  edge[0] = Bdd::kFalse;
  for (uint32_t k = 0; k < order.size(); ++k) edge[order[k]] = bdd.var(k);
  for (uint32_t v = g.num_inputs + 1; v < n; ++v) {
    Bdd::Edge a = edge[node_of(g.fanin0[v])] ^ is_compl(g.fanin0[v]);
    Bdd::Edge b = edge[node_of(g.fanin1[v])] ^ is_compl(g.fanin1[v]);
    edge[v] = bdd.land(a, b);
  }
  // Complement edges make equality modulo complement a node comparison. The
  // false constant is edge 1, so it is node 0 with the complement bit set.
  std::unordered_map<uint32_t, std::pair<uint32_t, bool>> first;
  for (uint32_t v = 0; v < n; ++v) {
    uint32_t node = edge[v] >> 1;
    bool c = edge[v] & 1;
    // Node 0 is false, which is edge 1; normalize so its phase is 0.
    auto [it, inserted] = first.try_emplace(node, std::make_pair(v, c));
    if (!inserted) classes.merge(v, it->second.first, c ^ it->second.second);
  }
  std::vector<uint32_t> counts = bdd.reachable_level_counts(edge);
  uint32_t widest = 0;
  double shared = 0;
  for (uint32_t k = 0; k < g.num_inputs; ++k) {
    widest = std::max(widest, counts[k]);
    shared += counts[k];
  }
  stats.emplace_back("bdd_nodes_created", static_cast<double>(bdd.num_nodes()));
  stats.emplace_back("bdd_shared_size", shared);
  stats.emplace_back("bdd_widest_level", static_cast<double>(widest));
  stats.emplace_back("bdd_bytes", static_cast<double>(bdd.memory_bytes()));
  return classes;
}

}  // namespace beq
