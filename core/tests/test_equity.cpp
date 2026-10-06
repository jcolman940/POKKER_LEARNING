#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>
#include <cmath>
#include <initializer_list>
#include <string_view>
#include <tuple>
#include <vector>
#include <stdexcept>

#include "pokercore/equity.hpp"

using namespace pokercore;
using Catch::Approx;

namespace {

std::vector<Range> ranges(std::initializer_list<std::string_view> texts) {
  std::vector<Range> out;
  for (auto t : texts) out.push_back(Range::parse(t));
  return out;
}

EquityResult run(std::initializer_list<std::string_view> players, std::string_view board = "",
                 EquityOptions opts = {}) {
  return calculate_equity(ranges(players), parse_cards(board), {}, opts);
}

EquityOptions exact() {
  EquityOptions o;
  o.mode = EquityMode::Exact;
  return o;
}

EquityOptions monte_carlo(std::uint64_t iterations, std::uint64_t seed = 42) {
  EquityOptions o;
  o.mode = EquityMode::MonteCarlo;
  o.iterations = iterations;
  o.seed = seed;
  return o;
}

void check_consistent(const EquityResult& r) {
  double equity_sum = 0.0;
  for (const auto& p : r.players) {
    CHECK(p.win + p.tie + p.lose == Approx(1.0));
    CHECK(p.equity >= p.win - 1e-12);
    CHECK(p.equity <= p.win + p.tie + 1e-12);
    equity_sum += p.equity;
  }
  CHECK(equity_sum == Approx(1.0));
}

}  // namespace

TEST_CASE("AA vs KK preflop is about 82/18", "[equity]") {
  const auto r = run({"AA", "KK"}, "", exact());
  REQUIRE(r.exact);
  CHECK(r.players[0].equity == Approx(0.82).margin(0.01));
  CHECK(r.players[1].equity == Approx(0.18).margin(0.01));
  CHECK(r.players[0].std_error == 0.0);
  check_consistent(r);
}

TEST_CASE("turn spot with a known number of outs is exact", "[equity]") {
  // AA vs a set of kings on the turn: only the two remaining aces win for AA.
  const auto r = run({"AhAd", "KcKd"}, "Kh7s2c3d");
  REQUIRE(r.exact);
  CHECK(r.samples == 44);
  CHECK(r.players[0].equity == Approx(2.0 / 44.0));
  CHECK(r.players[1].equity == Approx(42.0 / 44.0));
  CHECK(r.players[0].tie == 0.0);
}

TEST_CASE("river is a single showdown", "[equity]") {
  const auto win = run({"JsTs", "random"}, "AsKsQs2d3c");
  CHECK(win.players[0].equity == Approx(1.0));
  CHECK(win.players[0].win == Approx(1.0));

  const auto split = run({"2c2d", "3c3d"}, "AsKsQsJsTs");
  CHECK(split.players[0].tie == Approx(1.0));
  CHECK(split.players[0].equity == Approx(0.5));
  CHECK(split.players[1].equity == Approx(0.5));
}

TEST_CASE("symmetry: A vs B equals 1 - (B vs A)", "[equity]") {
  for (const auto& [a, b, board] : {std::tuple{"AhKh", "QsQc", ""},
                                    std::tuple{"JJ+,AKs", "22-99,ATs+", "Td7c2h"},
                                    std::tuple{"T9s", "random", "8s7d2c4h"}}) {
    const auto ab = run({a, b}, board);
    const auto ba = run({b, a}, board);
    REQUIRE(ab.exact);
    CHECK(ab.players[0].equity == Approx(1.0 - ba.players[0].equity));
    CHECK(ab.players[0].win == Approx(ba.players[0].lose));
    CHECK(ab.players[0].tie == Approx(ba.players[0].tie));
    check_consistent(ab);
  }
}

TEST_CASE("Monte Carlo agrees with exact enumeration within its standard error", "[equity]") {
  const auto ex = run({"AKs", "QQ"}, "", exact());
  const auto mc = run({"AKs", "QQ"}, "", monte_carlo(400'000));
  REQUIRE_FALSE(mc.exact);
  CHECK(mc.samples == 400'000);
  for (std::size_t i = 0; i < 2; ++i) {
    const double se = mc.players[i].std_error;
    CHECK(se > 0.0);
    CHECK(se < 0.002);
    CHECK(std::abs(mc.players[i].equity - ex.players[i].equity) < 4.0 * se);
  }
  check_consistent(mc);
}

TEST_CASE("Monte Carlo is reproducible with a fixed seed", "[equity]") {
  const auto a = run({"22+,A2s+", "random", "KQo"}, "", monte_carlo(20'000, 7));
  const auto b = run({"22+,A2s+", "random", "KQo"}, "", monte_carlo(20'000, 7));
  const auto c = run({"22+,A2s+", "random", "KQo"}, "", monte_carlo(20'000, 8));
  CHECK(a.seed == 7);
  CHECK(a.players[0].equity == b.players[0].equity);
  CHECK(a.players[0].equity != c.players[0].equity);
}

TEST_CASE("auto mode picks exact or Monte Carlo by workload", "[equity]") {
  EquityOptions opts;
  opts.iterations = 5'000;
  opts.seed = 1;
  // One combo each preflop: C(48, 5) runouts fits the default limit.
  CHECK(run({"AhKh", "QsQc"}, "", opts).exact);
  // Wide ranges preflop do not.
  const auto wide = run({"22+,A2s+", "random"}, "", opts);
  CHECK_FALSE(wide.exact);
  CHECK(wide.samples == 5'000);
  CHECK(wide.seed == 1);
  // Range vs range on the river is cheap again.
  CHECK(run({"22+,A2s+", "random"}, "AsKd7c4h2s", opts).exact);
}

TEST_CASE("multiway equity up to 10 players", "[equity]") {
  const auto six = run({"AA", "KK", "QQ", "JJ", "TT", "99"}, "", monte_carlo(50'000));
  REQUIRE(six.players.size() == 6);
  check_consistent(six);
  CHECK(six.players[0].equity > six.players[1].equity);

  const auto ten = run({"random", "random", "random", "random", "random", "random", "random",
                        "random", "random", "random"},
                       "", monte_carlo(20'000));
  check_consistent(ten);
  for (const auto& p : ten.players) CHECK(p.equity == Approx(0.1).margin(0.015));

  const auto three = run({"AhAd", "KhKd", "QhQd"}, "2c3c4s", exact());
  REQUIRE(three.exact);
  check_consistent(three);
}

TEST_CASE("card removal between players and against the board", "[equity]") {
  // Villain's AA range collapses to the one combo hero does not block.
  const auto r = run({"AhAs", "AA"}, "", exact());
  CHECK(r.players[0].tie > 0.9);

  // Dead cards are removed from both ranges and runouts.
  const auto dead = calculate_equity(ranges({"AhAd", "KcKd"}), parse_cards("Kh7s2c3d"),
                                     parse_cards("As"), exact());
  CHECK(dead.samples == 43);
  CHECK(dead.players[0].equity == Approx(1.0 / 43.0));
}

TEST_CASE("equity input validation", "[equity]") {
  CHECK_THROWS_AS(run({"AA"}), std::invalid_argument);                // one player
  CHECK_THROWS_AS(run({"AA", "KK"}, "AsKs"), std::invalid_argument);  // 2-card board
  CHECK_THROWS_AS(run({"AA", "KK"}, "AsAhAd"), std::invalid_argument);  // AA fully blocked
  CHECK_THROWS_AS(run({"AhKh", "AhQd"}, "", exact()), std::runtime_error);  // same card twice
  CHECK_THROWS_AS(calculate_equity(ranges({"AA", "KK"}), parse_cards("2c3c4c"), parse_cards("2c")),
                  std::invalid_argument);  // dead card on the board

  std::vector<Range> eleven(11, Range::parse("random"));
  CHECK_THROWS_AS(calculate_equity(eleven, {}), std::invalid_argument);
}

TEST_CASE("hand strength against a range on the current board", "[equity]") {
  const Combo aa = make_combo(parse_card("Ah"), parse_card("Ad"));
  // Top set beats every pair below; 77 and 22 make smaller sets and still lose.
  const auto s = hand_strength(aa, Range::parse("KK-22"), parse_cards("As7c2d"));
  CHECK(s.win == Approx(1.0));
  CHECK(s.win + s.tie + s.lose == Approx(1.0));
  CHECK(s.combos == Approx(10 * 6 + 3 + 3));  // 77 and 22 each lose combos to the board

  const auto behind = hand_strength(make_combo(parse_card("Kh"), parse_card("Kd")), Range::parse("AA"),
                                    parse_cards("Ac7c2d"));
  CHECK(behind.lose == Approx(1.0));
  CHECK(behind.combos == Approx(3));

  CHECK_THROWS_AS(hand_strength(aa, Range::parse("KK"), parse_cards("AsKs")), std::invalid_argument);
  CHECK_THROWS_AS(hand_strength(aa, Range::parse("KK"), parse_cards("Ah7c2d")),
                  std::invalid_argument);
}
