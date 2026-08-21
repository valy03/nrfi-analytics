interface WinLossBadgeProps {
  correct: boolean | null;
}

// Unlike PredictionBadge's NRFI/YRFI (deliberately neutral — neither is
// "good"), correctness genuinely is good/bad, so this is the one place a
// green/red status pair belongs (wireframes.md's palette: positive=green,
// negative=red).
export function WinLossBadge({ correct }: WinLossBadgeProps) {
  if (correct === null) {
    return (
      <span className="inline-flex items-center rounded-full bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-400 ring-1 ring-inset ring-slate-200">
        Pending
      </span>
    );
  }

  if (correct) {
    return (
      <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-semibold text-green-700 ring-1 ring-inset ring-green-600/20">
        Win
      </span>
    );
  }

  return (
    <span className="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700 ring-1 ring-inset ring-red-600/20">
      Loss
    </span>
  );
}
