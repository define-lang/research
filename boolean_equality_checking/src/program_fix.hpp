// The fixes a refactoring tool applies to a whole program until it
// compiles (DLP 59's refactoring steps, structural rewrites, literal
// propagation / constant folding / callee specialization, useless-input
// elimination, DLP 60's order and grouping, DLP 61's factoring, and DLP 62's matches,
// spellings, and wrappers), with every operation fixed after the ones it
// executes.
#pragma once

#include <optional>
#include <tuple>

#include "program.hpp"

namespace beq {

class ProgramFixer {
 public:
  struct OpResult {
    std::string name;
    int rounds = 0;
    double seconds = 0;
    std::string status = "ok";
    std::map<std::string, int> fixes;
  };

  // One line per operation fixed, as it's fixed: NAME PASS ROUNDS SECONDS
  // STATUS, then FIX=COUNT for each kind of fix.
  std::ostream* progress = nullptr;
  // Seconds spent in each part of fixing, over every operation, and the
  // checks' own parts.
  std::map<std::string, double> phase_s;
  CheckTimes check_times;

  explicit ProgramFixer(ProgramChecker& checker) : c_(checker), p_(checker.program()) {
    c_.statement_limit = false;
    c_.reuse_values = true;
    c_.first_fix_only = true;
  }

  std::vector<OpResult> fix_all(int max_rounds) {
    std::vector<OpResult> out;
    std::map<size_t, size_t> result_of;
    std::vector<size_t> first, rest;
    for (size_t i = 0; i < p_.ops.size(); ++i) {
      init_op_tracking(p_.ops[i]);
      // The fixes may pass DLP 59's statement limit on the way to a smaller
      // operation, but an operation written past it is the programmer's.
      const auto& stmts = p_.ops[i].stmts;
      if ((c_.max_views > 0 && static_cast<uint32_t>(p_.ops[i].nbool) > c_.max_views) ||
          std::count_if(stmts.begin(), stmts.end(), [](const PStmt& s) { return is_boolean_statement(s.kind); }) > 256)
        over_limit_.insert(p_.ops[i].name);
      (c_.in_registered_reach(p_.ops[i].name) ? first : rest).push_back(i);
    }
    // The registered operations and what they execute come first, until
    // they compile: only a match in one of them can write out executions in
    // a registered operation's definition, which changes the spellings of
    // every operation, and nothing they execute is fixed later.
    fix_until_stable(first, true, max_rounds, out, result_of);
    fix_until_stable(rest, false, max_rounds, out, result_of);
    for (OpResult& hr : helper_results_) out.push_back(std::move(hr));
    helper_results_.clear();
    Phase p{phase_s, "finish"};
    finish();
    return out;
  }

  // What each removed operation (or removed/extracted output view) was
  // replaced by, one line each, with view numbers 1-based among the operation's
  // original views and `@K` for the K-th (1-based) new output of a mixed op:
  //   NAME - dropped K ...
  //   NAME O literal T|F
  //   NAME O view K
  //   NAME O out @K
  //   NAME O statement KIND [OP] ARG...
  void write_replacements(std::ostream& out) const {
    // NAME - dropped K ...: read views removed (from 1, among the views the
    // operation was written with).
    for (const auto& [name, dropped] : dropped_) {
      if (synthesized_.count(name) || dropped.empty()) continue;
      out << name << " - dropped";
      for (int v : dropped) out << " " << v;
      out << "\n";
    }
    for (const auto& [name, r] : bool_replacements_) {
      if (synthesized_.count(name)) continue;
      write_bool_replacement_line(out, name, 0, r);
    }
    for (const auto& [name, exprs] : orig_out_exprs_) {
      if (synthesized_.count(name)) continue;
      const bool gone = removed_.count(name) > 0;
      for (size_t o = 0; o < exprs.size(); ++o) {
        const MixedOutExpr& e = exprs[o];
        if (!gone && e.kind == MixedOutExpr::kNewOut) continue;
        write_mixed_out_line(out, name, o, e);
      }
    }
  }

 private:
  struct OutRef {
    enum Kind { kView, kNewOut, kLiteral } kind = kView;
    int index = 0;  // 1-based view index (current in SigChange, original in orig_out_exprs_); 0-based new output index
    std::string literal;
  };

  struct MixedOutExpr {
    enum Kind { kNewOut, kLiteral, kView, kCall } kind = kNewOut;
    int index = 0;  // 0-based new output index (kNewOut), or 1-based view index (kView)
    std::string literal;
    std::string callee;
    std::vector<OutRef> args;
  };

  struct BoolReplacement {
    std::string kind;  // "literal", "view", "statement"
    std::string literal;
    int view = 0;     // 0-based view index (among current views in SigChange, original 0-based in bool_replacements_)
    PStmt statement;  // args have 1-based view indices (or literal)
  };

  struct SigChange {
    enum Kind { kDropBoolViews, kReplaceBoolOp, kSplitBoolOp, kRemapMixedOutputs } kind = kDropBoolViews;
    std::vector<int> dropped_views;  // 1-based sorted indices among current boolean views
    BoolReplacement bool_rep;
    std::vector<std::string> split_helpers;
    int new_out_count = 0;
    std::vector<MixedOutExpr> out_exprs;
  };

  // Adds the time from its making to its end to phase_s[name].
  struct Phase {
    std::map<std::string, double>& seconds;
    const char* name;
    double start = ProgramChecker::now();
    ~Phase() { seconds[name] += ProgramChecker::now() - start; }
  };

  void init_op_tracking(const POp& op) {
    orig_nbool_[op.name] = op.nbool;
    std::vector<int> bviews(static_cast<size_t>(op.nbool));
    for (int i = 0; i < op.nbool; ++i) bviews[static_cast<size_t>(i)] = i + 1;
    orig_bool_views_[op.name] = std::move(bviews);
    if (!op.boolean) {
      std::vector<MixedOutExpr> exprs(op.outs.size());
      for (size_t o = 0; o < op.outs.size(); ++o) {
        exprs[o].kind = MixedOutExpr::kNewOut;
        exprs[o].index = static_cast<int>(o);
      }
      orig_out_exprs_[op.name] = std::move(exprs);
    }
  }

  int current_to_orig_view(const std::string& name, int cur_view) const {
    const std::vector<int>& bv = orig_bool_views_.at(name);
    if (cur_view <= static_cast<int>(bv.size())) return bv[static_cast<size_t>(cur_view - 1)];
    return orig_nbool_.at(name) + (cur_view - static_cast<int>(bv.size()));
  }

  size_t history_size(const std::string& name) const {
    auto it = history_.find(name);
    return it == history_.end() ? 0 : it->second.size();
  }

  std::string unique_op_name(const std::string& base) const {
    if (!c_.has_op(base)) return base;
    for (int k = 2;; ++k) {
      std::string cand = base + "_" + std::to_string(k);
      if (!c_.has_op(cand)) return cand;
    }
  }

  size_t add_helper_op(POp helper, bool is_spec) {
    synthesized_.insert(helper.name);
    if (is_spec)
      spec_ops_.insert(helper.name);
    else
      extracted_ops_.insert(helper.name);
    init_op_tracking(helper);
    return c_.add_op(std::move(helper));
  }

  static void write_bool_replacement_line(std::ostream& out, const std::string& name, size_t view_idx,
                                          const BoolReplacement& r) {
    if (r.kind.empty()) return;
    out << name << " " << view_idx << " " << r.kind;
    if (r.kind == "literal") out << " " << r.literal;
    if (r.kind == "view") out << " " << r.view + 1;
    if (r.kind == "statement") {
      out << " " << r.statement.kind;
      if (!r.statement.name.empty()) out << " " << r.statement.name;
      for (const PArg& a : r.statement.args) out << " " << (a.is_literal() ? a.literal : std::to_string(a.id));
    }
    out << "\n";
  }

  static std::string out_ref_token(const OutRef& r) {
    if (r.kind == OutRef::kLiteral) return r.literal;
    if (r.kind == OutRef::kNewOut) return "@" + std::to_string(r.index + 1);
    return std::to_string(r.index);
  }

  // Resolves a helper call expression through the helper's signature history
  // (drops and final boolean replacement) for human-readable replacement output.
  void write_mixed_out_line(std::ostream& out, const std::string& name, size_t view_idx,
                            const MixedOutExpr& expr) const {
    if (expr.kind == MixedOutExpr::kLiteral) {
      out << name << " " << view_idx << " literal " << expr.literal << "\n";
      return;
    }
    if (expr.kind == MixedOutExpr::kView) {
      out << name << " " << view_idx << " view " << expr.index << "\n";
      return;
    }
    if (expr.kind == MixedOutExpr::kNewOut) {
      out << name << " " << view_idx << " out @" << (expr.index + 1) << "\n";
      return;
    }
    // kCall: replay callee's history on `args`.
    std::string callee = expr.callee;
    std::vector<OutRef> args = expr.args;
    for (;;) {
      auto hit = history_.find(callee);
      if (hit == history_.end()) break;
      bool redirected = false;
      for (const SigChange& sc : hit->second) {
        if (sc.kind == SigChange::kDropBoolViews) {
          std::vector<OutRef> kept;
          for (size_t i = 0; i < args.size(); ++i)
            if (!std::binary_search(sc.dropped_views.begin(), sc.dropped_views.end(), static_cast<int>(i + 1)))
              kept.push_back(args[i]);
          args = std::move(kept);
        } else if (sc.kind == SigChange::kReplaceBoolOp) {
          const BoolReplacement& r = sc.bool_rep;
          if (r.kind == "literal") {
            out << name << " " << view_idx << " literal " << r.literal << "\n";
            return;
          }
          if (r.kind == "view") {
            const OutRef& ref = args[static_cast<size_t>(r.view)];
            if (ref.kind == OutRef::kLiteral)
              out << name << " " << view_idx << " literal " << ref.literal << "\n";
            else if (ref.kind == OutRef::kNewOut)
              out << name << " " << view_idx << " out @" << (ref.index + 1) << "\n";
            else
              out << name << " " << view_idx << " view " << ref.index << "\n";
            return;
          }
          if (r.kind == "statement") {
            std::vector<OutRef> next_args;
            for (const PArg& a : r.statement.args) {
              if (a.is_literal())
                next_args.push_back({OutRef::kLiteral, 0, a.literal});
              else
                next_args.push_back(args[static_cast<size_t>(a.id - 1)]);
            }
            if (r.statement.kind == "call" && history_.count(r.statement.name)) {
              callee = r.statement.name;
              args = std::move(next_args);
              redirected = true;
              break;
            }
            out << name << " " << view_idx << " statement " << r.statement.kind;
            if (!r.statement.name.empty()) out << " " << r.statement.name;
            for (const OutRef& nr : next_args) out << " " << out_ref_token(nr);
            out << "\n";
            return;
          }
        }
      }
      if (!redirected) break;
    }
    out << name << " " << view_idx << " statement call " << callee;
    for (const OutRef& a : args) out << " " << out_ref_token(a);
    out << "\n";
  }

  // Updates `orig_out_exprs_[name]` after a `RemapMixedOutputs` step whose
  // `step_exprs` use current output and current view indices.
  void compose_orig_out_exprs(const std::string& name, const std::vector<MixedOutExpr>& step_exprs) {
    auto it = orig_out_exprs_.find(name);
    if (it == orig_out_exprs_.end()) return;
    // First convert step_exprs' current view indices to original view indices.
    std::vector<MixedOutExpr> orig_step = step_exprs;
    for (MixedOutExpr& e : orig_step) {
      if (e.kind == MixedOutExpr::kView) e.index = current_to_orig_view(name, e.index);
      if (e.kind == MixedOutExpr::kCall) {
        for (OutRef& r : e.args)
          if (r.kind == OutRef::kView) r.index = current_to_orig_view(name, r.index);
      }
    }
    for (MixedOutExpr& cur : it->second) {
      if (cur.kind == MixedOutExpr::kNewOut) {
        cur = orig_step[static_cast<size_t>(cur.index)];
      } else if (cur.kind == MixedOutExpr::kCall) {
        for (OutRef& r : cur.args) {
          if (r.kind != OutRef::kNewOut) continue;
          const MixedOutExpr& sub = orig_step[static_cast<size_t>(r.index)];
          if (sub.kind == MixedOutExpr::kNewOut) {
            r.index = sub.index;
          } else if (sub.kind == MixedOutExpr::kLiteral) {
            r.kind = OutRef::kLiteral;
            r.literal = sub.literal;
          } else if (sub.kind == MixedOutExpr::kView) {
            r.kind = OutRef::kView;
            r.index = sub.index;
          }
        }
      }
    }
  }

  OpResult fix_op(size_t index, int max_rounds) {
    OpResult res;
    res.name = p_.ops[index].name;
    if (over_limit_.count(res.name)) {
      res.status = "limits";
      return res;
    }
    const double t0 = ProgramChecker::now();
    c_.forget_values();
    {
      Phase p{phase_s, "replacements"};
      apply_replacements(index);
    }
    // Structural rewrite (DLP 59 Problem 6): multi-output bool ops split into
    // one single-output bool op per output view; 0-output bool ops stop cleanly.
    if (p_.ops[index].boolean && p_.ops[index].outs.size() != 1) {
      if (p_.ops[index].outs.empty() || c_.is_registered(p_.ops[index].name)) {
        res.status = "outputs";
        res.seconds = ProgramChecker::now() - t0;
        return res;
      }
      Phase p{phase_s, "split bool"};
      const std::string err = split_bool_op(index, max_rounds);
      if (!err.empty()) {
        res.status = err;
      } else {
        ++res.fixes["split outputs"];
      }
      res.seconds = ProgramChecker::now() - t0;
      return res;
    }

    bool done = false;
    for (int round = 0; round < max_rounds && !done; ++round) {
      {
        Phase p{phase_s, "replacements"};
        apply_replacements(index);
      }
      // Statements a fix leaves dead are part of that fix; the ones dead
      // before any fix are errors of their own.
      int dead = 0;
      {
        Phase p{phase_s, "canonicalize"};
        dead = canonicalize(index);
      }
      if (round == 0) res.fixes["dead"] += dead;
      res.rounds = round;

      // Literal propagation, constant folding, and callee specialization.
      {
        Phase p{phase_s, "literals"};
        const FoldStatus fs = fold_literals(index, max_rounds, res);
        if (fs == FoldStatus::kChanged) continue;
        if (fs == FoldStatus::kError) break;
      }

      // Constant boolean output views (after literal folding).
      if (p_.ops[index].boolean && p_.ops[index].outs.size() == 1 && p_.ops[index].outs[0].is_literal()) {
        if (c_.is_registered(p_.ops[index].name)) {
          res.status = "constant";
          break;
        }
        done = true;
        break;
      }
      if (!p_.ops[index].boolean && remove_constant_mixed_outputs(index)) {
        ++res.fixes["constant output"];
        c_.forget_values();
        if (removed_.count(p_.ops[index].name)) {
          done = true;
          break;
        }
        continue;
      }

      Report rep;
      {
        Phase p{phase_s, "check"};
        rep = c_.check(index, true, "tt");
      }
      check_times.add(rep.times);
      if (rep.errors.count("limits")) {
        res.status = "limits";
        break;
      }
      // A cycle is the programmer's to break: the fixes never make one.
      if (rep.errors.count("cycle")) {
        res.status = "cycle";
        break;
      }
      if (rep.errors.count("outputs")) {
        res.status = "outputs";
        break;
      }
      if (rep.literal_stmt >= 0) {
        res.status = "literal";
        break;
      }
      if (rep.redundant_kind == "constant") {
        Phase p{phase_s, "constant"};
        PArg lit;
        lit.literal = rep.redundant_other ? "T" : "F";
        replace_reads(p_.ops[index], rep.redundant_value, lit);
        ++res.fixes["constant"];
        c_.forget_values();
        continue;
      }
      if (!rep.redundant_kind.empty()) {
        // Every redundant value, up to an opposite value that's already a
        // `not`, at once: each is still a fix after the others, which keep
        // every function, and doing them together saves a check of the
        // whole operation for each.
        Phase p{phase_s, "redundant values"};
        POp& op = p_.ops[index];
        for (const Report::Merge& m : rep.merges) {
          if (m.opposite) {
            PStmt& st = stmt_of(op, m.value);
            st.kind = "not";
            st.name.clear();
            st.args = {m.with};
            ++res.fixes["opposite value"];
            continue;
          }
          replace_reads(op, m.value, m.with);
          ++res.fixes["redundant"];
        }
        continue;
      }
      if (!rep.unused_views.empty()) {
        Phase p{phase_s, "unused views"};
        drop_views(index, rep.unused_views);
        ++res.fixes["unused view"];
        continue;
      }
      if (rep.errors.count("wrapper")) {
        if (c_.is_registered(p_.ops[index].name)) {
          res.status = "registered wrapper";
          break;
        }
        ++res.fixes["wrapper"];
        done = true;
        break;
      }
      if (rep.has_factor) {
        Phase p{phase_s, "factor"};
        if (apply_factor(p_.ops[index], rep.factor)) {
          ++res.fixes["factor"];
          continue;
        }
      }
      if (rep.has_match) {
        // Every match in the order DLP 62 reports them, largest first, each
        // with the highest-precedence spelling among the matches of the
        // same value and size, as long as its statements and arguments
        // don't overlap a match already chosen: each is then still a match
        // after the others, which keep every function, and doing them
        // together saves a check of the whole operation for each.
        Phase p{phase_s, "matches"};
        std::vector<const Report::Found*> chosen;
        std::set<int> gone, read;
        const OpInfo info = c_.analyze(p_.ops[index]);
        std::unordered_map<int, const Report::Found*> best_for_value;
        std::vector<int> value_order;
        for (const Report::Found& f : rep.matches) {
          auto [it, inserted] = best_for_value.try_emplace(f.value, &f);
          if (inserted) {
            value_order.push_back(f.value);
          } else if (f.removed == it->second->removed && spelling_before(index, info, f, *it->second)) {
            it->second = &f;
          }
        }
        for (int v : value_order) {
          const Report::Found* best = best_for_value.at(v);
          bool overlaps = false;
          for (int x : best->removed_values) overlaps |= gone.count(x) > 0 || read.count(x) > 0;
          for (int a : best->args) overlaps |= gone.count(a) > 0;
          if (overlaps) continue;
          chosen.push_back(best);
          gone.insert(best->removed_values.begin(), best->removed_values.end());
          read.insert(best->args.begin(), best->args.end());
        }
        bool cycle = false;
        for (const Report::Found* best : chosen) {
          const int written =
              write_out_leading_back(best->op.rfind("not:", 0) == 0 ? best->op.substr(4) : best->op, index);
          if (written < 0) {
            cycle = true;
            break;
          }
          if (written > 0) res.fixes["write out"] += written;
          apply_execution(p_.ops[index], *best);
          ++res.fixes[best->op.rfind("not:", 0) == 0 ? "opposite match" : "match"];
        }
        if (cycle) {
          res.status = "cycle";
          break;
        }
        continue;
      }
      if (rep.has_spelling) {
        Phase p{phase_s, "spellings"};
        const int written = write_out_leading_back(rep.spelling.op, index);
        if (written < 0) {
          res.status = "cycle";
          break;
        }
        if (written > 0) res.fixes["write out"] += written;
        apply_execution(p_.ops[index], rep.spelling);
        ++res.fixes["spelling"];
        continue;
      }
      if (rep.errors.count("order_grouping")) {
        Phase p{phase_s, "grouping"};
        if (regroup_associative(p_.ops[index])) {
          ++res.fixes["grouping"];
          continue;
        }
      }
      if (rep.errors.count("useless_input")) {
        Phase p{phase_s, "useless input"};
        if (!rep.useless_targets.empty()) {
          eliminate_useless_target(index, rep.useless_targets[0].target_id, rep.useless_targets[0].input_id);
          ++res.fixes["useless input"];
          c_.forget_values();
          continue;
        }
        if (!rep.unused_mixed_inputs.empty()) {
          const std::string err = eliminate_unused_mixed_input(index, rep.unused_mixed_inputs, max_rounds);
          if (!err.empty()) {
            res.status = err;
            break;
          }
          ++res.fixes["useless input"];
          c_.forget_values();
          continue;
        }
        res.status = "useless_input";
        break;
      }
      if (rep.errors.count("mixed_bool_view") || rep.errors.count("mixed_shared_input")) {
        Phase p{phase_s, "mixed outputs"};
        const std::string err = fix_mixed_outputs(index, max_rounds);
        if (!err.empty()) {
          res.status = err;
          break;
        }
        ++res.fixes["mixed output"];
        c_.forget_values();
        if (removed_.count(p_.ops[index].name)) {
          done = true;
          break;
        }
        continue;
      }
      if (rep.errors.count("order_grouping") || rep.errors.count("order_arguments") ||
          rep.errors.count("order_statements") || rep.errors.count("order_factor")) {
        res.status = "order";
        break;
      }
      done = true;
    }
    if (!done && res.status == "ok") res.status = "rounds";
    if (done && !removed_.count(p_.ops[index].name)) {
      Phase p{phase_s, "settle"};
      settle(index);
    }
    res.seconds = ProgramChecker::now() - t0;
    return res;
  }

  enum class FoldStatus { kNone, kChanged, kError };

  // Folds boolean literals through `not`, `and`, `call` (specialization), and
  // `run` (specialization). Stops with `status = "literal"` only when a boolean
  // literal reaches an opaque non-boolean logical operation (`num` or `cmp`).
  FoldStatus fold_literals(size_t index, int max_rounds, OpResult& res) {
    const size_t nstmts = p_.ops[index].stmts.size();
    for (size_t k = 0; k < nstmts; ++k) {
      const PStmt& s = p_.ops[index].stmts[k];
      if (s.kind == "copy") continue;
      bool has_bool_lit = false;
      for (const PArg& a : s.args)
        if (a.is_literal() && (a.literal == "T" || a.literal == "F")) has_bool_lit = true;
      if (!has_bool_lit) continue;

      if (s.kind == "not") {
        PArg folded;
        folded.literal = s.args[0].literal == "T" ? "F" : "T";
        const int id = s.ids[0];
        p_.ops[index].stmts.erase(p_.ops[index].stmts.begin() + static_cast<std::ptrdiff_t>(k));
        replace_reads(p_.ops[index], id, folded);
        ++res.fixes["literal"];
        c_.forget_values();
        return FoldStatus::kChanged;
      }
      if (s.kind == "and") {
        PArg folded;
        if ((s.args[0].is_literal() && s.args[0].literal == "F") ||
            (s.args[1].is_literal() && s.args[1].literal == "F")) {
          folded.literal = "F";
        } else if (s.args[0].is_literal() && s.args[0].literal == "T") {
          folded = s.args[1];
        } else {
          folded = s.args[0];
        }
        const int id = s.ids[0];
        p_.ops[index].stmts.erase(p_.ops[index].stmts.begin() + static_cast<std::ptrdiff_t>(k));
        replace_reads(p_.ops[index], id, folded);
        ++res.fixes["literal"];
        c_.forget_values();
        return FoldStatus::kChanged;
      }
      if (s.kind == "call" || s.kind == "run") {
        const std::string callee_name = s.name;
        const size_t callee_idx = static_cast<size_t>(c_.index_of(callee_name));
        const int callee_nbool = p_.ops[callee_idx].nbool;
        // Check whether a boolean literal appears at a non-boolean view slot.
        for (size_t i = static_cast<size_t>(callee_nbool); i < s.args.size(); ++i) {
          if (s.args[i].is_literal() && (s.args[i].literal == "T" || s.args[i].literal == "F")) {
            res.status = "literal";
            return FoldStatus::kError;
          }
        }
        std::string mask;
        std::string suffix;
        for (int i = 0; i < callee_nbool; ++i) {
          const PArg& a = s.args[static_cast<size_t>(i)];
          if (a.is_literal() && (a.literal == "T" || a.literal == "F")) {
            mask.push_back(a.literal[0]);
            if (!suffix.empty()) suffix += "_";
            suffix += std::to_string(i + 1) + a.literal;
          } else {
            mask.push_back('-');
          }
        }
        const SpecKey key{callee_name, history_size(callee_name), "lit:" + mask};
        std::string spec_name;
        auto sit = specializations_.find(key);
        if (sit != specializations_.end()) {
          spec_name = sit->second;
        } else {
          POp spec = p_.ops[callee_idx];
          spec.name = unique_op_name(callee_name + "__L" + suffix);
          const int old_views = spec.views();
          std::unordered_map<int, PArg> view_sub;
          int new_nbool = 0;
          for (int v = 1; v <= callee_nbool; ++v) {
            const char m = mask[static_cast<size_t>(v - 1)];
            if (m == 'T' || m == 'F') {
              view_sub[v] = PArg{0, std::string(1, m)};
            } else {
              ++new_nbool;
              view_sub[v] = PArg{new_nbool, ""};
            }
          }
          for (int v = callee_nbool + 1; v <= old_views; ++v) {
            view_sub[v] = PArg{new_nbool + (v - callee_nbool), ""};
          }
          for (PStmt& st : spec.stmts)
            for (PArg& a : st.args)
              if (!a.is_literal() && a.id <= old_views) a = view_sub.at(a.id);
          for (PArg& a : spec.outs)
            if (!a.is_literal() && a.id <= old_views) a = view_sub.at(a.id);
          spec.nbool = new_nbool;
          spec_name = spec.name;
          const size_t spec_idx = add_helper_op(std::move(spec), /*is_spec=*/true);
          OpResult spec_res = fix_op(spec_idx, max_rounds);
          c_.forget_values();
          if (spec_res.status != "ok") {
            removed_.insert(spec_name);
            res.status = spec_res.status;
            return FoldStatus::kError;
          }
          specializations_[key] = spec_name;
          helper_results_.push_back(std::move(spec_res));
        }
        // Re-fetch `p_.ops[index]` because `add_helper_op` may reallocate `p_.ops`.
        PStmt& stmt = p_.ops[index].stmts[k];
        std::vector<PArg> new_args;
        for (size_t i = 0; i < stmt.args.size(); ++i) {
          if (static_cast<int>(i) < callee_nbool && mask[i] != '-') continue;
          new_args.push_back(stmt.args[i]);
        }
        stmt.name = spec_name;
        stmt.args = std::move(new_args);
        stmt.applied_version = 0;
        ++res.fixes["specialize"];
        c_.forget_values();
        return FoldStatus::kChanged;
      }
      // Opaque non-Boolean Logical Operation (`num` or `cmp`) receiving a boolean literal.
      res.status = "literal";
      return FoldStatus::kError;
    }
    return FoldStatus::kNone;
  }

  // Splits a multi-output `bool` op into one single-output `bool` op per output
  // view, fixes each helper immediately, and records `kSplitBoolOp` for callers.
  std::string split_bool_op(size_t index, int max_rounds) {
    const POp orig = p_.ops[index];
    std::vector<std::string> helpers;
    std::vector<MixedOutExpr> out_exprs;
    helpers.reserve(orig.outs.size());
    out_exprs.reserve(orig.outs.size());
    for (size_t o = 0; o < orig.outs.size(); ++o) {
      POp sub = orig;
      sub.name = unique_op_name(orig.name + "__out" + std::to_string(o + 1));
      sub.outs = {orig.outs[o]};
      const std::string hname = sub.name;
      const size_t hidx = add_helper_op(std::move(sub), /*is_spec=*/false);
      OpResult hres = fix_op(hidx, max_rounds);
      c_.forget_values();
      if (hres.status != "ok") return hres.status;
      helper_results_.push_back(std::move(hres));
      helpers.push_back(hname);
      MixedOutExpr expr;
      expr.kind = MixedOutExpr::kCall;
      expr.callee = hname;
      for (int v = 1; v <= orig.nbool; ++v) expr.args.push_back({OutRef::kView, v, ""});
      out_exprs.push_back(std::move(expr));
    }
    SigChange sc;
    sc.kind = SigChange::kSplitBoolOp;
    sc.split_helpers = std::move(helpers);
    history_[orig.name].push_back(std::move(sc));
    orig_out_exprs_[orig.name] = std::move(out_exprs);
    removed_.insert(orig.name);
    return "";
  }

  // Removes any constant boolean outputs (`T` or `F`) from a mixed op and
  // records `kRemapMixedOutputs` so callers substitute the literals.
  bool remove_constant_mixed_outputs(size_t index) {
    POp& op = p_.ops[index];
    bool any = false;
    for (const PArg& a : op.outs)
      if (a.is_literal() && (a.literal == "T" || a.literal == "F")) any = true;
    if (!any) return false;
    std::vector<PArg> new_outs;
    std::vector<MixedOutExpr> exprs;
    exprs.reserve(op.outs.size());
    for (const PArg& a : op.outs) {
      MixedOutExpr e;
      if (a.is_literal() && (a.literal == "T" || a.literal == "F")) {
        e.kind = MixedOutExpr::kLiteral;
        e.literal = a.literal;
      } else {
        e.kind = MixedOutExpr::kNewOut;
        e.index = static_cast<int>(new_outs.size());
        new_outs.push_back(a);
      }
      exprs.push_back(std::move(e));
    }
    const std::string name = op.name;
    op.outs = std::move(new_outs);
    compose_orig_out_exprs(name, exprs);
    SigChange sc;
    sc.kind = SigChange::kRemapMixedOutputs;
    sc.new_out_count = static_cast<int>(op.outs.size());
    sc.out_exprs = std::move(exprs);
    history_[name].push_back(std::move(sc));
    if (op.outs.empty()) removed_.insert(name);
    return true;
  }

  // Clones `target_id`'s boolean sub-DAG with `input_id` replaced by `F`,
  // preserving all other reads of `input_id` and intermediate nodes.
  void eliminate_useless_target(size_t index, int target_id, int input_id) {
    POp& op = p_.ops[index];
    const OpInfo info = c_.analyze(op);
    const int resolved_target = info.resolve(target_id);
    const int resolved_input = info.resolve(input_id);
    std::set<int> visited;
    std::vector<int> stmt_indices;
    std::function<void(int)> collect = [&](int v) {
      v = info.resolve(v);
      if (!visited.insert(v).second) return;
      if (info.input_number.count(v)) return;
      const int si = info.values.at(v).stmt;
      if (si < 0) return;
      const PStmt& s = op.stmts[static_cast<size_t>(si)];
      if (!is_boolean_statement(s.kind)) return;
      for (const PArg& a : s.args)
        if (!a.is_literal()) collect(a.id);
      stmt_indices.push_back(si);
    };
    collect(resolved_target);
    std::sort(stmt_indices.begin(), stmt_indices.end());
    std::unordered_map<int, int> clone_map;
    std::vector<PStmt> cloned;
    cloned.reserve(stmt_indices.size());
    for (int si : stmt_indices) {
      const PStmt& orig = op.stmts[static_cast<size_t>(si)];
      PStmt c = orig;
      for (PArg& a : c.args) {
        if (a.is_literal()) continue;
        const int r = info.resolve(a.id);
        if (r == resolved_input) {
          a = PArg{0, "F"};
        } else if (clone_map.count(r)) {
          a = PArg{clone_map.at(r), ""};
        } else {
          a = PArg{r, ""};
        }
      }
      const int fresh = op.next_id++;
      clone_map[orig.ids[0]] = fresh;
      c.ids = {fresh};
      cloned.push_back(std::move(c));
    }
    const size_t insert_at = stmt_index(op, resolved_target);
    const PArg replacement{clone_map.at(resolved_target), ""};
    op.stmts.insert(op.stmts.begin() + static_cast<std::ptrdiff_t>(insert_at), cloned.begin(), cloned.end());
    replace_reads(op, resolved_target, replacement);
  }

  // Eliminates unused boolean inputs in a mixed op: drops unused boolean input
  // views, deletes dead `cmp` statements, or specializes `run` callees to drop
  // unused boolean outputs.
  std::string eliminate_unused_mixed_input(size_t index, const std::vector<int>& unused, int max_rounds) {
    const OpInfo info = c_.analyze(p_.ops[index]);
    // 1. Unused boolean input interface views: drop all of them at once.
    std::vector<int> unused_views;
    for (int u : unused)
      if (u <= p_.ops[index].nbool) unused_views.push_back(u);
    if (!unused_views.empty()) {
      std::sort(unused_views.begin(), unused_views.end());
      drop_mixed_bool_views(index, unused_views);
      return "";
    }
    // 2. Dead `cmp` statement: delete it directly.
    for (int u : unused) {
      const int si = info.values.at(u).stmt;
      if (si >= 0 && p_.ops[index].stmts[static_cast<size_t>(si)].kind == "cmp") {
        p_.ops[index].stmts.erase(p_.ops[index].stmts.begin() + static_cast<std::ptrdiff_t>(si));
        return "";
      }
    }
    // 3. Unused output(s) of a `run` statement: drop all unused outputs of that
    // `run` via callee specialization (or erase the `run` if all outputs are unused).
    const std::set<int> unused_set(unused.begin(), unused.end());
    for (int u : unused) {
      const int si = info.values.at(u).stmt;
      if (si < 0 || p_.ops[index].stmts[static_cast<size_t>(si)].kind != "run") continue;
      const PStmt s = p_.ops[index].stmts[static_cast<size_t>(si)];
      std::vector<size_t> drop_idx;
      for (size_t o = 0; o < s.ids.size(); ++o)
        if (unused_set.count(s.ids[o])) drop_idx.push_back(o);
      if (drop_idx.size() == s.ids.size()) {
        p_.ops[index].stmts.erase(p_.ops[index].stmts.begin() + static_cast<std::ptrdiff_t>(si));
        return "";
      }
      std::string mask(s.ids.size(), '-');
      std::string suffix;
      for (size_t o : drop_idx) {
        mask[o] = 'X';
        if (!suffix.empty()) suffix += "_";
        suffix += std::to_string(o + 1);
      }
      const std::string callee_name = s.name;
      const SpecKey key{callee_name, history_size(callee_name), "drop:" + mask};
      std::string spec_name;
      auto sit = specializations_.find(key);
      if (sit != specializations_.end()) {
        spec_name = sit->second;
      } else {
        const size_t callee_idx = static_cast<size_t>(c_.index_of(callee_name));
        POp spec = p_.ops[callee_idx];
        spec.name = unique_op_name(callee_name + "__D" + suffix);
        std::vector<PArg> kept_outs;
        for (size_t o = 0; o < spec.outs.size(); ++o)
          if (mask[o] != 'X') kept_outs.push_back(spec.outs[o]);
        spec.outs = std::move(kept_outs);
        spec_name = spec.name;
        const size_t spec_idx = add_helper_op(std::move(spec), /*is_spec=*/true);
        OpResult spec_res = fix_op(spec_idx, max_rounds);
        c_.forget_values();
        if (spec_res.status != "ok") {
          removed_.insert(spec_name);
          return spec_res.status;
        }
        specializations_[key] = spec_name;
        helper_results_.push_back(std::move(spec_res));
      }
      PStmt& stmt = p_.ops[index].stmts[static_cast<size_t>(si)];
      std::vector<int> kept_ids;
      for (size_t o = 0; o < stmt.ids.size(); ++o)
        if (mask[o] != 'X') kept_ids.push_back(stmt.ids[o]);
      stmt.name = spec_name;
      stmt.ids = std::move(kept_ids);
      stmt.applied_version = 0;
      return "";
    }
    return "useless_input";
  }

  void record_dropped_bool_views(const std::string& name, const std::vector<int>& views) {
    std::vector<int>& orig_bv = orig_bool_views_.at(name);
    std::vector<int>& dropped = dropped_[name];
    for (int v : views) dropped.push_back(orig_bv[static_cast<size_t>(v - 1)]);
    std::sort(dropped.begin(), dropped.end());
    std::vector<int> kept_orig;
    for (size_t i = 0; i < orig_bv.size(); ++i)
      if (!std::binary_search(views.begin(), views.end(), static_cast<int>(i + 1))) kept_orig.push_back(orig_bv[i]);
    orig_bv = std::move(kept_orig);

    SigChange sc;
    sc.kind = SigChange::kDropBoolViews;
    sc.dropped_views = views;
    history_[name].push_back(std::move(sc));
  }

  void drop_mixed_bool_views(size_t index, const std::vector<int>& views) {
    POp& op = p_.ops[index];
    record_dropped_bool_views(op.name, views);
    const int old_views = op.views();
    std::unordered_map<int, int> moved;
    int next = 1;
    for (int v = 1; v <= op.nbool; ++v)
      if (!std::binary_search(views.begin(), views.end(), v)) moved[v] = next++;
    for (int v = op.nbool + 1; v <= old_views; ++v) moved[v] = next++;
    for (PStmt& st : op.stmts)
      for (PArg& a : st.args)
        if (!a.is_literal() && a.id <= old_views) a.id = moved.at(a.id);
    for (PArg& a : op.outs)
      if (!a.is_literal() && a.id <= old_views) a.id = moved.at(a.id);
    op.nbool -= static_cast<int>(views.size());
  }

  // Structural rewrite (DLP 59 Problem 7): extracts boolean logic on top of
  // non-boolean Boolean Sources for any boolean output view that depends on a
  // boolean input interface view or shares a non-boolean Boolean Source with
  // another boolean output view. The mixed op returns the distinct non-boolean
  // Boolean Sources directly (each at most once), and callers compute the
  // extracted boolean logic via helper bool ops (or inlined wrappers).
  std::string fix_mixed_outputs(size_t index, int max_rounds) {
    const POp orig = p_.ops[index];
    const OpInfo info = c_.analyze(orig);
    const uint32_t I = static_cast<uint32_t>(info.inputs.size());
    std::vector<std::vector<char>> out_sources(orig.outs.size());
    std::vector<char> is_bool_out(orig.outs.size(), 0);
    std::vector<char> bad_iface(orig.outs.size(), 0);
    std::vector<int> non_bool_uses(I, 0);

    for (size_t o = 0; o < orig.outs.size(); ++o) {
      const PArg& a = orig.outs[o];
      if (a.is_literal()) continue;
      const int r = info.resolve(a.id);
      if (info.values.at(r).kind != 'b') continue;
      is_bool_out[o] = 1;
      out_sources[o] = ProgramChecker::boolean_sources(orig, info, r);
      for (uint32_t i = 0; i < static_cast<uint32_t>(orig.nbool) && i < I; ++i)
        if (out_sources[o][i]) bad_iface[o] = 1;
      for (uint32_t i = static_cast<uint32_t>(orig.nbool); i < I; ++i)
        if (out_sources[o][i]) ++non_bool_uses[i];
    }

    std::vector<char> violating(orig.outs.size(), 0);
    for (size_t o = 0; o < orig.outs.size(); ++o) {
      if (!is_bool_out[o]) continue;
      if (bad_iface[o]) {
        violating[o] = 1;
        continue;
      }
      for (uint32_t i = static_cast<uint32_t>(orig.nbool); i < I; ++i)
        if (out_sources[o][i] && non_bool_uses[i] >= 2) {
          violating[o] = 1;
          break;
        }
    }

    // Build new outputs: keep non-violating outputs in place, then append each
    // distinct non-boolean Boolean Source needed by violating outputs (once).
    // Preserve original position when a violating output is already directly
    // one of those non-boolean Boolean Sources (e.g. `(c, not c)` keeps `c` at 0).
    std::vector<PArg> new_outs;
    std::unordered_map<int, int> source_to_new_out;  // resolved non-bool input id -> 0-based new out idx
    std::vector<int> kept_out_pos(orig.outs.size(), -1);
    for (size_t o = 0; o < orig.outs.size(); ++o) {
      if (!violating[o]) {
        kept_out_pos[o] = static_cast<int>(new_outs.size());
        new_outs.push_back(orig.outs[o]);
        continue;
      }
      const int r = info.resolve(orig.outs[o].id);
      auto iit = info.input_number.find(r);
      if (iit != info.input_number.end() && iit->second > orig.nbool && !source_to_new_out.count(r)) {
        const int pos = static_cast<int>(new_outs.size());
        source_to_new_out[r] = pos;
        new_outs.push_back(PArg{r, ""});
      }
    }
    for (uint32_t i = static_cast<uint32_t>(orig.nbool); i < I; ++i) {
      bool needed = false;
      for (size_t o = 0; o < orig.outs.size() && !needed; ++o)
        if (violating[o] && out_sources[o][i]) needed = true;
      if (!needed) continue;
      const int src_id = info.inputs[i];
      if (!source_to_new_out.count(src_id)) {
        const int pos = static_cast<int>(new_outs.size());
        source_to_new_out[src_id] = pos;
        new_outs.push_back(PArg{src_id, ""});
      }
    }

    std::vector<MixedOutExpr> out_exprs(orig.outs.size());
    for (size_t o = 0; o < orig.outs.size(); ++o) {
      if (!violating[o]) {
        out_exprs[o].kind = MixedOutExpr::kNewOut;
        out_exprs[o].index = kept_out_pos[o];
        continue;
      }
      const int r = info.resolve(orig.outs[o].id);
      // Directly a boolean input interface view.
      if (r <= orig.nbool) {
        out_exprs[o].kind = MixedOutExpr::kView;
        out_exprs[o].index = r;
        continue;
      }
      // Directly one of the returned non-boolean Boolean Sources.
      auto sit = source_to_new_out.find(r);
      if (sit != source_to_new_out.end()) {
        out_exprs[o].kind = MixedOutExpr::kNewOut;
        out_exprs[o].index = sit->second;
        continue;
      }
      // Clone the boolean sub-DAG of `r` into a helper bool op.
      POp helper;
      helper.name = unique_op_name(orig.name + "__bool" + std::to_string(o + 1));
      helper.boolean = true;
      std::unordered_map<int, int> val_map;
      std::vector<OutRef> call_args;
      for (uint32_t i = 0; i < I; ++i) {
        if (!out_sources[o][i]) continue;
        const int src_id = info.inputs[i];
        ++helper.nbool;
        val_map[src_id] = helper.nbool;
        if (i < static_cast<uint32_t>(orig.nbool))
          call_args.push_back({OutRef::kView, src_id, ""});
        else
          call_args.push_back({OutRef::kNewOut, source_to_new_out.at(src_id), ""});
      }
      helper.next_id = helper.nbool + 1;
      std::set<int> visited;
      std::vector<int> stmt_indices;
      std::function<void(int)> collect = [&](int v) {
        v = info.resolve(v);
        if (!visited.insert(v).second) return;
        if (info.input_number.count(v)) return;
        const int si = info.values.at(v).stmt;
        if (si < 0) return;
        const PStmt& st = orig.stmts[static_cast<size_t>(si)];
        if (!is_boolean_statement(st.kind)) return;
        for (const PArg& a : st.args)
          if (!a.is_literal()) collect(a.id);
        stmt_indices.push_back(si);
      };
      collect(r);
      std::sort(stmt_indices.begin(), stmt_indices.end());
      for (int si : stmt_indices) {
        PStmt st = orig.stmts[static_cast<size_t>(si)];
        for (PArg& a : st.args)
          if (!a.is_literal()) a = PArg{val_map.at(info.resolve(a.id)), ""};
        const int fresh = helper.next_id++;
        val_map[orig.stmts[static_cast<size_t>(si)].ids[0]] = fresh;
        st.ids = {fresh};
        helper.stmts.push_back(std::move(st));
      }
      helper.outs = {PArg{val_map.at(r), ""}};
      const std::string hname = helper.name;
      const size_t hidx = add_helper_op(std::move(helper), /*is_spec=*/false);
      OpResult hres = fix_op(hidx, max_rounds);
      c_.forget_values();
      if (hres.status != "ok") return hres.status;
      helper_results_.push_back(std::move(hres));

      out_exprs[o].kind = MixedOutExpr::kCall;
      out_exprs[o].callee = hname;
      out_exprs[o].args = std::move(call_args);
    }

    // Re-fetch `p_.ops[index]` after helper additions.
    p_.ops[index].outs = std::move(new_outs);
    compose_orig_out_exprs(orig.name, out_exprs);
    SigChange sc;
    sc.kind = SigChange::kRemapMixedOutputs;
    sc.new_out_count = static_cast<int>(p_.ops[index].outs.size());
    sc.out_exprs = std::move(out_exprs);
    history_[orig.name].push_back(std::move(sc));
    if (p_.ops[index].outs.empty()) removed_.insert(orig.name);
    return "";
  }

  // A fix that makes the operation at `index` execute the registered
  // operation `name` would make an execution cycle (DLP 9) when name's
  // definition leads back to it. So first the executions in name's
  // definition that lead back are written out in place, one at a time,
  // until none does: each is replaced by its operation's current
  // statements, which only execute what it executes, so this ends.
  // Returns how many were written out, or -1 when one is a `run`, which
  // can't be.
  int write_out_leading_back(const std::string& name, size_t index) {
    if (name == "and" || name == "not") return 0;
    const std::string target = p_.ops[index].name;
    const size_t r = static_cast<size_t>(c_.index_of(name));
    int written = 0;
    bool replaced = false;
    for (;;) {
      POp& reg = p_.ops[r];
      size_t k = reg.stmts.size();
      for (size_t j = 0; j < reg.stmts.size() && k == reg.stmts.size(); ++j) {
        const PStmt& s = reg.stmts[j];
        if ((s.kind == "call" || s.kind == "run") && executes(s.name, target)) k = j;
      }
      if (k == reg.stmts.size()) return written;
      if (reg.stmts[k].kind != "call") return -1;
      // Its executions give values to the views their operations have now.
      if (!replaced) {
        apply_replacements(r);
        replaced = true;
        rewritten_.insert(r);
        continue;
      }
      inline_call(reg, k);
      ++written;
    }
  }

  // Whether the registered operation `name` (transitively) executes `op`:
  // fixing op's definition with it would make the program execute itself.
  bool executes(const std::string& name, const std::string& op) const {
    if (name == op) return true;
    if (name == "and" || name == "not") return false;
    std::set<std::string> seen;
    std::vector<std::string> stack{name};
    while (!stack.empty()) {
      const std::string n = stack.back();
      stack.pop_back();
      if (!seen.insert(n).second) continue;
      for (const PStmt& s : p_.ops[static_cast<size_t>(c_.index_of(n))].stmts)
        if (s.kind == "call" || s.kind == "run") {
          if (s.name == op) return true;
          stack.push_back(s.name);
        }
    }
    return false;
  }

  bool spelling_before(size_t index, const OpInfo& info, const Report::Found& a, const Report::Found& b) {
    const POp& op = p_.ops[index];
    auto negations = [&](const Report::Found& f) {
      int n = f.op.rfind("not:", 0) == 0;
      for (int x : f.args) {
        const OpInfo::Value& v = info.values.at(x);
        n += v.stmt >= 0 && op.stmts[static_cast<size_t>(v.stmt)].kind == "not";
      }
      return n;
    };
    auto name = [](const Report::Found& f) { return f.op.rfind("not:", 0) == 0 ? f.op.substr(4) : f.op; };
    const int na = negations(a), nb = negations(b);
    if (na != nb) return na < nb;
    const std::vector<std::string> order = c_.follows(op);
    const auto pa = std::find(order.begin(), order.end(), name(a));
    const auto pb = std::find(order.begin(), order.end(), name(b));
    if (pa != pb) return pa < pb;
    ProgramChecker::Ranker ranker{op, info, {}};
    for (size_t i = 0; i < std::min(a.args.size(), b.args.size()); ++i) {
      PArg x, y;
      x.id = a.args[i];
      y.id = b.args[i];
      const int r = ranker.compare(x, y);
      if (r != 0) return r < 0;
    }
    return false;
  }

  static PStmt& stmt_of(POp& op, int id) {
    for (PStmt& s : op.stmts)
      if (std::find(s.ids.begin(), s.ids.end(), id) != s.ids.end()) return s;
    throw std::runtime_error("no statement defines " + std::to_string(id));
  }

  static size_t stmt_index(const POp& op, int id) {
    for (size_t k = 0; k < op.stmts.size(); ++k)
      if (std::find(op.stmts[k].ids.begin(), op.stmts[k].ids.end(), id) != op.stmts[k].ids.end()) return k;
    throw std::runtime_error("no statement defines " + std::to_string(id));
  }

  // The value of v's statement comes from an execution of a registered
  // operation instead (and a `not` of it for an opposite result).
  static void apply_execution(POp& op, const Report::Found& f) {
    const bool opposite = f.op.rfind("not:", 0) == 0;
    PStmt exec;
    exec.name = opposite ? f.op.substr(4) : f.op;
    exec.kind = "call";
    if (exec.name == "and" || exec.name == "not") {
      exec.kind = exec.name;
      exec.name.clear();
    }
    for (int a : f.args) {
      PArg x;
      x.id = a;
      exec.args.push_back(x);
    }
    const size_t k = stmt_index(op, f.value);
    if (!opposite) {
      exec.ids = op.stmts[k].ids;
      op.stmts[k] = std::move(exec);
      return;
    }
    exec.ids = {op.next_id++};
    PStmt negation;
    negation.kind = "not";
    PArg e;
    e.id = exec.ids[0];
    negation.args = {e};
    negation.ids = op.stmts[k].ids;
    op.stmts[k] = std::move(negation);
    op.stmts.insert(op.stmts.begin() + static_cast<std::ptrdiff_t>(k), std::move(exec));
  }

  static void replace_reads(POp& op, int id, const PArg& with) {
    for (PStmt& s : op.stmts)
      for (PArg& a : s.args)
        if (!a.is_literal() && a.id == id) a = with;
    for (PArg& a : op.outs)
      if (!a.is_literal() && a.id == id) a = with;
  }

  // DLP 60's order, dead statements removed, and copies wherever one value
  // goes to two views of an execution.
  // Returns how many dead boolean statements it removed.
  int canonicalize(size_t index) {
    POp& op = p_.ops[index];
    int removed = 0;
    {
      std::unordered_map<int, PArg> source;
      std::vector<PStmt> kept;
      for (PStmt& s : op.stmts) {
        for (PArg& a : s.args)
          if (!a.is_literal() && source.count(a.id)) a = source.at(a.id);
        if (s.kind == "copy") {
          source[s.ids[0]] = s.args[0];
          continue;
        }
        kept.push_back(std::move(s));
      }
      op.stmts = std::move(kept);
      for (PArg& a : op.outs)
        if (!a.is_literal() && source.count(a.id)) a = source.at(a.id);
    }
    // Dead boolean statements: nothing reads them from an exit.
    {
      std::unordered_map<int, size_t> def;
      for (size_t k = 0; k < op.stmts.size(); ++k)
        for (int id : op.stmts[k].ids) def[id] = k;
      std::vector<char> live(op.stmts.size(), 0);
      std::vector<size_t> stack;
      auto reach = [&](const PArg& a) {
        if (a.is_literal() || !def.count(a.id)) return;
        const size_t k = def.at(a.id);
        if (!live[k]) {
          live[k] = 1;
          stack.push_back(k);
        }
      };
      for (const PArg& a : op.outs) reach(a);
      for (size_t k = 0; k < op.stmts.size(); ++k)
        if (!is_boolean_statement(op.stmts[k].kind) && !live[k]) {
          live[k] = 1;
          stack.push_back(k);
        }
      while (!stack.empty()) {
        const size_t k = stack.back();
        stack.pop_back();
        for (const PArg& a : op.stmts[k].args) reach(a);
      }
      std::vector<PStmt> kept;
      for (size_t k = 0; k < op.stmts.size(); ++k) {
        if (live[k])
          kept.push_back(std::move(op.stmts[k]));
        else
          removed += is_boolean_statement(op.stmts[k].kind);
      }
      op.stmts = std::move(kept);
    }
    // Arguments of interchangeable views in rank order, in statement order
    // so that every value's arguments are sorted before it's ranked.
    {
      const OpInfo info = c_.analyze(op);
      ProgramChecker::Ranker ranker{op, info, {}};
      for (PStmt& s : op.stmts) {
        if (s.kind != "and" && s.kind != "call") continue;
        const std::vector<int> group = c_.statement_groups(s);
        for (size_t i = 0; i < s.args.size(); ++i)
          for (size_t j = i + 1; j < s.args.size(); ++j)
            if (group[i] == group[j] && ranker.compare(s.args[i], s.args[j]) > 0) std::swap(s.args[i], s.args[j]);
      }
      const std::vector<int> order = c_.canonical_order(op, info);
      std::vector<PStmt> sorted;
      for (int k : order) sorted.push_back(std::move(op.stmts[static_cast<size_t>(k)]));
      op.stmts = std::move(sorted);
    }
    // De-aliasing (DLP 55): a value given to two views of one execution is
    // given to the second through a copy right before it.
    std::vector<PStmt> out;
    for (PStmt& s : op.stmts) {
      std::set<int> given;
      for (PArg& a : s.args) {
        if (a.is_literal()) continue;
        if (!given.insert(a.id).second) {
          PStmt copy;
          copy.kind = "copy";
          copy.args = {a};
          copy.ids = {op.next_id++};
          a.id = copy.ids[0];
          out.push_back(std::move(copy));
        }
      }
      out.push_back(std::move(s));
    }
    op.stmts = std::move(out);
    return removed;
  }

  // Bottom-up canonicalization of the first non-canonical maximal single-use
  // associative, commutative binary chain (DLP 60): folds sorted leaves
  // v_1 <= v_2 <= ... <= v_m as op(v_1, v_2), op(v_3, t_1), ..., op(v_m, t_{m-2}),
  // inserting right before the chain's root so topological order is always
  // preserved. Returns true if a chain was rewritten (caller canonicalizes next).
  bool regroup_associative(POp& op) {
    const OpInfo info = c_.analyze(op);
    ProgramChecker::Ranker ranker{op, info, {}};
    const std::unordered_map<int, int> readers = ProgramChecker::reader_counts(op, info);
    std::unordered_map<int, int> sole_reader_stmt;
    for (size_t k = 0; k < op.stmts.size(); ++k) {
      if (op.stmts[k].kind == "copy") continue;
      for (const PArg& a : op.stmts[k].args)
        if (!a.is_literal()) sole_reader_stmt[info.resolve(a.id)] = static_cast<int>(k);
    }
    auto is_chain_root = [&](size_t k, const std::string& op_key) -> bool {
      const int id = op.stmts[k].ids[0];
      auto rit = readers.find(id);
      if (rit == readers.end() || rit->second != 1) return true;
      auto sit = sole_reader_stmt.find(id);
      if (sit == sole_reader_stmt.end()) return true;
      for (const PArg& o : op.outs)
        if (!o.is_literal() && info.resolve(o.id) == id) return true;
      std::string pk;
      uint8_t ptt = 0;
      return !(c_.binary_op_info(op.stmts[static_cast<size_t>(sit->second)], pk, ptt) && pk == op_key);
    };
    for (size_t k = 0; k < op.stmts.size(); ++k) {
      std::string op_key;
      uint8_t tt = 0;
      if (!c_.is_assoc_comm_stmt(op.stmts[k], op_key, tt)) continue;
      if (!is_chain_root(k, op_key)) continue;
      std::vector<PArg> leaves;
      std::vector<int> internal_stmts;
      c_.collect_assoc_chain(op, info, readers, static_cast<int>(k), op_key, leaves, internal_stmts);
      if (leaves.size() < 3) continue;
      for (PArg& a : leaves)
        if (!a.is_literal()) a.id = info.resolve(a.id);
      bool needs_regroup = false;
      for (int idx : internal_stmts) {
        const PStmt& s = op.stmts[static_cast<size_t>(idx)];
        auto is_same_single = [&](const PArg& a, int& child_stmt) -> bool {
          if (a.is_literal()) return false;
          const int rid = info.resolve(a.id);
          const OpInfo::Value& v = info.values.at(rid);
          auto rit = readers.find(rid);
          if (v.stmt < 0 || rit == readers.end() || rit->second != 1) return false;
          std::string ck;
          uint8_t ctt = 0;
          if (!c_.binary_op_info(op.stmts[static_cast<size_t>(v.stmt)], ck, ctt) || ck != op_key) return false;
          child_stmt = v.stmt;
          return true;
        };
        int c0 = -1, c1 = -1;
        const bool s0 = is_same_single(s.args[0], c0);
        const bool s1 = is_same_single(s.args[1], c1);
        if (s0 && s1) {
          needs_regroup = true;
          break;
        }
        if (s0 || s1) {
          const int child_stmt = s0 ? c0 : c1;
          const PArg& leaf_arg = s0 ? s.args[1] : s.args[0];
          std::vector<PArg> child_leaves;
          std::vector<int> child_stmts;
          c_.collect_assoc_chain(op, info, readers, child_stmt, op_key, child_leaves, child_stmts);
          for (const PArg& cl : child_leaves) {
            if (ranker.compare(leaf_arg, cl) < 0) {
              needs_regroup = true;
              break;
            }
          }
          if (needs_regroup) break;
        }
      }
      if (!needs_regroup) continue;

      std::stable_sort(leaves.begin(), leaves.end(),
                       [&](const PArg& a, const PArg& b) { return ranker.compare(a, b) < 0; });
      const int root_id = op.stmts[k].ids[0];
      const std::string kind = op.stmts[k].kind;
      const std::string name = op.stmts[k].name;
      const int ver = op.stmts[k].applied_version;
      std::vector<PStmt> added;
      PArg acc = leaves[0];
      for (size_t i = 1; i < leaves.size(); ++i) {
        PStmt ns;
        ns.kind = kind;
        ns.name = name;
        ns.applied_version = ver;
        ns.args = {leaves[i], acc};
        ns.ids = {op.next_id++};
        acc = PArg{};
        acc.id = ns.ids[0];
        added.push_back(std::move(ns));
      }
      op.stmts.insert(op.stmts.begin() + static_cast<std::ptrdiff_t>(k), added.begin(), added.end());
      replace_reads(op, root_id, acc);
      return true;
    }
    return false;
  }

  // DLP 61: Factors common factor `f.factor_id` out of all matching single-use
  // `inner`-chain terms inside `f.root_id`'s single-use `outer`-chain.
  bool apply_factor(POp& op, const Report::Factor& f) {
    const OpInfo info = c_.analyze(op);
    const std::unordered_map<int, int> readers = ProgramChecker::reader_counts(op, info);
    auto vit = info.values.find(f.root_id);
    if (vit == info.values.end() || vit->second.stmt < 0) return false;
    const int root_stmt = vit->second.stmt;
    const std::string outer_key = f.outer_kind == "and" ? "and" : ("call:" + f.outer_name);
    const std::string inner_key = f.inner_kind == "and" ? "and" : ("call:" + f.inner_name);
    std::vector<PArg> outer_leaves;
    std::vector<int> outer_stmts;
    c_.collect_assoc_chain(op, info, readers, root_stmt, outer_key, outer_leaves, outer_stmts);

    std::vector<std::vector<PArg>> matched_rem;
    std::vector<PArg> untouched;
    for (const PArg& leaf : outer_leaves) {
      if (!leaf.is_literal()) {
        const int lid = info.resolve(leaf.id);
        const OpInfo::Value& lv = info.values.at(lid);
        auto rit = readers.find(lid);
        if (lv.stmt >= 0 && rit != readers.end() && rit->second == 1) {
          std::string ck;
          uint8_t ctt = 0;
          if (c_.binary_op_info(op.stmts[static_cast<size_t>(lv.stmt)], ck, ctt) && ck == inner_key) {
            std::vector<PArg> factors;
            std::vector<int> inner_stmts;
            c_.collect_assoc_chain(op, info, readers, lv.stmt, inner_key, factors, inner_stmts);
            std::vector<PArg> rem;
            bool dropped_one = false;
            for (const PArg& fa : factors) {
              if (!dropped_one && !fa.is_literal() && info.resolve(fa.id) == f.factor_id) {
                dropped_one = true;
                continue;
              }
              PArg resolved = fa;
              if (!resolved.is_literal()) resolved.id = info.resolve(resolved.id);
              rem.push_back(resolved);
            }
            if (dropped_one && !rem.empty()) {
              matched_rem.push_back(std::move(rem));
              continue;
            }
          }
        }
      }
      PArg resolved = leaf;
      if (!resolved.is_literal()) resolved.id = info.resolve(resolved.id);
      untouched.push_back(resolved);
    }
    if (matched_rem.size() < 2) return false;

    const int outer_ver = f.outer_kind == "call" ? static_cast<int>(history_size(f.outer_name)) : 0;
    const int inner_ver = f.inner_kind == "call" ? static_cast<int>(history_size(f.inner_name)) : 0;
    std::vector<PStmt> added;
    auto make_bin = [&](const std::string& kind, const std::string& name, int ver, const PArg& a,
                        const PArg& b) -> PArg {
      PStmt ns;
      ns.kind = kind;
      ns.name = name;
      ns.applied_version = ver;
      ns.args = {a, b};
      ns.ids = {op.next_id++};
      PArg out;
      out.id = ns.ids[0];
      added.push_back(std::move(ns));
      return out;
    };
    auto fold = [&](const std::string& kind, const std::string& name, int ver, const std::vector<PArg>& items) -> PArg {
      PArg acc = items[0];
      for (size_t i = 1; i < items.size(); ++i) acc = make_bin(kind, name, ver, acc, items[i]);
      return acc;
    };

    std::vector<PArg> term_rems;
    term_rems.reserve(matched_rem.size());
    for (const auto& rem : matched_rem) term_rems.push_back(fold(f.inner_kind, f.inner_name, inner_ver, rem));
    const PArg combined_rem = fold(f.outer_kind, f.outer_name, outer_ver, term_rems);
    PArg farg;
    farg.id = f.factor_id;
    const PArg factored = make_bin(f.inner_kind, f.inner_name, inner_ver, farg, combined_rem);
    std::vector<PArg> final_terms = untouched;
    final_terms.push_back(factored);
    const PArg new_root = fold(f.outer_kind, f.outer_name, outer_ver, final_terms);

    op.stmts.insert(op.stmts.begin() + static_cast<std::ptrdiff_t>(root_stmt), added.begin(), added.end());
    replace_reads(op, f.root_id, new_root);
    return true;
  }

  // DLP 59's refactoring step 6: read views that don't matter are removed.
  // First tries replacing unused views with kept views without creating a
  // constant (uniform, then per-view). If every kept-view assignment creates a
  // constant (or no views are kept), substitutes `F` for the unused views and
  // lets literal propagation + callee specialization simplify them away.
  void drop_views(size_t index, const std::vector<int>& views) {
    const POp original_op = p_.ops[index];
    std::vector<int> kept;
    for (int y = 1; y <= original_op.nbool; ++y)
      if (std::find(views.begin(), views.end(), y) == views.end()) kept.push_back(y);
    bool found = false;
    for (int y : kept) {
      PArg with;
      with.id = y;
      for (int v : views) replace_reads(p_.ops[index], v, with);
      c_.forget_values();
      if (!c_.has_constant_value(index)) {
        found = true;
        break;
      }
      p_.ops[index] = original_op;
    }
    if (!found && views.size() > 1 && !kept.empty()) {
      bool all_ok = true;
      for (int v : views) {
        const POp before_v = p_.ops[index];
        bool ok_v = false;
        for (int y : kept) {
          PArg with;
          with.id = y;
          replace_reads(p_.ops[index], v, with);
          c_.forget_values();
          if (!c_.has_constant_value(index)) {
            ok_v = true;
            break;
          }
          p_.ops[index] = before_v;
        }
        if (!ok_v) {
          all_ok = false;
          break;
        }
      }
      if (all_ok) {
        found = true;
      } else {
        p_.ops[index] = original_op;
      }
    }
    if (!found) {
      PArg false_lit;
      false_lit.literal = "F";
      for (int v : views) replace_reads(p_.ops[index], v, false_lit);
    }
    c_.forget_values();
    POp& op = p_.ops[index];
    std::vector<int> sorted_views = views;
    std::sort(sorted_views.begin(), sorted_views.end());
    record_dropped_bool_views(op.name, sorted_views);
    std::unordered_map<int, int> moved;
    int next = 1;
    for (int v = 1; v <= op.nbool; ++v)
      if (!std::binary_search(sorted_views.begin(), sorted_views.end(), v)) moved[v] = next++;
    for (PStmt& st : op.stmts)
      for (PArg& a : st.args)
        if (!a.is_literal() && a.id <= op.nbool) a.id = moved.at(a.id);
    for (PArg& a : op.outs)
      if (!a.is_literal() && a.id <= op.nbool) a.id = moved.at(a.id);
    op.nbool = next - 1;
  }

  // Replaces statement k, an execution, with the executed operation's own
  // statements, its views given the execution's arguments.
  void inline_call(POp& op, size_t k) {
    inline_body(op, k, p_.ops[static_cast<size_t>(c_.index_of(op.stmts[k].name))]);
  }

  // Replaces statement k, an execution, with `callee`'s statements, its
  // views given the execution's arguments.
  void inline_body(POp& op, size_t k, const POp& callee) {
    const PStmt s = op.stmts[k];
    std::unordered_map<int, PArg> value;
    for (int v = 1; v <= callee.nbool; ++v) value[v] = s.args[static_cast<size_t>(v - 1)];
    auto map = [&](const PArg& a) { return a.is_literal() ? a : value.at(a.id); };
    std::vector<PStmt> body;
    for (const PStmt& st : callee.stmts) {
      PStmt n = st;
      for (PArg& a : n.args) a = map(a);
      for (int& id : n.ids) {
        const int fresh = op.next_id++;
        value[id].id = fresh;
        value[id].literal.clear();
        id = fresh;
      }
      body.push_back(std::move(n));
    }
    const PArg result = map(callee.outs[0]);
    op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k));
    op.stmts.insert(op.stmts.begin() + static_cast<std::ptrdiff_t>(k), body.begin(), body.end());
    replace_reads(op, s.ids[0], result);
  }

  // After a boolean operation compiles: if it evaluates to a constant literal,
  // names one of its views, or wraps one statement (DLP 62's wrapper), it's
  // removed and its callers compute that instead.
  void settle(size_t index) {
    POp& op = p_.ops[index];
    if (!op.boolean || op.outs.size() != 1) return;
    if (c_.is_registered(op.name)) return;
    const PArg& o = op.outs[0];
    BoolReplacement cur_rep;
    if (o.is_literal()) {
      cur_rep.kind = "literal";
      cur_rep.literal = o.literal;
    } else if (o.id <= op.views()) {
      cur_rep.kind = "view";
      cur_rep.view = o.id - 1;
    } else {
      int statements = 0;
      const PStmt* only = nullptr;
      for (const PStmt& s : op.stmts)
        if (is_boolean_statement(s.kind)) {
          ++statements;
          only = &s;
        }
      if (statements != 1 || (only->kind == "call" && !c_.is_registered(only->name))) return;
      cur_rep.kind = "statement";
      cur_rep.statement = *only;
      // Its arguments are views, maybe through copies.
      std::unordered_map<int, int> copies;
      for (const PStmt& s : op.stmts)
        if (s.kind == "copy" && !s.args[0].is_literal()) copies[s.ids[0]] = s.args[0].id;
      for (PArg& a : cur_rep.statement.args)
        if (!a.is_literal() && copies.count(a.id)) a.id = copies.at(a.id);
    }

    // Build original-view-indexed replacement for `write_replacements`.
    BoolReplacement orig_rep = cur_rep;
    if (orig_rep.kind == "view") {
      orig_rep.view = current_to_orig_view(op.name, cur_rep.view + 1) - 1;
    } else if (orig_rep.kind == "statement") {
      for (PArg& a : orig_rep.statement.args)
        if (!a.is_literal()) a.id = current_to_orig_view(op.name, a.id);
    }
    bool_replacements_[op.name] = std::move(orig_rep);

    SigChange sc;
    sc.kind = SigChange::kReplaceBoolOp;
    sc.bool_rep = std::move(cur_rep);
    history_[op.name].push_back(std::move(sc));
    removed_.insert(op.name);
  }

  // Fixes each operation in `ops` in order, each after the ones it executes,
  // then again each one whose definition a later fix wrote executions out
  // in, or whose executions have unapplied callee signature changes, and,
  // with `recheck`, each one that still has errors, until none is left.
  void fix_until_stable(const std::vector<size_t>& ops, bool recheck, int max_rounds, std::vector<OpResult>& out,
                        std::map<size_t, size_t>& result_of) {
    for (size_t i : ops) {
      if (removed_.count(p_.ops[i].name)) continue;
      result_of[i] = out.size();
      out.push_back(fix_op(i, max_rounds));
      log(out.back(), "first");
    }
    for (;;) {
      std::vector<size_t> again;
      for (size_t i : ops) {
        if (removed_.count(p_.ops[i].name) || out[result_of.at(i)].status != "ok") continue;
        Phase p{phase_s, "recheck"};
        if (rewritten_.count(i) || stale(p_.ops[i]) || (recheck && !c_.check(i, true, "tt").errors.empty()))
          again.push_back(i);
      }
      rewritten_.clear();
      if (again.empty()) return;
      for (size_t i : again) {
        OpResult r = fix_op(i, max_rounds);
        OpResult& total = out[result_of.at(i)];
        total.rounds += r.rounds;
        total.seconds += r.seconds;
        total.status = r.status;
        for (const auto& [k, n] : r.fixes) total.fixes[k] += n;
        ++total.fixes["fixed again"];
        log(r, "again");
      }
    }
  }

  void log(const OpResult& r, const char* pass) const {
    if (!progress) return;
    *progress << r.name << " " << pass << " " << r.rounds << " " << r.seconds << " " << r.status;
    for (const auto& [k, n] : r.fixes) *progress << " " << k << "=" << n;
    *progress << std::endl;
  }

  // Whether an operation executes one with unapplied signature changes.
  bool stale(const POp& op) const {
    for (const PStmt& s : op.stmts) {
      if (s.kind != "call" && s.kind != "run") continue;
      if (s.applied_version < static_cast<int>(history_size(s.name))) return true;
    }
    return false;
  }

  // Replays all pending callee signature changes onto `call` and `run`
  // statements in the operation at `index`.
  void apply_replacements(size_t index) {
    POp& op = p_.ops[index];
    for (size_t k = 0; k < op.stmts.size(); ++k) {
      PStmt& s = op.stmts[k];
      if (s.kind != "call" && s.kind != "run") continue;
      auto hit = history_.find(s.name);
      if (hit == history_.end() || s.applied_version >= static_cast<int>(hit->second.size())) continue;
      const SigChange& sc = hit->second[static_cast<size_t>(s.applied_version)];

      if (sc.kind == SigChange::kDropBoolViews) {
        std::vector<PArg> args;
        for (size_t i = 0; i < s.args.size(); ++i)
          if (!std::binary_search(sc.dropped_views.begin(), sc.dropped_views.end(), static_cast<int>(i + 1)))
            args.push_back(s.args[i]);
        s.args = std::move(args);
        ++s.applied_version;
        --k;
        continue;
      }

      if (sc.kind == SigChange::kReplaceBoolOp) {
        const BoolReplacement& r = sc.bool_rep;
        const int v = s.ids[0];
        if (r.kind == "literal") {
          const PArg lit{0, r.literal};
          op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k));
          replace_reads(op, v, lit);
          --k;
        } else if (r.kind == "view") {
          const PArg a = s.args[static_cast<size_t>(r.view)];
          op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k));
          replace_reads(op, v, a);
          --k;
        } else {
          PStmt n = r.statement;
          for (PArg& a : n.args)
            if (!a.is_literal()) a = s.args[static_cast<size_t>(a.id - 1)];
          n.ids = s.ids;
          n.applied_version = 0;
          s = std::move(n);
          --k;
        }
        continue;
      }

      if (sc.kind == SigChange::kSplitBoolOp) {
        const std::vector<PArg> old_args = s.args;
        const std::vector<int> old_ids = s.ids;
        std::vector<PStmt> calls;
        calls.reserve(old_ids.size());
        for (size_t o = 0; o < old_ids.size(); ++o) {
          PStmt c;
          c.kind = "call";
          c.name = sc.split_helpers[o];
          c.args = old_args;
          c.ids = {old_ids[o]};
          c.applied_version = 0;
          calls.push_back(std::move(c));
        }
        op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k));
        op.stmts.insert(op.stmts.begin() + static_cast<std::ptrdiff_t>(k), calls.begin(), calls.end());
        --k;
        continue;
      }

      if (sc.kind == SigChange::kRemapMixedOutputs) {
        const std::vector<PArg> old_args = s.args;
        const std::vector<int> old_ids = s.ids;
        std::vector<int> new_ids;
        new_ids.reserve(static_cast<size_t>(sc.new_out_count));
        for (int i = 0; i < sc.new_out_count; ++i) new_ids.push_back(op.next_id++);
        std::vector<PStmt> emitted;
        for (size_t o = 0; o < old_ids.size(); ++o) {
          const MixedOutExpr& e = sc.out_exprs[o];
          if (e.kind == MixedOutExpr::kNewOut) {
            replace_reads(op, old_ids[o], PArg{new_ids[static_cast<size_t>(e.index)], ""});
          } else if (e.kind == MixedOutExpr::kLiteral) {
            replace_reads(op, old_ids[o], PArg{0, e.literal});
          } else if (e.kind == MixedOutExpr::kView) {
            replace_reads(op, old_ids[o], old_args[static_cast<size_t>(e.index - 1)]);
          } else {
            PStmt c;
            c.kind = "call";
            c.name = e.callee;
            c.ids = {old_ids[o]};
            c.applied_version = 0;
            for (const OutRef& ref : e.args) {
              if (ref.kind == OutRef::kView)
                c.args.push_back(old_args[static_cast<size_t>(ref.index - 1)]);
              else if (ref.kind == OutRef::kNewOut)
                c.args.push_back(PArg{new_ids[static_cast<size_t>(ref.index)], ""});
              else
                c.args.push_back(PArg{0, ref.literal});
            }
            emitted.push_back(std::move(c));
          }
        }
        if (sc.new_out_count == 0) {
          op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k));
          op.stmts.insert(op.stmts.begin() + static_cast<std::ptrdiff_t>(k), emitted.begin(), emitted.end());
          --k;
        } else {
          op.stmts[k].ids = std::move(new_ids);
          ++op.stmts[k].applied_version;
          if (!emitted.empty())
            op.stmts.insert(op.stmts.begin() + static_cast<std::ptrdiff_t>(k + 1), emitted.begin(), emitted.end());
          --k;
        }
        continue;
      }
    }
  }

  // Removes the operations that were replaced (and any unreferenced synthesized
  // specializations), and puts every operation after the ones it executes.
  void finish() {
    // Prune synthesized specialization ops that are not transitively reachable
    // from any non-specialization op (e.g. if a caller later simplified away).
    std::set<std::string> keep;
    std::map<std::string, size_t> pos_by_name;
    for (size_t i = 0; i < p_.ops.size(); ++i) pos_by_name[p_.ops[i].name] = i;
    std::vector<std::string> stack;
    for (const POp& op : p_.ops) {
      if (removed_.count(op.name) || spec_ops_.count(op.name)) continue;
      if (keep.insert(op.name).second) stack.push_back(op.name);
    }
    while (!stack.empty()) {
      const std::string n = stack.back();
      stack.pop_back();
      auto pit = pos_by_name.find(n);
      if (pit == pos_by_name.end()) continue;
      for (const PStmt& s : p_.ops[pit->second].stmts) {
        if ((s.kind == "call" || s.kind == "run") && !removed_.count(s.name)) {
          if (keep.insert(s.name).second) stack.push_back(s.name);
        }
      }
    }

    std::map<std::string, POp> by_name;
    std::vector<std::string> names;
    for (POp& op : p_.ops) {
      if (removed_.count(op.name)) continue;
      if (spec_ops_.count(op.name) && !keep.count(op.name)) continue;
      names.push_back(op.name);
      by_name.emplace(op.name, std::move(op));
    }
    std::vector<POp> ordered;
    std::set<std::string> placed;
    std::function<void(const std::string&)> place = [&](const std::string& name) {
      if (!by_name.count(name) || !placed.insert(name).second) return;
      POp& op = by_name.at(name);
      for (const PStmt& s : op.stmts)
        if (s.kind == "call" || s.kind == "run") place(s.name);
      ordered.push_back(std::move(op));
    };
    for (const std::string& name : names) place(name);
    p_.ops = std::move(ordered);
    c_.rebuild_index();
  }

  using SpecKey = std::tuple<std::string, size_t, std::string>;

  ProgramChecker& c_;
  Program& p_;
  std::map<std::string, std::vector<SigChange>> history_;
  std::map<std::string, BoolReplacement> bool_replacements_;
  std::map<std::string, std::vector<MixedOutExpr>> orig_out_exprs_;
  std::map<std::string, int> orig_nbool_;
  std::map<std::string, std::vector<int>> orig_bool_views_;
  // Each operation's dropped read views (from 1, among the views it was written with).
  std::map<std::string, std::vector<int>> dropped_;
  std::map<SpecKey, std::string> specializations_;
  std::set<std::string> removed_;
  std::set<std::string> synthesized_, spec_ops_, extracted_ops_;
  std::vector<OpResult> helper_results_;
  // Operations whose definitions a fix of another one wrote executions out
  // in, by index.
  std::set<size_t> rewritten_;
  // Operations written with more than 256 boolean statements or > max_views.
  std::set<std::string> over_limit_;
};

}  // namespace beq
