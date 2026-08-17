import { teamColors } from "./teamBranding";

const HERO_GRADIENT_TEAMS = ["COL", "VGK", "TOR"] as const;

export function buildHeroGradient(): string {
  const stops = HERO_GRADIENT_TEAMS.map((abbrev) => teamColors(abbrev)!.primary);
  return `linear-gradient(135deg, ${stops.join(", ")})`;
}
