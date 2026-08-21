import type {
  AccuracyReport,
  GameDetail,
  GameSummary,
  ModelPerformanceEntry,
  NrfiFrequencyPoint,
  PitcherLeaderboardEntry,
  PredictedLabel,
  PredictionHistoryItem,
  TeamLeaderboardEntry,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed (${response.status})`, response.status);
  }
  return response.json();
}

export interface GamesQuery {
  date?: string;
  prediction?: PredictedLabel;
  minConfidence?: number;
  team?: string;
  sortBy?: "confidence";
}

// Maps camelCase (idiomatic TS) to the snake_case query params
// app/routers/games.py actually expects.
function toSearchParams(query: GamesQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (query.date) params.set("date", query.date);
  if (query.prediction) params.set("prediction", query.prediction);
  if (query.minConfidence !== undefined) {
    params.set("min_confidence", String(query.minConfidence));
  }
  if (query.team) params.set("team", query.team);
  if (query.sortBy) params.set("sort_by", query.sortBy);
  return params;
}

export async function getGames(
  query: GamesQuery = {},
  signal?: AbortSignal
): Promise<GameSummary[]> {
  const params = toSearchParams(query);
  const url = `${API_URL}/api/games${params.size ? `?${params}` : ""}`;
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new ApiError(`Failed to load games (${response.status})`, response.status);
  }
  return response.json();
}

export async function getGameDetail(
  gamePk: number,
  signal?: AbortSignal
): Promise<GameDetail> {
  const response = await fetch(`${API_URL}/api/games/${gamePk}`, { signal });
  if (!response.ok) {
    throw new ApiError(`Failed to load game ${gamePk} (${response.status})`, response.status);
  }
  return response.json();
}

export interface PredictionHistoryQuery {
  startDate?: string;
  endDate?: string;
  team?: string;
  modelVersion?: string;
  limit?: number;
  offset?: number;
}

export async function getPredictionHistory(
  query: PredictionHistoryQuery = {},
  signal?: AbortSignal
): Promise<PredictionHistoryItem[]> {
  const params = new URLSearchParams();
  if (query.startDate) params.set("start_date", query.startDate);
  if (query.endDate) params.set("end_date", query.endDate);
  if (query.team) params.set("team", query.team);
  if (query.modelVersion) params.set("model_version", query.modelVersion);
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  if (query.offset !== undefined) params.set("offset", String(query.offset));
  const qs = params.size ? `?${params}` : "";
  return fetchJson<PredictionHistoryItem[]>(`/api/history/predictions${qs}`, signal);
}

export async function getAccuracyReport(
  modelVersion?: string,
  signal?: AbortSignal
): Promise<AccuracyReport> {
  const qs = modelVersion ? `?model_version=${encodeURIComponent(modelVersion)}` : "";
  return fetchJson<AccuracyReport>(`/api/history/accuracy${qs}`, signal);
}

export async function getNrfiFrequency(signal?: AbortSignal): Promise<NrfiFrequencyPoint[]> {
  return fetchJson<NrfiFrequencyPoint[]>("/api/analytics/nrfi-frequency", signal);
}

export async function getPitcherLeaderboard(
  signal?: AbortSignal
): Promise<PitcherLeaderboardEntry[]> {
  return fetchJson<PitcherLeaderboardEntry[]>("/api/analytics/pitchers", signal);
}

export async function getTeamLeaderboard(signal?: AbortSignal): Promise<TeamLeaderboardEntry[]> {
  return fetchJson<TeamLeaderboardEntry[]>("/api/analytics/teams", signal);
}

export async function getModelPerformance(
  signal?: AbortSignal
): Promise<ModelPerformanceEntry[]> {
  return fetchJson<ModelPerformanceEntry[]>("/api/analytics/models", signal);
}
