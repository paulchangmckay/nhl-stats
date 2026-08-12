# Player Profile Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing `PlayerAdvancedPanel` dialog into a full player profile overlay — photo, team-branded header, bio detail row, and a position-aware box score — alongside its existing advanced-stats section, opened by clicking anywhere in a player's table row.

**Architecture:** No new backend endpoint. `app.py`'s `_fetch_players()` gains a handful of already-existing-but-unselected columns (`headshot_url`, birth city/state, draft fields). On the frontend, `App.tsx` joins the already-fetched `Player` bio row and `PlayerStats` row by `player_id` when a table row is clicked, and passes both into the renamed `PlayerProfilePanel`. Team colors/logos come from a new static `teamBranding.ts` lookup keyed by `team_abbrev` — no DB involvement.

**Tech Stack:** Flask + SQLite (backend), React 19 + TypeScript + Vite + Tailwind + shadcn/ui + Recharts (frontend), pytest (backend tests), Vitest + Testing Library (frontend tests).

## Global Constraints

- No new backend endpoint — reuse `/api/players`, `/api/players/stats`, `/api/players/<id>/advanced` exactly as they exist today.
- `headshot_url`, `birth_city`, `birth_state_province`, `draft_team_abbrev` are nullable strings; `draft_year`/`draft_round`/`draft_pick`/`draft_overall` are nullable numbers — never coerce these to `""`/`0` (an empty string or zero would be indistinguishable from real data).
- Team logo uses the NHL CDN's `_dark` variant (`https://assets.nhle.com/logos/nhl/svg/{ABBREV}_dark.svg`), not `_light` — matches the app's dark theme (verified both variants resolve via curl during grilling).
- The `teams` table has 33 rows: 32 real franchises + a literal `"UNK"` placeholder for players with no current team. `teamBranding.ts` must return `undefined` (no accent, no logo) for `"UNK"`, blank, and any other unrecognized abbreviation — never throw.
- Row click/keyboard trigger replaces the CF%-cell-only trigger; the CF% cell's own `onClick`/`role="button"` must be removed (nested-interactive-element anti-pattern once the row itself is interactive).
- Header/bio/box-score render immediately on dialog open (no fetch needed — already-loaded data); only the advanced-stats section shows its own loading/error state while `/api/players/<id>/advanced` resolves.
- Goalies (`position_code === "G"`): box score shows GP/W/L/OTL/SV%/GAA/SO instead of GP/G/A/P/+/-/PIM, and the entire advanced-stats section (strength toggle, percentile boxes, trend chart) is not rendered — also skip the `/advanced` fetch itself for goalies, since nothing renders it.

---

### Task 1: Backend — expose photo/bio/draft fields from `_fetch_players()`

**Files:**
- Modify: `app.py:53-91` (`_fetch_players` function)
- Test: `tests/test_app_helpers.py`

**Interfaces:**
- Produces: `_fetch_players(conn)` now returns dicts with additional keys `birth_city: str`, `birth_state_province: str`, `headshot_url: str | None`, `draft_year: int | None`, `draft_round: int | None`, `draft_pick: int | None`, `draft_overall: int | None`, `draft_team_abbrev: str | None`, alongside all existing keys unchanged. Consumed by `/api/players` (unchanged route, same function) and, on the frontend, by the `Player` TS type (Task 2).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_app_helpers.py` (after the existing `test_fetch_players_includes_team_place_name` test):

```python
def test_fetch_players_includes_photo_bio_and_draft_fields(conn):
    """Player profile overlay needs headshot_url, birth city/state, and
    draft info surfaced by the players query (existing columns on the
    players table, previously not selected by _fetch_players)."""
    database.upsert_player_stub(conn, {
        "player_id": 1, "first_name": "Connor", "last_name": "McDavid",
        "position_code": "C", "shoots_catches": "L",
    })
    database.upsert_player_enrichment(conn, {
        "player_id": 1,
        "headshot_url": "https://example.com/mcdavid.png",
        "birth_city": "Richmond Hill",
        "birth_state_province": "ON",
        "draft_year": 2015, "draft_round": 1, "draft_pick": 1,
        "draft_overall": 1, "draft_team_abbrev": "EDM",
        "is_active": 1,
    })
    conn.commit()

    players = _fetch_players(conn)

    assert len(players) == 1
    p = players[0]
    assert p["headshot_url"] == "https://example.com/mcdavid.png"
    assert p["birth_city"] == "Richmond Hill"
    assert p["birth_state_province"] == "ON"
    assert p["draft_year"] == 2015
    assert p["draft_round"] == 1
    assert p["draft_pick"] == 1
    assert p["draft_overall"] == 1
    assert p["draft_team_abbrev"] == "EDM"


def test_fetch_players_undrafted_player_has_null_draft_and_photo_fields(conn):
    """Undrafted / un-enriched players (~21% of the roster) must not error
    or fabricate data — these fields stay None, not '' or 0."""
    database.upsert_player_stub(conn, {
        "player_id": 2, "first_name": "Jane", "last_name": "Undrafted",
        "position_code": "D", "shoots_catches": "L",
    })
    conn.commit()

    players = _fetch_players(conn)

    assert players[0]["draft_year"] is None
    assert players[0]["draft_round"] is None
    assert players[0]["draft_pick"] is None
    assert players[0]["draft_overall"] is None
    assert players[0]["draft_team_abbrev"] is None
    assert players[0]["headshot_url"] is None
    assert players[0]["birth_city"] == ""
    assert players[0]["birth_state_province"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app_helpers.py -v -k photo_bio_and_draft or undrafted_player_has_null`
Expected: FAIL — `KeyError: 'headshot_url'` (or similar) since `_fetch_players` doesn't select these columns yet.

- [ ] **Step 3: Implement — extend the SELECT and dict in `_fetch_players()`**

Replace `app.py:53-91` entirely with:

```python
def _fetch_players(conn):
    rows = conn.execute("""
        SELECT
            p.player_id,
            p.sweater_number,
            p.first_name,
            p.last_name,
            p.position_code,
            p.shoots_catches,
            p.height_inches,
            p.weight_pounds,
            p.birth_date,
            p.birth_country,
            p.birth_city,
            p.birth_state_province,
            p.headshot_url,
            p.draft_year,
            p.draft_round,
            p.draft_pick,
            p.draft_overall,
            p.draft_team_abbrev,
            t.abbrev      AS team_abbrev,
            t.common_name AS team_name,
            t.place_name  AS team_place_name
        FROM players p
        LEFT JOIN teams t ON p.current_team_id = t.team_id
        ORDER BY p.last_name, p.first_name
    """).fetchall()

    players = []
    for r in rows:
        players.append({
            "player_id":            r["player_id"],
            "sweater_number":       r["sweater_number"],
            "first_name":           r["first_name"],
            "last_name":            r["last_name"],
            "position_code":        r["position_code"] or "",
            "shoots_catches":       r["shoots_catches"] or "",
            "height":               _height_str(r["height_inches"]),
            "weight_pounds":        r["weight_pounds"],
            "birth_date":           r["birth_date"] or "",
            "birth_country":        r["birth_country"] or "",
            "birth_city":           r["birth_city"] or "",
            "birth_state_province": r["birth_state_province"] or "",
            "headshot_url":         r["headshot_url"],
            "draft_year":           r["draft_year"],
            "draft_round":          r["draft_round"],
            "draft_pick":           r["draft_pick"],
            "draft_overall":        r["draft_overall"],
            "draft_team_abbrev":    r["draft_team_abbrev"],
            "team_abbrev":          r["team_abbrev"] or "",
            "team_name":            r["team_name"] or "",
            "team_place_name":      r["team_place_name"] or "",
        })
    return players
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_app_helpers.py -v`
Expected: All tests PASS, including the two new ones and the pre-existing `test_fetch_players_includes_team_place_name`.

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python -m pytest tests/ -v`
Expected: All PASS (no other test depends on `_fetch_players`'s exact key set in a way that would break).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_helpers.py
git commit -m "feat: expose headshot/bio/draft fields from _fetch_players"
```

---

### Task 2: Frontend — extend `Player` type and mock data

**Files:**
- Modify: `frontend/src/lib/types.ts` (`Player` interface)
- Modify: `frontend/src/lib/mock-data.ts` (`MOCK_PLAYERS`)

**Interfaces:**
- Consumes: nothing (pure type/data change).
- Produces: `Player` type now includes `birth_city: string`, `birth_state_province: string`, `headshot_url: string | null`, `draft_year: number | null`, `draft_round: number | null`, `draft_pick: number | null`, `draft_overall: number | null`, `draft_team_abbrev: string | null`. `MOCK_PLAYERS[0]` (MacKinnon) and `MOCK_PLAYERS[1]` (McDavid) have a `headshot_url` and full draft info; `MOCK_PLAYERS[2]` (Stolarz, goalie) has `headshot_url: null` and `draft_year: null` — deliberately covering both the photo-fallback and "Undrafted" cases used by Task 5's tests.

- [ ] **Step 1: Run the frontend build to confirm the current baseline compiles**

Run (from `frontend/`): `npm run build`
Expected: PASS (0 errors) — this is the baseline before the type change.

- [ ] **Step 2: Extend the `Player` interface**

In `frontend/src/lib/types.ts`, replace the `Player` interface with:

```ts
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
  birth_city: string;
  birth_state_province: string;
  headshot_url: string | null;
  draft_year: number | null;
  draft_round: number | null;
  draft_pick: number | null;
  draft_overall: number | null;
  draft_team_abbrev: string | null;
  team_abbrev: string;
  team_name: string;
  team_place_name: string;
}
```

- [ ] **Step 3: Run the build to verify it now fails**

Run (from `frontend/`): `npm run build`
Expected: FAIL — TS2739 (or similar) in `frontend/src/lib/mock-data.ts`: `MOCK_PLAYERS` objects are missing the new required properties.

- [ ] **Step 4: Update `MOCK_PLAYERS` with the new fields**

In `frontend/src/lib/mock-data.ts`, replace `MOCK_PLAYERS` with:

```ts
export const MOCK_PLAYERS: Player[] = [
  {
    player_id: 1, sweater_number: 29, first_name: "Nathan", last_name: "MacKinnon",
    position_code: "C", shoots_catches: "R", height: "6'0\"", weight_pounds: 181,
    birth_date: "1995-09-01", birth_country: "CAN",
    birth_city: "Cole Harbour", birth_state_province: "NS",
    headshot_url: "https://assets.nhle.com/mugs/nhl/latest/8477492.png",
    draft_year: 2013, draft_round: 1, draft_pick: 1, draft_overall: 1, draft_team_abbrev: "COL",
    team_abbrev: "COL", team_name: "Avalanche", team_place_name: "Colorado",
  },
  {
    player_id: 2, sweater_number: 97, first_name: "Connor", last_name: "McDavid",
    position_code: "C", shoots_catches: "L", height: "6'1\"", weight_pounds: 193,
    birth_date: "1997-01-13", birth_country: "CAN",
    birth_city: "Richmond Hill", birth_state_province: "ON",
    headshot_url: "https://assets.nhle.com/mugs/nhl/latest/8478402.png",
    draft_year: 2015, draft_round: 1, draft_pick: 1, draft_overall: 1, draft_team_abbrev: "EDM",
    team_abbrev: "EDM", team_name: "Oilers", team_place_name: "Edmonton",
  },
  {
    player_id: 3, sweater_number: 31, first_name: "Anthony", last_name: "Stolarz",
    position_code: "G", shoots_catches: "L", height: "6'6\"", weight_pounds: 240,
    birth_date: "1994-01-20", birth_country: "USA",
    birth_city: "Edison", birth_state_province: "NJ",
    headshot_url: null,
    draft_year: null, draft_round: null, draft_pick: null, draft_overall: null, draft_team_abbrev: null,
    team_abbrev: "TOR", team_name: "Maple Leafs", team_place_name: "Toronto",
  },
];
```

- [ ] **Step 5: Run the build to verify it passes**

Run (from `frontend/`): `npm run build`
Expected: PASS (0 errors).

- [ ] **Step 6: Run the existing frontend test suite to check for regressions**

Run (from `frontend/`): `npm test`
Expected: All PASS (no test asserts on the exact shape of `MOCK_PLAYERS` in a way the new fields would break).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/mock-data.ts
git commit -m "feat: add photo/bio/draft fields to Player type and mock data"
```

---

### Task 3: Frontend — team branding lookup (`teamBranding.ts`)

**Files:**
- Create: `frontend/src/lib/teamBranding.ts`
- Test: `frontend/src/lib/teamBranding.test.ts`

**Interfaces:**
- Produces: `teamColors(abbrev: string): { primary: string; secondary: string } | undefined` and `logoUrl(abbrev: string): string`. Consumed by `PlayerProfilePanel` (Task 5).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/teamBranding.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { teamColors, logoUrl } from "./teamBranding";

describe("teamBranding", () => {
  it("returns primary and secondary colors for a known team", () => {
    expect(teamColors("EDM")).toEqual({ primary: "#041E42", secondary: "#FF4C00" });
  });

  it("returns undefined for the UNK placeholder team", () => {
    expect(teamColors("UNK")).toBeUndefined();
  });

  it("returns undefined for a blank or unrecognized abbreviation", () => {
    expect(teamColors("")).toBeUndefined();
    expect(teamColors("ZZZ")).toBeUndefined();
  });

  it("has an entry for all 32 current NHL teams", () => {
    const abbrevs = [
      "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET",
      "EDM", "FLA", "LAK", "MIN", "MTL", "NJD", "NSH", "NYI", "NYR", "OTT",
      "PHI", "PIT", "SEA", "SJS", "STL", "TBL", "TOR", "UTA", "VAN", "VGK",
      "WPG", "WSH",
    ];
    for (const abbrev of abbrevs) {
      expect(teamColors(abbrev), `missing colors for ${abbrev}`).toBeDefined();
    }
  });

  it("builds a dark-variant NHL CDN logo URL for a given abbreviation", () => {
    expect(logoUrl("EDM")).toBe("https://assets.nhle.com/logos/nhl/svg/EDM_dark.svg");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/lib/teamBranding.test.ts`
Expected: FAIL — `Failed to resolve import "./teamBranding"` (file doesn't exist yet).

- [ ] **Step 3: Implement `teamBranding.ts`**

Create `frontend/src/lib/teamBranding.ts`:

```ts
interface TeamColors {
  primary: string;
  secondary: string;
}

// Researched per-team brand colors. UTA (Utah's NHL franchise) rebranded
// recently (relocated 2024, renamed 2025) — double-check against current
// official assets if these ever look wrong.
const TEAM_COLORS: Record<string, TeamColors> = {
  ANA: { primary: "#F47A38", secondary: "#000000" },
  BOS: { primary: "#FFB81C", secondary: "#000000" },
  BUF: { primary: "#002654", secondary: "#FCB514" },
  CAR: { primary: "#CC0000", secondary: "#000000" },
  CBJ: { primary: "#002654", secondary: "#CE1126" },
  CGY: { primary: "#C8102E", secondary: "#F1BE48" },
  CHI: { primary: "#CF0A2C", secondary: "#000000" },
  COL: { primary: "#6F263D", secondary: "#236192" },
  DAL: { primary: "#006847", secondary: "#000000" },
  DET: { primary: "#CE1126", secondary: "#FFFFFF" },
  EDM: { primary: "#041E42", secondary: "#FF4C00" },
  FLA: { primary: "#C8102E", secondary: "#041E42" },
  LAK: { primary: "#111111", secondary: "#A2AAAD" },
  MIN: { primary: "#154734", secondary: "#A6192E" },
  MTL: { primary: "#AF1E2D", secondary: "#192168" },
  NJD: { primary: "#CE1126", secondary: "#000000" },
  NSH: { primary: "#FFB81C", secondary: "#041E42" },
  NYI: { primary: "#00539B", secondary: "#F47D30" },
  NYR: { primary: "#0038A8", secondary: "#CE1126" },
  OTT: { primary: "#C8102E", secondary: "#000000" },
  PHI: { primary: "#F74902", secondary: "#000000" },
  PIT: { primary: "#000000", secondary: "#FFB81C" },
  SEA: { primary: "#001628", secondary: "#99D9D9" },
  SJS: { primary: "#006D75", secondary: "#000000" },
  STL: { primary: "#002F87", secondary: "#FCB514" },
  TBL: { primary: "#002868", secondary: "#FFFFFF" },
  TOR: { primary: "#00205B", secondary: "#FFFFFF" },
  UTA: { primary: "#010101", secondary: "#69B3E7" },
  VAN: { primary: "#00205B", secondary: "#00843D" },
  VGK: { primary: "#B4975A", secondary: "#333F42" },
  WPG: { primary: "#041E42", secondary: "#AC162C" },
  WSH: { primary: "#C8102E", secondary: "#041E42" },
};

export function teamColors(abbrev: string): TeamColors | undefined {
  return TEAM_COLORS[abbrev];
}

export function logoUrl(abbrev: string): string {
  return `https://assets.nhle.com/logos/nhl/svg/${abbrev}_dark.svg`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/lib/teamBranding.test.ts`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/teamBranding.ts frontend/src/lib/teamBranding.test.ts
git commit -m "feat: add teamBranding lookup for player profile colors/logos"
```

---

### Task 4: Frontend — `PlayerTable` whole-row click/keyboard trigger

**Files:**
- Modify: `frontend/src/components/PlayerTable.tsx`
- Modify: `frontend/src/components/PlayerTable.test.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces: `PlayerTableProps.onOpenProfile?: (playerId: number) => void` (renamed from `onOpenAdvanced`). Consumed by `App.tsx` (Task 6). The `cf_pct_5v5` cell loses its `data-testid="cf-pct-5v5-cell"`, `role="button"`, and `onClick` — it's a plain cell now.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/components/PlayerTable.test.tsx`, replace the last test (`"calls onOpenAdvanced with the player id when the CF% (5v5) cell is clicked"`) with:

```tsx
  it("calls onOpenProfile with the player id when a row is clicked", async () => {
    const onOpenProfile = vi.fn();
    render(
      <PlayerTable
        rows={MOCK_STATS}
        sortKey="points"
        sortDir="desc"
        onSort={() => {}}
        onOpenProfile={onOpenProfile}
      />
    );
    const row = document.querySelector('[data-player-id="1"]')!;
    await userEvent.click(row);
    expect(onOpenProfile).toHaveBeenCalledWith(1);
  });

  it("calls onOpenProfile when a row is focused and Enter is pressed", async () => {
    const onOpenProfile = vi.fn();
    render(
      <PlayerTable
        rows={MOCK_STATS}
        sortKey="points"
        sortDir="desc"
        onSort={() => {}}
        onOpenProfile={onOpenProfile}
      />
    );
    const row = document.querySelector('[data-player-id="2"]') as HTMLElement;
    row.focus();
    await userEvent.keyboard("{Enter}");
    expect(onOpenProfile).toHaveBeenCalledWith(2);
  });

  it("no longer gives the CF% (5v5) cell its own click handler (the row handles it)", () => {
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    expect(screen.queryByTestId("cf-pct-5v5-cell")).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `frontend/`): `npx vitest run src/components/PlayerTable.test.tsx`
Expected: FAIL — `onOpenProfile` prop doesn't exist yet (TS error) and/or the row click does nothing.

- [ ] **Step 3: Implement — row-level click/keyboard, remove per-cell handler**

Replace `frontend/src/components/PlayerTable.tsx` in full:

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
  { key: "cf_pct_5v5", label: "CF% (5v5)", numeric: true, skaterOnly: true },
];

function cellValue(col: Column, row: PlayerStats): string {
  const val = (row as unknown as Record<string, unknown>)[col.key];
  if (val === null || val === undefined) return "-";
  if (col.key === "save_pct") return Number(val).toFixed(3);
  if (col.key === "gaa") return Number(val).toFixed(2);
  if (col.key === "shooting_pct") return `${val}%`;
  if (col.key === "cf_pct_5v5") return `${val}%`;
  if (col.key === "plus_minus") return Number(val) > 0 ? `+${val}` : String(val);
  return String(val);
}

interface PlayerTableProps {
  rows: PlayerStats[];
  sortKey: string;
  sortDir: SortDirection;
  onSort: (key: string) => void;
  onOpenProfile?: (playerId: number) => void;
}

export function PlayerTable({ rows, sortKey, sortDir, onSort, onOpenProfile }: PlayerTableProps) {
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
          <TableRow
            key={row.player_id}
            data-player-id={row.player_id}
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
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `frontend/`): `npx vitest run src/components/PlayerTable.test.tsx`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PlayerTable.tsx frontend/src/components/PlayerTable.test.tsx
git commit -m "feat: make whole player row the click/keyboard trigger"
```

---

### Task 5: Frontend — rename and extend `PlayerAdvancedPanel` → `PlayerProfilePanel`

**Files:**
- Create: `frontend/src/components/PlayerProfilePanel.tsx` (replaces `PlayerAdvancedPanel.tsx`)
- Create: `frontend/src/components/PlayerProfilePanel.test.tsx` (replaces `PlayerAdvancedPanel.test.tsx`)
- Delete: `frontend/src/components/PlayerAdvancedPanel.tsx`, `frontend/src/components/PlayerAdvancedPanel.test.tsx`

**Interfaces:**
- Consumes: `teamColors`, `logoUrl` from `@/lib/teamBranding` (Task 3); `Player`, `PlayerStats`, `PlayerAdvancedStats` from `@/lib/types` (Task 2 for `Player`).
- Produces: `PlayerProfilePanelProps = { open: boolean; playerId: number; bio: Player | undefined; stats: PlayerStats | undefined; onOpenChange: (open: boolean) => void }`. Consumed by `App.tsx` (Task 6). Note the removed `playerName` prop — it's now derived internally from `stats`/`bio`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/PlayerProfilePanel.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PlayerProfilePanel } from "./PlayerProfilePanel";
import { MOCK_PLAYERS, MOCK_STATS } from "@/lib/mock-data";
import type { PlayerAdvancedStats } from "@/lib/types";

const MOCK_ADVANCED: PlayerAdvancedStats = {
  player_id: 1,
  season_id: "20242025",
  strength_states: {
    "5v5": {
      cf: 60, ca: 40, cf_pct: 60.0, ff: 45, fa: 30, ff_pct: 60.0,
      hdcf: 10, hdca: 5, hdcf_pct: 66.7, primary_points: 15,
      cf_pctile: 75.0, ff_pctile: 80.0, hdcf_pctile: 60.0, primary_points_pctile: 90.0,
    },
    "5v4": {
      cf: 20, ca: 5, cf_pct: 80.0, ff: 15, fa: 3, ff_pct: 83.3,
      hdcf: 4, hdca: 1, hdcf_pct: 80.0, primary_points: 5,
      cf_pctile: 55.0, ff_pctile: 60.0, hdcf_pctile: 50.0, primary_points_pctile: 65.0,
    },
  },
  trend: [
    { season_id: "20232024", cf_pct: 55.0 },
    { season_id: "20242025", cf_pct: 60.0 },
  ],
  pdo: 1005.3,
};

const mackinnonBio = MOCK_PLAYERS[0];   // has headshot_url + draft info
const mcdavidStats = MOCK_STATS[1];
const stolarzBio = MOCK_PLAYERS[2];     // goalie: no headshot_url, undrafted
const stolarzStats = MOCK_STATS[2];

describe("PlayerProfilePanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_ADVANCED) } as Response)
    ));
  });

  it("renders header/bio/box-score immediately, without waiting on the advanced-stats fetch", () => {
    render(
      <PlayerProfilePanel
        open
        playerId={1}
        bio={mackinnonBio}
        stats={MOCK_STATS[0]}
        onOpenChange={() => {}}
      />
    );
    expect(screen.getByText("Nathan MacKinnon")).toBeInTheDocument();
    expect(screen.getByText(/Cole Harbour/)).toBeInTheDocument();
    expect(screen.getByText(/Rd 1, Pick 1 \(2013, COL\)/)).toBeInTheDocument();
  });

  it("shows the silhouette fallback when headshot_url is null", () => {
    render(
      <PlayerProfilePanel
        open
        playerId={3}
        bio={stolarzBio}
        stats={stolarzStats}
        onOpenChange={() => {}}
      />
    );
    expect(screen.queryByRole("img", { name: /Anthony Stolarz/ })).not.toBeInTheDocument();
  });

  it("shows 'Undrafted' when draft_year is null", () => {
    render(
      <PlayerProfilePanel
        open
        playerId={3}
        bio={stolarzBio}
        stats={stolarzStats}
        onOpenChange={() => {}}
      />
    );
    expect(screen.getByText(/Undrafted/)).toBeInTheDocument();
  });

  it("shows the goalie box score (W/L/SV%/GAA/SO) and hides the advanced-stats section for goalies", async () => {
    render(
      <PlayerProfilePanel
        open
        playerId={3}
        bio={stolarzBio}
        stats={stolarzStats}
        onOpenChange={() => {}}
      />
    );
    expect(screen.getByText("0.918")).toBeInTheDocument(); // save_pct
    expect(screen.getByText("24")).toBeInTheDocument(); // wins
    await waitFor(() => expect(screen.queryByText(/loading advanced stats/i)).not.toBeInTheDocument());
    expect(screen.queryByText("CF%")).not.toBeInTheDocument();
  });

  it("shows the skater box score (G/A/P/+/-/PIM) for skaters", () => {
    render(
      <PlayerProfilePanel
        open
        playerId={2}
        bio={MOCK_PLAYERS[1]}
        stats={mcdavidStats}
        onOpenChange={() => {}}
      />
    );
    expect(screen.getByText("32")).toBeInTheDocument(); // goals
    expect(screen.getByText("88")).toBeInTheDocument(); // assists
  });

  it("loads and renders the advanced-stats section for skaters", async () => {
    render(
      <PlayerProfilePanel
        open
        playerId={1}
        bio={mackinnonBio}
        stats={MOCK_STATS[0]}
        onOpenChange={() => {}}
      />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument()); // CF% percentile
    expect(screen.getByText("1005.3")).toBeInTheDocument(); // PDO
  });

  it("switches the displayed strength state when the selector changes", async () => {
    render(
      <PlayerProfilePanel
        open
        playerId={1}
        bio={mackinnonBio}
        stats={MOCK_STATS[0]}
        onOpenChange={() => {}}
      />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "5v4" }));
    await waitFor(() => expect(screen.getByText("55")).toBeInTheDocument()); // 5v4's cf_pctile
  });

  it("renders without crashing when bio is undefined (data-gap edge case)", () => {
    render(
      <PlayerProfilePanel
        open
        playerId={1}
        bio={undefined}
        stats={MOCK_STATS[0]}
        onOpenChange={() => {}}
      />
    );
    expect(screen.getByText("Nathan MacKinnon")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `frontend/`): `npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: FAIL — `Failed to resolve import "./PlayerProfilePanel"` (file doesn't exist yet).

- [ ] **Step 3: Implement `PlayerProfilePanel.tsx`**

Create `frontend/src/components/PlayerProfilePanel.tsx`:

```tsx
import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { User } from "lucide-react";
import { teamColors, logoUrl } from "@/lib/teamBranding";
import type { Player, PlayerStats, PlayerAdvancedStats } from "@/lib/types";

const STRENGTH_STATES = ["5v5", "5v4", "4v5"] as const;

type FetchState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: PlayerAdvancedStats };

interface PercentileBoxProps {
  label: string;
  value: number | null;
  pctile: number | null;
}

function PercentileBox({ label, value, pctile }: PercentileBoxProps) {
  const color =
    pctile === null ? "bg-muted" : pctile >= 50 ? "bg-sky-500/20" : "bg-rose-500/20";
  return (
    <div className={`rounded-lg p-3 text-center ${color}`}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">
        {pctile === null ? "-" : Math.round(pctile)}
      </div>
      <div className="text-xs text-muted-foreground tabular-nums">
        {value === null ? "-" : `${value}%`}
      </div>
    </div>
  );
}

interface StatCellProps {
  label: string;
  value: string;
}

function StatCell({ label, value }: StatCellProps) {
  return (
    <div>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="tabular-nums">{value}</div>
    </div>
  );
}

function computeAge(birthDate: string): number | null {
  if (!birthDate) return null;
  const birth = new Date(birthDate);
  if (Number.isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const notYetHadBirthdayThisYear =
    today.getMonth() < birth.getMonth() ||
    (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate());
  if (notYetHadBirthdayThisYear) age -= 1;
  return age;
}

function draftLabel(bio: Player | undefined): string {
  if (!bio || bio.draft_year === null) return "Undrafted";
  return `Rd ${bio.draft_round}, Pick ${bio.draft_pick} (${bio.draft_year}, ${bio.draft_team_abbrev ?? ""})`;
}

function birthplaceLabel(bio: Player | undefined): string {
  if (!bio) return "";
  return [bio.birth_city, bio.birth_state_province, bio.birth_country].filter(Boolean).join(", ");
}

function formatSavePct(val: number | null): string {
  return val === null ? "-" : val.toFixed(3);
}

function formatGaa(val: number | null): string {
  return val === null ? "-" : val.toFixed(2);
}

function formatPlusMinus(val: number | null): string {
  if (val === null) return "-";
  return val > 0 ? `+${val}` : String(val);
}

interface PlayerProfilePanelProps {
  open: boolean;
  playerId: number;
  bio: Player | undefined;
  stats: PlayerStats | undefined;
  onOpenChange: (open: boolean) => void;
}

export function PlayerProfilePanel({
  open,
  playerId,
  bio,
  stats,
  onOpenChange,
}: PlayerProfilePanelProps) {
  const [state, setState] = useState<FetchState>({ status: "loading" });
  const [strengthState, setStrengthState] = useState<(typeof STRENGTH_STATES)[number]>("5v5");
  const [photoFailed, setPhotoFailed] = useState(false);

  const isGoalie = (bio?.position_code ?? stats?.position_code) === "G";

  useEffect(() => {
    setPhotoFailed(false);
  }, [playerId]);

  useEffect(() => {
    if (!open || isGoalie) return;
    setState({ status: "loading" });
    fetch(`/api/players/${playerId}/advanced`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed (${res.status})`);
        return res.json();
      })
      .then((data: PlayerAdvancedStats) => setState({ status: "ready", data }))
      .catch((err: Error) => setState({ status: "error", message: err.message }));
  }, [open, playerId, isGoalie]);

  const current = state.status === "ready" ? state.data.strength_states[strengthState] : undefined;
  const playerName = stats
    ? `${stats.first_name} ${stats.last_name}`
    : bio
      ? `${bio.first_name} ${bio.last_name}`
      : "";
  const teamAbbrev = bio?.team_abbrev ?? stats?.team_abbrev ?? "";
  const positionCode = bio?.position_code ?? stats?.position_code ?? "";
  const colors = teamColors(teamAbbrev);
  const age = bio ? computeAge(bio.birth_date) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader
          className="pl-3"
          style={colors ? { borderLeft: `4px solid ${colors.primary}` } : undefined}
        >
          <div className="flex items-center gap-4">
            {bio?.headshot_url && !photoFailed ? (
              <img
                src={bio.headshot_url}
                alt={playerName}
                className="h-16 w-16 rounded-full object-cover bg-muted"
                onError={() => setPhotoFailed(true)}
              />
            ) : (
              <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
                <User className="h-8 w-8 text-muted-foreground" aria-hidden />
              </div>
            )}
            <div className="flex-1">
              <DialogTitle className="flex items-center gap-2">
                {playerName}
                {bio?.sweater_number != null && (
                  <span className="text-muted-foreground font-normal">#{bio.sweater_number}</span>
                )}
              </DialogTitle>
              <div className="text-sm text-muted-foreground">
                {positionCode}
                {teamAbbrev ? ` · ${teamAbbrev}` : ""}
              </div>
            </div>
            {teamAbbrev && colors && (
              <img src={logoUrl(teamAbbrev)} alt={`${teamAbbrev} logo`} className="h-10 w-10" />
            )}
          </div>
        </DialogHeader>

        {bio && (
          <div className="text-sm text-muted-foreground">
            <div>
              {age !== null ? `${age} yrs` : ""}
              {bio.height ? ` · ${bio.height}` : ""}
              {bio.weight_pounds != null ? ` · ${bio.weight_pounds} lb` : ""}
              {bio.shoots_catches ? ` · Shoots: ${bio.shoots_catches}` : ""}
            </div>
            <div>{birthplaceLabel(bio)}</div>
            <div>Drafted: {draftLabel(bio)}</div>
          </div>
        )}

        {stats &&
          (isGoalie ? (
            <div className="grid grid-cols-4 gap-2 text-center text-sm">
              <StatCell label="GP" value={stats.gp?.toString() ?? "-"} />
              <StatCell label="W" value={stats.wins?.toString() ?? "-"} />
              <StatCell label="L" value={stats.losses?.toString() ?? "-"} />
              <StatCell label="OTL" value={stats.ot_losses?.toString() ?? "-"} />
              <StatCell label="SV%" value={formatSavePct(stats.save_pct)} />
              <StatCell label="GAA" value={formatGaa(stats.gaa)} />
              <StatCell label="SO" value={stats.shutouts?.toString() ?? "-"} />
            </div>
          ) : (
            <div className="grid grid-cols-6 gap-2 text-center text-sm">
              <StatCell label="GP" value={stats.gp?.toString() ?? "-"} />
              <StatCell label="G" value={stats.goals?.toString() ?? "-"} />
              <StatCell label="A" value={stats.assists?.toString() ?? "-"} />
              <StatCell label="P" value={stats.points?.toString() ?? "-"} />
              <StatCell label="+/-" value={formatPlusMinus(stats.plus_minus)} />
              <StatCell label="PIM" value={stats.pim?.toString() ?? "-"} />
            </div>
          ))}

        {!isGoalie && (
          <>
            {state.status === "loading" && (
              <div className="p-4 text-sm">Loading advanced stats...</div>
            )}
            {state.status === "error" && (
              <div className="p-4 text-sm text-destructive">{state.message}</div>
            )}

            {state.status === "ready" && (
              <div className="flex flex-col gap-4">
                <div className="flex gap-2">
                  {STRENGTH_STATES.map((s) => (
                    <Button
                      key={s}
                      size="sm"
                      variant={strengthState === s ? "default" : "outline"}
                      onClick={() => setStrengthState(s)}
                    >
                      {s}
                    </Button>
                  ))}
                </div>

                <div className="grid grid-cols-5 gap-2">
                  <PercentileBox label="CF%" value={current?.cf_pct ?? null} pctile={current?.cf_pctile ?? null} />
                  <PercentileBox label="FF%" value={current?.ff_pct ?? null} pctile={current?.ff_pctile ?? null} />
                  <PercentileBox label="HDCF%" value={current?.hdcf_pct ?? null} pctile={current?.hdcf_pctile ?? null} />
                  <PercentileBox
                    label="Primary Pts"
                    value={current?.primary_points ?? null}
                    pctile={current?.primary_points_pctile ?? null}
                  />
                  <div className="rounded-lg bg-muted p-3 text-center">
                    <div className="text-xs text-muted-foreground">PDO</div>
                    <div className="text-2xl font-semibold tabular-nums">
                      {state.data.pdo === null ? "-" : state.data.pdo}
                    </div>
                  </div>
                </div>

                <div className="h-40 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={state.data.trend}>
                      <XAxis dataKey="season_id" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip />
                      <Line type="monotone" dataKey="cf_pct" stroke="var(--color-sky-500)" dot />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Delete the old component and test files**

```bash
git rm frontend/src/components/PlayerAdvancedPanel.tsx frontend/src/components/PlayerAdvancedPanel.test.tsx
```

- [ ] **Step 5: Run tests to verify they pass**

Run (from `frontend/`): `npx vitest run src/components/PlayerProfilePanel.test.tsx`
Expected: All 8 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/PlayerProfilePanel.tsx frontend/src/components/PlayerProfilePanel.test.tsx
git commit -m "feat: extend PlayerAdvancedPanel into full PlayerProfilePanel"
```

---

### Task 6: Frontend — wire `PlayerProfilePanel` into `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `PlayerTable`'s `onOpenProfile` prop (Task 4), `PlayerProfilePanel`'s `{ open, playerId, bio, stats, onOpenChange }` props (Task 5).
- Produces: nothing new for other tasks — this is the final integration point.

- [ ] **Step 1: Write the failing test**

In `frontend/src/App.test.tsx`, add (after the existing tests, inside the `describe("App", ...)` block):

```tsx
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
    render(<App />);
    await screen.findByText("MacKinnon");

    const row = document.querySelector('[data-player-id="1"]')!;
    await userEvent.click(row);

    expect(await screen.findByText("Nathan MacKinnon")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/App.test.tsx -t "opens the profile panel"`
Expected: FAIL — clicking the row does nothing yet (still wired to the old `onOpenAdvanced`/`PlayerAdvancedPanel`).

- [ ] **Step 3: Implement — update imports, state, and wiring**

In `frontend/src/App.tsx`:

Replace line 4:
```tsx
import { PlayerAdvancedPanel } from "@/components/PlayerAdvancedPanel";
```
with:
```tsx
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
```

Replace line 41:
```tsx
  const [advancedPlayerId, setAdvancedPlayerId] = useState<number | null>(null);
```
with:
```tsx
  const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);
```

Replace the `<PlayerTable ... />` block (around line 199-206):
```tsx
          <PlayerTable
            rows={rows}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={handleSort}
            onOpenAdvanced={setAdvancedPlayerId}
          />
```
with:
```tsx
          <PlayerTable
            rows={rows}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={handleSort}
            onOpenProfile={setProfilePlayerId}
          />
```

Replace the `{advancedPlayerId !== null && (...)}` block (around line 209-223):
```tsx
      {advancedPlayerId !== null && (
        <PlayerAdvancedPanel
          open={advancedPlayerId !== null}
          playerId={advancedPlayerId}
          playerName={
            (() => {
              const p = rows.find((r) => r.player_id === advancedPlayerId);
              return p ? `${p.first_name} ${p.last_name}` : "";
            })()
          }
          onOpenChange={(open) => {
            if (!open) setAdvancedPlayerId(null);
          }}
        />
      )}
```
with:
```tsx
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
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/App.test.tsx -t "opens the profile panel"`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite to check for regressions**

Run (from `frontend/`): `npm test`
Expected: All tests PASS across every `.test.tsx` file.

- [ ] **Step 6: Run the frontend build**

Run (from `frontend/`): `npm run build`
Expected: PASS (0 TypeScript errors), producing `../static/dist/app.js` and `../static/dist/app.css`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat: wire PlayerProfilePanel into App with merged bio+stats data"
```

---

### Task 7: Manual verification in the running app

**Files:** none (verification only, per `verification-before-completion`).

- [ ] **Step 1: Run the full backend test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS.

- [ ] **Step 2: Run the full frontend test suite and build**

Run (from `frontend/`): `npm test && npm run build`
Expected: All PASS; build succeeds.

- [ ] **Step 3: Restart the app with the new build**

```bash
bash scripts/launch_app.sh
```
Expected: Opens `http://127.0.0.1:5099/` in the browser (or confirms it's already serving the new build — kill any stale process on port 5099 first if `launch_app.sh` reports the server already up from a pre-rebuild state).

- [ ] **Step 4: Manually verify each scenario from the spec's Testing Plan**

In the running app, click into (whole-row click, and Enter/Space while a row is focused):
- A skater with a headshot (e.g. Connor McDavid) — confirm photo, team-color accent bar, team logo, bio row (age/height/weight/shoots/birthplace/draft), skater box score, and the advanced-stats section (strength-state toggle, percentile boxes, trend chart) all render correctly.
- A skater/player with no `headshot_url` — confirm the silhouette fallback renders in the same slot with no layout shift.
- An undrafted player — confirm "Undrafted" renders instead of a broken draft string.
- A goalie — confirm the goalie box score (W/L/OTL/SV%/GAA/SO) renders and the advanced-stats section is completely absent (not just empty).
- A player with `team_abbrev` of `"UNK"` (if one exists in current data — check via `sqlite3 data/nhl_stats.db "SELECT player_id, first_name, last_name FROM players WHERE current_team_id IS NULL LIMIT 1;"`) — confirm no accent bar/logo renders and nothing crashes.

Expected: All scenarios render as designed, no console errors.

- [ ] **Step 5: Update `.wolf/anatomy.md` and append to `.wolf/memory.md`**

Per this project's `.claude/rules/openwolf.md` convention — reflect the renamed component (`PlayerAdvancedPanel` → `PlayerProfilePanel`) and the new `teamBranding.ts` file.
