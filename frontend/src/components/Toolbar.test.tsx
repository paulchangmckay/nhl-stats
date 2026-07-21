import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toolbar } from "./Toolbar";
import { MOCK_TEAMS, MOCK_PLAYERS } from "@/lib/mock-data";
import type { StatMins } from "@/lib/types";

const EMPTY_MINS: StatMins = { gp: null, goals: null, assists: null, points: null };

function baseProps(overrides = {}) {
  return {
    teams: MOCK_TEAMS,
    players: MOCK_PLAYERS,
    filters: { search: "", team: "", positions: new Set<string>(), statMins: EMPTY_MINS },
    onFiltersChange: vi.fn(),
    seasons: ["20252026"],
    onSeasonsChange: vi.fn(),
    count: { shown: 3, total: 3 },
    onSelectSuggestion: vi.fn(),
    ...overrides,
  };
}

describe("Toolbar", () => {
  it("shows suggestions matching the typed search text", async () => {
    const props = baseProps();
    render(<Toolbar {...props} />);
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "MacKinnon");
    expect(await screen.findByText("Nathan MacKinnon")).toBeInTheDocument();
  });

  it("calls onFiltersChange with updated search text as the user types", async () => {
    const onFiltersChange = vi.fn();
    render(<Toolbar {...baseProps({ onFiltersChange })} />);
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "Mc");
    expect(onFiltersChange).toHaveBeenCalled();
    const lastCall = onFiltersChange.mock.calls.at(-1)![0];
    expect(lastCall.search).toBe("Mc");
  });

  it("renders the position toggle, team picker, season picker, and stat filters", () => {
    render(<Toolbar {...baseProps()} />);
    expect(screen.getByRole("button", { name: "C" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all teams/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "2025–26" })).toBeInTheDocument();
    expect(screen.getByLabelText("GP≥")).toBeInTheDocument();
  });

  it("shows the player count", () => {
    render(<Toolbar {...baseProps({ count: { shown: 2, total: 3 } })} />);
    expect(screen.getByText("2 of 3 players")).toBeInTheDocument();
  });

  it("shows the plain total when no filters narrow the count", () => {
    render(<Toolbar {...baseProps({ count: { shown: 3, total: 3 } })} />);
    expect(screen.getByText("3 players")).toBeInTheDocument();
  });

  it("calls onSelectSuggestion when a suggestion is clicked", async () => {
    const onSelectSuggestion = vi.fn();
    render(<Toolbar {...baseProps({ onSelectSuggestion })} />);
    await userEvent.type(screen.getByPlaceholderText("Search players…"), "MacKinnon");
    await userEvent.click(await screen.findByText("Nathan MacKinnon"));
    expect(onSelectSuggestion).toHaveBeenCalledWith(
      expect.objectContaining({ player_id: 1, last_name: "MacKinnon" })
    );
  });
});
