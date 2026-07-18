# Player Bio Card — Design

> **Superseded 2026-07-17.** During spec review, scope expanded to a full
> frontend replatform onto React + Tailwind + shadcn/ui (not just the modal).
> Sequencing decision: replatform first as its own sub-project
> (`docs/superpowers/specs/2026-07-17-frontend-replatform-design.md`), then
> redo this Bio card design to build natively on the new stack instead of as
> an isolated React island in a vanilla page. Kept here for history — the
> "Decision reversal," "Build Pipeline," and "isolated modal" framing below no
> longer reflect the intended approach.

## Context

The player table (`templates/index.html`) currently has a Bio/Stats tab toggle:
Bio shows `BIO_COLS` (number, name, position, S/C, height, weight, birth date,
country, team), Stats shows `STAT_COLS` (season totals: GP, G, A, Pts, +/-, PIM,
PPG, SHG, Shots, SH%, Avg TOI, plus goalie-only columns). Both read from
`/api/players` and `/api/players/stats` respectively (`app.py`).

This spec:
1. Removes the Bio/Stats toggle — the table always shows stats (season totals).
2. Adds a "Player Bio card": clicking a player's name opens a modal showing their
   bio info, career/season stat totals, and an advanced-stats section (WAR/percentile
   metrics), modeled visually on a JFresh Hockey-style card
   (`~/Desktop/head-shot-example/Screenshot 2026-07-17 at 11.22.58 PM.png`).

**Decision reversal:** the 2026-07-02 decision log entry chose vanilla HTML/CSS/JS
over React specifically to avoid a build toolchain. This spec reintroduces React
(+ Vite + Recharts), scoped *only* to the new Bio card component — the existing
table/filter/search code in `index.html` and `search.js` stays vanilla JS,
untouched architecturally. Rationale: Recharts (chosen for the trend-line charts)
requires React as a peer dependency; hand-rolling equivalent SVG charts was
considered and rejected in favor of Recharts for chart quality or reduced future
compute needs. See Build Pipeline below for how the two worlds coexist.

## Scope

In scope:
1. Remove the Bio/Stats tab toggle and `BIO_COLS`. The table always renders
   `STAT_COLS`. The season selector, position filters, search, and stat-min
   filters (GP/G/A/Pts ≥) all remain, unconditionally visible (no more
   `stat-filter-row` show/hide keyed on `activeTab`).
2. Player name cells (`first_name`/`last_name`) become clickable, opening the
   Bio card modal for that player.
3. New `player_advanced_stats` table (schema below) to hold WAR/percentile
   metrics, one row per player per season. **Not populated by this change** — a
   separate in-progress effort is compiling this data; this spec only creates the
   schema and a dev-only mock seed script so the UI can be built and tested now.
   A real loader script lands as a follow-up once that data's format is known.
4. New endpoint `GET /api/players/<id>/card?seasons=<comma-list>` bundling bio +
   stat totals + advanced-stats rows for the modal's single fetch.
5. React (Vite build) + Recharts Bio card component, mounted into the existing
   page via a `<div id="bio-card-root">`, loaded only when a name is clicked.

Out of scope (no data source exists — explicitly deferred, not forgotten):
- Cap hit / contract length (would need a new data source, e.g. PuckPedia — not
  currently ingested anywhere in this project).
- The "4th Liner"-style role/usage label from the example card.
- Team primary-color accents (not stored; card uses the existing site accent
  blue `#58a6ff` instead of a per-team color).
- Populating real advanced-stats data — tracked as a follow-up once the other
  session's output format is known.
- Any change to career-vs-season-sum semantics already established by the
  existing `/api/players/stats` endpoint.

## Frontend Design

### Table changes (`templates/index.html`, `static/js/search.js`)

- Delete `BIO_COLS`, the `.tab-group`/`.tab-btn` markup and its click handler,
  and `activeTab` state. `activeCols()` always returns `STAT_COLS`.
- `stat-filter-row` (GP≥/G≥/A≥/Pts≥) loses its `display:none` toggle — always
  visible, same as the position filter row.
- On page load, stats for the default season (`20252026`) load immediately
  (today this only happens after switching to the Stats tab) — `loadStats()`
  is now called on initial page load instead of being gated behind the tab
  click handler.
- In `renderCell()`, the `first_name`/`last_name` cells render as a clickable
  `<span class="player-link">` (styled as a link — accent-blue text,
  pointer cursor, underline on hover) instead of plain text. Click handler calls
  `window.openPlayerCard(player.player_id)`.

### Bio card modal

- A `<div id="bio-card-root">` sits at the end of `<body>`, empty until a card
  is opened. `window.openPlayerCard(playerId)` is a function exported by the
  React bundle (attached to `window` from its entry file) — this is the sole
  integration point between the vanilla table code and the React modal.
- Modal behavior: dark overlay (click-outside or Escape closes it, matching the
  existing popup-dismiss pattern already used for team/season dropdowns),
  loading spinner while `/api/players/<id>/card` resolves, retry button on
  fetch failure.
- Card layout (dark theme, matching the example's visual density):
  - **Header row:** headshot (`headshot_url`, falls back to a placeholder
    silhouette if null/broken — most historical players won't have one),
    player name, team badge (abbrev, same styling as the table's), position
    badge.
  - **Bio row:** age (computed server-side from `birth_date`), height, weight,
    shoots/catches, birth city/state/country, draft info
    (`draft_overall`/`round`/`pick`/`team_abbrev` — rendered as e.g.
    "Round 2, Pick 45 (2019, TOR)", or "Undrafted" if `draft_year` is null).
  - **Stat totals row:** tiles for the season/career totals already tracked —
    GP, G, A, Pts, +/-, PIM, PPG, SHG, Shots, SH%, Avg TOI (or the goalie
    equivalents — W/L/OTL/SO/SV%/GAA — when `position_code === "G"`). Same
    season-selection semantics as the main table (respects whatever seasons
    are currently active there).
  - **Advanced stats section:** percentile tiles (WAR / EV Offence / EV
    Defence / PP / PK / Finishing / Goals / 1st Assists / Penalties /
    Competition / Teammates) for the most recent season with data, plus two
    Recharts `LineChart`s (WAR percentile trend, Offence/Defence/Finishing
    trend) across all seasons the player has advanced-stats rows for. If the
    player has zero `player_advanced_stats` rows, this whole section is
    replaced with a single "Advanced stats not yet available for this
    player" message — never fabricated/placeholder numbers.

## Build Pipeline

New `frontend/` directory at the repo root:
```
frontend/
  package.json       # react, react-dom, recharts, vite, @vitejs/plugin-react
  vite.config.js      # build.outDir -> ../static/js/bio-card, fixed (unhashed) entry filenames
  src/
    main.jsx          # attaches window.openPlayerCard, mounts/unmounts the modal root
    PlayerBioCard.jsx
    charts/
      WarTrendChart.jsx
      OffenceDefenceFinishingChart.jsx
```
- `npm install && npm run build` (run from `frontend/`) produces
  `static/js/bio-card/bio-card.js` (+ `.css`). Fixed filenames (no content
  hash) so `index.html`'s `<script>`/`<link>` tags don't need to change per
  build — acceptable at this project's scale and consistent with not adding a
  Jinja-manifest-reading layer for one bundle.
- Build output (`static/js/bio-card/`) is **git-ignored**, same treatment as
  `.venv/` — a generated artifact, not source. `README.md`'s setup section
  gains a step: install Node deps and build the bundle before `python app.py`,
  mirroring the existing "create venv, pip install" step.
- This is the only place React/Vite/Node enter the project. `app.py`,
  `templates/index.html`'s non-modal markup, and `search.js` have no build-time
  dependency and keep running exactly as today if `frontend/` is never touched.

## Backend Design

### New table: `player_advanced_stats`

```sql
CREATE TABLE IF NOT EXISTS player_advanced_stats (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id           INTEGER NOT NULL REFERENCES players(player_id),
    season_id           TEXT    NOT NULL,
    war_pct             REAL,
    ev_offence_pct      REAL,
    ev_defence_pct      REAL,
    pp_pct              REAL,
    pk_pct              REAL,
    finishing_pct       REAL,
    goals_pct           REAL,
    first_assists_pct   REAL,
    penalties_pct       REAL,
    competition_pct     REAL,
    teammates_pct       REAL,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE (player_id, season_id)
);
```
Added to `create_all_tables()`'s table list in `src/database.py`, alongside a
new `upsert_advanced_stats(conn, row)` helper following the existing
`INSERT OR REPLACE` pattern used by `upsert_season_stats` — safe here since,
unlike the multi-phase `players` table, this table has exactly one writer
(whatever loads advanced stats) and no partial-column-ownership concern.

### New endpoint: `GET /api/players/<id>/card`

Query param `seasons` (comma-separated, same format as `/api/players/stats`;
defaults to `20252026`). Response shape:
```jsonc
{
  "bio": { "player_id": ..., "first_name": ..., "last_name": ..., "age": 27,
           "position_code": ..., "height": "6'1\"", "weight_pounds": ...,
           "shoots_catches": ..., "birth_city": ..., "birth_state_province": ...,
           "birth_country": ..., "draft_year": ..., "draft_round": ...,
           "draft_pick": ..., "draft_overall": ..., "draft_team_abbrev": ...,
           "headshot_url": ..., "team_abbrev": ..., "team_name": ... },
  "stats": { /* same shape as one row of /api/players/stats */ },
  "advanced": [ /* zero or more player_advanced_stats rows, one per season,
                   sorted by season_id ascending, for chart plotting */ ]
}
```
`age` is computed in Python from `birth_date` (`date.today()` minus birth date,
whole years) — the only genuinely new derived field. Reuses `_height_str()`
already defined in `app.py`. `stats` reuses the existing per-season/career
summation logic from `api_players_stats` (refactored into a shared
`_fetch_player_stats(conn, player_id, seasons)` helper so both routes share one
query path rather than duplicating the SQL).

### Dev-only mock seed

`scripts/seed_advanced_stats.py`: inserts a handful of plausible
`player_advanced_stats` rows (2-3 real `player_id`s already in the DB, 3 seasons
each) via `upsert_advanced_stats`, purely so the card's advanced-stats section
and charts have something to render during development. Clearly labeled as
throwaway/dev-only in a module docstring — not run by any ETL pipeline or CI
step, not a source of truth.

## Testing Plan

- **Backend (pytest, `tests/test_app_helpers.py` or a new
  `tests/test_bio_card.py`):** `_fetch_player_stats` shared helper returns
  identical results to the existing per-season and "all seasons" code paths it
  replaces (regression coverage for the refactor); `/api/players/<id>/card`
  returns bio + stats + empty `advanced` list for a player with no advanced-stats
  rows, and a populated `advanced` list (sorted by season) after seeding one via
  `upsert_advanced_stats` in a test fixture; `age` computed correctly for a
  known `birth_date` fixture (including the leap-year/not-yet-had-birthday-
  this-year edge case); 404 (or empty bio) for an unknown `player_id`.
- **Frontend (Vitest, colocated in `frontend/src/*.test.jsx`, wired into the
  same `npm run` scripts used by CI — per the existing repo convention of
  adding a new test runner and its CI step in the same change):** the Bio card
  renders bio/stat fields from a mocked fetch response; renders the "not yet
  available" message when `advanced` is empty instead of rendering percentile
  tiles/charts; percentile tiles and both Recharts trend lines render with
  correct values when `advanced` has data.
- **`.github/workflows/ci.yml`:** gains a `frontend` job (or step) —
  `npm ci && npm test && npm run build` in `frontend/` — run alongside the
  existing Python test/audit steps, so a broken build or failing Vitest test
  blocks merge exactly like a failing pytest does today.
- **Manual verification** (`python app.py` after `npm run build`, per `run`/
  `verify` skills, since a modal + charts is genuinely easier to confirm by
  looking at it): clicking a name opens the card with correct data; closing via
  X, outside-click, and Escape all work; a player with no advanced-stats rows
  shows the fallback message, one seeded via the mock script shows tiles +
  charts; goalie vs skater stat-tile sets render correctly; broken/missing
  headshot degrades to the placeholder without breaking layout.
