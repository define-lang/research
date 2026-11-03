// `beq program FILE.prog --mode check|fix|edits|registry`: the full
// algorithm on a whole program (program.hpp), the fix loop
// (program_fix.hpp), random edits with incremental rechecking, and edits to
// booleans.defcl.
#pragma once

#include <iostream>

#include "program_fix.hpp"

namespace beq {

inline std::string times_json(const CheckTimes& t) {
  std::ostringstream o;
  o.precision(6);
  o << "{\"structure\":" << t.structure << ",\"tables\":" << t.tables << ",\"groups\":" << t.groups
    << ",\"order\":" << t.order << ",\"redundant\":" << t.redundant << ",\"matches\":" << t.matches
    << ",\"spellings\":" << t.spellings << ",\"total\":" << t.total() << ",\"tables_lookups\":" << t.lookups
    << ",\"tables_written_out\":" << t.written_out << "}";
  return o.str();
}

inline std::string report_json(const POp& op, const Report& r) {
  std::ostringstream o;
  o.precision(6);
  int statements = 0;
  for (const PStmt& s : op.stmts) statements += is_boolean_statement(s.kind);
  o << "{\"op\":\"" << op.name << "\",\"boolean\":" << (op.boolean ? "true" : "false") << ",\"inputs\":" << r.inputs
    << ",\"statements\":" << statements << ",\"how\":\"" << r.how << "\",\"errors\":{";
  bool first = true;
  for (const auto& [rule, detail] : r.errors) {
    o << (first ? "" : ",") << "\"" << rule << "\":" << detail;
    first = false;
  }
  o << "},\"t\":" << times_json(r.times) << ",\"stats\":{";
  first = true;
  for (const auto& [k, v] : r.stats) {
    o << (first ? "" : ",") << "\"" << k << "\":" << v;
    first = false;
  }
  o << "}}";
  return o.str();
}

struct CheckSummary {
  CheckTimes times;
  std::map<std::string, int> errors;
  int ops_with_errors = 0, tt = 0, sat = 0;
  std::vector<std::pair<double, std::string>> slowest;  // (time, report json)
  std::vector<double> op_times;
  std::map<uint32_t, std::array<double, 3>> by_inputs;  // count, total, slowest
  void add(const POp& op, const Report& r, size_t keep) {
    times.add(r.times);
    op_times.push_back(r.times.total());
    auto& b = by_inputs[r.inputs];
    b[0] += 1;
    b[1] += r.times.total();
    b[2] = std::max(b[2], r.times.total());
    for (const auto& [rule, detail] : r.errors) ++errors[rule];
    ops_with_errors += !r.errors.empty();
    (r.how == "sat" ? sat : tt) += 1;
    slowest.push_back({r.times.total(), report_json(op, r)});
    if (slowest.size() > 4 * keep) trim(keep);
  }
  void trim(size_t keep) {
    std::sort(slowest.begin(), slowest.end(), [](const auto& a, const auto& b) { return a.first > b.first; });
    if (slowest.size() > keep) slowest.resize(keep);
  }
  std::string json(size_t keep) {
    trim(keep);
    std::ostringstream o;
    o << "\"time_s\":" << times_json(times) << ",\"tt\":" << tt << ",\"sat\":" << sat
      << ",\"ops_with_errors\":" << ops_with_errors << ",\"errors\":{";
    bool first = true;
    for (const auto& [rule, n] : errors) {
      o << (first ? "" : ",") << "\"" << rule << "\":" << n;
      first = false;
    }
    std::sort(op_times.begin(), op_times.end());
    if (!op_times.empty())
      o << "},\"op_time_median_s\":" << op_times[op_times.size() / 2]
        << ",\"op_time_p99_s\":" << op_times[op_times.size() * 99 / 100] << ",\"op_time_max_s\":" << op_times.back()
        << ",\"by_inputs\":{";
    first = true;
    for (const auto& [inputs, b] : by_inputs) {
      o << (first ? "" : ",") << "\"" << inputs << "\":[" << b[0] << "," << b[1] << "," << b[2] << "]";
      first = false;
    }
    o << "},\"slowest\":[";
    for (size_t i = 0; i < slowest.size(); ++i) o << (i ? "," : "") << slowest[i].second;
    o << "]";
    return o.str();
  }
};

inline void read_patterns(ProgramChecker& c, const std::string& path) {
  std::ifstream in(path);
  for (std::string line; std::getline(in, line);) {
    std::istringstream words(line);
    std::string name;
    words >> name;
    std::vector<uint32_t>& p = c.patterns()[name];
    for (uint32_t a; words >> a;) p.push_back(a);
  }
}

inline void write_patterns(ProgramChecker& c, const std::string& path) {
  std::ofstream out(path);
  for (const auto& [name, p] : c.patterns()) {
    out << name;
    for (uint32_t a : p) out << " " << a;
    out << "\n";
  }
}

inline int run_program(const std::string& path, std::map<std::string, std::string>& opt) {
  auto get = [&](const std::string& k, double def) { return opt.count(k) ? std::stod(opt[k]) : def; };
  const std::string mode = opt.count("mode") ? opt["mode"] : "check";
  const std::string how = opt.count("how") ? opt["how"] : "auto";
  const size_t keep = static_cast<size_t>(get("slowest", 10));
  const double t_read = ProgramChecker::now();
  Program p = read_program(path);
  const double read_s = ProgramChecker::now() - t_read;
  ProgramChecker c(p);
  if (opt.count("patterns_in")) read_patterns(c, opt["patterns_in"]);
  c.record_registered();
  std::cout.precision(6);
  // The program as it is when each result is written (fixing changes it).
  auto head = [&]() {
    int boolean_ops = 0;
    size_t statements = 0, executions = 0, copies = 0;
    for (const POp& op : p.ops) {
      boolean_ops += op.boolean;
      for (const PStmt& s : op.stmts) {
        statements += is_boolean_statement(s.kind);
        executions += s.kind == "call" && !c.is_registered(s.name);
        copies += s.kind == "copy";
      }
    }
    std::ostringstream o;
    o.precision(6);
    o << "{\"mode\":\"" << mode << "\",\"file\":\"" << path << "\",\"ops\":" << p.ops.size()
      << ",\"boolean_ops\":" << boolean_ops << ",\"boolean_statements\":" << statements
      << ",\"user_executions\":" << executions << ",\"copies\":" << copies << ",\"read_s\":" << read_s;
    return o.str();
  };
  // Every operation, in order, recording what it computes.
  auto check_all = [&](CheckSummary& sum, std::ofstream* details) {
    for (size_t i = 0; i < p.ops.size(); ++i) {
      Report r = c.check(i, true, how);
      sum.add(p.ops[i], r, keep);
      if (details) *details << report_json(p.ops[i], r) << "\n";
    }
  };
  if (mode == "check") {
    std::unique_ptr<std::ofstream> details;
    if (opt.count("details")) details = std::make_unique<std::ofstream>(opt["details"]);
    CheckSummary sum;
    const double t0 = ProgramChecker::now();
    check_all(sum, details.get());
    const double wall = ProgramChecker::now() - t0;
    const std::vector<std::string> registry = c.check_registry();
    if (opt.count("patterns_out")) write_patterns(c, opt["patterns_out"]);
    std::cout << head() << ",\"wall_s\":" << wall << ",\"peak_rss_kb\":" << peak_rss_kb()
              << ",\"registry_errors\":" << registry.size() << "," << sum.json(keep) << "}" << std::endl;
    return 0;
  }
  if (mode == "unchanged") {
    // What checking an unchanged program costs with incremental rechecking:
    // each operation's text is hashed and compared with the stored hash;
    // none changed, so nothing is checked again.
    const double t0 = ProgramChecker::now();
    std::map<std::string, uint64_t> stored;
    if (opt.count("hashes_in")) {
      std::ifstream in(opt["hashes_in"]);
      std::string name;
      uint64_t h;
      while (in >> name >> h) stored[name] = h;
    }
    int changed = 0;
    std::vector<std::pair<std::string, uint64_t>> hashes;
    for (const POp& op : p.ops) {
      std::ostringstream text;
      for (const PStmt& st : op.stmts) {
        text << st.kind << ' ' << st.name;
        for (const PArg& a : st.args) text << ' ' << a.id << a.literal;
        text << '\n';
      }
      for (const PArg& a : op.outs) text << a.id << a.literal << ' ';
      uint64_t h = 0x99;
      for (char ch : text.str()) h = mix64(h ^ static_cast<unsigned char>(ch));
      auto it = stored.find(op.name);
      changed += it == stored.end() || it->second != h;
      hashes.push_back({op.name, h});
    }
    const double wall = ProgramChecker::now() - t0;
    if (opt.count("hashes_out")) {
      std::ofstream out(opt["hashes_out"]);
      for (const auto& [name, h] : hashes) out << name << " " << h << "\n";
    }
    std::cout << head() << ",\"hash_s\":" << wall << ",\"changed\":" << changed << ",\"peak_rss_kb\":" << peak_rss_kb()
              << "}" << std::endl;
    return 0;
  }
  if (mode == "groups") {
    // Each boolean operation's interchangeable views, as a label per view.
    for (size_t i = 0; i < p.ops.size(); ++i) {
      c.check(i, true, "tt");
      if (!p.ops[i].boolean) continue;
      std::cout << p.ops[i].name;
      for (int g : c.recorded(p.ops[i].name).group) std::cout << " " << g;
      std::cout << "\n";
    }
    return 0;
  }
  if (mode == "fix") {
    const size_t ops_before = p.ops.size();
    ProgramFixer fixer(c);
    if (opt.count("keep_searches")) c.reuse_search = true;
    if (opt.count("check_search")) c.check_search = true;
    std::ofstream progress;
    if (opt.count("progress")) {
      progress.open(opt["progress"]);
      fixer.progress = &progress;
    }
    const double t0 = ProgramChecker::now();
    std::vector<ProgramFixer::OpResult> results = fixer.fix_all(static_cast<int>(get("max_rounds", 400)));
    const double wall = ProgramChecker::now() - t0;
    // The program as written, read back and checked: what a compiler sees.
    int remaining = -1;
    double after_s = 0, write_s = 0;
    if (opt.count("out")) {
      const double tw = ProgramChecker::now();
      write_program(p, opt["out"]);
      write_s = ProgramChecker::now() - tw;
      const double ta = ProgramChecker::now();
      Program q = read_program(opt["out"]);
      ProgramChecker qc(q);
      qc.record_registered();
      remaining = 0;
      for (size_t i = 0; i < q.ops.size(); ++i) remaining += !qc.check(i, true, "tt").errors.empty();
      after_s = ProgramChecker::now() - ta;
    }
    std::map<std::string, int> statuses, fixes;
    std::vector<int> rounds;
    double slowest = 0;
    std::string slowest_name;
    auto count = [&](const ProgramFixer::OpResult& r) {
      ++statuses[r.status];
      for (const auto& [k, n] : r.fixes) fixes[k] += n;
      rounds.push_back(r.rounds);
      if (r.seconds > slowest) {
        slowest = r.seconds;
        slowest_name = r.name;
      }
    };
    for (const auto& r : results) count(r);
    std::sort(rounds.begin(), rounds.end());
    std::ostringstream o;
    o << head() << ",\"wall_s\":" << wall << ",\"peak_rss_kb\":" << peak_rss_kb() << ",\"ops_before\":" << ops_before
      << ",\"rounds_median\":" << rounds[rounds.size() / 2]
      << ",\"rounds_max\":" << rounds.back() << ",\"ops_with_errors_after\":" << remaining
      << ",\"check_after_s\":" << after_s << ",\"slowest_op_s\":" << slowest << ",\"slowest_op\":\"" << slowest_name
      << "\",\"statuses\":{";
    bool first = true;
    for (const auto& [k, n] : statuses) {
      o << (first ? "" : ",") << "\"" << k << "\":" << n;
      first = false;
    }
    o << "},\"fixes\":{";
    first = true;
    for (const auto& [k, n] : fixes) {
      o << (first ? "" : ",") << "\"" << k << "\":" << n;
      first = false;
    }
    o << "},\"write_s\":" << write_s << ",\"phase_s\":{";
    first = true;
    for (const auto& [k, sec] : fixer.phase_s) {
      o << (first ? "" : ",") << "\"" << k << "\":" << sec;
      first = false;
    }
    o << "},\"check_t\":" << times_json(fixer.check_times) << ",\"kept_searches\":" << c.kept_hits()
      << ",\"searches\":" << c.kept_misses();
    std::cout << o.str() << "}" << std::endl;
    if (opt.count("replacements")) {
      std::ofstream f(opt["replacements"]);
      fixer.write_replacements(f);
    }
    if (opt.count("failures")) {
      std::ofstream f(opt["failures"]);
      for (const auto& r : results)
        if (r.status != "ok") f << r.name << " " << r.status << "\n";
    }
    return 0;
  }
  // The rest edit a program that compiles, after checking it once.
  CheckSummary first;
  const double t0 = ProgramChecker::now();
  check_all(first, nullptr);
  const double first_s = ProgramChecker::now() - t0;
  std::vector<std::vector<size_t>> callers(p.ops.size());
  for (size_t i = 0; i < p.ops.size(); ++i)
    for (const PStmt& s : p.ops[i].stmts)
      if (s.kind == "call" || s.kind == "run") callers[static_cast<size_t>(c.index_of(s.name))].push_back(i);
  if (mode == "edits") {
    Rng rng(static_cast<uint64_t>(get("seed", 1)));
    const int edits = static_cast<int>(get("edits", 200));
    // Checks the operation, and again every operation that executes one
    // whose recorded function or interchangeable views changed.
    auto recheck_from = [&](size_t start, int& checked, int& changed, CheckTimes& times) {
      std::set<size_t> pending{start};
      while (!pending.empty()) {
        const size_t i = *pending.begin();
        pending.erase(pending.begin());
        const POp& op = p.ops[i];
        const uint64_t hash = c.recorded(op.name).hash;
        const std::vector<int> group = c.recorded(op.name).group;
        Report r = c.check(i, true, how);
        times.add(r.times);
        ++checked;
        if (c.recorded(op.name).hash == hash && c.recorded(op.name).group == group) continue;
        ++changed;
        for (size_t k : callers[i]) pending.insert(k);
      }
    };
    std::vector<double> times;
    std::vector<int> rechecked;
    for (int e = 0; e < edits; ++e) {
      const size_t i = rng.next() % p.ops.size();
      POp& op = p.ops[i];
      std::vector<size_t> ands;
      for (size_t k = 0; k < op.stmts.size(); ++k)
        if (op.stmts[k].kind == "and" && !op.stmts[k].args[0].is_literal()) ands.push_back(k);
      if (ands.empty()) {
        --e;
        continue;
      }
      const POp before = op;
      const size_t k = ands[rng.next() % ands.size()];
      const bool keeps_function = (e % 2) == 0;
      if (keeps_function) {
        std::swap(op.stmts[k].args[0], op.stmts[k].args[1]);
      } else {
        // Another boolean value that comes before the statement.
        const OpInfo info = c.analyze(op);
        std::vector<int> earlier(info.inputs.begin(), info.inputs.end());
        for (size_t j = 0; j < k; ++j)
          if (is_boolean_statement(op.stmts[j].kind)) earlier.push_back(op.stmts[j].ids[0]);
        std::vector<int> choices;
        for (int v : earlier)
          if (info.values.at(v).stmt < static_cast<int>(k) && v != op.stmts[k].args[0].id && v != op.stmts[k].args[1].id)
            choices.push_back(v);
        if (choices.empty()) {
          --e;
          continue;
        }
        op.stmts[k].args[0].id = choices[rng.next() % choices.size()];
      }
      int checked = 0, changed = 0;
      CheckTimes et;
      const double te = ProgramChecker::now();
      recheck_from(i, checked, changed, et);
      const double elapsed = ProgramChecker::now() - te;
      p.ops[i] = before;
      int c2 = 0, ch2 = 0;
      CheckTimes ut;
      recheck_from(i, c2, ch2, ut);
      times.push_back(elapsed);
      rechecked.push_back(checked);
      std::cout << "{\"edit\":" << e << ",\"op\":\"" << before.name << "\",\"keeps_function\":"
                << (keeps_function ? "true" : "false") << ",\"checked\":" << checked << ",\"changed\":" << changed
                << ",\"time_s\":" << elapsed << ",\"t\":" << times_json(et) << "}\n";
    }
    std::sort(times.begin(), times.end());
    std::sort(rechecked.begin(), rechecked.end());
    std::cout << head() << ",\"first_check_s\":" << first_s << ",\"edits\":" << times.size()
              << ",\"edit_time_median_s\":" << times[times.size() / 2] << ",\"edit_time_max_s\":" << times.back()
              << ",\"rechecked_median\":" << rechecked[rechecked.size() / 2] << ",\"rechecked_max\":" << rechecked.back()
              << ",\"peak_rss_kb\":" << peak_rss_kb() << "}" << std::endl;
    return 0;
  }
  if (mode == "registry") {
    // Registering an operation: the registered operations apply to every
    // operation, so every one is checked again, but only for matches and
    // spellings of the one added (all of them with --focused 0). The order
    // is by key, so registering one only puts it among the others.
    const std::vector<std::string> original = p.registered;
    std::vector<std::pair<std::string, std::vector<std::string>>> edits;
    if (opt.count("register")) {
      std::vector<std::string> added = original;
      added.push_back(opt["register"]);
      edits.push_back({"register " + opt["register"], added});
    }
    for (const auto& [name, registered] : edits) {
      p.registered = registered;
      std::set<std::string> changed, added;
      for (const std::string& r : registered)
        if (std::find(original.begin(), original.end(), r) == original.end()) {
          added.insert(r);
          changed.insert(r);
        }
      if (get("focused", 1) != 0) c.set_registry_edit(changed, added, !added.empty());
      CheckSummary sum;
      const double te = ProgramChecker::now();
      for (size_t i = 0; i < p.ops.size(); ++i) sum.add(p.ops[i], c.check(i, false, how, true), keep);
      const double elapsed = ProgramChecker::now() - te;
      std::cout << head() << ",\"edit\":\"" << name << "\",\"first_check_s\":" << first_s << ",\"recheck_s\":" << elapsed
                << ",\"registry_errors\":" << c.check_registry().size() << ",\"peak_rss_kb\":" << peak_rss_kb() << ","
                << sum.json(keep) << "}" << std::endl;
    }
    p.registered = original;
    c.set_registry_edit({}, {}, true);
    return 0;
  }
  throw std::runtime_error("unknown mode " + mode);
}

}  // namespace beq
