import type { ReactNode } from "react";
import type { Prediction } from "../api/types";
import { hasNotStarted } from "../lib/gameStatus";

interface PredictionBadgeProps {
  prediction: Prediction | null;
  status: string | null;
}

// NRFI/YRFI deliberately avoid green="good"/red="bad" — neither outcome is
// inherently good or bad, they're just different markets. Teal vs. amber
// keeps them visually distinct without implying a value judgment.
const LABEL_STYLES: Record<string, string> = {
  NRFI: "bg-teal-50 text-teal-700 ring-teal-600/20",
  YRFI: "bg-amber-50 text-amber-700 ring-amber-600/20",
};

function NeutralBadge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-400 ring-1 ring-inset ring-slate-200">
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
        className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${LABEL_STYLES[predicted_label]}`}
      >
        {predicted_label}
      </span>
      <span className="text-xs text-slate-500">
        {(confidence * 100).toFixed(1)}% confidence
      </span>
    </div>
  );
}
