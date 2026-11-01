// Open-addressing hash map from nonzero 64-bit keys to 32-bit values. The
// standard containers use several times the memory per entry, which matters
// at tens of millions of nodes.
#pragma once

#include <cstdint>
#include <vector>

#include "aig.hpp"

namespace beq {

class U64Map {
 public:
  explicit U64Map(size_t expected = 16) {
    size_t size = 16;
    while (size < expected * 2) size *= 2;
    keys_.assign(size, 0);
    values_.assign(size, 0);
  }

  // Returns a pointer to the value for key, or nullptr if absent.
  uint32_t* find(uint64_t key) {
    size_t mask = keys_.size() - 1;
    for (size_t slot = mix64(key) & mask;; slot = (slot + 1) & mask) {
      if (keys_[slot] == key) return &values_[slot];
      if (keys_[slot] == 0) return nullptr;
    }
  }

  // Inserts key if absent. Returns the value slot and whether it was inserted.
  std::pair<uint32_t*, bool> insert(uint64_t key, uint32_t value) {
    if ((count_ + 1) * 2 > keys_.size()) grow();
    size_t mask = keys_.size() - 1;
    for (size_t slot = mix64(key) & mask;; slot = (slot + 1) & mask) {
      if (keys_[slot] == key) return {&values_[slot], false};
      if (keys_[slot] == 0) {
        keys_[slot] = key;
        values_[slot] = value;
        ++count_;
        return {&values_[slot], true};
      }
    }
  }

  size_t size() const { return count_; }
  size_t memory_bytes() const { return keys_.size() * 12; }

 private:
  void grow() {
    std::vector<uint64_t> old_keys;
    std::vector<uint32_t> old_values;
    old_keys.swap(keys_);
    old_values.swap(values_);
    keys_.assign(old_keys.size() * 2, 0);
    values_.assign(old_keys.size() * 2, 0);
    count_ = 0;
    for (size_t i = 0; i < old_keys.size(); ++i)
      if (old_keys[i] != 0) insert(old_keys[i], old_values[i]);
  }

  std::vector<uint64_t> keys_;
  std::vector<uint32_t> values_;
  size_t count_ = 0;
};

}  // namespace beq
