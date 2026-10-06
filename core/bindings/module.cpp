#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <string>
#include <utility>
#include <vector>

#include "pokercore/card.hpp"
#include "pokercore/equity.hpp"
#include "pokercore/evaluator.hpp"
#include "pokercore/icm.hpp"
#include "pokercore/preflop.hpp"
#include "pokercore/range.hpp"
#include "pokercore/version.hpp"

namespace py = pybind11;
using namespace pokercore;

namespace {

EquityMode parse_mode(const std::string& mode) {
  if (mode == "auto") return EquityMode::Auto;
  if (mode == "exact") return EquityMode::Exact;
  if (mode == "monte_carlo") return EquityMode::MonteCarlo;
  throw std::invalid_argument("mode must be 'auto', 'exact' or 'monte_carlo'");
}

EquityResult equity(const std::vector<std::string>& players, const std::string& board,
                    const std::string& dead, const std::string& mode, std::uint64_t iterations,
                    double exact_limit, std::uint64_t seed) {
  std::vector<Range> ranges;
  ranges.reserve(players.size());
  for (const auto& p : players) ranges.push_back(Range::parse(p));
  const auto board_cards = parse_cards(board);
  const auto dead_cards = parse_cards(dead);

  EquityOptions opts;
  opts.mode = parse_mode(mode);
  opts.iterations = iterations;
  opts.exact_limit = exact_limit;
  opts.seed = seed;

  py::gil_scoped_release release;
  return calculate_equity(ranges, board_cards, dead_cards, opts);
}

}  // namespace

PYBIND11_MODULE(_core, m) {
  m.doc() = "Native poker core: hand evaluation and equity.";

  m.def("version", [] { return std::string(pokercore::version()); },
        "Version of the native core library.");

  m.def(
      "evaluate",
      [](const std::string& cards) {
        const auto parsed = parse_cards(cards);
        return evaluate(std::span<const Card>(parsed));
      },
      py::arg("cards"),
      "Strength of the best 5-card hand among 5 to 7 cards (e.g. 'AhKhQhJhTh2c3d'). "
      "Higher is better; equal values tie.");

  m.def(
      "hand_category", [](HandValue v) { return std::string(category_name(category(v))); },
      py::arg("value"), "Category name of a value returned by evaluate().");

  m.def(
      "range_combos",
      [](const std::string& text, const std::string& dead) {
        std::vector<std::pair<std::string, double>> out;
        for (const auto& wc : Range::parse(text).combos(to_mask(parse_cards(dead)))) {
          out.emplace_back(combo_to_string(wc.combo), wc.weight);
        }
        return out;
      },
      py::arg("text"), py::arg("dead") = "",
      "Expands range notation ('22+, A2s+, AKo:0.5, AhKh') into weighted combos, "
      "removing combos blocked by `dead` cards.");

  m.def(
      "range_grid",
      [](const std::string& text) {
        const Range r = Range::parse(text);
        std::vector<double> grid(kNumHandClasses);
        for (int i = 0; i < kNumHandClasses; ++i) grid[i] = r.class_weight(hand_class_from_index(i));
        return grid;
      },
      py::arg("text"),
      "Average weight of each of the 169 hand classes, in 13x13 grid order (row by row, "
      "aces first; suited above the diagonal).");

  m.def(
      "hand_class_names",
      [] {
        std::vector<std::string> names;
        for (int i = 0; i < kNumHandClasses; ++i) {
          names.push_back(hand_class_to_string(hand_class_from_index(i)));
        }
        return names;
      },
      "Names of the 169 hand classes in 13x13 grid order ('AA', 'AKs', ..., '22').");

  py::class_<HandStrength>(m, "HandStrength")
      .def_readonly("win", &HandStrength::win)
      .def_readonly("tie", &HandStrength::tie)
      .def_readonly("lose", &HandStrength::lose)
      .def_readonly("combos", &HandStrength::combos);

  m.def(
      "hand_strength",
      [](const std::string& hero, const std::string& villain, const std::string& board,
         const std::string& dead) {
        const auto hero_cards = parse_cards(hero);
        if (hero_cards.size() != 2) throw std::invalid_argument("hero must hold exactly 2 cards");
        return hand_strength(make_combo(hero_cards[0], hero_cards[1]), Range::parse(villain),
                             parse_cards(board), parse_cards(dead));
      },
      py::arg("hero"), py::arg("villain"), py::arg("board"), py::arg("dead") = "",
      "Showdown result of the hero hand vs a range on the current 3-5 card board, "
      "without dealing more cards.");

  m.def("icm_equity", &icm_equity, py::arg("stacks"), py::arg("payouts"),
        "Malmuth-Harville ICM: expected prize of each player (stacks <= 0 are eliminated). "
        "Up to 12 players with chips.");

  m.def(
      "preflop_equity_matrix",
      [](std::uint64_t trials_per_pair, std::uint64_t seed, int threads) {
        py::gil_scoped_release release;
        return preflop_equity_matrix(trials_per_pair, seed, threads);
      },
      py::arg("trials_per_pair"), py::arg("seed") = 1, py::arg("threads") = 0,
      "Heads-up preflop all-in equity between the 169 hand classes, as a flat row-major "
      "list (169 * 169) in 13x13 grid order.");

  py::class_<PlayerEquity>(m, "PlayerEquity")
      .def_readonly("equity", &PlayerEquity::equity)
      .def_readonly("win", &PlayerEquity::win)
      .def_readonly("tie", &PlayerEquity::tie)
      .def_readonly("lose", &PlayerEquity::lose)
      .def_readonly("std_error", &PlayerEquity::std_error)
      .def("__repr__", [](const PlayerEquity& p) {
        return "PlayerEquity(equity=" + std::to_string(p.equity) +
               ", win=" + std::to_string(p.win) + ", tie=" + std::to_string(p.tie) +
               ", lose=" + std::to_string(p.lose) + ", std_error=" + std::to_string(p.std_error) +
               ")";
      });

  py::class_<EquityResult>(m, "EquityResult")
      .def_readonly("players", &EquityResult::players)
      .def_readonly("exact", &EquityResult::exact)
      .def_readonly("samples", &EquityResult::samples)
      .def_readonly("seed", &EquityResult::seed);

  m.def("equity", &equity, py::arg("players"), py::arg("board") = "", py::arg("dead") = "",
        py::kw_only(), py::arg("mode") = "auto", py::arg("iterations") = 200'000,
        py::arg("exact_limit") = 3e7, py::arg("seed") = 0,
        "All-in equity for 2-10 players. Each player is a hand ('AhKh') or a range "
        "('QQ+,AKs'). mode: 'auto' | 'exact' | 'monte_carlo'. seed=0 picks a random seed.");
}
