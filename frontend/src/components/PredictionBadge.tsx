import type { ReactNode } from "react";
import type { Prediction } from "../api/types";
import { hasNotStarted } from "../lib/gameStatus";

interface PredictionBadgeProps {
  prediction: Prediction | null;
  status: string | null;
}

// NRFI/YRFI deliberately avoid green="good"/red="bad" — neither outcome is
// inherently good or bad, they're just different markets. Primary (green,
// this theme's brand color) vs. amber keeps them visually distinct without
// implying a value judgment.
const BADGE_STYLES: Record<string, string> = {
  NRFI: "bg-primary/10 text-primary",
  YRFI: "bg-amber-500/10 text-amber-700",
};
const DOT_STYLES: Record<string, string> = {
  NRFI: "bg-primary",
  YRFI: "bg-amber-500",
};

function NeutralBadge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-muted-foreground">
      {children}
    </span>
  );
}

export function PredictionBadge({ prediction, status }: PredictionBadgeProps) {
  if (!prediction) {
    if (!hasNotStarted(status)) {
      // Already underway or decided — there will never be a prediction for
      // this game, so "no prediction yet" would wrongly imply one's coming.
      return <NeutralBadge>{status}</NeutralBadge>;
    }
    return <NeutralBadge>No prediction yet</NeutralBadge>;
  }

  const { predicted_label, confidence } = prediction;

  return (
    <div className="flex items-center gap-2">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${BADGE_STYLES[predicted_label]}`}
      >
        <span className={`h-1.5 w-1.5 rounded-full ${DOT_STYLES[predicted_label]}`} />
        {predicted_label}
      </span>
      <span className="text-xs text-muted-foreground">
        {(confidence * 100).toFixed(1)}% confidence
      </span>
    </div>
  );
}
