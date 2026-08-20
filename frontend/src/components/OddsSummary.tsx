import type { Odds } from "../api/types";
import { formatMoneyline } from "../lib/format";

interface OddsSummaryProps {
  odds: Odds | null;
  homeAbbr: string;
  awayAbbr: string;
}

export function OddsSummary({ odds, homeAbbr, awayAbbr }: OddsSummaryProps) {
  if (!odds) {
    return <p className="text-sm text-slate-400">Odds unavailable</p>;
  }

  return (
    <div className="flex flex-wrap items-center gap-4 text-sm">
      <span className="text-slate-600">
        {awayAbbr}{" "}
        <span className="font-semibold text-slate-900">
          {formatMoneyline(odds.away_moneyline)}
        </span>
      </span>
      <span className="text-slate-600">
        {homeAbbr}{" "}
        <span className="font-semibold text-slate-900">
          {formatMoneyline(odds.home_moneyline)}
        </span>
      </span>
      <span className="text-xs text-slate-400">via {odds.bookmaker}</span>
    </div>
  );
}
