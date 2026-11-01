// Command-line driver: runs one equality-checking method on one AIGER file and
// prints one JSON line with its time, peak memory, and what it found.
//
//   beq METHOD FILE.aag [--planted FILE] [--key value ...]
//
// Methods: info, strash, norm_single, norm_all, cuts4, tt, bdd, sweep, auto.
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <string>

#include "aig.hpp"
#include "functional.hpp"
#include "hier.hpp"
#include "match.hpp"
#include "structural.hpp"
#include "sweep.hpp"

using namespace beq;

namespace {

struct Planted {
  Lit a, b;
  std::string kind;
};

std::vector<Planted> read_planted(const std::string& path) {
  std::vector<Planted> out;
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open " + path);
  Planted p;
  while (in >> p.a >> p.b >> p.kind) out.push_back(p);
  return out;
}

std::string json_escape(const std::string& s) {
  std::string out;
  for (char c : s) {
    if (c == '"' || c == '\\') out += '\\';
    out += c;
  }
  return out;
}

std::string fmt(double x) {
  std::ostringstream o;
  o.precision(9);
  o << x;
  return o.str();
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 3) {
    std::cerr << "usage: beq METHOD FILE.aag [--planted FILE] [--key value ...]\n";
    return 2;
  }
  std::string method = argv[1], path = argv[2];
  std::map<std::string, std::string> opt;
  for (int i = 3; i + 1 < argc; i += 2) {
    if (std::strncmp(argv[i], "--", 2) != 0) throw std::runtime_error("bad option");
    opt[argv[i] + 2] = argv[i + 1];
  }
  auto get = [&](const std::string& k, double def) { return opt.count(k) ? std::stod(opt[k]) : def; };

  if (method == "hier_edit") {
    // Random edits to a library, and the operations each one makes the
    // compiler check again: the edited one, and every operation that
    // executes one whose recorded truth tables changed.
    Hierarchy h(read_library(path));
    std::vector<std::vector<size_t>> callers(h.size());
    for (size_t i = 0; i < h.size(); ++i)
      for (const HStatement& st : h.op(i).statements)
        if (st.is_exec) callers[static_cast<size_t>(st.callee)].push_back(i);
    for (size_t i = 0; i < h.size(); ++i) h.check_tt(i);
    std::vector<uint64_t> hash(h.size());
    for (size_t i = 0; i < h.size(); ++i) hash[i] = h.recorded_hash(i);
    Rng rng(static_cast<uint64_t>(get("seed", 1)));
    const int edits = static_cast<int>(get("edits", 200));
    auto recheck_from = [&](size_t start, uint64_t& checked, uint64_t& changed) {
      std::vector<char> pending(h.size(), 0);
      pending[start] = 1;
      for (size_t i = start; i < h.size(); ++i) {
        if (!pending[i]) continue;
        ++checked;
        h.check_tt(i);
        uint64_t now = h.recorded_hash(i);
        if (now == hash[i]) continue;
        ++changed;
        hash[i] = now;
        for (size_t c : callers[i]) pending[c] = 1;
      }
    };
    for (int e = 0; e < edits; ++e) {
      size_t i = rng.next() % h.size();
      HOp& op = h.mutable_op(i);
      std::vector<size_t> ands;
      for (size_t k = 0; k < op.statements.size(); ++k)
        if (!op.statements[k].is_exec) ands.push_back(k);
      if (ands.empty()) continue;
      HStatement& st = op.statements[ands[rng.next() % ands.size()]];
      const bool keeps_function = (e % 2) == 0;
      const HStatement before = st;
      if (keeps_function)
        std::swap(st.a, st.b);
      else
        st.a ^= 1;
      uint64_t checked = 0, changed = 0;
      double t0 = now_seconds();
      recheck_from(i, checked, changed);
      double elapsed = now_seconds() - t0;
      // Undo, and bring every recorded table back.
      st = before;
      uint64_t c2 = 0, ch2 = 0;
      recheck_from(i, c2, ch2);
      int depth = 0;
      sscanf(op.name.c_str(), "L%d", &depth);
      std::cout << "{\"method\":\"hier_edit\",\"file\":\"" << json_escape(path) << "\",\"op\":\"" << op.name
                << "\",\"level\":" << depth << ",\"keeps_function\":" << (keeps_function ? "true" : "false")
                << ",\"checked\":" << checked << ",\"changed\":" << changed << ",\"library_ops\":" << h.size()
                << ",\"time_s\":" << fmt(elapsed) << "}" << std::endl;
    }
    return 0;
  }
  if (method == "hier") {
    // Checks every operation of a library (gen/hierarchy.py) in dependency
    // order with one method, and prints one JSON line per operation.
    Hierarchy h(read_library(path));
    const std::string how = opt.count("how") ? opt["how"] : "tt";
    const bool stop_first = get("stop_first", 0) != 0;
    if (opt.count("patterns_in")) {
      std::ifstream in(opt["patterns_in"]);
      std::string name;
      for (std::string line; std::getline(in, line);) {
        std::istringstream words(line);
        words >> name;
        for (uint32_t a; words >> a;) h.stored[name].push_back(a);
      }
    }
    const size_t copy_limit = static_cast<size_t>(get("copy_limit", 2e7));
    std::string previous_partition;
    for (size_t i = 0; i < h.size(); ++i) {
      const HOp& op = h.op(i);
      Stats hs;
      std::string hstatus = "ok";
      std::vector<uint64_t> keys;
      size_t flat_nodes = 0;
      double t0 = now_seconds();
      long rss0 = peak_rss_kb();
      try {
        if (how == "tt" || (how == "auto" && op.views <= 12)) {
          keys = h.check_tt(i);
        } else if (how == "bdd") {
          keys = h.check_bdd(i, static_cast<size_t>(get("bdd_nodes", 1 << 24)));
        } else if (how == "sat" || how == "sat_clauses" || how == "sat_hybrid" || how == "auto") {
          // `auto` is the modular algorithm: truth tables up to 12 views,
          // otherwise SAT with the hybrid refinement.
          // The executed operations' tables were recorded when they were
          // checked; this operation records its own the same way.
          const uint32_t expand_after = how == "sat" ? 0 : how == "sat_clauses" ? UINT32_MAX
                                                          : static_cast<uint32_t>(get("expand_after", 4));
          keys = h.check_sat(i, hs, expand_after, stop_first);
          double record = now_seconds();
          h.check_tt(i);
          hs.emplace_back("record_s", now_seconds() - record);
        } else if (how == "copy") {
          Aig flat;
          std::vector<Lit> values = h.flatten(i, flat, copy_limit);
          flat_nodes = flat.num_nodes();
          Classes classes(flat.num_nodes());
          if (flat.num_inputs <= 12) {
            classes = run_truth_tables(flat, 12, hs);
          } else {
            SweepParams p;
            p.exhaustive_inputs = 12;
            p.bdd_rescue_conflicts = 1000;
            Sweeper sweeper(flat, p);
            classes = sweeper.run(hs);
          }
          for (Lit l : values) keys.push_back(classes.rep_lit(l));
          // Copying doesn't record anything; nothing else needs it.
        } else {
          throw std::runtime_error("unknown method " + how);
        }
      } catch (const BddLimit&) {
        hstatus = "limit:bdd_nodes";
      } catch (const std::runtime_error& e) {
        hstatus = std::string("limit:") + e.what();
      }
      double elapsed = now_seconds() - t0;
      // Planted pairs found, and a hash of the classes of the operation's
      // own values, which every exact method must agree on.
      int found = 0;
      uint64_t partition = 0x51;
      if (hstatus == "ok") {
        for (auto [a, b] : op.planted) {
          bool same = (keys[node_of(a)] == keys[node_of(b)]) && is_compl(a) == is_compl(b);
          found += same;
        }
        std::unordered_map<uint64_t, uint32_t> first;
        for (uint32_t v = 0; v < keys.size(); ++v) {
          auto [it, inserted] = first.try_emplace(keys[v], v);
          partition = mix64(partition ^ (uint64_t{v} << 32 | it->second));
        }
      }
      uint32_t executions = 0;
      for (const HStatement& s : op.statements) executions += s.is_exec;
      std::ostringstream out;
      out << "{\"method\":\"hier\",\"how\":\"" << how << "\",\"file\":\"" << json_escape(path)
          << "\",\"op\":\"" << op.name << "\",\"status\":\"" << json_escape(hstatus)
          << "\",\"views\":" << op.views << ",\"statements\":" << op.statements.size()
          << ",\"executions\":" << executions << ",\"values\":" << op.num_values
          << ",\"flat_nodes\":" << flat_nodes << ",\"time_s\":" << fmt(elapsed)
          << ",\"rss_increase_kb\":" << (peak_rss_kb() - rss0) << ",\"redundant\":"
          << (hstatus == "ok" ? count_redundant(keys, op.views) : 0) << ",\"planted_found\":" << found
          << ",\"planted_total\":" << op.planted.size() << ",\"partition_hash\":\"" << std::hex << partition
          << std::dec << "\",\"stats\":{";
      bool first_stat = true;
      for (auto& [k, v] : hs) {
        out << (first_stat ? "" : ",") << "\"" << k << "\":" << fmt(v);
        first_stat = false;
      }
      out << "}}";
      std::cout << out.str() << std::endl;
    }
    if (opt.count("patterns_out")) {
      std::ofstream out(opt["patterns_out"]);
      for (auto& [name, patterns] : h.stored) {
        out << name;
        for (uint32_t a : patterns) out << " " << a;
        out << "\n";
      }
    }
    return 0;
  }
  double t0 = now_seconds();
  Aig g = read_aag(path);
  double parse_time = now_seconds() - t0;
  long rss_after_parse = peak_rss_kb();
  std::vector<Planted> planted;
  if (opt.count("planted")) planted = read_planted(opt["planted"]);

  if (method == "convert" || method == "miter") {
    // convert: writes the graph as binary AIGER. miter: also replaces the
    // outputs with one `x xor y` per planted pair, so a pair is proved when
    // its output becomes constant false.
    Aig out = g;
    if (method == "miter") {
      out.outputs.clear();
      for (const Planted& p : planted) {
        auto add = [&](Lit a, Lit b) {
          out.fanin0.push_back(a);
          out.fanin1.push_back(b);
          return make_lit(out.num_nodes() - 1);
        };
        Lit both = add(p.a, p.b);
        Lit neither = add(p.a ^ 1, p.b ^ 1);
        out.outputs.push_back(add(both ^ 1, neither ^ 1));
      }
      if (get("single", 0) != 0) {
        // One output, the `or` of every pair's difference, for tools that
        // prove a whole miter at once.
        Lit any = 0;
        for (Lit o : out.outputs) {
          out.fanin0.push_back(any ^ 1);
          out.fanin1.push_back(o ^ 1);
          any = make_lit(out.num_nodes() - 1) ^ 1;
        }
        out.outputs = {any};
      }
    }
    write_aig_binary(out, opt.at("out"));
    return 0;
  }
  if (method == "cnf") {
    // The miter of planted pair `pair` as DIMACS: only the two cones, with
    // the last clause asserting that the pair differs.
    const Planted& p = planted.at(static_cast<size_t>(get("pair", 0)));
    std::vector<uint32_t> var(g.num_nodes(), 0), stack{node_of(p.a), node_of(p.b)};
    std::vector<uint32_t> cone;
    while (!stack.empty()) {
      uint32_t u = stack.back();
      stack.pop_back();
      if (var[u] != 0) continue;
      var[u] = 1;
      cone.push_back(u);
      if (g.is_and(u)) {
        stack.push_back(node_of(g.fanin0[u]));
        stack.push_back(node_of(g.fanin1[u]));
      }
    }
    std::sort(cone.begin(), cone.end());
    for (size_t i = 0; i < cone.size(); ++i) var[cone[i]] = static_cast<uint32_t>(i + 1);
    auto lit = [&](Lit l) { return (is_compl(l) ? -1 : 1) * static_cast<int64_t>(var[node_of(l)]); };
    std::vector<std::vector<int64_t>> clauses;
    for (uint32_t u : cone) {
      int64_t z = var[u];
      if (u == 0) clauses.push_back({-z});
      if (!g.is_and(u)) continue;
      int64_t a = lit(g.fanin0[u]), b = lit(g.fanin1[u]);
      clauses.push_back({-z, a});
      clauses.push_back({-z, b});
      clauses.push_back({z, -a, -b});
    }
    clauses.push_back({lit(p.a), lit(p.b)});
    clauses.push_back({-lit(p.a), -lit(p.b)});
    std::ofstream out(opt.at("out"));
    out << "p cnf " << cone.size() << " " << clauses.size() << "\n";
    for (auto& c : clauses) {
      for (int64_t l : c) out << l << " ";
      out << "0\n";
    }
    return 0;
  }

  if (method == "match") {
    // Matches of registered operations; see match.hpp. Reads FILE.statements
    // and FILE.planted as gen/matching.py writes them.
    const std::string base = path.substr(0, path.size() - 4);
    std::vector<Registered> registered = standard_registered();
    if (opt.count("extra_arity"))
      add_random_registered(registered, static_cast<uint32_t>(get("extra_arity", 0)),
                            static_cast<uint32_t>(get("extra_count", 4)), 3);
    const std::vector<Statement> statements = read_statements(base + ".statements", get("file_order", 0) != 0);
    Stats mstats;
    std::string mstatus = "ok";
    std::set<Match> found;
    const std::string how = opt.count("how") ? opt["how"] : "exact";
    // Fast methods are timed over several fresh runs, keeping the fastest.
    const int repeat = static_cast<int>(get("repeat", 1));
    double elapsed = 1e30;
    std::unique_ptr<Matcher> kept;
    for (int rep = 0; rep < repeat; ++rep) {
      auto matcher = std::make_unique<Matcher>(g, statements, registered);
      if (opt.count("anchor"))
        matcher->set_anchor(opt["anchor"]);
      else if (how == "resub")
        matcher->set_anchor("any");
      matcher->set_plain(get("plain", 0) != 0);
      matcher->set_first_only(get("first_only", 0) != 0);
      matcher->set_spellings(get("spellings", 0) != 0);
      if (opt.count("precedence")) {
        std::vector<std::string> order;
        std::istringstream names(opt["precedence"]);
        for (std::string name; std::getline(names, name, ',');) order.push_back(name);
        matcher->set_precedence(order, get("precedence_strict", 0) != 0);
      }
      mstats.clear();
      double t = now_seconds();
      try {
        if (opt.count("cut_size")) matcher->set_cut_size(static_cast<uint32_t>(get("cut_size", 4)));
        if (how == "cuts")
          found = matcher->run_cuts(mstats);
        else if (how == "cut_values")
          found = matcher->run_cuts(mstats, true);
        else if (how == "cuts_negated")
          found = matcher->run_cuts(mstats, false, true);
        else if (how == "resub")
          found = matcher->run_resub(mstats);
        else
          found = matcher->run_exact(mstats);
      } catch (const std::runtime_error& e) {
        mstatus = std::string("limit:") + e.what();
      }
      elapsed = std::min(elapsed, now_seconds() - t);
      kept = std::move(matcher);
    }
    Matcher& matcher = *kept;
    std::set<Match> planted_matches;
    std::vector<std::string> planted_kinds;
    std::ifstream pin(base + ".planted");
    for (std::string line; std::getline(pin, line);) {
      std::istringstream words(line);
      Match m;
      std::string kind;
      words >> m.value >> m.op >> kind;
      for (Lit a; words >> a;) m.args.push_back(a);
      planted_matches.insert(m);
      planted_kinds.push_back(kind);
    }
    // The matches as found, arguments in view order, with their sizes.
    if (opt.count("dump_raw")) {
      std::ofstream dump(opt["dump_raw"]);
      for (const Match& m : found) {
        dump << m.value << " " << m.op << " " << matcher.match_size(m);
        for (Lit a : m.args) dump << " " << a;
        dump << "\n";
      }
      for (const Match& m : matcher.spelled()) {
        dump << m.value << " spell:" << m.op << " 0";
        for (Lit a : m.args) dump << " " << a;
        dump << "\n";
      }
    }
    // Compare by function: an argument written as a different literal with
    // the same function is the same argument.
    if (mstatus == "ok") found = matcher.canonical(found);
    std::map<std::string, std::pair<int, int>> kinds;
    {
      std::ifstream again(base + ".planted");
      for (std::string line; std::getline(again, line);) {
        std::istringstream words(line);
        Match m;
        std::string kind;
        words >> m.value >> m.op >> kind;
        for (Lit a; words >> a;) m.args.push_back(a);
        bool hit = found.count(*matcher.canonical({m}).begin()) > 0;
        auto& entry = kinds[kind];
        entry.first += hit ? 1 : 0;
        entry.second += 1;
      }
    }
    if (opt.count("dump")) {
      std::ofstream dump(opt["dump"]);
      for (const Match& m : found) {
        dump << m.value << " " << m.op;
        for (Lit a : m.args) dump << " " << a;
        dump << "\n";
      }
    }
    std::ostringstream out;
    out << "{\"method\":\"match\",\"how\":\"" << how << "\",\"anchor\":\""
        << (opt.count("anchor") ? opt["anchor"] : "cone") << "\",\"file\":\"" << json_escape(path)
        << "\",\"status\":\"" << json_escape(mstatus) << "\",\"inputs\":" << g.num_inputs
        << ",\"ands\":" << g.num_ands() << ",\"time_s\":" << fmt(elapsed) << ",\"rss_after_parse_kb\":"
        << rss_after_parse << ",\"peak_rss_kb\":" << peak_rss_kb() << ",\"matches\":" << found.size()
        << ",\"planted_by_kind\":{";
    bool first = true;
    for (auto& [kind, counts] : kinds) {
      out << (first ? "" : ",") << "\"" << kind << "\":[" << counts.first << "," << counts.second << "]";
      first = false;
    }
    out << "},\"stats\":{";
    first = true;
    for (auto& [k, v] : mstats) {
      out << (first ? "" : ",") << "\"" << k << "\":" << fmt(v);
      first = false;
    }
    out << "}}";
    std::cout << out.str() << std::endl;
    return 0;
  }

  Stats stats;
  std::string status = "ok";
  std::string chosen = method;
  double t1 = now_seconds();
  uint32_t width = live_width(g);
  double width_time = now_seconds() - t1;
  Classes classes(g.num_nodes());
  // Small instances run in microseconds, so time several repetitions and
  // report the fastest.
  const int repeat = static_cast<int>(get("repeat", 1));
  double method_time = 1e30;
  for (int rep = 0; rep < repeat; ++rep) {
  stats.clear();
  t1 = now_seconds();
  try {
    if (method == "auto") {
      // The combined algorithm. Truth tables over every input when there are
      // few; otherwise SAT sweeping where each pair goes through exhaustive
      // simulation (cones of at most 12 inputs), SAT up to 1,000 conflicts,
      // OBDDs of the two cones, and then either truth tables for the whole
      // graph (at most 20 inputs) or SAT with no limit. Every step is exact,
      // so the thresholds change only the time.
      const uint32_t small_inputs = static_cast<uint32_t>(get("small_inputs", 12));
      // With more inputs, an OBDD of the whole graph is tried first, within
      // a node budget proportional to the graph, because canonical OBDDs
      // settle every pair at once when they stay small.
      const double bdd_budget = get("bdd_budget", 0);
      bool done = false;
      if (g.num_inputs <= small_inputs) {
        chosen = "tt";
        classes = run_truth_tables(g, small_inputs, stats);
        done = true;
      } else if (bdd_budget > 0) {
        try {
          classes = run_bdd(g, first_use_order(g), static_cast<size_t>(bdd_budget * g.num_nodes()), stats);
          chosen = "bdd";
          done = true;
        } catch (const BddLimit&) {
          stats.clear();
        }
      }
      if (!done) {
        SweepParams p;
        p.exhaustive_inputs = static_cast<uint32_t>(get("exhaustive", 12));
        p.bdd_rescue_conflicts = static_cast<int64_t>(get("bdd_rescue", 1000));
        p.truth_table_fallback_inputs = static_cast<uint32_t>(get("tt_fallback", 20));
        p.bdd_rescue_nodes = static_cast<size_t>(get("bdd_rescue_nodes", p.bdd_rescue_nodes));
        if (opt.count("external")) p.external_solver = opt["external"];
        if (opt.count("temp_dir")) p.temp_dir = opt["temp_dir"];
        chosen = "sweep";
        try {
          Sweeper s(g, p);
          classes = s.run(stats);
        } catch (const SwitchToTruthTables&) {
          chosen = "sweep_then_tt";
          stats.clear();
          classes = run_truth_tables(g, p.truth_table_fallback_inputs, stats);
        }
      }
    } else if (chosen == "info") {
    } else if (chosen == "strash") {
      classes = run_strash(g, stats);
    } else if (chosen == "norm_single" || chosen == "norm_all") {
      classes = run_normalize(g, chosen == "norm_all", static_cast<size_t>(get("literal_budget", 4e9)), stats);
    } else if (chosen == "cuts4") {
      classes = run_cuts4(g, static_cast<size_t>(get("cut_budget", 2e9)), stats);
    } else if (chosen == "tt") {
      classes = run_truth_tables(g, static_cast<uint32_t>(get("tt_max", 30)), stats);
    } else if (chosen == "bdd") {
      std::vector<uint32_t> order;
      std::string o = opt.count("order") ? opt["order"] : "first_use";
      if (o == "first_use") {
        order = first_use_order(g);
      } else if (o == "natural") {
        for (uint32_t i = 1; i <= g.num_inputs; ++i) order.push_back(i);
      } else if (o == "reverse_first_use") {
        order = first_use_order(g);
        std::reverse(order.begin(), order.end());
      } else {
        throw std::runtime_error("unknown order");
      }
      classes = run_bdd(g, order, static_cast<size_t>(get("bdd_nodes", 1 << 26)), stats);
    } else if (chosen == "sweep") {
      SweepParams p;
      p.sim_rounds = static_cast<int>(get("sim_rounds", p.sim_rounds));
      p.conflict_limit = static_cast<int64_t>(get("conflicts", -1));
      p.recycle_vars = static_cast<uint32_t>(get("recycle_vars", p.recycle_vars));
      p.seed = static_cast<uint64_t>(get("seed", 1));
      p.bdd_rescue_conflicts = static_cast<int64_t>(get("bdd_rescue", 0));
      p.bdd_rescue_nodes = static_cast<size_t>(get("bdd_rescue_nodes", p.bdd_rescue_nodes));
      p.exhaustive_inputs = static_cast<uint32_t>(get("exhaustive", 0));
      p.justify = get("justify", 0) != 0;
      p.scope = get("scope", 1) != 0;
      p.scope_limit = static_cast<uint32_t>(get("scope_limit", p.scope_limit));
      Sweeper s(g, p);
      classes = s.run(stats);
    } else {
      throw std::runtime_error("unknown method " + chosen);
    }
  } catch (const BddLimit& e) {
    status = "limit:bdd_nodes";
  } catch (const std::runtime_error& e) {
    status = std::string("limit:") + e.what();
  }
  method_time = std::min(method_time, now_seconds() - t1);
  }

  // Summarize the classes found.
  uint64_t merged = 0, const_nodes = 0, input_nodes = 0, partition = 0x7a11;
  if (status == "ok") {
    for (uint32_t v = 1; v < g.num_nodes(); ++v) {
      Lit r = classes.rep_lit(make_lit(v));
      partition = mix64(partition ^ (static_cast<uint64_t>(v) << 32 | r));
      if (node_of(r) == v) continue;
      ++merged;
      if (node_of(r) == 0)
        ++const_nodes;
      else if (node_of(r) <= g.num_inputs)
        ++input_nodes;
    }
  }
  if (status == "ok" && opt.count("dump")) {
    // One line per node: the representative literal of its class.
    std::ofstream dump(opt["dump"]);
    for (uint32_t v = 0; v < g.num_nodes(); ++v) dump << classes.rep_lit(make_lit(v)) << "\n";
  }
  std::map<std::string, std::pair<int, int>> by_kind;
  int found = 0;
  for (const Planted& p : planted) {
    bool ok = status == "ok" && classes.rep_lit(p.a) == classes.rep_lit(p.b);
    found += ok;
    auto& entry = by_kind[p.kind];
    entry.first += ok;
    entry.second += 1;
  }

  std::ostringstream out;
  out << "{\"method\":\"" << method << "\",\"chosen\":\"" << chosen << "\",\"file\":\"" << json_escape(path)
      << "\",\"status\":\"" << json_escape(status) << "\",\"nodes\":" << g.num_nodes()
      << ",\"inputs\":" << g.num_inputs << ",\"ands\":" << g.num_ands() << ",\"width\":" << width
      << ",\"parse_s\":" << fmt(parse_time) << ",\"width_s\":" << fmt(width_time)
      << ",\"time_s\":" << fmt(method_time) << ",\"rss_after_parse_kb\":" << rss_after_parse
      << ",\"peak_rss_kb\":" << peak_rss_kb() << ",\"merged\":" << merged << ",\"const_nodes\":" << const_nodes
      << ",\"input_nodes\":" << input_nodes << ",\"partition_hash\":\"" << std::hex << partition << std::dec
      << "\",\"planted_found\":" << found << ",\"planted_total\":" << planted.size() << ",\"planted_by_kind\":{";
  bool first = true;
  for (auto& [kind, counts] : by_kind) {
    out << (first ? "" : ",") << "\"" << json_escape(kind) << "\":[" << counts.first << "," << counts.second << "]";
    first = false;
  }
  out << "},\"stats\":{";
  first = true;
  for (auto& [k, v] : stats) {
    out << (first ? "" : ",") << "\"" << k << "\":" << fmt(v);
    first = false;
  }
  out << "},\"options\":{";
  first = true;
  for (auto& [k, v] : opt) {
    if (k == "planted" || k == "dump" || k == "dump_raw" || k == "out" || k == "single" || k == "patterns_in" || k == "patterns_out")
      continue;
    out << (first ? "" : ",") << "\"" << k << "\":\"" << json_escape(v) << "\"";
    first = false;
  }
  out << "}}";
  std::cout << out.str() << std::endl;
  return 0;
}
