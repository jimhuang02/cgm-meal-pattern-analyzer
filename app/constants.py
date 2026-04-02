"""
Clinical thresholds and named constants for CGM analysis.
All values are sourced from published clinical guidelines.
"""

# ── Glucose range thresholds (ADA Standards of Medical Care 2023) ──────────
HYPO_THRESHOLD_MG_DL: float = 70.0      # Below: hypoglycemia
TIR_LOWER_MG_DL: float = 70.0           # Time-In-Range lower bound
TIR_UPPER_MG_DL: float = 180.0          # Time-In-Range upper bound (ADA target >70% for T2D)
TAR_THRESHOLD_MG_DL: float = 180.0      # Time-Above-Range threshold

# ── Variability thresholds (ADA/EASD 2019 consensus on CGM metrics) ─────────
CV_STABLE_MAX: float = 36.0             # CV < 36%: stable glycemia
CV_VARIABLE_MAX: float = 50.0           # CV 36–50%: variable; >50%: highly variable

# ── GMI formula coefficients (Bergenstal et al., 2018, Diabetes Care) ───────
GMI_INTERCEPT: float = 3.31             # Constant term in GMI = 3.31 + 0.02392 × mean_glucose
GMI_SLOPE: float = 0.02392              # Slope (per mg/dL mean glucose)

# ── Hypoglycemia event definition ───────────────────────────────────────────
HYPO_MIN_DURATION_MIN: int = 15         # Minimum consecutive minutes below threshold

# ── Simulation parameters ───────────────────────────────────────────────────
SIMULATION_DAYS: int = 14
READINGS_PER_DAY: int = 288             # One reading every 5 minutes
SENSOR_NOISE_STD_MG_DL: float = 3.0    # Gaussian sensor noise (±3 mg/dL)
MIN_GLUCOSE_MG_DL: float = 40.0        # Physiological floor for clipping
MAX_GLUCOSE_MG_DL: float = 400.0       # Physiological ceiling for clipping
READING_INTERVAL_MIN: int = 5           # Minutes between readings

# ── Patient profile parameters ──────────────────────────────────────────────
PROFILE_PARAMS: dict = {
    "well_controlled": {
        "label": "Well Controlled",
        "description": "Peaks rarely exceed 160 mg/dL, quick return to baseline",
        "fasting_base_range": (80.0, 95.0),    # mg/dL fasting glucose range
        "amplitude_range": (40.0, 60.0),        # mg/dL postprandial rise above baseline
        "onset_delay_range": (20, 35),           # minutes before glucose starts rising
        "peak_time_range": (50, 70),             # minutes to peak from meal time
        "fall_halflife_min": 35.0,               # exponential decay half-life in minutes
        "day_variability": 0.10,                 # ±10% amplitude scaling between days
        "overnight_drift_amplitude": 5.0,        # mg/dL sinusoidal overnight variation
    },
    "moderate": {
        "label": "Moderate",
        "description": "Peaks 180–220 mg/dL regularly, slow return, TIR ~50–65%",
        "fasting_base_range": (100.0, 120.0),
        "amplitude_range": (80.0, 110.0),
        "onset_delay_range": (25, 40),
        "peak_time_range": (60, 80),
        "fall_halflife_min": 65.0,
        "day_variability": 0.20,
        "overnight_drift_amplitude": 12.0,
    },
    "poorly_controlled": {
        "label": "Poorly Controlled",
        "description": "Peaks 220–300 mg/dL, very prolonged elevation, TIR <50%",
        "fasting_base_range": (140.0, 175.0),  # Chronically elevated fasting glucose
        "amplitude_range": (70.0, 130.0),       # Consistent large spikes
        "onset_delay_range": (30, 45),
        "peak_time_range": (70, 95),
        "fall_halflife_min": 110.0,             # Very slow recovery — stays elevated for hours
        "day_variability": 0.55,
        "overnight_drift_amplitude": 20.0,      # Large overnight swings
    },
}

# ── Default meal configuration ───────────────────────────────────────────────
DEFAULT_MEALS: list[dict] = [
    {"name": "Breakfast", "time": "07:30", "window_before_min": 30, "window_after_min": 150},
    {"name": "Lunch",     "time": "12:30", "window_before_min": 30, "window_after_min": 150},
    {"name": "Dinner",    "time": "19:00", "window_before_min": 30, "window_after_min": 150},
    {"name": "Snack",     "time": "15:00", "window_before_min": 30, "window_after_min": 120},
]
