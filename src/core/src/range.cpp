#include "pokercore/range.hpp"

#include <algorithm>
#include <cctype>
#include <charconv>
#include <stdexcept>

namespace pokercore {

namespace {

const std::array<Combo, kNumCombos>& combo_table() {
  static const auto table = [] {
    std::array<Combo, kNumCombos> t{};
    for (int hi = 1; hi < kNumCards; ++hi) {
      for (int lo = 0; lo < hi; ++lo) {
        t[hi * (hi - 1) / 2 + lo] = Combo{static_cast<Card>(hi), static_cast<Card>(lo)};
      }
    }
    return t;
  }();
  return table;
}

[[noreturn]] void fail(std::string_view token, std::string_view why) {
  throw std::invalid_argument("invalid range item '" + std::string(token) + "': " +
                              std::string(why));
}

bool is_suit_char(char ch) {
  const char low = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
  return low == 'c' || low == 'd' || low == 'h' || low == 's';
}

enum class Shape { Pair, Suited, Offsuit, Both };

struct ClassPattern {
  int high;
  int low;
  Shape shape;
};

ClassPattern parse_class_pattern(std::string_view item, std::string_view token) {
  if (item.size() < 2 || item.size() > 3) fail(token, "expected a hand like AKs, T9o, 77");
  int a = 0;
  int b = 0;
  try {
    a = parse_rank(item[0]);
    b = parse_rank(item[1]);
  } catch (const std::invalid_argument&) {
    fail(token, "bad rank");
  }
  const int high = std::max(a, b);
  const int low = std::min(a, b);
  if (high == low) {
    if (item.size() == 3) fail(token, "pairs cannot be suited or offsuit");
    return {high, low, Shape::Pair};
  }
  if (item.size() == 2) return {high, low, Shape::Both};
  const char s = static_cast<char>(std::tolower(static_cast<unsigned char>(item[2])));
  if (s == 's') return {high, low, Shape::Suited};
  if (s == 'o') return {high, low, Shape::Offsuit};
  fail(token, "expected 's' or 'o' suffix");
}

void apply_class(Range& range, int high, int low, Shape shape, double w) {
  if (shape == Shape::Pair) {
    range.set_class_weight({high, high, false}, w);
    return;
  }
  if (shape == Shape::Suited || shape == Shape::Both) range.set_class_weight({high, low, true}, w);
  if (shape == Shape::Offsuit || shape == Shape::Both) range.set_class_weight({high, low, false}, w);
}

double parse_weight(std::string_view text, std::string_view token) {
  double w = 0.0;
  const auto* begin = text.data();
  const auto* end = text.data() + text.size();
  const auto [ptr, ec] = std::from_chars(begin, end, w);
  if (ec != std::errc() || ptr != end) fail(token, "bad weight");
  if (w < 0.0 || w > 1.0) fail(token, "weight must be within [0, 1]");
  return w;
}

void apply_item(Range& range, std::string_view item, double w, std::string_view token) {
  if (item == "random" || item == "any") {
    for (int i = 0; i < kNumCombos; ++i) range.set_weight(combo_from_index(i), w);
    return;
  }

  // Specific combo, e.g. "AhKh".
  if (item.size() == 4 && is_suit_char(item[1]) && is_suit_char(item[3])) {
    try {
      range.set_weight(make_combo(parse_card(item.substr(0, 2)), parse_card(item.substr(2, 2))), w);
    } catch (const std::invalid_argument& e) {
      fail(token, e.what());
    }
    return;
  }

  // Span, e.g. "99-55", "A5s-A2s", "T9s-65s".
  if (const auto dash = item.find('-'); dash != std::string_view::npos) {
    const ClassPattern from = parse_class_pattern(item.substr(0, dash), token);
    const ClassPattern to = parse_class_pattern(item.substr(dash + 1), token);
    if (from.shape != to.shape) fail(token, "both ends must have the same shape");
    if (from.shape == Shape::Pair) {
      for (int r = std::min(from.high, to.high); r <= std::max(from.high, to.high); ++r) {
        apply_class(range, r, r, Shape::Pair, w);
      }
      return;
    }
    if (from.high == to.high) {
      for (int l = std::min(from.low, to.low); l <= std::max(from.low, to.low); ++l) {
        apply_class(range, from.high, l, from.shape, w);
      }
      return;
    }
    const int gap = from.high - from.low;
    if (gap != to.high - to.low) fail(token, "span ends must share the top card or the gap");
    for (int h = std::min(from.high, to.high); h <= std::max(from.high, to.high); ++h) {
      apply_class(range, h, h - gap, from.shape, w);
    }
    return;
  }

  // Ladder, e.g. "22+", "A2s+", "KTo+".
  if (item.back() == '+') {
    const ClassPattern p = parse_class_pattern(item.substr(0, item.size() - 1), token);
    if (p.shape == Shape::Pair) {
      for (int r = p.high; r < kNumRanks; ++r) apply_class(range, r, r, Shape::Pair, w);
    } else {
      for (int l = p.low; l < p.high; ++l) apply_class(range, p.high, l, p.shape, w);
    }
    return;
  }

  const ClassPattern p = parse_class_pattern(item, token);
  apply_class(range, p.high, p.low, p.shape, w);
}

}  // namespace

Combo make_combo(Card a, Card b) {
  if (a == b) throw std::invalid_argument("a combo needs two different cards");
  if (a >= kNumCards || b >= kNumCards) throw std::invalid_argument("card index out of range");
  return a > b ? Combo{a, b} : Combo{b, a};
}

int combo_index(Combo c) noexcept { return c.hi * (c.hi - 1) / 2 + c.lo; }

Combo combo_from_index(int index) noexcept { return combo_table()[index]; }

std::string combo_to_string(Combo c) { return card_to_string(c.hi) + card_to_string(c.lo); }

int HandClass::num_combos() const noexcept {
  if (is_pair()) return 6;
  return suited ? 4 : 12;
}

HandClass hand_class_of(Combo c) noexcept {
  const int a = card_rank(c.hi);
  const int b = card_rank(c.lo);
  const int high = std::max(a, b);
  const int low = std::min(a, b);
  return {high, low, high != low && card_suit(c.hi) == card_suit(c.lo)};
}

// Index in the usual 13x13 grid, read row by row with aces first: pairs on the
// diagonal, suited hands above it and offsuit hands below it.
int hand_class_index(HandClass h) noexcept {
  const int hi = 12 - h.high_rank;
  const int lo = 12 - h.low_rank;
  return h.suited ? hi * kNumRanks + lo : lo * kNumRanks + hi;
}

HandClass hand_class_from_index(int index) noexcept {
  const int row = index / kNumRanks;
  const int col = index % kNumRanks;
  if (row == col) return {12 - row, 12 - row, false};
  if (row < col) return {12 - row, 12 - col, true};
  return {12 - col, 12 - row, false};
}

std::string hand_class_to_string(HandClass h) {
  std::string out{kRankChars[h.high_rank], kRankChars[h.low_rank]};
  if (!h.is_pair()) out += h.suited ? 's' : 'o';
  return out;
}

std::vector<Combo> hand_class_combos(HandClass h) {
  std::vector<Combo> out;
  out.reserve(h.num_combos());
  for (int s1 = 0; s1 < kNumSuits; ++s1) {
    for (int s2 = 0; s2 < kNumSuits; ++s2) {
      if (h.is_pair()) {
        if (s1 < s2) out.push_back(make_combo(make_card(h.high_rank, s1), make_card(h.low_rank, s2)));
      } else if (h.suited == (s1 == s2)) {
        out.push_back(make_combo(make_card(h.high_rank, s1), make_card(h.low_rank, s2)));
      }
    }
  }
  return out;
}

Range Range::parse(std::string_view text) {
  Range range;
  std::size_t pos = 0;
  while (pos <= text.size()) {
    std::size_t next = text.find(',', pos);
    if (next == std::string_view::npos) next = text.size();

    std::string token;
    for (char ch : text.substr(pos, next - pos)) {
      if (!std::isspace(static_cast<unsigned char>(ch))) token += ch;
    }
    pos = next + 1;
    if (token.empty()) continue;

    std::string_view item = token;
    double w = 1.0;
    if (const auto colon = item.find(':'); colon != std::string_view::npos) {
      w = parse_weight(item.substr(colon + 1), token);
      item = item.substr(0, colon);
    }
    if (item.empty()) fail(token, "empty hand");
    apply_item(range, item, w, token);
  }
  return range;
}

Range Range::single(Combo c) {
  Range r;
  r.set_weight(c, 1.0);
  return r;
}

void Range::set_weight(Combo c, double w) {
  if (!(w >= 0.0 && w <= 1.0)) throw std::invalid_argument("weight must be within [0, 1]");
  weights_[combo_index(c)] = w;
}

void Range::set_class_weight(HandClass h, double w) {
  for (Combo c : hand_class_combos(h)) set_weight(c, w);
}

double Range::class_weight(HandClass h) const noexcept {
  const auto combos = hand_class_combos(h);
  double sum = 0.0;
  for (Combo c : combos) sum += weight(c);
  return sum / static_cast<double>(combos.size());
}

std::vector<WeightedCombo> Range::combos(CardMask dead) const {
  std::vector<WeightedCombo> out;
  for (int i = 0; i < kNumCombos; ++i) {
    if (weights_[i] <= 0.0) continue;
    const Combo c = combo_from_index(i);
    if (c.mask() & dead) continue;
    out.push_back({c, weights_[i]});
  }
  return out;
}

double Range::total_weight(CardMask dead) const {
  double sum = 0.0;
  for (const auto& wc : combos(dead)) sum += wc.weight;
  return sum;
}

bool Range::empty() const noexcept {
  return std::none_of(weights_.begin(), weights_.end(), [](double w) { return w > 0.0; });
}

}  // namespace pokercore
