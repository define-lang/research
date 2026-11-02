// The fixes a refactoring tool applies to a whole program until it
// compiles (DLP 57's refactoring steps, DLP 58's order, DLP 59's matches,
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
      // The fixes may pass DLP 57's statement limit on the way to a smaller
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

  // What each removed operation, or removed written view, was replaced by,
  // one line each: NAME VIEW literal T|F, NAME VIEW view K (from 1), or NAME
  // VIEW statement KIND [OP] ARG... with arguments as view numbers (the
  // views the operation has after any were dropped).
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
        if (r.kind == "literal") out << " " << r.literal;
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
  // How the callers of a removed operation, or of a removed written view,
  // compute its value instead.
  struct Replacement {
    std::string kind;  // literal, view, statement
    std::string literal;
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
    forget_specialized(res.name);
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
      if (rep.literal_stmt >= 0) {
        Phase p{phase_s, "literals"};
        simplify_literals(index);
        ++res.fixes["literal"];
        continue;
      }
      if (!rep.redundant_kind.empty()) {
        // Every redundant value, up to an opposite value that's already a
        // `not`, at once: each is still a fix after the others, which keep
        // every function, and doing them together saves a check of the
        // whole operation for each.
        Phase p{phase_s, "redundant values"};
        bool literals = false;
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
          literals |= m.with.is_literal();
          ++res.fixes[m.with.is_literal() ? "constant" : "redundant"];
        }
        if (literals) simplify_literals(index);
        continue;
      }
      if (!rep.unused_views.empty()) {
        Phase p{phase_s, "unused views"};
        drop_views(index, rep.unused_views);
        // The values that read a dropped view now compute something else.
        c_.forget_values();
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
        // Every match in the order DLP 59 reports them, largest first, each
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
      forget_specialized(reg.name);
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
    const int ca = c_.ands_of_name(name(a)), cb = c_.ands_of_name(name(b));
    if (ca != cb) return ca < cb;
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

  // DLP 58's order, dead statements removed, and copies wherever one value
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

  // DLP 57's refactoring step 6: read views that don't matter are removed.
  // The written view doesn't depend on them, so their reads can be given
  // any value without changing it: another read view the operation keeps,
  // so that no execution is given a literal and written out. When it keeps
  // none, its written view is a constant and nothing reads the views any
  // more, so the literal is never used. Then the views after them move
  // down, and every caller stops giving them a value
  // (`apply_replacements`).
  void drop_views(size_t index, const std::vector<int>& views) {
    {
      POp& op = p_.ops[index];
      PArg with;
      with.literal = "F";
      for (int v = 1; v <= op.nbool; ++v)
        if (std::find(views.begin(), views.end(), v) == views.end()) {
          with.literal.clear();
          with.id = v;
          break;
        }
      for (int v : views) replace_reads(op, v, with);
    }
    simplify_literals(index);
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
  }

  // DLP 57's simplification of a value that never changes, until no
  // boolean statement is given a literal: `x and false` is false, `x and
  // true` is x, the `not` of a literal is the other one, and an execution
  // given a literal computes what the executed operation computes with it.
  void simplify_literals(size_t index) { simplify_literals(p_.ops[index], !c_.in_registered_reach(p_.ops[index].name)); }

  // `specialize`: an execution written out uses its operation's statements
  // already simplified with the same literals, kept for the next one. Only
  // where no registered operation executes op, so that the copy's
  // executions can't lead back to it.
  void simplify_literals(POp& op, bool specialize) {
    for (;;) {
      size_t k = 0;
      for (; k < op.stmts.size(); ++k) {
        const PStmt& s = op.stmts[k];
        if (!is_boolean_statement(s.kind)) continue;
        if (std::any_of(s.args.begin(), s.args.end(), [](const PArg& a) { return a.is_literal(); })) break;
      }
      if (k == op.stmts.size()) return;
      PStmt s = op.stmts[k];
      const int v = s.ids[0];
      auto lit = [](bool b) {
        PArg a;
        a.literal = b ? "T" : "F";
        return a;
      };
      auto truth = [](const PArg& a) { return a.literal == "T"; };
      if (s.kind == "not") {
        op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k));
        replace_reads(op, v, lit(!truth(s.args[0])));
        continue;
      }
      if (s.kind == "and") {
        const PArg& a = s.args[0];
        const PArg& b = s.args[1];
        PArg with;
        if (a.is_literal() && b.is_literal())
          with = lit(truth(a) && truth(b));
        else {
          const PArg& l = a.is_literal() ? a : b;
          const PArg& other = a.is_literal() ? b : a;
          with = truth(l) ? other : lit(false);
        }
        op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k));
        replace_reads(op, v, with);
        continue;
      }
      simplify_call(op, k, specialize);
    }
  }

  // An execution given literals: what the executed operation computes with
  // them, over its other arguments.
  void simplify_call(POp& op, size_t k, bool specialize) {
    const PStmt s = op.stmts[k];
    const int v = s.ids[0];
    const std::vector<uint64_t>& table = c_.recorded(s.name).table;
    std::vector<int> free;
    uint64_t fixed = 0;
    for (size_t j = 0; j < s.args.size(); ++j) {
      if (s.args[j].is_literal())
        fixed |= static_cast<uint64_t>(s.args[j].literal == "T") << j;
      else
        free.push_back(static_cast<int>(j));
    }
    const size_t r = free.size();
    std::vector<uint64_t> residual(r <= 6 ? 1 : (size_t{1} << (r - 6)), 0);
    for (uint64_t m = 0; m < (uint64_t{1} << r); ++m) {
      uint64_t full = fixed;
      for (size_t i = 0; i < r; ++i) full |= ((m >> i) & 1) << free[i];
      if ((table[full >> 6] >> (full & 63)) & 1) residual[m >> 6] |= 1ULL << (m & 63);
    }
    const uint64_t mask = r >= 6 ? ~0ULL : ((1ULL << (1u << r)) - 1);
    auto all = [&](uint64_t value) {
      for (size_t w = 0; w < residual.size(); ++w)
        if (residual[w] != (value & mask)) return false;
      return true;
    };
    auto lit = [](bool b) {
      PArg a;
      a.literal = b ? "T" : "F";
      return a;
    };
    auto arg = [&](size_t i) { return s.args[static_cast<size_t>(free[i])]; };
    if (all(0) || all(~0ULL)) {
      op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k));
      replace_reads(op, v, lit(!all(0)));
      return;
    }
    if (r <= 6) {
      static const uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                       0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
      const uint64_t t = residual[0];
      for (size_t i = 0; i < r; ++i) {
        if (t == (kVar[i] & mask)) {
          op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k));
          replace_reads(op, v, arg(i));
          return;
        }
        if (t == (~kVar[i] & mask)) {
          PStmt& n = op.stmts[k];
          n.kind = "not";
          n.name.clear();
          n.args = {arg(i)};
          return;
        }
      }
      // An `and` of two arguments, either of them negated.
      if (r == 2)
        for (int na = 0; na < 2; ++na)
          for (int nb = 0; nb < 2; ++nb) {
            const uint64_t x = na ? ~kVar[0] : kVar[0], y = nb ? ~kVar[1] : kVar[1];
            for (int out = 0; out < 2; ++out) {
              const uint64_t f = out ? ~(x & y) : (x & y);
              if ((f & mask) != t) continue;
              rewrite(op, k, "and", "", {negated(op, k, arg(0), na), negated(op, k, arg(1), nb)}, out != 0);
              return;
            }
          }
      // A registered operation of the same arity that op follows and that
      // doesn't execute it, with its result negated or not.
      for (const std::string& name : c_.follows(op)) {
        if (name == "and" || name == "not" || executes(name, op.name)) continue;
        const POp& reg = p_.ops[static_cast<size_t>(c_.index_of(name))];
        if (static_cast<size_t>(reg.nbool) != r) continue;
        const uint64_t rt = c_.recorded(name).table[0];
        Registered rr{name, static_cast<uint32_t>(r), rt};
        for (const std::vector<int>& perm : permutations(static_cast<uint32_t>(r))) {
          uint64_t f = 0;
          for (uint64_t m = 0; m < (uint64_t{1} << r); ++m) f |= static_cast<uint64_t>(permuted_bit(rr, perm, static_cast<uint32_t>(m))) << m;
          for (int out = 0; out < 2; ++out) {
            if (((out ? ~f : f) & mask) != t) continue;
            std::vector<PArg> args(r);
            for (size_t i = 0; i < r; ++i) args[i] = arg(static_cast<size_t>(perm[i]));
            rewrite(op, k, "call", name, args, out != 0);
            return;
          }
        }
      }
    }
    // Otherwise the executed operation's statements, written out in this
    // one with the literals given to its views, which simplifying then
    // removes; the program keeps its value operations, as the termination
    // proof models it.
    // Only the outermost write-out is timed: simplifying its copy writes
    // out more.
    struct Depth {
      int& depth;
      ~Depth() { --depth; }
    } depth{++write_out_depth_};
    std::optional<Phase> p;
    if (write_out_depth_ == 1) p.emplace(phase_s, "literal write-outs");
    if (!specialize) {
      inline_call(op, k);
      return;
    }
    std::string key = s.name;
    for (const PArg& a : s.args) key += a.is_literal() ? " " + a.literal : " *";
    auto it = specialized_.find(key);
    if (it == specialized_.end()) {
      POp body = p_.ops[static_cast<size_t>(c_.index_of(s.name))];
      for (int view = 1; view <= body.nbool; ++view)
        if (s.args[static_cast<size_t>(view - 1)].is_literal()) replace_reads(body, view, s.args[static_cast<size_t>(view - 1)]);
      simplify_literals(body, true);
      it = specialized_.emplace(key, std::move(body)).first;
    }
    inline_body(op, k, it->second);
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

  // The value of statement k becomes kind(args), negated if `negate`.
  static void rewrite(POp& op, size_t k, const std::string& kind, const std::string& name, const std::vector<PArg>& args,
                      bool negate) {
    PStmt exec;
    exec.kind = kind;
    exec.name = name;
    exec.args = args;
    if (!negate) {
      exec.ids = op.stmts[k].ids;
      op.stmts[k] = std::move(exec);
      return;
    }
    exec.ids = {op.next_id++};
    PStmt& n = op.stmts[k];
    n.kind = "not";
    n.name.clear();
    PArg e;
    e.id = exec.ids[0];
    n.args = {e};
    op.stmts.insert(op.stmts.begin() + static_cast<std::ptrdiff_t>(k), std::move(exec));
  }

  // The argument, or its `not`: an existing `not` statement of it if one
  // comes before statement k, otherwise a new one right before k.
  static PArg negated(POp& op, size_t& k, const PArg& a, bool negate) {
    if (!negate) return a;
    for (size_t j = 0; j < k; ++j)
      if (op.stmts[j].kind == "not" && op.stmts[j].args[0] == a) {
        PArg x;
        x.id = op.stmts[j].ids[0];
        return x;
      }
    PStmt n;
    n.kind = "not";
    n.args = {a};
    n.ids = {op.next_id++};
    PArg x;
    x.id = n.ids[0];
    op.stmts.insert(op.stmts.begin() + static_cast<std::ptrdiff_t>(k), std::move(n));
    ++k;
    return x;
  }

  // After an operation compiles: if it's a boolean operation that only
  // names a constant, one of its views, or one statement it wraps, it's
  // removed and its callers compute that instead; a mixed operation's
  // constant boolean written views are removed the same way (DLP 57's
  // refactoring step 4).
  void settle(size_t index) {
    POp& op = p_.ops[index];
    if (op.boolean) {
      const PArg& o = op.outs[0];
      Replacement r;
      if (o.is_literal()) {
        r.kind = "literal";
        r.literal = o.literal;
      } else if (o.id <= op.views()) {
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
      return;
    }
    std::vector<Replacement> views(op.outs.size());
    bool any = false;
    std::vector<PArg> kept;
    for (size_t o = 0; o < op.outs.size(); ++o) {
      const PArg& a = op.outs[o];
      if (a.is_literal() && a.literal[0] != '#') {
        views[o].kind = "literal";
        views[o].literal = a.literal;
        any = true;
      } else if (!a.is_literal() && a.id <= op.nbool) {
        views[o].kind = "view";
        views[o].view = a.id - 1;
        any = true;
      } else {
        kept.push_back(a);
      }
    }
    if (!any) return;
    op.outs = kept;
    replacements_[op.name] = views;
    c_.check(index, true, "tt");
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

  // The operation is about to change: its statements simplified with
  // literals aren't its statements any more.
  void forget_specialized(const std::string& name) {
    for (auto it = specialized_.lower_bound(name + " "); it != specialized_.end() && it->first.rfind(name + " ", 0) == 0;)
      it = specialized_.erase(it);
  }

  // Whether an operation executes one that was removed, or gives values to
  // views that were dropped or to written views that were removed.
  bool stale(const POp& op) const {
    for (const PStmt& s : op.stmts) {
      if (s.kind != "call" && s.kind != "run") continue;
      if (removed_.count(s.name)) return true;
      const auto d = dropped_.find(s.name);
      if (s.kind == "call" && d != dropped_.end() && static_cast<int>(s.args.size()) == d->second.second) return true;
      const auto r = replacements_.find(s.name);
      if (s.kind == "run" && r != replacements_.end() && s.ids.size() == r->second.size()) return true;
    }
    return false;
  }

  // Calls of removed operations, and values of removed written views, in
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
      if (it == replacements_.end() || (s.kind != "call" && s.kind != "run")) continue;
      if (s.kind == "call") {
        const Replacement& r = it->second[0];
        const int v = s.ids[0];
        if (r.kind == "literal") {
          PArg l;
          l.literal = r.literal;
          op.stmts.erase(op.stmts.begin() + static_cast<std::ptrdiff_t>(k--));
          replace_reads(op, v, l);
        } else if (r.kind == "view") {
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
        continue;
      }
      // A run already rewritten has fewer values than the replacement has
      // views.
      if (s.ids.size() != it->second.size()) continue;
      std::vector<int> ids;
      for (size_t o = 0; o < s.ids.size(); ++o) {
        const Replacement& r = it->second[o];
        if (r.kind.empty()) {
          ids.push_back(s.ids[o]);
          continue;
        }
        PArg with;
        if (r.kind == "literal")
          with.literal = r.literal;
        else
          with = s.args[static_cast<size_t>(r.view)];
        replace_reads(op, s.ids[o], with);
      }
      s.ids = ids;
    }
    simplify_literals(index);
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
  // Each operation's statements simplified with literals given to some of
  // its views, by NAME then T, F or * for each view.
  std::map<std::string, POp> specialized_;
  int write_out_depth_ = 0;
  // Operations written with more than 256 boolean statements.
  std::set<std::string> over_limit_;
};

}  // namespace beq
