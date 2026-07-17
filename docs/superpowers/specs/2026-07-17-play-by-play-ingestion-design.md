# Play-by-Play & Shift Ingestion Foundation — Design

## Context

The roadmap (`files/roadmap_template.md`, Phase 5) has long flagged advanced metrics
(Corsi, Fenwick, xG, predictive modeling) as future ideas, but nothing has been built
toward them. The current schema (`src/database.py`) only stores box-score-level data —
per-game/per-season/career aggregate totals (goals, assists, points, shots, TOI,
goalie SV%/GAA). There is no shot-event data, no coordinates, no on-ice/situational
data, and no strength-state tracking per event.

A companion reference document (`nhl_advanced_analytics.md`, supplied by the user)
lays out the target metric set: Corsi, Fenwick, xG, PDO, GAR/WAR, RAPM, HDSC, GSAx,
Primary Points, and microstats. These form a dependency chain, not one flat feature:

- Corsi, Fenwick, HDSC, PDO, Primary Points — computable directly from shot/goal
  event data once it exists.
- xG — needs shot event data plus a trained shot-quality model (separate future
  phase).
- RAPM / WAR — needs xG plus on-ice player context (who was on the ice for every
  event) and ridge regression across player combinations, deployment, and score
  effects (separate future phase, largest lift).
- Microstats (zone entries/exits, hand-tracked passes, NHL EDGE speed data) — not
  obtainable from the free public NHL API; out of scope for this project entirely
  unless a future phase revisits data sourcing.

This spec covers only the ingestion foundation: getting raw shot-event and shift data
into the database, for all seasons currently represented in the DB. It does not
compute any metrics. Metric computation (Corsi/Fenwick/PDO/HDSC, then xG, then
RAPM/WAR) is deliberately deferred to later specs built on top of this one.

## Scope

In scope:
1. **Historical schedule backfill** — populate the `games` table for all games (not
   just the current week) across every season currently present in the DB:
   `20202021` through `20252026`, both regular season (`gameType=2`) and playoffs
   (`gameType=3`).
2. **Play-by-play event ingestion** — a new `game_events` table capturing every event
   type from the NHL play-by-play feed (not filtered to shots), for every completed
   game in the backfilled `games` table.
3. **Shift ingestion** — a new `player_shifts` table capturing every player shift
   (start/end time per period) for every completed game, enabling on-ice
   reconstruction in a later phase.
4. Three new ETL scripts wired into `run_all_etl.py`, following the existing
   "one script per data type" / idempotent-upsert pattern already used by
   `load_boxscores.py`.

Out of scope (explicitly deferred to later specs):
- Computing any metric (Corsi, Fenwick, xG, PDO, HDSC, primary points, RAPM, WAR).
- Resolving on-ice player sets per event (joining `game_events` against
  `player_shifts` by time range) — this is metrics-phase work, not ingestion.
- Any new API endpoints or UI surfacing this data.
- Microstats / NHL EDGE tracking data — not available via the free public API.

## Data Source Notes

- Season game lists: `GET https://api.nhle.com/stats/rest/en/game?cayenneExp=season={season} and gameType={type}`
  returns every game for that season/type in a single unpaginated response (confirmed:
  1,312 games for one season/type in one call). One call per `(season, gameType)` pair
  — 6 seasons × 2 types = 12 calls total for the backfill.
  **Note:** this endpoint returns a numeric `gameStateId` rather than the string
  `gameState` (`"OFF"`, `"LIVE"`, etc.) used everywhere else in this codebase and
  relied on for ETL gating (`game_state = 'OFF' AND NOT EXISTS ...`). Confirmed
  empirically that `gameStateId: 7` corresponds to `gameState: "OFF"` (cross-checked
  game `2025020001` against its play-by-play response, which includes the string
  form). `load_historical_schedule.py` must map `gameStateId` to the same string
  vocabulary before inserting into `games`, not store the numeric ID directly — since
  this backfill only targets already-completed historical seasons, essentially every
  row should resolve to `"OFF"`, but the mapping should be verified against a larger
  sample (and any non-`7` values investigated) during implementation rather than
  assumed. For any `gameStateId` without a known mapping, `load_historical_schedule.py`
  stores the raw numeric value as a string in `game_state` (e.g. `"9"`) rather than
  crashing or dropping the game, and logs a warning naming the game_id and the
  unmapped value. The row and its data aren't lost; it simply won't match the
  `game_state = 'OFF'` gating used downstream until the mapping is extended to cover
  that value — the same practical effect as the game not existing yet.
- Play-by-play: `GET https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play`
  — `data["plays"]` is a list of events, each with `typeDescKey` (event type),
  `periodDescriptor`, `timeInPeriod`, `situationCode` (raw strength-state code),
  and a `details` object whose shape varies by event type (coordinates, shooter,
  assists, faceoff winner/loser, penalty committed-by/drawn-by, etc.).
- Shifts: `GET https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId={game_id}`
  — `data["data"]` is a list of per-player shift records (period, start/end time,
  team, duration).

## Schema

```sql
CREATE TABLE game_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id             INTEGER NOT NULL REFERENCES games(game_id),
    event_id            INTEGER NOT NULL,        -- NHL's eventId, unique within a game
    period              INTEGER NOT NULL,
    time_in_period      TEXT,                    -- "MM:SS"
    situation_code      TEXT,                    -- raw strength-state code, decoded in a later phase
    event_type          TEXT NOT NULL,            -- typeDescKey, unfiltered (all event types captured)
    zone_code           TEXT,
    x_coord             INTEGER,
    y_coord             INTEGER,
    shot_type           TEXT,
    event_owner_team_id INTEGER REFERENCES teams(team_id),
    shooting_player_id  INTEGER REFERENCES players(player_id),  -- shooter, or scorer on a goal
    blocking_player_id  INTEGER REFERENCES players(player_id),  -- blocked-shot only
    goalie_in_net_id    INTEGER REFERENCES players(player_id),
    assist1_player_id   INTEGER REFERENCES players(player_id),  -- goals only
    assist2_player_id   INTEGER REFERENCES players(player_id),
    details_json        TEXT,                    -- raw `details` object verbatim, full fidelity
                                                   -- for event-type-specific fields not promoted
                                                   -- to their own column (faceoff winner/loser,
                                                   -- penalty committed-by/drawn-by, hit players, etc.)
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE (game_id, event_id)
);

CREATE INDEX idx_game_events_team_type ON game_events(event_owner_team_id, event_type);
CREATE INDEX idx_game_events_shooter   ON game_events(shooting_player_id);

CREATE TABLE player_shifts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id    INTEGER NOT NULL REFERENCES games(game_id),
    shift_id   INTEGER NOT NULL,       -- NHL's shift 'id' field, unique within a game
    player_id  INTEGER NOT NULL REFERENCES players(player_id),
    team_id    INTEGER REFERENCES teams(team_id),
    period     INTEGER NOT NULL,
    start_time TEXT,                  -- "MM:SS" within period
    end_time   TEXT,
    duration   TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (game_id, shift_id)
);

CREATE INDEX idx_player_shifts_player_game ON player_shifts(player_id, game_id);
```

Design rationale: common, broadly-useful fields (team, period, time, coordinates,
shooter/blocker/goalie/assists) get real columns for indexed querying and to support
the near-term metrics (Corsi, Fenwick, HDSC, PDO, primary points) without needing
JSON extraction. Everything else — which varies per event type (faceoff winner/loser,
penalty committed-by/drawn-by, hit participants, giveaway/takeaway player) — is
captured losslessly in `details_json` rather than modeled as dozens of
mostly-null columns. This means later phases (WAR's penalty differential and zone
starts, for example) can be built without a schema migration or API re-fetch; they
just need new extraction logic reading from data already on disk.

## Data Flow

Four ordered steps, each idempotent (safe to re-run, skips already-loaded data):

1. **`etl/load_historical_schedule.py`** (new) — for each of the 6 seasons × 2 game
   types, call the season-game-list endpoint and upsert into `games` (same
   `insert_game`/upsert semantics as the existing `load_schedule.py`, keyed on
   `game_id`).
2. **`etl/load_boxscores.py`** (existing, unchanged) — already gates on
   `game_state = 'OFF' AND NOT EXISTS (... player_game_stats ...)`; now has a much
   larger pool of completed games to work through after step 1.
3. **`etl/load_play_by_play.py`** (new) — same gating pattern:
   `games.game_state = 'OFF' AND NOT EXISTS (... game_events ...)`. For each pending
   game, fetch play-by-play, map every play to a `game_events` row (common columns
   extracted, full `details` dict JSON-encoded into `details_json`), upsert.
4. **`etl/load_shifts.py`** (new) — same gating pattern against `player_shifts`. For
   each pending game, fetch shift chart, upsert one row per shift record.

All four are added to the `steps` list in `scripts/run_all_etl.py`, in the order
above (schedule backfill first, since boxscores/events/shifts all depend on `games`
rows existing; boxscores before events/shifts to match existing script ordering,
though events/shifts do not actually depend on boxscore data). Going forward this
keeps new games' events/shifts current automatically as part of routine syncs — after
the initial backfill (see Operability below), `NOT EXISTS` gating makes these steps
fast no-ops on days with no new completed games.

**Operability — initial backfill is a one-time manual step, not part of routine
`run_all_etl.py` runs.** The existing steps in `run_all_etl.py` (teams, standings,
rosters, schedule, boxscores) are fast, meant to be run routinely to stay in sync.
The one-time 6-season backfill is ~15,000+ API calls and will realistically take
hours. Rather than let a routine sync invocation silently balloon into an hours-long
crawl the first time it's run against a cold DB, the initial backfill is a documented
manual step: run `load_historical_schedule.py`, `load_play_by_play.py`, and
`load_shifts.py` standalone (each already supports this via the existing
`if __name__ == "__main__"` pattern) once, before folding all three into the regular
`run_all_etl.py` chain for ongoing use.

**Volume & runtime:** ~1,300 regular-season games × 6 seasons ≈ 7,800 games, plus
playoff games. Each game needs 2 new API calls (play-by-play + shifts), so roughly
15,000+ additional API calls for the full backfill. The existing `NOT EXISTS` gating
makes this naturally resumable — an interrupted run (rate-limited, crashed, manually
stopped) picks up where it left off on the next `run_all_etl.py` invocation, with no
additional checkpointing logic needed.

## Error Handling

Matches the existing `load_boxscores.py` pattern exactly: each game is fetched and
processed inside a per-game `try/except`; a failure logs a warning
(`Warning: could not fetch play-by-play for game {game_id}: {e}`) and continues to
the next game rather than aborting the run. Rate-limit backoff (429 handling with
exponential wait) is already centralized in `src/api_client._get` and applies
automatically to the new endpoint calls.

**Proactive pacing:** unlike the existing loaders, which make at most a few dozen
calls per run, `load_play_by_play.py` and `load_shifts.py` each make one call per
pending game across a ~7,800+ game backfill. Rather than relying solely on reactive
429 backoff, both loaders add a small fixed delay (e.g. `time.sleep(0.2)`) after each
request in their pending-games loop, to keep steady-state load low and avoid tripping
rate limits in the first place. This only applies to these two bulk loaders, not the
existing lightweight steps.

## Testing Plan

Following existing conventions (`tests/test_database.py`, `tests/test_enrich_players.py`):

1. Unit tests for the JSON→row extraction functions (one per new ETL module) — as
   inline Python dict/list literals in the test file (trimmed excerpts of real API
   response shapes), matching the existing convention in `tests/test_enrich_players.py`
   and `tests/test_database.py` (no live API calls, no separate fixture files).
   Assert the extracted row dict(s) match expected values, including edge cases: an
   event type with a sparse `details` object, a shot with null coordinates, a shift
   with no `endTime` (ongoing at period end).
2. DB upsert regression tests for `game_events` and `player_shifts`, following the
   `test_upsert_player_enrichment_*` pattern in `tests/test_database.py` — confirm
   re-running ingestion for an already-loaded game does not duplicate rows (the
   `UNIQUE(game_id, event_id)` / `UNIQUE(game_id, shift_id)` constraints are what
   enforce this).
3. A unit test for the season-game-list extraction in `load_historical_schedule.py`,
   confirming games from a fixture response upsert into `games` with the same shape
   `load_schedule.py` already produces (no divergence between the "current week" and
   "historical backfill" code paths in how a `Game` row is built).
4. Manual verification: run the standalone loaders (`load_historical_schedule.py`,
   `load_play_by_play.py`, `load_shifts.py`) against a single season first — not the
   full 6-season backfill — and spot-check `game_events` row counts against a known
   game's actual shot totals (e.g. compare `SELECT COUNT(*) FROM game_events WHERE
   game_id = X AND event_type IN ('shot-on-goal','missed-shot','blocked-shot')`
   against that game's boxscore SOG totals) before running the standalone loaders
   across the remaining 5 seasons.
