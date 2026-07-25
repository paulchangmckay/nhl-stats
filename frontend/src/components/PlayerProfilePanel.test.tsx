import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PlayerProfilePanel } from "./PlayerProfilePanel";
import { MOCK_PLAYERS, MOCK_STATS } from "@/lib/mock-data";
import type { PlayerAdvancedStats } from "@/lib/types";

const MOCK_ADVANCED: PlayerAdvancedStats = {
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

const mackinnonBio = MOCK_PLAYERS[0];   // has headshot_url + draft info
const mcdavidStats = MOCK_STATS[1];
const stolarzBio = MOCK_PLAYERS[2];     // goalie: no headshot_url, undrafted
const stolarzStats = MOCK_STATS[2];

describe("PlayerProfilePanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_ADVANCED) } as Response)
    ));
  });

  it("renders header/bio/box-score immediately, without waiting on the advanced-stats fetch", () => {
    render(
      <PlayerProfilePanel
        open
        playerId={1}
        bio={mackinnonBio}
        stats={MOCK_STATS[0]}
        onOpenChange={() => {}}
      />
    );
    expect(screen.getByText("Nathan MacKinnon")).toBeInTheDocument();
    expect(screen.getByText(/Cole Harbour/)).toBeInTheDocument();
    expect(screen.getByText(/Rd 1, Pick 1 \(2013, COL\)/)).toBeInTheDocument();
  });

  it("shows the silhouette fallback when headshot_url is null", () => {
    render(
      <PlayerProfilePanel
        open
        playerId={3}
        bio={stolarzBio}
        stats={stolarzStats}
        onOpenChange={() => {}}
      />
    );
    expect(screen.queryByRole("img", { name: /Anthony Stolarz/ })).not.toBeInTheDocument();
  });

  it("shows 'Undrafted' when draft_year is null", () => {
    render(
      <PlayerProfilePanel
        open
        playerId={3}
        bio={stolarzBio}
        stats={stolarzStats}
        onOpenChange={() => {}}
      />
    );
    expect(screen.getByText(/Undrafted/)).toBeInTheDocument();
  });

  it("shows the goalie box score (W/L/SV%/GAA/SO) and hides the advanced-stats section for goalies", async () => {
    render(
      <PlayerProfilePanel
        open
        playerId={3}
        bio={stolarzBio}
        stats={stolarzStats}
        onOpenChange={() => {}}
      />
    );
    expect(screen.getByText("0.918")).toBeInTheDocument(); // save_pct
    expect(screen.getByText("24")).toBeInTheDocument(); // wins
    await waitFor(() => expect(screen.queryByText(/loading advanced stats/i)).not.toBeInTheDocument());
    expect(screen.queryByText("CF%")).not.toBeInTheDocument();
  });

  it("shows the skater box score (G/A/P/+/-/PIM) for skaters", () => {
    render(
      <PlayerProfilePanel
        open
        playerId={2}
        bio={MOCK_PLAYERS[1]}
        stats={mcdavidStats}
        onOpenChange={() => {}}
      />
    );
    expect(screen.getByText("32")).toBeInTheDocument(); // goals
    expect(screen.getByText("88")).toBeInTheDocument(); // assists
  });

  it("loads and renders the advanced-stats section for skaters", async () => {
    render(
      <PlayerProfilePanel
        open
        playerId={1}
        bio={mackinnonBio}
        stats={MOCK_STATS[0]}
        onOpenChange={() => {}}
      />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument()); // CF% percentile
    expect(screen.getByText("1005.3")).toBeInTheDocument(); // PDO
  });

  it("switches the displayed strength state when the selector changes", async () => {
    render(
      <PlayerProfilePanel
        open
        playerId={1}
        bio={mackinnonBio}
        stats={MOCK_STATS[0]}
        onOpenChange={() => {}}
      />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "5v4" }));
    await waitFor(() => expect(screen.getByText("55")).toBeInTheDocument()); // 5v4's cf_pctile
  });

  it("renders without crashing when bio is undefined (data-gap edge case)", () => {
    render(
      <PlayerProfilePanel
        open
        playerId={1}
        bio={undefined}
        stats={MOCK_STATS[0]}
        onOpenChange={() => {}}
      />
    );
    expect(screen.getByText("Nathan MacKinnon")).toBeInTheDocument();
  });
});
