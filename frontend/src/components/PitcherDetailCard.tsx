import type { Pitcher, Team } from "../api/types";
import { formatCount, formatPct, formatShortDate, formatStat } from "../lib/format";
import { getTeamColor } from "../lib/teamColors";
import { PitcherHeadshot } from "./PitcherHeadshot";

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

interface PitcherDetailCardProps {
  pitcher: Pitcher | null;
  team: Team;
  sideLabel: "Home" | "Away";
}

export function PitcherDetailCard({ pitcher, team, sideLabel }: PitcherDetailCardProps) {
  const color = getTeamColor(team.id);
  const heading = (
    <div className="mb-1 font-mono text-xs uppercase tracking-wide text-muted-foreground">
      {sideLabel} Starter
    </div>
  );

  if (!pitcher) {
    return (
      <div
        className="rounded-xl border-2 bg-card p-4"
        style={{ borderColor: `${color}55` }}
      >
        {heading}
        <p className="text-sm text-muted-foreground">Starter TBD</p>
      </div>
    );
  }

  return (
    <div
      className="rounded-xl border-2 bg-card p-4"
      style={{
        borderColor: `${color}80`,
        backgroundImage: `linear-gradient(to bottom, ${color}26, transparent 220px)`,
      }}
    >
      {heading}
      <div className="mb-3 flex items-center gap-3">
        <PitcherHeadshot pitcher={pitcher} size={56} />
        <h3 className="text-lg font-bold tracking-tight text-foreground">
          {pitcher.full_name}
          {pitcher.throws && (
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              (Throws {pitcher.throws})
            </span>
          )}
        </h3>
      </div>

      <div className="divide-y divide-border">
        <StatRow label="ERA" value={formatStat(pitcher.era)} />
        <StatRow label="WHIP" value={formatStat(pitcher.whip)} />
        <StatRow label="FIP" value={formatStat(pitcher.fip)} />
        <StatRow label="xERA" value={formatStat(pitcher.xera)} />
        <StatRow label="Strikeout %" value={formatPct(pitcher.k_rate_1st)} />
        <StatRow label="Walk %" value={formatPct(pitcher.bb_rate_1st)} />
        <StatRow label="Career NRFI %" value={formatPct(pitcher.nrfi_rate_career)} />
        <StatRow label="Season NRFI %" value={formatPct(pitcher.nrfi_rate_season)} />
        <StatRow label="Last 5 Starts NRFI %" value={formatPct(pitcher.nrfi_rate_last5)} />
        <StatRow label="Prior Starts" value={formatCount(pitcher.starts_prior)} />
      </div>

      {pitcher.recent_starts.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 font-mono text-xs uppercase tracking-wide text-muted-foreground">
            Last {pitcher.recent_starts.length} Starts
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="pb-1 font-medium">Date</th>
                <th className="pb-1 font-medium">Opp</th>
                <th className="pb-1 text-right font-medium">1st Runs</th>
                <th className="pb-1 text-right font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {pitcher.recent_starts.map((start) => (
                <tr key={start.game_pk} className="border-t border-border">
                  <td className="py-1 text-muted-foreground">
                    {formatShortDate(start.game_date)}
                  </td>
                  <td className="py-1 text-muted-foreground">{start.opponent}</td>
                  <td className="py-1 text-right font-mono text-muted-foreground">
                    {start.runs_1st ?? "—"}
                  </td>
                  <td className="py-1 text-right">
                    {start.nrfi == null ? (
                      "—"
                    ) : (
                      <span className={start.nrfi ? "text-primary" : "text-amber-600"}>
                        {start.nrfi ? "NRFI" : "YRFI"}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
