import type { Pitcher } from "../api/types";
import { formatCount, formatPct, formatShortDate, formatStat } from "../lib/format";

interface StatRowProps {
  label: string;
  value: string;
}

function StatRow({ label, value }: StatRowProps) {
  return (
    <div className="flex justify-between py-1 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  );
}

interface PitcherDetailCardProps {
  pitcher: Pitcher | null;
  sideLabel: "Home" | "Away";
}

export function PitcherDetailCard({ pitcher, sideLabel }: PitcherDetailCardProps) {
  const heading = (
    <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
      {sideLabel} Starter
    </div>
  );

  if (!pitcher) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        {heading}
        <p className="text-sm text-slate-400">Starter TBD</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      {heading}
      <h3 className="mb-3 text-lg font-semibold text-slate-900">
        {pitcher.full_name}
        {pitcher.throws && (
          <span className="ml-2 text-sm font-normal text-slate-400">
            (Throws {pitcher.throws})
          </span>
        )}
      </h3>

      <div className="divide-y divide-slate-100">
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
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Last {pitcher.recent_starts.length} Starts
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-400">
                <th className="pb-1 font-medium">Date</th>
                <th className="pb-1 font-medium">Opp</th>
                <th className="pb-1 text-right font-medium">1st Runs</th>
                <th className="pb-1 text-right font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {pitcher.recent_starts.map((start) => (
                <tr key={start.game_pk} className="border-t border-slate-100">
                  <td className="py-1 text-slate-600">{formatShortDate(start.game_date)}</td>
                  <td className="py-1 text-slate-600">{start.opponent}</td>
                  <td className="py-1 text-right text-slate-600">{start.runs_1st ?? "—"}</td>
                  <td className="py-1 text-right">
                    {start.nrfi == null ? (
                      "—"
                    ) : (
                      <span className={start.nrfi ? "text-teal-600" : "text-amber-600"}>
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
