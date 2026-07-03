# Advanced Player Filters — Design

## Context

The player table (`templates/index.html`) currently supports: a single Team dropdown
(exact match), a single Season dropdown (one season or "All Seasons (Career)"), and a
Bio/Stats tab toggle. All filtering happens client-side over JSON already loaded from
`/api/players` and `/api/players/stats` — appropriate at this dataset size (~705
players), per existing project convention (`.wolf/cerebrum.md`, 2026-07-02 entry on
client-side filter/sort pattern for ≤1000 rows).

This spec adds five changes to make the UI "more advanced": autocomplete name search,
position filter, multi-select seasons, stat threshold filters, and a richer team
filter (full names + logos).

## Scope

In scope:
1. **Name search with autocomplete** — text input that (a) live-filters the table by
   first/last-name substring match, case-insensitive, same as before, AND (b) shows a
   typeahead suggestion dropdown of up to 8 matching player names below the box.
   Clicking a suggestion clears the search text (restoring the table to its
   non-search-filtered state, other filters still applied) and scrolls to + briefly
   highlights that player's row.
2. **Position filter** — toggle buttons for C / L / R / D / G, multi-select (none
   active = no position filtering).
3. **Season multi-select** — replaces the single Season `<select>` with a checkbox
   dropdown. Multiple specific seasons can be checked at once; stats sum across all
   checked seasons. "All Seasons (Career)" remains available and is mutually
   exclusive with specific-season checkboxes (checking it clears the others and vice
   versa), since career totals come from a separate precomputed table
   (`player_career_stats`) rather than a sum over `player_season_stats`.
4. **Stat threshold filters** (Stats tab only) — four "≥" number inputs: GP, Goals,
   Assists, Points. Minimum-only (no max). Hidden entirely on the Bio tab. Skater
   stats only — goalie stats (W/L/SV%/GAA) are not filtered in this round.
5. **Team filter — full names + logos** — the Team filter converts from a native
   `<select>` to a custom single-select popup dropdown (same component pattern as
   the season multi-select), showing each team's small logo plus full common name
   (e.g. "Carolina Hurricanes"), no abbreviation prefix. Logos are loaded live from
   the NHL CDN (`assets.nhle.com/logos/nhl/svg/{ABBREV}_light.svg`) as plain
   `<img>` tags — no local storage or new backend route.

Out of scope (explicitly not changing):
- The Team column badge in the table body stays exactly as-is: abbreviation only,
  full name as hover tooltip. Only the filter dropdown changes.
- Goalie-specific stat filters.
- Any server-side pagination or query-based (non-JSON-bulk-load) architecture change.
- Automated test suite / CI — this project has no existing test framework
  (`.wolf/cerebrum.md` confirms it's a learning project without CI-level coverage);
  none is introduced as part of this UI change.

## Frontend Design

### Layout

The sticky header (`templates/index.html:190-215`) expands using the existing
`flex-wrap: wrap` behavior, growing to up to three visual rows:

- **Row 1 (always):** title, name search box (with suggestion popup), Team popup
  dropdown, Season checkbox-dropdown button, Bio/Stats tabs, player count.
- **Row 2 (always, both tabs):** position toggle buttons (C/L/R/D/G), styled with the
  existing `.pos-C`/`.pos-L`/etc. color scheme but as clickable toggle buttons with an
  active/pressed visual state (not just badges).
- **Row 3 (Stats tab only):** GP≥, G≥, A≥, Pts≥ number inputs, compact width, visually
  consistent with existing `select` styling. Entirely hidden (not just disabled) when
  `activeTab === "bio"`.

### Name search + autocomplete

- The search `<input>` filters the table live on every keystroke (existing
  first/last-name substring behavior, folded into the filter chain below).
- On the same keystroke, a suggestion popup appears below the input listing up to 8
  matching player names (`"First Last"`, sourced from `bioData` regardless of active
  tab), if the input is non-empty and has at least one match.
- Clicking a suggestion: clears the search input (table reverts to showing all rows
  allowed by the other active filters), closes the popup, scrolls the matched
  player's row into view (`scrollIntoView({behavior: "smooth", block: "center"})`),
  and applies a brief highlight (e.g. a CSS transition on background-color for
  ~1.5s) so the row is easy to spot.
- Popup closes on outside click, Escape, or when the input is cleared.

### Team popup dropdown

Same custom-component pattern as the season dropdown, but single-select:
- Button shows the selected team's logo + full name, or "All Teams" when none
  selected.
- Popup lists "All Teams" first, then one row per team: `<img>` logo (loaded from
  `https://assets.nhle.com/logos/nhl/svg/{abbrev}_light.svg`) + full `common_name`
  text, sorted alphabetically by name (matching the existing `/api/teams` order
  change — see Backend Design).
- Clicking a row selects that team, closes the popup, and re-renders the table
  (same effect as the current `team-filter` change handler).
- Popup closes on outside click or Escape.

### Season checkbox-dropdown

A small custom vanilla-JS component (no new library, consistent with the rest of the
file):
- A button showing the current selection summary (e.g. `"3 Seasons ▾"` or
  `"All Seasons (Career)"` or `"2025–26 ▾"` when only one is checked).
- Clicking it opens a popup `<div>` positioned below the button, containing "All
  Seasons (Career)" at the top, then a checkbox per season (matching the seven
  existing `<option>` values in the current dropdown).
- Checking "All Seasons (Career)" unchecks all specific seasons (and disables them
  visually) and vice versa.
- Popup closes on outside click or Escape.
- Default state on page load stays equivalent to today's default: only "2025–26"
  checked.

### Client-side filtering logic

All new filters (search, position, stat thresholds) join the existing filter chain in
`render()` (`index.html:441-444`) alongside the current team filter:

```
rows = data
  .filter(team match, if any team selected)
  .filter(search match, if search text present — first_name/last_name substring)
  .filter(position match, if any position toggled — position_code in active set)
  .filter(stat thresholds, if activeTab === "stats" — gp/goals/assists/points >= input value, blank input = no filter)
```

No new network calls are introduced by search or position filtering — both operate on
already-loaded `bioData` / `statsData[seasonKey]`. Team filtering still matches on
`team_abbrev` internally; only its selector UI changes (see Team popup dropdown
above) — the underlying filter predicate is unchanged.

## Backend Design

### `/api/teams` — sort order

Currently orders by `abbrev` (`app.py:39`). Changes to order by `common_name` so the
new team popup dropdown lists teams alphabetically by full name, matching how the
dropdown is displayed. No response shape change — `abbrev` and `common_name` are
already returned; only the SQL `ORDER BY` clause changes.

### `/api/players/stats` — multi-season support

Changes from a single `season` query param to a `seasons` query param accepting a
comma-separated list, e.g. `?seasons=20242025,20232024,20222023`.

- If the list is exactly `["all"]`: unchanged — uses the existing
  `player_career_stats` fast-path query (`app.py:92-125`).
- Otherwise: the existing single-season branch (`app.py:127-158`) generalizes from
  `WHERE s.season_id = ?` to `WHERE s.season_id IN (...)`, still `GROUP BY
  p.player_id`, summing counting stats (GP, G, A, Pts, PIM, PPG, SHG, Shots) across
  all seasons in the list. This already produces correct results for a list of
  exactly one season, so it fully replaces the old single-season code path — no
  separate single-season branch is needed.
- Rate/derived stats (Avg TOI, SH%, SV%, GAA) keep the current simplification —
  `MAX(CASE WHEN game_type=2 ...)` picks one representative value rather than
  computing a true weighted average across the selected seasons. This mirrors the
  existing single-season behavior's limitation and is not solved by this change.

### Frontend caching

`statsData` keys change from a single season id to the sorted, joined season-list
string used as the cache key (e.g. `"20222023,20232024"`), so re-selecting a
previously-fetched season combination doesn't refetch.

## Testing Plan

No automated test suite exists for this project. Verification is manual, via the dev
server (`python app.py`, after clearing port 5000 per `.wolf/cerebrum.md`):

1. Each new filter narrows the visible rows correctly in isolation.
2. Filters combine correctly (e.g. position=C AND search="mcd" AND Pts>=50).
3. Stat threshold row is visible on Stats tab, absent on Bio tab, and clears/ignored
   when switching to Bio.
4. Selecting "All Seasons (Career)" clears specific-season checkboxes and vice versa.
5. A 2-3 season combination's summed totals for a spot-checked player match manual
   addition of their per-season stats from `player_season_stats`.
6. Player count label reflects the fully-filtered row count, not just team-filtered
   count (existing `count-label` logic needs to account for all active filters, not
   only `activeTeam`).
7. Typing in the search box shows correct suggestions (max 8, name-substring match)
   and live-narrows the table at the same time; clicking a suggestion clears the
   search box, scrolls to, and highlights the right row.
8. Team popup dropdown lists teams alphabetically by full name with a logo per row;
   selecting one filters the table the same as the old native `<select>` did.
9. Team logos load correctly from the NHL CDN and degrade gracefully (broken-image
   icon, not a layout break) if a given abbreviation's logo URL 404s.
