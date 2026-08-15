// Matches the hardcoded default season used elsewhere in the app
// (Players.tsx, SeasonPicker.tsx) -- there is no backend "latest season"
// concept yet (see the design spec's Decision 2 for why). Centralized here
// so the two new ranking pages (TeamPage, TopPlayers) share one constant
// instead of duplicating the literal a second and third time.
export const LATEST_SEASON_ID = "20252026";
