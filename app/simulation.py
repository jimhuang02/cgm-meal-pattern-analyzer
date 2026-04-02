"""
CGM Glucose Simulation Engine.

Generates 14 days of continuous glucose monitor readings at 5-minute intervals.
The model includes:
  - Profile-specific fasting baseline and postprandial amplitude
  - Smooth postprandial spike curves (raised-cosine rise + exponential decay)
  - Overnight sinusoidal drift representing dawn phenomenon and sleep variation
  - Per-day amplitude scaling for inter-day variability
  - Gaussian sensor noise
"""

from datetime import datetime, timedelta, time as dtime

import numpy as np

from app.constants import (
    SIMULATION_DAYS,
    READINGS_PER_DAY,
    SENSOR_NOISE_STD_MG_DL,
    MIN_GLUCOSE_MG_DL,
    MAX_GLUCOSE_MG_DL,
    READING_INTERVAL_MIN,
    PROFILE_PARAMS,
)
from app.schemas import MealConfigInput


# Base date for all simulated sessions (deterministic, reproducible)
_SIM_BASE_DATE = datetime(2025, 1, 1, 0, 0, 0)


def _meal_time_to_slot(meal_time: dtime) -> int:
    """Convert a wall-clock time to a 5-minute slot index (0–287)."""
    return (meal_time.hour * 60 + meal_time.minute) // READING_INTERVAL_MIN


def _compute_spike(
    t_min: float,
    onset_delay: int,
    peak_time: int,
    amplitude: float,
    fall_halflife: float,
) -> float:
    """
    Glucose elevation (mg/dL) at *t_min* minutes after a meal.

    Rise phase uses a raised-cosine (sin²) curve from onset_delay to peak_time,
    giving a smooth S-shaped rise with zero derivative at both endpoints.
    Decay phase is exponential with the given half-life, ensuring continuity
    at the peak.

    Parameters
    ----------
    t_min : float
        Minutes elapsed since meal time.
    onset_delay : int
        Minutes before glucose starts rising (absorption lag).
    peak_time : int
        Minutes from meal to peak glucose.
    amplitude : float
        Maximum glucose elevation above baseline (mg/dL).
    fall_halflife : float
        Exponential half-life for the decay phase (minutes).
    """
    if t_min < onset_delay:
        return 0.0

    t = t_min - onset_delay
    rise_duration = max(peak_time - onset_delay, 1)

    if t <= rise_duration:
        # Raised cosine: smooth zero-to-one rise
        progress = t / rise_duration
        return float(amplitude * (np.sin(np.pi / 2.0 * progress) ** 2))
    else:
        # Exponential decay from peak
        t_decay = t - rise_duration
        decay_rate = np.log(2.0) / fall_halflife
        return float(amplitude * np.exp(-decay_rate * t_decay))


def simulate_glucose(
    profile_name: str,
    meal_inputs: list[MealConfigInput],
    seed: int = 42,
) -> tuple[list[datetime], list[float]]:
    """
    Generate a 14-day CGM trace for the given patient profile and meal schedule.

    Returns two parallel lists: timestamps and glucose values (mg/dL).
    The total length is SIMULATION_DAYS × READINGS_PER_DAY = 4032.

    Parameters
    ----------
    profile_name : str
        One of "well_controlled", "moderate", "poorly_controlled".
    meal_inputs : list[MealConfigInput]
        Meal schedule from the API request.
    seed : int
        Random seed for reproducibility.
    """
    params = PROFILE_PARAMS[profile_name]
    rng = np.random.default_rng(seed)

    # Parse meal times once
    parsed_meals: list[tuple[dtime, int, int]] = []
    for m in meal_inputs:
        h, mn = map(int, m.time.split(":"))
        parsed_meals.append((dtime(hour=h, minute=mn), m.window_before_min, m.window_after_min))

    all_timestamps: list[datetime] = []
    all_glucose: list[float] = []

    for day in range(SIMULATION_DAYS):
        # Per-day fasting baseline varies slightly
        fasting_base: float = float(
            rng.uniform(*params["fasting_base_range"])
        )
        # Per-day amplitude scaling (±variability)
        day_scale: float = float(
            1.0 + rng.uniform(-params["day_variability"], params["day_variability"])
        )

        # Per-meal random kinetics for this day
        meal_kinetics: list[tuple[int, int, float]] = []
        for _ in parsed_meals:
            onset = int(rng.integers(*params["onset_delay_range"]))
            peak_t = int(rng.integers(*params["peak_time_range"]))
            amp = float(rng.uniform(*params["amplitude_range"])) * day_scale
            meal_kinetics.append((onset, peak_t, amp))

        # Initialize daily trace at fasting baseline
        glucose = np.full(READINGS_PER_DAY, fasting_base, dtype=np.float64)

        # Overnight sinusoidal drift (slots 0–71 = 00:00–05:55)
        # Models the dawn phenomenon: gentle dip then rise before breakfast
        overnight_amp: float = params["overnight_drift_amplitude"]
        overnight_phase: float = float(rng.uniform(-0.4, 0.4))  # slight phase jitter
        overnight_slots = 72  # 6 hours × 12 slots/hour
        for i in range(overnight_slots):
            # sin from -π/2 to 3π/2 gives: starts at -1, rises to +1, falls back
            phase_rad = np.pi * i / overnight_slots + overnight_phase
            glucose[i] += overnight_amp * np.sin(phase_rad)

        # Add postprandial spikes for each meal
        for (meal_time_obj, _, _), (onset, peak_t, amp) in zip(parsed_meals, meal_kinetics):
            meal_slot = _meal_time_to_slot(meal_time_obj)
            fall_hl = params["fall_halflife_min"]

            # Compute spike for every slot from meal time onward
            for i in range(meal_slot, READINGS_PER_DAY):
                t_min = (i - meal_slot) * READING_INTERVAL_MIN
                spike = _compute_spike(t_min, onset, peak_t, amp, fall_hl)
                if spike < 0.5:  # Early exit once spike is negligible
                    if t_min > peak_t + fall_hl * 6:
                        break
                glucose[i] += spike

        # Gaussian sensor noise
        glucose += rng.normal(0.0, SENSOR_NOISE_STD_MG_DL, READINGS_PER_DAY)

        # Clip to physiologically plausible range
        glucose = np.clip(glucose, MIN_GLUCOSE_MG_DL, MAX_GLUCOSE_MG_DL)

        # Build timestamps
        day_start = _SIM_BASE_DATE + timedelta(days=day)
        timestamps = [
            day_start + timedelta(minutes=READING_INTERVAL_MIN * i)
            for i in range(READINGS_PER_DAY)
        ]

        all_timestamps.extend(timestamps)
        all_glucose.extend(glucose.tolist())

    return all_timestamps, all_glucose
