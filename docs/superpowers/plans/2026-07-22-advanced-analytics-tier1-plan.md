# Advanced Analytics (Tier 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute Corsi, Fenwick, HDSC, PDO, and Primary Points for all 6 already-ingested seasons, with a full strength-state breakdown and player-level on-ice reconstruction, then surface them via new API endpoints and a new player detail panel — per `docs/superpowers/specs/2026-07-22-advanced-analytics-design.md`.

**Architecture:** A prerequisite gap-fill backfills a missing `home_team_defending_side` field, then a new ETL module (`etl/compute_advanced_stats.py`) runs a sweep-line algorithm per game to reconstruct on-ice rosters and credit shot-attempt metrics, storing only final aggregate tallies (never the raw on-ice sets). New tables mirror the existing `player_game_stats` → `player_season_stats` → `player_career_stats` aggregation pattern. Two new Flask endpoints expose the data; a new React modal panel (Recharts + JFresh-card-style layout) surfaces it, entered via one new `PlayerTable` column.

**Tech Stack:** Python, SQLite (`sqlite3` stdlib), Flask, `requests`, pytest, React, TypeScript, Vitest, Recharts (new dependency).

## Global Constraints

- Every new ETL module follows the existing shape exactly: pure extraction/computation functions (unit-testable, no network calls), a `run(conn)` entry point, an `if __name__ == "__main__":` block. See `etl/load_play_by_play.py` as reference.
- Every new DB write uses `INSERT OR IGNORE` / `ON CONFLICT DO UPDATE` keyed on each table's `UNIQUE` constraint — re-running any step against already-processed data must be a no-op, never a duplicate or an error.
- Per-item error handling matches existing loaders: wrap each unit of work (one game) in `try/except Exception`, print a warning, continue — never abort the whole run over one bad game.
- No live network calls in tests. Fixtures are inline Python dict/list literals in the test file — no separate fixture files, matching `tests/test_load_play_by_play.py`.
- Frontend: `npm run build` (`tsc -b && vite build`) must pass, not just `npm test` (`vitest run`) — this codebase has twice shipped a build-breaking change that was 100% green on tests alone (bug-011, bug-014 in `.wolf/buglog.json`); both are mandatory verification steps for any frontend task in this plan.
- Foreign keys are enforced (`PRAGMA foreign_keys = ON`). Any `player_id`/`team_id`/`game_id` referenced by a new row must already exist.

---

### Task 1: `home_team_defending_side` schema migration + capture going forward

**Files:**
- Modify: `src/database.py` (add `ALTER TABLE game_events ADD COLUMN home_team_defending_side TEXT` to the existing migration-runner block, alongside the existing `players` migrations)
- Modify: `etl/load_play_by_play.py` (`_extract_event` — capture the new field)
- Modify: `tests/test_load_play_by_play.py`

**Interfaces:**
- Produces: `game_events.home_team_defending_side` column (`'left'` / `'right'` / `NULL` for not-yet-backfilled rows).
- Modifies: `load_play_by_play._extract_event(game_id, play) -> dict` — adds `"home_team_defending_side": play.get("homeTeamDefendingSide")` to the returned dict.

- [ ] **Step 1: Write a failing test for the new field on `_extract_event`**

Add to `tests/test_load_play_by_play.py`:

```python
def test_extract_event_captures_home_team_defending_side():
    play = {
        "eventId": 103,
        "periodDescriptor": {"number": 1},
        "timeInPeriod": "00:08",
        "situationCode": "1551",
        "typeDescKey": "shot-on-goal",
        "homeTeamDefendingSide": "right",
        "details": {"xCoord": 56, "yCoord": -39, "eventOwnerTeamId": 1},
    }
    row = _extract_event(game_id=2024020001, play=play)
    assert row["home_team_defending_side"] == "right"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_load_play_by_play.py -v -k defending_side`
Expected: FAIL — `KeyError: 'home_team_defending_side'`

- [ ] **Step 3: Add the migration and update extraction**

In `src/database.py`, find the existing `players` table migration block (the `ALTER TABLE players ADD COLUMN ...` sequence wrapped in `try/except` for "duplicate column" idempotency) and add, in the same style:

```python
_run_migration(conn, "ALTER TABLE game_events ADD COLUMN home_team_defending_side TEXT")
```

(Match whatever helper/pattern the existing `players` migrations use for "column already exists" idempotency — read that block first rather than assuming a specific helper name.)

In `etl/load_play_by_play.py`, in `_extract_event`, add to the returned dict:

```python
"home_team_defending_side": play.get("homeTeamDefendingSide"),
```

And update `database.insert_game_event` (and its `INSERT OR IGNORE` column list) to include the new column — check whether `insert_game_event` needs to become an upsert (`ON CONFLICT DO UPDATE SET home_team_defending_side = excluded.home_team_defending_side`) so Task 2's gap-fill can update already-inserted rows rather than being blocked by `INSERT OR IGNORE`'s no-op-on-conflict behavior. This is the one place in this plan where `INSERT OR IGNORE` alone is insufficient — Task 2 depends on `insert_game_event` actually updating the new column on a second call for the same `(game_id, event_id)`.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_load_play_by_play.py -v`
Expected: PASS (all tests, including the new one)

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/database.py etl/load_play_by_play.py tests/test_load_play_by_play.py
git commit -m "feat: capture home_team_defending_side for future play-by-play ingestion"
```

---

### Task 2: One-time gap-fill backfill for existing games

**Files:**
- Create: `etl/backfill_defending_side.py`
- Test: `tests/test_backfill_defending_side.py`

**Interfaces:**
- Consumes: `api_client.get_play_by_play(game_id)` (existing), `database.insert_game_event` (Task 1's upsert version).
- Produces: `backfill_defending_side.run(conn) -> None`.

- [ ] **Step 1: Write a failing test for the gating query**

Create `tests/test_backfill_defending_side.py`:

```python
from src import database
import etl.backfill_defending_side as module


def test_run_updates_existing_events_with_defending_side(conn, monkeypatch):
    # Seed a game and an event with home_team_defending_side still NULL
    database.insert_game(conn, {
        "game_id": 2024020001, "season_id": None, "game_type": 2,
        "game_date": "2024-10-04", "venue": None, "home_team_id": None,
        "away_team_id": None, "home_score": 1, "away_score": 4,
        "last_period_type": "REG", "game_state": "OFF",
    })
    database.insert_game_event(conn, {
        "game_id": 2024020001, "event_id": 103, "period": 1,
        "time_in_period": "00:08", "situation_code": "1551",
        "event_type": "shot-on-goal", "zone_code": "O", "x_coord": 56,
        "y_coord": -39, "shot_type": "wrist", "event_owner_team_id": None,
        "shooting_player_id": None, "blocking_player_id": None,
        "goalie_in_net_id": None, "assist1_player_id": None,
        "assist2_player_id": None, "details_json": "{}",
        "home_team_defending_side": None,
    })
    conn.commit()

    fake_plays = {"plays": [{
        "eventId": 103, "periodDescriptor": {"number": 1}, "timeInPeriod": "00:08",
        "situationCode": "1551", "typeDescKey": "shot-on-goal",
        "homeTeamDefendingSide": "right",
        "details": {"xCoord": 56, "yCoord": -39},
    }]}
    monkeypatch.setattr(module.api_client, "get_play_by_play", lambda gid: fake_plays)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    module.run(conn)

    row = conn.execute(
        "SELECT home_team_defending_side FROM game_events WHERE game_id = ? AND event_id = ?",
        (2024020001, 103),
    ).fetchone()
    assert row["home_team_defending_side"] == "right"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_backfill_defending_side.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'etl.backfill_defending_side'`

- [ ] **Step 3: Write the module**

Create `etl/backfill_defending_side.py`, following `load_play_by_play.py`'s exact shape but gated on the new column being null rather than the row not existing:

```python
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from etl.load_play_by_play import _extract_event

REQUEST_DELAY_SECONDS = 0.2


def run(conn):
    print("Backfilling home_team_defending_side for existing games...")

    pending = conn.execute("""
        SELECT DISTINCT g.game_id FROM games g
        JOIN game_events ge ON ge.game_id = g.game_id
        WHERE g.game_state = 'OFF' AND ge.home_team_defending_side IS NULL
    """).fetchall()

    print(f"  {len(pending)} games need defending-side backfill.")
    total_updated = 0

    for row in pending:
        game_id = row["game_id"]
        try:
            data = api_client.get_play_by_play(game_id)
        except Exception as e:
            print(f"  Warning: could not fetch play-by-play for game {game_id}: {e}")
            continue

        for play in data.get("plays", []):
            event = _extract_event(game_id, play)
            database.insert_game_event(conn, event)  # upsert overwrites the NULL
            total_updated += 1

        conn.commit()
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"  {total_updated} game_event rows updated.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_backfill_defending_side.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add etl/backfill_defending_side.py tests/test_backfill_defending_side.py
git commit -m "feat: add one-time gap-fill backfill for home_team_defending_side"
```

---

### Task 3: Pure decoding helpers — `situation_code` and elapsed-time conversion

**Files:**
- Create: `etl/advanced_stats/decoding.py`
- Test: `tests/test_decoding.py`

**Interfaces:**
- Produces: `decoding.decode_strength_state(situation_code: str, event_owner_team_id: int, home_team_id: int) -> str` — returns a generic `"{shooting}v{opposing}"` string, or `"other"` for unparseable input.
- Produces: `decoding.period_offset_seconds(period: int, period_type: str, game_type: int) -> int` — cumulative elapsed-seconds offset at the start of the given period.
- Produces: `decoding.elapsed_seconds(clock: str, period: int, period_type: str, game_type: int) -> int` — full conversion of an `"MM:SS"` clock string to game-elapsed seconds.

- [ ] **Step 1: Write failing tests, covering every code confirmed via live fetch during grilling**

Create `tests/test_decoding.py`:

```python
import pytest
from etl.advanced_stats.decoding import decode_strength_state, period_offset_seconds, elapsed_seconds

HOME = 1
AWAY = 2


def test_decode_5v5_both_goalies_in():
    assert decode_strength_state("1551", event_owner_team_id=HOME, home_team_id=HOME) == "5v5"


def test_decode_home_power_play():
    # away down to 4, home has 5 -> from home's (shooting) perspective, 5v4
    assert decode_strength_state("1451", event_owner_team_id=HOME, home_team_id=HOME) == "5v4"


def test_decode_away_shorthanded_from_away_perspective():
    # same code, but away is shooting -> from away's perspective, 4v5
    assert decode_strength_state("1451", event_owner_team_id=AWAY, home_team_id=HOME) == "4v5"


def test_decode_5_on_3():
    assert decode_strength_state("1351", event_owner_team_id=HOME, home_team_id=HOME) == "5v3"


def test_decode_both_goalies_pulled():
    assert decode_strength_state("0440", event_owner_team_id=HOME, home_team_id=HOME) == "4v4"


def test_decode_malformed_code_returns_other():
    assert decode_strength_state("bogus", event_owner_team_id=HOME, home_team_id=HOME) == "other"
    assert decode_strength_state(None, event_owner_team_id=HOME, home_team_id=HOME) == "other"


def test_period_offset_regulation_periods_fixed_1200s():
    assert period_offset_seconds(1, "REG", game_type=2) == 0
    assert period_offset_seconds(2, "REG", game_type=2) == 1200
    assert period_offset_seconds(3, "REG", game_type=2) == 2400


def test_period_offset_regular_season_ot_is_300s():
    assert period_offset_seconds(4, "OT", game_type=2) == 3600
    # a second reg-season OT period would be unusual but not invalid to compute an offset for
    assert period_offset_seconds(5, "OT", game_type=2) == 3900


def test_period_offset_playoff_ot_is_1200s():
    assert period_offset_seconds(4, "OT", game_type=3) == 3600
    assert period_offset_seconds(5, "OT", game_type=3) == 4800


def test_elapsed_seconds_combines_offset_and_clock():
    assert elapsed_seconds("00:08", period=1, period_type="REG", game_type=2) == 8
    assert elapsed_seconds("03:24", period=4, period_type="OT", game_type=2) == 3600 + 204
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_decoding.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'etl.advanced_stats.decoding'`

- [ ] **Step 3: Write the module**

Create `etl/advanced_stats/__init__.py` (empty) and `etl/advanced_stats/decoding.py`:

```python
REGULATION_PERIOD_SECONDS = 1200
REGULAR_SEASON_OT_SECONDS = 300
PLAYOFF_OT_SECONDS = 1200


def decode_strength_state(situation_code, event_owner_team_id, home_team_id):
    """situation_code is [awayGoalieInNet][awaySkaters][homeSkaters][homeGoalieInNet],
    confirmed via live NHL API samples (games 2020020003, 2020020007). Returns
    a generic '{shooting}v{opposing}' string oriented to the shooting team's
    perspective, or 'other' for anything that doesn't parse as 4 digits."""
    if not situation_code or len(situation_code) != 4 or not situation_code.isdigit():
        return "other"

    away_skaters = int(situation_code[1])
    home_skaters = int(situation_code[2])

    if event_owner_team_id == home_team_id:
        return f"{home_skaters}v{away_skaters}"
    return f"{away_skaters}v{home_skaters}"


def period_offset_seconds(period, period_type, game_type):
    """Cumulative elapsed-seconds offset at the start of `period`. Regulation
    periods (1-3) are always 1200s. OT length depends on game_type: 300s for
    regular season (game_type=2, single 3-on-3 period), 1200s for playoffs
    (game_type=3, full sudden-death periods) -- confirmed via live fetch that
    a regular-season OT period ends by ~300s (game 2020020003)."""
    if period <= 3:
        return (period - 1) * REGULATION_PERIOD_SECONDS

    ot_period_length = REGULAR_SEASON_OT_SECONDS if game_type == 2 else PLAYOFF_OT_SECONDS
    ot_periods_elapsed = period - 4
    return 3 * REGULATION_PERIOD_SECONDS + ot_periods_elapsed * ot_period_length


def elapsed_seconds(clock, period, period_type, game_type):
    minutes, seconds = clock.split(":")
    within_period = int(minutes) * 60 + int(seconds)
    return period_offset_seconds(period, period_type, game_type) + within_period
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_decoding.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add etl/advanced_stats/ tests/test_decoding.py
git commit -m "feat: add situation_code decoding and elapsed-time conversion helpers"
```

---

### Task 4: Advanced stats schema

**Files:**
- Modify: `src/database.py` (add `CREATE_PLAYER_GAME_ADVANCED_STATS`, `CREATE_TEAM_GAME_ADVANCED_STATS`, `CREATE_PLAYER_SEASON_ADVANCED_STATS`, `CREATE_TEAM_SEASON_ADVANCED_STATS`, `CREATE_PLAYER_CAREER_ADVANCED_STATS`, `CREATE_PLAYER_ADVANCED_PERCENTILES`, plus write functions)
- Modify: `tests/test_database.py`

**Interfaces:**
- Produces: `database.upsert_player_game_advanced_stats(conn, row: dict) -> None`
- Produces: `database.upsert_team_game_advanced_stats(conn, row: dict) -> None`
- Produces: `database.upsert_player_advanced_percentiles(conn, row: dict) -> None`

Per the design spec's Data Model section, use exact column shapes there. `player_season_advanced_stats`/`player_career_advanced_stats`/`team_season_advanced_stats` are populated by Task 6's `GROUP BY` aggregation, not by direct upsert calls from Task 5 — no separate write function needed for those, a plain `INSERT ... SELECT ... GROUP BY` executed via `conn.execute` is sufficient, matching how `player_season_stats` is populated from `player_game_stats` today (check `src/database.py` for that exact precedent before writing Task 6's SQL).

- [ ] **Step 1: Write failing tests for the new upsert functions**

Add to `tests/test_database.py`:

```python
def test_upsert_player_game_advanced_stats_is_idempotent(conn):
    _stub_player(conn, player_id=1, position_code="C")
    row = {
        "game_id": 100, "player_id": 1, "team_id": None, "strength_state": "5v5",
        "cf": 3, "ca": 2, "ff": 2, "fa": 1, "hdcf": 1, "hdca": 0,
        "gf": 1, "ga": 0, "primary_points": 1, "toi_seconds": 900,
    }
    database.upsert_player_game_advanced_stats(conn, row)
    database.upsert_player_game_advanced_stats(conn, row)  # re-run, must not duplicate
    conn.commit()

    count = conn.execute(
        "SELECT COUNT(*) AS c FROM player_game_advanced_stats"
    ).fetchone()["c"]
    assert count == 1


def test_upsert_player_game_advanced_stats_updates_on_conflict(conn):
    _stub_player(conn, player_id=1, position_code="C")
    row = {
        "game_id": 100, "player_id": 1, "team_id": None, "strength_state": "5v5",
        "cf": 3, "ca": 2, "ff": 2, "fa": 1, "hdcf": 1, "hdca": 0,
        "gf": 1, "ga": 0, "primary_points": 1, "toi_seconds": 900,
    }
    database.upsert_player_game_advanced_stats(conn, row)
    row["cf"] = 5  # a recompute changed the value
    database.upsert_player_game_advanced_stats(conn, row)
    conn.commit()

    result = conn.execute(
        "SELECT cf FROM player_game_advanced_stats WHERE game_id=100 AND player_id=1 AND strength_state='5v5'"
    ).fetchone()
    assert result["cf"] == 5
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_database.py -v -k advanced_stats`
Expected: FAIL — `AttributeError: module 'src.database' has no attribute 'upsert_player_game_advanced_stats'`

- [ ] **Step 3: Add the schema and write functions**

In `src/database.py`, add the six `CREATE TABLE IF NOT EXISTS` statements from the design spec's Data Model section verbatim (including the `game_type` + `team_abbrevs` columns on the season/career tables per the grilling-finding note there), register them in `create_all_tables`, and add:

```python
def upsert_player_game_advanced_stats(conn, r):
    conn.execute("""
        INSERT INTO player_game_advanced_stats
            (game_id, player_id, team_id, strength_state, cf, ca, ff, fa,
             hdcf, hdca, gf, ga, primary_points, toi_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(game_id, player_id, strength_state) DO UPDATE SET
            team_id=excluded.team_id, cf=excluded.cf, ca=excluded.ca,
            ff=excluded.ff, fa=excluded.fa, hdcf=excluded.hdcf, hdca=excluded.hdca,
            gf=excluded.gf, ga=excluded.ga, primary_points=excluded.primary_points,
            toi_seconds=excluded.toi_seconds
    """, (r["game_id"], r["player_id"], r["team_id"], r["strength_state"],
          r["cf"], r["ca"], r["ff"], r["fa"], r["hdcf"], r["hdca"],
          r["gf"], r["ga"], r["primary_points"], r["toi_seconds"]))


def upsert_team_game_advanced_stats(conn, r):
    conn.execute("""
        INSERT INTO team_game_advanced_stats
            (game_id, team_id, strength_state, cf, ca, ff, fa, gf, ga,
             shots_for, shots_against)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(game_id, team_id, strength_state) DO UPDATE SET
            cf=excluded.cf, ca=excluded.ca, ff=excluded.ff, fa=excluded.fa,
            gf=excluded.gf, ga=excluded.ga, shots_for=excluded.shots_for,
            shots_against=excluded.shots_against
    """, (r["game_id"], r["team_id"], r["strength_state"], r["cf"], r["ca"],
          r["ff"], r["fa"], r["gf"], r["ga"], r["shots_for"], r["shots_against"]))


def upsert_player_advanced_percentiles(conn, r):
    conn.execute("""
        INSERT INTO player_advanced_percentiles
            (season_id, player_id, strength_state, position_group,
             cf_pct_pctile, ff_pct_pctile, hdcf_pct_pctile, primary_points_pctile)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(season_id, player_id, strength_state) DO UPDATE SET
            position_group=excluded.position_group,
            cf_pct_pctile=excluded.cf_pct_pctile, ff_pct_pctile=excluded.ff_pct_pctile,
            hdcf_pct_pctile=excluded.hdcf_pct_pctile,
            primary_points_pctile=excluded.primary_points_pctile
    """, (r["season_id"], r["player_id"], r["strength_state"], r["position_group"],
          r["cf_pct_pctile"], r["ff_pct_pctile"], r["hdcf_pct_pctile"],
          r["primary_points_pctile"]))
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_database.py -v -k advanced_stats`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat: add advanced-stats schema and upsert functions"
```

---

### Task 5: Sweep-line on-ice reconstruction algorithm

**Files:**
- Create: `etl/advanced_stats/sweep.py`
- Test: `tests/test_sweep.py`

**Interfaces:**
- Produces: `sweep.compute_game_advanced_stats(shifts: list[dict], events: list[dict], home_team_id: int, game_type: int) -> tuple[list[dict], list[dict]]` — returns `(player_rows, team_rows)`, each row shaped for `upsert_player_game_advanced_stats`/`upsert_team_game_advanced_stats` (minus `game_id`, added by the caller in Task 6).
- Consumes: `decoding.decode_strength_state`, `decoding.elapsed_seconds` (Task 3).

This is the crux of the whole feature — the most important task to get right and the one with the richest test list, directly reflecting every grilling finding.

- [ ] **Step 1: Write failing tests covering every grilling-found edge case**

Create `tests/test_sweep.py`:

```python
from etl.advanced_stats.sweep import compute_game_advanced_stats

HOME = 1
AWAY = 2


def _shift(player_id, team_id, period, start, end, position_code="C"):
    return {"player_id": player_id, "team_id": team_id, "period": period,
            "start_time": start, "end_time": end, "position_code": position_code}


def _event(event_type, period, time_in_period, situation_code, event_owner_team_id,
           x_coord=0, y_coord=0):
    return {"event_type": event_type, "period": period, "time_in_period": time_in_period,
            "situation_code": situation_code, "event_owner_team_id": event_owner_team_id,
            "x_coord": x_coord, "y_coord": y_coord, "period_type": "REG"}


def test_shot_credits_on_ice_skaters_both_sides():
    shifts = [
        _shift(1, HOME, 1, "00:00", "20:00"),
        _shift(2, AWAY, 1, "00:00", "20:00"),
    ]
    events = [_event("shot-on-goal", 1, "00:10", "1551", HOME)]

    player_rows, team_rows = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)

    home_row = next(r for r in player_rows if r["player_id"] == 1)
    away_row = next(r for r in player_rows if r["player_id"] == 2)
    assert home_row["cf"] == 1 and home_row["ca"] == 0
    assert away_row["ca"] == 1 and away_row["cf"] == 0


def test_blocked_shot_counts_corsi_not_fenwick():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, AWAY, 1, "00:00", "20:00")]
    events = [_event("blocked-shot", 1, "00:10", "1551", HOME)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    home_row = next(r for r in player_rows if r["player_id"] == 1)
    assert home_row["cf"] == 1
    assert home_row["ff"] == 0


def test_goalie_excluded_from_skater_credit():
    shifts = [
        _shift(1, HOME, 1, "00:00", "20:00", position_code="C"),
        _shift(99, HOME, 1, "00:00", "20:00", position_code="G"),
        _shift(2, AWAY, 1, "00:00", "20:00"),
    ]
    events = [_event("shot-on-goal", 1, "00:10", "1551", HOME)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    goalie_rows = [r for r in player_rows if r["player_id"] == 99]
    assert goalie_rows == []  # goalie gets no advanced-stats row at all


def test_shift_with_no_end_time_closes_at_period_boundary():
    shifts = [
        _shift(1, HOME, 1, "18:00", None),   # still on ice at period end
        _shift(2, AWAY, 1, "00:00", "20:00"),
    ]
    events = [_event("shot-on-goal", 1, "19:00", "1551", HOME)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    home_row = next(r for r in player_rows if r["player_id"] == 1)
    assert home_row["cf"] == 1  # player 1 was still credited as on-ice


def test_shootout_period_excluded_entirely():
    shifts = [_shift(1, HOME, 5, "00:00", "00:30")]
    events = [{**_event("goal", 5, "00:10", "1010", HOME), "period_type": "SO"}]

    player_rows, team_rows = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    assert player_rows == []
    assert team_rows == []


def test_strength_state_generic_not_coerced_to_fixed_bucket():
    shifts = [
        _shift(1, HOME, 1, "00:00", "20:00"),
        _shift(2, HOME, 1, "00:00", "20:00"),
        _shift(3, HOME, 1, "00:00", "20:00"),
        _shift(4, HOME, 1, "00:00", "20:00"),
        _shift(5, HOME, 1, "00:00", "20:00"),
        _shift(6, AWAY, 1, "00:00", "20:00"),
        _shift(7, AWAY, 1, "00:00", "20:00"),
        _shift(8, AWAY, 1, "00:00", "20:00"),
    ]
    # 1351 = away down to 3 vs home's 5 -> a 5-on-3
    events = [_event("shot-on-goal", 1, "00:10", "1351", HOME)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    home_row = next(r for r in player_rows if r["player_id"] == 1)
    assert home_row["strength_state"] == "5v3"


def test_primary_points_needs_no_on_ice_data():
    events = [{**_event("goal", 1, "05:00", "1551", HOME), "shooting_player_id": 1,
               "assist1_player_id": 2}]
    player_rows, _ = compute_game_advanced_stats([], events, home_team_id=HOME, game_type=2)

    scorer_row = next(r for r in player_rows if r["player_id"] == 1)
    assister_row = next(r for r in player_rows if r["player_id"] == 2)
    assert scorer_row["primary_points"] == 1
    assert assister_row["primary_points"] == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_sweep.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'etl.advanced_stats.sweep'`

- [ ] **Step 3: Write the module**

Create `etl/advanced_stats/sweep.py`. Implementation notes rather than full code (this is genuinely the most complex piece — expect real iteration during implementation, not a mechanical transcription):

- Filter out any shift/event where `period_type == 'SO'` first (test: `test_shootout_period_excluded_entirely`).
- Convert every shift's `start_time`/`end_time` and every event's `time_in_period` to elapsed seconds via `decoding.elapsed_seconds`, passing through each row's own `period`/`period_type`/`game_type` (a null `end_time` resolves to that shift's period's end boundary, via `decoding.period_offset_seconds(period + 1, ...)`).
- Build a chronological merge of `(timestamp, kind, payload)` tuples for shift-starts, shift-ends, and events; walk it once maintaining `on_ice = {team_id: set(player_id)}`, restricted to `position_code in ('C','L','R','D')` when adding to the set (test: `test_goalie_excluded_from_skater_credit` — a goalie's shift is present in the input but never added to `on_ice`, so it accumulates no credit and produces no output row at all).
- On a shot-attempt event (`shot-on-goal`, `missed-shot`, `blocked-shot`, `goal`): decode `strength_state` via `decoding.decode_strength_state`; for every skater in `on_ice[shooting_team]`, increment that player's `(strength_state)` bucket's `cf` (+`hdcf` if high-danger by a fixed slot-zone check on normalized `x_coord`/`y_coord`); for every skater in the opposing team's on-ice set, increment `ca`/`hdca`. `ff`/`fa` mirror `cf`/`ca` except `blocked-shot` doesn't count. `goal` events additionally increment `gf`/`ga` and the team-level `shots_for`/`shots_against` (a goal is also a shot on goal).
- Accumulate `toi_seconds` per player per strength-state as the sweep passes through each interval between consecutive timestamps (multiply the interval length by 1 for every skater currently in `on_ice`, bucketed by whatever `strength_state` was active during that interval — this requires tracking the "current" strength state as a piece of sweep state too, updated whenever an event changes it, not just on shot events).
- `primary_points` comes from a separate, non-sweep pass: iterate `events`, and for any `goal` event increment the scorer's and `assist1_player_id`'s `primary_points` in whatever `strength_state` that goal occurred at — independent of on-ice sets, so it works even with an empty `shifts` list (test: `test_primary_points_needs_no_on_ice_data`).
- Return `(player_rows, team_rows)` as flat lists of dicts, one row per distinct `(player_id, strength_state)` / `(team_id, strength_state)` combination that accumulated anything.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_sweep.py -v`
Expected: PASS (7 tests) — iterate on the implementation until every case passes; this task's tests are the actual spec for correctness, treat any test that seems wrong as a signal to re-examine the test, not silently loosen it.

- [ ] **Step 5: Commit**

```bash
git add etl/advanced_stats/sweep.py tests/test_sweep.py
git commit -m "feat: add sweep-line on-ice reconstruction algorithm"
```

---

### Task 6: `etl/compute_advanced_stats.py` — main orchestration module

**Files:**
- Create: `etl/compute_advanced_stats.py`
- Test: `tests/test_compute_advanced_stats.py`

**Interfaces:**
- Consumes: `sweep.compute_game_advanced_stats` (Task 5), `database.upsert_player_game_advanced_stats`/`upsert_team_game_advanced_stats` (Task 4).
- Produces: `compute_advanced_stats.run(conn) -> None` (per-game pass, gated `NOT EXISTS`-style like every other loader) and `compute_advanced_stats.compute_season_aggregates(conn, season_id, game_type) -> None` and `compute_advanced_stats.compute_percentiles(conn, season_id) -> None` as separate, explicitly-called steps (not run automatically inside `run()` on every invocation — season aggregation only needs to re-run once per season's games are all processed, not once per new game, so keep it as a distinct, cheaper-to-reason-about step per the design spec's Operability section).

- [ ] **Step 1: Write a failing integration test for the per-game gating and DB round-trip**

Create `tests/test_compute_advanced_stats.py`:

```python
from src import database
import etl.compute_advanced_stats as module


def test_run_processes_pending_game_and_is_idempotent(conn):
    database.insert_game(conn, {
        "game_id": 2024020001, "season_id": None, "game_type": 2,
        "game_date": "2024-10-04", "venue": None, "home_team_id": 1,
        "away_team_id": 2, "home_score": 1, "away_score": 0,
        "last_period_type": "REG", "game_state": "OFF",
    })
    database._stub_player(conn, player_id=1, position_code="C")  # or the real stub helper
    database.insert_player_shift(conn, {
        "game_id": 2024020001, "shift_id": 1, "player_id": 1, "team_id": 1,
        "period": 1, "start_time": "00:00", "end_time": "20:00", "duration": "20:00",
    })
    database.insert_game_event(conn, {
        "game_id": 2024020001, "event_id": 1, "period": 1, "time_in_period": "00:10",
        "situation_code": "1551", "event_type": "shot-on-goal", "zone_code": "O",
        "x_coord": 10, "y_coord": 0, "shot_type": "wrist", "event_owner_team_id": 1,
        "shooting_player_id": None, "blocking_player_id": None, "goalie_in_net_id": None,
        "assist1_player_id": None, "assist2_player_id": None, "details_json": "{}",
        "home_team_defending_side": "right",
    })
    conn.commit()

    module.run(conn)
    module.run(conn)  # second run must not duplicate or error

    count = conn.execute(
        "SELECT COUNT(*) AS c FROM player_game_advanced_stats WHERE game_id = 2024020001"
    ).fetchone()["c"]
    assert count == 1
```

(Adjust the player-stub call to whatever this codebase's real test helper is named — check `tests/test_database.py`'s existing `_stub_player` fixture rather than assuming.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'etl.compute_advanced_stats'`

- [ ] **Step 3: Write the module**

Create `etl/compute_advanced_stats.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import database
from etl.advanced_stats.sweep import compute_game_advanced_stats


def run(conn):
    print("Computing advanced stats for completed games...")

    pending = conn.execute("""
        SELECT g.game_id, g.game_type, g.home_team_id FROM games g
        WHERE g.game_state = 'OFF'
          AND NOT EXISTS (
              SELECT 1 FROM player_game_advanced_stats pgas WHERE pgas.game_id = g.game_id
          )
    """).fetchall()

    print(f"  {len(pending)} completed games need advanced stats.")

    for row in pending:
        game_id, game_type, home_team_id = row["game_id"], row["game_type"], row["home_team_id"]
        try:
            shifts = _load_shifts_for_sweep(conn, game_id)
            events = _load_events_for_sweep(conn, game_id)
            player_rows, team_rows = compute_game_advanced_stats(
                shifts, events, home_team_id=home_team_id, game_type=game_type
            )
            for pr in player_rows:
                database.upsert_player_game_advanced_stats(conn, {**pr, "game_id": game_id})
            for tr in team_rows:
                database.upsert_team_game_advanced_stats(conn, {**tr, "game_id": game_id})
            conn.commit()
        except Exception as e:
            print(f"  Warning: could not compute advanced stats for game {game_id}: {e}")

    print("  Advanced stats computation complete.")


def _load_shifts_for_sweep(conn, game_id):
    rows = conn.execute("""
        SELECT ps.player_id, ps.team_id, ps.period, ps.start_time, ps.end_time,
               p.position_code
        FROM player_shifts ps JOIN players p ON p.player_id = ps.player_id
        WHERE ps.game_id = ?
    """, (game_id,)).fetchall()
    return [dict(r) for r in rows]


def _load_events_for_sweep(conn, game_id):
    rows = conn.execute("""
        SELECT event_id, period, time_in_period, situation_code, event_type,
               x_coord, y_coord, event_owner_team_id, shooting_player_id,
               assist1_player_id, home_team_defending_side
        FROM game_events WHERE game_id = ?
    """, (game_id,)).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
```

Note: `_load_shifts_for_sweep`/`_load_events_for_sweep` don't have `period_type` available directly from `game_events`/`player_shifts` today (only `period`, a plain integer) — confirm during implementation whether `period_type` ('REG'/'OT'/'SO') needs its own new column on one of these tables (most likely `game_events`, since `player_shifts` doesn't currently distinguish it either), since Task 5's sweep algorithm depends on knowing it per event/shift, not just the raw period number. If so, fold that into Task 1's migration rather than adding a second migration late — flag this to the user/reviewer if discovered only now, since it wasn't caught during the design/grilling passes and changes Task 1's scope slightly.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v`
Expected: PASS

- [ ] **Step 5: Write and test season/career aggregation + percentiles**

Add `compute_season_aggregates(conn, season_id, game_type)` (a `GROUP BY` `INSERT` from `player_game_advanced_stats`/`team_game_advanced_stats` into the season tables, following whatever exact SQL shape `player_season_stats`'s own aggregation step already uses — read that first) and `compute_percentiles(conn, season_id)` (ranks `cf_pct`/`ff_pct`/`hdcf_pct`/`primary_points` within `position_group`, for `strength_state IN ('5v5','5v4','4v5')` only, excluding players with `< 10` games played that season, per the design spec).

Write at least one test per function confirming: (a) a season aggregate row sums correctly across multiple games for one player, and (b) a percentile computation ranks a known 3-player synthetic population correctly (e.g. the top CF% player lands at percentile 100, per whatever percentile formula is chosen — nearest-rank or linear interpolation, pick one and test it explicitly since "percentile" is ambiguous without a stated method).

- [ ] **Step 6: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add etl/compute_advanced_stats.py tests/test_compute_advanced_stats.py
git commit -m "feat: add advanced stats orchestration module with season aggregation and percentiles"
```

---

### Task 7: Wire into ETL orchestration + document the two-step one-time backfill

**Files:**
- Modify: `scripts/run_all_etl.py` and/or `scripts/sync.py` (check which one(s) currently run `load_play_by_play`/`load_shifts` and mirror that placement exactly — per a prior cerebrum entry, `etl/pipeline.py` does NOT exist despite being referenced in old notes; verify the real current entrypoint file(s) before editing)
- Modify: `README.md`

- [ ] **Step 1: Add `compute_advanced_stats` to the appropriate step list(s)**, after the play-by-play/shifts steps.

- [ ] **Step 2: Document the two-step one-time backfill in `README.md`**, following the existing "One-time historical backfill" section's style: `python -m etl.backfill_defending_side` (Task 2) must run before `python -m etl.compute_advanced_stats` (Task 6), both standalone, before folding into routine ETL.

- [ ] **Step 3: Manually verify no syntax/import errors**

Run: `python -m py_compile scripts/run_all_etl.py etl/compute_advanced_stats.py etl/backfill_defending_side.py`
Expected: exit code 0

- [ ] **Step 4: Commit**

```bash
git add scripts/ README.md
git commit -m "feat: wire advanced stats computation into ETL orchestration"
```

---

### Task 8: API endpoints

**Files:**
- Modify: `app.py`
- Modify/create: whatever test file already covers `app.py`'s existing routes (check for `tests/test_app.py` or similar before assuming one needs to be created)

- [ ] **Step 1: Write failing tests for both new endpoints** (using Flask's test client, following whatever pattern the existing `/api/players/stats` test already uses for request/response assertions — read it first).

- [ ] **Step 2: Run to verify they fail**

- [ ] **Step 3: Implement `GET /api/players/<player_id>/advanced` and `GET /api/teams/<team_abbrev>/advanced`** per the design spec's API Layer section — read from `player_season_advanced_stats`/`team_season_advanced_stats`/`player_advanced_percentiles`, compute PDO as a derived ratio at query time, include the 6-season trend series.

- [ ] **Step 4: Run to verify they pass**

- [ ] **Step 5: Run the full test suite**

- [ ] **Step 6: Commit**

```bash
git add app.py tests/
git commit -m "feat: add advanced stats API endpoints"
```

---

### Task 9: Frontend — Recharts, `PlayerAdvancedPanel`, and the `PlayerTable` teaser column

**Files:**
- Modify: `frontend/package.json` (add `recharts`)
- Create: `frontend/src/components/PlayerAdvancedPanel.tsx`
- Create: `frontend/src/components/PlayerAdvancedPanel.test.tsx`
- Modify: `frontend/src/components/PlayerTable.tsx` (add one `COLUMNS` entry + row-click wiring)
- Modify: `frontend/src/lib/types.ts` (add an `AdvancedStats` type matching the API response shape from Task 8)

- [ ] **Step 1: Install Recharts**

```bash
cd frontend && npm install recharts
```

- [ ] **Step 2: Write failing component tests for `PlayerAdvancedPanel`**

Following the existing `@testing-library/react` convention seen in `PlayerTable.test.tsx`: render the panel with a mock API response shape, assert the headline percentile boxes and the PDO plain-value box (not percentile-colored, per the design spec) both render, and that a strength-state selector switching from `5v5` to `5v4` updates the displayed numbers.

- [ ] **Step 3: Run to verify they fail**

Run: `cd frontend && npm test -- PlayerAdvancedPanel`
Expected: FAIL — component doesn't exist yet

- [ ] **Step 4: Build `PlayerAdvancedPanel.tsx`**

Modal/overlay component (check which existing shadcn/Base UI primitive this codebase already uses for overlays — `Dialog`/`Sheet` under `frontend/src/components/ui/` — reuse it rather than hand-rolling a new modal). Layout per the design spec's Frontend section: header (name/team/headshot), percentile boxes row (CF%, FF%, HDCF%, Primary Points — color-coded; PDO as a separate plain value box), season trend line charts via Recharts, strength-state selector defaulting to `5v5` and offering only `5v5`/`5v4`/`4v5`.

- [ ] **Step 5: Wire the `PlayerTable` teaser column and row action**

Add one `COLUMNS` entry (e.g. `{ key: "cf_pct_5v5", label: "CF% (5v5)", numeric: true, skaterOnly: true }`) and repurpose the existing row-click handler (currently scroll-highlight-only, `App.tsx` per the earlier exploration) to also open `PlayerAdvancedPanel` for that player.

- [ ] **Step 6: Run to verify component tests pass**

Run: `cd frontend && npm test`
Expected: PASS (all tests, including new ones)

- [ ] **Step 7: Run the build — mandatory per this project's bug-011/bug-014 lesson, not optional**

Run: `cd frontend && npm run build`
Expected: exit code 0, no TypeScript errors

- [ ] **Step 8: Manual verification in a real browser**

Start the dev server, open a player's panel, confirm the strength-state selector actually changes displayed values and the charts render — a passing test suite alone is not sufficient evidence for this kind of UI claim per this project's own established convention (bug-008/bug-014 precedent for sticky/scroll-type claims; the same "don't trust jsdom for real rendering behavior" logic applies to a new chart-heavy modal).

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat: add player advanced stats panel and PlayerTable teaser column"
```

---

### Task 10: Single-season dry run and spot-check (manual verification gate)

**Files:** none — this is the Testing Plan's manual spot-check, run before committing to the full 6-season/8,058-game backfill.

- [ ] **Step 1: Run the two one-time backfill scripts against a single season's games only** (temporarily filter, mirroring the pattern used for the original ingestion backfill's own single-season dry run in the prior plan, then revert the filter after).

- [ ] **Step 2: Spot-check one known game's CF/CA against a public reference** (e.g. Natural Stat Trick's published per-game 5v5 CF/CA for that same `game_id`) — per the design spec's Testing Plan item 4.

- [ ] **Step 3: Report the spot-check results to the user before running the full 6-season backfill.** The full historical computation (all 8,058 games) is a separate, deliberate, user-initiated action — this plan's scope ends at "the pipeline is proven correct on one season," matching the same boundary the original ingestion plan drew for its own backfill.
