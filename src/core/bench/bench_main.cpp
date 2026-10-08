// Performance benchmark: 7-card evaluations per second and equity timings.
// Usage: pokercore_bench [num_random_hands]
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <string>
#include <vector>

#include "pokercore/card.hpp"
#include "pokercore/equity.hpp"
#include "pokercore/evaluator.hpp"

using namespace pokercore;
using Clock = std::chrono::steady_clock;

namespace {

double seconds_since(Clock::time_point start) {
  return std::chrono::duration<double>(Clock::now() - start).count();
}

void bench_random_hands(std::size_t count) {
  std::mt19937_64 rng(2024);
  std::vector<CardMask> hands;
  hands.reserve(count);
  std::vector<Card> deck(kNumCards);
  for (int i = 0; i < kNumCards; ++i) deck[i] = static_cast<Card>(i);
  for (std::size_t h = 0; h < count; ++h) {
    CardMask m = 0;
    for (int i = 0; i < 7; ++i) {
      std::uniform_int_distribution<int> pick(i, kNumCards - 1);
      std::swap(deck[i], deck[pick(rng)]);
      m |= card_bit(deck[i]);
    }
    hands.push_back(m);
  }

  const auto start = Clock::now();
  std::uint64_t checksum = 0;
  for (CardMask m : hands) checksum += evaluate(m);
  const double secs = seconds_since(start);
  std::printf("random 7-card hands : %10zu hands  %7.3f s  %8.1f M hands/s  (checksum %llu)\n",
              count, secs, static_cast<double>(count) / secs / 1e6,
              static_cast<unsigned long long>(checksum));
}

void bench_exhaustive_7() {
  const auto start = Clock::now();
  std::uint64_t count = 0;
  std::uint64_t checksum = 0;
  for (Card a = 0; a < kNumCards; ++a)
    for (Card b = a + 1; b < kNumCards; ++b)
      for (Card c = b + 1; c < kNumCards; ++c)
        for (Card d = c + 1; d < kNumCards; ++d)
          for (Card e = d + 1; e < kNumCards; ++e) {
            const CardMask base =
                card_bit(a) | card_bit(b) | card_bit(c) | card_bit(d) | card_bit(e);
            for (Card f = e + 1; f < kNumCards; ++f)
              for (Card g = f + 1; g < kNumCards; ++g) {
                checksum += evaluate(base | card_bit(f) | card_bit(g));
                ++count;
              }
          }
  const double secs = seconds_since(start);
  std::printf("all 7-card hands    : %10llu hands  %7.3f s  %8.1f M hands/s  (checksum %llu)\n",
              static_cast<unsigned long long>(count), secs, static_cast<double>(count) / secs / 1e6,
              static_cast<unsigned long long>(checksum));
}

void bench_equity(const char* label, std::vector<std::string> players, const std::string& board,
                  EquityMode mode, std::uint64_t iterations = 200'000) {
  std::vector<Range> ranges;
  for (const auto& p : players) ranges.push_back(Range::parse(p));
  EquityOptions opts;
  opts.mode = mode;
  opts.iterations = iterations;
  opts.seed = 1;
  const auto start = Clock::now();
  const auto r = calculate_equity(ranges, parse_cards(board), {}, opts);
  const double secs = seconds_since(start);
  std::printf("%-20s: %-6s %12llu samples %7.3f s  hero equity %.4f +/- %.4f\n", label,
              r.exact ? "exact" : "MC", static_cast<unsigned long long>(r.samples), secs,
              r.players[0].equity, r.players[0].std_error);
}

}  // namespace

int main(int argc, char** argv) {
  const std::size_t count = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : 20'000'000;
  bench_random_hands(count);
  bench_exhaustive_7();
  bench_equity("AA vs KK preflop", {"AA", "KK"}, "", EquityMode::Exact);
  bench_equity("AKs vs QQ preflop", {"AhKh", "QsQc"}, "", EquityMode::Auto);
  bench_equity("range vs range pre", {"22+,A2s+,KTo+", "random"}, "", EquityMode::Auto);
  bench_equity("range vs range flop", {"22+,A2s+,KTo+", "QQ+,AK"}, "Td7c2h", EquityMode::Auto);
  bench_equity("6-way preflop", {"AA", "KK", "QQ", "JJ", "TT", "random"}, "",
               EquityMode::MonteCarlo);
  return 0;
}
