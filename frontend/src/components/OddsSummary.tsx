import type { Odds } from "../api/types";
import { formatMoneyline } from "../lib/format";

interface OddsSummaryProps {
  odds: Odds | null;
  homeAbbr: string;
  awayAbbr: string;
}

export function OddsSummary({ odds, homeAbbr, awayAbbr }: OddsSummaryProps) {
  if (!odds) {
    return <p className="text-sm text-muted-foreground">Odds unavailable</p>;
  }

  return (
    <div className="flex flex-wrap items-center gap-4 text-sm">
      <span className="text-muted-foreground">
        {awayAbbr}{" "}
        <span className="font-mono font-semibold text-foreground">
          {formatMoneyline(odds.away_moneyline)}
        </span>
      </span>
      <span className="text-muted-foreground">
        {homeAbbr}{" "}
        <span className="font-mono font-semibold text-foreground">
          {formatMoneyline(odds.home_moneyline)}
        </span>
      </span>
      <span className="font-mono text-xs text-muted-foreground">via {odds.bookmaker}</span>
    </div>
  );
}
