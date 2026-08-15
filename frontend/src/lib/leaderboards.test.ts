import { describe, it, expect } from "vitest";
import { computeLeaderboards, type RankingRow } from "./leaderboards";

function skater(overrides: Partial<RankingRow> = {}): RankingRow {
  return {
    player_id: 1, name: "Test Skater", team_abbrev: "COL", position_group: "F",
    primary_points_per60_z: 1.0, shots_per60_z: 1.0,
    ca_per60_z: 0.5, hdca_per60_z: 0.5,
    sv_pct_z: null, gaa_z: null,
    ...overrides,
  };
}

function goalie(overrides: Partial<RankingRow> = {}): RankingRow {
  return {
    player_id: 2, name: "Test Goalie", team_abbrev: "COL", position_group: "G",
    primary_points_per60_z: null, shots_per60_z: null,
    ca_per60_z: null, hdca_per60_z: null,
    sv_pct_z: 1.0, gaa_z: -1.0,
    ...overrides,
  };
}

describe("computeLeaderboards", () => {
  it("computes the offense score as the weighted sum of primary_points_per60_z and shots_per60_z", () => {
    const { offense } = computeLeaderboards([skater({ primary_points_per60_z: 2.0, shots_per60_z: 1.0 })]);
    expect(offense[0].score).toBeCloseTo(0.62 * 2.0 + 0.38 * 1.0, 5);
  });

  it("computes the defense score as the weighted sum of the NEGATED ca/hdca z-scores", () => {
    const { defense } = computeLeaderboards([skater({ ca_per60_z: 1.0, hdca_per60_z: 1.0 })]);
    // lower CA/HDCA is better -- a positive raw z (above-average shots against) must produce a NEGATIVE score
    expect(defense[0].score).toBeCloseTo(0.64 * -1.0 + 0.36 * -1.0, 5);
  });

  it("computes the goalie score from sv_pct_z and negated gaa_z", () => {
    const { goalie: goalieBoard } = computeLeaderboards([goalie({ sv_pct_z: 2.0, gaa_z: 1.0 })]);
    expect(goalieBoard[0].score).toBeCloseTo(0.67 * 2.0 + 0.33 * -1.0, 5);
  });

  it("sorts each leaderboard descending by score", () => {
    const low = skater({ player_id: 1, primary_points_per60_z: 0.1, shots_per60_z: 0.1 });
    const high = skater({ player_id: 2, primary_points_per60_z: 3.0, shots_per60_z: 3.0 });
    const { offense } = computeLeaderboards([low, high]);
    expect(offense.map((p) => p.player_id)).toEqual([2, 1]);
  });

  it("excludes goalies from offense/defense and skaters from the goalie board", () => {
    const { offense, defense, goalie: goalieBoard } = computeLeaderboards([skater(), goalie()]);
    expect(offense.every((p) => p.player_id !== 2)).toBe(true);
    expect(defense.every((p) => p.player_id !== 2)).toBe(true);
    expect(goalieBoard.every((p) => p.player_id !== 1)).toBe(true);
  });

  it("excludes a row from a leaderboard when its required z-score fields are null", () => {
    const { offense } = computeLeaderboards([skater({ primary_points_per60_z: null })]);
    expect(offense).toHaveLength(0);
  });
});
