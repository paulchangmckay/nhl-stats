import { useEffect, useState } from "react";
import { Leaderboard } from "@/components/Leaderboard";
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
import { computeLeaderboards, type RankingRow } from "@/lib/leaderboards";
import { LATEST_SEASON_ID } from "@/lib/season";
import type { Player, PlayerStats } from "@/lib/types";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request to ${url} failed (${res.status})`);
  return res.json() as Promise<T>;
}

export default function TopPlayers() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [stats, setStats] = useState<PlayerStats[]>([]);
  const [rankings, setRankings] = useState<RankingRow[]>([]);
  const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);

  useEffect(() => {
    fetchJson<Player[]>("/api/players").then(setPlayers);
    fetchJson<PlayerStats[]>(`/api/players/stats?seasons=${LATEST_SEASON_ID}`).then(setStats);
    fetchJson<RankingRow[]>(`/api/players/rankings?season=${LATEST_SEASON_ID}`).then(setRankings);
  }, []);

  const { offense, defense, goalie } = computeLeaderboards(rankings);
  const bio = players.find((p) => p.player_id === profilePlayerId);
  const playerStats = stats.find((s) => s.player_id === profilePlayerId);

  return (
    <div>
      <h1 className="p-6 text-2xl font-bold">Top Players</h1>
      <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-3">
        <Leaderboard title="Top Offense" players={offense.slice(0, 15)} onSelectPlayer={setProfilePlayerId} />
        <Leaderboard title="Top Defense" players={defense.slice(0, 15)} onSelectPlayer={setProfilePlayerId} />
        <Leaderboard title="Top Goalie" players={goalie.slice(0, 15)} onSelectPlayer={setProfilePlayerId} />
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
