# Broken States Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three live-broken states: Home's unexplained empty section, TeamPage/TopPlayers silently swallowing rankings-fetch failures, and Leaderboard having no empty-state for a legitimately-empty category.

**Architecture:** Three independent, small fixes. Home gets a one-element text placeholder (no fetch). Leaderboard gets a conditional render branch. TeamPage/TopPlayers both get the same `FetchState<T>` pattern already proven in `Players.tsx`, applied only to their rankings fetch — scoped to the leaderboard grid, not the whole page.

**Tech Stack:** React 19, Vite 8, TypeScript, Tailwind CSS 4, shadcn (`Alert`, `Button`), Vitest + Testing Library.

## Global Constraints

- All frontend work happens under `frontend/` — commands below assume `cd frontend` first.
- Do NOT shrink the Home hero's padding — `App.tsx:6` wraps every page in `min-h-screen`, so a shorter hero would make the empty space below it *larger*, not smaller (confirmed during grilling; this was the original, incorrect plan).
- TeamPage/TopPlayers' other three fetches (`teams`, `players`, `stats`) are unchanged — only the rankings fetch gets error handling, matching the audit finding's exact scope.
- No loading skeletons in this plan — that's a separate, not-yet-scoped audit item.

---

### Task 1: Home — replace dead space with a text placeholder

**Files:**
- Modify: `frontend/src/pages/Home.tsx:16`
- Test: `frontend/src/pages/Home.test.tsx`

**Interfaces:** None — standalone page, no new exports.

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/pages/Home.test.tsx`, inside the existing `describe("Home", ...)` block:

```tsx
  it("shows a coming-soon placeholder instead of a blank section", () => {
    render(<Home />);
    expect(screen.getByText("League news coming soon.")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Home.test.tsx`
Expected: FAIL — text not found, `Home.tsx` still has only a comment at line 16.

- [ ] **Step 3: Replace the comment with the placeholder**

In `frontend/src/pages/Home.tsx`, replace line 16:
```tsx
      {/* News feed (#118) renders here inline once built — Home has no separate /news route. */}
```
with:
```tsx
      {/* News feed (#118) renders here inline once built — Home has no separate /news route. */}
      <p className="px-4 py-12 text-center text-sm text-muted-foreground">
        League news coming soon.
      </p>
```
(Keep the existing comment — it's still accurate documentation of what replaces this placeholder later.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Home.test.tsx`
Expected: PASS — all 3 tests in the file (2 existing + 1 new).

- [ ] **Step 5: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/pages/Home.tsx frontend/src/pages/Home.test.tsx
git commit -m "Replace Home's empty section with a coming-soon placeholder

The section below the hero was reserved for an unbuilt news feed
(#118) but rendered as a large unexplained blank area. Shrinking the
hero (the original plan) would have made this worse, not better --
App.tsx wraps every page in min-h-screen, so a shorter hero just
leaves more forced-empty space below it. A lightweight text
placeholder explains the space honestly with no new fetch surface."
```

---

### Task 2: Leaderboard — empty-state branch

**Files:**
- Modify: `frontend/src/components/Leaderboard.tsx`
- Test: `frontend/src/components/Leaderboard.test.tsx`

**Interfaces:** None — `LeaderboardProps` unchanged (`title: string`, `players: RankedPlayer[]`, `onSelectPlayer: (playerId: number) => void`).

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/components/Leaderboard.test.tsx`, inside the existing `describe("Leaderboard", ...)` block:

```tsx
  it("shows an empty-state message instead of a bare list when there are no players", () => {
    render(<Leaderboard title="Top Goalie" players={[]} onSelectPlayer={() => {}} />);
    expect(screen.getByText("No qualifying players.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/Leaderboard.test.tsx`
Expected: FAIL — "No qualifying players." not found (current code renders an empty `<ol>` with no message).

- [ ] **Step 3: Add the empty-state branch**

Replace `frontend/src/components/Leaderboard.tsx` lines 13-30 (the `<ol>...</ol>` block) with:

```tsx
      {players.length === 0 ? (
        <p className="py-2 text-sm text-muted-foreground">No qualifying players.</p>
      ) : (
        <ol className="flex flex-col gap-1">
          {players.map((p, i) => (
            <li key={p.player_id}>
              <button
                type="button"
                onClick={() => onSelectPlayer(p.player_id)}
                className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
              >
                <span>
                  <span className="mr-2 text-muted-foreground">{i + 1}.</span>
                  {p.name}
                  <span className="ml-2 text-muted-foreground">{p.team_abbrev}</span>
                </span>
                <span className="font-mono text-muted-foreground">{p.score.toFixed(2)}</span>
              </button>
            </li>
          ))}
        </ol>
      )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/Leaderboard.test.tsx`
Expected: PASS — all 3 tests in the file (2 existing + 1 new).

- [ ] **Step 5: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/components/Leaderboard.tsx frontend/src/components/Leaderboard.test.tsx
git commit -m "Add empty-state message to Leaderboard

A category with zero qualifying players (a real, non-error outcome --
e.g. a team with no goalie meeting the ranking threshold) rendered a
bare, contentless list. Add an explicit 'No qualifying players.'
message so this reads as expected behavior, not a bug."
```

---

### Task 3: TeamPage & TopPlayers — scoped rankings error/retry

**Files:**
- Modify: `frontend/src/pages/TeamPage.tsx`
- Modify: `frontend/src/pages/TopPlayers.tsx`
- Test: `frontend/src/pages/TeamPage.test.tsx`
- Test: `frontend/src/pages/TopPlayers.test.tsx`

**Interfaces:**
- Consumes: `RankingRow` from `@/lib/leaderboards` (unchanged), `computeLeaderboards` from `@/lib/leaderboards` (unchanged), `Alert`/`AlertTitle`/`AlertDescription` from `@/components/ui/alert`, `Button` from `@/components/ui/button` (same imports `Players.tsx` already uses).
- Produces: nothing new consumed elsewhere — both are leaf page components.

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/pages/TeamPage.test.tsx`, inside the existing `describe("TeamPage", ...)` block:

```tsx
  it("shows an error with retry when rankings fail, while the team header still renders", async () => {
    let rankingsCallCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/api/players/rankings")) {
          rankingsCallCount += 1;
          return Promise.resolve({ ok: false, status: 500 } as Response);
        }
        return mockFetchOnce(url);
      })
    );

    render(
      <MemoryRouter initialEntries={["/teams/COL"]}>
        <Routes>
          <Route path="/teams/:teamId" element={<TeamPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("Colorado Avalanche")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Failed to load rankings");
    expect(rankingsCallCount).toBe(1);

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(rankingsCallCount).toBe(2);
  });
```

Add the `userEvent` import at the top of `frontend/src/pages/TeamPage.test.tsx` (alongside the existing imports):
```tsx
import userEvent from "@testing-library/user-event";
```

Add to `frontend/src/pages/TopPlayers.test.tsx`, inside the existing `describe("TopPlayers", ...)` block:

```tsx
  it("shows an error with retry when rankings fail", async () => {
    let rankingsCallCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/api/players/rankings")) {
          rankingsCallCount += 1;
          return Promise.resolve({ ok: false, status: 500 } as Response);
        }
        return mockFetchOnce(url);
      })
    );

    render(
      <MemoryRouter>
        <TopPlayers />
      </MemoryRouter>
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Failed to load rankings");
    expect(rankingsCallCount).toBe(1);

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(rankingsCallCount).toBe(2);
  });
```

Add the `userEvent` import at the top of `frontend/src/pages/TopPlayers.test.tsx`:
```tsx
import userEvent from "@testing-library/user-event";
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/TeamPage.test.tsx src/pages/TopPlayers.test.tsx`
Expected: FAIL — no `role="alert"` element exists yet in either component (unhandled fetch rejection, rankings stays `[]` forever, `computeLeaderboards([])` returns empty arrays, `Leaderboard` renders its new empty-state text from Task 2 instead of an error).

- [ ] **Step 3: Wire `TeamPage.tsx`**

Add the `FetchState` type and the imports. Replace `frontend/src/pages/TeamPage.tsx` lines 1-14:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Leaderboard } from "@/components/Leaderboard";
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { computeLeaderboards, type RankingRow } from "@/lib/leaderboards";
import { LATEST_SEASON_ID } from "@/lib/season";
import { teamColors, logoUrl } from "@/lib/teamBranding";
import type { Team, Player, PlayerStats } from "@/lib/types";

type FetchState<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request to ${url} failed (${res.status})`);
  return res.json() as Promise<T>;
}
```

Replace lines 16-38 (the component body from `export default function TeamPage()` through the `computeLeaderboards` call) with:

```tsx
export default function TeamPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const [teams, setTeams] = useState<Team[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [stats, setStats] = useState<PlayerStats[]>([]);
  const [rankingsState, setRankingsState] = useState<FetchState<RankingRow[]>>({ status: "loading" });
  const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);

  function loadRankings() {
    if (!teamId) return;
    setRankingsState({ status: "loading" });
    fetchJson<RankingRow[]>(`/api/players/rankings?season=${LATEST_SEASON_ID}&team=${teamId}`)
      .then((data) => setRankingsState({ status: "ready", data }))
      .catch((err) => setRankingsState({ status: "error", message: err.message }));
  }

  useEffect(() => {
    if (!teamId) return;
    fetchJson<Team[]>("/api/teams").then(setTeams);
    fetchJson<Player[]>("/api/players").then(setPlayers);
    fetchJson<PlayerStats[]>(`/api/players/stats?seasons=${LATEST_SEASON_ID}`).then(setStats);
    loadRankings();
  }, [teamId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!teamId) return null;

  const team = teams.find((t) => t.abbrev === teamId);
  const colors = teamColors(teamId);
  const { offense, defense, goalie } = computeLeaderboards(
    rankingsState.status === "ready" ? rankingsState.data : []
  );
```

Replace lines 52-56 (the leaderboard grid) with:

```tsx
      <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-3">
        {rankingsState.status === "error" ? (
          <Alert variant="destructive" className="md:col-span-3">
            <AlertTitle>Failed to load rankings</AlertTitle>
            <AlertDescription>{rankingsState.message}</AlertDescription>
            <Button onClick={loadRankings} className="mt-2">Retry</Button>
          </Alert>
        ) : rankingsState.status === "ready" ? (
          <>
            <Leaderboard title="Top Offense" players={offense.slice(0, 5)} onSelectPlayer={setProfilePlayerId} />
            <Leaderboard title="Top Defense" players={defense.slice(0, 5)} onSelectPlayer={setProfilePlayerId} />
            <Leaderboard title="Top Goalie" players={goalie.slice(0, 5)} onSelectPlayer={setProfilePlayerId} />
          </>
        ) : null}
      </div>
```

- [ ] **Step 4: Wire `TopPlayers.tsx`**

Replace `frontend/src/pages/TopPlayers.tsx` lines 1-12 with:

```tsx
import { useEffect, useState } from "react";
import { Leaderboard } from "@/components/Leaderboard";
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { computeLeaderboards, type RankingRow } from "@/lib/leaderboards";
import { LATEST_SEASON_ID } from "@/lib/season";
import type { Player, PlayerStats } from "@/lib/types";

type FetchState<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request to ${url} failed (${res.status})`);
  return res.json() as Promise<T>;
}
```

Replace lines 14-26 (the component body from `export default function TopPlayers()` through the `computeLeaderboards` call) with:

```tsx
export default function TopPlayers() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [stats, setStats] = useState<PlayerStats[]>([]);
  const [rankingsState, setRankingsState] = useState<FetchState<RankingRow[]>>({ status: "loading" });
  const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);

  function loadRankings() {
    setRankingsState({ status: "loading" });
    fetchJson<RankingRow[]>(`/api/players/rankings?season=${LATEST_SEASON_ID}`)
      .then((data) => setRankingsState({ status: "ready", data }))
      .catch((err) => setRankingsState({ status: "error", message: err.message }));
  }

  useEffect(() => {
    fetchJson<Player[]>("/api/players").then(setPlayers);
    fetchJson<PlayerStats[]>(`/api/players/stats?seasons=${LATEST_SEASON_ID}`).then(setStats);
    loadRankings();
  }, []);

  const { offense, defense, goalie } = computeLeaderboards(
    rankingsState.status === "ready" ? rankingsState.data : []
  );
```

Replace lines 33-37 (the leaderboard grid) with:

```tsx
      <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-3">
        {rankingsState.status === "error" ? (
          <Alert variant="destructive" className="md:col-span-3">
            <AlertTitle>Failed to load rankings</AlertTitle>
            <AlertDescription>{rankingsState.message}</AlertDescription>
            <Button onClick={loadRankings} className="mt-2">Retry</Button>
          </Alert>
        ) : rankingsState.status === "ready" ? (
          <>
            <Leaderboard title="Top Offense" players={offense.slice(0, 15)} onSelectPlayer={setProfilePlayerId} />
            <Leaderboard title="Top Defense" players={defense.slice(0, 15)} onSelectPlayer={setProfilePlayerId} />
            <Leaderboard title="Top Goalie" players={goalie.slice(0, 15)} onSelectPlayer={setProfilePlayerId} />
          </>
        ) : null}
      </div>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/TeamPage.test.tsx src/pages/TopPlayers.test.tsx`
Expected: PASS — both new tests, plus the existing "fetches ... and renders three leaderboards" test in each file (the happy path still works since `rankingsState.status === "ready"` renders identically to the old unconditional render).

- [ ] **Step 6: Run the full suite and build to check for regressions**

Run: `cd frontend && npm test && npm run build`
Expected: all tests pass (113/113 — 109 baseline on `main` [Group 1's PR #132 hasn't merged yet, so this worktree branches from a 109-test `main`, not the 111 on that unmerged branch] + 1 from Task 1 + 1 from Task 2 + 2 new here), build succeeds.

- [ ] **Step 7: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/pages/TeamPage.tsx frontend/src/pages/TeamPage.test.tsx frontend/src/pages/TopPlayers.tsx frontend/src/pages/TopPlayers.test.tsx
git commit -m "Show error+retry when TeamPage/TopPlayers' rankings fetch fails

Both pages previously had no .catch() on the rankings fetch -- a
failure (e.g. the live backend's current rankings 500) left three
permanently empty leaderboard cards with no indication anything was
wrong. Scope the fix to just the leaderboard grid (team
header/logo, which don't depend on rankings, keep rendering
unconditionally) using the same FetchState + Alert + retry pattern
Players.tsx already established for its own fetches."
```

---

### Task 4: Visual acceptance check

**Files:** none modified — verification only.

- [ ] **Step 1: Start the dev server and backend**

Run: `cd frontend && npm run dev` (background)
Run: `cd "/Users/paulmckay/Desktop/NHL Stats Project" && .venv/bin/python app.py` (background — needed for real Team/TopPlayers pages; note the rankings endpoint is expected to still 500 against the real DB, which is exactly the scenario this plan handles)

- [ ] **Step 2: Capture screenshots via openwolf designqc**

Run: `openwolf designqc --url http://localhost:5173 --routes / /teams/EDM /top-players --desktop-only`

- [ ] **Step 3: Review captures**

Read the screenshots from `.wolf/designqc-captures/`. Confirm:
- Home no longer shows a large blank area — "League news coming soon." is visible below the hero.
- `/teams/EDM` and `/top-players` show a visible error message with a Retry button where the three leaderboard cards used to render empty (the real backend's rankings endpoint is still broken today, so this is the actual, currently-live scenario, not a simulated one).
- The team header/logo on `/teams/EDM` still renders normally above the error.

- [ ] **Step 4: Stop the dev server and backend**

Run: `pkill -f "vite"` and `pkill -f "app.py"`

No commit for this task — verification-only checkpoint.
