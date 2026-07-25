interface TeamColors {
  primary: string;
  secondary: string;
}

// Researched per-team brand colors. UTA (Utah's NHL franchise) rebranded
// recently (relocated 2024, renamed 2025) — double-check against current
// official assets if these ever look wrong.
const TEAM_COLORS: Record<string, TeamColors> = {
  ANA: { primary: "#F47A38", secondary: "#000000" },
  BOS: { primary: "#FFB81C", secondary: "#000000" },
  BUF: { primary: "#002654", secondary: "#FCB514" },
  CAR: { primary: "#CC0000", secondary: "#000000" },
  CBJ: { primary: "#002654", secondary: "#CE1126" },
  CGY: { primary: "#C8102E", secondary: "#F1BE48" },
  CHI: { primary: "#CF0A2C", secondary: "#000000" },
  COL: { primary: "#6F263D", secondary: "#236192" },
  DAL: { primary: "#006847", secondary: "#000000" },
  DET: { primary: "#CE1126", secondary: "#FFFFFF" },
  EDM: { primary: "#041E42", secondary: "#FF4C00" },
  FLA: { primary: "#C8102E", secondary: "#041E42" },
  LAK: { primary: "#111111", secondary: "#A2AAAD" },
  MIN: { primary: "#154734", secondary: "#A6192E" },
  MTL: { primary: "#AF1E2D", secondary: "#192168" },
  NJD: { primary: "#CE1126", secondary: "#000000" },
  NSH: { primary: "#FFB81C", secondary: "#041E42" },
  NYI: { primary: "#00539B", secondary: "#F47D30" },
  NYR: { primary: "#0038A8", secondary: "#CE1126" },
  OTT: { primary: "#C8102E", secondary: "#000000" },
  PHI: { primary: "#F74902", secondary: "#000000" },
  PIT: { primary: "#000000", secondary: "#FFB81C" },
  SEA: { primary: "#001628", secondary: "#99D9D9" },
  SJS: { primary: "#006D75", secondary: "#000000" },
  STL: { primary: "#002F87", secondary: "#FCB514" },
  TBL: { primary: "#002868", secondary: "#FFFFFF" },
  TOR: { primary: "#00205B", secondary: "#FFFFFF" },
  UTA: { primary: "#010101", secondary: "#69B3E7" },
  VAN: { primary: "#00205B", secondary: "#00843D" },
  VGK: { primary: "#B4975A", secondary: "#333F42" },
  WPG: { primary: "#041E42", secondary: "#AC162C" },
  WSH: { primary: "#C8102E", secondary: "#041E42" },
};

export function teamColors(abbrev: string): TeamColors | undefined {
  return TEAM_COLORS[abbrev];
}

export function logoUrl(abbrev: string): string {
  return `https://assets.nhle.com/logos/nhl/svg/${abbrev}_dark.svg`;
}
