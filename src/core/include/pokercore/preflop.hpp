#pragma once

#include <cstdint>
#include <vector>

namespace pokercore {

// Heads-up all-in preflop equity between the 169 hand classes, row-major
// (index a * 169 + b = equity of class a against class b, ties counted as half),
// with classes in the 13x13 grid order of hand_class_index().
//
// Each pair is estimated by Monte Carlo over its compatible combo pairs (cycled
// evenly, so card removal is exact) with `trials_per_pair` random boards. The
// result only depends on `seed`, not on the number of threads.
// E[b][a] = 1 - E[a][b] and the diagonal is exactly 0.5.
std::vector<double> preflop_equity_matrix(std::uint64_t trials_per_pair, std::uint64_t seed,
                                          int threads = 0);

}  // namespace pokercore
