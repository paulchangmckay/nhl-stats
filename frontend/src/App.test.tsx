import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
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

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url: string) => mockFetchOnce(url)));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("loads teams, players, and default-season stats, then renders the table", async () => {
    render(<App />);
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
    render(<App />);
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
    render(<App />);
    await screen.findByText(/failed to load/i);
    shouldFail = false;
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByText("MacKinnon")).toBeInTheDocument());
  });

  it("narrows rows when a search query is typed", async () => {
    render(<App />);
    await screen.findByText("MacKinnon");
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "McDavid");
    expect(screen.queryByText("MacKinnon")).not.toBeInTheDocument();
    expect(screen.getByText("McDavid")).toBeInTheDocument();
  });

  it("shows the player count, narrowed when a filter is active", async () => {
    render(<App />);
    await screen.findByText("MacKinnon");
    expect(screen.getByText("3 players")).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "McDavid");
    expect(screen.getByText("1 of 3 players")).toBeInTheDocument();
  });

  it("clears other filters, scrolls to, and highlights the row when a suggestion is clicked", async () => {
    render(<App />);
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

  it("wraps the table in a single bounded-height scroll container (bug-008 regression guard)", async () => {
    render(<App />);
    await screen.findByText("MacKinnon");
    const wrap = document.querySelector('[data-testid="table-wrap"]');
    expect(wrap).not.toBeNull();
    const style = wrap!.getAttribute("style") || "";
    expect(style).toMatch(/height/);
    expect(wrap).toHaveClass("overflow-auto");
  });
});
