# Shot Generation & Playmaking Rate Stats (Phase 1) — Design

## Context

The user asked for a large set of new player metrics across 7 categories: General
Offense, Passing, Offense Types, Zone Entries, DZ Retrievals & Exits,
Forechecking, and Normalization/Z-Scores. Cross-checking the raw data points each
category needs against what this project actually ingests (`etl/load_play_by_play.py`
→ `game_events`, `etl/load_shifts.py` → `player_shifts`, both sourced exclusively
from the NHL's free public API) surfaced a feasibility gap that two prior specs
already flagged: `2026-07-17-play-by-play-ingestion-design.md` and
`2026-07-22-advanced-analytics-design.md` both explicitly rule "microstats (zone
entries/exits, hand-tracked passes, forechecking)" out of scope, since the NHL's
public feed contains no pass events, no possession tracking, and no entry-style
classification — only discrete shot/goal/faceoff/giveaway/takeaway/hit/penalty
events with `x_coord`/`y_coord`, `zone_code`, `shot_type`, and `situation_code`.

The user confirmed (mid-brainstorm) that `hockeyR` (R) and `nhlpy` (Python) don't
change this: both are wrappers/scrapers over the same NHL.com public feed this
project already queries directly — `hockeyR` adds a derived xG model, `nhlpy` adds
nothing beyond convenience methods. Neither exposes passing, zone-entry-style,
retrieval, or forechecking-pressure data.

**This spec covers only the subset of the original 7-category request that's
buildable from data already on disk.** Everything else is named explicitly under
Phase 2 below so it isn't silently forgotten, and is blocked on acquiring a new
data source (a paid provider such as Sportlogiq/Stathletes, NHL Edge tracking
data, or manual/hand-charting) — a decision the user hasn't made and this spec
doesn't make for them.

This phase extends `2026-07-22-advanced-analytics-design.md`'s
`player_game_advanced_stats` → `player_season_advanced_stats` →
`player_career_advanced_stats` → percentile aggregation chain (verified directly
against the current `src/database.py` schema and `etl/advanced_stats/sweep.py`,
which have not materially changed since that spec shipped) rather than building a
parallel system.

## Scope

**In scope (Phase 1) — six new per-player, 5v5-only rate stats:**

1. **Shots/60** — individual shot attempts (on goal + missed + blocked + goal),
   credited only to the shooter, not the whole on-ice unit. This is a new
   "individual Corsi For" (`icf`) counter, distinct from the existing on-ice
   `cf`/`ca` counters that credit every on-ice skater.
2. **Chances/60** — individual high-danger shot attempts (`ihdcf`), reusing the
   existing `_is_high_danger()` slot-area definition from `sweep.py` verbatim, but
   crediting only the shooter.
3. **Rebounds Created/60** — a shot attempt is a "rebound" if another shot attempt
   by the same team follows within 3 seconds. Credited to the **original**
   shooter (the shot that created the second-chance opportunity), not the
   rebound shooter. Heuristic: no possession data exists to confirm the rebound
   was actually off a loose puck vs. a new clean look, so this is a
   time-proximity proxy — the same kind of heuristic public sites like Natural
   Stat Trick use for "rebound shots," not a novel invention. Documented as a
   heuristic in the API doc (see Documentation). **No same-player exclusion**:
   if the same player takes both shots (e.g. their own rebound bounces right
   back to them), it still counts — the definition is same-team-within-3-seconds
   only, not same-team-different-player, since the player still generated a
   genuine second-chance opportunity and a same-player exclusion would add its
   own edge cases (e.g. a third player's shot interleaved between two of the
   same player's shots) to an already-approximate heuristic.
4. **Deflections/60** — individual shot attempts with `shot_type IN ('deflected',
   'tip-in')` (both values confirmed present in the live `game_events` table).
   Pure data flag, no heuristic.
5. **Points/60** — goals + primary assists + secondary assists, 5v5 only, per 60
   minutes of 5v5 TOI. New `points` counter alongside the existing
   `primary_points` counter.
6. **Primary Points/60** — the existing `primary_points` counter (goal + primary
   assist only, already computed), newly exposed as a per-60 rate. No new raw
   data needed, only the rate calculation.

Plus: **true z-score normalization** for these six stats — `z = (player_rate -
group_mean) / group_stddev`, grouped by position (F/D), 5v5 only (the user's
raw-data list specifies "On-Ie 5v5 Time On Ice" as the sole TOI input, so unlike
the existing percentile system — which covers 5v5/5v4/4v5 — this phase's z-scores
are 5v5-only by the user's own stated scope, not a limitation). Same 10-GP
qualifying floor as the existing percentile system. Added **alongside** the
existing percentile-rank system, not replacing it — existing CF%/FF%/HDCF%
percentile boxes are untouched.

Also in scope: extending `_fetch_player_advanced()`'s response, a new "Shot
Generation" section in `PlayerProfilePanel`, one new teaser column on
`PlayerTable`, and a new API reference doc (see Documentation).

**Explicitly out of scope within Phase 1** (found while pinning down exact
definitions):

- **Shot Assists/60, Primary Contributions/60, Total Shot Contributions/60,
  Chance Contributions/60, Chance Assists/60** — the user's original definitions
  require pass-attribution data for shots that *aren't* goals (e.g. "the final
  pass to a shot that missed the net"). The NHL API only records assists on
  *goals*. Points/60 and Primary Points/60 (goal-based) are the substitute the
  user approved; the shot-assist-flavored versions are not built.
- **Rush Offense/60, Cycle & Forecheck Offense/60** — classifying a shot as
  "rush" vs. "cycle" requires detecting zone entries, which requires possession
  tracking the NHL feed doesn't have (only discrete zone-coded events, no
  continuous "who has the puck" signal). The user chose to defer this rather
  than ship a low-confidence heuristic. See Phase 2.
- **One-timers/60** — distinct from Deflections/60, this needs pass-to-shot
  timing data (was there a preceding pass, and how fast was the shot after
  receiving it) that doesn't exist in the feed. Deferred to Phase 2 alongside
  Passing.

**Phase 2 (deferred, not built in this spec)** — named explicitly so a future
session doesn't re-derive this from scratch:

- **Passing** (entire category): Point Shot Setups/60, Passes from Center
  Lane/60, High Danger Assists/60, Deflection Assists/60, One-timer Assists/60.
  Blocked on pass origin/destination coordinates — not in the NHL public feed at
  all.
- **Zone Entries** (entire category): Zone Entries/60, Controlled Entry%,
  Controlled Entries/60, Entries w/ Passing Play/60, Entries w/ Chances/60, Entry
  w/ Pass%, Controlled Entry w/ Chance%. Blocked on entry-style classification
  (carried/passed/dumped) — not derivable from zone-coded discrete events without
  possession tracking.
- **DZ Retrievals & Exits** (entire category): all 12 stats. Blocked on the same
  possession-tracking gap.
- **Forechecking** (entire category): Pressures/60, Recovered Dump-ins/60.
  Blocked on proximity/pressure data (would need NHL Edge tracking data or manual
  charting).
- Rush Offense/60, Cycle & Forecheck Offense/60, One-timers/60, Shots off HD
  Passes/60 (see above — these were part of the original ask's Offense Types
  category but share the same possession/passing data gap).

Unblocking Phase 2 requires a deliberate data-sourcing decision (paid provider,
NHL Edge, or manual tracking) that is out of scope for this spec to make.

## Data Model

New columns on `player_game_advanced_stats` (verified against the live schema in
`src/database.py:222`), following the existing abbreviation convention
(`cf`/`ca`/`ff`/`fa`/`hdcf`/`hdca`):

```sql
ALTER TABLE player_game_advanced_stats ADD COLUMN icf              INTEGER DEFAULT 0;
-- individual Corsi For: this player's own shot attempts (on goal + missed +
-- blocked + goal), NOT the on-ice-credit cf column (which credits every
-- on-ice skater regardless of who shot).
ALTER TABLE player_game_advanced_stats ADD COLUMN ihdcf            INTEGER DEFAULT 0;
-- individual High-Danger Corsi For: this player's own shot attempts inside the
-- existing _is_high_danger() slot definition (sweep.py:16-25), reused verbatim.
ALTER TABLE player_game_advanced_stats ADD COLUMN rebounds_created INTEGER DEFAULT 0;
-- credited to the ORIGINAL shooter when another shot attempt by the same team
-- follows within 3 seconds (see Computation Algorithm).
ALTER TABLE player_game_advanced_stats ADD COLUMN deflections      INTEGER DEFAULT 0;
-- individual shot attempts where shot_type IN ('deflected', 'tip-in').
ALTER TABLE player_game_advanced_stats ADD COLUMN points           INTEGER DEFAULT 0;
-- goals + assist1 + assist2 (primary_points only counts goal + assist1).
```

Same five columns, same meaning, added to `player_season_advanced_stats` (summed
via `GROUP BY`, matching `compute_season_aggregates()`'s existing pattern
exactly) and to `player_career_advanced_stats` with the existing `rs_`/`po_`
prefix convention (`rs_icf`, `po_icf`, etc.).

New table for z-scores, structurally parallel to the existing
`player_advanced_percentiles` (`src/database.py:348`) but 5v5-only per Scope:

```sql
CREATE TABLE player_rate_zscores (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id                   TEXT NOT NULL,
    player_id                   INTEGER NOT NULL REFERENCES players(player_id),
    position_group              TEXT NOT NULL,   -- 'F' or 'D'
    shots_per60_z               REAL,
    chances_per60_z             REAL,
    rebounds_created_per60_z    REAL,
    deflections_per60_z         REAL,
    points_per60_z              REAL,
    primary_points_per60_z      REAL,
    created_at                  TEXT DEFAULT (datetime('now')),
    UNIQUE (season_id, player_id)
);
```

No `strength_state` column (unlike `player_advanced_percentiles`) since this
table is 5v5-only by design — a future phase that extends z-scores to other
strength states would add the column back rather than this spec speculatively
including it now.

Rates themselves (Shots/60 etc.) are **not stored** — computed at API-response
time from `icf`/`toi_seconds` etc., exactly matching how `cf_pct` is already
computed in `app.py`'s `_fetch_player_advanced()` rather than stored in the DB.

## Computation Algorithm

Extends `compute_game_advanced_stats()` in `etl/advanced_stats/sweep.py` with two
additions, in the same function, no second pass over `game_events`:

1. **Individual shot-attempt credit** — inside the existing shot-attempt loop
   (`sweep.py:145-202`), alongside the on-ice `cf`/`ff`/`hdcf`/`gf` credit already
   given to every on-ice skater, add a single additional credit to
   `player_row(e["shooting_player_id"], owner, strength_for)`: `icf += 1`,
   `ihdcf += 1` if `high_danger`, `deflections += 1` if
   `e.get("shot_type") in ("deflected", "tip-in")`. This requires
   `_load_events_for_sweep()` in `etl/compute_advanced_stats.py` to also select
   `shot_type` (currently not in its `SELECT` list — see that function at
   `etl/compute_advanced_stats.py:76`).
2. **Rebound detection** — a new single pass over the already-time-sorted
   `event_list`, independent of on-ice reconstruction (same style as the
   existing primary-points loop at `sweep.py:96-108`, which is also
   on-ice-independent). Track `last_shot_attempt = {team_id: (t, shooting_player_id)}`
   as events are walked in order. For each shot-attempt event: if
   `last_shot_attempt.get(owner)` exists and `t - last_shot_attempt[owner][0] <= 3`,
   credit `rebounds_created += 1` to `last_shot_attempt[owner][1]` (the **prior**
   shooter, not the current one) at that prior shot's strength state; then update
   `last_shot_attempt[owner] = (t, current shooting_player_id)` regardless of
   whether this shot counted as a rebound. This means each original shot can
   "create" at most one credited rebound (the next same-team shot attempt within
   the window) rather than crediting every subsequent shot in a scramble back to
   the same original shooter — a defensible starting default per this project's
   existing "pin a boundary, revisit if numbers look off" pattern (see
   `sweep.py:8-11`'s HD-zone comment for precedent), not a literature constant.
3. **Points** — extend the existing goal-event loop (`sweep.py:96-108`): alongside
   the existing `primary_points` credit to `scorer` and `assist1`, add `points +=
   1` to `scorer`, `assist1`, **and** `assist2` (if `e.get("assist2_player_id")`
   is present) — `primary_points` logic is unchanged, `points` is a new sibling
   counter computed in the same loop.

`compute_season_aggregates()` picks up the five new columns via its existing
generic `SUM(...)` pattern — a column-list edit, no new logic
(`etl/compute_advanced_stats.py:88-115`).

**Z-score computation** — new function `compute_zscores(conn, season_id)`
alongside the existing `compute_percentiles()` in `etl/compute_advanced_stats.py`,
called from `_run_aggregation_and_percentiles()` next to the existing
`compute_percentiles(conn, season_id)` call. Same query shape as
`compute_percentiles()` (position-group filter, `PERCENTILE_MIN_GP` floor,
`WHERE strength_state = '5v5'` since this table has no strength-state
dimension), **plus one addition `compute_percentiles()` is missing**: an
explicit `AND psas.game_type = 2` filter (regular season only).
`player_season_advanced_stats` carries a `game_type` dimension (2 = regular
season, 3 = playoffs) with a separate row per player per `game_type`, but
`compute_percentiles()`'s query (`etl/compute_advanced_stats.py:132-140`) has no
`game_type` filter at all — a player who made the playoffs gets both their
regular-season and playoff rows pulled into the same population/percentile
undifferentiated. That's a pre-existing gap in code this spec builds on, not
introduced by this phase; **it is not fixed as part of this spec** (different
function, different blast radius, own investigation) but is logged as a known
issue for a future fix (see `.wolf/buglog.json`). `compute_zscores()` avoids
inheriting it by filtering explicitly — regular season only, since playoff
sample sizes are almost always too small to clear the new 20-player population
floor anyway (see below). Continuing: `rate = raw_count / (toi_seconds / 3600.0)`
per player
before taking the population mean/stddev per position group. A `toi_seconds = 0`
player is excluded from the population entirely (already effectively excluded by
the existing 10-GP floor, but explicit here since division by zero is the
specific new failure mode this computation introduces that `compute_percentiles`
didn't have). Population stddev of 0 (a degenerate case, e.g. every qualifying
player has an identical rate) → z-score `0.0` for all players in that group
rather than a division-by-zero, matching `_percentile_rank()`'s existing
single-player-population special case (`etl/compute_advanced_stats.py:170-176`)
in spirit.

**Minimum population size**: unlike `compute_percentiles()` (which computes for
any non-empty population, even n=2), `compute_zscores()` requires at least
`ZSCORE_MIN_POPULATION = 20` qualifying players in a given `(season_id,
position_group)` before computing any z-scores for that group — below that, a
mean/stddev is statistically unstable enough that a z-score would misrepresent
noise as a real outlier. Below the floor, every player in that group gets `NULL`
for all six z-score fields (no row written to `player_rate_zscores` for them)
rather than a computed-but-meaningless value. Same "defensible starting default,
not a literature constant, tune later without a schema change" status as
`PERCENTILE_MIN_GP` (`etl/compute_advanced_stats.py:10`).

## Operability

No new NHL API calls, no new backfill script — this phase computes entirely from
`game_events`/`player_shifts` data already on disk (unlike the 2026-07-22 spec's
`home_team_defending_side` gap-fill, which this phase depends on being already
complete). `player_game_advanced_stats` rows for already-processed games do
**not** automatically get the five new columns backfilled just by the migration
running — since `run()`'s gating (`etl/compute_advanced_stats.py:16-20`) is `NOT
EXISTS (... player_game_advanced_stats ...)`, already-processed games will never
be reprocessed by the normal incremental path. This spec therefore requires a
**one-time full recompute**: `DELETE FROM player_game_advanced_stats` (and the
season/career/percentile/zscore tables it feeds) before running
`python -m etl.compute_advanced_stats` once, rather than relying on incremental
gating to backfill the new columns. This mirrors the existing module's own
docstring precedent at `etl/compute_advanced_stats.py:44-50` (aggregation/
percentile steps re-run in full every time, cheap local SQL, no API calls) —
the per-game sweep step is the one exception normally gated by `NOT EXISTS`, and
this one-time recompute is the deliberate exception to that gating, not a
permanent change to it.

**Required before the DELETE:** back up the database file
(`cp data/nhl_stats.db data/nhl_stats.db.bak-$(date +%Y%m%d)` or equivalent) —
this is a destructive statement against the only copy of ~8,058 games' worth of
already-computed advanced stats, and the per-game `try/except` (see Error
Handling) means a failure partway through the recompute leaves the tables
partially or fully empty rather than rolling back. **All four advanced-stats
tables (`player_game_advanced_stats`, `player_season_advanced_stats`,
`player_career_advanced_stats`, `player_advanced_percentiles`) — not just the
ones this phase adds columns to — are empty for the entire duration of the
recompute**, since the season/career/percentile steps read from the per-game
table this phase deletes first. For a single-developer local SQLite file this is
acceptable (no concurrent users to disrupt), but it's a real, if brief, window
where `/api/players/<id>/advanced` returns empty results for every player, not
a purely cosmetic footnote.

## API Layer

Extends the existing `GET /api/players/<player_id>/advanced` response (no new
route — matches this project's "one advanced-stats payload per player"
convention already established by the 2026-07-22 spec). `_fetch_player_advanced()`
in `app.py` adds, per strength state where relevant (in practice only `5v5` will
have these fields populated, since rates/z-scores are 5v5-only):

```json
{
  "strength_states": {
    "5v5": {
      "...": "existing cf/ca/ff/fa/hdcf/hdca/primary_points fields, unchanged",
      "shots_per60": 12.3,
      "chances_per60": 4.1,
      "rebounds_created_per60": 0.8,
      "deflections_per60": 0.5,
      "points_per60": 2.1,
      "primary_points_per60": 1.6,
      "shots_per60_z": 0.87,
      "chances_per60_z": 1.42,
      "rebounds_created_per60_z": -0.31,
      "deflections_per60_z": 0.05,
      "points_per60_z": 1.10,
      "primary_points_per60_z": 0.95
    }
  }
}
```

Rates computed as `raw_count / (toi_seconds / 3600.0) if toi_seconds else None`
(mirrors the existing `_pct()` helper's zero-denominator handling already used
for `cf_pct` etc.). Both the six rate fields and the six z-score fields are
rounded to 2 decimal places (`round(value, 2)`) before being placed in the
response — independent of whatever precision `_pct()` uses internally for
percentages, since these are a different unit (a per-60 rate and a standard
score, not a 0-1 ratio) and 2 decimals is enough resolution to distinguish
players without implying false precision. Z-score fields are `None` when the
player didn't clear the 10-GP floor or `player_rate_zscores` has no row for
them (same "sparse, join and allow null" pattern the existing percentile fields
already use).

## Frontend

- `PlayerProfilePanel` gets a new "Shot Generation" section, placed after the
  existing CF%/FF%/HDCF%/Primary Points percentile-box row, using the same
  color-coded box pattern but keyed off z-score sign/magnitude instead of a 0-100
  percentile (e.g. z ≥ 0 green-leaning, z < 0 red-leaning, matching the existing
  ≥50/<50 percentile convention's spirit) — six boxes: Shots/60, Chances/60,
  Rebounds Created/60, Deflections/60, Points/60, Primary Points/60.
  Rebounds Created/60's box includes a tooltip noting it's a time-proximity
  heuristic, not a possession-confirmed stat (see Scope item 3). A box whose
  z-score is `null` (player below the 10-GP floor, or the season/position-group
  population fell below `ZSCORE_MIN_POPULATION`) renders greyed-out with "N/A"
  text instead of a color-coded value, plus a tooltip stating the specific
  reason (distinguishing "not enough games played" from "league sample too small
  this season" rather than one generic message) — keeps the 6-box grid layout
  stable across players rather than the grid reflowing per-player.
- `PlayerTable` gets exactly one new teaser column, `Shots/60 (5v5)`, following
  the existing single-teaser-column convention (`cf_pct_5v5` today).
- `frontend/src/lib/types.ts` — `PlayerAdvancedStats`'s per-strength-state shape
  gains the six rate fields and six z-score fields shown above.

## Documentation

New file `docs/api/advanced-stats.md` (new `docs/api/` directory — no prior API
reference doc exists in this repo; specs/plans in `docs/superpowers/` describe
*how* something was built, not the resulting API contract). Contents:

- The full current response shape of `GET /api/players/<player_id>/advanced` and
  `GET /api/teams/<team_abbrev>/advanced`, both pre-existing fields and this
  phase's additions.
- Per field: name, unit, whether it's a raw count, a rate (and the rate
  denominator — 5v5 TOI), or a z-score, and one sentence on how it's computed.
- An explicit "Not available" section listing the Phase 2 stats by name with a
  one-line reason each (mirrors the Scope section's Phase 2 list), so this doc
  answers "what do I have" and "what don't I have and why" in one place.

This doc is written and committed as part of this phase's implementation, kept
next to the code it documents rather than only living in this spec.

## Testing Plan

Following the existing `test_compute_advanced_stats.py` convention (inline
event/shift fixtures via `_seed_game`/`_seed_event`/`_seed_shift` helpers, real
SQLite temp DB, no mocks):

1. **Individual shot-attempt credit** — a game with one skater taking shots of
   several types (on-goal, missed, blocked, a high-danger-zone shot, a
   `deflected`-type shot), asserting `icf`/`ihdcf`/`deflections` land only on the
   shooter, not on other on-ice teammates (distinguishing this from the existing
   on-ice `cf`/`hdcf` test cases, which should be unaffected).
2. **Rebound detection** — table-driven: two same-team shots 2 seconds apart
   (counts), exactly 3 seconds apart (counts, boundary inclusive per the `<= 3`
   spec), 4 seconds apart (does not count), two *different*-team shots 1 second
   apart (does not count), and a three-shot scramble A→B→C each 2 seconds apart
   confirming each consecutive pair credits its own originating shooter
   independently (A credited once for creating B's shot, B credited once for
   creating C's shot — two separate credits, one per shooter) rather than A
   accumulating credit for both B and C (the "last_shot_attempt pointer moves
   forward on every shot attempt, not just qualifying rebounds" rule, which
   bounds any single shot to at most one credited rebound even inside a longer
   scramble).
3. **Points vs. primary_points** — a goal with both a primary and secondary
   assist, asserting `points` credits all three players (scorer + assist1 +
   assist2) while `primary_points` continues to credit only scorer + assist1
   (regression-guards the existing column against this new sibling logic).
4. **Season aggregation** — confirms the five new columns sum correctly across
   multiple games via the existing `compute_season_aggregates()` test pattern.
5. **Z-score computation** — table-driven population (a handful of synthetic
   season rows with known mean/stddev), asserting the computed z-scores match
   hand-calculated values; a degenerate zero-stddev population asserting `0.0`
   for all players rather than a division error; a `toi_seconds = 0` player
   correctly excluded from the population.
6. **API layer** — a test asserting `_fetch_player_advanced()`'s response
   includes the six new rate/z-score fields with correct division, and that a
   zero-TOI player gets `None` rather than a crash (mirrors the existing
   `_pct()` zero-denominator test if one exists, otherwise a new one following
   its pattern).
7. **Frontend** — a `PlayerProfilePanel.test.tsx` case asserting the new "Shot
   Generation" section renders the six boxes with correct z-score-based color
   coding, following the existing percentile-box test pattern.

## Error Handling

Matches the existing loader pattern: the per-game sweep step remains inside
`run()`'s existing per-game `try/except` (a failure in the new counters would
raise from within `compute_game_advanced_stats()`, still caught and logged the
same way as any other sweep failure). The new `compute_zscores()` function runs
in the same un-gated, full-recompute-every-time style as `compute_percentiles()`
— not individually try/excepted per player, since a bug there should surface
immediately during development/testing rather than silently skip a player (this
matches `compute_percentiles()`'s existing lack of per-player exception
handling, for consistency rather than introducing a new error-handling style for
one function).
