# NRFI Analytics — wireframes.md

> This document defines the layout and functionality of every page in the
> application before any frontend development begins.
>
> It answers: "If someone visited the website today, what would they see?"

---

# Architecture Decision: Homepage Question

> **Decided 2026-07-26.** This supersedes the earlier draft of this
> document, which treated the dashboard as "Today's Games" with picks as
> one section among several.

The homepage should not answer "what games are happening today." It should
answer:

**"What are today's best NRFI opportunities?"**

**Why this matters:**

- A generic games list makes the user do the work of finding the signal
  (scanning confidence scores across everything). Leading with picks does
  that work for them — which is the actual value proposition from
  planning.md ("explain why, not just display a score").
- It matches the primary persona: the sports bettor wants "today's best
  opportunities" first (requirements.md, Sports Bettor goals), not a
  full slate they have to sort through themselves.
- It doesn't remove information — the full game list still exists on the
  same page, immediately below. Nothing from requirements.md's dashboard
  spec is cut. It's a re-ordering of priority, not a scope change.

**Consequence for layout:** Top Picks moves from a mid-page section (as in
the original draft) to the top of the page, directly under the header —
before summary cards, before the full games list. The full "All Today's
Games" list becomes the secondary, complete view for users who want to
browse rather than be told.

This is the one architectural decision worth calling out explicitly in
this doc; everything else below is layout detail.

---

# Design Philosophy

The application should feel like a professional analytics platform, not a
gambling website.

Principles:

- Clean
- Data-first
- Transparent
- Fast
- Mobile-friendly
- Easy to understand

---

# Navigation

```
----------------------------------------------------
NRFI Analytics     Dashboard   History   Analytics   About
----------------------------------------------------
```

---

# Page 1 — Dashboard

**Purpose:** Answer "what are today's best NRFI opportunities?" in the
first section a user sees, then let them browse the full slate if they
want more.

```
----------------------------------------------------
HEADER
NRFI Analytics · Today's Date · Last Updated [timestamp]
----------------------------------------------------
TODAY'S BEST NRFI OPPORTUNITIES          <- first thing on the page
Rank | Game | Confidence | Fair Odds | Prediction
(top 3-5 picks, ranked by confidence, one-line reason per pick)
----------------------------------------------------
SUMMARY CARDS
Games Today | Model Accuracy | Season Record | ROI
----------------------------------------------------
ALL TODAY'S GAMES
Away @ Home | Starting Pitchers | Game Time | Prediction
| Confidence | Weather | [Quick View]
----------------------------------------------------
Filters (apply to the "All Today's Games" list)
Search Team · Minimum Confidence · NRFI / YRFI · Sort By
  - Confidence
  - Game Time
  - Odds
----------------------------------------------------
```

**Notes:**

- Top Picks section answers the headline question and needs no filters —
  it's already the distilled answer. Filters belong to the full list
  below, where browsing (not distillation) is the point.
- Summary cards move below Top Picks, not above — they're context
  ("how's the model doing overall"), not the answer to the homepage
  question, so they shouldn't compete with it for the top slot.
- Unconfirmed-pitcher games (from planning.md risk: "missing APIs" /
  starting pitchers not yet announced) should not appear in Top Picks —
  a pick needs a real prediction behind it. They can still appear,
  grayed out, in "All Today's Games."

---

# Page 2 — Game Details

**Purpose:** Display every statistic used to make the prediction.

```
----------------------------------------------------
Game Header
Away @ Home · Date · Time · Prediction · Confidence
----------------------------------------------------
Prediction Card
NRFI Probability · YRFI Probability · Confidence · Recommended Pick
----------------------------------------------------
Explanation
"The model favors an NRFI because:"
  • Both starting pitchers rank highly in first-inning performance.
  • Weather conditions reduce expected offense.
  • Both teams score below league average in the first inning.
----------------------------------------------------
Starting Pitchers
Away Pitcher                    Home Pitcher
ERA, WHIP, FIP, xERA            (same stats)
Career NRFI%, Season NRFI%
Last 5 Starts
----------------------------------------------------
Team Comparison
Away: OPS, OBP, SLG, 1st Inning Runs
Home: OPS, OBP, SLG, 1st Inning Runs
----------------------------------------------------
Weather
Temperature · Wind · Humidity · Roof Open?
----------------------------------------------------
Vegas Odds
Moneyline · Game Total · NRFI Odds · YRFI Odds
----------------------------------------------------
```

**Note:** Prediction + explanation stay above the raw stats (as in the
earlier draft) — lead with the "so what," back it up after. Consistent
with the dashboard's lead-with-the-answer pattern above.

---

# Page 3 — Historical Results

**Purpose:** Let users verify the model is honest and track long-term
performance.

```
----------------------------------------------------
Table
Date | Game | Prediction | Confidence | Actual Result | Win/Loss
----------------------------------------------------
Summary
Overall Record · Monthly Record · ROI · Accuracy · Avg Confidence
----------------------------------------------------
Filters
Season · Team · Prediction Type · Date Range
----------------------------------------------------
```

---

# Page 4 — Analytics

**Purpose:** Deeper insight into historical data and model performance.

```
----------------------------------------------------
Charts
Prediction Accuracy (over time) · Monthly Accuracy
NRFI Frequency · Prediction Distribution
----------------------------------------------------
Leaderboards
Best Pitchers · Worst Pitchers
Best Teams · Worst Teams
Highest Confidence Picks
----------------------------------------------------
Model Metrics
Accuracy · Precision · Recall · ROC AUC · Log Loss
----------------------------------------------------
```

---

# Page 5 — About

**Purpose:** Explain how the project works. This page exists as much for
the Recruiter persona as for users — requirements.md lists "evaluate
engineering quality" and "see machine learning integration" as explicit
Recruiter goals, and this is the page that satisfies them directly.

Sections:

- Project Overview
- How Predictions Work
- Technology Stack
- Machine Learning Pipeline
- Data Sources
- Disclaimer
- GitHub Repository

---

# Mobile Layout

```
Header
  ↓
Today's Best NRFI Opportunities   <- still first on mobile
  ↓
Summary Cards
  ↓
All Today's Games
  ↓
Bottom Navigation
```

Mobile ordering mirrors desktop: the headline question stays first
regardless of screen size. Filters for "All Today's Games" collapse into
a single "Filter" button that opens a sheet, rather than inline controls,
to keep the mobile page scannable.

---

# Color Palette

| Role | Color |
|------|-------|
| Background | White / dark gray |
| Primary | Blue |
| Positive | Green |
| Negative | Red |
| Neutral | Gray |

---

# Icons

Using outline icon set (Tabler) rather than emoji, for a professional-
analytics feel rather than a casual/consumer one (per Design Philosophy
above — "clean," "professional analytics platform").

| Concept | Icon |
|---------|------|
| Dashboard | `ti-chart-bar` |
| Games | `ti-ball-baseball` |
| Analytics | `ti-chart-line` |
| History | `ti-calendar` |
| Prediction | `ti-bulb` |
| Weather | `ti-sun` |

---

# MVP Screens

Version 1:

- ✓ Dashboard (Top Picks first)
- ✓ Game Details
- ✓ Historical Results
- ✓ Analytics
- ✓ About

---

# Future Screens

Version 2:

- User Login
- Favorites
- Saved Picks
- Email Alerts

Version 3:

- Model Comparison
- AI Chat
- Player Pages
- Team Pages
