export interface SearchablePlayer {
  first_name?: string | null;
  last_name?: string | null;
  team_name?: string | null;
  team_abbrev?: string | null;
  team_place_name?: string | null;
}

export function tokenize(query: string | undefined): string[] {
  return (query || "").toLowerCase().trim().split(/\s+/).filter(Boolean);
}

export function playerSearchText(p: SearchablePlayer): string {
  return [p.first_name, p.last_name, p.team_name, p.team_abbrev, p.team_place_name]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function matchesQuery(p: SearchablePlayer, query: string): boolean {
  const tokens = tokenize(query);
  if (tokens.length === 0) return false;
  const haystack = playerSearchText(p);
  return tokens.every((t) => haystack.includes(t));
}
