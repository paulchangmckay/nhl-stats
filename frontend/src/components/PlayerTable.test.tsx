import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { PlayerTable, type PlayerTableHandle } from "./PlayerTable";
import { MOCK_STATS } from "@/lib/mock-data";
import type { PlayerStats } from "@/lib/types";

const mockScrollToIndex = vi.fn();

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: vi.fn((options: { count: number }) => ({
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
  })),
}));

beforeEach(() => {
  mockScrollToIndex.mockClear();
});

// Unconditional, so a fake-timer test that fails partway through doesn't
// leak faked timers into every test that runs after it in this file.
afterEach(() => {
  vi.useRealTimers();
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

  it("scrollToPlayer keeps retrying across frames until the row mounts, not just one frame", () => {
    // Regression test: the row can't mount until a native "scroll" event
    // fires on the container (virtual-core flushSync's its re-render
    // inside that handler), and that event is asynchronous -- measured up
    // to ~2s late in a real-browser session for a long jump. A single
    // requestAnimationFrame check missed the row entirely and never
    // highlighted it. This test forces that "not mounted yet" condition
    // and confirms the retry loop keeps checking instead of giving up
    // after one frame.
    vi.useFakeTimers();
    const ref = createRef<PlayerTableHandle>();
    render(<PlayerTable ref={ref} rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);

    const row = document.querySelector('[data-player-id="2"]')!;
    const tbody = row.parentElement!;
    row.remove(); // simulate the row not being mounted yet

    ref.current!.scrollToPlayer(2);

    vi.advanceTimersByTime(16); // one frame: row still absent, must not give up
    expect(row.classList.contains("row-highlight")).toBe(false);

    tbody.appendChild(row); // simulate it mounting on a later frame
    vi.advanceTimersByTime(16);
    expect(row.classList.contains("row-highlight")).toBe(true);
  });

  it("a second scrollToPlayer supersedes the first still-polling call", () => {
    // The generation-token guard exists so two quick suggestion clicks
    // don't let the first (now-stale) call's retry loop highlight its
    // target after a second call has taken over.
    vi.useFakeTimers();
    const ref = createRef<PlayerTableHandle>();
    render(<PlayerTable ref={ref} rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);

    const rowA = document.querySelector('[data-player-id="1"]')!;
    const rowB = document.querySelector('[data-player-id="2"]')!;
    const tbody = rowA.parentElement!;
    rowA.remove();
    rowB.remove();

    ref.current!.scrollToPlayer(1);
    vi.advanceTimersByTime(16);
    ref.current!.scrollToPlayer(2); // supersedes the still-polling call for player 1

    tbody.appendChild(rowA);
    tbody.appendChild(rowB);
    vi.advanceTimersByTime(16);

    expect(rowA.classList.contains("row-highlight")).toBe(false);
    expect(rowB.classList.contains("row-highlight")).toBe(true);
  });

  it("keeps the sticky header above transformed rows (z-index regression guard)", () => {
    // Rows are positioned via CSS transform, which makes each <tr> a
    // stacking context painting at effective z-index 0 -- without an
    // explicit z-index on the sticky header, rows would paint over it
    // while scrolling (this actually happened on this branch once).
    render(<PlayerTable rows={MOCK_STATS} sortKey="points" sortDir="desc" onSort={() => {}} />);
    expect(document.querySelector("thead")).toHaveClass("sticky", "top-0", "z-10");
  });

  it("computes correct row positions and spacer height for a windowed (non-full) scroll view", () => {
    // Simulate scrolling partway through a 100-row list: only rows 40-42
    // are "visible" (mimicking what a real scroll position would report),
    // not the full mocked default (every row visible, which never
    // exercises the translateY/spacer math for a real windowed scenario).
    const manyRows: PlayerStats[] = Array.from({ length: 100 }, (_, i) => ({
      ...MOCK_STATS[0],
      player_id: 1000 + i,
      last_name: `Player${i}`,
    }));

    vi.mocked(useVirtualizer).mockReturnValueOnce({
      getVirtualItems: () => [
        { key: 40, index: 40, start: 1520, end: 1558, size: 38, lane: 0 },
        { key: 41, index: 41, start: 1558, end: 1596, size: 38, lane: 0 },
        { key: 42, index: 42, start: 1596, end: 1634, size: 38, lane: 0 },
      ],
      getTotalSize: () => 100 * 38,
      scrollToIndex: vi.fn(),
    } as unknown as ReturnType<typeof useVirtualizer>);

    render(<PlayerTable rows={manyRows} sortKey="points" sortDir="desc" onSort={() => {}} />);

    const firstRenderedRow = document.querySelector('[data-player-id="1040"]') as HTMLElement;
    expect(firstRenderedRow).toBeTruthy();
    // Row at virtual index 40 is the 0th rendered row (i=0): transform = start - i*38 = 1520 - 0 = 1520
    expect(firstRenderedRow.style.transform).toBe("translateY(1520px)");

    const secondRenderedRow = document.querySelector('[data-player-id="1041"]') as HTMLElement;
    // Row at virtual index 41 is the 1st rendered row (i=1): transform = start - i*38 = 1558 - 38 = 1520
    expect(secondRenderedRow.style.transform).toBe("translateY(1520px)");

    // Spacer: totalSize (3800) - renderedHeight (3 * 38 = 114) = 3686
    const spacerCell = document.querySelector('td[colspan]') as HTMLElement;
    expect(spacerCell).toBeTruthy();
    expect(spacerCell.style.height).toBe("3686px");
  });
});
