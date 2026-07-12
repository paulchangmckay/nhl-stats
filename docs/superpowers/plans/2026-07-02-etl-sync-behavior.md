# ETL & Sync Behavior Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two ad-hoc ETL orchestrators (`scripts/run_all_etl.py`, `scripts/sync.py`) with one unified, safe-to-repeat sync pipeline — triggered by a button in the Flask app or a weekly `launchd` job — that skips work that's still fresh, never silently overwrites good data with a gap, never runs two copies of itself at once, and reports live progress back to the UI.

**Architecture:** A new `src/sync_status.py` module owns a JSON status file (`data/sync_status.json`) that doubles as both the live progress feed and a PID-based concurrency lock, with self-healing reads that detect a crashed pipeline process. A new `etl/pipeline.py` is the single entrypoint (`python -m etl.pipeline`) that both the Flask button and `launchd` invoke; it wraps each of the 7 existing ETL modules' `run(conn)` calls with a freshness-window check (via a new `database.is_step_fresh()` helper) and log-and-continue error handling. Two of the seven modules (`load_rosters.py`, `load_standings.py`) gain diff-before-write logic so repeated syncs stop touching rows that haven't actually changed, with an explicit rule that a `null` from the API never overwrites a real value already in the DB.

**Tech Stack:** Python 3.14, Flask 3.1, SQLite3 (stdlib), pytest (newly enabled), vanilla JS/HTML for the frontend, macOS `launchd` for scheduling.

## Global Constraints

- Every existing ETL module keeps its current `run(conn)` signature — `pipeline.py` calls them exactly as `run_all_etl.py`/`sync.py` do today. No changes to `load_teams.py`, `load_schedule.py`, `load_boxscores.py`, `load_season_stats.py`, or `enrich_players.py` internals.
- Diff-before-write for rosters and standings must never let a `null`/missing API value overwrite a non-null value already in the DB, for any column either step writes.
- Sync status/progress is stored in a JSON file (`data/sync_status.json`), never in SQLite — this avoids read/write lock contention between the pipeline subprocess and Flask's polling reads.
- The concurrency lock is keyed on the actual OS PID of the running `etl.pipeline` process (not the Flask process that spawned it) and self-heals if that PID is no longer alive.
- The pipeline runs as a separate OS process (`subprocess.Popen`), never as a thread inside the Flask dev server — `app.py` runs with `debug=True`, whose auto-reloader can kill in-process background threads without warning.
- `launchd` plist uses absolute paths only (venv Python binary, explicit `WorkingDirectory`) — no shell wrapper, no reliance on inherited `PATH`.
- A failure in one pipeline step logs and moves on to the next step; it never aborts the whole run.

---

## Task 1: Test Infrastructure + `src/sync_status.py`

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_sync_status.py`
- Create: `src/sync_status.py`

**Interfaces:**
- Produces: `sync_status.STATUS_PATH` (module constant, default path `data/sync_status.json`)
- Produces: `sync_status.is_process_alive(pid: int | None) -> bool`
- Produces: `sync_status.read_status(path: str) -> dict` — self-healing: rewrites a `"running"` status with a dead PID to a terminal failed state before returning it
- Produces: `sync_status.write_status(path: str, data: dict) -> None` — atomic write (temp file + `os.replace`)
- Produces: `sync_status.try_acquire_lock(path: str) -> bool` — `True` if the lock was free and is now held by `os.getpid()`; `False` if another live process already holds it
- Produces: `sync_status.update_step(path: str, step_name: str, step_status: str) -> None`
- Produces: `sync_status.release_lock(path: str, result: str, steps: dict, error: str | None = None) -> None`
- Consumes: nothing (this is the foundational module)

- [ ] **Step 1: Enable pytest and install it**

Edit `requirements.txt`:

```
requests==2.32.3
flask==3.1.1
pytest==8.3.5
```

Run:
```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
.venv/bin/pip install pytest==8.3.5
```
Expected: `Successfully installed pytest-8.3.5 ...`

- [ ] **Step 2: Create test package files**

Create `tests/__init__.py` (empty file).

Create `tests/conftest.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src import database


@pytest.fixture
def db_conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = database.get_connection(db_path)
    database.create_all_tables(conn)
    yield conn
    conn.close()
```

- [ ] **Step 3: Write failing tests for `is_process_alive`, `read_status`, `write_status`**

Create `tests/test_sync_status.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import os as os_module
from src import sync_status


def test_is_process_alive_true_for_self():
    assert sync_status.is_process_alive(os_module.getpid()) is True


def test_is_process_alive_false_for_dead_pid():
    # High PID unlikely to be assigned on a dev machine; ProcessLookupError → False.
    assert sync_status.is_process_alive(999999) is False


def test_is_process_alive_false_for_none():
    assert sync_status.is_process_alive(None) is False


def test_read_status_missing_file_returns_default_idle(tmp_path):
    path = str(tmp_path / "status.json")
    status = sync_status.read_status(path)
    assert status["state"] == "idle"
    assert status["pid"] is None
    assert status["steps"] == {}


def test_write_status_then_read_status_round_trips(tmp_path):
    path = str(tmp_path / "status.json")
    sync_status.write_status(path, {"state": "running", "pid": 123, "steps": {}})
    result = sync_status.read_status(path)
    assert result["pid"] == 123


def test_write_status_creates_parent_directory(tmp_path):
    path = str(tmp_path / "nested" / "status.json")
    sync_status.write_status(path, {"state": "idle"})
    assert os_module.path.exists(path)


def test_read_status_self_heals_dead_pid_to_failed(tmp_path):
    path = str(tmp_path / "status.json")
    sync_status.write_status(path, {"state": "running", "pid": 999999, "steps": {"teams": "done"}})
    result = sync_status.read_status(path)
    assert result["state"] == "idle"
    assert result["last_result"] == "failed"
    assert result["error"] == "process died unexpectedly"
    # Self-heal must persist — a second read shouldn't re-detect "running".
    with open(path) as f:
        on_disk = json.load(f)
    assert on_disk["state"] == "idle"


def test_read_status_leaves_running_alone_if_pid_alive(tmp_path):
    path = str(tmp_path / "status.json")
    sync_status.write_status(path, {"state": "running", "pid": os_module.getpid(), "steps": {}})
    result = sync_status.read_status(path)
    assert result["state"] == "running"
```

- [ ] **Step 4: Run tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_sync_status.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.sync_status'` (all tests error/fail)

- [ ] **Step 5: Implement `src/sync_status.py` (status file read/write + self-heal)**

Create `src/sync_status.py`:

```python
import json
import os

STATUS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sync_status.json")


def _default_status():
    return {
        "state": "idle",
        "pid": None,
        "last_run": None,
        "last_result": None,
        "steps": {},
        "error": None,
    }


def is_process_alive(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def write_status(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def read_status(path):
    if not os.path.exists(path):
        return _default_status()
    with open(path) as f:
        data = json.load(f)
    if data.get("state") == "running" and not is_process_alive(data.get("pid")):
        data = dict(data)
        data["state"] = "idle"
        data["last_result"] = "failed"
        data["error"] = "process died unexpectedly"
        write_status(path, data)
    return data
```

- [ ] **Step 6: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_sync_status.py -v
```
Expected: all 7 tests `PASS`

- [ ] **Step 7: Commit**

```bash
git add requirements.txt tests/__init__.py tests/conftest.py tests/test_sync_status.py src/sync_status.py
git commit -m "feat: add JSON sync status file with self-healing dead-PID detection"
```

- [ ] **Step 8: Write failing tests for lock acquire/release and step updates**

Append to `tests/test_sync_status.py`:

```python
def test_try_acquire_lock_succeeds_when_idle(tmp_path):
    path = str(tmp_path / "status.json")
    acquired = sync_status.try_acquire_lock(path)
    assert acquired is True
    status = sync_status.read_status(path)
    assert status["state"] == "running"
    assert status["pid"] == os_module.getpid()


def test_try_acquire_lock_fails_when_already_running(tmp_path):
    path = str(tmp_path / "status.json")
    sync_status.write_status(path, {"state": "running", "pid": os_module.getpid(), "steps": {}})
    acquired = sync_status.try_acquire_lock(path)
    assert acquired is False


def test_try_acquire_lock_succeeds_when_previous_holder_is_dead(tmp_path):
    path = str(tmp_path / "status.json")
    sync_status.write_status(path, {"state": "running", "pid": 999999, "steps": {}})
    acquired = sync_status.try_acquire_lock(path)
    assert acquired is True


def test_update_step_sets_step_status(tmp_path):
    path = str(tmp_path / "status.json")
    sync_status.try_acquire_lock(path)
    sync_status.update_step(path, "teams", "done")
    sync_status.update_step(path, "standings", "running")
    status = sync_status.read_status(path)
    assert status["steps"]["teams"] == "done"
    assert status["steps"]["standings"] == "running"


def test_release_lock_writes_terminal_idle_state(tmp_path):
    path = str(tmp_path / "status.json")
    sync_status.try_acquire_lock(path)
    sync_status.release_lock(path, result="success", steps={"teams": "done"})
    status = sync_status.read_status(path)
    assert status["state"] == "idle"
    assert status["pid"] is None
    assert status["last_result"] == "success"
    assert status["steps"] == {"teams": "done"}
    assert status["last_run"] is not None
```

- [ ] **Step 9: Run tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_sync_status.py -v
```
Expected: `AttributeError: module 'src.sync_status' has no attribute 'try_acquire_lock'` (new tests fail; the 7 from Step 6 still pass)

- [ ] **Step 10: Implement lock acquire/release and step updates**

Append to `src/sync_status.py`:

```python
def try_acquire_lock(path):
    current = read_status(path)
    if current.get("state") == "running":
        return False
    write_status(path, {
        "state": "running",
        "pid": os.getpid(),
        "last_run": current.get("last_run"),
        "last_result": current.get("last_result"),
        "steps": {},
        "error": None,
    })
    return True


def update_step(path, step_name, step_status):
    current = read_status(path)
    current.setdefault("steps", {})[step_name] = step_status
    write_status(path, current)


def release_lock(path, result, steps, error=None):
    import time
    write_status(path, {
        "state": "idle",
        "pid": None,
        "last_run": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "last_result": result,
        "steps": steps,
        "error": error,
    })
```

- [ ] **Step 11: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_sync_status.py -v
```
Expected: all 12 tests `PASS`

- [ ] **Step 12: Commit**

```bash
git add src/sync_status.py tests/test_sync_status.py
git commit -m "feat: add PID-based lock acquire/release to sync status module"
```

---

## Task 2: `database.is_step_fresh()` Freshness-Window Helper

**Files:**
- Modify: `src/database.py`
- Create: `tests/test_database_sync.py`

**Interfaces:**
- Consumes: existing `database.get_sync_record`, `database.set_sync_record`, `sync_log` table
- Produces: `database.is_step_fresh(conn, key: str, within_hours: float) -> bool`

- [ ] **Step 1: Write failing tests**

Create `tests/test_database_sync.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import database


def test_is_step_fresh_false_when_never_synced(db_conn):
    assert database.is_step_fresh(db_conn, "teams:full", within_hours=24) is False


def test_is_step_fresh_true_when_synced_recently(db_conn):
    database.set_sync_record(db_conn, "teams:full")
    assert database.is_step_fresh(db_conn, "teams:full", within_hours=24) is True


def test_is_step_fresh_false_when_synced_outside_window(db_conn):
    db_conn.execute(
        "INSERT INTO sync_log (key, synced_at) VALUES (?, datetime('now', '-2 hours'))",
        ("standings:full",),
    )
    db_conn.commit()
    assert database.is_step_fresh(db_conn, "standings:full", within_hours=1) is False


def test_is_step_fresh_true_at_boundary_edge(db_conn):
    db_conn.execute(
        "INSERT INTO sync_log (key, synced_at) VALUES (?, datetime('now', '-30 minutes'))",
        ("rosters:full",),
    )
    db_conn.commit()
    assert database.is_step_fresh(db_conn, "rosters:full", within_hours=1) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_database_sync.py -v
```
Expected: `AttributeError: module 'src.database' has no attribute 'is_step_fresh'`

- [ ] **Step 3: Implement `is_step_fresh`**

In `src/database.py`, add directly after `set_sync_record` (after line 233):

```python
def is_step_fresh(conn, key, within_hours):
    """True if the given sync_log key was recorded within the last within_hours hours."""
    row = conn.execute(
        "SELECT (julianday('now') - julianday(synced_at)) * 24 AS hours_ago "
        "FROM sync_log WHERE key = ?", (key,)
    ).fetchone()
    if row is None or row["hours_ago"] is None:
        return False
    return row["hours_ago"] < within_hours
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_database_sync.py -v
```
Expected: all 4 tests `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/database.py tests/test_database_sync.py
git commit -m "feat: add is_step_fresh sync_log freshness-window helper"
```

---

## Task 3: Rosters Diff-Before-Write (Null-Guarded)

**Files:**
- Modify: `src/database.py`
- Modify: `etl/load_rosters.py`
- Modify: `tests/test_database_sync.py`

**Interfaces:**
- Consumes: existing `database.upsert_player(conn, p: dict)` (unchanged, still called internally)
- Produces: `database.diff_upsert_player(conn, new_data: dict) -> bool` — returns `True` if a write occurred, `False` if the row was already up to date. Never lets a `None` value in `new_data` overwrite a non-`None` existing column value.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_database_sync.py`:

```python
def _base_player(player_id=1, **overrides):
    p = {
        "player_id": player_id,
        "first_name": "Connor",
        "last_name": "McDavid",
        "position_code": "C",
        "sweater_number": 97,
        "shoots_catches": "L",
        "height_inches": 73,
        "weight_pounds": 194,
        "birth_date": "1997-01-13",
        "birth_country": "CAN",
        "current_team_id": 22,
        "birth_city": "Richmond Hill",
        "birth_state_province": "ON",
        "headshot_url": "http://example.com/97.png",
    }
    p.update(overrides)
    return p


def test_diff_upsert_player_inserts_new_player(db_conn):
    changed = database.diff_upsert_player(db_conn, _base_player())
    assert changed is True
    row = db_conn.execute("SELECT * FROM players WHERE player_id = 1").fetchone()
    assert row["first_name"] == "Connor"
    assert row["height_inches"] == 73


def test_diff_upsert_player_no_write_when_identical(db_conn):
    database.diff_upsert_player(db_conn, _base_player())
    changed = database.diff_upsert_player(db_conn, _base_player())
    assert changed is False


def test_diff_upsert_player_writes_when_value_changed(db_conn):
    database.diff_upsert_player(db_conn, _base_player())
    changed = database.diff_upsert_player(db_conn, _base_player(current_team_id=10))
    assert changed is True
    row = db_conn.execute("SELECT current_team_id FROM players WHERE player_id = 1").fetchone()
    assert row["current_team_id"] == 10


def test_diff_upsert_player_null_api_value_does_not_overwrite_existing(db_conn):
    database.diff_upsert_player(db_conn, _base_player())
    changed = database.diff_upsert_player(db_conn, _base_player(height_inches=None, weight_pounds=None))
    assert changed is False
    row = db_conn.execute("SELECT height_inches, weight_pounds FROM players WHERE player_id = 1").fetchone()
    assert row["height_inches"] == 73
    assert row["weight_pounds"] == 194


def test_diff_upsert_player_null_guard_combined_with_real_change(db_conn):
    database.diff_upsert_player(db_conn, _base_player())
    changed = database.diff_upsert_player(
        db_conn, _base_player(height_inches=None, current_team_id=10)
    )
    assert changed is True
    row = db_conn.execute("SELECT height_inches, current_team_id FROM players WHERE player_id = 1").fetchone()
    assert row["height_inches"] == 73     # preserved, API sent null
    assert row["current_team_id"] == 10   # updated, API sent a real change
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_database_sync.py -v
```
Expected: `AttributeError: module 'src.database' has no attribute 'diff_upsert_player'`

- [ ] **Step 3: Implement `diff_upsert_player`**

In `src/database.py`, add directly after `upsert_player` (after line 280):

```python
_PLAYER_DIFF_FIELDS = [
    "first_name", "last_name", "position_code", "sweater_number", "shoots_catches",
    "height_inches", "weight_pounds", "birth_date", "birth_country", "current_team_id",
    "birth_city", "birth_state_province", "headshot_url",
]


def diff_upsert_player(conn, new_data):
    """Upsert roster-sourced player data, but only write columns that actually
    changed, and never let a null API value overwrite a non-null DB value.
    Returns True if a write occurred, False if the row was already current."""
    current = conn.execute(
        "SELECT * FROM players WHERE player_id = ?", (new_data["player_id"],)
    ).fetchone()

    if current is None:
        upsert_player(conn, new_data)
        return True

    merged = {"player_id": new_data["player_id"]}
    changed = False
    for field in _PLAYER_DIFF_FIELDS:
        new_val = new_data.get(field)
        cur_val = current[field]
        effective = new_val if new_val is not None else cur_val
        merged[field] = effective
        if effective != cur_val:
            changed = True

    if not changed:
        return False

    upsert_player(conn, merged)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_database_sync.py -v
```
Expected: all 9 tests `PASS`

- [ ] **Step 5: Wire `load_rosters.py` to use `diff_upsert_player`**

In `etl/load_rosters.py`, change line 33 from:
```python
            database.upsert_player(conn, player.__dict__)
```
to:
```python
            database.diff_upsert_player(conn, player.__dict__)
```

- [ ] **Step 6: Manually verify rosters still load correctly**

Run:
```bash
.venv/bin/python -c "
from src.database import get_connection
from etl import load_rosters
conn = get_connection()
load_rosters.run(conn)
conn.close()
"
```
Expected: same per-team output as before (`  <ABBREV>: N players`), no errors, script completes.

- [ ] **Step 7: Commit**

```bash
git add src/database.py etl/load_rosters.py tests/test_database_sync.py
git commit -m "feat: add diff-before-write with null-guard to roster upserts"
```

---

## Task 4: Standings Diff-Before-Replace

**Files:**
- Modify: `src/database.py`
- Modify: `etl/load_standings.py`
- Modify: `tests/test_database_sync.py`

**Interfaces:**
- Consumes: existing `database.insert_standings_snapshot(conn, s: dict)` (unchanged, called internally for first-seen rows)
- Produces: `database.update_standings_snapshot(conn, s: dict) -> None` — `UPDATE` keyed on `(snapshot_date, team_id)`
- Produces: `database.diff_upsert_standings_snapshot(conn, s: dict) -> bool` — `True` if a write occurred

- [ ] **Step 1: Write failing tests**

Append to `tests/test_database_sync.py`:

```python
def _base_snapshot(team_id=1, **overrides):
    s = {
        "snapshot_date": "2026-07-02",
        "season_id": "20252026",
        "team_id": team_id,
        "games_played": 10,
        "wins": 6,
        "losses": 3,
        "ot_losses": 1,
        "points": 13,
        "regulation_wins": 5,
        "goal_for": 35,
        "goal_against": 28,
        "point_pct": 0.65,
        "streak_code": "W",
        "streak_count": 2,
    }
    s.update(overrides)
    return s


def test_diff_upsert_standings_inserts_first_snapshot_of_day(db_conn):
    changed = database.diff_upsert_standings_snapshot(db_conn, _base_snapshot())
    assert changed is True
    row = db_conn.execute(
        "SELECT * FROM standings WHERE snapshot_date = '2026-07-02' AND team_id = 1"
    ).fetchone()
    assert row["wins"] == 6


def test_diff_upsert_standings_no_write_when_identical(db_conn):
    database.diff_upsert_standings_snapshot(db_conn, _base_snapshot())
    changed = database.diff_upsert_standings_snapshot(db_conn, _base_snapshot())
    assert changed is False


def test_diff_upsert_standings_updates_same_day_row_when_changed(db_conn):
    database.diff_upsert_standings_snapshot(db_conn, _base_snapshot())
    changed = database.diff_upsert_standings_snapshot(
        db_conn, _base_snapshot(wins=7, points=15, games_played=11)
    )
    assert changed is True
    rows = db_conn.execute(
        "SELECT * FROM standings WHERE snapshot_date = '2026-07-02' AND team_id = 1"
    ).fetchall()
    assert len(rows) == 1  # updated in place, not a second row
    assert rows[0]["wins"] == 7
    assert rows[0]["points"] == 15


def test_diff_upsert_standings_keeps_one_row_per_day_across_days(db_conn):
    database.diff_upsert_standings_snapshot(db_conn, _base_snapshot(snapshot_date="2026-07-01"))
    database.diff_upsert_standings_snapshot(db_conn, _base_snapshot(snapshot_date="2026-07-02"))
    rows = db_conn.execute("SELECT * FROM standings WHERE team_id = 1").fetchall()
    assert len(rows) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_database_sync.py -v
```
Expected: `AttributeError: module 'src.database' has no attribute 'diff_upsert_standings_snapshot'`

- [ ] **Step 3: Implement `update_standings_snapshot` and `diff_upsert_standings_snapshot`**

In `src/database.py`, add directly after `insert_standings_snapshot` (after line 413):

```python
_STANDINGS_DIFF_FIELDS = [
    "games_played", "wins", "losses", "ot_losses", "points",
    "regulation_wins", "goal_for", "goal_against", "point_pct",
    "streak_code", "streak_count",
]


def update_standings_snapshot(conn, s):
    conn.execute("""
        UPDATE standings SET
            games_played = ?, wins = ?, losses = ?, ot_losses = ?, points = ?,
            regulation_wins = ?, goal_for = ?, goal_against = ?, point_pct = ?,
            streak_code = ?, streak_count = ?
        WHERE snapshot_date = ? AND team_id = ?
    """, (
        s["games_played"], s["wins"], s["losses"], s["ot_losses"], s["points"],
        s["regulation_wins"], s["goal_for"], s["goal_against"], s["point_pct"],
        s["streak_code"], s["streak_count"],
        s["snapshot_date"], s["team_id"],
    ))


def diff_upsert_standings_snapshot(conn, s):
    """Insert today's row if it doesn't exist yet; otherwise update it in place
    only if something actually changed. Returns True if a write occurred."""
    current = conn.execute(
        "SELECT * FROM standings WHERE snapshot_date = ? AND team_id = ?",
        (s["snapshot_date"], s["team_id"]),
    ).fetchone()

    if current is None:
        insert_standings_snapshot(conn, s)
        return True

    changed = any(s.get(f) != current[f] for f in _STANDINGS_DIFF_FIELDS)
    if not changed:
        return False

    update_standings_snapshot(conn, s)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_database_sync.py -v
```
Expected: all 13 tests `PASS`

- [ ] **Step 5: Wire `load_standings.py` to use `diff_upsert_standings_snapshot`**

In `etl/load_standings.py`, change line 55 from:
```python
        database.insert_standings_snapshot(conn, snapshot.__dict__)
```
to:
```python
        database.diff_upsert_standings_snapshot(conn, snapshot.__dict__)
```

- [ ] **Step 6: Manually verify standings still load correctly**

Run:
```bash
.venv/bin/python -c "
from src.database import get_connection
from etl import load_standings
conn = get_connection()
load_standings.run(conn)
conn.close()
"
```
Expected: `  N standings rows loaded for <today>.` with no errors.

- [ ] **Step 7: Commit**

```bash
git add src/database.py etl/load_standings.py tests/test_database_sync.py
git commit -m "feat: add diff-before-replace to standings snapshots"
```

---

## Task 5: `etl/pipeline.py` — Unified Orchestrator

**Files:**
- Create: `etl/pipeline.py`
- Create: `tests/test_pipeline.py`
- Delete: `scripts/run_all_etl.py`
- Delete: `scripts/sync.py`

**Interfaces:**
- Consumes: `sync_status.try_acquire_lock`, `sync_status.update_step`, `sync_status.release_lock`, `sync_status.STATUS_PATH` (Task 1); `database.is_step_fresh`, `database.set_sync_record`, `database.get_connection` (Task 2, existing)
- Produces: `pipeline.run(db_path: str | None = None, status_path: str | None = None) -> None`
- Produces: `pipeline.STEPS` — list of `(key, label, module, window_hours)` tuples; each `module` exposes `run(conn)`. `window_hours=None` means the step always runs (no pipeline-level freshness gate — currently only `enrichment`, which already self-gates internally per-player).

**Freshness key scheme used by this task** (fixed per-step keys, distinct from `load_season_stats.py`'s existing per-historical-season `season_stats:<season_id>` keys, which are untouched and still mean "never re-fetch once loaded"):

| Step key | sync_log key | Window |
|---|---|---|
| `teams` | `teams:full` | 720 hours (30 days) |
| `standings` | `standings:full` | 6 hours |
| `rosters` | `rosters:full` | 24 hours |
| `schedule` | `schedule:full` | 6 hours |
| `boxscores` | `boxscores:full` | 6 hours |
| `season_stats` | `season_stats:full` | 6 hours |
| `enrichment` | *(none — always runs)* | n/a |

- [ ] **Step 1: Write failing tests using fake step modules**

Create `tests/test_pipeline.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import database, sync_status
from etl import pipeline


class _FakeModule:
    """Stand-in for an etl.load_* module — records whether run() was called."""
    def __init__(self, raises=False):
        self.called = False
        self.raises = raises

    def run(self, conn):
        self.called = True
        if self.raises:
            raise RuntimeError("boom")


def test_pipeline_runs_all_steps_when_nothing_synced_yet(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    status_path = str(tmp_path / "status.json")
    conn = database.get_connection(db_path)
    database.create_all_tables(conn)
    conn.close()

    fake_a = _FakeModule()
    fake_b = _FakeModule()
    monkeypatch.setattr(pipeline, "STEPS", [
        ("stepa", "Step A", fake_a, 24),
        ("stepb", "Step B", fake_b, None),
    ])

    pipeline.run(db_path=db_path, status_path=status_path)

    assert fake_a.called is True
    assert fake_b.called is True
    status = sync_status.read_status(status_path)
    assert status["state"] == "idle"
    assert status["last_result"] == "success"
    assert status["steps"] == {"stepa": "done", "stepb": "done"}


def test_pipeline_skips_step_within_freshness_window(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    status_path = str(tmp_path / "status.json")
    conn = database.get_connection(db_path)
    database.create_all_tables(conn)
    database.set_sync_record(conn, "stepa:full")
    conn.close()

    fake_a = _FakeModule()
    monkeypatch.setattr(pipeline, "STEPS", [("stepa", "Step A", fake_a, 24)])

    pipeline.run(db_path=db_path, status_path=status_path)

    assert fake_a.called is False
    status = sync_status.read_status(status_path)
    assert status["steps"] == {"stepa": "skipped"}


def test_pipeline_logs_and_continues_after_step_failure(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    status_path = str(tmp_path / "status.json")
    conn = database.get_connection(db_path)
    database.create_all_tables(conn)
    conn.close()

    fake_fail = _FakeModule(raises=True)
    fake_ok = _FakeModule()
    monkeypatch.setattr(pipeline, "STEPS", [
        ("failstep", "Fail Step", fake_fail, None),
        ("okstep", "OK Step", fake_ok, None),
    ])

    pipeline.run(db_path=db_path, status_path=status_path)

    assert fake_ok.called is True  # ran despite the earlier failure
    status = sync_status.read_status(status_path)
    assert status["last_result"] == "partial_failure"
    assert status["steps"]["failstep"] == "failed"
    assert status["steps"]["okstep"] == "done"


def test_pipeline_refuses_to_run_when_already_locked(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    status_path = str(tmp_path / "status.json")
    conn = database.get_connection(db_path)
    database.create_all_tables(conn)
    conn.close()

    sync_status.try_acquire_lock(status_path)  # simulate another sync in progress

    fake_a = _FakeModule()
    monkeypatch.setattr(pipeline, "STEPS", [("stepa", "Step A", fake_a, None)])

    pipeline.run(db_path=db_path, status_path=status_path)

    assert fake_a.called is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_pipeline.py -v
```
Expected: `ModuleNotFoundError: No module named 'etl.pipeline'`

- [ ] **Step 3: Implement `etl/pipeline.py`**

Create `etl/pipeline.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import database, sync_status
from etl import (
    load_teams, load_standings, load_rosters, load_schedule, load_boxscores,
    load_season_stats, enrich_players,
)

STEPS = [
    ("teams", "Teams", load_teams, 24 * 30),
    ("standings", "Standings", load_standings, 6),
    ("rosters", "Rosters / Players", load_rosters, 24),
    ("schedule", "Schedule / Games", load_schedule, 6),
    ("boxscores", "Boxscores / Player Stats", load_boxscores, 6),
    ("season_stats", "Season Stats", load_season_stats, 6),
    ("enrichment", "Player Enrichment", enrich_players, None),
]


def run(db_path=None, status_path=None):
    status_path = status_path or sync_status.STATUS_PATH

    if not sync_status.try_acquire_lock(status_path):
        print("Sync already running, exiting.")
        return

    conn = database.get_connection(db_path) if db_path else database.get_connection()
    steps_result = {}
    overall_ok = True

    try:
        for key, label, module, window_hours in STEPS:
            sync_key = f"{key}:full"

            if window_hours is not None and database.is_step_fresh(conn, sync_key, window_hours):
                print(f"\n=== {label}: skipped (fresh) ===")
                steps_result[key] = "skipped"
                sync_status.update_step(status_path, key, "skipped")
                continue

            print(f"\n=== {label} ===")
            sync_status.update_step(status_path, key, "running")
            try:
                module.run(conn)
                database.set_sync_record(conn, sync_key)
                steps_result[key] = "done"
                sync_status.update_step(status_path, key, "done")
            except Exception as e:
                print(f"  ERROR in {label}: {e}")
                steps_result[key] = "failed"
                sync_status.update_step(status_path, key, "failed")
                overall_ok = False
    finally:
        conn.close()
        sync_status.release_lock(
            status_path,
            result="success" if overall_ok else "partial_failure",
            steps=steps_result,
        )

    print("\nPipeline complete.")


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_pipeline.py -v
```
Expected: all 4 tests `PASS`

- [ ] **Step 5: Remove the superseded orchestrator scripts**

```bash
git rm scripts/run_all_etl.py scripts/sync.py
```

- [ ] **Step 6: Manually verify the pipeline runs end-to-end against the real DB**

Run:
```bash
.venv/bin/python -m etl.pipeline
```
Expected: all 7 steps print their section header; steps that already have a fresh `sync_log` entry from earlier in this session print `skipped (fresh)`; ends with `Pipeline complete.`. Then confirm the status file:
```bash
cat data/sync_status.json
```
Expected: `"state": "idle"`, `"last_result": "success"` (or `"partial_failure"` if the NHL API had a transient error), and a `"steps"` entry for all 7 keys.

- [ ] **Step 7: Commit**

```bash
git add etl/pipeline.py tests/test_pipeline.py
git commit -m "feat: add unified etl.pipeline orchestrator, remove run_all_etl.py and sync.py"
```

---

## Task 6: Flask Sync-Trigger and Status Endpoints

**Files:**
- Modify: `app.py`
- Create: `tests/test_app_sync_endpoints.py`

**Interfaces:**
- Consumes: `sync_status.read_status`, `sync_status.STATUS_PATH` (Task 1)
- Produces: `POST /api/sync` — `202`/`200` `{"started": true}` if launched, `409` `{"error": "sync already running"}` if a live pipeline process already holds the lock
- Produces: `GET /api/sync/status` — returns the JSON status file contents directly

Note on lock ownership: the Flask endpoint does **not** call `try_acquire_lock` itself — that would record the *Flask worker's* PID as the lock holder, not the pipeline subprocess's. It only *reads* status to decide whether to spawn a new subprocess; the spawned `etl.pipeline` process acquires the lock itself, under its own PID, immediately after starting.

- [ ] **Step 1: Write failing tests with mocked subprocess**

Create `tests/test_app_sync_endpoints.py`:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import os as os_module
import pytest
import app as app_module
from src import sync_status


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_post_sync_starts_pipeline_when_idle(client, tmp_path, monkeypatch):
    status_path = str(tmp_path / "status.json")
    monkeypatch.setattr(sync_status, "STATUS_PATH", status_path)

    captured = {}
    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()
    monkeypatch.setattr(app_module.subprocess, "Popen", fake_popen)

    resp = client.post("/api/sync")

    assert resp.status_code == 200
    assert resp.get_json() == {"started": True}
    assert captured["args"][-2:] == ["-m", "etl.pipeline"]


def test_post_sync_refuses_when_already_running(client, tmp_path, monkeypatch):
    status_path = str(tmp_path / "status.json")
    monkeypatch.setattr(sync_status, "STATUS_PATH", status_path)
    sync_status.write_status(status_path, {"state": "running", "pid": os_module.getpid(), "steps": {}})

    called = {"popen": False}
    def fake_popen(args, **kwargs):
        called["popen"] = True
        return object()
    monkeypatch.setattr(app_module.subprocess, "Popen", fake_popen)

    resp = client.post("/api/sync")

    assert resp.status_code == 409
    assert resp.get_json() == {"error": "sync already running"}
    assert called["popen"] is False


def test_get_sync_status_returns_file_contents(client, tmp_path, monkeypatch):
    status_path = str(tmp_path / "status.json")
    monkeypatch.setattr(sync_status, "STATUS_PATH", status_path)
    sync_status.write_status(status_path, {"state": "idle", "last_result": "success", "steps": {"teams": "done"}})

    resp = client.get("/api/sync/status")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["last_result"] == "success"
    assert body["steps"] == {"teams": "done"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/python -m pytest tests/test_app_sync_endpoints.py -v
```
Expected: `404 NOT FOUND` assertion failures (routes don't exist yet) / `AttributeError: module 'app' has no attribute 'subprocess'`

- [ ] **Step 3: Implement the endpoints**

In `app.py`, add to the imports at the top (after line 6):

```python
import subprocess
from src import sync_status
```

Add after the `_height_str` function (after line 25), before the `@app.route("/")` block:

```python
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")


@app.route("/api/sync", methods=["POST"])
def api_sync_trigger():
    status = sync_status.read_status(sync_status.STATUS_PATH)
    if status.get("state") == "running":
        return jsonify({"error": "sync already running"}), 409
    subprocess.Popen([VENV_PYTHON, "-m", "etl.pipeline"], cwd=PROJECT_ROOT)
    return jsonify({"started": True})


@app.route("/api/sync/status")
def api_sync_status():
    return jsonify(sync_status.read_status(sync_status.STATUS_PATH))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/python -m pytest tests/test_app_sync_endpoints.py -v
```
Expected: all 3 tests `PASS`

- [ ] **Step 5: Run the full test suite to confirm nothing else broke**

Run:
```bash
.venv/bin/python -m pytest -v
```
Expected: all tests across `tests/test_sync_status.py`, `tests/test_database_sync.py`, `tests/test_pipeline.py`, `tests/test_app_sync_endpoints.py` `PASS`

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_sync_endpoints.py
git commit -m "feat: add /api/sync trigger and /api/sync/status endpoints"
```

---

## Task 7: Sync Button + Live Status UI

**Files:**
- Modify: `templates/index.html`

**Interfaces:**
- Consumes: `POST /api/sync`, `GET /api/sync/status` (Task 6)

- [ ] **Step 1: Add the Sync button and status line to the header**

In `templates/index.html`, replace the header block (lines 190–215):

```html
<header>
  <h1>🏒 NHL Players</h1>
  <div class="controls">
    <label for="team-filter">Team</label>
    <select id="team-filter">
      <option value="">All Teams</option>
    </select>

    <label for="season-filter">Season</label>
    <select id="season-filter">
      <option value="all">All Seasons (Career)</option>
      <option value="20252026" selected>2025–26</option>
      <option value="20242025">2024–25</option>
      <option value="20232024">2023–24</option>
      <option value="20222023">2022–23</option>
      <option value="20212022">2021–22</option>
      <option value="20202021">2020–21</option>
    </select>

    <div class="tab-group">
      <button class="tab-btn active" data-tab="bio">Bio</button>
      <button class="tab-btn" data-tab="stats">Stats</button>
    </div>

    <button id="sync-btn">Sync</button>
  </div>
  <span class="count" id="count-label"></span>
  <div id="sync-status-line" class="sync-status-line"></div>
</header>
```

- [ ] **Step 2: Add matching CSS for the button and status line**

In `templates/index.html`, add directly after the `.count { ... }` rule (after line 91):

```css
    #sync-btn {
      background: #21262d;
      color: #c9d1d9;
      border: 1px solid #30363d;
      border-radius: 6px;
      padding: 6px 14px;
      font-size: 13px;
      font-family: inherit;
      cursor: pointer;
    }
    #sync-btn:hover { background: #1c2129; color: #e6edf3; }
    #sync-btn:disabled { opacity: 0.5; cursor: default; }

    .sync-status-line {
      padding: 0 24px;
      font-size: 12px;
      color: #8b949e;
      min-height: 18px;
    }
    .sync-status-line .step-done    { color: #3fb950; }
    .sync-status-line .step-running { color: #58a6ff; }
    .sync-status-line .step-failed  { color: #f85149; }
    .sync-status-line .step-skipped { color: #8b949e; }
```

- [ ] **Step 3: Add the polling JS**

In `templates/index.html`, add at the end of the `<script>` block, directly before the closing `</script>` tag (before line with `</script>` near the end of the file):

```javascript
  // ─── Sync button + live status polling ──────────────────────────────────────
  const STEP_LABELS = {
    teams: "Teams", standings: "Standings", rosters: "Rosters", schedule: "Schedule",
    boxscores: "Boxscores", season_stats: "Season Stats", enrichment: "Enrichment",
  };

  let syncPollHandle = null;

  function renderSyncStatus(status) {
    const line = document.getElementById("sync-status-line");
    const btn = document.getElementById("sync-btn");

    if (status.state === "running") {
      btn.disabled = true;
      const parts = Object.entries(status.steps || {}).map(([key, val]) => {
        const icon = { done: "✓", running: "⟳", failed: "✗", skipped: "·" }[val] || "·";
        return `<span class="step-${val}">${icon} ${STEP_LABELS[key] || key}</span>`;
      });
      line.innerHTML = parts.join(" · ") || "Starting…";
    } else {
      btn.disabled = false;
      if (status.last_run) {
        const when = new Date(status.last_run).toLocaleString();
        const resultText = status.last_result === "success" ? "synced" : `synced (${status.last_result})`;
        line.textContent = `Last ${resultText}: ${when}`;
      } else {
        line.textContent = "";
      }
    }
  }

  function pollSyncStatus() {
    fetch("/api/sync/status")
      .then(r => r.json())
      .then(status => {
        renderSyncStatus(status);
        if (status.state === "running") {
          syncPollHandle = setTimeout(pollSyncStatus, 2000);
        } else if (syncPollHandle !== null) {
          syncPollHandle = null;
          loadStats(activeSeason);
          fetch("/api/players").then(r => r.json()).then(data => { bioData = data; renderTable(); });
        }
      });
  }

  document.getElementById("sync-btn").addEventListener("click", () => {
    fetch("/api/sync", { method: "POST" }).then(r => {
      if (r.status === 409) {
        pollSyncStatus();
        return;
      }
      pollSyncStatus();
    });
  });

  pollSyncStatus();
```

- [ ] **Step 4: Manually verify in the browser**

Run:
```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
.venv/bin/python app.py
```
Open `http://127.0.0.1:5000/` and:
1. Confirm the page loads with a "Sync" button next to the Bio/Stats toggle and no status text (assuming no prior sync ran) or a "Last synced: ..." line if one has.
2. Click "Sync". Confirm the button disables and the status line shows live step progress (`✓ Teams · ⟳ Standings · ...`).
3. Wait for it to finish (steps will mostly show `skipped (fresh)` if you ran the pipeline manually in Task 5's Step 6 recently). Confirm the button re-enables and the line switches to "Last synced: ...".
4. Click "Sync" again immediately from a second browser tab while the first is still running (if timing allows) — or re-click quickly — and confirm no duplicate/garbled status rendering occurs.

Stop the server with `Ctrl+C` when done.

- [ ] **Step 5: Commit**

```bash
git add templates/index.html
git commit -m "feat: add Sync button with live per-step status polling to UI"
```

---

## Task 8: `launchd` Weekly Schedule

**Files:**
- Create: `launchd/com.paulmckay.nhlstats.sync.plist`

- [ ] **Step 1: Create the plist**

Create `launchd/com.paulmckay.nhlstats.sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.paulmckay.nhlstats.sync</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/paulmckay/Desktop/NHL Stats Project/.venv/bin/python</string>
        <string>-m</string>
        <string>etl.pipeline</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/paulmckay/Desktop/NHL Stats Project</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/paulmckay/Desktop/NHL Stats Project/data/sync.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/paulmckay/Desktop/NHL Stats Project/data/sync.log</string>
</dict>
</plist>
```

`Weekday: 0` is Sunday, `Hour: 8` is 8am local time — adjust if a different day/time is preferred.

- [ ] **Step 2: Validate the plist syntax**

Run:
```bash
plutil -lint "/Users/paulmckay/Desktop/NHL Stats Project/launchd/com.paulmckay.nhlstats.sync.plist"
```
Expected: `... OK`

- [ ] **Step 3: Commit the plist to the repo**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add launchd/com.paulmckay.nhlstats.sync.plist
git commit -m "feat: add launchd plist for weekly sync schedule"
```

- [ ] **Step 4 (manual — not run by the implementer): Install and load the job**

This step activates a persistent, always-on system schedule outside the git repo. Present these exact commands to the user and let them run it themselves rather than executing it as part of implementation:

```bash
cp "/Users/paulmckay/Desktop/NHL Stats Project/launchd/com.paulmckay.nhlstats.sync.plist" ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.paulmckay.nhlstats.sync.plist
```

To verify it's loaded: `launchctl list | grep nhlstats`
To remove it later: `launchctl unload ~/Library/LaunchAgents/com.paulmckay.nhlstats.sync.plist && rm ~/Library/LaunchAgents/com.paulmckay.nhlstats.sync.plist`

---

## Final Verification

- [ ] Run the full test suite one more time: `.venv/bin/python -m pytest -v` — all tests pass.
- [ ] Confirm `data/` still holds `nhl_stats.db` and now also `sync_status.json` (and, once the plist is loaded, `sync.log`) — none of these should be tracked by git (`data/` is already in `.gitignore`).
- [ ] Confirm `scripts/run_all_etl.py` and `scripts/sync.py` no longer exist, and their prior functionality is fully covered by `python -m etl.pipeline`.
