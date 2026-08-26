interface ResultStampProps {
  correct: boolean;
}

// A rubber-stamp treatment (rotated, bold border, letter-spaced caps) —
// deliberately distinct from WinLossBadge's smooth pill (used in the
// History table's dense rows), since this sits in a card's header where a
// "stamped" mark reads better than another rounded chip competing with the
// prediction badge below it.
export function ResultStamp({ correct }: ResultStampProps) {
  const tone = correct
    ? "border-primary bg-primary/10 text-primary"
    : "border-destructive bg-destructive/10 text-destructive";

  return (
    <span
      className={`inline-flex -rotate-[4deg] items-center rounded border-2 px-1.5 py-px text-[10px] font-black uppercase leading-tight tracking-widest ${tone}`}
    >
      {correct ? "Won" : "Lost"}
    </span>
  );
}
