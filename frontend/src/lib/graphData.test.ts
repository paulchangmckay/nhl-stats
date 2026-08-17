import { describe, it, expect } from "vitest";
import { computeChartData } from "./graphData";
import type { AdvancedTrendPoint } from "./types";

// Same fixture shape as PlayerProfilePanel.test.tsx's MOCK_ADVANCED.trend:
// two 5v5 rows (different seasons) and one 5v4 row.
const TREND: AdvancedTrendPoint[] = [
  {
    season_id: "20232024", strength_state: "5v5", cf_pct: 55.0, ff_pct: 54.0, hdcf_pct: 58.0,
    primary_points: 10, pdo: 998.0, shots_per60: 20.0, chances_per60: 6.0,
    rebounds_created_per60: 3.0, deflections_per60: 1.0, points_per60: 15.0, primary_points_per60: 10.0,
  },
  {
    season_id: "20242025", strength_state: "5v5", cf_pct: 60.0, ff_pct: 60.0, hdcf_pct: 66.7,
    primary_points: 15, pdo: 1005.3, shots_per60: 24.0, chances_per60: 8.0,
    rebounds_created_per60: 4.0, deflections_per60: 2.0, points_per60: 20.0, primary_points_per60: 15.0,
  },
  {
    season_id: "20242025", strength_state: "5v4", cf_pct: 80.0, ff_pct: 83.3, hdcf_pct: 80.0,
    primary_points: 5, pdo: null, shots_per60: null, chances_per60: null,
    rebounds_created_per60: null, deflections_per60: null, points_per60: null, primary_points_per60: null,
  },
];

describe("computeChartData", () => {
  it("filters to the selected strength state for a strength-aware metric", () => {
    const result = computeChartData(TREND, "cf_pct", "5v4");
    expect(result).toHaveLength(1);
    expect(result[0].strength_state).toBe("5v4");
    expect(result[0].cf_pct).toBe(80.0);
  });

  it("returns all matching rows across seasons for the default 5v5 strength state", () => {
    const result = computeChartData(TREND, "cf_pct", "5v5");
    expect(result).toHaveLength(2);
    expect(result.every((row) => row.strength_state === "5v5")).toBe(true);
  });

  it("ignores the strength-state toggle for a non-strength-aware (per60) metric, always using 5v5", () => {
    const result = computeChartData(TREND, "shots_per60", "5v4");
    expect(result).toHaveLength(2);
    expect(result.every((row) => row.strength_state === "5v5")).toBe(true);
  });
});
