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

New pure function in `frontend/src/lib/utils.ts`. Accepts `string | number`
because Recharts calls it two different ways: `XAxis`'s `tickFormatter`
passes `value: any`, while the tooltip's `label` is typed `string | number`
— both get normalized to a string internally:

```ts
export function formatSeasonId(seasonId: string | number): string {
  const str = String(seasonId);
  if (!/^\d{8}$/.test(str)) return str; // fallback for unexpected input
  return `${str.slice(0, 4)}–${str.slice(6, 8)}`; // "20232024" -> "2023–24"
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
colocates `PercentileBox`/`ZScoreBox`/`StatCell` — but **exported** (unlike
those) so it can be unit-tested directly without rendering the full chart
(see Testing Plan).

Note the type is `TooltipContentProps`, not `TooltipProps` — `TooltipProps`
is what you pass *to* `<Tooltip>` (includes `content`, `cursor`, etc.);
`TooltipContentProps` is what Recharts actually passes to the `content`
render function (`active`, `payload`, `label`, `coordinate`, ...):

```tsx
import type { TooltipContentProps } from "recharts";

export function CFTrendTooltip({ active, payload, label }: TooltipContentProps<number, string>) {
  if (!active || !payload?.length) return null;
  const value = payload[0].value;
  return (
    <div className="rounded-lg bg-popover p-2.5 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10">
      <div className="text-xs text-muted-foreground">{formatSeasonId(label ?? "")}</div>
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
<Tooltip content={<CFTrendTooltip />} filterNull={false} />
<Line type="monotone" dataKey="cf_pct" stroke="var(--color-sky-500)" dot />
```

Axis ticks get the same friendly season format as the tooltip. Line
color/data/behavior are unchanged.

`filterNull={false}` is required: Recharts' `<Tooltip>` defaults to
`filterNull: true`, which strips any payload entry whose value is
`null`/`undefined` *before* `content` ever sees it. Without this override,
a season with `cf_pct: null` would receive an empty `payload` and the
tooltip would silently render nothing at all — inconsistent with every
other null-value display in this file, which shows `-` rather than
vanishing.

## Edge Cases

- `cf_pct` is `null` for a given season (per `AdvancedTrendPoint`'s type)
  → with `filterNull={false}`, the payload entry still reaches
  `CFTrendTooltip`, which shows `CF% -`, matching the `-` convention used
  for null values in `PercentileBox`/`ZScoreBox`.
- `season_id` doesn't match the expected 8-digit shape → `formatSeasonId`
  falls back to the raw string rather than producing a malformed label.
- Hovering outside any data point (`active` is `false`, or `payload` is
  empty) → tooltip renders nothing, matching Recharts' own convention for
  a custom tooltip `content`.

## Testing Plan

This codebase has no existing test that renders the trend chart or any
Recharts output, and its `vitest.config.ts` uses `environment: "jsdom"`
with only a no-op `ResizeObserver` polyfill (`test-setup.ts:11-17`) — not
a real layout engine. Recharts' `ResponsiveContainer` needs a non-zero
container size to render its SVG/children, which jsdom doesn't provide
without additional mocking. Rather than introduce that mocking (and
hover-event simulation on generated SVG nodes) for the first time here,
`CFTrendTooltip` is tested directly as an exported component with
constructed props — the standard pattern for testing custom Recharts
tooltip content, and independent of chart-sizing concerns entirely.

**Frontend** (`PlayerProfilePanel.test.tsx`):
- `formatSeasonId`: valid 8-digit input formats correctly (`"20232024"` →
  `"2023–24"`); malformed input (wrong length/non-numeric, including a raw
  number) falls back to the raw string unchanged.
- `CFTrendTooltip`, rendered directly with `active payload={[{ value: 55 }]}
  label="20232024"`, shows `"CF% 55%"` and the formatted season
  `"2023–24"`, not the raw key/id.
- `CFTrendTooltip`, rendered with `active={false}` (or an empty `payload`),
  renders nothing.
- `CFTrendTooltip`, rendered with `payload={[{ value: null }]}`, shows
  `"CF% -"` rather than `null`/`undefined`/blank.

**Manual verification** (per `verification-before-completion`): open the
player overlay for a skater with multiple seasons of trend data, hover
across the chart, confirm the tooltip shows a friendly season and a
percentage value styled consistently with the app's other popovers, and
confirm the X-axis itself now shows friendly season labels.
