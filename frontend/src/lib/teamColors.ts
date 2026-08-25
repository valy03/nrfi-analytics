// Real MLB team primary brand colors, keyed by the same team id used for
// logos (MLB Stats API ids) — public branding facts, same spirit as
// sourcing logos from MLB's own static CDN, not invented data. Used only
// as a low-opacity accent wash, never as information.
const TEAM_COLORS: Record<number, string> = {
  108: "#BA0021", // LAA Angels
  109: "#A71930", // AZ Diamondbacks
  110: "#DF4601", // BAL Orioles
  111: "#BD3039", // BOS Red Sox
  112: "#0E3386", // CHC Cubs
  113: "#C6011F", // CIN Reds
  114: "#0C2340", // CLE Guardians
  115: "#333366", // COL Rockies
  116: "#0C2340", // DET Tigers
  117: "#EB6E1F", // HOU Astros
  118: "#004687", // KC Royals
  119: "#005A9C", // LAD Dodgers
  120: "#AB0003", // WSH Nationals
  121: "#002D72", // NYM Mets
  133: "#003831", // ATH Athletics
  134: "#FDB827", // PIT Pirates
  135: "#2F241D", // SD Padres
  136: "#0C2C56", // SEA Mariners
  137: "#FD5A1E", // SF Giants
  138: "#C41E3A", // STL Cardinals
  139: "#092C5C", // TB Rays
  140: "#C0111F", // TEX Rangers
  141: "#134A8E", // TOR Blue Jays
  142: "#002B5C", // MIN Twins
  143: "#E81828", // PHI Phillies
  144: "#CE1141", // ATL Braves
  145: "#27251F", // CWS White Sox
  146: "#00A3E0", // MIA Marlins
  147: "#003087", // NYY Yankees
  158: "#FFC52F", // MIL Brewers
};

const DEFAULT_COLOR = "#64748b"; // muted-foreground gray fallback

export function getTeamColor(teamId: number): string {
  return TEAM_COLORS[teamId] ?? DEFAULT_COLOR;
}
