export function formatPct(value: number | null, decimals = 1): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatStat(value: number | null, decimals = 2): string {
  if (value == null) return "—";
  return value.toFixed(decimals);
}

export function formatCount(value: number | null): string {
  if (value == null) return "—";
  return value.toLocaleString();
}

export function formatMoneyline(value: number): string {
  return value > 0 ? `+${value}` : `${value}`;
}

export function formatShortDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function formatFullDateTime(startTimeUtc: string | null): string {
  if (!startTimeUtc) return "Time TBD";
  return new Date(startTimeUtc).toLocaleString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

// The American-odds line implied by the model's own win probability for
// its predicted side — "if this probability is right, this is the fair
// price," independent of whatever a real bookmaker is actually offering.
export function fairAmericanOdds(probability: number): number {
  const p = Math.min(Math.max(probability, 0.0001), 0.9999);
  return p >= 0.5 ? Math.round((-100 * p) / (1 - p)) : Math.round((100 * (1 - p)) / p);
}

export function formatRelativeTime(isoTimestamp: string): string {
  const diffMs = Date.now() - new Date(isoTimestamp).getTime();
  const diffMin = Math.round(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  return `${diffDay}d ago`;
}
