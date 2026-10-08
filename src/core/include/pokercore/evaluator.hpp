#pragma once

#include <array>
#include <bit>
#include <cstdint>
#include <span>
#include <string_view>

#include "pokercore/card.hpp"

namespace pokercore {

enum class Category : std::uint8_t {
  HighCard = 0,
  Pair = 1,
  TwoPair = 2,
  Trips = 3,
  Straight = 4,
  Flush = 5,
  FullHouse = 6,
  Quads = 7,
  StraightFlush = 8,
};

inline constexpr int kNumCategories = 9;

// Strength of the best 5-card hand. Higher is better; equal values tie.
// Layout: category in bits 20..23, then up to five 4-bit ranks (most significant
// first) that break ties within the category.
using HandValue = std::uint32_t;

constexpr Category category(HandValue v) noexcept { return static_cast<Category>(v >> 20); }
std::string_view category_name(Category c) noexcept;

namespace detail {

inline constexpr std::uint32_t kRankMask = 0x1FFF;

constexpr int top_rank(std::uint32_t ranks) noexcept { return std::bit_width(ranks) - 1; }

// Highest straight in a 13-bit rank set, as the rank of its top card; -1 if none.
// The ace also plays low (A-2-3-4-5, top card = 5).
constexpr int compute_straight_high(std::uint32_t ranks) noexcept {
  // Bit 0 = ace-low, bit i = rank i - 1.
  const std::uint32_t m = (ranks << 1) | (ranks >> 12);
  const std::uint32_t runs = m & (m >> 1) & (m >> 2) & (m >> 3) & (m >> 4);
  if (runs == 0) return -1;
  return top_rank(runs) + 3;
}

// Lookup tables over all 13-bit rank sets. They avoid relying on hardware
// POPCNT, which compilers only emit with CPU-specific flags. Built at startup
// rather than at compile time to stay within MSVC's constexpr step limit.
inline constexpr std::size_t kRankSets = std::size_t{1} << 13;

inline const auto kBitCount = [] {
  std::array<std::uint8_t, kRankSets> t{};
  for (std::size_t m = 1; m < kRankSets; ++m) t[m] = static_cast<std::uint8_t>(t[m >> 1] + (m & 1));
  return t;
}();

inline const auto kStraightHigh = [] {
  std::array<std::int8_t, kRankSets> t{};
  for (std::size_t m = 0; m < kRankSets; ++m) {
    t[m] = static_cast<std::int8_t>(compute_straight_high(static_cast<std::uint32_t>(m)));
  }
  return t;
}();

inline int straight_high(std::uint32_t ranks) noexcept { return kStraightHigh[ranks]; }

// Appends the `n` highest ranks of `ranks` to `value`, starting at nibble `slot`
// (4 = most significant kicker slot).
constexpr HandValue pack_top(std::uint32_t ranks, int n, int slot, HandValue value) noexcept {
  for (int i = 0; i < n; ++i) {
    const int r = top_rank(ranks);
    value |= static_cast<HandValue>(r) << (4 * (slot - i));
    ranks &= ~(1u << r);
  }
  return value;
}

constexpr HandValue make_value(Category c) noexcept {
  return static_cast<HandValue>(c) << 20;
}

}  // namespace detail

// Evaluates a set of 5, 6 or 7 cards given as a CardMask.
inline HandValue evaluate(CardMask cards) noexcept {
  using namespace detail;
  const auto s0 = static_cast<std::uint32_t>(cards) & kRankMask;
  const auto s1 = static_cast<std::uint32_t>(cards >> 16) & kRankMask;
  const auto s2 = static_cast<std::uint32_t>(cards >> 32) & kRankMask;
  const auto s3 = static_cast<std::uint32_t>(cards >> 48) & kRankMask;

  // With at most 7 cards a flush excludes quads and full houses, so it can be
  // resolved first.
  for (const std::uint32_t suit : {s0, s1, s2, s3}) {
    if (kBitCount[suit] >= 5) {
      const int sf = straight_high(suit);
      if (sf >= 0) {
        return make_value(Category::StraightFlush) | static_cast<HandValue>(sf) << 16;
      }
      return pack_top(suit, 5, 4, make_value(Category::Flush));
    }
  }

  const std::uint32_t ranks = s0 | s1 | s2 | s3;

  const std::uint32_t quads = s0 & s1 & s2 & s3;
  if (quads) {
    const int q = top_rank(quads);
    const HandValue v = make_value(Category::Quads) | static_cast<HandValue>(q) << 16;
    return pack_top(ranks & ~(1u << q), 1, 3, v);
  }

  const std::uint32_t at_least_2 = (s0 & s1) | (s0 & s2) | (s0 & s3) | (s1 & s2) | (s1 & s3) | (s2 & s3);
  const std::uint32_t at_least_3 = (s0 & s1 & s2) | (s0 & s1 & s3) | (s0 & s2 & s3) | (s1 & s2 & s3);

  if (at_least_3) {
    const int t = top_rank(at_least_3);
    const std::uint32_t pair_ranks = at_least_2 & ~(1u << t);
    if (pair_ranks) {
      return make_value(Category::FullHouse) | static_cast<HandValue>(t) << 16 |
             static_cast<HandValue>(top_rank(pair_ranks)) << 12;
    }
  }

  const int st = straight_high(ranks);
  if (st >= 0) {
    return make_value(Category::Straight) | static_cast<HandValue>(st) << 16;
  }

  if (at_least_3) {
    const int t = top_rank(at_least_3);
    const HandValue v = make_value(Category::Trips) | static_cast<HandValue>(t) << 16;
    return pack_top(ranks & ~(1u << t), 2, 3, v);
  }

  if (at_least_2) {
    const int p1 = top_rank(at_least_2);
    const std::uint32_t other_pairs = at_least_2 & ~(1u << p1);
    if (other_pairs) {
      const int p2 = top_rank(other_pairs);
      const HandValue v = make_value(Category::TwoPair) | static_cast<HandValue>(p1) << 16 |
                          static_cast<HandValue>(p2) << 12;
      return pack_top(ranks & ~(1u << p1) & ~(1u << p2), 1, 2, v);
    }
    const HandValue v = make_value(Category::Pair) | static_cast<HandValue>(p1) << 16;
    return pack_top(ranks & ~(1u << p1), 3, 3, v);
  }

  return pack_top(ranks, 5, 4, make_value(Category::HighCard));
}

// Evaluates 5 to 7 cards. Throws std::invalid_argument on a wrong count or duplicates.
HandValue evaluate(std::span<const Card> cards);

}  // namespace pokercore
