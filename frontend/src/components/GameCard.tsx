import { Clock, MapPin } from "lucide-react";
import { Link } from "react-router-dom";
import type { GameSummary, Pitcher, Team } from "../api/types";
import { formatMoneyline } from "../lib/format";
import { getTeamColor } from "../lib/teamColors";
import { PredictionBadge } from "./PredictionBadge";
import { TeamLogo } from "./TeamLogo";
import { WeatherSummary } from "./WeatherSummary";

function formatStartTime(startTimeUtc: string | null): string {
  if (!startTimeUtc) return "Time TBD";
  return new Date(startTimeUtc).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

interface TeamRowProps {
  team: Team;
  pitcher: Pitcher | null;
}

function TeamRow({ team, pitcher }: TeamRowProps) {
  const color = getTeamColor(team.id);
  return (
    <div
      className="flex items-center justify-between gap-3 rounded-lg px-3 py-2"
      style={{ backgroundImage: `linear-gradient(to right, ${color}40, transparent 90%)` }}
    >
      <div className="flex items-center gap-3">
        <TeamLogo team={team} size={32} />
        <div>
          <div className="font-semibold text-foreground">{team.name}</div>
          <div className="text-xs text-muted-foreground">
            {pitcher ? pitcher.full_name : "Starter TBD"}
            {pitcher?.throws && ` (${pitcher.throws}HP)`}
          </div>
        </div>
      </div>
      {pitcher?.nrfi_rate_season != null && (
        <span className="shrink-0 font-mono text-sm text-muted-foreground">
          {(pitcher.nrfi_rate_season * 100).toFixed(0)}% NRFI
        </span>
      )}
    </div>
  );
}

interface GameCardProps {
  game: GameSummary;
  // Both only set for Top Picks — reason needs a per-game detail fetch,
  // and fair odds needs a real prediction to compute from — neither is
  // available for the plain Full Slate list.
  reason?: string | null;
  fairOdds?: number | null;
}

export function GameCard({ game, reason, fairOdds }: GameCardProps) {
  // Unconfirmed starters (wireframes.md: "a pick needs a real prediction
  // behind it") — the game still belongs in the full list, just visually
  // deprioritized rather than looking identical to a fully-predicted one.
  const unconfirmed = !game.home_pitcher || !game.away_pitcher;

  return (
    <Link
      to={`/games/${game.game_pk}`}
      className={`block rounded-xl border border-primary/25 bg-card p-4 transition hover:border-primary/50 hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary ${
        unconfirmed ? "opacity-60" : ""
      }`}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Clock className="size-3.5" aria-hidden="true" />
          {formatStartTime(game.start_time_utc)}
        </span>
        <span className="inline-flex items-center gap-1">
          <MapPin className="size-3.5" aria-hidden="true" />
          {game.venue_name ?? "Venue TBD"}
        </span>
      </div>

      <div className="space-y-3">
        <TeamRow team={game.away_team} pitcher={game.away_pitcher} />
        <div className="relative border-t border-border">
          <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-2 text-xs text-muted-foreground">
            @
          </span>
        </div>
        <TeamRow team={game.home_team} pitcher={game.home_pitcher} />
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
        <PredictionBadge prediction={game.prediction} status={game.status} />
        <div className="flex items-center gap-3">
          {fairOdds != null && (
            <span
              className="font-mono text-sm font-medium text-foreground"
              title="Computed from our model's own probability — not a sportsbook line"
            >
              <span className="mr-1 text-[10px] font-normal uppercase tracking-wide text-muted-foreground">
                Fair
              </span>
              {formatMoneyline(fairOdds)}
            </span>
          )}
          <WeatherSummary weather={game.weather} />
        </div>
      </div>
      {reason && <p className="mt-1.5 text-xs text-muted-foreground">{reason}</p>}
    </Link>
  );
}
