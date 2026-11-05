// The fewest `and`s in any and-inverter graph computing a boolean function
// of up to four views: the first part of a registered operation's key
// (DLP 60). Every function of four views is in one of 222 NPN classes
// (permuting and negating views, negating the result), which share it;
// min_ands_table.hpp lists each class's smallest truth table and its count,
// found by exact synthesis (min_ands_experiment.py).
#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <unordered_map>

#include "min_ands_table.hpp"

namespace beq {

// The function's smallest truth table over every permutation and negation
// of its four views and negation of its result.
inline uint16_t npn_class(uint16_t table) {
  std::array<int, 4> perm;
  std::iota(perm.begin(), perm.end(), 0);
  uint16_t best = 0xFFFF;
  do {
    for (int flips = 0; flips < 16; ++flips) {
      uint16_t out = 0;
      for (int row = 0; row < 16; ++row) {
        int source = 0;
        for (int i = 0; i < 4; ++i)
          if ((row >> i) & 1) source |= 1 << perm[static_cast<size_t>(i)];
        source ^= flips;
        if ((table >> source) & 1) out = static_cast<uint16_t>(out | (1u << row));
      }
      best = std::min({best, out, static_cast<uint16_t>(~out)});
    }
  } while (std::next_permutation(perm.begin(), perm.end()));
  return best;
}

// The fewest `and`s computing a function of `views` views (at most four),
// given as its truth table, view 1 the lowest bit of the row.
inline int min_ands(uint64_t table, int views) {
  if (views > 4) throw std::runtime_error("min_ands needs at most four views");
  // The same function of four views, ignoring the views it doesn't have.
  uint16_t wide = 0;
  for (int row = 0; row < 16; ++row)
    if ((table >> (row & ((1 << views) - 1))) & 1) wide = static_cast<uint16_t>(wide | (1u << row));
  static const std::unordered_map<uint16_t, int> by_class = [] {
    std::unordered_map<uint16_t, int> out;
    for (const auto& [rep, ands] : kMinAnds) out[rep] = ands;
    return out;
  }();
  // Canonicalizing takes 768 transforms, and a program has few registered
  // operations, so each function's count is kept.
  static std::unordered_map<uint16_t, int> by_function;
  auto it = by_function.find(wide);
  if (it == by_function.end()) it = by_function.emplace(wide, by_class.at(npn_class(wide))).first;
  return it->second;
}

}  // namespace beq
