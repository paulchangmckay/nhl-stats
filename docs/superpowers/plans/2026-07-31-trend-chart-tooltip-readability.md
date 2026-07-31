# Trend Chart Tooltip Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the player overlay's bare, unstyled Recharts default tooltip on the CF% trend chart with a friendly, app-styled tooltip and matching X-axis labels.

**Architecture:** A pure `formatSeasonId` helper in `frontend/src/lib/utils.ts` converts raw `season_id` strings (e.g. `"20232024"`) to the app's existing en-dash display format (`"2023–24"`). A new exported `CFTrendTooltip` component in `PlayerProfilePanel.tsx` renders a custom tooltip matching the app's popover styling, wired in via Recharts' `Tooltip` `content` prop with `filterNull={false}` so null seasons still render `-` instead of vanishing.

**Tech Stack:** React 19, TypeScript, Recharts 3.10, Vitest + Testing Library, Tailwind (via `className`).

## Global Constraints

- Season display format: en-dash two-digit style, `"2023–24"` — matches `SeasonPicker.tsx`'s existing `SEASONS` lookup table. Do not use a hyphen or four-digit end year.
- Tooltip styling must match the app's existing popover convention exactly: `rounded-lg bg-popover p-2.5 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10` (from `frontend/src/components/ui/popover.tsx:35-40`).
- Null values render as `-`, matching `PercentileBox`/`ZScoreBox`/`StatCell` elsewhere in `PlayerProfilePanel.tsx` — never `null`, `undefined`, or blank.
- `<Tooltip>` must set `filterNull={false}` — Recharts' default (`true`) strips null-valued payload entries before `content` ever receives them, which would silently show no tooltip at all for a null-`cf_pct` season.
- `CFTrendTooltip` must be typed with `TooltipContentProps` (imported from `"recharts"`), not `TooltipProps` — these are different types in Recharts v3; `TooltipProps` is what you pass to `<Tooltip>`, `TooltipContentProps` is what the `content` render function receives.
- `formatSeasonId` must accept `string | number` (not just `string`) — it's called from both `XAxis`'s `tickFormatter` (`value: any`) and the tooltip's `label` (`string | number`).
- Out of scope: `SeasonPicker.tsx`, the chart's line color/data/series, and the separate stat-box explanatory-tooltip feature (`docs/superpowers/specs/2026-07-30-player-metric-tooltips-and-graph-filter-design.md`).

---

## Task 1: `formatSeasonId` utility

**Files:**
- Modify: `frontend/src/lib/utils.ts`
- Test: `frontend/src/lib/utils.test.ts` (new file — no existing tests for this file)

**Interfaces:**
- Produces: `formatSeasonId(seasonId: string | number): string` — used by Task 2's `CFTrendTooltip` and by the `XAxis` `tickFormatter` wiring in Task 2.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/utils.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { formatSeasonId } from "./utils";

describe("formatSeasonId", () => {
  it("formats a valid 8-digit season_id as en-dash two-digit style", () => {
    expect(formatSeasonId("20232024")).toBe("2023–24");
  });

  it("formats a numeric season_id the same way", () => {
    expect(formatSeasonId(20232024)).toBe("2023–24");
  });

  it("falls back to the raw string for malformed input", () => {
    expect(formatSeasonId("2023")).toBe("2023");
    expect(formatSeasonId("not-a-season")).toBe("not-a-season");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "frontend" && npx vitest run src/lib/utils.test.ts`
Expected: FAIL — `formatSeasonId` is not exported from `./utils`

- [ ] **Step 3: Write minimal implementation**

Add to `frontend/src/lib/utils.ts` (append after the existing `cn` function):

```ts
export function formatSeasonId(seasonId: string | number): string {
  const str = String(seasonId);
  if (!/^\d{8}$/.test(str)) return str;
  return `${str.slice(0, 4)}–${str.slice(6, 8)}`;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "frontend" && npx vitest run src/lib/utils.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/utils.ts frontend/src/lib/utils.test.ts
git commit -m "Add formatSeasonId helper for friendly season display"
```

---

## Task 2: `CFTrendTooltip` component and chart wiring

**Files:**
- Modify: `frontend/src/components/PlayerProfilePanel.tsx:9-16` (imports), `:327-336` (chart JSX)
- Test: `frontend/src/components/PlayerProfilePanel.test.tsx`

**Interfaces:**
- Consumes: `formatSeasonId(seasonId: string | number): string` from Task 1 (`frontend/src/lib/utils.ts`).
- Produces: exported `CFTrendTooltip` component, used only within this file's own chart JSX but exported for direct unit testing.

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/components/PlayerProfilePanel.test.tsx`, near the top (after existing imports):

```ts
import { CFTrendTooltip } from "./PlayerProfilePanel";
```

Add a new `describe` block at the end of the file, before the final closing of the outer `describe("PlayerProfilePanel", ...)` block — i.e. as its own top-level `describe`:

```tsx
describe("CFTrendTooltip", () => {
  it("shows the friendly season and formatted CF% value when active", () => {
    render(
      <CFTrendTooltip
        active
        payload={[{ value: 55, graphicalItemId: "cf_pct" }]}
        label="20232024"
      />
    );
    expect(screen.getByText("2023–24")).toBeInTheDocument();
    expect(screen.getByText("CF% 55%")).toBeInTheDocument();
  });

  it("renders nothing when inactive", () => {
    const { container } = render(
      <CFTrendTooltip active={false} payload={[{ value: 55, graphicalItemId: "cf_pct" }]} label="20232024" />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when payload is empty", () => {
    const { container } = render(
      <CFTrendTooltip active payload={[]} label="20232024" />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a dash for a null value instead of the literal null", () => {
    render(
      <CFTrendTooltip
        active
        payload={[{ value: null, graphicalItemId: "cf_pct" }]}
        label="20232024"
      />
    );
    expect(screen.getByText("CF% -")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "frontend" && npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: FAIL — `CFTrendTooltip` is not exported from `./PlayerProfilePanel`

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/components/PlayerProfilePanel.tsx`, update the recharts import block (currently lines 9-16) to also import the type:

```tsx
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { TooltipContentProps } from "recharts";
```

There is no existing `@/lib/utils` import in this file — add a new import line after the `teamBranding` import (currently line 18):

```tsx
import { formatSeasonId } from "@/lib/utils";
```

Add the `CFTrendTooltip` component, colocated with the file's other small presentational components (e.g. directly after `StatCell`, around line 91):

```tsx
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

Replace the chart JSX (current lines 327-336):

```tsx
<div className="h-40 w-full">
  <ResponsiveContainer width="100%" height="100%">
    <LineChart data={state.data.trend}>
      <XAxis dataKey="season_id" tickFormatter={formatSeasonId} tick={{ fontSize: 10 }} />
      <YAxis tick={{ fontSize: 10 }} />
      <Tooltip content={<CFTrendTooltip />} filterNull={false} />
      <Line type="monotone" dataKey="cf_pct" stroke="var(--color-sky-500)" dot />
    </LineChart>
  </ResponsiveContainer>
</div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "frontend" && npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: PASS (all existing tests plus the 4 new `CFTrendTooltip` tests)

- [ ] **Step 5: Type-check**

Run: `cd "frontend" && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/PlayerProfilePanel.tsx frontend/src/components/PlayerProfilePanel.test.tsx
git commit -m "Replace bare Recharts tooltip with styled CFTrendTooltip"
```

---

## Task 3: Manual verification

**Files:** none (verification only)

- [ ] **Step 1: Start the dev server**

Run: `cd "frontend" && npm run dev`

- [ ] **Step 2: Open the player overlay and check the chart**

Open the app in a browser, open the player overlay for a skater with multiple seasons of trend data, and confirm:
- The X-axis shows friendly season labels (e.g. `"2023–24"`), not raw 8-digit strings.
- Hovering over the trend line shows a tooltip styled like the app's other popovers (rounded, shadowed, ring border) with the season and `"CF% <value>%"`.
- No console errors.

- [ ] **Step 3: Run the full test suite**

Run: `cd "frontend" && npm test`
Expected: all tests pass

- [ ] **Step 4: Stop the dev server**
