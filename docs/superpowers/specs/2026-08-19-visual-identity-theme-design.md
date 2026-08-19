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

- Retint `:root` tokens to an ice-blue family: `--primary`, `--ring`, and `--chart-1` through `--chart-5` become a blue ramp (light-to-dark, for consistent data-viz color across recharts usage). `--background`, `--card`, `--border`, `--secondary`, `--muted`, `--accent` (the shadcn semantic hover-surface token, distinct from the new brand accent) get a subtle cool tint instead of pure `oklch(x 0 0)` gray — kept low-chroma so they still read as neutral structure, not competing color.
- Delete the light-mode `:root` block (currently lines 8-41) — it can never render since `class="dark"` is hardcoded.
- Delete the `.dark { ... }` override block (currently lines 43-75) — fold its role into `:root` directly, since there is only one theme now. No behavior change: `:root` becomes the single source of truth for all color tokens.
- Keep `class="dark"` on `<html>` (`index.html:2`) and the `@custom-variant dark (&:where(.dark, .dark *));` declaration (`index.css:6`) untouched. Seven installed shadcn primitives (`button.tsx`, `badge.tsx`, `input.tsx`, `checkbox.tsx`, `toggle.tsx`, `textarea.tsx`, `input-group.tsx`) use Tailwind's `dark:` variant internally and must keep resolving correctly.
- `--destructive` stays red, unchanged (error/invalid states, unrelated to brand accent).

### Color-scheme meta tag (`frontend/index.html`)

Add `<meta name="color-scheme" content="dark">` so native controls (date pickers, scrollbars, form-control chrome) render correctly against the forced-dark theme.

### Position color consistency

New file `frontend/src/lib/positionColors.ts` exports a single `POSITION_COLORS` map keyed by position code (`C`, `L`, `R`, `D`, `G`), holding the color identity per position (currently duplicated ad hoc as `POSITION_CLASSES` inside `PositionToggle.tsx:5-11`).

- `PositionToggle.tsx` imports `POSITION_COLORS` instead of defining its own local map; interactive toggle classes (text + `aria-pressed` background) derive from it.
- `PlayerTable.tsx:113-114` imports the same map and applies the matching color to the position `Badge` (replacing the current neutral `variant="outline"`), so a user who's learned the toggle's color language sees it carried through in the table.

## Testing

Pure CSS/token changes (theme retint, dead-code removal, meta tag) have no meaningful unit test — verified visually: run the dev server, browser-snapshot Home/Players/Teams/a Team page/Top Players, confirm the ice-blue accent renders consistently and no visual regression versus the current audit screenshots.

The position-color fix gets one test in `PlayerTable`'s existing test file: rendering a row for each position code (`C`, `L`, `R`, `D`, `G`) produces a `Badge` carrying the class/color defined in `POSITION_COLORS` for that code — asserts the shared map is actually wired in, not just present.

## Files touched

- `frontend/src/index.css` — retint, delete light block, delete `.dark` block
- `frontend/index.html` — add `color-scheme` meta tag
- `frontend/src/lib/positionColors.ts` — new, shared color map
- `frontend/src/components/PositionToggle.tsx` — consume shared map
- `frontend/src/components/PlayerTable.tsx` — consume shared map, colored position badge
