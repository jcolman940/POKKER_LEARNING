#include <catch2/catch_test_macros.hpp>

#include "pokercore/version.hpp"

TEST_CASE("version is a non-empty semver string", "[version]") {
  const auto v = pokercore::version();
  REQUIRE_FALSE(v.empty());
  REQUIRE(v.find('.') != std::string_view::npos);
}
