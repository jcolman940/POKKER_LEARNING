#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "pokercore/card.hpp"

namespace pokercore {

inline constexpr int kNumCombos = 1326;      // C(52, 2)
inline constexpr int kNumHandClasses = 169;  // 13 pairs + 78 suited + 78 offsuit

// A specific two-card holding, stored with hi > lo (card index order).
struct Combo {
  Card hi;
  Card lo;

  constexpr CardMask mask() const noexcept { return card_bit(hi) | card_bit(lo); }
  friend constexpr bool operator==(Combo, Combo) = default;
};

Combo make_combo(Card a, Card b);  // throws if a == b
int combo_index(Combo c) noexcept;  // [0, 1326)
Combo combo_from_index(int index) noexcept;
std::string combo_to_string(Combo c);

// Canonical starting-hand class (one cell of the 13x13 grid), e.g. "AKs", "T9o", "77".
struct HandClass {
  int high_rank;  // >= low_rank
  int low_rank;
  bool suited;    // always false for pairs

  bool is_pair() const noexcept { return high_rank == low_rank; }
  int num_combos() const noexcept;  // 6 / 4 / 12
  friend constexpr bool operator==(HandClass, HandClass) = default;
};

HandClass hand_class_of(Combo c) noexcept;
int hand_class_index(HandClass h) noexcept;  // [0, 169)
HandClass hand_class_from_index(int index) noexcept;
std::string hand_class_to_string(HandClass h);
std::vector<Combo> hand_class_combos(HandClass h);

struct WeightedCombo {
  Combo combo;
  double weight;
};

// A weighted range over the 1326 specific combos (weights in [0, 1]).
// Built from the 169-class grid or from standard text notation; card removal is
// applied when expanding with `combos(dead)`.
class Range {
 public:
  Range() { weights_.fill(0.0); }

  // Parses standard notation, comma separated, each item optionally followed by
  // ":weight" (later items override earlier ones):
  //   "AA", "AKs", "AKo", "AK"         single classes (AK = suited + offsuit)
  //   "22+", "A2s+", "KTo+", "QT+"     ladders (pairs up to AA, kicker up to below the top card)
  //   "99-55", "A5s-A2s", "KTo-K8o"    explicit spans with a common shape
  //   "AhKh"                           a specific combo
  //   "AA:1.0,AKs:0.5"                 PioViewer / ProPokerTools style weights
  // Whitespace is ignored. Throws std::invalid_argument on malformed input.
  static Range parse(std::string_view text);

  // A range holding exactly one combo with weight 1.
  static Range single(Combo c);

  double weight(Combo c) const noexcept { return weights_[combo_index(c)]; }
  void set_weight(Combo c, double w);
  void set_class_weight(HandClass h, double w);
  // Average weight over the combos of a class (what the 13x13 grid shows).
  double class_weight(HandClass h) const noexcept;

  // Combos with positive weight that do not intersect `dead`.
  std::vector<WeightedCombo> combos(CardMask dead = 0) const;

  // Sum of weights of the live combos (weighted combo count).
  double total_weight(CardMask dead = 0) const;

  bool empty() const noexcept;

 private:
  std::array<double, kNumCombos> weights_;
};

}  // namespace pokercore
