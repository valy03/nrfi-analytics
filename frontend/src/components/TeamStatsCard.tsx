import type { Team, TeamStats } from "../api/types";
import { formatCount, formatPct, formatStat } from "../lib/format";

interface StatRowProps {
  label: string;
  value: string;
}

function StatRow({ label, value }: StatRowProps) {
  return (
    <div className="flex justify-between py-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-medium text-foreground">{value}</span>
    </div>
  );
}

interface TeamStatsCardProps {
  team: Team;
  stats: TeamStats | null;
  splitLabel: string;
}

export function TeamStatsCard({ team, stats, splitLabel }: TeamStatsCardProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-1 font-mono text-xs uppercase tracking-wide text-muted-foreground">
        {team.abbreviation} Offense
      </div>
      <h3 className="mb-3 text-lg font-bold tracking-tight text-foreground">{team.name}</h3>

      {stats ? (
        <div className="divide-y divide-border">
          <StatRow label="1st Inning Runs/Game" value={formatStat(stats.runs_1st_avg)} />
          <StatRow label="Scored in 1st %" value={formatPct(stats.scored_1st_rate)} />
          <StatRow
            label="Season Scored in 1st %"
            value={formatPct(stats.scored_1st_rate_season)}
          />
          <StatRow label={splitLabel} value={formatPct(stats.scored_1st_rate_split)} />
          <StatRow label="OPS" value={formatStat(stats.ops)} />
          <StatRow label="OBP" value={formatStat(stats.obp)} />
          <StatRow label="Slugging %" value={formatStat(stats.slg)} />
          <StatRow label="Batting Average" value={formatStat(stats.batting_avg, 3)} />
          <StatRow label="Games Played" value={formatCount(stats.games_prior)} />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No stats available yet.</p>
      )}
    </div>
  );
}
