// The fixes a refactoring tool applies to a whole program until it
// compiles (DLP 59's refactoring steps, DLP 60's order, DLP 61's matches,
// spellings, and wrappers), with every operation fixed after the ones it
// executes.
#pragma once

#include <optional>

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
      // The fixes may pass DLP 59's statement limit on the way to a smaller
      // operation, but an operation written past it is the programmer's.
      const auto& stmts = p_.ops[i].stmts;
      if (std::count_if(stmts.begin(), stmts.end(), [](const PStmt& s) { return is_boolean_statement(s.kind); }) > 256)
        over_limit_.insert(p_.ops[i].name);
      (c_.in_registered_reach(p_.ops[i].name) ? first : rest).push_back(i);
    }
    // The registered operations and what they execute come first, until
    // they compile: only a match in one of them can write out executions in
    // a registered operation's definition, which changes the spellings of
    // every operation, and nothing they execute is fixed later.
    fix_until_stable(first, true, max_rounds, out, result_of);
    fix_until_stable(rest, false, max_rounds, out, result_of);
    Phase p{phase_s, "finish"};
    finish();
    return out;
  }

  // What each removed operation was replaced by, one line each: NAME 0 view
  // K (from 1), or NAME 0 statement KIND [OP] ARG... with arguments as view
  // numbers (the views the operation has after any were dropped).
  void write_replacements(std::ostream& out) const {
    // NAME - dropped K ...: read views removed (from 1, among the views the
    // operation was written with).
    for (const auto& [name, dropped] : dropped_) {
      out << name << " - dropped";
      for (int v : dropped.first) out << " " << v;
      out << "\n";
    }
    for (const auto& [name, views] : replacements_)
      for (size_t o = 0; o < views.size(); ++o) {
        const Replacement& r = views[o];
        if (r.kind.empty()) continue;
        out << name << " " << o << " " << r.kind;
        if (r.kind == "view") out << " " << r.view + 1;
        if (r.kind == "statement") {
          out << " " << r.statement.kind;
          if (!r.statement.name.empty()) out << " " << r.statement.name;
          for (const PArg& a : r.statement.args) out << " " << (a.is_literal() ? a.literal : std::to_string(a.id));
        }
        out << "\n";
      }
  }

 private:
  // How the callers of a removed operation compute its value instead.
  struct Replacement {
    std::string kind;  // view, statement
    int view = 0;  // the view whose argument it is, from 0
    PStmt statement;  // its arguments' ids are view numbers
  };

  // Adds the time from its making to its end to phase_s[name].
  struct Phase {
    std::map<std::string, double>& seconds;
    const char* name;
    double start = ProgramChecker::now();
    ~Phase() { seconds[name] += ProgramChecker::now() - start; }
  };

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
    bool done = false;
    for (int round = 0; round < max_rounds && !done; ++round) {
      // Statements a fix leaves dead are part of that fix; the ones dead
      // before any fix are errors of their own.
      int dead = 0;
      {
        Phase p{phase_s, "canonicalize"};
        dead = canonicalize(index);
      }
      if (round == 0) res.fixes["dead"] += dead;
      Report rep;
      {
        Phase p{phase_s, "check"};
        rep = c_.check(index, true, "tt");
      }
      check_times.add(rep.times);
      res.rounds = round;
      POp& op = p_.ops[index];
      if (rep.errors.count("limits")) {
        res.status = "limits";
        break;
      }
      // A cycle is the programmer's to break: the fixes never make one.
      if (rep.errors.count("cycle")) {
        res.status = "cycle";
        break;
      }
      // A literal or a value that never changes is the programmer's to
      // fix (DLP 59).
      if (rep.literal_stmt >= 0) {
        res.status = "literal";
        break;
      }
      if (rep.redundant_kind == "constant") {
        res.status = "constant";
        break;
      }
      if (!rep.redundant_kind.empty()) {
        // Every redundant value, up to an opposite value that's already a
        // `not`, at once: each is still a fix after the others, which keep
        // every function, and doing them together saves a check of the
        // whole operation for each.
        Phase p{phase_s, "redundant values"};
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
        if (!drop_views(index, rep.unused_views)) {
          res.status = "unused view";
          break;
        }
        ++res.fixes["unused view"];
        continue;
      }
      if (rep.errors.count("wrapper")) {
        if (c_.is_registered(op.name)) {
          res.status = "registered wrapper";
          break;
        }
        ++res.fixes["wrapper"];
        done = true;
        break;
      }
      if (rep.has_match) {
        // Every match in the order DLP 61 reports them, largest first, each
        // with the highest-precedence spelling among the matches of the
        // same value and size, as long as its statements and arguments
        // don't overlap a match already chosen: each is then still a match
        // after the others, which keep every function, and doing them
        // together saves a check of the whole operation for each.
        Phase p{phase_s, "matches"};
        std::vector<const Report::Found*> chosen;
        std::set<int> values, gone, read;
        const OpInfo info = c_.analyze(op);
        for (const Report::Found& f : rep.matches) {
          if (!values.insert(f.value).second) continue;
          const Report::Found* best = &f;
          for (const Report::Found& g : rep.matches)
            if (g.value == f.value && g.removed == f.removed && spelling_before(index, info, g, *best)) best = &g;
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
          const int written = write_out_leading_back(best->op.rfind("not:", 0) == 0 ? best->op.substr(4) : best->op, index);
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
      if (rep.errors.count("order_arguments") || rep.errors.count("order_statements")) {
        res.status = "order";
        break;
      }
      done = true;
    }
    if (!done && res.status == "ok") res.status = "rounds";
    if (done) {
      Phase p{phase_s, "settle"};
      settle(index);
    }
    res.seconds = ProgramChecker::now() - t0;
    return res;
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

  // DLP 59's refactoring step 6: read views that don't matter are removed.
  // The written view doesn't depend on them, so their reads can be given
  // any value without changing it: the first read view the operation keeps
  // that makes none of its values constant, which would be an error the
  // fix loop doesn't fix. Then the views after them move down, and every
  // caller stops giving them a value (`apply_replacements`). Returns false,
  // changing nothing, when no kept view will do.
  bool drop_views(size_t index, const std::vector<int>& views) {
    const POp original_op = p_.ops[index];
    bool found = false;
    for (int y = 1; y <= original_op.nbool && !found; ++y) {
      if (std::find(views.begin(), views.end(), y) != views.end()) continue;
      PArg with;
      with.id = y;
      for (int v : views) replace_reads(p_.ops[index], v, with);
      // The values that read a dropped view now compute something else.
      c_.forget_values();
      found = !c_.has_constant_value(index);
      if (!found) p_.ops[index] = original_op;
    }
    c_.forget_values();
    if (!found) return false;
    POp& op = p_.ops[index];
    std::vector<int> original = dropped_.count(op.name) ? dropped_.at(op.name).first : std::vector<int>{};
    const int arity = dropped_.count(op.name) ? dropped_.at(op.name).second : op.nbool;
    // Positions in the views the callers give values to.
    std::vector<int> kept_positions;
    for (int i = 1; i <= arity; ++i)
      if (std::find(original.begin(), original.end(), i) == original.end()) kept_positions.push_back(i);
    for (int v : views) original.push_back(kept_positions[static_cast<size_t>(v - 1)]);
    std::sort(original.begin(), original.end());
    dropped_[op.name] = {original, arity};
    std::unordered_map<int, int> moved;
    int next = 1;
    for (int v = 1; v <= op.nbool; ++v)
      if (std::find(views.begin(), views.end(), v) == views.end()) moved[v] = next++;
    for (PStmt& st : op.stmts)
      for (PArg& a : st.args)
        if (!a.is_literal() && a.id <= op.nbool) a.id = moved.at(a.id);
    for (PArg& a : op.outs)
      if (!a.is_literal() && a.id <= op.nbool) a.id = moved.at(a.id);
    op.nbool = next - 1;
    return true;
  }

  // Replaces statement k, an execution, with the executed operation's own
  // statements, its views given the execution's arguments.
  void inline_call(POp& op, size_t k) { inline_body(op, k, p_.ops[static_cast<size_t>(c_.index_of(op.stmts[k].name))]); }

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

  // After an operation compiles: if it's a boolean operation that only
  // names one of its views, or one statement it wraps (DLP 61's wrapper),
  // it's removed and its callers compute that instead. A mixed operation
  // keeps its written views: a caller's values from a `run` are boolean
  // inputs there, and giving the caller the value instead would change
  // its functions, and could make one never change.
  void settle(size_t index) {
    POp& op = p_.ops[index];
    if (op.boolean) {
      const PArg& o = op.outs[0];
      Replacement r;
      if (o.id <= op.views()) {
        r.kind = "view";
        r.view = o.id - 1;
      } else {
        int statements = 0;
        const PStmt* only = nullptr;
        for (const PStmt& s : op.stmts)
          if (is_boolean_statement(s.kind)) {
            ++statements;
            only = &s;
          }
        if (statements != 1 || (only->kind == "call" && !c_.is_registered(only->name))) return;
        r.kind = "statement";
        r.statement = *only;
        // Its arguments are views, maybe through copies.
        std::unordered_map<int, int> copies;
        for (const PStmt& s : op.stmts)
          if (s.kind == "copy") copies[s.ids[0]] = s.args[0].id;
        for (PArg& a : r.statement.args)
          if (copies.count(a.id)) a.id = copies.at(a.id);
      }
      if (c_.is_registered(op.name)) return;
      replacements_[op.name] = {r};
      removed_.insert(op.name);
    }
  }

  // Fixes each operation in `ops` in order, each after the ones it executes,
  // then again each one whose definition a later fix wrote executions out
  // in, or whose executions give values to views a later fix removed, and,
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

  // Whether an operation executes one that was removed, or gives values to
  // views that were dropped.
  bool stale(const POp& op) const {
    for (const PStmt& s : op.stmts) {
      if (s.kind != "call" && s.kind != "run") continue;
      if (removed_.count(s.name)) return true;
      const auto d = dropped_.find(s.name);
      if (s.kind == "call" && d != dropped_.end() && static_cast<int>(s.args.size()) == d->second.second) return true;
    }
    return false;
  }

  // Calls of removed operations, and values given to dropped views, in
  // an operation about to be fixed.
  void apply_replacements(size_t index) {
    POp& op = p_.ops[index];
    // Views the executed operation no longer has: the values given to them
    // go (a caller written before the views were dropped gives them all).
    for (PStmt& s : op.stmts) {
      auto it = dropped_.find(s.name);
      if (s.kind != "call" || it == dropped_.end() || static_cast<int>(s.args.size()) != it->second.second) continue;
      std::vector<PArg> args;
      for (size_t i = 0; i < s.args.size(); ++i)
        if (!std::binary_search(it->second.first.begin(), it->second.first.end(), static_cast<int>(i + 1)))
          args.push_back(s.args[i]);
      s.args = std::move(args);
    }
    for (size_t k = 0; k < op.stmts.size(); ++k) {
      PStmt& s = op.stmts[k];
      auto it = replacements_.find(s.name);
      if (it == replacements_.end() || s.kind != "call") continue;
      const Replacement& r = it->second[0];
      const int v = s.ids[0];
      if (r.kind == "view") {
        const PArg a = s.args[static_cast<size_t>(r.view)];
        op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k--));
        replace_reads(op, v, a);
      } else {
        PStmt n = r.statement;
        for (PArg& a : n.args)
          if (!a.is_literal()) a = s.args[static_cast<size_t>(a.id - 1)];
        n.ids = s.ids;
        s = std::move(n);
        // The wrapped statement may itself call a removed operation.
        --k;
      }
    }
  }

  // Removes the operations that were replaced, and puts every operation
  // after the ones it executes: registered operations whose definitions now
  // execute ones defined after them move before them. Otherwise the order
  // stays.
  void finish() {
    std::map<std::string, POp> by_name;
    std::vector<std::string> names;
    for (POp& op : p_.ops) {
      if (removed_.count(op.name)) continue;
      names.push_back(op.name);
      by_name.emplace(op.name, std::move(op));
    }
    std::vector<POp> ordered;
    std::set<std::string> placed;
    std::function<void(const std::string&)> place = [&](const std::string& name) {
      if (!placed.insert(name).second) return;
      POp& op = by_name.at(name);
      for (const PStmt& s : op.stmts)
        if (s.kind == "call" || s.kind == "run") place(s.name);
      ordered.push_back(std::move(op));
    };
    for (const std::string& name : names) place(name);
    p_.ops = std::move(ordered);
    c_.rebuild_index();
  }

  ProgramChecker& c_;
  Program& p_;
  std::map<std::string, std::vector<Replacement>> replacements_;
  // Each operation's dropped read views (from 1, among the views it was
  // written with), and how many views it was written with.
  std::map<std::string, std::pair<std::vector<int>, int>> dropped_;
  std::set<std::string> removed_;
  // Operations whose definitions a fix of another one wrote executions out
  // in, by index.
  std::set<size_t> rewritten_;
  // Operations written with more than 256 boolean statements.
  std::set<std::string> over_limit_;
};

}  // namespace beq
