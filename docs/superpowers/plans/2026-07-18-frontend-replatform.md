# Frontend Replatform (React + Tailwind + shadcn/ui) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vanilla HTML/CSS/JS player table (`templates/index.html` + `static/js/search.js`) with a React + TypeScript SPA built on Tailwind v4 + shadcn/ui, preserving every existing filter/sort/search behavior exactly, fixing the one latent bug (unhandled fetch failures), and wiring Vitest into CI from day one.

**Architecture:** `app.py`'s three JSON routes are untouched — this is frontend-only. A new `frontend/` directory (Vite + React + TS) builds to `static/dist/`, served by a minimal Flask shell. Filter/sort state lives in `App.tsx`; data is fetched once and cached client-side (same pattern as today, no React Query). shadcn primitives (`Command`, `Popover`, `ToggleGroup`, `Table`, `Badge`, `Skeleton`, `Alert`) replace the hand-rolled CSS/vanilla-JS equivalents.

**Tech Stack:** React 19, TypeScript 5, Vite 6, Tailwind CSS v4 (`@tailwindcss/vite`), shadcn/ui (Radix UI primitives), Vitest 3 + React Testing Library, Node 22 LTS, npm.

## Global Constraints

- **No backend changes.** `app.py` and its three routes (`/api/teams`, `/api/players`, `/api/players/stats`) are the frozen contract every task builds against. Never modify `app.py` in this plan.
- **Fetch-once, filter-client-side.** No React Query, no server-side pagination, no new data-fetching library — matches the existing `.wolf/cerebrum.md` (2026-07-02) decision, still valid at ~705 rows.
- **No runtime response validation.** Plain TypeScript interfaces (`lib/types.ts`) only — no Zod/io-ts.
- **Dark-only theme.** shadcn's standard dual-palette (light+dark) CSS-variable setup stays wired up (for future `npx shadcn add` compatibility), but `<html>` hard-codes the `dark` class — never toggled.
- **npm only**, Node 22 LTS pinned explicitly in CI (`actions/setup-node`), `frontend/package-lock.json` committed.
- **Fetch mocking in tests**: plain `vi.fn()` / `vi.stubGlobal('fetch', ...)` with canned fixture JSON. No MSW.
- **No new dependencies beyond what each task lists.** No icon library beyond shadcn's `lucide-react`, no state-management library, no CSS-in-JS.
- **Four-phase rollout, each its own branch/PR:** Phase 1 (Tasks 1-4) scaffold, Phase 2 (Tasks 5-11) toolbar components against mock data, Phase 3 (Tasks 12-15) real data + error handling, Phase 4 (Tasks 16-17) cutover. The old vanilla app stays exactly as-is and is what Flask actually serves until Task 16 — Phases 1-3 are additive only, never touching `templates/index.html`, `static/js/search.js`, or `tests/js/search.test.js`.
- **Every ported behavior must match today's exactly**: the 10 existing `tests/js/search.test.js` cases, the season-multi-select mutual-exclusivity rule, the sticky-header bounded-scroll-container technique (`bug-008` fix, `.wolf/buglog.json`), and the goalie-vs-skater column set.

---

## Phase 1: Scaffold

### Task 1: Vite + React + TypeScript project init

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx` (placeholder)
- Create: `frontend/src/vite-env.d.ts`
- Modify: `/.gitignore` (add `node_modules/`; `static/dist/` is already covered by the existing generic `dist/` rule)

**Interfaces:**
- Produces: `frontend/` npm project buildable via `npm run build` (outputs to `../static/dist/`) and runnable via `npm run dev` (Vite dev server, default port 5173).

- [ ] **Step 1: Scaffold the Vite React-TS template**

Run:
```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
npm create vite@latest frontend -- --template react-ts
```
Expected: creates `frontend/` with the standard Vite React-TS template (`package.json`, `tsconfig.json`, `src/main.tsx`, `src/App.tsx`, `index.html`, `vite.config.ts`).

- [ ] **Step 2: Point the build output at `static/dist/` and configure the dev proxy**

Replace `frontend/vite.config.ts`:
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        assetFileNames: "app[extname]",
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:5099",
    },
  },
});
```

- [ ] **Step 3: Replace `frontend/index.html`'s shell**

```html
<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NHL Players</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```
Note the hard-coded `class="dark"` on `<html>` — the app is always dark, never toggled (per Global Constraints).

- [ ] **Step 4: Replace `frontend/src/main.tsx`**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 5: Replace `frontend/src/App.tsx` with a placeholder**

```tsx
export default function App() {
  return <div>NHL Players — replatform in progress</div>;
}
```

- [ ] **Step 6: Update `.gitignore`**

Add to `/.gitignore` (repo root, alongside the existing `.venv/`/`venv/`/`env/` entries):
```
node_modules/
```
(`static/dist/` doesn't need a new entry — the existing generic `dist/` rule already matches it at any depth.)

- [ ] **Step 7: Verify the dev server runs**

Run:
```bash
cd frontend && npm run dev
```
Expected: Vite dev server starts on `http://localhost:5173/`, loading the placeholder page with no console errors. Stop with Ctrl+C.

- [ ] **Step 8: Verify the production build runs**

Run:
```bash
cd frontend && npm run build
```
Expected: exits 0, produces `static/dist/app.js` and `static/dist/app.css` (or `static/dist/app[extname]` variants) in the repo root's `static/dist/`.

- [ ] **Step 9: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts \
  frontend/tsconfig*.json frontend/index.html frontend/src/main.tsx frontend/src/App.tsx \
  frontend/src/vite-env.d.ts .gitignore
git commit -m "feat: scaffold Vite + React + TypeScript frontend"
```

---

### Task 2: Tailwind v4 + shadcn/ui init

**Files:**
- Modify: `frontend/vite.config.ts` (add Tailwind plugin)
- Create: `frontend/src/index.css`
- Create: `frontend/src/lib/utils.ts` (shadcn's `cn()` helper)
- Create: `frontend/components.json`
- Modify: `frontend/tsconfig.json`, `frontend/tsconfig.app.json` (path alias `@/*` -> `src/*`)

**Interfaces:**
- Produces: `cn(...)` from `frontend/src/lib/utils.ts` — used by every shadcn component generated from here on.
- Produces: working `npx shadcn@latest add <component>` in `frontend/` (requires `components.json` + the path alias below).

- [ ] **Step 1: Install Tailwind v4 and the Vite plugin**

```bash
cd frontend
npm install tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: Wire the Tailwind Vite plugin**

Update `frontend/vite.config.ts` (from Task 1):
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        assetFileNames: "app[extname]",
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:5099",
    },
  },
});
```

- [ ] **Step 3: Add the path alias to TypeScript config**

In `frontend/tsconfig.json`'s `compilerOptions` (and `tsconfig.app.json` if Vite's template split them):
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

- [ ] **Step 4: Create `frontend/src/index.css`**

```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

:root {
  --radius: 0.625rem;
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  --border: oklch(0.922 0 0);
}

.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  --card: oklch(0.205 0 0);
  --card-foreground: oklch(0.985 0 0);
  --primary: oklch(0.985 0 0);
  --primary-foreground: oklch(0.205 0 0);
  --border: oklch(1 0 0 / 10%);
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-border: var(--border);
  --radius-lg: var(--radius);
}

body {
  @apply bg-background text-foreground;
}
```
This defines both palettes (light + dark) so future `npx shadcn add` output stays compatible, per the Global Constraints — only `.dark` is ever actually applied, hard-coded on `<html>` from Task 1.

- [ ] **Step 5: Run shadcn init**

```bash
npx shadcn@latest init -d
```
Expected: creates `frontend/components.json` and `frontend/src/lib/utils.ts` (the `cn()` helper combining `clsx` + `tailwind-merge`), installs `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`. Answer/flag prompts to keep `src/index.css` as the CSS entry point and `@/*` as the alias (already configured in Steps 3-4).

- [ ] **Step 6: Verify `cn()` exists and the build still succeeds**

Run:
```bash
cat frontend/src/lib/utils.ts    # expect an exported `cn(...)` function
cd frontend && npm run build
```
Expected: build exits 0 with no Tailwind/PostCSS errors.

- [ ] **Step 7: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts \
  frontend/tsconfig*.json frontend/components.json frontend/src/index.css frontend/src/lib/utils.ts
git commit -m "feat: add Tailwind v4 + shadcn/ui init (dark-only theme)"
```

---

### Task 3: CI job for the frontend

**Files:**
- Modify: `.github/workflows/ci.yml` (add a `frontend` job)
- Create: `frontend/.nvmrc`

**Interfaces:**
- Produces: a `frontend` CI job that fails the PR check if `npm run build` fails (Vitest wiring lands in Task 5, this job runs `npm run build` only until then).

- [ ] **Step 1: Pin the local Node version**

Create `frontend/.nvmrc`:
```
22
```

- [ ] **Step 2: Add the CI job**

In `.github/workflows/ci.yml`, add a sibling job to the existing `check` job:
```yaml
  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build
```

- [ ] **Step 3: Verify locally**

Run:
```bash
cd frontend && npm ci && npm run build
```
Expected: exits 0 (this mirrors exactly what CI will run).

- [ ] **Step 4: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add .github/workflows/ci.yml frontend/.nvmrc
git commit -m "ci: add frontend build job (Node 22, npm)"
```

---

### Task 4: `scripts/dev.sh` + README

**Files:**
- Create: `scripts/dev.sh`
- Modify: `README.md` (setup section)

**Interfaces:**
- Produces: `./scripts/dev.sh` — one command starting both the Flask API and the Vite dev server, cleaning up on Ctrl+C.

- [ ] **Step 1: Write `scripts/dev.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python app.py &
FLASK_PID=$!

cleanup() {
  kill "$FLASK_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd frontend && npm run dev)
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/dev.sh
```

- [ ] **Step 3: Verify it starts both processes and cleans up**

Run:
```bash
./scripts/dev.sh &
DEV_PID=$!
sleep 3
curl -s http://127.0.0.1:5099/api/teams | head -c 100   # expect JSON team data
curl -s http://127.0.0.1:5173/ | head -c 100             # expect Vite's index.html
kill "$DEV_PID"
sleep 1
pgrep -f "python app.py" && echo "FAIL: Flask still running" || echo "OK: Flask cleaned up"
```
Expected: both endpoints respond, and the final line prints `OK: Flask cleaned up`.

- [ ] **Step 4: Update `README.md`**

Add to the setup/running section (after the existing venv/pip steps):
```markdown
### Frontend (React + Vite)

Install once:
```bash
cd frontend && npm install
```

Run both the Flask API and the Vite dev server with one command:
```bash
./scripts/dev.sh
```
This starts Flask on `http://127.0.0.1:5099` and the Vite dev server on
`http://localhost:5173` (which proxies `/api/*` to Flask). Ctrl+C stops both.

For a production-style run, build the frontend once and let Flask serve
everything:
```bash
cd frontend && npm run build
cd .. && python app.py
```
```

- [ ] **Step 5: Commit**

```bash
git add scripts/dev.sh README.md
git commit -m "feat: add scripts/dev.sh one-command dev workflow"
```

**End of Phase 1 — open PR, confirm CI green, merge before starting Phase 2.**

---

## Phase 2: Toolbar components (against mock data)

### Task 5: Port `lib/search.ts` + Vitest setup

**Files:**
- Create: `frontend/src/lib/search.ts`
- Create: `frontend/src/lib/search.test.ts`
- Create: `frontend/vitest.config.ts`
- Modify: `frontend/package.json` (add `test` script)
- Modify: `.github/workflows/ci.yml` (add `npm test` to the `frontend` job)

**Interfaces:**
- Produces: `tokenize(query: string): string[]`, `playerSearchText(p: Player): string`, `matchesQuery(p: Player, query: string): boolean` from `frontend/src/lib/search.ts` — consumed by Task 11 (`Toolbar`)'s search box.

- [ ] **Step 1: Install Vitest + React Testing Library**

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

- [ ] **Step 2: Create `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    globals: true,
  },
});
```

Create `frontend/src/test-setup.ts`:
```typescript
import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement scrollIntoView — stub it so components that call it
// (e.g. the search-suggestion-click row-scroll behavior, Task 13) don't throw.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
```

- [ ] **Step 3: Add the `test` script**

In `frontend/package.json`'s `"scripts"`:
```json
"test": "vitest run"
```

- [ ] **Step 4: Write the failing test file (ports all 10 cases from `tests/js/search.test.js`)**

`frontend/src/lib/search.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { tokenize, playerSearchText, matchesQuery } from "./search";

const mackinnon = {
  first_name: "Nathan",
  last_name: "MacKinnon",
  team_name: "Avalanche",
  team_abbrev: "COL",
  team_place_name: "Colorado",
};

describe("tokenize", () => {
  it("lowercases, trims, splits on whitespace, and drops empties", () => {
    expect(tokenize("  Nathan   MacKinnon ")).toEqual(["nathan", "mackinnon"]);
    expect(tokenize("")).toEqual([]);
    expect(tokenize(undefined)).toEqual([]);
  });
});

describe("playerSearchText", () => {
  it("concatenates name and team fields, lowercased", () => {
    expect(playerSearchText(mackinnon)).toBe("nathan mackinnon avalanche col colorado");
  });

  it("skips missing fields without leaving gaps", () => {
    expect(playerSearchText({ first_name: "Nathan", last_name: "MacKinnon" })).toBe(
      "nathan mackinnon"
    );
  });
});

describe("matchesQuery", () => {
  it("matches on last name alone", () => {
    expect(matchesQuery(mackinnon, "MacKinnon")).toBe(true);
  });

  it("matches full name in forward order", () => {
    expect(matchesQuery(mackinnon, "Nathan MacKinnon")).toBe(true);
  });

  it("matches full name in reversed order", () => {
    expect(matchesQuery(mackinnon, "MacKinnon Nathan")).toBe(true);
  });

  it("returns false for a non-matching query", () => {
    expect(matchesQuery(mackinnon, "Connor McDavid")).toBe(false);
  });

  it("returns false for an empty query", () => {
    expect(matchesQuery(mackinnon, "")).toBe(false);
  });

  it("matches team short name", () => {
    expect(matchesQuery(mackinnon, "Avalanche")).toBe(true);
  });

  it("matches team abbreviation", () => {
    expect(matchesQuery(mackinnon, "COL")).toBe(true);
  });

  it("matches team place name", () => {
    expect(matchesQuery(mackinnon, "Colorado")).toBe(true);
  });

  it("matches multi-token team name", () => {
    expect(matchesQuery(mackinnon, "Colorado Avalanche")).toBe(true);
  });

  it("does not cross-match a name token against an unrelated team", () => {
    const otherTeamPlayer = {
      first_name: "Connor",
      last_name: "McDavid",
      team_name: "Oilers",
      team_abbrev: "EDM",
      team_place_name: "Edmonton",
    };
    expect(matchesQuery(otherTeamPlayer, "Colorado Avalanche")).toBe(false);
  });
});
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL — `Cannot find module './search'`.

- [ ] **Step 6: Implement `frontend/src/lib/search.ts`**

```typescript
export interface SearchablePlayer {
  first_name?: string | null;
  last_name?: string | null;
  team_name?: string | null;
  team_abbrev?: string | null;
  team_place_name?: string | null;
}

export function tokenize(query: string | undefined): string[] {
  return (query || "").toLowerCase().trim().split(/\s+/).filter(Boolean);
}

export function playerSearchText(p: SearchablePlayer): string {
  return [p.first_name, p.last_name, p.team_name, p.team_abbrev, p.team_place_name]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function matchesQuery(p: SearchablePlayer, query: string): boolean {
  const tokens = tokenize(query);
  if (tokens.length === 0) return false;
  const haystack = playerSearchText(p);
  return tokens.every((t) => haystack.includes(t));
}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd frontend && npm test`
Expected: PASS — 10 tests passing.

- [ ] **Step 8: Wire `npm test` into CI**

In `.github/workflows/ci.yml`'s `frontend` job (from Task 3), add before the `Build` step:
```yaml
      - name: Tests
        run: npm test
```

- [ ] **Step 9: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/lib/search.ts frontend/src/lib/search.test.ts frontend/vitest.config.ts \
  frontend/src/test-setup.ts frontend/package.json frontend/package-lock.json .github/workflows/ci.yml
git commit -m "test: port search matching logic to TypeScript + Vitest, wire into CI"
```

---

### Task 6: `lib/types.ts` + dev mock fixtures

**Files:**
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/mock-data.ts`

**Interfaces:**
- Produces: `Player`, `PlayerStats`, `Team` interfaces — consumed by every component task from here on.
- Produces: `MOCK_TEAMS: Team[]`, `MOCK_PLAYERS: Player[]`, `MOCK_STATS: PlayerStats[]` — consumed by Tasks 7-11's component-level tests and Phase 2's mock-data-driven `Toolbar`.

- [ ] **Step 1: Write `frontend/src/lib/types.ts`**

```typescript
export interface Team {
  abbrev: string;
  common_name: string;
}

export interface Player {
  player_id: number;
  sweater_number: number | null;
  first_name: string;
  last_name: string;
  position_code: string;
  shoots_catches: string;
  height: string;
  weight_pounds: number | null;
  birth_date: string;
  birth_country: string;
  team_abbrev: string;
  team_name: string;
  team_place_name: string;
}

export interface PlayerStats {
  player_id: number;
  first_name: string;
  last_name: string;
  position_code: string;
  team_abbrev: string;
  team_name: string;
  gp: number | null;
  goals: number | null;
  assists: number | null;
  points: number | null;
  plus_minus: number | null;
  pim: number | null;
  pp_goals: number | null;
  sh_goals: number | null;
  shots: number | null;
  shooting_pct: number | null;
  avg_toi: string;
  wins: number | null;
  losses: number | null;
  ot_losses: number | null;
  shutouts: number | null;
  save_pct: number | null;
  gaa: number | null;
}

export type SortDirection = "asc" | "desc";

export interface StatMins {
  gp: number | null;
  goals: number | null;
  assists: number | null;
  points: number | null;
}
```
Field names/types mirror `app.py`'s `_fetch_players` (lines 74-90) and `api_players_stats` (lines 181-207) response dicts exactly — this is the frontend's contract with the frozen backend.

- [ ] **Step 2: Write `frontend/src/lib/mock-data.ts`**

```typescript
import type { Team, Player, PlayerStats } from "./types";

export const MOCK_TEAMS: Team[] = [
  { abbrev: "COL", common_name: "Colorado Avalanche" },
  { abbrev: "EDM", common_name: "Edmonton Oilers" },
  { abbrev: "TOR", common_name: "Toronto Maple Leafs" },
];

export const MOCK_PLAYERS: Player[] = [
  {
    player_id: 1, sweater_number: 29, first_name: "Nathan", last_name: "MacKinnon",
    position_code: "C", shoots_catches: "R", height: "6'0\"", weight_pounds: 181,
    birth_date: "1995-09-01", birth_country: "CAN",
    team_abbrev: "COL", team_name: "Avalanche", team_place_name: "Colorado",
  },
  {
    player_id: 2, sweater_number: 97, first_name: "Connor", last_name: "McDavid",
    position_code: "C", shoots_catches: "L", height: "6'1\"", weight_pounds: 193,
    birth_date: "1997-01-13", birth_country: "CAN",
    team_abbrev: "EDM", team_name: "Oilers", team_place_name: "Edmonton",
  },
  {
    player_id: 3, sweater_number: 31, first_name: "Anthony", last_name: "Stolarz",
    position_code: "G", shoots_catches: "L", height: "6'6\"", weight_pounds: 240,
    birth_date: "1994-01-20", birth_country: "USA",
    team_abbrev: "TOR", team_name: "Maple Leafs", team_place_name: "Toronto",
  },
];

export const MOCK_STATS: PlayerStats[] = [
  {
    player_id: 1, first_name: "Nathan", last_name: "MacKinnon", position_code: "C",
    team_abbrev: "COL", team_name: "Avalanche",
    gp: 82, goals: 44, assists: 84, points: 128, plus_minus: 32, pim: 42,
    pp_goals: 14, sh_goals: 1, shots: 297, shooting_pct: 14.8, avg_toi: "21:17",
    wins: null, losses: null, ot_losses: null, shutouts: null, save_pct: null, gaa: null,
  },
  {
    player_id: 2, first_name: "Connor", last_name: "McDavid", position_code: "C",
    team_abbrev: "EDM", team_name: "Oilers",
    gp: 76, goals: 32, assists: 88, points: 120, plus_minus: 12, pim: 30,
    pp_goals: 8, sh_goals: 2, shots: 246, shooting_pct: 13.0, avg_toi: "21:52",
    wins: null, losses: null, ot_losses: null, shutouts: null, save_pct: null, gaa: null,
  },
  {
    player_id: 3, first_name: "Anthony", last_name: "Stolarz", position_code: "G",
    team_abbrev: "TOR", team_name: "Maple Leafs",
    gp: 41, goals: null, assists: null, points: null, plus_minus: null, pim: 2,
    pp_goals: null, sh_goals: null, shots: null, shooting_pct: null, avg_toi: null as never,
    wins: 24, losses: 10, ot_losses: 4, shutouts: 3, save_pct: 0.918, gaa: 2.14,
  },
];
```

- [ ] **Step 3: Verify the project still builds**

Run: `cd frontend && npm run build`
Expected: exits 0 (pure type/data additions, no behavior to test standalone).

- [ ] **Step 4: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/lib/types.ts frontend/src/lib/mock-data.ts
git commit -m "feat: add Player/PlayerStats/Team types and dev mock fixtures"
```

---

### Task 7: `PositionToggle` component

**Files:**
- Create: `frontend/src/components/PositionToggle.tsx`
- Create: `frontend/src/components/PositionToggle.test.tsx`

**Interfaces:**
- Consumes: none (pure presentational + callback).
- Produces: `PositionToggle({ active: Set<string>, onChange: (next: Set<string>) => void })` — consumed by Task 11 (`Toolbar`).

- [ ] **Step 1: Install the shadcn `toggle-group` component**

```bash
cd frontend
npx shadcn@latest add toggle-group
```
Expected: creates `frontend/src/components/ui/toggle-group.tsx` (+ `toggle.tsx`), installs `@radix-ui/react-toggle-group`.

- [ ] **Step 2: Write the failing test**

`frontend/src/components/PositionToggle.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PositionToggle } from "./PositionToggle";

describe("PositionToggle", () => {
  it("calls onChange with the position added when an inactive toggle is clicked", async () => {
    const onChange = vi.fn();
    render(<PositionToggle active={new Set()} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "C" }));
    expect(onChange).toHaveBeenCalledWith(new Set(["C"]));
  });

  it("calls onChange with the position removed when an active toggle is clicked", async () => {
    const onChange = vi.fn();
    render(<PositionToggle active={new Set(["C", "D"])} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "C" }));
    expect(onChange).toHaveBeenCalledWith(new Set(["D"]));
  });

  it("renders all five position buttons", () => {
    render(<PositionToggle active={new Set()} onChange={() => {}} />);
    ["C", "L", "R", "D", "G"].forEach((pos) => {
      expect(screen.getByRole("button", { name: pos })).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 3: Install `user-event` and run the test to verify it fails**

```bash
cd frontend
npm install -D @testing-library/user-event
npm test -- PositionToggle
```
Expected: FAIL — `Cannot find module './PositionToggle'`.

- [ ] **Step 4: Implement `frontend/src/components/PositionToggle.tsx`**

```tsx
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

const POSITIONS = ["C", "L", "R", "D", "G"] as const;

const POSITION_CLASSES: Record<(typeof POSITIONS)[number], string> = {
  C: "text-green-500 data-[state=on]:bg-green-500 data-[state=on]:text-background",
  L: "text-blue-400 data-[state=on]:bg-blue-400 data-[state=on]:text-background",
  R: "text-sky-300 data-[state=on]:bg-sky-300 data-[state=on]:text-background",
  D: "text-purple-300 data-[state=on]:bg-purple-300 data-[state=on]:text-background",
  G: "text-orange-400 data-[state=on]:bg-orange-400 data-[state=on]:text-background",
};

interface PositionToggleProps {
  active: Set<string>;
  onChange: (next: Set<string>) => void;
}

export function PositionToggle({ active, onChange }: PositionToggleProps) {
  function toggle(pos: string) {
    const next = new Set(active);
    if (next.has(pos)) next.delete(pos);
    else next.add(pos);
    onChange(next);
  }

  return (
    <ToggleGroup type="multiple" value={Array.from(active)}>
      {POSITIONS.map((pos) => (
        <ToggleGroupItem
          key={pos}
          value={pos}
          aria-label={pos}
          onClick={() => toggle(pos)}
          className={POSITION_CLASSES[pos]}
        >
          {pos}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- PositionToggle`
Expected: PASS — 3 tests passing.

- [ ] **Step 6: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/components/ui/toggle-group.tsx frontend/src/components/ui/toggle.tsx \
  frontend/src/components/PositionToggle.tsx frontend/src/components/PositionToggle.test.tsx \
  frontend/package.json frontend/package-lock.json
git commit -m "feat: add PositionToggle component (C/L/R/D/G multi-select)"
```

---

### Task 8: `StatFilters` component

**Files:**
- Create: `frontend/src/components/StatFilters.tsx`
- Create: `frontend/src/components/StatFilters.test.tsx`

**Interfaces:**
- Consumes: `StatMins` from `frontend/src/lib/types.ts` (Task 6).
- Produces: `StatFilters({ value: StatMins, onChange: (next: StatMins) => void })` — consumed by Task 11 (`Toolbar`).

- [ ] **Step 1: Install the shadcn `input` and `label` components**

```bash
cd frontend
npx shadcn@latest add input label
```

- [ ] **Step 2: Write the failing test**

`frontend/src/components/StatFilters.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StatFilters } from "./StatFilters";
import type { StatMins } from "@/lib/types";

const EMPTY: StatMins = { gp: null, goals: null, assists: null, points: null };

describe("StatFilters", () => {
  it("calls onChange with a number when a value is typed", async () => {
    const onChange = vi.fn();
    render(<StatFilters value={EMPTY} onChange={onChange} />);
    await userEvent.type(screen.getByLabelText("GP≥"), "20");
    expect(onChange).toHaveBeenLastCalledWith({ ...EMPTY, gp: 20 });
  });

  it("calls onChange with null when the field is cleared", async () => {
    const onChange = vi.fn();
    render(<StatFilters value={{ ...EMPTY, goals: 10 }} onChange={onChange} />);
    await userEvent.clear(screen.getByLabelText("G≥"));
    expect(onChange).toHaveBeenLastCalledWith({ ...EMPTY, goals: null });
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npm test -- StatFilters`
Expected: FAIL — `Cannot find module './StatFilters'`.

- [ ] **Step 4: Implement `frontend/src/components/StatFilters.tsx`**

```tsx
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { StatMins } from "@/lib/types";

const FIELDS: { key: keyof StatMins; label: string }[] = [
  { key: "gp", label: "GP≥" },
  { key: "goals", label: "G≥" },
  { key: "assists", label: "A≥" },
  { key: "points", label: "Pts≥" },
];

interface StatFiltersProps {
  value: StatMins;
  onChange: (next: StatMins) => void;
}

export function StatFilters({ value, onChange }: StatFiltersProps) {
  return (
    <div className="flex items-center gap-3">
      {FIELDS.map(({ key, label }) => (
        <div key={key} className="flex items-center gap-1.5">
          <Label htmlFor={`stat-${key}`}>{label}</Label>
          <Input
            id={`stat-${key}`}
            type="number"
            min={0}
            className="w-16"
            value={value[key] ?? ""}
            onChange={(e) => {
              const raw = e.target.value;
              onChange({ ...value, [key]: raw === "" ? null : Number(raw) });
            }}
          />
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- StatFilters`
Expected: PASS — 2 tests passing.

- [ ] **Step 6: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/components/ui/input.tsx frontend/src/components/ui/label.tsx \
  frontend/src/components/StatFilters.tsx frontend/src/components/StatFilters.test.tsx \
  frontend/package.json frontend/package-lock.json
git commit -m "feat: add StatFilters component (GP/G/A/Pts minimum inputs)"
```

---

### Task 9: `TeamPicker` component

**Files:**
- Create: `frontend/src/components/TeamPicker.tsx`
- Create: `frontend/src/components/TeamPicker.test.tsx`

**Interfaces:**
- Consumes: `Team` from `frontend/src/lib/types.ts` (Task 6).
- Produces: `TeamPicker({ teams: Team[], active: string, onChange: (abbrev: string) => void })` — consumed by Task 11 (`Toolbar`). `active === ""` means "All Teams".

- [ ] **Step 1: Install the shadcn `popover` and `command` components**

```bash
cd frontend
npx shadcn@latest add popover command
```
Expected: installs `@radix-ui/react-popover` and `cmdk`.

- [ ] **Step 2: Write the failing test**

`frontend/src/components/TeamPicker.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TeamPicker } from "./TeamPicker";
import { MOCK_TEAMS } from "@/lib/mock-data";

describe("TeamPicker", () => {
  it("shows 'All Teams' when no team is active", () => {
    render(<TeamPicker teams={MOCK_TEAMS} active="" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /all teams/i })).toBeInTheDocument();
  });

  it("shows the selected team's name when a team is active", () => {
    render(<TeamPicker teams={MOCK_TEAMS} active="COL" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /colorado avalanche/i })).toBeInTheDocument();
  });

  it("calls onChange with the team abbrev when a team row is clicked", async () => {
    const onChange = vi.fn();
    render(<TeamPicker teams={MOCK_TEAMS} active="" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /all teams/i }));
    await userEvent.click(await screen.findByText("Edmonton Oilers"));
    expect(onChange).toHaveBeenCalledWith("EDM");
  });

  it("calls onChange with an empty string when 'All Teams' is clicked", async () => {
    const onChange = vi.fn();
    render(<TeamPicker teams={MOCK_TEAMS} active="COL" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /colorado avalanche/i }));
    await userEvent.click(await screen.findByText("All Teams"));
    expect(onChange).toHaveBeenCalledWith("");
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npm test -- TeamPicker`
Expected: FAIL — `Cannot find module './TeamPicker'`.

- [ ] **Step 4: Implement `frontend/src/components/TeamPicker.tsx`**

```tsx
import { useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandGroup, CommandItem, CommandList } from "@/components/ui/command";
import type { Team } from "@/lib/types";

function logoUrl(abbrev: string) {
  return `https://assets.nhle.com/logos/nhl/svg/${abbrev}_light.svg`;
}

interface TeamPickerProps {
  teams: Team[];
  active: string;
  onChange: (abbrev: string) => void;
}

export function TeamPicker({ teams, active, onChange }: TeamPickerProps) {
  const [open, setOpen] = useState(false);
  const activeTeam = teams.find((t) => t.abbrev === active);
  const label = activeTeam ? activeTeam.common_name : "All Teams";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex min-w-40 items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm"
        >
          {label}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0">
        <Command>
          <CommandList>
            <CommandGroup>
              <CommandItem
                onSelect={() => {
                  onChange("");
                  setOpen(false);
                }}
              >
                All Teams
              </CommandItem>
              {teams.map((t) => (
                <CommandItem
                  key={t.abbrev}
                  onSelect={() => {
                    onChange(t.abbrev);
                    setOpen(false);
                  }}
                >
                  <img src={logoUrl(t.abbrev)} alt="" className="h-4 w-4" />
                  {t.common_name}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- TeamPicker`
Expected: PASS — 4 tests passing.

- [ ] **Step 6: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/components/ui/popover.tsx frontend/src/components/ui/command.tsx \
  frontend/src/components/TeamPicker.tsx frontend/src/components/TeamPicker.test.tsx \
  frontend/package.json frontend/package-lock.json
git commit -m "feat: add TeamPicker component (logo + name popover)"
```

---

### Task 10: `SeasonPicker` component

**Files:**
- Create: `frontend/src/components/SeasonPicker.tsx`
- Create: `frontend/src/components/SeasonPicker.test.tsx`

**Interfaces:**
- Consumes: none new (uses a local `SEASONS` constant, `Popover`/`Command` from Task 9's install).
- Produces: `SeasonPicker({ active: string[], onChange: (next: string[]) => void })` — consumed by Task 11 (`Toolbar`). `active` is either `["all"]` or a list of specific season IDs; never both.

- [ ] **Step 1: Install the shadcn `checkbox` component**

```bash
cd frontend
npx shadcn@latest add checkbox
```

- [ ] **Step 2: Write the failing test**

`frontend/src/components/SeasonPicker.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SeasonPicker } from "./SeasonPicker";

describe("SeasonPicker", () => {
  it("shows the single season's label when one season is active", () => {
    render(<SeasonPicker active={["20252026"]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "2025–26" })).toBeInTheDocument();
  });

  it("shows 'All Seasons (Career)' when active is ['all']", () => {
    render(<SeasonPicker active={["all"]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /all seasons \(career\)/i })).toBeInTheDocument();
  });

  it("shows a count summary when multiple seasons are active", () => {
    render(<SeasonPicker active={["20252026", "20242025"]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "2 Seasons" })).toBeInTheDocument();
  });

  it("checking 'All Seasons' replaces the active list with ['all']", async () => {
    const onChange = vi.fn();
    render(<SeasonPicker active={["20252026"]} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "2025–26" }));
    await userEvent.click(screen.getByText("All Seasons (Career)"));
    expect(onChange).toHaveBeenCalledWith(["all"]);
  });

  it("checking a specific season while 'all' is active replaces it with just that season", async () => {
    const onChange = vi.fn();
    render(<SeasonPicker active={["all"]} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /all seasons \(career\)/i }));
    await userEvent.click(screen.getByText("2024–25"));
    expect(onChange).toHaveBeenCalledWith(["20242025"]);
  });

  it("unchecking the last remaining season is a no-op", async () => {
    const onChange = vi.fn();
    render(<SeasonPicker active={["20252026"]} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "2025–26" }));
    await userEvent.click(screen.getByText("2025–26", { selector: "span" }));
    expect(onChange).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npm test -- SeasonPicker`
Expected: FAIL — `Cannot find module './SeasonPicker'`.

- [ ] **Step 4: Implement `frontend/src/components/SeasonPicker.tsx`**

```tsx
import { useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";

export const SEASONS = [
  { id: "20252026", label: "2025–26" },
  { id: "20242025", label: "2024–25" },
  { id: "20232024", label: "2023–24" },
  { id: "20222023", label: "2022–23" },
  { id: "20212022", label: "2021–22" },
  { id: "20202021", label: "2020–21" },
];

function summaryLabel(active: string[]): string {
  if (active.includes("all")) return "All Seasons (Career)";
  if (active.length === 1) {
    return SEASONS.find((s) => s.id === active[0])?.label ?? active[0];
  }
  return `${active.length} Seasons`;
}

interface SeasonPickerProps {
  active: string[];
  onChange: (next: string[]) => void;
}

export function SeasonPicker({ active, onChange }: SeasonPickerProps) {
  const [open, setOpen] = useState(false);

  function toggleAll() {
    onChange(active.includes("all") ? ["20252026"] : ["all"]);
  }

  function toggleSeason(id: string) {
    if (active.includes("all")) {
      onChange([id]);
    } else if (active.includes(id)) {
      if (active.length > 1) onChange(active.filter((s) => s !== id));
      // else: no-op — at least one season must always remain selected
    } else {
      onChange([...active, id]);
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex min-w-40 items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm"
        >
          {summaryLabel(active)}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-2">
        <label className="flex items-center gap-2 rounded px-2 py-1.5 text-sm">
          <Checkbox checked={active.includes("all")} onCheckedChange={toggleAll} />
          <span>All Seasons (Career)</span>
        </label>
        {SEASONS.map((s) => (
          <label key={s.id} className="flex items-center gap-2 rounded px-2 py-1.5 text-sm">
            <Checkbox
              checked={active.includes(s.id)}
              onCheckedChange={() => toggleSeason(s.id)}
            />
            <span>{s.label}</span>
          </label>
        ))}
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- SeasonPicker`
Expected: PASS — 6 tests passing.

- [ ] **Step 6: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/components/ui/checkbox.tsx \
  frontend/src/components/SeasonPicker.tsx frontend/src/components/SeasonPicker.test.tsx \
  frontend/package.json frontend/package-lock.json
git commit -m "feat: add SeasonPicker component (multi-select with career-total exclusivity)"
```

---

### Task 11: `Toolbar` composing search + pickers + filters (mock data)

**Files:**
- Create: `frontend/src/components/Toolbar.tsx`
- Create: `frontend/src/components/Toolbar.test.tsx`
- Modify: `frontend/src/App.tsx` (render `Toolbar` against `MOCK_TEAMS`/`MOCK_PLAYERS`)

**Interfaces:**
- Consumes: `PositionToggle` (Task 7), `StatFilters` (Task 8), `TeamPicker` (Task 9), `SeasonPicker` (Task 10), `matchesQuery` (Task 5), `Player`/`Team`/`StatMins` (Task 6).
- Produces: `Toolbar({ teams, players, filters, onFiltersChange, seasons, onSeasonsChange, count, onSelectSuggestion })` where `filters: { search: string; team: string; positions: Set<string>; statMins: StatMins }` and `count: { shown: number; total: number }` — consumed by Task 13 (`App.tsx`'s real-data wiring). `onSelectSuggestion(player: Player)` fires when a suggestion is clicked — Task 13 implements the clear-filters + scroll-to-row behavior; `Toolbar` itself only reports the click.

- [ ] **Step 1: Install the shadcn `input` (already added, Task 8) — no new install needed**

- [ ] **Step 2: Write the failing test**

`frontend/src/components/Toolbar.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toolbar } from "./Toolbar";
import { MOCK_TEAMS, MOCK_PLAYERS } from "@/lib/mock-data";
import type { StatMins } from "@/lib/types";

const EMPTY_MINS: StatMins = { gp: null, goals: null, assists: null, points: null };

function baseProps(overrides = {}) {
  return {
    teams: MOCK_TEAMS,
    players: MOCK_PLAYERS,
    filters: { search: "", team: "", positions: new Set<string>(), statMins: EMPTY_MINS },
    onFiltersChange: vi.fn(),
    seasons: ["20252026"],
    onSeasonsChange: vi.fn(),
    count: { shown: 3, total: 3 },
    onSelectSuggestion: vi.fn(),
    ...overrides,
  };
}

describe("Toolbar", () => {
  it("shows suggestions matching the typed search text", async () => {
    const props = baseProps();
    render(<Toolbar {...props} />);
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "MacKinnon");
    expect(await screen.findByText("Nathan MacKinnon")).toBeInTheDocument();
  });

  it("calls onFiltersChange with updated search text as the user types", async () => {
    const onFiltersChange = vi.fn();
    render(<Toolbar {...baseProps({ onFiltersChange })} />);
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "Mc");
    expect(onFiltersChange).toHaveBeenCalled();
    const lastCall = onFiltersChange.mock.calls.at(-1)![0];
    expect(lastCall.search).toBe("Mc");
  });

  it("renders the position toggle, team picker, season picker, and stat filters", () => {
    render(<Toolbar {...baseProps()} />);
    expect(screen.getByRole("button", { name: "C" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all teams/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "2025–26" })).toBeInTheDocument();
    expect(screen.getByLabelText("GP≥")).toBeInTheDocument();
  });

  it("shows the player count", () => {
    render(<Toolbar {...baseProps({ count: { shown: 2, total: 3 } })} />);
    expect(screen.getByText("2 of 3 players")).toBeInTheDocument();
  });

  it("shows the plain total when no filters narrow the count", () => {
    render(<Toolbar {...baseProps({ count: { shown: 3, total: 3 } })} />);
    expect(screen.getByText("3 players")).toBeInTheDocument();
  });

  it("calls onSelectSuggestion when a suggestion is clicked", async () => {
    const onSelectSuggestion = vi.fn();
    render(<Toolbar {...baseProps({ onSelectSuggestion })} />);
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "MacKinnon");
    await userEvent.click(await screen.findByText("Nathan MacKinnon"));
    expect(onSelectSuggestion).toHaveBeenCalledWith(
      expect.objectContaining({ player_id: 1, last_name: "MacKinnon" })
    );
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npm test -- Toolbar`
Expected: FAIL — `Cannot find module './Toolbar'`.

- [ ] **Step 4: Implement `frontend/src/components/Toolbar.tsx`**

```tsx
import { Input } from "@/components/ui/input";
import { PositionToggle } from "./PositionToggle";
import { StatFilters } from "./StatFilters";
import { TeamPicker } from "./TeamPicker";
import { SeasonPicker } from "./SeasonPicker";
import { matchesQuery } from "@/lib/search";
import type { Player, Team, StatMins } from "@/lib/types";

export interface ToolbarFilters {
  search: string;
  team: string;
  positions: Set<string>;
  statMins: StatMins;
}

export interface PlayerCount {
  shown: number;
  total: number;
}

interface ToolbarProps {
  teams: Team[];
  players: Player[];
  filters: ToolbarFilters;
  onFiltersChange: (next: ToolbarFilters) => void;
  seasons: string[];
  onSeasonsChange: (next: string[]) => void;
  count: PlayerCount;
  onSelectSuggestion: (player: Player) => void;
}

export function Toolbar({
  teams,
  players,
  filters,
  onFiltersChange,
  seasons,
  onSeasonsChange,
  count,
  onSelectSuggestion,
}: ToolbarProps) {
  const suggestions = filters.search
    ? players.filter((p) => matchesQuery(p, filters.search)).slice(0, 8)
    : [];

  return (
    <div className="flex flex-col gap-3 border-b border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-semibold">NHL Players</h1>
        <div className="relative">
          <Input
            placeholder="Search players…"
            value={filters.search}
            onChange={(e) => onFiltersChange({ ...filters, search: e.target.value })}
            className="w-52"
          />
          {suggestions.length > 0 && (
            <div className="absolute top-full z-20 mt-1 max-h-64 w-52 overflow-y-auto rounded-md border border-border bg-card">
              {suggestions.map((p) => (
                <div
                  key={p.player_id}
                  className="cursor-pointer px-3 py-1.5 text-sm hover:bg-accent"
                  onClick={() => onSelectSuggestion(p)}
                >
                  {p.first_name} {p.last_name}
                </div>
              ))}
            </div>
          )}
        </div>
        <TeamPicker
          teams={teams}
          active={filters.team}
          onChange={(team) => onFiltersChange({ ...filters, team })}
        />
        <SeasonPicker active={seasons} onChange={onSeasonsChange} />
        <span className="ml-auto text-sm text-muted-foreground">
          {count.shown === count.total
            ? `${count.total} players`
            : `${count.shown} of ${count.total} players`}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <PositionToggle
          active={filters.positions}
          onChange={(positions) => onFiltersChange({ ...filters, positions })}
        />
        <StatFilters
          value={filters.statMins}
          onChange={(statMins) => onFiltersChange({ ...filters, statMins })}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- Toolbar`
Expected: PASS — 3 tests passing.

- [ ] **Step 6: Wire `Toolbar` into `App.tsx` against mock data**

Replace `frontend/src/App.tsx`:
```tsx
import { useState } from "react";
import { Toolbar, type ToolbarFilters } from "@/components/Toolbar";
import { MOCK_TEAMS, MOCK_PLAYERS } from "@/lib/mock-data";

export default function App() {
  const [filters, setFilters] = useState<ToolbarFilters>({
    search: "",
    team: "",
    positions: new Set(),
    statMins: { gp: null, goals: null, assists: null, points: null },
  });
  const [seasons, setSeasons] = useState<string[]>(["20252026"]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Toolbar
        teams={MOCK_TEAMS}
        players={MOCK_PLAYERS}
        filters={filters}
        onFiltersChange={setFilters}
        seasons={seasons}
        onSeasonsChange={setSeasons}
        count={{ shown: MOCK_PLAYERS.length, total: MOCK_PLAYERS.length }}
        onSelectSuggestion={() => {}}
      />
      <div className="p-4 text-sm text-muted-foreground">
        PlayerTable wiring lands in Phase 3.
      </div>
    </div>
  );
}
```
`count` and `onSelectSuggestion` are stubbed here against mock data — Task 13 replaces both with the real computed count and the real clear-filters-and-scroll-to-row behavior once `PlayerTable` exists to scroll to.

- [ ] **Step 7: Verify the full test suite and build both pass**

Run: `cd frontend && npm test && npm run build`
Expected: all tests PASS, build exits 0.

- [ ] **Step 8: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/components/Toolbar.tsx frontend/src/components/Toolbar.test.tsx frontend/src/App.tsx
git commit -m "feat: compose Toolbar (search, team/season pickers, position/stat filters) against mock data"
```

**End of Phase 2 — open PR, confirm CI green, merge before starting Phase 3.**

---

## Phase 3: `PlayerTable` + real data + error handling

### Task 12: `PlayerTable` component

**Files:**
- Create: `frontend/src/components/PlayerTable.tsx`
- Create: `frontend/src/components/PlayerTable.test.tsx`

**Interfaces:**
- Consumes: `PlayerStats`, `SortDirection` from `frontend/src/lib/types.ts` (Task 6).
- Produces: `PlayerTable({ rows: PlayerStats[], sortKey: string, sortDir: SortDirection, onSort: (key: string) => void })` — consumed by Task 13 (`App.tsx`).

- [ ] **Step 1: Install the shadcn `table`, `badge`, and `skeleton` components**

```bash
cd frontend
npx shadcn@latest add table badge skeleton
```

- [ ] **Step 2: Write the failing test**

`frontend/src/components/PlayerTable.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PlayerTable } from "./PlayerTable";
import { MOCK_STATS } from "@/lib/mock-data";

describe("PlayerTable", () => {
  it("renders one row per player", () => {
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    expect(screen.getByText("MacKinnon")).toBeInTheDocument();
    expect(screen.getByText("McDavid")).toBeInTheDocument();
    expect(screen.getByText("Stolarz")).toBeInTheDocument();
  });

  it("calls onSort with the column key when a header is clicked", async () => {
    const onSort = vi.fn();
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={onSort} />);
    await userEvent.click(screen.getByText("G"));
    expect(onSort).toHaveBeenCalledWith("goals");
  });

  it("shows goalie columns (W/L/SV%/GAA) only for goalie rows", () => {
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    // Stolarz (goalie) shows his save % and wins
    expect(screen.getByText("0.918")).toBeInTheDocument();
    expect(screen.getByText("24")).toBeInTheDocument();
  });

  it("renders an empty-state message when rows is empty", () => {
    render(<PlayerTable rows={[]} sortKey="points" sortDir="desc" onSort={() => {}} />);
    expect(screen.getByText(/no players found/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npm test -- PlayerTable`
Expected: FAIL — `Cannot find module './PlayerTable'`.

- [ ] **Step 4: Implement `frontend/src/components/PlayerTable.tsx`**

```tsx
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
];

function cellValue(col: Column, row: PlayerStats): string {
  const val = (row as unknown as Record<string, unknown>)[col.key];
  if (val === null || val === undefined) return "-";
  if (col.key === "save_pct") return Number(val).toFixed(3);
  if (col.key === "gaa") return Number(val).toFixed(2);
  if (col.key === "shooting_pct") return `${val}%`;
  if (col.key === "plus_minus") return Number(val) > 0 ? `+${val}` : String(val);
  return String(val);
}

interface PlayerTableProps {
  rows: PlayerStats[];
  sortKey: string;
  sortDir: SortDirection;
  onSort: (key: string) => void;
}

export function PlayerTable({ rows, sortKey, sortDir, onSort }: PlayerTableProps) {
  if (rows.length === 0) {
    return <div className="p-12 text-center text-sm text-muted-foreground">No players found.</div>;
  }

  const hasGoalie = rows.some((r) => r.position_code === "G");
  const columns = COLUMNS.filter((c) => {
    if (c.goalieOnly) return hasGoalie;
    return true;
  });

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
        {rows.map((row) => (
          <TableRow key={row.player_id} data-player-id={row.player_id}>
            {columns.map((col) => (
              <TableCell key={col.key} className={col.numeric ? "text-right tabular-nums" : ""}>
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
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- PlayerTable`
Expected: PASS — 4 tests passing.

- [ ] **Step 6: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/components/ui/table.tsx frontend/src/components/ui/badge.tsx \
  frontend/src/components/ui/skeleton.tsx \
  frontend/src/components/PlayerTable.tsx frontend/src/components/PlayerTable.test.tsx
git commit -m "feat: add PlayerTable component (sortable, goalie-aware columns)"
```

---

### Task 13: `App.tsx` real-data wiring + error handling

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/App.test.tsx`
- Modify: `frontend/src/lib/types.ts` (no change — already covers the shapes needed)

**Interfaces:**
- Consumes: `Toolbar` (Task 11), `PlayerTable` (Task 12), `Team`/`Player`/`PlayerStats` (Task 6).
- Produces: the fully wired `App` — this is the component Task 16's cutover mounts into production.

- [ ] **Step 0: Add the `row-highlight` CSS rule (used by the suggestion-click scroll/highlight behavior below)**

Append to `frontend/src/index.css` (created in Task 2):
```css
tr.row-highlight {
  background-color: color-mix(in oklch, var(--primary) 25%, transparent) !important;
  transition: background-color 0.3s ease;
}
```

- [ ] **Step 1: Install the shadcn `alert` and `button` components**

```bash
cd frontend
npx shadcn@latest add alert button
```

- [ ] **Step 2: Write the failing test**

`frontend/src/App.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
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

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url: string) => mockFetchOnce(url)));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("loads teams, players, and default-season stats, then renders the table", async () => {
    render(<App />);
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
    render(<App />);
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
    render(<App />);
    await screen.findByText(/failed to load/i);
    shouldFail = false;
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByText("MacKinnon")).toBeInTheDocument());
  });

  it("narrows rows when a search query is typed", async () => {
    render(<App />);
    await screen.findByText("MacKinnon");
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "McDavid");
    expect(screen.queryByText("MacKinnon")).not.toBeInTheDocument();
    expect(screen.getByText("McDavid")).toBeInTheDocument();
  });

  it("shows the player count, narrowed when a filter is active", async () => {
    render(<App />);
    await screen.findByText("MacKinnon");
    expect(screen.getByText("3 players")).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "McDavid");
    expect(screen.getByText("1 of 3 players")).toBeInTheDocument();
  });

  it("clears other filters, scrolls to, and highlights the row when a suggestion is clicked", async () => {
    render(<App />);
    await screen.findByText("MacKinnon");
    await userEvent.click(screen.getByRole("button", { name: "C" })); // active position filter
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "MacKinnon");
    await userEvent.click(await screen.findByText("Nathan MacKinnon"));

    // search box cleared, position filter cleared (McDavid, a center, is visible again)
    expect(screen.getByPlaceholderText("Search players…")).toHaveValue("");
    expect(screen.getByText("McDavid")).toBeInTheDocument();

    const row = document.querySelector('[data-player-id="1"]');
    expect(row).toHaveClass("row-highlight");
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npm test -- App`
Expected: FAIL — `App` doesn't fetch anything yet (still the Task 11 mock-data placeholder).

- [ ] **Step 4: Implement the fully wired `frontend/src/App.tsx`**

```tsx
import { useEffect, useMemo, useState } from "react";
import { Toolbar, type ToolbarFilters } from "@/components/Toolbar";
import { PlayerTable } from "@/components/PlayerTable";
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

export default function App() {
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
    <div className="min-h-screen bg-background text-foreground">
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
        <PlayerTable rows={rows} sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- App`
Expected: PASS — 4 tests passing.

- [ ] **Step 6: Run the full test suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: all tests PASS (including Tasks 5, 7-12's suites), build exits 0.

- [ ] **Step 7: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/components/ui/alert.tsx \
  frontend/src/components/ui/button.tsx frontend/src/index.css frontend/src/test-setup.ts
git commit -m "feat: wire App to real API data with fetch-failure Alert+Retry handling"
```
Also stages `frontend/src/test-setup.ts` (Task 5's `scrollIntoView` polyfill, needed for this task's suggestion-click test) if it wasn't already committed.

---

### Task 14: Sticky-header height offset (bug-008 regression guard)

**Files:**
- Modify: `frontend/src/components/PlayerTable.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- Produces: a bounded-height, single-scrolling-container wrapper around `PlayerTable`, matching the exact technique from `templates/index.html`'s `.table-wrap` (bug-008 fix, 2026-07-14) — never regressing to a page-scrolls-with-a-displaced-sticky-header state.

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/App.test.tsx`:
```tsx
  it("wraps the table in a single bounded-height scroll container (bug-008 regression guard)", async () => {
    render(<App />);
    await screen.findByText("MacKinnon");
    const wrap = document.querySelector('[data-testid="table-wrap"]');
    expect(wrap).not.toBeNull();
    const style = wrap!.getAttribute("style") || "";
    expect(style).toMatch(/height/);
    expect(wrap).toHaveClass("overflow-auto");
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- App`
Expected: FAIL — no element with `data-testid="table-wrap"` exists yet.

- [ ] **Step 3: Add the bounded-height wrapper in `App.tsx`**

In `frontend/src/App.tsx`, wrap the `<PlayerTable>` render (replacing the plain conditional block from Task 13's Step 4):
```tsx
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
          style={{ height: "max(200px, calc(100vh - var(--toolbar-height, 120px)))" }}
        >
          <PlayerTable rows={rows} sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
        </div>
      )}
```
This mirrors `templates/index.html`'s `.table-wrap` rule exactly (`height: max(200px, calc(100vh - var(--toolbar-height, 57px)))`, `overflow: auto`) — the floor (`200px`) and the `calc()` are both required per the `bug-008` fix, not just the `overflow: auto`.

- [ ] **Step 4: Recalculate `--toolbar-height` on toolbar resize**

Add to `frontend/src/App.tsx`, alongside the other `useEffect` calls:
```tsx
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
```
And add `data-toolbar` to `Toolbar`'s root `<div>` in `frontend/src/components/Toolbar.tsx`:
```tsx
    <div data-toolbar className="flex flex-col gap-3 border-b border-border bg-card p-4">
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- App`
Expected: PASS.

- [ ] **Step 6: Run the full suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: all PASS, build exits 0.

- [ ] **Step 7: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/components/Toolbar.tsx
git commit -m "fix: port bounded-height sticky-table-header technique (bug-008 regression guard)"
```

---

### Task 15: Final error-handling coverage (teams + stats fetch failures)

**Files:**
- Modify: `frontend/src/App.test.tsx`

**Interfaces:** none new — this task closes the test-coverage gap left by Task 13 (which only tested the players-fetch failure path).

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/App.test.tsx`:
```tsx
  it("shows an error alert with a retry button when the teams fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.includes("/api/teams")
          ? Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)
          : mockFetchOnce(url)
      )
    );
    render(<App />);
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
    render(<App />);
    await screen.findByText("NHL Players");
    expect(await screen.findByText(/failed to load stats/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the tests to verify current status**

Run: `cd frontend && npm test -- App`
Expected: PASS immediately — Task 13's `App.tsx` already implements both the teams- and stats-error branches; this task only adds the missing regression tests for them (no implementation change expected).

- [ ] **Step 3: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add frontend/src/App.test.tsx
git commit -m "test: cover teams-fetch and stats-fetch failure/retry paths"
```

**End of Phase 3 — open PR, confirm CI green (build + all Vitest suites), merge before starting Phase 4.**

---

## Phase 4: Cutover

### Task 16: Replace the Flask shell, delete the vanilla app

**Files:**
- Modify: `templates/index.html` (replace entirely)
- Delete: `static/js/search.js`
- Delete: `tests/js/search.test.js`
- Delete: `tests/js/` (if now empty)

**Interfaces:** none — this task only changes what Flask serves, not any API contract.

- [ ] **Step 1: Build the production bundle**

```bash
cd frontend && npm run build
```
Expected: exits 0, `static/dist/app.js` + `static/dist/app.css` are current.

- [ ] **Step 2: Replace `templates/index.html`**

```html
<!doctype html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NHL Players</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='dist/app.css') }}">
</head>
<body>
  <div id="root"></div>
  <script type="module" src="{{ url_for('static', filename='dist/app.js') }}"></script>
</body>
</html>
```

- [ ] **Step 3: Delete the retired vanilla files**

```bash
git rm static/js/search.js tests/js/search.test.js
rmdir tests/js 2>/dev/null || true
```

- [ ] **Step 4: Verify `app.py` needs no changes**

Run: `python -m pytest tests/ -v`
Expected: all existing Python tests still PASS unmodified — confirms Task 16 changed nothing about the backend contract (per the spec's Global Constraint).

- [ ] **Step 5: Manual end-to-end verification**

Run:
```bash
python app.py &
sleep 2
curl -s http://127.0.0.1:5099/ | grep -q 'id="root"' && echo "OK: shell serves React root"
kill %1
```
Then, per the `run`/`verify` skills, open `http://127.0.0.1:5099/` in a browser and manually confirm: search + autocomplete, team picker with logos, season multi-select (including "All Seasons" exclusivity), position toggles, stat-minimum filters, column sort (asc/desc toggle), goalie vs. skater columns, sticky header behavior on scroll, and a simulated fetch failure (e.g. temporarily stop `app.py`) showing the Alert+Retry UI.

- [ ] **Step 6: Commit**

```bash
cd "/Users/paulmckay/Desktop/NHL Stats Project"
git add templates/index.html
git commit -m "feat: cut over to the React frontend, retire the vanilla table page"
```

---

### Task 17: Close out issue #23, final CI confirmation

**Files:** none — verification-only task.

- [ ] **Step 1: Confirm CI is green end-to-end on the cutover PR**

Run: `gh pr checks <PR-number>`
Expected: both the Python `check` job and the `frontend` job (build + Vitest) show `pass`.

- [ ] **Step 2: Reference and close issue #23 in the PR description**

The cutover PR body should include `Closes #23` — `tests/js/search.test.js`'s `node --test` suite (which #23 was filed against) is deleted in Task 16, superseded by the Vitest suite wired into CI since Task 5. Once this PR merges, GitHub closes #23 automatically.

- [ ] **Step 3: No commit** — this task is verification/PR-metadata only.

**End of Phase 4 — merge. The replatform is complete: `main` serves the React app, the old vanilla files are gone, and CI enforces both the Python and frontend test suites on every future PR.**
