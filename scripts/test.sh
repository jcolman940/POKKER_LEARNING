#!/usr/bin/env bash
# Runs every test suite in the monorepo. Usage: scripts/test.sh [core|backend|frontend|integration]...
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
targets=("$@")
[[ ${#targets[@]} -eq 0 ]] && targets=(core backend frontend integration)

run_core() {
  echo "==> core (C++)"
  cmake -S "$ROOT/core" -B "$ROOT/core/build/dev" -G Ninja -DCMAKE_BUILD_TYPE=Release
  cmake --build "$ROOT/core/build/dev"
  ctest --test-dir "$ROOT/core/build/dev" --output-on-failure
}

run_backend() {
  echo "==> backend (Python)"
  (cd "$ROOT/backend" && uv sync --quiet && uv run ruff check . && uv run ruff format --check . && uv run pytest -q)
}

run_frontend() {
  echo "==> frontend (TypeScript)"
  (cd "$ROOT/frontend" && npm ci --silent && npm run typecheck && npm run lint && npm test)
}

run_integration() {
  echo "==> integration"
  (cd "$ROOT/backend" && uv sync --quiet && uv run pytest -q "$ROOT/tests/integration")
}

for t in "${targets[@]}"; do
  "run_$t"
done
echo "All requested suites passed."
