# URL Filter State — Design

**Date:** 2026-08-19
**Status:** Approved
**Scope:** Group 3c of 3 sub-projects under Group 3 ("Data Table & Layout") from the [NHL Stats UI/UX audit](../../../.wolf/memory.md) — must-fix item #8 (filters/sort/season not reflected in URL).

## Problem

`Players.tsx` keeps all filter/sort/season state in local `useState` (`filters`, `seasons`, `sortKey`, `sortDir`). A page refresh loses the current filtered/sorted view entirely, and there is no way to share a link to "Oilers centers sorted by points" — the exact kind of view a stats-browsing tool exists to let people share.

## Goals

- Refreshing the Players page preserves the current filters/sort/season.
- A URL copied and shared reproduces the same filtered/sorted view for whoever opens it.
- Malformed or hand-edited query params degrade to sane defaults, never to a broken/blank table.

## Anti-goals

- Not adding URL state to any page besides Players — Teams/TopPlayers/TeamPage have no comparable filter UI today.
- Not changing the Toolbar/StatFilters/SeasonPicker/PositionToggle/TeamPicker components' own internal behavior — they keep calling the same `onChange` callbacks they always have; only what's upstream of those callbacks (state storage) changes.
- Not adding debouncing to search or stat-min inputs — out of scope for this fix; addressed by choosing `replace` over `push` for URL updates instead (see Design).

## Design

### Pure encode/decode module (`frontend/src/lib/urlFilters.ts`)

No React, no `useSearchParams` — just data transformation, so it's directly unit-testable.

```ts
export const DEFAULT_FILTERS: ToolbarFilters = {
  search: "",
  team: "",
  positions: new Set(),
  statMins: { gp: null, goals: null, assists: null, points: null },
};
export const DEFAULT_SEASONS = ["20252026"];
export const DEFAULT_SORT_KEY = "points";
export const DEFAULT_SORT_DIR: SortDirection = "desc";

export function parseFiltersFromParams(params: URLSearchParams): {
  filters: ToolbarFilters;
  seasons: string[];
  sortKey: string;
  sortDir: SortDirection;
};

export function filtersToParams(
  filters: ToolbarFilters,
  seasons: string[],
  sortKey: string,
  sortDir: SortDirection
): URLSearchParams;
```

**Decode rules** (`parseFiltersFromParams`):
- `search` — `params.get("search") ?? ""`.
- `team` — `params.get("team") ?? ""`.
- `positions` — `params.get("positions")?.split(",").filter(Boolean) ?? []`, wrapped in a `Set`. Unknown codes are harmless (the position filter is a set-membership check against `PlayerStats.position_code`, which just never matches — no crash).
- `gp` / `goals` / `assists` / `points` — read the corresponding param; if present, `Number(raw)`; **if that's `NaN`, treat as `null`, not `NaN`.** This guard matters: `PlayerStats` fields are compared with `>=` (`Players.tsx:95-98`), and `p.gp >= NaN` is always `false` — an unguarded `NaN` from a hand-edited URL (`?gp=abc`) would silently filter out every player with no error shown, not just fail to apply the filter.
- `seasons` — `params.get("seasons")?.split(",").filter(Boolean)`, falling back to `DEFAULT_SEASONS` if absent or empty after filtering.
- `sortKey` — `params.get("sort") ?? DEFAULT_SORT_KEY`.
- `sortDir` — `params.get("dir")`, validated as exactly `"asc"` or `"desc"`; anything else (missing, garbage) falls back to `DEFAULT_SORT_DIR`.

**Encode rules** (`filtersToParams`) — the inverse, one rule per field: write the param only if the value differs from its default; write nothing for a field at its default. Empty result (`new URLSearchParams()`) when every field is at its default — the clean-URL case.

**Determinism note (caught during spec self-review):** `positions` is a `Set` (no guaranteed iteration order) and `seasons`' array order reflects click order, not a canonical order — neither would serialize to a stable URL string as-is, meaning the identical filter state could produce two different URLs depending on interaction history. Both get sorted before joining (`Array.from(positions).sort().join(",")`, `[...seasons].sort().join(",")`), mirroring the existing `seasonsKey` helper already in `Players.tsx:16-18`, which sorts for exactly this reason (a stable stats-cache key). Sorting `seasons` for the URL doesn't affect the `"all"` sentinel's semantics — `parseFiltersFromParams` reconstructs the array from the sorted string, and `.includes("all")` checks are order-independent.

### Hook (`frontend/src/lib/useUrlFilters.ts`)

```ts
export function useUrlFilters(): {
  filters: ToolbarFilters;
  seasons: string[];
  sortKey: string;
  sortDir: SortDirection;
  setFilters: (next: ToolbarFilters) => void;
  setSeasons: (next: string[]) => void;
  setSort: (key: string, dir: SortDirection) => void;
};
```

Thin wrapper around react-router-dom's `useSearchParams()` (already in use elsewhere in the app). Reads via `parseFiltersFromParams(searchParams)` on every render (cheap — a handful of `.get()` calls). Every setter computes the full next state, serializes via `filtersToParams`, and calls `setSearchParams(nextParams, { replace: true })`.

**`replace`, not `push`:** `Toolbar.tsx`'s search input and `StatFilters.tsx`'s numeric inputs both fire `onChange` on every keystroke with no debounce today. `push` would add one browser-history entry per keystroke — typing "McDavid" would spam 8 entries, and the back button would become a keystroke-undo instead of leaving the page. `replace` keeps the URL's role scoped to "current shareable/refreshable view," not an undo stack — this was confirmed as the desired UX during design.

### `Players.tsx` changes

Replace the 4 `useState` declarations (`filters`, `seasons`, `sortKey`, `sortDir`) with one call:
```ts
const { filters, seasons, sortKey, sortDir, setFilters, setSeasons, setSort } = useUrlFilters();
```

`handleSort` keeps its toggle logic (same key clicked → flip direction; different key → that key, `desc`) but calls `setSort` instead of two local setters:
```ts
function handleSort(key: string) {
  if (sortKey === key) {
    setSort(key, sortDir === "asc" ? "desc" : "asc");
  } else {
    setSort(key, "desc");
  }
}
```

`handleSelectSuggestion`'s filter-reset (currently a locally duplicated literal matching `Players.tsx`'s old initial state) becomes `setFilters(DEFAULT_FILTERS)`, imported from `urlFilters.ts` — single source of truth instead of two copies of the same shape that could drift.

Everything downstream of `filters`/`seasons`/`sortKey`/`sortDir` (the `rows` `useMemo`, the `Toolbar` props, `PlayerTable` props) is unchanged — they read the same variable names with the same types, just sourced from the hook instead of `useState`.

## Testing

- **`urlFilters.test.ts`** (new, no rendering — pure function tests): round-trip a filter set through `filtersToParams` → `parseFiltersFromParams` and confirm equality; confirm an empty/default filter set serializes to zero params; confirm `?gp=abc` decodes to `null` not `NaN`; confirm `?dir=sideways` decodes to `DEFAULT_SORT_DIR`; confirm `?positions=C,D` decodes to `new Set(["C","D"])`.
- **`Players.test.tsx`** (existing file, new tests): render with `initialEntries={["/players?team=EDM&sort=goals&dir=asc"]}` and assert the table reflects that state without any interaction (proves read-from-URL on load). Render at the default `/players`, interact with a filter (e.g. click a position toggle), and assert the resulting URL contains the new param — via a small test wrapper that also renders `useLocation().search` so the test can assert on it directly, rather than reaching into router internals.

## Files touched

- `frontend/src/lib/urlFilters.ts` — new, pure encode/decode
- `frontend/src/lib/urlFilters.test.ts` — new
- `frontend/src/lib/useUrlFilters.ts` — new, the hook
- `frontend/src/pages/Players.tsx` — swap local state for the hook
- `frontend/src/pages/Players.test.tsx` — new tests
