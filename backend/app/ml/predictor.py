"""Model serving: loads the trained bundle once, predicts, and explains with SHAP.

Nothing here is hardcoded. GPA comes from the regression model, pass probability
from `predict_proba` of the classifier, the risk tier from the multiclass model,
and every contribution number comes from a SHAP explainer built on the same
fitted model.
"""

from __future__ import annotations

import threading
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

from app.ml import features as F

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "cognipath_models.joblib"

# Human-readable names for the encoded feature columns shown in the UI.
FEATURE_LABELS = {
    "age": "Age",
    "Medu": "Mother's education",
    "Fedu": "Father's education",
    "traveltime": "Travel time to school",
    "studytime": "Weekly study time",
    "failures": "Past course failures",
    "famrel": "Family relationship quality",
    "freetime": "Free time after school",
    "goout": "Going out with friends",
    "Dalc": "Weekday alcohol use",
    "Walc": "Weekend alcohol use",
    "health": "Health status",
    "absences": "Absences",
    "G1": "Period 1 grade (G1)",
    "G2": "Period 2 grade (G2)",
    "attendance_pct": "Attendance %",
    "grade_trend": "Grade trend (G2 - G1)",
    "sex_M": "Sex = M",
    "address_U": "Lives in urban area",
    "famsize_LE3": "Small family (<=3)",
    "Pstatus_T": "Parents living together",
    "schoolsup_yes": "Extra school support",
    "famsup_yes": "Family educational support",
    "paid_yes": "Paid extra classes",
    "activities_yes": "Extracurricular activities",
    "higher_yes": "Wants higher education",
    "internet_yes": "Internet access at home",
    "romantic_yes": "In a romantic relationship",
}


class ModelNotTrainedError(RuntimeError):
    pass


class _Bundle:
    """Process-wide singleton holding models and lazily built SHAP explainers."""

    _lock = threading.Lock()
    _instance: "_Bundle | None" = None

    def __init__(self, path: Path = MODEL_PATH):
        if not path.exists():
            raise ModelNotTrainedError(
                f"Trained model bundle not found at {path}. "
                "Run `python -m app.ml.train` from the backend directory first."
            )
        self.data = joblib.load(path)
        self._explainers: dict[str, object] = {}

    @classmethod
    def get(cls) -> "_Bundle":
        with cls._lock:
            if cls._instance is None:
                cls._instance = _Bundle()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def explainer(self, task: str):
        if task in self._explainers:
            return self._explainers[task]
        model = self.data[f"{task}_model"]
        family = self.data.get(f"{task}_explainer_family", "tree")
        background = self.data["background"]
        if family == "tree":
            exp = shap.TreeExplainer(model)
        elif family == "linear":
            exp = shap.LinearExplainer(model, background)
        else:  # pragma: no cover - fallback for non tree/linear models
            exp = shap.KernelExplainer(model.predict, shap.kmeans(background, 20))
        self._explainers[task] = exp
        return exp


def get_bundle() -> dict:
    return _Bundle.get().data


def model_info() -> dict:
    b = get_bundle()
    return {
        "gpa_model": b["gpa_model_name"],
        "pass_model": b["pass_model_name"],
        "risk_model": b["risk_model_name"],
        "risk_labels": list(b["risk_labels"]),
        "n_encoded_features": len(b["feature_names"]),
    }


def build_frame(payload: dict) -> pd.DataFrame:
    """Build a one-row DataFrame in the exact training column order.

    Missing optional fields fall back to the TRAINING median/mode, never to an
    arbitrary constant, so imputation cannot leak test information.
    """
    b = get_bundle()
    row: dict = {}
    for col in F.NUMERIC_RAW:
        val = payload.get(col)
        row[col] = float(val) if val is not None else float(b["train_medians"].get(col, 0.0))
    for col in F.CATEGORICAL_RAW:
        val = payload.get(col)
        row[col] = val if val is not None else b["train_modes"][col]
    df = pd.DataFrame([row])
    df = F.add_derived_columns(df)
    if payload.get("attendance_pct") is not None:
        # An explicitly supplied attendance overrides the value derived from absences.
        df.loc[0, "attendance_pct"] = float(payload["attendance_pct"])
    return df[F.FEATURES]


def _transform(df: pd.DataFrame) -> np.ndarray:
    return np.asarray(get_bundle()["preprocessor"].transform(df))


def predict(payload: dict) -> dict:
    b = get_bundle()
    X = _transform(build_frame(payload))

    gpa = float(b["gpa_model"].predict(X)[0])
    gpa = float(np.clip(gpa, 0.0, 10.0))

    pass_proba = float(b["pass_model"].predict_proba(X)[0][list(b["pass_model"].classes_).index(1)])

    risk_proba = b["risk_model"].predict_proba(X)[0]
    risk_classes = list(b["risk_model"].classes_)
    risk_tier = str(risk_classes[int(np.argmax(risk_proba))])

    return {
        "predicted_gpa": round(gpa, 2),
        "predicted_g3_equivalent": round(gpa * F.GPA_SCALE, 2),
        "pass_probability": round(pass_proba, 4),
        "risk_tier": risk_tier,
        "risk_probabilities": {c: round(float(p), 4) for c, p in zip(risk_classes, risk_proba)},
        "models_used": {
            "gpa": b["gpa_model_name"],
            "pass": b["pass_model_name"],
            "risk": b["risk_model_name"],
        },
        "interpretation": (
            f"Model estimates a GPA of {gpa:.2f}/10 with a "
            f"{pass_proba * 100:.1f}% probability of passing. Predicted academic risk: "
            f"{risk_tier}. This is a statistical estimate for early intervention, "
            "not a verdict on the student."
        ),
    }


def _shap_vector(task: str, X: np.ndarray) -> tuple[np.ndarray, float, str]:
    """Return (per-feature shap values for the row, base value, explained class).

    For the multiclass risk model we explain the class the model actually
    predicted, so the attribution answers "why did it say High risk?".
    """
    b = get_bundle()
    model = b[f"{task}_model"]
    exp = _Bundle.get().explainer(task)
    values = exp.shap_values(X)
    base = exp.expected_value
    explained_class = ""

    arr = np.asarray(values)
    if arr.ndim == 3:            # (n, features, classes)
        classes = list(model.classes_)
        predicted = model.predict(X)[0]
        idx = classes.index(predicted) if predicted in classes else int(
            np.argmax(np.abs(arr[0]).sum(axis=0))
        )
        explained_class = str(predicted)
        vec = arr[0, :, idx]
        base = np.asarray(base).ravel()[idx]
    elif arr.ndim == 2:          # (n, features)
        vec = arr[0]
        base = float(np.asarray(base).ravel()[0])
        if task == "pass":
            explained_class = "pass"
    else:                        # pragma: no cover
        vec = arr
        base = float(np.asarray(base).ravel()[0])
    return np.asarray(vec, dtype=float), float(base), explained_class


def explain(payload: dict, task: str = "gpa", top_k: int = 10) -> dict:
    """Real SHAP attribution for one student and one prediction task."""
    if task not in {"gpa", "pass", "risk"}:
        raise ValueError("task must be one of: gpa, pass, risk")
    b = get_bundle()
    frame = build_frame(payload)
    X = _transform(frame)
    vec, base, explained_class = _shap_vector(task, X)

    names = b["feature_names"]
    if len(vec) != len(names):  # pragma: no cover - defensive
        raise RuntimeError(
            f"SHAP returned {len(vec)} values for {len(names)} features"
        )

    raw_values = frame.iloc[0].to_dict()
    contributions = []
    for name, value in zip(names, vec):
        contributions.append(
            {
                "feature": name,
                "label": FEATURE_LABELS.get(name, name.replace("_", " ").title()),
                "shap_value": round(float(value), 4),
                "direction": "positive" if value >= 0 else "negative",
                "student_value": _student_value(name, raw_values),
            }
        )
    contributions.sort(key=lambda c: -abs(c["shap_value"]))
    top = contributions[:top_k]

    return {
        "task": task,
        "explained_class": explained_class,
        "units": _units(task),
        "base_value": round(base, 4),
        "prediction": round(base + float(vec.sum()), 4),
        "explainer": b.get(f"{task}_explainer_family", "tree"),
        "model": b[f"{task}_model_name"],
        "top_contributions": top,
        "helping": [c for c in top if c["shap_value"] > 0][:5],
        "hurting": [c for c in top if c["shap_value"] < 0][:5],
        "explanation_note": (
            "SHAP values show how much each feature moved this student's prediction "
            "away from the dataset average. Positive values push the prediction up, "
            "negative values push it down. They explain the model's behaviour, not "
            "the real-world cause of the outcome."
        ),
    }


def _units(task: str) -> str:
    return {
        "gpa": "GPA points (0-10)",
        "pass": "log-odds of passing",
        "risk": "probability of the predicted risk class",
    }[task]


def _student_value(encoded_name: str, raw: dict):
    if encoded_name in raw:
        v = raw[encoded_name]
        return round(float(v), 2) if isinstance(v, (int, float, np.floating)) else v
    base = encoded_name.rsplit("_", 1)[0]
    return raw.get(base)
