#include <algorithm>
#include <array>
#include <catch2/catch_test_macros.hpp>
#include <cstdint>
#include <functional>
#include <random>
#include <span>
#include <string_view>
#include <unordered_set>
#include <vector>

#include "pokercore/card.hpp"
#include "pokercore/evaluator.hpp"

using namespace pokercore;

namespace {

HandValue eval(std::string_view text) {
  const auto cards = parse_cards(text);
  return evaluate(std::span<const Card>(cards));
}

// Deliberately naive 5-card evaluator (rank counting + sorting), used as an
// independent reference. Produces the same HandValue layout as `evaluate`.
HandValue reference_eval5(const std::array<Card, 5>& cards) {
  std::array<int, kNumRanks> counts{};
  bool flush = true;
  for (Card c : cards) {
    ++counts[card_rank(c)];
    if (card_suit(c) != card_suit(cards[0])) flush = false;
  }
  // Distinct ranks ordered by (count desc, rank desc).
  std::vector<std::pair<int, int>> groups;
  for (int r = 0; r < kNumRanks; ++r) {
    if (counts[r]) groups.emplace_back(counts[r], r);
  }
  std::sort(groups.begin(), groups.end(), std::greater<>());

  int straight_top = -1;
  if (groups.size() == 5) {
    if (groups[0].second - groups[4].second == 4) straight_top = groups[0].second;
    if (groups[0].second == 12 && groups[1].second == 3) straight_top = 3;  // wheel
  }

  Category cat;
  if (straight_top >= 0 && flush) {
    cat = Category::StraightFlush;
  } else if (groups[0].first == 4) {
    cat = Category::Quads;
  } else if (groups[0].first == 3 && groups[1].first == 2) {
    cat = Category::FullHouse;
  } else if (flush) {
    cat = Category::Flush;
  } else if (straight_top >= 0) {
    cat = Category::Straight;
  } else if (groups[0].first == 3) {
    cat = Category::Trips;
  } else if (groups[0].first == 2 && groups[1].first == 2) {
    cat = Category::TwoPair;
  } else if (groups[0].first == 2) {
    cat = Category::Pair;
  } else {
    cat = Category::HighCard;
  }

  HandValue v = static_cast<HandValue>(cat) << 20;
  if (cat == Category::StraightFlush || cat == Category::Straight) {
    return v | static_cast<HandValue>(straight_top) << 16;
  }
  int slot = 4;
  for (const auto& [count, rank] : groups) {
    v |= static_cast<HandValue>(rank) << (4 * slot--);
  }
  return v;
}

// Best 5-card hand among 6 or 7 cards, by brute force over subsets.
HandValue reference_best(const std::vector<Card>& cards) {
  const auto n = cards.size();
  HandValue best = 0;
  std::array<Card, 5> pick{};
  for (std::size_t a = 0; a < n; ++a)
    for (std::size_t b = a + 1; b < n; ++b)
      for (std::size_t c = b + 1; c < n; ++c)
        for (std::size_t d = c + 1; d < n; ++d)
          for (std::size_t e = d + 1; e < n; ++e) {
            pick = {cards[a], cards[b], cards[c], cards[d], cards[e]};
            best = std::max(best, reference_eval5(pick));
          }
  return best;
}

}  // namespace

TEST_CASE("all 2,598,960 five-card hands: category distribution and 7,462 classes",
          "[evaluator]") {
  std::array<std::uint64_t, kNumCategories> by_category{};
  std::unordered_set<HandValue> distinct;
  std::uint64_t total = 0;
  std::uint64_t mismatches = 0;

  for (Card a = 0; a < kNumCards; ++a)
    for (Card b = a + 1; b < kNumCards; ++b)
      for (Card c = b + 1; c < kNumCards; ++c)
        for (Card d = c + 1; d < kNumCards; ++d)
          for (Card e = d + 1; e < kNumCards; ++e) {
            const CardMask m =
                card_bit(a) | card_bit(b) | card_bit(c) | card_bit(d) | card_bit(e);
            const HandValue v = evaluate(m);
            ++by_category[static_cast<int>(category(v))];
            distinct.insert(v);
            ++total;
            if (v != reference_eval5({a, b, c, d, e})) ++mismatches;
          }

  CHECK(total == 2'598'960);
  CHECK(mismatches == 0);
  CHECK(by_category[static_cast<int>(Category::StraightFlush)] == 40);
  CHECK(by_category[static_cast<int>(Category::Quads)] == 624);
  CHECK(by_category[static_cast<int>(Category::FullHouse)] == 3'744);
  CHECK(by_category[static_cast<int>(Category::Flush)] == 5'108);
  CHECK(by_category[static_cast<int>(Category::Straight)] == 10'200);
  CHECK(by_category[static_cast<int>(Category::Trips)] == 54'912);
  CHECK(by_category[static_cast<int>(Category::TwoPair)] == 123'552);
  CHECK(by_category[static_cast<int>(Category::Pair)] == 1'098'240);
  CHECK(by_category[static_cast<int>(Category::HighCard)] == 1'302'540);
  CHECK(distinct.size() == 7'462);
}

TEST_CASE("all 133,784,560 seven-card hands: category distribution", "[evaluator][exhaustive7]") {
  std::array<std::uint64_t, kNumCategories> by_category{};
  std::uint64_t total = 0;
  std::vector<std::uint8_t> seen(std::size_t{1} << 24, 0);  // HandValue fits in 24 bits

  for (Card a = 0; a < kNumCards; ++a) {
    const CardMask ma = card_bit(a);
    for (Card b = a + 1; b < kNumCards; ++b) {
      const CardMask mb = ma | card_bit(b);
      for (Card c = b + 1; c < kNumCards; ++c) {
        const CardMask mc = mb | card_bit(c);
        for (Card d = c + 1; d < kNumCards; ++d) {
          const CardMask md = mc | card_bit(d);
          for (Card e = d + 1; e < kNumCards; ++e) {
            const CardMask me = md | card_bit(e);
            for (Card f = e + 1; f < kNumCards; ++f) {
              const CardMask mf = me | card_bit(f);
              for (Card g = f + 1; g < kNumCards; ++g) {
                const HandValue v = evaluate(mf | card_bit(g));
                ++by_category[static_cast<int>(category(v))];
                ++total;
                seen[v] = 1;
              }
            }
          }
        }
      }
    }
  }

  // Reference counts for 7-card hands (best five of seven).
  CHECK(total == 133'784'560);
  CHECK(by_category[static_cast<int>(Category::StraightFlush)] == 41'584);
  CHECK(by_category[static_cast<int>(Category::Quads)] == 224'848);
  CHECK(by_category[static_cast<int>(Category::FullHouse)] == 3'473'184);
  CHECK(by_category[static_cast<int>(Category::Flush)] == 4'047'644);
  CHECK(by_category[static_cast<int>(Category::Straight)] == 6'180'020);
  CHECK(by_category[static_cast<int>(Category::Trips)] == 6'461'620);
  CHECK(by_category[static_cast<int>(Category::TwoPair)] == 31'433'400);
  CHECK(by_category[static_cast<int>(Category::Pair)] == 58'627'800);
  CHECK(by_category[static_cast<int>(Category::HighCard)] == 23'294'460);
  // Best-of-seven can never be the weakest 5-card hands (e.g. 7-5-4-3-2), so only
  // 4,824 of the 7,462 classes appear.
  CHECK(std::count(seen.begin(), seen.end(), std::uint8_t{1}) == 4'824);
}

TEST_CASE("6 and 7 card evaluation matches brute force over 5-card subsets", "[evaluator]") {
  std::mt19937_64 rng(12345);
  std::array<Card, kNumCards> deck{};
  for (int i = 0; i < kNumCards; ++i) deck[i] = static_cast<Card>(i);

  for (int n : {6, 7}) {
    for (int iter = 0; iter < 200'000; ++iter) {
      for (int i = 0; i < n; ++i) {
        std::uniform_int_distribution<int> pick(i, kNumCards - 1);
        std::swap(deck[i], deck[pick(rng)]);
      }
      const std::vector<Card> cards(deck.begin(), deck.begin() + n);
      const HandValue expected = reference_best(cards);
      const HandValue actual = evaluate(std::span<const Card>(cards));
      if (actual != expected) {
        FAIL("mismatch for " << cards_to_string(cards));
      }
    }
  }
}

TEST_CASE("hand ordering spot checks", "[evaluator]") {
  CHECK(category(eval("AsKsQsJsTs")) == Category::StraightFlush);
  CHECK(category(eval("5d4d3d2dAd")) == Category::StraightFlush);
  CHECK(eval("5d4d3d2dAd") < eval("6h5h4h3h2h"));  // steel wheel is the lowest SF
  CHECK(eval("Ah2c3d4s5h") < eval("2c3d4s5h6h"));  // wheel is the lowest straight
  CHECK(category(eval("AhKhQhJh9c")) == Category::HighCard);
  CHECK(category(eval("QhKhAh2c3d")) == Category::HighCard);  // no wrap-around straight

  // Kickers matter.
  CHECK(eval("AsAhKd7c2s") > eval("AdAcQs7h2d"));
  CHECK(eval("AsAhKd7c3s") > eval("AdAcKs7h2d"));
  CHECK(eval("AsAhKd7c2s") == eval("AdAcKs7h2d"));  // exact tie
  CHECK(eval("KsKhKd2c2s") > eval("QsQhQdAcAs"));    // full house: trips first

  // 7 cards: board plays, flush beats straight, best two of three pairs.
  CHECK(eval("2c3dAsKsQsJsTs") == eval("4h5hAsKsQsJsTs"));
  CHECK(category(eval("9h8h7h6c5d2h3h")) == Category::Flush);
  CHECK(eval("AsAhKsKhQsQh2c") == eval("AdAcKdKcQdQc3h"));  // two pair AAKK with Q kicker
  CHECK(category(eval("AsAhAdKsKhKd2c")) == Category::FullHouse);
  CHECK(eval("AsAhAdKsKhKd2c") == eval("AsAhAdKsKh3c2c"));  // AAAKK either way
}

TEST_CASE("span evaluation validates input", "[evaluator]") {
  const std::vector<Card> four = parse_cards("AsKsQsJs");
  CHECK_THROWS_AS(evaluate(std::span<const Card>(four)), std::invalid_argument);
  const std::vector<Card> dup = {0, 0, 1, 2, 3};
  CHECK_THROWS_AS(evaluate(std::span<const Card>(dup)), std::invalid_argument);
  CHECK(category_name(Category::FullHouse) == "full_house");
}
