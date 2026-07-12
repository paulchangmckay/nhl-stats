# ETL & Sync Behavior — Design

## Context

The project has 7 ETL scripts (`etl/load_teams.py`, `load_standings.py`, `load_rosters.py`, `load_schedule.py`, `load_boxscores.py`, `load_season_stats.py`, `enrich_players.py`) and two manual orchestrators (`scripts/run_all_etl.py` for full rebuild, `scripts/sync.py` for a partial incremental sync). There is no scheduler, no concurrency guard, and only one script (`load_season_stats.py`) uses `sync_log` to skip already-done work.

Bugs fixed earlier this session (missing bio data, missing `position_code`, a WHERE-clause dead zone in `enrich_players.py`) all stemmed from the same underlying gap: there was never an explicit, agreed policy for *when* each ETL step should run, *what* it's allowed to overwrite, and *how* overlapping runs are prevented. This spec defines that policy so future ETL changes have a standard to follow instead of being decided ad hoc per script.

## Goals

- One unified sync pipeline, reused by both a weekly scheduled run and an on-demand run triggered from the app.
- Each step independently decides whether it needs to hit the NHL API (freshness window) and whether a fetched value is worth writing (diff-before-write), so repeated syncs are cheap.
- A clear, stated rule for which fields each step is allowed to overwrite vs. only fill in when missing.
- No two syncs run concurrently.
- A failure in one step doesn't stop the rest of the pipeline.
- The on-demand trigger is a button in the Flask app with a live-updating status view.

## Non-Goals

- Real-time/webhook-driven updates. The NHL API doesn't offer this; "on-demand" is a manual trigger, not push-based.
- Historical season stats re-validation. Once a past season is loaded and recorded in `sync_log`, it's treated as immutable and never re-fetched.
- Per-step manual triggers in the UI (e.g. "sync only rosters"). The button always runs the full pipeline.

## 1. Trigger & Orchestration

- **On-demand**: a "Sync" button in the Flask app's UI calls an endpoint that invokes the pipeline in the background (non-blocking) and returns immediately.
- **Weekly**: a `launchd` job (user-level, macOS-native — survives sleep/wake better than cron, which silently skips missed windows) invokes the same pipeline via CLI on a weekly schedule.
- **Single pipeline function**: both triggers call one orchestration function (replacing the current split between `run_all_etl.py` and `sync.py`). There is no "light" vs "full" mode — every sync runs all 7 steps in this order:

  1. Teams
  2. Standings
  3. Rosters
  4. Schedule
  5. Boxscores
  6. Season Stats
  7. Enrichment

  This order is preserved because later steps depend on earlier ones (e.g. boxscores need games from Schedule; season stats and enrichment need player stubs that Rosters/Season Stats create).

## 2. Freshness Windows & Diff-Before-Write

Two independent gates apply to every step:

- **Freshness window** — before calling the NHL API at all, check `sync_log` for that step's key. If the last successful run is within the window, skip the API call entirely.
- **Diff-before-write** — for steps that gain this behavior, after fetching, compare each candidate row to the current DB row. Only issue an UPDATE if at least one column differs. This keeps `updated_at` meaningful (it reflects the last real change, not the last time a sync happened to run) and avoids no-op write churn.

| Step | Freshness window | Write behavior |
|------|------|------|
| Teams | 30 days | Blind overwrite (near-static; diffing isn't worth the complexity) |
| Standings | 6 hours | **Diff-before-replace** (changed — see note below) |
| Rosters | 24 hours | **Diff-before-write** (new) |
| Schedule | 6 hours | `INSERT OR IGNORE` (already idempotent) |
| Boxscores | 6 hours | Already delta — only processes completed games with no existing `player_game_stats` rows |
| Season stats (current season) | 6 hours | Blind overwrite (small daily deltas; low cost) |
| Season stats (historical seasons) | Never re-fetch once loaded | One-time load, tracked via `sync_log` key per season |
| Enrichment | 7 days for active players; immediate for any player missing a tracked field | Already delta — `COALESCE`-based fill, see §3 |

**`sync_log` key scheme**: each step (and, where relevant, each sub-unit like a historical season) gets its own key, e.g. `teams:full`, `standings:<date>`, `rosters:full`, `schedule:full`, `boxscores:full`, `season_stats:current`, `season_stats:<season_id>`, `enrichment:full`. The pipeline checks the relevant key(s) before running a step and writes/updates them on success.

**Note on standings — behavior change from current code**: standings today uses `INSERT OR IGNORE` on `(snapshot_date, team_id)`, so a same-day resync after more games finish is silently dropped — the row for today already exists and is never touched again until tomorrow. That's inconsistent with a 6-hour freshness window, which implies later same-day syncs should pick up new results. This design changes standings to **diff-before-replace**: if a row for today's `snapshot_date` already exists, compare it to the freshly fetched data and `UPDATE` it in place if anything differs, rather than ignoring the write. The table still holds one row per team per day (a daily snapshot log across days), but that day's row is now allowed to be refined as the day progresses instead of being frozen at whatever the first sync captured.

## 3. Data Authority Rules

This formalizes the pattern already applied to fix the `position_code` and bio-data bugs this session, as a standing rule for all future ETL work:

- **Rosters are authoritative** for identity fields, current team, position, and roster-supplied bio data. When diffing finds the API disagrees with the DB, the API value wins and overwrites.
- **Enrichment is fill-only.** It never overwrites a value that Rosters or a prior Enrichment run already set. It writes via `COALESCE(existing_column, new_value)`, so it only populates currently-`NULL` fields. The exception is bookkeeping fields it owns outright (`is_active`, `enriched_at`, draft fields, career totals) — those are always written by Enrichment since no other step touches them.
- Any new ETL step must state, in its own header comment, which of these two categories it belongs to (authoritative-overwrite or fill-only) for each field it touches.

## 4. Concurrency & Error Handling

- **Concurrency guard**: a dedicated `sync_log` (or equivalent) key, e.g. `sync:running`, is written at pipeline start and cleared at pipeline end (including on failure — the clear happens in a `finally`). If a trigger (button click or `launchd` firing) finds this key set, it refuses to start a new sync and reports "sync already running" instead of overlapping.
- **Error handling**: log-and-continue per step. If a step raises, the pipeline records the failure against that step, moves on to the next step, and that step's data simply remains stale until the next successful sync. The pipeline as a whole does not abort on a single step's failure.

## 5. Status Reporting

- The pipeline records per-step status (`pending` / `running` / `done` / `failed`) as it executes, in a small persisted location the Flask app can read (a `sync_status` table, or a JSON status file — implementation detail for the plan stage).
- The Sync button's page polls this status at a short interval while a sync is active and renders live progress (e.g. "✓ Teams · ✓ Standings · ⟳ Rosters · … · ✗ Boxscores (failed) · …").
- When the pipeline finishes, the affected tables in the UI refresh automatically.

## Files Likely Touched (for planning reference)

- `scripts/run_all_etl.py`, `scripts/sync.py` → collapse into one pipeline module (e.g. `etl/pipeline.py` or similar)
- `src/database.py` → `sync_log` helpers extended for per-step keys, plus a `sync:running` lock and status read/write helpers
- `etl/load_standings.py`, `etl/load_rosters.py` → add diff-before-write
- `app.py` → new sync-trigger endpoint + status endpoint
- `templates/index.html` → Sync button + live status polling UI
- New: a `launchd` plist for the weekly schedule

## Open Questions for the Plan Stage

None outstanding — all decisions above were confirmed during design discussion.
