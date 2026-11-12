// Finding written-out registered operations ("matches", DLP 59) two ways:
//
// - cuts: DLP 59's definition. Every cut of at most K values of each
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
#include <unordered_map>
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

inline std::vector<Statement> read_statements(const std::string& path, bool file_order = false) {
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
  // Statement order is node order in the reordered graph, unless the file
  // is already in statement order (a `not` shares its argument's node).
  if (file_order) return out;
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

// What the search needs of values' functions when there are no truth
// tables over every input: each literal's function as a number (equal for
// equal functions), its value on one input assignment, and the exact check
// that target is R of args with every argument mattering, which on a
// difference gives an input assignment that shows it.
struct MatchOracle {
  virtual ~MatchOracle() = default;
  virtual uint64_t function_id(Lit l) = 0;
  virtual bool bit(Lit l, uint64_t minterm) = 0;
  virtual bool holds(Lit target, const Registered& r, const std::vector<Lit>& args, bool& differs,
                     uint64_t& difference) = 0;
};

class Matcher {
 public:
  // Search results kept from one check of an operation to the next while
  // the fix loop works on it, by value (doubled, plus whether it's
  // negated). The candidates a value's search reaches depend only on its
  // function, the operations searched, and the values available before it
  // (with whether each is a `not`, which a spelling's key counts), and for
  // spellings on the key of the value's own spelling: with those the
  // same, the candidates are replayed, and everything else (what a match
  // removes, existing executions, the exact check) is decided again.
  struct SearchCache {
    struct Leaf {
      uint32_t variant = 0;
      bool opposite = false;
      std::vector<int64_t> args;
    };
    struct Entry {
      std::vector<int64_t> pool;
      bool matched = false, spelled = false;
      std::array<int, 3> key{};
      std::vector<Leaf> match_leaves, spell_leaves;
    };
    std::unordered_map<int, Entry> entries;
    size_t hits = 0, misses = 0;
  };
  Matcher(const Aig& g, std::vector<Statement> statements, std::vector<Registered> registered)
      : g_(g), statements_(std::move(statements)), registered_(std::move(registered)) {
    for (const Registered& r : registered_) max_arity_ = std::max(max_arity_, r.arity);
    for (size_t i = 0; i < statements_.size(); ++i) by_lit_[statements_[i].lit] = i;
    uses_.assign(statements_.size(), 0);
    for (const Statement& s : statements_)
      for (Lit a : s.args) {
        auto it = by_lit_.find(a);
        if (it != by_lit_.end()) ++uses_[it->second];
      }
    for (Lit o : g_.outputs) {
      auto it = by_lit_.find(o);
      if (it != by_lit_.end()) ++uses_[it->second];
    }
    for (const Statement& s : statements_)
      for (const Registered& r : registered_)
        if (s.op == r.name) {
          executions_.insert({s.lit, s.op, s.args});
          std::vector<Lit> sorted = s.args;
          std::sort(sorted.begin(), sorted.end());
          sorted_executions_.insert({s.lit, s.op, sorted});
        }
  }

  // How the arguments of an exact match must relate to the value: "cone"
  // (in its statement-level cone), "support" (any available value whose
  // inputs are among the value's), or "any" (any available value).
  void set_anchor(const std::string& anchor) { anchor_ = anchor; }
  // The largest cut, in values (DLP 59: four).
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

  // DLP 59's cut definition, at the level of statements. With with_values,
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

  // The exact definition over earlier values, with opposite results, searched
  // the way Boolean resubstitution finds divisors: every available literal's
  // sample bits are also kept transposed, as one bitset of literals per
  // sampled input assignment, so the values a view can take, given the views
  // already chosen, are found for all candidates at once by and-ing the
  // bitsets of the assignments that constrain it, stopping as soon as none
  // are left. A value v matches R(a1..ak) when the ai are available before v,
  // v = R(ai) or v = not R(ai) (the opposite result, unless an operation
  // computing not R is registered), every ai matters, the match has at least
  // two statements, and it isn't an execution of R on those values (or, for
  // the opposite, an execution and its `not`).
  std::set<Match> run_resub(Stats& stats) {
    const uint32_t I = g_.num_inputs;
    (void)I;
    ensure_tables();
    prepare_variants();
    // Literals become available in statement order; each one's function is
    // kept once.
    const size_t capacity = I + 2 * statements_.size() + 2;
    lwords_ = (capacity + 63) / 64;
    if (lwords_ > kMaxPoolWords) throw std::runtime_error("too many values for the search");
    resub_pool_.clear();
    pool_codes_.clear();
    lit_samples_.clear();
    positions_.clear();
    rsamples_.assign(sample_.begin(), sample_.begin() + std::min<size_t>(sample_.size(), 256));
    positions_.assign(rsamples_.size(), std::vector<uint64_t>(lwords_, 0));
    std::set<uint64_t> seen;
    auto add = [&](Lit l) {
      // A literal given to a statement isn't a value.
      if (node_of(l) == 0) return;
      if (!seen.insert(table_hash(l)).second) return;
      const size_t index = resub_pool_.size();
      resub_pool_.push_back(l);
      if (search_cache_) {
        const int64_t code = pool_code(l);
        pool_codes_.insert(std::lower_bound(pool_codes_.begin(), pool_codes_.end(), code), code);
      }
      std::vector<uint64_t> bits((rsamples_.size() + 63) / 64, 0);
      for (size_t k = 0; k < rsamples_.size(); ++k)
        if (lit_bit(l, rsamples_[k])) {
          bits[k >> 6] |= 1ULL << (k & 63);
          positions_[k][index >> 6] |= 1ULL << (index & 63);
        }
      lit_samples_.push_back(std::move(bits));
    };
    std::vector<char> late(I + 1, 0);
    for (const auto& [index, lit] : late_inputs_) late[node_of(lit)] = 1;
    for (uint32_t i = 1; i <= I; ++i)
      if (!late[i]) add(make_lit(i));
    std::set<Match> found;
    size_t next_late = 0;
    for (size_t k = 0; k < statements_.size(); ++k) {
      const Statement& s = statements_[k];
      if (budget_) budget_->at = s.lit;
      while (next_late < late_inputs_.size() && late_inputs_[next_late].first <= k)
        add(late_inputs_[next_late++].second);
      for (Lit a : s.args) add(a);
      // With anchor "cone", arguments must be in v's statement-level cone;
      // with "support", functions of v's inputs only.
      allowed_.fill(0);
      std::set<uint64_t> in_cone;
      if (anchor_ == "cone")
        for (Lit a : cone_values(s.lit)) in_cone.insert(table_hash(a));
      for (size_t x = 0; x < resub_pool_.size(); ++x) {
        const Lit a = resub_pool_[x];
        if (anchor_ == "cone" && !in_cone.count(table_hash(a))) continue;
        if (anchor_ == "support" && (support_[node_of(a)] & ~support_[node_of(s.lit)])) continue;
        allowed_[x >> 6] |= 1ULL << (x & 63);
      }
      // A match removes at least two statements, so some statement v reads
      // must be read by v alone.
      bool sole_reader = false;
      for (Lit a : s.args) {
        auto it = by_lit_.find(a);
        // A value given twice (through a copy) is still read by v alone.
        sole_reader |= it != by_lit_.end() &&
                       uses_[it->second] == static_cast<int>(std::count(s.args.begin(), s.args.end(), a));
      }
      // The value's kept search, if the values before it are the same.
      SearchCache::Entry* entry = nullptr;
      if (search_cache_) {
        SearchCache::Entry& e = search_cache_->entries[2 * node_value_[node_of(s.lit)] + static_cast<int>(is_compl(s.lit))];
        if (e.pool != pool_codes_) {
          e = SearchCache::Entry{};
          e.pool = pool_codes_;
        }
        entry = &e;
      }
      // With spellings, every way of writing a value that is an execution
      // of a registered operation, or a `not` of one, is listed too, for a
      // precedence rule between them.
      if (spellings_) {
        const Statement* exec = &s;
        if (s.op == "not") {
          auto it = by_lit_.find(s.args[0]);
          exec = it == by_lit_.end() ? nullptr : &statements_[it->second];
        }
        if (exec && is_registered(exec->op)) {
          spelling_ = true;
          // With a declared order, only spellings that could have at least
          // the precedence of the one the program has are listed: no
          // operation is searched whose spellings would all come later.
          if (!order_.empty()) current_key_ = spelling_key(exec->op, exec->args, s.op == "not");
          if (entry && entry->spelled && entry->key == current_key_) {
            ++search_cache_->hits;
            replay(entry->spell_leaves, s.lit, spelled_);
          } else {
            if (entry) {
              ++search_cache_->misses;
              entry->spell_leaves.clear();
              recording_ = &entry->spell_leaves;
            }
            for (Lit target : {s.lit, s.lit ^ 1})
              for (const Variant& r : variants_) {
                if (!only_.empty() && !only_.count(r.r.name)) continue;
                if (target != s.lit && !r.opposite_allowed) continue;
                if (target != s.lit && precedence_strict_) continue;
                if (!order_.empty() && spelling_bound(r.r.name, target != s.lit) > current_key_) continue;
                chosen_.clear();
                resub_assign(s.lit, target, r, spelled_);
              }
            recording_ = nullptr;
            if (entry) {
              entry->spelled = true;
              entry->key = current_key_;
            }
          }
          spelling_ = false;
        }
      }
      if (plain_) sole_reader = true;
      if (!sole_reader) ++skipped_values_;
      if (sole_reader && matches_ && entry && entry->matched) {
        ++search_cache_->hits;
        replay(entry->match_leaves, s.lit, found);
      } else if (sole_reader && matches_) {
        if (entry) {
          ++search_cache_->misses;
          entry->match_leaves.clear();
          recording_ = &entry->match_leaves;
        }
        for (Lit target : {s.lit, s.lit ^ 1})
          for (const Variant& r : variants_) {
            if (!only_.empty() && !only_.count(r.r.name)) continue;
            if (target != s.lit && !r.opposite_allowed) continue;
            chosen_.clear();
            resub_assign(s.lit, target, r, found);
          }
        recording_ = nullptr;
        if (entry) entry->matched = true;
      }
      add(s.lit);
    }
    if (first_only_) {
      // The largest candidates first, then the earliest value; every
      // candidate that ties with the first that holds is reported too, so
      // the caller can break the tie by name and rank.
      std::stable_sort(pending_.begin(), pending_.end(), [](const Pending& a, const Pending& b) {
        return std::make_pair(b.size, a.statement) < std::make_pair(a.size, b.statement);
      });
      for (size_t i = 0; i < pending_.size();) {
        size_t end = i;
        while (end < pending_.size() && pending_[end].size == pending_[i].size &&
               pending_[end].statement == pending_[i].statement)
          ++end;
        for (size_t k = i; k < end; ++k) {
          const Pending& c = pending_[k];
          if (holds(c.v, c.target, c.var->r, c.args))
            found.insert(Match{c.v, c.target != c.v ? "not:" + c.var->r.name : c.var->r.name, c.args});
        }
        if (!found.empty()) break;
        i = end;
      }
      stats.emplace_back("candidates", static_cast<double>(pending_.size()));
    }
    stats.emplace_back("search_nodes", static_cast<double>(search_nodes_));
    stats.emplace_back("exact_checks", static_cast<double>(exact_checks_));
    stats.emplace_back("refinements", static_cast<double>(refinements_));
    stats.emplace_back("inessential", static_cast<double>(inessential_));
    stats.emplace_back("samples", static_cast<double>(rsamples_.size()));
    stats.emplace_back("skipped_values", static_cast<double>(skipped_values_));
    stats.emplace_back("hash_lookups", static_cast<double>(hash_lookups_));
    stats.emplace_back("position_steps", static_cast<double>(position_steps_));
    stats.emplace_back("leaf_candidates", static_cast<double>(leaf_candidates_));
    return found;
  }

  // The number of statements in a match: those reached from the value
  // without passing through an argument.
  // The number of statements in a match of the exact definition: the
  // statements that fixing it removes, which are the value's own and every
  // statement nothing reads once the value is computed from the arguments.
  size_t match_size(const Match& m) const { return removed(m.value, m.args).size(); }
  // Those statements, by index among the statements given.
  std::vector<size_t> match_statements(const Match& m) const { return removed(m.value, m.args); }

 private:
  bool is_registered(const std::string& op) const {
    for (const Registered& r : registered_)
      if (r.name == op) return true;
    return false;
  }

  // The statements that become unused when v is computed from args
  // instead: v's own, then any whose last reader was one of them.
  std::vector<size_t> removed(Lit v, const std::vector<Lit>& args) const {
    // Each statement's change in uses, cleared again before returning.
    if (delta_.size() < statements_.size()) delta_.assign(statements_.size(), 0);
    touched_.clear();
    auto change = [&](size_t i, int d) {
      if (delta_[i] == 0) touched_.push_back(i);
      delta_[i] += d;
    };
    auto uses_of = [&](size_t i) { return uses_[i] + delta_[i]; };
    for (Lit a : args) {
      auto it = by_lit_.find(a);
      if (it != by_lit_.end()) change(it->second, 1);
    }
    std::vector<size_t> out{by_lit_.at(v)}, stack{by_lit_.at(v)};
    while (!stack.empty()) {
      const size_t i = stack.back();
      stack.pop_back();
      for (Lit a : statements_[i].args) {
        auto it = by_lit_.find(a);
        if (it == by_lit_.end()) continue;
        change(it->second, -1);
        if (uses_of(it->second) == 0) {
          out.push_back(it->second);
          stack.push_back(it->second);
        }
      }
    }
    for (size_t i : touched_) delta_[i] = 0;
    return out;
  }
  std::map<std::pair<std::string, std::vector<int>>, bool>* holds_cache_ = nullptr;
  SearchCache* search_cache_ = nullptr;
  std::unordered_map<int64_t, int> pool_index_;
  // The pool's values by pool_code, sorted, while there's a search cache.
  std::vector<int64_t> pool_codes_;
  std::vector<SearchCache::Leaf>* recording_ = nullptr;
  std::vector<int> node_value_;
  mutable std::vector<int> delta_;
  mutable std::vector<size_t> touched_;

  static constexpr size_t kMaxPoolWords = 128;
  struct Variant {
    Registered r;
    std::vector<int> prev;
    // allow[j][c][t]: for views 0..j-1 given the bits of c, which values of
    // view j (bit 0: false, bit 1: true) leave some way to get the target t.
    std::vector<std::vector<std::array<uint8_t, 2>>> allow;
    bool opposite_allowed = true;
    // Majority: wherever R(args) equals the target, at most one argument
    // differs from it, so the argument that differs least differs on at
    // most a third of the samples. It's given to view 0.
    bool majority = false;
  };

  void prepare_variants() {
    variants_.clear();
    for (const Registered& r : registered_) {
      Variant v{r, previous_interchangeable(r), {}, true};
      // An operation computing the opposite is registered: the group is a
      // match for that one instead.
      for (const Registered& o : registered_) {
        if (o.arity != r.arity) continue;
        for (const std::vector<int>& perm : perms(r.arity)) {
          bool opposite = true;
          for (uint32_t c = 0; c < (1u << r.arity) && opposite; ++c)
            opposite = permuted_bit(o, perm, c) == !((r.table >> c) & 1);
          if (opposite) v.opposite_allowed = false;
        }
      }
      v.allow.resize(r.arity);
      for (uint32_t j = 0; j < r.arity; ++j) {
        v.allow[j].assign(1u << j, {0, 0});
        for (uint32_t c = 0; c < (1u << j); ++c)
          for (uint32_t t = 0; t < 2; ++t)
            for (uint32_t b = 0; b < 2; ++b) {
              const uint32_t fixed = c | (b << j);
              for (uint32_t rest = 0; rest < (1u << (r.arity - j - 1)); ++rest)
                if (((r.table >> (fixed | (rest << (j + 1)))) & 1) == t) v.allow[j][c][t] |= 1u << b;
            }
      }
      v.majority = !plain_ && r.arity == 3 && r.table == 0xE8;
      variants_.push_back(std::move(v));
    }
  }

  bool sample_bit(size_t index, size_t k) const { return (lit_samples_[index][k >> 6] >> (k & 63)) & 1; }

  void resub_assign(Lit v, Lit target, const Variant& var, std::set<Match>& found) {
    ++search_nodes_;
    if (budget_) budget_->spend(1, StepBudget::kSearch);
    const Registered& r = var.r;
    const uint32_t j = static_cast<uint32_t>(chosen_.size());
    // Candidates: available literals before v, after the previous
    // interchangeable view's value, not already chosen.
    std::array<uint64_t, kMaxPoolWords> cand{};
    const size_t n = resub_pool_.size();
    refresh_target(target);
    size_t lowest = var.prev[j] >= 0 ? static_cast<size_t>(chosen_[var.prev[j]]) + 1 : 0;
    if (var.majority && j == 0) {
      // How much each literal differs from the target on the samples as
      // they are now, which every later step of this search compares.
      const size_t sw0 = (rsamples_.size() + 63) / 64;
      const uint64_t flip0 = is_compl(target) ? ~0ULL : 0;
      differs_.assign(n, 0);
      for (size_t x = 0; x < n; ++x)
        for (size_t w = 0; w < sw0; ++w) {
          const uint64_t valid =
              (w + 1 == sw0 && rsamples_.size() % 64) ? ((1ULL << (rsamples_.size() % 64)) - 1) : ~0ULL;
          differs_[x] += static_cast<uint32_t>(
              __builtin_popcountll((lit_samples_[x][w] ^ target_cache_[w] ^ flip0) & valid));
        }
      majority_samples_ = rsamples_.size();
    }
    if (var.majority && j == 1) lowest = 0;
    if (var.majority) {
      for (size_t x = lowest; x < n; ++x) {
        if (j == 0 && 3 * differs_[x] > majority_samples_) continue;
        if (j > 0) {
          const size_t a = static_cast<size_t>(chosen_[0]);
          if (std::make_pair(differs_[x], x) < std::make_pair(differs_[a], a)) continue;
        }
        cand[x >> 6] |= 1ULL << (x & 63);
      }
    } else {
      // Every literal from `lowest` up to n, a word at a time.
      for (size_t w = lowest >> 6; w < (n + 63) / 64; ++w) {
        uint64_t word = ~0ULL;
        if (w == lowest >> 6) word &= ~0ULL << (lowest & 63);
        if (w == n >> 6) word &= (1ULL << (n & 63)) - 1;
        cand[w] = word;
      }
    }
    for (size_t w = 0; w < lwords_; ++w) cand[w] &= allowed_[w];
    for (int x : chosen_) cand[x >> 6] &= ~(1ULL << (x & 63));
    // Sampled assignments where view j must be false (m0) or true (m1), a
    // word at a time; one where no value of view j works prunes the node.
    const size_t sw = (rsamples_.size() + 63) / 64;
    m0_.assign(sw, 0);
    m1_.assign(sw, 0);
    const uint64_t flip = is_compl(target) ? ~0ULL : 0;
    for (size_t w = 0; w < sw; ++w) {
      const uint64_t valid = (w + 1 == sw && rsamples_.size() % 64) ? ((1ULL << (rsamples_.size() % 64)) - 1) : ~0ULL;
      const uint64_t tw = target_cache_[w] ^ flip;
      uint64_t dead = 0;
      for (uint32_t c = 0; c < (1u << j); ++c) {
        uint64_t block = valid;
        for (uint32_t i = 0; i < j; ++i) {
          const uint64_t b = lit_samples_[chosen_[i]][w];
          block &= ((c >> i) & 1) ? b : ~b;
        }
        for (uint32_t t = 0; t < 2; ++t) {
          const uint64_t at = block & (t ? tw : ~tw);
          switch (var.allow[j][c][t]) {
            case 0: dead |= at; break;
            case 1: m0_[w] |= at; break;
            case 2: m1_[w] |= at; break;
            default: break;
          }
        }
      }
      if (dead) return;
    }
    // When the last view's value is forced on every sample (as for `xor`),
    // the candidates are the literals with exactly those sample bits.
    if (j + 1 == r.arity && !plain_) {
      bool forced = true;
      for (size_t w = 0; w < sw && forced; ++w) {
        const uint64_t valid = (w + 1 == sw && rsamples_.size() % 64) ? ((1ULL << (rsamples_.size() % 64)) - 1) : ~0ULL;
        forced = (m0_[w] | m1_[w]) == valid;
      }
      if (forced) {
        ++hash_lookups_;
        refresh_signatures();
        auto it = signatures_.find(signature(m1_));
        if (it == signatures_.end()) return;
        const std::vector<int> bucket = it->second;
        // A candidate that fails adds a sample, which the others' bits then
        // have and m1_ doesn't: compare only the samples m1_ was built from.
        const size_t samples = rsamples_.size();
        auto same_bits = [&](int x) {
          for (size_t w = 0; w < sw; ++w) {
            const uint64_t valid = (w + 1 == sw && samples % 64) ? ((1ULL << (samples % 64)) - 1) : ~0ULL;
            if ((lit_samples_[x][w] & valid) != (m1_[w] & valid)) return false;
          }
          return true;
        };
        for (int x : bucket) {
          if (!((cand[x >> 6] >> (x & 63)) & 1) || !same_bits(x)) continue;
          chosen_.push_back(x);
          ++leaf_candidates_;
          if (budget_) budget_->spend(1, StepBudget::kSearch);
          resub_verify(v, target, var, found);
          chosen_.pop_back();
        }
        return;
      }
    }
    // Keep the candidates whose sample bits are m1_'s wherever a view's
    // value is forced: a position at a time over every candidate, or a
    // candidate at a time over every position, whichever is fewer words.
    size_t forced_bits = 0, candidates = 0;
    for (size_t w = 0; w < sw; ++w) forced_bits += static_cast<size_t>(__builtin_popcountll(m0_[w] | m1_[w]));
    for (size_t w = 0; w < lwords_; ++w) candidates += static_cast<size_t>(__builtin_popcountll(cand[w]));
    if (candidates * sw < forced_bits * lwords_) {
      uint64_t any = 0;
      for (size_t lw = 0; lw < lwords_; ++lw) {
        for (uint64_t bits = cand[lw]; bits; bits &= bits - 1) {
          const size_t x = lw * 64 + static_cast<size_t>(__builtin_ctzll(bits));
          if (x >= n) break;
          ++position_steps_;
          if (budget_) budget_->spend(1, StepBudget::kSearch);
          for (size_t w = 0; w < sw; ++w)
            if ((lit_samples_[x][w] ^ m1_[w]) & (m0_[w] | m1_[w])) {
              cand[lw] &= ~(1ULL << (x & 63));
              break;
            }
        }
        any |= cand[lw];
      }
      if (!any) return;
    } else {
      for (size_t w = 0; w < sw; ++w)
        for (uint64_t bits = m0_[w] | m1_[w]; bits; bits &= bits - 1) {
          const size_t k = w * 64 + static_cast<size_t>(__builtin_ctzll(bits));
          const bool one = (m1_[w] >> (k & 63)) & 1;
          ++position_steps_;
          if (budget_) budget_->spend(1, StepBudget::kSearch);
          const std::vector<uint64_t>& at = positions_[k];
          uint64_t any = 0;
          for (size_t lw = 0; lw < lwords_; ++lw) {
            cand[lw] &= one ? at[lw] : ~at[lw];
            any |= cand[lw];
          }
          if (!any) return;
        }
    }
    for (size_t w = 0; w < lwords_; ++w)
      for (uint64_t bits = cand[w]; bits; bits &= bits - 1) {
        const int x = static_cast<int>(w * 64 + static_cast<size_t>(__builtin_ctzll(bits)));
        if (static_cast<size_t>(x) >= n) break;
        chosen_.push_back(x);
        if (j + 1 == r.arity) {
          ++leaf_candidates_;
          if (budget_) budget_->spend(1, StepBudget::kSearch);
        }
        if (j + 1 < r.arity)
          resub_assign(v, target, var, found);
        else
          resub_verify(v, target, var, found);
        chosen_.pop_back();
      }
  }

  // The sample bits of v's node, which isn't in the pool yet, kept up to date
  // as samples are added.
  void refresh_target(Lit target) {
    if (target_cache_lit_ != node_of(target) || target_cache_size_ != rsamples_.size()) {
      target_cache_.assign((rsamples_.size() + 63) / 64, 0);
      for (size_t k = 0; k < rsamples_.size(); ++k)
        if (lit_bit(make_lit(node_of(target)), rsamples_[k])) target_cache_[k >> 6] |= 1ULL << (k & 63);
      target_cache_lit_ = node_of(target);
      target_cache_size_ = rsamples_.size();
    }
  }

  // Whether target = R(args) on every input assignment, with every argument
  // mattering. A difference found adds its assignment to the samples.
  bool holds(Lit v, Lit target, const Registered& r, const std::vector<Lit>& args) {
    if (!holds_cache_) return check_holds(v, target, r, args);
    std::vector<int> key{2 * node_value_[node_of(target)] + static_cast<int>(is_compl(target))};
    for (Lit a : args) key.push_back(2 * node_value_[node_of(a)] + static_cast<int>(is_compl(a)));
    auto [it, added] = holds_cache_->try_emplace({r.name, std::move(key)}, false);
    if (added) it->second = check_holds(v, target, r, args);
    return it->second;
  }

  bool check_holds(Lit v, Lit target, const Registered& r, const std::vector<Lit>& args) {
    (void)v;
    ++exact_checks_;
    // An exact check on truth tables costs a step for every word.
    if (budget_ && !oracle_) budget_->spend(words_, StepBudget::kSearch);
    if (oracle_) {
      bool differs = false;
      uint64_t difference = 0;
      if (oracle_->holds(target, r, args, differs, difference)) return true;
      if (differs) {
        ++refinements_;
        add_resub_sample(difference);
      } else {
        ++inessential_;
      }
      return false;
    }
    const uint64_t* tv = &tables_[size_t{node_of(target)} * words_];
    const uint64_t fv = is_compl(target) ? ~0ULL : 0;
    std::array<const uint64_t*, 8> at{};
    std::array<uint64_t, 8> flip{};
    for (uint32_t i = 0; i < r.arity; ++i) {
      at[i] = &tables_[size_t{node_of(args[i])} * words_];
      flip[i] = is_compl(args[i]) ? ~0ULL : 0;
    }
    // The standard operations get their own expressions, which are several
    // times faster than summing minterms.
    const uint64_t t2 = r.arity == 2 ? r.table : 0, t3 = r.arity == 3 ? r.table : 0;
    for (size_t w = 0; w < words_; ++w) {
      const uint64_t x0 = at[0][w] ^ flip[0], x1 = r.arity >= 2 ? at[1][w] ^ flip[1] : 0;
      uint64_t rw = 0;
      if (t2 == 0xE) {
        rw = x0 | x1;
      } else if (t2 == 0x6) {
        rw = x0 ^ x1;
      } else if (t2 == 0x9) {
        rw = ~(x0 ^ x1);
      } else if (t2 == 0xD) {
        rw = ~x0 | x1;
      } else if (t3 == 0xD8) {
        const uint64_t x2 = at[2][w] ^ flip[2];
        rw = (x0 & x1) | (~x0 & x2);
      } else if (t3 == 0xE8) {
        const uint64_t x2 = at[2][w] ^ flip[2];
        rw = (x0 & x1) | (x2 & (x0 | x1));
      } else {
        for (uint32_t m = 0; m < (1u << r.arity); ++m) {
          if (!((r.table >> m) & 1)) continue;
          uint64_t term = ~0ULL;
          for (uint32_t i = 0; i < r.arity; ++i) {
            const uint64_t x = at[i][w] ^ flip[i];
            term &= ((m >> i) & 1) ? x : ~x;
          }
          rw |= term;
        }
      }
      const uint64_t diff = (rw ^ tv[w] ^ fv) & (w + 1 == words_ ? last_mask_ : ~0ULL);
      if (diff) {
        ++refinements_;
        add_resub_sample(w * 64 + static_cast<uint64_t>(__builtin_ctzll(diff)));
        return false;
      }
    }
    // Every argument must matter: R's difference with respect to each view,
    // at these values, is true for some input assignment.
    for (uint32_t i = 0; i < r.arity; ++i) {
      bool matters = false;
      for (size_t w = 0; w < words_ && !matters; ++w) {
        uint64_t diff = 0;
        for (uint32_t m = 0; m < (1u << r.arity); ++m) {
          if ((m >> i) & 1) continue;
          if (((r.table >> m) & 1) == ((r.table >> (m | (1u << i))) & 1)) continue;
          uint64_t term = ~0ULL;
          for (uint32_t h = 0; h < r.arity; ++h)
            if (h != i) {
              const uint64_t x = at[h][w] ^ flip[h];
              term &= ((m >> h) & 1) ? x : ~x;
            }
          diff |= term;
        }
        matters = (diff & (w + 1 == words_ ? last_mask_ : ~0ULL)) != 0;
      }
      if (!matters) {
        ++inessential_;
        return false;
      }
    }
    return true;
  }

  // A value in the pool, by its value: doubled plus whether it's negated,
  // doubled plus whether it's a `not` statement.
  int64_t pool_code(Lit a) const {
    auto it = by_lit_.find(a);
    const bool is_not = it != by_lit_.end() && statements_[it->second].op == "not";
    return (static_cast<int64_t>(node_value_[node_of(a)]) * 2 + static_cast<int64_t>(is_compl(a))) * 2 + is_not;
  }

  // The candidates of a kept search, against the values as they are now.
  void replay(const std::vector<SearchCache::Leaf>& leaves, Lit v, std::set<Match>& found) {
    if (pool_index_.empty())
      for (size_t x = 0; x < resub_pool_.size(); ++x) pool_index_[pool_code(resub_pool_[x])] = static_cast<int>(x);
    for (const SearchCache::Leaf& leaf : leaves) {
      chosen_.clear();
      for (int64_t code : leaf.args) chosen_.push_back(pool_index_.at(code));
      resub_verify(v, leaf.opposite ? v ^ 1 : v, variants_[leaf.variant], found);
    }
    pool_index_.clear();
  }

  void resub_verify(Lit v, Lit target, const Variant& var, std::set<Match>& found) {
    const Registered& r = var.r;
    std::vector<Lit> args;
    for (int i : chosen_) args.push_back(resub_pool_[i]);
    if (recording_) {
      SearchCache::Leaf leaf;
      leaf.variant = static_cast<uint32_t>(&var - variants_.data());
      leaf.opposite = target != v;
      for (Lit a : args) leaf.args.push_back(pool_code(a));
      recording_->push_back(std::move(leaf));
    }
    const bool opposite = target != v;
    if (spelling_) {
      if (!order_.empty() && spelling_key(r.name, args, opposite) > current_key_) return;
      if (holds(v, target, r, args)) found.insert(Match{v, opposite ? "not:" + r.name : r.name, args});
      return;
    }
    // An execution of R on these values, or for the opposite result, an
    // execution and a `not` of it, is how the program should be written.
    std::vector<Lit> sorted = args;
    std::sort(sorted.begin(), sorted.end());
    if (sorted_executions_.count(Match{opposite ? v ^ 1 : v, r.name, sorted})) return;
    // A match has at least two statements, and an execution of a
    // registered operation and a `not` of it are only a match for an
    // operation that computes the opposite.
    const std::vector<size_t> group = removed(v, args);
    if (group.size() < 2 || (opposite && group.size() < min_opposite_removed_)) return;
    if (opposite && group.size() == 2) {
      const Statement& s = statements_[by_lit_.at(v)];
      if (s.op == "not") {
        auto it = by_lit_.find(s.args[0]);
        if (it != by_lit_.end() && std::find(group.begin(), group.end(), it->second) != group.end() &&
            is_registered(statements_[it->second].op))
          return;
      }
    }
    if (first_only_) {
      pending_.push_back({group.size(), by_lit_.at(v), v, target, &var, args});
      return;
    }
    if (!holds(v, target, r, args)) return;
    found.insert(Match{v, opposite ? "not:" + r.name : r.name, args});
  }

  static uint64_t signature(const std::vector<uint64_t>& bits) {
    uint64_t h = 0x9E37;
    for (uint64_t w : bits) h = mix64(h ^ w);
    return h;
  }

  // Literals by their sample bits, kept up to date as literals and samples
  // are added.
  void refresh_signatures() {
    if (signature_samples_ != rsamples_.size()) {
      signatures_.clear();
      signature_pool_ = 0;
      signature_samples_ = rsamples_.size();
    }
    for (; signature_pool_ < resub_pool_.size(); ++signature_pool_)
      signatures_[signature(lit_samples_[signature_pool_])].push_back(static_cast<int>(signature_pool_));
  }

  void add_resub_sample(uint64_t minterm) {
    const size_t k = rsamples_.size();
    rsamples_.push_back(minterm);
    positions_.emplace_back(lwords_, 0);
    for (size_t index = 0; index < resub_pool_.size(); ++index) {
      if (k % 64 == 0) lit_samples_[index].push_back(0);
      if (lit_bit(resub_pool_[index], minterm)) {
        lit_samples_[index][k >> 6] |= 1ULL << (k & 63);
        positions_[k][index >> 6] |= 1ULL << (index & 63);
      }
    }
  }

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
    if (oracle_) {
      if (sample_.empty()) {
        Rng rng(7);
        const uint64_t space = uint64_t{1} << g_.num_inputs;
        for (int k = 0; k < 1024; ++k) sample_.push_back(rng.next() % space);
      }
      return;
    }
    if (!tables_.empty()) return;
    if (!given_tables_.empty()) {
      const uint32_t I = g_.num_inputs;
      words_ = I <= 6 ? 1 : (size_t{1} << (I - 6));
      last_mask_ = I >= 6 ? ~0ULL : ((1ULL << (1u << I)) - 1);
      tables_ = std::move(given_tables_);
      support_ = std::move(given_support_);
      Rng rng(7);
      const uint64_t space = uint64_t{1} << I;
      for (int k = 0; k < 1024; ++k) sample_.push_back(rng.next() % space);
      return;
    }
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
    if (oracle_) return oracle_->bit(l, minterm);
    const uint64_t* t = &tables_[size_t{node_of(l)} * words_];
    return ((t[minterm >> 6] >> (minterm & 63)) & 1) ^ is_compl(l);
  }

  uint64_t table_hash(Lit l) const {
    if (hash_cache_.size() <= l) hash_cache_.resize(2 * size_t{g_.num_nodes()} + 2, 0);
    if (hash_cache_[l]) return hash_cache_[l];
    return hash_cache_[l] = compute_table_hash(l);
  }

  uint64_t compute_table_hash(Lit l) const {
    if (oracle_) return oracle_->function_id(l) | 1;
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
  std::set<Match> sorted_executions_;
  std::vector<int> uses_;
  std::vector<uint32_t> differs_;
  size_t majority_samples_ = 0;
  uint64_t skipped_values_ = 0, hash_lookups_ = 0;
  std::unordered_map<uint64_t, std::vector<int>> signatures_;
  size_t signature_samples_ = 0, signature_pool_ = 0;
  // Without the shortcuts, to check that they change nothing.
  bool plain_ = false;
  // Only the match DLP 59 reports: candidates are verified largest first.
  bool first_only_ = false;
  bool spellings_ = false, spelling_ = false;
  std::set<Match> spelled_;
  std::vector<std::string> order_;
  bool precedence_strict_ = false;
  std::vector<uint64_t> given_tables_;
  std::vector<uint32_t> given_support_;
  std::vector<std::pair<size_t, Lit>> late_inputs_;
  std::map<std::string, int> nodes_;
  size_t min_opposite_removed_ = 2;
  bool matches_ = true;
  std::set<std::string> only_;
  using Key = std::array<int, 3>;
  Key current_key_{};

  int aig_nodes(const std::string& op) const {
    auto it = nodes_.find(op);
    if (it != nodes_.end()) return it->second;
    if (op == "or" || op == "implies") return 1;
    if (op == "maj") return 4;
    return 3;
  }
  int order_of(const std::string& op) const {
    return static_cast<int>(std::find(order_.begin(), order_.end(), op) - order_.begin());
  }
  // Precedence without the tie between values: negations (values given
  // that are a `not`, and a `not` of the result), AIG nodes, declared order.
  Key spelling_key(const std::string& op, const std::vector<Lit>& args, bool opposite) const {
    int negations = opposite ? 1 : 0;
    for (Lit a : args) {
      auto it = by_lit_.find(a);
      negations += it != by_lit_.end() && statements_[it->second].op == "not";
    }
    return {negations, aig_nodes(op), order_of(op)};
  }
  Key spelling_bound(const std::string& op, bool opposite) const {
    return {opposite ? 1 : 0, aig_nodes(op), order_of(op)};
  }
  struct Pending {
    size_t size, statement;
    Lit v, target;
    const Variant* var;
    std::vector<Lit> args;
  };
  std::vector<Pending> pending_;

 public:
  void set_plain(bool plain) { plain_ = plain; }
  void set_first_only(bool first_only) { first_only_ = first_only; }
  void set_spellings(bool spellings) { spellings_ = spellings; }
  // The declared order of the registered operations for the precedence
  // rule, and whether opposite spellings are left out.
  void set_precedence(const std::vector<std::string>& order, bool strict) {
    order_ = order;
    precedence_strict_ = strict;
  }
  // Every spelling of each value that is an execution or a `not` of one.
  const std::set<Match>& spelled() const { return spelled_; }
  // Truth tables over every input for each node, and each node's inputs as
  // a bit set, instead of computing them from the graph: for statements
  // that are executions referring to recorded tables, whose nodes have no
  // fanins.
  // Values' functions from an oracle instead of truth tables.
  void set_oracle(MatchOracle* oracle) { oracle_ = oracle; }
  // Steps of the search count against DLP 59's budget.
  void set_budget(StepBudget* budget) { budget_ = budget; }
  void set_tables(std::vector<uint64_t> tables, std::vector<uint32_t> support) {
    given_tables_ = std::move(tables);
    given_support_ = std::move(support);
  }
  // Inputs that only become available just before a statement (by index),
  // in statement order: results of statements that aren't boolean.
  void set_late_inputs(std::vector<std::pair<size_t, Lit>> late) { late_inputs_ = std::move(late); }
  // Each registered operation's number of different `and`s, for the
  // precedence between spellings.
  void set_nodes(std::map<std::string, int> nodes) { nodes_ = std::move(nodes); }
  // DLP 61's restriction that an opposite result removes at least three
  // statements.
  void set_min_opposite_removed(size_t n) { min_opposite_removed_ = n; }
  // Whether to search for matches; off, only spellings are listed.
  void set_matches(bool matches) { matches_ = matches; }
  // Table hashes of literals, to carry over to another search on the same
  // tables.
  std::vector<uint64_t> take_hashes() { return std::move(hash_cache_); }
  void set_hashes(std::vector<uint64_t> hashes) { hash_cache_ = std::move(hashes); }
  // Dead statements (by index) don't read anything: a match's statements are
  // the ones nothing else that's live reads (DLP 59 makes the dead ones an
  // error of their own).
  void set_dead(const std::vector<char>& dead) {
    uses_.assign(statements_.size(), 0);
    for (size_t i = 0; i < statements_.size(); ++i) {
      if (dead[i]) continue;
      for (Lit a : statements_[i].args) {
        auto it = by_lit_.find(a);
        if (it != by_lit_.end()) ++uses_[it->second];
      }
    }
    for (Lit o : g_.outputs) {
      auto it = by_lit_.find(o);
      if (it != by_lit_.end()) ++uses_[it->second];
    }
  }
  // Only these registered operations are searched for (all when empty); the
  // others still decide which opposite results count.
  void set_only(std::set<std::string> names) { only_ = std::move(names); }
  // Exact checks already done, by the values involved: a value keeps its
  // function while a fix loop works on one operation, so a check of the
  // same values against the same operation has the same result.
  // `node_value` gives each node's value; a key is the operation's name
  // and the target's and arguments' values, each doubled plus whether
  // it's negated.
  using HoldsCache = std::map<std::pair<std::string, std::vector<int>>, bool>;
  void set_search_cache(SearchCache* cache) { search_cache_ = cache; }
  void set_holds_cache(HoldsCache* cache, std::vector<int> node_value) {
    holds_cache_ = cache;
    node_value_ = std::move(node_value);
  }

 private:
  std::map<Lit, size_t> by_lit_;
  std::vector<std::vector<std::vector<int>>> perms_;
  size_t words_ = 1;
  uint64_t last_mask_ = ~0ULL;
  std::vector<uint64_t> tables_;
  MatchOracle* oracle_ = nullptr;
  StepBudget* budget_ = nullptr;
  mutable std::vector<uint64_t> hash_cache_;
  std::vector<uint64_t> sample_;
  std::vector<Lit> pool_;
  std::vector<uint32_t> support_;
  std::string anchor_ = "cone";
  uint32_t cut_size_ = 4;
  uint64_t value_cuts_ = 0, value_candidates_ = 0, value_tuples_ = 0;
  std::vector<std::vector<uint64_t>> bits_;
  std::vector<uint64_t> vbits_;
  uint64_t search_nodes_ = 0, exact_checks_ = 0, refinements_ = 0, inessential_ = 0;
  // The search over earlier values.
  std::vector<Variant> variants_;
  std::vector<Lit> resub_pool_;
  std::vector<std::vector<uint64_t>> lit_samples_;  // by pool index, by sample
  std::vector<std::vector<uint64_t>> positions_;    // by sample, by pool index
  std::vector<uint64_t> rsamples_;
  std::vector<int> chosen_;
  std::vector<uint64_t> m0_, m1_;
  uint64_t position_steps_ = 0, leaf_candidates_ = 0;
  std::array<uint64_t, kMaxPoolWords> allowed_{};
  size_t lwords_ = 1;
  std::vector<uint64_t> target_cache_;
  uint32_t target_cache_lit_ = UINT32_MAX;
  size_t target_cache_size_ = 0;
};

}  // namespace beq
