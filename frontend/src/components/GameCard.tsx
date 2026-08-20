import type { GameSummary, Pitcher, Team } from "../api/types";
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

interface TeamColumnProps {
  team: Team;
  pitcher: Pitcher | null;
  align: "left" | "right";
}

function TeamColumn({ team, pitcher, align }: TeamColumnProps) {
  return (
    <div className={`flex items-center gap-3 ${align === "right" ? "flex-row-reverse text-right" : ""}`}>
      <TeamLogo team={team} />
      <div>
        <div className="font-semibold text-slate-900">{team.abbreviation}</div>
        <div className="text-xs text-slate-500">
          {pitcher ? pitcher.full_name : "Starter TBD"}
          {pitcher?.nrfi_rate_season != null && (
            <span className="ml-1 text-slate-400">
              ({(pitcher.nrfi_rate_season * 100).toFixed(0)}% NRFI)
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

interface GameCardProps {
  game: GameSummary;
}

export function GameCard({ game }: GameCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow-md">
      <div className="mb-3 flex items-center justify-between text-xs text-slate-400">
        <span>{formatStartTime(game.start_time_utc)}</span>
        <span>{game.venue_name ?? "Venue TBD"}</span>
      </div>

      <div className="flex items-center justify-between gap-4">
        <TeamColumn team={game.away_team} pitcher={game.away_pitcher} align="left" />
        <span className="text-sm font-medium text-slate-300">@</span>
        <TeamColumn team={game.home_team} pitcher={game.home_pitcher} align="right" />
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
        <PredictionBadge prediction={game.prediction} status={game.status} />
        <WeatherSummary weather={game.weather} />
      </div>
    </div>
  );
}
