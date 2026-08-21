# Broken States — Design

**Date:** 2026-08-19
**Status:** Approved
**Scope:** Group 2 of 3 from the [NHL Stats UI/UX audit](../../../.wolf/memory.md) — must-fix items #3 (Home empty section) and #4 (TeamPage/TopPlayers/Leaderboard silent failures).

## Problem

Three pages currently look broken to a user, live, not hypothetically:

1. **`Home.tsx:16`** — a large empty section renders below the hero, reserved for an unbuilt news feed (issue #118). Confirmed via full-page screenshot: roughly the entire remaining viewport is blank.
2. **`TeamPage.tsx:29-31` and `TopPlayers.tsx:23`** — both fetch `/api/players/rankings` with no `.catch()`. That endpoint currently 500s on the real backend (a separate, out-of-scope DB-schema bug: `no such column: z.ca_per60_z`). The unhandled rejection means both pages silently show three permanently empty "Top Offense/Defense/Goalie" cards with zero indication anything failed.
3. **`Leaderboard.tsx`** — has no empty-state branch at all. Even once the rankings fetch succeeds, a category that legitimately has zero qualifying players (e.g. a team with no goalie meeting the ranking threshold) renders a bare `<ol>` with nothing in it — indistinguishable from the broken-fetch case above.

## Goals

- Home no longer has a large unexplained blank area.
- A rankings-fetch failure on TeamPage/TopPlayers is visible to the user, with a way to retry, without hiding content (team header/logo) that isn't actually broken.
- A leaderboard category that's legitimately empty says so, distinguishably from a fetch error.

## Anti-goals

- Not building the real news feed (#118) — that's separate, tracked work. This just removes the dead space until it ships.
- Not adding error handling to TeamPage/TopPlayers' other three fetches (teams/players/stats) — those aren't reported broken; scope is the rankings fetch only, matching the audit finding.
- Not adding loading skeletons to these pages — a separate nice-to-have item from the audit, not bundled into this must-fix group.
- Not touching the backend 500 itself (missing DB column) — out of scope for a frontend audit group; the frontend must handle the failure gracefully regardless of its cause.

## Design

### Home (`frontend/src/pages/Home.tsx`)

**Corrected during grilling — the original "shrink the hero" plan was wrong.** `App.tsx:6` wraps every page in `min-h-screen`, which forces the page to fill the full viewport regardless of content height. Shrinking the hero's `py-24` padding would make the hero *shorter*, and since `min-h-screen` still forces the same total height, the empty area below would grow, not shrink — the opposite of the goal. The real defect isn't hero height; it's that the space has zero visual explanation for why it's blank.

Fix: replace the bare `{/* News feed (#118)... */}` comment with a lightweight text placeholder — no fetch, no new component:

```tsx
<p className="px-4 py-12 text-center text-sm text-muted-foreground">
  League news coming soon.
</p>
```

This keeps the hero exactly as it is today (no height change) and gives the remaining `min-h-screen` space a visible, honest explanation instead of looking broken.

### TeamPage.tsx / TopPlayers.tsx — scoped rankings error state

Both pages currently do:
```tsx
const [rankings, setRankings] = useState<RankingRow[]>([]);
// ...
fetchJson<RankingRow[]>(`/api/players/rankings?...`).then(setRankings);
```

Replace with the same `FetchState<T>` shape `Players.tsx` already defines locally (`Players.tsx:11-14`) — reused here, not shared into a common module, since it's a 4-line type alias and introducing a shared import for it would be over-engineering for two call sites:

```tsx
type FetchState<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };
```

```tsx
const [rankingsState, setRankingsState] = useState<FetchState<RankingRow[]>>({ status: "loading" });

function loadRankings() {
  setRankingsState({ status: "loading" });
  fetchJson<RankingRow[]>(`/api/players/rankings?...`)
    .then((data) => setRankingsState({ status: "ready", data }))
    .catch((err) => setRankingsState({ status: "error", message: err.message }));
}
```

`useEffect` calls `loadRankings()` instead of the old inline `.then(setRankings)` (dependency array unchanged — `[teamId]` for TeamPage, `[]` for TopPlayers). The other three fetches (`teams`, `players`, `stats`) are untouched — still plain `.then(setX)`, out of scope per the anti-goals above.

Rendering: the team header/logo (`TeamPage.tsx:45-51`) is unconditional and stays that way — it doesn't depend on rankings. The 3-column leaderboard grid wrapper (`<div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-3">`, `TeamPage.tsx:52-56` / `TopPlayers.tsx:33-37`) stays in place; what's conditional is only its children, branching on `rankingsState.status`:

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
      <Leaderboard title="Top Offense" players={offense.slice(0, N)} onSelectPlayer={setProfilePlayerId} />
      <Leaderboard title="Top Defense" players={defense.slice(0, N)} onSelectPlayer={setProfilePlayerId} />
      <Leaderboard title="Top Goalie" players={goalie.slice(0, N)} onSelectPlayer={setProfilePlayerId} />
    </>
  ) : null /* loading: matches current pre-fetch behavior, not a regression */}
</div>
```

(`N` is `5` on TeamPage, `15` on TopPlayers — unchanged from today.) `md:col-span-3` makes the `Alert` span the full grid width at the `md` breakpoint where the grid is actually 3 columns (it's 1 column below `md`, where spanning is a no-op). `offense`/`defense`/`goalie` are still derived via `computeLeaderboards(rankingsState.status === "ready" ? rankingsState.data : [])` — passing `[]` when not ready is safe since that branch of the JSX never reads them in that state.

### Leaderboard.tsx — empty-state branch

Add, before the existing `<ol>` map:
```tsx
{players.length === 0 ? (
  <p className="py-2 text-sm text-muted-foreground">No qualifying players.</p>
) : (
  <ol className="flex flex-col gap-1">
    {/* existing map, unchanged */}
  </ol>
)}
```

This fires for a genuinely empty category once `rankingsState.status === "ready"` — the parent no longer renders `<Leaderboard>` at all during `"loading"`/`"error"`, so this branch can't be mistaken for the fetch-failure case; by the time `<Leaderboard>` renders, the data is real.

## Testing

- **`Home.test.tsx`**: new test asserting the text "League news coming soon." renders — a direct, unambiguous check that the placeholder is in place.
- **`TeamPage.test.tsx`**: new test — mock `/api/players/rankings` to resolve `{ ok: false, status: 500 }`, render, assert the `Alert` with retry renders inside the leaderboard grid area *and* the team header (`"Colorado Avalanche"` per the existing fixture) still renders. A second assertion: clicking retry re-issues the rankings fetch (mock call count increments).
- **`TopPlayers.test.tsx`**: same shape as TeamPage's new test, without the team-header assertion (TopPlayers has no team header).
- **`Leaderboard.test.tsx`**: new test — render with `players={[]}`, assert "No qualifying players." renders and no `<ol>`/button role elements are present.

## Files touched

- `frontend/src/pages/Home.tsx` — hero padding
- `frontend/src/pages/TeamPage.tsx` — scoped `FetchState` for rankings, error/retry UI
- `frontend/src/pages/TopPlayers.tsx` — same
- `frontend/src/components/Leaderboard.tsx` — empty-state branch
- `frontend/src/pages/Home.test.tsx`, `frontend/src/pages/TeamPage.test.tsx`, `frontend/src/pages/TopPlayers.test.tsx`, `frontend/src/components/Leaderboard.test.tsx` — new tests per above
