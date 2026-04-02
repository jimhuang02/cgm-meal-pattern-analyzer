# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (SQLite fallback — no PostgreSQL needed)
uvicorn main:app --reload

# Run with PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost/cgm_analyzer uvicorn main:app --reload

# Run with LLM insights enabled
ANTHROPIC_API_KEY=sk-ant-... uvicorn main:app --reload
```

No test runner is configured. The interactive frontend at `http://localhost:8000` is the primary way to exercise the full stack.

## Architecture

Single-repo FastAPI app. The frontend is a plain HTML/JS/CSS file at `static/index.html` served by FastAPI — no build step, no bundler.

```
main.py                  # App entry point: mounts routers, serves index.html, /health
app/
  constants.py           # ALL clinical thresholds as named constants with citation comments
  database.py            # SQLModel engine; auto-switches SQLite↔PostgreSQL via DATABASE_URL
  models.py              # SQLModel ORM: Session, GlucoseReading, MealConfig
  schemas.py             # Pydantic request/response schemas for all endpoints
  simulation.py          # CGM glucose trace generator (numpy-based, profile-aware)
  analysis.py            # AGP analysis engine: percentiles, TIR/TAR/TBR, GMI, hypo events
  llm.py                 # Anthropic API call + placeholder fallback
  routers/
    simulate.py          # POST /api/simulate
    analysis.py          # GET  /api/analysis/{session_id}
    insight.py           # POST /api/insight/{session_id}
static/index.html        # Full SPA: controls panel + patient/clinician tab views + Chart.js
```

## Key conventions

- **No magic numbers**: every clinical threshold lives in `app/constants.py` with an inline comment citing the source guideline. Add new thresholds there, not inline.
- **Database fallback**: `DATABASE_URL` defaults to `sqlite:///./cgm_analyzer.db`. The `postgres://` → `postgresql://` rewrite in `database.py` handles Render's connection string format.
- **LLM fallback**: `app/llm.py` generates a realistic placeholder report from the analysis data when `ANTHROPIC_API_KEY` is absent. The UI must never break without an API key.
- **Simulation seed**: seeded from `hash(session_id) % 2**31` so the same session always reproduces the same trace; different sessions produce different data.
- **Bulk insert**: `db.add_all(readings)` is used for the 4032 glucose readings — do not switch to individual `db.add()` calls in a loop.

## Clinical formula reference

| Metric | Formula | Source |
|--------|---------|--------|
| GMI    | `3.31 + 0.02392 × mean_glucose` | Bergenstal et al., Diabetes Care 2018 |
| CV stability | stable <36%, variable 36–50%, highly variable >50% | ADA/EASD 2019 consensus |
| TIR target | >70% readings 70–180 mg/dL | ADA Standards of Care 2023 |
| Hypo event | <70 mg/dL for ≥15 consecutive minutes | ADA Standards of Care 2023 §6 |

## Deployment

`render.yaml` defines a single web service + one free-tier PostgreSQL database. The `buildCommand` is `pip install -r requirements.txt`; the `startCommand` is `uvicorn main:app --host 0.0.0.0 --port $PORT`. Tables are created automatically on startup via `create_db_and_tables()`.
