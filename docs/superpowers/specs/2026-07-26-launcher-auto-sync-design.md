# Launcher Auto-Sync — Design

## Context

The desktop launcher (`scripts/launch_app.sh`, invoked via
`scripts/launch_app.applescript` from the desktop icon) currently does two
things: check if a server is already listening on port 5099 (reuse it if
so), otherwise create/activate a venv, `pip install`, and start
`app.py`. It never touches git state and never builds the frontend — the
`frontend/` bundle in `static/dist/` has always been built manually by
whoever was doing implementation work that session.

This gap surfaced concretely during the 2026-07-25 player-profile-overlay
session: local `main` had diverged from `origin/main` (3 local-only doc
commits — spec/plan files committed directly during brainstorming/
writing-plans — vs. 2 origin-only commits from squash-merged PRs #74/#75),
`static/dist/` was stale relative to even the old local commits, and the
running Flask process (PID recorded via `lsof -iTCP:5099`) had been up
since before that session's work even started. The desktop icon was
serving code from a checkout that had never seen the actual feature.

This divergence pattern is structural, not a one-off mistake: this
project's `main` branch has `enforce_admins: true` branch protection (no
required review count, but no direct push regardless), so all real feature
work happens in a worktree, merged to `origin/main` via PR — while spec/plan
docs get committed straight to local `main` during brainstorming (git has
no branch-protection concept for local commits, only for pushes). Every
worktree-based feature this project ships will reproduce the same
divergence unless something reconciles it.

## Scope

In scope:
1. Add a sync step to `scripts/launch_app.sh`, run at the start of every
   launch, before the existing "is a server already running?" check.
2. Sync sequence: record current HEAD SHA → if working tree dirty,
   `git stash -u` → `git fetch origin` → `git rebase origin/main` → pop the
   stash → compare HEAD SHA before/after.
3. Rebase conflict handling: abort the rebase (`git rebase --abort`),
   restore the stash if it was popped as part of the abort path, alert via
   `osascript` (matching the script's existing alert pattern) telling the
   user to resolve manually in a terminal, then continue to launch on
   whatever was checked out before the sync attempt (never leave the user
   with no working app).
4. Offline/fetch-failure handling: log to `.run/app.log`, no dialog, launch
   proceeds on local state as-is.
5. Rebuild/restart decision: if the HEAD SHA is unchanged after sync AND
   `static/dist/` exists, behave exactly as today (reuse a running server
   via the existing `is_up` check, or cold-start without a rebuild). If the
   SHA changed, OR `static/dist/` is missing entirely (first-ever run),
   kill whatever process is listening on port 5099 (via `lsof -nP -iTCP:5099
   -sTCP:LISTEN`, extract PID, `kill`), run `npm install && npm run build`
   in `frontend/`, then start `app.py` fresh.
6. No new background processes, cron jobs, or launchd agents — sync only
   ever runs synchronously inside a launch, per the "on every launch"
   decision.

Out of scope:
- Any change to the branch-protection settings, PR/worktree workflow
  itself, or how spec/plan docs get committed during brainstorming.
- Handling merge/rebase conflicts automatically beyond the abort-and-alert
  path above — a real conflict always needs a human.
- A background poller/watcher that syncs while the app isn't being
  launched (explicitly declined in favor of the launch-time-only trigger).
- Changing what `app.py` serves or how the Flask app is structured.

## Sync Flow

```
launch_app.sh:
  1. cd "$PROJECT_DIR"
  2. BEFORE_SHA=$(git rev-parse HEAD)
  3. DIRTY=false; if `git status --porcelain` non-empty: git stash -u; DIRTY=true
  4. git fetch origin  (on failure: log, skip to step 8 with AFTER_SHA=BEFORE_SHA)
  5. git rebase origin/main
     - on success: continue
     - on conflict: git rebase --abort; if DIRTY: git stash pop; osascript alert
       "Auto-sync hit a conflict — resolve manually in a terminal, then
       relaunch."; continue to step 8 with AFTER_SHA=BEFORE_SHA
  6. if DIRTY: git stash pop
  7. AFTER_SHA=$(git rev-parse HEAD)
  8. NEEDS_REBUILD = [ "$AFTER_SHA" != "$BEFORE_SHA" ] || [ ! -d static/dist ]
  9. if NEEDS_REBUILD:
       - find PID on port 5099 (lsof -nP -iTCP:5099 -sTCP:LISTEN); if found:
         kill $PID (SIGTERM); poll is_up for up to ~3s; if still up, kill -9 $PID
       - if `git diff --name-only "$BEFORE_SHA..$AFTER_SHA"` touches
         frontend/package.json or frontend/package-lock.json: (cd frontend && npm install)
       - (cd frontend && npm run build)
  10. proceed with existing is_up / venv / pip / start-server logic unchanged,
      except is_up check is skipped when NEEDS_REBUILD was true (we just
      killed it) — go straight to starting the server fresh.
```

## Error Handling

- **Offline / fetch fails**: silent, logged, launch continues on local
  state. This is the routine case (working with no wifi) and must not
  interrupt normal use.
- **Rebase conflict**: the one case that alerts via dialog, since it needs
  the user's attention and can't be auto-resolved safely. The stash-pop
  happens as part of the abort recovery so no uncommitted work is lost.
- **npm install/build failure**: treat like the script's existing
  `pip install` failure handling — alert via `osascript` with a pointer to
  `.run/app.log`, exit 1 (don't half-start a server against a stale or
  missing bundle).
- **Stash pop conflict** (theoretical — the stashed files are daemon-
  appended `.wolf/*.md`/log files, unlikely to conflict with a rebase of
  doc/code commits, but not impossible): alert via `osascript`, leave the
  stash in place (never drop it), continue launching on whatever state
  resulted from the rebase.

## Testing Plan

Since this is a shell script with no existing test harness in this
project, verification is manual per `verification-before-completion`:
- Clean case: no local commits ahead, no origin commits ahead → launcher
  behaves identically to today (reuse running server or cold-start,
  no rebuild).
- Fast-forward case: origin has new commits, local has none ahead → sync
  pulls them, SHA changes, triggers rebuild + restart.
- Rebase case: local has unpushed doc commits, origin has new PR-merged
  commits (reproducing the actual 2026-07-25 divergence) → rebase
  succeeds, local doc commits preserved on top, SHA changes, rebuild
  triggers.
- Dirty-tree case: uncommitted `.wolf/*` changes present during sync →
  stash/rebase/pop completes cleanly, changes still present after launch.
- Offline case: disconnect network, launch → no dialog, app starts on
  current local state, failure logged.
- Conflict case (manually contrived): force a real conflicting change →
  alert appears, rebase aborted, previous state restored, app still
  launches.
