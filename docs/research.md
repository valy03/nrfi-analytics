# NRFI Analytics — research.md

> This document collects research related to baseball analytics, machine learning,
> and available datasets before implementation begins.
>
> The purpose is to understand the problem before building a solution.

---

# Research Questions

This document aims to answer the following questions:

1. What factors influence NRFI outcomes?
2. Which baseball statistics are most predictive?
3. What historical data is available?
4. Which APIs should the application use?
5. What machine learning approach should we start with?
6. What metrics should be used to evaluate the model?

---

# What is an NRFI?

## Definition

NRFI stands for **No Run First Inning**.

A game is considered an NRFI if:

- Neither team scores during the first inning.

Otherwise, it is considered a YRFI (Yes Run First Inning).

---

# Why Predict NRFI?

The first inning is unique because:

- Only the top of each batting order appears.
- Starting pitchers are fresh.
- Bullpens are irrelevant.
- Defensive substitutions rarely occur.

This makes NRFI prediction different from predicting the outcome of an entire baseball game.

---

# Initial Hypothesis

The following factors may significantly influence NRFI probability.

## Pitching

- Starting pitcher quality
- First inning ERA
- WHIP
- Strikeout rate
- Walk rate
- Home/Away splits
- Career NRFI%
- Recent form

---

## Team Offense

- First inning runs scored
- OPS
- OBP
- Slugging
- Strikeout %
- Walk %
- Hot streak

---

## Ballpark

- Park factor
- Home run factor
- Run factor

---

## Weather

- Temperature
- Wind direction
- Wind speed
- Humidity

---

## Betting Market

- Vegas Total
- Moneyline
- Implied Probability

---

## Other

- Umpire tendencies
- Rest days
- Travel
- Lineup strength

---

# Data Source Decisions

> Status: **Decided** (as of 2026-07-24). Superseded the "Candidate Data Sources"
> exploration below — kept for historical context.

## Baseball Data — DECIDED

**Primary: Baseball Savant / Statcast, via the `pybaseball` package**

- Pitch-level data, pulled from baseballsavant.com, includes `inning` and
  `inning_topbot` columns — meaning NRFI/YRFI ground truth can be derived
  directly from pitch-by-pitch data rather than approximated.
- Historical coverage back to the 2008 season (some features, like launch
  angle, only from 2015 onward).
- Free, no API key required.
- This will be the primary source for **historical training data** and for
  computing true first-inning-only splits for pitchers and teams (something
  season-level stats can't give us directly).

**Secondary: MLB Stats API (`statsapi.mlb.com`)**

- Free, public, no API key required.
- Used for the operational/daily side: today's schedule, confirmed starting
  pitchers, boxscores, standard season stats.
- Mature Python wrapper available (`MLB-StatsAPI`) if we don't want to hit
  raw endpoints ourselves.
- This will drive the **daily automation pipeline** (schedule → pitcher
  confirmation → prediction generation).

**Rejected for now:** FanGraphs, Baseball Reference — both require scraping
(no clean free API) and Statcast + MLB Stats API already cover what we need
for MVP. May revisit for advanced metrics (wRC+, park-adjusted stats) later.

---

## Weather — DECIDED

**OpenWeather (free tier)**

- Free tier (~1,000 calls/day) is more than sufficient for once-daily
  game-day pulls across an MLB slate (~15 games/day max).
- No further research needed; not a blocker.

---

## Betting Odds — DECIDED (display-only, non-blocking)

**The Odds API (free tier)**

- Free tier: NBA + MLB only, moneyline (h2h) markets only, no historical
  odds. (Originally noted here as 25 requests/day — M8.5 signed up for a
  real key and the actual quota is 500 requests, confirmed via the
  `x-requests-remaining` response header. Doesn't change the decision
  below either way.)
- **Decision:** odds will be **display-only context** on the game details
  page, not a model input. This avoids depending on a rate-limited free
  tier for anything the ML pipeline needs to function, and avoids paying
  for historical odds data we don't strictly need for MVP.
- One daily pull of today's moneylines — the whole slate in a single
  request (`app.collection.odds`) — is well within the quota regardless.
- Revisit as a paid/model-input feature only if odds prove meaningfully
  predictive and the project justifies the cost (Version 3+ territory).

---

# Candidate Data Sources (historical — see Decisions above)

## Baseball Data

Status: Resolved — see Data Source Decisions

Possible APIs considered:

- MLB Stats API ✓ (selected — operational data)
- Baseball Savant / Statcast ✓ (selected — historical training data)
- FanGraphs (rejected — scraping required)
- Baseball Reference (rejected — scraping required)

---

## Weather

Status: Resolved — see Data Source Decisions

- OpenWeather ✓ (selected)
- WeatherAPI (not needed)

---

## Betting Odds

Status: Resolved — see Data Source Decisions

- The Odds API ✓ (selected — free tier, display-only)

---

# Potential Features

## Pitcher Features

Possible metrics:

- ERA
- FIP
- xERA
- WHIP
- BABIP
- K%
- BB%
- Hard Hit %
- Barrel %
- First inning ERA (derivable from Statcast `inning` field)

---

## Team Features

Possible metrics:

- Team OPS
- Team OBP
- Team SLG
- Team wRC+ (would require FanGraphs if pursued later)
- First inning scoring % (derivable from Statcast `inning` field)

---

## Environment Features

- Stadium
- Roof Open?
- Wind
- Temperature
- Humidity

---

# Machine Learning Models

Candidates:

- Logistic Regression
- Random Forest
- XGBoost
- LightGBM

No decision has been made. (Still open — reasonable to defer until a
baseline dataset exists; recommend starting with Logistic Regression as an
interpretable baseline before moving to XGBoost.)

---

# Evaluation Metrics

Potential metrics:

- Accuracy
- Precision
- Recall
- F1 Score
- ROC AUC
- Log Loss

---

# Unknowns

- ~~Which APIs provide historical data?~~ Resolved — Statcast (via
  `pybaseball`) for historical, MLB Stats API for daily/operational.
- ~~Which APIs have rate limits?~~ Resolved — MLB Stats API and Statcast
  have no hard published limits for reasonable use; The Odds API free tier
  is 25 req/day (odds are display-only, so this is not a pipeline blocker).
- ~~Should historical betting odds be stored?~~ Resolved — no, not for
  MVP. Odds are fetched daily for display only.
- **Still open:** Which statistics are actually predictive? — this can only
  be answered empirically once a baseline dataset and model exist (feature
  importance / SHAP analysis after first training run).
- **Still open:** How much historical data is enough? — Statcast goes back
  to 2008, but recommend starting with a smaller recent window (e.g.
  2018–present) to avoid stale-era effects (rule changes, juiced-ball
  seasons, etc.) and expanding if the model needs more data.

---

# Research Log

| Date | Question | Finding | Decision |
|------|----------|---------|----------|
| 2026-07-24 | Which baseball data API should we use? | MLB Stats API is free/public for schedules & operational data; Statcast (via `pybaseball`) provides pitch-level data with inning info back to 2008, letting us derive NRFI ground truth directly. | Use MLB Stats API for daily automation, Statcast/`pybaseball` for historical training data. |
| 2026-07-24 | Is betting odds data affordable and worth using as a model input? | The Odds API free tier is capped at 25 req/day, MLB-only, moneyline-only, no historical odds. | Use odds as display-only context, not a model feature, for MVP. |
| 2026-07-24 | Is weather data a blocker? | OpenWeather free tier (~1,000 calls/day) easily covers a daily MLB slate. | No further research needed; proceed with OpenWeather free tier. |
