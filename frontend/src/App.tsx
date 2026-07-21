import { useState } from "react";
import { Toolbar, type ToolbarFilters } from "@/components/Toolbar";
import { MOCK_TEAMS, MOCK_PLAYERS } from "@/lib/mock-data";

export default function App() {
  const [filters, setFilters] = useState<ToolbarFilters>({
    search: "",
    team: "",
    positions: new Set(),
    statMins: { gp: null, goals: null, assists: null, points: null },
  });
  const [seasons, setSeasons] = useState<string[]>(["20252026"]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Toolbar
        teams={MOCK_TEAMS}
        players={MOCK_PLAYERS}
        filters={filters}
        onFiltersChange={setFilters}
        seasons={seasons}
        onSeasonsChange={setSeasons}
        count={{ shown: MOCK_PLAYERS.length, total: MOCK_PLAYERS.length }}
        onSelectSuggestion={() => {}}
      />
      <div className="p-4 text-sm text-muted-foreground">
        PlayerTable wiring lands in Phase 3.
      </div>
    </div>
  );
}
