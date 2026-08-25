interface ExplanationListProps {
  explanation: string[];
}

export function ExplanationList({ explanation }: ExplanationListProps) {
  if (explanation.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No explanation available for this prediction.
      </p>
    );
  }

  return (
    <div className="divide-y divide-border">
      {explanation.map((point) => (
        <div key={point} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
          <span
            aria-hidden="true"
            className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
          />
          <span className="text-sm text-foreground">{point}</span>
        </div>
      ))}
    </div>
  );
}
