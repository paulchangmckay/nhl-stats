# Historical Data Expansion (2017-18 to 2019-20) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 3 more historical NHL seasons (2017-18, 2018-19, 2019-20) to the database, and fix a confirmed data-quality gap (high-danger stats silently reading as misleadingly-low instead of missing) for the two seasons where the source API never provided rink-side data.

**Architecture:** Two independent pieces bundled into one plan because the second is a direct prerequisite for the first being *correct*: (1) a small, TDD'd code change to `etl/advanced_stats/sweep.py` and `etl/compute_advanced_stats.py` so a game with zero rink-side coverage on its shot-attempt plays stores high-danger stats as `NULL` instead of a computed `0`, and (2) extending three hardcoded `SEASONS` constants, then running the existing documented one-time historical-backfill pipeline against them.

**Tech Stack:** Python (sqlite3, pytest), TypeScript/React (Vitest), NHL public REST API (`api-web.nhle.com`, `api.nhle.com/stats/rest`).

## Global Constraints

- No new scripts, no CLI-configurable season ranges — `SEASONS` lists stay hardcoded constants (spec's explicit non-goal).
- `"20252026"` must remain the **last** entry in `etl/load_season_stats.py`'s `SEASONS` list — `run()`'s `current_season = SEASONS[-1]` logic depends on this position.
- No changes to `run_all_etl.py` or `scripts/sync.py` — both already iterate the `SEASONS`/`sync_log` state and pick up new seasons automatically.
- Every ETL step touched here is already idempotent/resumable — nothing in this plan should break that property.
- Full regression suite (`pytest tests/ -v`, `cd frontend && npm test`) must pass before the backfill (Task 5) is considered done. (The README also documents `node --test tests/js/search.test.js`, but that file doesn't exist anywhere in the repo — confirmed during the final whole-branch review. Pre-existing doc/reality drift, not introduced by this plan; dropped from this gate rather than perpetuated.)

---

### Task 1: HD-stat NULL propagation in `etl/advanced_stats/sweep.py`

**Files:**
- Modify: `etl/advanced_stats/sweep.py:41-226` (`compute_game_advanced_stats`)
- Test: `tests/test_sweep.py`

**Interfaces:**
- Consumes: existing `compute_game_advanced_stats(shifts, events, home_team_id, game_type)` signature — unchanged.
- Produces: player rows from `compute_game_advanced_stats` now have `hdcf`/`hdca`/`ihdcf` as `None` (instead of `0`) for any game where zero shot-attempt-type events (`shot-on-goal`/`missed-shot`/`blocked-shot`/`goal`) carry a non-null `home_team_defending_side`. Task 2 and Task 3 depend on this: they must treat `hdcf`/`hdca`/`ihdcf` as possibly-`None` wherever they're read.

- [ ] **Step 1: Extend the `_event()` test helper to allow overriding `home_team_defending_side`**

In `tests/test_sweep.py`, replace the existing `_event()` helper (lines 12-20):

```python
def _event(event_type, period, time_in_period, situation_code, event_owner_team_id,
           x_coord=0, y_coord=0, shooting_player_id=None, assist1_player_id=None,
           assist2_player_id=None, shot_type=None, home_team_defending_side="right"):
    return {"event_type": event_type, "period": period, "time_in_period": time_in_period,
            "situation_code": situation_code, "event_owner_team_id": event_owner_team_id,
            "x_coord": x_coord, "y_coord": y_coord,
            "shooting_player_id": shooting_player_id, "assist1_player_id": assist1_player_id,
            "assist2_player_id": assist2_player_id, "shot_type": shot_type,
            "home_team_defending_side": home_team_defending_side}
```

This is backward-compatible — every existing call site that doesn't pass `home_team_defending_side` keeps getting `"right"`, same as before.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_sweep.py`:

```python
def test_hd_stats_null_when_game_has_no_rink_side_data():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, AWAY, 1, "00:00", "20:00")]
    events = [_event("shot-on-goal", 1, "00:10", "1551", HOME, x_coord=-85, y_coord=0,
                      shooting_player_id=1, home_team_defending_side=None)]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)

    home_row = next(r for r in player_rows if r["player_id"] == 1)
    assert home_row["cf"] == 1  # Corsi doesn't need rink side -- unaffected
    assert home_row["icf"] == 1
    assert home_row["hdcf"] is None
    assert home_row["ihdcf"] is None

    away_row = next(r for r in player_rows if r["player_id"] == 2)
    assert away_row["ca"] == 1  # Corsi against unaffected
    assert away_row["hdca"] is None


def test_hd_stats_still_computed_when_game_has_rink_side_data():
    shifts = [_shift(1, HOME, 1, "00:00", "20:00"), _shift(2, AWAY, 1, "00:00", "20:00")]
    events = [_event("shot-on-goal", 1, "00:10", "1551", HOME, x_coord=-85, y_coord=0,
                      shooting_player_id=1, home_team_defending_side="right")]

    player_rows, _ = compute_game_advanced_stats(shifts, events, home_team_id=HOME, game_type=2)

    home_row = next(r for r in player_rows if r["player_id"] == 1)
    assert home_row["hdcf"] == 1
    assert home_row["ihdcf"] == 1
```

(`x_coord=-85` with `home_team_defending_side="right"` and a home shooter matches the coordinate convention already established in `test_individual_high_danger_and_deflection_credit` — the shot normalizes to the attacking-positive-x zone, `x=85 >= HIGH_DANGER_X_MIN(69)`.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd "/Users/paulmckay/Desktop/NHL Stats Project" && source .venv/bin/activate && python -m pytest tests/test_sweep.py -v -k hd_stats`
Expected: both new tests FAIL — `test_hd_stats_null_when_game_has_no_rink_side_data` fails because `home_row["hdcf"]` is `0`, not `None` (current code has no NULL-propagation yet); `test_hd_stats_still_computed_when_game_has_rink_side_data` should already PASS (it documents existing behavior) — if it doesn't, something is wrong with the coordinate assumption and needs fixing before proceeding.

- [ ] **Step 4: Implement the minimal fix**

In `etl/advanced_stats/sweep.py`, after the `event_list.sort(key=lambda e: e["t"])` line (currently line 61), add:

```python
    game_has_rink_side_data = any(
        e["event_type"] in SHOT_ATTEMPT_TYPES and e.get("home_team_defending_side") is not None
        for e in event_list
    )
```

Then, immediately before the final `return list(player_stats.values()), list(team_stats.values())` line (currently line 226), add:

```python
    if not game_has_rink_side_data:
        for row in player_stats.values():
            row["hdcf"] = None
            row["hdca"] = None
            row["ihdcf"] = None

```

Team rows (`team_row()`) don't carry `hdcf`/`hdca` fields at all (only players do), so no change is needed there.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_sweep.py -v`
Expected: all tests in the file PASS (the 2 new ones plus all pre-existing ones, unaffected).

- [ ] **Step 6: Commit**

```bash
git add etl/advanced_stats/sweep.py tests/test_sweep.py
git commit -m "Propagate NULL for HD stats when a game has zero rink-side data

_is_high_danger() already returned False (not None) when
home_team_defending_side was missing, so a game with no rink-side data at
all would silently compute hdcf/hdca/ihdcf to 0 -- indistinguishable from
a real (if implausible) zero-high-danger-chances game. Detect once per
game whether any shot-attempt play carries the field, and null out the
HD-derived fields for that game's player rows if not."
```

---

### Task 2: None-safe percentile computation in `etl/compute_advanced_stats.py`

**Files:**
- Modify: `etl/compute_advanced_stats.py:126-166` (`compute_percentiles`)
- Test: `tests/test_compute_advanced_stats.py`

**Interfaces:**
- Consumes: `player_season_advanced_stats.hdcf`/`hdca` columns, which (via `SUM()` over Task 1's now-nullable per-game rows) can be `None` when every game contributing to that player-season-strength_state group had no rink-side data at all.
- Produces: `player_advanced_percentiles.hdcf_pct_pctile` is `None` for players with no HD data for the season, and excludes them from the ranking population used for everyone else's `hdcf_pct_pctile` — `cf_pct_pctile`/`ff_pct_pctile`/`primary_points_pctile` are completely unaffected (unchanged).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compute_advanced_stats.py`:

```python
def test_compute_percentiles_hdcf_pctile_null_when_hdcf_null_excluded_from_population(conn):
    # Player 1 and 2 have real HD data; player 3's season HD data is NULL
    # (e.g. a 2017-18/2018-19 season with zero rink-side coverage all year).
    for player_id, hdcf, hdca in [(1, 8, 2), (2, 4, 4)]:
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        conn.execute("""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
            VALUES (?, '20172018', 2, 'HOM', '5v5', 20, 10, 20, 10, ?, ?, 1, 1, 1, 900, 12)
        """, (player_id, hdcf, hdca))
    database.upsert_player_stub(conn, {
        "player_id": 3, "first_name": "P", "last_name": "3",
        "position_code": "C", "shoots_catches": None,
    })
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp)
        VALUES (3, '20172018', 2, 'HOM', '5v5', 20, 10, 20, 10, NULL, NULL, 1, 1, 1, 900, 12)
    """)
    conn.commit()

    module.compute_percentiles(conn, season_id="20172018")

    p1 = conn.execute(
        "SELECT hdcf_pct_pctile FROM player_advanced_percentiles WHERE player_id = 1"
    ).fetchone()
    p3 = conn.execute(
        "SELECT hdcf_pct_pctile FROM player_advanced_percentiles WHERE player_id = 3"
    ).fetchone()
    assert p1["hdcf_pct_pctile"] == 100.0  # ranked only against player 2, unaffected by player 3
    assert p3["hdcf_pct_pctile"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v -k hdcf_pctile_null`
Expected: FAIL with `TypeError: unsupported operand type(s) for +: 'NoneType' and 'NoneType'` (from `_hd_pct_of`'s `row["hdcf"] + row["hdca"]` when both are `None`), or a `TypeError` from `sorted()` inside `_percentile_rank` if it gets that far.

- [ ] **Step 3: Implement the minimal fix**

In `etl/compute_advanced_stats.py`, replace the `_hd_pct_of` function (currently lines 149-150):

```python
            def _hd_pct_of(row):
                if row["hdcf"] is None or row["hdca"] is None:
                    return None
                return row["hdcf"] / (row["hdcf"] + row["hdca"]) if (row["hdcf"] + row["hdca"]) else 0
```

Replace the population-building line (currently line 154):

```python
            all_hdcf_pct = [v for v in (_hd_pct_of(r) for r in rows) if v is not None]
```

Replace the per-row upsert loop (currently lines 157-165):

```python
            for r in rows:
                hd_pct = _hd_pct_of(r)
                database.upsert_player_advanced_percentiles(conn, {
                    "season_id": season_id, "player_id": r["player_id"],
                    "strength_state": strength_state, "position_group": position_group,
                    "cf_pct_pctile": _percentile_rank(_pct_of(r), all_cf_pct),
                    "ff_pct_pctile": _percentile_rank(_fen_pct_of(r), all_ff_pct),
                    "hdcf_pct_pctile": _percentile_rank(hd_pct, all_hdcf_pct) if hd_pct is not None else None,
                    "primary_points_pctile": _percentile_rank(r["primary_points"], all_pp),
                })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v -k hdcf_pctile_null`
Expected: PASS.

- [ ] **Step 5: Run the full test file to check for regressions**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v`
Expected: all tests PASS, including `test_compute_percentiles_ranks_three_player_population` and `test_compute_percentiles_excludes_players_below_gp_floor` (unaffected — they use real integer `hdcf`/`hdca` values, never `None`).

- [ ] **Step 6: Commit**

```bash
git add etl/compute_advanced_stats.py tests/test_compute_advanced_stats.py
git commit -m "None-safe hdcf_pct_pctile computation

SUM(pgas.hdcf) over an all-NULL season (Task 1's per-game NULL for
zero-rink-side-data games) returns NULL, which crashed _hd_pct_of's
addition and would have crashed sorted() in _percentile_rank. Guard the
None case, exclude None-HD players from the ranking population, and
leave their own hdcf_pct_pctile as NULL rather than crashing or
computing a misleading value."
```

---

### Task 3: None-safe z-score computation in `etl/compute_advanced_stats.py`

**Files:**
- Modify: `etl/compute_advanced_stats.py:169-203` (`compute_zscores`)
- Test: `tests/test_compute_advanced_stats.py`

**Interfaces:**
- Consumes: `player_season_advanced_stats.ihdcf`, which can now be `None` for the same reason as Task 2 (`chances_per60_z` is the only one of the 6 rate fields keyed on an HD-derived column — `icf`/`rebounds_created`/`deflections`/`points`/`primary_points` are never nulled by Task 1 and need no change).
- Produces: `player_rate_zscores.chances_per60_z` is `None` for a player whose season `ihdcf` is `None`; their other 5 rate z-scores are computed normally and unaffected.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_compute_advanced_stats.py`:

```python
def test_compute_zscores_chances_per60_z_null_when_ihdcf_null(conn):
    # 20 qualifying players (meets ZSCORE_MIN_POPULATION); player 1's ihdcf
    # is NULL (e.g. a fully rink-side-missing season) while everyone else's
    # is real -- player 1 should get chances_per60_z = NULL but a normal
    # shots_per60_z (icf-based, unaffected by the HD-only NULL).
    for player_id in range(1, 21):
        database.upsert_player_stub(conn, {
            "player_id": player_id, "first_name": "P", "last_name": str(player_id),
            "position_code": "C", "shoots_catches": None,
        })
        ihdcf = "NULL" if player_id == 1 else str(player_id)
        conn.execute(f"""
            INSERT INTO player_season_advanced_stats
                (player_id, season_id, game_type, team_abbrevs, strength_state,
                 cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
                 icf, ihdcf, rebounds_created, deflections, points)
            VALUES (?, '20172018', 2, 'HOM', '5v5', 1,1,1,1,1,1,1,1,1, 3600, 12,
                    ?, {ihdcf}, 3, 1, 1, 5)
        """, (player_id, player_id))
    conn.commit()

    module.compute_zscores(conn, season_id="20172018")

    p1 = conn.execute(
        "SELECT chances_per60_z, shots_per60_z FROM player_rate_zscores WHERE player_id = 1"
    ).fetchone()
    assert p1["chances_per60_z"] is None
    assert p1["shots_per60_z"] is not None  # icf-based, unaffected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v -k chances_per60_z_null`
Expected: FAIL with `TypeError: unsupported operand type(s) for /: 'NoneType' and 'float'` from `_rate()`'s division when `row["ihdcf"]` is `None`.

- [ ] **Step 3: Implement the minimal fix**

In `etl/compute_advanced_stats.py`, replace the `_rate` function (currently lines 191-192):

```python
        def _rate(row, count_key):
            if row[count_key] is None:
                return None
            return row[count_key] / (row["toi_seconds"] / 3600.0)
```

Replace the `populations` dict comprehension (currently lines 194-195):

```python
        populations = {
            z_key: [v for v in (_rate(r, count_key) for r in rows) if v is not None]
            for z_key, count_key in rate_fields.items()
        }
```

Replace the per-row record-building loop (currently lines 197-202):

```python
        for r in rows:
            record = {"season_id": season_id, "player_id": r["player_id"],
                      "position_group": position_group}
            for z_key, count_key in rate_fields.items():
                rate_val = _rate(r, count_key)
                record[z_key] = _zscore(rate_val, populations[z_key]) if rate_val is not None else None
            database.upsert_player_rate_zscores(conn, record)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v -k chances_per60_z_null`
Expected: PASS.

- [ ] **Step 5: Run the full test file to check for regressions**

Run: `python -m pytest tests/test_compute_advanced_stats.py -v`
Expected: all tests PASS, including `test_compute_zscores_computes_expected_values_for_qualifying_population` and `test_compute_zscores_zero_stddev_population_yields_zero` (unaffected — no `None` values in their fixtures).

- [ ] **Step 6: Run the entire backend test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS (this closes out all code changes in the plan — Tasks 4-5 are constants + an operational run, no further code).

- [ ] **Step 7: Commit**

```bash
git add etl/compute_advanced_stats.py tests/test_compute_advanced_stats.py
git commit -m "None-safe chances_per60_z computation

Same class of gap as the hdcf_pct_pctile fix: row['ihdcf'] can now be
NULL (Task 1), which crashed _rate()'s division. Guard the None case,
exclude None contributors from the population, and leave
chances_per60_z as NULL for affected players while their other 5 rate
z-scores (icf/rebounds_created/deflections/points/primary_points-based,
never nulled by Task 1) compute normally."
```

---

### Task 4: Extend the three `SEASONS` constants

**Files:**
- Modify: `etl/load_historical_schedule.py:8`
- Modify: `etl/load_season_stats.py:8-14`
- Modify: `frontend/src/components/SeasonPicker.tsx:5-12`

**Interfaces:**
- Consumes: nothing new — pure constant extension.
- Produces: `SEASONS` (backend, both files) and `SEASONS` (frontend) now include `20172018`, `20182019`, `20192020` — Task 5's backfill run iterates these lists directly.

No tests are needed for this task — per the design spec's Testing section, none of the existing test files assert the full season list or a specific count (verified during brainstorming), so this is purely additive data with no behavior for a test to pin down.

- [ ] **Step 1: Extend `etl/load_historical_schedule.py`**

Change line 8 from:

```python
SEASONS = ["20202021", "20212022", "20222023", "20232024", "20242025", "20252026"]
```

to:

```python
SEASONS = ["20172018", "20182019", "20192020",
           "20202021", "20212022", "20222023", "20232024", "20242025", "20252026"]
```

- [ ] **Step 2: Extend `etl/load_season_stats.py`**

Change lines 8-15 from:

```python
SEASONS = [
    "20202021",
    "20212022",
    "20222023",
    "20232024",
    "20242025",
    "20252026",
]
```

to:

```python
SEASONS = [
    "20172018",
    "20182019",
    "20192020",
    "20202021",
    "20212022",
    "20222023",
    "20232024",
    "20242025",
    "20252026",
]
```

Note `"20252026"` stays last — `run()`'s `current_season = SEASONS[-1]` is unchanged and still correctly resolves to the current season.

- [ ] **Step 3: Extend `frontend/src/components/SeasonPicker.tsx`**

Change lines 5-12 from:

```typescript
export const SEASONS = [
  { id: "20252026", label: "2025–26" },
  { id: "20242025", label: "2024–25" },
  { id: "20232024", label: "2023–24" },
  { id: "20222023", label: "2022–23" },
  { id: "20212022", label: "2021–22" },
  { id: "20202021", label: "2020–21" },
];
```

to:

```typescript
export const SEASONS = [
  { id: "20252026", label: "2025–26" },
  { id: "20242025", label: "2024–25" },
  { id: "20232024", label: "2023–24" },
  { id: "20222023", label: "2022–23" },
  { id: "20212022", label: "2021–22" },
  { id: "20202021", label: "2020–21" },
  { id: "20192020", label: "2019–20" },
  { id: "20182019", label: "2018–19" },
  { id: "20172018", label: "2017–18" },
];
```

Order is display order in the dropdown (most recent first, matching the existing convention) — this does not need to match the backend `SEASONS` lists' order, which is iteration order for the backfill.

- [ ] **Step 4: Run the frontend test suite to confirm no regressions**

Run: `cd "/Users/paulmckay/Desktop/NHL Stats Project/frontend" && npm test`
Expected: all tests PASS (confirms the spec's finding that no test asserts the full list/count).

- [ ] **Step 5: Run the full backend test suite to confirm no regressions**

Run: `cd "/Users/paulmckay/Desktop/NHL Stats Project" && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add etl/load_historical_schedule.py etl/load_season_stats.py frontend/src/components/SeasonPicker.tsx
git commit -m "Extend SEASONS constants to cover 2017-18 through 2019-20

Adds the 3 new season IDs to both backend SEASONS lists (keeping
20252026 last in load_season_stats.py, since current_season = SEASONS[-1]
depends on that position) and the frontend SeasonPicker dropdown."
```

---

### Task 5: Run the historical backfill pipeline

**Files:** none modified — this is an operational task (running existing scripts against the live `data/nhl_stats.db`), not a code change.

**Interfaces:**
- Consumes: the extended `SEASONS` constants from Task 4, and the NULL-safe HD-stat code from Tasks 1-3.
- Produces: `data/nhl_stats.db` populated with games/boxscores/play-by-play/shifts/advanced-stats/season-stats/enrichment for the 3 new seasons.

- [ ] **Step 1: Back up the database first**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
cp data/nhl_stats.db "data/nhl_stats.db.bak-$(date +%Y%m%d)"
```

This is a ~1.5GB, multi-hour, many-thousand-API-call operation touching production data — back up first, matching the pattern the README already uses for other big rebuilds.

- [ ] **Step 2: Run the historical schedule backfill**

```bash
source .venv/bin/activate
python -m etl.load_historical_schedule
```

Expected: prints games loaded for all 9 seasons; the 6 pre-existing seasons should log as already-present (idempotent skip), the 3 new ones should show real counts (~1,300 regular-season + playoff games each).

- [ ] **Step 3: Run boxscores, play-by-play, and shifts backfill**

```bash
python -m etl.load_boxscores
python -m etl.load_play_by_play
python -m etl.load_shifts
```

Expected: each prints a count of games processed, scoped to the newly-scheduled games from Step 2 (existing 6 seasons' games are already loaded and skipped via each script's `NOT EXISTS` gate).

- [ ] **Step 4: Run the defending-side backfill safety net**

```bash
python -m etl.backfill_defending_side
```

Expected: for 2017-18/2018-19 games, this will report processing them (since `home_team_defending_side IS NULL` matches, per the confirmed 0% coverage) but cannot fill in a value the API never provided — this is expected and consistent with the design; Task 1-3's NULL-propagation is what makes this safe rather than misleading.

- [ ] **Step 5: Run advanced stats computation**

```bash
python -m etl.compute_advanced_stats
```

Expected: processes all new games' per-game advanced stats, then re-runs season/percentile/z-score aggregation for all seasons (cheap, no API calls, per the existing `_run_aggregation_and_percentiles` doc comment). This is the step that exercises Tasks 1-3's NULL-propagation code against real 2017-18/2018-19 data for the first time.

- [ ] **Step 6: Run season stats and player enrichment**

```bash
python etl/load_season_stats.py
python etl/enrich_players.py
```

Expected: `load_season_stats.py` loads bulk season stats for the 3 new seasons (not yet in `sync_log`, so not skipped); `enrich_players.py` enriches any newly-stubbed players from the older seasons.

- [ ] **Step 7: Spot-check warning output from Steps 2-6**

Review the terminal output captured from Steps 2-6 for a spike in "Warning: could not fetch/insert ..." lines relative to the near-zero rate seen on the existing 6 seasons (per the spec's Error Handling section). A spike signals an unhandled API-format difference for the older seasons that needs investigating before trusting the new data — a near-zero rate (consistent with the existing seasons) means the backfill went as expected.

- [ ] **Step 8: Spot-check the new seasons' data directly**

```bash
sqlite3 data/nhl_stats.db "SELECT season_id, COUNT(*) FROM games WHERE season_id IN ('20172018','20182019','20192020') GROUP BY season_id;"
sqlite3 data/nhl_stats.db "SELECT season_id, COUNT(*) FROM player_season_advanced_stats WHERE season_id IN ('20172018','20182019','20192020') AND hdcf IS NULL GROUP BY season_id;"
sqlite3 data/nhl_stats.db "SELECT season_id, COUNT(*) FROM player_season_advanced_stats WHERE season_id = '20192020' AND hdcf IS NOT NULL;"
```

Expected: real game counts for all 3 new seasons (~1,300 each); `hdcf IS NULL` rows present for `20172018`/`20182019` (confirming Tasks 1-3's NULL-propagation activated as designed, not silently computing misleading zeros); `20192020` should show real non-NULL `hdcf` rows (confirming the confirmed-good season wasn't accidentally nulled by an overly broad check).

- [ ] **Step 9: Run the full regression suite one final time**

```bash
python -m pytest tests/ -v
cd frontend && npm test
```

Expected: all PASS — confirms nothing about the live backfill broke any existing assertion.

- [ ] **Step 10: Update `.wolf/memory.md` and `.wolf/buglog.json` if any new data-quality findings emerged**

If Step 7's warning spot-check or Step 8's spot-check turned up anything unexpected (a new warning pattern, an unexpected NULL/non-NULL split), log it following this project's existing `.wolf/buglog.json` bug-entry convention before considering the task done — this is a discovery step against genuinely untested data, not a rubber-stamp.

No commit for this task — it modifies `data/nhl_stats.db`, which is git-ignored per the README (`data/ — SQLite database file (git-ignored)`).
