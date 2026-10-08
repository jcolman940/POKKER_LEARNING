#include "pokercore/evaluator.hpp"

#include <stdexcept>
#include <string>

namespace pokercore {

std::string_view category_name(Category c) noexcept {
  switch (c) {
    case Category::HighCard: return "high_card";
    case Category::Pair: return "pair";
    case Category::TwoPair: return "two_pair";
    case Category::Trips: return "trips";
    case Category::Straight: return "straight";
    case Category::Flush: return "flush";
    case Category::FullHouse: return "full_house";
    case Category::Quads: return "quads";
    case Category::StraightFlush: return "straight_flush";
  }
  return "unknown";
}

HandValue evaluate(std::span<const Card> cards) {
  if (cards.size() < 5 || cards.size() > 7) {
    throw std::invalid_argument("evaluate expects 5 to 7 cards, got " +
                                std::to_string(cards.size()));
  }
  CardMask mask = 0;
  for (Card c : cards) {
    if (c >= kNumCards) throw std::invalid_argument("card index out of range");
    const CardMask bit = card_bit(c);
    if (mask & bit) throw std::invalid_argument("duplicate card: " + card_to_string(c));
    mask |= bit;
  }
  return evaluate(mask);
}

}  // namespace pokercore
