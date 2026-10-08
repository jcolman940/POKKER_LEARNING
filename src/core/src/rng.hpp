#pragma once

// Internal helpers shared by the simulation code. Not part of the public API.

#include <algorithm>
#include <bit>
#include <cstddef>
#include <cstdint>

namespace pokercore::detail {

// xoshiro256** seeded through splitmix64: small, fast, and gives the same
// sequence on every compiler and platform (unlike std:: distributions).
class Rng {
 public:
  explicit Rng(std::uint64_t seed) {
    for (auto& word : state_) {
      seed += 0x9E3779B97F4A7C15ULL;
      std::uint64_t z = seed;
      z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
      z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
      word = z ^ (z >> 31);
    }
  }

  std::uint64_t next() noexcept {
    const std::uint64_t result = std::rotl(state_[1] * 5, 7) * 9;
    const std::uint64_t t = state_[1] << 17;
    state_[2] ^= state_[0];
    state_[3] ^= state_[1];
    state_[1] ^= state_[2];
    state_[0] ^= state_[3];
    state_[2] ^= t;
    state_[3] = std::rotl(state_[3], 45);
    return result;
  }

  // Uniform double in [0, 1).
  double uniform() noexcept { return static_cast<double>(next() >> 11) * 0x1.0p-53; }

  // Uniform integer in [0, n).
  std::size_t below(std::size_t n) noexcept {
    return std::min(static_cast<std::size_t>(uniform() * static_cast<double>(n)), n - 1);
  }

 private:
  std::uint64_t state_[4];
};

}  // namespace pokercore::detail
