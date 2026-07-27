# Launcher Auto-Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/launch_app.sh` automatically pull merged GitHub changes into local `main`, and rebuild/restart the app, every time the desktop icon is launched — so the desktop app never again serves stale code.

**Architecture:** All logic lives in `scripts/launch_app.sh` as new shell functions, inserted before the script's existing venv/pip/server-start logic. No new files, no background processes, no cron/launchd entries. The script becomes: sync with origin → decide if a rebuild is needed (SHA changed, or `static/dist/` missing) → if so, kill the stale server and rebuild the frontend → fall through to the existing (unchanged) venv/pip/start-server flow.

**Tech Stack:** Bash (existing script's language), git, npm, osascript (existing alert mechanism), lsof/curl (existing process/health-check tools).

## Global Constraints

- Sync runs synchronously at the start of every launch — no background pollers, cron jobs, or launchd agents.
- Rebuild/restart triggers when `AFTER_SHA != BEFORE_SHA` OR `static/dist/` is missing entirely.
- Kill sequence for a stale server on port 5099: SIGTERM, poll `is_up` for up to ~3 seconds, then SIGKILL if still listening.
- `npm install` runs only when `frontend/package.json` or `frontend/package-lock.json` changed in the synced commit range, or when there's no commit range to check (first-ever build / `static/dist/` missing) — otherwise skip straight to `npm run build`.
- "Dirty working tree" is treated uniformly (`git stash -u` covers everything, including `.wolf/*` daemon files) — no special-casing.
- Rebase conflict: abort the rebase, restore the stash if one was made, alert via `osascript`, continue launching on the pre-sync state.
- Stash-pop conflict (after a successful rebase or on any recovery path): always alert, never attempt auto-resolution, leave the stash in the stash list.
- Offline / `git fetch` failure: silent — log to `.run/app.log` only, no dialog, launch continues on local state.
- Out of scope: branch-protection settings, a background watcher/poller, any change to `app.py` or Flask structure.

---

### Task 1: Git auto-sync + conditional rebuild/restart in `launch_app.sh`

**Files:**
- Modify: `scripts/launch_app.sh` (full rewrite of the file's body — see below)

**Interfaces:**
- Produces: `sync_with_origin()` — no args, prints the post-sync HEAD SHA to stdout (its only output; logs and alerts go elsewhere), used by the main script as `AFTER_SHA=$(sync_with_origin)`.
- Produces: `kill_stale_server()` — no args, no output; kills whatever process (if any) is listening on `$PORT`.
- Produces: `rebuild_frontend(before_sha, after_sha)` — two positional args (git SHAs, may be equal), no output; runs conditional `npm install` + `npm run build`, exits the whole script with `alert` + `exit 1` on failure.

- [ ] **Step 1: Replace the full contents of `scripts/launch_app.sh`**

```bash
#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

PORT=5099
URL="http://127.0.0.1:${PORT}/"
LOG_DIR="$PROJECT_DIR/.run"
LOG_FILE="$LOG_DIR/app.log"

mkdir -p "$LOG_DIR"

alert() {
  osascript -e "display dialog \"$1\" with title \"NHL Stats Launcher\" buttons {\"OK\"} default button 1 with icon caution"
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

  if ! git rebase origin/main >> "$LOG_FILE" 2>&1; then
    git rebase --abort >> "$LOG_FILE" 2>&1
    if [ "$dirty" = true ] && ! git stash pop >> "$LOG_FILE" 2>&1; then
      alert "Auto-sync hit a conflict merging GitHub changes, then hit a second conflict restoring your local changes. Resolve manually in a terminal (see git stash list). Launching on the current local state for now."
      echo "$before_sha"
      return 0
    fi
    alert "Auto-sync hit a conflict merging the latest GitHub changes. Resolve manually in a terminal (git rebase origin/main), then relaunch. Launching on the current local state for now."
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
  pid=$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -n 1)
  if [ -z "$pid" ]; then
    return 0
  fi

  kill "$pid" 2>/dev/null || true

  local waited=0
  while is_up && [ "$waited" -lt 6 ]; do
    sleep 0.5
    waited=$((waited + 1))
  done

  if is_up; then
    kill -9 "$pid" 2>/dev/null || true
  fi
}

rebuild_frontend() {
  local before_sha="$1"
  local after_sha="$2"
  local need_npm_install=true

  if [ "$before_sha" != "$after_sha" ] && ! git diff --name-only "$before_sha..$after_sha" | grep -qE '^frontend/package(-lock)?\.json$'; then
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
if [ "$AFTER_SHA" != "$BEFORE_SHA" ] || [ ! -d "$PROJECT_DIR/static/dist" ]; then
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
```

- [ ] **Step 2: Lint with shellcheck**

Run: `shellcheck scripts/launch_app.sh`
Expected: no output (clean). Fix any warnings shellcheck raises before proceeding — do not add blanket `# shellcheck disable` comments beyond the pre-existing `SC1091` (sourcing a venv activate script, which shellcheck can't resolve statically).

- [ ] **Step 3: Smoke-test on the current clean repo state**

The repo right now has local `main` fully caught up with `origin/main` (no divergence) and a server may already be running on port 5099. Run:

```bash
bash scripts/launch_app.sh
```

Expected: the script exits 0, your browser opens to `http://127.0.0.1:5099/`, and `tail -20 .run/app.log` shows either "reused existing server" behavior (no `npm run build` invocation logged) if a server was already up and no sync changes occurred, or a normal cold-start (venv/pip/server start lines) if nothing was running. No `osascript` dialog should appear.

- [ ] **Step 4: Commit**

```bash
git add scripts/launch_app.sh
git commit -m "feat: auto-sync with origin/main and rebuild frontend on launch"
```

---

### Task 2: Manual scenario verification

**Files:**
- No file changes expected unless Task 1 revealed a bug — if so, fix `scripts/launch_app.sh` in this task and note it in the report.
- Test: none (no automated test harness exists for shell scripts in this project — verification is manual, per this feature's design spec's Testing Plan).

**Interfaces:**
- Consumes: `scripts/launch_app.sh` as built in Task 1 — treat it as a black box, invoke only via `bash scripts/launch_app.sh` and by inspecting `git`/`lsof`/`.run/app.log` state before and after, exactly as an end user would experience it (never read Task 1's diff to "verify" behavior — run it).

- [ ] **Step 1: Fast-forward case (origin ahead, local has nothing to lose)**

Set up: create a throwaway commit on a scratch branch to simulate "origin moved" without touching real history, or use a disposable clone. Simplest safe reproduction — use a temporary bare clone as a fake "local" so nothing here touches the real working repo:

```bash
TMPDIR=$(mktemp -d)
git clone "$PROJECT_DIR" "$TMPDIR/ff-test"
cd "$TMPDIR/ff-test"
git remote set-url origin "$PROJECT_DIR"
git reset --hard HEAD~1
cp "$PROJECT_DIR/scripts/launch_app.sh" scripts/launch_app.sh
bash scripts/launch_app.sh > launch-output.log 2>&1 &
sleep 8
kill %1 2>/dev/null || true
git log --oneline -1
```

Expected: after the run, `git log --oneline -1` in `$TMPDIR/ff-test` matches `$PROJECT_DIR`'s current HEAD (sync pulled the missing commit), and `.run/app.log` inside the clone shows a rebuild (npm install/build lines) since the SHA changed. Clean up: `pkill -f "$TMPDIR/ff-test/app.py"; rm -rf "$TMPDIR"`.

- [ ] **Step 2: Rebase case (local has unpushed commits, origin has new commits)**

Using the same kind of disposable clone as Step 1: make one local-only commit (e.g. touch a scratch file, commit it), reset the clone's view of origin back one commit so origin has something the clone doesn't, run the script, and confirm both the local-only commit and the "origin" commit are present afterward with the local commit rebased on top:

```bash
TMPDIR=$(mktemp -d)
git clone "$PROJECT_DIR" "$TMPDIR/rebase-test"
cd "$TMPDIR/rebase-test"
git remote set-url origin "$PROJECT_DIR"
echo "scratch" > SCRATCH.md && git add SCRATCH.md && git commit -m "test: local-only commit"
cp "$PROJECT_DIR/scripts/launch_app.sh" scripts/launch_app.sh
bash scripts/launch_app.sh > launch-output.log 2>&1 &
sleep 8
kill %1 2>/dev/null || true
git log --oneline -3
```

Expected: `git log --oneline -3` shows the local "test: local-only commit" still present, now rebased on top of `origin/main`'s HEAD (no merge commit, linear history). No `osascript` dialog. Clean up as in Step 1.

- [ ] **Step 3: Dirty-tree case (uncommitted changes present during sync)**

In a disposable clone, make an uncommitted (not committed) change, then run the script:

```bash
TMPDIR=$(mktemp -d)
git clone "$PROJECT_DIR" "$TMPDIR/dirty-test"
cd "$TMPDIR/dirty-test"
git remote set-url origin "$PROJECT_DIR"
echo "uncommitted change" >> README.md
cp "$PROJECT_DIR/scripts/launch_app.sh" scripts/launch_app.sh
bash scripts/launch_app.sh > launch-output.log 2>&1 &
sleep 8
kill %1 2>/dev/null || true
git status --porcelain
git stash list
```

Expected: `git status --porcelain` still shows the README.md modification present (stash was popped back cleanly), and `git stash list` is empty (no leftover stash). Clean up as in Step 1.

- [ ] **Step 4: Offline case (fetch fails)**

In a disposable clone, point `origin` at an unreachable URL so `git fetch` fails, then run the script:

```bash
TMPDIR=$(mktemp -d)
git clone "$PROJECT_DIR" "$TMPDIR/offline-test"
cd "$TMPDIR/offline-test"
git remote set-url origin "https://127.0.0.1:1/nonexistent.git"
cp "$PROJECT_DIR/scripts/launch_app.sh" scripts/launch_app.sh
bash scripts/launch_app.sh > launch-output.log 2>&1 &
sleep 8
kill %1 2>/dev/null || true
grep "auto-sync: git fetch failed" .run/app.log
```

Expected: `.run/app.log` contains the "auto-sync: git fetch failed (offline?), skipping sync" line, no `osascript` dialog appeared, and the app still attempted to launch (check `launch-output.log` / `.run/app.log` for normal venv/server-start activity past the sync step). Clean up as in Step 1.

- [ ] **Step 5: Conflict case (rebase genuinely conflicts)**

In a disposable clone, create a real conflict: make a local commit that edits the same line the "origin" side also changed relative to a shared ancestor, then run the script:

```bash
TMPDIR=$(mktemp -d)
git clone "$PROJECT_DIR" "$TMPDIR/conflict-test"
cd "$TMPDIR/conflict-test"
git remote set-url origin "$PROJECT_DIR"
git reset --hard HEAD~1
echo "local conflicting change" >> README.md
git add README.md && git commit -m "test: conflicting local change"
cp "$PROJECT_DIR/scripts/launch_app.sh" scripts/launch_app.sh
bash scripts/launch_app.sh > launch-output.log 2>&1 &
sleep 8
kill %1 2>/dev/null || true
git status
```

Note: this only produces a genuine conflict if `origin/main`'s last commit also touched `README.md`'s same lines — if `git log -p -1 "$PROJECT_DIR"` shows the last real commit didn't touch README.md, substitute whatever file the actual last commit on `origin/main` changed, editing the same lines it changed, so the rebase has a real collision to resolve.

Expected: `git status` shows no rebase in progress (the script's `git rebase --abort` cleaned it up), the local commit is still present and HEAD is unchanged from before the sync attempt, and an `osascript` dialog appeared during the run (visually confirm, since this can't be grepped from a log — the dialog itself is the alert path, not logged). Clean up as in Step 1.

- [ ] **Step 6: Report**

Summarize pass/fail for each of the 5 scenarios above in the task report. If any scenario failed, fix `scripts/launch_app.sh` (in this task, not a separate one), re-run shellcheck, re-run the failing scenario(s) until they pass, then proceed.

- [ ] **Step 7: Commit (only if Task 1's script needed fixes)**

```bash
git add scripts/launch_app.sh
git commit -m "fix: address scenario-verification findings in launch_app.sh auto-sync"
```

If no fixes were needed, skip this step (nothing to commit).
