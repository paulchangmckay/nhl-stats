import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import TeamPage from "./TeamPage";

const TEAMS = [{ abbrev: "COL", common_name: "Colorado Avalanche" }];
const PLAYERS = [
  { player_id: 1, first_name: "Nathan", last_name: "MacKinnon", team_abbrev: "COL" },
];
const STATS = [{ player_id: 1, team_abbrev: "COL", points: 100 }];
const RANKINGS = [
  {
    player_id: 1, name: "Nathan MacKinnon", team_abbrev: "COL", position_group: "F",
    primary_points_per60_z: 2.0, shots_per60_z: 1.5,
    ca_per60_z: -0.5, hdca_per60_z: -0.3,
    sv_pct_z: null, gaa_z: null,
  },
];

function mockFetchOnce(url: string) {
  if (url.includes("/api/teams")) return Promise.resolve({ ok: true, json: () => Promise.resolve(TEAMS) } as Response);
  if (url.includes("/api/players/rankings")) return Promise.resolve({ ok: true, json: () => Promise.resolve(RANKINGS) } as Response);
  if (url.includes("/api/players/stats")) return Promise.resolve({ ok: true, json: () => Promise.resolve(STATS) } as Response);
  if (url.includes("/api/players")) return Promise.resolve({ ok: true, json: () => Promise.resolve(PLAYERS) } as Response);
  return Promise.reject(new Error(`unexpected url: ${url}`));
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url: string) => mockFetchOnce(url)));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TeamPage", () => {
  it("fetches team-scoped rankings and renders three leaderboards with the team's branded name", async () => {
    render(
      <MemoryRouter initialEntries={["/teams/COL"]}>
        <Routes>
          <Route path="/teams/:teamId" element={<TeamPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("Colorado Avalanche")).toBeInTheDocument();
    expect(screen.getByText("Top Offense")).toBeInTheDocument();
    expect(screen.getByText("Top Defense")).toBeInTheDocument();
    expect(screen.getByText("Top Goalie")).toBeInTheDocument();
    // Fixture qualifies this player for both Top Offense and Top Defense
    // (non-null offense AND defense z-scores), so the name legitimately
    // renders twice — findByText's single-match assumption doesn't hold.
    expect((await screen.findAllByText("Nathan MacKinnon")).length).toBeGreaterThan(0);

    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    const rankingsCall = fetchMock.mock.calls.find((c) => String(c[0]).includes("/api/players/rankings"));
    expect(rankingsCall![0]).toContain("team=COL");
  });
});
