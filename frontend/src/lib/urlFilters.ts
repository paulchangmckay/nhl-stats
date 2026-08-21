import type { ToolbarFilters } from "@/components/Toolbar";
import type { SortDirection, StatMins } from "@/lib/types";

export const DEFAULT_FILTERS: ToolbarFilters = {
  search: "",
  team: "",
  positions: new Set(),
  statMins: { gp: null, goals: null, assists: null, points: null },
};
export const DEFAULT_SEASONS = ["20252026"];
export const DEFAULT_SORT_KEY = "points";
export const DEFAULT_SORT_DIR: SortDirection = "desc";

const STAT_MIN_KEYS: (keyof StatMins)[] = ["gp", "goals", "assists", "points"];

function parseStatMin(raw: string | null): number | null {
  if (raw === null || raw.trim() === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function parseFiltersFromParams(params: URLSearchParams): {
  filters: ToolbarFilters;
  seasons: string[];
  sortKey: string;
  sortDir: SortDirection;
} {
  const positionsRaw = params.get("positions");
  const positions = new Set(
    positionsRaw ? positionsRaw.split(",").filter((s) => s.length > 0) : []
  );

  const statMins: StatMins = {
    gp: parseStatMin(params.get("gp")),
    goals: parseStatMin(params.get("goals")),
    assists: parseStatMin(params.get("assists")),
    points: parseStatMin(params.get("points")),
  };

  const seasonsRaw = params.get("seasons");
  const seasons = seasonsRaw
    ? seasonsRaw.split(",").filter((s) => s.length > 0)
    : DEFAULT_SEASONS;

  const dirRaw = params.get("dir");
  const sortDir: SortDirection = dirRaw === "asc" || dirRaw === "desc" ? dirRaw : DEFAULT_SORT_DIR;

  return {
    filters: {
      search: params.get("search") ?? "",
      team: params.get("team") ?? "",
      positions,
      statMins,
    },
    seasons: seasons.length > 0 ? seasons : DEFAULT_SEASONS,
    sortKey: params.get("sort") ?? DEFAULT_SORT_KEY,
    sortDir,
  };
}

export function filtersToParams(
  filters: ToolbarFilters,
  seasons: string[],
  sortKey: string,
  sortDir: SortDirection
): URLSearchParams {
  const params = new URLSearchParams();

  if (filters.search !== DEFAULT_FILTERS.search) params.set("search", filters.search);
  if (filters.team !== DEFAULT_FILTERS.team) params.set("team", filters.team);
  if (filters.positions.size > 0) {
    params.set("positions", Array.from(filters.positions).sort().join(","));
  }
  for (const key of STAT_MIN_KEYS) {
    const value = filters.statMins[key];
    if (value !== null) params.set(key, String(value));
  }

  const sortedSeasons = [...seasons].sort();
  const sortedDefaultSeasons = [...DEFAULT_SEASONS].sort();
  if (sortedSeasons.join(",") !== sortedDefaultSeasons.join(",")) {
    params.set("seasons", sortedSeasons.join(","));
  }

  if (sortKey !== DEFAULT_SORT_KEY) params.set("sort", sortKey);
  if (sortDir !== DEFAULT_SORT_DIR) params.set("dir", sortDir);

  return params;
}
