# Desktop Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A double-clickable Desktop icon that syncs the venv, keeps dependencies up to date, starts the Flask app if it isn't already running, and opens the browser to it — no manual terminal, no visible Terminal window.

**Architecture:** A committed shell script (`scripts/launch_app.sh`) does all the real work (venv setup, dependency sync, background server start, health-check polling, browser opening). A committed AppleScript wrapper (`scripts/launch_app.applescript`) just shells out to it, compiled with `osacompile` into a real `.app` on the Desktop with no Terminal window. The Flask app moves from port 5000 to port 5099 to avoid a confirmed conflict with macOS's AirPlay Receiver.

**Tech Stack:** bash, AppleScript (`osacompile`), Python 3 / venv / pip, Flask, curl, `osascript` for error dialogs.

## Global Constraints

- App must listen on port **5099**, not 5000 (`ControlCenter`/AirPlay Receiver already occupies 5000 and answers 403 even when nothing else is listening — confirmed live on this machine).
- No "stop server" icon or process-management UI — out of scope.
- The launcher is tied to this machine's fixed project path: `/Users/paulmckay/Desktop/NHL Stats Project`. Not building portability.
- Logs go to `.run/app.log` (new directory, gitignored).
- The compiled Desktop `.app` is a generated artifact placed at `~/Desktop/NHL Stats.app` — it is NOT committed to git (it lives outside the repo entirely). Only its AppleScript *source* (`scripts/launch_app.applescript`) is committed.
- On any failure (venv creation, `pip install`, server never comes up), show a native macOS alert dialog via `osascript` — there is no visible Terminal to read output from.

---

### Task 1: Move the Flask app from port 5000 to port 5099

**Files:**
- Modify: `app.py` (bottom of file, the `if __name__ == "__main__":` block)

**Interfaces:**
- Produces: the app now binds `127.0.0.1:5099` instead of the Flask default `127.0.0.1:5000`. All later tasks target `5099`.

- [ ] **Step 1: Make the change**

In `app.py`, find:
```python
if __name__ == "__main__":
    app.run(debug=_debug_enabled())
```
Replace with:
```python
if __name__ == "__main__":
    app.run(debug=_debug_enabled(), port=5099)
```

- [ ] **Step 2: Verify manually**

Run:
```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
source .venv/bin/activate
python app.py > /tmp/port_test.log 2>&1 &
APP_PID=$!
sleep 1.5
curl -s -o /dev/null -w "%{http_code}\n" --max-time 2 http://127.0.0.1:5099/
kill "$APP_PID"
wait "$APP_PID" 2>/dev/null
```
Expected output: `200`

- [ ] **Step 3: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add app.py
git commit -m "fix: run Flask app on port 5099 to avoid AirPlay Receiver conflict on 5000"
```

---

### Task 2: Write `scripts/launch_app.sh`

**Files:**
- Create: `scripts/launch_app.sh`
- Modify: `.gitignore` (add `.run/`)

**Interfaces:**
- Consumes: port `5099` from Task 1.
- Produces: an executable script at `scripts/launch_app.sh` that Task 3's AppleScript wrapper calls by absolute path. On success it leaves the Flask app running in the background and the default browser open to `http://127.0.0.1:5099/`.

- [ ] **Step 1: Add `.run/` to `.gitignore`**

Append to `/Users/paulmckay/Desktop/NHL Stats Project/.gitignore`:
```
.run/
```

- [ ] **Step 2: Write the script**

Create `scripts/launch_app.sh`:
```bash
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
```

- [ ] **Step 3: Make it executable**

```bash
chmod +x "/Users/paulmckay/Desktop/NHL Stats Project/scripts/launch_app.sh"
```

- [ ] **Step 4: Verify cold start**

Temporarily move `.venv` aside so the script has to rebuild it from scratch:
```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
mv .venv /tmp/venv_backup
./scripts/launch_app.sh
```
Expected: no error printed, `.venv/` and `.run/app.log` now exist, and (per the script's own logic) the default browser opens to `http://127.0.0.1:5099/` showing the app's index page. Confirm the server process is running:
```bash
pgrep -fl "python .*app.py"
```
Expected: one matching line.

- [ ] **Step 5: Verify warm start (already running)**

With the server from Step 4 still running:
```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
./scripts/launch_app.sh
pgrep -fl "python .*app.py"
```
Expected: still exactly **one** matching process (no duplicate server spawned), and the browser opens/reopens the tab.

- [ ] **Step 6: Verify restart after the server is killed**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
pkill -f "python .*app.py"
sleep 1
./scripts/launch_app.sh
pgrep -fl "python .*app.py"
tail -5 .run/app.log
```
Expected: a new matching process, and `.run/app.log` has a fresh set of "Running on http://127.0.0.1:5099" lines appended below the earlier run's output.

- [ ] **Step 7: Clean up test state**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
pkill -f "python .*app.py"
rm -rf .venv
mv /tmp/venv_backup .venv
```
(Restores the original `.venv` that existed before this task's cold-start test, so Task 3's own verification starts from a clean, known state.)

- [ ] **Step 8: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add scripts/launch_app.sh .gitignore
git commit -m "feat: add launch_app.sh to sync venv, start the server, and open the browser"
```

---

### Task 3: Add the AppleScript wrapper and compile the Desktop icon

**Files:**
- Create: `scripts/launch_app.applescript`
- Generate (not committed): `~/Desktop/NHL Stats.app`

**Interfaces:**
- Consumes: `scripts/launch_app.sh` from Task 2, referenced by its absolute path.
- Produces: a double-clickable `.app` on the Desktop with no Terminal window.

- [ ] **Step 1: Write the AppleScript wrapper**

Create `scripts/launch_app.applescript`:
```applescript
try
	do shell script quoted form of "/Users/paulmckay/Desktop/NHL Stats Project/scripts/launch_app.sh"
end try
```
(The `try`/`end try` swallows the generic AppleScript-level error dialog that `do shell script` would otherwise raise on a non-zero exit — `launch_app.sh` already shows its own descriptive `osascript` alert on every failure path, so this avoids a redundant second dialog.)

- [ ] **Step 2: Compile it into a Desktop app**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
osacompile -o ~/Desktop/"NHL Stats.app" scripts/launch_app.applescript
```
Expected: `~/Desktop/NHL Stats.app` now exists.

- [ ] **Step 3: Verify cold start end-to-end (simulating a real double-click)**

Confirm the server isn't already running, then launch:
```bash
pkill -f "python .*app.py" 2>/dev/null || true
open ~/Desktop/"NHL Stats.app"
sleep 5
curl -s -o /dev/null -w "%{http_code}\n" --max-time 2 http://127.0.0.1:5099/
```
Expected: `200`, and no Terminal window appeared during the process (confirm visually — this is a GUI check, not scriptable).

- [ ] **Step 4: Verify warm start (double-click again while running)**

```bash
open ~/Desktop/"NHL Stats.app"
sleep 1
pgrep -fl "python .*app.py"
```
Expected: still exactly one matching process — the second launch just reopened the browser tab rather than starting a second server.

- [ ] **Step 5: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add scripts/launch_app.applescript
git commit -m "feat: add AppleScript wrapper compiled to a Desktop launcher icon"
```

**End state:** `~/Desktop/NHL Stats.app` is a working double-clickable launcher; the Flask app is running in the background at `http://127.0.0.1:5099/`, matching the intended end-to-end use case. No further cleanup needed — leaving it running is expected.
