import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "./Home";

describe("Home", () => {
  it("renders the hero heading and subtext", () => {
    render(<Home />);
    expect(
      screen.getByRole("heading", { name: "Dig Into Every Player's Numbers" })
    ).toBeInTheDocument();
    expect(
      screen.getByText("Deep player and team analytics for every skater and goalie in the league.")
    ).toBeInTheDocument();
  });

  it("applies a gradient background to the hero section", () => {
    render(<Home />);
    const hero = screen.getByTestId("hero");
    expect(hero.style.backgroundImage).toMatch(/^linear-gradient\(135deg,/);
  });
});
