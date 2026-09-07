"""Feature schema and derivation rules for CogniPath AI.

Source dataset: UCI Student Performance (Cortez & Silva, 2008), `student-mat.csv`,
395 records, 33 raw columns, no missing values.

Two kinds of columns are used and they are kept explicitly separate:

RAW      -> present verbatim in the UCI file.
DERIVED  -> computed from RAW columns by a documented, deterministic rule below.

Nothing else is invented. Concept-mastery data does NOT exist in this dataset and
is therefore never derived here; it is supplied by the user or, for the demo
cohort, produced by `app.ml.mastery_simulator` and explicitly labelled simulated.
"""

from __future__ import annotations

import pandas as pd

# --- Raw numeric predictors -------------------------------------------------
NUMERIC_RAW = [
    "age",
    "Medu",       # mother's education 0-4
    "Fedu",       # father's education 0-4
    "traveltime",  # 1-4
    "studytime",   # weekly study time, 1-4 (1: <2h ... 4: >10h)
    "failures",    # number of past class failures, 0-3
    "famrel",      # family relationship quality 1-5
    "freetime",    # free time after school 1-5
    "goout",       # going out with friends 1-5
    "Dalc",        # workday alcohol 1-5
    "Walc",        # weekend alcohol 1-5
    "health",      # current health status 1-5
    "absences",    # 0-93
    "G1",          # first period grade 0-20
    "G2",          # second period grade 0-20
]

# --- Raw categorical predictors --------------------------------------------
CATEGORICAL_RAW = [
    "sex",
    "address",
    "famsize",
    "Pstatus",
    "schoolsup",
    "famsup",
    "paid",
    "activities",
    "higher",
    "internet",
    "romantic",
]

# --- Derived predictors -----------------------------------------------------
# attendance_pct: the dataset records absences, not attendance. We assume a
# nominal term length of TERM_SESSIONS scheduled sessions and clip at 0%.
#   attendance_pct = 100 * (1 - min(absences, TERM_SESSIONS) / TERM_SESSIONS)
# TERM_SESSIONS = 60 is a modelling assumption, documented in the README; it is a
# monotone rescaling of `absences`, so it adds interpretability, not information.
TERM_SESSIONS = 60

# grade_trend: G2 - G1. Captures whether the student is improving or declining
# between the two assessed periods. Purely a difference of two raw columns.
DERIVED = ["attendance_pct", "grade_trend"]

FEATURES = NUMERIC_RAW + DERIVED + CATEGORICAL_RAW
NUMERIC_FEATURES = NUMERIC_RAW + DERIVED

# --- Targets ----------------------------------------------------------------
# gpa: G3 is graded 0-20 (Portuguese scale). Indian academic projects are graded
# on a 0-10 GPA scale, so we apply an exact linear rescale gpa = G3 / 2.
# This is a unit conversion, not a new signal.
GPA_SCALE = 2.0

# passed: the dataset's own pass mark is 10/20 (Cortez & Silva use the same
# threshold in the original paper).
PASS_THRESHOLD_G3 = 10

# risk tier: derived from G3 with published-style bands, then expressed on the
# GPA scale. High: G3 < 10 (fail), Medium: 10 <= G3 < 14, Low: G3 >= 14.
RISK_BANDS_G3 = [(0, 10, "High"), (10, 14, "Medium"), (14, 21, "Low")]
RISK_LABELS = ["Low", "Medium", "High"]


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of `df` with the DERIVED columns added."""
    out = df.copy()
    out["attendance_pct"] = 100.0 * (
        1.0 - out["absences"].clip(upper=TERM_SESSIONS) / TERM_SESSIONS
    )
    out["grade_trend"] = out["G2"] - out["G1"]
    return out


def risk_tier_from_g3(g3: float) -> str:
    for low, high, label in RISK_BANDS_G3:
        if low <= g3 < high:
            return label
    return "Low"


def add_targets(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["gpa"] = out["G3"] / GPA_SCALE
    out["passed"] = (out["G3"] >= PASS_THRESHOLD_G3).astype(int)
    out["risk_tier"] = out["G3"].apply(risk_tier_from_g3)
    return out


def risk_tier_from_gpa(gpa: float) -> str:
    """Same bands as `risk_tier_from_g3`, expressed on the 0-10 GPA scale."""
    return risk_tier_from_g3(gpa * GPA_SCALE)
