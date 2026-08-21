import { useEffect, useMemo, useRef, useState } from "react";
import { Toolbar } from "@/components/Toolbar";
import { PlayerTable, type PlayerTableHandle } from "@/components/PlayerTable";
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { matchesQuery } from "@/lib/search";
import { useUrlFilters } from "@/lib/useUrlFilters";
import { DEFAULT_FILTERS } from "@/lib/urlFilters";
import type { Team, Player, PlayerStats } from "@/lib/types";

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

  const { filters, seasons, sortKey, sortDir, setFilters, setSeasons, setSort } = useUrlFilters();
  const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);
  const tableRef = useRef<PlayerTableHandle>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

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
  }, [filters, seasons, teamsState.status, playersState.status]);

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
      setSort(key, sortDir === "asc" ? "desc" : "asc");
    } else {
      setSort(key, "desc");
    }
  }

  function handleSelectSuggestion(player: Player) {
    setFilters(DEFAULT_FILTERS);
    requestAnimationFrame(() => {
      tableRef.current?.scrollToPlayer(player.player_id);
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
