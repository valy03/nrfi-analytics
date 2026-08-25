interface ConfidenceDialProps {
  // The predicted side's real win probability (0-1) — not a fabricated
  // "strength" label. Our model's honest edge usually sits closer to
  // 50-58% (see docs/milestones.md M5/M6), so this ring is often close to
  // half-full — that's the model being honest, not the dial being broken.
  value: number;
  size?: number;
}

export function ConfidenceDial({ value, size = 120 }: ConfidenceDialProps) {
  const strokeWidth = Math.round(size * 0.08);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = Math.max(0, Math.min(1, value));
  const dashOffset = circumference * (1 - filled);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--muted)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--primary)"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-2xl font-bold tabular-nums text-foreground">
          {Math.round(filled * 100)}%
        </span>
      </div>
    </div>
  );
}
