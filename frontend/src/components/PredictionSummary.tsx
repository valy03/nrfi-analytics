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
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="text-sm text-slate-400">
          {hasNotStarted(status)
            ? "No prediction yet — check back once both starters are announced."
            : `No prediction was made for this game (${status}).`}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Prediction
          </div>
          <div className="text-2xl font-bold text-slate-900">
            {prediction.predicted_label}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Confidence
          </div>
          <div className="text-2xl font-bold text-slate-900">
            {formatPct(prediction.confidence)}
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 text-sm">
        <div>
          <span className="text-slate-500">NRFI Probability</span>
          <div className="font-medium text-slate-900">
            {formatPct(prediction.nrfi_probability)}
          </div>
        </div>
        <div>
          <span className="text-slate-500">YRFI Probability</span>
          <div className="font-medium text-slate-900">
            {formatPct(prediction.yrfi_probability)}
          </div>
        </div>
      </div>

      <div className="mt-3 text-xs text-slate-400">
        {prediction.model_name} · {prediction.model_version}
      </div>
    </div>
  );
}
