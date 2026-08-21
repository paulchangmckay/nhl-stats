# PlayerTable Virtualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `PlayerTable` from mounting all ~1038 rows unconditionally — only rows within (and just outside) the visible scroll window should exist in the DOM at any time, with no behavioral or visual regression.

**Architecture:** `@tanstack/react-virtual`'s `useVirtualizer` drives which rows render, positioned via `translateY` (not `position: absolute`, which would conflict with the existing sticky header). `PlayerTable` becomes a `forwardRef` component exposing one imperative method (`scrollToPlayer`) so `Players.tsx`'s search-suggestion-click feature can force a currently-unmounted row to mount, then highlight it — without `Players.tsx` needing to know virtualization exists.

**Tech Stack:** React 19, `@tanstack/react-virtual@3.14.10` (new dependency — confirmed via `npm view`/dry-run install to support React 19 and install cleanly against this project's exact lockfile), Vitest + Testing Library.

## Global Constraints

- Row height is fixed at **38px** (measured live against the running app — every cell is `whitespace-nowrap`, uniformly one line tall). `estimateSize: () => 38`.
- Rows are positioned via `transform: translateY(...)`, never `position: absolute` — matches `@tanstack/react-virtual`'s documented table pattern and avoids conflicting with the sticky header.
- `<TableRow>`'s React `key` stays `row.player_id` (via `rows[virtualItem.index].player_id`) — never `virtualItem.key`, which defaults to a position index, not player identity (verified against the installed `VirtualItem` type definition during grilling).
- `PlayerTable`'s new `scrollContainerRef` prop is **optional** in the type system (`scrollContainerRef?: React.RefObject<HTMLDivElement>`) even though the one real caller (`Players.tsx`) always provides it — this keeps every existing test call site (which passes no such prop) compiling without modification.
- No column/horizontal virtualization, no row-count threshold that conditionally disables virtualization, no roving-tabindex keyboard-navigation fix — all explicitly out of scope per the spec's anti-goals.
- **Testing gap found while writing this plan, not in the original spec:** `Players.test.tsx` renders the real (unmocked) `PlayerTable` and asserts on rendered player names (e.g. `findByText("MacKinnon")`). `vi.mock` is scoped per test file — mocking `@tanstack/react-virtual` only in `PlayerTable.test.tsx` would leave `Players.test.tsx` exposed to jsdom's lack of real layout (a 0-height scroll container could make the real virtualizer compute zero visible rows, breaking those assertions). Both `PlayerTable.test.tsx` and `Players.test.tsx` get their own independent `vi.mock("@tanstack/react-virtual", ...)` — duplicated rather than shared via a common module, to avoid relying on cross-file `vi.mock` hoisting behavior working correctly across an import boundary (not worth the risk to save a few lines).

---

### Task 1: Virtualize `PlayerTable` with an imperative `scrollToPlayer` handle

**Files:**
- Modify: `frontend/package.json` (new dependency)
- Modify: `frontend/src/components/PlayerTable.tsx` (full virtualization rewrite)
- Modify: `frontend/src/components/PlayerTable.test.tsx` (mock + new tests)

**Interfaces:**
- Consumes: `useVirtualizer` from `@tanstack/react-virtual`.
- Produces:
  - `export interface PlayerTableHandle { scrollToPlayer(playerId: number): void; }`
  - `PlayerTableProps` gains `scrollContainerRef?: React.RefObject<HTMLDivElement>` (optional, per Global Constraints).
  - `PlayerTable` becomes `React.forwardRef<PlayerTableHandle, PlayerTableProps>(...)`.

- [ ] **Step 1: Install the dependency**

Run: `cd frontend && npm install @tanstack/react-virtual`
Expected: `package.json`/`package-lock.json` updated, `@tanstack/react-virtual@3.14.10` and `@tanstack/virtual-core@3.17.8` added.

- [ ] **Step 2: Write the failing tests**

Replace `frontend/src/components/PlayerTable.test.tsx` lines 1-6 (imports) with:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import { PlayerTable, type PlayerTableHandle } from "./PlayerTable";
import { MOCK_STATS } from "@/lib/mock-data";

const mockScrollToIndex = vi.fn();

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (options: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: options.count }, (_, index) => ({
        key: index,
        index,
        start: index * 38,
        end: (index + 1) * 38,
        size: 38,
        lane: 0,
      })),
    getTotalSize: () => options.count * 38,
    scrollToIndex: mockScrollToIndex,
  }),
}));

beforeEach(() => {
  mockScrollToIndex.mockClear();
});
```

Add these two new tests inside the existing `describe("PlayerTable", ...)` block, after the last existing `it(...)`:

```tsx
  it("scrollToPlayer calls the virtualizer's scrollToIndex with the player's index", () => {
    const ref = createRef<PlayerTableHandle>();
    render(<PlayerTable ref={ref} rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    ref.current!.scrollToPlayer(2); // McDavid, index 1 in MOCK_STATS
    expect(mockScrollToIndex).toHaveBeenCalledWith(1, { align: "center", behavior: "auto" });
  });

  it("scrollToPlayer is a no-op for an unknown player id", () => {
    const ref = createRef<PlayerTableHandle>();
    render(<PlayerTable ref={ref} rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    ref.current!.scrollToPlayer(9999);
    expect(mockScrollToIndex).not.toHaveBeenCalled();
  });
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/PlayerTable.test.tsx`
Expected: the two new tests FAIL — `PlayerTable` doesn't accept a `ref` yet (not a `forwardRef` component), so `ref.current` is `null` and `ref.current!.scrollToPlayer` throws. The 7 pre-existing tests should still PASS at this point (the mock is inert until the component actually calls `useVirtualizer` — which it doesn't yet).

- [ ] **Step 4: Rewrite `frontend/src/components/PlayerTable.tsx`**

Replace the entire file with:

```tsx
import { forwardRef, useImperativeHandle } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { PlayerStats, SortDirection } from "@/lib/types";

const ROW_HEIGHT_PX = 38;

interface Column {
  key: string;
  label: string;
  numeric?: boolean;
  goalieOnly?: boolean;
  skaterOnly?: boolean;
}

const COLUMNS: Column[] = [
  { key: "last_name", label: "Last Name" },
  { key: "first_name", label: "First Name" },
  { key: "position_code", label: "Pos" },
  { key: "team_abbrev", label: "Team" },
  { key: "gp", label: "GP", numeric: true },
  { key: "goals", label: "G", numeric: true, skaterOnly: true },
  { key: "assists", label: "A", numeric: true, skaterOnly: true },
  { key: "points", label: "Pts", numeric: true, skaterOnly: true },
  { key: "plus_minus", label: "+/-", numeric: true, skaterOnly: true },
  { key: "pim", label: "PIM", numeric: true },
  { key: "shooting_pct", label: "SH%", numeric: true, skaterOnly: true },
  { key: "avg_toi", label: "Avg TOI", skaterOnly: true },
  { key: "wins", label: "W", numeric: true, goalieOnly: true },
  { key: "losses", label: "L", numeric: true, goalieOnly: true },
  { key: "save_pct", label: "SV%", numeric: true, goalieOnly: true },
  { key: "gaa", label: "GAA", numeric: true, goalieOnly: true },
  { key: "cf_pct_5v5", label: "CF% (5v5)", numeric: true, skaterOnly: true },
  { key: "shots_per60_5v5", label: "Shots/60 (5v5)", numeric: true, skaterOnly: true },
];

function cellValue(col: Column, row: PlayerStats): string {
  const val = (row as unknown as Record<string, unknown>)[col.key];
  if (val === null || val === undefined) return "-";
  if (col.key === "save_pct") return Number(val).toFixed(3);
  if (col.key === "gaa") return Number(val).toFixed(2);
  if (col.key === "shooting_pct") return `${val}%`;
  if (col.key === "cf_pct_5v5") return `${val}%`;
  if (col.key === "shots_per60_5v5") return Number(val).toFixed(2);
  if (col.key === "plus_minus") return Number(val) > 0 ? `+${val}` : String(val);
  return String(val);
}

export interface PlayerTableHandle {
  scrollToPlayer(playerId: number): void;
}

interface PlayerTableProps {
  rows: PlayerStats[];
  sortKey: string;
  sortDir: SortDirection;
  onSort: (key: string) => void;
  onOpenProfile?: (playerId: number) => void;
  scrollContainerRef?: React.RefObject<HTMLDivElement>;
}

export const PlayerTable = forwardRef<PlayerTableHandle, PlayerTableProps>(function PlayerTable(
  { rows, sortKey, sortDir, onSort, onOpenProfile, scrollContainerRef },
  ref
) {
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollContainerRef?.current ?? null,
    estimateSize: () => ROW_HEIGHT_PX,
    overscan: 10,
  });

  useImperativeHandle(
    ref,
    () => ({
      scrollToPlayer(playerId: number) {
        const index = rows.findIndex((r) => r.player_id === playerId);
        if (index === -1) return;
        virtualizer.scrollToIndex(index, { align: "center", behavior: "auto" });
        requestAnimationFrame(() => {
          const el = document.querySelector(`[data-player-id="${playerId}"]`);
          if (!el) return;
          el.classList.add("row-highlight");
          setTimeout(() => el.classList.remove("row-highlight"), 1500);
        });
      },
    }),
    [rows, virtualizer]
  );

  if (rows.length === 0) {
    return <div className="p-12 text-center text-sm text-muted-foreground">No players found.</div>;
  }

  const hasGoalie = rows.some((r) => r.position_code === "G");
  const columns = COLUMNS.filter((c) => {
    if (c.goalieOnly) return hasGoalie;
    return true;
  });

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();
  const renderedHeight = virtualItems.length * ROW_HEIGHT_PX;
  const spacerHeight = totalSize - renderedHeight;

  return (
    <Table>
      <TableHeader className="sticky top-0 bg-card">
        <TableRow>
          {columns.map((col) => (
            <TableHead
              key={col.key}
              onClick={() => onSort(col.key)}
              className="cursor-pointer select-none"
            >
              {col.label}
              {sortKey === col.key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {virtualItems.map((virtualItem, i) => {
          const row = rows[virtualItem.index];
          return (
            <TableRow
              key={row.player_id}
              data-player-id={row.player_id}
              style={{ transform: `translateY(${virtualItem.start - i * ROW_HEIGHT_PX}px)` }}
              tabIndex={onOpenProfile ? 0 : undefined}
              role={onOpenProfile ? "button" : undefined}
              onClick={onOpenProfile ? () => onOpenProfile(row.player_id) : undefined}
              onKeyDown={
                onOpenProfile
                  ? (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onOpenProfile(row.player_id);
                      }
                    }
                  : undefined
              }
              className={onOpenProfile ? "cursor-pointer hover:bg-muted/50" : undefined}
            >
              {columns.map((col) => (
                <TableCell
                  key={col.key}
                  className={col.numeric ? "text-right tabular-nums" : ""}
                >
                  {col.key === "position_code" ? (
                    <Badge variant="outline">{row.position_code}</Badge>
                  ) : col.skaterOnly && row.position_code === "G" ? (
                    "-"
                  ) : (
                    cellValue(col, row)
                  )}
                </TableCell>
              ))}
            </TableRow>
          );
        })}
        {spacerHeight > 0 && (
          <tr aria-hidden="true">
            <td colSpan={columns.length} style={{ height: spacerHeight, padding: 0, border: "none" }} />
          </tr>
        )}
      </TableBody>
    </Table>
  );
});
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/PlayerTable.test.tsx`
Expected: PASS — all 10 tests (8 existing + 2 new). The mocked `useVirtualizer` reports every row as a virtual item, so every existing assertion (row text, sort clicks, goalie columns, empty state, click-to-open-profile, keyboard Enter) behaves exactly as before virtualization — the mock makes virtualization transparent to these tests, per the spec's testing strategy.

- [ ] **Step 6: Run the build to check for type errors**

Run: `cd frontend && npm run build`
Expected: exit 0. Do not run the full `npm test` suite yet — `Players.test.tsx` renders the real (now-virtualized) `PlayerTable` and does not have its own mock until Task 2, so it is expected to fail at this point. That's addressed in Task 2's Step 1-2, not a regression to chase down here; running the full suite now would only produce a confusing, expected-but-unresolved failure. `PlayerTable.test.tsx`'s own 10 tests (confirmed passing in Step 5) are the complete verification for this task.

- [ ] **Step 7: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/package.json frontend/package-lock.json frontend/src/components/PlayerTable.tsx frontend/src/components/PlayerTable.test.tsx
git commit -m "Virtualize PlayerTable, expose imperative scrollToPlayer handle

Only rows within (and just outside) the visible scroll window are now
mounted, replacing unconditional rendering of up to ~1038 rows.
Positioned via translateY per @tanstack/react-virtual's documented
table pattern (not position: absolute, which would conflict with the
sticky header). Exposes scrollToPlayer via forwardRef +
useImperativeHandle so callers can force an unmounted row to mount
and highlight it, without needing to know virtualization exists --
Players.tsx's search-suggestion-click feature depends on this in
Task 2. Tests mock the virtualizer to report every row as visible, so
existing table-behavior assertions (sorting, badges, click handlers)
stay meaningful without depending on jsdom's real layout, which
doesn't exist."
```

---

### Task 2: Wire `Players.tsx` to the ref, fix the search-suggestion scroll

**Files:**
- Modify: `frontend/src/pages/Players.tsx:1-9,127-141,193-210`
- Modify: `frontend/src/pages/Players.test.tsx`

**Interfaces:**
- Consumes: `PlayerTableHandle` (Task 1) from `@/components/PlayerTable`.
- Produces: no new exports — `Players` is a page component.

- [ ] **Step 1: Add the same virtualizer mock to `Players.test.tsx`**

Add near the top of `frontend/src/pages/Players.test.tsx`, alongside the existing imports (exact placement doesn't matter as long as it's before the `describe` block — `vi.mock` calls are hoisted by Vitest regardless of where they appear in the file):

```tsx
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (options: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: options.count }, (_, index) => ({
        key: index,
        index,
        start: index * 38,
        end: (index + 1) * 38,
        size: 38,
        lane: 0,
      })),
    getTotalSize: () => options.count * 38,
    scrollToIndex: vi.fn(),
  }),
}));
```

(This mirrors Task 1's mock but doesn't need a shared, assertable `scrollToIndex` reference — no test in this file asserts on `scrollToIndex` calls directly, only on the eventual visible effect: the target row gaining the `row-highlight` class. A plain inert `vi.fn()` is sufficient here.)

- [ ] **Step 2: Run the full suite to confirm this alone fixes the Task-1-introduced failures**

Run: `cd frontend && npm test`
Expected: `Players.test.tsx`'s previously-failing tests (from Task 1's real, unmocked virtualization) now PASS again — the mock renders every row, so `findByText("MacKinnon")` and similar assertions resolve exactly as before. This confirms the mock is the correct, sufficient fix before continuing to Step 3's actual behavior change.

- [ ] **Step 3: Wire `Players.tsx`**

Replace `frontend/src/pages/Players.tsx` line 1 with:

```tsx
import { useEffect, useMemo, useRef, useState } from "react";
```

Replace line 3 with:

```tsx
import { PlayerTable, type PlayerTableHandle } from "@/components/PlayerTable";
```

Add a new ref declaration inside the `Players` component, immediately after the existing `const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);` line (currently line 41):

```tsx
  const tableRef = useRef<PlayerTableHandle>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
```

Replace `handleSelectSuggestion` (currently lines 127-141) with:

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

(The DOM-querying and highlight logic that used to live here moved into `PlayerTable`'s `scrollToPlayer` method in Task 1 — this function now only resets filters and asks the table to scroll to the player, matching the design's stated boundary: `Players.tsx` shouldn't need to know virtualization exists.)

Replace the table-wrapping `<div>` and `<PlayerTable>` (currently lines 194-209) with:

```tsx
        <div
          ref={scrollContainerRef}
          data-testid="table-wrap"
          className="overflow-auto"
          style={{
            height:
              "max(200px, calc(100vh - var(--toolbar-height, 57px) - var(--header-height, 0px)))",
          }}
        >
          <PlayerTable
            ref={tableRef}
            rows={rows}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={handleSort}
            onOpenProfile={setProfilePlayerId}
            scrollContainerRef={scrollContainerRef}
          />
        </div>
```

- [ ] **Step 4: Verify the existing suggestion-click test tolerates the new two-hop async sequence**

`frontend/src/pages/Players.test.tsx:120-135` already has this test, unmodified by this plan:

```tsx
  it("clears other filters, scrolls to, and highlights the row when a suggestion is clicked", async () => {
    renderPlayers();
    await screen.findByText("MacKinnon");
    await userEvent.click(screen.getByRole("button", { name: "C" })); // active position filter
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "MacKinnon");
    await userEvent.click(await screen.findByText("Nathan MacKinnon"));

    // search box cleared, position filter cleared (McDavid, a center, is visible again)
    expect(screen.getByPlaceholderText("Search players…")).toHaveValue("");
    expect(screen.getByText("McDavid")).toBeInTheDocument();

    await waitFor(() => {
      const row = document.querySelector('[data-player-id="1"]');
      expect(row).toHaveClass("row-highlight");
    });
  });
```

It already wraps the highlight assertion in `waitFor` — which should tolerate the new two-hop sequence (outer `requestAnimationFrame` for the filter reset to commit, then `scrollToPlayer`'s own internal `requestAnimationFrame` for the scroll-triggered mount to commit) without any change, since `waitFor` polls until the assertion passes or its default 1000ms timeout — comfortably longer than two chained animation-frame ticks. No edit is anticipated here; this step is confirming that expectation against the real run, not applying a known fix.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/Players.test.tsx`
Expected: PASS — all tests, including the suggestion-click test (with or without the `waitFor` adjustment from Step 4, whichever the real run required).

- [ ] **Step 6: Run the full suite and build to check for regressions**

Run: `cd frontend && npm test && npm run build`
Expected: all tests pass, build succeeds.

- [ ] **Step 7: Commit**

Run from the worktree root (`/Users/paulmckay/Desktop/NHL Stats Project/.worktrees/feature-139-player-table-virtualization`), not the main checkout — confirm with `git rev-parse --show-toplevel` first if unsure:

```bash
git add frontend/src/pages/Players.tsx frontend/src/pages/Players.test.tsx
git commit -m "Wire Players.tsx to PlayerTable's virtualization ref

The scroll container's height depends on page-chrome CSS vars
(--toolbar-height, --header-height) PlayerTable has no business
knowing about, so Players.tsx keeps owning and rendering that
wrapper div and passes its ref down. handleSelectSuggestion no longer
reaches into the DOM directly -- it resets filters, then asks the
table (via tableRef.scrollToPlayer) to scroll to and highlight the
target player, which now correctly force-mounts the row first if
virtualization has it unmounted. Players.test.tsx gets the same
virtualizer mock as PlayerTable.test.tsx, since it renders the real
PlayerTable and was exposed to the same jsdom-layout gap."
```

---

### Task 3: Visual and behavioral acceptance check

**Files:** none modified — verification only.

- [ ] **Step 1: Start the dev server and backend**

Run: `cd frontend && npm run dev` (background)
Run: `cd "/Users/paulmckay/Desktop/NHL Stats Project" && .venv/bin/python app.py` (background)

- [ ] **Step 2: Verify DOM node count drops**

Navigate to `/players` (unfiltered, ~1038 rows). Via the `playwright` MCP tools, run:
```js
document.querySelectorAll('table tbody tr[data-player-id]').length
```
Expected: well under 1038 — roughly `overscan * 2 + (container height / 38)`, e.g. on a typical viewport somewhere in the 30-60 range, not 1000+.

- [ ] **Step 3: Verify scrolling mounts/unmounts rows correctly**

Scroll the table container partway down. Re-run the same `document.querySelectorAll(...)` query and check the rendered `data-player-id` values — confirm they've changed to reflect the new scroll position (different player IDs than Step 2's initial set), and the count stays roughly the same (not accumulating).

- [ ] **Step 4: Verify the sticky header survives scrolling**

Scroll the table down partway. Confirm the column header row (`GP`, `G`, `A`, `Pts`, etc.) is still visible pinned at the top of the scroll container, not scrolled away — this was flagged as a real (not hypothetical) risk during design research and must be actually checked, not assumed.

- [ ] **Step 5: Verify the search-suggestion scroll-to-row works for a currently-unmounted player**

With the table scrolled to the top (so a player far down the alphabetically/points-sorted list is definitely unmounted), use the search box to find and click a suggestion for a player who is not currently visible. Confirm: the view scrolls to that player's row, and it briefly gets a highlight treatment — this is the actual regression case virtualization introduces, and the specific scenario the imperative handle exists to fix.

- [ ] **Step 6: Visual comparison — no regression**

Compare against a pre-virtualization screenshot (or just visual inspection) — row heights, spacing, borders, hover states, position badges should all look identical to before. No flicker or layout shift while scrolling.

- [ ] **Step 7: Stop the dev server and backend**

Run: `pkill -f "vite"` and `pkill -f "app.py"`

No commit for this task — verification-only checkpoint.
