# Responsive Clipping Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop two layouts from clipping their content — the Teams grid cuts off long team names instead of wrapping, and PlayerProfilePanel's 4 fixed-column stat grids clip cell content on narrow (mobile) viewports.

**Architecture:** Pure CSS/Tailwind class changes, no new components, no logic changes. Teams gets one `min-w-0` addition; PlayerProfilePanel gets responsive column-count breakpoints on its 4 existing grids.

**Tech Stack:** React 19, Vite 8, TypeScript, Tailwind CSS 4.

## Global Constraints

- Do not change the Teams grid's existing column-count breakpoints (`grid-cols-2 sm:grid-cols-4 lg:grid-cols-6`) — only add `min-w-0` to the grid item.
- Do not change PlayerProfilePanel's dialog width classes (`max-w-[calc(100%-2rem)] sm:max-w-lg`) — only the 4 grids' column counts inside it.
- No new unit tests — jsdom doesn't evaluate CSS media queries or compute real layout, so a className-presence assertion wouldn't verify the actual fix. Verification is visual (Task 3).

---

### Task 1: Teams grid — allow long names to wrap

**Files:**
- Modify: `frontend/src/pages/Teams.tsx:25`

**Interfaces:** None — no props or exports change.

- [ ] **Step 1: Make the change**

In `frontend/src/pages/Teams.tsx`, change line 25 from:
```tsx
            className="flex flex-col items-center gap-2 rounded-lg border border-border p-4 text-center transition-colors hover:bg-muted"
```
to:
```tsx
            className="flex min-w-0 flex-col items-center gap-2 rounded-lg border border-border p-4 text-center transition-colors hover:bg-muted"
```

- [ ] **Step 2: Run the existing test file to confirm no regressions**

Run: `cd frontend && npx vitest run src/pages/Teams.test.tsx`
Expected: PASS — both existing tests (link rendering, UNK filtering unaffected by a layout-only class change).

- [ ] **Step 3: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/pages/Teams.tsx
git commit -m "Let long team names wrap instead of clipping

The grid item (Link) had no min-w-0, so its default min-width: auto
let long names ('Boston Bruins') overflow the card edge instead of
wrapping at ~480-750px viewport width."
```

---

### Task 2: PlayerProfilePanel — responsive stat grid columns

**Files:**
- Modify: `frontend/src/components/PlayerProfilePanel.tsx:342,352,387,404`

**Interfaces:** None — no props or exports change; `StatCell`, `PercentileBox`, `ZScoreBox`, `SelectableStatBox` are unchanged (verified during grilling: none of them have internal `whitespace-nowrap` or fixed widths that would block a column-count fix from working).

- [ ] **Step 1: Goalie stats grid**

In `frontend/src/components/PlayerProfilePanel.tsx`, change line 342 from:
```tsx
            <div className="grid grid-cols-4 gap-2 text-center text-sm">
```
to:
```tsx
            <div className="grid grid-cols-3 gap-2 text-center text-sm sm:grid-cols-4">
```

- [ ] **Step 2: Skater stats grid**

Change line 352 from:
```tsx
            <div className="grid grid-cols-6 gap-2 text-center text-sm">
```
to:
```tsx
            <div className="grid grid-cols-3 gap-2 text-center text-sm sm:grid-cols-6">
```

- [ ] **Step 3: Percentile boxes grid**

Change line 387 from:
```tsx
                <div className="grid grid-cols-5 gap-2">
```
to:
```tsx
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
```

- [ ] **Step 4: Z-score boxes grid**

Change line 404 from:
```tsx
                <div className="grid grid-cols-3 gap-2">
```
to:
```tsx
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
```
(This grid gets `grid-cols-1`, not a partial reduction like the others — its labels are long enough, e.g. "Rebounds Created/60", that even 2 columns leaves too little margin at mobile width to reliably avoid clipping, confirmed during grilling.)

- [ ] **Step 5: Run the existing test file to confirm no regressions**

Run: `cd frontend && npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: PASS — all existing tests (stat values rendering, tooltip behavior) unaffected by layout-only class changes.

- [ ] **Step 6: Run the full suite and build to check for regressions**

Run: `cd frontend && npm test && npm run build`
Expected: all tests pass (same count as before this task — no tests added or removed in this plan), build succeeds.

- [ ] **Step 7: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/components/PlayerProfilePanel.tsx
git commit -m "Add responsive column counts to PlayerProfilePanel stat grids

All 4 stat grids (goalie-4, skater-6, percentile-5, z-score-3) were
fixed-column with no breakpoints. The dialog is only
max-w-[calc(100%-2rem)] below the sm (640px) breakpoint (~311px
content width) -- confirmed live clipping 'PIM', 'Primary Pts', and
'Rebounds...' at that width. Reduce columns below sm, restore the
full count at sm and above."
```

---

### Task 3: Visual acceptance check

**Files:** none modified — verification only.

- [ ] **Step 1: Start the dev server and backend**

Run: `cd frontend && npm run dev` (background)
Run: `cd "/Users/paulmckay/Desktop/NHL Stats Project" && .venv/bin/python app.py` (background)

- [ ] **Step 2: Capture the Teams grid via openwolf designqc**

Run: `openwolf designqc --url http://localhost:5173 --routes /teams`
(No `--desktop-only` this time — the mobile capture, confirmed at 375x812px during grilling, is what actually exercises the wrapping fix.)

- [ ] **Step 3: Review the Teams captures**

Read the screenshots from `.wolf/designqc-captures/`. Confirm: at the mobile (375px) capture, long team names ("Boston Bruins", "Chicago Blackhawks", "Toronto Maple Leafs", etc.) wrap onto a second line instead of being cut off.

- [ ] **Step 4: Open the profile dialog via playwright at a narrow viewport**

`designqc` can't reach the profile dialog (no route opens it directly — that's audit finding #8, addressed in a later sub-project). Use the `playwright` MCP tools directly:
1. Resize the browser to 375x812.
2. Navigate to `http://localhost:5173/players`.
3. Click a skater row (e.g. Connor McDavid) to open the profile dialog.
4. Screenshot the dialog — confirm the skater stat grid (6 cells: GP/G/A/P/+-/PIM) shows all 6 labels fully, no cut-off text.
5. Close the dialog, click a goalie row.
6. Screenshot the dialog — confirm the goalie stat grid (7 cells) shows all labels fully.
7. If a skater's advanced-stats panel loaded (percentile/z-score grids), confirm those also show full labels with no clipping.

- [ ] **Step 5: Stop the dev server and backend**

Run: `pkill -f "vite"` and `pkill -f "app.py"`

No commit for this task — verification-only checkpoint.
