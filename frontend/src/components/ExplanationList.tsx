interface ExplanationListProps {
  explanation: string[];
}

export function ExplanationList({ explanation }: ExplanationListProps) {
  if (explanation.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        No explanation available for this prediction.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {explanation.map((point) => (
        <li key={point} className="flex gap-2 text-sm text-slate-700">
          <span aria-hidden="true" className="text-teal-600">
            •
          </span>
          <span>{point}</span>
        </li>
      ))}
    </ul>
  );
}
