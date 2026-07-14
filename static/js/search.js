function tokenize(query) {
  return (query || "").toLowerCase().trim().split(/\s+/).filter(Boolean);
}

function playerSearchText(p) {
  return [p.first_name, p.last_name, p.team_name, p.team_abbrev, p.team_place_name]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function matchesQuery(p, query) {
  const tokens = tokenize(query);
  if (tokens.length === 0) return false;
  const haystack = playerSearchText(p);
  return tokens.every((t) => haystack.includes(t));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { tokenize, playerSearchText, matchesQuery };
}
