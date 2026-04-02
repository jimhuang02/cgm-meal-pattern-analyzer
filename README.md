# CGM Meal Pattern Analyzer

## 1. Clinical Context

Postprandial (after-meal) glucose spikes are a primary driver of cardiovascular and microvascular complications in diabetes, yet standard A1c tests and most CGM summary screens obscure meal-level patterns entirely. The Ambulatory Glucose Profile (AGP) standardizes CGM reporting by collapsing multiple days of data onto a single 24-hour percentile chart, giving clinicians a compact view of glycemic variability. Current consumer CGM apps display raw glucose traces but do not isolate per-meal postprandial windows, compute meal-specific variability coefficients, or generate patient-friendly pattern interpretations.

## 2. What This System Does

Simulate 14 days of CGM data for a chosen patient profile and get a full AGP analysis with per-meal statistics, LLM-generated insights, and a clinician-grade dashboard — all in a single web app with zero local setup.

**Features:**
- Three patient profiles (well-controlled / moderate / poorly-controlled) with physiologically accurate simulation models
- Four configurable meal slots with adjustable pre/post windows
- Per-meal AGP percentile curves (P10–P90), peak glucose, time-to-peak, excursion, and CV%
- Stability classification: stable / variable / highly variable (ADA 2019 thresholds)
- Overall TIR / TAR / TBR, Glucose Management Indicator (GMI), and hypoglycemia event log
- AI-generated patient-facing pattern report (Claude Haiku) with concrete action suggestions
- Dual-view dashboard: patient card view + full clinician AGP chart

## 3. Architecture

```
Browser (Chart.js SPA)
        │
        │  HTTP/JSON
        ▼
┌───────────────────────────────────────┐
│           FastAPI (main.py)           │
│                                       │
│  POST /api/simulate                   │
│  GET  /api/analysis/{session_id}      │
│  POST /api/insight/{session_id}       │
│  GET  /health                         │
└──────────┬────────────────────────────┘
           │
     ┌─────▼──────┐     ┌─────────────────┐
     │ PostgreSQL  │     │  Anthropic API   │
     │ (SQLModel)  │     │  (Claude Haiku)  │
     │             │     │                 │
     │ sessions    │     │  LLM insight     │
     │ gl_readings │     │  generation      │
     │ meal_configs│     └─────────────────┘
     └─────────────┘
           │
     ┌─────▼──────────────┐
     │  Analysis Engine   │
     │  (app/analysis.py) │
     │                    │
     │  AGP percentiles   │
     │  Meal CV / peaks   │
     │  TIR / GMI / Hypo  │
     └────────────────────┘
```

## 4. API Reference

### POST /api/simulate
```json
// Request
{
  "patient_profile": "moderate",
  "meal_configs": [
    { "name": "Breakfast", "time": "07:30", "window_before_min": 30, "window_after_min": 150 },
    { "name": "Lunch",     "time": "12:30", "window_before_min": 30, "window_after_min": 150 },
    { "name": "Dinner",    "time": "19:00", "window_before_min": 30, "window_after_min": 150 },
    { "name": "Snack",     "time": "15:00", "window_before_min": 30, "window_after_min": 120 }
  ]
}

// Response
{ "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6" }
```

### GET /api/analysis/{session_id}
```json
// Response (abbreviated)
{
  "session_id": "...",
  "patient_profile": "moderate",
  "tir_percent": 68.4,
  "tar_percent": 24.1,
  "tbr_percent": 7.5,
  "gmi": 7.2,
  "mean_glucose": 163.0,
  "cv_percent": 34.8,
  "hypo_events": [
    { "start_time": "2025-01-03T02:10:00", "duration_minutes": 25, "min_glucose": 63.1 }
  ],
  "meal_analyses": [
    {
      "meal_name": "Breakfast", "meal_time": "07:30",
      "peak_glucose": 178.4, "time_to_peak_minutes": 65.0,
      "excursion_mg_dl": 83.2, "cv_percent": 38.5,
      "stability": "variable",
      "percentiles": { "minutes": [-30,...,150], "p10": [...], "p50": [...], ... }
    }
  ],
  "agp_24h": { "p10": [...288 values...], "p25": [...], "p50": [...], "p75": [...], "p90": [...] }
}
```

### POST /api/insight/{session_id}
```json
// Response
{
  "report": "Your glucose control over the past 14 days shows moderate variability, with 68% of readings in the healthy range and a Glucose Management Indicator of 7.2%..."
}
```

### GET /health
```json
{ "status": "ok", "db": "connected" }
```

## 5. Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

1. Fork this repository
2. Connect to Render and select **New → Blueprint** pointing at this repo
3. Render will auto-provision a PostgreSQL database and web service from `render.yaml`
4. Optionally set `ANTHROPIC_API_KEY` in the Render environment dashboard to enable AI insights (the app works without it in demo mode)

**Local development:**
```bash
pip install -r requirements.txt
# Optionally set DATABASE_URL; defaults to SQLite if unset
uvicorn main:app --reload
```
Open `http://localhost:8000`.
