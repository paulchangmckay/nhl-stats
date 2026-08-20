import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { teamColors, logoUrl } from "@/lib/teamBranding";
import type { Team } from "@/lib/types";

export default function Teams() {
  const [teams, setTeams] = useState<Team[]>([]);

  useEffect(() => {
    fetch("/api/teams")
      .then((res) => res.json())
      .then(setTeams);
  }, []);

  return (
    <div className="grid grid-cols-2 gap-4 p-6 sm:grid-cols-4 lg:grid-cols-6">
      {teams
        .filter((team) => team.abbrev !== "UNK")
        .map((team) => {
        const colors = teamColors(team.abbrev);
        return (
          <Link
            key={team.abbrev}
            to={`/teams/${team.abbrev}`}
            className="flex min-w-0 flex-col items-center gap-2 rounded-lg border border-border p-4 text-center transition-colors hover:bg-muted"
            style={colors ? { borderTopColor: colors.primary, borderTopWidth: "4px" } : undefined}
          >
            <img src={logoUrl(team.abbrev)} alt={`${team.abbrev} logo`} className="h-12 w-12" />
            <span className="text-sm font-medium">{team.common_name}</span>
          </Link>
        );
      })}
    </div>
  );
}
