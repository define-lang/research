// A small incremental CDCL SAT solver in the style of MiniSat: two watched
// literals, VSIDS, first-UIP learning with recursive minimization, phase
// saving, Luby restarts, and learnt clause reduction by LBD. ABC's own sweeping
// commands use MiniSat-derived solvers of this kind, so it stands in for them;
// CaDiCaL (through python-sat) is used separately to cross-check hard cases.
#pragma once

#include <algorithm>
#include <cstdint>
#include <vector>

namespace sat {

using Lit = uint32_t;  // 2 * var + negated
inline Lit pos(uint32_t v) { return 2 * v; }
inline Lit neg(uint32_t v) { return 2 * v + 1; }
inline uint32_t var(Lit l) { return l >> 1; }
inline bool sign(Lit l) { return l & 1; }

enum class Result { kSat, kUnsat, kUnknown };

class Solver {
 public:
  uint32_t new_var() {
    uint32_t v = num_vars();
    assign_.push_back(kUndef);
    level_.push_back(0);
    reason_.push_back(kNoReason);
    activity_.push_back(0.0);
    polarity_.push_back(1);
    seen_.push_back(0);
    heap_index_.push_back(-1);
    watches_.emplace_back();
    watches_.emplace_back();
    heap_insert(v);
    return v;
  }

  uint32_t num_vars() const { return static_cast<uint32_t>(assign_.size()); }

  // Declares v = a and b, for justification-based decisions. Once any gate
  // is declared, the solver only branches on fanins of gates that are false
  // with no false fanin, and answers SAT when there are none: every assigned
  // gate is then consistent with some assignment of the unassigned inputs.
  void set_gate(uint32_t v, Lit a, Lit b) {
    if (gate_a_.size() < num_vars()) {
      gate_a_.resize(num_vars(), UINT32_MAX);
      gate_b_.resize(num_vars(), UINT32_MAX);
    }
    gate_a_[v] = a;
    gate_b_[v] = b;
    circuit_ = true;
  }

  // Whether the last satisfying assignment gave v a value.
  bool model_defined(uint32_t v) const { return model_[v] != kUndef; }

  // Adds a clause at decision level 0. Returns false if the formula is now
  // unsatisfiable.
  bool add_clause(std::vector<Lit> lits) {
    if (!ok_) return false;
    std::sort(lits.begin(), lits.end());
    size_t j = 0;
    Lit prev = UINT32_MAX;
    for (Lit l : lits) {
      uint8_t v = value(l);
      if (v == kTrue || l == (prev ^ 1)) return true;
      if (v != kFalse && l != prev) lits[j++] = prev = l;
    }
    lits.resize(j);
    if (lits.empty()) return ok_ = false;
    if (lits.size() == 1) {
      enqueue(lits[0], kNoReason);
      return ok_ = (propagate() == kNoReason);
    }
    uint32_t cref = alloc_clause(lits, false);
    attach(cref);
    ++num_original_;
    return true;
  }

  // Restricts decisions in the next solve calls to these variables. This is
  // sound when the variables are the cone of the assumptions in a circuit:
  // any conflict-free assignment of the cone extends to an evaluation of the
  // whole circuit, which satisfies every clause. An empty scope allows all.
  void set_scope(const std::vector<uint32_t>& vars) {
    ++scope_epoch_;
    if (scope_mark_.size() < num_vars()) scope_mark_.resize(num_vars(), 0);
    for (uint32_t v : vars) scope_mark_[v] = scope_epoch_;
    scoped_ = !vars.empty();
  }

  // Solves under assumptions. conflict_limit < 0 means no limit.
  Result solve(const std::vector<Lit>& assumptions, int64_t conflict_limit) {
    if (!ok_) return Result::kUnsat;
    assumptions_ = assumptions;
    int64_t conflicts_here = 0;
    Result result = Result::kUnknown;
    for (int restart = 0;; ++restart) {
      int64_t budget = static_cast<int64_t>(luby(restart) * 100);
      result = search(budget, conflict_limit, conflicts_here);
      if (result != Result::kUnknown) break;
      if (conflict_limit >= 0 && conflicts_here >= conflict_limit) break;
    }
    if (result == Result::kSat) {
      model_.assign(assign_.begin(), assign_.end());
    }
    backtrack(0);
    for (uint32_t v : parked_)
      if (heap_index_[v] < 0) heap_insert(v);
    parked_.clear();
    return result;
  }

  // Value of a variable in the last satisfying assignment.
  bool model_value(uint32_t v) const { return model_[v] == kTrue; }

  uint64_t conflicts = 0;
  uint64_t decisions = 0;
  uint64_t propagations = 0;

 private:
  static constexpr uint8_t kFalse = 0, kTrue = 1, kUndef = 2;
  static constexpr uint32_t kNoReason = UINT32_MAX;

  struct Watcher {
    uint32_t cref;
    Lit blocker;
  };

  // Clause layout in the arena: [size, learnt | lbd << 1, activity bits, lits...]
  uint32_t& csize(uint32_t c) { return arena_[c]; }
  bool clearnt(uint32_t c) const { return arena_[c + 1] & 1; }
  uint32_t clbd(uint32_t c) const { return arena_[c + 1] >> 1; }
  float& cact(uint32_t c) { return *reinterpret_cast<float*>(&arena_[c + 2]); }
  Lit* clits(uint32_t c) { return &arena_[c + 3]; }

  uint8_t value(Lit l) const {
    uint8_t a = assign_[var(l)];
    return a == kUndef ? kUndef : static_cast<uint8_t>(a ^ sign(l));
  }

  uint32_t alloc_clause(const std::vector<Lit>& lits, bool learnt, uint32_t lbd = 0) {
    uint32_t c = static_cast<uint32_t>(arena_.size());
    arena_.push_back(static_cast<uint32_t>(lits.size()));
    arena_.push_back((learnt ? 1u : 0u) | (lbd << 1));
    arena_.push_back(0);
    cact(c) = 0.0f;
    arena_.insert(arena_.end(), lits.begin(), lits.end());
    if (learnt) learnts_.push_back(c);
    return c;
  }

  void attach(uint32_t c) {
    Lit* l = clits(c);
    watches_[l[0]].push_back({c, l[1]});
    watches_[l[1]].push_back({c, l[0]});
  }

  uint32_t decision_level() const { return static_cast<uint32_t>(trail_lim_.size()); }

  void enqueue(Lit l, uint32_t reason) {
    uint32_t v = var(l);
    assign_[v] = sign(l) ? kFalse : kTrue;
    level_[v] = decision_level();
    reason_[v] = reason;
    trail_.push_back(l);
  }

  uint32_t propagate() {
    uint32_t conflict = kNoReason;
    while (qhead_ < trail_.size()) {
      Lit p = trail_[qhead_++];
      Lit false_lit = p ^ 1;
      std::vector<Watcher>& ws = watches_[false_lit];
      ++propagations;
      size_t i = 0, j = 0;
      const size_t end = ws.size();
      while (i < end) {
        Watcher w = ws[i++];
        if (value(w.blocker) == kTrue) {
          ws[j++] = w;
          continue;
        }
        Lit* c = clits(w.cref);
        if (c[0] == false_lit) std::swap(c[0], c[1]);
        Lit first = c[0];
        Watcher w2{w.cref, first};
        if (first != w.blocker && value(first) == kTrue) {
          ws[j++] = w2;
          continue;
        }
        uint32_t size = csize(w.cref);
        bool moved = false;
        for (uint32_t k = 2; k < size; ++k) {
          if (value(c[k]) != kFalse) {
            std::swap(c[1], c[k]);
            watches_[c[1]].push_back(w2);
            moved = true;
            break;
          }
        }
        if (moved) continue;
        ws[j++] = w2;
        if (value(first) == kFalse) {
          conflict = w.cref;
          qhead_ = static_cast<uint32_t>(trail_.size());
          while (i < end) ws[j++] = ws[i++];
        } else {
          enqueue(first, w.cref);
        }
      }
      ws.resize(j);
      if (conflict != kNoReason) break;
    }
    return conflict;
  }

  uint32_t abstract_level(uint32_t v) const { return 1u << (level_[v] & 31); }

  bool lit_redundant(Lit p, uint32_t abstract_levels) {
    stack_.clear();
    stack_.push_back(p);
    size_t top = to_clear_.size();
    while (!stack_.empty()) {
      uint32_t r = reason_[var(stack_.back())];
      stack_.pop_back();
      Lit* c = clits(r);
      uint32_t size = csize(r);
      for (uint32_t i = 1; i < size; ++i) {
        Lit q = c[i];
        uint32_t v = var(q);
        if (!seen_[v] && level_[v] > 0) {
          if (reason_[v] != kNoReason && (abstract_level(v) & abstract_levels)) {
            seen_[v] = 1;
            stack_.push_back(q);
            to_clear_.push_back(q);
          } else {
            for (size_t k = top; k < to_clear_.size(); ++k) seen_[var(to_clear_[k])] = 0;
            to_clear_.resize(top);
            return false;
          }
        }
      }
    }
    return true;
  }

  void analyze(uint32_t confl, std::vector<Lit>& learnt, uint32_t& bt_level, uint32_t& lbd) {
    learnt.clear();
    learnt.push_back(0);
    int path = 0;
    Lit p = UINT32_MAX;
    size_t index = trail_.size();
    do {
      if (clearnt(confl)) bump_clause(confl);
      Lit* c = clits(confl);
      uint32_t size = csize(confl);
      for (uint32_t j = (p == UINT32_MAX ? 0 : 1); j < size; ++j) {
        Lit q = c[j];
        uint32_t v = var(q);
        if (!seen_[v] && level_[v] > 0) {
          bump_var(v);
          seen_[v] = 1;
          if (level_[v] >= decision_level())
            ++path;
          else
            learnt.push_back(q);
        }
      }
      while (!seen_[var(trail_[--index])]) {
      }
      p = trail_[index];
      confl = reason_[var(p)];
      seen_[var(p)] = 0;
      --path;
    } while (path > 0);
    learnt[0] = p ^ 1;

    to_clear_.assign(learnt.begin(), learnt.end());
    uint32_t abstract_levels = 0;
    for (size_t i = 1; i < learnt.size(); ++i) abstract_levels |= abstract_level(var(learnt[i]));
    size_t j = 1;
    for (size_t i = 1; i < learnt.size(); ++i) {
      uint32_t v = var(learnt[i]);
      if (reason_[v] == kNoReason || !lit_redundant(learnt[i], abstract_levels)) learnt[j++] = learnt[i];
    }
    learnt.resize(j);
    for (Lit l : to_clear_) seen_[var(l)] = 0;

    bt_level = 0;
    if (learnt.size() > 1) {
      size_t max_i = 1;
      for (size_t i = 2; i < learnt.size(); ++i)
        if (level_[var(learnt[i])] > level_[var(learnt[max_i])]) max_i = i;
      std::swap(learnt[1], learnt[max_i]);
      bt_level = level_[var(learnt[1])];
    }
    // LBD: number of distinct decision levels in the clause.
    ++lbd_stamp_;
    lbd = 0;
    for (Lit l : learnt) {
      uint32_t lv = level_[var(l)];
      if (lv >= lbd_seen_.size()) lbd_seen_.resize(lv + 1, 0);
      if (lbd_seen_[lv] != lbd_stamp_) {
        lbd_seen_[lv] = lbd_stamp_;
        ++lbd;
      }
    }
  }

  void backtrack(uint32_t lvl) {
    if (decision_level() <= lvl) return;
    for (size_t c = trail_.size(); c > trail_lim_[lvl]; --c) {
      uint32_t v = var(trail_[c - 1]);
      polarity_[v] = sign(trail_[c - 1]);
      assign_[v] = kUndef;
      reason_[v] = kNoReason;
      if (heap_index_[v] < 0) heap_insert(v);
    }
    qhead_ = trail_lim_[lvl];
    trail_.resize(trail_lim_[lvl]);
    trail_lim_.resize(lvl);
  }

  Result search(int64_t budget, int64_t limit, int64_t& conflicts_here) {
    std::vector<Lit> learnt;
    for (;;) {
      uint32_t confl = propagate();
      if (confl != kNoReason) {
        ++conflicts;
        ++conflicts_here;
        if (decision_level() == 0) {
          ok_ = false;
          return Result::kUnsat;
        }
        uint32_t bt, lbd;
        analyze(confl, learnt, bt, lbd);
        // Never backtrack below the assumption levels for a unit: the unit
        // holds at level 0 regardless of assumptions.
        backtrack(bt);
        if (learnt.size() == 1) {
          enqueue(learnt[0], kNoReason);
        } else {
          uint32_t c = alloc_clause(learnt, true, lbd);
          attach(c);
          bump_clause(c);
          enqueue(learnt[0], c);
        }
        var_inc_ /= 0.95;
        cla_inc_ /= 0.999f;
        --budget;
        if (limit >= 0 && conflicts_here >= limit) {
          backtrack(0);
          return Result::kUnknown;
        }
      } else {
        if (budget <= 0) {
          backtrack(0);
          return Result::kUnknown;
        }
        if (learnts_.size() >= max_learnts_ + trail_.size()) reduce_db();
        Lit next = UINT32_MAX;
        while (decision_level() < assumptions_.size()) {
          Lit a = assumptions_[decision_level()];
          uint8_t v = value(a);
          if (v == kTrue) {
            trail_lim_.push_back(static_cast<uint32_t>(trail_.size()));
          } else if (v == kFalse) {
            return Result::kUnsat;
          } else {
            next = a;
            break;
          }
        }
        if (next == UINT32_MAX && circuit_) {
          next = pick_justification();
          if (next == UINT32_MAX) return Result::kSat;
          ++decisions;
        } else if (next == UINT32_MAX) {
          uint32_t v = pick_branch_var();
          if (v == UINT32_MAX) return Result::kSat;
          next = polarity_[v] ? neg(v) : pos(v);
          ++decisions;
        }
        trail_lim_.push_back(static_cast<uint32_t>(trail_.size()));
        enqueue(next, kNoReason);
      }
    }
  }

  void reduce_db() {
    std::vector<uint32_t> candidates;
    std::vector<uint32_t> keep;
    for (uint32_t c : learnts_) {
      bool locked = false;
      Lit l0 = clits(c)[0];
      if (value(l0) == kTrue && reason_[var(l0)] == c) locked = true;
      if (locked || clbd(c) <= 2)
        keep.push_back(c);
      else
        candidates.push_back(c);
    }
    std::sort(candidates.begin(), candidates.end(), [&](uint32_t a, uint32_t b) {
      if (clbd(a) != clbd(b)) return clbd(a) > clbd(b);
      return cact(a) < cact(b);
    });
    std::vector<char> removed_flag;
    size_t remove_count = candidates.size() / 2;
    std::vector<uint32_t> removed(candidates.begin(), candidates.begin() + static_cast<long>(remove_count));
    keep.insert(keep.end(), candidates.begin() + static_cast<long>(remove_count), candidates.end());
    std::sort(removed.begin(), removed.end());
    compact(removed);
    max_learnts_ = max_learnts_ + max_learnts_ / 10;
  }

  // Rebuilds the arena without the removed learnt clauses.
  void compact(const std::vector<uint32_t>& removed) {
    std::vector<uint32_t> new_arena;
    new_arena.reserve(arena_.size());
    std::vector<uint32_t> new_learnts;
    // Map from old cref to new cref for reasons, through a sorted walk.
    std::vector<std::pair<uint32_t, uint32_t>> moves;
    size_t r = 0;
    for (uint32_t c = 0; c < arena_.size();) {
      uint32_t size = arena_[c];
      uint32_t total = 3 + size;
      if (r < removed.size() && removed[r] == c) {
        ++r;
      } else {
        uint32_t nc = static_cast<uint32_t>(new_arena.size());
        new_arena.insert(new_arena.end(), arena_.begin() + c, arena_.begin() + c + total);
        moves.emplace_back(c, nc);
        if (arena_[c + 1] & 1) new_learnts.push_back(nc);
      }
      c += total;
    }
    auto remap = [&](uint32_t c) {
      auto it = std::lower_bound(moves.begin(), moves.end(), std::make_pair(c, 0u));
      return it->second;
    };
    for (uint32_t v = 0; v < num_vars(); ++v)
      if (reason_[v] != kNoReason) reason_[v] = remap(reason_[v]);
    arena_.swap(new_arena);
    learnts_.swap(new_learnts);
    for (auto& ws : watches_) ws.clear();
    for (auto [old_c, nc] : moves) attach(nc);
  }

  void bump_var(uint32_t v) {
    if ((activity_[v] += var_inc_) > 1e100) {
      for (double& a : activity_) a *= 1e-100;
      var_inc_ *= 1e-100;
    }
    if (heap_index_[v] >= 0) heap_up(heap_index_[v]);
  }

  void bump_clause(uint32_t c) {
    if ((cact(c) += cla_inc_) > 1e20f) {
      for (uint32_t l : learnts_) cact(l) *= 1e-20f;
      cla_inc_ *= 1e-20f;
    }
  }

  // Finds the most recently assigned false gate with no false fanin and
  // returns a decision that makes one of its fanins false.
  Lit pick_justification() {
    if (gate_a_.size() < num_vars()) {
      gate_a_.resize(num_vars(), UINT32_MAX);
      gate_b_.resize(num_vars(), UINT32_MAX);
    }
    // Facts at level 0 hold in every assignment of the circuit, so they never
    // need justifying.
    const size_t begin = trail_lim_.empty() ? trail_.size() : trail_lim_[0];
    for (size_t i = trail_.size(); i > begin; --i) {
      Lit l = trail_[i - 1];
      uint32_t v = var(l);
      if (gate_a_[v] == UINT32_MAX || !sign(l)) continue;
      Lit a = gate_a_[v], b = gate_b_[v];
      if (value(a) == kFalse || value(b) == kFalse) continue;
      // Propagation would have made the other fanin false if one were true,
      // so both are unassigned here.
      Lit pick = activity_[var(a)] >= activity_[var(b)] ? a : b;
      return pick ^ 1;
    }
    return UINT32_MAX;
  }

  uint32_t pick_branch_var() {
    while (!heap_.empty()) {
      uint32_t v = heap_[0];
      heap_remove_top();
      if (assign_[v] != kUndef) continue;
      if (scoped_ && (v >= scope_mark_.size() || scope_mark_[v] != scope_epoch_)) {
        parked_.push_back(v);
        continue;
      }
      return v;
    }
    return UINT32_MAX;
  }

  static double luby(int x) {
    int size = 1, seq = 0;
    while (size < x + 1) {
      ++seq;
      size = 2 * size + 1;
    }
    while (size - 1 != x) {
      size = (size - 1) >> 1;
      --seq;
      x = x % size;
    }
    double r = 1;
    for (int i = 0; i < seq; ++i) r *= 2;
    return r;
  }

  // Binary max-heap on activity.
  void heap_insert(uint32_t v) {
    heap_index_[v] = static_cast<int32_t>(heap_.size());
    heap_.push_back(v);
    heap_up(heap_index_[v]);
  }
  void heap_up(int32_t i) {
    uint32_t v = heap_[i];
    while (i > 0) {
      int32_t p = (i - 1) / 2;
      if (activity_[heap_[p]] >= activity_[v]) break;
      heap_[i] = heap_[p];
      heap_index_[heap_[i]] = i;
      i = p;
    }
    heap_[i] = v;
    heap_index_[v] = i;
  }
  void heap_remove_top() {
    uint32_t top = heap_[0];
    heap_index_[top] = -1;
    uint32_t last = heap_.back();
    heap_.pop_back();
    if (heap_.empty()) return;
    int32_t i = 0;
    int32_t n = static_cast<int32_t>(heap_.size());
    for (;;) {
      int32_t c = 2 * i + 1;
      if (c >= n) break;
      if (c + 1 < n && activity_[heap_[c + 1]] > activity_[heap_[c]]) ++c;
      if (activity_[heap_[c]] <= activity_[last]) break;
      heap_[i] = heap_[c];
      heap_index_[heap_[i]] = i;
      i = c;
    }
    heap_[i] = last;
    heap_index_[last] = i;
  }

  bool ok_ = true;
  std::vector<uint32_t> arena_;
  std::vector<uint32_t> learnts_;
  std::vector<std::vector<Watcher>> watches_;
  std::vector<uint8_t> assign_;
  std::vector<uint32_t> level_;
  std::vector<uint32_t> reason_;
  std::vector<double> activity_;
  std::vector<uint8_t> polarity_;
  std::vector<uint8_t> seen_;
  std::vector<int32_t> heap_index_;
  std::vector<uint32_t> heap_;
  std::vector<Lit> gate_a_, gate_b_;
  std::vector<uint32_t> scope_mark_, parked_;
  uint32_t scope_epoch_ = 0;
  bool scoped_ = false;
  bool circuit_ = false;
  std::vector<Lit> trail_;
  std::vector<uint32_t> trail_lim_;
  std::vector<Lit> assumptions_;
  std::vector<uint8_t> model_;
  std::vector<Lit> stack_, to_clear_;
  std::vector<uint32_t> lbd_seen_;
  uint32_t lbd_stamp_ = 0;
  uint32_t qhead_ = 0;
  double var_inc_ = 1.0;
  float cla_inc_ = 1.0f;
  size_t max_learnts_ = 4000;
  uint64_t num_original_ = 0;
};

}  // namespace sat
