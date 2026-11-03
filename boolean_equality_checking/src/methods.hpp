// Exact methods other than truth tables over every input, for
// `beq program --method M` (methods_experiment.py): truth tables in chunks
// of input assignments, OBDDs, and SAT sweeping. Each gives what the rules
// need of an operation's values: their classes up to complement (tt_keys'
// form), the read views the written view depends on, and, as a
// MatchOracle, the exact check of a match.
#pragma once

#include <algorithm>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "aig.hpp"
#include "bdd.hpp"
#include "match.hpp"
#include "sat.hpp"
#include "split.hpp"

namespace beq {

// An operation's boolean values: node 0 is the constant false, nodes 1 to
// inputs are the boolean inputs, and every later node is an `and` or an
// execution, by its function's truth table over its arguments.
struct MethodGraph {
  struct Node {
    std::vector<Lit> args;
    bool is_and = true;
    uint64_t table = 0;  // an execution of at most six views
  };
  uint32_t inputs = 0;
  std::vector<Node> nodes;  // node inputs + 1 + k is nodes[k]
  Lit out = 0;              // the written view
  uint32_t views = 0;       // boolean read views: inputs 1 to views

  uint32_t num_nodes() const { return inputs + 1 + static_cast<uint32_t>(nodes.size()); }
  const Node& node(uint32_t n) const { return nodes[n - inputs - 1]; }

  // A node's word from its arguments' words.
  static uint64_t word(const Node& node, const uint64_t* a) {
    if (node.is_and) return a[0] & a[1];
    uint64_t out = 0;
    const size_t k = node.args.size();
    for (uint32_t m = 0; m < (1u << k); ++m) {
      if (!((node.table >> m) & 1)) continue;
      uint64_t term = ~0ULL;
      for (size_t i = 0; i < k; ++i) term &= ((m >> i) & 1) ? a[i] : ~a[i];
      out |= term;
    }
    return out;
  }

  // Every node's value on one input assignment.
  std::vector<char> evaluate(uint64_t minterm) const {
    std::vector<char> v(num_nodes(), 0);
    for (uint32_t i = 1; i <= inputs; ++i) v[i] = static_cast<char>((minterm >> (i - 1)) & 1);
    uint64_t a[8];
    for (uint32_t n = inputs + 1; n < num_nodes(); ++n) {
      const Node& x = node(n);
      for (size_t i = 0; i < x.args.size(); ++i) a[i] = (v[node_of(x.args[i])] ^ is_compl(x.args[i])) ? ~0ULL : 0;
      v[n] = static_cast<char>(word(x, a) & 1);
    }
    return v;
  }

  // The nodes the given literals depend on, in node order.
  std::vector<uint32_t> cone(const std::vector<Lit>& roots) const {
    std::vector<char> in(num_nodes(), 0);
    std::vector<uint32_t> stack;
    for (Lit r : roots) stack.push_back(node_of(r));
    while (!stack.empty()) {
      const uint32_t n = stack.back();
      stack.pop_back();
      if (in[n]) continue;
      in[n] = 1;
      if (n > inputs)
        for (Lit a : node(n).args) stack.push_back(node_of(a));
    }
    std::vector<uint32_t> out;
    for (uint32_t n = 0; n < num_nodes(); ++n)
      if (in[n]) out.push_back(n);
    return out;
  }
};

// R of the arguments' words, and whether each argument matters there: R's
// value differs with that argument flipped.
inline uint64_t registered_word(const Registered& r, const uint64_t* a) {
  uint64_t out = 0;
  for (uint32_t m = 0; m < (1u << r.arity); ++m) {
    if (!((r.table >> m) & 1)) continue;
    uint64_t term = ~0ULL;
    for (uint32_t i = 0; i < r.arity; ++i) term &= ((m >> i) & 1) ? a[i] : ~a[i];
    out |= term;
  }
  return out;
}

inline uint64_t matters_word(const Registered& r, const uint64_t* a, uint32_t i) {
  uint64_t diff = 0;
  for (uint32_t m = 0; m < (1u << r.arity); ++m) {
    if ((m >> i) & 1) continue;
    if (((r.table >> m) & 1) == ((r.table >> (m | (1u << i))) & 1)) continue;
    uint64_t term = ~0ULL;
    for (uint32_t h = 0; h < r.arity; ++h)
      if (h != i) term &= ((m >> h) & 1) ? a[h] : ~a[h];
    diff |= term;
  }
  return diff;
}

// What every method shares: values on sampled input assignments for the
// search, and function ids from the classes.
class MethodBase : public MatchOracle {
 public:
  explicit MethodBase(const MethodGraph& g) : g_(g) {}
  std::vector<uint64_t> keys;      // tt_keys' form, by node
  std::vector<int> unused_views;   // from 1
  uint64_t undecided = 0;          // exact checks a method couldn't decide
  virtual void run() = 0;          // the classes
  virtual void find_unused() = 0;  // the read views that don't matter

  uint64_t function_id(Lit l) override {
    const uint64_t k = keys[node_of(l)];
    return ((k >> 1) << 1 | ((k & 1) ^ static_cast<uint64_t>(is_compl(l)))) * 0x9E3779B97F4A7C15ULL;
  }
  bool bit(Lit l, uint64_t minterm) override {
    auto it = sampled_.find(minterm);
    if (it == sampled_.end()) it = sampled_.emplace(minterm, g_.evaluate(minterm)).first;
    return it->second[node_of(l)] ^ is_compl(l);
  }

 protected:
  const MethodGraph& g_;
  std::unordered_map<uint64_t, std::vector<char>> sampled_;
};

// Truth tables computed 2^C input assignments at a time, the inputs past C
// fixed per chunk: the same work as one table over every input, with
// memory for one chunk of every value, plus a hash per chunk of the written
// view (for the read views past C).
class ChunkMethod : public MethodBase {
 public:
  ChunkMethod(const MethodGraph& g, uint32_t chunk_inputs) : MethodBase(g) {
    c_ = std::min(g.inputs, chunk_inputs);
    words_ = c_ <= 6 ? 1 : (size_t{1} << (c_ - 6));
    chunks_ = uint64_t{1} << (g.inputs - c_);
  }

  // The read views come out of the same pass over the chunks.
  void run() override {
    const uint32_t n = g_.num_nodes();
    std::vector<uint64_t> h(n, 0x77), phase(n, 0);
    std::vector<uint64_t> out_hash(chunks_);
    std::vector<char>& matters = matters_;
    matters.assign(g_.views + 1, 0);
    std::vector<uint32_t> all(n);
    std::iota(all.begin(), all.end(), 0);
    const uint64_t valid = c_ >= 6 ? ~0ULL : ((1ULL << (1u << c_)) - 1);
    for (uint64_t c = 0; c < chunks_; ++c) {
      evaluate_chunk(c, all);
      for (uint32_t x = 0; x < n; ++x) {
        const uint64_t* row = &t_[size_t{x} * words_];
        if (c == 0) phase[x] = row[0] & 1;
        const uint64_t f = phase[x] ? ~0ULL : 0;
        for (size_t w = 0; w < words_; ++w) h[x] = mix64(h[x] ^ ((row[w] ^ f) & valid));
      }
      const Lit o = g_.out;
      uint64_t oh = 0x55;
      std::vector<uint64_t> orow(words_);
      for (size_t w = 0; w < words_; ++w) {
        orow[w] = (t_[size_t{node_of(o)} * words_ + w] ^ (is_compl(o) ? ~0ULL : 0)) & valid;
        oh = mix64(oh ^ orow[w]);
      }
      out_hash[c] = oh;
      for (uint32_t i = 1; i <= std::min(g_.views, c_); ++i) {
        if (matters[i]) continue;
        const uint32_t bit = i - 1;
        if (bit < 6) {
          for (size_t w = 0; w < words_ && !matters[i]; ++w)
            matters[i] = ((orow[w] ^ (orow[w] >> (1 << bit))) & ~kVar[bit] & valid) != 0;
        } else {
          const size_t b = size_t{1} << (bit - 6);
          for (size_t w = 0; w < words_ && !matters[i]; ++w) matters[i] = !(w & b) && orow[w] != orow[w | b];
        }
      }
    }
    for (uint32_t i = c_ + 1; i <= g_.views; ++i) {
      const uint64_t b = uint64_t{1} << (i - 1 - c_);
      for (uint64_t c = 0; c < chunks_ && !matters[i]; ++c) matters[i] = !(c & b) && out_hash[c] != out_hash[c | b];
    }
    keys.assign(n, 0);
    for (uint32_t x = 0; x < n; ++x) keys[x] = (h[x] & ~1ULL) | phase[x];
  }

  void find_unused() override {
    for (uint32_t i = 1; i <= g_.views; ++i)
      if (!matters_[i]) unused_views.push_back(static_cast<int>(i));
  }

  bool holds(Lit target, const Registered& r, const std::vector<Lit>& args, bool& differs,
             uint64_t& difference) override {
    std::vector<Lit> roots = args;
    roots.push_back(target);
    const std::vector<uint32_t> cone = g_.cone(roots);
    const uint64_t valid = c_ >= 6 ? ~0ULL : ((1ULL << (1u << c_)) - 1);
    std::vector<char> matters(r.arity, 0);
    uint64_t a[8];
    for (uint64_t c = 0; c < chunks_; ++c) {
      evaluate_chunk(c, cone);
      for (size_t w = 0; w < words_; ++w) {
        for (uint32_t i = 0; i < r.arity; ++i) a[i] = word(args[i], w);
        const uint64_t diff = (registered_word(r, a) ^ word(target, w)) & valid;
        if (diff) {
          differs = true;
          difference = (c << c_) | (w * 64 + static_cast<uint64_t>(__builtin_ctzll(diff)));
          return false;
        }
        for (uint32_t i = 0; i < r.arity; ++i)
          if (!matters[i]) matters[i] = (matters_word(r, a, i) & valid) != 0;
      }
    }
    return std::all_of(matters.begin(), matters.end(), [](char m) { return m != 0; });
  }

  size_t memory_words() const { return t_.size(); }

 private:
  static constexpr uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                       0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
  uint32_t c_ = 0;
  std::vector<char> matters_;
  size_t words_ = 1;
  uint64_t chunks_ = 1;
  std::vector<uint64_t> t_;

  uint64_t word(Lit l, size_t w) const { return t_[size_t{node_of(l)} * words_ + w] ^ (is_compl(l) ? ~0ULL : 0); }

  // The given nodes' rows for chunk c, in node order.
  void evaluate_chunk(uint64_t c, const std::vector<uint32_t>& nodes) {
    if (t_.empty()) t_.assign(size_t{g_.num_nodes()} * words_, 0);
    uint64_t a[8];
    for (uint32_t x : nodes) {
      uint64_t* row = &t_[size_t{x} * words_];
      if (x == 0) {
        std::fill(row, row + words_, 0);
      } else if (x <= g_.inputs) {
        const uint32_t bit = x - 1;
        for (size_t w = 0; w < words_; ++w)
          row[w] = bit < 6 ? kVar[bit]
                   : bit < c_ ? (((w >> (bit - 6)) & 1) ? ~0ULL : 0)
                              : (((c >> (bit - c_)) & 1) ? ~0ULL : 0);
      } else {
        const MethodGraph::Node& node = g_.node(x);
        for (size_t w = 0; w < words_; ++w) {
          for (size_t i = 0; i < node.args.size(); ++i) a[i] = word(node.args[i], w);
          row[w] = MethodGraph::word(node, a);
        }
      }
    }
  }
};

// OBDDs (bdd.hpp, complement edges) of every value, under one order of the
// inputs: "natural", "reverse", "dfs" (first reached from the written view,
// arguments in order), or "random".
class BddMethod : public MethodBase {
 public:
  BddMethod(const MethodGraph& g, const std::string& order, size_t node_limit)
      : MethodBase(g), bdd_(g.inputs, node_limit) {
    level_.resize(g.inputs + 1);
    std::vector<uint32_t> inputs;
    if (order == "dfs") {
      std::vector<char> seen(g.num_nodes(), 0);
      std::vector<uint32_t> stack{node_of(g.out)};
      while (!stack.empty()) {
        const uint32_t n = stack.back();
        stack.pop_back();
        if (seen[n]) continue;
        seen[n] = 1;
        if (n >= 1 && n <= g.inputs) inputs.push_back(n);
        if (n > g.inputs) {
          const auto& args = g.node(n).args;
          for (size_t i = args.size(); i-- > 0;) stack.push_back(node_of(args[i]));
        }
      }
      for (uint32_t i = 1; i <= g.inputs; ++i)
        if (!seen[i]) inputs.push_back(i);
    } else {
      for (uint32_t i = 1; i <= g.inputs; ++i) inputs.push_back(i);
      if (order == "reverse") std::reverse(inputs.begin(), inputs.end());
      if (order == "random") {
        Rng rng(11);
        for (size_t i = inputs.size(); i > 1; --i) std::swap(inputs[i - 1], inputs[rng.next() % i]);
      }
    }
    input_at_.assign(g.inputs, 0);
    for (uint32_t k = 0; k < inputs.size(); ++k) {
      level_[inputs[k]] = k;
      input_at_[k] = inputs[k];
    }
  }

  void run() override {
    const uint32_t n = g_.num_nodes();
    edge_.assign(n, Bdd::kFalse);
    for (uint32_t i = 1; i <= g_.inputs; ++i) edge_[i] = bdd_.var(level_[i]);
    for (uint32_t x = g_.inputs + 1; x < n; ++x) {
      const MethodGraph::Node& node = g_.node(x);
      std::vector<Bdd::Edge> a;
      for (Lit l : node.args) a.push_back(lit(l));
      edge_[x] = node.is_and ? bdd_.land(a[0], a[1]) : apply_table(node.table, a);
    }
    keys.assign(n, 0);
    for (uint32_t x = 0; x < n; ++x) keys[x] = mix64(edge_[x] >> 1) << 1 | (edge_[x] & 1);
  }

  void find_unused() override {
    const std::vector<char> in = support(lit(g_.out));
    for (uint32_t i = 1; i <= g_.views; ++i)
      if (!in[level_[i]]) unused_views.push_back(static_cast<int>(i));
  }

  bool holds(Lit target, const Registered& r, const std::vector<Lit>& args, bool& differs,
             uint64_t& difference) override {
    std::vector<Bdd::Edge> a;
    for (Lit l : args) a.push_back(lit(l));
    const Bdd::Edge rv = apply_table(r.table, a), t = lit(target);
    if (rv != t) {
      differs = true;
      difference = 0;
      bdd_.satisfying_path(lxor(rv, t), [&](uint32_t level, bool value) {
        if (value) difference |= uint64_t{1} << (input_at_[level] - 1);
      });
      return false;
    }
    for (uint32_t i = 0; i < r.arity; ++i) {
      std::vector<Bdd::Edge> lo = a, hi = a;
      lo[i] = Bdd::kFalse;
      hi[i] = Bdd::kTrue;
      if (apply_table(r.table, lo) == apply_table(r.table, hi)) return false;
    }
    return true;
  }

  size_t nodes() const { return bdd_.num_nodes(); }
  size_t memory_bytes() const { return bdd_.memory_bytes(); }
  // The written view's OBDD nodes: what an execution of the operation refers to.
  size_t out_nodes() {
    const std::vector<uint32_t> counts = bdd_.reachable_level_counts({lit(g_.out)});
    return std::accumulate(counts.begin(), counts.end(), size_t{0});
  }
  // The written view on one input assignment, walking its OBDD.
  bool evaluate_out(uint64_t minterm) const {
    Bdd::Edge e = edge_[node_of(g_.out)] ^ (is_compl(g_.out) ? 1u : 0u);
    while ((e >> 1) != 0) {
      const uint32_t n = e >> 1, c = e & 1;
      const bool v = (minterm >> (input_at_[bdd_.level_of(n)] - 1)) & 1;
      e = (v ? bdd_.high(n) : bdd_.low(n)) ^ c;
    }
    return e == Bdd::kTrue;
  }

 private:
  Bdd bdd_;
  std::vector<uint32_t> level_, input_at_;
  std::vector<Bdd::Edge> edge_;

  Bdd::Edge lit(Lit l) const { return edge_[node_of(l)] ^ (is_compl(l) ? 1u : 0u); }
  Bdd::Edge lor(Bdd::Edge a, Bdd::Edge b) { return bdd_.land(a ^ 1, b ^ 1) ^ 1; }
  Bdd::Edge lxor(Bdd::Edge a, Bdd::Edge b) { return lor(bdd_.land(a, b ^ 1), bdd_.land(a ^ 1, b)); }
  Bdd::Edge apply_table(uint64_t table, const std::vector<Bdd::Edge>& a) {
    Bdd::Edge out = Bdd::kFalse;
    for (uint32_t m = 0; m < (1u << a.size()); ++m) {
      if (!((table >> m) & 1)) continue;
      Bdd::Edge term = Bdd::kTrue;
      for (size_t i = 0; i < a.size(); ++i) term = bdd_.land(term, ((m >> i) & 1) ? a[i] : a[i] ^ 1);
      out = lor(out, term);
    }
    return out;
  }
  std::vector<char> support(Bdd::Edge e) const {
    std::vector<char> in(g_.inputs + 1, 0), seen(bdd_.num_nodes(), 0);
    std::vector<uint32_t> stack{e >> 1};
    while (!stack.empty()) {
      const uint32_t n = stack.back();
      stack.pop_back();
      if (n == 0 || seen[n]) continue;
      seen[n] = 1;
      in[bdd_.level_of(n)] = 1;
      stack.push_back(bdd_.low(n) >> 1);
      stack.push_back(bdd_.high(n) >> 1);
    }
    return in;
  }
};

// SAT sweeping: values grouped by their values on random input assignments
// (and every difference found since), then each candidate pair proved
// equal or shown different by the CDCL solver (sat.hpp), on one
// incremental encoding of the operation.
class SatMethod : public MethodBase {
 public:
  explicit SatMethod(const MethodGraph& g) : MethodBase(g) {
    const uint32_t n = g.num_nodes();
    for (uint32_t x = 0; x < n; ++x) var_.push_back(solver_.new_var());
    solver_.add_clause({sat::neg(var_[0])});
    for (uint32_t x = g.inputs + 1; x < n; ++x) encode(var_[x], g.node(x).is_and ? 0x8 : g.node(x).table, g.node(x).args);
    Rng rng(5);
    for (int k = 0; k < kRandomWords * 64; ++k) patterns_.push_back(rng.next() & mask());
  }

  void run() override {
    const uint32_t n = g_.num_nodes();
    sim_ = simulate(patterns_);
    const std::vector<std::vector<uint64_t>>& sim = sim_;
    keys.assign(n, 0);
    std::unordered_map<uint64_t, std::vector<uint32_t>> groups;
    for (uint32_t x = 0; x < n; ++x) {
      const uint64_t phase = sim[x][0] & 1;
      uint64_t h = 0x91;
      for (uint64_t w : sim[x]) h = mix64(h ^ (w ^ (phase ? ~0ULL : 0)));
      keys[x] = (mix64(x + 1) & ~1ULL) | phase;
      std::vector<uint32_t>& group = groups[h];
      for (uint32_t rep : group) {
        const bool flip = ((sim[x][0] ^ sim[rep][0]) & 1) != 0;
        bool separated = false;
        for (const std::vector<char>& values : fresh_) separated |= (values[x] != (values[rep] ^ flip));
        if (separated) continue;
        if (equal(sat::pos(var_[x]), sat::pos(var_[rep]) ^ (flip ? 1u : 0u))) {
          keys[x] = keys[rep] ^ (flip ? 1u : 0u);
          break;
        }
      }
      if (keys[x] == ((mix64(x + 1) & ~1ULL) | phase)) group.push_back(x);
    }
  }

  void find_unused() override {
    const std::vector<std::vector<uint64_t>>& sim = sim_;
    // A read view the written view depends on changes it on some sampled
    // assignment when flipped; the others need a proof.
    const Lit o = g_.out;
    for (uint32_t i = 1; i <= g_.views; ++i) {
      std::vector<uint64_t> flipped = patterns_;
      for (uint64_t& p : flipped) p ^= uint64_t{1} << (i - 1);
      const std::vector<std::vector<uint64_t>> s2 = simulate(flipped);
      bool matters = false;
      for (size_t w = 0; w < s2[0].size() && !matters; ++w) matters = s2[node_of(o)][w] != sim[node_of(o)][w];
      if (!matters) matters = view_matters(i);
      if (!matters) unused_views.push_back(static_cast<int>(i));
    }
  }

  bool holds(Lit target, const Registered& r, const std::vector<Lit>& args, bool& differs,
             uint64_t& difference) override {
    std::vector<sat::Lit> a;
    for (Lit l : args) a.push_back(slit(l));
    const uint32_t rv = solver_.new_var();
    encode_lits(rv, r.table, a);
    const sat::Lit t = slit(target);
    if (!equal(sat::pos(rv), t)) {
      differs = true;
      difference = last_model_;
      return false;
    }
    for (uint32_t i = 0; i < r.arity; ++i) {
      std::vector<sat::Lit> lo = a, hi = a;
      lo[i] = sat::pos(var_[0]);
      hi[i] = sat::neg(var_[0]);
      const uint32_t v0 = solver_.new_var(), v1 = solver_.new_var();
      encode_lits(v0, r.table, lo);
      encode_lits(v1, r.table, hi);
      if (equal(sat::pos(v0), sat::pos(v1))) return false;
    }
    return true;
  }

  uint64_t sat_calls = 0;

 private:
  static constexpr int kRandomWords = 16;
  sat::Solver solver_;
  std::vector<uint32_t> var_;
  std::vector<uint64_t> patterns_;
  std::vector<std::vector<char>> fresh_;
  std::vector<std::vector<uint64_t>> sim_;
  uint64_t last_model_ = 0;

  uint64_t mask() const { return g_.inputs >= 64 ? ~0ULL : ((uint64_t{1} << g_.inputs) - 1); }
  sat::Lit slit(Lit l) const { return sat::pos(var_[node_of(l)]) ^ (is_compl(l) ? 1u : 0u); }

  void encode(uint32_t v, uint64_t table, const std::vector<Lit>& args) {
    std::vector<sat::Lit> a;
    for (Lit l : args) a.push_back(slit(l));
    encode_lits(v, table, a);
  }
  // v = table(a): one clause per row.
  void encode_lits(uint32_t v, uint64_t table, const std::vector<sat::Lit>& a) {
    for (uint32_t m = 0; m < (1u << a.size()); ++m) {
      std::vector<sat::Lit> clause;
      for (size_t i = 0; i < a.size(); ++i) clause.push_back(((m >> i) & 1) ? (a[i] ^ 1) : a[i]);
      clause.push_back(((table >> m) & 1) ? sat::pos(v) : sat::neg(v));
      solver_.add_clause(clause);
    }
  }

  // Whether a and b are always equal; a difference is kept as a fresh
  // assignment and in last_model_.
  bool equal(sat::Lit a, sat::Lit b) {
    for (int side = 0; side < 2; ++side) {
      ++sat_calls;
      const std::vector<sat::Lit> assume = side == 0 ? std::vector<sat::Lit>{a, b ^ 1} : std::vector<sat::Lit>{a ^ 1, b};
      if (solver_.solve(assume, -1) == sat::Result::kSat) {
        last_model_ = 0;
        for (uint32_t i = 1; i <= g_.inputs; ++i)
          if (solver_.model_value(var_[i])) last_model_ |= uint64_t{1} << (i - 1);
        fresh_.push_back(g_.evaluate(last_model_));
        return false;
      }
    }
    return true;
  }

  // A second copy of the written view's cone with read view i negated.
  bool view_matters(uint32_t i) {
    const std::vector<uint32_t> cone = g_.cone({g_.out});
    std::unordered_map<uint32_t, sat::Lit> copy;
    for (uint32_t x : cone) {
      if (x <= g_.inputs) {
        copy[x] = x == i ? sat::neg(var_[x]) : sat::pos(var_[x]);
        continue;
      }
      std::vector<sat::Lit> a;
      for (Lit l : g_.node(x).args) a.push_back(copy.at(node_of(l)) ^ (is_compl(l) ? 1u : 0u));
      const uint32_t v = solver_.new_var();
      encode_lits(v, g_.node(x).is_and ? 0x8 : g_.node(x).table, a);
      copy[x] = sat::pos(v);
    }
    return !equal(slit(g_.out), copy.at(node_of(g_.out)) ^ (is_compl(g_.out) ? 1u : 0u));
  }

  std::vector<std::vector<uint64_t>> simulate(const std::vector<uint64_t>& patterns) const {
    const uint32_t n = g_.num_nodes();
    const size_t words = (patterns.size() + 63) / 64;
    std::vector<std::vector<uint64_t>> sim(n, std::vector<uint64_t>(words, 0));
    for (size_t k = 0; k < patterns.size(); ++k)
      for (uint32_t i = 1; i <= g_.inputs; ++i)
        if ((patterns[k] >> (i - 1)) & 1) sim[i][k / 64] |= 1ULL << (k % 64);
    uint64_t a[8];
    for (uint32_t x = g_.inputs + 1; x < n; ++x) {
      const MethodGraph::Node& node = g_.node(x);
      for (size_t w = 0; w < words; ++w) {
        for (size_t i = 0; i < node.args.size(); ++i)
          a[i] = sim[node_of(node.args[i])][w] ^ (is_compl(node.args[i]) ? ~0ULL : 0);
        sim[x][w] = MethodGraph::word(node, a);
      }
    }
    return sim;
  }
};

// The split check (split.hpp), with each match checked over the leaves of
// one check of the value and the arguments.
class SplitMethod : public MethodBase {
 public:
  SplitMethod(const MethodGraph& g, SplitCheck& sc) : MethodBase(g), sc_(sc) {
    keys = sc.keys;
  }

  // The split check itself ran before: SplitCheck::run.
  void run() override {}
  void find_unused() override {
    const uint32_t o = node_of(g_.out);
    for (uint32_t i = 1; i <= g_.views; ++i)
      if (sc_.constant(o) || !sc_.depends_on(o, i)) unused_views.push_back(static_cast<int>(i));
  }

  bool holds(Lit target, const Registered& r, const std::vector<Lit>& args, bool& differs,
             uint64_t& difference) override {
    (void)difference;
    std::vector<uint32_t> tops{node_of(target)};
    for (Lit a : args)
      if (std::find(tops.begin(), tops.end(), node_of(a)) == tops.end()) tops.push_back(node_of(a));
    size_t words = 1;
    uint32_t leaves = 0;
    const auto* t = sc_.tables_of(tops, words, leaves);
    if (!t) {
      ++undecided;
      return false;
    }
    const uint64_t valid = leaves >= 6 ? ~0ULL : ((1ULL << (1u << leaves)) - 1);
    auto word = [&](Lit l, size_t w) { return t->at(node_of(l))[w] ^ (is_compl(l) ? ~0ULL : 0); };
    std::vector<char> matters(r.arity, 0);
    uint64_t a[8];
    for (size_t w = 0; w < words; ++w) {
      for (uint32_t i = 0; i < r.arity; ++i) a[i] = word(args[i], w);
      // A difference over the leaves has no one input assignment to give
      // the search: the leaves are values.
      if ((registered_word(r, a) ^ word(target, w)) & valid) {
        differs = false;
        return false;
      }
      for (uint32_t i = 0; i < r.arity; ++i)
        if (!matters[i]) matters[i] = (matters_word(r, a, i) & valid) != 0;
    }
    return std::all_of(matters.begin(), matters.end(), [](char m) { return m != 0; });
  }

 private:
  SplitCheck& sc_;
};

}  // namespace beq
