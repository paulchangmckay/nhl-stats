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
