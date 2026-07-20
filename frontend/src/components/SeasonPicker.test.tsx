import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SeasonPicker } from "./SeasonPicker";

describe("SeasonPicker", () => {
  it("shows the single season's label when one season is active", () => {
    render(<SeasonPicker active={["20252026"]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "2025–26" })).toBeInTheDocument();
  });

  it("shows 'All Seasons (Career)' when active is ['all']", () => {
    render(<SeasonPicker active={["all"]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /all seasons \(career\)/i })).toBeInTheDocument();
  });

  it("shows a count summary when multiple seasons are active", () => {
    render(<SeasonPicker active={["20252026", "20242025"]} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "2 Seasons" })).toBeInTheDocument();
  });

  it("checking 'All Seasons' replaces the active list with ['all']", async () => {
    const onChange = vi.fn();
    render(<SeasonPicker active={["20252026"]} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "2025–26" }));
    await userEvent.click(screen.getByText("All Seasons (Career)"));
    expect(onChange).toHaveBeenCalledWith(["all"]);
  });

  it("checking a specific season while 'all' is active replaces it with just that season", async () => {
    const onChange = vi.fn();
    render(<SeasonPicker active={["all"]} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /all seasons \(career\)/i }));
    await userEvent.click(screen.getByText("2024–25"));
    expect(onChange).toHaveBeenCalledWith(["20242025"]);
  });

  it("unchecking the last remaining season is a no-op", async () => {
    const onChange = vi.fn();
    render(<SeasonPicker active={["20252026"]} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "2025–26" }));
    await userEvent.click(screen.getByText("2025–26", { selector: "span" }));
    expect(onChange).not.toHaveBeenCalled();
  });
});
