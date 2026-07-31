# Historical Data Expansion (2017-18 to 2019-20) — Design

## Context

The database currently covers 6 seasons: `20202021` through `20252026`, hardcoded
as `SEASONS` constants in `etl/load_historical_schedule.py` and
`etl/load_season_stats.py`, and mirrored in `frontend/src/components/SeasonPicker.tsx`.
The user wants 3 more years of historical data added: `20172018`, `20182019`,
`20192020`, extending the range backward to 9 total seasons.

No other backend code depends on the season range — `app.py`'s advanced-stats
endpoints derive available seasons dynamically (`MAX(season_id)`/`SELECT DISTINCT`
against the DB), and no validation rejects season IDs outside 2020-2026. The two
`SEASONS` lists plus the frontend list are the only hardcoded update points
(confirmed via codebase search — see Non-Goals for what was checked and ruled out).

Pre-2020 NHL data is untested territory for this project: there is no prior
cerebrum/buglog entry about older-season data quality, and community knowledge
suggests older shift-chart/play-by-play data can be sparser or differently
formatted than recent seasons. This spec proceeds on the recommendation to run
all 3 seasons in one pass (user's explicit choice over a staged single-season
spot-check), accepting that any format surprise surfaces as warning-count spikes
in script output rather than being caught before committing to the full range.

## Scope

**In scope:**
1. Extend `etl/load_historical_schedule.py`'s `SEASONS` list with the 3 new
   season IDs, prepended before the existing 6.
2. Extend `etl/load_season_stats.py`'s `SEASONS` list the same way, preserving
   `"20252026"` as the **last** entry — `run()`'s `current_season = SEASONS[-1]`
   logic depends on this position to know which season to always re-fetch instead
   of skipping via `sync_log`.
3. Extend `frontend/src/components/SeasonPicker.tsx`'s `SEASONS` array with the 3
   matching `{ id, label }` entries (e.g. `{ id: "20192020", label: "2019–20" }`).
4. Run the existing one-time historical-backfill sequence (already documented in
   `README.md`) against the updated `SEASONS` lists, in this order:
   1. `python -m etl.load_historical_schedule`
   2. `python -m etl.load_boxscores`
   3. `python -m etl.load_play_by_play`
   4. `python -m etl.load_shifts`
   5. `python -m etl.backfill_defending_side`
   6. `python -m etl.compute_advanced_stats`
   7. `python etl/load_season_stats.py`
   8. `python etl/enrich_players.py`
5. Run the existing test suites (`pytest tests/ -v`, `node --test tests/js/search.test.js`,
   plus `frontend`'s test runner) afterward as a regression check.

**Out of scope / non-goals:**
- No new scripts, no CLI-configurable season ranges. The `SEASONS` lists stay
  hardcoded constants — this is a one-time backfill, not a recurring need for
  arbitrary season ranges.
- No changes to `run_all_etl.py` or `scripts/sync.py` — both already iterate
  whatever the `SEASONS` lists (or `sync_log`/`NOT EXISTS` gates) say, so they
  pick up the new seasons automatically once the constants change.
- No changes to `etl/advanced_stats/decoding.py` or `sweep.py` — their game-ID
  references (e.g. `2020020003`) are illustrative doc comments only, not
  season-range gates.
- Frontend/backend test files were checked (`SeasonPicker.test.tsx`,
  `Toolbar.test.tsx`, `App.test.tsx`, `PlayerProfilePanel.test.tsx`,
  `tests/test_load_historical_schedule.py`) — none assert the full season list
  or a specific season count, only sample against individual season IDs like
  `"20252026"`. No test changes are required as part of this work.

## Data Flow

Every step in the backfill sequence already gates on "not yet loaded" (either a
`NOT EXISTS` subquery against `games`/`game_events`/`player_shifts`, or a
`sync_log` check), so re-running the full sequence against a DB that already has
6 seasons loaded only touches games belonging to the 3 new seasons — nothing
existing is re-fetched or modified. This is the same idempotent/resumable
property the README already documents for the original 6-season backfill.

`etl/backfill_defending_side.py` is included even though `load_play_by_play.py`
already captures `home_team_defending_side` inline during normal ingestion
(`play.get("homeTeamDefendingSide")` in `_extract_event`). It's kept as a
zero-cost safety net: its query (`WHERE ge.home_team_defending_side IS NULL`) is
a no-op if the older seasons' API responses include the field like current
seasons do, and fills the gap automatically if they don't — without needing to
know in advance which case applies.

## Error Handling

No new error-handling code. Every existing script already wraps per-game API
calls in try/except, logs a warning, and continues (never aborts the whole run
on one bad game) — this behavior is inherited as-is for the 3 new seasons. The
one behavioral difference to watch for: since pre-2020 data is unverified for
this codebase, a spike in "Warning: could not fetch/insert ..." lines during the
run (versus the near-zero warning rate seen on the existing 6 seasons) is the
signal that something about the older API responses doesn't match current
assumptions. This isn't a new mechanism — it's reading the same output the
existing scripts already produce, just with the expectation that it needs a
closer look on this run than it normally would.

## Testing

No new logic is introduced (this is a data-constant change plus reruns of
existing, already-tested ETL scripts), so no new unit tests are needed. Full
regression pass: `python -m pytest tests/ -v`, `node --test tests/js/search.test.js`,
and the frontend test runner, all run after the constant changes and before the
backfill is considered done, to confirm nothing implicitly assumed a 6-season
range.

## Sizing

Current `data/nhl_stats.db` is ~1.5GB for 6 seasons (~8,058 games). 3 more
seasons (~3,900 more games, based on ~1,300 games/season at this league size)
will likely add roughly 700MB-1GB. No disk-space guard exists in any script;
this is a personal-machine consideration, not a code change.
