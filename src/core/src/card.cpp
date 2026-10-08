#include "pokercore/card.hpp"

#include <cctype>
#include <stdexcept>

namespace pokercore {

int parse_rank(char ch) {
  const char up = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
  for (int r = 0; r < kNumRanks; ++r) {
    if (kRankChars[r] == up) return r;
  }
  throw std::invalid_argument(std::string("invalid rank: '") + ch + "'");
}

int parse_suit(char ch) {
  const char low = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
  for (int s = 0; s < kNumSuits; ++s) {
    if (kSuitChars[s] == low) return s;
  }
  throw std::invalid_argument(std::string("invalid suit: '") + ch + "'");
}

Card parse_card(std::string_view text) {
  if (text.size() != 2) {
    throw std::invalid_argument("invalid card: '" + std::string(text) + "'");
  }
  return make_card(parse_rank(text[0]), parse_suit(text[1]));
}

std::vector<Card> parse_cards(std::string_view text) {
  std::vector<Card> cards;
  CardMask seen = 0;
  std::size_t i = 0;
  while (i < text.size()) {
    const char ch = text[i];
    if (ch == ' ' || ch == ',' || ch == '\t' || ch == '\n' || ch == '\r') {
      ++i;
      continue;
    }
    if (i + 1 >= text.size()) {
      throw std::invalid_argument("invalid cards: '" + std::string(text) + "'");
    }
    const Card c = parse_card(text.substr(i, 2));
    if (seen & card_bit(c)) {
      throw std::invalid_argument("duplicate card: " + card_to_string(c));
    }
    seen |= card_bit(c);
    cards.push_back(c);
    i += 2;
  }
  return cards;
}

std::string card_to_string(Card c) {
  return {kRankChars[card_rank(c)], kSuitChars[card_suit(c)]};
}

std::string cards_to_string(const std::vector<Card>& cards) {
  std::string out;
  out.reserve(cards.size() * 2);
  for (Card c : cards) out += card_to_string(c);
  return out;
}

CardMask to_mask(const std::vector<Card>& cards) {
  CardMask m = 0;
  for (Card c : cards) m |= card_bit(c);
  return m;
}

}  // namespace pokercore
