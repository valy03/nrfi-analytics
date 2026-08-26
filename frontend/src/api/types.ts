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

export interface TeamStats {
  scored_1st_rate: number | null;
  scored_1st_rate_season: number | null;
  scored_1st_rate_recent: number | null;
  scored_1st_rate_split: number | null;
  runs_1st_avg: number | null;
  k_rate_1st: number | null;
  games_prior: number | null;
  // Traditional stats — no data source yet (docs/milestones.md M8).
  ops: number | null;
  obp: number | null;
  slg: number | null;
  batting_avg: number | null;
}

export interface ActualResult {
  home_runs_1st: number | null;
  away_runs_1st: number | null;
  first_inning_runs: number | null;
  nrfi: boolean | null;
  home_score: number | null;
  away_score: number | null;
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
  correct: boolean | null;
  actual_result: ActualResult | null;
  weather: Weather | null;
}

export interface GameDetail {
  game_pk: number;
  game_date: string;
  start_time_utc: string | null;
  status: string | null;
  venue_name: string | null;
  home_team: Team;
  away_team: Team;
  home_pitcher: Pitcher | null;
  away_pitcher: Pitcher | null;
  home_team_stats: TeamStats | null;
  away_team_stats: TeamStats | null;
  prediction: Prediction | null;
  correct: boolean | null;
  explanation: string[];
  actual_result: ActualResult | null;
  weather: Weather | null;
  odds: Odds | null;
}

// Mirrors backend/app/schemas/history.py.

export interface PredictionHistoryItem {
  game_pk: number;
  game_date: string;
  home_team: string;
  away_team: string;
  predicted_label: PredictedLabel;
  actual_label: PredictedLabel | null;
  correct: boolean | null;
  confidence: number;
  nrfi_probability: number;
  model_name: string;
  model_version: string;
}

export interface AccuracyBucket {
  period: string;
  total: number;
  correct: number;
  accuracy: number | null;
  win_rate: number | null;
  roi: number | null;
}

export interface AccuracyReport {
  overall: AccuracyBucket;
  monthly: AccuracyBucket[];
  yearly: AccuracyBucket[];
}

// Mirrors backend/app/schemas/analytics.py.

export interface NrfiFrequencyPoint {
  period: string;
  games: number;
  nrfi_rate: number;
}

export interface PitcherLeaderboardEntry {
  pitcher_id: number;
  full_name: string;
  starts: number;
  nrfi_rate: number;
  runs_1st_avg: number;
}

export interface TeamLeaderboardEntry {
  team_id: number;
  abbreviation: string;
  games: number;
  scored_1st_rate: number;
}

export interface ModelPerformanceEntry {
  model_name: string;
  model_version: string;
  total: number;
  correct: number;
  accuracy: number;
}
