# Player Metric Tooltips & Click-to-Filter Graph — Design

## Context

`docs/superpowers/specs/2026-07-25-player-profile-overlay-design.md` built
`PlayerProfilePanel`, which includes an advanced-stats section (percentile
boxes, per-60 z-score boxes, a strength-state toggle, and a single-line
trend chart) carried over unchanged from the earlier `PlayerAdvancedPanel`.
That section has two gaps: only 2 of 10 advanced-stat boxes have any
explanatory tooltip (and those use the bare `title` attribute), and the
trend chart is hardcoded to one fixed metric (`cf_pct`) with no way to view
any other metric's history.

This spec adds proper tooltips to every advanced-stat box (name, what it
measures, calculation) and makes each box clickable to filter which
metric(s) the trend graph displays.

## Scope

In scope — the 10 advanced-stat boxes only:
- Percentile row: CF%, FF%, HDCF%, Primary Pts
- Per-60 z-score row: Shots/60, Chances/60, Rebounds Created/60,
  Deflections/60, Points/60, Primary Points/60

Out of scope: the basic box-score boxes (GP/G/A/P/+/-/PIM, or the goalie
GP/W/L/OTL/SV%/GAA/SO equivalents) — self-explanatory, not graphed. Goalies
have no advanced-stats section at all today and this spec doesn't add one.

### Metric families

Clicking a box outside the currently-selected family replaces the
selection (single active family at a time); clicking within the active
family toggles that box in/out of the current multi-select. The last
remaining box in a selection cannot be deselected (a click that would
empty the selection is a no-op) — the graph is never empty.

| Family | Metrics | Strength-aware? |
|---|---|---|
| Percentage | CF%, FF%, HDCF% | Yes — follows the 5v5/5v4/4v5 toggle |
| Count | Primary Pts | Yes |
| Composite | PDO | No — always 5v5 |
| Per-60 rate | Shots/60, Chances/60, Rebounds Created/60, Deflections/60, Points/60, Primary Points/60 | No — always 5v5 |

Default state on dialog open: CF% selected, 5v5 active (matches today's
behavior/graph exactly).

## Data Flow

### Backend: extend `GET /api/players/<id>/advanced`

**Prerequisite fix, in scope for this spec:** `player_season_advanced_stats`
has a `game_type` dimension (2=regular season, 3=playoffs), with a separate
row per player/season/game_type/strength_state. Neither of
`_fetch_player_advanced`'s existing queries — the current-season
`season_rows` query (`app.py:246-251`) nor the single-metric `trend` query
being replaced (`app.py:301-307`) — filters by `game_type`, so a player
who's made the playoffs has both rows pulled in undifferentiated for the
same `season_id`. This is a known, already-logged gap
(`.wolf/buglog.json`, found while grilling the 2026-07-27
shot-generation-rate-stats spec): `compute_zscores()` already established
the fix pattern (`AND game_type = 2`), and the buglog entry explicitly
recommends applying it "when this gets fixed" in a future touch of this
area. Since this spec is already rewriting the trend query and this exact
function, both `season_rows` and the new trend query add
`AND game_type = 2`. (`player_advanced_percentiles`'s population — the
`compute_percentiles()` ETL step — has the same underlying gap but at the
*compute* stage, not just the query stage; fixing that requires an ETL
logic change and a rerun, a materially bigger task than this spec's
frontend-focused scope, so it stays deferred exactly as buglog.json
already tracks it.) Existing test fixtures (`tests/test_app_advanced_stats.py`,
`_seed_season_row`) already hardcode `game_type=2` for every row, so this
fix doesn't change any existing test's expected values.

`_fetch_player_advanced` (`app.py`) replaces its current single-metric
trend query with one parameterized query producing a flat, season-ordered
array — one row per `(season_id, strength_state)` — instead of today's
`[{season_id, cf_pct}]`:

```
trend: [
  { season_id, strength_state, cf_pct, ff_pct, hdcf_pct, primary_points,
    pdo, shots_per60, chances_per60, rebounds_created_per60,
    deflections_per60, points_per60, primary_points_per60 },
  ...
]
```

- `cf_pct`/`ff_pct`/`hdcf_pct`/`primary_points` are populated for all three
  `strength_state` rows per season, sourced from
  `player_season_advanced_stats`.
- `pdo`, and the six `*_per60` fields, are populated only on the
  `strength_state = "5v5"` row for each season (left-joined from
  `player_rate_zscores` and `team_season_advanced_stats`, both of which are
  5v5-only tables with no `strength_state` column); `null` on `5v4`/`4v5`
  rows.
- This mirrors the existing per-request query pattern in
  `_fetch_player_advanced` (current-season percentile/z-score/PDO lookups),
  just parameterized across all of a player's seasons instead of one.

`docs/api/advanced-stats.md` gets a new section documenting this `trend`
shape. `tests/test_app_advanced_stats.py`'s
`test_fetch_player_advanced_includes_trend_across_seasons` is updated for
the new row shape (still flat/season-ordered — additive change, not a
rewrite), plus new cases: per-60/PDO fields are `null` on non-5v5 rows,
and a `game_type=3` (playoff) row seeded for a season is excluded from
both `trend` and `strength_states` (covering the `game_type = 2` fix
above).

`frontend/src/lib/types.ts`'s `AdvancedTrendPoint` type is updated from
`{ season_id, cf_pct }` to the full new row shape (all fields except
`season_id`/`strength_state` nullable). `frontend/src/lib/mock-data.ts`'s
trend fixture is updated to match, for use in the new frontend tests
below.

### Frontend: metric definitions

New `frontend/src/lib/metricDefinitions.ts` — single source of truth for
tooltip copy, hand-authored from `docs/api/advanced-stats.md`:

```ts
export type MetricKey =
  | "cf_pct" | "ff_pct" | "hdcf_pct" | "primary_points" | "pdo"
  | "shots_per60" | "chances_per60" | "rebounds_created_per60"
  | "deflections_per60" | "points_per60" | "primary_points_per60";

export interface MetricDefinition {
  label: string;        // short box label, e.g. "CF%"
  name: string;          // full name, e.g. "Corsi For %"
  description: string;   // what it measures, plain language
  formula: string;       // calculation, e.g. "cf / (cf + ca) × 100"
  family: "percentage" | "count" | "composite" | "per60";
  strengthAware: boolean;
}

export const METRIC_DEFINITIONS: Record<MetricKey, MetricDefinition> = { ... };
```

Both the tooltip and the box's `metricKey`/family-capping logic read from
this config — no duplicated copy or family lists elsewhere.

### Frontend: tooltip component

New `frontend/src/components/ui/tooltip.tsx`, generated the same way as
the existing `dialog.tsx`/`popover.tsx` (shadcn CLI, base-ui `Tooltip`
primitive) — matches the project's existing convention for `ui/`
components, and provides hover+focus triggering with correct
`role="tooltip"` out of the box, rather than repurposing `Popover`
(click-triggered) or hand-rolling one.

## Component Design

**`PercentileBox` / `ZScoreBox`** — existing value-display logic
unchanged. Both gain `metricKey: MetricKey`, `selected: boolean`,
`onToggle: (key: MetricKey) => void` props. Each box is wrapped in the new
`Tooltip`, showing `name` / `description` / `formula` from
`METRIC_DEFINITIONS` on hover or keyboard focus. Clicking the box body (or
Enter/Space when focused) calls `onToggle`; a `selected` box gets a visible
highlighted border/ring, consistent with the existing `strengthState`
button's `variant="default"` vs `"outline"` active/inactive treatment.

**`PlayerProfilePanel`** — new local state:

```ts
const [selectedMetrics, setSelectedMetrics] = useState<Set<MetricKey>>(
  new Set(["cf_pct"])
);
```

`onToggle(key)` logic: if `METRIC_DEFINITIONS[key].family` differs from the
family of the currently-selected metrics, replace the selection with
`new Set([key])`; otherwise toggle `key` in/out of the existing set,
except a toggle-off that would leave the set empty is ignored. Resets to
`new Set(["cf_pct"])` when `playerId` changes (same effect that already
resets `photoFailed`/`logoFailed` on player change).

**Graph** — `trend` is filtered client-side before rendering:

```ts
const activeStrengthState = METRIC_DEFINITIONS[first(selectedMetrics)].strengthAware
  ? strengthState
  : "5v5";
const chartData = state.data.trend.filter(r => r.strength_state === activeStrengthState);
```

One Recharts `<Line dataKey={key} />` per key in `selectedMetrics`, each a
distinct color, with a small legend showing `METRIC_DEFINITIONS[key].label`
per line. Switching the 5v5/5v4/4v5 toggle re-filters `chartData` in place
for strength-aware selections; it's a no-op for per60/PDO selections
(always 5v5).

## Edge Cases

- Toggling off the last selected box in a family → no-op, selection stays
  non-empty (graph never renders with zero lines).
- Switching strength state while a per60/PDO metric is selected → graph
  data unaffected (always reads the 5v5 rows for those metrics), only the
  percentage/count-family boxes' own displayed values change.
- Player/season with fewer seasons of trend history than others → graph
  renders whatever rows exist; no minimum-seasons requirement (matches
  today's behavior).
- Changing players (`playerId` changes) while the dialog is open →
  selection resets to default (`cf_pct`, 5v5), same lifecycle as the
  existing photo/logo-failure reset.
- Keyboard-only navigation: tooltip shows on focus (not just hover); box
  toggle fires on Enter/Space when focused — required since boxes become
  interactive, not just for mouse users.

## Testing Plan

**Backend** (`tests/test_app_advanced_stats.py`):
- Update `test_fetch_player_advanced_includes_trend_across_seasons` for
  the new row shape (`strength_state` field, multi-metric).
- New case: a season's `5v4`/`4v5` trend rows have `null` `pdo` and
  `*_per60` fields; the `5v5` row for that season has them populated.
- New case: `cf_pct`/`ff_pct`/`hdcf_pct`/`primary_points` differ correctly
  across the three strength-state rows for the same season.
- New case: a `game_type=3` (playoff) row seeded for a player/season is
  excluded from both `trend` and `strength_states` — covers the
  `game_type = 2` fix to both queries.

**Frontend** (`PlayerProfilePanel.test.tsx`):
- Hovering/focusing a box shows its tooltip with the expected name/
  description/formula text from `metricDefinitions.ts`.
- Clicking a box within the active family toggles it into/out of
  `selectedMetrics` and the graph's rendered `<Line>` set.
- Clicking a box from a different family replaces the selection
  (previously-selected boxes un-highlight, graph drops their lines).
- Clicking the sole selected box is a no-op (stays selected, graph
  unchanged).
- Switching the strength-state toggle re-filters the graph's data for a
  strength-aware selection; per60/PDO selections are unaffected by the
  toggle.
- Changing `playerId` resets selection to default (`cf_pct`, 5v5).

**Manual verification** (per `verification-before-completion`): open the
overlay for a skater with multiple seasons of data, hover each of the 10
boxes to confirm tooltip copy reads correctly, click through several boxes
within and across families, toggle strength states, confirm the graph and
highlighted-box state stay in sync in the actual running app.
