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
  const bio = players.find((p) => p.player_id === profilePlayerId);
  const playerStats = stats.find((s) => s.player_id === profilePlayerId);

  return (
    <div>
      <h1 className="p-6 text-2xl font-bold">Top Players</h1>
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
      {profilePlayerId !== null && (
        <PlayerProfilePanel
          open={profilePlayerId !== null}
          playerId={profilePlayerId}
          bio={bio}
          stats={playerStats}
          onOpenChange={(open) => {
            if (!open) setProfilePlayerId(null);
          }}
        />
      )}
    </div>
  );
}
