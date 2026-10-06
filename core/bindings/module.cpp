#include <pybind11/pybind11.h>

#include <string>

#include "pokercore/version.hpp"

namespace py = pybind11;

PYBIND11_MODULE(_core, m) {
  m.doc() = "Native poker core: hand evaluation and equity.";
  m.def("version", [] { return std::string(pokercore::version()); },
        "Version of the native core library.");
}
