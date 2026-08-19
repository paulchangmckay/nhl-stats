# Visual Identity & Theme — Design

**Date:** 2026-08-19
**Status:** Approved
**Scope:** Group 1 of 3 from the [NHL Stats UI/UX audit](../../../.wolf/memory.md) — must-fix items #1, #2, #9.

## Problem

The app renders on the stock, unmodified shadcn "zinc" theme — every color token in `frontend/src/index.css` is zero-chroma gray (`oklch(x 0 0)`). The only color anywhere in the app comes from per-team accents on two pages, despite `frontend/src/lib/teamBranding.ts` holding 32 fully-researched team palettes unused. Dark mode is hardcoded (`index.html:2`, `class="dark"`) with no toggle, which leaves the entire light-theme `:root` block in `index.css` as dead code that can never render, and no `color-scheme` meta tag, so native browser controls don't match the forced-dark theme. Separately, position color-coding is inconsistent: `PositionToggle.tsx` color-codes each position (C/L/R/D/G) but `PlayerTable.tsx`'s position `Badge` renders as plain neutral outline — the color language a user learns from the toggle disappears in the table.

## Goals

- Give the app a real, deliberate visual identity — one ice-blue accent family, not stock gray.
- Remove dead code: the unreachable light-theme token block and the now-redundant `.dark {}` override.
- Make position color-coding consistent between `PositionToggle` and `PlayerTable`.

## Anti-goals

- Not building a light/dark toggle — this is a single-user hobby project (Tier 0), dark-only is a deliberate, confirmed choice.
- Not touching per-team accent colors (Home hero, TeamPage, PlayerProfilePanel) — those are already correct and out of scope.
- Not introducing a new component library or design token abstraction beyond CSS custom properties already in place.

## Design

### Theme tokens (`frontend/src/index.css`)

Single-theme rewrite, no new abstraction layer:

- Retint `:root` tokens to an ice-blue family, pinned to these exact values (locked during grilling — no free-form "pick a blue" left to implementation time):

  ```
  --background:          oklch(0.16 0.02 240)
  --foreground:          oklch(0.97 0.01 235)
  --card:                oklch(0.21 0.02 240)
  --card-foreground:     oklch(0.97 0.01 235)
  --primary:             oklch(0.75 0.13 230)   /* ice blue */
  --primary-foreground:  oklch(0.18 0.03 240)   /* dark navy on ice blue */
  --border:              oklch(1 0 0 / 10%)     /* unchanged — alpha-based, tint-agnostic */
  --popover:             oklch(0.21 0.02 240)
  --popover-foreground:  oklch(0.97 0.01 235)
  --secondary:           oklch(0.27 0.02 240)
  --secondary-foreground: oklch(0.97 0.01 235)
  --muted:               oklch(0.27 0.02 240)
  --muted-foreground:    oklch(0.70 0.02 235)
  --accent:              oklch(0.27 0.02 240)   /* shadcn hover-surface token, distinct from brand accent above */
  --accent-foreground:   oklch(0.97 0.01 235)
  --input:               oklch(1 0 0 / 15%)
  --ring:                oklch(0.70 0.12 230)
  ```

  `--primary` (L 0.75) against `--primary-foreground` (L 0.18) gives a large lightness gap, expected to clear WCAG AA (4.5:1) comfortably for button/focus-ring text — confirmed visually during the acceptance check below, not just assumed from the numbers.
  `--destructive` stays red, unchanged (error/invalid states, unrelated to brand accent).
  `--sidebar*` tokens (`--sidebar`, `--sidebar-foreground`, `--sidebar-primary`, `--sidebar-primary-foreground`, `--sidebar-accent`, `--sidebar-accent-foreground`, `--sidebar-border`, `--sidebar-ring`) and `--chart-1` through `--chart-5` are all dead — grepped, zero usage anywhere in `src/`. Delete them rather than spending design effort retinting values nothing reads.

**Follow-up, explicitly out of scope here:** `PlayerProfilePanel.tsx:28-31`'s trend-line chart uses its own hardcoded, unrelated palette (`sky-500, amber-500, emerald-500, rose-500, violet-500, cyan-500`) that has nothing to do with the ice-blue identity this spec builds. Confirmed via grep — `--chart-*` tokens aren't referenced there or anywhere else. Not fixed in this spec (would expand the file list beyond what's approved); worth its own follow-up item.
- Delete the light-mode `:root` block (currently lines 8-41) — it can never render since `class="dark"` is hardcoded.
- Delete the `.dark { ... }` override block (currently lines 43-75) — fold its role into `:root` directly, since there is only one theme now. No behavior change: `:root` becomes the single source of truth for all color tokens.
- Keep `class="dark"` on `<html>` (`index.html:2`) and the `@custom-variant dark (&:where(.dark, .dark *));` declaration (`index.css:6`) untouched. Seven installed shadcn primitives (`button.tsx`, `badge.tsx`, `input.tsx`, `checkbox.tsx`, `toggle.tsx`, `textarea.tsx`, `input-group.tsx`) use Tailwind's `dark:` variant internally and must keep resolving correctly.
- `--destructive` stays red, unchanged (error/invalid states, unrelated to brand accent).

### Color-scheme meta tag (`frontend/index.html`)

Add `<meta name="color-scheme" content="dark">` so native controls (date pickers, scrollbars, form-control chrome) render correctly against the forced-dark theme.

### Position color consistency

New file `frontend/src/lib/positionColors.ts` exports a single `POSITION_COLORS` map keyed by position code (`C`, `L`, `R`, `D`, `G`). Each entry holds two pre-written, complete Tailwind class strings — never concatenated/derived at runtime, so Tailwind's JIT scanner sees full literals in source and doesn't silently drop classes:

```ts
export const POSITION_COLORS: Record<"C" | "L" | "R" | "D" | "G", { toggleClass: string; badgeClass: string }> = {
  C: { toggleClass: "text-green-500 aria-pressed:bg-green-500 aria-pressed:text-background", badgeClass: "border-green-500/40 bg-green-500/10 text-green-500" },
  L: { toggleClass: "text-blue-400 aria-pressed:bg-blue-400 aria-pressed:text-background", badgeClass: "border-blue-400/40 bg-blue-400/10 text-blue-400" },
  R: { toggleClass: "text-sky-300 aria-pressed:bg-sky-300 aria-pressed:text-background", badgeClass: "border-sky-300/40 bg-sky-300/10 text-sky-300" },
  D: { toggleClass: "text-purple-300 aria-pressed:bg-purple-300 aria-pressed:text-background", badgeClass: "border-purple-300/40 bg-purple-300/10 text-purple-300" },
  G: { toggleClass: "text-orange-400 aria-pressed:bg-orange-400 aria-pressed:text-background", badgeClass: "border-orange-400/40 bg-orange-400/10 text-orange-400" },
};
```

- `PositionToggle.tsx` imports `POSITION_COLORS` instead of defining its own local `POSITION_CLASSES`; each `ToggleGroupItem` uses `.toggleClass` (the existing values, moved as-is — no color changes to the toggle itself).
- `PlayerTable.tsx:113-114` imports the same map and applies `.badgeClass` to the position `Badge` (replacing the current neutral `variant="outline"`), so a user who's learned the toggle's color language sees it carried through in the table.

## Testing

Pure CSS/token changes (theme retint, dead-code removal, meta tag) have no meaningful unit test — a string-match on OKLCH literals would break on any future nudge without catching a real regression, so this is a deliberate TDD exemption for non-behavioral styling, not a gap. Verified visually instead: run `openwolf designqc` (per `.claude/rules/openwolf.md`) to capture screenshots across Home/Players/Teams/a Team page/Top Players, read them from `.wolf/designqc-captures/`, confirm the ice-blue accent renders consistently, contrast holds on buttons/focus rings, and there's no visual regression versus the current audit screenshots.

The position-color fix gets tests in both existing test files touching the shared map:

- `PlayerTable.test.tsx`: `MOCK_STATS` only covers `C`/`G` — rather than extending that shared fixture (other tests depend on its exact shape/count), the new test builds a small local inline fixture (one minimal row per position code, all 5) passed directly to `<PlayerTable rows={...} .../>`, asserting each row's `Badge` carries the `.badgeClass` defined in `POSITION_COLORS` for that code.
- `PositionToggle.test.tsx` (already exists): extend with one assertion per position code, asserting each `ToggleGroupItem` carries the matching `.toggleClass`.

Together these verify both consumers of the shared map are actually wired in, not just that the map exists.

## Files touched

- `frontend/src/index.css` — retint, delete light block, delete `.dark` block
- `frontend/index.html` — add `color-scheme` meta tag
- `frontend/src/lib/positionColors.ts` — new, shared color map
- `frontend/src/components/PositionToggle.tsx` — consume shared map
- `frontend/src/components/PlayerTable.tsx` — consume shared map, colored position badge
