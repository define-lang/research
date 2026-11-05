// Whole Define programs (gen/program.py's format): every rule of DLPs 58-60
// checked per value operation with executions as references, the fixes a
// refactoring tool applies, and incremental rechecking.
#pragma once

#include <algorithm>
#include <chrono>
#include <fstream>
#include <functional>
#include <limits>
#include <tuple>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include "hier.hpp"
#include "match.hpp"
#include "min_ands.hpp"
#include "methods.hpp"
#include "split.hpp"

namespace beq {

// An argument: a value (by id) or a literal (`T`, `F`, or `#TEXT`).
struct PArg {
  int id = 0;
  std::string literal;
  bool is_literal() const { return id == 0; }
  bool operator==(const PArg& o) const { return id == o.id && literal == o.literal; }
};

struct PStmt {
  std::string kind;  // and, not, call, copy, cmp, num, run
  std::string name;  // the operation of call, run, cmp, num
  std::vector<PArg> args;
  std::vector<int> ids;  // the values it defines
};

struct POp {
  std::string name;
  bool boolean = true;
  int nbool = 0, nnum = 0;
  std::vector<PStmt> stmts;
  std::vector<PArg> outs;
  int next_id = 1;
  int views() const { return nbool + nnum; }
};

struct Program {
  std::vector<std::string> registered;
  std::vector<POp> ops;
};

inline bool is_boolean_statement(const std::string& kind) { return kind == "and" || kind == "not" || kind == "call"; }

inline PArg parse_arg(const std::string& w) {
  PArg a;
  if (w == "T" || w == "F" || w[0] == '#')
    a.literal = w;
  else
    a.id = std::stoi(w);
  return a;
}

inline std::string arg_text(const PArg& a, const std::unordered_map<int, int>& number) {
  return a.is_literal() ? a.literal : std::to_string(number.at(a.id));
}

inline Program read_program(const std::string& path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open " + path);
  Program p;
  std::unordered_map<std::string, int> index;
  POp* op = nullptr;
  for (std::string line; std::getline(in, line);) {
    std::istringstream words(line);
    std::string kind;
    if (!(words >> kind)) continue;
    if (kind == "registered") {
      for (std::string name; words >> name;) p.registered.push_back(name);
    } else if (kind == "op") {
      p.ops.emplace_back();
      op = &p.ops.back();
      std::string type;
      words >> op->name >> type;
      op->boolean = type == "bool";
      if (op->boolean)
        words >> op->nbool;
      else
        words >> op->nbool >> op->nnum;
      op->next_id = op->views() + 1;
      index[op->name] = static_cast<int>(p.ops.size() - 1);
    } else if (kind == "out") {
      for (std::string w; words >> w;) op->outs.push_back(parse_arg(w));
    } else if (kind == "end") {
      op = nullptr;
    } else {
      PStmt s;
      s.kind = kind;
      if (kind == "call" || kind == "run" || kind == "cmp" || kind == "num") words >> s.name;
      for (std::string w; words >> w;) s.args.push_back(parse_arg(w));
      int n = 1;
      if (kind == "run") n = static_cast<int>(p.ops[static_cast<size_t>(index.at(s.name))].outs.size());
      for (int k = 0; k < n; ++k) s.ids.push_back(op->next_id++);
      op->stmts.push_back(std::move(s));
    }
  }
  return p;
}

inline void write_program(const Program& p, const std::string& path) {
  std::ofstream out(path);
  out << "registered";
  for (const std::string& r : p.registered) out << " " << r;
  out << "\n";
  for (const POp& op : p.ops) {
    std::unordered_map<int, int> number;
    int next = 1;
    for (int v = 1; v <= op.views(); ++v) number[v] = next++;
    for (const PStmt& s : op.stmts)
      for (int id : s.ids) number[id] = next++;
    if (op.boolean)
      out << "op " << op.name << " bool " << op.nbool << "\n";
    else
      out << "op " << op.name << " mixed " << op.nbool << " " << op.nnum << "\n";
    for (const PStmt& s : op.stmts) {
      out << s.kind;
      if (!s.name.empty()) out << " " << s.name;
      for (const PArg& a : s.args) out << " " << arg_text(a, number);
      out << "\n";
    }
    out << "out";
    for (const PArg& a : op.outs) out << " " << arg_text(a, number);
    out << "\nend\n";
  }
}

// What an operation records once it's checked, for the operations that
// execute it.
struct Recorded {
  std::vector<uint64_t> table;  // a boolean operation's written view, 2^views bits
  std::vector<int> group;       // a label per read view: equal labels are interchangeable
  std::vector<char> out_boolean;  // a mixed operation: which written views are boolean
  uint64_t hash = 0;
  // The written view's function also as an and-inverter graph over the read
  // views (nodes from views + 1), with every execution written out and
  // structural hashing, when that's smaller than looking each minterm up in
  // the table costs: executing it then costs one operation per node per
  // word of the caller's tables instead of one lookup per minterm.
  std::vector<std::pair<Lit, Lit>> aig;
  Lit aig_out = 0;
  bool has_aig = false;
  // Past twenty boolean inputs, the written view's decision diagram (DLP
  // 58) instead of a table.
  std::shared_ptr<RecordedDiagram> diagram;
  // A table of more than six views as a diagram, made the first time an
  // operation checked with BDDs executes it: each execution then follows
  // its nodes instead of all of its rows.
  mutable std::shared_ptr<RecordedDiagram> table_diagram;
};

// Everything about one operation's values that the rules need.
struct OpInfo {
  struct Value {
    char kind = 'b';  // 'b' boolean, 'n' numeric
    int stmt = -1;    // the statement that defines it; -1 for a read view
    int out = 0;      // which of a `run`'s values
  };
  std::unordered_map<int, Value> values;
  std::unordered_map<int, int> source;  // a copy's source
  std::vector<int> inputs;             // boolean inputs, by input number - 1
  std::unordered_map<int, int> input_number;
  std::unordered_map<int, Lit> lit;    // each boolean value's literal
  std::vector<int> node_stmt;          // for nodes past the inputs: the statement
  uint32_t num_nodes = 0;
  int boolean_statements = 0;
  int resolve(int id) const {
    auto it = source.find(id);
    return it == source.end() ? id : it->second;
  }
};

inline std::string rank_name(const PStmt& s) {
  if (s.kind == "and") return "standard:/boolean/and";
  if (s.kind == "not") return "standard:/boolean/not";
  return s.name;
}

struct CheckTimes {
  double structure = 0, tables = 0, groups = 0, order = 0, redundant = 0, matches = 0, spellings = 0, split = 0;
  // Parts of `tables`: executions of operations looked up in their recorded
  // tables, minterm by minterm, and executions of written-out ones.
  double lookups = 0, written_out = 0;
  void add(const CheckTimes& o) {
    lookups += o.lookups;
    written_out += o.written_out;
    structure += o.structure;
    tables += o.tables;
    groups += o.groups;
    order += o.order;
    redundant += o.redundant;
    matches += o.matches;
    spellings += o.spellings;
    split += o.split;
  }
  double total() const { return structure + tables + groups + order + redundant + matches + spellings + split; }
};

// The first violation of each rule, in gen/program.py's terms.
struct Report {
  std::map<std::string, std::string> errors;
  // For the fixes.
  int redundant_value = 0, redundant_other = 0;
  // Unless the first redundant value never changes: it and every later one,
  // up to the first that never changes or is the opposite of an earlier
  // value and already a `not`, with what replaces it: an earlier value, or
  // for an opposite value, the `not` of the earlier value.
  struct Merge {
    int value = 0;
    PArg with;
    bool opposite = false;
  };
  std::vector<Merge> merges;
  std::string redundant_kind;
  int literal_stmt = -1;
  struct Found {
    int value = 0;
    std::string op;  // "not:R" for an opposite result
    size_t removed = 0;
    std::vector<int> args;
    std::vector<int> removed_values;  // a match's statements that go, by value
  };
  Found match, spelling;
  std::vector<Found> matches;  // every match, for the spelling a fix uses
  std::vector<int> dead;          // dead boolean statements' values
  std::vector<int> unused_views;  // read views that don't matter, from 1
  bool has_match = false, has_spelling = false;
  std::string how;
  uint32_t inputs = 0;
  CheckTimes times;
  Stats stats;
};

class ProgramChecker {
 public:
  explicit ProgramChecker(Program& p) : p_(p) { rebuild_index(); }

  // DLP 58's limit of 256 boolean statements. The fix loop checks past it:
  // writing out an execution given a constant can pass it on the way to a
  // smaller operation.
  bool statement_limit = true;
  // The fix loop fixes one kind of error at a time, in a fixed order
  // (literals, redundant values, read views that don't matter, matches,
  // spellings), so it skips the searches for kinds after the first found.
  bool first_fix_only = false;
  // With reuse_search (`--keep_searches 1`), the fix loop keeps each
  // value's search from one check to the next (Matcher::SearchCache); with
  // check_search as well, every check also searches again and stops if the
  // two differ.
  bool reuse_search = false, check_search = false;
  // With split (`--split 1`), the rules on values (redundant values, read
  // views that don't matter) and the limits are checked statement by
  // statement (split.hpp) instead of with truth tables over every boolean
  // input; past 20 inputs, only those rules and the ones that don't need
  // values' functions are checked. With check_split as well, every check
  // also finds the redundant values and read views the other way, with
  // truth tables up to 20 inputs and SAT up to 32, and stops if the two
  // differ.
  bool split = false, check_split = false;
  // The exact method (`--method`): "auto", the default, is DLP 58's rule
  // (truth tables up to 16 inputs, OBDDs past them within step_budget); the
  // others are for methods_experiment.py: "tt" (truth tables over every
  // input, up to input_limit inputs), "chunk" (truth tables
  // 2^chunk_inputs input assignments at a time), "bdd" (OBDDs, inputs in
  // bdd_order), "sat" (SAT sweeping), or "split" (split.hpp). With
  // measure_executions, each operation's report also gives what an
  // execution of it refers to and what evaluating that costs.
  std::string method = "auto", bdd_order = "dfs";
  uint32_t input_limit = 20, chunk_inputs = 16;
  size_t bdd_node_limit = size_t{1} << 26;
  bool measure_executions = false;
  // Without search_matches (`--matches 0`), no matches or spellings are
  // searched: the other parts of a method that can't search in time.
  bool search_matches = true;
  size_t split_compared_tt = 0, split_compared_sat = 0;
  mutable std::map<std::string, std::pair<uint64_t, bool>> views_matter_;
  // Values whose kept search was used, and searched again, so far (with
  // the ones in search_cache_).
  size_t search_hits = 0, search_misses = 0;
  size_t kept_hits() const { return search_hits + search_cache_.hits; }
  size_t kept_misses() const { return search_misses + search_cache_.misses; }

  // While the fix loop works on one operation, every value keeps its
  // function from one fix to the next (until a read view is dropped), so
  // executions' tables and exact checks are kept by value instead of
  // computed again.
  bool reuse_values = false;
  void forget_values() {
    reuse_name_.clear();
    call_rows_.clear();
    holds_cache_.clear();
    key_of_value_.clear();
    hash_of_value_.clear();
    search_hits += search_cache_.hits;
    search_misses += search_cache_.misses;
    search_cache_ = Matcher::SearchCache{};
  }

  Program& program() { return p_; }
  // After an edit to booleans.defcl in a program that compiled: only these
  // registered operations can make new matches or spellings, the new ones
  // and those whose place in the order changed; `matches` is false when
  // only the order changed, which can't add a match. An operation that
  // executes a newly registered one is checked against all of them.
  void set_registry_edit(std::set<std::string> changed, std::set<std::string> added, bool matches) {
    changed_ = std::move(changed);
    added_ = std::move(added);
    edit_matches_ = matches;
  }
  const Recorded& recorded(const std::string& name) const { return recorded_.at(name); }
  bool has_recorded(const std::string& name) const { return recorded_.count(name) > 0; }
  // After operations are added or removed: the index, and the hierarchy
  // the SAT check uses, rebuilt from every operation already recorded.
  void rebuild_index() {
    index_.clear();
    for (size_t i = 0; i < p_.ops.size(); ++i) index_[p_.ops[i].name] = static_cast<int>(i);
    find_cycles();
    std::map<std::string, std::vector<uint32_t>> stored;
    if (hier_) stored = std::move(hier_->stored);
    std::vector<HOp> ops(p_.ops.size());
    hier_ = std::make_unique<Hierarchy>(std::move(ops));
    hier_->stored = std::move(stored);
    for (size_t i = 0; i < p_.ops.size(); ++i)
      if (recorded_.count(p_.ops[i].name)) update_hierarchy(i, analyze(p_.ops[i]));
  }
  // DLP 9 forbids execution cycles: the operations in one (by their
  // strongly connected component), and every operation that executes one,
  // whose functions are undefined.
  void find_cycles() {
    component_.assign(p_.ops.size(), -1);
    cyclic_.assign(p_.ops.size(), 0);
    reaches_cycle_.assign(p_.ops.size(), 0);
    std::vector<int> low(p_.ops.size(), 0), order(p_.ops.size(), -1), stack;
    std::vector<char> on_stack(p_.ops.size(), 0);
    int next = 0, components = 0;
    std::function<void(size_t)> visit = [&](size_t i) {
      order[i] = low[i] = next++;
      stack.push_back(static_cast<int>(i));
      on_stack[i] = 1;
      for (const PStmt& s : p_.ops[i].stmts) {
        if (s.kind != "call" && s.kind != "run") continue;
        const size_t j = static_cast<size_t>(index_.at(s.name));
        if (j == i) cyclic_[i] = 1;
        if (order[j] < 0) {
          visit(j);
          low[i] = std::min(low[i], low[j]);
        } else if (on_stack[j]) {
          low[i] = std::min(low[i], order[j]);
        }
      }
      if (low[i] != order[i]) return;
      std::vector<int> members;
      for (int top = -1; top != static_cast<int>(i);) {
        top = stack.back();
        stack.pop_back();
        on_stack[static_cast<size_t>(top)] = 0;
        component_[static_cast<size_t>(top)] = components;
        members.push_back(top);
      }
      ++components;
      for (int m : members) {
        if (members.size() > 1) cyclic_[static_cast<size_t>(m)] = 1;
        reaches_cycle_[static_cast<size_t>(m)] = cyclic_[static_cast<size_t>(m)];
      }
      // Components finish after every component they execute.
      for (int m : members)
        for (const PStmt& s : p_.ops[static_cast<size_t>(m)].stmts)
          if ((s.kind == "call" || s.kind == "run") && reaches_cycle_[static_cast<size_t>(index_.at(s.name))])
            for (int n : members) reaches_cycle_[static_cast<size_t>(n)] = 1;
    };
    for (size_t i = 0; i < p_.ops.size(); ++i)
      if (order[i] < 0) visit(i);
  }

  int index_of(const std::string& name) const { return index_.at(name); }
  bool in_registered_reach(const std::string& name) const { return registered_reach_.count(name) > 0; }
  bool has_op(const std::string& name) const { return index_.count(name) > 0; }
  // Adds an operation at the end, without disturbing the others' indices.
  size_t add_op(POp op) {
    p_.ops.push_back(std::move(op));
    const size_t at = p_.ops.size() - 1;
    index_[p_.ops[at].name] = static_cast<int>(at);
    // Nothing executes it yet, so it's in no cycle.
    component_.push_back(-1 - static_cast<int>(at));
    cyclic_.push_back(0);
    char reaches = 0;
    for (const PStmt& s : p_.ops[at].stmts)
      if (s.kind == "call" || s.kind == "run") reaches |= reaches_cycle_[static_cast<size_t>(index_.at(s.name))];
    reaches_cycle_.push_back(reaches);
    hier_->add(HOp());
    return at;
  }
  void forget(const std::string& name) { recorded_.erase(name); }
  bool is_registered(const std::string& name) const {
    return std::find(p_.registered.begin(), p_.registered.end(), name) != p_.registered.end();
  }

  // Patterns stored by the SAT check, by operation name.
  std::map<std::string, std::vector<uint32_t>>& patterns() { return hier_->stored; }

  OpInfo analyze(const POp& op) const {
    OpInfo info;
    for (int v = 1; v <= op.views(); ++v) info.values[v] = {v <= op.nbool ? 'b' : 'n', -1, 0};
    for (size_t k = 0; k < op.stmts.size(); ++k) {
      const PStmt& s = op.stmts[k];
      const int stmt = static_cast<int>(k);
      if (s.kind == "copy") {
        const int src = info.resolve(s.args[0].id);
        info.source[s.ids[0]] = src;
        info.values[s.ids[0]] = {info.values.at(src).kind, stmt, 0};
      } else if (s.kind == "num") {
        info.values[s.ids[0]] = {'n', stmt, 0};
      } else if (s.kind == "run") {
        const Recorded& r = recorded_.at(s.name);
        for (size_t o = 0; o < s.ids.size(); ++o)
          info.values[s.ids[o]] = {r.out_boolean[o] ? 'b' : 'n', stmt, static_cast<int>(o)};
      } else {
        info.values[s.ids[0]] = {'b', stmt, 0};
        if (is_boolean_statement(s.kind)) ++info.boolean_statements;
      }
    }
    // Boolean inputs in value order: read views, then results of statements
    // that aren't boolean, as they come.
    for (int v = 1; v <= op.nbool; ++v) info.inputs.push_back(v);
    for (const PStmt& s : op.stmts)
      if (s.kind == "cmp" || s.kind == "run")
        for (int id : s.ids)
          if (info.values.at(id).kind == 'b') info.inputs.push_back(id);
    for (size_t k = 0; k < info.inputs.size(); ++k) {
      info.input_number[info.inputs[k]] = static_cast<int>(k + 1);
      info.lit[info.inputs[k]] = make_lit(static_cast<uint32_t>(k + 1));
    }
    uint32_t node = static_cast<uint32_t>(info.inputs.size()) + 1;
    for (size_t k = 0; k < op.stmts.size(); ++k) {
      const PStmt& s = op.stmts[k];
      if (s.kind == "and" || s.kind == "call") {
        info.lit[s.ids[0]] = make_lit(node++);
        info.node_stmt.push_back(static_cast<int>(k));
      } else if (s.kind == "not") {
        info.lit[s.ids[0]] = arg_lit(info, s.args[0]) ^ 1;
      } else if (s.kind == "copy" && info.values.at(s.ids[0]).kind == 'b') {
        info.lit[s.ids[0]] = info.lit.at(info.resolve(s.ids[0]));
      }
    }
    info.num_nodes = node;
    return info;
  }

  Lit arg_lit(const OpInfo& info, const PArg& a) const {
    if (a.is_literal()) return a.literal == "T" ? 1 : 0;
    return info.lit.at(info.resolve(a.id));
  }

  // Truth tables over every boolean input for every node, executions looked
  // up in the executed operation's recorded table.
  std::vector<uint64_t> tables(const POp& op, const OpInfo& info, size_t& words) const {
    const uint32_t I = static_cast<uint32_t>(info.inputs.size());
    words = I <= 6 ? 1 : (size_t{1} << (I - 6));
    std::vector<uint64_t> t(size_t{info.num_nodes} * words, 0);
    static const uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                     0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
    for (uint32_t i = 1; i <= I; ++i) {
      uint64_t* row = &t[size_t{i} * words];
      const uint32_t bit = i - 1;
      for (size_t w = 0; w < words; ++w) row[w] = bit < 6 ? kVar[bit] : (((w >> (bit - 6)) & 1) ? ~0ULL : 0);
    }
    auto word = [&](Lit l, size_t w) { return t[size_t{node_of(l)} * words + w] ^ (is_compl(l) ? ~0ULL : 0); };
    uint32_t node = I + 1;
    std::vector<Lit> args;
    for (int k : info.node_stmt) {
      const PStmt& s = op.stmts[static_cast<size_t>(k)];
      uint64_t* row = &t[size_t{node} * words];
      args.clear();
      for (const PArg& a : s.args) args.push_back(arg_lit(info, a));
      const bool reuse = reuse_values && reuse_name_ == op.name;
      if (s.kind == "and") {
        for (size_t w = 0; w < words; ++w) row[w] = word(args[0], w) & word(args[1], w);
      } else if (reuse && call_rows_.count(s.ids[0])) {
        const std::vector<uint64_t>& kept = call_rows_.at(s.ids[0]);
        std::copy(kept.begin(), kept.end(), row);
      } else {
        const Recorded& callee = recorded_.at(s.name);
        const double te = now();
        if (callee.diagram) {
          evaluate_diagram(*callee.diagram, args, words, word, row);
          written_out_s_ += now() - te;
        } else if (callee.has_aig) {
          evaluate_aig(callee, args, words, word, row);
          written_out_s_ += now() - te;
        } else {
          lookup(callee.table, args, words, word, row);
          lookup_s_ += now() - te;
        }
        if (reuse) call_rows_[s.ids[0]].assign(row, row + words);
      }
      ++node;
    }
    if (I < 6)
      for (size_t n = 0; n < info.num_nodes; ++n) t[n] &= (1ULL << (1u << I)) - 1;
    return t;
  }

  template <typename Word>
  static void evaluate_aig(const Recorded& callee, const std::vector<Lit>& args, size_t words, Word word, uint64_t* row) {
    const size_t first = args.size() + 1;
    std::vector<uint64_t> v(first + callee.aig.size());
    auto get = [&](Lit l) { return v[node_of(l)] ^ (is_compl(l) ? ~0ULL : 0); };
    for (size_t w = 0; w < words; ++w) {
      v[0] = 0;
      for (size_t j = 0; j < args.size(); ++j) v[j + 1] = word(args[j], w);
      for (size_t n = 0; n < callee.aig.size(); ++n) v[first + n] = get(callee.aig[n].first) & get(callee.aig[n].second);
      row[w] = get(callee.aig_out);
    }
  }

  template <typename Word>
  static void lookup(const std::vector<uint64_t>& table, const std::vector<Lit>& args, size_t words, Word word,
                     uint64_t* row) {
    const size_t k = args.size();
    auto bit = [&](uint64_t m) { return (table[m >> 6] >> (m & 63)) & 1; };
    if (k <= 6) {
      // A mux tree over the arguments' words: 2^k - 1 selections per word.
      std::vector<uint64_t> level(size_t{1} << k);
      std::vector<uint64_t> a(k);
      for (size_t w = 0; w < words; ++w) {
        for (size_t j = 0; j < k; ++j) a[j] = word(args[j], w);
        for (uint64_t m = 0; m < (uint64_t{1} << k); ++m) level[m] = bit(m) ? ~0ULL : 0;
        for (size_t j = k; j-- > 0;) {
          const size_t half = size_t{1} << j;
          for (size_t m = 0; m < half; ++m) level[m] = (a[j] & level[m + half]) | (~a[j] & level[m]);
        }
        row[w] = level[0];
      }
      return;
    }
    std::vector<uint64_t> a(k);
    for (size_t w = 0; w < words; ++w) {
      for (size_t j = 0; j < k; ++j) a[j] = word(args[j], w);
      uint64_t out = 0;
      for (int b = 0; b < 64; ++b) {
        uint64_t m = 0;
        for (size_t j = 0; j < k; ++j) m |= ((a[j] >> b) & 1) << j;
        out |= bit(m) << b;
      }
      row[w] = out;
    }
  }

  // Interchangeable views of a boolean operation: one equality check per
  // pair of read views, on its recorded table, a word at a time.
  static std::vector<int> groups_of(const std::vector<uint64_t>& table, int views) {
    std::vector<int> parent(static_cast<size_t>(views));
    std::iota(parent.begin(), parent.end(), 0);
    std::function<int(int)> find = [&](int x) {
      int& p = parent[static_cast<size_t>(x)];
      return p == x ? x : p = find(p);
    };
    static const uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                     0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
    const size_t words = table.size();
    const uint64_t valid = views >= 6 ? ~0ULL : ((1ULL << (1u << views)) - 1);
    // Swapping views i < j changes only minterms where they differ: the one
    // with i false and j true must equal its partner with i true, j false.
    auto swappable = [&](int i, int j) {
      if (j < 6) {
        const uint64_t lo = ~kVar[i] & kVar[j] & valid, hi = kVar[i] & ~kVar[j] & valid;
        const int d = (1 << j) - (1 << i);
        for (size_t w = 0; w < words; ++w)
          if ((table[w] & lo) != ((table[w] & hi) << d)) return false;
        return true;
      }
      const size_t bj = size_t{1} << (j - 6);
      if (i < 6) {
        for (size_t w = 0; w < words; ++w) {
          if (w & bj) continue;
          if ((table[w | bj] & ~kVar[i]) != ((table[w] & kVar[i]) >> (1 << i))) return false;
        }
        return true;
      }
      const size_t bi = size_t{1} << (i - 6);
      for (size_t w = 0; w < words; ++w)
        if (!(w & bi) && (w & bj) && table[w] != table[w ^ bi ^ bj]) return false;
      return true;
    };
    for (int i = 0; i < views; ++i)
      for (int j = i + 1; j < views; ++j)
        if (find(i) != find(j) && swappable(i, j)) parent[static_cast<size_t>(find(j))] = find(i);
    std::vector<int> label(static_cast<size_t>(views));
    for (int v = 0; v < views; ++v) label[static_cast<size_t>(v)] = find(v);
    return label;
  }

  // The groups of a boolean statement's operation, as a label per view.
  std::vector<int> statement_groups(const PStmt& s) const {
    if (s.kind == "and") return {0, 0};
    if (s.kind == "not") return {0};
    return recorded_.at(s.name).group;
  }

  // DLP 59's rank order. Returns <0, 0, >0.
  struct Ranker {
    const POp& op;
    const OpInfo& info;
    std::map<std::pair<int, int>, int> memo;
    int category(const PArg& a) const {
      if (a.is_literal()) return 1;
      return info.values.at(info.resolve(a.id)).stmt < 0 ? 0 : 2;
    }
    int compare(const PArg& x, const PArg& y) {
      const int cx = category(x), cy = category(y);
      if (cx != cy) return cx < cy ? -1 : 1;
      if (cx == 1) {
        const std::string qx = x.literal[0] == '#' ? "number" : "boolean", qy = y.literal[0] == '#' ? "number" : "boolean";
        if (qx != qy) return qx < qy ? -1 : 1;
        return x.literal == y.literal ? 0 : (x.literal < y.literal ? -1 : 1);
      }
      const int a = info.resolve(x.id), b = info.resolve(y.id);
      if (a == b) return 0;
      if (cx == 0) return a < b ? -1 : 1;
      auto it = memo.find({a, b});
      if (it != memo.end()) return it->second;
      const OpInfo::Value& va = info.values.at(a);
      const OpInfo::Value& vb = info.values.at(b);
      const PStmt& sa = op.stmts[static_cast<size_t>(va.stmt)];
      const PStmt& sb = op.stmts[static_cast<size_t>(vb.stmt)];
      int r = 0;
      for (size_t k = 0; k < std::min(sa.args.size(), sb.args.size()) && r == 0; ++k) r = compare(sa.args[k], sb.args[k]);
      if (r == 0 && sa.args.size() != sb.args.size()) r = sa.args.size() < sb.args.size() ? -1 : 1;
      if (r == 0) {
        const std::string na = rank_name(sa), nb = rank_name(sb);
        if (na != nb) r = na < nb ? -1 : 1;
      }
      if (r == 0 && va.out != vb.out) r = va.out < vb.out ? -1 : 1;
      memo[{a, b}] = r;
      memo[{b, a}] = -r;
      return r;
    }
  };

  // The canonical order of the statements other than copies (DLP 59).
  std::vector<int> canonical_order(const POp& op, const OpInfo& info) const {
    std::vector<int> order;
    std::set<int> placed;
    std::function<void(const PArg&)> visit = [&](const PArg& a) {
      if (a.is_literal()) return;
      const int v = info.resolve(a.id);
      const OpInfo::Value& val = info.values.at(v);
      if (val.stmt < 0) return;
      const PStmt& s = op.stmts[static_cast<size_t>(val.stmt)];
      if (!is_boolean_statement(s.kind) || placed.count(val.stmt)) return;
      for (const PArg& x : s.args) visit(x);
      placed.insert(val.stmt);
      order.push_back(val.stmt);
    };
    for (size_t k = 0; k < op.stmts.size(); ++k) {
      const PStmt& s = op.stmts[k];
      if (s.kind != "cmp" && s.kind != "num" && s.kind != "run") continue;
      for (const PArg& a : s.args) visit(a);
      order.push_back(static_cast<int>(k));
    }
    for (const PArg& a : op.outs) visit(a);
    return order;
  }

  // Checks one operation. With `record`, also records what it computes for
  // the operations that execute it. `how`: "auto" (truth tables up to 20
  // inputs, DLP 58's limit, since matches need every value's table anyway;
  // SAT with stored patterns for redundant values only past it) or "tt". `registry_only` skips the rules a booleans.defcl edit can't change.
  Report check(size_t index, bool record, const std::string& how = "auto", bool registry_only = false) {
    const POp& op = p_.ops[index];
    if (reuse_values && reuse_name_ != op.name) {
      forget_values();
      reuse_name_ = op.name;
    }
    Report rep;
    double t0 = now();
    OpInfo info = analyze(op);
    const uint32_t I = static_cast<uint32_t>(info.inputs.size());
    rep.inputs = I;
    if (split) {
      // The split check finds the limits below.
    } else if (info.boolean_statements > 256 && statement_limit && method != "auto") {
      rep.errors["limits"] = "\"statements\"";
    } else if (I > input_limit && method != "auto") {
      rep.errors["limits"] = "\"inputs\"";
    }
    for (size_t k = 0; k < op.stmts.size() && rep.literal_stmt < 0; ++k) {
      const PStmt& s = op.stmts[k];
      if (!is_boolean_statement(s.kind)) continue;
      for (const PArg& a : s.args)
        if (a.is_literal()) {
          rep.literal_stmt = static_cast<int>(k);
          rep.errors["literal"] = std::to_string(k);
          break;
        }
    }
    if (op.boolean && info.boolean_statements == 1) {
      for (const PStmt& s : op.stmts)
        if (is_boolean_statement(s.kind) && (s.kind != "call" || is_registered(s.name))) rep.errors["wrapper"] = "true";
    }
    if (reaches_cycle_[index]) {
      std::vector<int> back;
      for (const PStmt& s : op.stmts)
        if ((s.kind == "call" || s.kind == "run") && component_[static_cast<size_t>(index_.at(s.name))] == component_[index] &&
            cyclic_[index])
          back.push_back(s.ids[0]);
      if (!back.empty()) rep.errors["cycle"] = list_json(back);
    }
    rep.times.structure = now() - t0;
    if (rep.errors.count("limits") || reaches_cycle_[index]) return rep;
    // auto is DLP 58's rule: truth tables up to 16 inputs, and up to 20 for
    // a value operation that executes one of more than six views, which
    // tables look up where BDDs would have to apply it node by node; BDDs
    // otherwise. Past the old limits (256 statements, 20 inputs), checking
    // counts steps against the budget; within them, a value operation whose
    // BDDs go over the budget is checked with truth tables instead.
    const bool old_limits = info.boolean_statements <= 256 && I <= 20;
    {
      bool wide_execution = false;
      for (const PStmt& s : op.stmts) wide_execution |= s.kind == "call" && s.args.size() > 6;
      const std::string use =
          method == "auto" ? (I <= 16 || (I <= 20 && wide_execution) ? "tt" : "bdd") : method;
      if (use != "tt" && !in_registered_reach(op.name) && (op.boolean || method == "auto")) {
        const Report before = rep;
        bool fell_back = false;
        Report r = check_with_method(op, info, record, rep, use, old_limits, fell_back);
        if (!fell_back) return r;
        rep = before;
        rep.stats.emplace_back("budget_fallback", 1);
      }
    }
    StepBudget budget;
    const bool budgeted = method == "auto" && !old_limits && step_budget && !in_registered_reach(op.name);
    if (budgeted) budget.limit = step_budget;
    try {

    std::unique_ptr<SplitCheck> sc;
    if (split) {
      const double ts = now();
      sc = split_check(op, info, rep);
      rep.times.split = now() - ts;
      if (rep.errors.count("limits")) {
        // What a mixed operation records doesn't need its values' functions.
        if (record && op.boolean) forget(op.name);
        if (record && !op.boolean) record_op(op, info, {}, 0);
        return rep;
      }
    }
    // Truth tables over every boolean input: always within the limits,
    // where matches and executions need them; past them only with split.
    const bool full = I <= input_limit;
    double t1 = now();
    size_t words = 1;
    lookup_s_ = written_out_s_ = 0;
    std::vector<uint64_t> t;
    if (full) t = tables(op, info, words);
    // Truth tables cost a step for every 2 words they compute.
    if (budgeted) budget.spend(size_t{info.num_nodes} * words / 2 + 1, StepBudget::kSearch);
    rep.times.lookups = lookup_s_;
    rep.times.written_out = written_out_s_;
    if (record) {
      if (full || !op.boolean) {
        record_op(op, info, t, words);
        update_hierarchy(index, info);
      } else {
        // An operation that executes it is past the limits (split_check).
        forget(op.name);
      }
    }
    rep.times.tables = now() - t1;
    std::vector<int> table_unused;
    {
      double td = now();
      rep.dead = dead_statements(op, info);
      if (!rep.dead.empty()) rep.errors["dead"] = list_json(rep.dead);
      if (op.boolean && full) {
        std::vector<uint64_t> written;
        const Lit o = arg_lit(info, op.outs[0]);
        for (size_t w = 0; w < words; ++w) written.push_back(t[size_t{node_of(o)} * words + w] ^ (is_compl(o) ? ~0ULL : 0));
        table_unused = unused_views(written, op.nbool);
      }
      if (op.boolean) {
        if (split) {
          const Lit o = arg_lit(info, op.outs[0]);
          for (int v = 1; v <= op.nbool; ++v)
            if (sc->constant(node_of(o)) || !sc->depends_on(node_of(o), static_cast<uint32_t>(v)))
              rep.unused_views.push_back(v);
          if (check_split && full && rep.unused_views != table_unused)
            throw std::runtime_error("split check: read views that don't matter differ in " + op.name);
        } else {
          rep.unused_views = table_unused;
        }
        if (!rep.unused_views.empty()) rep.errors["unused_view"] = list_json(rep.unused_views);
      }
      rep.times.structure += now() - td;
    }
    if (op.boolean && record && full) {
      double tg = now();
      Recorded& r = recorded_[op.name];
      r.group = groups_of(r.table, op.nbool);
      rep.times.groups = now() - tg;
    }
    if (measure_executions && op.boolean && record && full && !in_registered_reach(op.name))
      measure_table_executions(op, rep);
    if (!registry_only) {
      double to = now();
      check_order(op, info, rep);
      rep.times.order = now() - to;
      double tr = now();
      rep.how = split ? "split" : (how == "auto" && I > 20) ? "sat" : "tt";
      if (rep.how == "sat" && !record) update_hierarchy(index, info);
      std::vector<uint64_t> keys;
      if (split) {
        keys = sc->keys;
        if (check_split) compare_split(index, op, info, t, words, keys, rep);
      } else {
        keys = rep.how == "sat" ? hier_->check_sat(index, rep.stats, 4) : keys_of(op, info, t, words);
      }
      find_redundant(op, info, keys, rep);
      rep.times.redundant = now() - tr;
    } else {
      // The registered operations only change matches and spellings; the
      // redundant-value rule still decides whether they're checked.
      std::vector<uint64_t> keys = split ? sc->keys : keys_of(op, info, t, words);
      find_redundant(op, info, keys, rep);
      rep.errors.erase("redundant");
    }
    const bool fixed_first = first_fix_only && (rep.literal_stmt >= 0 || !rep.unused_views.empty());
    // Matches and spellings need every value's function.
    if (rep.redundant_kind.empty() && !fixed_first && full && search_matches) {
      const std::set<int> dead(rep.dead.begin(), rep.dead.end());
      find_matches(op, info, std::move(t), dead, rep, nullptr, budgeted ? &budget : nullptr);
      if (measure_executions) rep.stats.emplace_back("matches_found", static_cast<double>(rep.matches.size()));
    }
    } catch (const BudgetExceeded&) {
      rep.errors["limits"] = "[\"budget\"," + std::to_string(budget_value(op, info, budget.at)) + "]";
      add_steps(rep, budget);
      if (record && op.boolean) forget(op.name);
      return rep;
    }
    if (budgeted) add_steps(rep, budget);
    return rep;
  }

  // The split check of an operation's values (split.hpp). Past the limits,
  // a limits error in rep instead: a part or group of values past them, or
  // an execution of an operation with no recorded function (one past them).
  std::unique_ptr<SplitCheck> split_check(const POp& op, const OpInfo& info, Report& rep) {
    const uint32_t I = static_cast<uint32_t>(info.inputs.size());
    std::vector<SplitNode> nodes(info.num_nodes);
    for (size_t j = 0; j < info.node_stmt.size(); ++j) {
      const PStmt& s = op.stmts[static_cast<size_t>(info.node_stmt[j])];
      SplitNode& node = nodes[I + 1 + j];
      for (const PArg& a : s.args) node.args.push_back(arg_lit(info, a));
      if (s.kind == "and") {
        node.chain = 1;
        node.is_and = true;
        continue;
      }
      auto it = recorded_.find(s.name);
      if (it == recorded_.end() || it->second.table.empty()) {
        rep.errors["limits"] = "\"execution\"";
        return nullptr;
      }
      const Recorded& r = it->second;
      node.all_views_matter = all_views_matter(s.name, r);
      if (s.args.size() == 2) {
        const uint64_t t = r.table[0] & 0xF;
        node.chain = t == 0x8 ? 1 : t == 0xE ? 2 : t == 0x6 ? 3 : t == 0x9 ? 4 : 0;
      }
    }
    auto eval = [&, I](uint32_t node, const std::vector<Lit>& args, size_t words, const SplitCheck::Word& word,
                    uint64_t* row) {
      const PStmt& s = op.stmts[static_cast<size_t>(info.node_stmt[node - I - 1])];
      const Recorded& callee = recorded_.at(s.name);
      if (callee.has_aig)
        evaluate_aig(callee, args, words, word, row);
      else
        lookup(callee.table, args, words, word, row);
    };
    auto sc = std::make_unique<SplitCheck>(std::move(nodes), I, eval);
    if (method == "split") sc->input_limit = input_limit;
    sc->run();
    if (sc->over_limits) rep.errors["limits"] = "\"split\"";
    rep.stats.emplace_back("split_parts", static_cast<double>(sc->parts));
    rep.stats.emplace_back("split_part_max_leaves", static_cast<double>(sc->parts_max_leaves));
    rep.stats.emplace_back("split_groups", static_cast<double>(sc->groups));
    rep.stats.emplace_back("split_groups_fixed_form", static_cast<double>(sc->groups_fixed_form));
    rep.stats.emplace_back("split_group_max_leaves", static_cast<double>(sc->groups_max_leaves));
    return sc;
  }

  bool all_views_matter(const std::string& name, const Recorded& r) const {
    auto it = views_matter_.find(name);
    if (it != views_matter_.end() && it->second.first == r.hash) return it->second.second;
    const POp& callee = p_.ops[static_cast<size_t>(index_.at(name))];
    const bool all = unused_views(r.table, callee.nbool).empty();
    views_matter_[name] = {r.hash, all};
    return all;
  }

  // check_split: the split check's classes of values against truth tables
  // over every input, or past 20 inputs SAT, up to 32.
  void compare_split(size_t index, const POp& op, const OpInfo& info, const std::vector<uint64_t>& t, size_t words,
                     const std::vector<uint64_t>& keys, Report& rep) {
    std::vector<uint64_t> other;
    if (info.inputs.size() <= 20) {
      other = tt_keys(info, t, words);
      ++split_compared_tt;
    } else if (info.inputs.size() <= 32) {
      update_hierarchy(index, info);
      other = hier_->check_sat(index, rep.stats, 4);
      ++split_compared_sat;
    } else {
      return;
    }
    // Equal classes both ways, with one phase between them per class.
    std::map<uint64_t, std::pair<uint64_t, uint64_t>> to, from;
    for (size_t n = 0; n < keys.size(); ++n) {
      const uint64_t phase = (keys[n] ^ other[n]) & 1;
      const auto i = to.try_emplace(keys[n] >> 1, other[n] >> 1, phase).first;
      const auto j = from.try_emplace(other[n] >> 1, keys[n] >> 1, phase).first;
      if (i->second != std::make_pair(other[n] >> 1, phase) || j->second != std::make_pair(keys[n] >> 1, phase))
        throw std::runtime_error("split check: values' classes differ in " + op.name + " at node " + std::to_string(n));
    }
  }

  // An operation's boolean values for the methods (methods.hpp).
  MethodGraph method_graph(const POp& op, const OpInfo& info) const {
    MethodGraph g;
    g.inputs = static_cast<uint32_t>(info.inputs.size());
    g.views = static_cast<uint32_t>(op.nbool);
    for (int k : info.node_stmt) {
      const PStmt& s = op.stmts[static_cast<size_t>(k)];
      MethodGraph::Node n;
      for (const PArg& a : s.args) n.args.push_back(arg_lit(info, a));
      if (s.kind == "call") {
        if (s.args.size() > 64) throw std::runtime_error("methods: an execution of more than 64 views");
        n.is_and = false;
        const Recorded& r = recorded_.at(s.name);
        if (r.diagram) {
          n.diagram = r.diagram.get();
        } else if (s.args.size() > 6) {
          n.big_table = &r.table;
          n.diagram = diagram_of_table(r, static_cast<uint32_t>(s.args.size()));
        } else {
          n.table = r.table[0];
          if (s.args.size() < 6) n.table &= (1ULL << (1u << s.args.size())) - 1;
        }
      }
      g.nodes.push_back(std::move(n));
    }
    g.out = op.boolean ? arg_lit(info, op.outs[0]) : 0;
    return g;
  }

  // A recorded table's diagram: the last view asked first.
  static const RecordedDiagram* diagram_of_table(const Recorded& r, uint32_t views) {
    if (!r.table_diagram) {
      auto rd = std::make_shared<RecordedDiagram>();
      rd->dd = Diagram(views);
      std::function<Diagram::Node(uint64_t, uint32_t)> go = [&](uint64_t from, uint32_t i) -> Diagram::Node {
        if (i == 0) return ((r.table[from >> 6] >> (from & 63)) & 1) ? Diagram::kTrue : Diagram::kFalse;
        const uint64_t half = uint64_t{1} << (i - 1);
        const Diagram::Node lo = go(from, i - 1), hi = go(from + half, i - 1);
        return rd->dd.make(views - i, lo, hi);
      };
      rd->root = go(0, views);
      for (uint32_t l = 0; l < views; ++l) rd->view_of_level.push_back(views - 1 - l);
      r.table_diagram = rd;
    }
    return r.table_diagram.get();
  }

  // DLP 58's budget, in steps (StepBudget), for each value operation past
  // the old limits (`--step_budget`; 0 is no budget).
  uint64_t step_budget = 1'000'000'000ULL;

  // The order of the boolean inputs for BDDs (a level per input, from 1):
  // as first reached depth-first from each value no boolean statement reads,
  // in statement order, through each statement's values in written order.
  std::vector<uint32_t> input_order(const POp& op, const OpInfo& info) const {
    const uint32_t I = static_cast<uint32_t>(info.inputs.size());
    std::vector<uint32_t> level(I + 1, UINT32_MAX);
    uint32_t next = 0;
    std::set<int> read, visited;
    for (const PStmt& s : op.stmts)
      if (is_boolean_statement(s.kind))
        for (const PArg& a : s.args)
          if (!a.is_literal()) read.insert(info.resolve(a.id));
    std::function<void(int)> visit = [&](int v) {
      v = info.resolve(v);
      if (!visited.insert(v).second) return;
      auto in = info.input_number.find(v);
      if (in != info.input_number.end()) {
        level[static_cast<uint32_t>(in->second)] = next++;
        return;
      }
      const OpInfo::Value& val = info.values.at(v);
      if (val.stmt < 0) return;
      const PStmt& s = op.stmts[static_cast<size_t>(val.stmt)];
      if (!is_boolean_statement(s.kind)) return;
      for (const PArg& a : s.args)
        if (!a.is_literal()) visit(a.id);
    };
    for (const PStmt& s : op.stmts)
      if (is_boolean_statement(s.kind) && !read.count(s.ids[0])) visit(s.ids[0]);
    // Inputs no boolean statement reads come last.
    for (uint32_t i = 1; i <= I; ++i)
      if (level[i] == UINT32_MAX) level[i] = next++;
    return level;
  }

  // Records a boolean operation checked with BDDs: its written view's
  // diagram, and the interchangeable views from it.
  void record_bdd(const POp& op, const OpInfo& info, BddMethod& bm) {
    if (!op.boolean) {
      record_op(op, info, {}, 0);
      return;
    }
    auto rd = std::make_shared<RecordedDiagram>(bm.record());
    Recorded& r = recorded_[op.name];
    r.aig.clear();
    r.has_aig = false;
    r.table.clear();
    r.table_diagram.reset();
    r.hash = rd->dd.hash(rd->root);
    r.diagram = rd;
    r.group = diagram_groups(*rd, op.nbool, bm);
    update_hierarchy(index_.at(op.name), info);
  }

  // Interchangeable views of a recorded diagram: swapping views i and j
  // leaves it the same when it's the same with i false and j true as with
  // i true and j false.
  static std::vector<int> diagram_groups(RecordedDiagram& rd, int views, MethodBase& dm) {
    std::vector<uint32_t> level_of(static_cast<size_t>(views), 0);
    for (uint32_t l = 0; l < rd.view_of_level.size(); ++l) level_of[rd.view_of_level[l]] = l;
    std::vector<int> parent(static_cast<size_t>(views));
    std::iota(parent.begin(), parent.end(), 0);
    std::function<int(int)> find = [&](int x) {
      int& p = parent[static_cast<size_t>(x)];
      return p == x ? x : p = find(p);
    };
    for (int i = 0; i < views; ++i)
      for (int j = i + 1; j < views; ++j) {
        if (find(i) == find(j) || !dm.may_be_interchangeable(static_cast<uint32_t>(i), static_cast<uint32_t>(j))) continue;
        const uint32_t li = level_of[static_cast<size_t>(i)], lj = level_of[static_cast<size_t>(j)];
        if (rd.dd.restrict2(rd.root, li, false, lj, true) == rd.dd.restrict2(rd.root, li, true, lj, false))
          parent[static_cast<size_t>(find(j))] = find(i);
      }
    std::vector<int> label(static_cast<size_t>(views));
    for (int v = 0; v < views; ++v) label[static_cast<size_t>(v)] = find(v);
    return label;
  }

  // An execution of an operation that records a decision diagram, over
  // the caller's words: each node's word from its children's, children
  // first (nodes are made after their children).
  template <typename Word>
  static void evaluate_diagram(const RecordedDiagram& rd, const std::vector<Lit>& args, size_t words, Word word,
                               uint64_t* row) {
    std::vector<Diagram::Node> nodes;
    {
      std::vector<char> seen(rd.dd.size() + 2, 0);
      std::vector<Diagram::Node> stack{rd.root};
      while (!stack.empty()) {
        const Diagram::Node n = stack.back();
        stack.pop_back();
        if (Diagram::terminal(n) || seen[n]) continue;
        seen[n] = 1;
        nodes.push_back(n);
        stack.push_back(rd.dd.lo(n));
        stack.push_back(rd.dd.hi(n));
      }
      std::sort(nodes.begin(), nodes.end());
    }
    std::vector<uint32_t> at(rd.dd.size() + 2, 0);
    for (size_t k = 0; k < nodes.size(); ++k) at[nodes[k]] = static_cast<uint32_t>(k);
    std::vector<uint64_t> v(nodes.size());
    auto get = [&](Diagram::Node n) { return n == Diagram::kTrue ? ~0ULL : n == Diagram::kFalse ? 0ULL : v[at[n]]; };
    for (size_t w = 0; w < words; ++w) {
      for (size_t k = 0; k < nodes.size(); ++k) {
        const Diagram::Node n = nodes[k];
        const uint64_t x = word(args[rd.view_of_level[rd.dd.level(n)]], w);
        v[k] = (x & get(rd.dd.hi(n))) | (~x & get(rd.dd.lo(n)));
      }
      row[w] = get(rd.root);
    }
  }

  // check() for a boolean operation with a method other than truth tables
  // over every input. It records nothing: no operation executes it.
  static void add_steps(Report& rep, const StepBudget& budget) {
    rep.stats.emplace_back("steps", static_cast<double>(budget.used));
    rep.stats.emplace_back("steps_bdd", static_cast<double>(budget.by_kind[StepBudget::kBdd]));
    rep.stats.emplace_back("steps_search", static_cast<double>(budget.by_kind[StepBudget::kSearch]));
    rep.stats.emplace_back("steps_sample", static_cast<double>(budget.by_kind[StepBudget::kSample]));
    rep.stats.emplace_back("steps_node", static_cast<double>(budget.by_kind[StepBudget::kNode]));
  }

  // The statement whose value the budget's work was for, as its value.
  static int budget_value(const POp& op, const OpInfo& info, Lit at) {
    int value = 0;
    for (const PStmt& st : op.stmts)
      if (is_boolean_statement(st.kind) && node_of(info.lit.at(st.ids[0])) == node_of(at) &&
          (st.kind != "not" || info.lit.at(st.ids[0]) == at)) {
        value = st.ids[0];
        if (st.kind != "not") break;
      }
    return value;
  }

  // With may_fall_back, a value operation within the old limits that goes
  // over the budget sets fell_back instead of getting the error.
  Report check_with_method(const POp& op, const OpInfo& info, bool record, Report& rep, const std::string& method,
                           bool may_fall_back, bool& fell_back) {
    const MethodGraph g = method_graph(op, info);
    const uint32_t I = g.inputs;
    rep.how = method;
    // DLP 58's rule counts its BDDs' and its search's steps.
    const bool rule = this->method == "auto";
    StepBudget budget;
    if (rule && step_budget) budget.limit = step_budget;
    std::unique_ptr<MethodBase> m;
    std::unique_ptr<SplitCheck> sc;
    const double t1 = now();
    try {
      if (method == "chunk") {
        m = std::make_unique<ChunkMethod>(g, chunk_inputs);
      } else if (method == "bdd") {
        m = rule ? std::make_unique<BddMethod>(g, input_order(op, info), bdd_node_limit)
                 : std::make_unique<BddMethod>(g, bdd_order, bdd_node_limit);
      } else if (method == "sat") {
        m = std::make_unique<SatMethod>(g);
      } else if (method == "split") {
        sc = split_check(op, info, rep);
        if (!sc || rep.errors.count("limits")) return rep;
        m = std::make_unique<SplitMethod>(g, *sc);
      } else {
        throw std::runtime_error("unknown method " + method);
      }
      if (rule) m->budget = &budget;
      m->run();
      rep.times.tables = now() - t1 + (method == "split" ? rep.times.split : 0);
      rep.times.split = 0;
      const double tu = now();
      if (op.boolean) m->find_unused();
      rep.times.structure += now() - tu;
      rep.unused_views = m->unused_views;
      if (!rep.unused_views.empty()) rep.errors["unused_view"] = list_json(rep.unused_views);
      rep.dead = dead_statements(op, info);
      if (!rep.dead.empty()) rep.errors["dead"] = list_json(rep.dead);
      const double to = now();
      check_order(op, info, rep);
      rep.times.order = now() - to;
      const double tr = now();
      find_redundant(op, info, m->keys, rep);
      rep.times.redundant = now() - tr;
      const bool fixed_first = first_fix_only && (rep.literal_stmt >= 0 || !rep.unused_views.empty());
      if (rep.redundant_kind.empty() && !fixed_first && search_matches) {
        const std::set<int> dead(rep.dead.begin(), rep.dead.end());
        find_matches(op, info, {}, dead, rep, m.get(), rule ? &budget : nullptr);
      }
    } catch (const BddLimit&) {
      rep.errors["limits"] = "\"bdd nodes\"";
      return rep;
    } catch (const BudgetExceeded&) {
      if (may_fall_back) {
        fell_back = true;
        return rep;
      }
      rep.errors["limits"] = "[\"budget\"," + std::to_string(budget_value(op, info, budget.at)) + "]";
      add_steps(rep, budget);
      if (record) {
        if (op.boolean)
          forget(op.name);
        else
          record_op(op, info, {}, 0);
      }
      return rep;
    }
    add_steps(rep, budget);
    if (record) {
      const double tg = now();
      auto* b = dynamic_cast<BddMethod*>(m.get());
      if (rule && b)
        record_bdd(op, info, *b);
      else if (op.boolean)
        forget(op.name);
      else
        record_op(op, info, {}, 0);
      rep.times.groups = now() - tg;
    }
    rep.stats.emplace_back("undecided", static_cast<double>(m->undecided));
    rep.stats.emplace_back("matches_found", static_cast<double>(rep.matches.size()));
    if (auto* b = dynamic_cast<BddMethod*>(m.get())) {
      rep.stats.emplace_back("bdd_nodes", static_cast<double>(b->nodes()));
      rep.stats.emplace_back("bdd_bytes", static_cast<double>(b->memory_bytes()));
    }
    if (auto* st = dynamic_cast<SatMethod*>(m.get())) rep.stats.emplace_back("sat_calls", static_cast<double>(st->sat_calls));
    if (measure_executions) {
      // An execution refers to the written view's OBDD, or else to the
      // operation's statements written out.
      Rng rng(3);
      const uint64_t mask = I >= 64 ? ~0ULL : ((uint64_t{1} << I) - 1);
      std::vector<uint64_t> minterms(kExecutionSamples);
      for (uint64_t& x : minterms) x = rng.next() & mask;
      if (auto* b = dynamic_cast<BddMethod*>(m.get())) {
        rep.stats.emplace_back("exec_record_bytes", static_cast<double>(b->out_nodes() * 12));
        const double te = now();
        uint64_t ones = 0;
        for (uint64_t x : minterms) ones += b->evaluate_out(x);
        rep.stats.emplace_back("exec_ns_per_assignment", (now() - te) * 1e9 / kExecutionSamples);
        sink_ ^= ones;
      } else {
        const std::vector<uint32_t> cone = g.cone({g.out});
        rep.stats.emplace_back("exec_record_bytes", static_cast<double>(cone.size() * 8));
        const double te = now();
        std::vector<uint64_t> v(g.num_nodes(), 0);
        uint64_t a[64], acc = 0;
        for (size_t w = 0; w < kExecutionSamples / 64; ++w) {
          for (uint32_t x : cone) {
            if (x == 0) {
              v[x] = 0;
            } else if (x <= I) {
              uint64_t bits = 0;
              for (int k = 0; k < 64; ++k) bits |= ((minterms[w * 64 + static_cast<size_t>(k)] >> (x - 1)) & 1) << k;
              v[x] = bits;
            } else {
              const MethodGraph::Node& node = g.node(x);
              for (size_t i = 0; i < node.args.size(); ++i) a[i] = v[node_of(node.args[i])] ^ (is_compl(node.args[i]) ? ~0ULL : 0);
              v[x] = MethodGraph::word(node, a);
            }
          }
          acc ^= v[node_of(g.out)];
        }
        rep.stats.emplace_back("exec_ns_per_assignment", (now() - te) * 1e9 / kExecutionSamples);
        sink_ ^= acc;
      }
    }
    return rep;
  }

  static constexpr size_t kExecutionSamples = 1 << 16;
  // Keeps the timed evaluations from being optimized away.
  mutable uint64_t sink_ = 0;

  // measure_executions for truth tables: an execution refers to the
  // recorded table and looks up each input assignment in it.
  void measure_table_executions(const POp& op, Report& rep) const {
    const Recorded& r = recorded_.at(op.name);
    rep.stats.emplace_back("exec_record_bytes", static_cast<double>(r.table.size() * 8));
    Rng rng(3);
    const uint64_t mask = op.nbool >= 64 ? ~0ULL : ((uint64_t{1} << op.nbool) - 1);
    std::vector<uint64_t> minterms(kExecutionSamples);
    for (uint64_t& x : minterms) x = rng.next() & mask;
    const double te = now();
    uint64_t ones = 0;
    for (uint64_t x : minterms) ones += (r.table[x >> 6] >> (x & 63)) & 1;
    rep.stats.emplace_back("exec_ns_per_assignment", (now() - te) * 1e9 / kExecutionSamples);
    sink_ ^= ones;
  }

  // Whether one of the operation's boolean values never changes.
  bool has_constant_value(size_t index) const {
    const POp& op = p_.ops[index];
    const OpInfo info = analyze(op);
    size_t words = 1;
    const std::vector<uint64_t> t = tables(op, info, words);
    const std::vector<uint64_t> keys = tt_keys(info, t, words);
    for (const PStmt& s : op.stmts)
      if (is_boolean_statement(s.kind) && (keys[node_of(info.lit.at(s.ids[0]))] >> 1) == (keys[0] >> 1)) return true;
    return false;
  }

  // Boolean statements whose value doesn't reach a written view or a
  // statement that isn't boolean (DLP 58), in statement order.
  static std::vector<int> dead_statements(const POp& op, const OpInfo& info) {
    std::set<int> live;
    std::vector<int> stack;
    auto reach = [&](const PArg& a) {
      if (a.is_literal()) return;
      const int v = info.resolve(a.id);
      if (info.values.at(v).stmt >= 0 && live.insert(v).second) stack.push_back(v);
    };
    for (const PArg& a : op.outs) reach(a);
    for (const PStmt& s : op.stmts)
      if (!is_boolean_statement(s.kind) && s.kind != "copy")
        for (const PArg& a : s.args) reach(a);
    while (!stack.empty()) {
      const int v = stack.back();
      stack.pop_back();
      for (const PArg& a : op.stmts[static_cast<size_t>(info.values.at(v).stmt)].args) reach(a);
    }
    std::vector<int> dead;
    for (const PStmt& s : op.stmts)
      if (is_boolean_statement(s.kind) && !live.count(s.ids[0])) dead.push_back(s.ids[0]);
    return dead;
  }

  // Read views a boolean operation's written view doesn't depend on, from 1.
  static std::vector<int> unused_views(const std::vector<uint64_t>& table, int views) {
    static const uint64_t kVar[6] = {0xAAAAAAAAAAAAAAAAULL, 0xCCCCCCCCCCCCCCCCULL, 0xF0F0F0F0F0F0F0F0ULL,
                                     0xFF00FF00FF00FF00ULL, 0xFFFF0000FFFF0000ULL, 0xFFFFFFFF00000000ULL};
    const uint64_t valid = views >= 6 ? ~0ULL : ((1ULL << (1u << views)) - 1);
    std::vector<int> out;
    for (int i = 0; i < views; ++i) {
      bool matters = false;
      for (size_t w = 0; w < table.size() && !matters; ++w) {
        if (i < 6) {
          matters = ((table[w] ^ (table[w] >> (1 << i))) & ~kVar[i] & valid) != 0;
        } else {
          const size_t b = size_t{1} << (i - 6);
          matters = !(w & b) && table[w] != table[w | b];
        }
      }
      if (!matters) out.push_back(i + 1);
    }
    return out;
  }

  static std::string list_json(const std::vector<int>& values) {
    std::string out = "[";
    for (size_t i = 0; i < values.size(); ++i) out += (i ? "," : "") + std::to_string(values[i]);
    return out + "]";
  }

  // Records the registered operations, and what they execute, before any
  // operation is checked: every operation's matches need them, wherever
  // they're defined.
  void record_registered() {
    std::set<std::string> needed;
    std::vector<std::string> stack(p_.registered.begin(), p_.registered.end());
    while (!stack.empty()) {
      const std::string n = stack.back();
      stack.pop_back();
      if (!needed.insert(n).second) continue;
      for (const PStmt& s : p_.ops[static_cast<size_t>(index_.at(n))].stmts)
        if (s.kind == "call") stack.push_back(s.name);
    }
    for (size_t i = 0; i < p_.ops.size(); ++i) {
      const POp& op = p_.ops[i];
      if (!needed.count(op.name) || reaches_cycle_[i]) continue;
      registered_reach_.insert(op.name);
      const OpInfo info = analyze(op);
      size_t words = 1;
      const std::vector<uint64_t> t = tables(op, info, words);
      record_op(op, info, t, words);
      recorded_[op.name].group = groups_of(recorded_[op.name].table, op.nbool);
      update_hierarchy(i, info);
    }
  }

  // Writes the operation out as an and-inverter graph (see Recorded::aig),
  // giving up past the size where a table lookup costs less.
  void record_aig(const POp& op, const OpInfo& info, Recorded& r) const {
    const size_t limit = op.nbool <= 6 ? (size_t{1} << op.nbool) : 16 * static_cast<size_t>(op.nbool);
    r.aig.clear();
    r.has_aig = false;
    std::map<std::pair<Lit, Lit>, Lit> strash;
    const uint32_t first = static_cast<uint32_t>(op.nbool) + 1;
    auto land = [&](Lit a, Lit b) -> Lit {
      if (a > b) std::swap(a, b);
      if (a == 0 || a == (b ^ 1)) return 0;
      if (a == 1 || a == b) return b;
      auto it = strash.find({a, b});
      if (it != strash.end()) return it->second;
      const Lit l = make_lit(first + static_cast<uint32_t>(r.aig.size()));
      r.aig.push_back({a, b});
      strash[{a, b}] = l;
      return l;
    };
    std::unordered_map<int, Lit> value;
    for (int v = 1; v <= op.nbool; ++v) value[v] = make_lit(static_cast<uint32_t>(v));
    auto get = [&](const PArg& a) { return a.is_literal() ? Lit{a.literal == "T" ? 1u : 0u} : value.at(info.resolve(a.id)); };
    for (const PStmt& s : op.stmts) {
      if (r.aig.size() > limit) return;
      if (s.kind == "and") {
        value[s.ids[0]] = land(get(s.args[0]), get(s.args[1]));
      } else if (s.kind == "not") {
        value[s.ids[0]] = get(s.args[0]) ^ 1;
      } else if (s.kind == "call") {
        const Recorded& callee = recorded_.at(s.name);
        if (!callee.has_aig) return;
        std::vector<Lit> sub{0};
        for (const PArg& a : s.args) sub.push_back(get(a));
        auto map = [&](Lit l) { return sub[node_of(l)] ^ (is_compl(l) ? 1u : 0u); };
        for (const auto& [a, b] : callee.aig) sub.push_back(land(map(a), map(b)));
        value[s.ids[0]] = map(callee.aig_out);
      }
    }
    if (r.aig.size() > limit) return;
    r.aig_out = get(op.outs[0]);
    r.has_aig = true;
  }

  void record_op(const POp& op, const OpInfo& info, const std::vector<uint64_t>& t, size_t words) {
    Recorded& r = recorded_[op.name];
    r.table_diagram.reset();
    r.diagram.reset();
    if (op.boolean) {
      const uint32_t I = static_cast<uint32_t>(info.inputs.size());
      const size_t rwords = I <= 6 ? 1 : (size_t{1} << (I - 6));
      r.table.assign(rwords, 0);
      const Lit o = arg_lit(info, op.outs[0]);
      for (size_t w = 0; w < words; ++w) r.table[w] = t[size_t{node_of(o)} * words + w] ^ (is_compl(o) ? ~0ULL : 0);
      if (I < 6) r.table[0] &= (1ULL << (1u << I)) - 1;
      uint64_t h = 0x77;
      for (uint64_t w : r.table) h = mix64(h ^ w);
      r.hash = h;
      record_aig(op, info, r);
    } else {
      r.out_boolean.clear();
      uint64_t h = 0x55;
      for (const PArg& a : op.outs) {
        const bool b = a.is_literal() ? a.literal[0] != '#' : info.values.at(info.resolve(a.id)).kind == 'b';
        r.out_boolean.push_back(b);
        h = mix64(h ^ static_cast<uint64_t>(b));
      }
      r.hash = h;
    }
  }

  void check_order(const POp& op, const OpInfo& info, Report& rep) const {
    Ranker ranker{op, info, {}};
    for (const PStmt& s : op.stmts) {
      if (s.kind != "and" && s.kind != "call") continue;
      const std::vector<int> group = statement_groups(s);
      bool bad = false;
      for (size_t i = 0; i < s.args.size() && !bad; ++i)
        for (size_t j = i + 1; j < s.args.size() && !bad; ++j)
          if (group[i] == group[j] && ranker.compare(s.args[i], s.args[j]) > 0) bad = true;
      if (bad) {
        rep.errors["order_arguments"] = std::to_string(s.ids[0]);
        break;
      }
    }
    const std::vector<int> order = canonical_order(op, info);
    std::vector<int> actual;
    for (size_t k = 0; k < op.stmts.size(); ++k)
      if (op.stmts[k].kind != "copy") actual.push_back(static_cast<int>(k));
    for (size_t k = 0; k < std::max(order.size(), actual.size()); ++k)
      if (k >= order.size() || k >= actual.size() || order[k] != actual[k]) {
        rep.errors["order_statements"] = std::to_string(k);
        break;
      }
  }

  // Each node's class up to complement, in the high bits, and its phase.
  // Each node's value: the read view for an input, the statement's first
  // value for the others, 0 for the constant.
  static std::vector<int> node_values(const POp& op, const OpInfo& info) {
    std::vector<int> out(info.num_nodes, 0);
    for (size_t i = 0; i < info.inputs.size(); ++i) out[i + 1] = info.inputs[i];
    for (size_t n = 0; n < info.node_stmt.size(); ++n)
      out[info.inputs.size() + 1 + n] = op.stmts[static_cast<size_t>(info.node_stmt[n])].ids[0];
    return out;
  }

  // tt_keys, with each value's key kept while `reuse_values` holds.
  std::vector<uint64_t> keys_of(const POp& op, const OpInfo& info, const std::vector<uint64_t>& t, size_t words) {
    if (!reuse_values || reuse_name_ != op.name) return tt_keys(info, t, words);
    const std::vector<int> value = node_values(op, info);
    bool all = true;
    for (uint32_t n = 1; n < info.num_nodes && all; ++n) all = key_of_value_.count(value[n]) > 0;
    if (!all) {
      std::vector<uint64_t> keys = tt_keys(info, t, words);
      for (uint32_t n = 1; n < info.num_nodes; ++n) key_of_value_[value[n]] = keys[n];
      return keys;
    }
    std::vector<uint64_t> keys = tt_keys_of_constant(info, t, words);
    for (uint32_t n = 1; n < info.num_nodes; ++n) keys[n] = key_of_value_.at(value[n]);
    return keys;
  }

  // tt_keys for node 0 alone, the rest left 0.
  static std::vector<uint64_t> tt_keys_of_constant(const OpInfo& info, const std::vector<uint64_t>& t, size_t words) {
    std::vector<uint64_t> keys(info.num_nodes, 0);
    OpInfo one;
    one.num_nodes = 1;
    one.inputs = info.inputs;
    keys[0] = tt_keys(one, t, words)[0];
    return keys;
  }

  static std::vector<uint64_t> tt_keys(const OpInfo& info, const std::vector<uint64_t>& t, size_t words) {
    std::vector<uint64_t> keys(info.num_nodes);
    for (uint32_t n = 0; n < info.num_nodes; ++n) {
      const uint64_t* row = &t[size_t{n} * words];
      const uint64_t phase = row[0] & 1;
      uint64_t h = 0x77;
      for (size_t w = 0; w < words; ++w) h = mix64(h ^ (row[w] ^ (phase ? ~0ULL : 0)));
      keys[n] = (h & ~1ULL) | phase;
    }
    // Truth tables of up to six inputs only use the low bits of a word.
    if (info.inputs.size() < 6) {
      const uint64_t mask = (1ULL << (1u << info.inputs.size())) - 1;
      for (uint32_t n = 0; n < info.num_nodes; ++n) {
        const uint64_t row = t[n] & mask, phase = row & 1;
        keys[n] = (mix64(0x77 ^ ((row ^ (phase ? mask : 0)))) & ~1ULL) | phase;
      }
    }
    return keys;
  }

  // An operation's boolean statements as a hierarchy operation for the SAT
  // check (hier.hpp): its boolean inputs as views, `not` as complemented
  // literals, and its recorded table.
  void update_hierarchy(size_t index, const OpInfo& info) {
    const POp& op = p_.ops[index];
    HOp h;
    h.name = op.name;
    h.views = static_cast<uint32_t>(info.inputs.size());
    h.num_values = info.num_nodes;
    for (int k : info.node_stmt) {
      const PStmt& s = op.stmts[static_cast<size_t>(k)];
      HStatement hs;
      if (s.kind == "and") {
        hs.a = arg_lit(info, s.args[0]);
        hs.b = arg_lit(info, s.args[1]);
      } else {
        hs.is_exec = true;
        hs.outputs = 1;
        hs.callee = index_.at(s.name);
        for (const PArg& a : s.args) hs.args.push_back(arg_lit(info, a));
      }
      h.statements.push_back(std::move(hs));
    }
    for (const PArg& a : op.outs)
      if (a.is_literal() ? a.literal[0] != '#' : info.values.at(info.resolve(a.id)).kind == 'b')
        h.outputs.push_back(arg_lit(info, a));
    auto it = recorded_.find(op.name);
    if (op.boolean && it != recorded_.end()) h.out_tables = {it->second.table};
    hier_->mutable_op(index) = std::move(h);
  }

  void find_redundant(const POp& op, const OpInfo& info, const std::vector<uint64_t>& keys, Report& rep) const {
    auto key = [&](Lit l) { return keys[node_of(l)] ^ (is_compl(l) ? 1u : 0u); };
    // The first value of each class in each phase: -1 for false.
    std::map<uint64_t, std::array<int, 2>> first;
    auto note = [&](uint64_t k, int v) {
      auto& slot = first.try_emplace(k >> 1, std::array<int, 2>{0, 0}).first->second;
      if (slot[k & 1] == 0) slot[k & 1] = v;
    };
    note(keys[0], -1);
    for (int v : info.inputs) note(key(info.lit.at(v)), v);
    for (const PStmt& s : op.stmts) {
      if (!is_boolean_statement(s.kind)) continue;
      const int v = s.ids[0];
      const uint64_t k = key(info.lit.at(v));
      auto it = first.find(k >> 1);
      if (it != first.end()) {
        const std::array<int, 2>& slot = it->second;
        std::string kind;
        int other = 0;
        if (slot[k & 1] == -1 || slot[(k & 1) ^ 1] == -1) {
          kind = "constant";
          other = slot[k & 1] == -1 ? 0 : 1;  // 0: false, 1: true
        } else if (slot[k & 1] != 0) {
          kind = "same";
          other = slot[k & 1];
        } else if (!(s.kind == "not" && info.resolve(s.args[0].id) == slot[(k & 1) ^ 1])) {
          kind = "opposite";
          other = slot[(k & 1) ^ 1];
        }
        if (!kind.empty()) {
          // An opposite value that's a `not` of another value waits: that
          // value is redundant itself, fixed in this batch. A value that
          // never changes is an error the fix loop doesn't fix.
          if (!rep.merges.empty() && ((kind == "opposite" && s.kind == "not") || kind == "constant")) return;
          if (rep.redundant_kind.empty()) {
            rep.redundant_kind = kind;
            rep.redundant_value = v;
            rep.redundant_other = other;
            rep.errors["redundant"] = "[" + std::to_string(v) + ",\"" + kind + "\"," +
                                      (kind == "constant" ? (other ? "\"T\"" : "\"F\"") : std::to_string(other)) + "]";
          }
          if (kind == "constant") return;
          Report::Merge m;
          m.value = v;
          m.opposite = kind == "opposite";
          m.with.id = other;
          rep.merges.push_back(m);
          // An opposite value stays, as the `not` of the earlier one.
          if (kind == "opposite") note(k, v);
          continue;
        }
      }
      note(k, v);
    }
  }

  // A registered operation's key (DLP 60): the fewest `and`s computing its
  // function, then its number of read views, then its truth table as a
  // number. Only operations of up to four read views can be registered.
  std::tuple<int, int, uint64_t> key_of(const std::string& name) const {
    const POp& op = p_.ops[static_cast<size_t>(index_.at(name))];
    const uint64_t table = recorded_.at(name).table[0];
    return {op.nbool <= 4 ? min_ands(table, op.nbool) : std::numeric_limits<int>::max(), op.nbool, table};
  }

  // The registered operations an operation follows, in their order: `and`
  // and `not`, then the others by key; a registered operation's own
  // definition follows only the ones with smaller keys (DLP 60).
  std::vector<std::string> follows(const POp& op) const {
    std::vector<std::pair<std::tuple<int, int, uint64_t>, std::string>> keyed;
    for (const std::string& name : p_.registered)
      // One in or executing a cycle has no function to match (DLP 9).
      if (!reaches_cycle_[static_cast<size_t>(index_.at(name))]) keyed.push_back({key_of(name), name});
    std::sort(keyed.begin(), keyed.end());
    const bool registered = is_registered(op.name) && recorded_.count(op.name);
    std::vector<std::string> out{"and", "not"};
    for (const auto& [key, name] : keyed) {
      if (registered && key >= key_of(op.name)) break;
      out.push_back(name);
    }
    return out;
  }

  std::vector<int> groups_of_name(const std::string& name) const {
    if (name == "and") return {0, 0};
    if (name == "not") return {0};
    return recorded_.at(name).group;
  }

  Registered registered_of(const std::string& name) const {
    if (name == "and") return {name, 2, 0x8};
    if (name == "not") return {name, 1, 0x1};
    const POp& r = p_.ops[static_cast<size_t>(index_.at(name))];
    return {name, static_cast<uint32_t>(r.nbool), recorded_.at(name).table[0]};
  }

  void find_matches(const POp& op, const OpInfo& info, std::vector<uint64_t> t, const std::set<int>& dead,
                    Report& rep, MatchOracle* oracle = nullptr, StepBudget* budget = nullptr) {
    const std::vector<std::string> order = follows(op);
    std::vector<Registered> registered;
    std::map<std::string, int> nodes;
    for (const std::string& name : order) {
      registered.push_back(registered_of(name));
      nodes[name] = 0;
    }
    auto place = [&](const std::string& name) { return std::find(order.begin(), order.end(), name) - order.begin(); };
    // The graph the matcher sees: inputs, then a node per `and` or `call`.
    Aig g;
    g.num_inputs = static_cast<uint32_t>(info.inputs.size());
    g.fanin0.assign(info.num_nodes, 0);
    g.fanin1.assign(info.num_nodes, 0);
    std::vector<Statement> statements;
    std::vector<char> dead_flags;
    std::vector<std::pair<size_t, Lit>> late;
    std::unordered_map<Lit, int> value_of;
    for (int v : info.inputs) value_of[info.lit.at(v)] = v;
    for (const PStmt& s : op.stmts) {
      if (s.kind == "cmp" || s.kind == "run")
        for (int id : s.ids)
          if (info.values.at(id).kind == 'b') late.push_back({statements.size(), info.lit.at(id)});
      if (!is_boolean_statement(s.kind)) continue;
      Statement st;
      st.lit = info.lit.at(s.ids[0]);
      st.op = s.kind == "call" ? s.name : s.kind;
      if (s.kind == "call" && place(s.name) == static_cast<std::ptrdiff_t>(order.size())) st.op = "call:" + s.name;
      dead_flags.push_back(dead.count(s.ids[0]) > 0);
      for (const PArg& a : s.args) st.args.push_back(arg_lit(info, a));
      value_of.emplace(st.lit, s.ids[0]);
      statements.push_back(std::move(st));
    }
    // Statements read by an exit: written views and statements that aren't
    // boolean.
    for (const PStmt& s : op.stmts)
      if (s.kind == "cmp" || s.kind == "num" || s.kind == "run")
        for (const PArg& a : s.args)
          if (!a.is_literal() && info.values.at(info.resolve(a.id)).kind == 'b') g.outputs.push_back(arg_lit(info, a));
    for (const PArg& a : op.outs)
      if (!a.is_literal() && info.values.at(info.resolve(a.id)).kind == 'b') g.outputs.push_back(arg_lit(info, a));
    std::vector<uint32_t> support(info.num_nodes, 0);
    Ranker ranker{op, info, {}};
    auto value_arg = [&](Lit l) {
      PArg a;
      a.id = value_of.at(l);
      return a;
    };
    std::vector<Report::Found> matches, spellings;
    std::vector<uint64_t> hashes;
    // The kept hashes are of truth tables; an oracle's function ids aren't
    // those, so a check with an oracle keeps nothing.
    const bool reuse = reuse_values && reuse_name_ == op.name && !oracle;
    const std::vector<int> node_value = reuse ? node_values(op, info) : std::vector<int>{};
    if (reuse) {
      hashes.assign(2 * size_t{info.num_nodes} + 2, 0);
      for (uint32_t n = 1; n < info.num_nodes; ++n)
        for (uint32_t c = 0; c < 2; ++c) {
          auto it = hash_of_value_.find(2 * node_value[n] + static_cast<int>(c));
          if (it != hash_of_value_.end()) hashes[2 * size_t{n} + c] = it->second;
        }
    }
    bool focused = !changed_.empty();
    for (const PStmt& s : op.stmts)
      if (s.kind == "call" && added_.count(s.name)) focused = false;
    // The match search, then the spelling search, with the kept searches
    // when `use_cache`.
    const bool cached = reuse && reuse_search && !in_registered_reach(op.name);
    auto search = [&](bool use_cache, std::vector<uint64_t> tables, std::vector<Report::Found>& found_matches,
                      std::vector<Report::Found>& found_spellings, bool timed) {
      for (int pass = 0; pass < 2; ++pass) {
        if (pass == 0 && focused && !edit_matches_) continue;
        if (pass == 1 && first_fix_only && !found_matches.empty()) break;
        double tp = now();
        Matcher m(g, statements, registered);
        m.set_hashes(std::move(hashes));
        m.set_budget(budget);
        if (oracle)
          m.set_oracle(oracle);
        else
          m.set_tables(pass == 0 ? tables : std::move(tables), support);
        m.set_late_inputs(late);
        m.set_anchor("any");
        m.set_nodes(nodes);
        m.set_min_opposite_removed(3);
        m.set_spellings(pass == 1);
        m.set_matches(pass == 0);
        m.set_precedence(order, true);
        m.set_dead(dead_flags);
        if (focused) m.set_only(changed_);
        if (reuse) m.set_holds_cache(&holds_cache_, node_value);
        if (use_cache) m.set_search_cache(&search_cache_);
        Stats st;
        std::set<Match> found = m.run_resub(st);
        for (const Match& x : pass == 0 ? found : m.spelled()) {
          Report::Found f;
          f.value = value_of.at(x.value);
          f.op = x.op;
          if (pass == 0) {
            for (size_t i : m.match_statements(x)) f.removed_values.push_back(value_of.at(statements[i].lit));
            f.removed = f.removed_values.size();
          }
          for (Lit a : x.args) f.args.push_back(value_of.at(a));
          (pass == 0 ? found_matches : found_spellings).push_back(std::move(f));
        }
        hashes = m.take_hashes();
        if (!timed) continue;
        for (auto& [k, v] : st) rep.stats.emplace_back((pass == 0 ? "match_" : "spell_") + k, v);
        (pass == 0 ? rep.times.matches : rep.times.spellings) = now() - tp;
      }
    };
    std::vector<uint64_t> tables_copy;
    if (cached && check_search) tables_copy = t;
    search(cached, std::move(t), matches, spellings, true);
    std::vector<Report::Found> full_matches, full_spellings;
    if (cached && check_search) search(false, std::move(tables_copy), full_matches, full_spellings, false);
    if (reuse)
      for (uint32_t n = 1; n < info.num_nodes; ++n)
        for (uint32_t c = 0; c < 2; ++c)
          if (2 * size_t{n} + c < hashes.size() && hashes[2 * size_t{n} + c])
            hash_of_value_[2 * node_value[n] + static_cast<int>(c)] = hashes[2 * size_t{n} + c];
    // Arguments in view order, each interchangeable group sorted by rank.
    auto canonical_args = [&](Report::Found& f) {
      const std::string name = f.op.rfind("not:", 0) == 0 ? f.op.substr(4) : f.op;
      const std::vector<int> group = groups_of_name(name);
      for (size_t i = 0; i < f.args.size(); ++i)
        for (size_t j = i + 1; j < f.args.size(); ++j)
          if (group[i] == group[j] && ranker.compare(value_arg(info.lit.at(f.args[i])), value_arg(info.lit.at(f.args[j]))) > 0)
            std::swap(f.args[i], f.args[j]);
    };
    auto position = [&](int v) { return info.values.at(v).stmt; };
    auto rank_less = [&](const std::vector<int>& a, const std::vector<int>& b) {
      for (size_t i = 0; i < std::min(a.size(), b.size()); ++i) {
        PArg x, y;
        x.id = a[i];
        y.id = b[i];
        const int r = ranker.compare(x, y);
        if (r != 0) return r < 0;
      }
      return a.size() < b.size();
    };
    for (Report::Found& f : matches) canonical_args(f);
    for (Report::Found& f : spellings) canonical_args(f);
    if (cached && check_search) {
      // The kept searches have to find exactly what searching again does.
      for (Report::Found& f : full_matches) canonical_args(f);
      for (Report::Found& f : full_spellings) canonical_args(f);
      auto same = [](std::vector<Report::Found> a, std::vector<Report::Found> b) {
        auto key = [](const Report::Found& f) {
          std::vector<int> removed = f.removed_values;
          std::sort(removed.begin(), removed.end());
          return std::make_tuple(f.value, f.op, f.args, removed);
        };
        auto less = [&](const Report::Found& x, const Report::Found& y) { return key(x) < key(y); };
        std::sort(a.begin(), a.end(), less);
        std::sort(b.begin(), b.end(), less);
        if (a.size() != b.size()) return false;
        for (size_t i = 0; i < a.size(); ++i)
          if (key(a[i]) != key(b[i])) return false;
        return true;
      };
      if (!same(matches, full_matches) || !same(spellings, full_spellings))
        throw std::runtime_error("kept search differs in " + op.name);
    }
    if (!matches.empty()) {
      auto name = [](const Report::Found& f) { return f.op.rfind("not:", 0) == 0 ? f.op.substr(4) : f.op; };
      auto better = [&](const Report::Found& a, const Report::Found& b) {
        if (a.removed != b.removed) return a.removed > b.removed;
        if (position(a.value) != position(b.value)) return position(a.value) < position(b.value);
        if (name(a) != name(b)) return place(name(a)) < place(name(b));
        return rank_less(a.args, b.args);
      };
      std::stable_sort(matches.begin(), matches.end(), better);
      rep.match = matches.front();
      rep.matches = matches;
      rep.has_match = true;
      rep.errors["match"] = found_json(rep.match, true);
    }
    // Spellings: a `call` of a registered operation with a spelling whose
    // key comes first.
    auto negations = [&](const std::vector<int>& args) {
      int n = 0;
      for (int a : args) {
        const OpInfo::Value& v = info.values.at(a);
        n += v.stmt >= 0 && op.stmts[static_cast<size_t>(v.stmt)].kind == "not";
      }
      return n;
    };
    auto key_less = [&](const std::string& ra, const std::vector<int>& aa, const std::string& rb, const std::vector<int>& ab) {
      const int na = negations(aa), nb = negations(ab);
      if (na != nb) return na < nb;
      if (place(ra) != place(rb)) return place(ra) < place(rb);
      return rank_less(aa, ab);
    };
    for (const PStmt& s : op.stmts) {
      // Every execution of a registered operation is a spelling, `and`
      // included. A `not` isn't respelled: a value that's the `not` of
      // another is written as that `not` (DLP 58's opposite values).
      const std::string name = s.kind == "call" ? s.name : s.kind;
      if (!is_boolean_statement(s.kind) || s.kind == "not" ||
          place(name) == static_cast<std::ptrdiff_t>(order.size()))
        continue;
      // An execution given a literal is DLP 58's error, not a spelling.
      if (std::any_of(s.args.begin(), s.args.end(), [](const PArg& a) { return a.is_literal(); })) continue;
      const int v = s.ids[0];
      Report::Found self;
      self.op = name;
      for (const PArg& a : s.args) self.args.push_back(info.resolve(a.id));
      canonical_args(self);
      const std::vector<int>& current = self.args;
      const Report::Found* best = nullptr;
      for (const Report::Found& f : spellings) {
        if (f.value != v || f.op.rfind("not:", 0) == 0) continue;
        if (!best || key_less(f.op, f.args, best->op, best->args)) best = &f;
      }
      if (best && !(best->op == name && best->args == current) && key_less(best->op, best->args, name, current)) {
        rep.spelling = *best;
        rep.has_spelling = true;
        rep.errors["spelling"] = found_json(rep.spelling, false);
        break;
      }
    }
  }

  static std::string found_json(const Report::Found& f, bool with_removed) {
    std::ostringstream o;
    o << "[" << f.value << ",\"" << f.op << "\",";
    if (with_removed) o << f.removed << ",";
    o << "[";
    for (size_t i = 0; i < f.args.size(); ++i) o << (i ? "," : "") << f.args[i];
    o << "]]";
    return o.str();
  }

  // Configuration rules for booleans.defcl (DLP 60): at most four read
  // views and one written view, and no two that compute the same thing.
  std::vector<std::string> check_registry() const {
    std::vector<std::string> out;
    // `and` and `not` are registered for every operation, before the rest.
    std::vector<std::string> all{"and", "not"};
    all.insert(all.end(), p_.registered.begin(), p_.registered.end());
    for (size_t i = 2; i < all.size(); ++i) {
      const POp& a = p_.ops[static_cast<size_t>(index_.at(all[i]))];
      if (!a.boolean || a.nbool > 4) out.push_back(a.name + ": more than four read views");
      // One in or executing a cycle has no function to compare (DLP 9).
      if (!recorded_.count(a.name)) continue;
      for (size_t j = 0; j < i; ++j) {
        if (j >= 2 && !recorded_.count(all[j])) continue;
        const Registered rb = registered_of(all[j]);
        if (static_cast<uint32_t>(a.nbool) != rb.arity) continue;
        const uint64_t ta = recorded_.at(a.name).table[0];
        const int bviews = static_cast<int>(rb.arity);
        for (const std::vector<int>& perm : permutations(static_cast<uint32_t>(bviews))) {
          bool same = true;
          for (uint32_t c = 0; c < (1u << bviews) && same; ++c) same = permuted_bit(rb, perm, c) == ((ta >> c) & 1);
          if (same) {
            out.push_back(a.name + " computes the same as " + rb.name);
            break;
          }
        }
      }
    }
    return out;
  }

  static double now() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
  }

 private:
  Program& p_;
  std::unordered_map<std::string, int> index_;
  std::unordered_map<std::string, Recorded> recorded_;
  // What `reuse_values` keeps, for the operation named reuse_name_: each
  // execution's table by its value, and the matcher's exact checks.
  std::string reuse_name_;
  mutable std::unordered_map<int, std::vector<uint64_t>> call_rows_;
  Matcher::HoldsCache holds_cache_;
  Matcher::SearchCache search_cache_;
  // Each value's tt_keys key, and the matcher's table hash of each value
  // (doubled) and of its `not` (doubled plus one).
  std::unordered_map<int, uint64_t> key_of_value_;
  std::unordered_map<int, uint64_t> hash_of_value_;
  // By operation index: its strongly connected component in the execution
  // graph, whether it's in a cycle, and whether it executes one.
  std::vector<int> component_;
  std::vector<char> cyclic_, reaches_cycle_;
  // The registered operations and every operation their definitions execute.
  std::set<std::string> registered_reach_;
  std::unique_ptr<Hierarchy> hier_;
  std::set<std::string> changed_, added_;
  mutable double lookup_s_ = 0, written_out_s_ = 0;
  bool edit_matches_ = true;
};

}  // namespace beq
