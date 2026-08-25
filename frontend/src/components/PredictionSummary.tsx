import type { Prediction } from "../api/types";
import { formatPct } from "../lib/format";
import { hasNotStarted } from "../lib/gameStatus";

interface PredictionSummaryProps {
  prediction: Prediction | null;
  status: string | null;
}

export function PredictionSummary({ prediction, status }: PredictionSummaryProps) {
  if (!prediction) {
    return (
      <div className="rounded-xl border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">
          {hasNotStarted(status)
            ? "No prediction yet — check back once both starters are announced."
            : `No prediction was made for this game (${status}).`}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-muted-foreground">NRFI Probability</span>
          <div className="font-mono font-medium text-foreground">
            {formatPct(prediction.nrfi_probability)}
          </div>
        </div>
        <div>
          <span className="text-muted-foreground">YRFI Probability</span>
          <div className="font-mono font-medium text-foreground">
            {formatPct(prediction.yrfi_probability)}
          </div>
        </div>
      </div>
      <div className="mt-3 border-t border-border pt-3 text-xs text-muted-foreground">
        {prediction.model_name} · {prediction.model_version}
      </div>
    </div>
  );
}
