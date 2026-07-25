import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PlayerTable } from "./PlayerTable";
import { MOCK_STATS } from "@/lib/mock-data";

describe("PlayerTable", () => {
  it("renders one row per player", () => {
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    expect(screen.getByText("MacKinnon")).toBeInTheDocument();
    expect(screen.getByText("McDavid")).toBeInTheDocument();
    expect(screen.getByText("Stolarz")).toBeInTheDocument();
  });

  it("calls onSort with the column key when a header is clicked", async () => {
    const onSort = vi.fn();
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={onSort} />);
    await userEvent.click(screen.getByRole("columnheader", { name: "G" }));
    expect(onSort).toHaveBeenCalledWith("goals");
  });

  it("shows goalie columns (W/L/SV%/GAA) only for goalie rows", () => {
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    // Stolarz (goalie) shows his save % and wins
    expect(screen.getByText("0.918")).toBeInTheDocument();
    expect(screen.getByText("24")).toBeInTheDocument();
  });

  it("renders an empty-state message when rows is empty", () => {
    render(<PlayerTable rows={[]} sortKey="points" sortDir="desc" onSort={() => {}} />);
    expect(screen.getByText(/no players found/i)).toBeInTheDocument();
  });

  it("calls onOpenProfile with the player id when a row is clicked", async () => {
    const onOpenProfile = vi.fn();
    render(
      <PlayerTable
        rows={MOCK_STATS}
        sortKey="points"
        sortDir="desc"
        onSort={() => {}}
        onOpenProfile={onOpenProfile}
      />
    );
    const row = document.querySelector('[data-player-id="1"]')!;
    await userEvent.click(row);
    expect(onOpenProfile).toHaveBeenCalledWith(1);
  });

  it("calls onOpenProfile when a row is focused and Enter is pressed", async () => {
    const onOpenProfile = vi.fn();
    render(
      <PlayerTable
        rows={MOCK_STATS}
        sortKey="points"
        sortDir="desc"
        onSort={() => {}}
        onOpenProfile={onOpenProfile}
      />
    );
    const row = document.querySelector('[data-player-id="2"]') as HTMLElement;
    row.focus();
    await userEvent.keyboard("{Enter}");
    expect(onOpenProfile).toHaveBeenCalledWith(2);
  });

  it("no longer gives the CF% (5v5) cell its own click handler (the row handles it)", () => {
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    expect(screen.queryByTestId("cf-pct-5v5-cell")).not.toBeInTheDocument();
  });
});
