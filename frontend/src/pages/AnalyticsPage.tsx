import { useEffect, useState, type ReactNode } from "react";
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
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="mb-5 text-lg font-bold tracking-tight text-foreground">{title}</div>
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
    <div className="mx-auto max-w-6xl px-4 py-10 md:px-6 md:py-12">
      <header className="mb-8">
        <span className="font-mono text-xs uppercase tracking-[0.2em] text-primary">
          Model Performance
        </span>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-balance md:text-4xl">
          Analytics
        </h1>
        <p className="mt-3 max-w-2xl text-pretty leading-relaxed text-muted-foreground">
          How the model behaves over time — its accuracy trend and league-wide NRFI
          frequency, straight from the predictions and box-score tables.
        </p>
      </header>

      {state.status === "loading" && (
        <p className="text-center text-muted-foreground">Loading…</p>
      )}

      {state.status === "error" && (
        <p className="rounded-lg bg-destructive/10 p-4 text-center text-sm text-destructive">
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
