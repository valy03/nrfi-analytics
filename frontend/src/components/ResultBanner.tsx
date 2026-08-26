import { Check, X } from "lucide-react";
import type { ActualResult, PredictedLabel, Team } from "../api/types";

interface ResultBannerProps {
  correct: boolean;
  predictedLabel: PredictedLabel;
  actualResult: ActualResult;
  homeTeam: Team;
  awayTeam: Team;
}

// A plain-language confirmation of what actually happened — built from the
// real per-side 1st-inning runs already stored (ActualResult), not a
// generic "correct"/"incorrect" label. Correctness genuinely is good/bad
// (same reasoning as WinLossBadge), so green/red is appropriate here.
function describeOutcome(result: ActualResult, homeTeam: Team, awayTeam: Team): string {
  if (result.nrfi) return "First inning scoreless.";
  const homeScored = (result.home_runs_1st ?? 0) > 0;
  const awayScored = (result.away_runs_1st ?? 0) > 0;
  if (homeScored && awayScored) return "Both teams scored in the 1st.";
  if (homeScored) return `${homeTeam.name} scored in the 1st.`;
  if (awayScored) return `${awayTeam.name} scored in the 1st.`;
  return "A run scored in the 1st.";
}

export function ResultBanner({
  correct,
  predictedLabel,
  actualResult,
  homeTeam,
  awayTeam,
}: ResultBannerProps) {
  const Icon = correct ? Check : X;
  const tone = correct
    ? "border-primary bg-primary/5 text-primary"
    : "border-destructive bg-destructive/5 text-destructive";

  return (
    <div className={`flex items-center gap-2 rounded-lg border-l-4 px-4 py-2.5 text-sm ${tone}`}>
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      <span className="font-semibold">{predictedLabel} {correct ? "Confirmed" : "Missed"}.</span>
      <span className="font-normal text-foreground">
        {describeOutcome(actualResult, homeTeam, awayTeam)}
      </span>
    </div>
  );
}
