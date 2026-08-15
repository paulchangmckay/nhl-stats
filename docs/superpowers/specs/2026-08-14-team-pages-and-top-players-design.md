# Team Pages + Top Players Page — Design

**Issues:** #116 (branded team pages with top-player summaries and stats), #117 (Top Players page for the latest season)
**Base branch:** `feature/119-120-header-nav-hero-image` (Group 1 — provides the `Header`/routing infrastructure and the `/teams`, `/top-players` placeholder routes this group replaces)
**Date:** 2026-08-14

## Problem

Group 1 added placeholder routes at `/teams` and `/top-players` with no real content. #116 wants a branded page per NHL team summarizing that team's top players; #117 wants a league-wide page showing the league's top players for the latest season. Both need a definition of "top" that didn't exist before this design.

## Decisions

1. **`/teams` is a picker, not a single page.** It shows all 32 teams as branded cards (logo + colors from `teamBranding.ts`) in a grid; clicking one navigates to a new dynamic route `/teams/:teamId` for that team's actual content.
2. **Ranking model is a three-way composite score (v1), not simple points-sorting.** A detailed analytics formula was proposed (individual/on-ice expected-goals metrics, GSAx, HDSV%, oZS%) but roughly half its inputs don't exist in this database — they depend on a per-shot expected-goals model that isn't built. That work is tracked separately: [#124](https://github.com/paulchangmckay/nhl-stats/issues/124) (expected-goals shot-quality model) and [#125](https://github.com/paulchangmckay/nhl-stats/issues/125) (GSAx/HDSV% for goalies). This design implements a v1 using only what's available today, keeping the same relative weighting among the surviving terms:
   - **Offense** ≈ 0.62·z(primary_points) + 0.38·z(iCF)
   - **Defense** ≈ 0.64·z(−CA/60) + 0.36·z(−HDCA/60)
   - **Goalie** ≈ 0.67·z(SV%) + 0.33·z(−GAA)

   where z(x) = (x − population_mean) / population_stddev, population = whichever player set is being ranked (a team's roster, or the league).
3. **Scores don't combine into one blended list.** Offense, Defense, and Goalie are three separate leaderboards, not merged — forcing them into one ranking would require inventing position-weighting rules the source data doesn't justify yet.
4. **`/top-players` uses the same three-leaderboard model, league-wide**, rather than a generic sortable table — consistent with the team page, and reuses the same scoring function and UI rather than building two different ranking paradigms.
5. **Minimum sample-size guard.** Players below a games-played threshold are excluded from ranking (proposed: 10 GP for skaters, 5 GP for goalies) — z-scores are noisy on tiny samples, and an early-season call-up with 2 games and a lucky shot shouldn't top a leaderboard.
6. **Scoring computation lives client-side**, as a pure, unit-testable TypeScript function — not in the backend. Z-scores need the full population (mean/stddev) in memory regardless of where they're computed, and this matches the codebase's existing convention of extracting logic like this into pure functions (the precedent from issue #97) rather than adding scoring logic to the Flask layer.
7. **Small backend addition required.** The season-specific branch of `/api/players/stats` (`app.py:160-199`) already `JOIN`s `player_season_advanced_stats` (aliased `adv`) to compute `cf_pct_5v5`/`shots_per60_5v5` — it just doesn't `SELECT` the fields this design needs yet. Adding `SUM(adv.primary_points)`, `SUM(adv.icf)`, and CA/60 and HDCA/60 (same per-hour-of-TOI division pattern as the existing `shots_per60_5v5`) is a small extension of an already-existing query — no new route, no schema change.

## Architecture

Routes (added to the nested layout under `App` in `main.tsx`, alongside Group 1's existing routes):
- `/teams` → `pages/Teams.tsx` — team picker grid.
- `/teams/:teamId` → `pages/TeamPage.tsx` — branded header + three leaderboards, replaces the `PlaceholderPage` currently at `/teams`.
- `/top-players` → `pages/TopPlayers.tsx` — three leaderboards, league-wide, replaces the current `PlaceholderPage`.

Backend:
- `app.py`'s `api_players_stats` season-specific query gains four new `SELECT` expressions (`primary_points`, `icf`, `ca_per60`, `hdca_per60`), computed the same way `shots_per60_5v5` already is (`SUM(...) / NULLIF(SUM(adv.toi_seconds)/3600.0, 0)`). The `"all"` seasons branch is unaffected (no `adv` join there; team/top-players pages will call with a specific season, same as the existing Players page does today).

## Components

- **`lib/leaderboards.ts`** — pure function `computeLeaderboards(players: PlayerStats[], minGpSkater = 10, minGpGoalie = 5): { offense: RankedPlayer[]; defense: RankedPlayer[]; goalie: RankedPlayer[] }`. Filters by the GP threshold, computes population mean/stddev per metric, applies the three weighted-z-score formulas above, sorts descending. `RankedPlayer` = `PlayerStats & { score: number }`.
- **`components/Leaderboard.tsx`** — renders one ranked list (title, ranked rows with player name/team/score/key stat), row click opens `PlayerProfilePanel` (same `open`/`playerId`/`bio`/`stats` pattern already used on `/players`). Reused by both `TeamPage` and `TopPlayers`.
- **`pages/Teams.tsx`** — maps all 32 team abbreviations (`teamBranding.ts`'s `TEAM_COLORS` keys) to branded `<Link>` cards.
- **`pages/TeamPage.tsx`** — reads `:teamId` via `useParams`, fetches `/api/players/stats?seasons=<latest>` (same hardcoded latest-season default as `Players.tsx` today), filters to that team's roster client-side, runs `computeLeaderboards`, renders three `Leaderboard`s (top 5 each) inside team-branded styling (colors/logo from `teamBranding.ts`).
- **`pages/TopPlayers.tsx`** — fetches the same endpoint unfiltered, runs `computeLeaderboards` over the full league population, renders three `Leaderboard`s (top 15 each, given the much larger population).

## Data Flow

Both pages independently fetch `/api/players/stats?seasons=<latest>` (no shared cache across routes — matches the existing pattern where `Players.tsx` also fetches its own data on mount). `computeLeaderboards` runs client-side against whatever population is passed in (team roster or full league). No new global state.

## Testing

- `computeLeaderboards()`: direct unit tests — z-score math against known inputs, GP-threshold exclusion, tie-handling, and that offense/defense/goalie are independently ranked (not blended).
- `Leaderboard.tsx`: renders ranked rows in order, row click opens the profile panel with correct `playerId`.
- `Teams.tsx`: renders 32 team cards, each linking to the correct `/teams/:teamId`.
- `TeamPage.tsx` / `TopPlayers.tsx`: mocked fetch, correct roster/league filtering, three leaderboards render.
- Backend: `api_players_stats`'s season-specific branch returns the four new fields with correct values (extend existing test coverage for this route, same style as `cf_pct_5v5`'s existing tests).

## Out of Scope

- The full expected-goals model (ixG, xGA/60, RelxGA, GSAx, HDSV%, oZS%) — tracked in #124 and #125.
- Position-weighted blending of offense/defense into one combined skater score.
- Server-side computation of z-scores/rankings (kept client-side per Decision 6).
- Any UI for adjusting the GP threshold or formula weights — v1 values are fixed constants, not user-configurable.
