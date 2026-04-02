"""POST /api/simulate — run glucose simulation and persist to database."""

from datetime import time as dtime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.models import Session as DbSession, GlucoseReading, MealConfig
from app.schemas import SimulateRequest, SimulateResponse
from app.simulation import simulate_glucose
from app.constants import PROFILE_PARAMS

router = APIRouter()


@router.post("/simulate", response_model=SimulateResponse)
def run_simulation(
    body: SimulateRequest,
    db: Session = Depends(get_session),
) -> SimulateResponse:
    """
    Simulate 14 days of CGM data for the given patient profile and meal schedule.

    Stores all 4032 glucose readings and the meal configuration in the database.
    Returns a session_id used to retrieve analysis results.
    """
    if body.patient_profile not in PROFILE_PARAMS:
        raise HTTPException(status_code=422, detail="Unknown patient_profile.")

    if not (1 <= len(body.meal_configs) <= 8):
        raise HTTPException(status_code=422, detail="Provide 1–8 meal configurations.")

    # Create session record
    db_session = DbSession(patient_profile=body.patient_profile, status="pending")
    db.add(db_session)
    db.flush()  # Populate db_session.id before FK inserts

    # Persist meal configs
    for m in body.meal_configs:
        h, mn = map(int, m.time.split(":"))
        db.add(
            MealConfig(
                session_id=db_session.id,
                meal_name=m.name,
                meal_time=dtime(hour=h, minute=mn),
                window_before_min=m.window_before_min,
                window_after_min=m.window_after_min,
            )
        )

    # Run simulation
    timestamps, glucose_values = simulate_glucose(
        profile_name=body.patient_profile,
        meal_inputs=body.meal_configs,
        seed=hash(db_session.id) % (2**31),
    )

    # Bulk-insert glucose readings
    readings = [
        GlucoseReading(
            session_id=db_session.id,
            timestamp=ts,
            glucose_mg_dl=gl,
        )
        for ts, gl in zip(timestamps, glucose_values)
    ]
    db.add_all(readings)

    db_session.status = "complete"
    db.commit()

    return SimulateResponse(session_id=db_session.id)
