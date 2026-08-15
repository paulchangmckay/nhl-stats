# Team Pages + Top Players Page — Design

**Issues:** #116 (branded team pages with top-player summaries and stats), #117 (Top Players page for the latest season)
**Base branch:** `feature/119-120-header-nav-hero-image` (Group 1 — provides the `Header`/routing infrastructure and the `/teams`, `/top-players` placeholder routes this group replaces)
**Date:** 2026-08-14

## Problem

Group 1 added placeholder routes at `/teams` and `/top-players` with no real content. #116 wants a branded page per NHL team summarizing that team's top players; #117 wants a league-wide page showing the league's top players for the latest season. Both need a definition of "top" that didn't exist before this design.

## Decisions

1. **`/teams` is a picker, not a single page.** It shows all 32 teams as branded cards (logo + colors from `teamBranding.ts`) in a grid; clicking one navigates to a new dynamic route `/teams/:teamId` for that team's actual content.

2. **Ranking model is a three-way composite score (v1), not simple points-sorting.** A detailed analytics formula was proposed (individual/on-ice expected-goals metrics, GSAx, HDSV%, oZS%) but roughly half its inputs don't exist in this database — they depend on a per-shot expected-goals model that isn't built. That work is tracked separately: [#124](https://github.com/paulchangmckay/nhl-stats/issues/124) (expected-goals shot-quality model) and [#125](https://github.com/paulchangmckay/nhl-stats/issues/125) (GSAx/HDSV% for goalies). This design implements a v1 using only what's available today, keeping the same relative weighting among the surviving terms:
   - **Offense** ≈ 0.62·z(primary_points/60) + 0.38·z(iCF/60)
   - **Defense** ≈ 0.64·z(−CA/60) + 0.36·z(−HDCA/60)
   - **Goalie** ≈ 0.67·z(SV%) + 0.33·z(−GAA)

3. **Scoring reuses and extends the existing ETL-precomputed z-score system — it is not computed fresh per page.** `etl/compute_advanced_stats.py`'s `compute_zscores()` already computes `primary_points_per60_z` and `shots_per60_z` (the field name is historical; it's actually iCF/60 — see `rate_fields = {"shots_per60_z": "icf", ...}`) for every skater, per season, **segmented by position group (F/D)**, with existing guards (`PERCENTILE_MIN_GP = 10`, `ZSCORE_MIN_POPULATION = 20`) already matching this design's intended sample-size floor. This is populated data (2088 rows for the current season `20252026` in `player_advanced_percentiles`, 774 in `player_rate_zscores`, confirmed live), and it's already the source powering the percentile bars in the existing `PlayerProfilePanel` overlay via `/api/players/<id>/advanced`.

   Building a second, independent client-side population-statistics system (the originally-drafted approach) would create two different "how good is this player" numbers in the same app that don't necessarily agree. Instead:
   - **Offense** needs no new ETL work — `primary_points_per60_z` and `shots_per60_z` already exist for the current season.
   - **Defense** needs two new fields added to `compute_zscores()`'s `rate_fields` dict (`ca_per60_z`, `hdca_per60_z`, sourced from `player_season_advanced_stats.ca`/`.hdca` — already-collected on-ice columns not yet exposed as rates). Same position-group split, same guards, same table (`player_rate_zscores`, two new columns via `ALTER TABLE` + the corresponding `CREATE TABLE`/`upsert_player_rate_zscores` updates).
   - **Goalie** needs a new ETL function (`compute_goalie_zscores`, no position-group split — goalies are already one group) and a new table (`goalie_rate_zscores`: `season_id`, `player_id`, `sv_pct_z`, `gaa_z`), computed from `player_season_stats` (`save_pct`, `gaa`, filtered to `position_code = 'G'` and a goalie-specific min-GP floor — proposed 5, no existing precedent to match since no goalie z-scoring exists yet).

4. **Scores don't combine into one blended list.** Offense, Defense, and Goalie are three separate leaderboards, not merged — forcing them into one ranking would require inventing position-weighting rules the source data doesn't justify yet.

5. **`/top-players` uses the same three-leaderboard model, league-wide**, rather than a generic sortable table — consistent with the team page, and reuses the same scoring function and UI rather than building two different ranking paradigms.

6. **The final weighted-combination step (turning two already-computed z-scores into one Offense/Defense/Goalie composite) is a small, pure, unit-testable TypeScript function.** Unlike the original draft, this function does *not* compute population statistics itself — that's now the ETL's job (Decision 3) — it just combines already-z-scored inputs with the fixed weights above and sorts. This keeps the codebase's existing convention (pure, testable business logic per issue #97) without duplicating the population-statistics work the ETL already does correctly.

## Architecture

**ETL** (`etl/compute_advanced_stats.py`):
- Extend `compute_zscores()`: add `"ca_per60_z": "ca"` and `"hdca_per60_z": "hdca"` to the `rate_fields` dict; add `ca`, `hdca` to that function's `SELECT` from `player_season_advanced_stats`. Same position-group loop, same `_rate()`/`_zscore()` helpers, same guards — purely additive.
- New `compute_goalie_zscores(conn, season_id)`: queries `player_season_stats` for `position_code = 'G'` rows meeting a min-GP floor, computes `z(save_pct)` and `z(-gaa)` across that season's qualifying goalie population using the same `_zscore()` helper, upserts into a new `goalie_rate_zscores` table.
- Schema: `player_rate_zscores` gains two columns (`ca_per60_z`, `hdca_per60_z`) via migration; new `CREATE_GOALIE_RATE_ZSCORES` table; `upsert_player_rate_zscores` and a new `upsert_goalie_rate_zscores` updated/added in `src/database.py`.
- `_run_aggregation_and_percentiles()` calls the new `compute_goalie_zscores()` alongside the existing `compute_zscores()` call, per season.
- After this ships, `scripts/run_all_etl.py` needs to run once (or the specific ETL step) to backfill the new columns/table for existing seasons — noted as a plan task, not a design decision.

**Backend API** — new endpoint, not an extension of `api_players_stats` (that endpoint is raw box-score-style stats, a different concern):
- `GET /api/players/rankings?season=<id>[&team=<abbrev>]` — joins `players`/`teams` to `player_rate_zscores` (skaters) and `goalie_rate_zscores` (goalies), returns per player: `player_id`, `name`, `team_abbrev`, `position_group` (`F`/`D`/`G`), and whichever z-score fields apply to their group. Optional `team` filter narrows to one team's roster (team pages); omitted, returns the full league (top-players page).

**Frontend routes** (added to the nested layout under `App` in `main.tsx`, alongside Group 1's existing routes):
- `/teams` → `pages/Teams.tsx` — team picker grid.
- `/teams/:teamId` → `pages/TeamPage.tsx` — branded header + three leaderboards, replaces the `PlaceholderPage` currently at `/teams`.
- `/top-players` → `pages/TopPlayers.tsx` — three leaderboards, league-wide, replaces the current `PlaceholderPage`.

## Components

- **`lib/leaderboards.ts`** — pure function `computeLeaderboards(players: RankingRow[]): { offense: RankedPlayer[]; defense: RankedPlayer[]; goalie: RankedPlayer[] }`, where `RankingRow` is the shape returned by `/api/players/rankings`. Splits by `position_group`, combines the two relevant z-scores per composite with the fixed weights from Decision 2, sorts each list descending. No population math — inputs are already z-scored.
- **`components/Leaderboard.tsx`** — renders one ranked list (title, ranked rows with player name/team/score), row click opens `PlayerProfilePanel` (same `open`/`playerId`/`bio`/`stats` pattern already used on `/players` — this panel separately fetches its own bio/stats/advanced data by `playerId`, so the ranking rows only need to carry the ID). Reused by both `TeamPage` and `TopPlayers`.
- **`pages/Teams.tsx`** — maps all 32 team abbreviations (`teamBranding.ts`'s `TEAM_COLORS` keys) to branded `<Link>` cards.
- **`pages/TeamPage.tsx`** — reads `:teamId` via `useParams`, fetches `/api/players/rankings?season=<latest>&team=<teamId>` (same hardcoded latest-season default as `Players.tsx` today), runs `computeLeaderboards`, renders three `Leaderboard`s (top 5 each) inside team-branded styling (colors/logo from `teamBranding.ts`).
- **`pages/TopPlayers.tsx`** — fetches `/api/players/rankings?season=<latest>` (no team filter), runs `computeLeaderboards` over the full league population, renders three `Leaderboard`s (top 15 each, given the much larger population).

## Data Flow

Both pages independently fetch `/api/players/rankings` with their own query params (team-scoped or league-wide) — no shared cache across routes, matching the existing pattern where `Players.tsx` also fetches its own data on mount. All population statistics (mean/stddev per metric, per position group) are computed once by the ETL job per season, not per page load. `computeLeaderboards` only combines and sorts already-z-scored rows. No new global state.

## Testing

- **ETL**: `compute_zscores()`'s new `ca_per60_z`/`hdca_per60_z` fields get the same test treatment as the existing `chances_per60_z` (null-propagation, min-population floor, game-type filtering — see `tests/test_compute_advanced_stats.py`'s existing tests for that field as the pattern to mirror). New `compute_goalie_zscores()` gets its own test file following the same structure (population-floor guard, zero-stddev guard, correct z-score values for a known qualifying population).
- **Backend**: `/api/players/rankings` — returns correct fields for skaters vs. goalies, `team` filter narrows correctly, unfiltered returns league-wide.
- **`computeLeaderboards()`**: direct unit tests — composite-score math against known z-score inputs, correct position-group splitting (F/D/G), that offense/defense/goalie are independently ranked (not blended).
- **`Leaderboard.tsx`**: renders ranked rows in order, row click opens the profile panel with correct `playerId`.
- **`Teams.tsx`**: renders 32 team cards, each linking to the correct `/teams/:teamId`.
- **`TeamPage.tsx` / `TopPlayers.tsx`**: mocked fetch, correct team-filtered/league-wide requests, three leaderboards render.

## Out of Scope

- The full expected-goals model (ixG, xGA/60, RelxGA, GSAx, HDSV%, oZS%) — tracked in #124 and #125.
- Position-weighted blending of offense/defense into one combined skater score.
- Any UI for adjusting the GP threshold or formula weights — v1 values are fixed constants, not user-configurable.
- Historical backfill beyond re-running the existing ETL pipeline for already-ingested seasons (no new historical data ingestion).
