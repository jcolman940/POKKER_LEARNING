#pragma once

#include <vector>

namespace pokercore {

inline constexpr int kMaxIcmPlayers = 12;

// Malmuth-Harville ICM: expected prize of each player given chip stacks and the
// remaining payouts (payouts[0] = 1st place). Players with a stack <= 0 are
// considered eliminated and get 0. Places beyond the number of live players are
// ignored, and missing places pay 0.
// Throws std::invalid_argument with more than kMaxIcmPlayers live players or
// negative payouts.
std::vector<double> icm_equity(const std::vector<double>& stacks,
                               const std::vector<double>& payouts);

}  // namespace pokercore
