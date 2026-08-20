import type { PredictedLabel } from "../api/types";

export interface Filters {
  search: string;
  prediction: PredictedLabel | "ALL";
  minConfidence: number; // 0-1
  sortByConfidence: boolean;
}

export const DEFAULT_FILTERS: Filters = {
  search: "",
  prediction: "ALL",
  minConfidence: 0,
  sortByConfidence: false,
};

interface FiltersBarProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function FiltersBar({ filters, onChange }: FiltersBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <input
        type="search"
        placeholder="Search teams…"
        value={filters.search}
        onChange={(e) => onChange({ ...filters, search: e.target.value })}
        className="min-w-[160px] flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
      />

      <select
        value={filters.prediction}
        onChange={(e) =>
          onChange({ ...filters, prediction: e.target.value as Filters["prediction"] })
        }
        className="rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
      >
        <option value="ALL">All predictions</option>
        <option value="NRFI">NRFI only</option>
        <option value="YRFI">YRFI only</option>
      </select>

      <label className="flex items-center gap-2 text-sm text-slate-600">
        Min confidence
        <input
          type="range"
          min={0}
          max={100}
          step={5}
          value={filters.minConfidence * 100}
          onChange={(e) =>
            onChange({ ...filters, minConfidence: Number(e.target.value) / 100 })
          }
          className="accent-teal-600"
        />
        <span className="w-10 text-right tabular-nums text-slate-500">
          {Math.round(filters.minConfidence * 100)}%
        </span>
      </label>

      <label className="flex items-center gap-2 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={filters.sortByConfidence}
          onChange={(e) => onChange({ ...filters, sortByConfidence: e.target.checked })}
          className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
        />
        Sort by confidence
      </label>
    </div>
  );
}
