#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python app.py &
FLASK_PID=$!

cleanup() {
  kill "$FLASK_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd frontend && npm run dev)
