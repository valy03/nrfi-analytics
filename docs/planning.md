# NRFI Analytics — planning.md

> Complete this document before writing any implementation code.
>
> This document defines the scope, architecture, and goals of the project.
> It serves as the blueprint for implementation and future AI-assisted development.
>
> Update this document whenever major architectural decisions change.

---

# Project Overview

## Project Name

NRFI Analytics

---

## Problem

Sports bettors and baseball fans often rely on scattered statistics when evaluating No Run First Inning (NRFI) bets.

Useful information such as:

- Starting pitcher performance
- Team first inning tendencies
- Weather
- Ballpark effects
- Historical trends
- Betting odds

is spread across multiple websites.

Most websites either provide statistics without context or provide predictions without explaining why.

---

## Solution

NRFI Analytics will automatically collect baseball statistics from multiple trusted data sources, generate machine learning predictions for every MLB game, and explain each prediction using transparent statistical evidence.

The application will provide:

- Daily NRFI predictions
- Confidence scores
- Statistical breakdowns
- Historical model performance
- Interactive analytics dashboard
- AI-generated explanations

The goal is to build a transparent sports analytics platform rather than simply another betting website.

---

# Project Goals

## Primary Goals

- Learn Machine Learning fundamentals
- Learn feature engineering
- Learn sports analytics
- Build an automated ETL pipeline
- Build an end-to-end ML application
- Improve backend architecture skills
- Deploy a production-ready application

---

## Secondary Goals

- Learn model evaluation
- Learn scheduled jobs
- Learn data engineering
- Learn experiment tracking
- Practice modern UI design

---

# Target Users

## User 1

Sports bettors looking for daily NRFI opportunities.

Needs:

- Confidence
- Transparency
- Historical performance

---

## User 2

Baseball fans interested in analytics.

Needs:

- Team statistics
- Pitcher comparisons
- Game insights

---

## User 3

Recruiters

Needs:

- Evidence of software engineering
- ML knowledge
- Data engineering
- Full-stack architecture

---

# MVP Features

## Dashboard

Today's Games

Top NRFI Picks

Confidence Scores

---

## Game Details

Starting Pitchers

Team Statistics

Historical Matchups

Weather

Vegas Odds

Prediction Explanation

---

## Historical Results

Past Predictions

Accuracy

Win Rate

ROI

---

## Analytics

Charts

Model Accuracy

Pitcher Leaderboards

Team Leaderboards

---

# Stretch Features

- User Accounts
- Favorite Teams
- Email Alerts
- Mobile Responsive Design
- Multiple Prediction Models
- Live Odds Tracking
- Model Comparison
- SHAP Feature Importance
- AI Chat Assistant

---

# Success Criteria

The MVP is complete when:

✓ Daily MLB games update automatically

✓ Predictions generate automatically

✓ Users can view today's predictions

✓ Historical predictions are stored

✓ Dashboard displays analytics

✓ Application is deployed

---

# Non Goals

The project will NOT:

- Guarantee profitable betting
- Replace professional handicappers
- Predict every betting market
- Support sports other than MLB (initially)

---

# Risks

## Technical Risks

- Data quality
- Missing APIs
- Model overfitting
- Limited historical data

---

## Product Risks

- Users misunderstanding confidence scores
- Data source downtime
- API rate limits

---

# High-Level Architecture

Data Sources

↓

Data Collection

↓

PostgreSQL Database

↓

Feature Engineering

↓

Machine Learning Model

↓

Prediction Service

↓

REST API

↓

React Dashboard

---

# Tech Stack (Tentative)

Frontend

- React
- TypeScript
- TailwindCSS

Backend

- FastAPI
- Python

Database

- PostgreSQL

Machine Learning

- pandas
- scikit-learn
- XGBoost

Deployment

- Docker
- Railway
- Vercel
