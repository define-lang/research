// SAT sweeping (fraiging): random simulation groups nodes that might be equal,
// then nodes are proved equal or different with a SAT solver in topological
// order, and each proved equality is merged into a functionally reduced graph
// so later questions are asked about smaller, shared structure. Each solver
// counterexample becomes a simulation pattern that splits its group.
#pragma once

#include <unistd.h>

#include <cstdio>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include "aig.hpp"
#include "bdd.hpp"
#include "hashmap.hpp"
#include "sat.hpp"
#include "structural.hpp"

namespace beq {

struct SweepParams {
  int sim_rounds = 16;            // 64 random patterns per round
  int64_t conflict_limit = -1;    // per SAT call; negative means run to completion
  uint32_t recycle_vars = 100000;  // start a new solver past this many variables
  uint64_t seed = 1;
  // When positive, a SAT call that reaches this many conflicts is retried with
  // OBDDs of the two cones before going back to SAT without a limit.
  int64_t bdd_rescue_conflicts = 0;
  size_t bdd_rescue_nodes = 1u << 22;
  // When positive, pairs whose cones together read at most this many inputs
  // are decided by simulating every assignment of those inputs instead of SAT.
  uint32_t exhaustive_inputs = 0;
  // Branch only to justify false gates, as circuit SAT solvers do.
  bool justify = false;
  // When positive and the graph has at most this many inputs, a pair that
  // neither SAT (within bdd_rescue_conflicts) nor OBDDs decide makes the
  // sweeper stop and throw SwitchToTruthTables, so the caller can decide the
  // whole graph with truth tables, whose cost depends only on the inputs.
  uint32_t truth_table_fallback_inputs = 0;
  // When set, the last step for a pair is this external solver (run as
  // `SOLVER -q FILE` on the two cones as DIMACS, with temporary files in
  // temp_dir) instead of the built-in solver with no limit.
  std::string external_solver;
  std::string temp_dir = "/tmp";
  // Branch only on variables in the cones of the two nodes being compared.
  bool scope = true;
  uint32_t scope_limit = 4096;
};

struct SwitchToTruthTables {};

class Sweeper {
 public:
  Sweeper(const Aig& g, const SweepParams& p)
      : g_(g), p_(p), rng_(p.seed), classes_(g.num_nodes()), recycle_threshold_(p.recycle_vars) {}

  Classes run(Stats& stats) {
    const uint32_t n = g_.num_nodes();
    hash_.assign(n, 0x51ed);
    phase_.assign(n, 0);
    sim_.assign(n, 0);
    // Random simulation.
    std::vector<uint64_t> input_words(g_.num_inputs + 1);
    for (int r = 0; r < p_.sim_rounds; ++r) {
      for (uint32_t i = 1; i <= g_.num_inputs; ++i) input_words[i] = rng_.next();
      simulate(input_words, r == 0);
    }
    pending_.clear();
    // Functionally reduced graph.
    f_fanin0_.assign(g_.num_inputs + 1, 0);
    f_fanin1_.assign(g_.num_inputs + 1, 0);
    f_strash_ = U64Map(n);
    map_.assign(n, 0);
    f_owner_.assign(g_.num_inputs + 1, 0);
    for (uint32_t v = 0; v <= g_.num_inputs; ++v) {
      map_[v] = make_lit(v);
      f_owner_[v] = v;
    }
    new_solver();
    for (uint32_t v = 0; v <= g_.num_inputs; ++v) add_rep(v);
    for (uint32_t v = g_.num_inputs + 1; v < n; ++v) process(v);
    stats.emplace_back("sat_calls", static_cast<double>(sat_calls_));
    stats.emplace_back("sat_equal", static_cast<double>(sat_equal_));
    stats.emplace_back("sat_different", static_cast<double>(sat_different_));
    stats.emplace_back("sat_undecided", static_cast<double>(sat_undecided_));
    stats.emplace_back("conflicts", static_cast<double>(total_conflicts_ + solver_->conflicts));
    stats.emplace_back("max_call_conflicts", static_cast<double>(max_call_conflicts_));
    stats.emplace_back("strash_merges", static_cast<double>(strash_merges_));
    stats.emplace_back("cex_flushes", static_cast<double>(flushes_));
    stats.emplace_back("pending_skips", static_cast<double>(pending_skips_));
    stats.emplace_back("bdd_rescues", static_cast<double>(bdd_rescues_));
    stats.emplace_back("bdd_rescue_failures", static_cast<double>(bdd_rescue_failures_));
    stats.emplace_back("exhaustive_checks", static_cast<double>(exhaustive_checks_));
    stats.emplace_back("recycles", static_cast<double>(recycles_));
    stats.emplace_back("external_calls", static_cast<double>(external_calls_));
    stats.emplace_back("fraig_nodes", static_cast<double>(f_fanin0_.size()));
    return std::move(classes_);
  }

 private:
  // One round of simulation over the original graph, folded into the hashes.
  void simulate(const std::vector<uint64_t>& input_words, bool set_phase) {
    const uint32_t n = g_.num_nodes();
    sim_[0] = 0;
    for (uint32_t i = 1; i <= g_.num_inputs; ++i) sim_[i] = input_words[i];
    for (uint32_t v = g_.num_inputs + 1; v < n; ++v) {
      uint64_t a = sim_[node_of(g_.fanin0[v])] ^ (is_compl(g_.fanin0[v]) ? ~0ULL : 0);
      uint64_t b = sim_[node_of(g_.fanin1[v])] ^ (is_compl(g_.fanin1[v]) ? ~0ULL : 0);
      sim_[v] = a & b;
    }
    for (uint32_t v = 0; v < n; ++v) {
      if (set_phase) phase_[v] = sim_[v] & 1;
      uint64_t word = phase_[v] ? ~sim_[v] : sim_[v];
      hash_[v] = mix64(hash_[v] ^ word);
    }
  }

  void add_rep(uint32_t v) {
    buckets_[hash_[v]].push_back(v);
    reps_.push_back(v);
  }

  // Simulates the pending counterexamples (up to 64) and rebuilds the groups.
  void flush_pending() {
    if (pending_.empty()) return;
    ++flushes_;
    std::vector<uint64_t> input_words(g_.num_inputs + 1, 0);
    for (size_t k = 0; k < 64; ++k) {
      // Unused bits repeat the first pattern so they never split a group.
      const std::vector<char>& pattern = pending_[k < pending_.size() ? k : 0];
      for (uint32_t i = 1; i <= g_.num_inputs; ++i)
        if (pattern[i]) input_words[i] |= 1ULL << k;
    }
    simulate(input_words, false);
    pending_.clear();
    ++pending_stamp_;
    buckets_.clear();
    for (uint32_t r : reps_) buckets_[hash_[r]].push_back(r);
  }

  // Value of node v on the pending patterns, as one word.
  uint64_t pending_value(uint32_t v) {
    if (pending_eval_stamp_.size() != g_.num_nodes()) {
      pending_eval_stamp_.assign(g_.num_nodes(), 0);
      pending_word_.assign(g_.num_nodes(), 0);
    }
    uint64_t stamp = (pending_stamp_ << 8) | pending_.size();
    if (pending_eval_stamp_[v] == stamp) return pending_word_[v];
    stack_.clear();
    stack_.push_back(v);
    while (!stack_.empty()) {
      uint32_t u = stack_.back();
      if (pending_eval_stamp_[u] == stamp) {
        stack_.pop_back();
        continue;
      }
      if (u <= g_.num_inputs) {
        uint64_t w = 0;
        if (u != 0)
          for (size_t k = 0; k < pending_.size(); ++k)
            if (pending_[k][u]) w |= 1ULL << k;
        pending_word_[u] = w;
        pending_eval_stamp_[u] = stamp;
        stack_.pop_back();
        continue;
      }
      uint32_t a = node_of(g_.fanin0[u]), b = node_of(g_.fanin1[u]);
      bool ready = true;
      if (pending_eval_stamp_[a] != stamp) {
        stack_.push_back(a);
        ready = false;
      }
      if (pending_eval_stamp_[b] != stamp) {
        stack_.push_back(b);
        ready = false;
      }
      if (!ready) continue;
      uint64_t wa = pending_word_[a] ^ (is_compl(g_.fanin0[u]) ? ~0ULL : 0);
      uint64_t wb = pending_word_[b] ^ (is_compl(g_.fanin1[u]) ? ~0ULL : 0);
      pending_word_[u] = wa & wb;
      pending_eval_stamp_[u] = stamp;
      stack_.pop_back();
    }
    return pending_word_[v];
  }

  Lit f_and(Lit a, Lit b) {
    Lit r = trivial_and(a, b);
    if (r != UINT32_MAX) return r;
    if (a > b) std::swap(a, b);
    uint32_t next = static_cast<uint32_t>(f_fanin0_.size());
    auto [slot, inserted] = f_strash_.insert((static_cast<uint64_t>(a) << 32) | b, next);
    if (inserted) {
      f_fanin0_.push_back(a);
      f_fanin1_.push_back(b);
      f_owner_.push_back(UINT32_MAX);
    }
    return make_lit(*slot);
  }

  void process(uint32_t v) {
    Lit a = map_[node_of(g_.fanin0[v])] ^ is_compl(g_.fanin0[v]);
    Lit b = map_[node_of(g_.fanin1[v])] ^ is_compl(g_.fanin1[v]);
    Lit f = f_and(a, b);
    map_[v] = f;
    uint32_t fn = node_of(f);
    if (f_owner_[fn] != UINT32_MAX) {
      // Structural hashing or a trivial rule found it.
      ++strash_merges_;
      uint32_t owner = f_owner_[fn];
      classes_.merge(v, owner, is_compl(f));
      map_[v] = map_[owner] ^ is_compl(f);
      return;
    }
    f_owner_[fn] = v;
    for (bool restart = true; restart;) {
      restart = false;
      auto it = buckets_.find(hash_[v]);
      if (it == buckets_.end()) break;
      // Copy, since a flush rebuilds the buckets.
      std::vector<uint32_t> candidates = it->second;
      for (uint32_t r : candidates) {
        bool ph = phase_[v] ^ phase_[r];
        if (!pending_.empty()) {
          uint64_t mask = pending_.size() == 64 ? ~0ULL : ((1ULL << pending_.size()) - 1);
          uint64_t diff = (pending_value(v) ^ pending_value(r) ^ (ph ? ~0ULL : 0)) & mask;
          if (diff) {
            ++pending_skips_;
            continue;
          }
        }
        Lit target = map_[r] ^ ph;
        int result = decide(f, target);
        if (result == 1) {
          classes_.merge(v, r, ph);
          map_[v] = target;
          return;
        }
        if (result == 0 && pending_.size() == 64) {
          flush_pending();
          restart = true;
          break;
        }
      }
    }
    add_rep(v);
  }

  // 1: equal, 0: different (a counterexample was recorded), -1: undecided.
  int decide(Lit x, Lit y) {
    if (p_.exhaustive_inputs > 0) {
      int r = exhaustive_check(x, y);
      if (r >= 0) return r;
    }
    int64_t limit = p_.conflict_limit;
    if (p_.bdd_rescue_conflicts > 0) limit = p_.bdd_rescue_conflicts;
    int r = sat_check(x, y, limit);
    if (r == -1 && p_.bdd_rescue_conflicts > 0) {
      ++bdd_rescues_;
      r = bdd_check(x, y);
      if (r == -1) {
        ++bdd_rescue_failures_;
        if (g_.num_inputs <= p_.truth_table_fallback_inputs) throw SwitchToTruthTables();
        if (!p_.external_solver.empty()) {
          ++external_calls_;
          r = external_check(x, y);
        } else {
          r = sat_check(x, y, p_.conflict_limit);
        }
      }
    }
    if (r == -1) ++sat_undecided_;
    return r;
  }

  void new_solver() {
    if (solver_) total_conflicts_ += solver_->conflicts;
    solver_ = std::make_unique<sat::Solver>();
    sat_var_.assign(f_fanin0_.size(), UINT32_MAX);
    // Node 0 is false.
    sat_var_[0] = solver_->new_var();
    solver_->add_clause({sat::neg(sat_var_[0])});
  }

  sat::Lit sat_lit(Lit l) { return 2 * sat_var_[node_of(l)] + is_compl(l); }

  // Limits the solver's decisions to the cones of x and y, unless the cones
  // are larger than scope_limit nodes, when walking them would cost more than
  // the decisions it saves.
  void set_scope(Lit x, Lit y) {
    ++cone_epoch_;
    if (cone_mark_.size() < f_fanin0_.size()) cone_mark_.resize(f_fanin0_.size(), 0);
    scope_.clear();
    stack_.clear();
    stack_.push_back(node_of(x));
    stack_.push_back(node_of(y));
    while (!stack_.empty()) {
      uint32_t u = stack_.back();
      stack_.pop_back();
      if (cone_mark_[u] == cone_epoch_) continue;
      cone_mark_[u] = cone_epoch_;
      scope_.push_back(sat_var_[u]);
      if (scope_.size() > p_.scope_limit) {
        scope_.clear();
        break;
      }
      if (u > g_.num_inputs) {
        stack_.push_back(node_of(f_fanin0_[u]));
        stack_.push_back(node_of(f_fanin1_[u]));
      }
    }
    solver_->set_scope(scope_);
  }

  void encode_cone(uint32_t root) {
    if (sat_var_.size() < f_fanin0_.size()) sat_var_.resize(f_fanin0_.size(), UINT32_MAX);
    stack_.clear();
    stack_.push_back(root);
    while (!stack_.empty()) {
      uint32_t u = stack_.back();
      if (sat_var_[u] != UINT32_MAX) {
        stack_.pop_back();
        continue;
      }
      if (u <= g_.num_inputs) {
        sat_var_[u] = solver_->new_var();
        stack_.pop_back();
        continue;
      }
      uint32_t a = node_of(f_fanin0_[u]), b = node_of(f_fanin1_[u]);
      bool ready = true;
      if (sat_var_[a] == UINT32_MAX) {
        stack_.push_back(a);
        ready = false;
      }
      if (sat_var_[b] == UINT32_MAX) {
        stack_.push_back(b);
        ready = false;
      }
      if (!ready) continue;
      uint32_t z = sat_var_[u] = solver_->new_var();
      sat::Lit la = sat_lit(f_fanin0_[u]), lb = sat_lit(f_fanin1_[u]);
      solver_->add_clause({sat::neg(z), la});
      solver_->add_clause({sat::neg(z), lb});
      solver_->add_clause({sat::pos(z), la ^ 1, lb ^ 1});
      if (p_.justify) solver_->set_gate(z, la, lb);
      stack_.pop_back();
    }
  }

  int sat_check(Lit x, Lit y, int64_t limit) {
    // A solver holding the whole graph makes every call slower, so start a
    // new one once it's large. The next threshold is four times what the
    // first question after that needs, so when questions need cones that span
    // the graph, re-encoding them doesn't happen again and again.
    bool fresh = false;
    if (solver_->num_vars() > recycle_threshold_) {
      ++recycles_;
      new_solver();
      fresh = true;
    }
    encode_cone(node_of(x));
    encode_cone(node_of(y));
    if (fresh) recycle_threshold_ = std::max<size_t>(p_.recycle_vars, 4 * size_t{solver_->num_vars()});
    if (p_.scope) set_scope(x, y);
    sat::Lit sx = sat_lit(x), sy = sat_lit(y);
    // x and not y, then not x and y.
    for (int side = 0; side < 2; ++side) {
      std::vector<sat::Lit> assumptions = side == 0 ? std::vector<sat::Lit>{sx, sy ^ 1}
                                                    : std::vector<sat::Lit>{sx ^ 1, sy};
      ++sat_calls_;
      uint64_t before = solver_->conflicts;
      sat::Result res = solver_->solve(assumptions, limit);
      max_call_conflicts_ = std::max<uint64_t>(max_call_conflicts_, solver_->conflicts - before);
      if (res == sat::Result::kUnknown) return -1;
      if (res == sat::Result::kSat) {
        record_counterexample();
        ++sat_different_;
        return 0;
      }
    }
    ++sat_equal_;
    solver_->add_clause({sx ^ 1, sy});
    solver_->add_clause({sx, sy ^ 1});
    return 1;
  }

  void record_counterexample() {
    std::vector<char> pattern(g_.num_inputs + 1, 0);
    for (uint32_t i = 1; i <= g_.num_inputs; ++i) {
      if (i < sat_var_.size() && sat_var_[i] != UINT32_MAX && solver_->model_defined(sat_var_[i]))
        pattern[i] = solver_->model_value(sat_var_[i]);
      else
        pattern[i] = rng_.next() & 1;
    }
    add_pattern(std::move(pattern));
  }

  void add_pattern(std::vector<char> pattern) { pending_.push_back(std::move(pattern)); }

  // Nodes of the reduced graph in the cones of x and y, in topological order.
  // Stops early, with more than max_inputs inputs or more than max_nodes
  // nodes, once the cones have that many.
  std::vector<uint32_t> cone(Lit x, Lit y, std::vector<uint32_t>& inputs, size_t max_inputs = SIZE_MAX,
                             size_t max_nodes = SIZE_MAX) {
    std::vector<uint32_t> nodes;
    if (walk_mark_.size() < f_fanin0_.size()) walk_mark_.resize(f_fanin0_.size(), 0);
    ++walk_epoch_;
    stack_.clear();
    stack_.push_back(node_of(x));
    stack_.push_back(node_of(y));
    while (!stack_.empty()) {
      uint32_t u = stack_.back();
      stack_.pop_back();
      if (walk_mark_[u] == walk_epoch_) continue;
      walk_mark_[u] = walk_epoch_;
      if (u == 0) continue;
      if (u <= g_.num_inputs) {
        inputs.push_back(u);
        if (inputs.size() > max_inputs) return nodes;
        continue;
      }
      nodes.push_back(u);
      if (nodes.size() > max_nodes) {
        inputs.resize(max_inputs == SIZE_MAX ? inputs.size() : max_inputs + 1);
        return nodes;
      }
      stack_.push_back(node_of(f_fanin0_[u]));
      stack_.push_back(node_of(f_fanin1_[u]));
    }
    std::sort(nodes.begin(), nodes.end());
    std::sort(inputs.begin(), inputs.end());
    return nodes;
  }

  int bdd_check(Lit x, Lit y) {
    std::vector<uint32_t> inputs;
    std::vector<uint32_t> nodes = cone(x, y, inputs);
    // Order the cone's inputs by first use in the reduced graph's order.
    std::vector<uint32_t> level(g_.num_inputs + 1, UINT32_MAX);
    uint32_t next_level = 0;
    for (uint32_t u : nodes)
      for (Lit f : {f_fanin0_[u], f_fanin1_[u]}) {
        uint32_t w = node_of(f);
        if (w >= 1 && w <= g_.num_inputs && level[w] == UINT32_MAX) level[w] = next_level++;
      }
    Bdd bdd(next_level, p_.bdd_rescue_nodes);
    std::unordered_map<uint32_t, Bdd::Edge> edge;
    edge[0] = Bdd::kFalse;
    try {
      for (uint32_t w : inputs) edge[w] = bdd.var(level[w]);
      for (uint32_t u : nodes)
        edge[u] = bdd.land(edge[node_of(f_fanin0_[u])] ^ is_compl(f_fanin0_[u]),
                           edge[node_of(f_fanin1_[u])] ^ is_compl(f_fanin1_[u]));
    } catch (const BddLimit&) {
      return -1;
    }
    Bdd::Edge ex = edge[node_of(x)] ^ is_compl(x), ey = edge[node_of(y)] ^ is_compl(y);
    if (ex == ey) return 1;
    // Different: find a distinguishing pattern with SAT, which is easy now that
    // the answer is known to be satisfiable, but can still be slow; instead walk
    // the BDD of x xor y.
    Bdd::Edge d;
    try {
      d = bdd.land(ex, ey ^ 1);
      if (d == Bdd::kFalse) d = bdd.land(ex ^ 1, ey);
    } catch (const BddLimit&) {
      // Known to differ, but building the difference hit the limit; SAT will
      // find the counterexample.
      return -1;
    }
    std::vector<char> pattern(g_.num_inputs + 1, 0);
    for (uint32_t i = 1; i <= g_.num_inputs; ++i) pattern[i] = rng_.next() & 1;
    std::vector<uint32_t> input_at_level(next_level);
    for (uint32_t w : inputs) input_at_level[level[w]] = w;
    bdd.satisfying_path(d, [&](uint32_t lv, bool value) { pattern[input_at_level[lv]] = value; });
    add_pattern(std::move(pattern));
    return 0;
  }

  // Decides x == y with an external solver on the CNF of the two cones.
  int external_check(Lit x, Lit y) {
    std::vector<uint32_t> inputs;
    std::vector<uint32_t> nodes = cone(x, y, inputs);
    std::unordered_map<uint32_t, int64_t> var;
    int64_t next = 0;
    var[0] = ++next;
    for (uint32_t w : inputs) var[w] = ++next;
    for (uint32_t u : nodes) var[u] = ++next;
    auto lit = [&](Lit l) { return (is_compl(l) ? -1 : 1) * var.at(node_of(l)); };
    std::ostringstream cnf;
    size_t clauses = 0;
    cnf << -var[0] << " 0\n";
    ++clauses;
    for (uint32_t u : nodes) {
      int64_t z = var[u], a = lit(f_fanin0_[u]), b = lit(f_fanin1_[u]);
      cnf << -z << " " << a << " 0\n" << -z << " " << b << " 0\n" << z << " " << -a << " " << -b << " 0\n";
      clauses += 3;
    }
    cnf << lit(x) << " " << lit(y) << " 0\n" << -lit(x) << " " << -lit(y) << " 0\n";
    clauses += 2;
    std::string path = p_.temp_dir + "/beq_XXXXXX";
    int fd = mkstemp(path.data());
    if (fd < 0) throw std::runtime_error("cannot create a temporary file in " + p_.temp_dir);
    close(fd);
    {
      std::ofstream out(path);
      out << "p cnf " << next << " " << clauses << "\n" << cnf.str();
    }
    std::string command = p_.external_solver + " -q " + path;
    FILE* pipe = popen(command.c_str(), "r");
    if (pipe == nullptr) throw std::runtime_error("cannot run " + p_.external_solver);
    std::string output;
    char buffer[65536];
    for (size_t n; (n = fread(buffer, 1, sizeof buffer, pipe)) > 0;) output.append(buffer, n);
    int status = pclose(pipe);
    std::remove(path.c_str());
    int code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
    if (code == 20) {
      ++sat_equal_;
      return 1;
    }
    if (code != 10) throw std::runtime_error("external solver failed: " + command);
    // A counterexample: read the input values from the `v` lines.
    std::unordered_map<int64_t, bool> value;
    std::istringstream lines(output);
    for (std::string line; std::getline(lines, line);) {
      if (line.rfind("v ", 0) != 0) continue;
      std::istringstream literals(line.substr(2));
      for (int64_t l; literals >> l && l != 0;) value[l > 0 ? l : -l] = l > 0;
    }
    std::vector<char> pattern(g_.num_inputs + 1, 0);
    for (uint32_t i = 1; i <= g_.num_inputs; ++i) {
      auto it = var.find(i);
      pattern[i] = it != var.end() && value.count(it->second) ? value[it->second] : (rng_.next() & 1);
    }
    add_pattern(std::move(pattern));
    ++sat_different_;
    return 0;
  }

  int exhaustive_check(Lit x, Lit y) {
    std::vector<uint32_t> inputs;
    // Cones that read few inputs but have many nodes are rare, and walking
    // a large cone for every pair costs more than exhaustive simulation saves.
    std::vector<uint32_t> nodes = cone(x, y, inputs, p_.exhaustive_inputs, 512);
    if (inputs.size() > p_.exhaustive_inputs) return -1;
    ++exhaustive_checks_;
    const uint32_t k = static_cast<uint32_t>(inputs.size());
    const size_t words = k <= 6 ? 1 : (size_t{1} << (k - 6));
    // Each node's table is a slice of one buffer; slot 0 is constant false.
    if (slot_of_.size() < f_fanin0_.size()) slot_of_.resize(f_fanin0_.size(), 0);
    table_.assign((1 + k + nodes.size()) * words, 0);
    auto slice = [&](uint32_t slot) { return &table_[slot * words]; };
    slot_of_[0] = 0;
    static const uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                     0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
    for (uint32_t j = 0; j < k; ++j) {
      slot_of_[inputs[j]] = 1 + j;
      uint64_t* t = slice(1 + j);
      for (size_t w = 0; w < words; ++w) t[w] = j < 6 ? kVar[j] : (((w >> (j - 6)) & 1) ? ~0ULL : 0);
    }
    for (size_t i = 0; i < nodes.size(); ++i) {
      uint32_t u = nodes[i];
      uint32_t slot = static_cast<uint32_t>(1 + k + i);
      slot_of_[u] = slot;
      const uint64_t* a = slice(slot_of_[node_of(f_fanin0_[u])]);
      const uint64_t* b = slice(slot_of_[node_of(f_fanin1_[u])]);
      uint64_t fa = is_compl(f_fanin0_[u]) ? ~0ULL : 0, fb = is_compl(f_fanin1_[u]) ? ~0ULL : 0;
      uint64_t* r = slice(slot);
      for (size_t w = 0; w < words; ++w) r[w] = (a[w] ^ fa) & (b[w] ^ fb);
    }
    const uint64_t mask = k >= 6 ? ~0ULL : ((1ULL << (1u << k)) - 1);
    const uint64_t* tx = slice(slot_of_[node_of(x)]);
    const uint64_t* ty = slice(slot_of_[node_of(y)]);
    uint64_t fx = is_compl(x) ? ~0ULL : 0, fy = is_compl(y) ? ~0ULL : 0;
    for (size_t w = 0; w < words; ++w) {
      uint64_t d = ((tx[w] ^ fx) ^ (ty[w] ^ fy)) & mask;
      if (d) {
        uint64_t minterm = w * 64 + static_cast<uint64_t>(__builtin_ctzll(d));
        std::vector<char> pattern(g_.num_inputs + 1, 0);
        for (uint32_t i = 1; i <= g_.num_inputs; ++i) pattern[i] = rng_.next() & 1;
        for (uint32_t j = 0; j < k; ++j) pattern[inputs[j]] = (minterm >> j) & 1;
        add_pattern(std::move(pattern));
        return 0;
      }
    }
    return 1;
  }

  const Aig& g_;
  SweepParams p_;
  Rng rng_;
  Classes classes_;
  std::vector<uint64_t> hash_;
  std::vector<char> phase_;
  std::vector<uint64_t> sim_;
  std::unordered_map<uint64_t, std::vector<uint32_t>> buckets_;
  std::vector<uint32_t> reps_;
  std::vector<std::vector<char>> pending_;
  uint64_t pending_stamp_ = 1;
  std::vector<uint64_t> pending_eval_stamp_;
  std::vector<uint64_t> pending_word_;
  std::vector<uint32_t> stack_;
  std::vector<Lit> f_fanin0_, f_fanin1_;
  std::vector<uint32_t> f_owner_;  // original node a reduced node stands for
  U64Map f_strash_;
  std::vector<Lit> map_;
  std::unique_ptr<sat::Solver> solver_;
  std::vector<uint32_t> sat_var_;
  std::vector<uint32_t> cone_mark_, scope_;
  size_t recycle_threshold_ = 0;
  std::vector<uint32_t> walk_mark_, slot_of_;
  uint32_t walk_epoch_ = 0;
  std::vector<uint64_t> table_;
  uint32_t cone_epoch_ = 0;
  uint64_t sat_calls_ = 0, sat_equal_ = 0, sat_different_ = 0, sat_undecided_ = 0;
  uint64_t total_conflicts_ = 0, max_call_conflicts_ = 0, strash_merges_ = 0, flushes_ = 0;
  uint64_t pending_skips_ = 0, bdd_rescues_ = 0, bdd_rescue_failures_ = 0, exhaustive_checks_ = 0;
  uint64_t recycles_ = 0;
  uint64_t external_calls_ = 0;
};

}  // namespace beq
