import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getGameDetail } from "../api/client";
import type { GameDetail } from "../api/types";
import { ExplanationList } from "../components/ExplanationList";
import { OddsSummary } from "../components/OddsSummary";
import { PitcherDetailCard } from "../components/PitcherDetailCard";
import { PredictionSummary } from "../components/PredictionSummary";
import { TeamLogo } from "../components/TeamLogo";
import { TeamStatsCard } from "../components/TeamStatsCard";
import { WeatherSummary } from "../components/WeatherSummary";
import { formatFullDateTime } from "../lib/format";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; game: GameDetail };

export function GameDetailPage() {
  const { gamePk } = useParams<{ gamePk: string }>();
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    if (!gamePk) return;
    const controller = new AbortController();
    setState({ status: "loading" });

    getGameDetail(Number(gamePk), controller.signal)
      .then((game) => setState({ status: "ready", game }))
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        const message =
          err instanceof ApiError && err.status === 404
            ? "Game not found."
            : err instanceof ApiError
              ? err.message
              : "Could not reach the API";
        setState({ status: "error", message });
      });

    return () => controller.abort();
  }, [gamePk]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link
        to="/"
        className="mb-6 inline-block text-sm text-teal-600 hover:text-teal-700"
      >
        ← Back to today's games
      </Link>

      {state.status === "loading" && (
        <p className="text-center text-slate-400">Loading game…</p>
      )}

      {state.status === "error" && (
        <p className="rounded-lg bg-red-50 p-4 text-center text-sm text-red-600">
          {state.message}
        </p>
      )}

      {state.status === "ready" && (
        <GameDetailContent game={state.game} />
      )}
    </div>
  );
}

function GameDetailContent({ game }: { game: GameDetail }) {
  return (
    <div className="space-y-6">
      <header className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-center gap-6">
          <div className="flex flex-col items-center gap-2">
            <TeamLogo team={game.away_team} size={56} />
            <span className="font-semibold text-slate-900">
              {game.away_team.abbreviation}
            </span>
          </div>
          <span className="text-lg text-slate-300">@</span>
          <div className="flex flex-col items-center gap-2">
            <TeamLogo team={game.home_team} size={56} />
            <span className="font-semibold text-slate-900">
              {game.home_team.abbreviation}
            </span>
          </div>
        </div>
        <div className="mt-4 space-y-1 text-center text-sm text-slate-500">
          <div>
            {formatFullDateTime(game.start_time_utc)}
            {game.status && <span className="ml-2 text-slate-400">({game.status})</span>}
          </div>
          <div>{game.venue_name ?? "Venue TBD"}</div>
          <div className="flex justify-center">
            <WeatherSummary weather={game.weather} />
          </div>
        </div>
      </header>

      <PredictionSummary prediction={game.prediction} status={game.status} />

      {game.prediction && (
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Why This Prediction
          </div>
          <ExplanationList explanation={game.explanation} />
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Betting Odds
        </div>
        <OddsSummary
          odds={game.odds}
          homeAbbr={game.home_team.abbreviation}
          awayAbbr={game.away_team.abbreviation}
        />
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <PitcherDetailCard pitcher={game.away_pitcher} sideLabel="Away" />
        <PitcherDetailCard pitcher={game.home_pitcher} sideLabel="Home" />
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <TeamStatsCard
          team={game.away_team}
          stats={game.away_team_stats}
          splitLabel="Road (scored 1st %)"
        />
        <TeamStatsCard
          team={game.home_team}
          stats={game.home_team_stats}
          splitLabel="Home (scored 1st %)"
        />
      </section>
    </div>
  );
}
