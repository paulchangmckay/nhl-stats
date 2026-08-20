import { useSearchParams } from "react-router-dom";
import type { ToolbarFilters } from "@/components/Toolbar";
import type { SortDirection } from "@/lib/types";
import { parseFiltersFromParams, filtersToParams } from "./urlFilters";

export function useUrlFilters() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { filters, seasons, sortKey, sortDir } = parseFiltersFromParams(searchParams);

  function setFilters(next: ToolbarFilters) {
    setSearchParams(filtersToParams(next, seasons, sortKey, sortDir), { replace: true });
  }

  function setSeasons(next: string[]) {
    setSearchParams(filtersToParams(filters, next, sortKey, sortDir), { replace: true });
  }

  function setSort(key: string, dir: SortDirection) {
    setSearchParams(filtersToParams(filters, seasons, key, dir), { replace: true });
  }

  return { filters, seasons, sortKey, sortDir, setFilters, setSeasons, setSort };
}
