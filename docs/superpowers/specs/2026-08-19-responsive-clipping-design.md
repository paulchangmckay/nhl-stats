# Responsive Clipping Fixes — Design

**Date:** 2026-08-19
**Status:** Approved
**Scope:** Group 3a of 3 sub-projects under Group 3 ("Data Table & Layout") from the [NHL Stats UI/UX audit](../../../.wolf/memory.md) — must-fix items #6 (PlayerProfilePanel stat grids clip on narrow viewports) and #7 (Teams grid clips long team names).

## Problem

Two layouts overflow their containers instead of wrapping/reflowing, confirmed live:

1. **`Teams.tsx:22-29`** — the grid item (`<Link>`) has no `min-w-0`. Its default `min-width: auto` lets long team names overflow the card edge instead of wrapping. Confirmed at ~480-750px viewport width: "Boston Bruins" renders as "Boston Bruin", cut off, no wrap, no ellipsis.
2. **`PlayerProfilePanel.tsx`** — 4 fixed-column stat grids (goalie `grid-cols-4`, skater `grid-cols-6`, percentile `grid-cols-5`, z-score `grid-cols-3`) have no responsive breakpoints. The dialog itself (`sm:max-w-lg`, `frontend/src/components/PlayerProfilePanel.tsx:286`) is `max-w-[calc(100%-2rem)]` below the `sm` (640px) breakpoint — roughly 311px of usable content width on a mobile viewport. At that width, 5-6 fixed columns leave ~45-70px per cell. Confirmed live in the McDavid profile dialog: "PIM" (skater-6 grid), "Primary Pts" (percentile-5 grid), and "Rebounds..." (z-score-3 grid, long labels like "Rebounds Created/60") all render off the right edge with no indication more content exists.

## Goals

- Long team names wrap onto a second line instead of being cut off.
- All 4 PlayerProfilePanel stat grids reflow to fewer columns below the `sm` breakpoint, so cells have room for their content.

## Anti-goals

- Not redesigning the Teams grid's column-count breakpoints (`grid-cols-2 sm:grid-cols-4 lg:grid-cols-6`) — those are unrelated to the wrapping bug and already reasonable.
- Not touching the dialog's own width breakpoints (`max-w-[calc(100%-2rem)] sm:max-w-lg`) — the fix is making the grids *inside* the dialog adapt to that existing width, not changing the dialog's width itself.
- The goalie `grid-cols-4` grid wasn't in the audit's confirmed screenshot (the test player was a skater) but has the identical structural issue and is in the same file already being touched — included for consistency, not scope creep into a different file.

## Design

### Teams grid (`frontend/src/pages/Teams.tsx:22-25`)

Add `min-w-0` to the `Link`'s existing className:
```tsx
className="flex min-w-0 flex-col items-center gap-2 rounded-lg border border-border p-4 text-center transition-colors hover:bg-muted"
```
No other changes — the `<span>` text wraps by default once the grid item is allowed to shrink below its unconstrained content width.

### PlayerProfilePanel stat grids

Four className changes, each just adding a mobile-width column count before the existing `sm:` breakpoint:

| Grid | Location | Current | New |
|---|---|---|---|
| Goalie stats (7 cells) | `PlayerProfilePanel.tsx:342` | `grid grid-cols-4 gap-2 text-center text-sm` | `grid grid-cols-3 gap-2 text-center text-sm sm:grid-cols-4` |
| Skater stats (6 cells) | `PlayerProfilePanel.tsx:352` | `grid grid-cols-6 gap-2 text-center text-sm` | `grid grid-cols-3 gap-2 text-center text-sm sm:grid-cols-6` |
| Percentile boxes (5 cells) | `PlayerProfilePanel.tsx:387` | `grid grid-cols-5 gap-2` | `grid grid-cols-3 gap-2 sm:grid-cols-5` |
| Z-score boxes (3 cells, long labels) | `PlayerProfilePanel.tsx:404` | `grid grid-cols-3 gap-2` | `grid grid-cols-1 gap-2 sm:grid-cols-3` |

Rationale per grid: goalie/skater/percentile grids get roughly half their column count below `sm` (wraps to 2-3 rows instead of clipping); the z-score grid's labels are long enough ("Rebounds Created/60") that even 2 columns would still be tight, so it goes to single-column (stacked) below `sm`.

## Testing

jsdom (Vitest's test environment) doesn't evaluate CSS media queries or compute real layout, so a unit test can't detect actual visual overflow — asserting `sm:grid-cols-6` is present in a className string doesn't verify it prevents clipping at 375px. The real verification is visual, via two different mechanisms since `openwolf designqc` only navigates routes — it has no way to click and open the profile dialog:

- **Teams grid:** `openwolf designqc` against `/teams`, mobile capture included by default (only `--desktop-only` skips it) — confirms team names wrap instead of clipping.
- **PlayerProfilePanel:** `designqc` can't reach it (no route opens the dialog directly — that's precisely audit finding #8's gap, addressed in a later sub-project, not this one). Use the `playwright` MCP tools directly: navigate to `/players` at a narrow viewport (e.g. 375px), click a skater row to open the dialog, screenshot it; repeat for a goalie row (different grid). Confirms no stat cell text is cut off at either viewport width.

No new unit tests are added for this reason — this is a deliberate exemption (same category as Group 1's CSS-only exemption), not a gap. Existing tests for both components (`Teams.test.tsx`, `PlayerProfilePanel.test.tsx`) continue to pass unmodified since neither file's tested behavior (links rendering, stat values rendering) changes — only layout classes do.

## Files touched

- `frontend/src/pages/Teams.tsx` — `min-w-0` on the grid item
- `frontend/src/components/PlayerProfilePanel.tsx` — responsive column counts on 4 grids
