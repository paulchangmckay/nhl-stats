import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import { PlayerTable, type PlayerTableHandle } from "./PlayerTable";
import { MOCK_STATS } from "@/lib/mock-data";

const mockScrollToIndex = vi.fn();

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (options: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: options.count }, (_, index) => ({
        key: index,
        index,
        start: index * 38,
        end: (index + 1) * 38,
        size: 38,
        lane: 0,
      })),
    getTotalSize: () => options.count * 38,
    scrollToIndex: mockScrollToIndex,
  }),
}));

beforeEach(() => {
  mockScrollToIndex.mockClear();
});

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

  it("renders the Shots/60 (5v5) teaser column", () => {
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    expect(screen.getByRole("columnheader", { name: "Shots/60 (5v5)" })).toBeInTheDocument();
  });

  it("scrollToPlayer calls the virtualizer's scrollToIndex with the player's index", () => {
    const ref = createRef<PlayerTableHandle>();
    render(<PlayerTable ref={ref} rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    ref.current!.scrollToPlayer(2); // McDavid, index 1 in MOCK_STATS
    expect(mockScrollToIndex).toHaveBeenCalledWith(1, { align: "center", behavior: "auto" });
  });

  it("scrollToPlayer is a no-op for an unknown player id", () => {
    const ref = createRef<PlayerTableHandle>();
    render(<PlayerTable ref={ref} rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    ref.current!.scrollToPlayer(9999);
    expect(mockScrollToIndex).not.toHaveBeenCalled();
  });
});
