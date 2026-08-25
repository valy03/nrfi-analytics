import { useState } from "react";
import type { NrfiFrequencyPoint } from "../api/types";

// Single sequential hue (this app's primary theme color) — one series, no
// legend needed. Ink stays on text tokens; only the bars carry the series
// color.
const BAR_COLOR = "var(--primary)";
const BAR_COLOR_HOVER = "#15803d"; // green-700 — a step darker than --primary for hover
const GRIDLINE = "var(--border)";
const AXIS_TEXT = "var(--muted-foreground)";

const WIDTH = 640;
const HEIGHT = 220;
const MARGIN = { top: 16, right: 12, bottom: 28, left: 40 };
const MAX_BAR_WIDTH = 24;
const BAR_GAP = 2;

function niceMax(value: number): number {
  // Smallest "clean" ceiling (in 5%-steps) at least 15% above the data max,
  // so the tallest bar never touches the plot's top edge.
  const padded = value * 1.15;
  return Math.min(1, Math.ceil(padded / 0.05) * 0.05);
}

interface NrfiFrequencyChartProps {
  data: NrfiFrequencyPoint[];
}

export function NrfiFrequencyChart({ data }: NrfiFrequencyChartProps) {
  const [hovered, setHovered] = useState<number | null>(null);

  if (data.length === 0) {
    return <p className="text-sm text-muted-foreground">No labeled games yet.</p>;
  }

  const plotWidth = WIDTH - MARGIN.left - MARGIN.right;
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const maxRate = niceMax(Math.max(...data.map((d) => d.nrfi_rate)));
  const yTicks = [0, 0.25 * maxRate, 0.5 * maxRate, 0.75 * maxRate, maxRate];

  const slotWidth = plotWidth / data.length;
  const barWidth = Math.min(MAX_BAR_WIDTH, slotWidth - BAR_GAP);

  const yFor = (rate: number) => plotHeight - (rate / maxRate) * plotHeight;

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="w-full"
        role="img"
        aria-label="NRFI rate by season"
      >
        <g transform={`translate(${MARGIN.left}, ${MARGIN.top})`}>
          {yTicks.map((tick) => (
            <g key={tick}>
              <line
                x1={0}
                x2={plotWidth}
                y1={yFor(tick)}
                y2={yFor(tick)}
                stroke={GRIDLINE}
                strokeWidth={1}
              />
              <text
                x={-8}
                y={yFor(tick)}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={11}
                fill={AXIS_TEXT}
              >
                {Math.round(tick * 100)}%
              </text>
            </g>
          ))}

          {data.map((point, i) => {
            const x = i * slotWidth + (slotWidth - barWidth) / 2;
            const y = yFor(point.nrfi_rate);
            const height = plotHeight - y;
            const isHovered = hovered === i;
            return (
              <g key={point.period}>
                <rect
                  x={x}
                  y={y}
                  width={barWidth}
                  height={Math.max(height, 1)}
                  rx={4}
                  fill={isHovered ? BAR_COLOR_HOVER : BAR_COLOR}
                  onPointerEnter={() => setHovered(i)}
                  onPointerLeave={() => setHovered(null)}
                  onFocus={() => setHovered(i)}
                  onBlur={() => setHovered(null)}
                  tabIndex={0}
                  role="button"
                  aria-label={`${point.period}: ${(point.nrfi_rate * 100).toFixed(1)}% NRFI over ${point.games} games`}
                />
                <text
                  x={i * slotWidth + slotWidth / 2}
                  y={plotHeight + 18}
                  textAnchor="middle"
                  fontSize={11}
                  fill={AXIS_TEXT}
                >
                  {point.period}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {hovered !== null && (
        <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs shadow-md">
          <div className="font-semibold text-foreground">{data[hovered].period}</div>
          <div className="text-muted-foreground">
            {(data[hovered].nrfi_rate * 100).toFixed(1)}% NRFI · {data[hovered].games} games
          </div>
        </div>
      )}
    </div>
  );
}
