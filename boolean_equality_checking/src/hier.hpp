// Checking value operations whose executions refer to other value operations
// instead of copying them (see gen/hierarchy.py for the library format).
//
// Each operation is checked once, in dependency order, for redundant values
// among the values its own statements compute (DLP 57), and records the
// truth table of each view it writes. Four ways:
//
// - copy: every execution is inlined, recursively, into one flat graph, which
//   the combined algorithm then checks.
// - tt: truth tables over the operation's views; an execution is a lookup in
//   the executed operation's recorded tables, one per combination.
// - sat: simulation with lookups groups the values, and each candidate pair
//   is decided by SAT on the operation's own statements, with each
//   execution's results as free variables. A satisfying assignment is checked
//   against the executed operations' tables, and for each execution that
//   disagrees, a clause fixing its results for those values is added before
//   solving again (counterexample-guided abstraction refinement).
// - bdd: each operation records OBDDs of the views it writes, over its views
//   in order, and an execution composes them with the OBDDs of its values.
#pragma once

#include <fstream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include "aig.hpp"
#include "bdd.hpp"
#include "sat.hpp"
#include "structural.hpp"
#include "sweep.hpp"

namespace beq {

struct HStatement {
  bool is_exec = false;
  Lit a = 0, b = 0;  // for an `and`
  int callee = -1;   // for an execution
  int outputs = 0;
  std::vector<Lit> args;
};

struct HOp {
  std::string name;
  uint32_t views = 0;
  std::vector<HStatement> statements;
  std::vector<Lit> outputs;
  std::vector<std::pair<Lit, Lit>> planted;
  uint32_t num_values = 0;  // false, the views, and every statement's values
  // Recorded: truth table of each written view, 2^views bits.
  std::vector<std::vector<uint64_t>> out_tables;
  // Recorded: OBDDs of each written view, in this operation's own manager.
  std::unique_ptr<Bdd> bdd;
  std::vector<Bdd::Edge> out_bdds;
};

inline std::vector<HOp> read_library(const std::string& path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open " + path);
  std::vector<HOp> ops;
  std::map<std::string, int> index;
  for (std::string line; std::getline(in, line);) {
    std::istringstream words(line);
    std::string kind;
    words >> kind;
    if (kind == "op") {
      ops.emplace_back();
      words >> ops.back().name >> ops.back().views;
      ops.back().num_values = 1 + ops.back().views;
      index[ops.back().name] = static_cast<int>(ops.size() - 1);
    } else if (kind == "and") {
      HStatement s;
      words >> s.a >> s.b;
      ops.back().statements.push_back(s);
      ++ops.back().num_values;
    } else if (kind == "exec") {
      HStatement s;
      std::string callee;
      s.is_exec = true;
      words >> callee >> s.outputs;
      s.callee = index.at(callee);
      for (Lit a; words >> a;) s.args.push_back(a);
      ops.back().statements.push_back(s);
      ops.back().num_values += static_cast<uint32_t>(s.outputs);
    } else if (kind == "out") {
      for (Lit a; words >> a;) ops.back().outputs.push_back(a);
    } else if (kind == "planted") {
      Lit a, b;
      words >> a >> b;
      ops.back().planted.push_back({a, b});
    }
  }
  return ops;
}

// Redundant values among an operation's own values, given each value's key:
// a value that's always the same as false, a view, or an earlier value, or
// always the opposite of one. Every check's key is a class of functions up to
// complement, and in the low bit which of the two functions the value is, so
// equal values have equal keys and opposite ones differ in the low bit. A
// `not` is a complemented literal, never a value, so no value is exempt.
inline uint32_t count_redundant(const std::vector<uint64_t>& keys, uint32_t views) {
  std::unordered_map<uint64_t, uint32_t> first;
  uint32_t redundant = 0;
  for (uint32_t v = 0; v < keys.size(); ++v) {
    auto [it, inserted] = first.try_emplace(keys[v] >> 1, v);
    if (!inserted && v > views) ++redundant;
  }
  return redundant;
}

class Hierarchy {
 public:
  explicit Hierarchy(std::vector<HOp> ops) : ops_(std::move(ops)) {}

  size_t size() const { return ops_.size(); }
  const HOp& op(size_t i) const { return ops_[i]; }

  // Truth tables of every value of operation i, with executions as lookups.
  // Records the written views' tables. Returns each value's hash.
  std::vector<uint64_t> check_tt(size_t i) {
    HOp& op = ops_[i];
    const size_t words = op.views <= 6 ? 1 : (size_t{1} << (op.views - 6));
    const uint64_t mask = op.views >= 6 ? ~0ULL : ((1ULL << (1u << op.views)) - 1);
    std::vector<std::vector<uint64_t>> t(op.num_values, std::vector<uint64_t>(words, 0));
    static const uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                     0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
    for (uint32_t v = 0; v < op.views; ++v)
      for (size_t w = 0; w < words; ++w)
        t[1 + v][w] = (v < 6 ? kVar[v] : (((w >> (v - 6)) & 1) ? ~0ULL : 0)) & mask;
    auto lit_word = [&](Lit l, size_t w) { return (t[node_of(l)][w] ^ (is_compl(l) ? ~0ULL : 0)) & mask; };
    uint32_t next = 1 + op.views;
    for (const HStatement& s : op.statements) {
      if (!s.is_exec) {
        for (size_t w = 0; w < words; ++w) t[next][w] = lit_word(s.a, w) & lit_word(s.b, w);
        ++next;
        continue;
      }
      const HOp& callee = ops_[s.callee];
      for (size_t w = 0; w < words; ++w) {
        std::vector<uint64_t> arg(s.args.size());
        for (size_t j = 0; j < s.args.size(); ++j) arg[j] = lit_word(s.args[j], w);
        const int bits = op.views < 6 ? (1 << op.views) : 64;
        for (int b = 0; b < bits; ++b) {
          uint32_t index = 0;
          for (size_t j = 0; j < arg.size(); ++j) index |= ((arg[j] >> b) & 1) << j;
          for (int o = 0; o < s.outputs; ++o)
            if ((callee.out_tables[o][index >> 6] >> (index & 63)) & 1) t[next + o][w] |= 1ULL << b;
        }
        lookups_ += static_cast<uint64_t>(bits);
      }
      next += static_cast<uint32_t>(s.outputs);
    }
    op.out_tables.clear();
    for (Lit o : op.outputs) {
      std::vector<uint64_t> table(words);
      for (size_t w = 0; w < words; ++w) table[w] = lit_word(o, w);
      op.out_tables.push_back(table);
    }
    std::vector<uint64_t> keys(op.num_values);
    for (uint32_t v = 0; v < op.num_values; ++v) {
      // The class is the table that's false on the first assignment.
      const uint64_t opposite = t[v][0] & 1;
      uint64_t h = 0x77;
      for (size_t w = 0; w < words; ++w) h = mix64(h ^ (t[v][w] ^ (opposite ? mask : 0)));
      keys[v] = (h & ~1ULL) | opposite;
    }
    return keys;
  }

  // Copies every execution into one flat graph. Returns the flat literal of
  // each of the operation's own values, or throws past node_limit nodes.
  std::vector<Lit> flatten(size_t i, Aig& flat, size_t node_limit) const {
    const HOp& op = ops_[i];
    flat = Aig();
    flat.num_inputs = op.views;
    flat.fanin0.assign(1 + op.views, 0);
    flat.fanin1.assign(1 + op.views, 0);
    std::vector<Lit> args;
    for (uint32_t v = 0; v < op.views; ++v) args.push_back(make_lit(1 + v));
    std::vector<Lit> values;
    inline_op(i, args, flat, node_limit, &values);
    return values;
  }

  uint64_t lookups() const { return lookups_; }

  HOp& mutable_op(size_t i) { return ops_[i]; }

  // A hash of the truth tables an operation records for the views it writes.
  uint64_t recorded_hash(size_t i) const {
    uint64_t h = 0x99;
    for (const std::vector<uint64_t>& t : ops_[i].out_tables)
      for (uint64_t w : t) h = mix64(h ^ w);
    return h;
  }

  // OBDDs of every value of operation i in its own manager; executions
  // compose the callee's recorded OBDDs. Records the written views' OBDDs.
  // Returns each value's edge (equal functions have equal edges).
  std::vector<uint64_t> check_bdd(size_t i, size_t node_limit) {
    HOp& op = ops_[i];
    op.bdd = std::make_unique<Bdd>(op.views, node_limit);
    Bdd& m = *op.bdd;
    std::vector<Bdd::Edge> e(op.num_values);
    e[0] = Bdd::kFalse;
    for (uint32_t v = 0; v < op.views; ++v) e[1 + v] = m.var(v);
    auto lit_edge = [&](Lit l) { return e[node_of(l)] ^ (is_compl(l) ? 1u : 0u); };
    uint32_t next = 1 + op.views;
    for (const HStatement& s : op.statements) {
      if (!s.is_exec) {
        e[next++] = m.land(lit_edge(s.a), lit_edge(s.b));
        continue;
      }
      const HOp& callee = ops_[s.callee];
      std::vector<Bdd::Edge> args;
      for (Lit a : s.args) args.push_back(lit_edge(a));
      std::unordered_map<uint32_t, Bdd::Edge> memo;
      for (int o = 0; o < s.outputs; ++o) e[next + o] = compose(*callee.bdd, callee.out_bdds[o], args, m, memo);
      next += static_cast<uint32_t>(s.outputs);
    }
    op.out_bdds.clear();
    for (Lit o : op.outputs) op.out_bdds.push_back(lit_edge(o));
    std::vector<uint64_t> keys(e.begin(), e.end());
    return keys;
  }

  // Simulation with lookups, then SAT with abstraction refinement for each
  // candidate pair. Needs the callees' recorded truth tables. Returns each
  // value's class key (twice the first value it was proved equal to or the
  // opposite of, plus one if it's the opposite).
  // expand: an execution that disagrees with its callee's table gets the
  // callee's own statements as clauses (with the callee's executions as new
  // free results). Otherwise, it gets one clause fixing its results for the
  // values it was given in that assignment.
  // Assignments of an operation's views that showed two of its values differ,
  // stored with it, by operation name.
  std::map<std::string, std::vector<uint32_t>> stored;

  // expand_after: an execution gets one clause per disagreeing assignment for
  // its first expand_after disagreements, and is expanded after that (0
  // expands at the first; a huge number never expands).
  std::vector<uint64_t> check_sat(size_t i, Stats& stats, uint32_t expand_after, bool stop_first = false) {
    const HOp& op = ops_[i];
    const uint32_t n = op.num_values;
    // Simulation: the stored assignments first, then 1,024 random ones from
    // a fixed seed.
    std::vector<uint32_t>& patterns = stored[op.name];
    const int stored_rounds = static_cast<int>((patterns.size() + 63) / 64);
    const int rounds = stored_rounds + 16;
    std::vector<std::vector<uint64_t>> sim(n, std::vector<uint64_t>(rounds, 0));
    for (size_t k = 0; k < patterns.size(); ++k)
      for (uint32_t v = 0; v < op.views; ++v)
        if ((patterns[k] >> v) & 1) sim[1 + v][k / 64] |= 1ULL << (k % 64);
    Rng rng(5);
    for (uint32_t v = 0; v < op.views; ++v)
      for (int r = stored_rounds; r < rounds; ++r) sim[1 + v][r] = rng.next();
    // Unused bits of the last stored word repeat the first assignment, so they
    // never separate anything.
    for (size_t k = patterns.size(); k < static_cast<size_t>(stored_rounds) * 64; ++k)
      for (uint32_t v = 0; v < op.views; ++v)
        if ((patterns[0] >> v) & 1) sim[1 + v][k / 64] |= 1ULL << (k % 64);
    stats.emplace_back("patterns_used", static_cast<double>(patterns.size()));
    simulate(op, sim, rounds);
    Encoding enc;
    uint32_t false_var = enc.solver.new_var();
    enc.solver.add_clause({sat::neg(false_var)});
    enc.false_lit = sat::pos(false_var);
    std::vector<sat::Lit> views;
    for (uint32_t v = 0; v < op.views; ++v) views.push_back(sat::pos(enc.solver.new_var()));
    enc.views = views;
    std::vector<sat::Lit> value = encode_body(i, views, enc);
    const size_t patterns_before = patterns.size();
    std::vector<std::vector<char>> fresh;  // every value on each new assignment
    // Candidates by signature, in value order, with a value and its opposite
    // under one signature: the simulation that's false on the first
    // assignment. Each signature keeps every value proved different from the
    // earlier ones with that signature, and from their opposites.
    std::map<std::vector<uint64_t>, std::vector<uint32_t>> groups;
    std::vector<uint64_t> keys(n);
    uint64_t equal = 0;
    for (uint32_t v = 0; v < n; ++v) {
      keys[v] = 2 * uint64_t{v};
      std::vector<uint64_t> signature = sim[v];
      if (signature[0] & 1)
        for (uint64_t& word : signature) word = ~word;
      std::vector<uint32_t>& group = groups[signature];
      bool merged = false;
      for (uint32_t r : group) {
        const bool flip = ((sim[v][0] ^ sim[r][0]) & 1) != 0;
        // An assignment found earlier in this check may already separate them.
        bool separated = false;
        for (const std::vector<char>& values : fresh) separated |= values[v] != (values[r] ^ flip);
        if (separated) continue;
        if (decide(enc, value[v], value[r] ^ (flip ? 1u : 0u), expand_after)) {
          ++equal;
          keys[v] = keys[r] ^ (flip ? 1u : 0u);
          merged = true;
          break;
        }
        // A real difference: store the assignment that showed it.
        uint32_t assignment = 0;
        for (uint32_t w = 0; w < op.views; ++w) assignment |= static_cast<uint32_t>(lit_value(enc, views[w])) << w;
        patterns.push_back(assignment);
        fresh.push_back(evaluate(op, assignment));
      }
      if (!merged) group.push_back(v);
      // DLP 57 reports the first redundant value of an operation.
      if (merged && stop_first && v > op.views) {
        stats.emplace_back("stopped_at", static_cast<double>(v));
        break;
      }
    }
    stats.emplace_back("patterns_added", static_cast<double>(patterns.size() - patterns_before));
    stats.emplace_back("sat_calls", static_cast<double>(enc.calls));
    stats.emplace_back("refinements", static_cast<double>(enc.refinements));
    stats.emplace_back("expanded", static_cast<double>(enc.expanded));
    stats.emplace_back("instances", static_cast<double>(enc.instances.size()));
    stats.emplace_back("sat_vars", static_cast<double>(enc.solver.num_vars()));
    stats.emplace_back("proved_equal", static_cast<double>(equal));
    return keys;
  }

 private:
  struct Instance {
    int callee;
    std::vector<sat::Lit> args;
    std::vector<sat::Lit> outputs;
    bool expanded = false;
    uint32_t disagreements = 0;
  };

  struct Encoding {
    sat::Solver solver;
    sat::Lit false_lit = 0;
    std::vector<sat::Lit> views;
    std::vector<Instance> instances;
    uint64_t calls = 0, refinements = 0, expanded = 0;
  };

  // Clauses for operation i's own statements with its views given by `views`.
  // Each execution's results are new free variables, recorded as an
  // instance that can be expanded later. Returns the literal of each value.
  std::vector<sat::Lit> encode_body(size_t i, const std::vector<sat::Lit>& views, Encoding& enc) const {
    const HOp& op = ops_[i];
    std::vector<sat::Lit> value(op.num_values);
    value[0] = enc.false_lit;
    for (uint32_t v = 0; v < op.views; ++v) value[1 + v] = views[v];
    auto lit = [&](Lit l) { return value[node_of(l)] ^ (is_compl(l) ? 1u : 0u); };
    uint32_t next = 1 + op.views;
    for (const HStatement& s : op.statements) {
      if (!s.is_exec) {
        sat::Lit z = sat::pos(enc.solver.new_var());
        enc.solver.add_clause({z ^ 1, lit(s.a)});
        enc.solver.add_clause({z ^ 1, lit(s.b)});
        enc.solver.add_clause({z, lit(s.a) ^ 1, lit(s.b) ^ 1});
        value[next++] = z;
        continue;
      }
      Instance inst;
      inst.callee = s.callee;
      for (Lit a : s.args) inst.args.push_back(lit(a));
      for (int o = 0; o < s.outputs; ++o) {
        inst.outputs.push_back(sat::pos(enc.solver.new_var()));
        value[next++] = inst.outputs.back();
      }
      enc.instances.push_back(std::move(inst));
    }
    return value;
  }

  bool lit_value(const Encoding& enc, sat::Lit l) const { return enc.solver.model_value(sat::var(l)) ^ sat::sign(l); }

  // Whether the values with literals x and y are equal.
  bool decide(Encoding& enc, sat::Lit x, sat::Lit y, uint32_t expand_after) const {
    for (;;) {
      ++enc.calls;
      sat::Result res = enc.solver.solve({x, y ^ 1}, -1);
      if (res == sat::Result::kUnsat) res = enc.solver.solve({x ^ 1, y}, -1);
      if (res == sat::Result::kUnsat) return true;
      // Check every unexpanded execution against its callee's table.
      bool consistent = true;
      for (size_t k = 0; k < enc.instances.size(); ++k) {
        if (enc.instances[k].expanded) continue;
        const Instance inst = enc.instances[k];
        const HOp& callee = ops_[inst.callee];
        uint32_t index = 0;
        for (size_t j = 0; j < inst.args.size(); ++j) index |= static_cast<uint32_t>(lit_value(enc, inst.args[j])) << j;
        bool agrees = true;
        for (size_t o = 0; o < inst.outputs.size(); ++o) {
          bool expected = (callee.out_tables[o][index >> 6] >> (index & 63)) & 1;
          agrees &= lit_value(enc, inst.outputs[o]) == expected;
        }
        if (agrees) continue;
        consistent = false;
        ++enc.refinements;
        if (enc.instances[k].disagreements++ >= expand_after) {
          enc.instances[k].expanded = true;
          ++enc.expanded;
          std::vector<sat::Lit> body = encode_body(static_cast<size_t>(inst.callee), inst.args, enc);
          for (size_t o = 0; o < inst.outputs.size(); ++o) {
            sat::Lit out = body[node_of(callee.outputs[o])] ^ (is_compl(callee.outputs[o]) ? 1u : 0u);
            enc.solver.add_clause({inst.outputs[o] ^ 1, out});
            enc.solver.add_clause({inst.outputs[o], out ^ 1});
          }
        } else {
          std::vector<sat::Lit> clause;
          for (sat::Lit a : inst.args) clause.push_back(lit_value(enc, a) ? (a ^ 1) : a);
          for (size_t o = 0; o < inst.outputs.size(); ++o) {
            bool expected = (callee.out_tables[o][index >> 6] >> (index & 63)) & 1;
            std::vector<sat::Lit> c = clause;
            c.push_back(expected ? inst.outputs[o] : (inst.outputs[o] ^ 1));
            enc.solver.add_clause(c);
          }
        }
      }
      if (consistent) return false;  // a real difference
    }
  }

  // Every value of an operation on one assignment of its views.
  std::vector<char> evaluate(const HOp& op, uint32_t assignment) const {
    std::vector<char> value(op.num_values, 0);
    for (uint32_t v = 0; v < op.views; ++v) value[1 + v] = (assignment >> v) & 1;
    auto lit = [&](Lit l) -> char { return value[node_of(l)] ^ (is_compl(l) ? 1 : 0); };
    uint32_t next = 1 + op.views;
    for (const HStatement& s : op.statements) {
      if (!s.is_exec) {
        value[next] = lit(s.a) & lit(s.b);
        ++next;
        continue;
      }
      const HOp& callee = ops_[s.callee];
      uint32_t index = 0;
      for (size_t j = 0; j < s.args.size(); ++j) index |= static_cast<uint32_t>(lit(s.args[j])) << j;
      for (int o = 0; o < s.outputs; ++o) value[next + o] = (callee.out_tables[o][index >> 6] >> (index & 63)) & 1;
      next += static_cast<uint32_t>(s.outputs);
    }
    return value;
  }

  void simulate(const HOp& op, std::vector<std::vector<uint64_t>>& sim, int rounds) const {
    auto word = [&](Lit l, int r) { return sim[node_of(l)][r] ^ (is_compl(l) ? ~0ULL : 0); };
    uint32_t next = 1 + op.views;
    for (const HStatement& s : op.statements) {
      if (!s.is_exec) {
        for (int r = 0; r < rounds; ++r) sim[next][r] = word(s.a, r) & word(s.b, r);
        ++next;
        continue;
      }
      const HOp& callee = ops_[s.callee];
      for (int r = 0; r < rounds; ++r)
        for (int b = 0; b < 64; ++b) {
          uint32_t index = 0;
          for (size_t j = 0; j < s.args.size(); ++j) index |= ((word(s.args[j], r) >> b) & 1) << j;
          for (int o = 0; o < s.outputs; ++o)
            if ((callee.out_tables[o][index >> 6] >> (index & 63)) & 1) sim[next + o][r] |= 1ULL << b;
        }
      next += static_cast<uint32_t>(s.outputs);
    }
  }

  // Substitutes OBDDs for a callee's views: walks the callee's OBDD.
  Bdd::Edge compose(const Bdd& from, Bdd::Edge f, const std::vector<Bdd::Edge>& args, Bdd& to,
                    std::unordered_map<uint32_t, Bdd::Edge>& memo) const {
    uint32_t node = f >> 1;
    uint32_t c = f & 1;
    if (node == 0) return Bdd::kTrue ^ c;
    auto it = memo.find(node);
    if (it != memo.end()) return it->second ^ c;
    Bdd::Edge hi = compose(from, from.high(node), args, to, memo);
    Bdd::Edge lo = compose(from, from.low(node), args, to, memo);
    Bdd::Edge x = args[from.level_of(node)];
    // x ? hi : lo
    Bdd::Edge r = to.land(to.land(x, hi) ^ 1, to.land(x ^ 1, lo) ^ 1) ^ 1;
    memo[node] = r;
    return r ^ c;
  }

  void inline_op(size_t i, const std::vector<Lit>& args, Aig& flat, size_t node_limit,
                 std::vector<Lit>* own_values) const {
    const HOp& op = ops_[i];
    std::vector<Lit> value(op.num_values, 0);
    for (uint32_t v = 0; v < op.views; ++v) value[1 + v] = args[v];
    auto lit_of = [&](Lit l) { return value[node_of(l)] ^ (is_compl(l) ? 1u : 0u); };
    uint32_t next = 1 + op.views;
    for (const HStatement& s : op.statements) {
      if (!s.is_exec) {
        flat.fanin0.push_back(lit_of(s.a));
        flat.fanin1.push_back(lit_of(s.b));
        if (flat.num_nodes() > node_limit) throw std::runtime_error("flat graph past the node limit");
        value[next++] = make_lit(flat.num_nodes() - 1);
        continue;
      }
      std::vector<Lit> callee_args;
      for (Lit a : s.args) callee_args.push_back(lit_of(a));
      std::vector<Lit> results;
      inline_op(static_cast<size_t>(s.callee), callee_args, flat, node_limit, nullptr);
      // The callee's written views, from its last inlining.
      for (int o = 0; o < s.outputs; ++o) value[next + o] = last_outputs_[o];
      next += static_cast<uint32_t>(s.outputs);
    }
    last_outputs_.clear();
    for (Lit o : op.outputs) last_outputs_.push_back(lit_of(o));
    if (own_values) *own_values = value;
  }

  std::vector<HOp> ops_;
  mutable std::vector<Lit> last_outputs_;
  uint64_t lookups_ = 0;
};

}  // namespace beq
