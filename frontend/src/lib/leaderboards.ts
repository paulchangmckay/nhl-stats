export interface RankingRow {
  player_id: number;
  name: string;
  team_abbrev: string;
  position_group: "F" | "D" | "G";
  primary_points_per60_z: number | null;
  shots_per60_z: number | null;
  ca_per60_z: number | null;
  hdca_per60_z: number | null;
  sv_pct_z: number | null;
  gaa_z: number | null;
}

export interface RankedPlayer {
  player_id: number;
  name: string;
  team_abbrev: string;
  score: number;
}

const OFFENSE_WEIGHTS = { primaryPoints: 0.62, shots: 0.38 };
const DEFENSE_WEIGHTS = { ca: 0.64, hdca: 0.36 };
const GOALIE_WEIGHTS = { svPct: 0.67, gaa: 0.33 };

function toRankedPlayer(row: RankingRow, score: number): RankedPlayer {
  return { player_id: row.player_id, name: row.name, team_abbrev: row.team_abbrev, score };
}

function sortDescending(players: RankedPlayer[]): RankedPlayer[] {
  return [...players].sort((a, b) => b.score - a.score);
}

export function computeLeaderboards(rows: RankingRow[]): {
  offense: RankedPlayer[];
  defense: RankedPlayer[];
  goalie: RankedPlayer[];
} {
  const skaters = rows.filter((r) => r.position_group === "F" || r.position_group === "D");
  const goalies = rows.filter((r) => r.position_group === "G");

  const offense = sortDescending(
    skaters
      .filter((r): r is RankingRow & { primary_points_per60_z: number; shots_per60_z: number } =>
        r.primary_points_per60_z != null && r.shots_per60_z != null
      )
      .map((r) =>
        toRankedPlayer(
          r,
          OFFENSE_WEIGHTS.primaryPoints * r.primary_points_per60_z +
            OFFENSE_WEIGHTS.shots * r.shots_per60_z
        )
      )
  );

  const defense = sortDescending(
    skaters
      .filter((r): r is RankingRow & { ca_per60_z: number; hdca_per60_z: number } =>
        r.ca_per60_z != null && r.hdca_per60_z != null
      )
      .map((r) =>
        toRankedPlayer(r, DEFENSE_WEIGHTS.ca * -r.ca_per60_z + DEFENSE_WEIGHTS.hdca * -r.hdca_per60_z)
      )
  );

  const goalie = sortDescending(
    goalies
      .filter((r): r is RankingRow & { sv_pct_z: number; gaa_z: number } =>
        r.sv_pct_z != null && r.gaa_z != null
      )
      .map((r) => toRankedPlayer(r, GOALIE_WEIGHTS.svPct * r.sv_pct_z + GOALIE_WEIGHTS.gaa * -r.gaa_z))
  );

  return { offense, defense, goalie };
}
