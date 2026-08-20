// Mirrors backend/app/prediction/job.py's PENDING_STATUSES — the statuses
// the backend considers "hasn't started yet, still eligible to predict".
// Shared here so the dashboard card and the game-detail page agree on what
// "no prediction yet" vs. "already underway/decided" means.
const PENDING_STATUSES = new Set([
  "Scheduled",
  "Pre-Game",
  "Warmup",
  "Delayed Start",
  "Delayed",
]);

export function hasNotStarted(status: string | null): boolean {
  return status == null || PENDING_STATUSES.has(status);
}
