#!/usr/bin/env bash
# Starts backend (http://127.0.0.1:8000) and frontend dev server (http://localhost:5173).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
(cd "$ROOT/src/backend" && uv sync --quiet && uv run uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT
(cd "$ROOT/src/frontend" && npm install --silent && npm run dev)
