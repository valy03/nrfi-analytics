import { Cloud, Database, DollarSign, LineChart } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface SectionProps {
  title: string;
  children: ReactNode;
}

function Section({ title, children }: SectionProps) {
  return (
    <section>
      <h2 className="text-2xl font-bold tracking-tight">{title}</h2>
      <div className="mt-3 space-y-3 leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

const PIPELINE_STEPS = [
  {
    n: "01",
    title: "Collect",
    body: "Pull the day's MLB schedule and confirmed starting pitchers each morning, before first pitch.",
  },
  {
    n: "02",
    title: "Compute",
    body: "Build a 32-feature snapshot per matchup — pitcher and team first-inning rates, ballpark tendencies, recent form — using only data strictly before the game.",
  },
  {
    n: "03",
    title: "Score",
    body: "Run the trained Logistic Regression model to get an NRFI/YRFI call and a confidence score.",
  },
  {
    n: "04",
    title: "Explain",
    body: "Generate a rule-based explanation naming the factors that moved the prediction most — published alongside every call, not just the number.",
  },
];

const DATA_SOURCES = [
  {
    icon: Database,
    title: "MLB Stats API",
    body: "Daily schedule, probable pitchers, and final scores.",
  },
  {
    icon: LineChart,
    title: "Baseball Savant / Statcast",
    body: "Pitch-level historical data back to 2018, via pybaseball — the source for every model feature.",
  },
  {
    icon: Cloud,
    title: "OpenWeather",
    body: "Game-time conditions, display-only.",
  },
  {
    icon: DollarSign,
    title: "The Odds API",
    body: "Moneyline odds, display-only context — not a model input.",
  },
];

export function AboutPage() {
  return (
    <div>
      <section className="bg-chalk border-b border-border">
        <div className="mx-auto max-w-3xl px-4 py-14 text-center md:px-6 md:py-20">
          <span className="font-mono text-xs uppercase tracking-[0.2em] text-primary">
            Our Approach
          </span>
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-balance md:text-5xl">
            Predictions you can actually check.
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-pretty leading-relaxed text-muted-foreground">
            NRFI Analytics predicts MLB's "No Run First Inning" market — will either team
            score in the first inning? The goal isn't just a probability; it's showing why
            the model landed where it did, so a prediction is something you can evaluate,
            not just trust.
          </p>
        </div>
      </section>

      <div className="mx-auto max-w-3xl space-y-14 px-4 py-12 md:px-6 md:py-16">
        <Section title="How Predictions Work">
          <p>
            A game only gets predicted once both starters are announced and before it
            starts — the app never predicts a live or finished game.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {PIPELINE_STEPS.map((step) => (
              <div key={step.n} className="rounded-xl border border-border bg-card p-5">
                <span className="font-mono text-sm font-bold text-primary">{step.n}</span>
                <h3 className="mt-2 font-semibold text-foreground">{step.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {step.body}
                </p>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Technology Stack">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              <strong className="text-foreground">Backend:</strong> Python, FastAPI,
              SQLAlchemy, PostgreSQL, Alembic
            </li>
            <li>
              <strong className="text-foreground">Machine learning:</strong> scikit-learn
              (Logistic Regression), XGBoost (evaluated candidate)
            </li>
            <li>
              <strong className="text-foreground">Frontend:</strong> React, TypeScript,
              Tailwind CSS, Vite
            </li>
            <li>
              <strong className="text-foreground">Infrastructure:</strong> Docker Compose
              (local dev)
            </li>
          </ul>
        </Section>

        <Section title="Machine Learning Pipeline">
          <p>
            A season-based Logistic Regression baseline was trained on 2018-2023 (13,047
            games) and evaluated on 2024-2026 (4,886 held-out games) — seasons the model
            never saw during training. An XGBoost candidate was trained on the identical
            split and features for a genuine head-to-head comparison.
          </p>
          <p>
            <strong className="text-foreground">XGBoost lost</strong> on held-out ROC AUC
            (0.506 vs. 0.515) and Logistic Regression remains the production model —
            chosen on the numbers, not because a simpler algorithm was assumed better. The
            two models mostly agree on which features matter (pitcher first-inning rate
            stats dominate both); they just disagree on how to combine them, and the
            simpler combination generalized better here.
          </p>
          <p>
            The honest headline number:{" "}
            <strong className="text-foreground">51.9% accuracy</strong>, ROC AUC{" "}
            <strong className="text-foreground">0.515</strong> on held-out data — a real
            edge over the 48.4% majority-class baseline, but a modest one. First-inning
            scoring is close to a coin flip; a pitcher's career first-inning NRFI rate has
            a measured talent standard deviation of just 0.034 against a league mean of
            0.712, meaning most of the spread between pitchers is noise, not skill. That
            ceiling is a property of the sport, not a shortcut taken in the model.
          </p>
        </Section>

        <Section title="Data Sources">
          <div className="divide-y divide-border rounded-xl border border-border bg-card">
            {DATA_SOURCES.map((source) => (
              <div key={source.title} className="flex gap-4 p-5">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <source.icon className="size-5" aria-hidden="true" />
                </span>
                <div>
                  <h3 className="font-semibold text-foreground">{source.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {source.body}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Section>

        <section className="rounded-2xl border border-primary/20 bg-primary/[0.04] p-6 md:p-8">
          <h2 className="text-xl font-bold tracking-tight">Disclaimer</h2>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            Built for educational and informational purposes. Nothing here is betting
            advice, and no prediction is a guarantee — first-inning scoring genuinely is
            close to a coin flip, and this project says so plainly rather than overselling
            a 51.9%-accuracy model.
          </p>
          <Link
            to="/"
            className="mt-6 inline-flex rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            See today's picks
          </Link>
        </section>

        <p className="text-center text-xs leading-relaxed text-muted-foreground">
          <a
            href="https://github.com/valy03/nrfi-analytics"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            github.com/valy03/nrfi-analytics
          </a>
        </p>
      </div>
    </div>
  );
}
