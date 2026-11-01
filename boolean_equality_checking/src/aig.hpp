// And-Inverter Graph, AIGER reading, and the result format every method shares.
#pragma once

#include <sys/resource.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace beq {

// Literal = 2 * node + complement. Node 0 is constant false, nodes
// 1..num_inputs are inputs, and the rest are `and` nodes in topological order,
// which for the generated workloads is also the statement order.
using Lit = uint32_t;
inline uint32_t node_of(Lit l) { return l >> 1; }
inline bool is_compl(Lit l) { return l & 1; }
inline Lit make_lit(uint32_t n, bool c = false) { return 2 * n + (c ? 1 : 0); }

struct Aig {
  uint32_t num_inputs = 0;
  std::vector<Lit> fanin0, fanin1;  // indexed by node; unused for const/inputs
  std::vector<Lit> outputs;

  uint32_t num_nodes() const { return static_cast<uint32_t>(fanin0.size()); }
  bool is_and(uint32_t n) const { return n > num_inputs; }
  uint32_t num_ands() const { return num_nodes() - 1 - num_inputs; }
};

inline Aig read_aag(const std::string& path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open " + path);
  std::string magic;
  uint64_t m, i, l, o, a;
  in >> magic >> m >> i >> l >> o >> a;
  if (magic != "aag" || l != 0) throw std::runtime_error("expected combinational aag: " + path);
  Aig g;
  g.num_inputs = static_cast<uint32_t>(i);
  g.fanin0.assign(m + 1, 0);
  g.fanin1.assign(m + 1, 0);
  for (uint64_t k = 0; k < i; ++k) {
    uint64_t lit;
    in >> lit;
    if (lit != 2 * (k + 1)) throw std::runtime_error("inputs must be numbered 1..I");
  }
  for (uint64_t k = 0; k < o; ++k) {
    uint64_t lit;
    in >> lit;
    g.outputs.push_back(static_cast<Lit>(lit));
  }
  for (uint64_t k = 0; k < a; ++k) {
    uint64_t lhs, r0, r1;
    in >> lhs >> r0 >> r1;
    if (lhs != 2 * (i + 1 + k) || r0 >= lhs || r1 >= lhs)
      throw std::runtime_error("and nodes must be numbered in topological order");
    g.fanin0[lhs / 2] = static_cast<Lit>(r0);
    g.fanin1[lhs / 2] = static_cast<Lit>(r1);
  }
  return g;
}

inline void write_aig_binary(const Aig& g, const std::string& path) {
  // Binary AIGER requires lhs > rhs0 >= rhs1, so fanins are swapped as needed.
  std::ofstream out(path, std::ios::binary);
  out << "aig " << g.num_nodes() - 1 << " " << g.num_inputs << " 0 " << g.outputs.size() << " "
      << g.num_ands() << "\n";
  for (Lit lit : g.outputs) out << lit << "\n";
  auto put = [&](uint32_t x) {
    while (x & ~0x7fu) {
      out.put(static_cast<char>((x & 0x7f) | 0x80));
      x >>= 7;
    }
    out.put(static_cast<char>(x));
  };
  for (uint32_t n = g.num_inputs + 1; n < g.num_nodes(); ++n) {
    Lit lhs = make_lit(n);
    Lit r0 = std::max(g.fanin0[n], g.fanin1[n]);
    Lit r1 = std::min(g.fanin0[n], g.fanin1[n]);
    put(lhs - r0);
    put(r0 - r1);
  }
}

inline std::vector<uint32_t> fanout_counts(const Aig& g) {
  std::vector<uint32_t> fo(g.num_nodes(), 0);
  for (uint32_t n = g.num_inputs + 1; n < g.num_nodes(); ++n) {
    ++fo[node_of(g.fanin0[n])];
    ++fo[node_of(g.fanin1[n])];
  }
  for (Lit lit : g.outputs) ++fo[node_of(lit)];
  return fo;
}

// Live values along the node order: an input is live from its first use to its
// last use, and an `and` node from its definition to its last use. Returns the
// largest number live between two consecutive nodes.
inline uint32_t live_width(const Aig& g) {
  const uint32_t n = g.num_nodes();
  std::vector<uint32_t> first(n, UINT32_MAX), last(n, 0);
  for (uint32_t v = g.num_inputs + 1; v < n; ++v) {
    for (Lit f : {g.fanin0[v], g.fanin1[v]}) {
      uint32_t u = node_of(f);
      if (u == 0) continue;
      first[u] = std::min(first[u], v);
      last[u] = std::max(last[u], v);
    }
  }
  // delta[p] changes the live count for the cut just after node p.
  std::vector<int32_t> delta(n + 1, 0);
  for (uint32_t u = 1; u < n; ++u) {
    if (last[u] == 0) continue;
    uint32_t begin = g.is_and(u) ? u : first[u];
    // Live on cuts after positions begin..last-1. An input used only once is
    // read at its first use and never live across a cut.
    if (begin < last[u]) {
      delta[begin] += 1;
      delta[last[u]] -= 1;
    }
  }
  int32_t live = 0, best = 0;
  for (uint32_t p = 0; p < n; ++p) {
    live += delta[p];
    best = std::max(best, live);
  }
  return static_cast<uint32_t>(best);
}

// Inputs in the order of their first use by an `and` node; unused inputs last.
inline std::vector<uint32_t> first_use_order(const Aig& g) {
  std::vector<uint32_t> order;
  std::vector<char> seen(g.num_inputs + 1, 0);
  for (uint32_t v = g.num_inputs + 1; v < g.num_nodes(); ++v) {
    for (Lit f : {g.fanin0[v], g.fanin1[v]}) {
      uint32_t u = node_of(f);
      if (u >= 1 && u <= g.num_inputs && !seen[u]) {
        seen[u] = 1;
        order.push_back(u);
      }
    }
  }
  for (uint32_t u = 1; u <= g.num_inputs; ++u)
    if (!seen[u]) order.push_back(u);
  return order;
}

// Union-find over nodes with a phase bit, so a class can hold a node and the
// complement of another. Every method reports its findings through this.
class Classes {
 public:
  explicit Classes(uint32_t n) : parent_(n), phase_(n, 0) { std::iota(parent_.begin(), parent_.end(), 0); }

  // Records that node a equals node b xor phase.
  void merge(uint32_t a, uint32_t b, bool phase) {
    auto [ra, pa] = find(a);
    auto [rb, pb] = find(b);
    if (ra == rb) return;
    bool p = pa ^ pb ^ phase;
    if (ra < rb) std::swap(ra, rb);
    parent_[ra] = rb;
    phase_[ra] = p;
  }

  std::pair<uint32_t, bool> find(uint32_t a) {
    bool p = false;
    uint32_t r = a;
    while (parent_[r] != r) {
      p ^= phase_[r];
      r = parent_[r];
    }
    // Path compression with phase.
    bool q = p;
    uint32_t x = a;
    while (parent_[x] != x) {
      uint32_t next = parent_[x];
      bool px = phase_[x];
      parent_[x] = r;
      phase_[x] = q;
      q ^= px;
      x = next;
    }
    return {r, p};
  }

  // Representative literal: the smallest node in the class, with phase.
  Lit rep_lit(Lit l) {
    auto [r, p] = find(node_of(l));
    return make_lit(r, p ^ is_compl(l));
  }

 private:
  std::vector<uint32_t> parent_;
  std::vector<char> phase_;
};

inline double now_seconds() {
  using clock = std::chrono::steady_clock;
  return std::chrono::duration<double>(clock::now().time_since_epoch()).count();
}

inline long peak_rss_kb() {
  rusage usage{};
  getrusage(RUSAGE_SELF, &usage);
  return usage.ru_maxrss;
}

inline uint64_t mix64(uint64_t x) {
  x ^= x >> 33;
  x *= 0xff51afd7ed558ccdULL;
  x ^= x >> 33;
  x *= 0xc4ceb9fe1a85ec53ULL;
  x ^= x >> 33;
  return x;
}

// Deterministic generator so every run of a method is reproducible.
struct Rng {
  uint64_t s;
  explicit Rng(uint64_t seed) : s(seed * 0x9e3779b97f4a7c15ULL + 1) {}
  uint64_t next() {
    s += 0x9e3779b97f4a7c15ULL;
    return mix64(s);
  }
};

}  // namespace beq
