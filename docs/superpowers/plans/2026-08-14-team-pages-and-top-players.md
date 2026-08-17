# Team Pages + Top Players Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build branded per-team pages (top offense/defense/goalie leaderboards) and a league-wide Top Players page, closing #116 and #117.

**Architecture:** Extend the existing ETL-precomputed z-score system (`etl/compute_advanced_stats.py`) with two new rate fields (CA/60, HDCA/60) and a new goalie z-score table, expose them via a new `/api/players/rankings` endpoint, and consume them from a small pure frontend function that combines already-computed z-scores into three composite leaderboards (Offense/Defense/Goalie) shared by both new pages.

**Tech Stack:** Python/Flask/SQLite (ETL + backend), React 19 + TypeScript + react-router-dom + Tailwind/shadcn (frontend), pytest + Vitest/Testing Library.

## Global Constraints

- Scoring weights (fixed constants, not user-configurable): Offense = 0.62·z(primary_points/60) + 0.38·z(iCF/60); Defense = 0.64·z(−CA/60) + 0.36·z(−HDCA/60); Goalie = 0.67·z(SV%) + 0.33·z(−GAA).
- Reuse existing thresholds: `PERCENTILE_MIN_GP = 10`, `ZSCORE_MIN_POPULATION = 20` (both already in `etl/compute_advanced_stats.py`). New goalie-specific floor: `GOALIE_ZSCORE_MIN_GP = 5`.
- Offense/Defense/Goalie are three separate leaderboards — never merged into one blended list.
- Top 5 per leaderboard on a team page; top 15 per leaderboard on the league-wide Top Players page.
- No population statistics computed client-side — all mean/stddev math happens in the ETL job. The frontend only combines already-z-scored values with fixed weights.
- Follow existing conventions: `@/` import alias, `cn()` from `@/lib/utils`, Tailwind design tokens (`bg-card`, `border-border`, `text-muted-foreground`), `teamBranding.ts`'s `teamColors()`/`logoUrl()` (the `_dark` logo variant, matching this app's theme — not `TeamPicker.tsx`'s separate `_light` one-off).

---

### Task 1: ETL — add CA/60 and HDCA/60 z-scores to `compute_zscores()`

**Files:**
- Modify: `src/database.py` (schema constant, migration list, upsert function)
- Modify: `etl/compute_advanced_stats.py` (`compute_zscores()`)
- Test: `tests/test_compute_advanced_stats.py`

**Interfaces:**
- Produces: `player_rate_zscores` table gains `ca_per60_z REAL`, `hdca_per60_z REAL` columns, populated by `compute_zscores()` for every season/position-group (F/D) alongside the existing fields.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_compute_advanced_stats.py` (append near the existing `chances_per60_z` tests):

```python
def test_compute_zscores_computes_ca_and_hdca_per60_z(conn):
    # 20 qualifying players (meets ZSCORE_MIN_POPULATION), each with distinct
    # ca/hdca values so a real, non-degenerate z-score is computable.
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
            VALUES (?, '20172018', 2, 'HOM', '5v5', 1, ?, 1, 1, 1, ?, 1, 1, 1, 3600, 12,
                    1, 1, 1, 1, 5)
        """, (player_id, player_id, player_id))
    conn.commit()

    module.compute_zscores(conn, season_id="20172018")

    p1 = conn.execute(
        "SELECT ca_per60_z, hdca_per60_z FROM player_rate_zscores WHERE player_id = 1"
    ).fetchone()
    assert p1["ca_per60_z"] is not None
    assert p1["hdca_per60_z"] is not None
    # player 1 has the lowest ca/hdca of the 20 -- lowest raw value means the
    # most negative z-score (this is the raw per-metric z, not yet negated
    # for "lower is better" -- that inversion happens in the frontend combine step)
    assert p1["ca_per60_z"] < 0
    assert p1["hdca_per60_z"] < 0


def test_compute_zscores_ca_hdca_null_when_below_min_population(conn):
    # Only 5 qualifying players -- below ZSCORE_MIN_POPULATION (20), so every
    # z-score field (including the new ones) must be None, not just skipped.
    for player_id in range(1, 6):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, '20172018', 2, 'HOM', '5v5', 1, ?, 1, 1, 1, ?, 1, 1, 1, 3600, 12,
                    1, 1, 1, 1, 5)
        """, (player_id, player_id, player_id))
    conn.commit()

    module.compute_zscores(conn, season_id="20172018")

    rows = conn.execute("SELECT * FROM player_rate_zscores WHERE season_id = '20172018'").fetchall()
    assert len(rows) == 0  # below ZSCORE_MIN_POPULATION -- compute_zscores skips the whole group
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python3 -m pytest tests/test_compute_advanced_stats.py -k "ca_and_hdca or below_min_population" -v`
Expected: FAIL — `sqlite3.OperationalError: no such column: ca_per60_z` (column doesn't exist yet).

- [ ] **Step 3: Add the schema migration**

In `src/database.py`, find `_ADVANCED_STATS_MIGRATIONS` (line 615) and add two entries at the end of the list, right before the closing `]`:

```python
    "ALTER TABLE player_rate_zscores ADD COLUMN ca_per60_z REAL",
    "ALTER TABLE player_rate_zscores ADD COLUMN hdca_per60_z REAL",
```

Also update `CREATE_PLAYER_RATE_ZSCORES` (the `CREATE TABLE IF NOT EXISTS player_rate_zscores` string, so a brand-new database gets the columns without needing the migration) — add the two columns to the `CREATE TABLE` body, right after `primary_points_per60_z   REAL,`:

```python
    primary_points_per60_z   REAL,
    ca_per60_z                REAL,
    hdca_per60_z              REAL,
```

- [ ] **Step 4: Update `upsert_player_rate_zscores`**

In `src/database.py`, replace the existing `upsert_player_rate_zscores` function (around line 1006) with:

```python
def upsert_player_rate_zscores(conn, r):
    conn.execute("""
        INSERT INTO player_rate_zscores
            (season_id, player_id, position_group, shots_per60_z, chances_per60_z,
             rebounds_created_per60_z, deflections_per60_z, points_per60_z,
             primary_points_per60_z, ca_per60_z, hdca_per60_z)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(season_id, player_id) DO UPDATE SET
            position_group=excluded.position_group,
            shots_per60_z=excluded.shots_per60_z, chances_per60_z=excluded.chances_per60_z,
            rebounds_created_per60_z=excluded.rebounds_created_per60_z,
            deflections_per60_z=excluded.deflections_per60_z,
            points_per60_z=excluded.points_per60_z,
            primary_points_per60_z=excluded.primary_points_per60_z,
            ca_per60_z=excluded.ca_per60_z, hdca_per60_z=excluded.hdca_per60_z
    """, (r["season_id"], r["player_id"], r["position_group"], r["shots_per60_z"],
          r["chances_per60_z"], r["rebounds_created_per60_z"], r["deflections_per60_z"],
          r["points_per60_z"], r["primary_points_per60_z"],
          r["ca_per60_z"], r["hdca_per60_z"]))
```

- [ ] **Step 5: Extend `compute_zscores()`**

In `etl/compute_advanced_stats.py`, in `compute_zscores()` (line 179), update the `rate_fields` dict and the query's `SELECT` list:

```python
def compute_zscores(conn, season_id):
    rate_fields = {
        "shots_per60_z": "icf", "chances_per60_z": "ihdcf",
        "rebounds_created_per60_z": "rebounds_created",
        "deflections_per60_z": "deflections",
        "points_per60_z": "points", "primary_points_per60_z": "primary_points",
        "ca_per60_z": "ca", "hdca_per60_z": "hdca",
    }
    for position_group, position_codes in (("F", ("C", "L", "R")), ("D", ("D",))):
        placeholders = ",".join("?" * len(position_codes))
        query = f"""
            SELECT psas.player_id, psas.icf, psas.ihdcf, psas.rebounds_created,
                   psas.deflections, psas.points, psas.primary_points, psas.toi_seconds,
                   psas.ca, psas.hdca
            FROM player_season_advanced_stats psas
            JOIN players p ON p.player_id = psas.player_id
            WHERE psas.season_id = ? AND psas.strength_state = '5v5' AND psas.game_type = 2
              AND psas.gp >= ? AND psas.toi_seconds > 0 AND p.position_code IN ({placeholders})
        """  # nosec B608 -- placeholders is only "?,?,..."; position_codes is a fixed internal tuple (never user input), values are bound below, never interpolated
        rows = conn.execute(query, (season_id, PERCENTILE_MIN_GP, *position_codes)).fetchall()
```

(The rest of the function — `if len(rows) < ZSCORE_MIN_POPULATION`, `_rate()`, `populations`, `sufficient_population`, the final upsert loop — is unchanged; it already iterates `rate_fields` generically, so the two new entries flow through automatically.)

- [ ] **Step 6: Run test to verify it passes**

Run: `./.venv/bin/python3 -m pytest tests/test_compute_advanced_stats.py -k "ca_and_hdca or below_min_population" -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Run the full ETL test suite**

Run: `./.venv/bin/python3 -m pytest tests/test_compute_advanced_stats.py -v`
Expected: all tests PASS, no regressions (the two new `rate_fields` entries are purely additive).

- [ ] **Step 8: Commit**

```bash
git add src/database.py etl/compute_advanced_stats.py tests/test_compute_advanced_stats.py
git commit -m "feat: add CA/60 and HDCA/60 z-scores to compute_zscores (#116, #117)"
```

---

### Task 2: ETL — goalie z-scores (new table + function)

**Files:**
- Modify: `src/database.py` (new `CREATE_GOALIE_RATE_ZSCORES`, new `upsert_goalie_rate_zscores`, register the new table)
- Modify: `etl/compute_advanced_stats.py` (new `compute_goalie_zscores()`, new `GOALIE_ZSCORE_MIN_GP` constant, wire into `_run_aggregation_and_percentiles()`)
- Test: `tests/test_compute_advanced_stats.py`

**Interfaces:**
- Consumes: `_zscore(value, population)` (existing helper, `etl/compute_advanced_stats.py`, unchanged signature).
- Produces: new `goalie_rate_zscores` table (`season_id`, `player_id`, `sv_pct_z`, `gaa_z`); `compute_goalie_zscores(conn, season_id)` — no return value, upserts rows, mirrors `compute_zscores()`'s shape.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_compute_advanced_stats.py`:

```python
def test_compute_goalie_zscores_computes_sv_pct_and_gaa_z(conn):
    # 6 qualifying goalies (only need to clear GOALIE_ZSCORE_MIN_GP=5, no
    # separate min-population floor like skaters -- goalie pools are much
    # smaller league-wide, so this uses len(rows) > 0 as its only floor).
    database.upsert_season(conn, {"season_id": "20172018", "start_year": 2017, "end_year": 2018})
    for player_id in range(1, 7):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "G", "last_name": str(player_id),
            "position_code": "G", "shoots_catches": None,
        })
        conn.execute("""
            INSERT INTO player_season_stats
                (player_id, season_id, game_type, position_code, gp, save_pct, gaa)
            VALUES (?, '20172018', 2, 'G', 10, ?, ?)
        """, (player_id, 0.900 + player_id * 0.001, 3.00 - player_id * 0.05))
    conn.commit()

    module.compute_goalie_zscores(conn, season_id="20172018")

    rows = conn.execute("SELECT * FROM goalie_rate_zscores WHERE season_id = '20172018'").fetchall()
    assert len(rows) == 6
    p1 = next(r for r in rows if r["player_id"] == 1)
    assert p1["sv_pct_z"] is not None
    assert p1["gaa_z"] is not None


def test_compute_goalie_zscores_excludes_goalies_below_min_gp(conn):
    database.upsert_season(conn, {"season_id": "20172018", "start_year": 2017, "end_year": 2018})
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "G", "last_name": "Qualifies",
        "position_code": "G", "shoots_catches": None,
    })
    database.upsert_player_stub(conn, {
        "player_id": 2, "first_name": "G", "last_name": "TooFew",
        "position_code": "G", "shoots_catches": None,
    })
    conn.execute("""
        INSERT INTO player_season_stats
            (player_id, season_id, game_type, position_code, gp, save_pct, gaa)
        VALUES (1, '20172018', 2, 'G', 10, 0.910, 2.50)
    """)
    conn.execute("""
        INSERT INTO player_season_stats
            (player_id, season_id, game_type, position_code, gp, save_pct, gaa)
        VALUES (2, '20172018', 2, 'G', 2, 0.920, 2.00)
    """)  # gp=2, below GOALIE_ZSCORE_MIN_GP=5
    conn.commit()

    module.compute_goalie_zscores(conn, season_id="20172018")

    rows = conn.execute("SELECT player_id FROM goalie_rate_zscores WHERE season_id = '20172018'").fetchall()
    assert [r["player_id"] for r in rows] == [1]


def test_compute_goalie_zscores_excludes_skaters(conn):
    database.upsert_season(conn, {"season_id": "20172018", "start_year": 2017, "end_year": 2018})
    for player_id in range(1, 7):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "S", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        conn.execute("""
            INSERT INTO player_season_stats
                (player_id, season_id, game_type, position_code, gp, save_pct, gaa)
            VALUES (?, '20172018', 2, 'C', 10, NULL, NULL)
        """, (player_id,))
    conn.commit()

    module.compute_goalie_zscores(conn, season_id="20172018")

    rows = conn.execute("SELECT * FROM goalie_rate_zscores WHERE season_id = '20172018'").fetchall()
    assert len(rows) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python3 -m pytest tests/test_compute_advanced_stats.py -k "goalie_zscores" -v`
Expected: FAIL — `AttributeError: module 'etl.compute_advanced_stats' has no attribute 'compute_goalie_zscores'`.

- [ ] **Step 3: Add the schema (new table)**

In `src/database.py`, add a new constant right after `CREATE_PLAYER_RATE_ZSCORES` (after line 588):

```python
CREATE_GOALIE_RATE_ZSCORES = """
CREATE TABLE IF NOT EXISTS goalie_rate_zscores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id     TEXT NOT NULL,
    player_id     INTEGER NOT NULL REFERENCES players(player_id),
    sv_pct_z      REAL,
    gaa_z         REAL,
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE (season_id, player_id)
);
"""
```

Find where `CREATE_PLAYER_RATE_ZSCORES` is registered in the table-creation list (around line 670-671, inside whatever function iterates `[..., CREATE_PLAYER_CAREER_ADVANCED_STATS, CREATE_PLAYER_ADVANCED_PERCENTILES, CREATE_PLAYER_RATE_ZSCORES]`) and add `CREATE_GOALIE_RATE_ZSCORES` to that same list, right after `CREATE_PLAYER_RATE_ZSCORES`.

- [ ] **Step 4: Add `upsert_goalie_rate_zscores`**

In `src/database.py`, add a new function right after `upsert_player_rate_zscores`:

```python
def upsert_goalie_rate_zscores(conn, r):
    conn.execute("""
        INSERT INTO goalie_rate_zscores (season_id, player_id, sv_pct_z, gaa_z)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(season_id, player_id) DO UPDATE SET
            sv_pct_z=excluded.sv_pct_z, gaa_z=excluded.gaa_z
    """, (r["season_id"], r["player_id"], r["sv_pct_z"], r["gaa_z"]))
```

- [ ] **Step 5: Add `compute_goalie_zscores()`**

In `etl/compute_advanced_stats.py`, add a new constant near the top (with `PERCENTILE_MIN_GP`/`ZSCORE_MIN_POPULATION`):

```python
GOALIE_ZSCORE_MIN_GP = 5
```

Add the function itself, after `compute_zscores()` (after its `conn.commit()` at line 232, before `def _zscore(...)`):

```python
def compute_goalie_zscores(conn, season_id):
    rows = conn.execute("""
        SELECT player_id, save_pct, gaa
        FROM player_season_stats
        WHERE season_id = ? AND game_type = 2 AND position_code = 'G'
          AND gp >= ? AND save_pct IS NOT NULL AND gaa IS NOT NULL
    """, (season_id, GOALIE_ZSCORE_MIN_GP)).fetchall()

    if not rows:
        return

    sv_pcts = [r["save_pct"] for r in rows]
    gaas = [r["gaa"] for r in rows]

    for r in rows:
        database.upsert_goalie_rate_zscores(conn, {
            "season_id": season_id,
            "player_id": r["player_id"],
            "sv_pct_z": _zscore(r["save_pct"], sv_pcts),
            "gaa_z": _zscore(r["gaa"], gaas),
        })
    conn.commit()
```

- [ ] **Step 6: Wire the new function into `_run_aggregation_and_percentiles()`**

In `etl/compute_advanced_stats.py`, in `_run_aggregation_and_percentiles()` (line 46), update the final loop:

```python
    season_ids = {row["season_id"] for row in season_game_type_pairs}
    for season_id in season_ids:
        compute_percentiles(conn, season_id)
        compute_zscores(conn, season_id)
        compute_goalie_zscores(conn, season_id)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `./.venv/bin/python3 -m pytest tests/test_compute_advanced_stats.py -k "goalie_zscores" -v`
Expected: PASS (3 tests).

- [ ] **Step 8: Run the full ETL test suite**

Run: `./.venv/bin/python3 -m pytest tests/test_compute_advanced_stats.py -v`
Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add src/database.py etl/compute_advanced_stats.py tests/test_compute_advanced_stats.py
git commit -m "feat: add goalie z-scores (SV%, GAA) to the ETL pipeline (#116, #117)"
```

---

### Task 3: Backend — `/api/players/rankings` endpoint

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_rankings.py` (create)

**Interfaces:**
- Produces: `GET /api/players/rankings?season=<id>[&team=<abbrev>]` → JSON array of objects: `{player_id, name, team_abbrev, position_group, primary_points_per60_z, shots_per60_z, ca_per60_z, hdca_per60_z, sv_pct_z, gaa_z}` (skater rows have `sv_pct_z`/`gaa_z` as `null`; goalie rows have the four skater z-fields as `null`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app_rankings.py
import app as app_module
from src import database


def _seed_team_and_player(conn, player_id, team_abbrev, position_code, first, last):
    database.upsert_team(conn, {
        "team_id": player_id, "abbrev": team_abbrev, "common_name": team_abbrev,
        "place_name": team_abbrev, "conference": None, "division": None,
    })
    database.upsert_player_stub(conn, {
        "player_id": player_id, "first_name": first, "last_name": last,
        "position_code": position_code, "shoots_catches": None,
    })
    conn.execute(
        "UPDATE players SET current_team_id = ? WHERE player_id = ?",
        (player_id, player_id),
    )


def test_rankings_returns_skaters_and_goalies(conn, monkeypatch):
    _seed_team_and_player(conn, 1, "HOM", "C", "Skater", "One")
    _seed_team_and_player(conn, 2, "HOM", "G", "Goalie", "Two")
    conn.execute("""
        INSERT INTO player_rate_zscores
            (season_id, player_id, position_group, shots_per60_z, chances_per60_z,
             rebounds_created_per60_z, deflections_per60_z, points_per60_z,
             primary_points_per60_z, ca_per60_z, hdca_per60_z)
        VALUES ('20242025', 1, 'F', 0.5, 0.1, 0.2, 0.3, 0.4, 1.2, -0.6, -0.7)
    """)
    conn.execute("""
        INSERT INTO goalie_rate_zscores (season_id, player_id, sv_pct_z, gaa_z)
        VALUES ('20242025', 2, 0.9, -0.4)
    """)
    conn.commit()

    monkeypatch.setattr(app_module, "get_connection", lambda: conn)
    client = app_module.app.test_client()
    resp = client.get("/api/players/rankings?season=20242025")

    assert resp.status_code == 200
    rows = resp.get_json()
    skater = next(r for r in rows if r["player_id"] == 1)
    goalie = next(r for r in rows if r["player_id"] == 2)

    assert skater["position_group"] == "F"
    assert skater["primary_points_per60_z"] == 1.2
    assert skater["ca_per60_z"] == -0.6
    assert skater["sv_pct_z"] is None

    assert goalie["position_group"] == "G"
    assert goalie["sv_pct_z"] == 0.9
    assert goalie["gaa_z"] == -0.4
    assert goalie["primary_points_per60_z"] is None


def test_rankings_team_filter_narrows_to_one_team(conn, monkeypatch):
    _seed_team_and_player(conn, 1, "HOM", "C", "Home", "Player")
    _seed_team_and_player(conn, 2, "AWY", "C", "Away", "Player")
    for pid in (1, 2):
        conn.execute("""
            INSERT INTO player_rate_zscores
                (season_id, player_id, position_group, shots_per60_z, chances_per60_z,
                 rebounds_created_per60_z, deflections_per60_z, points_per60_z,
                 primary_points_per60_z, ca_per60_z, hdca_per60_z)
            VALUES ('20242025', ?, 'F', 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, -0.1, -0.1)
        """, (pid,))
    conn.commit()

    monkeypatch.setattr(app_module, "get_connection", lambda: conn)
    client = app_module.app.test_client()
    resp = client.get("/api/players/rankings?season=20242025&team=HOM")

    rows = resp.get_json()
    assert [r["player_id"] for r in rows] == [1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python3 -m pytest tests/test_app_rankings.py -v`
Expected: FAIL — 404 (route doesn't exist yet).

- [ ] **Step 3: Add the route**

In `app.py`, add after the existing `api_players_stats` route (after its `return jsonify(players)` / closing, i.e. after line ~239 where that function ends):

```python
@app.route("/api/players/rankings")
def api_players_rankings():
    season_id = request.args.get("season")
    team_abbrev = request.args.get("team")
    conn = get_connection()

    skater_query = """
        SELECT p.player_id, p.first_name || ' ' || p.last_name AS name,
               t.abbrev AS team_abbrev, z.position_group,
               z.primary_points_per60_z, z.shots_per60_z,
               z.ca_per60_z, z.hdca_per60_z
        FROM player_rate_zscores z
        JOIN players p ON p.player_id = z.player_id
        LEFT JOIN teams t ON p.current_team_id = t.team_id
        WHERE z.season_id = ?
    """
    params = [season_id]
    if team_abbrev:
        skater_query += " AND t.abbrev = ?"
        params.append(team_abbrev)
    skater_rows = conn.execute(skater_query, params).fetchall()

    goalie_query = """
        SELECT p.player_id, p.first_name || ' ' || p.last_name AS name,
               t.abbrev AS team_abbrev, g.sv_pct_z, g.gaa_z
        FROM goalie_rate_zscores g
        JOIN players p ON p.player_id = g.player_id
        LEFT JOIN teams t ON p.current_team_id = t.team_id
        WHERE g.season_id = ?
    """
    goalie_params = [season_id]
    if team_abbrev:
        goalie_query += " AND t.abbrev = ?"
        goalie_params.append(team_abbrev)
    goalie_rows = conn.execute(goalie_query, goalie_params).fetchall()

    conn.close()

    result = [
        {
            "player_id": r["player_id"], "name": r["name"], "team_abbrev": r["team_abbrev"],
            "position_group": r["position_group"],
            "primary_points_per60_z": r["primary_points_per60_z"],
            "shots_per60_z": r["shots_per60_z"],
            "ca_per60_z": r["ca_per60_z"], "hdca_per60_z": r["hdca_per60_z"],
            "sv_pct_z": None, "gaa_z": None,
        }
        for r in skater_rows
    ] + [
        {
            "player_id": r["player_id"], "name": r["name"], "team_abbrev": r["team_abbrev"],
            "position_group": "G",
            "primary_points_per60_z": None, "shots_per60_z": None,
            "ca_per60_z": None, "hdca_per60_z": None,
            "sv_pct_z": r["sv_pct_z"], "gaa_z": r["gaa_z"],
        }
        for r in goalie_rows
    ]
    return jsonify(result)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python3 -m pytest tests/test_app_rankings.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full backend suite**

Run: `./.venv/bin/python3 -m pytest tests/ -v --ignore=tests/test_database_libsql_adapter.py --ignore=tests/test_database_migrations_libsql.py`
Expected: all tests PASS (144 + this task's 2 new + Tasks 1/2's 5 new = adjust to actual count at run time; no regressions).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_rankings.py
git commit -m "feat: add /api/players/rankings endpoint (#116, #117)"
```

---

### Task 4: Backfill — run the ETL against the real database

**Files:**
- None (operational task — no code changes)

**Interfaces:**
- N/A — this task populates data, it doesn't change any interface.

- [ ] **Step 1: Run the ETL's aggregation/percentile/z-score step against the real database**

Run: `./.venv/bin/python3 -c "from src import database; from etl.compute_advanced_stats import _run_aggregation_and_percentiles; conn = database.get_connection(); _run_aggregation_and_percentiles(conn); conn.close()"`

- [ ] **Step 2: Verify the new columns/table actually have data for the current season**

Run:
```bash
./.venv/bin/python3 -c "
import sqlite3
conn = sqlite3.connect('data/nhl_stats.db')
print('ca_per60_z non-null count:', conn.execute(\"SELECT COUNT(*) FROM player_rate_zscores WHERE season_id='20252026' AND ca_per60_z IS NOT NULL\").fetchone()[0])
print('goalie_rate_zscores count:', conn.execute(\"SELECT COUNT(*) FROM goalie_rate_zscores WHERE season_id='20252026'\").fetchone()[0])
"
```
Expected: both counts > 0. If either is 0, stop and investigate before continuing — per this project's own documented lesson (a merged ETL feature previously sat unexecuted against the real database for weeks with passing tests the whole time), a green test suite is not evidence this step actually populated real data.

- [ ] **Step 3: No commit** (this task only mutates `data/nhl_stats.db`, which is gitignored — nothing to commit. This step must be re-run in any other environment, e.g. after a Turso sync, before the ranking pages will show real leaderboards there.)

---

### Task 5: Frontend — `lib/leaderboards.ts` (pure combine function)

**Files:**
- Create: `frontend/src/lib/leaderboards.ts`
- Create: `frontend/src/lib/leaderboards.test.ts`

**Interfaces:**
- Produces: `export interface RankingRow` (matches `/api/players/rankings`'s JSON shape exactly); `export interface RankedPlayer { player_id: number; name: string; team_abbrev: string; score: number; }`; `export function computeLeaderboards(rows: RankingRow[]): { offense: RankedPlayer[]; defense: RankedPlayer[]; goalie: RankedPlayer[] }`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/lib/leaderboards.test.ts
import { describe, it, expect } from "vitest";
import { computeLeaderboards, type RankingRow } from "./leaderboards";

function skater(overrides: Partial<RankingRow> = {}): RankingRow {
  return {
    player_id: 1, name: "Test Skater", team_abbrev: "COL", position_group: "F",
    primary_points_per60_z: 1.0, shots_per60_z: 1.0,
    ca_per60_z: 0.5, hdca_per60_z: 0.5,
    sv_pct_z: null, gaa_z: null,
    ...overrides,
  };
}

function goalie(overrides: Partial<RankingRow> = {}): RankingRow {
  return {
    player_id: 2, name: "Test Goalie", team_abbrev: "COL", position_group: "G",
    primary_points_per60_z: null, shots_per60_z: null,
    ca_per60_z: null, hdca_per60_z: null,
    sv_pct_z: 1.0, gaa_z: -1.0,
    ...overrides,
  };
}

describe("computeLeaderboards", () => {
  it("computes the offense score as the weighted sum of primary_points_per60_z and shots_per60_z", () => {
    const { offense } = computeLeaderboards([skater({ primary_points_per60_z: 2.0, shots_per60_z: 1.0 })]);
    expect(offense[0].score).toBeCloseTo(0.62 * 2.0 + 0.38 * 1.0, 5);
  });

  it("computes the defense score as the weighted sum of the NEGATED ca/hdca z-scores", () => {
    const { defense } = computeLeaderboards([skater({ ca_per60_z: 1.0, hdca_per60_z: 1.0 })]);
    // lower CA/HDCA is better -- a positive raw z (above-average shots against) must produce a NEGATIVE score
    expect(defense[0].score).toBeCloseTo(0.64 * -1.0 + 0.36 * -1.0, 5);
  });

  it("computes the goalie score from sv_pct_z and negated gaa_z", () => {
    const { goalie: goalieBoard } = computeLeaderboards([goalie({ sv_pct_z: 2.0, gaa_z: 1.0 })]);
    expect(goalieBoard[0].score).toBeCloseTo(0.67 * 2.0 + 0.33 * -1.0, 5);
  });

  it("sorts each leaderboard descending by score", () => {
    const low = skater({ player_id: 1, primary_points_per60_z: 0.1, shots_per60_z: 0.1 });
    const high = skater({ player_id: 2, primary_points_per60_z: 3.0, shots_per60_z: 3.0 });
    const { offense } = computeLeaderboards([low, high]);
    expect(offense.map((p) => p.player_id)).toEqual([2, 1]);
  });

  it("excludes goalies from offense/defense and skaters from the goalie board", () => {
    const { offense, defense, goalie: goalieBoard } = computeLeaderboards([skater(), goalie()]);
    expect(offense.every((p) => p.player_id !== 2)).toBe(true);
    expect(defense.every((p) => p.player_id !== 2)).toBe(true);
    expect(goalieBoard.every((p) => p.player_id !== 1)).toBe(true);
  });

  it("excludes a row from a leaderboard when its required z-score fields are null", () => {
    const { offense } = computeLeaderboards([skater({ primary_points_per60_z: null })]);
    expect(offense).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/leaderboards.test.ts`
Expected: FAIL — `Failed to resolve import "./leaderboards"`.

- [ ] **Step 3: Write the implementation**

```ts
// frontend/src/lib/leaderboards.ts
export interface RankingRow {
  player_id: number;
  name: string;
  team_abbrev: string;
  position_group: "F" | "D" | "G";
  primary_points_per60_z: number | null;
  shots_per60_z: number | null;
  ca_per60_z: number | null;
  hdca_per60_z: number | null;
  sv_pct_z: number | null;
  gaa_z: number | null;
}

export interface RankedPlayer {
  player_id: number;
  name: string;
  team_abbrev: string;
  score: number;
}

const OFFENSE_WEIGHTS = { primaryPoints: 0.62, shots: 0.38 };
const DEFENSE_WEIGHTS = { ca: 0.64, hdca: 0.36 };
const GOALIE_WEIGHTS = { svPct: 0.67, gaa: 0.33 };

function toRankedPlayer(row: RankingRow, score: number): RankedPlayer {
  return { player_id: row.player_id, name: row.name, team_abbrev: row.team_abbrev, score };
}

function sortDescending(players: RankedPlayer[]): RankedPlayer[] {
  return [...players].sort((a, b) => b.score - a.score);
}

export function computeLeaderboards(rows: RankingRow[]): {
  offense: RankedPlayer[];
  defense: RankedPlayer[];
  goalie: RankedPlayer[];
} {
  const skaters = rows.filter((r) => r.position_group === "F" || r.position_group === "D");
  const goalies = rows.filter((r) => r.position_group === "G");

  const offense = sortDescending(
    skaters
      .filter((r): r is RankingRow & { primary_points_per60_z: number; shots_per60_z: number } =>
        r.primary_points_per60_z != null && r.shots_per60_z != null
      )
      .map((r) =>
        toRankedPlayer(
          r,
          OFFENSE_WEIGHTS.primaryPoints * r.primary_points_per60_z +
            OFFENSE_WEIGHTS.shots * r.shots_per60_z
        )
      )
  );

  const defense = sortDescending(
    skaters
      .filter((r): r is RankingRow & { ca_per60_z: number; hdca_per60_z: number } =>
        r.ca_per60_z != null && r.hdca_per60_z != null
      )
      .map((r) =>
        toRankedPlayer(r, DEFENSE_WEIGHTS.ca * -r.ca_per60_z + DEFENSE_WEIGHTS.hdca * -r.hdca_per60_z)
      )
  );

  const goalie = sortDescending(
    goalies
      .filter((r): r is RankingRow & { sv_pct_z: number; gaa_z: number } =>
        r.sv_pct_z != null && r.gaa_z != null
      )
      .map((r) => toRankedPlayer(r, GOALIE_WEIGHTS.svPct * r.sv_pct_z + GOALIE_WEIGHTS.gaa * -r.gaa_z))
  );

  return { offense, defense, goalie };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/leaderboards.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/leaderboards.ts frontend/src/lib/leaderboards.test.ts
git commit -m "feat: add computeLeaderboards pure function (#116, #117)"
```

---

### Task 6: Frontend — `components/Leaderboard.tsx`

**Files:**
- Create: `frontend/src/components/Leaderboard.tsx`
- Create: `frontend/src/components/Leaderboard.test.tsx`

**Interfaces:**
- Consumes: `RankedPlayer` from `@/lib/leaderboards` (Task 5).
- Produces: `export function Leaderboard({ title, players, onSelectPlayer }: { title: string; players: RankedPlayer[]; onSelectPlayer: (playerId: number) => void })`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/Leaderboard.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Leaderboard } from "./Leaderboard";
import type { RankedPlayer } from "@/lib/leaderboards";

const PLAYERS: RankedPlayer[] = [
  { player_id: 1, name: "Nathan MacKinnon", team_abbrev: "COL", score: 2.1 },
  { player_id: 2, name: "Cale Makar", team_abbrev: "COL", score: 1.4 },
];

describe("Leaderboard", () => {
  it("renders the title and players in the given order", () => {
    render(<Leaderboard title="Top Offense" players={PLAYERS} onSelectPlayer={() => {}} />);
    expect(screen.getByText("Top Offense")).toBeInTheDocument();
    const rows = screen.getAllByRole("button");
    expect(rows[0]).toHaveTextContent("Nathan MacKinnon");
    expect(rows[1]).toHaveTextContent("Cale Makar");
  });

  it("calls onSelectPlayer with the correct player_id when a row is clicked", async () => {
    const onSelectPlayer = vi.fn();
    render(<Leaderboard title="Top Offense" players={PLAYERS} onSelectPlayer={onSelectPlayer} />);
    await userEvent.click(screen.getByText("Cale Makar"));
    expect(onSelectPlayer).toHaveBeenCalledWith(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/Leaderboard.test.tsx`
Expected: FAIL — `Failed to resolve import "./Leaderboard"`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/components/Leaderboard.tsx
import type { RankedPlayer } from "@/lib/leaderboards";

interface LeaderboardProps {
  title: string;
  players: RankedPlayer[];
  onSelectPlayer: (playerId: number) => void;
}

export function Leaderboard({ title, players, onSelectPlayer }: LeaderboardProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      <ol className="flex flex-col gap-1">
        {players.map((p, i) => (
          <li key={p.player_id}>
            <button
              type="button"
              onClick={() => onSelectPlayer(p.player_id)}
              className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
            >
              <span>
                <span className="mr-2 text-muted-foreground">{i + 1}.</span>
                {p.name}
                <span className="ml-2 text-muted-foreground">{p.team_abbrev}</span>
              </span>
              <span className="font-mono text-muted-foreground">{p.score.toFixed(2)}</span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/Leaderboard.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Leaderboard.tsx frontend/src/components/Leaderboard.test.tsx
git commit -m "feat: add Leaderboard component (#116, #117)"
```

---

### Task 7: Frontend — shared latest-season constant

**Files:**
- Create: `frontend/src/lib/season.ts`

**Interfaces:**
- Produces: `export const LATEST_SEASON_ID = "20252026";`

- [ ] **Step 1: Create the file**

```ts
// frontend/src/lib/season.ts
// Matches the hardcoded default season used elsewhere in the app
// (Players.tsx, SeasonPicker.tsx) -- there is no backend "latest season"
// concept yet (see the design spec's Decision 2 for why). Centralized here
// so the two new ranking pages (TeamPage, TopPlayers) share one constant
// instead of duplicating the literal a second and third time.
export const LATEST_SEASON_ID = "20252026";
```

- [ ] **Step 2: No test needed** (a single exported string literal has no behavior to test).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/season.ts
git commit -m "chore: add shared LATEST_SEASON_ID constant for ranking pages"
```

---

### Task 8: Frontend — `pages/TeamPage.tsx`

**Files:**
- Create: `frontend/src/pages/TeamPage.tsx`
- Create: `frontend/src/pages/TeamPage.test.tsx`

**Interfaces:**
- Consumes: `computeLeaderboards`/`RankingRow` (Task 5), `Leaderboard` (Task 6), `LATEST_SEASON_ID` (Task 7), `teamColors`/`logoUrl` from `@/lib/teamBranding` (existing), `PlayerProfilePanel` (existing, `frontend/src/components/PlayerProfilePanel.tsx`), `Team`/`Player`/`PlayerStats` types (existing, `@/lib/types`).
- Produces: `export default function TeamPage()` — reads `:teamId` via `useParams`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/pages/TeamPage.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import TeamPage from "./TeamPage";

const TEAMS = [{ abbrev: "COL", common_name: "Colorado Avalanche" }];
const PLAYERS = [
  { player_id: 1, first_name: "Nathan", last_name: "MacKinnon", team_abbrev: "COL" },
];
const STATS = [{ player_id: 1, team_abbrev: "COL", points: 100 }];
const RANKINGS = [
  {
    player_id: 1, name: "Nathan MacKinnon", team_abbrev: "COL", position_group: "F",
    primary_points_per60_z: 2.0, shots_per60_z: 1.5,
    ca_per60_z: -0.5, hdca_per60_z: -0.3,
    sv_pct_z: null, gaa_z: null,
  },
];

function mockFetchOnce(url: string) {
  if (url.includes("/api/teams")) return Promise.resolve({ ok: true, json: () => Promise.resolve(TEAMS) } as Response);
  if (url.includes("/api/players/rankings")) return Promise.resolve({ ok: true, json: () => Promise.resolve(RANKINGS) } as Response);
  if (url.includes("/api/players/stats")) return Promise.resolve({ ok: true, json: () => Promise.resolve(STATS) } as Response);
  if (url.includes("/api/players")) return Promise.resolve({ ok: true, json: () => Promise.resolve(PLAYERS) } as Response);
  return Promise.reject(new Error(`unexpected url: ${url}`));
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url: string) => mockFetchOnce(url)));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TeamPage", () => {
  it("fetches team-scoped rankings and renders three leaderboards with the team's branded name", async () => {
    render(
      <MemoryRouter initialEntries={["/teams/COL"]}>
        <Routes>
          <Route path="/teams/:teamId" element={<TeamPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("Colorado Avalanche")).toBeInTheDocument();
    expect(screen.getByText("Top Offense")).toBeInTheDocument();
    expect(screen.getByText("Top Defense")).toBeInTheDocument();
    expect(screen.getByText("Top Goalie")).toBeInTheDocument();
    expect(await screen.findByText("Nathan MacKinnon")).toBeInTheDocument();

    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    const rankingsCall = fetchMock.mock.calls.find((c) => String(c[0]).includes("/api/players/rankings"));
    expect(rankingsCall![0]).toContain("team=COL");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/TeamPage.test.tsx`
Expected: FAIL — `Failed to resolve import "./TeamPage"`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/pages/TeamPage.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Leaderboard } from "@/components/Leaderboard";
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
import { computeLeaderboards, type RankingRow } from "@/lib/leaderboards";
import { LATEST_SEASON_ID } from "@/lib/season";
import { teamColors, logoUrl } from "@/lib/teamBranding";
import type { Team, Player, PlayerStats } from "@/lib/types";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request to ${url} failed (${res.status})`);
  return res.json() as Promise<T>;
}

export default function TeamPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const [teams, setTeams] = useState<Team[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [stats, setStats] = useState<PlayerStats[]>([]);
  const [rankings, setRankings] = useState<RankingRow[]>([]);
  const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);

  useEffect(() => {
    if (!teamId) return;
    fetchJson<Team[]>("/api/teams").then(setTeams);
    fetchJson<Player[]>("/api/players").then(setPlayers);
    fetchJson<PlayerStats[]>(`/api/players/stats?seasons=${LATEST_SEASON_ID}`).then(setStats);
    fetchJson<RankingRow[]>(
      `/api/players/rankings?season=${LATEST_SEASON_ID}&team=${teamId}`
    ).then(setRankings);
  }, [teamId]);

  if (!teamId) return null;

  const team = teams.find((t) => t.abbrev === teamId);
  const colors = teamColors(teamId);
  const { offense, defense, goalie } = computeLeaderboards(rankings);

  const bio = players.find((p) => p.player_id === profilePlayerId);
  const playerStats = stats.find((s) => s.player_id === profilePlayerId);

  return (
    <div>
      <div
        className="flex items-center gap-4 p-6"
        style={colors ? { backgroundColor: colors.primary, color: "#fff" } : undefined}
      >
        <img src={logoUrl(teamId)} alt={`${teamId} logo`} className="h-16 w-16" />
        <h1 className="text-2xl font-bold">{team?.common_name ?? teamId}</h1>
      </div>
      <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-3">
        <Leaderboard title="Top Offense" players={offense.slice(0, 5)} onSelectPlayer={setProfilePlayerId} />
        <Leaderboard title="Top Defense" players={defense.slice(0, 5)} onSelectPlayer={setProfilePlayerId} />
        <Leaderboard title="Top Goalie" players={goalie.slice(0, 5)} onSelectPlayer={setProfilePlayerId} />
      </div>
      {profilePlayerId !== null && (
        <PlayerProfilePanel
          open={profilePlayerId !== null}
          playerId={profilePlayerId}
          bio={bio}
          stats={playerStats}
          onOpenChange={(open) => {
            if (!open) setProfilePlayerId(null);
          }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/TeamPage.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/TeamPage.tsx frontend/src/pages/TeamPage.test.tsx
git commit -m "feat: add TeamPage with branded header and three leaderboards (#116)"
```

---

### Task 9: Frontend — `pages/Teams.tsx` (picker grid)

**Files:**
- Create: `frontend/src/pages/Teams.tsx`
- Create: `frontend/src/pages/Teams.test.tsx`

**Interfaces:**
- Consumes: `teamColors`/`logoUrl` from `@/lib/teamBranding`, `Team` type from `@/lib/types`.
- Produces: `export default function Teams()`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/pages/Teams.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Teams from "./Teams";

const TEAMS = [
  { abbrev: "COL", common_name: "Colorado Avalanche" },
  { abbrev: "TOR", common_name: "Toronto Maple Leafs" },
];

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(TEAMS) } as Response))
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Teams", () => {
  it("renders a card linking to /teams/:abbrev for every fetched team", async () => {
    render(
      <MemoryRouter>
        <Teams />
      </MemoryRouter>
    );

    const link = await screen.findByRole("link", { name: /Colorado Avalanche/i });
    expect(link).toHaveAttribute("href", "/teams/COL");
    expect(screen.getByRole("link", { name: /Toronto Maple Leafs/i })).toHaveAttribute(
      "href",
      "/teams/TOR"
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Teams.test.tsx`
Expected: FAIL — `Failed to resolve import "./Teams"`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/pages/Teams.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { teamColors, logoUrl } from "@/lib/teamBranding";
import type { Team } from "@/lib/types";

export default function Teams() {
  const [teams, setTeams] = useState<Team[]>([]);

  useEffect(() => {
    fetch("/api/teams")
      .then((res) => res.json())
      .then(setTeams);
  }, []);

  return (
    <div className="grid grid-cols-2 gap-4 p-6 sm:grid-cols-4 lg:grid-cols-6">
      {teams.map((team) => {
        const colors = teamColors(team.abbrev);
        return (
          <Link
            key={team.abbrev}
            to={`/teams/${team.abbrev}`}
            className="flex flex-col items-center gap-2 rounded-lg border border-border p-4 text-center transition-colors hover:bg-muted"
            style={colors ? { borderTopColor: colors.primary, borderTopWidth: "4px" } : undefined}
          >
            <img src={logoUrl(team.abbrev)} alt={`${team.abbrev} logo`} className="h-12 w-12" />
            <span className="text-sm font-medium">{team.common_name}</span>
          </Link>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Teams.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Teams.tsx frontend/src/pages/Teams.test.tsx
git commit -m "feat: add Teams picker grid page (#116)"
```

---

### Task 10: Frontend — `pages/TopPlayers.tsx`

**Files:**
- Create: `frontend/src/pages/TopPlayers.tsx`
- Create: `frontend/src/pages/TopPlayers.test.tsx`

**Interfaces:**
- Consumes: same as Task 8 (`computeLeaderboards`, `Leaderboard`, `LATEST_SEASON_ID`, `PlayerProfilePanel`), minus team branding/`useParams` (this page is unscoped).
- Produces: `export default function TopPlayers()`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/pages/TopPlayers.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import TopPlayers from "./TopPlayers";

const PLAYERS = [{ player_id: 1, first_name: "Nathan", last_name: "MacKinnon", team_abbrev: "COL" }];
const STATS = [{ player_id: 1, team_abbrev: "COL", points: 100 }];
const RANKINGS = [
  {
    player_id: 1, name: "Nathan MacKinnon", team_abbrev: "COL", position_group: "F",
    primary_points_per60_z: 2.0, shots_per60_z: 1.5,
    ca_per60_z: -0.5, hdca_per60_z: -0.3,
    sv_pct_z: null, gaa_z: null,
  },
];

function mockFetchOnce(url: string) {
  if (url.includes("/api/players/rankings")) return Promise.resolve({ ok: true, json: () => Promise.resolve(RANKINGS) } as Response);
  if (url.includes("/api/players/stats")) return Promise.resolve({ ok: true, json: () => Promise.resolve(STATS) } as Response);
  if (url.includes("/api/players")) return Promise.resolve({ ok: true, json: () => Promise.resolve(PLAYERS) } as Response);
  return Promise.reject(new Error(`unexpected url: ${url}`));
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url: string) => mockFetchOnce(url)));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TopPlayers", () => {
  it("fetches league-wide rankings (no team filter) and renders three leaderboards", async () => {
    render(
      <MemoryRouter>
        <TopPlayers />
      </MemoryRouter>
    );

    expect(screen.getByText("Top Offense")).toBeInTheDocument();
    expect(screen.getByText("Top Defense")).toBeInTheDocument();
    expect(screen.getByText("Top Goalie")).toBeInTheDocument();
    expect(await screen.findByText("Nathan MacKinnon")).toBeInTheDocument();

    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    const rankingsCall = fetchMock.mock.calls.find((c) => String(c[0]).includes("/api/players/rankings"));
    expect(rankingsCall![0]).not.toContain("team=");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/TopPlayers.test.tsx`
Expected: FAIL — `Failed to resolve import "./TopPlayers"`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/pages/TopPlayers.tsx
import { useEffect, useState } from "react";
import { Leaderboard } from "@/components/Leaderboard";
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
import { computeLeaderboards, type RankingRow } from "@/lib/leaderboards";
import { LATEST_SEASON_ID } from "@/lib/season";
import type { Player, PlayerStats } from "@/lib/types";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request to ${url} failed (${res.status})`);
  return res.json() as Promise<T>;
}

export default function TopPlayers() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [stats, setStats] = useState<PlayerStats[]>([]);
  const [rankings, setRankings] = useState<RankingRow[]>([]);
  const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);

  useEffect(() => {
    fetchJson<Player[]>("/api/players").then(setPlayers);
    fetchJson<PlayerStats[]>(`/api/players/stats?seasons=${LATEST_SEASON_ID}`).then(setStats);
    fetchJson<RankingRow[]>(`/api/players/rankings?season=${LATEST_SEASON_ID}`).then(setRankings);
  }, []);

  const { offense, defense, goalie } = computeLeaderboards(rankings);
  const bio = players.find((p) => p.player_id === profilePlayerId);
  const playerStats = stats.find((s) => s.player_id === profilePlayerId);

  return (
    <div>
      <h1 className="p-6 text-2xl font-bold">Top Players</h1>
      <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-3">
        <Leaderboard title="Top Offense" players={offense.slice(0, 15)} onSelectPlayer={setProfilePlayerId} />
        <Leaderboard title="Top Defense" players={defense.slice(0, 15)} onSelectPlayer={setProfilePlayerId} />
        <Leaderboard title="Top Goalie" players={goalie.slice(0, 15)} onSelectPlayer={setProfilePlayerId} />
      </div>
      {profilePlayerId !== null && (
        <PlayerProfilePanel
          open={profilePlayerId !== null}
          playerId={profilePlayerId}
          bio={bio}
          stats={playerStats}
          onOpenChange={(open) => {
            if (!open) setProfilePlayerId(null);
          }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/TopPlayers.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/TopPlayers.tsx frontend/src/pages/TopPlayers.test.tsx
git commit -m "feat: add TopPlayers league-wide leaderboard page (#117)"
```

---

### Task 11: Wire routes into `main.tsx`

**Files:**
- Modify: `frontend/src/main.tsx`

**Interfaces:**
- Consumes: `Teams` (Task 9), `TeamPage` (Task 8), `TopPlayers` (Task 10).

- [ ] **Step 1: Update the route table**

Replace the current `teams`/`top-players` `PlaceholderPage` routes in `frontend/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import App from "./App";
import Home from "./pages/Home";
import Players from "./pages/Players";
import Teams from "./pages/Teams";
import TeamPage from "./pages/TeamPage";
import TopPlayers from "./pages/TopPlayers";
import PlaceholderPage from "./pages/PlaceholderPage";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<Home />} />
          <Route path="players" element={<Players />} />
          <Route path="teams" element={<Teams />} />
          <Route path="teams/:teamId" element={<TeamPage />} />
          <Route path="top-players" element={<TopPlayers />} />
          <Route path="betting" element={<PlaceholderPage title="Betting" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>
);
```

- [ ] **Step 2: Run the full frontend suite**

Run: `cd frontend && npm test`
Expected: all tests PASS — every new suite from Tasks 5-10, plus every pre-existing suite untouched by this branch.

- [ ] **Step 3: Run the build**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors.

- [ ] **Step 4: Run the full backend suite once more**

Run: `./.venv/bin/python3 -m pytest tests/ -v --ignore=tests/test_database_libsql_adapter.py --ignore=tests/test_database_migrations_libsql.py`
Expected: all tests PASS.

- [ ] **Step 5: Manual smoke check**

Run: `cd frontend && npm run dev` (and `./.venv/bin/python3 app.py` in a second terminal), then in a browser:
- Visit `/teams` → grid of 32 branded team cards.
- Click a team → `/teams/<abbrev>` shows the branded header and three leaderboards with real players (assuming Task 4's backfill ran).
- Visit `/top-players` → three leaderboards, more players per list than a team page.
- Click a leaderboard row on either page → the existing player profile overlay opens with the right player.
- Hard-refresh on `/teams/COL` (or any team) → resolves correctly via Group 1's Flask fallback (Task 1 of the header-nav plan), not a 404.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/main.tsx
git commit -m "feat: wire Teams/TeamPage/TopPlayers into the route table (#116, #117)"
```

---

## Plan Self-Review Notes

- **Spec coverage:** ETL extension for Offense/Defense fields (Task 1), goalie z-scores (Task 2), backend rankings endpoint (Task 3), real-data backfill (Task 4), pure combine function (Task 5), Leaderboard component (Task 6), shared season constant (Task 7), TeamPage with branding (Task 8), Teams picker (Task 9), TopPlayers (Task 10), routing (Task 11). All spec sections have a task. Out-of-scope items (full xG model, blended scores, configurable weights) are correctly not implemented anywhere in this plan.
- **Type consistency:** `RankingRow` (Task 5) matches the exact JSON shape `/api/players/rankings` (Task 3) returns — field names and nullability verified against the endpoint's `jsonify(result)` construction. `RankedPlayer`'s fields (`player_id`, `name`, `team_abbrev`, `score`) are consumed identically by `Leaderboard` (Task 6), `TeamPage` (Task 8), and `TopPlayers` (Task 10).
- **Pattern verification:** `TeamPage`/`TopPlayers`'s `profilePlayerId` + `PlayerProfilePanel` wiring was checked directly against `Players.tsx`'s existing usage (read during grilling) — same `open`/`playerId`/`bio`/`stats`/`onOpenChange` prop shape, same "look up bio and stats separately by player_id from two independently-fetched collections" pattern, not assumed from the spec's prose description alone. The ETL migration/upsert/CREATE-table extension pattern (Tasks 1-2) was verified against the actual current `_ADVANCED_STATS_MIGRATIONS` list and `upsert_player_rate_zscores` function content, not inferred.
