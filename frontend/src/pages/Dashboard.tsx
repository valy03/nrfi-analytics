import { useEffect, useMemo, useState } from "react";
import { ApiError, getAccuracyReport, getGameDetail, getGames } from "../api/client";
import type { AccuracyReport, GameSummary } from "../api/types";
import { DEFAULT_FILTERS, FiltersBar, type Filters } from "../components/FiltersBar";
import { GameCard } from "../components/GameCard";
import { StatTile } from "../components/StatTile";
import { TopPicks, type TopPick } from "../components/TopPicks";
import { formatPct, formatRelativeTime } from "../lib/format";

const TOP_PICKS_COUNT = 5;

type GamesState =
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
  const [gamesState, setGamesState] = useState<GamesState>({ status: "loading" });
  const [accuracy, setAccuracy] = useState<AccuracyReport | null>(null);
  const [topPicks, setTopPicks] = useState<TopPick[]>([]);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);

  // No `date` param — the backend resolves "today" via mlb_today() (US
  // Eastern), the same calendar M1/M7 use, rather than trusting whatever
  // "today" the visitor's browser/timezone happens to think it is.
  useEffect(() => {
    const controller = new AbortController();
    setGamesState({ status: "loading" });

    getGames({}, controller.signal)
      .then((games) => setGamesState({ status: "ready", games }))
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        const message = err instanceof ApiError ? err.message : "Could not reach the API";
        setGamesState({ status: "error", message });
      });

    // A failed accuracy fetch just leaves the summary cards reading "—" —
    // not worth failing the whole page over.
    getAccuracyReport(undefined, controller.signal)
      .then(setAccuracy)
      .catch(() => {});

    return () => controller.abort();
  }, []);

  // Top Picks needs each pick's real explanation (not a re-implemented,
  // possibly-drifting copy of the backend's rule-based logic), so it fetches
  // full game detail for just the ranked few — bounded to TOP_PICKS_COUNT
  // requests, not one per game on the slate.
  useEffect(() => {
    if (gamesState.status !== "ready") return;
    const controller = new AbortController();

    const ranked = gamesState.games
      .filter((g): g is GameSummary & { prediction: NonNullable<GameSummary["prediction"]> } =>
        g.prediction != null
      )
      .sort((a, b) => b.prediction.confidence - a.prediction.confidence)
      .slice(0, TOP_PICKS_COUNT);

    if (ranked.length === 0) {
      setTopPicks([]);
      return;
    }

    Promise.all(
      ranked.map((game) =>
        getGameDetail(game.game_pk, controller.signal)
          .then((detail) => ({ game, reason: detail.explanation[0] ?? null }))
          .catch(() => ({ game, reason: null }))
      )
    ).then((picks) => setTopPicks(picks));

    return () => controller.abort();
  }, [gamesState]);

  const visibleGames = useMemo(() => {
    if (gamesState.status !== "ready") return [];
    return applyFilters(gamesState.games, filters);
  }, [gamesState, filters]);

  const lastUpdated = useMemo(() => {
    if (gamesState.status !== "ready") return null;
    const timestamps = gamesState.games
      .map((g) => g.prediction?.predicted_at)
      .filter((t): t is string => Boolean(t));
    return timestamps.length ? timestamps.sort().at(-1)! : null;
  }, [gamesState]);

  const seasonRecord = useMemo(() => {
    if (!accuracy) return null;
    const currentYear = String(new Date().getFullYear());
    return accuracy.yearly.find((y) => y.period === currentYear) ?? accuracy.overall;
  }, [accuracy]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Today's Best NRFI Opportunities</h1>
        <p className="text-sm text-slate-500">
          {lastUpdated
            ? `Predictions last updated ${formatRelativeTime(lastUpdated)}`
            : "NRFI/YRFI predictions for every MLB game today"}
        </p>
      </header>

      <div className="mb-8">
        <TopPicks picks={topPicks} />
      </div>

      {gamesState.status === "ready" && (
        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatTile label="Games Today" value={String(gamesState.games.length)} />
          <StatTile label="Model Accuracy" value={formatPct(accuracy?.overall.accuracy ?? null)} />
          <StatTile
            label="Season Record"
            value={
              seasonRecord
                ? `${seasonRecord.correct}-${seasonRecord.total - seasonRecord.correct}`
                : "—"
            }
          />
          <StatTile label="ROI" value="—" />
        </div>
      )}

      <h2 className="mb-4 text-lg font-semibold text-slate-900">All Today's Games</h2>

      <div className="mb-6">
        <FiltersBar filters={filters} onChange={setFilters} />
      </div>

      {gamesState.status === "loading" && (
        <p className="text-center text-slate-400">Loading today's slate…</p>
      )}

      {gamesState.status === "error" && (
        <p className="rounded-lg bg-red-50 p-4 text-center text-sm text-red-600">
          {gamesState.message}
        </p>
      )}

      {gamesState.status === "ready" && gamesState.games.length === 0 && (
        <p className="text-center text-slate-400">No MLB games scheduled today.</p>
      )}

      {gamesState.status === "ready" &&
        gamesState.games.length > 0 &&
        visibleGames.length === 0 && (
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
