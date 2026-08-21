import { Link } from "react-router-dom";
import type { GameSummary } from "../api/types";
import { fairAmericanOdds, formatMoneyline } from "../lib/format";
import { PredictionBadge } from "./PredictionBadge";

export interface TopPick {
  game: GameSummary;
  reason: string | null;
}

interface TopPicksProps {
  picks: TopPick[];
}

export function TopPicks({ picks }: TopPicksProps) {
  if (picks.length === 0) {
    return (
      <p className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-400">
        No confident picks yet — check back once today's starters are announced.
      </p>
    );
  }

  return (
    <div className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      {picks.map(({ game, reason }, i) => {
        const prediction = game.prediction!; // every pick here is guaranteed to have one
        const sideProbability =
          prediction.predicted_label === "NRFI"
            ? prediction.nrfi_probability
            : prediction.yrfi_probability;

        return (
          <Link
            key={game.game_pk}
            to={`/games/${game.game_pk}`}
            className="flex items-center gap-4 p-4 transition hover:bg-slate-50"
          >
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-50 text-sm font-bold text-teal-700">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <div className="font-semibold text-slate-900">
                {game.away_team.abbreviation} @ {game.home_team.abbreviation}
              </div>
              {reason && <div className="truncate text-xs text-slate-500">{reason}</div>}
            </div>
            <PredictionBadge prediction={prediction} status={game.status} />
            <span className="w-14 shrink-0 text-right text-sm font-medium tabular-nums text-slate-600">
              {formatMoneyline(fairAmericanOdds(sideProbability))}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
