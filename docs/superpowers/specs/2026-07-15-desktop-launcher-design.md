# Desktop Launcher for NHL Stats App

## Problem
Running the app currently requires manually opening a terminal, `cd`-ing into the
project, activating `.venv`, and running `python app.py` every time. This is
repetitive and easy to get wrong (e.g. forgetting to activate the venv).

## Goal
A double-clickable Desktop icon that sets up/activates the venv, keeps
dependencies in sync, starts the Flask app if it isn't already running, and
opens the browser to it — with no visible Terminal window.

## Anti-goals
- No "stop server" icon or process-management UI. The Flask process keeps
  running in the background after first launch. Manual stop:
  `pkill -f "python app.py"` or Activity Monitor.
- Not building a portable/relocatable launcher — it's tied to this machine's
  fixed project path (`/Users/paulmckay/Desktop/NHL Stats Project`).

## Port choice: 5099, not the Flask default 5000
Confirmed live on this machine: macOS Control Center's AirPlay Receiver
already listens on port 5000 (`ControlCenter *:5000`) and answers
`http://127.0.0.1:5000/` with HTTP 403 — even when the Flask app isn't
running. A naive "does it respond" health check would always see a response
and wrongly conclude the app is already up, skipping straight to opening the
browser on AirPlay's 403 page instead of starting Flask.

This exact port-5000 conflict is already a recurring, documented pain point
in this repo (`.wolf/cerebrum.md`, entries from 2026-07-02 and 2026-07-14),
including a prior recommendation to fall back to `app.run(port=5099)`.
Rather than special-case the health check around AirPlay's status code, the
app moves to **port 5099** outright, sidestepping the conflict entirely:

- `app.py`: change `app.run(debug=_debug_enabled())` to
  `app.run(debug=_debug_enabled(), port=5099)`.
- All `127.0.0.1` URLs below use `:5099`.

### `scripts/launch_app.sh` (new, committed)
The real logic, run every time the Desktop icon is double-clicked:

1. Resolve its own directory (via the script's real path, not `$PWD`) and `cd`
   there, so it works regardless of how/where it's invoked from.
2. Health-check `http://127.0.0.1:5099/` with a short timeout. If it responds,
   the server is already running — skip to step 5 (open browser).
3. If not running:
   - Create `.venv` via `python3 -m venv .venv` if the directory doesn't exist.
   - Activate `.venv`.
   - Run `pip install -r requirements.txt` (fast no-op if already satisfied,
     keeps the venv in sync with requirements.txt on every launch).
   - Start `python app.py` in the background (detached via `nohup`, so it
     survives `launch_app.sh` returning), redirecting stdout/stderr to
     `.run/app.log` (new, gitignored — created on first run).
4. Poll the health endpoint for up to ~10 seconds waiting for the server to
   come up.
5. Open `http://127.0.0.1:5099` in the default browser.

On any failure (venv creation, `pip install`, or the server never responding
in step 4), show a native macOS alert dialog (`osascript -e 'display dialog
...'`) with the error — there's no visible Terminal to read otherwise — and
exit non-zero without opening a browser tab.

### `scripts/launch_app.applescript` (new, committed)
A minimal AppleScript wrapper whose only job is to shell out to
`launch_app.sh` with its absolute path. Compiling this with `osacompile`
produces a real `.app` bundle.

### Desktop icon (generated artifact, not committed)
Built once via:
```
osacompile -o ~/Desktop/"NHL Stats.app" scripts/launch_app.applescript
```
This produces a double-clickable `.app` on the Desktop with no Terminal
window — functionally identical to hand-building it in Automator.app's GUI,
but scripted and reproducible (can be regenerated with one command if the
Desktop icon is ever lost or the script changes).

### `.gitignore` update
Add `.run/` (log directory) to `.gitignore`.

## Data flow
Double-click Desktop icon → AppleScript shells out to `launch_app.sh` → port
5099 health check → (cold start: venv + deps + server) or (already up: skip
straight through) → browser opens to the app.

## Testing / verification
- Delete `.venv` and double-click the icon → confirm cold start: venv gets
  created, deps installed, server starts, browser opens to a working page.
- Double-click again while the server is still running → confirm it does NOT
  restart the process, just reopens the browser.
- Kill the server process, then double-click again → confirm a clean restart
  and that `.run/app.log` has the new run's output appended.
- Temporarily break `requirements.txt` (bad package name) → confirm the
  failure surfaces as a macOS alert dialog instead of failing silently.
