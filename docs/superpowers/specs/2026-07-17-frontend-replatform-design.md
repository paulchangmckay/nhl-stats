# Frontend Replatform (React + Tailwind + shadcn/ui) — Design

## Context

The player table (`templates/index.html` + `static/js/search.js`, ~470 lines of
inline JS/CSS in a Jinja template) is hand-rolled vanilla HTML/CSS/JS, a
deliberate 2026-07-02 decision to avoid a build toolchain at a time when the
UI was a single filtered/sortable table. Since then the UI has grown
(autocomplete search, team/season popups, position toggles, stat threshold
filters — see `docs/superpowers/specs/2026-07-02-advanced-filters-design.md`)
and a further feature (a Player Bio card,
`docs/superpowers/specs/2026-07-17-player-bio-card-design.md`) was about to
add React scoped to just one modal, using Recharts + shadcn/ui.

Mid-review of that Bio card spec, scope expanded: rather than one isolated
React island in an otherwise-vanilla page, the whole frontend should move onto
React + Tailwind + shadcn/ui — both to support the Bio card cleanly and as a
deliberate visual/technical upgrade in its own right. This spec supersedes the
2026-07-02 vanilla-JS decision and covers *only* that replatform. The Player
Bio card gets its own spec afterward, built on top of this new foundation.

**This is a pure re-platform, not a feature change.** Every filter, sort, and
interaction that works today must work identically after — the goal is a new
engine under an upgraded (but functionally equivalent) UI, not new
functionality. New functionality (the Bio card) is explicitly the next
project, not this one.

## Scope

In scope:
1. Rebuild the entire player table page — search + autocomplete, team popup
   (logo + name), season multi-select popup, position toggle group, GP/G/A/
   Pts≥ stat filters, sortable sticky table, loading/empty states, player
   count label — as a React + TypeScript SPA using Tailwind v4 + shadcn/ui
   components, mounted into a minimal Flask-served HTML shell.
2. New `frontend/` build (Vite), git-ignored build output in `static/dist/`.
3. Retire `templates/index.html`'s current markup/inline script,
   `static/js/search.js`, and `tests/js/search.test.js` once the React app
   has full feature parity — no dual-maintenance period.
4. Vitest + React Testing Library test suite, wired into
   `.github/workflows/ci.yml` from the start. This supersedes and closes
   issue #23 ("Wire JS test suite into CI") — the suite it refers to
   (`tests/js/search.test.js`, never wired in) is retired along with
   `search.js`, replaced by a suite that *is* wired in from day one.
5. A deliberate visual refresh: adopt shadcn's default component look
   (spacing, typography, `Card`/`Table`/`Command`/`Popover` styling) as the
   new design language, keeping the dark theme and the existing
   position-color-coding (C/L/R/D/G accent colors) as the palette carried
   forward, rather than pixel-matching every current CSS rule.
6. Fetch-failure handling for all three API calls (`/api/teams`,
   `/api/players`, `/api/players/stats`) — today's app leaves the page stuck
   on "Loading…" forever on a network error. Fixed as part of this replatform
   (see Frontend Design → Error handling) since the fetch logic is being
   rebuilt regardless — not new functionality, a latent bug fixed in code
   already being touched.

Out of scope (explicitly not part of this project):
- Any change to `app.py` or the three JSON API routes (`/api/teams`,
  `/api/players`, `/api/players/stats`) — this is frontend-only. Their
  response shapes are the React app's contract, unchanged.
- The Player Bio card feature itself (separate spec, next project, builds on
  this foundation).
- Server-side pagination, React Query, or any change to the "fetch once,
  filter client-side" data pattern established 2026-07-02 — still appropriate
  at ~705 rows; introducing a data-fetching library here would be
  over-engineering for this dataset size.
- E2E/browser automation testing (e.g. Playwright) — not currently used
  anywhere in this project; manual verification via `run`/`verify` skills
  continues to be how the app gets checked end-to-end. Could be a future
  addition but isn't pulled in just because this touches the frontend.
- Any new npm dependency beyond what's needed for this migration (no icon
  library beyond what shadcn pulls in via `lucide-react`, no state-management
  library, no CSS-in-JS).

## Architecture

- **Backend**: unchanged. `app.py`'s `index()` route still renders
  `templates/index.html`, now a minimal shell:
  ```html
  <div id="root"></div>
  <script type="module" src="{{ url_for('static', filename='dist/app.js') }}"></script>
  <link rel="stylesheet" href="{{ url_for('static', filename='dist/app.css') }}">
  ```
  Fixed (unhashed) output filenames, same rationale as the superseded Bio
  card spec: no content-hash cache-busting needed at this project's scale, and
  it keeps the Jinja shell static instead of needing to read a Vite manifest.
- **Frontend**: `frontend/` at repo root.
  ```
  frontend/
    package.json         # react, react-dom, typescript, vite, @vitejs/plugin-react,
                          # @tailwindcss/vite, tailwindcss, shadcn deps (class-variance-authority,
                          # clsx, tailwind-merge, lucide-react, radix-ui primitives per component)
    vite.config.ts        # plugins: [react(), tailwindcss()]; build.outDir -> ../static/dist;
                          # dev server proxy: '/api' -> 'http://127.0.0.1:5099'
    components.json       # shadcn CLI config
    tsconfig.json
    src/
      main.tsx             # mounts <App /> into #root
      App.tsx              # top-level layout: Toolbar + PlayerTable
      lib/
        search.ts          # ported tokenize/playerSearchText/matchesQuery
        types.ts            # Player, PlayerStats, Team API response shapes
      components/
        ui/                # shadcn-generated primitives (button, input, table,
                            # popover, command, toggle-group, badge, skeleton, ...)
        Toolbar.tsx
        TeamPicker.tsx
        SeasonPicker.tsx
        PositionToggle.tsx
        StatFilters.tsx
        PlayerTable.tsx
  ```
- **Dev workflow**: two processes during development — `python app.py`
  (API, :5099) and `npm run dev` in `frontend/` (Vite dev server, proxies
  `/api/*` to Flask). Production: `npm run build` once, then `python app.py`
  alone serves everything (same-origin, no proxy needed).
- **`scripts/dev.sh`**: new convenience script (matches the project's existing
  `scripts/*.sh` pattern, e.g. `scripts/audit.sh`, `scripts/launch_app.sh`)
  that starts `python app.py` in the background, then runs `npm run dev`
  (in `frontend/`) in the foreground, trapping exit to kill the backgrounded
  Flask process on Ctrl+C. Documented in `README.md` as the one-command way
  to run the app locally during development.
- **Dark mode**: the app is always dark (no light/dark toggle exists or is
  planned). shadcn's standard `init` still sets up its normal dual-palette
  CSS-variable system (light + dark, toggled via a `.dark` class) — kept
  as-is rather than hand-rolling a dark-only variant, so every future
  `npx shadcn add <component>` drop-in stays compatible with zero edits.
  The `.dark` class is simply hard-coded onto `<html>` in the shell
  (`frontend/index.html` / `main.tsx`) and never toggled — light mode is
  wired up but never activated.
- **Node / package manager**: npm (matches the spec's existing `npm ci`/
  `npm run build` references), Node 22 LTS pinned explicitly via
  `actions/setup-node` in CI — same "pin the CI runtime explicitly" pattern
  already used for Python (`python-version: "3.12"`). `frontend/package-lock.json`
  is committed for reproducible installs. An `engines` field in
  `package.json` (or a `.nvmrc`) documents the expected local Node version.

## Frontend Design

### Data & state

- `App.tsx` fetches `/api/teams` and `/api/players` once on mount (`useEffect`
  + `fetch`, no library) into component state. Season-scoped stats
  (`/api/players/stats?seasons=...`) are fetched on demand and cached in a
  `Record<seasonsKey, PlayerStats[]>` map in state — direct port of the
  existing `statsData` object cache keyed by joined-sorted-season-list, same
  as today.
- Filter state (search text, active team, active seasons, active positions,
  stat minimums, sort key/direction) lives in `App.tsx` and is threaded down
  as props — no context/Redux/Zustand needed at this component count.
- `lib/search.ts` ports `tokenize`/`playerSearchText`/`matchesQuery`
  verbatim (same logic, TypeScript types added) — this is the exact
  regression-tested behavior from `tests/js/search.test.js`'s 10 cases (name
  order, team abbrev/name/place matching, empty-query, non-match), which
  become the first Vitest suite ported over unchanged in intent.
- **No runtime response validation** (no Zod/io-ts) — plain TypeScript
  interfaces in `lib/types.ts` are the only contract check, enforced at
  compile time only. This is a single-repo, single-maintainer project where
  frontend and backend change together in the same PR, so the drift risk
  Zod protects against barely exists here, and the failure mode if it did
  drift (a blank cell, not a crash) is low-severity and easy to spot in a
  tool with one user.

### Error handling

Each of the three fetches (`/api/teams`, `/api/players`,
`/api/players/stats`) wraps in a `try/catch`. On failure, the affected
section renders a shadcn `Alert` (destructive variant) with the error and a
"Retry" button that re-runs the failed fetch — replacing today's behavior of
an indefinite, unexplained "Loading…" state. This is a fix to latent
behavior in code being rewritten regardless, not new functionality.

### Component-by-component mapping (today → replatformed)

| Today | Replatformed |
|---|---|
| `#search-input` + `.suggestion-list` | shadcn `Command` inside a `Popover`, filtered live via `matchesQuery` |
| `.popup-select` (Team) | shadcn `Popover` + `Command` list, each row a team logo `<img>` + name |
| `.popup-select` (Season) | shadcn `Popover` with a checkbox list; "All Seasons (Career)" mutually exclusive with specific seasons, same rule as today |
| `.pos-toggle-group` | shadcn `ToggleGroup` (`type="multiple"`), one `ToggleGroupItem` per position, existing C/L/R/D/G color coding preserved as custom Tailwind classes |
| `.stat-input` × 4 | shadcn `Input type="number"`, always visible (no more tab-conditional hiding, since the Bio/Stats toggle was already being removed per the prior spec's scope) |
| `<table>` / sortable `<th>` | shadcn `Table` primitives; header `onClick` toggles sort key/direction identically to today's logic |
| `.team-badge` / `.pos-badge` | shadcn `Badge`, `variant` per position color |
| `#loading-msg` | shadcn `Skeleton` rows |
| `#empty-msg` | plain centered text, unchanged in spirit |
| Sticky header + bounded scroll container (`bug-008` fix, 2026-07-14) | same technique (bounded-height `overflow:auto` wrapper, `sticky top-0` thead), ported deliberately — this was a hard-won fix and must not regress |

Note: the Bio/Stats toggle removal (originally scoped in the Bio card spec)
happens naturally here too, since this project rebuilds the table from
scratch — the replatformed table only ever shows stats columns. Bio-specific
fields (height, weight, birth date/country, draft info) aren't shown in the
table in either version; they were always Bio-tab-only and remain deferred to
the Bio card feature, not added to the table.

## Build Pipeline / CI

- `.github/workflows/ci.yml` gains a `frontend` job: `actions/setup-node`,
  `npm ci`, `npm test` (Vitest), `npm run build` (Vite) — run alongside the
  existing Python job, both required to pass before merge (matches the
  existing convention of adding a new test runner and its CI wiring in the
  same change, per the 2026-07-14 cerebrum entry that flagged this being
  missed once already for `search.js`).
- `static/dist/` added to `.gitignore` (alongside `.venv/`, `node_modules/`).
- `README.md` setup section gains: `cd frontend && npm install && npm run
  build` as a required step before `python app.py`, mirroring the existing
  Python venv setup step.

## Rollout Plan

Four sequential PRs (each its own branch/worktree, each independently green
in CI, `main` deployable after every one — not just the last):

1. **Scaffold**: `frontend/` init (Vite + React + TS + Tailwind v4 + shadcn
   `init`), empty `App.tsx` rendering a placeholder, `frontend` CI job added
   and green, `scripts/dev.sh` added. Proves the build pipeline works before
   any real component exists. Old vanilla app untouched and still live.
2. **Toolbar components**: search/autocomplete, team picker, season picker,
   position toggle, stat filters — built against static/mock data (not yet
   wired to the real API). Old vanilla app still untouched and still what
   Flask actually serves.
3. **PlayerTable + real data**: wired to the actual `/api/teams`,
   `/api/players`, `/api/players/stats` endpoints, sorting, error handling
   (Alert + retry) implemented. The React app is now fully feature-complete,
   but Flask still serves the old vanilla `index.html` — the new app is
   reachable only via `npm run dev` for review/testing, not yet live.
4. **Cutover**: delete `templates/index.html`'s old markup/inline script,
   `static/js/search.js`, `tests/js/search.test.js`; replace with the minimal
   Flask shell serving the built React app. Single commit/PR so there's no
   window where both versions are half-live.

## Testing Plan

- **Fetch mocking**: plain `vi.fn()`/`vi.stubGlobal('fetch', ...)` per test,
  returning canned fixture JSON — no MSW. The three endpoints have no
  request-matching complexity (no query-string routing logic to fake), so
  MSW's network-layer interception is more infrastructure than this suite
  needs.
- **Vitest unit tests**: `lib/search.ts` — direct port of all 10 existing
  `search.test.js` cases.
- **Vitest + React Testing Library component tests**:
  - `PlayerTable` sorts correctly on header click, toggles asc/desc on
    repeat click, renders goalie-specific columns only for `position_code
    === "G"` rows.
  - Each of the three fetches renders the Alert+Retry error state on a
    stubbed rejection, and recovers (re-fetches and renders data) when Retry
    is clicked and the stub then resolves.
  - `Toolbar` filters (search, team, season, position, stat minimums) each
    narrow the rendered row set correctly in isolation and in combination
    (mirrors the 2026-07-02 spec's manual test plan items 1-2, now
    automated).
  - Season multi-select: checking "All Seasons (Career)" clears specific
    checkboxes and vice versa.
  - Clicking a search suggestion clears the search box and scrolls to /
    highlights the matched row (jsdom `scrollIntoView` mock).
  - Sticky-header height offset recalculates on toolbar row-wrapping
    (regression test for `bug-008`).
- **Manual verification** (`npm run dev` + `python app.py`, per `run`/
  `verify` skills): full pass through every filter combination, visual check
  against the shadcn-based redesign, confirm no layout regressions on narrow
  viewports (the `bug-008` sticky-header fix was specifically about avoiding
  whole-page horizontal scroll on narrow screens).
- Existing Python `tests/` suite requires no changes and must still pass
  unmodified — confirms the backend contract truly didn't change.
