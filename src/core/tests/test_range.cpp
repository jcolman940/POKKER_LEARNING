#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>
#include <set>
#include <stdexcept>
#include <string_view>

#include "pokercore/range.hpp"

using namespace pokercore;
using Catch::Approx;

namespace {

std::size_t count(std::string_view text, CardMask dead = 0) {
  return Range::parse(text).combos(dead).size();
}

HandClass hc(std::string_view text) {
  const auto combos = Range::parse(text).combos();
  REQUIRE_FALSE(combos.empty());
  return hand_class_of(combos.front().combo);
}

}  // namespace

TEST_CASE("combo indexing covers all 1326 combos exactly once", "[range]") {
  std::set<int> seen;
  for (int i = 0; i < kNumCombos; ++i) {
    const Combo c = combo_from_index(i);
    CHECK(c.hi > c.lo);
    CHECK(combo_index(c) == i);
    seen.insert(combo_index(c));
  }
  CHECK(seen.size() == kNumCombos);
  CHECK(make_combo(0, 5) == make_combo(5, 0));
  CHECK_THROWS_AS(make_combo(3, 3), std::invalid_argument);
}

TEST_CASE("169 hand classes map to 1326 combos", "[range]") {
  std::set<int> indices;
  int total = 0;
  for (int i = 0; i < kNumHandClasses; ++i) {
    const HandClass h = hand_class_from_index(i);
    CHECK(hand_class_index(h) == i);
    indices.insert(i);
    const auto combos = hand_class_combos(h);
    CHECK(static_cast<int>(combos.size()) == h.num_combos());
    for (Combo c : combos) CHECK(hand_class_of(c) == h);
    total += static_cast<int>(combos.size());
  }
  CHECK(indices.size() == kNumHandClasses);
  CHECK(total == kNumCombos);
  CHECK(hand_class_to_string(hand_class_from_index(0)) == "AA");
  CHECK(hand_class_to_string(hand_class_from_index(1)) == "AKs");
  CHECK(hand_class_to_string(hand_class_from_index(13)) == "AKo");
  CHECK(hand_class_to_string(hand_class_from_index(168)) == "22");
}

TEST_CASE("range notation: single classes", "[range]") {
  CHECK(count("AA") == 6);
  CHECK(count("AKs") == 4);
  CHECK(count("AKo") == 12);
  CHECK(count("AK") == 16);
  CHECK(count("KA") == 16);
  CHECK(count("aks") == 4);
  CHECK(hand_class_to_string(hc("T9s")) == "T9s");
  CHECK(count("random") == 1326);
}

TEST_CASE("range notation: ladders and spans", "[range]") {
  CHECK(count("22+") == 13 * 6);
  CHECK(count("TT+") == 5 * 6);
  CHECK(count("A2s+") == 12 * 4);
  CHECK(count("KTo+") == 3 * 12);  // KTo, KJo, KQo
  CHECK(count("QT+") == 2 * 16);
  CHECK(count("99-55") == 5 * 6);
  CHECK(count("55-99") == 5 * 6);
  CHECK(count("A5s-A2s") == 4 * 4);
  CHECK(count("T9s-65s") == 5 * 4);
  CHECK(count("22+, A2s+, KTo+") == 78 + 48 + 36);
}

TEST_CASE("range notation: specific combos and weights", "[range]") {
  const Range r = Range::parse("AhKh");
  CHECK(r.combos().size() == 1);
  CHECK(combo_to_string(r.combos().front().combo) == "AhKh");

  const Range w = Range::parse("AA:1.0,AKs:0.5, KK:0.25");
  CHECK(w.class_weight({12, 12, false}) == Approx(1.0));
  CHECK(w.class_weight({12, 11, true}) == Approx(0.5));
  CHECK(w.class_weight({11, 11, false}) == Approx(0.25));
  CHECK(w.total_weight() == Approx(6 + 2 + 1.5));

  // Later items override earlier ones.
  const Range o = Range::parse("QQ+, KK:0.5");
  CHECK(o.class_weight({11, 11, false}) == Approx(0.5));
  CHECK(o.class_weight({12, 12, false}) == Approx(1.0));

  // A weight of zero removes the class.
  CHECK(count("22+, 22:0") == 72);
}

TEST_CASE("card removal drops blocked combos", "[range]") {
  const CardMask ah = card_bit(parse_card("Ah"));
  CHECK(count("AA", ah) == 3);
  CHECK(count("AKs", ah) == 3);
  CHECK(count("AKo", ah) == 9);
  CHECK(count("AA", to_mask(parse_cards("AhAs"))) == 1);
  CHECK(count("random", to_mask(parse_cards("AhKdQc"))) == 1176);  // C(49, 2)
}

TEST_CASE("range notation rejects malformed input", "[range]") {
  CHECK_THROWS_AS(Range::parse("AAs"), std::invalid_argument);
  CHECK_THROWS_AS(Range::parse("AKx"), std::invalid_argument);
  CHECK_THROWS_AS(Range::parse("A"), std::invalid_argument);
  CHECK_THROWS_AS(Range::parse("AK:1.5"), std::invalid_argument);
  CHECK_THROWS_AS(Range::parse("AK:abc"), std::invalid_argument);
  CHECK_THROWS_AS(Range::parse("AKs-QJo"), std::invalid_argument);
  CHECK_THROWS_AS(Range::parse("AKs-T8s"), std::invalid_argument);
  CHECK_THROWS_AS(Range::parse("AhAh"), std::invalid_argument);
  CHECK(Range::parse("").empty());
  CHECK(Range::parse(" , ").empty());
}
