import { useState } from "react";
import type { AccuracyBucket } from "../api/types";

const LINE_COLOR = "#0d9488"; // teal-600 — same sequential hue as NrfiFrequencyChart
const GRIDLINE = "#e1e0d9";
const AXIS_TEXT = "#898781";

const WIDTH = 640;
const HEIGHT = 220;
const MARGIN = { top: 16, right: 16, bottom: 28, left: 40 };
const HIT_RADIUS = 12; // >= 24px hit target per the dataviz skill's interaction spec

interface AccuracyOverTimeChartProps {
  monthly: AccuracyBucket[];
}

export function AccuracyOverTimeChart({ monthly }: AccuracyOverTimeChartProps) {
  const [hovered, setHovered] = useState<number | null>(null);

  const graded = monthly.filter((b) => b.accuracy != null);

  if (graded.length === 0) {
    return <p className="text-sm text-slate-400">No graded predictions yet.</p>;
  }

  // A trend needs at least two points to mean anything — one point is a
  // stat, not a line (dataviz skill: "single current value -> stat tile,
  // not a one-bar chart"). Show it as a single labeled dot instead of
  // stretching one value across an empty line chart.
  if (graded.length === 1) {
    const only = graded[0];
    return (
      <div className="flex items-baseline gap-3">
        <span className="text-3xl font-bold text-slate-900">
          {(only.accuracy! * 100).toFixed(1)}%
        </span>
        <span className="text-sm text-slate-500">
          {only.period} · {only.correct}/{only.total} correct
        </span>
      </div>
    );
  }

  const plotWidth = WIDTH - MARGIN.left - MARGIN.right;
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const yTicks = [0, 0.25, 0.5, 0.75, 1];

  const xFor = (i: number) => (i / (graded.length - 1)) * plotWidth;
  const yFor = (rate: number) => plotHeight - rate * plotHeight;

  const linePath = graded
    .map((b, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yFor(b.accuracy!)}`)
    .join(" ");

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="w-full"
        role="img"
        aria-label="Prediction accuracy by month"
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

          {/* A coin-flip reference line — the honest floor this model has to clear. */}
          <line
            x1={0}
            x2={plotWidth}
            y1={yFor(0.5)}
            y2={yFor(0.5)}
            stroke={AXIS_TEXT}
            strokeWidth={1}
            strokeDasharray="3 3"
          />

          <path d={linePath} fill="none" stroke={LINE_COLOR} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

          {graded.map((b, i) => (
            <g key={b.period}>
              <circle
                cx={xFor(i)}
                cy={yFor(b.accuracy!)}
                r={4}
                fill={LINE_COLOR}
                stroke="#fcfcfb"
                strokeWidth={2}
              />
              <circle
                cx={xFor(i)}
                cy={yFor(b.accuracy!)}
                r={HIT_RADIUS}
                fill="transparent"
                onPointerEnter={() => setHovered(i)}
                onPointerLeave={() => setHovered(null)}
                onFocus={() => setHovered(i)}
                onBlur={() => setHovered(null)}
                tabIndex={0}
                role="button"
                aria-label={`${b.period}: ${(b.accuracy! * 100).toFixed(1)}% accuracy over ${b.total} predictions`}
              />
              <text
                x={xFor(i)}
                y={plotHeight + 18}
                textAnchor="middle"
                fontSize={11}
                fill={AXIS_TEXT}
              >
                {b.period.slice(5)}
              </text>
            </g>
          ))}
        </g>
      </svg>

      {hovered !== null && (
        <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-md">
          <div className="font-semibold text-slate-900">{graded[hovered].period}</div>
          <div className="text-slate-500">
            {(graded[hovered].accuracy! * 100).toFixed(1)}% · {graded[hovered].correct}/
            {graded[hovered].total} correct
          </div>
        </div>
      )}
    </div>
  );
}
