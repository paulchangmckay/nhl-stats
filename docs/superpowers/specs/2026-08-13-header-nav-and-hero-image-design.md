# Header Navigation + Homepage Hero — Design

**Issues:** #119 (header navigation between pages), #120 (hero image on homepage, depends on #119)
**Date:** 2026-08-13

## Problem

The app currently has no router and no homepage — `frontend/src/App.tsx` renders a single view (toolbar + player stats table) with no navigation. Two upcoming issue groups (#116/#117: team pages + top players; later, betting/odds pages) need real routes to land in, and #119/#120 ask for a persistent header nav and a homepage hero section to sit above them.

## Decisions

1. **Routing:** introduce `react-router-dom` now, rather than building a decorative nav with dead links. This group's placeholder routes give the very next group (#116/#117) somewhere to land without a second routing migration.
2. **Homepage becomes a dedicated landing page.** The current toolbar/table view moves off `/` and onto its own route (`/players`); `/` becomes a hero-only landing page. This is a bigger change than "just add a hero," but keeps Home focused on orientation/branding rather than mixing it with the data-dense table view.
3. **Nav scope:** Home, Players, Teams, Top Players, Betting. News (#118) is deliberately excluded from the nav — it will live as an inline section on the Home page in a future group, not as its own route.
4. **Hero image:** a CSS gradient built from the existing `TEAM_COLORS` palette (`frontend/src/lib/teamBranding.ts`), not a photo/illustration. No image-asset pipeline (`public/`, `src/assets/`) exists in the repo today, and sourcing/licensing real hockey imagery is out of scope for this group.
5. **Header is sticky.** It stays visible on scroll (standard nav UX). This requires updating `Players.tsx`'s table-height calc (see Architecture) so the table doesn't overflow past the viewport by the header's height.
6. **Backend SPA fallback is in scope.** `app.py` currently only serves `index.html` at `/` (no catch-all), so a hard refresh or direct URL hit on `/players`, `/teams`, `/top-players`, or `/betting` would 404 from Flask, not just render blank. A catch-all route is added as part of this group — without it the nav feature is broken for a common case (refresh, bookmark, shared link).
7. **Unknown client-side routes** (e.g. a typo'd path) redirect to Home (`<Route path="*" element={<Navigate to="/" />} />`) rather than showing a dedicated 404 page — simplest safe default, revisit if a real need for a distinct not-found page emerges.

## Architecture

- Add `react-router-dom`. Routes:
  - `/` → `pages/Home.tsx` (hero)
  - `/players` → `pages/Players.tsx` (existing toolbar + table, moved as-is from `App.tsx`)
  - `/teams` → `pages/PlaceholderPage.tsx` (title="Teams") — real content lands in a future group covering #116
  - `/top-players` → `pages/PlaceholderPage.tsx` (title="Top Players") — real content lands in a future group covering #117
  - `/betting` → `pages/PlaceholderPage.tsx` (title="Betting") — no group scheduled yet
- `App.tsx` becomes a thin layout shell: `<Header />` + `<Outlet />` (router-rendered page content). The existing toolbar/table JSX is relocated into `pages/Players.tsx` unchanged.

## Components

- **`components/Header.tsx`** — nav links (Home, Players, Teams, Top Players, Betting) using React Router's `NavLink` for active-route styling. Mobile: hamburger toggle opens a shadcn `Sheet` containing the same links. Sticky (`position: sticky; top: 0`), and reserves layout space the same way `Toolbar.tsx` already does today — a `data-header` attribute measured in an effect, written to a `--header-height` CSS var.
- **`Players.tsx`'s table-height calc updated:** `height: max(200px, calc(100vh - var(--toolbar-height, 57px) - var(--header-height, 0px)))` — previously only accounted for the Toolbar; now also subtracts the sticky Header's height so the table stays within the visible viewport instead of overflowing by the header's height.
- **Backend fallback:** `app.py` gets a catch-all route (excluding `/api/*` and `/static/*`) that also calls `render_template("index.html")`, so any client-side route resolves correctly on a direct hit or hard refresh.
- **`pages/Home.tsx`** — hero section: gradient background composed from `TEAM_COLORS` values, headline + subtext. Includes a code comment marking where an inline news feed (#118) will be added later — no functional news code in this group.
- **`pages/Players.tsx`** — the current `App.tsx` body (toolbar + `PlayerTable`, loading/error states, `profilePlayerId` overlay logic), relocated with no behavior changes.
- **`pages/PlaceholderPage.tsx`** — reusable "coming soon" component taking a `title` prop, used for `/teams`, `/top-players`, `/betting` until each is replaced by real content in its own group.

## Data Flow / State

No new global state. Active nav highlighting comes from the router's current location (`NavLink`'s built-in `isActive`). The hero gradient is a static computed value at render — not tied to a selected team, since Home is app-wide branding rather than a team-specific view.

## Testing

- Router smoke tests: each route renders without error; `NavLink` active-state class toggles when location changes; unknown path redirects to `/`.
- **`App.test.tsx` (8 existing tests, incl. the bug-008 table-height regression guard) moves to `Players.test.tsx`.** `render(<App />)` becomes `render(<Players />)` wrapped in `<MemoryRouter initialEntries={["/players"]}>`. Test bodies/assertions are unchanged — only the host component, file name, and router wrapper change. The bug-008 test's height-style assertion is updated to match the new two-variable calc.
- A new, small `App.test.tsx` covers the shell itself: `Header` renders, `Outlet` renders the active route's content.
- `Header`: mobile menu open/close behavior (`Sheet` toggling) gets a component test.
- `PlaceholderPage`: trivial render test (title prop displays).
- Backend: a test hitting `/players` (or another non-root path) directly confirms `index.html` is returned, not a 404.

## Out of Scope

- Real content for `/teams`, `/top-players`, `/betting` (future groups).
- News feed implementation (#118) — only a placement comment in `Home.tsx`.
- Any licensed/photographic hero imagery — gradient only, revisit if a future request specifically asks for a photo hero.
