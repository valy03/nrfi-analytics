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
