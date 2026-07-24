import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PlayerAdvancedPanel } from "./PlayerAdvancedPanel";
import type { PlayerAdvancedStats } from "@/lib/types";

const MOCK_DATA: PlayerAdvancedStats = {
  player_id: 1,
  season_id: "20242025",
  strength_states: {
    "5v5": {
      cf: 60, ca: 40, cf_pct: 60.0, ff: 45, fa: 30, ff_pct: 60.0,
      hdcf: 10, hdca: 5, hdcf_pct: 66.7, primary_points: 15,
      cf_pctile: 75.0, ff_pctile: 80.0, hdcf_pctile: 60.0, primary_points_pctile: 90.0,
    },
    "5v4": {
      cf: 20, ca: 5, cf_pct: 80.0, ff: 15, fa: 3, ff_pct: 83.3,
      hdcf: 4, hdca: 1, hdcf_pct: 80.0, primary_points: 5,
      cf_pctile: 55.0, ff_pctile: 60.0, hdcf_pctile: 50.0, primary_points_pctile: 65.0,
    },
  },
  trend: [
    { season_id: "20232024", cf_pct: 55.0 },
    { season_id: "20242025", cf_pct: 60.0 },
  ],
  pdo: 1005.3,
};

describe("PlayerAdvancedPanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_DATA) } as Response)
    ));
  });

  it("renders percentile boxes and the plain PDO value box once data loads", async () => {
    render(
      <PlayerAdvancedPanel open playerId={1} playerName="Test Player" onOpenChange={() => {}} />
    );

    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument()); // CF% percentile
    expect(screen.getByText("1005.3")).toBeInTheDocument(); // PDO plain value
  });

  it("switches the displayed strength state when the selector changes", async () => {
    render(
      <PlayerAdvancedPanel open playerId={1} playerName="Test Player" onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "5v4" }));

    await waitFor(() => expect(screen.getByText("55")).toBeInTheDocument()); // 5v4's cf_pctile
  });
});
