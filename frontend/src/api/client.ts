import type { GameDetail, GameSummary, PredictedLabel } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
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
