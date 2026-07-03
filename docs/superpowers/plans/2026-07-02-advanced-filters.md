# Advanced Player Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add search-with-autocomplete, a position filter, a multi-select season control, Stats-tab stat-threshold filters, and a richer team filter (full names + logos) to the NHL player table.

**Architecture:** Everything lives in the existing two files — `templates/index.html` (vanilla HTML/CSS/JS, no build step, no framework) and `app.py` (Flask). No new files, no new libraries, no new network endpoints beyond extending the two existing `/api/teams` and `/api/players/stats` routes.

**Tech Stack:** Flask (Python), SQLite via `src/database.py`, vanilla HTML/CSS/JS (no npm, no build step).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-02-advanced-filters-design.md` — read it before starting if anything below is ambiguous.
- Client-side filter/sort pattern stays intact — all filtering (search, position, stat thresholds, team) happens in JS over already-loaded JSON; only the season *stats sum* is server-side.
- The Team column badge inside table rows (abbreviation + hover tooltip) does **not** change — only the Team *filter control* changes.
- No goalie-stat filters in this round (GP/G/A/Pts only, skaters).
- No server-side pagination or query-model change.
- Team logos load live from `https://assets.nhle.com/logos/nhl/svg/{ABBREV}_light.svg` — no local storage, no new backend route. A 404'd logo must degrade gracefully (hidden, not a broken-image icon breaking layout).
- Season default on page load: only `"20252026"` checked. At least one season must always remain checked — the UI must not allow unchecking the last one.
- **Testing deviation (explicitly approved in the spec):** this project has no automated test suite or test runner (no `pytest`, no JS test framework) and none is introduced by this feature. Every task below ends with a **manual verification** step against the running dev server instead of a `pytest`/failing-test cycle. This replaces, for this plan only, the standard TDD red/green step shape.
- Dev server: `lsof -ti :5000 | xargs kill -9` before every `python app.py` run (port 5000 is frequently already bound on this machine, per `.wolf/cerebrum.md`).

---

### Task 1: Backend — `/api/teams` alphabetical order

**Files:**
- Modify: `app.py:35-42` (`api_teams` route)

**Interfaces:**
- Produces: `/api/teams` still returns `[{"abbrev": str, "common_name": str}, ...]`, now ordered by `common_name` ascending instead of `abbrev`. Consumed by Task 5 (team popup dropdown expects alphabetical-by-name order already applied server-side).

- [ ] **Step 1: Change the ORDER BY clause**

In `app.py`, inside `api_teams()`:

```python
@app.route("/api/teams")
def api_teams():
    conn = get_connection()
    rows = conn.execute(
        "SELECT abbrev, common_name FROM teams ORDER BY common_name"
    ).fetchall()
    conn.close()
    return jsonify([{"abbrev": r["abbrev"], "common_name": r["common_name"]} for r in rows])
```

(Only the SQL string changes: `ORDER BY abbrev` → `ORDER BY common_name`.)

- [ ] **Step 2: Manual verification**

```bash
lsof -ti :5000 | xargs kill -9
python app.py &
sleep 1
curl -s http://127.0.0.1:5000/api/teams | python3 -m json.tool | head -20
```

Expected: the first entries are alphabetically first by `common_name` (e.g. a team like "Anaheim Ducks" appears before teams starting with later letters), not grouped by abbreviation.

- [ ] **Step 3: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add app.py
git commit -m "feat: sort /api/teams alphabetically by common name"
```

---

### Task 2: Backend — multi-season stats endpoint

**Files:**
- Modify: `app.py:87-188` (`api_players_stats` route)

**Interfaces:**
- Consumes: nothing new (same `players`, `teams`, `player_career_stats`, `player_season_stats` tables).
- Produces: `/api/players/stats?seasons=<comma-separated season ids>` (replaces the old single-value `season` param). `seasons=all` behaves exactly as the old `season=all` (career fast path). `seasons=20232024` behaves exactly as the old `season=20232024`. `seasons=20232024,20222023` sums counting stats across both seasons in one response. Response shape (list of player-stat dicts) is unchanged — consumed by Task 6's `loadStats()`.

- [ ] **Step 1: Replace the `season` param with a parsed `seasons` list**

In `app.py`, at the top of `api_players_stats()`, replace:

```python
    season = request.args.get("season", "all")
    conn = get_connection()

    if season == "all":
```

with:

```python
    seasons_param = request.args.get("seasons", "all")
    seasons = [s.strip() for s in seasons_param.split(",") if s.strip()]
    if not seasons:
        seasons = ["all"]
    conn = get_connection()

    if seasons == ["all"]:
```

- [ ] **Step 2: Generalize the single-season branch to an `IN (...)` clause**

Replace the `else:` branch's SQL (the block starting `rows = conn.execute("""` under `else:`) — specifically the `WHERE s.season_id = ?` line and the parameter tuple — with an `IN` clause built from the number of seasons requested:

```python
    else:
        placeholders = ",".join("?" for _ in seasons)
        rows = conn.execute(f"""
            SELECT
                p.player_id,
                p.first_name,
                p.last_name,
                p.position_code,
                t.abbrev      AS team_abbrev,
                t.common_name AS team_name,
                SUM(s.gp)                                                    AS gp,
                SUM(s.goals)                                                 AS goals,
                SUM(s.assists)                                               AS assists,
                SUM(s.points)                                                AS points,
                SUM(s.plus_minus)                                            AS plus_minus,
                SUM(s.pim)                                                   AS pim,
                SUM(s.pp_goals)                                              AS pp_goals,
                SUM(s.sh_goals)                                              AS sh_goals,
                SUM(s.shots)                                                 AS shots,
                ROUND(SUM(s.goals)*100.0 / NULLIF(SUM(s.shots), 0), 1)     AS shooting_pct,
                MAX(CASE WHEN s.game_type = 2 THEN s.avg_toi END)           AS avg_toi,
                SUM(s.wins)                                                  AS wins,
                SUM(s.losses)                                                AS losses,
                SUM(s.ot_losses)                                             AS ot_losses,
                SUM(s.shutouts)                                              AS shutouts,
                MAX(CASE WHEN s.game_type = 2 THEN s.save_pct END)          AS save_pct,
                MAX(CASE WHEN s.game_type = 2 THEN s.gaa END)               AS gaa
            FROM players p
            LEFT JOIN teams t ON p.current_team_id = t.team_id
            JOIN player_season_stats s ON p.player_id = s.player_id
            WHERE s.season_id IN ({placeholders})
            GROUP BY p.player_id
            ORDER BY SUM(s.points) DESC
        """, seasons).fetchall()
```

Note: `placeholders` only ever contains `?` and `,` characters (one `?` per season in the list) — the actual season id *values* are passed through the parameterized second argument to `conn.execute`, not interpolated into the SQL string, so this is not vulnerable to SQL injection despite the f-string.

The rest of the function (the `players = []` serialization loop) is unchanged.

- [ ] **Step 3: Manual verification — single season still works**

```bash
curl -s "http://127.0.0.1:5000/api/players/stats?seasons=20232024" | python3 -m json.tool | head -30
```

Expected: identical shape/values to what the old `?season=20232024` used to return (spot check a known player's goals/assists/points).

- [ ] **Step 4: Manual verification — multi-season sum is correct**

```bash
curl -s "http://127.0.0.1:5000/api/players/stats?seasons=20232024" | python3 -c "import json,sys; d=json.load(sys.stdin); print(next(p for p in d if p['last_name']=='McDavid'))"
curl -s "http://127.0.0.1:5000/api/players/stats?seasons=20222023" | python3 -c "import json,sys; d=json.load(sys.stdin); print(next(p for p in d if p['last_name']=='McDavid'))"
curl -s "http://127.0.0.1:5000/api/players/stats?seasons=20232024,20222023" | python3 -c "import json,sys; d=json.load(sys.stdin); print(next(p for p in d if p['last_name']=='McDavid'))"
```

Expected: the combined call's `goals`/`assists`/`points`/`gp` equal the sum of the two single-season calls for the same player (adjust the player name if McDavid isn't in your `data/nhl_stats.db`).

- [ ] **Step 5: Manual verification — career path unaffected**

```bash
curl -s "http://127.0.0.1:5000/api/players/stats?seasons=all" | python3 -m json.tool | head -20
```

Expected: identical to the old `?season=all` response.

- [ ] **Step 6: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add app.py
git commit -m "feat: support summing stats across multiple seasons via ?seasons="
```

---

### Task 3: Frontend — header restructure + position filter

This is the first frontend task. It splits the single-row header into three stacked rows (row1: existing controls; row2: new position toggles, always visible; row3: reserved for Task 4's stat filters, hidden for now) and fixes the sticky table-header offset so it doesn't overlap the now-taller header.

**Files:**
- Modify: `templates/index.html:7-186` (`<style>` block)
- Modify: `templates/index.html:190-215` (`<header>` markup)
- Modify: `templates/index.html:229-237` (JS state block)
- Modify: `templates/index.html:435-479` (`render()`)
- Modify: `templates/index.html:489` (final `buildHeader()` call)

**Interfaces:**
- Produces: `let activePositions` (a `Set<string>` of active position codes), `function updateHeaderOffset()`. Both consumed by Task 4 (stat row visibility) and used internally.
- Consumes: nothing new.

- [ ] **Step 1: Restructure the `header` CSS into rows**

Replace the existing `header { ... }` rule (`templates/index.html:17-28`):

```css
    header {
      background: #161b22;
      border-bottom: 1px solid #30363d;
      padding: 14px 24px;
      display: flex;
      align-items: center;
      gap: 16px;
      position: sticky;
      top: 0;
      z-index: 10;
      flex-wrap: wrap;
    }
```

with:

```css
    header {
      background: #161b22;
      border-bottom: 1px solid #30363d;
      padding: 14px 24px 10px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      position: sticky;
      top: 0;
      z-index: 10;
    }

    .header-row1 {
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }

    .header-row2, .header-row3 {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
```

- [ ] **Step 2: Add position-toggle CSS**

Add this new block right after the `.tab-btn` rules (after `templates/index.html:84`, the `.tab-btn.active` rule):

```css
    .pos-toggle-group {
      display: flex;
      gap: 4px;
    }

    .pos-toggle {
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 4px;
      padding: 3px 8px;
      font-size: 11px;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
    }

    .pos-toggle.pos-C { color: #3fb950; border-color: #3fb950; }
    .pos-toggle.pos-L { color: #58a6ff; border-color: #58a6ff; }
    .pos-toggle.pos-R { color: #79c0ff; border-color: #79c0ff; }
    .pos-toggle.pos-D { color: #d2a8ff; border-color: #d2a8ff; }
    .pos-toggle.pos-G { color: #ffa657; border-color: #ffa657; }

    .pos-toggle.pos-C.active { background: #3fb950; color: #0d1117; }
    .pos-toggle.pos-L.active { background: #58a6ff; color: #0d1117; }
    .pos-toggle.pos-R.active { background: #79c0ff; color: #0d1117; }
    .pos-toggle.pos-D.active { background: #d2a8ff; color: #0d1117; }
    .pos-toggle.pos-G.active { background: #ffa657; color: #0d1117; }
```

- [ ] **Step 3: Make the sticky table-header offset dynamic**

Change `thead th`'s `top` value (`templates/index.html:117`), from:

```css
      top: 57px;
```

to:

```css
      top: var(--thead-top, 57px);
```

(No other properties on that rule change.)

- [ ] **Step 4: Restructure the header markup into rows**

Replace the entire `<header>...</header>` block (`templates/index.html:190-215`):

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
  </div>
  <span class="count" id="count-label"></span>
</header>
```

with:

```html
<header>
  <div class="header-row1">
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
    </div>
    <span class="count" id="count-label"></span>
  </div>

  <div class="header-row2" id="pos-filter-row">
    <label>Position</label>
    <div class="pos-toggle-group">
      <button type="button" class="pos-toggle pos-C" data-pos="C">C</button>
      <button type="button" class="pos-toggle pos-L" data-pos="L">L</button>
      <button type="button" class="pos-toggle pos-R" data-pos="R">R</button>
      <button type="button" class="pos-toggle pos-D" data-pos="D">D</button>
      <button type="button" class="pos-toggle pos-G" data-pos="G">G</button>
    </div>
  </div>
</header>
```

(Note: `team-filter`/`season-filter` `<select>`s stay exactly as-is here — Tasks 5 and 6 replace them. This task only moves them inside `.header-row1` and adds row2.)

- [ ] **Step 5: Add `activePositions` state and `updateHeaderOffset()`**

In the JS state block (`templates/index.html:229-237`), add one line after `let activeTeam = "";`:

```js
  let activeTeam   = "";
  let activePositions = new Set();
```

Then add this new function anywhere in the `<script>` block above `render()`:

```js
  function updateHeaderOffset() {
    const header = document.querySelector("header");
    document.documentElement.style.setProperty("--thead-top", `${header.offsetHeight}px`);
  }
```

- [ ] **Step 6: Wire up the position toggle buttons**

Add this new event-wiring block near the other `addEventListener` calls (after the existing `team-filter`/`season-filter` listeners, `templates/index.html:317-326`):

```js
  document.querySelectorAll(".pos-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const pos = btn.dataset.pos;
      if (activePositions.has(pos)) activePositions.delete(pos);
      else activePositions.add(pos);
      btn.classList.toggle("active");
      render();
    });
  });
```

- [ ] **Step 7: Add position filtering to the render chain and call `updateHeaderOffset()`**

In `render()` (`templates/index.html:435-479`), replace:

```js
    // Filter
    let rows = activeTeam
      ? data.filter(p => p.team_abbrev === activeTeam)
      : data;
```

with:

```js
    // Filter
    let rows = data;
    if (activeTeam) rows = rows.filter(p => p.team_abbrev === activeTeam);
    if (activePositions.size > 0) rows = rows.filter(p => activePositions.has(p.position_code));
```

Then, at the very end of `render()` (right after the `isEmpty` block, before the closing `}`), add:

```js
    updateHeaderOffset();
```

- [ ] **Step 8: Call `updateHeaderOffset()` once on initial load**

Change the final line of the script (`templates/index.html:489`), from:

```js
  buildHeader();
```

to:

```js
  buildHeader();
  updateHeaderOffset();
```

- [ ] **Step 9: Manual verification**

```bash
lsof -ti :5000 | xargs kill -9
python app.py &
sleep 1
open http://127.0.0.1:5000
```

In the browser:
- Confirm the header now shows two rows: the original controls, then a row of C/L/R/D/G buttons.
- Click "C" — table narrows to centers only; button visually activates (colored background).
- Click "D" too — table shows centers and defensemen combined; click "C" again to deactivate — table shows defensemen only.
- Scroll the table down — confirm the sticky column headers (`thead th`) sit directly under the taller header bar with no gap or overlap.

- [ ] **Step 10: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add templates/index.html
git commit -m "feat: add position filter and split header into rows"
```

---

### Task 4: Frontend — Stats-tab threshold filters

**Files:**
- Modify: `templates/index.html:7-186` (`<style>` block)
- Modify: `<header>` markup (add row3, added in Task 3)
- Modify: JS state block
- Modify: `render()`
- Modify: tab-btn click listener (`templates/index.html:328-345` in the original file)

**Interfaces:**
- Consumes: `activeTab` (existing), `updateHeaderOffset()` (Task 3).
- Produces: `let statMins = { gp, goals, assists, points }` — not consumed elsewhere in this plan, but keep the name exact for Task 9's count-label check.

- [ ] **Step 1: Add stat-input CSS**

Add after the `.pos-toggle` rules added in Task 3:

```css
    .stat-input {
      width: 64px;
      background: #21262d;
      color: #e6edf3;
      border: 1px solid #30363d;
      border-radius: 6px;
      padding: 5px 8px;
      font-size: 13px;
    }

    .stat-input:focus { outline: none; border-color: #58a6ff; }
```

- [ ] **Step 2: Add the row3 markup**

Add this new `<div>` as a sibling directly after the `.header-row2` div (inside `<header>`, after the position-toggle row added in Task 3):

```html
  <div class="header-row3" id="stat-filter-row" style="display:none">
    <label for="min-gp">GP≥</label>
    <input type="number" min="0" class="stat-input" id="min-gp">
    <label for="min-goals">G≥</label>
    <input type="number" min="0" class="stat-input" id="min-goals">
    <label for="min-assists">A≥</label>
    <input type="number" min="0" class="stat-input" id="min-assists">
    <label for="min-points">Pts≥</label>
    <input type="number" min="0" class="stat-input" id="min-points">
  </div>
```

- [ ] **Step 3: Add `statMins` state**

In the JS state block, after `let activePositions = new Set();`:

```js
  let statMins = { gp: null, goals: null, assists: null, points: null };
```

- [ ] **Step 4: Wire the four inputs**

Add near the position-toggle wiring from Task 3:

```js
  function wireStatInput(id, key) {
    document.getElementById(id).addEventListener("input", e => {
      const v = e.target.value;
      statMins[key] = v === "" ? null : Number(v);
      render();
    });
  }
  wireStatInput("min-gp", "gp");
  wireStatInput("min-goals", "goals");
  wireStatInput("min-assists", "assists");
  wireStatInput("min-points", "points");
```

- [ ] **Step 5: Add threshold filtering to the render chain**

In `render()`, immediately after the `activePositions` filter line added in Task 3:

```js
    if (activeTab === "stats") {
      if (statMins.gp      != null) rows = rows.filter(p => (p.gp      ?? 0) >= statMins.gp);
      if (statMins.goals   != null) rows = rows.filter(p => (p.goals   ?? 0) >= statMins.goals);
      if (statMins.assists != null) rows = rows.filter(p => (p.assists ?? 0) >= statMins.assists);
      if (statMins.points  != null) rows = rows.filter(p => (p.points  ?? 0) >= statMins.points);
    }
```

- [ ] **Step 6: Show/hide row3 on tab switch**

In the tab-btn click listener, find:

```js
      activeTab = tab;
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
```

and add immediately after it:

```js
      document.getElementById("stat-filter-row").style.display = tab === "stats" ? "" : "none";
```

(`updateHeaderOffset()` does not need an extra call site here — it already runs at the end of every `render()`, added in Task 3, and this tab handler always ends by calling `render()` directly or via `loadStats()`.)

- [ ] **Step 7: Manual verification**

```bash
lsof -ti :5000 | xargs kill -9
python app.py &
sleep 1
open http://127.0.0.1:5000
```

In the browser:
- Click the "Stats" tab — confirm a third header row appears with GP≥/G≥/A≥/Pts≥ inputs, and the sticky column headers still don't overlap.
- Type `50` into Pts≥ — confirm only players with 50+ points remain.
- Clear the input — confirm all players return.
- Click back to "Bio" tab — confirm row3 disappears entirely (not just visually hidden with leftover space) and filters have no effect on the Bio tab.

- [ ] **Step 8: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add templates/index.html
git commit -m "feat: add GP/G/A/Pts minimum-threshold filters on Stats tab"
```

---

### Task 5: Frontend — team popup dropdown (full names + logos)

**Files:**
- Modify: `<header>` markup (inside `.controls`, replacing the `team-filter` `<select>`)
- Modify: `<style>` block
- Modify: JS state block, teams-fetch block, event listeners

**Interfaces:**
- Consumes: `/api/teams` (Task 1) — already sorted alphabetically by `common_name`.
- Produces: `let teamsList` (array of `{abbrev, common_name}`), `function logoUrl(abbrev)`. `activeTeam` (existing variable) keeps its meaning (selected abbrev or `""`).

- [ ] **Step 1: Add popup-select CSS**

Add after the `.stat-input` rules from Task 4:

```css
    .popup-select { position: relative; }

    .popup-select-btn {
      display: flex;
      align-items: center;
      gap: 6px;
      background: #21262d;
      color: #e6edf3;
      border: 1px solid #30363d;
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 13px;
      font-family: inherit;
      cursor: pointer;
      min-width: 160px;
    }

    .popup-select-btn:focus { outline: none; border-color: #58a6ff; }

    .popup-select-menu {
      position: absolute;
      top: calc(100% + 4px);
      left: 0;
      background: #21262d;
      border: 1px solid #30363d;
      border-radius: 6px;
      max-height: 320px;
      overflow-y: auto;
      z-index: 20;
      min-width: 220px;
    }

    .popup-select-row {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      font-size: 13px;
      cursor: pointer;
      white-space: nowrap;
    }

    .popup-select-row:hover { background: #1c2129; }

    .popup-select-row img {
      width: 16px;
      height: 16px;
      object-fit: contain;
    }
```

- [ ] **Step 2: Replace the team `<select>` markup**

Inside `.controls`, replace:

```html
      <label for="team-filter">Team</label>
      <select id="team-filter">
        <option value="">All Teams</option>
      </select>
```

with:

```html
      <div class="popup-select" id="team-popup">
        <button type="button" class="popup-select-btn" id="team-popup-btn">All Teams</button>
        <div class="popup-select-menu" id="team-popup-menu" style="display:none"></div>
      </div>
```

- [ ] **Step 3: Add `teamsList` state**

In the JS state block, after `let statMins = ...;`:

```js
  let teamsList = [];
```

- [ ] **Step 4: Replace the teams-fetch block**

Replace:

```js
  fetch("/api/teams")
    .then(r => r.json())
    .then(teams => {
      const sel = document.getElementById("team-filter");
      teams.forEach(t => {
        const opt = document.createElement("option");
        opt.value = t.abbrev;
        opt.textContent = `${t.abbrev} — ${t.common_name}`;
        sel.appendChild(opt);
      });
    });
```

with:

```js
  function logoUrl(abbrev) {
    return `https://assets.nhle.com/logos/nhl/svg/${abbrev}_light.svg`;
  }

  function renderTeamPopup() {
    const menu = document.getElementById("team-popup-menu");
    menu.innerHTML = "";

    const allRow = document.createElement("div");
    allRow.className = "popup-select-row";
    allRow.textContent = "All Teams";
    allRow.addEventListener("click", () => selectTeam("", "All Teams"));
    menu.appendChild(allRow);

    teamsList.forEach(t => {
      const row = document.createElement("div");
      row.className = "popup-select-row";
      const img = document.createElement("img");
      img.src = logoUrl(t.abbrev);
      img.alt = "";
      img.onerror = () => { img.style.visibility = "hidden"; };
      row.appendChild(img);
      const span = document.createElement("span");
      span.textContent = t.common_name;
      row.appendChild(span);
      row.addEventListener("click", () => selectTeam(t.abbrev, t.common_name));
      menu.appendChild(row);
    });
  }

  function selectTeam(abbrev, label) {
    activeTeam = abbrev;
    document.getElementById("team-popup-btn").textContent = label;
    document.getElementById("team-popup-menu").style.display = "none";
    render();
  }

  fetch("/api/teams")
    .then(r => r.json())
    .then(teams => {
      teamsList = teams;
      renderTeamPopup();
    });
```

- [ ] **Step 5: Remove the old `team-filter` change listener and wire the popup button**

Remove:

```js
  document.getElementById("team-filter").addEventListener("change", e => {
    activeTeam = e.target.value;
    render();
  });
```

Add in its place:

```js
  document.getElementById("team-popup-btn").addEventListener("click", e => {
    e.stopPropagation();
    const menu = document.getElementById("team-popup-menu");
    menu.style.display = menu.style.display === "none" ? "" : "none";
  });

  document.addEventListener("click", e => {
    if (!e.target.closest("#team-popup")) {
      document.getElementById("team-popup-menu").style.display = "none";
    }
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      document.getElementById("team-popup-menu").style.display = "none";
    }
  });
```

- [ ] **Step 6: Manual verification**

```bash
lsof -ti :5000 | xargs kill -9
python app.py &
sleep 1
open http://127.0.0.1:5000
```

In the browser:
- Click the Team button (shows "All Teams") — a popup opens listing full team names alphabetically, each with a small logo to the left.
- Confirm logos render (or, if any 404, that team's row just has no visible icon — no broken-image glyph, no layout shift).
- Click a team — popup closes, button label updates to that team's full name, table filters to that team only (Team column badges in rows are unaffected, still abbreviations).
- Click elsewhere on the page — popup closes if still open. Reopen it and press Escape — it closes.

- [ ] **Step 7: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add templates/index.html
git commit -m "feat: replace team filter select with popup dropdown (full names + logos)"
```

---

### Task 6: Frontend — season multi-select checkbox dropdown

**Files:**
- Modify: `<header>` markup (replacing the `season-filter` `<select>`)
- Modify: JS state block, `loadStats`, `currentData`, event listeners, tab-btn click listener

**Interfaces:**
- Consumes: `/api/players/stats?seasons=...` (Task 2).
- Produces: `let activeSeasons` (array, replaces the old `activeSeason` string — no other task in this plan reads the old name), `function seasonsKey(seasons)`. `statsData` is now keyed by `seasonsKey(...)` output instead of a raw season id.

- [ ] **Step 1: Replace the season `<select>` markup**

Inside `.controls`, replace:

```html
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
```

with:

```html
      <div class="popup-select" id="season-popup">
        <button type="button" class="popup-select-btn" id="season-popup-btn">2025–26</button>
        <div class="popup-select-menu" id="season-popup-menu" style="display:none"></div>
      </div>
```

- [ ] **Step 2: Replace `activeSeason` with `activeSeasons` and add `SEASONS`**

In the JS state block, replace:

```js
  let activeSeason = "20252026";
```

with:

```js
  let activeSeasons = ["20252026"];

  const SEASONS = [
    { id: "20252026", label: "2025–26" },
    { id: "20242025", label: "2024–25" },
    { id: "20232024", label: "2023–24" },
    { id: "20222023", label: "2022–23" },
    { id: "20212022", label: "2021–22" },
    { id: "20202021", label: "2020–21" },
  ];
```

- [ ] **Step 3: Replace `loadStats` and `currentData` for multi-season keys**

Replace the existing `loadStats` function:

```js
  function loadStats(season) {
    if (statsData[season]) { render(); return; }
    showLoading(true);
    fetch(`/api/players/stats?season=${season}`)
      .then(r => r.json())
      .then(data => {
        statsData[season] = data;
        showLoading(false);
        render();
      });
  }
```

with:

```js
  function seasonsKey(seasons) {
    return seasons.includes("all") ? "all" : [...seasons].sort().join(",");
  }

  function loadStats(seasons) {
    const key = seasonsKey(seasons);
    if (statsData[key]) { render(); return; }
    showLoading(true);
    fetch(`/api/players/stats?seasons=${seasons.join(",")}`)
      .then(r => r.json())
      .then(data => {
        statsData[key] = data;
        showLoading(false);
        render();
      });
  }
```

Replace `currentData()`:

```js
  function currentData() {
    return activeTab === "bio" ? bioData : (statsData[activeSeason] || []);
  }
```

with:

```js
  function currentData() {
    return activeTab === "bio" ? bioData : (statsData[seasonsKey(activeSeasons)] || []);
  }
```

- [ ] **Step 4: Add the season popup rendering + toggle logic**

Add these functions near the team-popup functions from Task 5:

```js
  function seasonButtonLabel() {
    if (activeSeasons.includes("all")) return "All Seasons (Career)";
    if (activeSeasons.length === 1) {
      return SEASONS.find(s => s.id === activeSeasons[0])?.label || activeSeasons[0];
    }
    return `${activeSeasons.length} Seasons`;
  }

  function toggleSeason(id) {
    if (id === "all") {
      activeSeasons = activeSeasons.includes("all") ? ["20252026"] : ["all"];
    } else if (activeSeasons.includes("all")) {
      activeSeasons = [id];
    } else if (activeSeasons.includes(id)) {
      if (activeSeasons.length > 1) activeSeasons = activeSeasons.filter(s => s !== id);
      // else: no-op — at least one season must always remain selected
    } else {
      activeSeasons = [...activeSeasons, id];
    }
    renderSeasonPopup();
    document.getElementById("season-popup-btn").textContent = seasonButtonLabel();
    if (activeTab === "stats") loadStats(activeSeasons);
  }

  function renderSeasonPopup() {
    const menu = document.getElementById("season-popup-menu");
    menu.innerHTML = "";

    const allRow = document.createElement("div");
    allRow.className = "popup-select-row";
    const allCheck = document.createElement("input");
    allCheck.type = "checkbox";
    allCheck.checked = activeSeasons.includes("all");
    allRow.appendChild(allCheck);
    allRow.appendChild(document.createTextNode("All Seasons (Career)"));
    allRow.addEventListener("click", () => toggleSeason("all"));
    menu.appendChild(allRow);

    SEASONS.forEach(s => {
      const row = document.createElement("div");
      row.className = "popup-select-row";
      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = activeSeasons.includes(s.id);
      row.appendChild(check);
      row.appendChild(document.createTextNode(s.label));
      row.addEventListener("click", () => toggleSeason(s.id));
      menu.appendChild(row);
    });
  }

  renderSeasonPopup();
```

- [ ] **Step 5: Remove the old `season-filter` listener and wire the new popup button**

Remove:

```js
  document.getElementById("season-filter").addEventListener("change", e => {
    activeSeason = e.target.value;
    if (activeTab === "stats") loadStats(activeSeason);
  });
```

Add in its place, and extend the shared outside-click/Escape handlers added in Task 5 to also close this popup:

```js
  document.getElementById("season-popup-btn").addEventListener("click", e => {
    e.stopPropagation();
    const menu = document.getElementById("season-popup-menu");
    menu.style.display = menu.style.display === "none" ? "" : "none";
  });
```

Then update the two handlers added in Task 5, Step 5:

```js
  document.addEventListener("click", e => {
    if (!e.target.closest("#team-popup")) document.getElementById("team-popup-menu").style.display = "none";
    if (!e.target.closest("#season-popup")) document.getElementById("season-popup-menu").style.display = "none";
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      document.getElementById("team-popup-menu").style.display = "none";
      document.getElementById("season-popup-menu").style.display = "none";
    }
  });
```

- [ ] **Step 6: Update the tab-btn click listener's stats branch**

Find (inside the tab-btn click listener):

```js
      } else {
        sortKey = "points"; sortDir = "desc";
        loadStats(activeSeason);
        return;  // loadStats calls render when done
      }
```

Change `loadStats(activeSeason)` to:

```js
        loadStats(activeSeasons);
```

- [ ] **Step 7: Manual verification**

```bash
lsof -ti :5000 | xargs kill -9
python app.py &
sleep 1
open http://127.0.0.1:5000
```

In the browser:
- Click the Season button (shows "2025–26") — popup opens with "All Seasons (Career)" plus 6 season checkboxes, only 2025–26 checked.
- Try unchecking 2025–26 while it's the only one checked — confirm it stays checked (can't reach zero seasons).
- Check "2023–24" too — button label becomes "2 Seasons". Switch to Stats tab — confirm totals for a known player equal the manual curl-sum check from Task 2, Step 3.
- Check "All Seasons (Career)" — confirm it unchecks the specific seasons and the table matches the old career-totals behavior; then check a specific season again — confirm "All Seasons (Career)" unchecks itself.

- [ ] **Step 8: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add templates/index.html
git commit -m "feat: replace season select with multi-select checkbox dropdown"
```

---

### Task 7: Frontend — name search (live filter)

**Files:**
- Modify: `<header>` markup (add search box before `.controls`)
- Modify: `<style>` block
- Modify: JS state block, `render()`

**Interfaces:**
- Produces: `let searchText` (string) — consumed by Task 8 (autocomplete suggestions read the same variable's source input).

- [ ] **Step 1: Add search-box CSS**

Add after the `.popup-select-row img` rule from Task 5:

```css
    .search-wrap { position: relative; }

    #search-input {
      background: #21262d;
      color: #e6edf3;
      border: 1px solid #30363d;
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 13px;
      width: 200px;
    }

    #search-input:focus { outline: none; border-color: #58a6ff; }
```

- [ ] **Step 2: Add the search box markup**

Inside `.header-row1`, right after `<h1>🏒 NHL Players</h1>` and before `<div class="controls">`:

```html
    <div class="search-wrap" id="search-wrap">
      <input type="text" id="search-input" placeholder="Search players…" autocomplete="off">
    </div>
```

- [ ] **Step 3: Add `searchText` state**

In the JS state block, after `let teamsList = [];`:

```js
  let searchText = "";
```

- [ ] **Step 4: Wire the input**

Add near the other event listeners:

```js
  document.getElementById("search-input").addEventListener("input", e => {
    searchText = e.target.value;
    render();
  });
```

- [ ] **Step 5: Add search filtering to the render chain**

In `render()`, immediately after the `activePositions` filter line (before the `activeTab === "stats"` threshold block from Task 4):

```js
    if (searchText) {
      const q = searchText.toLowerCase();
      rows = rows.filter(p =>
        (p.first_name || "").toLowerCase().includes(q) ||
        (p.last_name  || "").toLowerCase().includes(q)
      );
    }
```

- [ ] **Step 6: Manual verification**

```bash
lsof -ti :5000 | xargs kill -9
python app.py &
sleep 1
open http://127.0.0.1:5000
```

In the browser: type a partial first or last name into the search box — confirm the table narrows live on every keystroke. Clear the box — confirm the full (or other-filters-applied) table returns.

- [ ] **Step 7: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add templates/index.html
git commit -m "feat: add live name search filter"
```

---

### Task 8: Frontend — autocomplete suggestion dropdown

**Files:**
- Modify: `<style>` block
- Modify: search box markup (add suggestion container)
- Modify: `render()` (tag rows with `data-player-id`)
- Modify: search-input listener; outside-click/Escape handlers (from Task 5/6)

**Interfaces:**
- Consumes: `bioData` (existing), `searchText` (Task 7).

- [ ] **Step 1: Add suggestion-list CSS**

Add after the `#search-input:focus` rule from Task 7:

```css
    .suggestion-list {
      position: absolute;
      top: calc(100% + 4px);
      left: 0;
      background: #21262d;
      border: 1px solid #30363d;
      border-radius: 6px;
      min-width: 200px;
      max-height: 260px;
      overflow-y: auto;
      z-index: 20;
    }

    .suggestion-item {
      padding: 6px 10px;
      font-size: 13px;
      cursor: pointer;
      white-space: nowrap;
    }

    .suggestion-item:hover { background: #1c2129; }

    tbody tr.row-highlight {
      background: #1f6feb66 !important;
      transition: background-color 0.3s ease;
    }
```

- [ ] **Step 2: Add the suggestion container to the search box markup**

Change the `.search-wrap` div from Task 7:

```html
    <div class="search-wrap" id="search-wrap">
      <input type="text" id="search-input" placeholder="Search players…" autocomplete="off">
    </div>
```

to:

```html
    <div class="search-wrap" id="search-wrap">
      <input type="text" id="search-input" placeholder="Search players…" autocomplete="off">
      <div class="suggestion-list" id="search-suggestions" style="display:none"></div>
    </div>
```

- [ ] **Step 3: Add `renderSuggestions` and `selectSuggestion`**

Add these functions near the other popup functions:

```js
  function renderSuggestions(query) {
    const box = document.getElementById("search-suggestions");
    if (!query) { box.style.display = "none"; box.innerHTML = ""; return; }
    const q = query.toLowerCase();
    const matches = bioData.filter(p =>
      (p.first_name || "").toLowerCase().includes(q) ||
      (p.last_name  || "").toLowerCase().includes(q)
    ).slice(0, 8);
    box.innerHTML = "";
    if (matches.length === 0) { box.style.display = "none"; return; }
    matches.forEach(p => {
      const item = document.createElement("div");
      item.className = "suggestion-item";
      item.textContent = `${p.first_name} ${p.last_name}`;
      item.addEventListener("click", () => selectSuggestion(p));
      box.appendChild(item);
    });
    box.style.display = "";
  }

  function selectSuggestion(player) {
    document.getElementById("search-input").value = "";
    searchText = "";
    document.getElementById("search-suggestions").style.display = "none";
    render();
    requestAnimationFrame(() => {
      const row = document.querySelector(`tr[data-player-id="${player.player_id}"]`);
      if (!row) return;
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      row.classList.add("row-highlight");
      setTimeout(() => row.classList.remove("row-highlight"), 1500);
    });
  }
```

- [ ] **Step 4: Call `renderSuggestions` from the search-input listener**

Change the listener from Task 7, Step 4:

```js
  document.getElementById("search-input").addEventListener("input", e => {
    searchText = e.target.value;
    render();
  });
```

to:

```js
  document.getElementById("search-input").addEventListener("input", e => {
    searchText = e.target.value;
    renderSuggestions(searchText);
    render();
  });
```

- [ ] **Step 5: Tag each table row with the player id**

In `render()`, find the row-building loop:

```js
    rows.forEach(p => {
      const tr = document.createElement("tr");
      cols.forEach(col => tr.appendChild(renderCell(col, p)));
      tbody.appendChild(tr);
    });
```

change to:

```js
    rows.forEach(p => {
      const tr = document.createElement("tr");
      tr.dataset.playerId = p.player_id;
      cols.forEach(col => tr.appendChild(renderCell(col, p)));
      tbody.appendChild(tr);
    });
```

- [ ] **Step 6: Extend the shared outside-click/Escape handlers**

Update the two handlers from Task 6, Step 5 to also close the suggestions box:

```js
  document.addEventListener("click", e => {
    if (!e.target.closest("#team-popup")) document.getElementById("team-popup-menu").style.display = "none";
    if (!e.target.closest("#season-popup")) document.getElementById("season-popup-menu").style.display = "none";
    if (!e.target.closest("#search-wrap")) document.getElementById("search-suggestions").style.display = "none";
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      document.getElementById("team-popup-menu").style.display = "none";
      document.getElementById("season-popup-menu").style.display = "none";
      document.getElementById("search-suggestions").style.display = "none";
    }
  });
```

- [ ] **Step 7: Manual verification**

```bash
lsof -ti :5000 | xargs kill -9
python app.py &
sleep 1
open http://127.0.0.1:5000
```

In the browser: type a partial name — confirm up to 8 matching suggestions appear below the box (and the table still live-filters underneath, per Task 7). Click one — confirm the search box clears, the table reverts to unfiltered (or other-filters-applied), and the page scrolls to that player's row with a brief highlight flash. Click elsewhere / press Escape while the suggestion box is open — confirm it closes.

- [ ] **Step 8: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add templates/index.html
git commit -m "feat: add autocomplete suggestion dropdown with scroll-to-highlight"
```

---

### Task 9: Integration — count label + full manual verification pass

**Files:**
- Modify: `render()` (count-label logic)

**Interfaces:**
- Consumes: `activeTeam`, `activePositions`, `searchText`, `statMins`, `activeTab` (all from prior tasks).

- [ ] **Step 1: Update the count-label logic to reflect all active filters**

In `render()`, replace:

```js
    const total = data.length;
    const shown = rows.length;
    document.getElementById("count-label").textContent =
      activeTeam ? `${shown} of ${total} players` : `${total} players`;
```

with:

```js
    const total = data.length;
    const shown = rows.length;
    const filtersActive = !!activeTeam || activePositions.size > 0 || !!searchText ||
      (activeTab === "stats" && Object.values(statMins).some(v => v != null));
    document.getElementById("count-label").textContent =
      filtersActive ? `${shown} of ${total} players` : `${total} players`;
```

- [ ] **Step 2: Manual verification of the count label alone**

```bash
lsof -ti :5000 | xargs kill -9
python app.py &
sleep 1
open http://127.0.0.1:5000
```

Type into the search box (no team/position/stat filters active) — confirm the count label switches from `"705 players"` (or whatever the full count is) to `"N of 705 players"`. Clear it — confirm it reverts. Repeat with position toggles only, and with stat thresholds only (Stats tab).

- [ ] **Step 3: Full manual verification pass (spec's Testing Plan, all 9 items)**

Run through every item from `docs/superpowers/specs/2026-07-02-advanced-filters-design.md`'s Testing Plan in one sitting, in this order:

1. Each new filter (search, position, season, stat thresholds, team) narrows the visible rows correctly in isolation.
2. Filters combine correctly — e.g. set position=C, type "mcd" in search, set Pts≥50 on the Stats tab, confirm only matching rows remain.
3. Stat threshold row (row3) is visible on Stats tab, absent on Bio tab, and has no effect when the Bio tab is active.
4. Selecting "All Seasons (Career)" clears specific-season checkboxes and vice versa; at least one season stays selected at all times.
5. Pick 2-3 seasons in the season popup; confirm summed totals for a spot-checked player match manual addition of their per-season stats (reuse the curl commands from Task 2, Step 3).
6. Player count label reflects the fully-filtered row count for every filter combination, not just the team filter.
7. Type a partial name; confirm both the live table filter and the ≤8-item suggestion dropdown appear; click a suggestion; confirm search clears, table reverts, and the target row scrolls into view and highlights briefly.
8. Team popup lists teams alphabetically by full name with a logo per row; selecting one filters the table exactly as the old `<select>` did; a missing/404 logo doesn't break the row's layout.
9. All three popups (team, season, suggestions) close on outside click and on Escape, and don't interfere with each other when opened one after another.

- [ ] **Step 4: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add templates/index.html
git commit -m "feat: make player count reflect all active filters; finish manual verification pass"
```
