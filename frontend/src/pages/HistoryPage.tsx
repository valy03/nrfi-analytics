import { useEffect, useMemo, useState } from "react";
import { ApiError, getAccuracyReport, getPredictionHistory } from "../api/client";
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
const PREDICTION_TABS: (PredictedLabel | "ALL")[] = ["ALL", "NRFI", "YRFI"];

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
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-6 md:py-10">
      <header className="mb-8">
        <span className="font-mono text-xs uppercase tracking-[0.2em] text-primary">
          Track Record
        </span>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-balance md:text-4xl">
          Historical Results
        </h1>
        <p className="mt-3 max-w-2xl text-pretty leading-relaxed text-muted-foreground">
          Every graded prediction, kept public and honest. We publish losses alongside wins —
          transparency only counts when it includes the misses.
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

      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-4">
        <div className="flex gap-1 rounded-lg bg-secondary p-1">
          {PREDICTION_TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setFilters({ ...filters, prediction: tab })}
              className={`rounded-md px-3 py-1 text-sm font-medium transition ${
                filters.prediction === tab
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab === "ALL" ? "All" : tab}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          From
          <input
            type="date"
            value={filters.startDate}
            onChange={(e) => setFilters({ ...filters, startDate: e.target.value })}
            className="rounded-md border border-border bg-card px-2 py-1 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          To
          <input
            type="date"
            value={filters.endDate}
            onChange={(e) => setFilters({ ...filters, endDate: e.target.value })}
            className="rounded-md border border-border bg-card px-2 py-1 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </label>
        <input
          type="search"
          placeholder="Search teams…"
          value={filters.team}
          onChange={(e) => setFilters({ ...filters, team: e.target.value })}
          className="min-w-[140px] flex-1 rounded-md border border-border bg-card px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>

      {state.status === "loading" && <p className="text-center text-muted-foreground">Loading…</p>}

      {state.status === "error" && (
        <p className="rounded-lg bg-destructive/10 p-4 text-center text-sm text-destructive">
          {state.message}
        </p>
      )}

      {state.status === "ready" && visibleItems.length === 0 && (
        <p className="text-center text-muted-foreground">
          No predictions match the current filters.
        </p>
      )}

      {state.status === "ready" && visibleItems.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
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
                <tr
                  key={`${item.game_pk}-${item.model_version}`}
                  className="border-b border-border last:border-0"
                >
                  <td className="px-4 py-2 font-mono text-muted-foreground">{item.game_date}</td>
                  <td className="px-4 py-2 font-medium text-foreground">
                    {item.away_team} @ {item.home_team}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{item.predicted_label}</td>
                  <td className="px-4 py-2 font-mono tabular-nums text-muted-foreground">
                    {(item.confidence * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{item.actual_label ?? "—"}</td>
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
            className="rounded-md border border-border px-4 py-1.5 text-sm text-muted-foreground hover:bg-secondary"
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}
