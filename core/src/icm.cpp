#include "pokercore/icm.hpp"

#include <bit>
#include <cstdint>
#include <stdexcept>
#include <string>

namespace pokercore {

std::vector<double> icm_equity(const std::vector<double>& stacks,
                               const std::vector<double>& payouts) {
  for (double p : payouts) {
    if (p < 0.0) throw std::invalid_argument("payouts cannot be negative");
  }

  // Map live players to a compact index.
  std::vector<int> live;
  for (int i = 0; i < static_cast<int>(stacks.size()); ++i) {
    if (stacks[i] > 0.0) live.push_back(i);
  }
  const int n = static_cast<int>(live.size());
  if (n > kMaxIcmPlayers) {
    throw std::invalid_argument("ICM supports up to " + std::to_string(kMaxIcmPlayers) +
                                " players with chips");
  }

  std::vector<double> result(stacks.size(), 0.0);
  if (n == 0) return result;

  const int places = std::min(n, static_cast<int>(payouts.size()));
  const std::uint32_t full = (std::uint32_t{1} << n) - 1;

  // value[mask * n + k]: expected prize of live player k from the places still
  // to be awarded when exactly the players in `mask` remain.
  // Place awarded next = n - popcount(mask) (0 = first). Masks are processed by
  // increasing size so the smaller sub-masks are always ready.
  std::vector<double> value(static_cast<std::size_t>(full + 1) * n, 0.0);
  std::vector<double> chips(n);
  for (int k = 0; k < n; ++k) chips[k] = stacks[live[k]];

  for (int size = 1; size <= n; ++size) {
    const int place = n - size;
    if (place >= places) continue;  // nothing left to pay at this depth
    for (std::uint32_t mask = 1; mask <= full; ++mask) {
      if (std::popcount(mask) != size) continue;
      double total = 0.0;
      for (int k = 0; k < n; ++k) {
        if (mask & (1u << k)) total += chips[k];
      }
      double* out = &value[static_cast<std::size_t>(mask) * n];
      for (int i = 0; i < n; ++i) {
        if (!(mask & (1u << i))) continue;
        const double p = chips[i] / total;  // i takes this place
        out[i] += p * payouts[place];
        const std::uint32_t rest = mask & ~(1u << i);
        if (rest == 0) continue;
        const double* sub = &value[static_cast<std::size_t>(rest) * n];
        for (int k = 0; k < n; ++k) out[k] += p * sub[k];
      }
    }
  }

  for (int k = 0; k < n; ++k) result[live[k]] = value[static_cast<std::size_t>(full) * n + k];
  return result;
}

}  // namespace pokercore
