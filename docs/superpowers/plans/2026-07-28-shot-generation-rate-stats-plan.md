# Shot Generation & Playmaking Rate Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add six new 5v5 per-60 rate stats (Shots, Chances, Rebounds Created, Deflections, Points, Primary Points) plus z-score normalization to the existing advanced-stats pipeline, API, and player profile UI.

**Architecture:** Extends the existing `player_game_advanced_stats` → `player_season_advanced_stats` → percentile-computation chain (`etl/advanced_stats/sweep.py` + `etl/compute_advanced_stats.py` + `src/database.py`) with five new raw-count columns and a new `player_rate_zscores` table, computed in the same single-pass sweep with no second pass over `game_events`. Rates are computed at API-response time (`app.py`), not stored. Frontend surfaces them as a new section in `PlayerProfilePanel` plus one teaser column in `PlayerTable`.

**Tech Stack:** Python 3 / Flask / sqlite3 (backend, ETL), React 19 + TypeScript + Vite + Tailwind + shadcn/ui + Recharts (frontend), pytest (backend tests), Vitest + Testing Library (frontend tests).

## Global Constraints

- Rebound window: a shot attempt within **3 seconds (inclusive, `<= 3`)** of a prior shot attempt by the **same team** (no same-player exclusion) credits the **original** shooter, not the current one. The tracking pointer advances on every shot attempt regardless of whether it counted as a rebound, so any single shot can create at most one credited rebound.
- Deflection flag: `shot_type IN ('deflected', 'tip-in')` — confirmed live values, no other shot_type counts.
- Points: goals + assist1 + assist2 (all three credited). Primary Points (existing column, unchanged): goals + assist1 only.
- Individual credit (`icf`, `ihdcf`, `deflections`) goes only to `shooting_player_id`, never to the whole on-ice unit — distinct from existing `cf`/`hdcf`.
- Z-scores: `ZSCORE_MIN_POPULATION = 20` qualifying players per `(season_id, position_group)`, regular season only (`game_type = 2`), 5v5 only, same `PERCENTILE_MIN_GP = 10` floor as the existing percentile system. Below the population floor: no row written (all six fields null for that group).
- Rounding: rates and z-scores both round to 2 decimal places.
- All new API/UI fields apply to the `5v5` strength state only — never shown/computed for `5v4`/`4v5`.
- Full spec: `docs/superpowers/specs/2026-07-27-shot-generation-rate-stats-design.md`.

---

## File Structure

**Backend:**
- Modify `src/database.py` — schema (5 new columns × 3 advanced-stats tables, new `player_rate_zscores` table), migrations list, two upsert function changes.
- Modify `etl/advanced_stats/sweep.py` — individual shot credit, rebound detection, points computation, all inside the existing shot-attempt/goal loops.
- Modify `etl/compute_advanced_stats.py` — select `shot_type`/`assist2_player_id`, extend season aggregation, new `compute_zscores()`.
- Modify `app.py` — extend `_fetch_player_advanced()` and the `/api/players/stats` season branch.
- Test: `tests/test_sweep.py`, `tests/test_compute_advanced_stats.py`, `tests/test_app_advanced_stats.py` (all extended, no new files).

**Frontend:**
- Modify `frontend/src/lib/types.ts`, `frontend/src/components/PlayerProfilePanel.tsx`, `frontend/src/components/PlayerTable.tsx`.
- Test: `frontend/src/components/PlayerProfilePanel.test.tsx`, `frontend/src/components/PlayerTable.test.tsx` (extended).

**Docs/Ops:**
- Create `docs/api/advanced-stats.md`.
- Modify `README.md` (new one-time backfill section).

---

### Task 1: Schema — new columns, new table, upsert functions

**Files:**
- Modify: `src/database.py`
- Test: `tests/test_compute_advanced_stats.py` (new schema-smoke test)

**Interfaces:**
- Produces: `database.upsert_player_rate_zscores(conn, r) -> None` where `r` has keys `season_id, player_id, position_group, shots_per60_z, chances_per60_z, rebounds_created_per60_z, deflections_per60_z, points_per60_z, primary_points_per60_z`. `database.upsert_player_game_advanced_stats(conn, r)` now requires `r` to additionally have `icf, ihdcf, rebounds_created, deflections, points`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compute_advanced_stats.py`:

```python
def test_schema_has_new_rate_stat_columns_and_zscore_table(conn):
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(player_game_advanced_stats)")}
    assert {"icf", "ihdcf", "rebounds_created", "deflections", "points"} <= cols

    season_cols = {row["name"] for row in conn.execute("PRAGMA table_info(player_season_advanced_stats)")}
    assert {"icf", "ihdcf", "rebounds_created", "deflections", "points"} <= season_cols

    career_cols = {row["name"] for row in conn.execute("PRAGMA table_info(player_career_advanced_stats)")}
    assert {"rs_icf", "rs_ihdcf", "rs_rebounds_created", "rs_deflections", "rs_points",
            "po_icf", "po_ihdcf", "po_rebounds_created", "po_deflections", "po_points"} <= career_cols

    zscore_cols = {row["name"] for row in conn.execute("PRAGMA table_info(player_rate_zscores)")}
    assert {"season_id", "player_id", "position_group", "shots_per60_z", "chances_per60_z",
            "rebounds_created_per60_z", "deflections_per60_z", "points_per60_z",
            "primary_points_per60_z"} <= zscore_cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compute_advanced_stats.py::test_schema_has_new_rate_stat_columns_and_zscore_table -v`
Expected: FAIL — missing columns/table.

- [ ] **Step 3: Extend the three existing `CREATE_*_ADVANCED_STATS` DDL strings**

In `src/database.py`, inside `CREATE_PLAYER_GAME_ADVANCED_STATS` (currently ends `primary_points INTEGER DEFAULT 0,\n    toi_seconds    INTEGER DEFAULT 0,`), insert after the `toi_seconds` line and before `created_at`:

```sql
    icf             INTEGER DEFAULT 0,  -- individual Corsi For (own shot attempts, not on-ice)
    ihdcf           INTEGER DEFAULT 0,  -- individual High-Danger Corsi For
    rebounds_created INTEGER DEFAULT 0, -- credited to original shooter, see sweep.py
    deflections     INTEGER DEFAULT 0,  -- shot_type IN ('deflected', 'tip-in')
    points          INTEGER DEFAULT 0,  -- goals + assist1 + assist2 (primary_points excludes assist2)
```

Same five lines (identical names) inserted the same way into `CREATE_PLAYER_SEASON_ADVANCED_STATS` (after its `toi_seconds`/before `gp`).

In `CREATE_PLAYER_CAREER_ADVANCED_STATS`, insert after `rs_toi_seconds INTEGER DEFAULT 0,` and before `po_cf`:

```sql
    rs_icf              INTEGER DEFAULT 0,
    rs_ihdcf            INTEGER DEFAULT 0,
    rs_rebounds_created INTEGER DEFAULT 0,
    rs_deflections      INTEGER DEFAULT 0,
    rs_points           INTEGER DEFAULT 0,
```

and after `po_toi_seconds INTEGER DEFAULT 0,` and before `last_updated`:

```sql
    po_icf              INTEGER DEFAULT 0,
    po_ihdcf            INTEGER DEFAULT 0,
    po_rebounds_created INTEGER DEFAULT 0,
    po_deflections      INTEGER DEFAULT 0,
    po_points           INTEGER DEFAULT 0,
```

- [ ] **Step 4: Add the `player_rate_zscores` table DDL**

After `CREATE_PLAYER_ADVANCED_PERCENTILES` in `src/database.py`, add:

```python
CREATE_PLAYER_RATE_ZSCORES = """
CREATE TABLE IF NOT EXISTS player_rate_zscores (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id                TEXT NOT NULL,
    player_id                INTEGER NOT NULL REFERENCES players(player_id),
    position_group           TEXT NOT NULL,
    shots_per60_z            REAL,
    chances_per60_z          REAL,
    rebounds_created_per60_z REAL,
    deflections_per60_z      REAL,
    points_per60_z           REAL,
    primary_points_per60_z   REAL,
    created_at                TEXT DEFAULT (datetime('now')),
    UNIQUE (season_id, player_id)
);
"""
```

- [ ] **Step 5: Add migrations for existing databases**

After `_GAME_EVENTS_MIGRATIONS` in `src/database.py`, add:

```python
_ADVANCED_STATS_MIGRATIONS = [
    "ALTER TABLE player_game_advanced_stats ADD COLUMN icf INTEGER DEFAULT 0",
    "ALTER TABLE player_game_advanced_stats ADD COLUMN ihdcf INTEGER DEFAULT 0",
    "ALTER TABLE player_game_advanced_stats ADD COLUMN rebounds_created INTEGER DEFAULT 0",
    "ALTER TABLE player_game_advanced_stats ADD COLUMN deflections INTEGER DEFAULT 0",
    "ALTER TABLE player_game_advanced_stats ADD COLUMN points INTEGER DEFAULT 0",
    "ALTER TABLE player_season_advanced_stats ADD COLUMN icf INTEGER DEFAULT 0",
    "ALTER TABLE player_season_advanced_stats ADD COLUMN ihdcf INTEGER DEFAULT 0",
    "ALTER TABLE player_season_advanced_stats ADD COLUMN rebounds_created INTEGER DEFAULT 0",
    "ALTER TABLE player_season_advanced_stats ADD COLUMN deflections INTEGER DEFAULT 0",
    "ALTER TABLE player_season_advanced_stats ADD COLUMN points INTEGER DEFAULT 0",
    "ALTER TABLE player_career_advanced_stats ADD COLUMN rs_icf INTEGER DEFAULT 0",
    "ALTER TABLE player_career_advanced_stats ADD COLUMN rs_ihdcf INTEGER DEFAULT 0",
    "ALTER TABLE player_career_advanced_stats ADD COLUMN rs_rebounds_created INTEGER DEFAULT 0",
    "ALTER TABLE player_career_advanced_stats ADD COLUMN rs_deflections INTEGER DEFAULT 0",
    "ALTER TABLE player_career_advanced_stats ADD COLUMN rs_points INTEGER DEFAULT 0",
    "ALTER TABLE player_career_advanced_stats ADD COLUMN po_icf INTEGER DEFAULT 0",
    "ALTER TABLE player_career_advanced_stats ADD COLUMN po_ihdcf INTEGER DEFAULT 0",
    "ALTER TABLE player_career_advanced_stats ADD COLUMN po_rebounds_created INTEGER DEFAULT 0",
    "ALTER TABLE player_career_advanced_stats ADD COLUMN po_deflections INTEGER DEFAULT 0",
    "ALTER TABLE player_career_advanced_stats ADD COLUMN po_points INTEGER DEFAULT 0",
]
```

Update `run_migrations()`:

```python
def run_migrations(conn):
    for sql in _PLAYER_MIGRATIONS + _GAME_EVENTS_MIGRATIONS + _ADVANCED_STATS_MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
```

Update `create_all_tables()`'s table list to include `CREATE_PLAYER_RATE_ZSCORES` alongside `CREATE_PLAYER_ADVANCED_PERCENTILES`.

- [ ] **Step 6: Extend `upsert_player_game_advanced_stats` and add `upsert_player_rate_zscores`**

Replace `upsert_player_game_advanced_stats`:

```python
def upsert_player_game_advanced_stats(conn, r):
    conn.execute("""
        INSERT INTO player_game_advanced_stats
            (game_id, player_id, team_id, strength_state, cf, ca, ff, fa,
             hdcf, hdca, gf, ga, primary_points, toi_seconds,
             icf, ihdcf, rebounds_created, deflections, points)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(game_id, player_id, strength_state) DO UPDATE SET
            team_id=excluded.team_id, cf=excluded.cf, ca=excluded.ca,
            ff=excluded.ff, fa=excluded.fa, hdcf=excluded.hdcf, hdca=excluded.hdca,
            gf=excluded.gf, ga=excluded.ga, primary_points=excluded.primary_points,
            toi_seconds=excluded.toi_seconds,
            icf=excluded.icf, ihdcf=excluded.ihdcf,
            rebounds_created=excluded.rebounds_created, deflections=excluded.deflections,
            points=excluded.points
    """, (r["game_id"], r["player_id"], r["team_id"], r["strength_state"],
          r["cf"], r["ca"], r["ff"], r["fa"], r["hdcf"], r["hdca"],
          r["gf"], r["ga"], r["primary_points"], r["toi_seconds"],
          r["icf"], r["ihdcf"], r["rebounds_created"], r["deflections"], r["points"]))
```

Add after `upsert_player_advanced_percentiles`:

```python
def upsert_player_rate_zscores(conn, r):
    conn.execute("""
        INSERT INTO player_rate_zscores
            (season_id, player_id, position_group, shots_per60_z, chances_per60_z,
             rebounds_created_per60_z, deflections_per60_z, points_per60_z,
             primary_points_per60_z)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(season_id, player_id) DO UPDATE SET
            position_group=excluded.position_group,
            shots_per60_z=excluded.shots_per60_z, chances_per60_z=excluded.chances_per60_z,
            rebounds_created_per60_z=excluded.rebounds_created_per60_z,
            deflections_per60_z=excluded.deflections_per60_z,
            points_per60_z=excluded.points_per60_z,
            primary_points_per60_z=excluded.primary_points_per60_z
    """, (r["season_id"], r["player_id"], r["position_group"], r["shots_per60_z"],
          r["chances_per60_z"], r["rebounds_created_per60_z"], r["deflections_per60_z"],
          r["points_per60_z"], r["primary_points_per60_z"]))
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_compute_advanced_stats.py::test_schema_has_new_rate_stat_columns_and_zscore_table -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/database.py tests/test_compute_advanced_stats.py
git commit -m "feat: add schema for shot-generation rate stat columns and z-score table"
```

---

### Task 2: Sweep — individual shot credit, rebound detection, points

**Files:**
- Modify: `etl/advanced_stats/sweep.py`
- Test: `tests/test_sweep.py`

**Interfaces:**
- Consumes: nothing new from other tasks — self-contained within `compute_game_advanced_stats(shifts, events, home_team_id, game_type)`.
- Produces: each player row in the returned list now additionally has `icf, ihdcf, rebounds_created, deflections, points` keys (int), consumed by Task 1's `upsert_player_game_advanced_stats`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sweep.py`, and first extend the `_event` helper (backward compatible — all new params have defaults matching prior hardcoded behavior):

```python
def _event(event_type, period, time_in_period, situation_code, event_owner_team_id,
           x_coord=0, y_coord=0, shooting_player_id=None, assist1_player_id=None,
           assist2_player_id=None, shot_type=None):
    return {"event_type": event_type, "period": period, "time_in_period": time_in_period,
            "situation_code": situation_code, "event_owner_team_id": event_owner_team_id,
            "x_coord": x_coord, "y_coord": y_coord,
            "shooting_player_id": shooting_player_id, "assist1_player_id": assist1_player_id,
            "assist2_player_id": assist2_player_id, "shot_type": shot_type,
            "home_team_defending_side": "right"}
```

Append these test functions:

```python
def test_individual_shot_credit_only_on_shooter_not_teammates():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, HOME, 1, "00:00", "20:00"),
              _shift(3, AWAY, 1, "00:00", "20:00")]
    events = [_event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    shooter_row = next(r for r in player_rows if r["player_id"] == 1)
    teammate_row = next(r for r in player_rows if r["player_id"] == 2)
    assert shooter_row["icf"] == 1
    assert teammate_row["icf"] == 0
    assert shooter_row["cf"] == 1 and teammate_row["cf"] == 1  # on-ice credit unaffected


def test_individual_high_danger_and_deflection_credit():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, AWAY, 1, "00:00", "20:00")]
    events = [_event("shot-on-goal", 1, "00:10", "1551", HOME, x_coord=85, y_coord=0,
                      shooting_player_id=1, shot_type="deflected")]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    shooter_row = next(r for r in player_rows if r["player_id"] == 1)
    assert shooter_row["ihdcf"] == 1
    assert shooter_row["deflections"] == 1


def test_rebound_credited_to_original_shooter_within_3_seconds():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, HOME, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:12", "1551", HOME, shooting_player_id=2),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    original = next(r for r in player_rows if r["player_id"] == 1)
    rebounder = next(r for r in player_rows if r["player_id"] == 2)
    assert original["rebounds_created"] == 1
    assert rebounder["rebounds_created"] == 0


def test_rebound_boundary_exactly_3_seconds_counts():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, HOME, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:13", "1551", HOME, shooting_player_id=2),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    original = next(r for r in player_rows if r["player_id"] == 1)
    assert original["rebounds_created"] == 1


def test_rebound_beyond_window_does_not_count():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, HOME, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:14", "1551", HOME, shooting_player_id=2),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    original = next(r for r in player_rows if r["player_id"] == 1)
    assert original["rebounds_created"] == 0


def test_rebound_different_teams_does_not_count():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, AWAY, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:11", "1551", AWAY, shooting_player_id=2),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    home_shooter = next(r for r in player_rows if r["player_id"] == 1)
    assert home_shooter["rebounds_created"] == 0


def test_rebound_same_player_consecutive_shots_counts():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:12", "1551", HOME, shooting_player_id=1),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    shooter_row = next(r for r in player_rows if r["player_id"] == 1)
    assert shooter_row["rebounds_created"] == 1


def test_rebound_scramble_credits_each_pair_independently():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, HOME, 1, "00:00", "20:00"),
              _shift(3, HOME, 1, "00:00", "20:00")]
    events = [
        _event("shot-on-goal", 1, "00:10", "1551", HOME, shooting_player_id=1),
        _event("shot-on-goal", 1, "00:12", "1551", HOME, shooting_player_id=2),
        _event("shot-on-goal", 1, "00:14", "1551", HOME, shooting_player_id=3),
    ]
    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)
    p1 = next(r for r in player_rows if r["player_id"] == 1)
    p2 = next(r for r in player_rows if r["player_id"] == 2)
    p3 = next(r for r in player_rows if r["player_id"] == 3)
    assert p1["rebounds_created"] == 1
    assert p2["rebounds_created"] == 1
    assert p3["rebounds_created"] == 0


def test_points_credits_scorer_and_both_assists_primary_points_excludes_secondary():
    events = [_event("goal", 1, "05:00", "1551", HOME, shooting_player_id=1,
                      assist1_player_id=2, assist2_player_id=3)]
    player_rows, _ = compute_game_advanced_stats([], events, home_team_id=HOME, game_type=2)

    scorer = next(r for r in player_rows if r["player_id"] == 1)
    primary_assister = next(r for r in player_rows if r["player_id"] == 2)
    secondary_assister = next(r for r in player_rows if r["player_id"] == 3)

    assert scorer["points"] == 1 and scorer["primary_points"] == 1
    assert primary_assister["points"] == 1 and primary_assister["primary_points"] == 1
    assert secondary_assister["points"] == 1 and secondary_assister["primary_points"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sweep.py -v -k "individual_shot or high_danger_and_deflection or rebound or points_credits"`
Expected: FAIL — `KeyError: 'icf'` (and similar) since these fields don't exist yet.

- [ ] **Step 3: Implement**

In `etl/advanced_stats/sweep.py`, extend `player_row()`'s initial dict (inside `compute_game_advanced_stats`):

```python
    def player_row(player_id, team_id, strength_state):
        key = (player_id, strength_state)
        if key not in player_stats:
            player_stats[key] = {
                "player_id": player_id, "team_id": team_id, "strength_state": strength_state,
                "cf": 0, "ca": 0, "ff": 0, "fa": 0, "hdcf": 0, "hdca": 0,
                "gf": 0, "ga": 0, "primary_points": 0, "toi_seconds": 0,
                "icf": 0, "ihdcf": 0, "rebounds_created": 0, "deflections": 0, "points": 0,
            }
        return player_stats[key]
```

Replace the "Primary points" loop's body (the `if scorer is not None:` / `if assist1 is not None:` block) to also credit `points`, and add an `assist2` branch:

```python
        scorer = e.get("shooting_player_id")
        if scorer is not None:
            player_row(scorer, owner, strength_state)["primary_points"] += 1
            player_row(scorer, owner, strength_state)["points"] += 1
        assist1 = e.get("assist1_player_id")
        if assist1 is not None:
            player_row(assist1, owner, strength_state)["primary_points"] += 1
            player_row(assist1, owner, strength_state)["points"] += 1
        assist2 = e.get("assist2_player_id")
        if assist2 is not None:
            player_row(assist2, owner, strength_state)["points"] += 1
```

In the shot-attempt loop, add `is_deflection` next to the existing `high_danger` computation:

```python
        is_deflection = e.get("shot_type") in ("deflected", "tip-in")
```

Add a `last_shot_attempt = {}` dict before the `for e in event_list:` loop starts (same scope as the loop, initialized once before it), and insert individual-credit + rebound logic right after the existing "credit `ca`/`fa`/`hdca`/`ga` to opposing on-ice skaters" block, before the `t_for = team_row(owner, strength_for)` line:

```python
        shooter = e.get("shooting_player_id")
        if shooter is not None:
            shooter_row = player_row(shooter, owner, strength_for)
            shooter_row["icf"] += 1
            if high_danger:
                shooter_row["ihdcf"] += 1
            if is_deflection:
                shooter_row["deflections"] += 1

            prior = last_shot_attempt.get(owner)
            if prior is not None and (t - prior[0]) <= 3:
                player_row(prior[1], owner, prior[2])["rebounds_created"] += 1
            last_shot_attempt[owner] = (t, shooter, strength_for)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sweep.py -v`
Expected: PASS (all tests, including the pre-existing ones — confirms no regression).

- [ ] **Step 5: Commit**

```bash
git add etl/advanced_stats/sweep.py tests/test_sweep.py
git commit -m "feat: compute individual shot credit, rebounds created, and points in sweep"
```

---

### Task 3: Orchestration — load shot_type/assist2, extend season aggregation

**Files:**
- Modify: `etl/compute_advanced_stats.py`
- Test: `tests/test_compute_advanced_stats.py`

**Interfaces:**
- Consumes: Task 2's new player-row keys, Task 1's extended `upsert_player_game_advanced_stats`.
- Produces: `player_season_advanced_stats` rows now include `icf, ihdcf, rebounds_created, deflections, points`, consumed by Task 4.

- [ ] **Step 1: Write the failing test**

Extend `_seed_event` in `tests/test_compute_advanced_stats.py` (backward compatible):

```python
def _seed_event(conn, game_id, event_id, event_owner_team_id=HOME,
                 shooting_player_id=None, shot_type="wrist", x_coord=10, y_coord=0):
    database.insert_game_event(conn, {
        "game_id": game_id, "event_id": event_id, "period": 1,
        "time_in_period": "00:10", "situation_code": "1551",
        "event_type": "shot-on-goal", "zone_code": "O", "x_coord": x_coord,
        "y_coord": y_coord, "shot_type": shot_type, "event_owner_team_id": event_owner_team_id,
        "shooting_player_id": shooting_player_id, "blocking_player_id": None, "goalie_in_net_id": None,
        "assist1_player_id": None, "assist2_player_id": None, "details_json": "{}",
        "home_team_defending_side": "right",
    })
```

Append:

```python
def test_compute_season_aggregates_sums_new_rate_stat_columns(conn):
    _seed_game(conn, 2024020001)
    _seed_shift(conn, 2024020001, 1, player_id=1, team_id=HOME)
    _seed_event(conn, 2024020001, 1, shooting_player_id=1, shot_type="deflected")
    conn.commit()

    module.run(conn)

    row = conn.execute("""
        SELECT icf, ihdcf, deflections FROM player_season_advanced_stats
        WHERE player_id = 1 AND season_id = '20242025' AND game_type = 2 AND strength_state = '5v5'
    """).fetchone()
    assert row["icf"] == 1
    assert row["deflections"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compute_advanced_stats.py::test_compute_season_aggregates_sums_new_rate_stat_columns -v`
Expected: FAIL — `icf`/`deflections` are `0` or `KeyError` since `_load_events_for_sweep` doesn't select `shot_type` yet and season aggregation doesn't sum the new columns.

- [ ] **Step 3: Implement**

In `etl/compute_advanced_stats.py`, update `_load_events_for_sweep`:

```python
def _load_events_for_sweep(conn, game_id):
    rows = conn.execute("""
        SELECT event_id, period, time_in_period, situation_code, event_type,
               x_coord, y_coord, shot_type, event_owner_team_id, shooting_player_id,
               assist1_player_id, assist2_player_id, home_team_defending_side
        FROM game_events WHERE game_id = ?
    """, (game_id,)).fetchall()
    return [dict(r) for r in rows]
```

Update `compute_season_aggregates`:

```python
def compute_season_aggregates(conn, season_id, game_type):
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
             icf, ihdcf, rebounds_created, deflections, points)
        SELECT
            pgas.player_id, g.season_id, g.game_type,
            (SELECT GROUP_CONCAT(DISTINCT t.abbrev)
             FROM player_game_advanced_stats pgas2
             JOIN teams t ON t.team_id = pgas2.team_id
             JOIN games g2 ON g2.game_id = pgas2.game_id
             WHERE pgas2.player_id = pgas.player_id
               AND g2.season_id = g.season_id AND g2.game_type = g.game_type) AS team_abbrevs,
            pgas.strength_state,
            SUM(pgas.cf), SUM(pgas.ca), SUM(pgas.ff), SUM(pgas.fa),
            SUM(pgas.hdcf), SUM(pgas.hdca), SUM(pgas.gf), SUM(pgas.ga),
            SUM(pgas.primary_points), SUM(pgas.toi_seconds),
            COUNT(DISTINCT pgas.game_id),
            SUM(pgas.icf), SUM(pgas.ihdcf), SUM(pgas.rebounds_created),
            SUM(pgas.deflections), SUM(pgas.points)
        FROM player_game_advanced_stats pgas
        JOIN games g ON g.game_id = pgas.game_id
        WHERE g.season_id = ? AND g.game_type = ?
        GROUP BY pgas.player_id, pgas.strength_state
        ON CONFLICT(player_id, season_id, game_type, strength_state) DO UPDATE SET
            team_abbrevs=excluded.team_abbrevs, cf=excluded.cf, ca=excluded.ca,
            ff=excluded.ff, fa=excluded.fa, hdcf=excluded.hdcf, hdca=excluded.hdca,
            gf=excluded.gf, ga=excluded.ga, primary_points=excluded.primary_points,
            toi_seconds=excluded.toi_seconds, gp=excluded.gp,
            icf=excluded.icf, ihdcf=excluded.ihdcf,
            rebounds_created=excluded.rebounds_created, deflections=excluded.deflections,
            points=excluded.points
    """, (season_id, game_type))
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v`
Expected: PASS (all tests, including pre-existing ones).

- [ ] **Step 5: Commit**

```bash
git add etl/compute_advanced_stats.py tests/test_compute_advanced_stats.py
git commit -m "feat: load shot_type/assist2 and aggregate new rate stat columns to season grain"
```

---

### Task 4: Z-score computation

**Files:**
- Modify: `etl/compute_advanced_stats.py`
- Test: `tests/test_compute_advanced_stats.py`

**Interfaces:**
- Consumes: `player_season_advanced_stats` rows from Task 3, `database.upsert_player_rate_zscores` from Task 1.
- Produces: `compute_advanced_stats.compute_zscores(conn, season_id) -> None`, called from `_run_aggregation_and_percentiles`, consumed by Task 5's API layer.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_compute_advanced_stats.py`:

```python
def _seed_zscore_population(conn, count, season_id="20242025", icf_start=1, toi_seconds=3600, game_type=2):
    for player_id in range(1, count + 1):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        icf = icf_start if icf_start is not None else player_id
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, ?, ?, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, ?, 12, ?, 3, 1, 1, 5)
        """, (player_id, season_id, game_type, toi_seconds, icf))
    conn.commit()


def test_compute_zscores_below_min_population_yields_no_rows(conn):
    _seed_zscore_population(conn, count=5)
    module.compute_zscores(conn, season_id="20242025")
    row = conn.execute("SELECT * FROM player_rate_zscores WHERE player_id = 1").fetchone()
    assert row is None


def test_compute_zscores_computes_expected_values_for_qualifying_population(conn):
    for player_id in range(1, 21):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, '20242025', 2, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, 3600, 12, ?, 3, 1, 1, 5)
        """, (player_id, player_id))
    conn.commit()

    module.compute_zscores(conn, season_id="20242025")

    import statistics
    rates = list(range(1, 21))  # toi_seconds=3600 (1hr) -> rate == icf directly
    mean = statistics.mean(rates)
    stdev = statistics.pstdev(rates)
    expected = round((1 - mean) / stdev, 2)

    row = conn.execute("SELECT shots_per60_z FROM player_rate_zscores WHERE player_id = 1").fetchone()
    assert row["shots_per60_z"] == expected


def test_compute_zscores_zero_stddev_population_yields_zero(conn):
    _seed_zscore_population(conn, count=20, icf_start=10)  # identical icf for everyone
    module.compute_zscores(conn, season_id="20242025")
    row = conn.execute("SELECT shots_per60_z FROM player_rate_zscores WHERE player_id = 1").fetchone()
    assert row["shots_per60_z"] == 0.0


def test_compute_zscores_excludes_zero_toi_player(conn):
    for player_id in range(1, 21):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        toi = 0 if player_id == 1 else 3600
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, '20242025', 2, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, ?, 12, 10, 3, 1, 1, 5)
        """, (player_id, toi))
    conn.commit()

    module.compute_zscores(conn, season_id="20242025")
    row = conn.execute("SELECT * FROM player_rate_zscores WHERE player_id = 1").fetchone()
    assert row is None


def test_compute_zscores_filters_by_game_type_regular_season_only(conn):
    _seed_zscore_population(conn, count=20)
    database.upsert_player_stub(conn, {
        "player_id": 21, "first_name": "P", "last_name": "21",
        "position_code": "C", "shoots_catches": None,
    })
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
             icf, ihdcf, rebounds_created, deflections, points)
        VALUES (21, '20242025', 3, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, 3600, 12, 999, 3, 1, 1, 5)
    """)
    conn.commit()

    module.compute_zscores(conn, season_id="20242025")
    row = conn.execute("SELECT * FROM player_rate_zscores WHERE player_id = 21").fetchone()
    assert row is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v -k zscores`
Expected: FAIL — `AttributeError: module 'etl.compute_advanced_stats' has no attribute 'compute_zscores'`.

- [ ] **Step 3: Implement**

In `etl/compute_advanced_stats.py`, add near `PERCENTILE_MIN_GP`:

```python
ZSCORE_MIN_POPULATION = 20
```

Add after `compute_percentiles`:

```python
def compute_zscores(conn, season_id):
    rate_fields = {
        "shots_per60_z": "icf", "chances_per60_z": "ihdcf",
        "rebounds_created_per60_z": "rebounds_created",
        "deflections_per60_z": "deflections",
        "points_per60_z": "points", "primary_points_per60_z": "primary_points",
    }
    for position_group, position_codes in (("F", ("C", "L", "R")), ("D", ("D",))):
        placeholders = ",".join("?" * len(position_codes))
        query = f"""
            SELECT psas.player_id, psas.icf, psas.ihdcf, psas.rebounds_created,
                   psas.deflections, psas.points, psas.primary_points, psas.toi_seconds
            FROM player_season_advanced_stats psas
            JOIN players p ON p.player_id = psas.player_id
            WHERE psas.season_id = ? AND psas.strength_state = '5v5' AND psas.game_type = 2
              AND psas.gp >= ? AND psas.toi_seconds > 0 AND p.position_code IN ({placeholders})
        """  # nosec B608 -- placeholders is only "?,?,..."; position_codes is a fixed internal tuple (never user input), values are bound below, never interpolated
        rows = conn.execute(query, (season_id, PERCENTILE_MIN_GP, *position_codes)).fetchall()

        if len(rows) < ZSCORE_MIN_POPULATION:
            continue

        def _rate(row, count_key):
            return row[count_key] / (row["toi_seconds"] / 3600.0)

        populations = {z_key: [_rate(r, count_key) for r in rows]
                       for z_key, count_key in rate_fields.items()}

        for r in rows:
            record = {"season_id": season_id, "player_id": r["player_id"],
                      "position_group": position_group}
            for z_key, count_key in rate_fields.items():
                record[z_key] = _zscore(_rate(r, count_key), populations[z_key])
            database.upsert_player_rate_zscores(conn, record)
    conn.commit()


def _zscore(value, population):
    mean = sum(population) / len(population)
    variance = sum((v - mean) ** 2 for v in population) / len(population)
    stddev = variance ** 0.5
    if stddev == 0:
        return 0.0
    return round((value - mean) / stddev, 2)
```

Wire into `_run_aggregation_and_percentiles`, replacing the `for season_id in season_ids: compute_percentiles(conn, season_id)` loop body:

```python
    for season_id in season_ids:
        compute_percentiles(conn, season_id)
        compute_zscores(conn, season_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add etl/compute_advanced_stats.py tests/test_compute_advanced_stats.py
git commit -m "feat: compute z-score normalization for shot-generation rate stats"
```

---

### Task 5: API layer

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_advanced_stats.py`

**Interfaces:**
- Consumes: `player_season_advanced_stats`/`player_rate_zscores` rows from Tasks 3–4.
- Produces: `/api/players/<id>/advanced` response's `strength_states["5v5"]` gains 12 fields (6 rates + 6 z-scores); `/api/players/stats` season-branch response gains `shots_per60_5v5`. Consumed by Tasks 6–8.

- [ ] **Step 1: Write the failing tests**

Extend `_seed_season_row` in `tests/test_app_advanced_stats.py` (backward compatible):

```python
def _seed_season_row(conn, player_id, season_id, strength_state, cf, ca, ff, fa,
                      hdcf, hdca, primary_points, team_abbrevs="HOM",
                      icf=0, ihdcf=0, rebounds_created=0, deflections=0, points=0,
                      toi_seconds=900):
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
             icf, ihdcf, rebounds_created, deflections, points)
        VALUES (?, ?, 2, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, 20, ?, ?, ?, ?, ?)
    """, (player_id, season_id, team_abbrevs, strength_state, cf, ca, ff, fa,
          hdcf, hdca, primary_points, toi_seconds,
          icf, ihdcf, rebounds_created, deflections, points))
    conn.commit()
```

Append:

```python
def test_fetch_player_advanced_includes_rate_stats_for_5v5_only(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5,
                      primary_points=15, icf=30, ihdcf=8, rebounds_created=4, deflections=2,
                      points=20, toi_seconds=3600)
    _seed_season_row(conn, 1, "20242025", "5v4", cf=20, ca=5, ff=15, fa=3, hdcf=4, hdca=1,
                      primary_points=5, icf=99, ihdcf=99, rebounds_created=99, deflections=99,
                      points=99, toi_seconds=900)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")

    s5v5 = result["strength_states"]["5v5"]
    assert s5v5["shots_per60"] == 30.0
    assert s5v5["chances_per60"] == 8.0
    assert s5v5["rebounds_created_per60"] == 4.0
    assert s5v5["deflections_per60"] == 2.0
    assert s5v5["points_per60"] == 20.0
    assert s5v5["primary_points_per60"] == 15.0
    assert "shots_per60" not in result["strength_states"]["5v4"]


def test_fetch_player_advanced_zscore_null_when_no_zscore_row(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5,
                      primary_points=15, icf=30, toi_seconds=3600)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")
    assert result["strength_states"]["5v5"]["shots_per60_z"] is None


def test_fetch_player_advanced_zscore_populated_when_zscore_row_exists(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5,
                      primary_points=15, icf=30, toi_seconds=3600)
    database.upsert_player_rate_zscores(conn, {
        "season_id": "20242025", "player_id": 1, "position_group": "F",
        "shots_per60_z": 1.23, "chances_per60_z": 0.5, "rebounds_created_per60_z": -0.2,
        "deflections_per60_z": 0.0, "points_per60_z": 0.9, "primary_points_per60_z": 0.8,
    })
    conn.commit()

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")
    assert result["strength_states"]["5v5"]["shots_per60_z"] == 1.23


def test_players_stats_season_query_includes_shots_per60_5v5(conn, monkeypatch):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    conn.execute("""
        INSERT INTO player_season_stats
            (player_id, season_id, game_type, team_abbrevs, position_code, gp, goals, assists,
             points, plus_minus, pim, pp_goals, sh_goals, shots, shooting_pct, avg_toi,
             wins, losses, ot_losses, shutouts, save_pct, gaa)
        VALUES (1, '20242025', 2, 'HOM', 'C', 10, 5, 5, 10, 0, 0, 0, 0, 20, 25.0, '15:00',
                NULL, NULL, NULL, NULL, NULL, NULL)
    """)
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
             icf, ihdcf, rebounds_created, deflections, points)
        VALUES (1, '20242025', 2, 'HOM', '5v5', 60, 40, 45, 30, 10, 5, 6, 4, 10, 3600, 10,
                24, 8, 4, 2, 20)
    """)
    conn.commit()

    monkeypatch.setattr(app_module, "get_connection", lambda: conn)
    client = app_module.app.test_client()
    resp = client.get("/api/players/stats?seasons=20242025")

    assert resp.status_code == 200
    player = next(p for p in resp.get_json() if p["player_id"] == 1)
    assert player["shots_per60_5v5"] == 24.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app_advanced_stats.py -v -k "rate_stats or zscore or shots_per60_5v5"`
Expected: FAIL — `KeyError: 'shots_per60'` and similar.

- [ ] **Step 3: Implement**

In `app.py`, replace `_fetch_player_advanced`'s body from the `season_rows = conn.execute(...)` line through the end of the `for r in season_rows:` loop:

```python
def _fetch_player_advanced(conn, player_id, season_id):
    season_rows = conn.execute("""
        SELECT strength_state, cf, ca, ff, fa, hdcf, hdca, primary_points, team_abbrevs,
               icf, ihdcf, rebounds_created, deflections, points, toi_seconds
        FROM player_season_advanced_stats
        WHERE player_id = ? AND season_id = ?
    """, (player_id, season_id)).fetchall()

    pctile_rows = conn.execute("""
        SELECT strength_state, cf_pct_pctile, ff_pct_pctile, hdcf_pct_pctile, primary_points_pctile
        FROM player_advanced_percentiles
        WHERE player_id = ? AND season_id = ?
    """, (player_id, season_id)).fetchall()
    pctiles_by_state = {r["strength_state"]: r for r in pctile_rows}

    zscore_row = conn.execute("""
        SELECT shots_per60_z, chances_per60_z, rebounds_created_per60_z,
               deflections_per60_z, points_per60_z, primary_points_per60_z
        FROM player_rate_zscores WHERE player_id = ? AND season_id = ?
    """, (player_id, season_id)).fetchone()

    strength_states = {}
    team_abbrevs = None
    for r in season_rows:
        state = r["strength_state"]
        pctile = pctiles_by_state.get(state)
        entry = {
            "cf": r["cf"], "ca": r["ca"], "cf_pct": _pct(r["cf"], r["cf"] + r["ca"]),
            "ff": r["ff"], "fa": r["fa"], "ff_pct": _pct(r["ff"], r["ff"] + r["fa"]),
            "hdcf": r["hdcf"], "hdca": r["hdca"], "hdcf_pct": _pct(r["hdcf"], r["hdcf"] + r["hdca"]),
            "primary_points": r["primary_points"],
            "cf_pctile": pctile["cf_pct_pctile"] if pctile else None,
            "ff_pctile": pctile["ff_pct_pctile"] if pctile else None,
            "hdcf_pctile": pctile["hdcf_pct_pctile"] if pctile else None,
            "primary_points_pctile": pctile["primary_points_pctile"] if pctile else None,
        }
        if state == "5v5":
            toi_hours = r["toi_seconds"] / 3600.0 if r["toi_seconds"] else None
            entry.update({
                "shots_per60": round(r["icf"] / toi_hours, 2) if toi_hours else None,
                "chances_per60": round(r["ihdcf"] / toi_hours, 2) if toi_hours else None,
                "rebounds_created_per60": round(r["rebounds_created"] / toi_hours, 2) if toi_hours else None,
                "deflections_per60": round(r["deflections"] / toi_hours, 2) if toi_hours else None,
                "points_per60": round(r["points"] / toi_hours, 2) if toi_hours else None,
                "primary_points_per60": round(r["primary_points"] / toi_hours, 2) if toi_hours else None,
                "shots_per60_z": zscore_row["shots_per60_z"] if zscore_row else None,
                "chances_per60_z": zscore_row["chances_per60_z"] if zscore_row else None,
                "rebounds_created_per60_z": zscore_row["rebounds_created_per60_z"] if zscore_row else None,
                "deflections_per60_z": zscore_row["deflections_per60_z"] if zscore_row else None,
                "points_per60_z": zscore_row["points_per60_z"] if zscore_row else None,
                "primary_points_per60_z": zscore_row["primary_points_per60_z"] if zscore_row else None,
            })
        strength_states[state] = entry
        if state == "5v5":
            team_abbrevs = r["team_abbrevs"]
```

Leave the rest of `_fetch_player_advanced` (trend/PDO) unchanged.

In the `/api/players/stats` season-specific branch, add a new SELECT column right after `cf_pct_5v5`'s line:

```sql
                ROUND(SUM(adv.cf) * 100.0 / NULLIF(SUM(adv.cf) + SUM(adv.ca), 0), 1) AS cf_pct_5v5,
                ROUND(SUM(adv.icf) * 1.0 / NULLIF(SUM(adv.toi_seconds) / 3600.0, 0), 2) AS shots_per60_5v5
```

And in the response-building loop, add after the `cf_pct_5v5` line:

```python
            "cf_pct_5v5":   r["cf_pct_5v5"] if "cf_pct_5v5" in r.keys() else None,
            # Same "season-specific branch only" caveat as cf_pct_5v5 above -- no
            # career-level advanced-stats aggregation exists yet.
            "shots_per60_5v5": r["shots_per60_5v5"] if "shots_per60_5v5" in r.keys() else None,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_app_advanced_stats.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_advanced_stats.py
git commit -m "feat: expose shot-generation rate stats and z-scores via the API"
```

---

### Task 6: Frontend types

**Files:**
- Modify: `frontend/src/lib/types.ts`

**Interfaces:**
- Produces: `AdvancedStrengthState` gains 12 optional fields; `PlayerStats` gains `shots_per60_5v5`. Consumed by Tasks 7–8.

- [ ] **Step 1: Implement**

In `frontend/src/lib/types.ts`, add to `PlayerStats` right after `cf_pct_5v5?: number | null;`:

```typescript
  shots_per60_5v5?: number | null;
```

Add to `AdvancedStrengthState` right after `primary_points_pctile: number | null;`:

```typescript
  shots_per60?: number | null;
  chances_per60?: number | null;
  rebounds_created_per60?: number | null;
  deflections_per60?: number | null;
  points_per60?: number | null;
  primary_points_per60?: number | null;
  shots_per60_z?: number | null;
  chances_per60_z?: number | null;
  rebounds_created_per60_z?: number | null;
  deflections_per60_z?: number | null;
  points_per60_z?: number | null;
  primary_points_per60_z?: number | null;
```

All optional (`?`) since only the `5v5` entry ever populates them — `5v4`/`4v5` entries won't have these keys at all.

- [ ] **Step 2: Verify the frontend still type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add shot-generation rate stat and z-score types"
```

---

### Task 7: PlayerProfilePanel — Shot Generation section

**Files:**
- Modify: `frontend/src/components/PlayerProfilePanel.tsx`
- Test: `frontend/src/components/PlayerProfilePanel.test.tsx`

**Interfaces:**
- Consumes: Task 6's `AdvancedStrengthState` fields via `state.data.strength_states["5v5"]` (always 5v5, independent of the existing `STRENGTH_STATES` toggle/`current`).

- [ ] **Step 1: Write the failing tests**

In `frontend/src/components/PlayerProfilePanel.test.tsx`, extend `MOCK_ADVANCED`'s `"5v5"` entry (add fields, don't remove existing ones):

```typescript
    "5v5": {
      cf: 60, ca: 40, cf_pct: 60.0, ff: 45, fa: 30, ff_pct: 60.0,
      hdcf: 10, hdca: 5, hdcf_pct: 66.7, primary_points: 15,
      cf_pctile: 75.0, ff_pctile: 80.0, hdcf_pctile: 60.0, primary_points_pctile: 90.0,
      shots_per60: 24.0, chances_per60: 8.0, rebounds_created_per60: 4.0,
      deflections_per60: 2.0, points_per60: 20.0, primary_points_per60: 15.0,
      shots_per60_z: 1.23, chances_per60_z: 0.5, rebounds_created_per60_z: -0.2,
      deflections_per60_z: 0.0, points_per60_z: 0.9, primary_points_per60_z: 0.8,
    },
```

Append inside the `describe("PlayerProfilePanel", ...)` block:

```typescript
  it("renders the Shot Generation z-score boxes for 5v5", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("1.23")).toBeInTheDocument());
    expect(screen.getByText("24.00")).toBeInTheDocument();
  });

  it("shows N/A for a Shot Generation stat with a null z-score", async () => {
    vi.stubGlobal("fetch", vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          ...MOCK_ADVANCED,
          strength_states: {
            ...MOCK_ADVANCED.strength_states,
            "5v5": { ...MOCK_ADVANCED.strength_states["5v5"], shots_per60_z: null },
          },
        }),
      } as Response)
    ));
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getAllByText("N/A").length).toBeGreaterThan(0));
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: FAIL — the new text isn't rendered yet.

- [ ] **Step 3: Implement**

In `frontend/src/components/PlayerProfilePanel.tsx`, add a new component after `PercentileBox`:

```tsx
interface ZScoreBoxProps {
  label: string;
  rate: number | null | undefined;
  z: number | null | undefined;
  nullReason: string;
  tooltip?: string;
}

function ZScoreBox({ label, rate, z, nullReason, tooltip }: ZScoreBoxProps) {
  if (z === null || z === undefined) {
    return (
      <div className="rounded-lg bg-muted p-3 text-center opacity-60" title={nullReason}>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-2xl font-semibold tabular-nums">N/A</div>
      </div>
    );
  }
  const color = z >= 0 ? "bg-sky-500/20" : "bg-rose-500/20";
  return (
    <div className={`rounded-lg p-3 text-center ${color}`} title={tooltip}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{z.toFixed(2)}</div>
      <div className="text-xs text-muted-foreground tabular-nums">
        {rate == null ? "-" : rate.toFixed(2)}
      </div>
    </div>
  );
}
```

Insert a new grid, reading from `state.data.strength_states["5v5"]` (not `current`, since this section is always 5v5), between the existing `grid grid-cols-5 gap-2` percentile-box block and the trend-chart `<div className="h-40 w-full">`:

```tsx
                <div className="grid grid-cols-3 gap-2">
                  <ZScoreBox label="Shots/60"
                    rate={state.data.strength_states["5v5"]?.shots_per60}
                    z={state.data.strength_states["5v5"]?.shots_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox label="Chances/60"
                    rate={state.data.strength_states["5v5"]?.chances_per60}
                    z={state.data.strength_states["5v5"]?.chances_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox label="Rebounds Created/60"
                    rate={state.data.strength_states["5v5"]?.rebounds_created_per60}
                    z={state.data.strength_states["5v5"]?.rebounds_created_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season"
                    tooltip="Heuristic: a shot attempt within 3 seconds of this player's own shot attempt, same team. Not possession-confirmed." />
                  <ZScoreBox label="Deflections/60"
                    rate={state.data.strength_states["5v5"]?.deflections_per60}
                    z={state.data.strength_states["5v5"]?.deflections_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox label="Points/60"
                    rate={state.data.strength_states["5v5"]?.points_per60}
                    z={state.data.strength_states["5v5"]?.points_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox label="Primary Points/60"
                    rate={state.data.strength_states["5v5"]?.primary_points_per60}
                    z={state.data.strength_states["5v5"]?.primary_points_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                </div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: PASS (all tests, including pre-existing ones).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PlayerProfilePanel.tsx frontend/src/components/PlayerProfilePanel.test.tsx
git commit -m "feat: render Shot Generation z-score boxes in the player profile panel"
```

---

### Task 8: PlayerTable — teaser column

**Files:**
- Modify: `frontend/src/components/PlayerTable.tsx`
- Test: `frontend/src/components/PlayerTable.test.tsx`

**Interfaces:**
- Consumes: Task 5/6's `shots_per60_5v5` field.

- [ ] **Step 1: Write the failing test**

Append inside `describe("PlayerTable", ...)` in `frontend/src/components/PlayerTable.test.tsx`:

```typescript
  it("renders the Shots/60 (5v5) teaser column", () => {
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    expect(screen.getByRole("columnheader", { name: "Shots/60 (5v5)" })).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/PlayerTable.test.tsx`
Expected: FAIL — no column with that name.

- [ ] **Step 3: Implement**

In `frontend/src/components/PlayerTable.tsx`, add to `COLUMNS` right after the `cf_pct_5v5` entry:

```typescript
  { key: "shots_per60_5v5", label: "Shots/60 (5v5)", numeric: true, skaterOnly: true },
```

Add to `cellValue`, after the `cf_pct_5v5` branch:

```typescript
  if (col.key === "shots_per60_5v5") return Number(val).toFixed(2);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/PlayerTable.test.tsx`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PlayerTable.tsx frontend/src/components/PlayerTable.test.tsx
git commit -m "feat: add Shots/60 (5v5) teaser column to the player table"
```

---

### Task 9: Docs, one-time backfill, sync verification

**Files:**
- Create: `docs/api/advanced-stats.md`
- Modify: `README.md`

**Interfaces:** none (documentation/operability only).

- [ ] **Step 1: Write the API reference doc**

Create `docs/api/advanced-stats.md`:

```markdown
# Advanced Stats API Reference

Documents `GET /api/players/<player_id>/advanced` and `GET /api/teams/<team_abbrev>/advanced`.

## `GET /api/players/<player_id>/advanced?season=<season_id>`

Returns `{ player_id, season_id, strength_states, trend, pdo }`.

`strength_states` is keyed by `5v5` / `5v4` / `4v5`. Every state has:

| Field | Type | Meaning |
|---|---|---|
| `cf`, `ca` | int | On-ice Corsi For/Against (all on-ice skaters credited) |
| `cf_pct` | float\|null | `cf / (cf+ca) * 100`, 1 decimal |
| `ff`, `fa`, `ff_pct` | — | Fenwick equivalents (excludes blocked shots) |
| `hdcf`, `hdca`, `hdcf_pct` | — | High-danger Corsi equivalents |
| `primary_points` | int | Goals + primary assists (on-ice independent) |
| `cf_pctile`, `ff_pctile`, `hdcf_pctile`, `primary_points_pctile` | float\|null | Percentile rank within position group, 10-GP floor, `5v5`/`5v4`/`4v5` only |

**`5v5` only**, additionally:

| Field | Type | Meaning |
|---|---|---|
| `shots_per60` | float\|null | Individual shot attempts (on goal+missed+blocked+goal) / 5v5 TOI hours, 2 decimals |
| `chances_per60` | float\|null | Individual high-danger shot attempts / TOI hours |
| `rebounds_created_per60` | float\|null | **Heuristic**: shot attempts followed within 3s by a same-team shot attempt, credited to the original shooter / TOI hours. Not possession-confirmed. |
| `deflections_per60` | float\|null | Individual shot attempts with `shot_type IN ('deflected','tip-in')` / TOI hours |
| `points_per60` | float\|null | Goals + all assists / TOI hours |
| `primary_points_per60` | float\|null | `primary_points` / TOI hours |
| `shots_per60_z`, `chances_per60_z`, `rebounds_created_per60_z`, `deflections_per60_z`, `points_per60_z`, `primary_points_per60_z` | float\|null | Z-score vs. position-group population (regular season, 10-GP floor, 20-player minimum population). `null` if the player or the league sample doesn't clear the floor. |

## `GET /api/players/stats?seasons=<season_id>`

Adds `shots_per60_5v5` (float\|null) alongside the existing `cf_pct_5v5` teaser field — same "season-specific query only, `null` for the all-seasons/career view" caveat, since no career-level advanced-stats aggregation is populated yet.

## Not available (Phase 2 — blocked on a data source beyond the free NHL API)

- **Passing**: Point Shot Setups/60, Passes from Center Lane/60, High Danger Assists/60, Deflection Assists/60, One-timer Assists/60 — no pass event/coordinate data in the NHL public feed.
- **Zone Entries**: Zone Entries/60, Controlled Entry%, Controlled Entries/60, Entries w/ Passing Play/60, Entries w/ Chances/60, Entry w/ Pass%, Controlled Entry w/ Chance% — entry style (carried/passed/dumped) isn't derivable from discrete zone-coded events.
- **DZ Retrievals & Exits**: all 12 stats — same possession-tracking gap.
- **Forechecking**: Pressures/60, Recovered Dump-ins/60 — needs proximity/pressure data (NHL Edge tracking or manual charting).
- **Rush Offense/60, Cycle & Forecheck Offense/60, One-timers/60, Shots off HD Passes/60** — deferred alongside the above (possession/passing gap).
```

- [ ] **Step 2: Add the one-time backfill section to README.md**

Add a new section to `README.md`, styled after the existing "One-time backfill (advanced stats...)" section (right after it):

```markdown
### One-time backfill (shot-generation rate stats)

After pulling this change, the new `icf`/`ihdcf`/`rebounds_created`/`deflections`/
`points` columns and the `player_rate_zscores` table need to exist before a
recompute can populate them, and `run()`'s `NOT EXISTS` gating means already-
processed games won't be reprocessed on their own — a one-time full recompute
is required:

```bash
python scripts/setup_db.py   # applies the schema migration (safe to rerun)
cp data/nhl_stats.db "data/nhl_stats.db.bak-$(date +%Y%m%d)"   # required -- see below
sqlite3 data/nhl_stats.db "DELETE FROM player_game_advanced_stats; DELETE FROM player_season_advanced_stats; DELETE FROM player_career_advanced_stats; DELETE FROM player_advanced_percentiles; DELETE FROM player_rate_zscores;"
python -m etl.compute_advanced_stats
```

**Back up first.** This deletes and rebuilds all advanced-stats tables (not
just the ones this phase adds columns to) — a per-game failure partway through
leaves them partially or fully empty rather than rolling back. All advanced
stats are unavailable via the API for the duration of the recompute (a personal
local SQLite file, so no concurrent users are affected, but it's a real window,
not a cosmetic one).

After this completes once, `python scripts/run_all_etl.py` — already the
documented way to keep `game_events`/`player_shifts`/advanced stats current —
is sufficient going forward; its existing `NOT EXISTS` gating picks up the new
columns for every game processed after this backfill with no further changes.
```

- [ ] **Step 3: Verify sync integration end-to-end**

This is a manual verification, not a test — confirms the "rides along automatically" claim rather than assuming it:

1. Confirm the current row count: `sqlite3 data/nhl_stats.db "SELECT COUNT(*) FROM player_game_advanced_stats;"`
2. Run `python scripts/run_all_etl.py` (after the Task 9 Step 2 backfill has completed once).
3. Confirm the row count is unchanged (idempotent — no new games existed to process) and spot-check a known player: `sqlite3 data/nhl_stats.db "SELECT icf, ihdcf, deflections, points FROM player_game_advanced_stats WHERE player_id = <a real player_id> LIMIT 5;"` — values should be non-null/non-placeholder integers, not all zero (unless that player genuinely took no shots in those games).
4. When a new game actually completes (next real game day), rerun `python scripts/run_all_etl.py` and confirm the row count increases and the new game's row has non-zero `icf` for at least one player who recorded a shot — this is the real end-to-end confirmation that new games pick up the new columns without any code change, since `compute_advanced_stats.run()` is already wired into `run_all_etl.py`'s step list (unlike `scripts/sync.py`, which does not include it).

- [ ] **Step 4: Commit**

```bash
git add docs/api/advanced-stats.md README.md
git commit -m "docs: add advanced-stats API reference and shot-generation backfill instructions"
```

---

## Plan Self-Review

**Spec coverage:** Shots/60 (Task 2/5), Chances/60 (Task 2/5), Rebounds Created/60 heuristic incl. same-player/scramble rules (Task 2), Deflections/60 (Task 2), Points/60 + Primary Points/60 (Task 2/5), z-score normalization incl. min-population floor and `game_type` fix (Task 4), backup-before-destructive-recompute (Task 9), null z-score UI (Task 7), 2-decimal rounding (Task 5/7), PlayerProfilePanel section + PlayerTable teaser column (Tasks 7–8), `docs/api/advanced-stats.md` (Task 9), sync/`run_all_etl.py` verification (Task 9). All spec sections have a corresponding task.

**Placeholder scan:** no TBD/TODO; every step has complete, runnable code; no "similar to Task N" references.

**Type consistency:** `icf`/`ihdcf`/`rebounds_created`/`deflections`/`points` dict keys are identical from sweep.py (Task 2) → upsert (Task 1) → season aggregation (Task 3) → z-score query (Task 4) → API response (Task 5) → TS types (Task 6) → component props (Tasks 7–8). `compute_zscores(conn, season_id)` signature matches its call site in `_run_aggregation_and_percentiles`. `upsert_player_rate_zscores(conn, r)` key names match both the z-score computation's `record` dict (Task 4) and the test fixtures (Tasks 1, 4, 5).
