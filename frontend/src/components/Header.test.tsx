import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Header } from "./Header";

function renderHeader(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Header />
    </MemoryRouter>
  );
}

describe("Header", () => {
  it("renders a nav link for every top-level page", () => {
    renderHeader();
    for (const label of ["Home", "Players", "Teams", "Top Players", "Betting"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it("marks the active route's link", () => {
    renderHeader("/players");
    const [playersLink] = screen.getAllByText("Players");
    expect(playersLink).toHaveClass("text-foreground");
  });

  it("opens the mobile menu when the hamburger button is clicked", async () => {
    renderHeader();
    expect(screen.queryByText("Menu")).not.toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Open menu"));
    expect(await screen.findByText("Menu")).toBeInTheDocument();
  });
});
