import { describe, it, expect } from "vitest";
import {
  DEFAULT_FILTERS,
  DEFAULT_SEASONS,
  DEFAULT_SORT_KEY,
  DEFAULT_SORT_DIR,
  parseFiltersFromParams,
  filtersToParams,
} from "./urlFilters";

describe("filtersToParams", () => {
  it("produces an empty params string when everything is at its default", () => {
    const params = filtersToParams(DEFAULT_FILTERS, DEFAULT_SEASONS, DEFAULT_SORT_KEY, DEFAULT_SORT_DIR);
    expect(params.toString()).toBe("");
  });

  it("writes only the fields that differ from default", () => {
    const filters = { ...DEFAULT_FILTERS, team: "EDM" };
    const params = filtersToParams(filters, DEFAULT_SEASONS, "goals", "asc");
    expect(params.get("team")).toBe("EDM");
    expect(params.get("sort")).toBe("goals");
    expect(params.get("dir")).toBe("asc");
    expect(params.has("search")).toBe(false);
    expect(params.has("seasons")).toBe(false);
  });

  it("sorts positions before joining, regardless of Set insertion order", () => {
    const filtersA = { ...DEFAULT_FILTERS, positions: new Set(["R", "C", "D"]) };
    const filtersB = { ...DEFAULT_FILTERS, positions: new Set(["D", "R", "C"]) };
    const paramsA = filtersToParams(filtersA, DEFAULT_SEASONS, DEFAULT_SORT_KEY, DEFAULT_SORT_DIR);
    const paramsB = filtersToParams(filtersB, DEFAULT_SEASONS, DEFAULT_SORT_KEY, DEFAULT_SORT_DIR);
    expect(paramsA.get("positions")).toBe("C,D,R");
    expect(paramsB.get("positions")).toBe("C,D,R");
  });

  it("sorts seasons before joining", () => {
    const params = filtersToParams(DEFAULT_FILTERS, ["20232024", "20212022"], DEFAULT_SORT_KEY, DEFAULT_SORT_DIR);
    expect(params.get("seasons")).toBe("20212022,20232024");
  });
});

describe("parseFiltersFromParams", () => {
  it("returns all defaults for an empty params object", () => {
    const result = parseFiltersFromParams(new URLSearchParams());
    expect(result.filters).toEqual(DEFAULT_FILTERS);
    expect(result.seasons).toEqual(DEFAULT_SEASONS);
    expect(result.sortKey).toBe(DEFAULT_SORT_KEY);
    expect(result.sortDir).toBe(DEFAULT_SORT_DIR);
  });

  it("round-trips a non-default filter set through filtersToParams and back", () => {
    const filters = {
      search: "mcdavid",
      team: "EDM",
      positions: new Set(["C", "L"]),
      statMins: { gp: 10, goals: null, assists: 5, points: null },
    };
    const params = filtersToParams(filters, ["20232024", "20242025"], "goals", "asc");
    const result = parseFiltersFromParams(params);
    expect(result.filters).toEqual(filters);
    expect(result.seasons).toEqual(["20232024", "20242025"]);
    expect(result.sortKey).toBe("goals");
    expect(result.sortDir).toBe("asc");
  });

  it("decodes a malformed numeric stat-min param as null, not NaN", () => {
    const result = parseFiltersFromParams(new URLSearchParams("gp=abc"));
    expect(result.filters.statMins.gp).toBeNull();
  });

  it("decodes an empty (but present) numeric stat-min param as null, not 0", () => {
    const result = parseFiltersFromParams(new URLSearchParams("gp="));
    expect(result.filters.statMins.gp).toBeNull();
  });

  it("decodes an Infinity numeric stat-min param as null, not Infinity", () => {
    const result = parseFiltersFromParams(new URLSearchParams("gp=Infinity"));
    expect(result.filters.statMins.gp).toBeNull();
  });

  it("decodes a whitespace-only numeric stat-min param as null", () => {
    const result = parseFiltersFromParams(new URLSearchParams("gp=%20"));
    expect(result.filters.statMins.gp).toBeNull();
  });

  it("decodes an invalid sort direction as the default", () => {
    const result = parseFiltersFromParams(new URLSearchParams("dir=sideways"));
    expect(result.sortDir).toBe("desc");
  });

  it("decodes an empty positions param as an empty set, not a set containing an empty string", () => {
    const result = parseFiltersFromParams(new URLSearchParams("positions="));
    expect(result.filters.positions).toEqual(new Set());
  });
});
