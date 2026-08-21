import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  getAccuracyReport,
  getPitcherLeaderboard,
  getTeamLeaderboard,
  getNrfiFrequency,
} from "../api/client";
import type {
  AccuracyReport,
  NrfiFrequencyPoint,
  PitcherLeaderboardEntry,
  TeamLeaderboardEntry,
} from "../api/types";
import { AccuracyOverTimeChart } from "../components/AccuracyOverTimeChart";
import { Leaderboard } from "../components/Leaderboard";
import { NrfiFrequencyChart } from "../components/NrfiFrequencyChart";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "ready";
      accuracy: AccuracyReport;
      nrfiFrequency: NrfiFrequencyPoint[];
      pitchers: PitcherLeaderboardEntry[];
      teams: TeamLeaderboardEntry[];
    };

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
        {title}
      </div>
      {children}
    </div>
  );
}

export function AnalyticsPage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });

    Promise.all([
      getAccuracyReport(undefined, controller.signal),
      getNrfiFrequency(controller.signal),
      getPitcherLeaderboard(controller.signal),
      getTeamLeaderboard(controller.signal),
    ])
      .then(([accuracy, nrfiFrequency, pitchers, teams]) =>
        setState({ status: "ready", accuracy, nrfiFrequency, pitchers, teams })
      )
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        const message = err instanceof ApiError ? err.message : "Could not reach the API";
        setState({ status: "error", message });
      });

    return () => controller.abort();
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <Link to="/" className="mb-6 inline-block text-sm text-teal-600 hover:text-teal-700">
        ← Back to today's games
      </Link>

      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>
        <p className="text-sm text-slate-500">
          Prediction accuracy over time and league-wide NRFI trends, straight from the
          predictions and box-score tables.
        </p>
      </header>

      {state.status === "loading" && <p className="text-center text-slate-400">Loading…</p>}

      {state.status === "error" && (
        <p className="rounded-lg bg-red-50 p-4 text-center text-sm text-red-600">
          {state.message}
        </p>
      )}

      {state.status === "ready" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <Card title="Prediction Accuracy Over Time">
              <AccuracyOverTimeChart monthly={state.accuracy.monthly} />
            </Card>
            <Card title="NRFI Frequency by Season">
              <NrfiFrequencyChart data={state.nrfiFrequency} />
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <Card title="Pitcher Leaderboard — First-Inning NRFI Rate">
              <Leaderboard
                valueColumnLabel="NRFI Rate"
                rows={state.pitchers.map((p) => ({
                  key: p.pitcher_id,
                  label: p.full_name,
                  secondaryLabel: `${p.starts} starts · ${p.runs_1st_avg.toFixed(2)} runs/1st`,
                  value: p.nrfi_rate,
                  valueLabel: `${(p.nrfi_rate * 100).toFixed(0)}%`,
                }))}
              />
            </Card>
            <Card title="Team Leaderboard — Quietest First Innings">
              <Leaderboard
                valueColumnLabel="Scored in 1st"
                rows={state.teams.map((t) => ({
                  key: t.team_id,
                  label: t.abbreviation,
                  secondaryLabel: `${t.games.toLocaleString()} games`,
                  // Inverted so the quietest offense (best for NRFI) still
                  // reads as the longest bar, matching the ranking order.
                  value: 1 - t.scored_1st_rate,
                  valueLabel: `${(t.scored_1st_rate * 100).toFixed(0)}%`,
                }))}
              />
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
