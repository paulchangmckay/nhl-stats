import { describe, it, expect } from "vitest";
import { teamColors, logoUrl } from "./teamBranding";

describe("teamBranding", () => {
  it("returns primary and secondary colors for a known team", () => {
    expect(teamColors("EDM")).toEqual({ primary: "#041E42", secondary: "#FF4C00" });
  });

  it("returns undefined for the UNK placeholder team", () => {
    expect(teamColors("UNK")).toBeUndefined();
  });

  it("returns undefined for a blank or unrecognized abbreviation", () => {
    expect(teamColors("")).toBeUndefined();
    expect(teamColors("ZZZ")).toBeUndefined();
  });

  it("has an entry for all 32 current NHL teams", () => {
    const abbrevs = [
      "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET",
      "EDM", "FLA", "LAK", "MIN", "MTL", "NJD", "NSH", "NYI", "NYR", "OTT",
      "PHI", "PIT", "SEA", "SJS", "STL", "TBL", "TOR", "UTA", "VAN", "VGK",
      "WPG", "WSH",
    ];
    for (const abbrev of abbrevs) {
      expect(teamColors(abbrev), `missing colors for ${abbrev}`).toBeDefined();
    }
  });

  it("builds a dark-variant NHL CDN logo URL for a given abbreviation", () => {
    expect(logoUrl("EDM")).toBe("https://assets.nhle.com/logos/nhl/svg/EDM_dark.svg");
  });
});
