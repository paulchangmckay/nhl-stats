export type MetricKey =
  | "cf_pct" | "ff_pct" | "hdcf_pct" | "primary_points" | "pdo"
  | "shots_per60" | "chances_per60" | "rebounds_created_per60"
  | "deflections_per60" | "points_per60" | "primary_points_per60";

export type MetricFamily = "percentage" | "count" | "composite" | "per60";

export interface MetricDefinition {
  label: string;
  name: string;
  description: string;
  formula: string;
  family: MetricFamily;
  strengthAware: boolean;
}

export const METRIC_DEFINITIONS: Record<MetricKey, MetricDefinition> = {
  cf_pct: {
    label: "CF%", name: "Corsi For %",
    description: "Share of shot attempts (on goal, missed, or blocked) this player's on-ice for vs. against.",
    formula: "cf / (cf + ca) × 100",
    family: "percentage", strengthAware: true,
  },
  ff_pct: {
    label: "FF%", name: "Fenwick For %",
    description: "Like CF%, but excludes blocked shots.",
    formula: "ff / (ff + fa) × 100",
    family: "percentage", strengthAware: true,
  },
  hdcf_pct: {
    label: "HDCF%", name: "High-Danger Corsi For %",
    description: "Share of high-danger shot attempts this player's on-ice for vs. against.",
    formula: "hdcf / (hdcf + hdca) × 100",
    family: "percentage", strengthAware: true,
  },
  primary_points: {
    label: "Primary Pts", name: "Primary Points",
    description: "Goals plus primary assists this player recorded (on-ice independent).",
    formula: "goals + primary assists",
    family: "count", strengthAware: true,
  },
  pdo: {
    label: "PDO", name: "PDO",
    description: "This player's team's on-ice shooting % plus save % at 5v5 — a puck-luck indicator that tends to regress toward 1000.",
    formula: "(shooting% + save%) × 1000",
    family: "composite", strengthAware: false,
  },
  shots_per60: {
    label: "Shots/60", name: "Individual Shot Attempts per 60",
    description: "This player's own shot attempts (on goal, missed, blocked, or goal) per 60 minutes of 5v5 ice time.",
    formula: "(SOG + missed + blocked + goals) / TOI hours",
    family: "per60", strengthAware: false,
  },
  chances_per60: {
    label: "Chances/60", name: "Individual High-Danger Chances per 60",
    description: "This player's own high-danger shot attempts per 60 minutes of 5v5 ice time.",
    formula: "individual high-danger shot attempts / TOI hours",
    family: "per60", strengthAware: false,
  },
  rebounds_created_per60: {
    label: "Rebounds Created/60", name: "Rebounds Created per 60",
    description: "Heuristic: a shot attempt within 3 seconds of this player's own shot attempt, same team, credited to the original shooter. Not possession-confirmed.",
    formula: "rebounds created / TOI hours",
    family: "per60", strengthAware: false,
  },
  deflections_per60: {
    label: "Deflections/60", name: "Deflections per 60",
    description: "This player's own shot attempts that were deflections or tip-ins, per 60 minutes of 5v5 ice time.",
    formula: "deflection/tip-in shot attempts / TOI hours",
    family: "per60", strengthAware: false,
  },
  points_per60: {
    label: "Points/60", name: "Points per 60",
    description: "Goals plus all assists per 60 minutes of 5v5 ice time.",
    formula: "(goals + assists) / TOI hours",
    family: "per60", strengthAware: false,
  },
  primary_points_per60: {
    label: "Primary Points/60", name: "Primary Points per 60",
    description: "Goals plus primary assists per 60 minutes of 5v5 ice time.",
    formula: "primary_points / TOI hours",
    family: "per60", strengthAware: false,
  },
};
