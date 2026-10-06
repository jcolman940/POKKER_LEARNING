#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>
#include <numeric>
#include <stdexcept>
#include <vector>

#include "pokercore/icm.hpp"

using namespace pokercore;
using Catch::Approx;

TEST_CASE("ICM basic properties", "[icm]") {
  // Winner-take-all is proportional to chips.
  const auto wta = icm_equity({1000, 3000}, {100});
  CHECK(wta[0] == Approx(25));
  CHECK(wta[1] == Approx(75));

  // Equal stacks split the prize pool evenly.
  const auto even = icm_equity({1000, 1000, 1000}, {50, 30, 20});
  for (double v : even) CHECK(v == Approx(100.0 / 3));

  // Total equity equals the prizes that can be awarded.
  const auto r = icm_equity({5000, 3000, 1500, 500}, {50, 30, 20});
  CHECK(std::accumulate(r.begin(), r.end(), 0.0) == Approx(100));
  CHECK(r[0] > r[1]);
  CHECK(r[1] > r[2]);
  CHECK(r[2] > r[3]);
  // Chip leader gets less than its chip share of the pool: the ICM effect.
  CHECK(r[0] < 100 * 5000.0 / 10000);
}

TEST_CASE("ICM matches a hand-computed 3-player example", "[icm]") {
  // Stacks 50/30/20, payouts 70/30.
  // P(A 1st) = .5; P(A 2nd) = .3*(50/70) + .2*(50/80) = .339285714...
  const auto r = icm_equity({50, 30, 20}, {70, 30});
  CHECK(r[0] == Approx(0.5 * 70 + (0.3 * 50.0 / 70 + 0.2 * 50.0 / 80) * 30));
  CHECK(r[0] + r[1] + r[2] == Approx(100));
}

TEST_CASE("ICM handles busted players, short payouts and limits", "[icm]") {
  const auto r = icm_equity({0, 100, 100}, {60, 40, 10});
  CHECK(r[0] == 0.0);
  CHECK(r[1] == Approx(50));  // only two places can still be awarded
  CHECK(icm_equity({}, {10}).empty());
  CHECK(icm_equity({100, 0}, {10, 5})[0] == Approx(10));

  std::vector<double> many(13, 100.0);
  CHECK_THROWS_AS(icm_equity(many, {100}), std::invalid_argument);
  CHECK_THROWS_AS(icm_equity({1, 2}, {-1}), std::invalid_argument);

  std::vector<double> twelve(12, 100.0);
  const auto t = icm_equity(twelve, {50, 30, 20});
  CHECK(t[0] == Approx(100.0 / 12));
}
