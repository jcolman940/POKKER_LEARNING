#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <string>
#include <utility>
#include <vector>

#include "pokercore/card.hpp"
#include "pokercore/equity.hpp"
#include "pokercore/evaluator.hpp"
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
