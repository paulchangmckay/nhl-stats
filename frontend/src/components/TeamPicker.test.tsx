import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TeamPicker } from "./TeamPicker";
import { MOCK_TEAMS } from "@/lib/mock-data";

describe("TeamPicker", () => {
  it("shows 'All Teams' when no team is active", () => {
    render(<TeamPicker teams={MOCK_TEAMS} active="" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /all teams/i })).toBeInTheDocument();
  });

  it("shows the selected team's name when a team is active", () => {
    render(<TeamPicker teams={MOCK_TEAMS} active="COL" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /colorado avalanche/i })).toBeInTheDocument();
  });

  it("calls onChange with the team abbrev when a team row is clicked", async () => {
    const onChange = vi.fn();
    render(<TeamPicker teams={MOCK_TEAMS} active="" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /all teams/i }));
    await userEvent.click(await screen.findByText("Edmonton Oilers"));
    expect(onChange).toHaveBeenCalledWith("EDM");
  });

  it("calls onChange with an empty string when 'All Teams' is clicked", async () => {
    const onChange = vi.fn();
    render(<TeamPicker teams={MOCK_TEAMS} active="COL" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /colorado avalanche/i }));
    await userEvent.click(await screen.findByText("All Teams"));
    expect(onChange).toHaveBeenCalledWith("");
  });
});
