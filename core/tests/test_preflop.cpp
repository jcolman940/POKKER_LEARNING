#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include "pokercore/equity.hpp"
#include "pokercore/preflop.hpp"
#include "pokercore/range.hpp"

using namespace pokercore;
using Catch::Approx;

namespace {

int idx(std::string_view name) {
  for (int i = 0; i < kNumHandClasses; ++i) {
    if (hand_class_to_string(hand_class_from_index(i)) == name) return i;
  }
  FAIL("unknown class " << name);
  return -1;
}

}  // namespace

TEST_CASE("preflop class equity matrix", "[preflop]") {
  const auto m = preflop_equity_matrix(4'000, 1, 0);
  REQUIRE(m.size() == static_cast<std::size_t>(kNumHandClasses * kNumHandClasses));
  auto e = [&](std::string_view a, std::string_view b) {
    return m[static_cast<std::size_t>(idx(a)) * kNumHandClasses + idx(b)];
  };

  CHECK(e("AA", "AA") == 0.5);
  CHECK(e("AA", "KK") + e("KK", "AA") == Approx(1.0));

  // Against the general equity engine (4,000 trials per pair: standard error ~0.8%).
  EquityOptions reference;
  reference.mode = EquityMode::MonteCarlo;
  reference.iterations = 200'000;
  reference.seed = 3;
  for (auto [a, b] : {std::pair{"AA", "KK"}, std::pair{"AKs", "QQ"}, std::pair{"72o", "AKo"}}) {
    const auto r = calculate_equity({Range::parse(a), Range::parse(b)}, {}, {}, reference);
    CHECK(e(a, b) == Approx(r.players[0].equity).margin(0.03));
  }

  // Same seed, different thread counts: identical results.
  const auto single = preflop_equity_matrix(500, 9, 1);
  const auto multi = preflop_equity_matrix(500, 9, 4);
  CHECK(single == multi);
}
