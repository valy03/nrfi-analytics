import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  getAccuracyReport,
  getPredictionHistory,
} from "../api/client";
import type { AccuracyReport, PredictedLabel, PredictionHistoryItem } from "../api/types";
import { StatTile } from "../components/StatTile";
import { WinLossBadge } from "../components/WinLossBadge";

const PAGE_SIZE = 25;

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; items: PredictionHistoryItem[]; accuracy: AccuracyReport };

interface Filters {
  startDate: string;
  endDate: string;
  team: string;
  prediction: PredictedLabel | "ALL";
}

const DEFAULT_FILTERS: Filters = { startDate: "", endDate: "", team: "", prediction: "ALL" };

function formatPct(value: number | null): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

export function HistoryPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });
    setOffset(0);

    Promise.all([
      getPredictionHistory(
        {
          startDate: filters.startDate || undefined,
          endDate: filters.endDate || undefined,
          team: filters.team || undefined,
          limit: PAGE_SIZE,
          offset: 0,
        },
        controller.signal
      ),
      getAccuracyReport(undefined, controller.signal),
    ])
      .then(([items, accuracy]) => {
        setHasMore(items.length === PAGE_SIZE);
        setState({ status: "ready", items, accuracy });
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        const message = err instanceof ApiError ? err.message : "Could not reach the API";
        setState({ status: "error", message });
      });

    return () => controller.abort();
  }, [filters.startDate, filters.endDate, filters.team]);

  const loadMore = () => {
    if (state.status !== "ready") return;
    const nextOffset = offset + PAGE_SIZE;
    getPredictionHistory({
      startDate: filters.startDate || undefined,
      endDate: filters.endDate || undefined,
      team: filters.team || undefined,
      limit: PAGE_SIZE,
      offset: nextOffset,
    }).then((more) => {
      setOffset(nextOffset);
      setHasMore(more.length === PAGE_SIZE);
      setState((prev) =>
        prev.status === "ready" ? { ...prev, items: [...prev.items, ...more] } : prev
      );
    });
  };

  const visibleItems = useMemo(() => {
    if (state.status !== "ready") return [];
    if (filters.prediction === "ALL") return state.items;
    return state.items.filter((item) => item.predicted_label === filters.prediction);
  }, [state, filters.prediction]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Historical Results</h1>
        <p className="text-sm text-slate-500">
          Every prediction the model has made, graded against what actually happened.
        </p>
      </header>

      {state.status === "ready" && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatTile label="Overall Accuracy" value={formatPct(state.accuracy.overall.accuracy)} />
          <StatTile label="Win Rate" value={formatPct(state.accuracy.overall.win_rate)} />
          <StatTile
            label="Graded Predictions"
            value={state.accuracy.overall.total.toLocaleString()}
          />
          <StatTile label="ROI" value="—" />
        </div>
      )}

      <div className="mb-6 flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          From
          <input
            type="date"
            value={filters.startDate}
            onChange={(e) => setFilters({ ...filters, startDate: e.target.value })}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          To
          <input
            type="date"
            value={filters.endDate}
            onChange={(e) => setFilters({ ...filters, endDate: e.target.value })}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
          />
        </label>
        <input
          type="search"
          placeholder="Search teams…"
          value={filters.team}
          onChange={(e) => setFilters({ ...filters, team: e.target.value })}
          className="min-w-[140px] flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
        />
        <select
          value={filters.prediction}
          onChange={(e) =>
            setFilters({ ...filters, prediction: e.target.value as Filters["prediction"] })
          }
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
        >
          <option value="ALL">All predictions</option>
          <option value="NRFI">NRFI only</option>
          <option value="YRFI">YRFI only</option>
        </select>
      </div>

      {state.status === "loading" && <p className="text-center text-slate-400">Loading…</p>}

      {state.status === "error" && (
        <p className="rounded-lg bg-red-50 p-4 text-center text-sm text-red-600">
          {state.message}
        </p>
      )}

      {state.status === "ready" && visibleItems.length === 0 && (
        <p className="text-center text-slate-400">No predictions match the current filters.</p>
      )}

      {state.status === "ready" && visibleItems.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Game</th>
                <th className="px-4 py-2 font-medium">Prediction</th>
                <th className="px-4 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">Actual</th>
                <th className="px-4 py-2 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {visibleItems.map((item) => (
                <tr key={`${item.game_pk}-${item.model_version}`} className="border-b border-slate-50 last:border-0">
                  <td className="px-4 py-2 text-slate-600">{item.game_date}</td>
                  <td className="px-4 py-2 text-slate-900">
                    {item.away_team} @ {item.home_team}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{item.predicted_label}</td>
                  <td className="px-4 py-2 tabular-nums text-slate-600">
                    {(item.confidence * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-2 text-slate-600">{item.actual_label ?? "—"}</td>
                  <td className="px-4 py-2">
                    <WinLossBadge correct={item.correct} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {state.status === "ready" && hasMore && filters.prediction === "ALL" && (
        <div className="mt-4 text-center">
          <button
            onClick={loadMore}
            className="rounded-md border border-slate-300 px-4 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}
