import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Teams from "./Teams";

const TEAMS = [
  { abbrev: "COL", common_name: "Colorado Avalanche" },
  { abbrev: "TOR", common_name: "Toronto Maple Leafs" },
];

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(TEAMS) } as Response))
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Teams", () => {
  it("renders a card linking to /teams/:abbrev for every fetched team", async () => {
    render(
      <MemoryRouter>
        <Teams />
      </MemoryRouter>
    );

    const link = await screen.findByRole("link", { name: /Colorado Avalanche/i });
    expect(link).toHaveAttribute("href", "/teams/COL");
    expect(screen.getByRole("link", { name: /Toronto Maple Leafs/i })).toHaveAttribute(
      "href",
      "/teams/TOR"
    );
  });
});
