// Exact methods other than truth tables over every input, for
// `beq program --method M` (methods_experiment.py): truth tables in chunks
// of input assignments, OBDDs, and SAT sweeping. Each gives what the rules
// need of an operation's values: their classes up to complement (tt_keys'
// form), the read views the written view depends on, and, as a
// MatchOracle, the exact check of a match.
#pragma once

#include <algorithm>
#include <functional>
#include <map>
#include <memory>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "aig.hpp"
#include "bdd.hpp"
#include "diagram.hpp"
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
    // An execution of more views: its recorded table, or past twenty
    // inputs its recorded decision diagram.
    const std::vector<uint64_t>* big_table = nullptr;
    const RecordedDiagram* diagram = nullptr;
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
    if (node.big_table || node.diagram) {
      std::vector<char> at(node.diagram ? node.diagram->view_of_level.size() : 0);
      for (int b = 0; b < 64; ++b) {
        bool v = false;
        if (node.big_table) {
          uint64_t m = 0;
          for (size_t i = 0; i < k; ++i) m |= ((a[i] >> b) & 1) << i;
          v = ((*node.big_table)[m >> 6] >> (m & 63)) & 1;
        } else {
          for (size_t l = 0; l < at.size(); ++l) at[l] = static_cast<char>((a[node.diagram->view_of_level[l]] >> b) & 1);
          v = node.diagram->dd.evaluate(node.diagram->root, at);
        }
        out |= uint64_t{v} << b;
      }
      return out;
    }
    for (uint32_t m = 0; m < (1u << k); ++m) {
      if (!((node.table >> m) & 1)) continue;
      uint64_t term = ~0ULL;
      for (size_t i = 0; i < k; ++i) term &= ((m >> i) & 1) ? a[i] : ~a[i];
      out |= term;
    }
    return out;
  }

  // Every node's value on one input assignment.
  std::vector<char> evaluate(const Assignment& assign) const {
    std::vector<char> v(num_nodes(), 0);
    for (uint32_t i = 1; i <= inputs; ++i) v[i] = static_cast<char>(assign.get(i - 1));
    uint64_t a[64];
    std::vector<char> at;
    for (uint32_t n = inputs + 1; n < num_nodes(); ++n) {
      const Node& x = node(n);
      if (x.big_table) {
        uint64_t m = 0;
        for (size_t i = 0; i < x.args.size(); ++i) m |= static_cast<uint64_t>(v[node_of(x.args[i])] ^ is_compl(x.args[i])) << i;
        v[n] = static_cast<char>(((*x.big_table)[m >> 6] >> (m & 63)) & 1);
        continue;
      }
      if (x.diagram) {
        at.assign(x.diagram->view_of_level.size(), 0);
        for (size_t l = 0; l < at.size(); ++l) {
          const Lit arg = x.args[x.diagram->view_of_level[l]];
          at[l] = static_cast<char>(v[node_of(arg)] ^ is_compl(arg));
        }
        v[n] = static_cast<char>(x.diagram->dd.evaluate(x.diagram->root, at));
        continue;
      }
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
    return ((k >> 1) << 1 | ((k & 1) ^ static_cast<uint64_t>(is_compl(l)))) + 1;
  }
  const std::vector<char>& eval_assignment(const Assignment& assign) {
    auto it = sampled_.find(assign);
    if (it == sampled_.end()) {
      if (budget) budget->spend(g_.num_nodes(), StepBudget::kSample);
      it = sampled_.emplace(assign, g_.evaluate(assign)).first;
    }
    return it->second;
  }
  bool bit(Lit l, const Assignment& assign) override {
    return eval_assignment(assign)[node_of(l)] ^ is_compl(l);
  }

  // Seed the symmetry filter with targeted assignments (e.g., 64 satisfying +
  // 64 falsifying paths from a RecordedDiagram) so biased functions (like wide
  // AND/OR trees) still reject non-symmetric pairs immediately.
  void seed_symmetry_samples(const std::vector<Assignment>& samples) {
    sym_seeded_ = samples;
    sim_cone_.clear();
  }

  // Whether swapping read views i and j (from 0) can leave the written view
  // the same: false when it changes it on one of 128 assignments.
  // Only the nodes in dep_nodes_[i] U dep_nodes_[j] are simulated again.
  bool may_be_interchangeable(uint32_t i, uint32_t j) {
    if (sim_cone_.empty()) {
      sim_cone_ = g_.cone({g_.out});
      sim_.assign(size_t{g_.num_nodes()} * kWords, 0);
      read_words_ = (static_cast<size_t>(g_.views) + 63) / 64;
      if (read_words_ == 0) read_words_ = 1;
      reads_.assign(size_t{g_.num_nodes()} * read_words_, 0);
      dep_nodes_.assign(g_.views, {});
      Rng rng(9);
      uint64_t a[64];
      for (uint32_t x : sim_cone_) {
        if (x == 0) continue;
        if (x <= g_.inputs) {
          for (size_t w = 0; w < kWords; ++w) {
            uint64_t bits = 0;
            if (!sym_seeded_.empty()) {
              for (int b = 0; b < 64; ++b) {
                const size_t idx = w * 64 + static_cast<size_t>(b);
                if (idx < sym_seeded_.size() && sym_seeded_[idx].get(x - 1)) bits |= 1ULL << b;
              }
            } else {
              bits = rng.next();
            }
            sim_[size_t{x} * kWords + w] = bits;
          }
          if (x <= g_.views) reads_[size_t{x} * read_words_ + ((x - 1) >> 6)] = uint64_t{1} << ((x - 1) & 63);
          continue;
        }
        const MethodGraph::Node& node = g_.node(x);
        for (Lit l : node.args)
          for (size_t rw = 0; rw < read_words_; ++rw)
            reads_[size_t{x} * read_words_ + rw] |= reads_[size_t{node_of(l)} * read_words_ + rw];
        for (size_t rw = 0; rw < read_words_; ++rw)
          for (uint64_t bits = reads_[size_t{x} * read_words_ + rw]; bits; bits &= bits - 1) {
            const uint32_t v = static_cast<uint32_t>(rw * 64 + static_cast<size_t>(__builtin_ctzll(bits)));
            if (v < g_.views) dep_nodes_[v].push_back(x);
          }
        for (size_t w = 0; w < kWords; ++w) {
          for (size_t k = 0; k < node.args.size(); ++k)
            a[k] = sim_[size_t{node_of(node.args[k])} * kWords + w] ^ (is_compl(node.args[k]) ? ~0ULL : 0);
          sim_[size_t{x} * kWords + w] = MethodGraph::word(node, a);
        }
      }
      swapped_.assign(sim_.size(), 0);
      swapped_mark_.assign(g_.num_nodes(), 0);
      swapped_gen_ = 0;
    }
    ++swapped_gen_;
    if (swapped_gen_ == 0) {
      std::fill(swapped_mark_.begin(), swapped_mark_.end(), 0);
      swapped_gen_ = 1;
    }
    const uint32_t ni = i + 1, nj = j + 1;
    swapped_mark_[ni] = swapped_gen_;
    swapped_mark_[nj] = swapped_gen_;
    for (size_t w = 0; w < kWords; ++w) {
      swapped_[size_t{ni} * kWords + w] = sim_[size_t{nj} * kWords + w];
      swapped_[size_t{nj} * kWords + w] = sim_[size_t{ni} * kWords + w];
    }
    const auto& di = dep_nodes_[i];
    const auto& dj = dep_nodes_[j];
    size_t pi = 0, pj = 0;
    uint64_t a[64];
    while (pi < di.size() || pj < dj.size()) {
      uint32_t x;
      if (pj == dj.size() || (pi < di.size() && di[pi] < dj[pj]))
        x = di[pi++];
      else if (pi == di.size() || dj[pj] < di[pi])
        x = dj[pj++];
      else {
        x = di[pi++];
        ++pj;
      }
      const MethodGraph::Node& node = g_.node(x);
      for (size_t w = 0; w < kWords; ++w) {
        for (size_t k = 0; k < node.args.size(); ++k) {
          const uint32_t u = node_of(node.args[k]);
          const uint64_t v = (swapped_mark_[u] == swapped_gen_ ? swapped_ : sim_)[size_t{u} * kWords + w];
          a[k] = v ^ (is_compl(node.args[k]) ? ~0ULL : 0);
        }
        swapped_[size_t{x} * kWords + w] = MethodGraph::word(node, a);
      }
      swapped_mark_[x] = swapped_gen_;
    }
    const uint32_t o = node_of(g_.out);
    if (swapped_mark_[o] != swapped_gen_) return true;
    for (size_t w = 0; w < kWords; ++w)
      if (swapped_[size_t{o} * kWords + w] != sim_[size_t{o} * kWords + w]) return false;
    return true;
  }

  StepBudget* budget = nullptr;

 protected:
  const MethodGraph& g_;
  std::unordered_map<Assignment, std::vector<char>, AssignmentHash> sampled_;
  static constexpr size_t kWords = 2;
  std::vector<uint32_t> sim_cone_;
  std::vector<uint64_t> sim_, swapped_, reads_;
  std::vector<std::vector<uint32_t>> dep_nodes_;
  std::vector<uint32_t> swapped_mark_;
  uint32_t swapped_gen_ = 0;
  size_t read_words_ = 1;
  std::vector<Assignment> sym_seeded_;
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
    std::vector<uint64_t> h1(n, 0x77), h2(n, 0x9E3779B97F4A7C15ULL), phase(n, 0);
    std::vector<uint64_t> out_h1(chunks_), out_h2(chunks_);
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
        for (size_t w = 0; w < words_; ++w) {
          const uint64_t v = (row[w] ^ f) & valid;
          h1[x] = mix64(h1[x] ^ v);
          h2[x] = mix64(h2[x] ^ (v * 0xBF58476D1CE4E5B9ULL + w));
        }
      }
      const Lit o = g_.out;
      uint64_t oh1 = 0x55, oh2 = 0x94D049BB133111EBULL;
      std::vector<uint64_t> orow(words_);
      for (size_t w = 0; w < words_; ++w) {
        orow[w] = (t_[size_t{node_of(o)} * words_ + w] ^ (is_compl(o) ? ~0ULL : 0)) & valid;
        oh1 = mix64(oh1 ^ orow[w]);
        oh2 = mix64(oh2 ^ (orow[w] * 0xBF58476D1CE4E5B9ULL + w));
      }
      out_h1[c] = oh1;
      out_h2[c] = oh2;
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
      for (uint64_t c = 0; c < chunks_ && !matters[i]; ++c)
        matters[i] = !(c & b) && (out_h1[c] != out_h1[c | b] || out_h2[c] != out_h2[c | b]);
    }
    // Assign canonical class ids from 128-bit signatures (verifying collisions
    // on chunks when two nodes share a 128-bit signature).
    std::map<std::pair<uint64_t, uint64_t>, std::vector<uint32_t>> groups;
    for (uint32_t x = 0; x < n; ++x) groups[{h1[x], h2[x]}].push_back(x);
    keys.assign(n, 0);
    for (const auto& [sig, members] : groups) {
      if (members.size() == 1) {
        const uint32_t x = members[0];
        keys[x] = (static_cast<uint64_t>(x) << 1) | phase[x];
        continue;
      }
      // Verify exact equality over chunks for every pair in this group.
      std::vector<uint32_t> rep_of(members.size(), UINT32_MAX);
      const std::vector<uint32_t> cone = g_.cone([&]() {
        std::vector<Lit> roots;
        for (uint32_t x : members) roots.push_back(make_lit(x));
        return roots;
      }());
      std::vector<std::vector<char>> diff(members.size(), std::vector<char>(members.size(), 0));
      for (uint64_t c = 0; c < chunks_; ++c) {
        evaluate_chunk(c, cone);
        for (size_t a = 0; a < members.size(); ++a) {
          const uint64_t fa = phase[members[a]] ? ~0ULL : 0;
          const uint64_t* ra = &t_[size_t{members[a]} * words_];
          for (size_t b = a + 1; b < members.size(); ++b) {
            if (diff[a][b]) continue;
            const uint64_t fb = phase[members[b]] ? ~0ULL : 0;
            const uint64_t* rb = &t_[size_t{members[b]} * words_];
            for (size_t w = 0; w < words_; ++w)
              if (((ra[w] ^ fa) & valid) != ((rb[w] ^ fb) & valid)) {
                diff[a][b] = 1;
                break;
              }
          }
        }
      }
      for (size_t a = 0; a < members.size(); ++a) {
        if (rep_of[a] != UINT32_MAX) continue;
        rep_of[a] = members[a];
        for (size_t b = a + 1; b < members.size(); ++b)
          if (!diff[a][b] && rep_of[b] == UINT32_MAX) rep_of[b] = members[a];
      }
      for (size_t a = 0; a < members.size(); ++a)
        keys[members[a]] = (static_cast<uint64_t>(rep_of[a]) << 1) | phase[members[a]];
    }
  }

  void find_unused() override {
    for (uint32_t i = 1; i <= g_.views; ++i)
      if (!matters_[i]) unused_views.push_back(static_cast<int>(i));
  }

  bool holds(Lit target, const Registered& r, const std::vector<Lit>& args, bool& differs,
             Assignment& difference) override {
    std::vector<Lit> roots = args;
    roots.push_back(target);
    const std::vector<uint32_t> cone = g_.cone(roots);
    const uint64_t valid = c_ >= 6 ? ~0ULL : ((1ULL << (1u << c_)) - 1);
    std::vector<char> matters(r.arity, 0);
    uint64_t a[64];
    for (uint64_t c = 0; c < chunks_; ++c) {
      evaluate_chunk(c, cone);
      for (size_t w = 0; w < words_; ++w) {
        for (uint32_t i = 0; i < r.arity; ++i) a[i] = word(args[i], w);
        const uint64_t diff = (registered_word(r, a) ^ word(target, w)) & valid;
        if (diff) {
          differs = true;
          difference = Assignment::from_u64((c << c_) | (w * 64 + static_cast<uint64_t>(__builtin_ctzll(diff))), g_.inputs);
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
    uint64_t a[64];
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
  // Inputs at the levels given (a level per input, from 1).
  // `node_limit` is the canonical shared ROBDD reachable-node limit; construction
  // uses a 2x safety cap so intermediate nodes don't prematurely reject an
  // operation whose canonical shared ROBDD fits within `node_limit`.
  BddMethod(const MethodGraph& g, const std::vector<uint32_t>& level_of_input, size_t node_limit)
      : MethodBase(g),
        bdd_(g.inputs, node_limit >= (size_t{1} << 30) ? node_limit : node_limit * 2),
        canonical_limit_(node_limit) {
    level_ = level_of_input;
    input_at_.assign(g.inputs, 0);
    for (uint32_t i = 1; i <= g.inputs; ++i) input_at_[level_[i]] = i;
  }

  BddMethod(const MethodGraph& g, const std::string& order, size_t node_limit)
      : MethodBase(g),
        bdd_(g.inputs, node_limit >= (size_t{1} << 30) ? node_limit : node_limit * 2),
        canonical_limit_(node_limit) {
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
    bdd_.budget = budget;
    edge_.assign(n, Bdd::kFalse);
    for (uint32_t i = 1; i <= g_.inputs; ++i) edge_[i] = bdd_.var(level_[i]);
    for (uint32_t x = g_.inputs + 1; x < n; ++x) {
      if (budget) budget->at = make_lit(x);
      const MethodGraph::Node& node = g_.node(x);
      std::vector<Bdd::Edge> a;
      for (Lit l : node.args) a.push_back(lit(l));
      if (node.is_and)
        edge_[x] = bdd_.land(a[0], a[1]);
      else if (node.diagram)
        edge_[x] = compose(*node.diagram, a);
      else if (node.big_table)
        edge_[x] = apply_big(*node.big_table, a);
      else
        edge_[x] = apply_table(node.table, a);
    }
    // Enforce the canonical compiler-independent shared ROBDD node limit.
    canonical_nodes_ = bdd_.reachable_node_count(edge_);
    if (canonical_nodes_ > canonical_limit_) throw BddLimit();
    // Equal functions are the same edge, and opposite ones the same node.
    keys.assign(n, 0);
    for (uint32_t x = 0; x < n; ++x) keys[x] = edge_[x];
  }

  void find_unused() override {
    const std::vector<char> in = support(lit(g_.out));
    for (uint32_t i = 1; i <= g_.views; ++i)
      if (!in[level_[i]]) unused_views.push_back(static_cast<int>(i));
  }

  // Precomputed semantic support bitsets for every ROBDD node reachable from
  // `edge_`, computed in one bottom-up O(|BDD| * ceil(inputs / 64)) pass.
  struct SupportTable {
    size_t words = 0;
    std::vector<uint32_t> index;  // BDD node -> dense row index (0 for terminal)
    std::vector<uint64_t> bits;   // row * words + (input_idx >> 6)
    const std::vector<Bdd::Edge>* edge = nullptr;
    bool has(Lit l, uint32_t input_idx) const {
      const uint32_t n = (*edge)[node_of(l)] >> 1;
      if (n == 0) return false;
      const uint32_t row = index[n];
      return ((bits[size_t{row} * words + (input_idx >> 6)] >> (input_idx & 63)) & 1ULL) != 0;
    }
  };

  SupportTable all_supports() const {
    SupportTable st;
    st.words = (static_cast<size_t>(g_.inputs) + 63) / 64;
    st.edge = &edge_;
    if (st.words == 0) return st;
    const size_t total = bdd_.num_nodes();
    std::vector<char> seen(total, 0);
    std::vector<uint32_t> stack;
    for (Bdd::Edge e : edge_) {
      const uint32_t n = e >> 1;
      if (n != 0 && !seen[n]) {
        seen[n] = 1;
        stack.push_back(n);
      }
    }
    while (!stack.empty()) {
      const uint32_t n = stack.back();
      stack.pop_back();
      const uint32_t lo = bdd_.low(n) >> 1, hi = bdd_.high(n) >> 1;
      if (lo != 0 && !seen[lo]) {
        seen[lo] = 1;
        stack.push_back(lo);
      }
      if (hi != 0 && !seen[hi]) {
        seen[hi] = 1;
        stack.push_back(hi);
      }
    }
    st.index.assign(total, 0);
    uint32_t rows = 1;  // row 0 = terminal (empty support)
    for (uint32_t n = 1; n < total; ++n)
      if (seen[n]) st.index[n] = rows++;
    st.bits.assign(size_t{rows} * st.words, 0);
    for (uint32_t n = 1; n < total; ++n) {
      if (!seen[n]) continue;
      uint64_t* dst = &st.bits[size_t{st.index[n]} * st.words];
      const uint32_t inp = input_at_[bdd_.level_of(n)] - 1;
      dst[inp >> 6] |= uint64_t{1} << (inp & 63);
      const uint32_t lo = bdd_.low(n) >> 1, hi = bdd_.high(n) >> 1;
      if (lo != 0) {
        const uint64_t* src = &st.bits[size_t{st.index[lo]} * st.words];
        for (size_t w = 0; w < st.words; ++w) dst[w] |= src[w];
      }
      if (hi != 0) {
        const uint64_t* src = &st.bits[size_t{st.index[hi]} * st.words];
        for (size_t w = 0; w < st.words; ++w) dst[w] |= src[w];
      }
    }
    return st;
  }

  uint64_t function_id(Lit l) override { return static_cast<uint64_t>(lit(l)) + 1; }

  bool distinguish(Lit a, Lit b, Assignment& out) override {
    const Bdd::Edge ea = lit(a), eb = lit(b);
    if (ea == eb) return false;
    out = Assignment::zeros(g_.inputs);
    bdd_.distinguishing_path(ea, eb, [&](uint32_t level, bool value) {
      if (value) out.set(input_at_[level] - 1);
    });
    return true;
  }

  bool holds(Lit target, const Registered& r, const std::vector<Lit>& args, bool& differs,
             Assignment& difference) override {
    std::vector<Bdd::Edge> a;
    a.reserve(args.size());
    for (Lit l : args) a.push_back(lit(l));
    const Bdd::Edge rv = apply_table(r.table, a), t = lit(target);
    if (rv != t) {
      differs = true;
      difference = Assignment::zeros(g_.inputs);
      bdd_.distinguishing_path(rv, t, [&](uint32_t level, bool value) {
        if (value) difference.set(input_at_[level] - 1);
      });
      return false;
    }
    // Fast O(1) essential-argument checks for standard operations.
    if (r.arity == 2) {
      const uint64_t tb = r.table & 0xFULL;
      if (tb == 0x6 || tb == 0x9) return true;  // xor, eq: both views always matter
      if (tb == 0x8) return a[0] != Bdd::kFalse && a[1] != Bdd::kFalse;
      if (tb == 0xE) return a[0] != Bdd::kTrue && a[1] != Bdd::kTrue;
      if (tb == 0xD) return a[1] != Bdd::kTrue && a[0] != Bdd::kFalse;
    } else if (r.arity == 3) {
      const uint64_t tb = r.table & 0xFFULL;
      if (tb == 0xD8) return a[1] != a[2] && a[0] != Bdd::kFalse && a[0] != Bdd::kTrue;
      if (tb == 0xE8) return a[1] != a[2] && a[0] != a[2] && a[0] != a[1];
    }
    // General case: check each view's (arity - 1)-variable Boolean derivative.
    const uint32_t sub_rows = 1u << (r.arity - 1);
    const uint64_t sub_mask = sub_rows == 64 ? ~0ULL : ((uint64_t{1} << sub_rows) - 1);
    std::vector<Bdd::Edge> other(r.arity - 1);
    for (uint32_t i = 0; i < r.arity; ++i) {
      uint64_t deriv = 0;
      for (uint32_t sm = 0; sm < sub_rows; ++sm) {
        const uint32_t lo_m = (sm & ((1u << i) - 1)) | ((sm & ~((1u << i) - 1)) << 1);
        const uint32_t hi_m = lo_m | (1u << i);
        if (((r.table >> lo_m) & 1) != ((r.table >> hi_m) & 1)) deriv |= uint64_t{1} << sm;
      }
      if (deriv == sub_mask) continue;  // always matters
      size_t p = 0;
      for (uint32_t h = 0; h < r.arity; ++h)
        if (h != i) other[p++] = a[h];
      if (apply_table(deriv, other) == Bdd::kFalse) return false;
    }
    return true;
  }

  // Diagnostic helpers for compiler error messages (care sets and pairwise relations).
  uint64_t care_set_mask(const std::vector<Lit>& args) {
    if (args.size() > 4) return 0;
    uint64_t mask = 0;
    const uint32_t rows = 1u << args.size();
    for (uint32_t m = 0; m < rows; ++m) {
      Bdd::Edge conj = Bdd::kTrue;
      for (size_t i = 0; i < args.size() && conj != Bdd::kFalse; ++i)
        conj = bdd_.land(conj, ((m >> i) & 1) ? lit(args[i]) : (lit(args[i]) ^ 1));
      if (conj != Bdd::kFalse) mask |= uint64_t{1} << m;
    }
    return mask;
  }
  bool implies(Lit a, Lit b) { return bdd_.land(lit(a), lit(b) ^ 1) == Bdd::kFalse; }
  bool mutually_exclusive(Lit a, Lit b) { return bdd_.land(lit(a), lit(b)) == Bdd::kFalse; }

  size_t nodes() const { return bdd_.num_nodes(); }
  size_t canonical_nodes() const { return canonical_nodes_; }
  size_t memory_bytes() const { return bdd_.memory_bytes(); }
  // The written view's OBDD nodes: what an execution of the operation refers to.
  // The written view's diagram alone, without complement edges, levels in
  // this operation's order, for the operations that execute it.
  RecordedDiagram record() const {
    RecordedDiagram rd;
    rd.dd = Diagram(g_.inputs);
    std::unordered_map<Bdd::Edge, Diagram::Node> copy;
    std::function<Diagram::Node(Bdd::Edge)> go = [&](Bdd::Edge e) -> Diagram::Node {
      if ((e >> 1) == 0) return e == Bdd::kTrue ? Diagram::kTrue : Diagram::kFalse;
      auto it = copy.find(e);
      if (it != copy.end()) return it->second;
      const uint32_t n = e >> 1, c = e & 1;
      const Diagram::Node lo = go(bdd_.low(n) ^ c), hi = go(bdd_.high(n) ^ c);
      const Diagram::Node r = rd.dd.make(bdd_.level_of(n), lo, hi);
      copy.emplace(e, r);
      return r;
    };
    rd.root = go(edge_[node_of(g_.out)] ^ (is_compl(g_.out) ? 1u : 0u));
    for (uint32_t l = 0; l < g_.inputs; ++l) rd.view_of_level.push_back(input_at_[l] - 1);
    return rd;
  }

  size_t out_nodes() {
    const std::vector<uint32_t> counts = bdd_.reachable_level_counts({lit(g_.out)});
    return std::accumulate(counts.begin(), counts.end(), size_t{0});
  }
  // The written view on one input assignment, walking its OBDD.
  bool evaluate_out(const Assignment& assign) const {
    Bdd::Edge e = edge_[node_of(g_.out)] ^ (is_compl(g_.out) ? 1u : 0u);
    while ((e >> 1) != 0) {
      const uint32_t n = e >> 1, c = e & 1;
      const bool v = assign.get(input_at_[bdd_.level_of(n)] - 1);
      e = (v ? bdd_.high(n) : bdd_.low(n)) ^ c;
    }
    return e == Bdd::kTrue;
  }

 private:
  Bdd bdd_;
  size_t canonical_limit_ = size_t{1} << 26;
  size_t canonical_nodes_ = 0;
  std::vector<uint32_t> level_, input_at_;
  std::vector<Bdd::Edge> edge_;

  Bdd::Edge lit(Lit l) const { return edge_[node_of(l)] ^ (is_compl(l) ? 1u : 0u); }

  Bdd::Edge shannon(uint64_t table, uint32_t k, const Bdd::Edge* a) {
    if (k == 0) return (table & 1) ? Bdd::kTrue : Bdd::kFalse;
    const uint32_t half = 1u << (k - 1);
    const uint64_t mask = half == 64 ? ~0ULL : ((uint64_t{1} << half) - 1);
    const uint64_t lo = table & mask;
    const uint64_t hi = (table >> half) & mask;
    if (lo == hi) return shannon(lo, k - 1, a);
    if (lo == (hi ^ mask)) return bdd_.lxor(a[k - 1], shannon(lo, k - 1, a));
    return bdd_.ite(a[k - 1], shannon(hi, k - 1, a), shannon(lo, k - 1, a));
  }

  Bdd::Edge apply_table(uint64_t table, const std::vector<Bdd::Edge>& a) {
    const size_t k = a.size();
    if (k == 0) return (table & 1) ? Bdd::kTrue : Bdd::kFalse;
    if (k == 1) {
      switch (table & 3u) {
        case 0: return Bdd::kFalse;
        case 1: return a[0] ^ 1;
        case 2: return a[0];
        default: return Bdd::kTrue;
      }
    }
    if (k == 2) {
      switch (table & 0xFu) {
        case 0x0: return Bdd::kFalse;
        case 0xF: return Bdd::kTrue;
        case 0x8: return bdd_.land(a[0], a[1]);
        case 0xE: return bdd_.lor(a[0], a[1]);
        case 0x6: return bdd_.lxor(a[0], a[1]);
        case 0x9: return bdd_.lxor(a[0], a[1]) ^ 1;
        case 0xD: return bdd_.lor(a[0] ^ 1, a[1]);
        case 0xB: return bdd_.lor(a[0], a[1] ^ 1);
        case 0x2: return bdd_.land(a[0], a[1] ^ 1);
        case 0x4: return bdd_.land(a[0] ^ 1, a[1]);
        case 0x1: return bdd_.land(a[0] ^ 1, a[1] ^ 1);
        case 0x7: return bdd_.land(a[0], a[1]) ^ 1;
        default: break;
      }
    } else if (k == 3) {
      switch (table & 0xFFu) {
        case 0xD8: return bdd_.ite(a[0], a[1], a[2]);
        case 0xE8: return bdd_.ite(a[0], bdd_.lor(a[1], a[2]), bdd_.land(a[1], a[2]));
        case 0x96: return bdd_.lxor(a[0], bdd_.lxor(a[1], a[2]));
        case 0x69: return bdd_.lxor(a[0], bdd_.lxor(a[1], a[2])) ^ 1;
        default: break;
      }
    }
    return shannon(table, static_cast<uint32_t>(k), a.data());
  }

  // An execution of a recorded diagram: each of its nodes asks for an
  // argument.
  Bdd::Edge compose(const RecordedDiagram& rd, const std::vector<Bdd::Edge>& by_view) {
    std::unordered_map<Diagram::Node, Bdd::Edge> memo{{Diagram::kFalse, Bdd::kFalse}, {Diagram::kTrue, Bdd::kTrue}};
    std::function<Bdd::Edge(Diagram::Node)> go = [&](Diagram::Node n) {
      auto it = memo.find(n);
      if (it != memo.end()) return it->second;
      const Bdd::Edge r = bdd_.ite(by_view[rd.view_of_level[rd.dd.level(n)]], go(rd.dd.hi(n)), go(rd.dd.lo(n)));
      memo.emplace(n, r);
      return r;
    };
    return go(rd.root);
  }

  // An execution of a recorded table of more than six views: Shannon on
  // the last argument first, so each half of a range of rows is a range,
  // and equal ranges are one function.
  Bdd::Edge apply_big(const std::vector<uint64_t>& table, const std::vector<Bdd::Edge>& a) {
    std::map<std::pair<uint32_t, std::vector<uint64_t>>, Bdd::Edge> memo;
    auto bits = [&](uint64_t from, uint32_t i) {
      // Rows from..from + 2^i as words (one word when i <= 6).
      std::vector<uint64_t> out;
      if (i <= 6) {
        const uint64_t len = uint64_t{1} << i;
        const uint64_t w = table[from >> 6] >> (from & 63);
        out.push_back(len == 64 ? w : (w & ((uint64_t{1} << len) - 1)));
      } else {
        out.assign(table.begin() + static_cast<std::ptrdiff_t>(from >> 6),
                   table.begin() + static_cast<std::ptrdiff_t>((from >> 6) + (uint64_t{1} << (i - 6))));
      }
      return out;
    };
    std::function<Bdd::Edge(uint64_t, uint32_t)> go = [&](uint64_t from, uint32_t i) -> Bdd::Edge {
      if (i == 0) return ((table[from >> 6] >> (from & 63)) & 1) ? Bdd::kTrue : Bdd::kFalse;
      auto key = std::make_pair(i, bits(from, i));
      auto it = memo.find(key);
      if (it != memo.end()) return it->second;
      const uint64_t half = uint64_t{1} << (i - 1);
      const Bdd::Edge r = bdd_.ite(a[i - 1], go(from + half, i - 1), go(from, i - 1));
      memo.emplace(std::move(key), r);
      return r;
    };
    return go(0, static_cast<uint32_t>(a.size()));
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
    for (const MethodGraph::Node& node : g.nodes)
      if (node.big_table || node.diagram) throw std::runtime_error("sat: an execution of more than six views");
    const uint32_t n = g.num_nodes();
    for (uint32_t x = 0; x < n; ++x) var_.push_back(solver_.new_var());
    solver_.add_clause({sat::neg(var_[0])});
    for (uint32_t x = g.inputs + 1; x < n; ++x) encode(var_[x], g.node(x).is_and ? 0x8 : g.node(x).table, g.node(x).args);
    Rng rng(5);
    for (int k = 0; k < kRandomWords * 64; ++k) patterns_.push_back(Assignment::random(g.inputs, rng));
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
      keys[x] = (static_cast<uint64_t>(x) << 1) | phase;
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
      if (keys[x] == ((static_cast<uint64_t>(x) << 1) | phase)) group.push_back(x);
    }
  }

  void find_unused() override {
    const std::vector<std::vector<uint64_t>>& sim = sim_;
    // A read view the written view depends on changes it on some sampled
    // assignment when flipped; the others need a proof.
    const Lit o = g_.out;
    for (uint32_t i = 1; i <= g_.views; ++i) {
      std::vector<Assignment> flipped = patterns_;
      for (Assignment& p : flipped) p.flip(i - 1);
      const std::vector<std::vector<uint64_t>> s2 = simulate(flipped);
      bool matters = false;
      for (size_t w = 0; w < s2[0].size() && !matters; ++w) matters = s2[node_of(o)][w] != sim[node_of(o)][w];
      if (!matters) matters = view_matters(i);
      if (!matters) unused_views.push_back(static_cast<int>(i));
    }
  }

  bool holds(Lit target, const Registered& r, const std::vector<Lit>& args, bool& differs,
             Assignment& difference) override {
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
  std::vector<Assignment> patterns_;
  std::vector<std::vector<char>> fresh_;
  std::vector<std::vector<uint64_t>> sim_;
  Assignment last_model_;

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
        last_model_ = Assignment::zeros(g_.inputs);
        for (uint32_t i = 1; i <= g_.inputs; ++i)
          if (solver_.model_value(var_[i])) last_model_.set(i - 1);
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

  std::vector<std::vector<uint64_t>> simulate(const std::vector<Assignment>& patterns) const {
    const uint32_t n = g_.num_nodes();
    const size_t words = (patterns.size() + 63) / 64;
    std::vector<std::vector<uint64_t>> sim(n, std::vector<uint64_t>(words, 0));
    for (size_t k = 0; k < patterns.size(); ++k)
      for (uint32_t i = 1; i <= g_.inputs; ++i)
        if (patterns[k].get(i - 1)) sim[i][k / 64] |= 1ULL << (k % 64);
    uint64_t a[64];
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
             Assignment& difference) override {
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
    uint64_t a[64];
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
