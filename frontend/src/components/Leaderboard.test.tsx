import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Leaderboard } from "./Leaderboard";
import type { RankedPlayer } from "@/lib/leaderboards";

const PLAYERS: RankedPlayer[] = [
  { player_id: 1, name: "Nathan MacKinnon", team_abbrev: "COL", score: 2.1 },
  { player_id: 2, name: "Cale Makar", team_abbrev: "COL", score: 1.4 },
];

describe("Leaderboard", () => {
  it("renders the title and players in the given order", () => {
    render(<Leaderboard title="Top Offense" players={PLAYERS} onSelectPlayer={() => {}} />);
    expect(screen.getByText("Top Offense")).toBeInTheDocument();
    const rows = screen.getAllByRole("button");
    expect(rows[0]).toHaveTextContent("Nathan MacKinnon");
    expect(rows[1]).toHaveTextContent("Cale Makar");
  });

  it("calls onSelectPlayer with the correct player_id when a row is clicked", async () => {
    const onSelectPlayer = vi.fn();
    render(<Leaderboard title="Top Offense" players={PLAYERS} onSelectPlayer={onSelectPlayer} />);
    await userEvent.click(screen.getByText("Cale Makar"));
    expect(onSelectPlayer).toHaveBeenCalledWith(2);
  });

  it("shows an empty-state message instead of a bare list when there are no players", () => {
    render(<Leaderboard title="Top Goalie" players={[]} onSelectPlayer={() => {}} />);
    expect(screen.getByText("No qualifying players.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
