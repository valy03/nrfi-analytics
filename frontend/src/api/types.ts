// Mirrors backend/app/schemas/games.py — keep these two in sync by hand;
// there's no shared schema generation yet.

export interface Team {
  id: number;
  name: string;
  abbreviation: string;
}

export interface PitcherRecentStart {
  game_pk: number;
  game_date: string;
  opponent: string;
  runs_1st: number | null;
  nrfi: boolean | null;
}

export interface Pitcher {
  id: number;
  full_name: string;
  throws: string | null;
  // Traditional season stats — no data source yet (docs/milestones.md M8).
  era: number | null;
  whip: number | null;
  fip: number | null;
  xera: number | null;
  // First-inning rate stats, as of this game.
  k_rate_1st: number | null;
  bb_rate_1st: number | null;
  nrfi_rate_career: number | null;
  nrfi_rate_season: number | null;
  nrfi_rate_last5: number | null;
  starts_prior: number | null;
  recent_starts: PitcherRecentStart[];
}

export type PredictedLabel = "NRFI" | "YRFI";

export interface Prediction {
  predicted_label: PredictedLabel;
  nrfi_probability: number;
  yrfi_probability: number;
  confidence: number;
  model_name: string;
  model_version: string;
  predicted_at: string;
}

export interface Weather {
  temp_f: number;
  conditions: string;
  wind_mph: number;
  wind_direction_deg: number | null;
  captured_at: string;
}

export interface Odds {
  home_moneyline: number;
  away_moneyline: number;
  bookmaker: string;
  captured_at: string;
}

export interface GameSummary {
  game_pk: number;
  game_date: string;
  start_time_utc: string | null;
  status: string | null;
  venue_name: string | null;
  home_team: Team;
  away_team: Team;
  home_pitcher: Pitcher | null;
  away_pitcher: Pitcher | null;
  prediction: Prediction | null;
  weather: Weather | null;
}
