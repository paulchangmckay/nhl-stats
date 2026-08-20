# PlayerTable Virtualization — Design

**Date:** 2026-08-20
**Status:** Approved
**Scope:** Group 3b of 3 sub-projects under Group 3 ("Data Table & Layout") from the [NHL Stats UI/UX audit](../../../.wolf/memory.md) — must-fix item #5, the final and highest-risk sub-project in the audit.

## Problem

`PlayerTable.tsx` renders every row in `rows` unconditionally into the DOM — up to ~1038 rows × up to 18 columns for the unfiltered season, ~15,000+ live cells, re-filtered and re-rendered on every keystroke in the search box (`Players.tsx`'s `rows` `useMemo`). This is the single largest perceived-performance problem identified in the original audit.

## Goals

- Only rows within (and just outside) the visible scroll window are mounted in the DOM at any time.
- No visual or behavioral regression: sorting, position badges, click-to-open-profile, empty state, and the sticky header all keep working exactly as today.
- The existing "click a search suggestion → scroll to and highlight that row" feature keeps working, even though the target row usually won't be mounted yet.

## Anti-goals

- No column/horizontal virtualization — the audit's finding is specifically about row count (~15,000 cells = rows × columns), not horizontal scroll performance. Out of scope.
- No row-count threshold that conditionally skips virtualization for small filtered result sets — a single code path (always virtualized) is simpler than a conditional one, and `@tanstack/react-virtual`'s overhead is negligible even for a handful of rows.
- Not touching `PlayerProfilePanel`, `Leaderboard`, or any other table/list in the app — scoped to `PlayerTable.tsx` and the one caller (`Players.tsx`) that depends on its scroll-to-row behavior.

## Design

### Library

`@tanstack/react-virtual@3.14.10` — confirmed via `npm view` to support React 19 (`peerDependencies.react: "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0"`). The only new dependency this plan introduces.

### Row height

Fixed at **38px** — measured live against the running app (`getBoundingClientRect().height` on 10 sampled rows, all identical at 37.59375px). Every cell is `whitespace-nowrap` (`ui/table.tsx`'s `TableCell`), so rows are always exactly one line tall — no dynamic measurement (`measureElement`) is needed, only the simpler fixed-size `estimateSize: () => 38` path.

### `PlayerTable.tsx` — internal virtualization

- The scroll container ref moves *into* `PlayerTable` (currently, `Players.tsx` owns the `<div data-testid="table-wrap" className="overflow-auto" style={{ height: ... }}>` wrapper around `<PlayerTable>`; that wrapper's ref becomes the `getScrollElement` target for `useVirtualizer`, passed down or established locally — exact prop/ref shape is a plan-level detail, not re-litigated here since it doesn't change the component's external contract).
- `useVirtualizer({ count: rows.length, getScrollElement, estimateSize: () => 38, overscan: 10 })`.
- `TableBody` renders only `virtualizer.getVirtualItems()` — each item's corresponding `<TableRow>` gets `style={{ transform: `translateY(${virtualItem.start - virtualItem.index * virtualItem.size}px)` }}` (the library's documented table pattern: rows stay in normal table flow, positioned via `translateY`, not `position: absolute` — verified against `@tanstack/react-virtual`'s official table example, since `position: absolute` would conflict with the existing `sticky` header's layout assumptions).
- A spacer row (or equivalent) establishes `virtualizer.getTotalSize()` as the table's true scrollable height, so the scrollbar reflects the full row count, not just the mounted subset.
- `TableHeader`'s existing `className="sticky top-0 bg-card"` is untouched — `position: sticky` is purely a function of the nearest scrolling ancestor and doesn't depend on sibling row count, so virtualizing `tbody`'s rows doesn't affect it. Verified as a real (not hypothetical) risk during design research — known GitHub issues exist for sticky headers breaking under table virtualization, specifically in setups combining a *separate* header-rendering library (TanStack Table) with the virtualizer; this app's plain, hand-rendered `<TableHeader>` doesn't have that specific failure mode, but it's still called out explicitly for the manual verification pass to actually check, not assumed safe.

### Scroll-to-row fix (`PlayerTable` exposes an imperative handle)

`PlayerTable` becomes `forwardRef`, exposing one method via `useImperativeHandle`:

```ts
export interface PlayerTableHandle {
  scrollToPlayer(playerId: number): void;
}
```

`scrollToPlayer` internally: finds the player's index in the current `rows` prop, calls `virtualizer.scrollToIndex(index, { align: "center", behavior: "auto" })` (`behavior: "auto"` — an instant jump, not `"smooth"` — so the target row mounts as soon as the resulting re-render commits, rather than only mounting once a scroll animation reaches it), then — inside its own `requestAnimationFrame` (waiting for that re-render to commit and paint) — queries `[data-player-id="${playerId}"]` *within its own container* and applies the existing highlight behavior (`classList.add("row-highlight")`, timed removal). All DOM-querying and highlight logic that today lives in `Players.tsx`'s `handleSelectSuggestion` moves into this method — `PlayerTable` owns its own DOM structure and how to visually locate a row within it; `Players.tsx` shouldn't need to know virtualization exists at all.

This branch is based on `main`, which does not yet include the URL-filter-state sub-project's `DEFAULT_FILTERS` (that work is on a separate, unmerged branch — PR #138). `Players.tsx`'s `handleSelectSuggestion` on `main` today resets filters via a local object literal, not a shared constant. This design touches only the scroll/highlight half of that function, leaving the filter-reset literal exactly as-is:

```tsx
function handleSelectSuggestion(player: Player) {
  setFilters({
    search: "",
    team: "",
    positions: new Set(),
    statMins: { gp: null, goals: null, assists: null, points: null },
  });
  requestAnimationFrame(() => {
    tableRef.current?.scrollToPlayer(player.player_id);
  });
}
```
The outer `requestAnimationFrame` here waits for the *filter reset* to commit (so `PlayerTable`'s `rows` prop reflects the unfiltered list before `scrollToPlayer` computes an index against it) — a separate concern from `scrollToPlayer`'s own internal rAF, which waits for the *scroll-triggered mount* to commit. Two renders, two waits, correctly sequenced rather than collapsed into one.

### Testing

**Unit tests (`PlayerTable.test.tsx`):** `vi.mock("@tanstack/react-virtual")` with a stub `useVirtualizer` that reports every row as visible (`getVirtualItems()` returns one item per row, `getTotalSize()` returns `rows.length * 38`). Every existing test (rendering, sorting, position badges, empty state, click-to-open-profile, keyboard nav) keeps working completely unchanged — they're testing table *behavior*, not virtualization, and the mock makes virtualization transparent to them. New tests specific to the imperative handle: `scrollToPlayer` calls the mocked `virtualizer.scrollToIndex` with the correct computed index.

**Manual/visual verification (via `playwright` against the real app, matching the pattern established in Groups 3a/3c):**
- DOM node count with the full 1038-row unfiltered table stays low (well under the ~15,000 cells today) regardless of scroll position.
- Scrolling the table renders new rows and un-mounts old ones (spot-check via DOM query at different scroll positions).
- The sticky header stays stuck while scrolling (the real risk called out above — not assumed safe, actually checked).
- Search-suggestion click still scrolls to and highlights the target row, including for a player far outside the current viewport (the actual regression case virtualization introduces).
- Visual comparison against the pre-virtualization table — no layout shift, no flicker, row heights/spacing unchanged.

## Files touched

- `frontend/package.json` — add `@tanstack/react-virtual`
- `frontend/src/components/PlayerTable.tsx` — virtualization, `forwardRef` + imperative handle
- `frontend/src/components/PlayerTable.test.tsx` — mock virtualizer, new handle tests
- `frontend/src/pages/Players.tsx` — `handleSelectSuggestion` simplified to use the ref
