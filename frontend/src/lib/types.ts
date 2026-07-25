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
  cf_pct_5v5?: number | null;
}

export type SortDirection = "asc" | "desc";

export interface StatMins {
  gp: number | null;
  goals: number | null;
  assists: number | null;
  points: number | null;
}

export interface AdvancedStrengthState {
  cf: number;
  ca: number;
  cf_pct: number | null;
  ff: number;
  fa: number;
  ff_pct: number | null;
  hdcf: number;
  hdca: number;
  hdcf_pct: number | null;
  primary_points: number;
  cf_pctile: number | null;
  ff_pctile: number | null;
  hdcf_pctile: number | null;
  primary_points_pctile: number | null;
}

export interface AdvancedTrendPoint {
  season_id: string;
  cf_pct: number | null;
}

export interface PlayerAdvancedStats {
  player_id: number;
  season_id: string | null;
  strength_states: Record<string, AdvancedStrengthState>;
  trend: AdvancedTrendPoint[];
  pdo: number | null;
}
