# Header Navigation + Homepage Hero Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the NHL-Stats app a persistent, mobile-responsive header nav and a hero-only homepage, closing issues #119 and #120.

**Architecture:** Introduce `react-router-dom` with a nested-layout route (`App` renders `<Header/>` + `<Outlet/>`). The existing toolbar/table view moves off `/` and onto its own `/players` route unchanged; `/` becomes a dedicated hero landing page. `/teams`, `/top-players`, `/betting` get a shared placeholder page until their own groups land. Flask gets a catch-all fallback route so direct hits/refreshes on any client-side route resolve correctly.

**Tech Stack:** React 19 + TypeScript, Vite, Tailwind v4 + shadcn/ui (`@base-ui/react` primitives), Vitest + Testing Library (frontend); Flask + pytest (backend).

## Global Constraints

- Add `react-router-dom` (resolves to `7.18.2` as of this plan — verified installs cleanly against `react@^19.2.7`/`react-dom@^19.2.7` with no peer conflicts).
- No new image assets — hero is a CSS gradient built from `frontend/src/lib/teamBranding.ts`'s existing `TEAM_COLORS`, not a photo.
- Nav items, in order: Home (`/`), Players (`/players`), Teams (`/teams`), Top Players (`/top-players`), Betting (`/betting`). No "News" nav item — it will live inline on Home in a future group (#118), not built here.
- No new shadcn "Sheet" component — one doesn't exist in `frontend/src/components/ui/` (only `dialog.tsx`, `popover.tsx`, etc., all on `@base-ui/react` primitives) and the codebase already uses `Dialog` for the same "toggle a panel open/closed" need (`PlayerProfilePanel.tsx`). The mobile nav menu reuses the existing `Dialog` component instead of introducing a new primitive.
- Unknown routes redirect to `/` (`<Route path="*" element={<Navigate to="/" replace />} />`) — no dedicated 404 page.
- Follow existing conventions throughout: `@/` import alias, `cn()` from `@/lib/utils` for conditional classes, Tailwind design tokens (`bg-background`, `text-foreground`, `border-border`, `bg-card`, `text-muted-foreground`), `lucide-react` icons imported as `XIcon`/`MenuIcon`-style names (matches `dialog.tsx`'s existing `XIcon` import).

---

### Task 1: Flask SPA-fallback route

**Files:**
- Modify: `app.py:30-32`
- Test: `tests/test_app_spa_fallback.py` (create)

**Interfaces:**
- Produces: no new importable symbols — this is a route registration, verified via HTTP behavior only.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app_spa_fallback.py
import app as app_module


def test_direct_hit_on_client_route_returns_index_html():
    client = app_module.app.test_client()
    resp = client.get("/players")
    assert resp.status_code == 200
    assert b"<div id=\"root\">" in resp.data


def test_unknown_client_route_also_returns_index_html():
    client = app_module.app.test_client()
    resp = client.get("/teams")
    assert resp.status_code == 200
    assert b"<div id=\"root\">" in resp.data


def test_unmatched_api_path_still_404s():
    client = app_module.app.test_client()
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404


def test_unmatched_static_path_still_404s():
    client = app_module.app.test_client()
    resp = client.get("/static/does-not-exist.js")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_spa_fallback.py -v`
Expected: the two "returns index.html" tests FAIL with 404 (no catch-all route registered yet). The two "still 404s" tests PASS already (nothing changed their behavior yet) — that's fine, they're regression guards for the fix in Step 3.

- [ ] **Step 3: Add the catch-all route**

In `app.py`, add `abort` to the existing Flask import on line 5, and add the new route directly after `index()` (after line 32):

```python
from flask import Flask, jsonify, render_template, request, abort
```

```python
@app.route("/<path:path>")
def spa_fallback(path):
    if path.startswith("api/") or path.startswith("static/"):
        abort(404)
    return render_template("index.html")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_app_spa_fallback.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS (existing `/api/*` routes are unaffected — Flask/Werkzeug matches the more specific literal routes before the `<path:path>` catch-all, and the explicit `path.startswith("api/")` guard is defense-in-depth on top of that).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_spa_fallback.py
git commit -m "feat: add Flask SPA-fallback route for client-side routing (#119)"
```

---

### Task 2: Install react-router-dom

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`

**Interfaces:**
- Produces: `react-router-dom` importable in all subsequent frontend tasks (`BrowserRouter`, `Routes`, `Route`, `Navigate`, `NavLink`, `Outlet`).

- [ ] **Step 1: Install the dependency**

Run: `cd frontend && npm install react-router-dom`
Expected output: adds `react-router-dom` (`^7.18.2`), `react-router`, `cookie`, `set-cookie-parser` to `package.json`/`package-lock.json`, no peer-dependency warnings.

- [ ] **Step 2: Verify the frontend still builds**

Run: `cd frontend && npm run build`
Expected: build succeeds (no code uses the new dependency yet, this just confirms the install didn't break anything).

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add react-router-dom dependency"
```

---

### Task 3: PlaceholderPage component

**Files:**
- Create: `frontend/src/pages/PlaceholderPage.tsx`
- Test: `frontend/src/pages/PlaceholderPage.test.tsx`

**Interfaces:**
- Produces: `export default function PlaceholderPage({ title }: { title: string })`, rendering `title` as a heading plus fixed "Coming soon." body text.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/pages/PlaceholderPage.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PlaceholderPage from "./PlaceholderPage";

describe("PlaceholderPage", () => {
  it("renders the given title and a coming-soon message", () => {
    render(<PlaceholderPage title="Teams" />);
    expect(screen.getByRole("heading", { name: "Teams" })).toBeInTheDocument();
    expect(screen.getByText("Coming soon.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/PlaceholderPage.test.tsx`
Expected: FAIL — `Failed to resolve import "./PlaceholderPage"`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/pages/PlaceholderPage.tsx
interface PlaceholderPageProps {
  title: string;
}

export default function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-24 text-center">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="text-muted-foreground">Coming soon.</p>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/PlaceholderPage.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PlaceholderPage.tsx frontend/src/pages/PlaceholderPage.test.tsx
git commit -m "feat: add reusable PlaceholderPage for not-yet-built routes"
```

---

### Task 4: Hero gradient helper + Home page

**Files:**
- Create: `frontend/src/lib/heroGradient.ts`
- Create: `frontend/src/lib/heroGradient.test.ts`
- Create: `frontend/src/pages/Home.tsx`
- Create: `frontend/src/pages/Home.test.tsx`

**Interfaces:**
- Consumes: `teamColors` from `@/lib/teamBranding` (existing: `teamColors(abbrev: string): { primary: string; secondary: string } | undefined`).
- Produces: `export function buildHeroGradient(): string` (a CSS `linear-gradient(...)` value); `export default function Home()`.

- [ ] **Step 1: Write the failing test for the gradient helper**

```ts
// frontend/src/lib/heroGradient.test.ts
import { describe, it, expect } from "vitest";
import { buildHeroGradient } from "./heroGradient";
import { teamColors } from "./teamBranding";

describe("buildHeroGradient", () => {
  it("builds a 135deg linear-gradient from the fixed team-color stops", () => {
    const gradient = buildHeroGradient();
    expect(gradient.startsWith("linear-gradient(135deg,")).toBe(true);
    expect(gradient).toContain(teamColors("COL")!.primary);
    expect(gradient).toContain(teamColors("VGK")!.primary);
    expect(gradient).toContain(teamColors("TOR")!.primary);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/heroGradient.test.ts`
Expected: FAIL — `Failed to resolve import "./heroGradient"`.

- [ ] **Step 3: Write the gradient helper**

```ts
// frontend/src/lib/heroGradient.ts
import { teamColors } from "./teamBranding";

const HERO_GRADIENT_TEAMS = ["COL", "VGK", "TOR"] as const;

export function buildHeroGradient(): string {
  const stops = HERO_GRADIENT_TEAMS.map((abbrev) => teamColors(abbrev)!.primary);
  return `linear-gradient(135deg, ${stops.join(", ")})`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/heroGradient.test.ts`
Expected: PASS (1 test).

- [ ] **Step 5: Write the failing test for Home**

```tsx
// frontend/src/pages/Home.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "./Home";

describe("Home", () => {
  it("renders the hero heading and subtext", () => {
    render(<Home />);
    expect(
      screen.getByRole("heading", { name: "Dig Into Every Player's Numbers" })
    ).toBeInTheDocument();
    expect(
      screen.getByText("Deep player and team analytics for every skater and goalie in the league.")
    ).toBeInTheDocument();
  });

  it("applies a gradient background to the hero section", () => {
    render(<Home />);
    const hero = screen.getByTestId("hero");
    expect(hero.style.backgroundImage).toMatch(/^linear-gradient\(135deg,/);
  });
});
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Home.test.tsx`
Expected: FAIL — `Failed to resolve import "./Home"`.

- [ ] **Step 7: Write the Home page**

```tsx
// frontend/src/pages/Home.tsx
import { buildHeroGradient } from "@/lib/heroGradient";

export default function Home() {
  return (
    <div>
      <section
        data-testid="hero"
        className="flex flex-col items-center justify-center gap-3 px-4 py-24 text-center text-white"
        style={{ backgroundImage: buildHeroGradient() }}
      >
        <h1 className="text-4xl font-bold sm:text-5xl">Dig Into Every Player's Numbers</h1>
        <p className="max-w-xl text-base text-white/90 sm:text-lg">
          Deep player and team analytics for every skater and goalie in the league.
        </p>
      </section>
      {/* News feed (#118) renders here inline once built — Home has no separate /news route. */}
    </div>
  );
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Home.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/heroGradient.ts frontend/src/lib/heroGradient.test.ts frontend/src/pages/Home.tsx frontend/src/pages/Home.test.tsx
git commit -m "feat: add hero gradient helper and Home page (#120)"
```

---

### Task 5: Relocate the stats table view into Players.tsx

**Files:**
- Create: `frontend/src/pages/Players.tsx`
- Create: `frontend/src/pages/Players.test.tsx` (relocated from `frontend/src/App.test.tsx`)
- Delete: `frontend/src/App.test.tsx` (superseded by `Players.test.tsx` + the new shell test in Task 7)

**Interfaces:**
- Consumes: `Toolbar`, `PlayerTable`, `PlayerProfilePanel`, `Alert`/`AlertDescription`/`AlertTitle`, `Button`, `Skeleton`, `matchesQuery`, `Team`/`Player`/`PlayerStats`/`SortDirection` types — all unchanged from their current `App.tsx` imports.
- Produces: `export default function Players()` — same behavior as the current `App` component, just renamed and relocated. Reads `--header-height` (written by `Header`, Task 6) via CSS `var(...)` with a `0px` fallback, so this task doesn't depend on Task 6 being done first.

- [ ] **Step 1: Create Players.tsx with the moved body and updated height calc**

```tsx
// frontend/src/pages/Players.tsx
import { useEffect, useMemo, useState } from "react";
import { Toolbar, type ToolbarFilters } from "@/components/Toolbar";
import { PlayerTable } from "@/components/PlayerTable";
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { matchesQuery } from "@/lib/search";
import type { Team, Player, PlayerStats, SortDirection } from "@/lib/types";

type FetchState<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

function seasonsKey(seasons: string[]): string {
  return seasons.includes("all") ? "all" : [...seasons].sort().join(",");
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request to ${url} failed (${res.status})`);
  return res.json() as Promise<T>;
}

export default function Players() {
  const [teamsState, setTeamsState] = useState<FetchState<Team[]>>({ status: "loading" });
  const [playersState, setPlayersState] = useState<FetchState<Player[]>>({ status: "loading" });
  const [statsCache, setStatsCache] = useState<Record<string, PlayerStats[]>>({});
  const [statsError, setStatsError] = useState<string | null>(null);

  const [filters, setFilters] = useState<ToolbarFilters>({
    search: "",
    team: "",
    positions: new Set(),
    statMins: { gp: null, goals: null, assists: null, points: null },
  });
  const [seasons, setSeasons] = useState<string[]>(["20252026"]);
  const [sortKey, setSortKey] = useState("points");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);

  function loadTeams() {
    setTeamsState({ status: "loading" });
    fetchJson<Team[]>("/api/teams")
      .then((data) => setTeamsState({ status: "ready", data }))
      .catch((err) => setTeamsState({ status: "error", message: err.message }));
  }

  function loadPlayers() {
    setPlayersState({ status: "loading" });
    fetchJson<Player[]>("/api/players")
      .then((data) => setPlayersState({ status: "ready", data }))
      .catch((err) => setPlayersState({ status: "error", message: err.message }));
  }

  function loadStats(seasonList: string[]) {
    const key = seasonsKey(seasonList);
    if (statsCache[key]) return;
    setStatsError(null);
    fetchJson<PlayerStats[]>(`/api/players/stats?seasons=${seasonList.join(",")}`)
      .then((data) => setStatsCache((prev) => ({ ...prev, [key]: data })))
      .catch((err) => setStatsError(err.message));
  }

  useEffect(loadTeams, []);
  useEffect(loadPlayers, []);
  useEffect(() => loadStats(seasons), [seasons]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    function updateToolbarHeight() {
      const toolbar = document.querySelector("[data-toolbar]");
      if (toolbar) {
        document.documentElement.style.setProperty(
          "--toolbar-height",
          `${toolbar.getBoundingClientRect().height}px`
        );
      }
    }
    updateToolbarHeight();
    window.addEventListener("resize", updateToolbarHeight);
    return () => window.removeEventListener("resize", updateToolbarHeight);
  }, [filters, seasons]);

  const rows = useMemo(() => {
    if (playersState.status !== "ready") return [];
    const stats = statsCache[seasonsKey(seasons)] ?? [];
    let filtered = stats;
    if (filters.team) filtered = filtered.filter((p) => p.team_abbrev === filters.team);
    if (filters.positions.size > 0) {
      filtered = filtered.filter((p) => filters.positions.has(p.position_code));
    }
    if (filters.search) filtered = filtered.filter((p) => matchesQuery(p, filters.search));
    const { gp, goals, assists, points } = filters.statMins;
    if (gp != null) filtered = filtered.filter((p) => (p.gp ?? 0) >= gp);
    if (goals != null) filtered = filtered.filter((p) => (p.goals ?? 0) >= goals);
    if (assists != null) filtered = filtered.filter((p) => (p.assists ?? 0) >= assists);
    if (points != null) filtered = filtered.filter((p) => (p.points ?? 0) >= points);

    const sorted = [...filtered].sort((a, b) => {
      const va = (a as unknown as Record<string, unknown>)[sortKey];
      const vb = (b as unknown as Record<string, unknown>)[sortKey];
      const isNum = typeof va === "number" || typeof vb === "number";
      if (isNum) {
        const na = va == null ? -Infinity : Number(va);
        const nb = vb == null ? -Infinity : Number(vb);
        return sortDir === "asc" ? na - nb : nb - na;
      }
      const sa = String(va ?? "").toLowerCase();
      const sb = String(vb ?? "").toLowerCase();
      if (sa < sb) return sortDir === "asc" ? -1 : 1;
      if (sa > sb) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [playersState, statsCache, seasons, filters, sortKey, sortDir]);

  function handleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  function handleSelectSuggestion(player: Player) {
    setFilters({
      search: "",
      team: "",
      positions: new Set(),
      statMins: { gp: null, goals: null, assists: null, points: null },
    });
    requestAnimationFrame(() => {
      const row = document.querySelector(`[data-player-id="${player.player_id}"]`);
      if (!row) return;
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      row.classList.add("row-highlight");
      setTimeout(() => row.classList.remove("row-highlight"), 1500);
    });
  }

  const totalCount = statsCache[seasonsKey(seasons)]?.length ?? 0;

  if (teamsState.status === "error") {
    return (
      <Alert variant="destructive" className="m-4">
        <AlertTitle>Failed to load teams</AlertTitle>
        <AlertDescription>{teamsState.message}</AlertDescription>
        <Button onClick={loadTeams} className="mt-2">Retry</Button>
      </Alert>
    );
  }

  if (playersState.status === "error") {
    return (
      <Alert variant="destructive" className="m-4">
        <AlertTitle>Failed to load players</AlertTitle>
        <AlertDescription>{playersState.message}</AlertDescription>
        <Button onClick={loadPlayers} className="mt-2">Retry</Button>
      </Alert>
    );
  }

  if (teamsState.status === "loading" || playersState.status === "loading") {
    return (
      <div className="space-y-2 p-4">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }

  return (
    <div>
      <Toolbar
        teams={teamsState.data}
        players={playersState.data}
        filters={filters}
        onFiltersChange={setFilters}
        seasons={seasons}
        onSeasonsChange={setSeasons}
        count={{ shown: rows.length, total: totalCount }}
        onSelectSuggestion={handleSelectSuggestion}
      />
      {statsError ? (
        <Alert variant="destructive" className="m-4">
          <AlertTitle>Failed to load stats</AlertTitle>
          <AlertDescription>{statsError}</AlertDescription>
          <Button onClick={() => loadStats(seasons)} className="mt-2">Retry</Button>
        </Alert>
      ) : (
        <div
          data-testid="table-wrap"
          className="overflow-auto"
          style={{
            height:
              "max(200px, calc(100vh - var(--toolbar-height, 57px) - var(--header-height, 0px)))",
          }}
        >
          <PlayerTable
            rows={rows}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={handleSort}
            onOpenProfile={setProfilePlayerId}
          />
        </div>
      )}

      {profilePlayerId !== null && (
        <PlayerProfilePanel
          open={profilePlayerId !== null}
          playerId={profilePlayerId}
          bio={
            playersState.status === "ready"
              ? playersState.data.find((p) => p.player_id === profilePlayerId)
              : undefined
          }
          stats={rows.find((r) => r.player_id === profilePlayerId)}
          onOpenChange={(open) => {
            if (!open) setProfilePlayerId(null);
          }}
        />
      )}
    </div>
  );
}
```

Note: the outer `min-h-screen bg-background text-foreground` wrapper div from the original `App.tsx` is dropped here — that responsibility moves to the new `App.tsx` shell in Task 7, which wraps `<Header/>` and `<Outlet/>` together.

- [ ] **Step 2: Create Players.test.tsx (relocated from App.test.tsx, updated)**

```tsx
// frontend/src/pages/Players.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Players from "./Players";
import { MOCK_TEAMS, MOCK_PLAYERS, MOCK_STATS } from "@/lib/mock-data";

function mockFetchOnce(url: string) {
  if (url.includes("/api/teams")) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_TEAMS) } as Response);
  }
  if (url.includes("/api/players/stats")) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_STATS) } as Response);
  }
  if (url.includes("/api/players")) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_PLAYERS) } as Response);
  }
  return Promise.reject(new Error(`unexpected url: ${url}`));
}

function renderPlayers() {
  return render(
    <MemoryRouter initialEntries={["/players"]}>
      <Players />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url: string) => mockFetchOnce(url)));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Players", () => {
  it("loads teams, players, and default-season stats, then renders the table", async () => {
    renderPlayers();
    expect(await screen.findByText("MacKinnon")).toBeInTheDocument();
  });

  it("shows an error alert with a retry button when the players fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.includes("/api/players") && !url.includes("stats")
          ? Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)
          : mockFetchOnce(url)
      )
    );
    renderPlayers();
    expect(await screen.findByText(/failed to load/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("recovers when Retry is clicked and the fetch then succeeds", async () => {
    let shouldFail = true;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/api/players") && !url.includes("stats") && shouldFail) {
          return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response);
        }
        return mockFetchOnce(url);
      })
    );
    renderPlayers();
    await screen.findByText(/failed to load/i);
    shouldFail = false;
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByText("MacKinnon")).toBeInTheDocument());
  });

  it("shows an error alert with a retry button when the teams fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.includes("/api/teams")
          ? Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)
          : mockFetchOnce(url)
      )
    );
    renderPlayers();
    expect(await screen.findByText(/failed to load teams/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows an inline error alert with a retry button when the stats fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.includes("/api/players/stats")
          ? Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)
          : mockFetchOnce(url)
      )
    );
    renderPlayers();
    await screen.findByText("NHL Players");
    expect(await screen.findByText(/failed to load stats/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("narrows rows when a search query is typed", async () => {
    renderPlayers();
    await screen.findByText("MacKinnon");
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "McDavid");
    expect(screen.queryByText("MacKinnon")).not.toBeInTheDocument();
    expect(screen.getByText("McDavid")).toBeInTheDocument();
  });

  it("shows the player count, narrowed when a filter is active", async () => {
    renderPlayers();
    await screen.findByText("MacKinnon");
    expect(screen.getByText("3 players")).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "McDavid");
    expect(screen.getByText("1 of 3 players")).toBeInTheDocument();
  });

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

  it("wraps the table in a single bounded-height scroll container sized for the sticky toolbar and header (bug-008 regression guard)", async () => {
    renderPlayers();
    await screen.findByText("MacKinnon");
    const wrap = document.querySelector('[data-testid="table-wrap"]');
    expect(wrap).not.toBeNull();
    const style = wrap!.getAttribute("style") || "";
    expect(style).toMatch(/--toolbar-height/);
    expect(style).toMatch(/--header-height/);
    expect(wrap).toHaveClass("overflow-auto");
  });

  it("opens the profile panel with merged bio and stats data when a row is clicked", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/advanced")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                player_id: 1, season_id: "20252026", strength_states: {}, trend: [], pdo: null,
              }),
          } as Response);
        }
        return mockFetchOnce(url);
      })
    );
    renderPlayers();
    await screen.findByText("MacKinnon");

    const row = document.querySelector('[data-player-id="1"]')!;
    await userEvent.click(row);

    expect(await screen.findByText("Nathan MacKinnon")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Delete the old App.test.tsx**

```bash
git rm frontend/src/App.test.tsx
```

- [ ] **Step 4: Run the new test file**

Run: `cd frontend && npx vitest run src/pages/Players.test.tsx`
Expected: PASS (9 tests). `App.tsx` still exists unchanged at this point (Task 7 rewrites it), so this file just adds a second, currently-duplicate rendering path — that's expected and temporary until Task 7.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Players.tsx frontend/src/pages/Players.test.tsx
git commit -m "refactor: relocate stats table view to pages/Players.tsx (#119)"
```

---

### Task 6: Header component

**Files:**
- Create: `frontend/src/components/Header.tsx`
- Create: `frontend/src/components/Header.test.tsx`

**Interfaces:**
- Consumes: `Dialog`, `DialogContent`, `DialogTitle` from `@/components/ui/dialog` (existing); `cn` from `@/lib/utils` (existing); `NavLink` from `react-router-dom` (Task 2).
- Produces: `export function Header()`. Writes `--header-height` onto `document.documentElement.style`, mirroring how `Players.tsx` already writes `--toolbar-height` (same `data-*` + `ResizeObserver`-free `resize`-listener pattern).

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/Header.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Header } from "./Header";

function renderHeader(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Header />
    </MemoryRouter>
  );
}

describe("Header", () => {
  it("renders a nav link for every top-level page", () => {
    renderHeader();
    for (const label of ["Home", "Players", "Teams", "Top Players", "Betting"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it("marks the active route's link", () => {
    renderHeader("/players");
    const [playersLink] = screen.getAllByText("Players");
    expect(playersLink).toHaveClass("text-foreground");
  });

  it("opens the mobile menu when the hamburger button is clicked", async () => {
    renderHeader();
    expect(screen.queryByText("Menu")).not.toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Open menu"));
    expect(await screen.findByText("Menu")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/Header.test.tsx`
Expected: FAIL — `Failed to resolve import "./Header"`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/components/Header.tsx
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { MenuIcon } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/players", label: "Players", end: false },
  { to: "/teams", label: "Teams", end: false },
  { to: "/top-players", label: "Top Players", end: false },
  { to: "/betting", label: "Betting", end: false },
] as const;

function navLinkClass({ isActive }: { isActive: boolean }) {
  return cn(
    "text-sm font-medium transition-colors hover:text-foreground",
    isActive ? "text-foreground" : "text-muted-foreground"
  );
}

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    function updateHeaderHeight() {
      const header = document.querySelector("[data-header]");
      if (header) {
        document.documentElement.style.setProperty(
          "--header-height",
          `${header.getBoundingClientRect().height}px`
        );
      }
    }
    updateHeaderHeight();
    window.addEventListener("resize", updateHeaderHeight);
    return () => window.removeEventListener("resize", updateHeaderHeight);
  }, []);

  return (
    <header
      data-header
      className="sticky top-0 z-40 flex items-center justify-between border-b border-border bg-card px-4 py-3"
    >
      <span className="text-base font-semibold">NHL Stats</span>

      <nav className="hidden items-center gap-6 md:flex">
        {NAV_LINKS.map(({ to, label, end }) => (
          <NavLink key={to} to={to} end={end} className={navLinkClass}>
            {label}
          </NavLink>
        ))}
      </nav>

      <button
        type="button"
        aria-label="Open menu"
        className="md:hidden"
        onClick={() => setMobileOpen(true)}
      >
        <MenuIcon />
      </button>

      <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
        <DialogContent>
          <DialogTitle>Menu</DialogTitle>
          <nav className="flex flex-col gap-4 pt-2">
            {NAV_LINKS.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={navLinkClass}
                onClick={() => setMobileOpen(false)}
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </DialogContent>
      </Dialog>
    </header>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/Header.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Header.tsx frontend/src/components/Header.test.tsx
git commit -m "feat: add sticky Header with active-route nav and mobile menu (#119)"
```

---

### Task 7: Wire up routing — App shell + main.tsx

**Files:**
- Modify: `frontend/src/App.tsx` (full rewrite)
- Modify: `frontend/src/main.tsx`
- Create: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `Header` (Task 6), `Home` (Task 4), `Players` (Task 5), `PlaceholderPage` (Task 3), `Outlet`/`BrowserRouter`/`Routes`/`Route`/`Navigate` from `react-router-dom` (Task 2).
- Produces: `export default function App()` — layout-only, no page-specific logic.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/App.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import App from "./App";

function renderApp(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<App />}>
          <Route index element={<div>home content</div>} />
          <Route path="players" element={<div>players content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("App shell", () => {
  it("renders the header brand alongside the matched route's content", () => {
    renderApp("/");
    expect(screen.getByText("NHL Stats")).toBeInTheDocument();
    expect(screen.getByText("home content")).toBeInTheDocument();
  });

  it("renders a different route's content via the Outlet", () => {
    renderApp("/players");
    expect(screen.getByText("players content")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/App.test.tsx`
Expected: FAIL — `App` still renders the old toolbar/table content directly, not a `Header` + `Outlet` shell, so `screen.getByText("home content")` won't be found.

- [ ] **Step 3: Rewrite App.tsx as the shell**

```tsx
// frontend/src/App.tsx
import { Outlet } from "react-router-dom";
import { Header } from "@/components/Header";

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <Outlet />
    </div>
  );
}
```

- [ ] **Step 4: Wire the router in main.tsx**

```tsx
// frontend/src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import App from "./App";
import Home from "./pages/Home";
import Players from "./pages/Players";
import PlaceholderPage from "./pages/PlaceholderPage";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<Home />} />
          <Route path="players" element={<Players />} />
          <Route path="teams" element={<PlaceholderPage title="Teams" />} />
          <Route path="top-players" element={<PlaceholderPage title="Top Players" />} />
          <Route path="betting" element={<PlaceholderPage title="Betting" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>
);
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/App.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the full frontend suite**

Run: `cd frontend && npm test`
Expected: all tests PASS — `Players.test.tsx` (9), `Header.test.tsx` (3), `Home.test.tsx` (2), `PlaceholderPage.test.tsx` (1), `heroGradient.test.ts` (1), `App.test.tsx` (2), plus every pre-existing suite untouched by this plan (`PlayerTable`, `PlayerProfilePanel`, `Toolbar`, etc.).

- [ ] **Step 7: Manual smoke check**

Run: `cd frontend && npm run dev` (and `python app.py` in a second terminal for the API), then in a browser:
- Visit `/` → hero renders, header sticky on scroll.
- Click "Players" in the nav → table renders, no layout gap/overlap between header, toolbar, and table.
- Resize to a narrow (mobile) width → nav collapses to a hamburger; opening it shows all 5 links; clicking one navigates and closes the menu.
- Hard-refresh on `/players`, `/teams`, `/betting` → each loads correctly (no 404), confirming Task 1's Flask fallback works end-to-end with the real router.

- [ ] **Step 8: Run the full backend suite once more (App shell doesn't touch it, but confirms nothing else drifted)**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/main.tsx
git commit -m "feat: wire up react-router with Header/Outlet shell and hero Home route (#119, #120)"
```

---

## Plan Self-Review Notes

- **Spec coverage:** Routing (Task 2, 7), Home hero on `/` (Task 4), Players moved to `/players` (Task 5), Teams/Top Players/Betting placeholders (Task 3, 7), News excluded from nav (Task 6's `NAV_LINKS`, Home's placement comment), sticky Header + `--header-height` calc fix (Task 5 Step 1, Task 6), backend SPA fallback (Task 1), unknown-route redirect (Task 7 Step 4), App.test.tsx relocation (Task 5). All spec sections have a task.
- **Type consistency:** `PlaceholderPage`'s `title: string` prop matches its three call sites in `main.tsx` (`title="Teams"`, `title="Top Players"`, `title="Betting"`). `Header`'s `NAV_LINKS` labels ("Home", "Players", "Teams", "Top Players", "Betting") match the spec's nav scope exactly, in the same order.
- **Pattern verification:** `Header`'s height-reservation effect (Task 6 Step 3) was modeled directly on `Toolbar`'s existing `data-toolbar` + `--toolbar-height` effect (read from `App.tsx:70-83` during grilling) — same `querySelector`/`getBoundingClientRect`/`resize`-listener shape, just a different attribute and CSS var name.
