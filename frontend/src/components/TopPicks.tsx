import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import type { GameSummary } from "../api/types";
import { fairAmericanOdds, formatMoneyline } from "../lib/format";
import { getTeamColor } from "../lib/teamColors";
import { ConfidenceDial } from "./ConfidenceDial";
import { GameCard } from "./GameCard";
import { PredictionBadge } from "./PredictionBadge";
import { ResultBanner } from "./ResultBanner";
import { TeamLogo } from "./TeamLogo";

export interface TopPick {
  game: GameSummary;
  reason: string | null;
}

interface TopPicksProps {
  picks: TopPick[];
}

function formatStartTime(startTimeUtc: string | null): string {
  if (!startTimeUtc) return "Time TBD";
  return new Date(startTimeUtc).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function TopPicks({ picks }: TopPicksProps) {
  if (picks.length === 0) {
    return (
      <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
        No confident picks yet — check back once today's starters are announced.
      </p>
    );
  }

  const [feature, ...rest] = picks;
  const featurePrediction = feature.game.prediction!; // every pick here has one
  const featureProbability =
    featurePrediction.predicted_label === "NRFI"
      ? featurePrediction.nrfi_probability
      : featurePrediction.yrfi_probability;
  const featureFairOdds = fairAmericanOdds(featureProbability);
  const awayColor = getTeamColor(feature.game.away_team.id);
  const homeColor = getTeamColor(feature.game.home_team.id);

  return (
    <div>
      <div
        className="rounded-2xl border border-primary/25 bg-card p-6"
        style={{
          backgroundImage: `linear-gradient(to right, ${awayColor}26 0%, transparent 48%, transparent 52%, ${homeColor}26 100%)`,
        }}
      >
        <div className="mb-5 flex items-center justify-between">
          <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
            Pick of the Day
          </span>
          <PredictionBadge prediction={featurePrediction} status={feature.game.status} />
        </div>

        {feature.game.correct !== null && feature.game.actual_result && (
          <div className="mb-5">
            <ResultBanner
              correct={feature.game.correct}
              predictedLabel={featurePrediction.predicted_label}
              actualResult={feature.game.actual_result}
              homeTeam={feature.game.home_team}
              awayTeam={feature.game.away_team}
            />
          </div>
        )}

        <div className="flex flex-col gap-6 md:flex-row md:items-center">
          <div className="flex items-center gap-4">
            <ConfidenceDial value={featureProbability} size={110} />
            <div>
              <div className="flex items-center gap-2 text-lg font-bold text-foreground">
                <TeamLogo team={feature.game.away_team} size={28} />
                {feature.game.away_team.abbreviation}
                <span className="font-normal text-muted-foreground">@</span>
                <TeamLogo team={feature.game.home_team} size={28} />
                {feature.game.home_team.abbreviation}
              </div>
              <div className="text-sm text-muted-foreground">
                {feature.game.away_pitcher?.full_name ?? "TBD"} vs{" "}
                {feature.game.home_pitcher?.full_name ?? "TBD"}
              </div>
              <div className="mt-1 font-mono text-xs text-muted-foreground">
                {formatStartTime(feature.game.start_time_utc)} · {feature.game.venue_name ?? "Venue TBD"}
              </div>
            </div>
          </div>

          <div className="flex-1 md:border-l md:border-border md:pl-6">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Why We Like It
              </span>
              <span
                className="font-mono text-sm font-semibold text-foreground"
                title="Computed from our model's own probability — not a sportsbook line"
              >
                <span className="mr-1 text-[10px] font-normal uppercase tracking-wide text-muted-foreground">
                  Our fair odds
                </span>
                {formatMoneyline(featureFairOdds)}
              </span>
            </div>
            <p className="text-sm text-foreground">
              {feature.reason ?? "Explanation unavailable for this pick."}
            </p>
            <Link
              to={`/games/${feature.game.game_pk}`}
              className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              Full breakdown <ArrowUpRight className="size-3.5" />
            </Link>
          </div>
        </div>
      </div>

      {rest.length > 0 && (
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {rest.map(({ game, reason }) => {
            const prediction = game.prediction!;
            const probability =
              prediction.predicted_label === "NRFI"
                ? prediction.nrfi_probability
                : prediction.yrfi_probability;
            return (
              <GameCard
                key={game.game_pk}
                game={game}
                reason={reason}
                fairOdds={fairAmericanOdds(probability)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
