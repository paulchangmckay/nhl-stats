# Trend Chart Tooltip Readability — Design

## Context

`PlayerProfilePanel.tsx` (built in
`docs/superpowers/specs/2026-07-25-player-profile-overlay-design.md`)
includes a small trend chart (Recharts `LineChart`) plotting a player's
`cf_pct` (Corsi-For %) across seasons. The chart's `<Tooltip />`
(`PlayerProfilePanel.tsx:332`) is Recharts' bare, unconfigured default:

- Label = raw `season_id` string, e.g. `"20232024"`.
- Value = raw number with the raw series key `cf_pct` as its name (no
  `name`/`formatter` supplied).
- Styling = Recharts' built-in plain white/gray box — doesn't match the
  app's `--popover`/`--card` design tokens used everywhere else (see
  `popover.tsx`, `dialog.tsx`).

The X-axis (`PlayerProfilePanel.tsx:330`) has the same problem: raw
`season_id` rendered directly as tick labels.

This is a pure readability fix: friendly labels/numbers and app-consistent
styling, no data or behavior changes.

Note: a separate approved spec,
`docs/superpowers/specs/2026-07-30-player-metric-tooltips-and-graph-filter-design.md`,
will later rewrite this same graph block to support multiple selectable
metric lines. That spec adds explanatory hover tooltips to the *stat boxes*
and doesn't touch the chart's own data-point tooltip styling at all, so
this fix is complementary and expected to rebase cleanly when that larger
feature is implemented.

## Scope

In scope: `frontend/src/components/PlayerProfilePanel.tsx` (the trend
chart JSX, `PlayerProfilePanel.tsx:327-336`) and a new formatting helper in
`frontend/src/lib/utils.ts`.

Out of scope: `SeasonPicker.tsx` (has its own hardcoded season-label
lookup table — not touched), the chart's line color/data/series, and the
box-explanation-tooltip feature covered by the separate spec above.

## Design

### 1. Season formatting helper

New pure function in `frontend/src/lib/utils.ts`:

```ts
export function formatSeasonId(seasonId: string): string {
  if (!/^\d{8}$/.test(seasonId)) return seasonId; // fallback for unexpected input
  return `${seasonId.slice(0, 4)}–${seasonId.slice(6, 8)}`; // "20232024" -> "2023–24"
}
```

Uses the same en-dash (`–`) two-digit style already established in
`SeasonPicker.tsx` (`SEASONS` lookup table), so the chart reads
consistently with the rest of the app. Malformed input (unexpected
`season_id` shape) falls back to rendering the raw string rather than
throwing or showing garbled output.

### 2. Custom tooltip component

A small `CFTrendTooltip` component defined locally in
`PlayerProfilePanel.tsx`, colocated the same way the file already
colocates `PercentileBox`/`ZScoreBox`/`StatCell`:

```tsx
function CFTrendTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const value = payload[0].value as number | null;
  return (
    <div className="rounded-lg bg-popover p-2.5 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10">
      <div className="text-xs text-muted-foreground">{formatSeasonId(label)}</div>
      <div className="tabular-nums font-semibold">
        CF% {value == null ? "-" : `${value}%`}
      </div>
    </div>
  );
}
```

Styling mirrors the existing popover convention exactly (`rounded-lg`,
`bg-popover`, `shadow-md`, `ring-1 ring-foreground/10`, `p-2.5`, `text-sm`
— from `popover.tsx`), and the label/value conventions used elsewhere in
this same file (`text-xs text-muted-foreground` for labels, `tabular-nums`
for numbers). Null values render as `-`, matching `PercentileBox`/
`ZScoreBox` elsewhere in the file.

### 3. Wiring

```tsx
<XAxis dataKey="season_id" tickFormatter={formatSeasonId} tick={{ fontSize: 10 }} />
<YAxis tick={{ fontSize: 10 }} />
<Tooltip content={<CFTrendTooltip />} />
<Line type="monotone" dataKey="cf_pct" stroke="var(--color-sky-500)" dot />
```

Axis ticks get the same friendly season format as the tooltip. Line
color/data/behavior are unchanged.

## Edge Cases

- `cf_pct` is `null` for a given season (per `AdvancedTrendPoint`'s type)
  → tooltip shows `CF% -`, matching the `-` convention used for null
  values in `PercentileBox`/`ZScoreBox`.
- `season_id` doesn't match the expected 8-digit shape → `formatSeasonId`
  falls back to the raw string rather than producing a malformed label.
- Hovering outside any data point (`active` is `false`, or `payload` is
  empty) → tooltip renders nothing, matching Recharts' own convention for
  a custom tooltip `content`.

## Testing Plan

**Frontend** (`PlayerProfilePanel.test.tsx`):
- `formatSeasonId`: valid 8-digit input formats correctly (`"20232024"` →
  `"2023–24"`); malformed input (wrong length/non-numeric) falls back to
  the raw string unchanged.
- Trend chart renders the friendly season label (not the raw `season_id`)
  somewhere in the rendered output for the axis.
- Hovering/simulating an active tooltip payload shows `"CF%"` and a
  formatted percentage value, not the raw `cf_pct` key.
- A trend point with `cf_pct: null` renders `-` in the tooltip rather than
  `null`/`undefined`/blank.

**Manual verification** (per `verification-before-completion`): open the
player overlay for a skater with multiple seasons of trend data, hover
across the chart, confirm the tooltip shows a friendly season and a
percentage value styled consistently with the app's other popovers, and
confirm the X-axis itself now shows friendly season labels.
