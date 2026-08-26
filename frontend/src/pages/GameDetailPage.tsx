import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, getGameDetail } from "../api/client";
import type { GameDetail } from "../api/types";
import { ConfidenceDial } from "../components/ConfidenceDial";
import { ExplanationList } from "../components/ExplanationList";
import { OddsSummary } from "../components/OddsSummary";
import { PitcherDetailCard } from "../components/PitcherDetailCard";
import { PredictionBadge } from "../components/PredictionBadge";
import { PredictionSummary } from "../components/PredictionSummary";
import { ResultBanner } from "../components/ResultBanner";
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
    <div className="mx-auto max-w-4xl px-4 py-8 md:px-6 md:py-10">
      {state.status === "loading" && (
        <p className="text-center text-muted-foreground">Loading game…</p>
      )}

      {state.status === "error" && (
        <p className="rounded-lg bg-destructive/10 p-4 text-center text-sm text-destructive">
          {state.message}
        </p>
      )}

      {state.status === "ready" && <GameDetailContent game={state.game} />}
    </div>
  );
}

function GameDetailContent({ game }: { game: GameDetail }) {
  const prediction = game.prediction;
  const probability = prediction
    ? prediction.predicted_label === "NRFI"
      ? prediction.nrfi_probability
      : prediction.yrfi_probability
    : null;

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-border bg-card p-6 md:p-8">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="font-mono text-xs text-muted-foreground">
              {formatFullDateTime(game.start_time_utc)}
              {game.status && ` · (${game.status})`} · {game.venue_name ?? "Venue TBD"}
            </p>
            <h1 className="mt-2 flex items-center gap-3 text-2xl font-bold tracking-tight md:text-3xl">
              <TeamLogo team={game.away_team} size={36} />
              {game.away_team.name}
              <span className="text-muted-foreground">@</span>
              {game.home_team.name}
              <TeamLogo team={game.home_team} size={36} />
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {game.away_pitcher?.full_name ?? "TBD"}
              {game.away_pitcher?.throws && ` (${game.away_pitcher.throws}HP)`} vs{" "}
              {game.home_pitcher?.full_name ?? "TBD"}
              {game.home_pitcher?.throws && ` (${game.home_pitcher.throws}HP)`}
            </p>
            <div className="mt-4 flex items-center gap-3">
              <PredictionBadge prediction={prediction} status={game.status} />
              <WeatherSummary weather={game.weather} />
            </div>
            {game.correct !== null && prediction && game.actual_result && (
              <div className="mt-4">
                <ResultBanner
                  correct={game.correct}
                  predictedLabel={prediction.predicted_label}
                  actualResult={game.actual_result}
                  homeTeam={game.home_team}
                  awayTeam={game.away_team}
                />
              </div>
            )}
          </div>
          {probability != null && (
            <div className="flex shrink-0 justify-center md:justify-end">
              <ConfidenceDial value={probability} size={140} />
            </div>
          )}
        </div>
      </div>

      <PredictionSummary prediction={game.prediction} status={game.status} />

      {game.prediction && (
        <section className="rounded-xl border border-border bg-card p-4">
          <div className="mb-2 font-mono text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Why This Prediction
          </div>
          <ExplanationList explanation={game.explanation} />
        </section>
      )}

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="mb-2 font-mono text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Betting Odds
        </div>
        <OddsSummary
          odds={game.odds}
          homeAbbr={game.home_team.abbreviation}
          awayAbbr={game.away_team.abbreviation}
        />
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <PitcherDetailCard pitcher={game.away_pitcher} team={game.away_team} sideLabel="Away" />
        <PitcherDetailCard pitcher={game.home_pitcher} team={game.home_team} sideLabel="Home" />
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

      <p className="rounded-xl border border-dashed border-border bg-secondary/40 p-4 text-xs leading-relaxed text-muted-foreground">
        <span className="font-semibold text-foreground">How to read this:</span> every rate
        above is computed as of this game only — from data strictly before it, never same-day
        results — and shrunk toward the league average when a pitcher or team has a small
        sample behind it, so one lucky start can't look like a track record. First-inning
        scoring is close to a coin flip league-wide, so a modest edge here is expected, not a
        bug.
      </p>
    </div>
  );
}
