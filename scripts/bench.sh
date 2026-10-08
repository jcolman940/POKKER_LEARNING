#!/usr/bin/env bash
# Builds the native core in Release and runs the performance benchmark.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cmake -S "$ROOT/src/core" -B "$ROOT/src/core/build/dev" -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build "$ROOT/src/core/build/dev" --target pokercore_bench
"$ROOT/src/core/build/dev/pokercore_bench" "$@"
