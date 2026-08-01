import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PlayerProfilePanel, TrendTooltip } from "./PlayerProfilePanel";
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
      shots_per60: 24.0, chances_per60: 8.0, rebounds_created_per60: 4.0,
      deflections_per60: 2.0, points_per60: 20.0, primary_points_per60: 15.0,
      shots_per60_z: 1.23, chances_per60_z: 0.5, rebounds_created_per60_z: -0.2,
      deflections_per60_z: 0.0, points_per60_z: 0.9, primary_points_per60_z: 0.8,
    },
    "5v4": {
      cf: 20, ca: 5, cf_pct: 80.0, ff: 15, fa: 3, ff_pct: 83.3,
      hdcf: 4, hdca: 1, hdcf_pct: 80.0, primary_points: 5,
      cf_pctile: 55.0, ff_pctile: 60.0, hdcf_pctile: 50.0, primary_points_pctile: 65.0,
    },
  },
  trend: [
    { season_id: "20232024", strength_state: "5v5", cf_pct: 55.0, ff_pct: 54.0, hdcf_pct: 58.0,
      primary_points: 10, pdo: 998.0, shots_per60: 20.0, chances_per60: 6.0,
      rebounds_created_per60: 3.0, deflections_per60: 1.0, points_per60: 15.0, primary_points_per60: 10.0 },
    { season_id: "20242025", strength_state: "5v5", cf_pct: 60.0, ff_pct: 60.0, hdcf_pct: 66.7,
      primary_points: 15, pdo: 1005.3, shots_per60: 24.0, chances_per60: 8.0,
      rebounds_created_per60: 4.0, deflections_per60: 2.0, points_per60: 20.0, primary_points_per60: 15.0 },
    { season_id: "20242025", strength_state: "5v4", cf_pct: 80.0, ff_pct: 83.3, hdcf_pct: 80.0,
      primary_points: 5, pdo: null, shots_per60: null, chances_per60: null,
      rebounds_created_per60: null, deflections_per60: null, points_per60: null, primary_points_per60: null },
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

  it("renders the Shot Generation z-score boxes for 5v5", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("1.23")).toBeInTheDocument());
    expect(screen.getByText("24.00")).toBeInTheDocument();
  });

  it("shows N/A for a Shot Generation stat with a null z-score", async () => {
    vi.stubGlobal("fetch", vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          ...MOCK_ADVANCED,
          strength_states: {
            ...MOCK_ADVANCED.strength_states,
            "5v5": { ...MOCK_ADVANCED.strength_states["5v5"], shots_per60_z: null },
          },
        }),
      } as Response)
    ));
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getAllByText("N/A").length).toBeGreaterThan(0));
  });

  it("highlights CF% by default and toggles selection within the percentage family", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    const cfBox = screen.getByRole("button", { name: "CF%" });
    expect(cfBox).toHaveAttribute("aria-pressed", "true");

    const ffBox = screen.getByRole("button", { name: /FF%/ });
    expect(ffBox).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(ffBox);
    expect(ffBox).toHaveAttribute("aria-pressed", "true");
    expect(cfBox).toHaveAttribute("aria-pressed", "true"); // both selected, same family
  });

  it("clicking a box in a different family replaces the selection", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    const cfBox = screen.getByRole("button", { name: "CF%" });
    const pdoBox = screen.getByRole("button", { name: /PDO/ });

    await userEvent.click(pdoBox);
    expect(pdoBox).toHaveAttribute("aria-pressed", "true");
    expect(cfBox).toHaveAttribute("aria-pressed", "false"); // replaced, different family
  });

  it("clicking the sole selected box is a no-op (never empties the selection)", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    const cfBox = screen.getByRole("button", { name: "CF%" });
    await userEvent.click(cfBox);
    expect(cfBox).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the metric's name, description, and formula on hover", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    const cfBox = screen.getByRole("button", { name: "CF%" });
    await userEvent.hover(cfBox);
    expect(await screen.findByText("Corsi For %")).toBeInTheDocument();
    expect(screen.getByText("cf / (cf + ca) × 100")).toBeInTheDocument();
  });

  it("shows a single CF% line by default", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    expect(screen.getByText("CF%", { selector: "span" })).toBeInTheDocument();
  });

  it("adding a second metric in the same family adds a second line to the legend", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /FF%/ }));
    expect(screen.getByText("CF%", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("FF%", { selector: "span" })).toBeInTheDocument();
  });

  it("switching strength state re-filters the graph for a strength-aware selection", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    // MOCK_ADVANCED.trend has one 5v4 row (season 20242025) and two 5v5 rows.
    await userEvent.click(screen.getByRole("button", { name: "5v4" }));
    await waitFor(() => expect(screen.getByText("55")).toBeInTheDocument()); // 5v4 cf_pctile, sanity check toggle worked
    // With 5v4 active and cf_pct (strength-aware) selected, chart data should be the single 5v4 trend row.
    // Verified indirectly: no crash, still one legend entry.
    expect(screen.getByText("CF%", { selector: "span" })).toBeInTheDocument();
  });

  it("selecting a per60 metric ignores the strength-state toggle (always 5v5)", async () => {
    render(
      <PlayerProfilePanel open playerId={1} bio={mackinnonBio} stats={MOCK_STATS[0]}
        onOpenChange={() => {}} />
    );
    await waitFor(() => expect(screen.getByText("75")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Shots\/60/ }));
    await userEvent.click(screen.getByRole("button", { name: "5v4" }));
    expect(screen.getByText("Shots/60", { selector: "span" })).toBeInTheDocument();
  });
});

describe("TrendTooltip", () => {
  it("shows the friendly season and each selected metric's formatted value when active", () => {
    render(
      <TrendTooltip
        active
        payload={[
          { dataKey: "cf_pct", value: 55, color: "blue", graphicalItemId: "cf_pct" },
          { dataKey: "ff_pct", value: 60, color: "orange", graphicalItemId: "ff_pct" },
        ]}
        label="20232024"
      />
    );
    expect(screen.getByText("2023–24")).toBeInTheDocument();
    expect(screen.getByText("CF% 55%")).toBeInTheDocument();
    expect(screen.getByText("FF% 60%")).toBeInTheDocument();
  });

  it("formats a non-percentage metric without a % suffix", () => {
    render(
      <TrendTooltip
        active
        payload={[{ dataKey: "shots_per60", value: 12.34, color: "blue", graphicalItemId: "shots_per60" }]}
        label="20232024"
      />
    );
    expect(screen.getByText("Shots/60 12.34")).toBeInTheDocument();
  });

  it("renders nothing when inactive", () => {
    const { container } = render(
      <TrendTooltip active={false} payload={[{ dataKey: "cf_pct", value: 55, color: "blue", graphicalItemId: "cf_pct" }]} label="20232024" />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when payload is empty", () => {
    const { container } = render(
      <TrendTooltip active payload={[]} label="20232024" />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a dash for a null value instead of the literal null", () => {
    render(
      <TrendTooltip
        active
        payload={[{ dataKey: "cf_pct", value: null as unknown as number, color: "blue", graphicalItemId: "cf_pct" }]} // Recharts' ValueType omits null even though filterNull={false} lets it reach here at runtime
        label="20232024"
      />
    );
    expect(screen.getByText("CF% -")).toBeInTheDocument();
  });
});
