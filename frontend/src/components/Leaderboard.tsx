export interface LeaderboardRow {
  key: string | number;
  label: string;
  secondaryLabel: string;
  value: number;
  valueLabel: string;
}

interface LeaderboardProps {
  rows: LeaderboardRow[];
  valueColumnLabel: string;
}

// A table with an inline bar per row — the "compare magnitude" job from a
// single sequential hue, but built as a real <table> so it's inherently its
// own accessible data view rather than a separate SVG chart needing one.
export function Leaderboard({ rows, valueColumnLabel }: LeaderboardProps) {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-400">Not enough games played yet.</p>;
  }

  const maxValue = Math.max(...rows.map((r) => r.value));

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs text-slate-400">
          <th className="pb-2 font-medium">#</th>
          <th className="pb-2 font-medium">Name</th>
          <th className="pb-2 font-medium">{valueColumnLabel}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={row.key} className="border-t border-slate-100">
            <td className="py-2 align-top text-slate-400">{i + 1}</td>
            <td className="py-2 align-top">
              <div className="text-slate-900">{row.label}</div>
              <div className="text-xs text-slate-400">{row.secondaryLabel}</div>
            </td>
            <td className="w-40 py-2 align-top">
              <div className="flex items-center gap-2">
                <div className="h-2 flex-1 rounded-full bg-slate-100">
                  <div
                    className="h-2 rounded-full bg-teal-600"
                    style={{ width: `${(row.value / maxValue) * 100}%` }}
                  />
                </div>
                <span className="w-14 shrink-0 text-right font-medium tabular-nums text-slate-900">
                  {row.valueLabel}
                </span>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
