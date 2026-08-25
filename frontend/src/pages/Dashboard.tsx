import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  getAccuracyReport,
  getGameDetail,
  getGames,
  getTopPicksAccuracy,
} from "../api/client";
import type { AccuracyBucket, AccuracyReport, GameSummary } from "../api/types";
import { DEFAULT_FILTERS, FiltersBar, type Filters } from "../components/FiltersBar";
import { GameCard } from "../components/GameCard";
import { StatTile } from "../components/StatTile";
import { TopPicks, type TopPick } from "../components/TopPicks";
import { formatPct, formatRelativeTime } from "../lib/format";

const TOP_PICKS_COUNT = 3;

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
  const [topPicksAccuracy, setTopPicksAccuracy] = useState<AccuracyBucket | null>(null);
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

    getTopPicksAccuracy(TOP_PICKS_COUNT, undefined, controller.signal)
      .then(setTopPicksAccuracy)
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

  // Label the hero with the slate's own date (from the backend's
  // mlb_today(), US Eastern), not the browser's local clock — those two
  // can disagree by a full calendar day for a few hours each evening
  // Pacific time, which would otherwise show a date that doesn't match
  // the games actually on screen.
  const today = useMemo(() => {
    const gameDate = gamesState.status === "ready" ? gamesState.games[0]?.game_date : undefined;
    if (!gameDate) {
      return new Date().toLocaleDateString(undefined, { month: "long", day: "numeric" });
    }
    const [year, month, day] = gameDate.split("-").map(Number);
    return new Date(year, month - 1, day).toLocaleDateString(undefined, {
      month: "long",
      day: "numeric",
    });
  }, [gamesState]);

  return (
    <div>
      {/* Hero */}
      <section className="bg-chalk border-b border-border">
        <div className="mx-auto max-w-6xl px-4 py-10 md:px-6 md:py-14">
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div className="max-w-xl">
              <span className="font-mono text-xs uppercase tracking-[0.2em] text-primary">
                Today · {today}
              </span>
              <h1 className="mt-3 text-3xl font-bold tracking-tight text-balance md:text-4xl">
                No Run First Inning, explained.
              </h1>
              <p className="mt-3 text-pretty leading-relaxed text-muted-foreground">
                Transparent, data-driven NRFI predictions for every MLB game — with the exact
                factors behind each call, not just a confidence score.
              </p>
              {lastUpdated && (
                <p className="mt-2 font-mono text-xs text-muted-foreground">
                  Predictions last updated {formatRelativeTime(lastUpdated)}
                </p>
              )}
            </div>
            {gamesState.status === "ready" && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-5 md:flex">
                <StatTile label="Games Today" value={String(gamesState.games.length)} />
                <StatTile
                  label="Model Accuracy"
                  value={formatPct(accuracy?.overall.accuracy ?? null)}
                />
                <StatTile
                  label="Season Record"
                  value={
                    seasonRecord
                      ? `${seasonRecord.correct}-${seasonRecord.total - seasonRecord.correct}`
                      : "—"
                  }
                />
                <StatTile
                  label="Top 3 Plays Record"
                  value={
                    topPicksAccuracy && topPicksAccuracy.total > 0
                      ? `${topPicksAccuracy.correct}-${topPicksAccuracy.total - topPicksAccuracy.correct}`
                      : "—"
                  }
                />
                <StatTile label="ROI" value="—" />
              </div>
            )}
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 py-10 md:px-6 md:py-12">
        {/* Top Picks */}
        <section>
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-xl font-bold tracking-tight">Top Picks</h2>
            <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
              Highest confidence
            </span>
          </div>
          <TopPicks picks={topPicks} />
        </section>

        {/* Full slate */}
        <section className="mt-14">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-xl font-bold tracking-tight">Full Slate</h2>
            {gamesState.status === "ready" && (
              <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
                {gamesState.games.length} games
              </span>
            )}
          </div>

          <div className="mb-6">
            <FiltersBar filters={filters} onChange={setFilters} />
          </div>

          {gamesState.status === "loading" && (
            <p className="text-center text-muted-foreground">Loading today's slate…</p>
          )}

          {gamesState.status === "error" && (
            <p className="rounded-lg bg-destructive/10 p-4 text-center text-sm text-destructive">
              {gamesState.message}
            </p>
          )}

          {gamesState.status === "ready" && gamesState.games.length === 0 && (
            <p className="text-center text-muted-foreground">No MLB games scheduled today.</p>
          )}

          {gamesState.status === "ready" &&
            gamesState.games.length > 0 &&
            visibleGames.length === 0 && (
              <p className="text-center text-muted-foreground">
                No games match the current filters.
              </p>
            )}

          {visibleGames.length > 0 && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {visibleGames.map((game) => (
                <GameCard key={game.game_pk} game={game} />
              ))}
            </div>
          )}
        </section>
      </div>

      <footer className="border-t border-border">
        <div className="mx-auto max-w-6xl px-4 py-6 md:px-6">
          <div className="flex flex-col gap-2 font-mono text-xs uppercase tracking-wide text-muted-foreground md:flex-row md:items-center md:justify-between">
            <span>NRFI Analytics — for informational purposes only</span>
            <span>Model outputs are estimates, not guarantees. Not betting advice.</span>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            21+ · For entertainment only. NRFI Analytics is an independent product and is
            not affiliated with, endorsed by, or sponsored by Major League Baseball. Team
            names and logos are the property of their respective owners and appear here
            only to identify the teams in publicly available game data.
          </p>
        </div>
      </footer>
    </div>
  );
}
