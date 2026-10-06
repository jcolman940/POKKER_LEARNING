#include "pokercore/version.hpp"

#include "pokercore/version_info.hpp"

namespace pokercore {

std::string_view version() noexcept { return POKERCORE_VERSION_STRING; }

}  // namespace pokercore
