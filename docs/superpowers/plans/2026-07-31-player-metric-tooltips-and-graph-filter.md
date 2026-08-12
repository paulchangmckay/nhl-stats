# Player Metric Tooltips & Click-to-Filter Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explanatory tooltips (name/description/formula) and click-to-filter behavior to the 10 advanced-stat boxes in `PlayerProfilePanel`, so clicking a box toggles its trend line on the graph, while fixing a known `game_type` data-mixing gap in the queries this touches.

**Architecture:** Backend rewrites `_fetch_player_advanced`'s `trend` query (app.py) into a flat, multi-metric, per-strength-state array, filtered to `game_type = 2` (regular season). Frontend adds a `metricDefinitions.ts` config (single source of truth for tooltip copy + family grouping), a shadcn-generated `ui/tooltip.tsx` primitive, and refactors `PlayerProfilePanel.tsx`'s three box components behind a shared `SelectableStatBox` wrapper that handles click-to-toggle, keyboard access, and tooltip display. Selection state is family-capped local `useState`, matching the existing `strengthState` toggle pattern already in the component.

**Tech Stack:** Flask + SQLite (`app.py`, `src/database.py`), pytest; React 19 + TypeScript + Vite + Tailwind v4 + shadcn/ui (`base-nova` style, `@base-ui/react` primitives) + Recharts, Vitest + Testing Library.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-30-player-metric-tooltips-and-graph-filter-design.md` (grilled/approved — includes the `game_type = 2` fix addendum).
- Backend queries touched must filter `game_type = 2` (regular season only) — see spec's "Prerequisite fix" section.
- Scope is the 10 advanced-stat boxes only (4 percentile-row + 6 per-60 z-score boxes, including PDO). Basic box score and goalie stats are untouched.
- Metric families (selecting a different family replaces the selection; last box in a family can't be deselected): percentage (`cf_pct`, `ff_pct`, `hdcf_pct`), count (`primary_points`), composite (`pdo`), per60 (`shots_per60`, `chances_per60`, `rebounds_created_per60`, `deflections_per60`, `points_per60`, `primary_points_per60`).
- Default selection on dialog open / player change: `cf_pct`, 5v5 active.
- Tooltip triggers on hover **and** keyboard focus; click/Enter/Space toggles graph selection — these are separate gestures, not in conflict.
- Backend tests: `pytest`. Run from repo root: `pytest tests/test_app_advanced_stats.py -v`.
- Frontend tests: Vitest. Run from `frontend/`: `npx vitest run src/components/PlayerProfilePanel.test.tsx`.
- Commit after each task with a descriptive message; no `--no-verify`.

---

### Task 1: Backend — fix `game_type` gap + rewrite trend query

**Files:**
- Modify: `app.py:245-326` (`_fetch_player_advanced`)
- Modify: `tests/test_app_advanced_stats.py`
- Modify: `docs/api/advanced-stats.md`

**Interfaces:**
- Consumes: existing `_pct(numer, denom)` helper (`app.py:241-242`), existing tables `player_season_advanced_stats`, `team_season_advanced_stats`, `teams`.
- Produces: `_fetch_player_advanced(conn, player_id, season_id)` now returns `trend` as a flat list of dicts, each with keys `season_id, strength_state, cf_pct, ff_pct, hdcf_pct, primary_points, pdo, shots_per60, chances_per60, rebounds_created_per60, deflections_per60, points_per60, primary_points_per60`. `strength_states` values are unchanged in shape (still keyed by `5v5`/`5v4`/`4v5`, same fields as today), just now correctly scoped to `game_type = 2`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_app_advanced_stats.py`. First, extend the `_seed_season_row` helper to accept an optional `game_type` parameter (default `2`, preserving every existing call site):

```python
def _seed_season_row(conn, player_id, season_id, strength_state, cf, ca, ff, fa,
                      hdcf, hdca, primary_points, team_abbrevs="HOM",
                      icf=0, ihdcf=0, rebounds_created=0, deflections=0, points=0,
                      toi_seconds=900, game_type=2):
    conn.execute("""
        INSERT INTO player_season_advanced_stats
            (player_id, season_id, game_type, team_abbrevs, strength_state,
             cf, ca, ff, fa, hdcf, hdca, gf, ga, primary_points, toi_seconds, gp,
             icf, ihdcf, rebounds_created, deflections, points)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, 20, ?, ?, ?, ?, ?)
    """, (player_id, season_id, game_type, team_abbrevs, strength_state, cf, ca, ff, fa,
          hdcf, hdca, primary_points, toi_seconds,
          icf, ihdcf, rebounds_created, deflections, points))
    conn.commit()
```

Then update the existing `test_fetch_player_advanced_includes_trend_across_seasons` test (it currently only asserts season order — extend it for the new row shape) and add three new tests, all appended after it:

```python
def test_fetch_player_advanced_includes_trend_across_seasons(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    _seed_season_row(conn, 1, "20232024", "5v5", cf=50, ca=50, ff=40, fa=40, hdcf=5, hdca=5, primary_points=10)
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5, primary_points=15)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")

    trend_seasons = [t["season_id"] for t in result["trend"]]
    assert trend_seasons == ["20232024", "20242025"]
    row = result["trend"][1]
    assert row["strength_state"] == "5v5"
    assert row["cf_pct"] == 60.0
    assert row["ff_pct"] == 60.0
    assert row["primary_points"] == 15


def test_fetch_player_advanced_trend_includes_all_strength_states_per_season(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5, primary_points=15)
    _seed_season_row(conn, 1, "20242025", "5v4", cf=20, ca=5, ff=15, fa=3, hdcf=4, hdca=1, primary_points=5)
    _seed_season_row(conn, 1, "20242025", "4v5", cf=5, ca=20, ff=3, fa=15, hdcf=1, hdca=4, primary_points=1)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")

    states = {row["strength_state"] for row in result["trend"] if row["season_id"] == "20242025"}
    assert states == {"5v5", "5v4", "4v5"}
    by_state = {row["strength_state"]: row for row in result["trend"] if row["season_id"] == "20242025"}
    assert by_state["5v4"]["cf_pct"] == 80.0  # 20 / (20+5) * 100


def test_fetch_player_advanced_trend_per60_and_pdo_are_5v5_only(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    database.upsert_team(conn, {"team_id": HOME, "abbrev": "HOM", "common_name": "Home",
                                 "place_name": "Home", "conference": None, "division": None})
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5,
                      primary_points=15, icf=30, ihdcf=8, rebounds_created=4, deflections=2,
                      points=20, toi_seconds=3600, team_abbrevs="HOM")
    _seed_season_row(conn, 1, "20242025", "5v4", cf=20, ca=5, ff=15, fa=3, hdcf=4, hdca=1,
                      primary_points=5, icf=99, toi_seconds=900, team_abbrevs="HOM")
    _seed_team_season_row(conn, HOME, "20242025", "5v5", gf=30, ga=25, shots_for=300, shots_against=280)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")

    by_state = {row["strength_state"]: row for row in result["trend"] if row["season_id"] == "20242025"}
    assert by_state["5v5"]["shots_per60"] == 30.0
    expected_pdo = round((30 / 300 + (280 - 25) / 280) * 1000, 1)
    assert by_state["5v5"]["pdo"] == expected_pdo
    assert by_state["5v4"]["shots_per60"] is None
    assert by_state["5v4"]["pdo"] is None


def test_fetch_player_advanced_excludes_playoff_game_type(conn):
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Test", "last_name": "Player",
        "position_code": "C", "shoots_catches": None,
    })
    _seed_season_row(conn, 1, "20242025", "5v5", cf=60, ca=40, ff=45, fa=30, hdcf=10, hdca=5,
                      primary_points=15, game_type=2)
    _seed_season_row(conn, 1, "20242025", "5v5", cf=999, ca=1, ff=999, fa=1, hdcf=999, hdca=1,
                      primary_points=999, game_type=3)

    result = _fetch_player_advanced(conn, player_id=1, season_id="20242025")

    trend_5v5 = [row for row in result["trend"] if row["season_id"] == "20242025" and row["strength_state"] == "5v5"]
    assert len(trend_5v5) == 1
    assert trend_5v5[0]["cf_pct"] == 60.0  # not the game_type=3 row's inflated value
    assert result["strength_states"]["5v5"]["cf"] == 60  # season_rows query also excludes playoffs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app_advanced_stats.py -v`
Expected: `test_fetch_player_advanced_trend_includes_all_strength_states_per_season`, `test_fetch_player_advanced_trend_per60_and_pdo_are_5v5_only`, and `test_fetch_player_advanced_excludes_playoff_game_type` FAIL (trend still single-metric, no `game_type` filter). The updated `test_fetch_player_advanced_includes_trend_across_seasons` also FAILS on the new assertions (`KeyError: 'strength_state'`).

- [ ] **Step 3: Rewrite `_fetch_player_advanced` in `app.py`**

Replace lines 245-326 (the full function) with:

```python
def _fetch_player_advanced(conn, player_id, season_id):
    season_rows = conn.execute("""
        SELECT strength_state, cf, ca, ff, fa, hdcf, hdca, primary_points, team_abbrevs,
               icf, ihdcf, rebounds_created, deflections, points, toi_seconds
        FROM player_season_advanced_stats
        WHERE player_id = ? AND season_id = ? AND game_type = 2
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

    trend_rows = conn.execute("""
        SELECT season_id, strength_state, cf, ca, ff, fa, hdcf, hdca, primary_points,
               team_abbrevs, icf, ihdcf, rebounds_created, deflections, points, toi_seconds
        FROM player_season_advanced_stats
        WHERE player_id = ? AND game_type = 2
        ORDER BY season_id, strength_state
    """, (player_id,)).fetchall()

    trend = []
    for r in trend_rows:
        entry = {
            "season_id": r["season_id"],
            "strength_state": r["strength_state"],
            "cf_pct": _pct(r["cf"], r["cf"] + r["ca"]),
            "ff_pct": _pct(r["ff"], r["ff"] + r["fa"]),
            "hdcf_pct": _pct(r["hdcf"], r["hdcf"] + r["hdca"]),
            "primary_points": r["primary_points"],
            "pdo": None,
            "shots_per60": None, "chances_per60": None, "rebounds_created_per60": None,
            "deflections_per60": None, "points_per60": None, "primary_points_per60": None,
        }
        if r["strength_state"] == "5v5":
            toi_hours = r["toi_seconds"] / 3600.0 if r["toi_seconds"] else None
            if toi_hours:
                entry.update({
                    "shots_per60": round(r["icf"] / toi_hours, 2),
                    "chances_per60": round(r["ihdcf"] / toi_hours, 2),
                    "rebounds_created_per60": round(r["rebounds_created"] / toi_hours, 2),
                    "deflections_per60": round(r["deflections"] / toi_hours, 2),
                    "points_per60": round(r["points"] / toi_hours, 2),
                    "primary_points_per60": round(r["primary_points"] / toi_hours, 2),
                })
            first_abbrev = (r["team_abbrevs"] or "").split(",")[0] if r["team_abbrevs"] else None
            if first_abbrev:
                team_row = conn.execute("""
                    SELECT tsas.gf, tsas.ga, tsas.shots_for, tsas.shots_against
                    FROM team_season_advanced_stats tsas
                    JOIN teams t ON t.team_id = tsas.team_id
                    WHERE t.abbrev = ? AND tsas.season_id = ? AND tsas.strength_state = '5v5'
                      AND tsas.game_type = 2
                """, (first_abbrev, r["season_id"])).fetchone()
                if team_row and team_row["shots_for"] and team_row["shots_against"]:
                    shooting_pct = team_row["gf"] / team_row["shots_for"]
                    save_pct = (team_row["shots_against"] - team_row["ga"]) / team_row["shots_against"]
                    entry["pdo"] = round((shooting_pct + save_pct) * 1000, 1)
        trend.append(entry)

    pdo = None
    first_abbrev = (team_abbrevs or "").split(",")[0] if team_abbrevs else None
    if first_abbrev:
        team_row = conn.execute("""
            SELECT tsas.gf, tsas.ga, tsas.shots_for, tsas.shots_against
            FROM team_season_advanced_stats tsas
            JOIN teams t ON t.team_id = tsas.team_id
            WHERE t.abbrev = ? AND tsas.season_id = ? AND tsas.strength_state = '5v5'
        """, (first_abbrev, season_id)).fetchone()
        if team_row and team_row["shots_for"] and team_row["shots_against"]:
            shooting_pct = team_row["gf"] / team_row["shots_for"]
            save_pct = (team_row["shots_against"] - team_row["ga"]) / team_row["shots_against"]
            pdo = round((shooting_pct + save_pct) * 1000, 1)

    return {
        "player_id": player_id, "season_id": season_id,
        "strength_states": strength_states, "trend": trend, "pdo": pdo,
    }
```

(Only two things changed from the current version: `season_rows`' `WHERE` clause gained `AND game_type = 2`, and the old 6-line `trend_rows`/`trend` block was replaced by the new multi-metric loop above. Everything else — `pctile_rows`, `zscore_row`, the `strength_states` loop, and the final `pdo` block — is unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app_advanced_stats.py -v`
Expected: PASS, all tests including the 3 new ones and the updated one. Also run the full backend suite to confirm no regressions: `pytest tests/ -v` — expect all green (existing tests all seed `game_type=2` per the helper default, per the earlier check of `_seed_season_row`, so none of them relied on the missing filter).

- [ ] **Step 5: Update API docs**

In `docs/api/advanced-stats.md`, replace the `trend` description. Find this line in the `## GET /api/players/<player_id>/advanced...` section:

```
Returns `{ player_id, season_id, strength_states, trend, pdo }`.
```

Directly below it, before the `strength_states` table, insert:

```
`trend` is a flat array, one row per `(season_id, strength_state)`, ordered by
season then strength state, filtered to regular-season games only
(`game_type = 2`). Every row has:

| Field | Type | Meaning |
|---|---|---|
| `season_id` | string | |
| `strength_state` | string | `5v5` / `5v4` / `4v5` |
| `cf_pct`, `ff_pct`, `hdcf_pct`, `primary_points` | — | Same as the `strength_states` fields above, for that season |
| `pdo`, `shots_per60`, `chances_per60`, `rebounds_created_per60`, `deflections_per60`, `points_per60`, `primary_points_per60` | float\|null | **5v5 rows only** — `null` on `5v4`/`4v5` rows |
```

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_advanced_stats.py docs/api/advanced-stats.md
git commit -m "Fix game_type gap and extend trend to all metrics per strength state

_fetch_player_advanced's queries never filtered by game_type, mixing
playoff and regular-season rows for the same player-season. Adds the
game_type=2 filter (matching compute_zscores()'s existing convention)
and rewrites the trend query to carry all 10 advanced-stat metrics
across all three strength states instead of a single fixed cf_pct
series, laying the groundwork for click-to-filter on the frontend."
```

---

### Task 2: Frontend — extend `AdvancedTrendPoint` type + update test mock fixture

**Files:**
- Modify: `frontend/src/lib/types.ts:96-99`
- Modify: `frontend/src/components/PlayerProfilePanel.test.tsx:8-32` (the local `MOCK_ADVANCED` fixture — note: the trend fixture lives here, not in `lib/mock-data.ts`, which has no advanced-stats mock at all)

**Interfaces:**
- Produces: `AdvancedTrendPoint` type used by `PlayerProfilePanel.tsx` (Task 5/7) and any other consumer of `PlayerAdvancedStats.trend`.

- [ ] **Step 1: Update the type**

In `frontend/src/lib/types.ts`, replace lines 96-99:

```ts
export interface AdvancedTrendPoint {
  season_id: string;
  cf_pct: number | null;
}
```

with:

```ts
export interface AdvancedTrendPoint {
  season_id: string;
  strength_state: string;
  cf_pct: number | null;
  ff_pct: number | null;
  hdcf_pct: number | null;
  primary_points: number | null;
  pdo: number | null;
  shots_per60: number | null;
  chances_per60: number | null;
  rebounds_created_per60: number | null;
  deflections_per60: number | null;
  points_per60: number | null;
  primary_points_per60: number | null;
}
```

- [ ] **Step 2: Update the test fixture**

In `frontend/src/components/PlayerProfilePanel.test.tsx`, replace the `trend` field (lines 27-30) inside `MOCK_ADVANCED`:

```ts
  trend: [
    { season_id: "20232024", cf_pct: 55.0 },
    { season_id: "20242025", cf_pct: 60.0 },
  ],
```

with:

```ts
  trend: [
    { season_id: "20232024", strength_state: "5v5", cf_pct: 55.0, ff_pct: 54.0, hdcf_pct: 58.0,
      primary_points: 10, pdo: 998.0, shots_per60: 20.0, chances_per60: 6.0,
      rebounds_created_per60: 3.0, deflections_per60: 1.0, points_per60: 15.0, primary_points_per60: 10.0 },
    { season_id: "20242025", strength_state: "5v5", cf_pct: 60.0, ff_pct: 60.0, hdcf_pct: 66.7,
      primary_points: 15, pdo: 1005.3, shots_per60: 24.0, chances_per60: 8.0,
      rebounds_created_per60: 4.0, deflections_per60: 2.0, points_per60: 20.0, primary_points_per60: 15.0 },
    { season_id: "20242025", strength_state: "5v4", cf_pct: 80.0, ff_pct: 83.3, hdcf_pct: 80.0,
      primary_points: 5, pdo: null, shots_per60: null, chances_per60: null,
      rebounds_created_per60: null, deflections_per60: null, points_per60: null, primary_points_per60: null },
  ],
```

- [ ] **Step 3: Verify the build and existing tests still pass**

Run (from `frontend/`): `npx tsc -b`
Expected: no type errors — `PlayerProfilePanel.tsx` still reads `state.data.trend` and passes it to `<LineChart data={...}>` with `dataKey="cf_pct"`, which is still a valid key on the wider type.

Run: `npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: all existing tests PASS unchanged — this task only widens types/fixtures, no component behavior changed yet.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/components/PlayerProfilePanel.test.tsx
git commit -m "Widen AdvancedTrendPoint to the new multi-metric trend shape"
```

---

### Task 3: Frontend — new `metricDefinitions.ts` config

**Files:**
- Create: `frontend/src/lib/metricDefinitions.ts`

**Interfaces:**
- Produces: `MetricKey` (union type), `MetricFamily` (union type), `MetricDefinition` interface, `METRIC_DEFINITIONS: Record<MetricKey, MetricDefinition>`. Consumed by `PlayerProfilePanel.tsx` in Tasks 5-7.

No test file for this task — it's a static data config with no branching logic (per the design spec's testing plan), verified indirectly by the components that consume it in later tasks.

- [ ] **Step 1: Create the file**

```ts
export type MetricKey =
  | "cf_pct" | "ff_pct" | "hdcf_pct" | "primary_points" | "pdo"
  | "shots_per60" | "chances_per60" | "rebounds_created_per60"
  | "deflections_per60" | "points_per60" | "primary_points_per60";

export type MetricFamily = "percentage" | "count" | "composite" | "per60";

export interface MetricDefinition {
  label: string;
  name: string;
  description: string;
  formula: string;
  family: MetricFamily;
  strengthAware: boolean;
}

export const METRIC_DEFINITIONS: Record<MetricKey, MetricDefinition> = {
  cf_pct: {
    label: "CF%", name: "Corsi For %",
    description: "Share of shot attempts (on goal, missed, or blocked) this player's on-ice for vs. against.",
    formula: "cf / (cf + ca) × 100",
    family: "percentage", strengthAware: true,
  },
  ff_pct: {
    label: "FF%", name: "Fenwick For %",
    description: "Like CF%, but excludes blocked shots.",
    formula: "ff / (ff + fa) × 100",
    family: "percentage", strengthAware: true,
  },
  hdcf_pct: {
    label: "HDCF%", name: "High-Danger Corsi For %",
    description: "Share of high-danger shot attempts this player's on-ice for vs. against.",
    formula: "hdcf / (hdcf + hdca) × 100",
    family: "percentage", strengthAware: true,
  },
  primary_points: {
    label: "Primary Pts", name: "Primary Points",
    description: "Goals plus primary assists this player recorded (on-ice independent).",
    formula: "goals + primary assists",
    family: "count", strengthAware: true,
  },
  pdo: {
    label: "PDO", name: "PDO",
    description: "This player's team's on-ice shooting % plus save % at 5v5 — a puck-luck indicator that tends to regress toward 1000.",
    formula: "(shooting% + save%) × 1000",
    family: "composite", strengthAware: false,
  },
  shots_per60: {
    label: "Shots/60", name: "Individual Shot Attempts per 60",
    description: "This player's own shot attempts (on goal, missed, blocked, or goal) per 60 minutes of 5v5 ice time.",
    formula: "(SOG + missed + blocked + goals) / TOI hours",
    family: "per60", strengthAware: false,
  },
  chances_per60: {
    label: "Chances/60", name: "Individual High-Danger Chances per 60",
    description: "This player's own high-danger shot attempts per 60 minutes of 5v5 ice time.",
    formula: "individual high-danger shot attempts / TOI hours",
    family: "per60", strengthAware: false,
  },
  rebounds_created_per60: {
    label: "Rebounds Created/60", name: "Rebounds Created per 60",
    description: "Heuristic: a shot attempt within 3 seconds of this player's own shot attempt, same team, credited to the original shooter. Not possession-confirmed.",
    formula: "rebounds created / TOI hours",
    family: "per60", strengthAware: false,
  },
  deflections_per60: {
    label: "Deflections/60", name: "Deflections per 60",
    description: "This player's own shot attempts that were deflections or tip-ins, per 60 minutes of 5v5 ice time.",
    formula: "deflection/tip-in shot attempts / TOI hours",
    family: "per60", strengthAware: false,
  },
  points_per60: {
    label: "Points/60", name: "Points per 60",
    description: "Goals plus all assists per 60 minutes of 5v5 ice time.",
    formula: "(goals + assists) / TOI hours",
    family: "per60", strengthAware: false,
  },
  primary_points_per60: {
    label: "Primary Points/60", name: "Primary Points per 60",
    description: "Goals plus primary assists per 60 minutes of 5v5 ice time.",
    formula: "primary_points / TOI hours",
    family: "per60", strengthAware: false,
  },
};
```

- [ ] **Step 2: Verify it compiles**

Run (from `frontend/`): `npx tsc -b`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/metricDefinitions.ts
git commit -m "Add metricDefinitions.ts: single source of truth for tooltip copy and metric families"
```

---

### Task 4: Frontend — generate the `ui/tooltip.tsx` primitive

**Files:**
- Create: `frontend/src/components/ui/tooltip.tsx`

**Interfaces:**
- Produces: `Tooltip`, `TooltipTrigger`, `TooltipContent`, `TooltipProvider` components (standard shadcn tooltip export surface), consumed by `PlayerProfilePanel.tsx` in Task 6.

- [ ] **Step 1: Generate the component via the shadcn CLI**

Run (from `frontend/`): `npx shadcn@latest add tooltip`

This project already has `components.json` configured (`style: "base-nova"`, `@base-ui/react` primitives) and generated `dialog.tsx`/`popover.tsx` the same way, so this follows established convention rather than hand-rolling a new primitive.

- [ ] **Step 2: Verify the generated file's exports**

Read `frontend/src/components/ui/tooltip.tsx` and confirm it exports `Tooltip`, `TooltipTrigger`, `TooltipContent`, and `TooltipProvider` (the standard shadcn tooltip API surface, consistent across shadcn's radix and base-ui backends). If the generated export names differ, note the actual names now — Task 6's import statement must match exactly.

- [ ] **Step 3: Verify it compiles**

Run (from `frontend/`): `npx tsc -b`
Expected: no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/tooltip.tsx frontend/package.json frontend/package-lock.json
git commit -m "Add shadcn Tooltip primitive (ui/tooltip.tsx)"
```

---

### Task 5: Frontend — metric selection state + click-to-toggle on all 10 boxes

**Files:**
- Modify: `frontend/src/components/PlayerProfilePanel.tsx`
- Modify: `frontend/src/components/PlayerProfilePanel.test.tsx`

**Interfaces:**
- Consumes: `MetricKey`, `METRIC_DEFINITIONS` from `@/lib/metricDefinitions` (Task 3).
- Produces: a new `SelectableStatBox` component (used internally, and by Task 6 for tooltip wrapping); `selectedMetrics: Set<MetricKey>` state and `toggleMetric(key: MetricKey): void` handler, both scoped inside `PlayerProfilePanel`.

Note: the PDO box is currently anonymous inline JSX (lines 291-296), not a component like `PercentileBox`/`ZScoreBox` — but PDO is explicitly one of the 10 in-scope metrics (its own "composite" family, per the spec's family table). This task extracts the shared `SelectableStatBox` wrapper so all three box "shapes" (percentile, z-score, PDO) get click/keyboard/highlight behavior without duplicating that logic three times.

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/components/PlayerProfilePanel.test.tsx`, inside the `describe("PlayerProfilePanel", ...)` block, after the existing tests:

```ts
  it("highlights CF% by default and toggles selection within the percentage family", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    const cfBox = screen.getByRole("button", { name: /CF%/ });
    expect(cfBox).toHaveAttribute("aria-pressed", "true");

    const ffBox = screen.getByRole("button", { name: /FF%/ });
    expect(ffBox).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(ffBox);
    expect(ffBox).toHaveAttribute("aria-pressed", "true");
    expect(cfBox).toHaveAttribute("aria-pressed", "true"); // both selected, same family
  });

  it("clicking a box in a different family replaces the selection", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    const cfBox = screen.getByRole("button", { name: /CF%/ });
    const pdoBox = screen.getByRole("button", { name: /PDO/ });

    await userEvent.click(pdoBox);
    expect(pdoBox).toHaveAttribute("aria-pressed", "true");
    expect(cfBox).toHaveAttribute("aria-pressed", "false"); // replaced, different family
  });

  it("clicking the sole selected box is a no-op (never empties the selection)", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    const cfBox = screen.getByRole("button", { name: /CF%/ });
    await userEvent.click(cfBox);
    expect(cfBox).toHaveAttribute("aria-pressed", "true");
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `frontend/`): `npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: FAIL — `getByRole("button", { name: /CF%/ })` doesn't match anything (boxes aren't interactive yet).

- [ ] **Step 3: Add the `MetricKey`/`METRIC_DEFINITIONS` import**

In `frontend/src/components/PlayerProfilePanel.tsx`, after the existing `import type { Player, PlayerStats, PlayerAdvancedStats } from "@/lib/types";` (line 19), add:

```tsx
import { METRIC_DEFINITIONS, type MetricKey } from "@/lib/metricDefinitions";
```

- [ ] **Step 4: Add the `SelectableStatBox` wrapper**

After the `ZScoreBox` function (which ends at line 77, right before `interface StatCellProps` at line 79), insert:

```tsx
interface SelectableStatBoxProps {
  metricKey: MetricKey;
  selected: boolean;
  onToggle: (key: MetricKey) => void;
  colorClass: string;
  children: React.ReactNode;
}

function SelectableStatBox({ metricKey, selected, onToggle, colorClass, children }: SelectableStatBoxProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      aria-label={METRIC_DEFINITIONS[metricKey].label}
      onClick={() => onToggle(metricKey)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onToggle(metricKey);
        }
      }}
      className={`rounded-lg p-3 text-center cursor-pointer ${colorClass} ${selected ? "ring-2 ring-sky-400" : ""}`}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 5: Update `PercentileBox` and `ZScoreBox` to use it**

Replace `PercentileBoxProps`/`PercentileBox` (lines 28-48) with:

```tsx
interface PercentileBoxProps {
  metricKey: MetricKey;
  label: string;
  value: number | null;
  pctile: number | null;
  selected: boolean;
  onToggle: (key: MetricKey) => void;
}

function PercentileBox({ metricKey, label, value, pctile, selected, onToggle }: PercentileBoxProps) {
  const color =
    pctile === null ? "bg-muted" : pctile >= 50 ? "bg-sky-500/20" : "bg-rose-500/20";
  return (
    <SelectableStatBox metricKey={metricKey} selected={selected} onToggle={onToggle} colorClass={color}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">
        {pctile === null ? "-" : Math.round(pctile)}
      </div>
      <div className="text-xs text-muted-foreground tabular-nums">
        {value === null ? "-" : `${value}%`}
      </div>
    </SelectableStatBox>
  );
}
```

Replace `ZScoreBoxProps`/`ZScoreBox` (lines 50-77) with:

```tsx
interface ZScoreBoxProps {
  metricKey: MetricKey;
  label: string;
  rate: number | null | undefined;
  z: number | null | undefined;
  nullReason: string;
  selected: boolean;
  onToggle: (key: MetricKey) => void;
}

function ZScoreBox({ metricKey, label, rate, z, nullReason, selected, onToggle }: ZScoreBoxProps) {
  if (z === null || z === undefined) {
    return (
      <SelectableStatBox metricKey={metricKey} selected={selected} onToggle={onToggle} colorClass="bg-muted opacity-60">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-2xl font-semibold tabular-nums">N/A</div>
      </SelectableStatBox>
    );
  }
  const color = z >= 0 ? "bg-sky-500/20" : "bg-rose-500/20";
  return (
    <SelectableStatBox metricKey={metricKey} selected={selected} onToggle={onToggle} colorClass={color}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{z.toFixed(2)}</div>
      <div className="text-xs text-muted-foreground tabular-nums">
        {rate == null ? "-" : rate.toFixed(2)}
      </div>
    </SelectableStatBox>
  );
}
```

(The `tooltip`/`nullReason`-as-`title` behavior is intentionally dropped here — Task 6 replaces it with a proper `Tooltip` sourced from `metricDefinitions.ts`, still incorporating `nullReason`.)

- [ ] **Step 6: Add selection state and the toggle handler**

In the `PlayerProfilePanel` component, after the existing `const [logoFailed, setLogoFailed] = useState(false);` (line 148), add:

```tsx
  const [selectedMetrics, setSelectedMetrics] = useState<Set<MetricKey>>(() => new Set(["cf_pct"]));

  function toggleMetric(key: MetricKey) {
    setSelectedMetrics((prev) => {
      const first = prev.values().next().value as MetricKey | undefined;
      const currentFamily = first ? METRIC_DEFINITIONS[first].family : null;
      const newFamily = METRIC_DEFINITIONS[key].family;
      if (currentFamily !== null && currentFamily !== newFamily) {
        return new Set([key]);
      }
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }
```

- [ ] **Step 7: Reset selection when the player changes**

Replace the existing effect (lines 152-155):

```tsx
  useEffect(() => {
    setPhotoFailed(false);
    setLogoFailed(false);
  }, [playerId]);
```

with:

```tsx
  useEffect(() => {
    setPhotoFailed(false);
    setLogoFailed(false);
    setSelectedMetrics(new Set(["cf_pct"]));
  }, [playerId]);
```

- [ ] **Step 8: Wire `metricKey`/`selected`/`onToggle` onto all 10 box call sites**

Replace the percentile-row grid (lines 282-297):

```tsx
                <div className="grid grid-cols-5 gap-2">
                  <PercentileBox label="CF%" value={current?.cf_pct ?? null} pctile={current?.cf_pctile ?? null} />
                  <PercentileBox label="FF%" value={current?.ff_pct ?? null} pctile={current?.ff_pctile ?? null} />
                  <PercentileBox label="HDCF%" value={current?.hdcf_pct ?? null} pctile={current?.hdcf_pctile ?? null} />
                  <PercentileBox
                    label="Primary Pts"
                    value={current?.primary_points ?? null}
                    pctile={current?.primary_points_pctile ?? null}
                  />
                  <div className="rounded-lg bg-muted p-3 text-center">
                    <div className="text-xs text-muted-foreground">PDO</div>
                    <div className="text-2xl font-semibold tabular-nums">
                      {state.data.pdo === null ? "-" : state.data.pdo}
                    </div>
                  </div>
                </div>
```

with:

```tsx
                <div className="grid grid-cols-5 gap-2">
                  <PercentileBox metricKey="cf_pct" selected={selectedMetrics.has("cf_pct")} onToggle={toggleMetric}
                    label="CF%" value={current?.cf_pct ?? null} pctile={current?.cf_pctile ?? null} />
                  <PercentileBox metricKey="ff_pct" selected={selectedMetrics.has("ff_pct")} onToggle={toggleMetric}
                    label="FF%" value={current?.ff_pct ?? null} pctile={current?.ff_pctile ?? null} />
                  <PercentileBox metricKey="hdcf_pct" selected={selectedMetrics.has("hdcf_pct")} onToggle={toggleMetric}
                    label="HDCF%" value={current?.hdcf_pct ?? null} pctile={current?.hdcf_pctile ?? null} />
                  <PercentileBox metricKey="primary_points" selected={selectedMetrics.has("primary_points")} onToggle={toggleMetric}
                    label="Primary Pts" value={current?.primary_points ?? null} pctile={current?.primary_points_pctile ?? null} />
                  <SelectableStatBox metricKey="pdo" selected={selectedMetrics.has("pdo")} onToggle={toggleMetric} colorClass="bg-muted">
                    <div className="text-xs text-muted-foreground">PDO</div>
                    <div className="text-2xl font-semibold tabular-nums">
                      {state.data.pdo === null ? "-" : state.data.pdo}
                    </div>
                  </SelectableStatBox>
                </div>
```

Replace the per-60 z-score grid (lines 299-325):

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

with:

```tsx
                <div className="grid grid-cols-3 gap-2">
                  <ZScoreBox metricKey="shots_per60" selected={selectedMetrics.has("shots_per60")} onToggle={toggleMetric}
                    label="Shots/60"
                    rate={state.data.strength_states["5v5"]?.shots_per60}
                    z={state.data.strength_states["5v5"]?.shots_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox metricKey="chances_per60" selected={selectedMetrics.has("chances_per60")} onToggle={toggleMetric}
                    label="Chances/60"
                    rate={state.data.strength_states["5v5"]?.chances_per60}
                    z={state.data.strength_states["5v5"]?.chances_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox metricKey="rebounds_created_per60" selected={selectedMetrics.has("rebounds_created_per60")} onToggle={toggleMetric}
                    label="Rebounds Created/60"
                    rate={state.data.strength_states["5v5"]?.rebounds_created_per60}
                    z={state.data.strength_states["5v5"]?.rebounds_created_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox metricKey="deflections_per60" selected={selectedMetrics.has("deflections_per60")} onToggle={toggleMetric}
                    label="Deflections/60"
                    rate={state.data.strength_states["5v5"]?.deflections_per60}
                    z={state.data.strength_states["5v5"]?.deflections_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox metricKey="points_per60" selected={selectedMetrics.has("points_per60")} onToggle={toggleMetric}
                    label="Points/60"
                    rate={state.data.strength_states["5v5"]?.points_per60}
                    z={state.data.strength_states["5v5"]?.points_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                  <ZScoreBox metricKey="primary_points_per60" selected={selectedMetrics.has("primary_points_per60")} onToggle={toggleMetric}
                    label="Primary Points/60"
                    rate={state.data.strength_states["5v5"]?.primary_points_per60}
                    z={state.data.strength_states["5v5"]?.primary_points_per60_z}
                    nullReason="Below the 10-GP floor, or league sample too small this season" />
                </div>
```

(Note: the `rebounds_created_per60` box's old `tooltip="Heuristic: ..."` prop is dropped here — that exact copy now lives in `metricDefinitions.ts`'s `rebounds_created_per60.description`, wired up in Task 6.)

- [ ] **Step 9: Run tests to verify they pass**

Run (from `frontend/`): `npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: PASS, all tests including the 3 new ones.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/PlayerProfilePanel.tsx frontend/src/components/PlayerProfilePanel.test.tsx
git commit -m "Add click-to-select state to all 10 advanced-stat boxes, family-capped"
```

---

### Task 6: Frontend — wire tooltips onto `SelectableStatBox`

**Files:**
- Modify: `frontend/src/components/PlayerProfilePanel.tsx`
- Modify: `frontend/src/components/PlayerProfilePanel.test.tsx`

**Interfaces:**
- Consumes: `Tooltip`, `TooltipTrigger`, `TooltipContent`, `TooltipProvider` from `@/components/ui/tooltip` (Task 4).
- Produces: `SelectableStatBox` now shows a hover/focus tooltip with the metric's `name`/`description`/`formula` (and, for z-score boxes in their N/A state, the existing `nullReason` text).

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/components/PlayerProfilePanel.test.tsx`:

```ts
  it("shows the metric's name, description, and formula on hover", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    const cfBox = screen.getByRole("button", { name: /CF%/ });
    await userEvent.hover(cfBox);
    expect(await screen.findByText("Corsi For %")).toBeInTheDocument();
    expect(screen.getByText("cf / (cf + ca) × 100")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: FAIL — hovering shows nothing, no tooltip wired up yet.

- [ ] **Step 3: Import the tooltip primitive**

In `frontend/src/components/PlayerProfilePanel.tsx`, after the `import { METRIC_DEFINITIONS, type MetricKey } from "@/lib/metricDefinitions";` line added in Task 5, add:

```tsx
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@/components/ui/tooltip";
```

(If Task 4's generated file exports different names, use those exact names here instead.)

- [ ] **Step 4: Wrap `SelectableStatBox`'s content in a `Tooltip`, add an `extraNote` prop**

Replace the `SelectableStatBox` component added in Task 5 with:

```tsx
interface SelectableStatBoxProps {
  metricKey: MetricKey;
  selected: boolean;
  onToggle: (key: MetricKey) => void;
  colorClass: string;
  extraNote?: string;
  children: React.ReactNode;
}

function SelectableStatBox({ metricKey, selected, onToggle, colorClass, extraNote, children }: SelectableStatBoxProps) {
  const def = METRIC_DEFINITIONS[metricKey];
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          role="button"
          tabIndex={0}
          aria-pressed={selected}
          aria-label={def.label}
          onClick={() => onToggle(metricKey)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onToggle(metricKey);
            }
          }}
          className={`rounded-lg p-3 text-center cursor-pointer ${colorClass} ${selected ? "ring-2 ring-sky-400" : ""}`}
        >
          {children}
        </div>
      </TooltipTrigger>
      <TooltipContent>
        <div className="font-medium">{def.name}</div>
        <div>{def.description}</div>
        <div className="text-muted-foreground">{def.formula}</div>
        {extraNote && <div className="text-muted-foreground italic">{extraNote}</div>}
      </TooltipContent>
    </Tooltip>
  );
}
```

- [ ] **Step 5: Pass `nullReason` through as `extraNote` on `ZScoreBox`'s N/A branch**

In `ZScoreBox` (from Task 5), replace the N/A-branch return:

```tsx
    return (
      <SelectableStatBox metricKey={metricKey} selected={selected} onToggle={onToggle} colorClass="bg-muted opacity-60">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-2xl font-semibold tabular-nums">N/A</div>
      </SelectableStatBox>
    );
```

with:

```tsx
    return (
      <SelectableStatBox metricKey={metricKey} selected={selected} onToggle={onToggle}
        colorClass="bg-muted opacity-60" extraNote={nullReason}>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-2xl font-semibold tabular-nums">N/A</div>
      </SelectableStatBox>
    );
```

- [ ] **Step 6: Wrap the advanced-stats section in `TooltipProvider`**

In the `state.status === "ready"` branch, the existing wrapping element is `<div className="flex flex-col gap-4">` (line 268). Change it to also render `TooltipProvider` as the outermost element for that branch — replace:

```tsx
            {state.status === "ready" && (
              <div className="flex flex-col gap-4">
```

with:

```tsx
            {state.status === "ready" && (
              <TooltipProvider delayDuration={300}>
              <div className="flex flex-col gap-4">
```

And its closing tag — find the matching closing `</div>` right before the outer `</>` (end of the `!isGoalie && (<>...</>)` block, i.e. immediately before line 339's `)}` that closes the `{state.status === "ready" && (...)}` block). Replace:

```tsx
              </div>
            )}
```

(the one that closes the `flex flex-col gap-4` div, immediately preceding the final `)}` of `{state.status === "ready" && (...)}`) with:

```tsx
              </div>
              </TooltipProvider>
            )}
```

- [ ] **Step 7: Run the test to verify it passes**

Run (from `frontend/`): `npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: PASS, all tests.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/PlayerProfilePanel.tsx frontend/src/components/PlayerProfilePanel.test.tsx
git commit -m "Wire hover/focus tooltips onto all 10 advanced-stat boxes"
```

---

### Task 7: Frontend — graph filters by selected metrics and strength state

**Files:**
- Modify: `frontend/src/components/PlayerProfilePanel.tsx`
- Modify: `frontend/src/components/PlayerProfilePanel.test.tsx`

**Interfaces:**
- Produces: the trend `<LineChart>` now renders one `<Line>` per key in `selectedMetrics`, reading from `trend` rows filtered to the strength-state relevant to the current selection.

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/components/PlayerProfilePanel.test.tsx`:

```ts
  it("shows a single CF% line by default", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    expect(screen.getByText("CF%", { selector: "span" })).toBeInTheDocument();
  });

  it("adding a second metric in the same family adds a second line to the legend", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /FF%/ }));
    expect(screen.getByText("CF%", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("FF%", { selector: "span" })).toBeInTheDocument();
  });

  it("switching strength state re-filters the graph for a strength-aware selection", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    // MOCK_ADVANCED.trend has one 5v4 row (season 20242025) and two 5v5 rows.
    await userEvent.click(screen.getByRole("button", { name: "5v4" }));
    await waitFor(() => expect(screen.getByText("55")).toBeInTheDocument()); // 5v4 cf_pctile, sanity check toggle worked
    // With 5v4 active and cf_pct (strength-aware) selected, chart data should be the single 5v4 trend row.
    // Verified indirectly: no crash, still one legend entry.
    expect(screen.getByText("CF%", { selector: "span" })).toBeInTheDocument();
  });

  it("selecting a per60 metric ignores the strength-state toggle (always 5v5)", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Shots\/60/ }));
    await userEvent.click(screen.getByRole("button", { name: "5v4" }));
    expect(screen.getByText("Shots/60", { selector: "span" })).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `frontend/`): `npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: FAIL — chart still renders a single hardcoded `cf_pct` line with no legend at all.

- [ ] **Step 3: Compute `chartData` and derive the active strength state**

In `PlayerProfilePanel`, right after the existing `const current = state.status === "ready" ? state.data.strength_states[strengthState] : undefined;` (line 169), add:

```tsx
  const primaryMetricKey = selectedMetrics.values().next().value as MetricKey;
  const graphStrengthState = METRIC_DEFINITIONS[primaryMetricKey].strengthAware ? strengthState : "5v5";
  const chartData = state.status === "ready"
    ? state.data.trend.filter((row) => row.strength_state === graphStrengthState)
    : [];
```

- [ ] **Step 4: Add a color palette constant**

Near the top of the file, after the existing `const STRENGTH_STATES = ["5v5", "5v4", "4v5"] as const;` (line 21), add:

```tsx
const LINE_COLORS = [
  "var(--color-sky-500)", "var(--color-amber-500)", "var(--color-emerald-500)",
  "var(--color-rose-500)", "var(--color-violet-500)", "var(--color-cyan-500)",
];
```

- [ ] **Step 5: Replace the fixed single-line chart with a multi-line, legend-annotated one**

Replace the chart block (lines 327-336):

```tsx
                <div className="h-40 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={state.data.trend}>
                      <XAxis dataKey="season_id" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip />
                      <Line type="monotone" dataKey="cf_pct" stroke="var(--color-sky-500)" dot />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
```

with:

```tsx
                <div className="flex flex-col gap-1">
                  <div className="flex gap-3 text-xs text-muted-foreground">
                    {Array.from(selectedMetrics).map((key, i) => (
                      <span key={key} className="flex items-center gap-1">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: LINE_COLORS[i % LINE_COLORS.length] }}
                        />
                        {METRIC_DEFINITIONS[key].label}
                      </span>
                    ))}
                  </div>
                  <div className="h-40 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData}>
                        <XAxis dataKey="season_id" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip />
                        {Array.from(selectedMetrics).map((key, i) => (
                          <Line key={key} type="monotone" dataKey={key} stroke={LINE_COLORS[i % LINE_COLORS.length]} dot />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
```

- [ ] **Step 6: Run tests to verify they pass**

Run (from `frontend/`): `npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: PASS, all tests.

- [ ] **Step 7: Run the full frontend suite**

Run (from `frontend/`): `npx vitest run`
Expected: PASS, no regressions anywhere else in the frontend test suite.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/PlayerProfilePanel.tsx frontend/src/components/PlayerProfilePanel.test.tsx
git commit -m "Graph filters by selected metrics and active strength state, with legend"
```

---

## Manual Verification (after all tasks)

Per `verification-before-completion`, before considering this done:

1. Run backend build/tests: `pytest tests/ -v` (all green).
2. Run frontend build/tests: from `frontend/`, `npx tsc -b && npx vitest run` (both green).
3. Start the app (`run` skill or existing dev workflow), open the player profile overlay for a skater with multiple seasons of trend history.
4. Hover each of the 10 boxes — confirm tooltip copy (name/description/formula) reads correctly, and the two z-score N/A boxes (if any player has one) also show the null-reason note.
5. Click through boxes within a family (e.g. CF% then FF%) — confirm both highlight and both lines appear on the graph with a matching legend.
6. Click a box in a different family (e.g. PDO) — confirm the prior selection clears and only PDO is selected/graphed.
7. Toggle strength state (5v5/5v4/4v5) with a percentage-family metric selected — confirm the graph's data changes. Toggle strength state with a per-60 metric selected — confirm the graph is unaffected.
8. Close the dialog and reopen it for a different player — confirm the selection resets to CF%/5v5.
9. Tab through the boxes via keyboard only — confirm focus shows the tooltip and Enter/Space toggles selection.
