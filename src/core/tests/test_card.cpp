#include <catch2/catch_test_macros.hpp>
#include <stdexcept>

#include "pokercore/card.hpp"

using namespace pokercore;

TEST_CASE("card parsing and formatting round-trip", "[card]") {
  for (int i = 0; i < kNumCards; ++i) {
    const auto c = static_cast<Card>(i);
    CHECK(parse_card(card_to_string(c)) == c);
  }
  CHECK(parse_card("Ah") == make_card(12, 2));
  CHECK(parse_card("2c") == make_card(0, 0));
  CHECK(parse_card("tS") == make_card(8, 3));
}

TEST_CASE("parse_cards accepts separators and rejects bad input", "[card]") {
  CHECK(parse_cards("AhKd").size() == 2);
  CHECK(cards_to_string(parse_cards("Ah Kd,Qs")) == "AhKdQs");
  CHECK(parse_cards("").empty());
  CHECK_THROWS_AS(parse_card("1h"), std::invalid_argument);
  CHECK_THROWS_AS(parse_card("Ax"), std::invalid_argument);
  CHECK_THROWS_AS(parse_cards("AhK"), std::invalid_argument);
  CHECK_THROWS_AS(parse_cards("AhAh"), std::invalid_argument);
}

TEST_CASE("card masks use one 16-bit lane per suit", "[card]") {
  CHECK(card_bit(parse_card("2c")) == 1);
  CHECK(card_bit(parse_card("Ac")) == (1ULL << 12));
  CHECK(card_bit(parse_card("2d")) == (1ULL << 16));
  CHECK(card_bit(parse_card("As")) == (1ULL << 60));
  CHECK(to_mask(parse_cards("2c2d")) == ((1ULL << 0) | (1ULL << 16)));
}
