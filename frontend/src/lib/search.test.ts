import { describe, it, expect } from "vitest";
import { tokenize, playerSearchText, matchesQuery } from "./search";

const mackinnon = {
  first_name: "Nathan",
  last_name: "MacKinnon",
  team_name: "Avalanche",
  team_abbrev: "COL",
  team_place_name: "Colorado",
};

describe("tokenize", () => {
  it("lowercases, trims, splits on whitespace, and drops empties", () => {
    expect(tokenize("  Nathan   MacKinnon ")).toEqual(["nathan", "mackinnon"]);
    expect(tokenize("")).toEqual([]);
    expect(tokenize(undefined)).toEqual([]);
  });
});

describe("playerSearchText", () => {
  it("concatenates name and team fields, lowercased", () => {
    expect(playerSearchText(mackinnon)).toBe("nathan mackinnon avalanche col colorado");
  });

  it("skips missing fields without leaving gaps", () => {
    expect(playerSearchText({ first_name: "Nathan", last_name: "MacKinnon" })).toBe(
      "nathan mackinnon"
    );
  });
});

describe("matchesQuery", () => {
  it("matches on last name alone", () => {
    expect(matchesQuery(mackinnon, "MacKinnon")).toBe(true);
  });

  it("matches full name in forward order", () => {
    expect(matchesQuery(mackinnon, "Nathan MacKinnon")).toBe(true);
  });

  it("matches full name in reversed order", () => {
    expect(matchesQuery(mackinnon, "MacKinnon Nathan")).toBe(true);
  });

  it("returns false for a non-matching query", () => {
    expect(matchesQuery(mackinnon, "Connor McDavid")).toBe(false);
  });

  it("returns false for an empty query", () => {
    expect(matchesQuery(mackinnon, "")).toBe(false);
  });

  it("matches team short name", () => {
    expect(matchesQuery(mackinnon, "Avalanche")).toBe(true);
  });

  it("matches team abbreviation", () => {
    expect(matchesQuery(mackinnon, "COL")).toBe(true);
  });

  it("matches team place name", () => {
    expect(matchesQuery(mackinnon, "Colorado")).toBe(true);
  });

  it("matches multi-token team name", () => {
    expect(matchesQuery(mackinnon, "Colorado Avalanche")).toBe(true);
  });

  it("does not cross-match a name token against an unrelated team", () => {
    const otherTeamPlayer = {
      first_name: "Connor",
      last_name: "McDavid",
      team_name: "Oilers",
      team_abbrev: "EDM",
      team_place_name: "Edmonton",
    };
    expect(matchesQuery(otherTeamPlayer, "Colorado Avalanche")).toBe(false);
  });
});
