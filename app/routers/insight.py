"""POST /api/insight/{session_id} — generate LLM pattern report."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Session as DbSession, GlucoseReading, MealConfig
from app.schemas import InsightResponse
from app.analysis import build_analysis_response
from app.llm import generate_insight

router = APIRouter()


@router.post("/insight/{session_id}", response_model=InsightResponse)
def get_insight(
    session_id: str,
    db: Session = Depends(get_session),
) -> InsightResponse:
    """
    Generate a patient-facing LLM report for the given session.

    Re-runs the analysis to build the prompt, then calls the Anthropic API
    (or returns a placeholder if no API key is configured).
    """
    db_session = db.get(DbSession, session_id)
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if db_session.status != "complete":
        raise HTTPException(status_code=400, detail="Simulation not yet complete.")

    readings = db.exec(
        select(GlucoseReading)
        .where(GlucoseReading.session_id == session_id)
        .order_by(GlucoseReading.timestamp)
    ).all()

    meal_configs = db.exec(
        select(MealConfig).where(MealConfig.session_id == session_id)
    ).all()

    analysis = build_analysis_response(
        session_id=session_id,
        patient_profile=db_session.patient_profile,
        readings=list(readings),
        meal_configs=list(meal_configs),
    )

    return generate_insight(analysis)
