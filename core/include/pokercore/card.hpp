#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace pokercore {

// Ranks: 0 = deuce ... 12 = ace. Suits: 0 = clubs, 1 = diamonds, 2 = hearts, 3 = spades.
inline constexpr int kNumRanks = 13;
inline constexpr int kNumSuits = 4;
inline constexpr int kNumCards = 52;

inline constexpr char kRankChars[] = "23456789TJQKA";
inline constexpr char kSuitChars[] = "cdhs";

// A card is an index in [0, 52): rank * 4 + suit.
using Card = std::uint8_t;

constexpr Card make_card(int rank, int suit) noexcept {
  return static_cast<Card>(rank * kNumSuits + suit);
}
constexpr int card_rank(Card c) noexcept { return c / kNumSuits; }
constexpr int card_suit(Card c) noexcept { return c % kNumSuits; }

// Set of cards as a bitmask: bit (suit * 16 + rank). Each suit uses a 13-bit lane,
// which lets the evaluator extract per-suit rank masks with a shift.
using CardMask = std::uint64_t;

constexpr CardMask card_bit(Card c) noexcept {
  return CardMask{1} << (card_suit(c) * 16 + card_rank(c));
}

// Parsing. Ranks accept upper or lower case ("Ah", "ah", "Td", "tD").
// Throws std::invalid_argument on malformed input.
int parse_rank(char ch);
int parse_suit(char ch);
Card parse_card(std::string_view text);
// Parses a run of cards, with or without separators: "AhKd", "Ah Kd Qs", "Ah,Kd".
std::vector<Card> parse_cards(std::string_view text);

std::string card_to_string(Card c);
std::string cards_to_string(const std::vector<Card>& cards);

CardMask to_mask(const std::vector<Card>& cards);

}  // namespace pokercore
