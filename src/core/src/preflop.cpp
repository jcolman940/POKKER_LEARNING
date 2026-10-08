#include "pokercore/preflop.hpp"

#include <algorithm>
#include <atomic>
#include <stdexcept>
#include <thread>
#include <utility>

#include "pokercore/evaluator.hpp"
#include "pokercore/range.hpp"
#include "rng.hpp"

namespace pokercore {

namespace {

double estimate_pair(const std::vector<Combo>& a, const std::vector<Combo>& b,
                     std::uint64_t trials, std::uint64_t seed) {
  std::vector<std::pair<CardMask, CardMask>> pairs;
  for (Combo ca : a) {
    for (Combo cb : b) {
      if (!(ca.mask() & cb.mask())) pairs.emplace_back(ca.mask(), cb.mask());
    }
  }
  detail::Rng rng(seed);
  double share = 0.0;
  for (std::uint64_t t = 0; t < trials; ++t) {
    const auto& [ha, hb] = pairs[t % pairs.size()];
    const CardMask used = ha | hb;
    CardMask board = 0;
    for (int k = 0; k < 5;) {
      const CardMask bit = card_bit(static_cast<Card>(rng.below(kNumCards)));
      if (bit & (used | board)) continue;
      board |= bit;
      ++k;
    }
    const HandValue va = evaluate(ha | board);
    const HandValue vb = evaluate(hb | board);
    share += va > vb ? 1.0 : (va == vb ? 0.5 : 0.0);
  }
  return share / static_cast<double>(trials);
}

}  // namespace

std::vector<double> preflop_equity_matrix(std::uint64_t trials_per_pair, std::uint64_t seed,
                                          int threads) {
  if (trials_per_pair == 0) throw std::invalid_argument("trials_per_pair must be positive");
  if (threads <= 0) threads = static_cast<int>(std::max(1u, std::thread::hardware_concurrency()));

  std::vector<std::vector<Combo>> combos(kNumHandClasses);
  for (int i = 0; i < kNumHandClasses; ++i) combos[i] = hand_class_combos(hand_class_from_index(i));

  std::vector<std::pair<int, int>> jobs;
  for (int a = 0; a < kNumHandClasses; ++a) {
    for (int b = a + 1; b < kNumHandClasses; ++b) jobs.emplace_back(a, b);
  }

  std::vector<double> matrix(static_cast<std::size_t>(kNumHandClasses) * kNumHandClasses, 0.5);
  std::atomic<std::size_t> next{0};
  auto worker = [&] {
    for (std::size_t j = next++; j < jobs.size(); j = next++) {
      const auto [a, b] = jobs[j];
      // Per-pair seed: results do not depend on scheduling.
      const double e = estimate_pair(combos[a], combos[b], trials_per_pair,
                                     seed * 0x9E3779B97F4A7C15ULL + j + 1);
      matrix[static_cast<std::size_t>(a) * kNumHandClasses + b] = e;
      matrix[static_cast<std::size_t>(b) * kNumHandClasses + a] = 1.0 - e;
    }
  };
  std::vector<std::thread> pool;
  for (int t = 1; t < threads; ++t) pool.emplace_back(worker);
  worker();
  for (auto& th : pool) th.join();
  return matrix;
}

}  // namespace pokercore
