import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Leaderboard } from "@/components/Leaderboard";
import { PlayerProfilePanel } from "@/components/PlayerProfilePanel";
import { computeLeaderboards, type RankingRow } from "@/lib/leaderboards";
import { LATEST_SEASON_ID } from "@/lib/season";
import { teamColors, logoUrl } from "@/lib/teamBranding";
import type { Team, Player, PlayerStats } from "@/lib/types";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request to ${url} failed (${res.status})`);
  return res.json() as Promise<T>;
}

export default function TeamPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const [teams, setTeams] = useState<Team[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [stats, setStats] = useState<PlayerStats[]>([]);
  const [rankings, setRankings] = useState<RankingRow[]>([]);
  const [profilePlayerId, setProfilePlayerId] = useState<number | null>(null);

  useEffect(() => {
    if (!teamId) return;
    fetchJson<Team[]>("/api/teams").then(setTeams);
    fetchJson<Player[]>("/api/players").then(setPlayers);
    fetchJson<PlayerStats[]>(`/api/players/stats?seasons=${LATEST_SEASON_ID}`).then(setStats);
    fetchJson<RankingRow[]>(
      `/api/players/rankings?season=${LATEST_SEASON_ID}&team=${teamId}`
    ).then(setRankings);
  }, [teamId]);

  if (!teamId) return null;

  const team = teams.find((t) => t.abbrev === teamId);
  const colors = teamColors(teamId);
  const { offense, defense, goalie } = computeLeaderboards(rankings);

  const bio = players.find((p) => p.player_id === profilePlayerId);
  const playerStats = stats.find((s) => s.player_id === profilePlayerId);

  return (
    <div>
      <div
        className="flex items-center gap-4 p-6"
        style={colors ? { backgroundColor: colors.primary, color: "#fff" } : undefined}
      >
        <img src={logoUrl(teamId)} alt={`${teamId} logo`} className="h-16 w-16" />
        <h1 className="text-2xl font-bold">{team?.common_name ?? teamId}</h1>
      </div>
      <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-3">
        <Leaderboard title="Top Offense" players={offense.slice(0, 5)} onSelectPlayer={setProfilePlayerId} />
        <Leaderboard title="Top Defense" players={defense.slice(0, 5)} onSelectPlayer={setProfilePlayerId} />
        <Leaderboard title="Top Goalie" players={goalie.slice(0, 5)} onSelectPlayer={setProfilePlayerId} />
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
