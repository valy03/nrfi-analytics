import type { ReactNode } from "react";

interface SectionProps {
  title: string;
  children: ReactNode;
}

function Section({ title, children }: SectionProps) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold text-slate-900">{title}</h2>
      <div className="space-y-3 text-sm leading-relaxed text-slate-600">{children}</div>
    </section>
  );
}

export function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">About NRFI Analytics</h1>
        <p className="mt-1 text-sm text-slate-500">
          How this project works, end to end — data collection through a model in
          production.
        </p>
      </header>

      <Section title="Project Overview">
        <p>
          NRFI Analytics predicts MLB's "No Run First Inning" market: will either team
          score in the first inning? The goal isn't just a probability — it's showing{" "}
          <em>why</em> the model landed where it did, so a prediction is something you
          can evaluate, not just trust.
        </p>
      </Section>

      <Section title="How Predictions Work">
        <p>
          Each morning, before the day's first pitch, the app pulls the MLB schedule
          and confirmed starting pitchers, computes a 32-feature snapshot for each
          matchup (pitcher and team first-inning rates, ballpark tendencies, recent
          form), and scores it with a trained model. The output is an NRFI/YRFI call,
          a confidence score, and a short rule-based explanation naming the factors
          that moved the prediction most.
        </p>
        <p>
          A game only gets predicted once both starters are announced and before it
          starts — the app never predicts a live or finished game.
        </p>
      </Section>

      <Section title="Technology Stack">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Backend:</strong> Python, FastAPI, SQLAlchemy, PostgreSQL, Alembic
          </li>
          <li>
            <strong>Machine learning:</strong> scikit-learn (Logistic Regression),
            XGBoost (evaluated candidate)
          </li>
          <li>
            <strong>Frontend:</strong> React, TypeScript, Tailwind CSS, Vite
          </li>
          <li>
            <strong>Infrastructure:</strong> Docker Compose (local dev)
          </li>
        </ul>
      </Section>

      <Section title="Machine Learning Pipeline">
        <p>
          A season-based Logistic Regression baseline was trained on 2018-2023
          (13,047 games) and evaluated on 2024-2026 (4,886 held-out games) — seasons
          the model never saw during training. An XGBoost candidate was trained on the
          identical split and features for a genuine head-to-head comparison.
        </p>
        <p>
          <strong>XGBoost lost</strong> on held-out ROC AUC (0.506 vs. 0.515) and
          Logistic Regression remains the production model — chosen on the numbers,
          not because a simpler algorithm was assumed better. The two models mostly
          agree on which features matter (pitcher first-inning rate stats dominate
          both); they just disagree on how to combine them, and the simpler
          combination generalized better here.
        </p>
        <p>
          The honest headline number: <strong>51.9% accuracy</strong>, ROC AUC{" "}
          <strong>0.515</strong> on held-out data — a real edge over the 48.4%
          majority-class baseline, but a modest one. First-inning scoring is close to
          a coin flip; a pitcher's career first-inning NRFI rate has a measured talent
          standard deviation of just 0.034 against a league mean of 0.712, meaning
          most of the spread between pitchers is noise, not skill. That ceiling is a
          property of the sport, not a shortcut taken in the model.
        </p>
      </Section>

      <Section title="Data Sources">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>MLB Stats API</strong> — daily schedule, probable pitchers, final
            scores
          </li>
          <li>
            <strong>Baseball Savant / Statcast</strong> (via pybaseball) — pitch-level
            historical data back to 2018, the source for every model feature
          </li>
          <li>
            <strong>OpenWeather</strong> — game-time conditions, display-only
          </li>
          <li>
            <strong>The Odds API</strong> — moneyline odds, display-only context, not
            a model input
          </li>
        </ul>
      </Section>

      <Section title="Disclaimer">
        <p>
          Built for educational and informational purposes. Nothing here is betting
          advice, and no prediction is a guarantee — first-inning scoring genuinely is
          close to a coin flip, and this project says so plainly rather than
          overselling a 51.9%-accuracy model.
        </p>
      </Section>

      <Section title="GitHub Repository">
        <p>
          <a
            href="https://github.com/valy03/nrfi-analytics"
            target="_blank"
            rel="noopener noreferrer"
            className="text-teal-600 hover:text-teal-700"
          >
            github.com/valy03/nrfi-analytics
          </a>
        </p>
      </Section>
    </div>
  );
}
