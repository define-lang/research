// Finding written-out registered operations ("matches", DLP 57) two ways:
//
// - cuts: DLP 57's definition. Every cut of at most K values of each
//   statement's value, at the level of statements, with its truth table
//   compared with the registered operations up to view order.
// - exact: a value matches a registered operation R when, as a function of
//   the value operation's inputs, it equals R applied to values in its cone.
//   For each R, the search gives values to R's views one at a time, prunes a
//   partial assignment as soon as some sampled input assignment makes v's
//   value unreachable, finds the last view's value where R depends on it by
//   a scan, and checks each candidate on the full truth tables. Pruning on
//   samples only uses necessary conditions, so nothing is missed, and a
//   candidate that fails the full check adds an input assignment to the
//   sample.
//
// Both report the same kind of match: (value, operation, arguments in view
// order). An execution of R on the same arguments is not a match.
#pragma once

#include <algorithm>
#include <array>
#include <fstream>
#include <functional>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include "aig.hpp"
#include "structural.hpp"

namespace beq {

struct Registered {
  std::string name;
  uint32_t arity;
  uint64_t table;  // bit m for minterm m, view i is bit i of m
};

inline std::vector<Registered> standard_registered() {
  auto table = [](uint32_t arity, auto f) {
    uint64_t t = 0;
    for (uint32_t m = 0; m < (1u << arity); ++m)
      if (f(m)) t |= 1ULL << m;
    return t;
  };
  auto bit = [](uint32_t m, int i) { return (m >> i) & 1; };
  return {
      {"or", 2, table(2, [&](uint32_t m) { return bit(m, 0) | bit(m, 1); })},
      {"xor", 2, table(2, [&](uint32_t m) { return bit(m, 0) ^ bit(m, 1); })},
      {"eq", 2, table(2, [&](uint32_t m) { return 1 - (bit(m, 0) ^ bit(m, 1)); })},
      {"implies", 2, table(2, [&](uint32_t m) { return (1 - bit(m, 0)) | bit(m, 1); })},
      {"mux", 3, table(3, [&](uint32_t m) { return bit(m, 0) ? bit(m, 1) : bit(m, 2); })},
      {"maj", 3, table(3, [&](uint32_t m) { return bit(m, 0) + bit(m, 1) + bit(m, 2) >= 2; })},
  };
}

// Random registered operations of a given arity that depend on every view,
// for measuring how the cost grows with the arity limit. They almost never
// match anything; only the time matters.
inline void add_random_registered(std::vector<Registered>& out, uint32_t arity, uint32_t count, uint64_t seed) {
  Rng rng(seed);
  const uint64_t mask = arity >= 6 ? ~0ULL : ((1ULL << (1u << arity)) - 1);
  while (count > 0) {
    uint64_t t = rng.next() & mask;
    bool depends = true;
    for (uint32_t v = 0; v < arity && depends; ++v) {
      uint64_t lo = 0, hi = 0;
      for (uint32_t m = 0; m < (1u << arity); ++m) {
        if ((m >> v) & 1)
          hi |= ((t >> m) & 1) << (m & ~(1u << v));
        else
          lo |= ((t >> m) & 1) << m;
      }
      depends = lo != hi;
    }
    if (!depends) continue;
    out.push_back({"random" + std::to_string(arity) + "_" + std::to_string(count), arity, t});
    --count;
  }
}

struct Statement {
  Lit lit;
  std::string op;
  std::vector<Lit> args;
};

struct Match {
  Lit value;
  std::string op;
  std::vector<Lit> args;  // in view order
  bool operator<(const Match& o) const {
    return std::tie(value, op, args) < std::tie(o.value, o.op, o.args);
  }
};

inline std::vector<Statement> read_statements(const std::string& path) {
  std::vector<Statement> out;
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open " + path);
  for (std::string line; std::getline(in, line);) {
    std::istringstream words(line);
    Statement s;
    words >> s.lit >> s.op;
    for (Lit a; words >> a;) s.args.push_back(a);
    out.push_back(s);
  }
  // Statement order is node order in the reordered graph.
  std::stable_sort(out.begin(), out.end(),
                   [](const Statement& a, const Statement& b) { return node_of(a.lit) < node_of(b.lit); });
  return out;
}

// Minterm m of the table of a permuted operation: view i of R takes the
// value of position perm[i] of the set.
inline bool permuted_bit(const Registered& r, const std::vector<int>& perm, uint32_t combo) {
  uint32_t index = 0;
  for (uint32_t i = 0; i < r.arity; ++i) index |= ((combo >> perm[i]) & 1) << i;
  return (r.table >> index) & 1;
}

// Every permutation of 0..k-1.
inline std::vector<std::vector<int>> permutations(uint32_t k) {
  std::vector<int> p(k);
  std::iota(p.begin(), p.end(), 0);
  std::vector<std::vector<int>> out;
  do out.push_back(p);
  while (std::next_permutation(p.begin(), p.end()));
  return out;
}

class Matcher {
 public:
  Matcher(const Aig& g, std::vector<Statement> statements, std::vector<Registered> registered)
      : g_(g), statements_(std::move(statements)), registered_(std::move(registered)) {
    for (const Registered& r : registered_) max_arity_ = std::max(max_arity_, r.arity);
    for (size_t i = 0; i < statements_.size(); ++i) by_lit_[statements_[i].lit] = i;
    for (const Statement& s : statements_)
      for (const Registered& r : registered_)
        if (s.op == r.name) executions_.insert({s.lit, s.op, s.args});
  }

  // How the arguments of an exact match must relate to the value: "cone"
  // (in its statement-level cone), "support" (any available value whose
  // inputs are among the value's), or "any" (any available value).
  void set_anchor(const std::string& anchor) { anchor_ = anchor; }
  // The largest cut, in values (DLP 57: four).
  void set_cut_size(uint32_t k) { cut_size_ = k; }

  // Rewrites each match's arguments to the first available literal with the
  // same function, so matches from both methods, and the planted ones, can be
  // compared. Not part of either method's time.
  std::set<Match> canonical(const std::set<Match>& in) {
    ensure_tables();
    std::map<uint64_t, Lit> first;
    auto note = [&](Lit l) { first.try_emplace(table_hash(l), l); };
    for (uint32_t i = 1; i <= g_.num_inputs; ++i) note(make_lit(i));
    for (const Statement& s : statements_) {
      for (Lit a : s.args) note(a);
      note(s.lit);
    }
    std::set<Match> out;
    for (Match m : in) {
      for (Lit& a : m.args) a = first.at(table_hash(a));
      std::sort(m.args.begin(), m.args.end());
      out.insert(m);
    }
    return out;
  }

  // DLP 57's cut definition, at the level of statements. With with_values,
  // the arguments of R can also be any available values that are functions
  // of a subset of the cut's values: v's table over the cut must equal R of
  // their tables over the cut.
  std::set<Match> run_cuts(Stats& stats, bool with_values = false, bool negated_leaves = false) {
    struct StCut {
      std::vector<Lit> leaves;  // sorted
      uint64_t table;           // over the leaves in order
    };
    std::map<Lit, std::vector<StCut>> cuts;  // by positive or negative literal of a value
    auto cuts_of = [&](Lit l) -> std::vector<StCut> {
      auto it = cuts.find(l);
      if (it != cuts.end()) return it->second;
      // An input. A negated input is the value of a `not` statement: its own
      // cut, and the input's with the negated table.
      if (is_compl(l)) return {StCut{{l}, 0x2}, StCut{{l ^ 1}, 0x1}};
      return {StCut{{l}, 0x2}};
    };
    auto expand = [](const StCut& c, const std::vector<Lit>& leaves) {
      uint64_t out = 0;
      std::vector<int> pos(c.leaves.size());
      for (size_t i = 0; i < c.leaves.size(); ++i)
        pos[i] = static_cast<int>(std::find(leaves.begin(), leaves.end(), c.leaves[i]) - leaves.begin());
      for (uint32_t m = 0; m < (1u << leaves.size()); ++m) {
        uint32_t idx = 0;
        for (size_t i = 0; i < pos.size(); ++i) idx |= ((m >> pos[i]) & 1) << i;
        if ((c.table >> idx) & 1) out |= 1ULL << m;
      }
      return out;
    };
    std::set<Match> found;
    size_t total = 0;
    // For with_values: the literals available so far, and each one's cuts by
    // leaf set.
    std::set<Lit> available;
    std::map<std::vector<Lit>, std::vector<std::pair<Lit, uint64_t>>> by_leaves;
    auto make_available = [&](Lit l) {
      if (!available.insert(l).second) return;
      for (const StCut& c : cuts_of(l)) by_leaves[c.leaves].push_back({l, c.table});
    };
    if (with_values || negated_leaves)
      for (uint32_t i = 1; i <= g_.num_inputs; ++i) make_available(make_lit(i));
    for (const Statement& s : statements_) {
      if (with_values || negated_leaves)
        for (Lit a : s.args) make_available(a);
      std::vector<std::vector<StCut>> arg_cuts;
      for (Lit a : s.args) arg_cuts.push_back(cuts_of(a));
      std::vector<StCut> out;
      // Every combination of one cut per argument with at most K leaves.
      std::vector<size_t> pick(s.args.size(), 0);
      for (;;) {
        std::vector<Lit> leaves;
        for (size_t i = 0; i < s.args.size(); ++i)
          for (Lit l : arg_cuts[i][pick[i]].leaves) leaves.push_back(l);
        std::sort(leaves.begin(), leaves.end());
        leaves.erase(std::unique(leaves.begin(), leaves.end()), leaves.end());
        if (leaves.size() <= cut_size_) {
          bool duplicate = false;
          for (const StCut& c : out) duplicate |= c.leaves == leaves;
          if (!duplicate) {
            std::vector<uint64_t> arg_tables;
            for (size_t i = 0; i < s.args.size(); ++i) arg_tables.push_back(expand(arg_cuts[i][pick[i]], leaves));
            uint64_t t = 0;
            for (uint32_t m = 0; m < (1u << leaves.size()); ++m) {
              uint32_t combo = 0;
              for (size_t i = 0; i < arg_tables.size(); ++i) combo |= ((arg_tables[i] >> m) & 1) << i;
              if (evaluate(s.op, combo, static_cast<uint32_t>(s.args.size()))) t |= 1ULL << m;
            }
            out.push_back({leaves, t});
            if (leaves.size() >= 2) check_cut(s.lit, leaves, t, found, negated_leaves ? &available : nullptr);
            if (with_values && leaves.size() >= 2) {
              // Candidates: available values with a cut inside these leaves.
              std::vector<std::pair<Lit, uint64_t>> candidates;
              std::set<uint64_t> tables;
              for (uint32_t subset = 1; subset < (1u << leaves.size()); ++subset) {
                std::vector<Lit> sub;
                for (size_t i = 0; i < leaves.size(); ++i)
                  if ((subset >> i) & 1) sub.push_back(leaves[i]);
                auto it = by_leaves.find(sub);
                if (it == by_leaves.end()) continue;
                for (auto [lit, table] : it->second) {
                  if (node_of(lit) == node_of(s.lit)) continue;
                  uint64_t over = expand(StCut{sub, table}, leaves);
                  if (tables.insert(over).second) candidates.push_back({lit, over});
                }
              }
              ++value_cuts_;
              value_candidates_ += candidates.size();
              match_values(s.lit, leaves, t, candidates, found);
            }
          }
        }
        size_t i = 0;
        while (i < pick.size() && ++pick[i] == arg_cuts[i].size()) pick[i++] = 0;
        if (i == pick.size()) break;
      }
      out.push_back({{s.lit}, 0x2});
      total += out.size();
      // The complemented literal of a value has the complemented tables.
      std::vector<StCut> negated;
      for (const StCut& c : out) {
        uint64_t mask = c.leaves.size() >= 6 ? ~0ULL : ((1ULL << (1u << c.leaves.size())) - 1);
        negated.push_back({c.leaves, ~c.table & mask});
      }
      // The negation of a value is the value of a `not` statement, with a cut
      // holding only itself.
      negated.push_back({{s.lit ^ 1}, 0x2});
      cuts[s.lit] = std::move(out);
      cuts[s.lit ^ 1] = std::move(negated);
      if (with_values || negated_leaves) make_available(s.lit);
    }
    stats.emplace_back("total_cuts", static_cast<double>(total));
    if (with_values) {
      stats.emplace_back("value_cuts", static_cast<double>(value_cuts_));
      stats.emplace_back("value_candidates", static_cast<double>(value_candidates_));
      stats.emplace_back("value_tuples", static_cast<double>(value_tuples_));
    }
    return found;
  }

  // The exact definition. Requires truth tables over every input.
  std::set<Match> run_exact(Stats& stats) {
    const uint32_t I = g_.num_inputs;
    if (I > 20) throw std::runtime_error("exact matching needs at most 20 inputs");
    ensure_tables();
    // Values available before each statement: inputs, values statements
    // computed, and literals statements were given (which covers `not x`).
    std::vector<Lit> available;
    std::set<uint64_t> seen;
    auto add = [&](Lit l) {
      uint64_t h = table_hash(l);
      if (seen.insert(h).second) available.push_back(l);
    };
    for (uint32_t i = 1; i <= I; ++i) add(make_lit(i));
    std::set<Match> found;
    for (const Statement& s : statements_) {
      for (Lit a : s.args) add(a);
      search(s.lit, available, found);
      add(s.lit);
    }
    stats.emplace_back("search_nodes", static_cast<double>(search_nodes_));
    stats.emplace_back("exact_checks", static_cast<double>(exact_checks_));
    stats.emplace_back("refinements", static_cast<double>(refinements_));
    stats.emplace_back("inessential", static_cast<double>(inessential_));
    return found;
  }

 private:
  static bool evaluate(const std::string& op, uint32_t combo, uint32_t n) {
    auto bit = [&](int i) { return (combo >> i) & 1; };
    if (op == "not") return !bit(0);
    if (op == "and" || op == "and3") return combo == (1u << n) - 1;
    if (op == "or3") return combo != 0;
    if (op == "or") return bit(0) | bit(1);
    if (op == "xor") return bit(0) ^ bit(1);
    if (op == "eq") return !(bit(0) ^ bit(1));
    if (op == "implies") return !bit(0) || bit(1);
    if (op == "mux") return bit(0) ? bit(1) : bit(2);
    if (op == "maj") return bit(0) + bit(1) + bit(2) >= 2;
    throw std::runtime_error("unknown operation " + op);
  }

  // The statements a match replaces: those reached from the value without
  // passing through an argument, counting a `not` for each negated value
  // given to one of them. Returns 0 if some argument isn't reached, since a
  // match is a group of statements computing the value from its arguments.
  size_t group_size(Lit value, const std::vector<Lit>& args, bool all_reached) const {
    std::set<Lit> stop(args.begin(), args.end()), seen, reached;
    std::vector<Lit> stack{value};
    size_t count = 0;
    while (!stack.empty()) {
      Lit l = stack.back();
      stack.pop_back();
      if (stop.count(l)) {
        reached.insert(l);
        continue;
      }
      if (!seen.insert(l).second) continue;
      auto it = by_lit_.find(l);
      if (it != by_lit_.end()) {
        ++count;
        for (Lit a : statements_[it->second].args) stack.push_back(a);
      } else if (by_lit_.count(l ^ 1) || (is_compl(l) && node_of(l) <= g_.num_inputs)) {
        // The `not` of a value a statement computes, or of an input.
        ++count;
        stack.push_back(l ^ 1);
      }
    }
    return !all_reached || reached.size() == stop.size() ? count : 0;
  }

  // stop: the values the match's statements read, when they aren't the
  // arguments themselves (a negated cut leaf given as its `not`).
  void record(Lit value, const Registered& r, std::vector<Lit> args, std::set<Match>& found,
              const std::vector<Lit>* stop = nullptr) {
    Match m{value, r.name, args};
    if (executions_.count(m)) return;
    if (group_size(value, stop ? *stop : args, anchor_ == "cone") < 2) return;
    // One match per set of arguments: views of a symmetric operation can be
    // given the same values in several orders.
    std::sort(m.args.begin(), m.args.end());
    found.insert(m);
  }

  // Whether v's table t over the leaves equals R of some candidates' tables.
  void match_values(Lit v, const std::vector<Lit>& leaves, uint64_t t,
                    const std::vector<std::pair<Lit, uint64_t>>& candidates, std::set<Match>& found) {
    const uint64_t mask = leaves.size() >= 6 ? ~0ULL : ((1ULL << (1u << leaves.size())) - 1);
    for (const Registered& r : registered_) {
      std::vector<int> prev = previous_interchangeable(r);
      std::vector<int> chosen;
      std::function<void()> go = [&]() {
        const uint32_t j = static_cast<uint32_t>(chosen.size());
        // Prune: for some assignment of the leaves, no values of the
        // remaining views give v's value.
        for (uint32_t c = 0; c < (1u << j); ++c) {
          uint64_t block = mask;
          for (uint32_t i = 0; i < j; ++i) block &= ((c >> i) & 1) ? candidates[chosen[i]].second : ~candidates[chosen[i]].second;
          uint32_t reachable = reach(r, j, c);
          uint64_t bad = 0;
          if (!(reachable & 2)) bad |= t;
          if (!(reachable & 1)) bad |= ~t;
          if (block & bad & mask) return;
        }
        if (j == r.arity) {
          ++value_tuples_;
          // Every argument must matter over the leaves.
          for (uint32_t i = 0; i < r.arity; ++i) {
            uint64_t diff = 0;
            for (uint32_t m = 0; m < (1u << r.arity); ++m) {
              if ((m >> i) & 1) continue;
              if (((r.table >> m) & 1) == ((r.table >> (m | (1u << i))) & 1)) continue;
              uint64_t term = mask;
              for (uint32_t h = 0; h < r.arity; ++h)
                if (h != i) term &= ((m >> h) & 1) ? candidates[chosen[h]].second : ~candidates[chosen[h]].second;
              diff |= term;
            }
            if (!(diff & mask)) return;
          }
          std::vector<Lit> args;
          for (int i : chosen) args.push_back(candidates[i].first);
          Match m{v, r.name, args};
          if (executions_.count(m) || group_size(v, leaves, true) < 2) return;
          std::sort(m.args.begin(), m.args.end());
          found.insert(m);
          return;
        }
        const int lowest = prev[j] >= 0 ? chosen[prev[j]] + 1 : 0;
        for (int x = lowest; x < static_cast<int>(candidates.size()); ++x) {
          bool repeated = false;
          for (int y : chosen) repeated |= y == x;
          if (repeated) continue;
          chosen.push_back(x);
          go();
          chosen.pop_back();
        }
      };
      go();
    }
  }

  // With negated_leaves, a leaf whose negation is an available value can be
  // given to R as that value.
  void check_cut(Lit value, const std::vector<Lit>& leaves, uint64_t t, std::set<Match>& found,
                 const std::set<Lit>* negations = nullptr) {
    const uint32_t k = static_cast<uint32_t>(leaves.size());
    for (uint32_t flip = 0; flip < (1u << k); ++flip) {
      std::vector<Lit> given = leaves;
      bool allowed = true;
      for (uint32_t i = 0; i < k && allowed; ++i)
        if ((flip >> i) & 1) {
          allowed = negations && negations->count(leaves[i] ^ 1);
          given[i] = leaves[i] ^ 1;
        }
      if (!allowed) continue;
      // The table over the given values: negating leaf i swaps its halves.
      uint64_t tt = 0;
      for (uint32_t m = 0; m < (1u << k); ++m)
        if ((t >> (m ^ flip)) & 1) tt |= 1ULL << m;
      for (const Registered& r : registered_) {
        if (r.arity != k) continue;
        for (const std::vector<int>& perm : perms(k)) {
          bool same = true;
          for (uint32_t c = 0; c < (1u << k) && same; ++c) same = permuted_bit(r, perm, c) == ((tt >> c) & 1);
          if (!same) continue;
          std::vector<Lit> args(k);
          for (uint32_t i = 0; i < k; ++i) args[i] = given[perm[i]];
          record(value, r, args, found, &leaves);
        }
      }
    }
  }

  const std::vector<std::vector<int>>& perms(uint32_t k) {
    if (perms_.size() <= k) perms_.resize(k + 1);
    if (perms_[k].empty()) perms_[k] = permutations(k);
    return perms_[k];
  }

  void ensure_tables() {
    if (!tables_.empty()) return;
    const uint32_t I = g_.num_inputs;
    words_ = I <= 6 ? 1 : (size_t{1} << (I - 6));
    last_mask_ = I >= 6 ? ~0ULL : ((1ULL << (1u << I)) - 1);
    compute_node_tables();
  }

  void compute_node_tables() {
    const uint32_t n = g_.num_nodes();
    support_.assign(n, 0);
    for (uint32_t i = 1; i <= g_.num_inputs; ++i) support_[i] = 1u << (i - 1);
    for (uint32_t v = g_.num_inputs + 1; v < n; ++v)
      support_[v] = support_[node_of(g_.fanin0[v])] | support_[node_of(g_.fanin1[v])];
    tables_.assign(size_t{n} * words_, 0);
    static const uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                     0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
    for (uint32_t i = 1; i <= g_.num_inputs; ++i) {
      uint64_t* t = &tables_[size_t{i} * words_];
      uint32_t bit = i - 1;
      for (size_t w = 0; w < words_; ++w) t[w] = bit < 6 ? kVar[bit] : (((w >> (bit - 6)) & 1) ? ~0ULL : 0);
    }
    for (uint32_t v = g_.num_inputs + 1; v < n; ++v) {
      const uint64_t* a = &tables_[size_t{node_of(g_.fanin0[v])} * words_];
      const uint64_t* b = &tables_[size_t{node_of(g_.fanin1[v])} * words_];
      uint64_t fa = is_compl(g_.fanin0[v]) ? ~0ULL : 0, fb = is_compl(g_.fanin1[v]) ? ~0ULL : 0;
      uint64_t* t = &tables_[size_t{v} * words_];
      for (size_t w = 0; w < words_; ++w) t[w] = (a[w] ^ fa) & (b[w] ^ fb);
    }
    // A sample of minterms for the search: random ones from a fixed seed.
    Rng rng(7);
    const uint64_t space = uint64_t{1} << g_.num_inputs;
    for (int k = 0; k < 1024; ++k) sample_.push_back(rng.next() % space);
  }

  bool lit_bit(Lit l, uint64_t minterm) const {
    const uint64_t* t = &tables_[size_t{node_of(l)} * words_];
    return ((t[minterm >> 6] >> (minterm & 63)) & 1) ^ is_compl(l);
  }

  uint64_t table_hash(Lit l) const {
    const uint64_t* t = &tables_[size_t{node_of(l)} * words_];
    uint64_t flip = is_compl(l) ? ~0ULL : 0, h = 0x2545;
    for (size_t w = 0; w < words_; ++w) h = mix64(h ^ ((t[w] ^ flip) & (w + 1 == words_ ? last_mask_ : ~0ULL)));
    return h | 1;
  }

  // Sample bits of a literal, as words.
  std::vector<uint64_t> sample_bits(Lit l) const {
    std::vector<uint64_t> out((sample_.size() + 63) / 64, 0);
    for (size_t k = 0; k < sample_.size(); ++k)
      if (lit_bit(l, sample_[k])) out[k >> 6] |= 1ULL << (k & 63);
    return out;
  }

  // Values in the statement-level cone of v, as literals given to statements.
  std::vector<Lit> cone_values(Lit v) const {
    std::vector<Lit> out;
    std::set<Lit> seen;
    std::vector<Lit> stack;
    auto visit_args = [&](Lit l) {
      auto it = by_lit_.find(l);
      if (it == by_lit_.end()) it = by_lit_.find(l ^ 1);
      if (it == by_lit_.end()) return;
      for (Lit a : statements_[it->second].args) stack.push_back(a);
    };
    visit_args(v);
    while (!stack.empty()) {
      Lit l = stack.back();
      stack.pop_back();
      if (!seen.insert(l).second) continue;
      // A value and its negation are both reached: computing `not x` needs x.
      out.push_back(l);
      out.push_back(l ^ 1);
      visit_args(l);
    }
    return out;
  }

  // For R with its first j views fixed to the bits of c: whether some values
  // of the other views make it 0 (bit 0) and 1 (bit 1).
  static uint32_t reach(const Registered& r, uint32_t j, uint32_t c) {
    uint32_t out = 0;
    for (uint32_t rest = 0; rest < (1u << (r.arity - j)); ++rest) {
      uint32_t m = c | (rest << j);
      out |= ((r.table >> m) & 1) ? 2 : 1;
    }
    return out;
  }

  // Views of R that can be swapped without changing it. Each view's values
  // must come after the values of the earlier interchangeable view, so
  // symmetric operations aren't searched once per order.
  static std::vector<int> previous_interchangeable(const Registered& r) {
    std::vector<int> out(r.arity, -1);
    for (uint32_t i = 1; i < r.arity; ++i)
      for (uint32_t h = i; h-- > 0;) {
        bool same = true;
        for (uint32_t m = 0; m < (1u << r.arity) && same; ++m) {
          uint32_t bi = (m >> i) & 1, bh = (m >> h) & 1;
          uint32_t swapped = (m & ~((1u << i) | (1u << h))) | (bi << h) | (bh << i);
          same = ((r.table >> m) & 1) == ((r.table >> swapped) & 1);
        }
        if (same) {
          out[i] = static_cast<int>(h);
          break;
        }
      }
    return out;
  }

  void search(Lit v, const std::vector<Lit>& available, std::set<Match>& found) {
    // Arguments of a match must be in v's cone; v isn't computed from the
    // rest of the available values.
    std::set<uint64_t> in_cone;
    if (anchor_ == "cone")
      for (Lit a : cone_values(v)) in_cone.insert(table_hash(a));
    pool_.clear();
    for (Lit a : available) {
      if (node_of(a) == node_of(v)) continue;
      if (anchor_ == "cone" && !in_cone.count(table_hash(a))) continue;
      if (anchor_ == "support" && (support_[node_of(a)] & ~support_[node_of(v)])) continue;
      pool_.push_back(a);
    }
    bits_.clear();
    for (Lit a : pool_) bits_.push_back(sample_bits(a));
    vbits_ = sample_bits(v);
    for (const Registered& r : registered_) {
      std::vector<int> chosen;
      std::vector<int> prev = previous_interchangeable(r);
      assign(v, r, prev, chosen, found);
    }
  }

  uint64_t word_mask(size_t w) const {
    size_t n = sample_.size();
    return (w + 1 == bits_words() && n % 64) ? ((1ULL << (n % 64)) - 1) : ~0ULL;
  }
  size_t bits_words() const { return vbits_.size(); }

  // Sample words where the chosen views take the values in combo c.
  void block_of(const std::vector<int>& chosen, uint32_t c, std::vector<uint64_t>& block) const {
    block.assign(bits_words(), ~0ULL);
    for (size_t i = 0; i < chosen.size(); ++i)
      for (size_t w = 0; w < bits_words(); ++w)
        block[w] &= ((c >> i) & 1) ? bits_[chosen[i]][w] : ~bits_[chosen[i]][w];
  }

  void assign(Lit v, const Registered& r, const std::vector<int>& prev, std::vector<int>& chosen,
              std::set<Match>& found) {
    ++search_nodes_;
    const uint32_t j = static_cast<uint32_t>(chosen.size());
    std::vector<uint64_t> block;
    // Prune: on some sample, no values of the remaining views give v's value.
    for (uint32_t c = 0; c < (1u << j); ++c) {
      uint32_t reachable = reach(r, j, c);
      block_of(chosen, c, block);
      for (size_t w = 0; w < bits_words(); ++w) {
        uint64_t bad = 0;
        if (!(reachable & 2)) bad |= vbits_[w];
        if (!(reachable & 1)) bad |= ~vbits_[w];
        if (block[w] & bad & word_mask(w)) return;
      }
    }
    const int lowest = prev[j] >= 0 ? chosen[prev[j]] + 1 : 0;
    if (j + 1 < r.arity) {
      for (int x = lowest; x < static_cast<int>(pool_.size()); ++x) {
        chosen.push_back(x);
        assign(v, r, prev, chosen, found);
        chosen.pop_back();
      }
      return;
    }
    // The last view is forced wherever R depends on it.
    std::vector<uint64_t> must(bits_words(), 0), value(bits_words(), 0);
    for (uint32_t c = 0; c < (1u << j); ++c) {
      bool r0 = (r.table >> c) & 1, r1 = (r.table >> (c | (1u << j))) & 1;
      if (r0 == r1) continue;
      block_of(chosen, c, block);
      for (size_t w = 0; w < bits_words(); ++w) {
        must[w] |= block[w];
        value[w] |= block[w] & (r1 ? vbits_[w] : ~vbits_[w]);
      }
    }
    for (int x = lowest; x < static_cast<int>(pool_.size()); ++x) {
      bool ok = true;
      for (size_t w = 0; w < bits_words() && ok; ++w)
        ok = ((bits_[x][w] ^ value[w]) & must[w] & word_mask(w)) == 0;
      if (!ok) continue;
      chosen.push_back(x);
      verify(v, r, chosen, found);
      chosen.pop_back();
    }
  }

  // Whether v equals R of the chosen values on every minterm; if not, the
  // first minterm where they differ joins the sample.
  void verify(Lit v, const Registered& r, const std::vector<int>& chosen, std::set<Match>& found) {
    // Views can't be given the same value (DLP 55: views of a logical
    // operation may not alias); the pool has one literal per function.
    for (size_t i = 0; i < chosen.size(); ++i)
      for (size_t h = 0; h < i; ++h)
        if (chosen[i] == chosen[h]) return;
    ++exact_checks_;
    const uint64_t* tv = &tables_[size_t{node_of(v)} * words_];
    uint64_t fv = is_compl(v) ? ~0ULL : 0;
    for (size_t w = 0; w < words_; ++w) {
      uint64_t rw = 0;
      for (uint32_t m = 0; m < (1u << r.arity); ++m) {
        if (!((r.table >> m) & 1)) continue;
        uint64_t term = ~0ULL;
        for (uint32_t i = 0; i < r.arity; ++i) {
          Lit a = pool_[chosen[i]];
          uint64_t t = tables_[size_t{node_of(a)} * words_ + w] ^ (is_compl(a) ? ~0ULL : 0);
          term &= ((m >> i) & 1) ? t : ~t;
        }
        rw |= term;
      }
      uint64_t diff = (rw ^ tv[w] ^ fv) & (w + 1 == words_ ? last_mask_ : ~0ULL);
      if (diff) {
        ++refinements_;
        add_sample(w * 64 + static_cast<uint64_t>(__builtin_ctzll(diff)), v);
        return;
      }
    }
    // Every argument must matter: R's difference with respect to each view,
    // at these values, is true somewhere. A match with an argument that
    // makes no difference is a match of a smaller operation.
    for (uint32_t i = 0; i < r.arity; ++i) {
      bool matters = false;
      for (size_t w = 0; w < words_ && !matters; ++w) {
        uint64_t diff = 0;
        for (uint32_t m = 0; m < (1u << r.arity); ++m) {
          if ((m >> i) & 1) continue;
          if (((r.table >> m) & 1) == ((r.table >> (m | (1u << i))) & 1)) continue;
          uint64_t term = ~0ULL;
          for (uint32_t h = 0; h < r.arity; ++h) {
            if (h == i) continue;
            Lit a = pool_[chosen[h]];
            uint64_t t = tables_[size_t{node_of(a)} * words_ + w] ^ (is_compl(a) ? ~0ULL : 0);
            term &= ((m >> h) & 1) ? t : ~t;
          }
          diff |= term;
        }
        matters = (diff & (w + 1 == words_ ? last_mask_ : ~0ULL)) != 0;
      }
      if (!matters) {
        ++inessential_;
        return;
      }
    }
    std::vector<Lit> args;
    for (int i : chosen) args.push_back(pool_[i]);
    record(v, r, args, found);
  }

  void add_sample(uint64_t minterm, Lit v) {
    size_t k = sample_.size();
    sample_.push_back(minterm);
    if (k % 64 == 0) {
      for (auto& b : bits_) b.push_back(0);
      vbits_.push_back(0);
    }
    for (size_t j = 0; j < pool_.size(); ++j)
      if (lit_bit(pool_[j], minterm)) bits_[j][k >> 6] |= 1ULL << (k & 63);
    if (lit_bit(v, minterm)) vbits_[k >> 6] |= 1ULL << (k & 63);
  }

  const Aig& g_;
  std::vector<Statement> statements_;
  std::vector<Registered> registered_;
  uint32_t max_arity_ = 0;
  std::set<Match> executions_;
  std::map<Lit, size_t> by_lit_;
  std::vector<std::vector<std::vector<int>>> perms_;
  size_t words_ = 1;
  uint64_t last_mask_ = ~0ULL;
  std::vector<uint64_t> tables_;
  std::vector<uint64_t> sample_;
  std::vector<Lit> pool_;
  std::vector<uint32_t> support_;
  std::string anchor_ = "cone";
  uint32_t cut_size_ = 4;
  uint64_t value_cuts_ = 0, value_candidates_ = 0, value_tuples_ = 0;
  std::vector<std::vector<uint64_t>> bits_;
  std::vector<uint64_t> vbits_;
  uint64_t search_nodes_ = 0, exact_checks_ = 0, refinements_ = 0, inessential_ = 0;
};

}  // namespace beq
