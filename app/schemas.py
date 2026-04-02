"""Pydantic request/response schemas for all API endpoints."""

from typing import Optional
from pydantic import BaseModel, field_validator


# ── Request schemas ──────────────────────────────────────────────────────────

class MealConfigInput(BaseModel):
    name: str
    time: str                   # "HH:MM" 24-hour format
    window_before_min: int = 30
    window_after_min: int = 120

    @field_validator("time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("time must be HH:MM format")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Invalid hour or minute value")
        return v

    @field_validator("window_before_min", "window_after_min")
    @classmethod
    def validate_window(cls, v: int) -> int:
        if not (0 <= v <= 360):
            raise ValueError("Window must be 0–360 minutes")
        return v


class SimulateRequest(BaseModel):
    patient_profile: str        # "well_controlled" | "moderate" | "poorly_controlled"
    meal_configs: list[MealConfigInput]

    @field_validator("patient_profile")
    @classmethod
    def validate_profile(cls, v: str) -> str:
        valid = {"well_controlled", "moderate", "poorly_controlled"}
        if v not in valid:
            raise ValueError(f"patient_profile must be one of {valid}")
        return v


# ── Response schemas ─────────────────────────────────────────────────────────

class SimulateResponse(BaseModel):
    session_id: str


class MealPercentiles(BaseModel):
    """Percentile curves for a meal window, aligned to minutes-from-meal."""
    minutes: list[int]
    p10: list[float]
    p25: list[float]
    p50: list[float]
    p75: list[float]
    p90: list[float]


class MealAnalysis(BaseModel):
    meal_name: str
    meal_time: str
    window_before_min: int
    window_after_min: int
    peak_glucose: float             # Median of daily peak values (mg/dL)
    time_to_peak_minutes: float     # Median minutes from meal to peak
    excursion_mg_dl: float          # Median peak minus pre-meal baseline
    cv_percent: float               # Coefficient of variation across the window
    stability: str                  # "stable" | "variable" | "highly_variable"
    percentiles: MealPercentiles


class HypoEvent(BaseModel):
    start_time: str                 # ISO 8601 timestamp
    duration_minutes: int
    min_glucose: float


class AgpPercentiles(BaseModel):
    """Full 24-hour AGP: 288 five-minute slots, five percentile curves."""
    p10: list[float]
    p25: list[float]
    p50: list[float]
    p75: list[float]
    p90: list[float]


class AnalysisResponse(BaseModel):
    session_id: str
    patient_profile: str
    tir_percent: float              # % readings 70–180 mg/dL
    tar_percent: float              # % readings >180 mg/dL
    tbr_percent: float              # % readings <70 mg/dL
    gmi: float                      # Glucose Management Indicator (%)
    mean_glucose: float             # mg/dL
    cv_percent: float               # Overall CV across all readings
    hypo_events: list[HypoEvent]
    meal_analyses: list[MealAnalysis]
    agp_24h: AgpPercentiles


class InsightResponse(BaseModel):
    report: str


class HealthResponse(BaseModel):
    status: str
    db: str
