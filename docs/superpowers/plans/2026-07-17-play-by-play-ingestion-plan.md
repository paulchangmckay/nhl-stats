# Play-by-Play & Shift Ingestion Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest raw NHL play-by-play events and player shifts for all 6 seasons currently in the DB (20202021–20252026, regular season + playoffs), laying the foundation for a future Corsi/Fenwick/xG/RAPM/WAR metrics phase — without computing any metrics yet.

**Architecture:** Two new raw tables (`game_events`, `player_shifts`) plus a `games`-table backfill for historical seasons, all populated by three new ETL scripts that follow this codebase's existing "one script per data type, idempotent upsert, `run(conn)` entry point" pattern. Common fields get real columns; everything event-type-specific is preserved losslessly in a `details_json` overflow column so later phases don't need a schema migration.

**Tech Stack:** Python, SQLite (`sqlite3` stdlib), Flask, `requests`, pytest.

## Global Constraints

- Every new DB write function uses `INSERT OR IGNORE` keyed on the table's `UNIQUE` constraint, matching every existing `insert_*` function in `src/database.py` — re-running any loader against already-loaded data must be a no-op, not a duplicate or an error.
- Every new ETL script follows the existing shape exactly: a pure extraction function (raw API dict → row dict, unit-testable with no network calls), a `run(conn)` entry point, and an `if __name__ == "__main__":` block that opens its own connection. See `etl/load_boxscores.py` as the reference.
- Per-item error handling matches `load_boxscores.py`: wrap each unit of work (one game) in `try/except Exception`, print a warning, and continue — never let one bad game abort the whole run.
- No live network calls in tests. Fixtures are inline Python dict/list literals in the test file, matching `tests/test_enrich_players.py` and `tests/test_database.py` — no separate fixture files.
- Foreign keys are enforced (`PRAGMA foreign_keys = ON` in `get_connection`). Any player_id referenced by a new table must exist in `players` first — see Task 1's `ensure_player_stub`.

---

### Task 1: Schema, dataclasses, and DB write functions

**Files:**
- Modify: `src/database.py` (add `CREATE_GAME_EVENTS`, `CREATE_PLAYER_SHIFTS`, index statements, `create_all_tables`, `insert_game_event`, `insert_player_shift`, `ensure_player_stub`)
- Modify: `tests/test_database.py` (add tests for the three new write functions)

**Interfaces:**
- Produces: `database.insert_game_event(conn, e: dict) -> None` — `e` keys: `game_id, event_id, period, time_in_period, situation_code, event_type, zone_code, x_coord, y_coord, shot_type, event_owner_team_id, shooting_player_id, blocking_player_id, goalie_in_net_id, assist1_player_id, assist2_player_id, details_json`.
- Produces: `database.insert_player_shift(conn, s: dict) -> None` — `s` keys: `game_id, shift_id, player_id, team_id, period, start_time, end_time, duration`.
- Produces: `database.ensure_player_stub(conn, player_id: int, first_name: str = "Unknown", last_name: str = "") -> None`.

No new `models.py` dataclasses: unlike `Game`/`PlayerGameStats`, `game_events`/`player_shifts` rows are built and consumed as plain dicts end-to-end (Tasks 4–5's `_extract_event`/`_extract_shift` return dicts directly, and their tests subscript them as `row["game_id"]`) — matching `insert_standings_snapshot`'s existing dict-based convention rather than the dataclass-based one, since there's no intermediate step that benefits from the extra type.

- [ ] **Step 1: Write failing tests for the new write functions**

Append to `tests/test_database.py`:

```python
def test_insert_game_event_is_idempotent(conn):
    database.ensure_player_stub(conn, 1)
    event = {
        "game_id": 100, "event_id": 1, "period": 1, "time_in_period": "00:08",
        "situation_code": "1551", "event_type": "shot-on-goal", "zone_code": "O",
        "x_coord": 56, "y_coord": -39, "shot_type": "wrist",
        "event_owner_team_id": None, "shooting_player_id": 1,
        "blocking_player_id": None, "goalie_in_net_id": None,
        "assist1_player_id": None, "assist2_player_id": None,
        "details_json": "{}",
    }
    database.insert_game_event(conn, event)
    database.insert_game_event(conn, event)  # re-insert, must not duplicate
    conn.commit()

    count = conn.execute("SELECT COUNT(*) AS c FROM game_events").fetchone()["c"]
    assert count == 1


def test_insert_player_shift_is_idempotent(conn):
    database.ensure_player_stub(conn, 2)
    shift = {
        "game_id": 100, "shift_id": 1, "player_id": 2, "team_id": None,
        "period": 1, "start_time": "00:00", "end_time": "17:15", "duration": "17:15",
    }
    database.insert_player_shift(conn, shift)
    database.insert_player_shift(conn, shift)  # re-insert, must not duplicate
    conn.commit()

    count = conn.execute("SELECT COUNT(*) AS c FROM player_shifts").fetchone()["c"]
    assert count == 1


def test_ensure_player_stub_creates_placeholder_when_missing(conn):
    database.ensure_player_stub(conn, 999, first_name="Jacob", last_name="Markstrom")
    conn.commit()

    row = conn.execute(
        "SELECT first_name, last_name FROM players WHERE player_id = ?", (999,)
    ).fetchone()
    assert row["first_name"] == "Jacob"
    assert row["last_name"] == "Markstrom"


def test_ensure_player_stub_does_not_overwrite_existing_player(conn):
    _stub_player(conn, player_id=5, position_code="C")

    database.ensure_player_stub(conn, 5, first_name="Should", last_name="NotApply")
    conn.commit()

    row = conn.execute(
        "SELECT first_name, position_code FROM players WHERE player_id = ?", (5,)
    ).fetchone()
    assert row["first_name"] == "Test"  # from _stub_player, unchanged
    assert row["position_code"] == "C"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_database.py -v -k "game_event or player_shift or ensure_player_stub"`
Expected: FAIL — `AttributeError: module 'src.database' has no attribute 'insert_game_event'` (and similarly for the other two functions/tables not existing yet).

- [ ] **Step 3: Add the schema and write functions**

In `src/database.py`, add after `CREATE_PLAYER_CAREER_STATS` (before `CREATE_SYNC_LOG`):

```python
CREATE_GAME_EVENTS = """
CREATE TABLE IF NOT EXISTS game_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id             INTEGER NOT NULL REFERENCES games(game_id),
    event_id            INTEGER NOT NULL,
    period              INTEGER NOT NULL,
    time_in_period      TEXT,
    situation_code      TEXT,
    event_type          TEXT NOT NULL,
    zone_code           TEXT,
    x_coord             INTEGER,
    y_coord             INTEGER,
    shot_type           TEXT,
    event_owner_team_id INTEGER REFERENCES teams(team_id),
    shooting_player_id  INTEGER REFERENCES players(player_id),
    blocking_player_id  INTEGER REFERENCES players(player_id),
    goalie_in_net_id    INTEGER REFERENCES players(player_id),
    assist1_player_id   INTEGER REFERENCES players(player_id),
    assist2_player_id   INTEGER REFERENCES players(player_id),
    details_json        TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE (game_id, event_id)
);
"""

CREATE_GAME_EVENTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_game_events_team_type ON game_events(event_owner_team_id, event_type)",
    "CREATE INDEX IF NOT EXISTS idx_game_events_shooter ON game_events(shooting_player_id)",
]

CREATE_PLAYER_SHIFTS = """
CREATE TABLE IF NOT EXISTS player_shifts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id    INTEGER NOT NULL REFERENCES games(game_id),
    shift_id   INTEGER NOT NULL,
    player_id  INTEGER NOT NULL REFERENCES players(player_id),
    team_id    INTEGER REFERENCES teams(team_id),
    period     INTEGER NOT NULL,
    start_time TEXT,
    end_time   TEXT,
    duration   TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (game_id, shift_id)
);
"""

CREATE_PLAYER_SHIFTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_player_shifts_player_game ON player_shifts(player_id, game_id)",
]
```

Update `create_all_tables`:

```python
def create_all_tables(conn):
    for sql in [CREATE_TEAMS, CREATE_SEASONS, CREATE_PLAYERS,
                CREATE_GAMES, CREATE_PLAYER_GAME_STATS, CREATE_STANDINGS,
                CREATE_PLAYER_SEASON_STATS, CREATE_PLAYER_CAREER_STATS,
                CREATE_GAME_EVENTS, CREATE_PLAYER_SHIFTS, CREATE_SYNC_LOG]:
        conn.execute(sql)
    for sql in CREATE_GAME_EVENTS_INDEXES + CREATE_PLAYER_SHIFTS_INDEXES:
        conn.execute(sql)
```

Add at the end of `src/database.py`, after `insert_standings_snapshot`:

```python
def insert_game_event(conn, e):
    conn.execute(
        "INSERT OR IGNORE INTO game_events "
        "(game_id, event_id, period, time_in_period, situation_code, event_type, "
        "zone_code, x_coord, y_coord, shot_type, event_owner_team_id, "
        "shooting_player_id, blocking_player_id, goalie_in_net_id, "
        "assist1_player_id, assist2_player_id, details_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (e["game_id"], e["event_id"], e["period"], e["time_in_period"],
         e["situation_code"], e["event_type"], e["zone_code"], e["x_coord"],
         e["y_coord"], e["shot_type"], e["event_owner_team_id"],
         e["shooting_player_id"], e["blocking_player_id"], e["goalie_in_net_id"],
         e["assist1_player_id"], e["assist2_player_id"], e["details_json"]),
    )


def insert_player_shift(conn, s):
    conn.execute(
        "INSERT OR IGNORE INTO player_shifts "
        "(game_id, shift_id, player_id, team_id, period, start_time, end_time, duration) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (s["game_id"], s["shift_id"], s["player_id"], s["team_id"], s["period"],
         s["start_time"], s["end_time"], s["duration"]),
    )


def ensure_player_stub(conn, player_id, first_name="Unknown", last_name=""):
    """Inserts a minimal placeholder player row if player_id isn't already
    present, so FK-constrained inserts (game_events, player_shifts) referencing
    a not-yet-seen player don't fail. enrich_players.py's landing-API pass
    (gated on position_code IS NULL) picks up any such stub and fills in the
    real name/bio on its next run."""
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (player_id, first_name, last_name),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_database.py -v -k "game_event or player_shift or ensure_player_stub"`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full existing test suite to check for regressions**

Run: `python -m pytest tests/ -v`
Expected: PASS (all existing tests plus the 4 new ones)

- [ ] **Step 6: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat: add game_events/player_shifts schema and write functions"
```

---

### Task 2: `api_client` — three new fetch functions

**Files:**
- Modify: `src/api_client.py`

**Interfaces:**
- Produces: `api_client.get_season_games(season_id: str, game_type: int) -> list[dict]`
- Produces: `api_client.get_play_by_play(game_id: int) -> dict` (caller reads `["plays"]`)
- Produces: `api_client.get_shift_chart(game_id: int) -> list[dict]`

No test file exists for `api_client.py` today (it's a thin wrapper with no branching logic beyond URL construction and pass-through). Following the "no live network calls in tests" constraint, this task verifies URL construction by monkeypatching `_get` — a new, small test file, since none exists yet to extend.

- [ ] **Step 1: Write failing tests for URL construction**

Create `tests/test_api_client.py`:

```python
from src import api_client


def test_get_season_games_builds_correct_url(monkeypatch):
    captured = {}

    def fake_get(url):
        captured["url"] = url
        return {"data": [{"id": 1}], "total": 1}

    monkeypatch.setattr(api_client, "_get", fake_get)
    result = api_client.get_season_games("20242025", 2)

    assert "season=20242025" in captured["url"]
    assert "gameType=2" in captured["url"]
    assert result == [{"id": 1}]


def test_get_play_by_play_builds_correct_url(monkeypatch):
    captured = {}

    def fake_get(url):
        captured["url"] = url
        return {"plays": []}

    monkeypatch.setattr(api_client, "_get", fake_get)
    result = api_client.get_play_by_play(2024020001)

    assert captured["url"] == "https://api-web.nhle.com/v1/gamecenter/2024020001/play-by-play"
    assert result == {"plays": []}


def test_get_shift_chart_builds_correct_url(monkeypatch):
    captured = {}

    def fake_get(url):
        captured["url"] = url
        return {"data": [{"id": 1, "playerId": 100}]}

    monkeypatch.setattr(api_client, "_get", fake_get)
    result = api_client.get_shift_chart(2024020001)

    assert "gameId=2024020001" in captured["url"]
    assert result == [{"id": 1, "playerId": 100}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api_client.py -v`
Expected: FAIL — `AttributeError: module 'src.api_client' has no attribute 'get_season_games'`

- [ ] **Step 3: Add the three functions**

In `src/api_client.py`, add after `get_player_landing`:

```python
def get_season_games(season_id, game_type):
    """Returns every game for a season/gameType in one unpaginated call."""
    url = f"{BASE_STATS}/game?cayenneExp=season={season_id}%20and%20gameType={game_type}"
    data = _get(url)
    return data.get("data", [])


def get_play_by_play(game_id):
    """Returns the full play-by-play feed for a game; caller reads data['plays']."""
    return _get(f"{BASE_WEB}/gamecenter/{game_id}/play-by-play")


def get_shift_chart(game_id):
    """Returns per-player shift records for a game."""
    data = _get(f"{BASE_STATS}/shiftcharts?cayenneExp=gameId={game_id}")
    return data.get("data", [])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_api_client.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/api_client.py tests/test_api_client.py
git commit -m "feat: add play-by-play, shift chart, and season game list API client functions"
```

---

### Task 3: `etl/load_historical_schedule.py`

**Files:**
- Create: `etl/load_historical_schedule.py`
- Test: `tests/test_load_historical_schedule.py`

**Interfaces:**
- Consumes: `api_client.get_season_games(season_id, game_type)` (Task 2), `database.insert_game(conn, dict)` (existing), `models.Game` (existing).
- Produces: `load_historical_schedule.run(conn) -> None`; `load_historical_schedule._map_game_state(game_state_id) -> str`; `load_historical_schedule._extract_game(g: dict) -> Game` (used by Task 8 test-writers as the reference shape, not consumed by other tasks).

- [ ] **Step 1: Write failing tests for state mapping and extraction**

Create `tests/test_load_historical_schedule.py`:

```python
from etl.load_historical_schedule import _map_game_state, _extract_game


def test_map_game_state_known_value_returns_off():
    assert _map_game_state(7) == "OFF"


def test_map_game_state_unknown_value_falls_back_to_raw_string():
    assert _map_game_state(99) == "99"


def test_extract_game_maps_all_fields():
    raw = {
        "id": 2024020001, "season": 20242025, "gameType": 2,
        "gameDate": "2024-10-04", "homeTeamId": 7, "visitingTeamId": 1,
        "homeScore": 1, "visitingScore": 4, "gameStateId": 7,
    }
    game = _extract_game(raw)

    assert game.game_id == 2024020001
    assert game.season_id == "20242025"
    assert game.game_type == 2
    assert game.game_date == "2024-10-04"
    assert game.home_team_id == 7
    assert game.away_team_id == 1
    assert game.home_score == 1
    assert game.away_score == 4
    assert game.game_state == "OFF"
    assert game.venue is None
    assert game.last_period_type is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_load_historical_schedule.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'etl.load_historical_schedule'`

- [ ] **Step 3: Write the module**

Create `etl/load_historical_schedule.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database
from src.models import Game

SEASONS = ["20202021", "20212022", "20222023", "20232024", "20242025", "20252026"]
GAME_TYPES = [2, 3]  # regular season, playoffs

_GAME_STATE_MAP = {
    7: "OFF",
}


def _map_game_state(game_state_id):
    """Maps the numeric gameStateId from the season-game-list endpoint to the
    string gameState vocabulary used everywhere else in this codebase
    (game_state = 'OFF' gating). Falls back to the raw numeric value as a
    string for anything unmapped, so the row isn't lost -- it just won't
    match 'OFF'-gated queries until the mapping is extended."""
    return _GAME_STATE_MAP.get(game_state_id, str(game_state_id))


def _extract_game(g):
    return Game(
        game_id=g["id"],
        season_id=str(g.get("season", "")),
        game_type=g.get("gameType"),
        game_date=g.get("gameDate", ""),
        venue=None,
        home_team_id=g.get("homeTeamId"),
        away_team_id=g.get("visitingTeamId"),
        home_score=g.get("homeScore"),
        away_score=g.get("visitingScore"),
        last_period_type=None,
        game_state=_map_game_state(g.get("gameStateId")),
    )


def run(conn):
    print("Loading historical schedule (season game backfill)...")
    total = 0

    for season_id in SEASONS:
        for game_type in GAME_TYPES:
            try:
                games = api_client.get_season_games(season_id, game_type)
            except Exception as e:
                print(f"  Warning: could not fetch game list for season {season_id} "
                      f"type {game_type}: {e}")
                continue

            for g in games:
                if g.get("gameStateId") not in _GAME_STATE_MAP:
                    print(f"  Warning: game {g.get('id')} has unmapped "
                          f"gameStateId {g.get('gameStateId')!r}")
                game = _extract_game(g)
                database.insert_game(conn, game.__dict__)
                total += 1

            conn.commit()

    print(f"  {total} historical games loaded/verified.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_load_historical_schedule.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add etl/load_historical_schedule.py tests/test_load_historical_schedule.py
git commit -m "feat: add historical schedule backfill ETL script"
```

---

### Task 4: `etl/load_play_by_play.py`

**Files:**
- Create: `etl/load_play_by_play.py`
- Test: `tests/test_load_play_by_play.py`

**Interfaces:**
- Consumes: `api_client.get_play_by_play(game_id)` (Task 2), `database.insert_game_event(conn, dict)`, `database.ensure_player_stub(conn, player_id)` (Task 1).
- Produces: `load_play_by_play.run(conn) -> None`; `load_play_by_play._extract_event(game_id, play: dict) -> dict`.

**Note on commit frequency:** unlike the existing lightweight loaders (which commit once at the end, since they process at most a few dozen games per run), this loader processes up to ~7,800 games in the initial backfill. Committing once per game (not once at the end) is required for the "naturally resumable" behavior described in the design spec — an interrupted run must not lose all progress since the last full run.

- [ ] **Step 1: Write failing tests for event extraction**

Create `tests/test_load_play_by_play.py`:

```python
from etl.load_play_by_play import _extract_event


def test_extract_event_shot_on_goal():
    play = {
        "eventId": 103,
        "periodDescriptor": {"number": 1},
        "timeInPeriod": "00:08",
        "situationCode": "1551",
        "typeDescKey": "shot-on-goal",
        "details": {
            "xCoord": 56, "yCoord": -39, "zoneCode": "O", "shotType": "wrist",
            "shootingPlayerId": 8483495, "goalieInNetId": 8480045,
            "eventOwnerTeamId": 1,
        },
    }
    row = _extract_event(game_id=2024020001, play=play)

    assert row["game_id"] == 2024020001
    assert row["event_id"] == 103
    assert row["period"] == 1
    assert row["time_in_period"] == "00:08"
    assert row["situation_code"] == "1551"
    assert row["event_type"] == "shot-on-goal"
    assert row["zone_code"] == "O"
    assert row["x_coord"] == 56
    assert row["y_coord"] == -39
    assert row["shot_type"] == "wrist"
    assert row["event_owner_team_id"] == 1
    assert row["shooting_player_id"] == 8483495
    assert row["goalie_in_net_id"] == 8480045
    assert row["blocking_player_id"] is None
    assert row["assist1_player_id"] is None
    assert '"shootingPlayerId": 8483495' in row["details_json"]


def test_extract_event_goal_uses_scoring_player_id_as_shooter():
    play = {
        "eventId": 274,
        "periodDescriptor": {"number": 1},
        "timeInPeriod": "08:39",
        "situationCode": "1551",
        "typeDescKey": "goal",
        "details": {
            "scoringPlayerId": 8476474, "assist1PlayerId": 8480192,
            "eventOwnerTeamId": 1,
        },
    }
    row = _extract_event(game_id=2024020001, play=play)

    assert row["shooting_player_id"] == 8476474
    assert row["assist1_player_id"] == 8480192
    assert row["assist2_player_id"] is None


def test_extract_event_sparse_details_event_type():
    play = {
        "eventId": 152,
        "periodDescriptor": {"number": 1},
        "timeInPeriod": "00:00",
        "situationCode": "1551",
        "typeDescKey": "period-start",
    }
    row = _extract_event(game_id=2024020001, play=play)

    assert row["event_type"] == "period-start"
    assert row["shooting_player_id"] is None
    assert row["details_json"] == "{}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_load_play_by_play.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'etl.load_play_by_play'`

- [ ] **Step 3: Write the module**

Create `etl/load_play_by_play.py`:

```python
import sys
import os
import json
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database

REQUEST_DELAY_SECONDS = 0.2


def _extract_event(game_id, play):
    details = play.get("details", {}) or {}
    period_desc = play.get("periodDescriptor", {}) or {}
    return {
        "game_id": game_id,
        "event_id": play["eventId"],
        "period": period_desc.get("number"),
        "time_in_period": play.get("timeInPeriod"),
        "situation_code": play.get("situationCode"),
        "event_type": play.get("typeDescKey"),
        "zone_code": details.get("zoneCode"),
        "x_coord": details.get("xCoord"),
        "y_coord": details.get("yCoord"),
        "shot_type": details.get("shotType"),
        "event_owner_team_id": details.get("eventOwnerTeamId"),
        "shooting_player_id": details.get("shootingPlayerId") or details.get("scoringPlayerId"),
        "blocking_player_id": details.get("blockingPlayerId"),
        "goalie_in_net_id": details.get("goalieInNetId"),
        "assist1_player_id": details.get("assist1PlayerId"),
        "assist2_player_id": details.get("assist2PlayerId"),
        "details_json": json.dumps(details),
    }


def _ensure_referenced_players(conn, row):
    for key in ("shooting_player_id", "blocking_player_id", "goalie_in_net_id",
                "assist1_player_id", "assist2_player_id"):
        player_id = row.get(key)
        if player_id is not None:
            database.ensure_player_stub(conn, player_id)


def run(conn):
    print("Loading play-by-play events for completed games...")

    pending = conn.execute("""
        SELECT g.game_id FROM games g
        WHERE g.game_state = 'OFF'
          AND NOT EXISTS (
              SELECT 1 FROM game_events ge WHERE ge.game_id = g.game_id
          )
    """).fetchall()

    print(f"  {len(pending)} completed games need play-by-play.")
    total_events = 0

    for row in pending:
        game_id = row["game_id"]
        try:
            data = api_client.get_play_by_play(game_id)
        except Exception as e:
            print(f"  Warning: could not fetch play-by-play for game {game_id}: {e}")
            continue

        for play in data.get("plays", []):
            event = _extract_event(game_id, play)
            _ensure_referenced_players(conn, event)
            database.insert_game_event(conn, event)
            total_events += 1

        conn.commit()
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"  {total_events} game_event rows inserted.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_load_play_by_play.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write a failing DB-level idempotency regression test**

Append to `tests/test_load_play_by_play.py`:

```python
from src import database


def test_run_does_not_duplicate_events_on_second_invocation(conn, monkeypatch):
    database.insert_game(conn, {
        "game_id": 2024020001, "season_id": "20242025", "game_type": 2,
        "game_date": "2024-10-04", "venue": None, "home_team_id": 7,
        "away_team_id": 1, "home_score": 1, "away_score": 4,
        "last_period_type": "REG", "game_state": "OFF",
    })
    conn.commit()

    fake_plays = {"plays": [{
        "eventId": 103, "periodDescriptor": {"number": 1}, "timeInPeriod": "00:08",
        "situationCode": "1551", "typeDescKey": "shot-on-goal",
        "details": {"xCoord": 56, "yCoord": -39, "shootingPlayerId": 8483495,
                     "eventOwnerTeamId": 1},
    }]}

    import etl.load_play_by_play as module
    monkeypatch.setattr(module.api_client, "get_play_by_play", lambda gid: fake_plays)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    module.run(conn)
    # game_events now exists for this game, so a second run must find nothing pending
    module.run(conn)

    count = conn.execute("SELECT COUNT(*) AS c FROM game_events").fetchone()["c"]
    assert count == 1
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_load_play_by_play.py -v`
Expected: PASS (4 tests) — the second `run()` call finds zero pending games because `game_events` already has a row for game 2024020001, so the `NOT EXISTS` gate excludes it.

- [ ] **Step 7: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 8: Commit**

```bash
git add etl/load_play_by_play.py tests/test_load_play_by_play.py
git commit -m "feat: add play-by-play event ingestion ETL script"
```

---

### Task 5: `etl/load_shifts.py`

**Files:**
- Create: `etl/load_shifts.py`
- Test: `tests/test_load_shifts.py`

**Interfaces:**
- Consumes: `api_client.get_shift_chart(game_id)` (Task 2), `database.insert_player_shift(conn, dict)`, `database.ensure_player_stub(conn, player_id, first_name, last_name)` (Task 1).
- Produces: `load_shifts.run(conn) -> None`; `load_shifts._extract_shift(game_id, shift: dict) -> dict`.

- [ ] **Step 1: Write failing tests for shift extraction**

Create `tests/test_load_shifts.py`:

```python
from etl.load_shifts import _extract_shift


def test_extract_shift_maps_all_fields():
    shift = {
        "id": 14376602, "playerId": 8474593, "teamId": 1, "period": 1,
        "startTime": "00:00", "endTime": "17:15", "duration": "17:15",
        "firstName": "Jacob", "lastName": "Markstrom",
    }
    row = _extract_shift(game_id=2024020001, shift=shift)

    assert row["game_id"] == 2024020001
    assert row["shift_id"] == 14376602
    assert row["player_id"] == 8474593
    assert row["team_id"] == 1
    assert row["period"] == 1
    assert row["start_time"] == "00:00"
    assert row["end_time"] == "17:15"
    assert row["duration"] == "17:15"


def test_extract_shift_handles_missing_end_time():
    shift = {
        "id": 14376999, "playerId": 8474593, "teamId": 1, "period": 3,
        "startTime": "19:58", "endTime": None, "duration": None,
        "firstName": "Jacob", "lastName": "Markstrom",
    }
    row = _extract_shift(game_id=2024020001, shift=shift)

    assert row["end_time"] is None
    assert row["duration"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_load_shifts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'etl.load_shifts'`

- [ ] **Step 3: Write the module**

Create `etl/load_shifts.py`:

```python
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import api_client, database

REQUEST_DELAY_SECONDS = 0.2


def _extract_shift(game_id, shift):
    return {
        "game_id": game_id,
        "shift_id": shift["id"],
        "player_id": shift["playerId"],
        "team_id": shift.get("teamId"),
        "period": shift.get("period"),
        "start_time": shift.get("startTime"),
        "end_time": shift.get("endTime"),
        "duration": shift.get("duration"),
    }


def run(conn):
    print("Loading shift charts for completed games...")

    pending = conn.execute("""
        SELECT g.game_id FROM games g
        WHERE g.game_state = 'OFF'
          AND NOT EXISTS (
              SELECT 1 FROM player_shifts ps WHERE ps.game_id = g.game_id
          )
    """).fetchall()

    print(f"  {len(pending)} completed games need shift charts.")
    total_shifts = 0

    for row in pending:
        game_id = row["game_id"]
        try:
            shifts = api_client.get_shift_chart(game_id)
        except Exception as e:
            print(f"  Warning: could not fetch shift chart for game {game_id}: {e}")
            continue

        for shift in shifts:
            database.ensure_player_stub(
                conn, shift["playerId"],
                first_name=shift.get("firstName", "Unknown"),
                last_name=shift.get("lastName", ""),
            )
            record = _extract_shift(game_id, shift)
            database.insert_player_shift(conn, record)
            total_shifts += 1

        conn.commit()
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"  {total_shifts} player_shifts rows inserted.")


if __name__ == "__main__":
    conn = database.get_connection()
    run(conn)
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_load_shifts.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Write a failing DB-level idempotency regression test**

Append to `tests/test_load_shifts.py`:

```python
from src import database


def test_run_does_not_duplicate_shifts_on_second_invocation(conn, monkeypatch):
    database.insert_game(conn, {
        "game_id": 2024020001, "season_id": "20242025", "game_type": 2,
        "game_date": "2024-10-04", "venue": None, "home_team_id": 7,
        "away_team_id": 1, "home_score": 1, "away_score": 4,
        "last_period_type": "REG", "game_state": "OFF",
    })
    conn.commit()

    fake_shifts = [{
        "id": 14376602, "playerId": 8474593, "teamId": 1, "period": 1,
        "startTime": "00:00", "endTime": "17:15", "duration": "17:15",
        "firstName": "Jacob", "lastName": "Markstrom",
    }]

    import etl.load_shifts as module
    monkeypatch.setattr(module.api_client, "get_shift_chart", lambda gid: fake_shifts)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    module.run(conn)
    module.run(conn)  # second run must find nothing pending

    count = conn.execute("SELECT COUNT(*) AS c FROM player_shifts").fetchone()["c"]
    assert count == 1
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_load_shifts.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 8: Commit**

```bash
git add etl/load_shifts.py tests/test_load_shifts.py
git commit -m "feat: add shift chart ingestion ETL script"
```

---

### Task 6: Wire into `run_all_etl.py` and document the one-time backfill

**Files:**
- Modify: `scripts/run_all_etl.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `etl.load_historical_schedule.run`, `etl.load_play_by_play.run`, `etl.load_shifts.run` (Tasks 3–5).

No new automated test — `run_all_etl.py` is a thin orchestration script with no existing test coverage (consistent with the rest of this script). Verified manually in Step 3.

- [ ] **Step 1: Add the three new steps to `run_all_etl.py`**

Modify `scripts/run_all_etl.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import get_connection
from etl import (
    load_teams, load_standings, load_rosters, load_schedule,
    load_historical_schedule, load_boxscores, load_play_by_play, load_shifts,
    load_season_stats, enrich_players,
)

conn = get_connection()

steps = [
    ("Teams", load_teams),
    ("Standings", load_standings),
    ("Rosters / Players", load_rosters),
    ("Schedule / Games", load_schedule),
    ("Historical Schedule Backfill", load_historical_schedule),
    ("Boxscores / Player Stats", load_boxscores),
    ("Play-by-Play Events", load_play_by_play),
    ("Shift Charts", load_shifts),
    ("Season Stats (historical)", load_season_stats),
    ("Player Enrichment (bio / draft / career)", enrich_players),
]

for label, module in steps:
    print(f"\n=== {label} ===")
    try:
        module.run(conn)
    except Exception as e:
        print(f"  ERROR in {label}: {e}")

conn.close()
print("\nAll ETL complete.")
```

- [ ] **Step 2: Document the one-time backfill in `README.md`**

In `README.md`, after the existing "Run all ETL to populate the database" step (`python scripts/run_all_etl.py`), add:

```markdown
### One-time historical backfill (play-by-play & shifts)

`run_all_etl.py` keeps `game_events` and `player_shifts` current for new
games automatically. The *first* time you populate these tables, though,
there are ~7,800+ historical games (6 seasons, regular season + playoffs)
to backfill — realistically hours, not the seconds `run_all_etl.py`'s other
steps take. Run this once, standalone, before your first `run_all_etl.py`
run against a fresh database:

```bash
python -m etl.load_historical_schedule
python -m etl.load_boxscores
python -m etl.load_play_by_play
python -m etl.load_shifts
```

Each script is idempotent and resumable (safe to re-run or interrupt
partway through — already-loaded games are skipped). After this completes
once, `python scripts/run_all_etl.py` is sufficient going forward; the
same three steps run as fast no-ops when there's nothing new to load.
```

- [ ] **Step 3: Manually verify the orchestration script imports and runs cleanly**

Run: `python -c "import scripts.run_all_etl"` from the project root — this will actually execute the module (it has no `if __name__ == "__main__":` guard, matching its existing behavior), so instead verify via a syntax/import check that doesn't hit the network:

Run: `python -m py_compile scripts/run_all_etl.py etl/load_historical_schedule.py etl/load_play_by_play.py etl/load_shifts.py`
Expected: no output, exit code 0 (confirms no syntax errors / import-time failures across all four modified/new files)

- [ ] **Step 4: Commit**

```bash
git add scripts/run_all_etl.py README.md
git commit -m "feat: wire play-by-play/shift ingestion into run_all_etl, document one-time backfill"
```

---

### Task 7: Single-season dry run and spot-check (manual verification gate)

**Files:** none (no code changes — this is the verification gate the design spec's Testing Plan item #4 calls for, before running the full 6-season backfill)

This task is deliberately manual, not automated — it's validating live behavior against the real NHL API for one season before committing to the ~15,000-call full backfill.

- [ ] **Step 1: Temporarily narrow the season list to a single season**

In `etl/load_historical_schedule.py`, temporarily edit `SEASONS = ["20242025", "20242025"]` → just `SEASONS = ["20242025"]` for this dry run (revert after Step 5).

- [ ] **Step 2: Run the standalone loaders in order**

```bash
python -m etl.load_historical_schedule
python -m etl.load_boxscores
python -m etl.load_play_by_play
python -m etl.load_shifts
```

Expected: each prints a summary line (e.g. `1312 historical games loaded/verified.`, `N game_event rows inserted.`, `N player_shifts rows inserted.`) with no unhandled exceptions. Individual per-game warnings are acceptable; a large fraction of games failing is not.

- [ ] **Step 3: Spot-check one game's shot count against its boxscore**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/nhl_stats.db')
game_id = 2024020001
sog = conn.execute('''
    SELECT COUNT(*) FROM game_events
    WHERE game_id = ? AND event_type IN ('shot-on-goal','missed-shot','blocked-shot')
''', (game_id,)).fetchone()[0]
box_sog = conn.execute('SELECT SUM(shots_on_goal) FROM player_game_stats WHERE game_id = ?', (game_id,)).fetchone()[0]
print('game_events shot-attempt rows:', sog)
print('boxscore total shots_on_goal (subset of the above):', box_sog)
"
```

Expected: `game_events shot-attempt rows` (all attempt types combined) should be greater than or equal to `box_sog` (shots on goal alone) — confirms events are being captured with the right event-type breakdown, not double-counted or missing entirely.

- [ ] **Step 4: Confirm shift data reconstructs a plausible on-ice count**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/nhl_stats.db')
game_id = 2024020001
rows = conn.execute('SELECT COUNT(DISTINCT player_id) FROM player_shifts WHERE game_id = ?', (game_id,)).fetchone()[0]
print('distinct players with shifts in this game:', rows)
"
```

Expected: roughly 36-46 (both teams' active skaters + goalies for one game) — confirms shift data isn't wildly under- or over-populated.

- [ ] **Step 5: Revert the temporary season-list edit**

```bash
git diff etl/load_historical_schedule.py
git checkout -- etl/load_historical_schedule.py
```

Expected: `SEASONS` back to the full 6-season list committed in Task 3.

- [ ] **Step 6: Report results to the user before running the full backfill**

Summarize the spot-check numbers from Steps 3–4 and any warnings seen in Step 2. The full 6-season backfill (all `SEASONS`) is a separate, user-initiated action — this plan's scope ends at "the pipeline is proven correct on one season," not at "the full historical dataset is loaded," since that run will take hours and should be kicked off deliberately, not as an automatic last step of implementation.
