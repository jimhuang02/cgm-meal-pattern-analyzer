"""
AGP (Ambulatory Glucose Profile) Analysis Engine.

Computes all clinical metrics from a 14-day CGM dataset:
  - 24-hour AGP percentile curves (P10/P25/P50/P75/P90)
  - Per-meal window statistics: peak, time-to-peak, excursion, CV, stability class
  - Overall session metrics: TIR, TAR, TBR, GMI, CV
  - Hypoglycemia event detection (glucose < 70 for ≥15 consecutive minutes)
"""

from datetime import datetime, time as dtime
from typing import Union

import numpy as np

from app.constants import (
    HYPO_THRESHOLD_MG_DL,
    TIR_LOWER_MG_DL,
    TIR_UPPER_MG_DL,
    TAR_THRESHOLD_MG_DL,
    CV_STABLE_MAX,
    CV_VARIABLE_MAX,
    GMI_INTERCEPT,
    GMI_SLOPE,
    HYPO_MIN_DURATION_MIN,
    SIMULATION_DAYS,
    READINGS_PER_DAY,
    READING_INTERVAL_MIN,
)
from app.models import GlucoseReading, MealConfig
from app.schemas import (
    AnalysisResponse,
    AgpPercentiles,
    MealAnalysis,
    MealPercentiles,
    HypoEvent,
)


def _classify_stability(cv: float) -> str:
    """
    Classify glycemic variability from coefficient of variation.

    Thresholds per ADA/EASD 2019 consensus on CGM standardized metrics
    (Danne et al., Diabetes Care 2019).
    """
    if cv < CV_STABLE_MAX:
        return "stable"
    elif cv <= CV_VARIABLE_MAX:
        return "variable"
    return "highly_variable"


def _time_to_slot(t: Union[dtime, str]) -> int:
    """Convert a TIME object or 'HH:MM' string to a 0–287 slot index."""
    if isinstance(t, str):
        h, m = map(int, t.split(":"))
    else:
        h, m = t.hour, t.minute
    return (h * 60 + m) // READING_INTERVAL_MIN


def _build_glucose_matrix(
    readings: list[GlucoseReading],
) -> np.ndarray:
    """
    Reshape a flat list of 4032 readings into a (14, 288) numpy matrix.

    Rows = days, columns = 5-minute slots within the day.
    If the reading count is not exactly SIMULATION_DAYS × READINGS_PER_DAY,
    the matrix is zero-padded to fill missing values.
    """
    total = SIMULATION_DAYS * READINGS_PER_DAY
    values = np.array([r.glucose_mg_dl for r in readings], dtype=np.float64)
    if len(values) < total:
        values = np.pad(values, (0, total - len(values)), constant_values=100.0)
    return values[:total].reshape(SIMULATION_DAYS, READINGS_PER_DAY)


def compute_agp_percentiles(matrix: np.ndarray) -> AgpPercentiles:
    """
    Compute full 24-hour AGP (Ambulatory Glucose Profile) percentile curves.

    The AGP collapses all 14 days onto a single 24-hour axis by computing
    percentiles across the day axis for each 5-minute slot.
    Reference: Matthaei et al., J Diabetes Sci Technol 2014.
    """
    pcts = np.percentile(matrix, [10, 25, 50, 75, 90], axis=0)  # shape (5, 288)
    return AgpPercentiles(
        p10=np.round(pcts[0], 1).tolist(),
        p25=np.round(pcts[1], 1).tolist(),
        p50=np.round(pcts[2], 1).tolist(),
        p75=np.round(pcts[3], 1).tolist(),
        p90=np.round(pcts[4], 1).tolist(),
    )


def compute_meal_analysis(
    matrix: np.ndarray,
    meal: MealConfig,
) -> MealAnalysis:
    """
    Compute all clinical metrics for a single meal window across 14 days.

    The window is [meal_time - window_before_min, meal_time + window_after_min].
    Percentiles are computed per 5-minute slot across all 14 days, then
    summary statistics are derived from per-day peak detection.

    Parameters
    ----------
    matrix : np.ndarray
        Shape (14, 288) glucose matrix.
    meal : MealConfig
        Meal configuration from the database.
    """
    meal_slot = _time_to_slot(meal.meal_time)
    before_slots = meal.window_before_min // READING_INTERVAL_MIN
    after_slots = meal.window_after_min // READING_INTERVAL_MIN

    start_slot = max(0, meal_slot - before_slots)
    end_slot = min(READINGS_PER_DAY - 1, meal_slot + after_slots)

    # Extract window: shape (14, n_slots)
    window = matrix[:, start_slot : end_slot + 1]
    n_slots = window.shape[1]

    # Pre-meal baseline: mean of 30 min immediately before meal, computed per day
    baseline_start = max(0, meal_slot - 6)
    if baseline_start < meal_slot:
        pre_meal_baseline_per_day = np.mean(matrix[:, baseline_start:meal_slot], axis=1)  # (14,)
    else:
        pre_meal_baseline_per_day = matrix[:, meal_slot]  # fallback
    pre_meal_baseline = float(np.mean(pre_meal_baseline_per_day))

    # Percentile curves across days, per slot
    pcts = np.percentile(window, [10, 25, 50, 75, 90], axis=0)  # (5, n_slots)

    # Minutes-from-meal labels (negative = before meal)
    slot_offset = meal_slot - start_slot
    minutes = [
        (i - slot_offset) * READING_INTERVAL_MIN for i in range(n_slots)
    ]

    # Per-day peak in the post-meal window
    post_meal_start = meal_slot - start_slot
    post_window = window[:, post_meal_start:]  # shape (14, after_slots)
    daily_peaks = np.max(post_window, axis=1)           # shape (14,)
    peak_indices = np.argmax(post_window, axis=1)       # shape (14,)

    peak_glucose = float(np.median(daily_peaks))
    time_to_peak = float(np.median(peak_indices) * READING_INTERVAL_MIN)
    excursion = float(peak_glucose - pre_meal_baseline)

    # CV of daily peak excursions across 14 days.
    # Measures day-to-day reproducibility of the meal glucose response,
    # which maps cleanly onto the ADA CV < 36% stability threshold
    # (Danne et al., ADA/EASD 2019 consensus on CGM metrics).
    daily_excursions = np.maximum(daily_peaks - pre_meal_baseline_per_day, 1.0)
    mean_exc = float(np.mean(daily_excursions))
    cv = float(np.std(daily_excursions) / mean_exc * 100.0) if mean_exc > 1 else 0.0

    return MealAnalysis(
        meal_name=meal.meal_name,
        meal_time=str(meal.meal_time)[:5],   # "HH:MM"
        window_before_min=meal.window_before_min,
        window_after_min=meal.window_after_min,
        peak_glucose=round(peak_glucose, 1),
        time_to_peak_minutes=round(time_to_peak, 1),
        excursion_mg_dl=round(excursion, 1),
        cv_percent=round(cv, 1),
        stability=_classify_stability(cv),
        percentiles=MealPercentiles(
            minutes=minutes,
            p10=np.round(pcts[0], 1).tolist(),
            p25=np.round(pcts[1], 1).tolist(),
            p50=np.round(pcts[2], 1).tolist(),
            p75=np.round(pcts[3], 1).tolist(),
            p90=np.round(pcts[4], 1).tolist(),
        ),
    )


def find_hypo_events(
    readings: list[GlucoseReading],
) -> list[HypoEvent]:
    """
    Detect hypoglycemia episodes: glucose < 70 mg/dL for ≥15 consecutive minutes.

    The 15-minute threshold matches the ADA definition of a clinically significant
    hypoglycemia event (ADA Standards of Care 2023, Section 6).
    """
    events: list[HypoEvent] = []
    in_event = False
    event_start: datetime | None = None
    event_readings: list[float] = []

    for reading in readings:
        if reading.glucose_mg_dl < HYPO_THRESHOLD_MG_DL:
            if not in_event:
                in_event = True
                event_start = reading.timestamp
                event_readings = [reading.glucose_mg_dl]
            else:
                event_readings.append(reading.glucose_mg_dl)
        else:
            if in_event:
                duration = len(event_readings) * READING_INTERVAL_MIN
                if duration >= HYPO_MIN_DURATION_MIN:
                    events.append(
                        HypoEvent(
                            start_time=event_start.isoformat(),
                            duration_minutes=duration,
                            min_glucose=round(float(min(event_readings)), 1),
                        )
                    )
                in_event = False
                event_readings = []

    # Handle event still open at end of trace
    if in_event and event_readings:
        duration = len(event_readings) * READING_INTERVAL_MIN
        if duration >= HYPO_MIN_DURATION_MIN:
            events.append(
                HypoEvent(
                    start_time=event_start.isoformat(),
                    duration_minutes=duration,
                    min_glucose=round(float(min(event_readings)), 1),
                )
            )

    return events


def build_analysis_response(
    session_id: str,
    patient_profile: str,
    readings: list[GlucoseReading],
    meal_configs: list[MealConfig],
) -> AnalysisResponse:
    """
    Orchestrate all analysis computations and assemble the full response.

    This function is the single entry point for the analysis router and
    coordinates matrix construction, AGP percentile calculation, per-meal
    window analysis, and overall session metric computation.
    """
    matrix = _build_glucose_matrix(readings)
    all_values = matrix.flatten()

    # ── Time-in-Range metrics (ADA 2023) ─────────────────────────────────────
    n_total = len(all_values)
    tir = float(np.sum((all_values >= TIR_LOWER_MG_DL) & (all_values <= TIR_UPPER_MG_DL)) / n_total * 100)
    tar = float(np.sum(all_values > TAR_THRESHOLD_MG_DL) / n_total * 100)
    tbr = float(np.sum(all_values < HYPO_THRESHOLD_MG_DL) / n_total * 100)

    # ── Glucose Management Indicator (Bergenstal 2018) ────────────────────────
    mean_glucose = float(np.mean(all_values))
    gmi = round(GMI_INTERCEPT + GMI_SLOPE * mean_glucose, 2)

    # ── Overall CV ────────────────────────────────────────────────────────────
    overall_cv = float(np.std(all_values) / mean_glucose * 100) if mean_glucose > 0 else 0.0

    # ── Per-meal analyses ─────────────────────────────────────────────────────
    meal_analyses = [compute_meal_analysis(matrix, m) for m in meal_configs]

    # ── 24-hour AGP ───────────────────────────────────────────────────────────
    agp = compute_agp_percentiles(matrix)

    # ── Hypoglycemia events ───────────────────────────────────────────────────
    hypo_events = find_hypo_events(readings)

    return AnalysisResponse(
        session_id=session_id,
        patient_profile=patient_profile,
        tir_percent=round(tir, 1),
        tar_percent=round(tar, 1),
        tbr_percent=round(tbr, 1),
        gmi=gmi,
        mean_glucose=round(mean_glucose, 1),
        cv_percent=round(overall_cv, 1),
        hypo_events=hypo_events,
        meal_analyses=meal_analyses,
        agp_24h=agp,
    )
