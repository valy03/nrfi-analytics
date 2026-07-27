# NRFI Analytics — requirements.md

> This document defines the functional and non-functional requirements for the application.
>
> It answers one question:
>
> "What should the application do?"
>
> This document intentionally avoids implementation details.

---

# Version

Current Version

MVP (v1.0)

---

# Application Goal

Provide users with transparent, data-driven No Run First Inning (NRFI) predictions for every MLB game using statistical analysis and machine learning.

The application should help users understand WHY a prediction was made rather than simply displaying a confidence score.

---

# User Personas

## Sports Bettor

Goals

- Find today's best NRFI opportunities
- Understand prediction confidence
- Compare games quickly
- Review historical model performance

---

## Baseball Fan

Goals

- Learn about pitcher matchups
- Compare team statistics
- Explore historical trends
- Learn baseball analytics

---

## Recruiter

Goals

- Evaluate engineering quality
- View architecture
- See machine learning integration
- Observe data engineering pipeline

---

# Functional Requirements

## Dashboard

The homepage shall display:

- Today's MLB games
- Home and away teams
- Team logos
- Starting pitchers
- Game time
- Prediction (NRFI / YRFI)
- Confidence score
- Expected probability
- Weather summary

Users shall be able to:

- Sort by confidence
- Search teams
- Filter by prediction
- Filter by confidence

---

## Game Details

Each game page shall display:

### General

- Teams
- Date
- Time
- Stadium
- Weather

---

### Starting Pitchers

- Name
- ERA
- WHIP
- FIP
- xERA
- Strikeout %
- Walk %
- Career NRFI %
- Season NRFI %
- Last 5 Starts

---

### Team Statistics

- First inning runs scored
- OPS
- OBP
- Slugging %
- Team batting average
- Home/Away splits

---

### Prediction

Display:

- NRFI Probability
- YRFI Probability
- Confidence Score

---

### Explanation

The application shall explain why the model made the prediction.

Example:

• Elite starting pitching

• Cold offenses

• Pitcher-friendly weather

• Strong historical trends

---

## Historical Results

Users shall be able to:

View

- Previous predictions
- Actual results
- Confidence
- Win/Loss
- Date

Statistics

- Overall accuracy
- Monthly accuracy
- Yearly accuracy
- ROI
- Win rate

---

## Analytics

Display charts for:

- Prediction accuracy over time
- NRFI frequency
- Pitcher leaderboard
- Team leaderboard
- Best model performance

---

# Machine Learning Requirements

The application shall:

- Generate one prediction per MLB game
- Store prediction probability
- Store confidence
- Store model version
- Store prediction timestamp

The application shall NOT:

- Retrain the model every request
- Predict live games

---

# Automation Requirements

The application shall automatically:

- Update today's MLB schedule
- Retrieve starting pitchers
- Retrieve statistics
- Generate predictions
- Store predictions

No manual intervention should be required.

---

# Performance Requirements

Dashboard should load in under 2 seconds.

Game pages should load in under 2 seconds.

Predictions should be generated before the first scheduled game.

---

# Non-Functional Requirements

The application should be:

- Responsive
- Easy to understand
- Mobile friendly
- Transparent
- Maintainable
- Well documented

---

# MVP Scope

Version 1 will include:

✓ Dashboard

✓ Game Details

✓ Prediction Engine

✓ Historical Results

✓ Analytics

✓ Automated Daily Updates

---

# Out of Scope

Version 1 will NOT include:

- User accounts
- Paid subscriptions
- Mobile application
- Live inning predictions
- Parlays
- Push notifications
- Community picks
- Social features

---

# Future Features

Version 2

- User accounts
- Favorite teams
- Email alerts
- Daily newsletters

Version 3

- Multiple prediction models
- SHAP feature importance
- Interactive AI assistant

Version 4

- Other betting markets
- Strikeout props
- Hits props
- Total runs
- Home run predictions
