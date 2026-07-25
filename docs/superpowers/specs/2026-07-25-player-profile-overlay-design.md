# Player Profile Overlay — Design

## Context

`docs/superpowers/specs/2026-07-17-player-bio-card-design.md` planned a full
player bio card (photo, bio detail row, stat totals, advanced-stats
percentiles + trend), but was explicitly superseded mid-review: scope had
expanded to a full frontend replatform onto React + Tailwind + shadcn/ui, and
that spec was deferred to be "redone to build natively on the new stack."

The replatform happened (`2026-07-17-frontend-replatform-design.md`), and
`2026-07-22-advanced-analytics-design.md` (PR #70) landed a
`PlayerAdvancedPanel` dialog — but that dialog only covers the
advanced-stats half of the original bio-card plan (percentile boxes +
trend chart, opened by clicking a player's CF% cell). Photo, bio detail row,
and basic stat totals were never added. This spec completes that deferred
work: extending `PlayerAdvancedPanel` into a full player profile overlay.

**Prerequisite fix (this session, already done):** the advanced-stats
aggregation ETL (`etl/compute_advanced_stats.py`) had been merged in PR #70
but never actually run against `data/nhl_stats.db` — `player_season_advanced_stats`
and `player_advanced_percentiles` were both empty, so `PlayerAdvancedPanel`
rendered with no data. Ran the ETL (62,143 season-aggregate rows, 12,826
percentile rows populated); logged as `bug-016` in `.wolf/buglog.json`. The
frontend build was also stale (missing `recharts` dependency, build never
re-run since PR #70 merged) — rebuilt and verified in-browser via Playwright
before starting this design.

**Decision reversal:** the superseded 2026-07-17 spec explicitly called
team-color accents out of scope ("card uses the existing site accent blue
`#58a6ff` instead of a per-team color"). This spec reverses that — the user
wants team-branded colors and logos in the profile overlay.

## Scope

In scope:
1. Rename `PlayerAdvancedPanel` → `PlayerProfilePanel` (component file +
   colocated test file), reflecting its expanded purpose.
2. Trigger: clicking anywhere in a player's table row opens the dialog
   (replaces today's CF%-cell-only click target).
3. Header: headshot photo (silhouette fallback if missing/broken), team
   logo, name, sweater number, position, team — on a background accented
   with that team's primary/secondary color.
4. Bio detail row: age (computed client-side from `birth_date`), height,
   weight, shoots/catches, birthplace (city, state/province, country),
   draft info ("Rd 2, Pick 45 (2019, TOR)" or "Undrafted").
5. Box score: GP/G/A/P/+/-/PIM for skaters; GP/W/L/OTL/SV%/GAA/SO for
   goalies (branched on `position_code === "G"`).
6. Existing advanced-stats section (percentile boxes + trend chart)
   unchanged, skaters only — hidden entirely for goalies.
7. Backend: add `headshot_url`, `birth_city`, `birth_state_province`,
   `draft_year`, `draft_round`, `draft_pick`, `draft_overall`,
   `draft_team_abbrev` to `_fetch_players()`'s SELECT in `app.py` and the
   `Player` TS type (all already exist as columns on `players`, just not
   currently selected/exposed).
8. New `frontend/src/lib/teamBranding.ts`: static 32-team
   `{primary, secondary}` hex color map (researched per-team official/
   widely-recognized brand colors, hardcoded — verified one-time, no
   runtime dependency), plus a `logoUrl(abbrev)` helper pointing at the
   NHL's public logo CDN, `_dark` variant
   (`https://assets.nhle.com/logos/nhl/svg/{ABBREV}_dark.svg` — confirmed
   resolving via curl; chosen over `_light` because it's designed for dark
   backgrounds, matching the app's dark theme).
9. `PlayerTable.tsx`: whole `TableRow` becomes the click/keyboard target
   (`tabIndex={0}`, `role="button"`, `onClick`, `onKeyDown` for Enter/Space,
   `cursor-pointer` + hover background). The `cf_pct_5v5` cell's own
   `onClick`/`role="button"`/underline styling is removed — it becomes a
   plain data cell, since a per-cell handler nested inside a now-clickable
   row would be both redundant and a nested-interactive-element a11y
   anti-pattern.

Out of scope (unchanged from the original bio-card spec's exclusions):
- Cap hit / contract length (no data source ingested).
- "4th Liner"-style role/usage labels.
- Fixing the pre-existing font-loading 404 found during verification
  (`bug-017` in buglog — cosmetic, `vite.config.ts` base-path mismatch).

## Data Flow

No new backend endpoint. `App.tsx` already fetches both `/api/players`
(bio, into `playersState`) and `/api/players/stats` (season totals, into
`statsCache` → `rows`) independently, but today only the `PlayerStats` row
is looked up when opening the dialog (`rows.find(...)`) — bio fields aren't
joined in anywhere.

Change: on row click, look up **both** the matching `PlayerStats` row (from
`rows`) and the matching `Player` bio row (from `playersState.data`) by
`player_id`, and pass both into `PlayerProfilePanel`. The existing
`/api/players/<id>/advanced` fetch (for the percentile/trend section) is
unchanged, still triggered independently on dialog open.

Team color/logo are derived client-side from `team_abbrev` (present on both
row types) via `teamBranding.ts` — no DB or backend involvement.

## Component Design

**Header** — photo/logo/name/number/position/team on the dialog's existing
dark background, with a solid-color accent bar (using the team's primary
color, ~4-6px) along the header's top or left edge — not a full-bleed
color fill, since the app is dark-themed throughout and a full-bleed fill
in an arbitrary team color risks poor contrast for some of the 32 teams.
Photo falls back to a generic silhouette icon (same slot, no layout shift)
when `headshot_url` is null or the image fails to load (`<img onError>`).

**Bio row** — age/height/weight/shoots-catches/birthplace/draft info, all
sourced from the joined `Player` bio row. Draft info renders "Undrafted"
when `draft_year` is null (roughly 21% of players, confirmed via data
check).

**Box score** — skater fields (GP/G/A/P/+/-/PIM) or goalie fields
(GP/W/L/OTL/SV%/GAA/SO), branched on `position_code`. Reflects whatever
season(s) are currently selected in the app's global season picker (same
`seasonsKey`/`statsCache` scope already driving the table) — no separate
season control inside the dialog for this section.

**Advanced-stats section** — unchanged from today's `PlayerAdvancedPanel`
(strength-state toggle, percentile boxes, trend line chart), just
repositioned below the new header/bio/box-score content. Not rendered for
goalies.

**Loading state** — header/bio/box-score render immediately on dialog open
(sourced from already-fetched `rows`/`playersState` data, no fetch delay).
Only the advanced-stats section shows its own "Loading..."/error state
independently while `/api/players/<id>/advanced` resolves, instead of today's
behavior of gating the entire dialog body on that fetch.

## Edge Cases

- Missing/broken `headshot_url` → silhouette fallback, no layout shift.
  Coverage check: 1,776/1,833 players (97%) have a `headshot_url` today.
- Missing/blank `team_abbrev`, or the literal `"UNK"` placeholder value
  (the `teams` table has 33 rows: the 32 real franchises plus `UNK` for
  players with no current team — free agents, some retired players) →
  `teamBranding.ts` lookup returns `undefined` for both; no color accent
  and no logo, default panel styling, no lookup crash.
- Goalies (246 in the dataset) → goalie box score, advanced section hidden.
- `draft_year` null (undrafted, ~21% of players) → "Undrafted" label
  instead of blank/broken draft string.
- Player with a `PlayerStats` row but no matching bio row (or vice versa,
  from data gaps) → render what's available, never crash on a missing
  lookup.

## Testing Plan

- Extend `PlayerAdvancedPanel.test.tsx` → `PlayerProfilePanel.test.tsx`:
  row-click opens the dialog; photo renders vs. silhouette fallback; team
  accent color applied from `teamBranding.ts`; bio row renders all fields
  including "Undrafted" case; goalie vs. skater box-score branching;
  advanced-stats section hidden for goalies.
- Backend: extend existing `/api/players` test coverage to assert the new
  SELECT fields (`headshot_url`, birth city/state, draft fields) are
  returned.
- Manual verification (per `verification-before-completion`): click through
  several players of each position (F/D/G), one with no headshot, one
  undrafted, confirm rendering matches design in the actual running app.
