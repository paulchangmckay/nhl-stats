# Advanced Analytics (Tier 1) — Design

## Context

The 2026-07-17 play-by-play & shift ingestion design deliberately scoped itself to
raw data ingestion only, deferring all metric computation to later specs. That
backfill completed 2026-07-20: 8,058 games, 2,494,684 `game_events` rows, and
5,658,387 `player_shifts` rows are on disk, all games covered.

A companion reference document (`nhl_advanced_analytics.md`, supplied by the user)
laid out the full target metric set as a dependency chain:

- Corsi, Fenwick, HDSC, PDO, Primary Points — computable directly from existing
  event/shift data.
- xG — needs a trained shot-quality model (separate future phase).
- RAPM / WAR — needs xG plus on-ice player context and ridge regression across
  player combinations (separate future phase, largest lift).

This spec covers only the first tier: Corsi, Fenwick, HDSC, PDO, and Primary
Points. No model training, no on-ice regression. It deliberately builds the on-ice
reconstruction (shift × event join) that a future RAPM/WAR phase will also need,
but does not persist the raw on-ice sets — only final aggregate tallies — since
persisting them now would be scope creep against a phase that isn't happening yet.

**Prerequisite gap found during grilling:** correct HDSC computation requires
knowing which physical end of the rink each team is defending each period (the
raw `x_coord`/`y_coord` values are meaningless as a "high danger" zone without
this), and the NHL API's `homeTeamDefendingSide` field (confirmed present on
every play event via a live fetch against `2025020001`) was never captured
during the original ingestion backfill — it's a top-level play field, not part
of the `details` object that got JSON-dumped into `details_json`. This spec
therefore includes a small prerequisite: a `game_events` migration plus a
one-time gap-fill re-fetch of play-by-play for all 8,058 already-ingested games,
solely to backfill this one field (see Computation Algorithm and Operability).

## Scope

In scope:
1. Player-level, full strength-state breakdown for Corsi, Fenwick, HDSC, where
   `strength_state` is derived generically from the decoded skater counts (e.g.
   `5v5`, `5v4`, `4v5`, `4v4`, `3v3`, `5v3`, `3v5`, `6v5`, `5v6`, etc. — see Data
   Model) rather than a fixed short list, so uncommon-but-meaningful states like
   a 5-on-3 aren't silently discarded.
2. Team-level PDO (5v5 shooting% + save%) per strength state.
3. Player-level Primary Points (goals + primary assists), all strength states.
4. Percentile ranking per metric, within position group (forwards vs. defensemen),
   per season, among players clearing a minimum TOI/GP floor.
5. Computation for all 6 already-backfilled seasons (2020-21 through 2025-26), plus
   ongoing incremental computation for newly-completed games via `scripts/sync.py`.
6. New API endpoints exposing per-player and per-team advanced stats.
7. A new player detail panel (modal/overlay, not a routed page) surfacing these
   metrics, styled after a JFresh-Hockey-style player card (percentile boxes +
   season trend charts), populated with this phase's metrics rather than WAR.
8. One new teaser column (e.g. `CF% (5v5)`) added to the existing flat
   `PlayerTable`, linking into the new panel.
9. A `game_events` schema migration (`home_team_defending_side` column) and a
   one-time gap-fill re-fetch backfill for that field across all 8,058 already-
   ingested games (see the prerequisite note in Context).

Explicit exclusions within the sweep (found during grilling, not in the original
draft):
- **Shootout events** (`periodDescriptor.periodType == 'SO'`, confirmed via live
  fetch on game `2020020007`) are skipped entirely — no meaningful on-ice/
  strength-state concept applies to a 1-on-1 shootout attempt, and its
  `situationCode` values (e.g. `"1010"`) aren't real strength encodings.
- **Goalies** (`players.position_code == 'G'`) are excluded from the on-ice
  skater roster used to credit `cf`/`ca`/`ff`/`fa`/`hdcf`/`hdca`/`gf`/`ga`/
  `toi_seconds` — confirmed goalies do have `player_shifts` rows (8 in one
  sample game), so this must be an explicit filter, not an assumption. Goalie
  performance is already tracked via existing box-score fields elsewhere in
  this schema.

Out of scope (explicitly deferred to later specs):
- xG (shot-quality model) and RAPM/WAR (on-ice regression).
- Persisting the raw on-ice reconstruction (event × on-ice-player junction data) —
  only final aggregate counts are stored. A future RAPM/WAR spec can extend this
  phase's per-game module to also emit that data at that time.
- Any team-level detail view/page (team PDO is computed and exposed via API, but
  no new team UI surface beyond what already exists).
- Microstats (zone entries/exits, NHL EDGE data) — not available via the free
  public API, as already noted in the ingestion spec.

## Data Model

New tables, following the existing `player_game_stats` → `player_season_stats` →
`player_career_stats` aggregation pattern already used in `src/database.py`:

```sql
-- Migration to the existing game_events table (grilling finding — see Context):
ALTER TABLE game_events ADD COLUMN home_team_defending_side TEXT;
-- 'left' or 'right', as returned verbatim by the NHL API's homeTeamDefendingSide
-- field on every play event. Backfilled via a one-time gap-fill re-fetch for
-- already-ingested games (see Operability); captured directly going forward.

CREATE TABLE player_game_advanced_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(game_id),
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    team_id         INTEGER REFERENCES teams(team_id),
    strength_state  TEXT NOT NULL,   -- generic '{shooting}v{opposing}', e.g.
                                      -- '5v5','5v4','4v5','5v3','6v5', etc.;
                                      -- 'other' reserved only for unparseable
                                      -- situation_code values (see below)
    cf              INTEGER DEFAULT 0,  -- Corsi For (all shot attempts, on-ice)
    ca              INTEGER DEFAULT 0,  -- Corsi Against
    ff              INTEGER DEFAULT 0,  -- Fenwick For (unblocked attempts)
    fa              INTEGER DEFAULT 0,  -- Fenwick Against
    hdcf            INTEGER DEFAULT 0,  -- High-Danger Corsi For
    hdca            INTEGER DEFAULT 0,  -- High-Danger Corsi Against
    gf              INTEGER DEFAULT 0,  -- Goals For, on-ice (PDO input)
    ga              INTEGER DEFAULT 0,  -- Goals Against, on-ice (PDO input)
    primary_points  INTEGER DEFAULT 0,  -- goals + primary assists (no on-ice needed)
    toi_seconds     INTEGER DEFAULT 0,  -- on-ice time in this strength state
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (game_id, player_id, strength_state)
);
CREATE INDEX idx_player_game_adv_player ON player_game_advanced_stats(player_id);

CREATE TABLE team_game_advanced_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(game_id),
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    strength_state  TEXT NOT NULL,
    cf              INTEGER DEFAULT 0,
    ca              INTEGER DEFAULT 0,
    ff              INTEGER DEFAULT 0,
    fa              INTEGER DEFAULT 0,
    gf              INTEGER DEFAULT 0,
    ga              INTEGER DEFAULT 0,
    shots_for       INTEGER DEFAULT 0,  -- shots on goal, for shooting%/save% (PDO)
    shots_against   INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (game_id, team_id, strength_state)
);

-- player_season_advanced_stats / player_career_advanced_stats: same column shape
-- as player_game_advanced_stats (minus game_id, plus season_id + game_type for
-- the season table), aggregated via GROUP BY, mirroring the existing
-- player_season_stats/player_career_stats pattern exactly — including a
-- team_abbrevs column (grilling finding: confirmed player_season_stats already
-- combines a traded player's stats across all their teams into one row per
-- (player_id, season_id, game_type), rather than splitting per team; the new
-- table follows the same convention rather than inventing a different one).

-- team_season_advanced_stats: same relationship to team_game_advanced_stats,
-- also split by game_type to match the existing convention.

CREATE TABLE player_advanced_percentiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id       TEXT NOT NULL REFERENCES seasons(season_id),
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    strength_state  TEXT NOT NULL,   -- one of '5v5','5v4','4v5' only — see below
    position_group  TEXT NOT NULL,   -- 'F' or 'D'
    cf_pct_pctile   REAL,
    ff_pct_pctile   REAL,
    hdcf_pct_pctile REAL,
    primary_points_pctile REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (season_id, player_id, strength_state)
);
```

PDO is computed from `team_season_advanced_stats` (5v5 shooting% + save% = PDO,
conventionally ×1000) at query time in the API layer — no separate PDO table,
since it's a simple derived ratio of already-aggregated columns, not something
that needs its own storage.

`situation_code` decoding is a pure function, not a lookup table — confirmed via
live samples (games `2020020003`, `2020020007`) that the raw 4-digit code is
positionally structured as `[awayGoalieInNet][awaySkaters][homeSkaters][homeGoalieInNet]`
(e.g. `"1551"` = both goalies in, 5 skaters each = 5v5; `"1351"` = away down to 3
skaters vs. home's 5 = a 5-on-3; `"0440"` = both goalies pulled, 4-on-4). Given a
game's `home_team_id` and an event's `event_owner_team_id`, the decoder reads the
two skater-count digits, orients them as `"{shooting_team_skaters}v{opposing_team_skaters}"`,
and returns that string directly — no fixed enum, no per-code branching table.
`strength_state = 'other'` is reserved only for a `situationCode` that fails to
parse as 4 digits at all (malformed data), never for a legitimate-but-uncommon
skater combination.

## Computation Algorithm

New ETL module `etl/compute_advanced_stats.py`, following the existing `run(conn)`
/ idempotent-upsert convention used by every other loader, gated the same way as
`load_play_by_play.py`: `games.game_state = 'OFF' AND NOT EXISTS (... 
player_game_advanced_stats ...)`.

**Step 0 (one-time prerequisite): `home_team_defending_side` gap-fill.** Before
the main compute module can run correctly, a standalone script re-fetches
play-by-play for every already-ingested completed game solely to populate the
new `home_team_defending_side` column (see Data Model) — the field was never
captured during the original ingestion backfill. Same idempotent/gated shape as
the other loaders (`NOT EXISTS`-style check on the new column being non-null),
same per-game `try/except` + warn-and-continue error handling, same proactive
pacing (`time.sleep`) as the original bulk loaders, since this is ~8,058 fresh
API calls. `load_play_by_play.py` is also patched to capture this field for any
future game ingestion, so this gap-fill never needs to run again after this
one time.

Per pending game, in the main `etl/compute_advanced_stats.py` module:

1. **Filter out shootouts** — any event or shift with `periodDescriptor.periodType
   == 'SO'` (or the equivalent stored period-type marker) is excluded before any
   other processing; shootouts have no meaningful on-ice/strength-state concept
   (confirmed via live fetch: `situationCode` values there, e.g. `"1010"`, aren't
   real strength encodings).
2. **Parse shifts** — convert `player_shifts.start_time`/`end_time` ("MM:SS" clock
   strings) to elapsed game-seconds. The offset per period is looked up from
   `(game_type, period_type)`, not a flat constant: regulation periods (1-3) are
   always 1200s regardless of `game_type`; OT is 300s for regular-season games
   (`game_type=2`, single 3-on-3 period) but 1200s per OT period for playoffs
   (`game_type=3`, potentially multiple full sudden-death periods) — confirmed
   via live fetch that a regular-season OT period actually ends by ~300s
   (game `2020020003`). A shift with a null `end_time` closes at that period's
   correct boundary length, not an assumed 1200s.
3. **Parse events** — same elapsed-seconds conversion for `game_events.time_in_period`,
   plus decode `situation_code` into a generic `strength_state` string per the
   Data Model section (not a fixed lookup table). Skater-set on-ice roster
   membership is restricted to `position_code IN ('C','L','R','D')` — goalies are
   excluded from `cf`/`ca`/`ff`/`fa`/`hdcf`/`hdca`/`gf`/`ga`/`toi_seconds` credit
   even though they have their own `player_shifts` rows (confirmed: 8 goalie
   shift rows in one sample game).
4. **Sweep** — merge shift-start, shift-end, and event timestamps into one
   chronologically sorted sequence for the game; walk it once, maintaining a
   `{team_id: set(skater_player_id)}` on-ice roster, updating on each shift
   start/end. On a shot-attempt event (`shot-on-goal`, `missed-shot`,
   `blocked-shot`, `goal`):
   - Credit `cf`/`hdcf` (if in the high-danger zone, by `x_coord`/`y_coord`
     normalized for rink side via `home_team_defending_side` and the shooting
     team's home/away status, against a fixed slot-area definition pinned during
     implementation) to every on-ice skater of the shooting team, at that
     moment's `strength_state`; credit `ca`/`hdca` to the opposing on-ice
     skaters.
   - `blocked-shot` events count toward Corsi but not Fenwick.
   - `goal` events additionally increment `gf`/`ga` for the on-ice teams (PDO
     input) and update the corresponding `team_game_advanced_stats` row's
     shots-for/against.
   - `toi_seconds` accumulates per player per strength-state as the sweep passes
     through each interval.
5. **Primary Points** — computed directly via `GROUP BY` over `game_events` on
   `shooting_player_id` (goals) and `assist1_player_id` (primary assists); no
   sweep/on-ice data needed. Not affected by the shootout filter's other rules
   since shootout goals are already excluded upstream in step 1.
6. Upsert one row per `(game_id, player_id, strength_state)` into
   `player_game_advanced_stats`, and per `(game_id, team_id, strength_state)` into
   `team_game_advanced_stats`.

Season/career aggregation and percentile computation run as later steps in the
same module, after per-game rows exist for the relevant seasons. Percentiles rank
players within position group (`players.position_code` mapped to F/D), computed
**only for `5v5`, `5v4`, and `4v5`** — the three states with enough league-wide
sample size for a percentile to mean anything (grilling finding: with
`strength_state` now generic rather than a fixed 5-bucket list, rarer states like
`3v3` OT or a `5v3` power play don't have enough total ice time across the
league for a meaningful rank; their raw aggregate counts are still stored in
`player_season_advanced_stats`, just never percentiled). Players below a
**10-games-played floor** for that season are excluded (a deliberately low bar:
excludes single-game call-ups without excluding legitimate depth players; not a
literature-derived constant, just a defensible starting default that can be
tuned later without a schema change since it's a query-time filter, not a stored
value). PDO is never percentiled — see Frontend section.

## Operability

Two manual one-time steps, run in order, following the same precedent as the
play-by-play ingestion spec:

1. **`home_team_defending_side` gap-fill** (`python -m etl.backfill_defending_side`
   or similar standalone entrypoint) — the ~8,058 API calls described in the
   Computation Algorithm's Step 0. This is the one part of this spec that does
   hit the NHL API and needs the same rate-limit pacing as the original
   ingestion backfill.
2. **`python -m etl.compute_advanced_stats`** — the main historical computation
   across all 6 backfilled seasons. Pure local computation (`game_events` /
   `player_shifts` already fully backfilled, and step 1 has just added the one
   missing field) — no NHL API calls, no rate-limiting concern here. If the full
   8,058-game backfill proves too slow single-threaded in practice, the fallback
   is batching by season with progress logging — not multiprocessing, which is
   more complexity than justified unless the numbers demand it.

Once both complete, `etl/compute_advanced_stats.py` folds into `scripts/sync.py`'s
ordered step list so newly-completed games get advanced stats computed
automatically going forward; `NOT EXISTS` gating keeps this a fast no-op on days
with no new completed games. `load_play_by_play.py`'s patch to capture
`home_team_defending_side` going forward means step 1 never needs to run again.

## API Layer

Two new endpoints in `app.py`, following existing route/response conventions:

- **`GET /api/players/<player_id>/advanced?season=...`** (default: most recent
  season) — full breakdown for one player: per-strength-state CF/CA/CF%,
  FF/FA/FF%, HDCF/HDCA/HDCF%, PDO (via team context), Primary Points, each
  metric's percentile rank within position group, and a 6-season trend series
  for the panel's charts.
- **`GET /api/teams/<team_abbrev>/advanced?season=...`** — team-level PDO and
  shot-attempt differentials.

The existing `/api/players/stats` endpoint is unchanged — advanced metrics are a
separate concern, not folded into the box-score-stats query shape.

## Frontend

- New component `PlayerAdvancedPanel.tsx` — a modal/overlay (not a routed page),
  opened from a new per-row action on `PlayerTable` (repurposing today's
  scroll-highlight-only row click).
- Adds **Recharts** as a new frontend dependency (nothing is currently installed)
  for the trend-line charts, consistent with this environment's `dataviz` skill
  convention.
- Layout adapted from the JFresh-Hockey-style reference card supplied by the
  user (`~/Desktop/head-shot-example/`): player name/headshot/team header, a row
  of color-coded percentile boxes (CF%, FF%, HDCF%, Primary Points — each ranked
  within position group per the Computation Algorithm section), and a
  season-over-season line chart per metric — using this phase's metrics in place
  of the reference's WAR/percentile-of-forwards fields. **PDO is shown as a
  separate plain value box (the player's team's PDO for the selected
  season/strength-state), not color-coded by percentile** — since PDO is
  team-level by design (Data Model section) and ranking a player by their team's
  luck-driven shooting%+save% isn't a meaningful individual skill signal, unlike
  the other four boxes.
- A strength-state selector within the panel (default `5v5`) switches which cut
  of the boxes/charts is shown, rather than displaying every possible strength
  state simultaneously. The percentile boxes only ever offer the three
  percentile-eligible states (`5v5`, `5v4`, `4v5`); raw (non-percentiled) counts
  for other states are not exposed in this phase's UI, matching the "backend
  computes and stores everything, UI surfaces the headline cuts" split already
  established for percentiles.
- `PlayerTable` gets exactly one new column (e.g. `CF% (5v5)`) added to its
  existing `COLUMNS` array, serving as both a sortable headline stat and the
  entry point into the panel — the full breakdown lives in the panel, not as
  additional table columns.

## Testing Plan

Following this project's existing conventions (inline dict/list fixtures trimmed
from real API response shapes, no separate fixture files, no live API calls):

1. **Sweep-line algorithm unit tests** — synthetic shift/event lists (a handful
   of players/shifts/events), asserting on-ice credit counts against hand-computed
   expected values. Cases: a shift with no `end_time` (period-end, both a
   regulation and a regular-season-OT period length), overlapping shifts, a shot
   event exactly at a shift boundary, a goalie present in shifts but correctly
   excluded from skater credit, and a shootout-period event correctly excluded
   from processing entirely.
2. **`situation_code` decoding unit tests** — table-driven, covering the codes
   confirmed via live fetch (`1551`→5v5, `1451`/`1541`→4v5/5v4, `1331`→3v3,
   `1441`→4v4, `1351`→5v3, `0440`→4v4-both-pulled) plus one malformed code,
   asserting the malformed case lands in `strength_state = 'other'` while every
   legitimate skater combination gets its own generic `AvB` string rather than
   being coerced into `other`.
3. **DB upsert regression tests** for `player_game_advanced_stats` and
   `team_game_advanced_stats`, following the existing
   `test_upsert_player_enrichment_*` pattern — confirm re-running for an
   already-processed game does not duplicate or double-count rows.
4. **Manual spot-check** — before trusting the full 6-season backfill, manually
   verify computed CF/CA for at least one known game against a public reference
   (e.g. Natural Stat Trick's published per-game numbers).

## Error Handling

Matches the existing loader pattern exactly: each game is processed inside a
per-game `try/except`; a failure logs a warning
(`Warning: could not compute advanced stats for game {game_id}: {e}`) and
continues to the next game rather than aborting the run.
