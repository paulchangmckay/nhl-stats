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
cerebrum/buglog entry about older-season data quality. This spec proceeds on
the recommendation to run all 3 seasons in one pass (user's explicit choice
over a staged single-season spot-check), accepting that any format surprise
surfaces as warning-count spikes in script output rather than being caught
before committing to the full range.

**Confirmed during grilling (live API calls, not speculation):** for
shot-attempt event types specifically (`shot-on-goal`, `missed-shot`,
`blocked-shot`, `goal` — the only types `_is_high_danger()` in
`etl/advanced_stats/sweep.py` is ever called on), `homeTeamDefendingSide` is
**entirely absent** in 2017-18 and 2018-19 (0/124 and 0/136 shot-attempt plays
tested), and **fully present** in 2019-20 (matching current-season behavior).
An earlier partial-coverage reading for 2019-20 (316/376 plays) turned out to
be a red herring: the missing 60 were all `stoppage`/`period-end`/`game-end`
events, which never carry the field in any era and are irrelevant to
high-danger computation. So the real impact is scoped precisely to **2017-18
and 2018-19 only**.

`_is_high_danger()` returns `False` (not an error, not `None`) when
`home_team_defending_side is None` for a given shot. Left unaddressed, this
means HDCF/HDCA for 2017-18/2018-19 wouldn't be *missing* — they'd silently
compute to near-zero, indistinguishable from a real (if implausible) "team
generated almost no high-danger chances" reading. This spec now includes a
fix for that (see Scope item 6 and HD-Stat NULL Propagation below), rather
than shipping data that looks real but isn't.

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
6. **HD-stat NULL propagation** (added during grilling — see HD-Stat NULL
   Propagation section below): a small code change to `etl/advanced_stats/sweep.py`
   and `etl/compute_advanced_stats.py` so that a game with zero rink-side
   coverage on its shot-attempt plays stores `hdcf`/`hdca`/`ihdcf` as `NULL`
   for that game, instead of silently aggregating to a misleadingly-low
   real number.

**Out of scope / non-goals:**
- No new scripts, no CLI-configurable season ranges. The `SEASONS` lists stay
  hardcoded constants — this is a one-time backfill, not a recurring need for
  arbitrary season ranges.
- No changes to `run_all_etl.py` or `scripts/sync.py` — both already iterate
  whatever the `SEASONS` lists (or `sync_log`/`NOT EXISTS` gates) say, so they
  pick up the new seasons automatically once the constants change.
- No changes to `etl/advanced_stats/decoding.py` — its game-ID references
  (e.g. `2020020003`) are illustrative doc comments only, not season-range
  gates. (`sweep.py` **does** change now, per Scope item 6 above — the
  original assumption that it wouldn't need to didn't survive grilling.)
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

## HD-Stat NULL Propagation

`etl/advanced_stats/sweep.py`'s `player_row()`/`team_row()` initialize `hdcf`/
`hdca` (and the individual variant `ihdcf`) as plain integer counters starting
at `0`, incremented whenever `_is_high_danger()` returns `True` for a shot.
There's currently no way to distinguish "this game genuinely had zero
high-danger chances" from "this game's data can't tell us." The fix:

1. **Per-game detection, computed once** (not per-shot): before building
   player/team rows for a game, check whether *any* shot-attempt-type play
   (`shot-on-goal`/`missed-shot`/`blocked-shot`/`goal`) in that game carries a
   non-null `home_team_defending_side`. If none do, mark the game as
   `hd_data_unavailable = True` for the rest of processing.
2. **Row initialization**: when `hd_data_unavailable`, initialize `hdcf`/
   `hdca`/`ihdcf` as `None` instead of `0`, and skip incrementing them
   entirely (incrementing `None` would error, and there's nothing meaningful
   to increment toward anyway).
3. **Season/career aggregation needs no change.** `compute_advanced_stats.py:105`
   already aggregates via `SUM(pgas.hdcf)`, and standard SQL `SUM()` ignores
   `NULL` rows rather than treating them as zero — a player's season HDCF
   naturally sums only across the games where the data actually exists,
   verified by inspection of the existing query rather than assumed.
4. **Percentile/rate computations** (`_hd_pct_of()` at `compute_advanced_stats.py:150`,
   the z-score functions) already guard their denominators (`if (row["hdcf"] + row["hdca"]) else 0`)
   — these need a `None`-check added alongside the existing zero-check, since
   `None + None` raises `TypeError` where `0 + 0` doesn't.

This only affects 2017-18 and 2018-19 per the confirmed data above; every
other season (including the 3 currently in the middle of being added,
2019-20, and all 6 pre-existing seasons) is unaffected and behaves exactly as
today.

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

The `SEASONS`-constant changes and backfill rerun introduce no new logic, so
no new tests are needed for those parts. The HD-stat NULL propagation (Scope
item 6) **does** need new tests, following this project's established TDD
convention (see `tests/test_sweep.py` for the existing per-game aggregation
test pattern): one test confirming a game with zero rink-side coverage on its
shot-attempt plays produces `hdcf`/`hdca`/`ihdcf` as `NULL`, and one
confirming a game with full coverage (today's existing behavior) is
unaffected. Full regression pass: `python -m pytest tests/ -v`,
`node --test tests/js/search.test.js`, and the frontend test runner, all run
after all code changes and before the backfill is considered done, to confirm
nothing implicitly assumed a 6-season range or non-null HD stats.

## Sizing

Current `data/nhl_stats.db` is ~1.5GB for 6 seasons (~8,058 games). 3 more
seasons (~3,900 more games, based on ~1,300 games/season at this league size)
will likely add roughly 700MB-1GB. No disk-space guard exists in any script;
this is a personal-machine consideration, not a code change.
