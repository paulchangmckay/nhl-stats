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

## Scope

In scope:
1. Player-level, full strength-state breakdown (5v5, 5v4, 4v5, 4v4, 3v3, other) for
   Corsi, Fenwick, HDSC.
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
CREATE TABLE player_game_advanced_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(game_id),
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    team_id         INTEGER REFERENCES teams(team_id),
    strength_state  TEXT NOT NULL,   -- '5v5','5v4','4v5','4v4','3v3','other'
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
-- as player_game_advanced_stats (minus game_id, plus season_id or nothing for
-- career), aggregated via GROUP BY, mirroring the existing
-- player_season_stats/player_career_stats pattern exactly.

-- team_season_advanced_stats: same relationship to team_game_advanced_stats.

CREATE TABLE player_advanced_percentiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id       TEXT NOT NULL REFERENCES seasons(season_id),
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    strength_state  TEXT NOT NULL,
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

A `situation_code` decoding table (implemented as a Python constant/lookup, not a
DB table — it's static domain knowledge, not data) maps the NHL API's raw 4-digit
`situationCode` strings to `strength_state`, resolved per-team (the same raw code
implies a different state depending on whether you're computing for the team on
the power play vs. the team shorthanded).

## Computation Algorithm

New ETL module `etl/compute_advanced_stats.py`, following the existing `run(conn)`
/ idempotent-upsert convention used by every other loader, gated the same way as
`load_play_by_play.py`: `games.game_state = 'OFF' AND NOT EXISTS (... 
player_game_advanced_stats ...)`.

Per pending game:

1. **Parse shifts** — convert `player_shifts.start_time`/`end_time` ("MM:SS" clock
   strings) to elapsed game-seconds, using `period` to offset (period 1:
   0-1200s, period 2: 1200-2400s, ... OT periods continue the offset). A shift
   with a null `end_time` closes at that period's boundary.
2. **Parse events** — same elapsed-seconds conversion for `game_events.time_in_period`,
   plus decode `situation_code` into `strength_state` per team via the lookup
   table. Any `situation_code` that doesn't match a known pattern maps to
   `strength_state = 'other'` and is logged (never dropped, never raises) —
   matching the existing unmapped-`gameStateId` handling precedent in
   `load_historical_schedule.py`.
3. **Sweep** — merge shift-start, shift-end, and event timestamps into one
   chronologically sorted sequence for the game; walk it once, maintaining a
   `{team_id: set(player_id)}` on-ice roster, updating on each shift
   start/end. On a shot-attempt event (`shot-on-goal`, `missed-shot`,
   `blocked-shot`, `goal`):
   - Credit `cf`/`hdcf` (if in the high-danger zone, by `x_coord`/`y_coord` against
     a fixed slot-area definition) to every on-ice skater of the shooting team, at
     that moment's `strength_state`; credit `ca`/`hdca` to the opposing on-ice
     skaters.
   - `blocked-shot` events count toward Corsi but not Fenwick.
   - `goal` events additionally increment `gf`/`ga` for the on-ice teams (PDO
     input) and update the corresponding `team_game_advanced_stats` row's
     shots-for/against.
   - `toi_seconds` accumulates per player per strength-state as the sweep passes
     through each interval.
4. **Primary Points** — computed directly via `GROUP BY` over `game_events` on
   `shooting_player_id` (goals) and `assist1_player_id` (primary assists); no
   sweep/on-ice data needed.
5. Upsert one row per `(game_id, player_id, strength_state)` into
   `player_game_advanced_stats`, and per `(game_id, team_id, strength_state)` into
   `team_game_advanced_stats`.

Season/career aggregation and percentile computation run as later steps in the
same module, after per-game rows exist for the relevant seasons. Percentiles rank
players within position group (`players.position_code` mapped to F/D), excluding
anyone below a minimum TOI/GP floor for that season/strength-state (exact
threshold TBD during implementation — the plan should pick a defensible value,
e.g. modeled on the ~40-game floor commonly used by public sites).

## Operability

Following the same precedent as the play-by-play ingestion spec: the one-time
historical computation across all 6 backfilled seasons is a **documented manual
step** (`python -m etl.compute_advanced_stats`, standalone entrypoint), not
something a routine `sync.py` run triggers automatically against a cold set of
new tables. Once that initial backfill completes, the module folds into
`scripts/sync.py`'s ordered step list, so newly-completed games get advanced
stats computed automatically going forward; `NOT EXISTS` gating keeps this a fast
no-op on days with no new completed games.

This computation reads only already-ingested local data (`game_events` /
`player_shifts` are fully backfilled) — no NHL API calls, so no rate-limiting
concern, unlike the original ingestion backfill. If the full 8,058-game backfill
proves too slow single-threaded in practice, the fallback is batching by season
with progress logging — not multiprocessing, which is more complexity than
justified unless the numbers demand it.

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
  of color-coded percentile boxes (one per metric: CF%, FF%, HDCF%, PDO, Primary
  Points), and a season-over-season line chart per metric — using this phase's
  metrics in place of the reference's WAR/percentile-of-forwards fields.
- A strength-state selector within the panel (default `5v5`) switches which cut
  of the boxes/charts is shown, rather than displaying all six strength states
  simultaneously.
- `PlayerTable` gets exactly one new column (e.g. `CF% (5v5)`) added to its
  existing `COLUMNS` array, serving as both a sortable headline stat and the
  entry point into the panel — the full breakdown lives in the panel, not as
  additional table columns.

## Testing Plan

Following this project's existing conventions (inline dict/list fixtures trimmed
from real API response shapes, no separate fixture files, no live API calls):

1. **Sweep-line algorithm unit tests** — synthetic shift/event lists (a handful
   of players/shifts/events), asserting on-ice credit counts against hand-computed
   expected values. Cases: a shift with no `end_time` (period-end), overlapping
   shifts, a shot event exactly at a shift boundary, an unmapped `situation_code`.
2. **`situation_code` decoding unit tests** — table-driven, covering known codes
   (5v5, 5v4, 4v5, 4v4, 3v3, goalie-pulled variants) plus one unmapped code,
   asserting it lands in `strength_state = 'other'` rather than raising.
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
