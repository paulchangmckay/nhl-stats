#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

PORT=5099
URL="http://127.0.0.1:${PORT}/"
LOG_DIR="$PROJECT_DIR/.run"
LOG_FILE="$LOG_DIR/app.log"
BUILT_SHA_FILE="$LOG_DIR/built-sha"

mkdir -p "$LOG_DIR"

alert() {
  osascript -e "display dialog \"$1\" with title \"NHL Stats Launcher\" buttons {\"OK\"} default button 1 with icon caution" >/dev/null 2>>"$LOG_FILE"
}

trap 'alert "Unexpected error starting the app. See '"$LOG_FILE"' for details."' ERR

is_up() {
  curl -sf -o /dev/null -m 1 "$URL"
}

open_browser() {
  open "$URL"
}

sync_with_origin() {
  local before_sha after_sha dirty=false

  before_sha=$(git rev-parse HEAD)

  if [ -n "$(git status --porcelain)" ]; then
    if git stash push -u -m "launch_app auto-sync $(date +%s)" >> "$LOG_FILE" 2>&1; then
      dirty=true
    else
      echo "auto-sync: git stash failed, skipping sync" >> "$LOG_FILE"
      echo "$before_sha"
      return 0
    fi
  fi

  if ! git fetch origin >> "$LOG_FILE" 2>&1; then
    echo "auto-sync: git fetch failed (offline?), skipping sync" >> "$LOG_FILE"
    if [ "$dirty" = true ] && ! git stash pop >> "$LOG_FILE" 2>&1; then
      alert "Auto-sync: could not restore your stashed changes after a failed fetch. Resolve manually with 'git stash list' in a terminal."
    fi
    echo "$before_sha"
    return 0
  fi

  if ! git merge --no-edit origin/main >> "$LOG_FILE" 2>&1; then
    git merge --abort >> "$LOG_FILE" 2>&1
    if [ "$dirty" = true ] && ! git stash pop >> "$LOG_FILE" 2>&1; then
      alert "Auto-sync hit a conflict merging GitHub changes, then hit a second conflict restoring your local changes. Resolve manually in a terminal (see git stash list). Launching on the current local state for now."
      echo "$before_sha"
      return 0
    fi
    alert "Auto-sync hit a conflict merging the latest GitHub changes. Resolve manually in a terminal (git merge origin/main), then relaunch. Launching on the current local state for now."
    echo "$before_sha"
    return 0
  fi

  after_sha=$(git rev-parse HEAD)

  if [ "$dirty" = true ] && ! git stash pop >> "$LOG_FILE" 2>&1; then
    alert "Auto-sync synced new code but hit a conflict restoring your local changes. Resolve manually in a terminal (see git stash list). Launching with the synced code; your uncommitted changes are safe in the stash."
  fi

  echo "$after_sha"
}

kill_stale_server() {
  local pid
  pid=$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -n 1) || true
  if [ -z "$pid" ]; then
    return 0
  fi

  kill "$pid" 2>/dev/null || true

  local waited=0
  while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 6 ]; do
    sleep 0.5
    waited=$((waited + 1))
  done

  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
}

rebuild_frontend() {
  local before_sha="$1"
  local after_sha="$2"
  local need_npm_install=true

  if [ "$before_sha" != "$after_sha" ] && ! git diff --name-only "$before_sha..$after_sha" 2>>"$LOG_FILE" | grep -qE '^frontend/package(-lock)?\.json$'; then
    need_npm_install=false
  fi

  if [ "$need_npm_install" = true ]; then
    if ! (cd "$PROJECT_DIR/frontend" && npm install >> "$LOG_FILE" 2>&1); then
      alert "Failed to install frontend dependencies. See $LOG_FILE for details."
      exit 1
    fi
  fi

  if ! (cd "$PROJECT_DIR/frontend" && npm run build >> "$LOG_FILE" 2>&1); then
    alert "Failed to build the frontend. See $LOG_FILE for details."
    exit 1
  fi
}

BEFORE_SHA=$(git rev-parse HEAD)
AFTER_SHA=$(sync_with_origin)

NEEDS_REBUILD=false
if [ ! -d "$PROJECT_DIR/static/dist" ] || [ ! -f "$BUILT_SHA_FILE" ] || [ "$(cat "$BUILT_SHA_FILE" 2>/dev/null)" != "$AFTER_SHA" ]; then
  NEEDS_REBUILD=true
fi

if [ "$NEEDS_REBUILD" = false ]; then
  if is_up; then
    open_browser
    exit 0
  fi
else
  kill_stale_server
  rebuild_frontend "$BEFORE_SHA" "$AFTER_SHA"
  echo "$AFTER_SHA" > "$BUILT_SHA_FILE"
fi

if [ ! -f "$PROJECT_DIR/.venv/bin/activate" ]; then
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
