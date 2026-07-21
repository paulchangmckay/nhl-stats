import type { Team, Player, PlayerStats } from "./types";

export const MOCK_TEAMS: Team[] = [
  { abbrev: "COL", common_name: "Colorado Avalanche" },
  { abbrev: "EDM", common_name: "Edmonton Oilers" },
  { abbrev: "TOR", common_name: "Toronto Maple Leafs" },
];

export const MOCK_PLAYERS: Player[] = [
  {
    player_id: 1, sweater_number: 29, first_name: "Nathan", last_name: "MacKinnon",
    position_code: "C", shoots_catches: "R", height: "6'0\"", weight_pounds: 181,
    birth_date: "1995-09-01", birth_country: "CAN",
    team_abbrev: "COL", team_name: "Avalanche", team_place_name: "Colorado",
  },
  {
    player_id: 2, sweater_number: 97, first_name: "Connor", last_name: "McDavid",
    position_code: "C", shoots_catches: "L", height: "6'1\"", weight_pounds: 193,
    birth_date: "1997-01-13", birth_country: "CAN",
    team_abbrev: "EDM", team_name: "Oilers", team_place_name: "Edmonton",
  },
  {
    player_id: 3, sweater_number: 31, first_name: "Anthony", last_name: "Stolarz",
    position_code: "G", shoots_catches: "L", height: "6'6\"", weight_pounds: 240,
    birth_date: "1994-01-20", birth_country: "USA",
    team_abbrev: "TOR", team_name: "Maple Leafs", team_place_name: "Toronto",
  },
];

export const MOCK_STATS: PlayerStats[] = [
  {
    player_id: 1, first_name: "Nathan", last_name: "MacKinnon", position_code: "C",
    team_abbrev: "COL", team_name: "Avalanche",
    gp: 82, goals: 44, assists: 84, points: 128, plus_minus: 32, pim: 42,
    pp_goals: 14, sh_goals: 1, shots: 297, shooting_pct: 14.8, avg_toi: "21:17",
    wins: null, losses: null, ot_losses: null, shutouts: null, save_pct: null, gaa: null,
  },
  {
    player_id: 2, first_name: "Connor", last_name: "McDavid", position_code: "C",
    team_abbrev: "EDM", team_name: "Oilers",
    gp: 76, goals: 32, assists: 88, points: 120, plus_minus: 12, pim: 30,
    pp_goals: 8, sh_goals: 2, shots: 246, shooting_pct: 13.0, avg_toi: "21:52",
    wins: null, losses: null, ot_losses: null, shutouts: null, save_pct: null, gaa: null,
  },
  {
    player_id: 3, first_name: "Anthony", last_name: "Stolarz", position_code: "G",
    team_abbrev: "TOR", team_name: "Maple Leafs",
    gp: 41, goals: null, assists: null, points: null, plus_minus: null, pim: 2,
    pp_goals: null, sh_goals: null, shots: null, shooting_pct: null, avg_toi: null as never,
    wins: 24, losses: 10, ot_losses: 4, shutouts: 3, save_pct: 0.918, gaa: 2.14,
  },
];
