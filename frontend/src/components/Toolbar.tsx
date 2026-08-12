import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { PositionToggle } from "./PositionToggle";
import { StatFilters } from "./StatFilters";
import { TeamPicker } from "./TeamPicker";
import { SeasonPicker } from "./SeasonPicker";
import { matchesQuery } from "@/lib/search";
import type { Player, Team, StatMins } from "@/lib/types";

export interface ToolbarFilters {
  search: string;
  team: string;
  positions: Set<string>;
  statMins: StatMins;
}

export interface PlayerCount {
  shown: number;
  total: number;
}

interface ToolbarProps {
  teams: Team[];
  players: Player[];
  filters: ToolbarFilters;
  onFiltersChange: (next: ToolbarFilters) => void;
  seasons: string[];
  onSeasonsChange: (next: string[]) => void;
  count: PlayerCount;
  onSelectSuggestion: (player: Player) => void;
}

export function Toolbar({
  teams,
  players,
  filters,
  onFiltersChange,
  seasons,
  onSeasonsChange,
  count,
  onSelectSuggestion,
}: ToolbarProps) {
  const [localSearch, setLocalSearch] = useState(filters.search);

  useEffect(() => {
    setLocalSearch(filters.search);
  }, [filters.search]);

  const suggestions = localSearch
    ? players.filter((p) => matchesQuery(p, localSearch)).slice(0, 8)
    : [];

  return (
    <div data-toolbar className="flex flex-col gap-3 border-b border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-semibold">NHL Players</h1>
        <div className="relative">
          <Input
            placeholder="Search players…"
            value={localSearch}
            onChange={(e) => {
              setLocalSearch(e.target.value);
              onFiltersChange({ ...filters, search: e.target.value });
            }}
            className="w-52"
          />
          {suggestions.length > 0 && (
            <div className="absolute top-full z-20 mt-1 max-h-64 w-52 overflow-y-auto rounded-md border border-border bg-card">
              {suggestions.map((p) => (
                <div
                  key={p.player_id}
                  className="cursor-pointer px-3 py-1.5 text-sm hover:bg-accent"
                  onClick={() => onSelectSuggestion(p)}
                >
                  {p.first_name} {p.last_name}
                </div>
              ))}
            </div>
          )}
        </div>
        <TeamPicker
          teams={teams}
          active={filters.team}
          onChange={(team) => onFiltersChange({ ...filters, team })}
        />
        <SeasonPicker active={seasons} onChange={onSeasonsChange} />
        <span className="ml-auto text-sm text-muted-foreground">
          {count.shown === count.total
            ? `${count.total} players`
            : `${count.shown} of ${count.total} players`}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <PositionToggle
          active={filters.positions}
          onChange={(positions) => onFiltersChange({ ...filters, positions })}
        />
        <StatFilters
          value={filters.statMins}
          onChange={(statMins) => onFiltersChange({ ...filters, statMins })}
        />
      </div>
    </div>
  );
}
