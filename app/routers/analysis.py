"""GET /api/analysis/{session_id} — return full AGP analysis for a session."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Session as DbSession, GlucoseReading, MealConfig
from app.schemas import AnalysisResponse
from app.analysis import build_analysis_response

router = APIRouter()


@router.get("/analysis/{session_id}", response_model=AnalysisResponse)
def get_analysis(
    session_id: str,
    db: Session = Depends(get_session),
) -> AnalysisResponse:
    """
    Compute and return all AGP metrics for the given session.

    Fetches raw glucose readings and meal configs from the database,
    runs the full analysis pipeline, and returns structured JSON.
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

    if not readings:
        raise HTTPException(status_code=404, detail="No readings found for this session.")

    return build_analysis_response(
        session_id=session_id,
        patient_profile=db_session.patient_profile,
        readings=list(readings),
        meal_configs=list(meal_configs),
    )
