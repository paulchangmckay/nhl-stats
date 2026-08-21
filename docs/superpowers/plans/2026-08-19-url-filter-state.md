# URL Filter State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Players.tsx's filter/sort/season state from local `useState` into the URL, so refreshing or sharing a link preserves the current view.

**Architecture:** A pure encode/decode module (`urlFilters.ts`, no React) backs a thin `useUrlFilters` hook wrapping react-router-dom's `useSearchParams`. `Players.tsx` swaps its 4 `useState` calls for one hook call; everything downstream is unchanged.

**Tech Stack:** React 19, TypeScript, react-router-dom 7.18.2 (already a dependency; confirmed via `frontend/src/main.tsx` — plain `<BrowserRouter>`, no data-router loaders), Vitest + Testing Library.

## Global Constraints

- URL updates use `{ replace: true }`, never `push` — `Toolbar.tsx`'s search input and `StatFilters.tsx`'s numeric inputs fire `onChange` on every keystroke with no debounce; `push` would spam browser history.
- Default values are omitted from the URL entirely — write a param only when it differs from its default.
- `gp`/`goals`/`assists`/`points` decode `NaN` (malformed input, e.g. `?gp=abc`) as `null`, never as `NaN` — an unguarded `NaN` makes `p.gp >= NaN` silently `false` for every row, hiding all results with no visible error.
- `positions` and `seasons` are sorted before joining into their URL param (`Array.from(positions).sort().join(",")`, `[...seasons].sort().join(",")`) — mirrors the existing `seasonsKey` helper in `Players.tsx:16-18`, which sorts for the same determinism reason (identical filter state must always produce the identical URL string).
- `sortDir` decodes to exactly `"asc"` or `"desc"`; any other value (missing, malformed) falls back to `"desc"`.

---

### Task 1: Pure encode/decode module

**Files:**
- Create: `frontend/src/lib/urlFilters.ts`
- Test: `frontend/src/lib/urlFilters.test.ts`

**Interfaces:**
- Consumes: `ToolbarFilters` from `@/components/Toolbar` (`{ search: string; team: string; positions: Set<string>; statMins: StatMins }`), `StatMins` and `SortDirection` from `@/lib/types`.
- Produces:
  - `DEFAULT_FILTERS: ToolbarFilters`
  - `DEFAULT_SEASONS: string[]`
  - `DEFAULT_SORT_KEY: string`
  - `DEFAULT_SORT_DIR: SortDirection`
  - `parseFiltersFromParams(params: URLSearchParams): { filters: ToolbarFilters; seasons: string[]; sortKey: string; sortDir: SortDirection }`
  - `filtersToParams(filters: ToolbarFilters, seasons: string[], sortKey: string, sortDir: SortDirection): URLSearchParams`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/urlFilters.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import {
  DEFAULT_FILTERS,
  DEFAULT_SEASONS,
  DEFAULT_SORT_KEY,
  DEFAULT_SORT_DIR,
  parseFiltersFromParams,
  filtersToParams,
} from "./urlFilters";

describe("filtersToParams", () => {
  it("produces an empty params string when everything is at its default", () => {
    const params = filtersToParams(DEFAULT_FILTERS, DEFAULT_SEASONS, DEFAULT_SORT_KEY, DEFAULT_SORT_DIR);
    expect(params.toString()).toBe("");
  });

  it("writes only the fields that differ from default", () => {
    const filters = { ...DEFAULT_FILTERS, team: "EDM" };
    const params = filtersToParams(filters, DEFAULT_SEASONS, "goals", "asc");
    expect(params.get("team")).toBe("EDM");
    expect(params.get("sort")).toBe("goals");
    expect(params.get("dir")).toBe("asc");
    expect(params.has("search")).toBe(false);
    expect(params.has("seasons")).toBe(false);
  });

  it("sorts positions before joining, regardless of Set insertion order", () => {
    const filtersA = { ...DEFAULT_FILTERS, positions: new Set(["R", "C", "D"]) };
    const filtersB = { ...DEFAULT_FILTERS, positions: new Set(["D", "R", "C"]) };
    const paramsA = filtersToParams(filtersA, DEFAULT_SEASONS, DEFAULT_SORT_KEY, DEFAULT_SORT_DIR);
    const paramsB = filtersToParams(filtersB, DEFAULT_SEASONS, DEFAULT_SORT_KEY, DEFAULT_SORT_DIR);
    expect(paramsA.get("positions")).toBe("C,D,R");
    expect(paramsB.get("positions")).toBe("C,D,R");
  });

  it("sorts seasons before joining", () => {
    const params = filtersToParams(DEFAULT_FILTERS, ["20232024", "20212022"], DEFAULT_SORT_KEY, DEFAULT_SORT_DIR);
    expect(params.get("seasons")).toBe("20212022,20232024");
  });
});

describe("parseFiltersFromParams", () => {
  it("returns all defaults for an empty params object", () => {
    const result = parseFiltersFromParams(new URLSearchParams());
    expect(result.filters).toEqual(DEFAULT_FILTERS);
    expect(result.seasons).toEqual(DEFAULT_SEASONS);
    expect(result.sortKey).toBe(DEFAULT_SORT_KEY);
    expect(result.sortDir).toBe(DEFAULT_SORT_DIR);
  });

  it("round-trips a non-default filter set through filtersToParams and back", () => {
    const filters = {
      search: "mcdavid",
      team: "EDM",
      positions: new Set(["C", "L"]),
      statMins: { gp: 10, goals: null, assists: 5, points: null },
    };
    const params = filtersToParams(filters, ["20232024", "20242025"], "goals", "asc");
    const result = parseFiltersFromParams(params);
    expect(result.filters).toEqual(filters);
    expect(result.seasons).toEqual(["20232024", "20242025"]);
    expect(result.sortKey).toBe("goals");
    expect(result.sortDir).toBe("asc");
  });

  it("decodes a malformed numeric stat-min param as null, not NaN", () => {
    const result = parseFiltersFromParams(new URLSearchParams("gp=abc"));
    expect(result.filters.statMins.gp).toBeNull();
  });

  it("decodes an invalid sort direction as the default", () => {
    const result = parseFiltersFromParams(new URLSearchParams("dir=sideways"));
    expect(result.sortDir).toBe("desc");
  });

  it("decodes an empty positions param as an empty set, not a set containing an empty string", () => {
    const result = parseFiltersFromParams(new URLSearchParams("positions="));
    expect(result.filters.positions).toEqual(new Set());
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/urlFilters.test.ts`
Expected: FAIL — `Cannot find module './urlFilters'` (the module doesn't exist yet).

- [ ] **Step 3: Write `frontend/src/lib/urlFilters.ts`**

```ts
import type { ToolbarFilters } from "@/components/Toolbar";
import type { SortDirection, StatMins } from "@/lib/types";

export const DEFAULT_FILTERS: ToolbarFilters = {
  search: "",
  team: "",
  positions: new Set(),
  statMins: { gp: null, goals: null, assists: null, points: null },
};
export const DEFAULT_SEASONS = ["20252026"];
export const DEFAULT_SORT_KEY = "points";
export const DEFAULT_SORT_DIR: SortDirection = "desc";

const STAT_MIN_KEYS: (keyof StatMins)[] = ["gp", "goals", "assists", "points"];

function parseStatMin(raw: string | null): number | null {
  if (raw === null) return null;
  const n = Number(raw);
  return Number.isNaN(n) ? null : n;
}

export function parseFiltersFromParams(params: URLSearchParams): {
  filters: ToolbarFilters;
  seasons: string[];
  sortKey: string;
  sortDir: SortDirection;
} {
  const positionsRaw = params.get("positions");
  const positions = new Set(
    positionsRaw ? positionsRaw.split(",").filter((s) => s.length > 0) : []
  );

  const statMins: StatMins = {
    gp: parseStatMin(params.get("gp")),
    goals: parseStatMin(params.get("goals")),
    assists: parseStatMin(params.get("assists")),
    points: parseStatMin(params.get("points")),
  };

  const seasonsRaw = params.get("seasons");
  const seasons = seasonsRaw
    ? seasonsRaw.split(",").filter((s) => s.length > 0)
    : DEFAULT_SEASONS;

  const dirRaw = params.get("dir");
  const sortDir: SortDirection = dirRaw === "asc" || dirRaw === "desc" ? dirRaw : DEFAULT_SORT_DIR;

  return {
    filters: {
      search: params.get("search") ?? "",
      team: params.get("team") ?? "",
      positions,
      statMins,
    },
    seasons: seasons.length > 0 ? seasons : DEFAULT_SEASONS,
    sortKey: params.get("sort") ?? DEFAULT_SORT_KEY,
    sortDir,
  };
}

export function filtersToParams(
  filters: ToolbarFilters,
  seasons: string[],
  sortKey: string,
  sortDir: SortDirection
): URLSearchParams {
  const params = new URLSearchParams();

  if (filters.search !== DEFAULT_FILTERS.search) params.set("search", filters.search);
  if (filters.team !== DEFAULT_FILTERS.team) params.set("team", filters.team);
  if (filters.positions.size > 0) {
    params.set("positions", Array.from(filters.positions).sort().join(","));
  }
  for (const key of STAT_MIN_KEYS) {
    const value = filters.statMins[key];
    if (value !== null) params.set(key, String(value));
  }

  const sortedSeasons = [...seasons].sort();
  const sortedDefaultSeasons = [...DEFAULT_SEASONS].sort();
  if (sortedSeasons.join(",") !== sortedDefaultSeasons.join(",")) {
    params.set("seasons", sortedSeasons.join(","));
  }

  if (sortKey !== DEFAULT_SORT_KEY) params.set("sort", sortKey);
  if (sortDir !== DEFAULT_SORT_DIR) params.set("dir", sortDir);

  return params;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/urlFilters.test.ts`
Expected: PASS — all 9 tests.

- [ ] **Step 5: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/lib/urlFilters.ts frontend/src/lib/urlFilters.test.ts
git commit -m "Add pure encode/decode for Players filter/sort/season URL state

No React -- just data transformation, so it's directly unit-testable.
Guards NaN from malformed numeric params (would otherwise silently
filter out every row via p.gp >= NaN), validates sortDir against its
two-value union, and sorts positions/seasons before joining so
identical filter state always produces the identical URL string."
```

---

### Task 2: `useUrlFilters` hook

**Files:**
- Create: `frontend/src/lib/useUrlFilters.ts`

**Interfaces:**
- Consumes: `parseFiltersFromParams`, `filtersToParams` from `./urlFilters` (Task 1). `useSearchParams` from `react-router-dom`.
- Produces: `useUrlFilters(): { filters: ToolbarFilters; seasons: string[]; sortKey: string; sortDir: SortDirection; setFilters: (next: ToolbarFilters) => void; setSeasons: (next: string[]) => void; setSort: (key: string, dir: SortDirection) => void }`

This hook has no independent unit test — it's a thin composition of two already-tested pieces (`urlFilters.ts`'s pure functions, and `react-router-dom`'s own tested `useSearchParams`). It's exercised indirectly through `Players.test.tsx` in Task 3, which is the actual integration point that matters.

- [ ] **Step 1: Write `frontend/src/lib/useUrlFilters.ts`**

```ts
import { useSearchParams } from "react-router-dom";
import type { ToolbarFilters } from "@/components/Toolbar";
import type { SortDirection } from "@/lib/types";
import { parseFiltersFromParams, filtersToParams } from "./urlFilters";

export function useUrlFilters() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { filters, seasons, sortKey, sortDir } = parseFiltersFromParams(searchParams);

  function setFilters(next: ToolbarFilters) {
    setSearchParams(filtersToParams(next, seasons, sortKey, sortDir), { replace: true });
  }

  function setSeasons(next: string[]) {
    setSearchParams(filtersToParams(filters, next, sortKey, sortDir), { replace: true });
  }

  function setSort(key: string, dir: SortDirection) {
    setSearchParams(filtersToParams(filters, seasons, key, dir), { replace: true });
  }

  return { filters, seasons, sortKey, sortDir, setFilters, setSeasons, setSort };
}
```

- [ ] **Step 2: Run the full suite to confirm no regressions**

Run: `cd frontend && npm test`
Expected: all existing tests still pass (this file isn't consumed anywhere yet — Task 3 wires it in).

- [ ] **Step 3: Run the build to confirm no type errors**

Run: `cd frontend && npm run build`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/lib/useUrlFilters.ts
git commit -m "Add useUrlFilters hook wrapping useSearchParams

Thin composition over urlFilters.ts's pure functions and
react-router-dom's useSearchParams. Every setter uses { replace:
true } -- Toolbar's search input and StatFilters' numeric inputs fire
onChange on every keystroke with no debounce, so push would spam one
history entry per keystroke."
```

---

### Task 3: Wire `Players.tsx` to the hook

**Files:**
- Modify: `frontend/src/pages/Players.tsx:1-41,118-141`
- Test: `frontend/src/pages/Players.test.tsx`

**Interfaces:**
- Consumes: `useUrlFilters` (Task 2), `DEFAULT_FILTERS` from `@/lib/urlFilters` (Task 1).
- Produces: no new exports — `Players` is a page component, its behavior (not its interface) is what's under test.

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/pages/Players.test.tsx`, inside the existing `describe("Players", ...)` block. First, add these imports at the top of the file (alongside the existing ones):

```tsx
import { useLocation } from "react-router-dom";
```

Add a small wrapper that exposes the current URL search string for assertions, and a variant of `renderPlayers` that accepts initial entries:

```tsx
function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
}

function renderPlayersAt(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Players />
      <LocationDisplay />
    </MemoryRouter>
  );
}
```

Then the new tests:

```tsx
  it("reads filters and sort from the URL on initial load", async () => {
    renderPlayersAt("/players?team=EDM&sort=goals&dir=asc");
    await screen.findByText("McDavid");
    // MOCK_STATS has 3 players: MacKinnon (COL), McDavid (EDM), Stolarz
    // (TOR). The team=EDM filter should narrow to McDavid only -- checking
    // that MacKinnon is absent proves the filter actually applied from the
    // URL, not just that the page rendered without crashing.
    expect(screen.queryByText("MacKinnon")).not.toBeInTheDocument();
  });

  it("writes a non-default filter to the URL and omits untouched defaults", async () => {
    renderPlayersAt("/players");
    await screen.findByText("MacKinnon");
    await userEvent.click(screen.getByRole("button", { name: "C" }));
    await waitFor(() => {
      expect(screen.getByTestId("location-search")).toHaveTextContent("positions=C");
    });
    expect(screen.getByTestId("location-search").textContent).not.toContain("search=");
  });

  it("resets filters via URL and still scrolls to/highlights the selected suggestion", async () => {
    renderPlayersAt("/players?team=EDM");
    await screen.findByText("McDavid");
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "McDavid");
    // The suggestion dropdown item renders "{first_name} {last_name}" as one
    // combined text node (Toolbar.tsx) -- distinct from the table cell's
    // last-name-only "McDavid" text, so this exact string is what
    // disambiguates the suggestion from the table row already on screen.
    const suggestion = await screen.findByText("Connor McDavid", { selector: "div" });
    await userEvent.click(suggestion);
    await waitFor(() => {
      expect(screen.getByTestId("location-search").textContent).not.toContain("team=");
    });
    const row = document.querySelector('[data-player-id="2"]');
    expect(row).toHaveClass("row-highlight");
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/Players.test.tsx`
Expected: FAIL — `Players.tsx` still uses local `useState`, so URL params are never read or written; the third test's suggestion-click flow won't find the expected post-reset state.

- [ ] **Step 3: Wire `Players.tsx`**

Replace `frontend/src/pages/Players.tsx` lines 1-9 (imports) with:

```tsx
import { useEffect, useMemo, useState } from "react";
import { Toolbar, type ToolbarFilters } from "@/components/Toolbar";
import { PlayerTable } from "@/components/PlayerTable";
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { matchesQuery } from "@/lib/search";
import { useUrlFilters } from "@/lib/useUrlFilters";
import { DEFAULT_FILTERS } from "@/lib/urlFilters";
import type { Team, Player, PlayerStats } from "@/lib/types";
```

(Removed the now-unused `SortDirection` type import — `sortDir`'s type is inferred from the hook.)

Replace lines 26-41 (the component's state declarations) with:

```tsx
export default function Players() {
  const [teamsState, setTeamsState] = useState<FetchState<Team[]>>({ status: "loading" });
  const [playersState, setPlayersState] = useState<FetchState<Player[]>>({ status: "loading" });
  const [statsCache, setStatsCache] = useState<Record<string, PlayerStats[]>>({});
  const [statsError, setStatsError] = useState<string | null>(null);

  const { filters, seasons, sortKey, sortDir, setFilters, setSeasons, setSort } = useUrlFilters();
  const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);
```

Replace the `handleSort` function (currently around line 118-125) with:

```tsx
  function handleSort(key: string) {
    if (sortKey === key) {
      setSort(key, sortDir === "asc" ? "desc" : "asc");
    } else {
      setSort(key, "desc");
    }
  }
```

Replace the filter-reset object literal inside `handleSelectSuggestion` (currently lines 128-133) with:

```tsx
  function handleSelectSuggestion(player: Player) {
    setFilters(DEFAULT_FILTERS);
    requestAnimationFrame(() => {
      const row = document.querySelector(`[data-player-id="${player.player_id}"]`);
      if (!row) return;
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      row.classList.add("row-highlight");
      setTimeout(() => row.classList.remove("row-highlight"), 1500);
    });
  }
```

No other lines in `Players.tsx` change — `onFiltersChange={setFilters}` and `onSeasonsChange={setSeasons}` (passed to `<Toolbar>`) already match the hook's returned function names and signatures.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/Players.test.tsx`
Expected: PASS — all tests in the file, including the 3 new ones.

- [ ] **Step 5: Run the full suite and build to check for regressions**

Run: `cd frontend && npm test && npm run build`
Expected: all tests pass (109 baseline + 9 from Task 1 + 3 from this task = 121), build succeeds.

- [ ] **Step 6: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/pages/Players.tsx frontend/src/pages/Players.test.tsx
git commit -m "Move Players' filter/sort/season state into the URL

Refreshing or sharing a link now preserves the current filtered/
sorted view. Swaps 4 useState calls for one useUrlFilters() call;
everything downstream (the rows useMemo, Toolbar/PlayerTable props)
is unchanged since the hook returns the same variable names and
types the local state used to."
```

---

### Task 4: Manual acceptance check

**Files:** none modified — verification only.

- [ ] **Step 1: Start the dev server and backend**

Run: `cd frontend && npm run dev` (background)
Run: `cd "/Users/paulmckay/Desktop/NHL Stats Project" && .venv/bin/python app.py` (background)

- [ ] **Step 2: Verify read-from-URL**

Navigate to `http://localhost:5173/players?team=EDM&sort=goals&dir=asc`. Confirm: the team picker shows EDM selected, the table is sorted by Goals ascending, and only Oilers players appear.

- [ ] **Step 3: Verify write-to-URL and default omission**

Navigate to `http://localhost:5173/players` (no params). Click a position toggle (e.g. "C"). Confirm the URL becomes `?positions=C` — no other params appear. Clear the position filter. Confirm the URL returns to `/players` with no query string.

- [ ] **Step 4: Verify refresh preserves state**

With some filters active (e.g. `?team=EDM&positions=C`), refresh the page. Confirm the toolbar and table still reflect that filtered state after reload (not the initial suggestions).

- [ ] **Step 5: Verify malformed-URL resilience**

Navigate to `http://localhost:5173/players?gp=notanumber&dir=sideways`. Confirm the page loads normally with all players shown (the malformed `gp` filter is ignored, not applied as "always false") and sort direction falls back to descending — no blank table, no crash, no console error.

- [ ] **Step 6: Stop the dev server and backend**

Run: `pkill -f "vite"` and `pkill -f "app.py"`

No commit for this task — verification-only checkpoint.
