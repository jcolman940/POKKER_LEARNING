#pragma once

#include <cstdint>
#include <vector>

#include "pokercore/card.hpp"
#include "pokercore/range.hpp"

namespace pokercore {

inline constexpr int kMinPlayers = 2;
inline constexpr int kMaxPlayers = 10;

enum class EquityMode {
  Auto,        // exact when the work fits in `exact_limit`, Monte Carlo otherwise
  Exact,       // always enumerate every combo assignment and runout
  MonteCarlo,  // always sample
};

struct EquityOptions {
  EquityMode mode = EquityMode::Auto;
  // Monte Carlo trials.
  std::uint64_t iterations = 200'000;
  // Auto mode enumerates exactly when (combo assignments x runouts) is at most this.
  double exact_limit = 3e7;
  // RNG seed for Monte Carlo; 0 picks a random seed (reported back in the result).
  std::uint64_t seed = 0;
};

struct PlayerEquity {
  double equity = 0.0;     // win + share of split pots
  double win = 0.0;        // probability of winning alone
  double tie = 0.0;        // probability of splitting the pot
  double lose = 0.0;       // 1 - win - tie
  double std_error = 0.0;  // standard error of `equity` (0 when exact)
};

struct EquityResult {
  std::vector<PlayerEquity> players;
  bool exact = false;
  std::uint64_t samples = 0;  // runouts evaluated (exact) or trials (Monte Carlo)
  std::uint64_t seed = 0;     // seed actually used (0 when exact)
};

// All-in equity at showdown for 2..10 players, each holding a weighted range
// (a single hand is a range with one combo). Combos are weighted by the product
// of the players' weights over every non-conflicting assignment (card removal),
// and every runout of the remaining board is equally likely.
//
// `board` has 0, 3, 4 or 5 cards; `dead` cards are removed from the deck.
// Throws std::invalid_argument when the input is inconsistent (bad board size,
// duplicated cards, a range left empty after card removal...) and
// std::runtime_error when no non-conflicting assignment can be dealt.
EquityResult calculate_equity(const std::vector<Range>& players, const std::vector<Card>& board,
                              const std::vector<Card>& dead = {}, const EquityOptions& options = {});

}  // namespace pokercore
