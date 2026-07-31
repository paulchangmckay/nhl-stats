import { describe, it, expect } from "vitest";
import { formatSeasonId } from "./utils";

describe("formatSeasonId", () => {
  it("formats a valid 8-digit season_id as en-dash two-digit style", () => {
    expect(formatSeasonId("20232024")).toBe("2023–24");
  });

  it("formats a numeric season_id the same way", () => {
    expect(formatSeasonId(20232024)).toBe("2023–24");
  });

  it("falls back to the raw string for malformed input", () => {
    expect(formatSeasonId("2023")).toBe("2023");
    expect(formatSeasonId("not-a-season")).toBe("not-a-season");
  });
});
