import { useEffect, useMemo, useState } from "react";
import { ApiError, getGames } from "../api/client";
import type { GameSummary } from "../api/types";
import { DEFAULT_FILTERS, FiltersBar, type Filters } from "../components/FiltersBar";
import { GameCard } from "../components/GameCard";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; games: GameSummary[] };

function matchesSearch(game: GameSummary, search: string): boolean {
  if (!search.trim()) return true;
  const needle = search.trim().toLowerCase();
  return (
    game.home_team.name.toLowerCase().includes(needle) ||
    game.home_team.abbreviation.toLowerCase().includes(needle) ||
    game.away_team.name.toLowerCase().includes(needle) ||
    game.away_team.abbreviation.toLowerCase().includes(needle)
  );
}

function applyFilters(games: GameSummary[], filters: Filters): GameSummary[] {
  let result = games.filter((game) => matchesSearch(game, filters.search));

  if (filters.prediction !== "ALL") {
    result = result.filter((game) => game.prediction?.predicted_label === filters.prediction);
  }
  if (filters.minConfidence > 0) {
    result = result.filter(
      (game) => (game.prediction?.confidence ?? -1) >= filters.minConfidence
    );
  }
  if (filters.sortByConfidence) {
    result = [...result].sort(
      (a, b) => (b.prediction?.confidence ?? -1) - (a.prediction?.confidence ?? -1)
    );
  }
  return result;
}

export function Dashboard() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });

    // No `date` param — the backend resolves "today" via mlb_today() (US
    // Eastern), the same calendar M1/M7 use, rather than trusting whatever
    // "today" the visitor's browser/timezone happens to think it is.
    getGames({}, controller.signal)
      .then((games) => setState({ status: "ready", games }))
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        const message = err instanceof ApiError ? err.message : "Could not reach the API";
        setState({ status: "error", message });
      });

    return () => controller.abort();
  }, []);

  const visibleGames = useMemo(() => {
    if (state.status !== "ready") return [];
    return applyFilters(state.games, filters);
  }, [state, filters]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Today's Games</h1>
        <p className="text-sm text-slate-500">
          NRFI/YRFI predictions for every MLB game today.
        </p>
      </header>

      <div className="mb-6">
        <FiltersBar filters={filters} onChange={setFilters} />
      </div>

      {state.status === "loading" && (
        <p className="text-center text-slate-400">Loading today's slate…</p>
      )}

      {state.status === "error" && (
        <p className="rounded-lg bg-red-50 p-4 text-center text-sm text-red-600">
          {state.message}
        </p>
      )}

      {state.status === "ready" && state.games.length === 0 && (
        <p className="text-center text-slate-400">No MLB games scheduled today.</p>
      )}

      {state.status === "ready" && state.games.length > 0 && visibleGames.length === 0 && (
        <p className="text-center text-slate-400">No games match the current filters.</p>
      )}

      {visibleGames.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {visibleGames.map((game) => (
            <GameCard key={game.game_pk} game={game} />
          ))}
        </div>
      )}
    </div>
  );
}
