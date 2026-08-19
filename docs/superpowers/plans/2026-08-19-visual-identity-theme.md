# Visual Identity & Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the app's stock zero-chroma shadcn theme with a deliberate ice-blue identity, delete dead theme code (hardcoded dark mode's unreachable light block, unused chart/sidebar tokens), and make position color-coding consistent between `PositionToggle` and `PlayerTable`.

**Architecture:** Single-theme CSS custom-property rewrite in `index.css` (no new abstraction layer — `:root` becomes the one source of truth for all color tokens, since dark is the only theme). Position color-coding gets one new shared module (`positionColors.ts`) consumed by both components that currently duplicate/diverge on it.

**Tech Stack:** React 19, Vite 8, Tailwind CSS 4 (`@theme inline` token pipeline), Vitest + Testing Library.

## Global Constraints

- All frontend work happens under `frontend/` (the Vite project root) — commands below assume `cd frontend` first.
- OKLCH color values are locked from the spec — do not substitute different values at implementation time (see spec section "Theme tokens").
- `class="dark"` on `<html>` and `@custom-variant dark (&:where(.dark, .dark *));` in `index.css:6` stay untouched — 7 installed shadcn primitives depend on the `dark:` Tailwind variant resolving via that class.
- Tailwind class strings in `positionColors.ts` must always be complete literals — never built by string concatenation/interpolation at runtime, or Tailwind's JIT scanner silently drops them from the production build.
- `--destructive` (`oklch(0.704 0.191 22.216)`) is unchanged — unrelated to this identity work.

---

### Task 1: Retint theme tokens and remove dead CSS

**Files:**
- Modify: `frontend/src/index.css:1-75` (full `:root` and `.dark` blocks)
- Modify: `frontend/index.html:2`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: retinted `--background`, `--foreground`, `--card`, `--card-foreground`, `--primary`, `--primary-foreground`, `--border`, `--popover`, `--popover-foreground`, `--secondary`, `--secondary-foreground`, `--muted`, `--muted-foreground`, `--accent`, `--accent-foreground`, `--input`, `--ring` tokens in `:root`, consumed by every component that uses Tailwind's `bg-background`, `text-primary`, etc. utility classes (no code changes needed in consuming components — they already reference these token names).

This task is CSS-only with no behavioral assertion to red/green — see spec section "Testing" for why (a string-match on OKLCH literals breaks on any future nudge without catching a real regression). Verification here is: the existing test suite still passes (nothing about component logic changes) and `npm run build` succeeds (catches any CSS/HTML syntax error introduced by the edit). Visual acceptance (ice-blue renders correctly, contrast holds) happens after Task 2, once both CSS and position-color changes are in, via `openwolf designqc`.

- [ ] **Step 1: Replace `frontend/src/index.css` lines 1-75 with the retinted single-theme block**

Replace the entire current content from line 1 (`@import "tailwindcss";`) through line 75 (the closing `}` of the `.dark` block) with:

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";
@import "@fontsource-variable/geist";

@custom-variant dark (&:where(.dark, .dark *));

:root {
  --radius: 0.625rem;
  --background: oklch(0.16 0.02 240);
  --foreground: oklch(0.97 0.01 235);
  --card: oklch(0.21 0.02 240);
  --card-foreground: oklch(0.97 0.01 235);
  --primary: oklch(0.75 0.13 230);
  --primary-foreground: oklch(0.18 0.03 240);
  --border: oklch(1 0 0 / 10%);
  --popover: oklch(0.21 0.02 240);
  --popover-foreground: oklch(0.97 0.01 235);
  --secondary: oklch(0.27 0.02 240);
  --secondary-foreground: oklch(0.97 0.01 235);
  --muted: oklch(0.27 0.02 240);
  --muted-foreground: oklch(0.70 0.02 235);
  --accent: oklch(0.27 0.02 240);
  --accent-foreground: oklch(0.97 0.01 235);
  --destructive: oklch(0.704 0.191 22.216);
  --input: oklch(1 0 0 / 15%);
  --ring: oklch(0.70 0.12 230);
}
```

This removes: the old zero-chroma light-mode `:root` block (dead — `class="dark"` is hardcoded, it could never render), the separate `.dark { ... }` override block (folded into `:root` since there's only one theme now), and the unused `--chart-1` through `--chart-5` and `--sidebar*` tokens (confirmed zero usage anywhere in `src/` during grilling).

- [ ] **Step 2: Add the color-scheme meta tag to `frontend/index.html`**

Change line 2 from:
```html
<html lang="en" class="dark">
```
to (unchanged — `class="dark"` stays):
```html
<html lang="en" class="dark">
```

Add a new line after line 5 (`<meta name="viewport" ...>`), before line 6 (`<title>`):

```html
    <meta name="color-scheme" content="dark" />
```

Full resulting `<head>`:
```html
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="color-scheme" content="dark" />
    <title>NHL Players</title>
  </head>
```

- [ ] **Step 3: Verify the build succeeds**

Run: `cd frontend && npm run build`
Expected: exits 0, no TypeScript or CSS errors. This is the correctness gate for a CSS-only change — a broken token reference or invalid OKLCH syntax fails the build.

- [ ] **Step 4: Verify the existing test suite still passes**

Run: `cd frontend && npm test`
Expected: all existing tests pass unchanged — this task touches no component logic, only CSS tokens and a static HTML meta tag.

- [ ] **Step 5: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/index.css frontend/index.html
git commit -m "Retint theme to ice-blue identity, delete dead CSS

Removes the unreachable light-mode :root block (class=\"dark\" is
hardcoded, it never rendered), folds the now-redundant .dark override
into :root, and deletes --chart-1..5/--sidebar* (zero usage anywhere
in src/). Adds color-scheme meta tag so native controls match the
forced-dark theme."
```

---

### Task 2: Shared position color map + consistent badge colors

**Files:**
- Create: `frontend/src/lib/positionColors.ts`
- Modify: `frontend/src/components/PositionToggle.tsx:1-11`
- Modify: `frontend/src/components/PlayerTable.tsx:113-114`
- Modify: `frontend/src/components/PositionToggle.test.tsx`
- Modify: `frontend/src/components/PlayerTable.test.tsx`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `POSITION_COLORS: Record<"C" | "L" | "R" | "D" | "G", { toggleClass: string; badgeClass: string }>`, exported from `frontend/src/lib/positionColors.ts` — the canonical position-color source, importable by any future component that needs to render a position with brand-consistent color.

- [ ] **Step 1: Write the failing test for `PlayerTable`'s position badge color**

Add to `frontend/src/components/PlayerTable.test.tsx`, inside the existing `describe("PlayerTable", ...)` block (after the last existing `it(...)`):

```tsx
  it("colors the position badge to match POSITION_COLORS for every position code", () => {
    const rows: PlayerStats[] = (["C", "L", "R", "D", "G"] as const).map((position_code, i) => ({
      ...MOCK_STATS[0],
      player_id: 100 + i,
      last_name: `Test${position_code}`,
      position_code,
    }));
    render(<PlayerTable rows={rows} sortKey="points" sortDir="desc" onSort={() => {}} />);
    rows.forEach((row) => {
      // Scoped to the row, not screen: the table has columns literally labeled
      // "G" (Goals) and "L" (Losses) — a page-wide getByText("G"/"L") would
      // match both the column header and the badge and throw on ambiguity.
      const tableRow = document.querySelector(`[data-player-id="${row.player_id}"]`) as HTMLElement;
      const badge = within(tableRow).getByText(row.position_code);
      const expectedClasses = POSITION_COLORS[row.position_code as keyof typeof POSITION_COLORS].badgeClass.split(" ");
      expectedClasses.forEach((cls) => expect(badge).toHaveClass(cls));
    });
  });
```

Add the required imports at the top of the file: change the existing `import { render, screen } from "@testing-library/react";` to also pull in `within`, and add the two new imports below the existing `MOCK_STATS` import:

```tsx
import { render, screen, within } from "@testing-library/react";
```

```tsx
import type { PlayerStats } from "@/lib/types";
import { POSITION_COLORS } from "@/lib/positionColors";
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/PlayerTable.test.tsx`
Expected: FAIL — `Cannot find module '@/lib/positionColors'` (the module doesn't exist yet).

- [ ] **Step 3: Write the failing test for `PositionToggle`'s per-position toggle color**

Add to `frontend/src/components/PositionToggle.test.tsx`, inside the existing `describe("PositionToggle", ...)` block:

```tsx
  it("applies the POSITION_COLORS toggleClass to each position button", () => {
    render(<PositionToggle active={new Set()} onChange={() => {}} />);
    (["C", "L", "R", "D", "G"] as const).forEach((pos) => {
      const button = screen.getByRole("button", { name: pos });
      const expectedClasses = POSITION_COLORS[pos].toggleClass.split(" ");
      expectedClasses.forEach((cls) => expect(button).toHaveClass(cls));
    });
  });
```

Add the import at the top of the file:
```tsx
import { POSITION_COLORS } from "@/lib/positionColors";
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/PositionToggle.test.tsx`
Expected: FAIL — `Cannot find module '@/lib/positionColors'`.

- [ ] **Step 5: Create `frontend/src/lib/positionColors.ts`**

```ts
export const POSITION_COLORS: Record<
  "C" | "L" | "R" | "D" | "G",
  { toggleClass: string; badgeClass: string }
> = {
  C: {
    toggleClass: "text-green-500 aria-pressed:bg-green-500 aria-pressed:text-background",
    badgeClass: "border-green-500/40 bg-green-500/10 text-green-500",
  },
  L: {
    toggleClass: "text-blue-400 aria-pressed:bg-blue-400 aria-pressed:text-background",
    badgeClass: "border-blue-400/40 bg-blue-400/10 text-blue-400",
  },
  R: {
    toggleClass: "text-sky-300 aria-pressed:bg-sky-300 aria-pressed:text-background",
    badgeClass: "border-sky-300/40 bg-sky-300/10 text-sky-300",
  },
  D: {
    toggleClass: "text-purple-300 aria-pressed:bg-purple-300 aria-pressed:text-background",
    badgeClass: "border-purple-300/40 bg-purple-300/10 text-purple-300",
  },
  G: {
    toggleClass: "text-orange-400 aria-pressed:bg-orange-400 aria-pressed:text-background",
    badgeClass: "border-orange-400/40 bg-orange-400/10 text-orange-400",
  },
};
```

- [ ] **Step 6: Wire `PositionToggle.tsx` to consume the shared map**

Replace `frontend/src/components/PositionToggle.tsx` lines 1-11:

```tsx
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

const POSITIONS = ["C", "L", "R", "D", "G"] as const;

const POSITION_CLASSES: Record<(typeof POSITIONS)[number], string> = {
  C: "text-green-500 aria-pressed:bg-green-500 aria-pressed:text-background",
  L: "text-blue-400 aria-pressed:bg-blue-400 aria-pressed:text-background",
  R: "text-sky-300 aria-pressed:bg-sky-300 aria-pressed:text-background",
  D: "text-purple-300 aria-pressed:bg-purple-300 aria-pressed:text-background",
  G: "text-orange-400 aria-pressed:bg-orange-400 aria-pressed:text-background",
};
```

with:

```tsx
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { POSITION_COLORS } from "@/lib/positionColors";

const POSITIONS = ["C", "L", "R", "D", "G"] as const;
```

Then update the `className` prop on `ToggleGroupItem` (currently `className={POSITION_CLASSES[pos]}`) to:

```tsx
className={POSITION_COLORS[pos].toggleClass}
```

- [ ] **Step 7: Wire `PlayerTable.tsx` to consume the shared map**

Add the import near the top of `frontend/src/components/PlayerTable.tsx` (alongside the existing `Badge` import):

```tsx
import { POSITION_COLORS } from "@/lib/positionColors";
```

Replace line 114:
```tsx
                  <Badge variant="outline">{row.position_code}</Badge>
```
with:
```tsx
                  <Badge
                    variant="outline"
                    className={POSITION_COLORS[row.position_code as keyof typeof POSITION_COLORS].badgeClass}
                  >
                    {row.position_code}
                  </Badge>
```

- [ ] **Step 8: Run both tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/PlayerTable.test.tsx src/components/PositionToggle.test.tsx`
Expected: PASS — all tests in both files, including the two new ones.

- [ ] **Step 9: Run the full test suite and build to check for regressions**

Run: `cd frontend && npm test && npm run build`
Expected: all tests pass, build succeeds.

- [ ] **Step 10: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/lib/positionColors.ts frontend/src/components/PositionToggle.tsx frontend/src/components/PlayerTable.tsx frontend/src/components/PositionToggle.test.tsx frontend/src/components/PlayerTable.test.tsx
git commit -m "Make position color-coding consistent across PositionToggle and PlayerTable

Extracts the position->color mapping PositionToggle already had into
a shared lib/positionColors.ts, and applies it to PlayerTable's
position badge (previously a plain neutral outline badge with no
color at all) so the color language a user learns from the toggle
carries through in the table."
```

---

### Task 3: Visual acceptance check

**Files:** none modified — verification only.

**Interfaces:**
- Consumes: the running app with Task 1 + Task 2 applied.
- Produces: confirmation the identity work is visually correct, closing out this plan.

- [ ] **Step 1: Start the dev server**

Run: `cd frontend && npm run dev` (background — leave running for the next step)

- [ ] **Step 2: Capture screenshots via openwolf designqc**

Run: `openwolf designqc` (per `.claude/rules/openwolf.md` — the project's standard UI-check tool)

- [ ] **Step 3: Review captures**

Read the screenshots from `.wolf/designqc-captures/`. Confirm:
- The ice-blue accent renders consistently across Home, Players, Teams, a Team detail page, and Top Players.
- Button/focus-ring text (white on `--primary`) is legibly readable — visually confirms the OKLCH lightness-gap contrast reasoning from the spec.
- The position badges in the Players table show color, matching the toggle's color language.
- No visual regression versus the audit's original screenshots (layout unchanged — this plan only touches color, not structure).

- [ ] **Step 4: Stop the dev server**

Run: `pkill -f "vite"` (or Ctrl-C the foreground process if run interactively)

No commit for this task — it's a verification-only checkpoint. If Step 3 surfaces an issue, fix it as a small follow-up commit on the same branch before moving to PR.
