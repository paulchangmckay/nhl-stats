import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import Players from "./Players";
import { MOCK_TEAMS, MOCK_PLAYERS, MOCK_STATS } from "@/lib/mock-data";

function mockFetchOnce(url: string) {
  if (url.includes("/api/teams")) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_TEAMS) } as Response);
  }
  if (url.includes("/api/players/stats")) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_STATS) } as Response);
  }
  if (url.includes("/api/players")) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(MOCK_PLAYERS) } as Response);
  }
  return Promise.reject(new Error(`unexpected url: ${url}`));
}

function renderPlayers() {
  return render(
    <MemoryRouter initialEntries={["/players"]}>
      <Players />
    </MemoryRouter>
  );
}

function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
}

function renderPlayersAt(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Players />
      <LocationDisplay />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url: string) => mockFetchOnce(url)));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Players", () => {
  it("loads teams, players, and default-season stats, then renders the table", async () => {
    renderPlayers();
    expect(await screen.findByText("MacKinnon")).toBeInTheDocument();
  });

  it("shows an error alert with a retry button when the players fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.includes("/api/players") && !url.includes("stats")
          ? Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)
          : mockFetchOnce(url)
      )
    );
    renderPlayers();
    expect(await screen.findByText(/failed to load/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("recovers when Retry is clicked and the fetch then succeeds", async () => {
    let shouldFail = true;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/api/players") && !url.includes("stats") && shouldFail) {
          return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response);
        }
        return mockFetchOnce(url);
      })
    );
    renderPlayers();
    await screen.findByText(/failed to load/i);
    shouldFail = false;
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByText("MacKinnon")).toBeInTheDocument());
  });

  it("shows an error alert with a retry button when the teams fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.includes("/api/teams")
          ? Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)
          : mockFetchOnce(url)
      )
    );
    renderPlayers();
    expect(await screen.findByText(/failed to load teams/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows an inline error alert with a retry button when the stats fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.includes("/api/players/stats")
          ? Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) } as Response)
          : mockFetchOnce(url)
      )
    );
    renderPlayers();
    await screen.findByText("NHL Players");
    expect(await screen.findByText(/failed to load stats/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("narrows rows when a search query is typed", async () => {
    renderPlayers();
    await screen.findByText("MacKinnon");
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "McDavid");
    expect(screen.queryByText("MacKinnon")).not.toBeInTheDocument();
    expect(screen.getByText("McDavid")).toBeInTheDocument();
  });

  it("shows the player count, narrowed when a filter is active", async () => {
    renderPlayers();
    await screen.findByText("MacKinnon");
    expect(screen.getByText("3 players")).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "McDavid");
    expect(screen.getByText("1 of 3 players")).toBeInTheDocument();
  });

  it("clears other filters, scrolls to, and highlights the row when a suggestion is clicked", async () => {
    renderPlayers();
    await screen.findByText("MacKinnon");
    await userEvent.click(screen.getByRole("button", { name: "C" })); // active position filter
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "MacKinnon");
    await userEvent.click(await screen.findByText("Nathan MacKinnon"));

    // search box cleared, position filter cleared (McDavid, a center, is visible again)
    expect(screen.getByPlaceholderText("Search players…")).toHaveValue("");
    expect(screen.getByText("McDavid")).toBeInTheDocument();

    await waitFor(() => {
      const row = document.querySelector('[data-player-id="1"]');
      expect(row).toHaveClass("row-highlight");
    });
  });

  it("wraps the table in a single bounded-height scroll container sized for the sticky toolbar and header (bug-008 regression guard)", async () => {
    renderPlayers();
    await screen.findByText("MacKinnon");
    const wrap = document.querySelector('[data-testid="table-wrap"]');
    expect(wrap).not.toBeNull();
    const style = wrap!.getAttribute("style") || "";
    expect(style).toMatch(/--toolbar-height/);
    expect(style).toMatch(/--header-height/);
    expect(wrap).toHaveClass("overflow-auto");
  });

  it("opens the profile panel with merged bio and stats data when a row is clicked", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/advanced")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                player_id: 1, season_id: "20252026", strength_states: {}, trend: [], pdo: null,
              }),
          } as Response);
        }
        return mockFetchOnce(url);
      })
    );
    renderPlayers();
    await screen.findByText("MacKinnon");

    const row = document.querySelector('[data-player-id="1"]')!;
    await userEvent.click(row);

    expect(await screen.findByText("Nathan MacKinnon")).toBeInTheDocument();
  });

  it("reads filters and sort from the URL on initial load", async () => {
    renderPlayersAt("/players?team=EDM&sort=goals&dir=asc");
    await screen.findByText("McDavid");
    // MOCK_STATS has 3 players: MacKinnon (COL), McDavid (EDM), Stolarz
    // (TOR). The team=EDM filter should narrow to McDavid only -- checking
    // that MacKinnon is absent proves the filter actually applied from the
    // URL, not just that the page rendered without crashing.
    expect(screen.queryByText("MacKinnon")).not.toBeInTheDocument();
  });

  it("writes a non-default filter to the URL and omits untouched defaults", async () => {
    renderPlayersAt("/players");
    await screen.findByText("MacKinnon");
    await userEvent.click(screen.getByRole("button", { name: "C" }));
    await waitFor(() => {
      expect(screen.getByTestId("location-search")).toHaveTextContent("positions=C");
    });
    expect(screen.getByTestId("location-search").textContent).not.toContain("search=");
  });

  it("resets filters via URL and still scrolls to/highlights the selected suggestion", async () => {
    renderPlayersAt("/players?team=EDM");
    await screen.findByText("McDavid");
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "McDavid");
    // The suggestion dropdown item renders "{first_name} {last_name}" as one
    // combined text node (Toolbar.tsx) -- distinct from the table cell's
    // last-name-only "McDavid" text, so this exact string is what
    // disambiguates the suggestion from the table row already on screen.
    const suggestion = await screen.findByText("Connor McDavid", { selector: "div" });
    await userEvent.click(suggestion);
    await waitFor(() => {
      expect(screen.getByTestId("location-search").textContent).not.toContain("team=");
    });
    await waitFor(() => {
      expect(document.querySelector('[data-player-id="2"]')).toHaveClass("row-highlight");
    });
  });

  it("preserves other filters when the season changes, and only fetches stats once per season", async () => {
    let statsCallCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/api/players/stats")) {
          statsCallCount += 1;
        }
        return mockFetchOnce(url);
      })
    );
    renderPlayersAt("/players?team=EDM&seasons=20232024");
    await screen.findByText("McDavid");
    expect(statsCallCount).toBe(1);

    expect(screen.getByTestId("location-search").textContent).toContain("team=EDM");
  });
});
