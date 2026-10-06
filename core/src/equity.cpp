#include "pokercore/equity.hpp"

#include <algorithm>
#include <bit>
#include <cmath>
#include <random>
#include <stdexcept>
#include <string>

#include "pokercore/evaluator.hpp"
#include "rng.hpp"

namespace pokercore {

namespace {

double binomial(int n, int k) {
  if (k < 0 || k > n) return 0.0;
  double r = 1.0;
  for (int i = 1; i <= k; ++i) r = r * (n - k + i) / i;
  return r;
}

struct PlayerCombos {
  std::vector<WeightedCombo> combos;
  std::vector<double> cumulative;  // for weighted sampling
};

// Evaluates one showdown and returns the number of players sharing the best hand;
// `values` receives every player's hand value.
int showdown(const CardMask* holes, int n, CardMask board, HandValue* values, HandValue& best) {
  best = 0;
  int winners = 0;
  for (int i = 0; i < n; ++i) {
    values[i] = evaluate(holes[i] | board);
    if (values[i] > best) {
      best = values[i];
      winners = 1;
    } else if (values[i] == best) {
      ++winners;
    }
  }
  return winners;
}

class ExactEnumerator {
 public:
  ExactEnumerator(const std::vector<PlayerCombos>& players, CardMask board, CardMask dead,
                  int missing)
      : players_(players),
        n_(static_cast<int>(players.size())),
        board_(board),
        dead_(dead),
        missing_(missing),
        holes_(n_),
        values_(n_),
        win_(n_),
        tie_(n_),
        share_(n_),
        run_win_(n_),
        run_tie_(n_),
        run_share_(n_) {}

  EquityResult run() {
    assign(0, board_ | dead_, 1.0);
    if (total_weight_ <= 0.0) {
      throw std::runtime_error("no non-conflicting combination of hands exists");
    }
    EquityResult result;
    result.exact = true;
    result.samples = samples_;
    for (int i = 0; i < n_; ++i) {
      PlayerEquity p;
      p.win = win_[i] / total_weight_;
      p.tie = tie_[i] / total_weight_;
      p.equity = share_[i] / total_weight_;
      p.lose = std::max(0.0, 1.0 - p.win - p.tie);
      result.players.push_back(p);
    }
    return result;
  }

 private:
  void assign(int player, CardMask used, double weight) {
    if (player == n_) {
      evaluate_runouts(used, weight);
      return;
    }
    for (const auto& wc : players_[player].combos) {
      const CardMask m = wc.combo.mask();
      if (m & used) continue;
      holes_[player] = m;
      assign(player + 1, used | m, weight * wc.weight);
    }
  }

  void evaluate_runouts(CardMask used, double weight) {
    deck_.clear();
    for (int c = 0; c < kNumCards; ++c) {
      const CardMask bit = card_bit(static_cast<Card>(c));
      if (!(bit & used)) deck_.push_back(bit);
    }
    std::fill(run_win_.begin(), run_win_.end(), 0);
    std::fill(run_tie_.begin(), run_tie_.end(), 0);
    std::fill(run_share_.begin(), run_share_.end(), 0.0);
    runouts_ = 0;

    deal(0, 0, board_);

    for (int i = 0; i < n_; ++i) {
      win_[i] += weight * static_cast<double>(run_win_[i]);
      tie_[i] += weight * static_cast<double>(run_tie_[i]);
      share_[i] += weight * run_share_[i];
    }
    total_weight_ += weight * static_cast<double>(runouts_);
    samples_ += runouts_;
  }

  void deal(std::size_t start, int depth, CardMask board) {
    if (depth == missing_) {
      score(board);
      return;
    }
    const std::size_t last = deck_.size() - static_cast<std::size_t>(missing_ - depth);
    for (std::size_t i = start; i <= last; ++i) {
      deal(i + 1, depth + 1, board | deck_[i]);
    }
  }

  void score(CardMask board) {
    HandValue best = 0;
    const int winners = showdown(holes_.data(), n_, board, values_.data(), best);
    const double share = 1.0 / winners;
    for (int i = 0; i < n_; ++i) {
      if (values_[i] != best) continue;
      if (winners == 1) {
        ++run_win_[i];
      } else {
        ++run_tie_[i];
      }
      run_share_[i] += share;
    }
    ++runouts_;
  }

  const std::vector<PlayerCombos>& players_;
  int n_;
  CardMask board_;
  CardMask dead_;
  int missing_;

  std::vector<CardMask> holes_;
  std::vector<HandValue> values_;
  std::vector<CardMask> deck_;

  std::vector<double> win_, tie_, share_;
  std::vector<std::uint64_t> run_win_, run_tie_;
  std::vector<double> run_share_;
  std::uint64_t runouts_ = 0;
  std::uint64_t samples_ = 0;
  double total_weight_ = 0.0;
};

EquityResult monte_carlo(std::vector<PlayerCombos>& players, CardMask board, CardMask dead,
                         int missing, std::uint64_t iterations, std::uint64_t seed) {
  const int n = static_cast<int>(players.size());
  for (auto& p : players) {
    double acc = 0.0;
    p.cumulative.clear();
    for (const auto& wc : p.combos) p.cumulative.push_back(acc += wc.weight);
  }

  std::vector<CardMask> deck;
  for (int c = 0; c < kNumCards; ++c) {
    const CardMask bit = card_bit(static_cast<Card>(c));
    if (!(bit & (board | dead))) deck.push_back(bit);
  }

  detail::Rng rng(seed);
  std::vector<CardMask> holes(n);
  std::vector<HandValue> values(n);
  std::vector<std::uint64_t> wins(n, 0), ties(n, 0);
  std::vector<double> share_sum(n, 0.0), share_sq(n, 0.0);

  // Rejection sampling of the whole assignment keeps the joint distribution exact
  // (product of weights over non-conflicting assignments).
  constexpr std::uint64_t kMaxConsecutiveRejects = 1'000'000;

  for (std::uint64_t it = 0; it < iterations; ++it) {
    CardMask used = 0;
    std::uint64_t rejects = 0;
    for (;;) {
      used = board | dead;
      bool ok = true;
      for (int i = 0; i < n && ok; ++i) {
        const auto& p = players[i];
        const double u = rng.uniform() * p.cumulative.back();
        auto pos = static_cast<std::size_t>(
            std::upper_bound(p.cumulative.begin(), p.cumulative.end(), u) - p.cumulative.begin());
        pos = std::min(pos, p.combos.size() - 1);
        const CardMask m = p.combos[pos].combo.mask();
        if (m & used) {
          ok = false;
        } else {
          holes[i] = m;
          used |= m;
        }
      }
      if (ok) break;
      if (++rejects >= kMaxConsecutiveRejects) {
        throw std::runtime_error("could not deal non-conflicting hands; ranges overlap too much");
      }
    }

    CardMask full_board = board;
    for (int k = 0; k < missing;) {
      const CardMask bit = deck[rng.below(deck.size())];
      if (bit & used) continue;
      used |= bit;
      full_board |= bit;
      ++k;
    }

    HandValue best = 0;
    const int winners = showdown(holes.data(), n, full_board, values.data(), best);
    const double share = 1.0 / winners;
    for (int i = 0; i < n; ++i) {
      if (values[i] != best) continue;
      if (winners == 1) {
        ++wins[i];
      } else {
        ++ties[i];
      }
      share_sum[i] += share;
      share_sq[i] += share * share;
    }
  }

  EquityResult result;
  result.exact = false;
  result.samples = iterations;
  result.seed = seed;
  const auto trials = static_cast<double>(iterations);
  for (int i = 0; i < n; ++i) {
    PlayerEquity p;
    p.win = static_cast<double>(wins[i]) / trials;
    p.tie = static_cast<double>(ties[i]) / trials;
    p.lose = std::max(0.0, 1.0 - p.win - p.tie);
    p.equity = share_sum[i] / trials;
    const double variance = std::max(0.0, share_sq[i] / trials - p.equity * p.equity);
    p.std_error = iterations > 1 ? std::sqrt(variance / (trials - 1.0)) : 0.0;
    result.players.push_back(p);
  }
  return result;
}

}  // namespace

EquityResult calculate_equity(const std::vector<Range>& players, const std::vector<Card>& board,
                              const std::vector<Card>& dead, const EquityOptions& options) {
  const int n = static_cast<int>(players.size());
  if (n < kMinPlayers || n > kMaxPlayers) {
    throw std::invalid_argument("equity needs between 2 and 10 players, got " + std::to_string(n));
  }
  if (board.size() != 0 && board.size() != 3 && board.size() != 4 && board.size() != 5) {
    throw std::invalid_argument("board must have 0, 3, 4 or 5 cards");
  }

  CardMask board_mask = 0;
  for (Card c : board) {
    if (c >= kNumCards) throw std::invalid_argument("card index out of range");
    if (board_mask & card_bit(c)) throw std::invalid_argument("duplicate board card");
    board_mask |= card_bit(c);
  }
  CardMask dead_mask = 0;
  for (Card c : dead) {
    if (c >= kNumCards) throw std::invalid_argument("card index out of range");
    if ((board_mask | dead_mask) & card_bit(c)) {
      throw std::invalid_argument("dead card " + card_to_string(c) + " is repeated or on the board");
    }
    dead_mask |= card_bit(c);
  }

  const int missing = 5 - static_cast<int>(board.size());
  const int free_cards = kNumCards - std::popcount(board_mask | dead_mask);
  if (2 * n + missing > free_cards) throw std::invalid_argument("not enough cards in the deck");

  std::vector<PlayerCombos> live(n);
  double assignments = 1.0;
  for (int i = 0; i < n; ++i) {
    live[i].combos = players[i].combos(board_mask | dead_mask);
    if (live[i].combos.empty()) {
      throw std::invalid_argument("player " + std::to_string(i + 1) +
                                  " has no possible hands after card removal");
    }
    assignments *= static_cast<double>(live[i].combos.size());
  }

  const double work = assignments * binomial(free_cards - 2 * n, missing);
  const bool exact = options.mode == EquityMode::Exact ||
                     (options.mode == EquityMode::Auto && work <= options.exact_limit);

  if (exact) {
    return ExactEnumerator(live, board_mask, dead_mask, missing).run();
  }

  if (options.iterations == 0) throw std::invalid_argument("iterations must be positive");
  std::uint64_t seed = options.seed;
  if (seed == 0) {
    std::random_device rd;
    seed = (static_cast<std::uint64_t>(rd()) << 32) ^ rd();
    if (seed == 0) seed = 1;
  }
  return monte_carlo(live, board_mask, dead_mask, missing, options.iterations, seed);
}

HandStrength hand_strength(Combo hero, const Range& villain, const std::vector<Card>& board,
                           const std::vector<Card>& dead) {
  if (board.size() < 3 || board.size() > 5) {
    throw std::invalid_argument("hand strength needs a board of 3 to 5 cards");
  }
  const CardMask board_mask = to_mask(board);
  const CardMask dead_mask = to_mask(dead);
  if (std::popcount(board_mask) != static_cast<int>(board.size())) {
    throw std::invalid_argument("duplicate board card");
  }
  if (hero.mask() & (board_mask | dead_mask)) {
    throw std::invalid_argument("hero cards collide with the board or dead cards");
  }

  const HandValue hero_value = evaluate(hero.mask() | board_mask);
  HandStrength out;
  for (const auto& wc : villain.combos(board_mask | dead_mask | hero.mask())) {
    const HandValue v = evaluate(wc.combo.mask() | board_mask);
    if (hero_value > v) {
      out.win += wc.weight;
    } else if (hero_value == v) {
      out.tie += wc.weight;
    } else {
      out.lose += wc.weight;
    }
    out.combos += wc.weight;
  }
  if (out.combos > 0.0) {
    out.win /= out.combos;
    out.tie /= out.combos;
    out.lose /= out.combos;
  }
  return out;
}

}  // namespace pokercore
