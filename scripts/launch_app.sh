#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

PORT=5099
URL="http://127.0.0.1:${PORT}/"
LOG_DIR="$PROJECT_DIR/.run"
LOG_FILE="$LOG_DIR/app.log"

alert() {
  osascript -e "display dialog \"$1\" with title \"NHL Stats Launcher\" buttons {\"OK\"} default button 1 with icon caution"
}

is_up() {
  curl -s -o /dev/null -m 1 "$URL"
}

open_browser() {
  open "$URL"
}

if is_up; then
  open_browser
  exit 0
fi

mkdir -p "$LOG_DIR"

if [ ! -d "$PROJECT_DIR/.venv" ]; then
  if ! python3 -m venv "$PROJECT_DIR/.venv" >> "$LOG_FILE" 2>&1; then
    alert "Failed to create the virtual environment. See $LOG_FILE for details."
    exit 1
  fi
fi

# shellcheck disable=SC1091
source "$PROJECT_DIR/.venv/bin/activate"

if ! pip install -q -r "$PROJECT_DIR/requirements.txt" >> "$LOG_FILE" 2>&1; then
  alert "Failed to install dependencies. See $LOG_FILE for details."
  exit 1
fi

nohup python "$PROJECT_DIR/app.py" >> "$LOG_FILE" 2>&1 &

for _ in {1..20}; do
  if is_up; then
    open_browser
    exit 0
  fi
  sleep 0.5
done

alert "The app server did not start within 10 seconds. See $LOG_FILE for details."
exit 1
