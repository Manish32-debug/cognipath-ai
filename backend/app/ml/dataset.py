"""Dataset loading for CogniPath AI.

The only real data in this project is the UCI Student Performance file. Anything
else the application shows is either user input or explicitly simulated demo
data (see `mastery_simulator.py`).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.ml import features as F

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_CSV = DATA_DIR / "student-mat.csv"


class DatasetError(RuntimeError):
    pass


def load_raw(csv_path: Path | str = DEFAULT_CSV) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise DatasetError(
            f"Dataset not found at {path}. Download student-mat.csv "
            "(UCI Student Performance) into backend/data/."
        )
    # The UCI file is semicolon separated with quoted categorical values.
    df = pd.read_csv(path, sep=";")
    missing = [c for c in F.NUMERIC_RAW + F.CATEGORICAL_RAW + ["G3"] if c not in df.columns]
    if missing:
        raise DatasetError(f"Dataset is missing required columns: {missing}")
    return df


def load_prepared(csv_path: Path | str = DEFAULT_CSV) -> pd.DataFrame:
    """Raw data + derived features + derived targets."""
    df = load_raw(csv_path)
    df = F.add_derived_columns(df)
    df = F.add_targets(df)
    return df


def profile(df: pd.DataFrame) -> dict:
    """Small data-quality report used by the training script and the README."""
    return {
        "n_rows": int(len(df)),
        "n_columns": int(df.shape[1]),
        "missing_values": int(df.isna().sum().sum()),
        "target_gpa_mean": float(df["gpa"].mean()),
        "target_gpa_std": float(df["gpa"].std()),
        "pass_rate": float(df["passed"].mean()),
        "risk_distribution": {
            k: int(v) for k, v in df["risk_tier"].value_counts().items()
        },
    }
