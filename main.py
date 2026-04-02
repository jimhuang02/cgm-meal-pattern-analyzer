"""
CGM Meal Pattern Analyzer — FastAPI application entry point.

Serves:
  - Single-page frontend at /
  - REST API under /api/
  - Health check at /health
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import text

from app.database import create_db_and_tables, engine, get_session
from app.routers import simulate, analysis, insight
from app.schemas import HealthResponse

app = FastAPI(
    title="CGM Meal Pattern Analyzer",
    description="Clinical CGM data analysis with AGP metrics and LLM insights",
    version="1.0.0",
)

# ── Static files ─────────────────────────────────────────────────────────────
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ── Startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


# ── API routers ───────────────────────────────────────────────────────────────
app.include_router(simulate.router, prefix="/api", tags=["simulation"])
app.include_router(analysis.router, prefix="/api", tags=["analysis"])
app.include_router(insight.router, prefix="/api", tags=["insight"])


# ── Frontend ──────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def serve_frontend() -> FileResponse:
    return FileResponse(str(_STATIC_DIR / "index.html"))


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> JSONResponse:
    """Return application and database status."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        db_status = f"error: {exc}"

    return JSONResponse({"status": "ok", "db": db_status})
