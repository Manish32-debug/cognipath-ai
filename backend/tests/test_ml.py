"""Dataset, preprocessing, model loading, prediction and SHAP."""
from __future__ import annotations

import numpy as np
import pytest

from app.ml import features as F
from app.ml.dataset import load_prepared
from app.ml.predictor import build_frame, explain, model_info, predict


def test_derived_columns_are_exact_functions_of_raw():
    df = load_prepared()
    assert df["grade_trend"].equals(df["G2"] - df["G1"])
    expected = 100.0 * (1 - df["absences"].clip(upper=F.TERM_SESSIONS) / F.TERM_SESSIONS)
    assert np.allclose(df["attendance_pct"], expected)


def test_targets_follow_documented_rules():
    df = load_prepared()
    assert np.allclose(df["gpa"], df["G3"] / 2)
    assert (df["passed"] == (df["G3"] >= 10).astype(int)).all()
    assert df.loc[df["G3"] < 10, "risk_tier"].eq("High").all()
    assert df.loc[df["G3"] >= 14, "risk_tier"].eq("Low").all()


def test_no_missing_values_in_source_data():
    assert load_prepared().isna().sum().sum() == 0


def test_build_frame_has_training_column_order(sample_features):
    frame = build_frame(sample_features)
    assert list(frame.columns) == F.FEATURES
    assert len(frame) == 1


def test_predict_returns_calibrated_ranges(sample_features):
    out = predict(sample_features)
    assert 0 <= out["predicted_gpa"] <= 10
    assert 0 <= out["pass_probability"] <= 1
    assert out["risk_tier"] in {"Low", "Medium", "High"}
    assert abs(sum(out["risk_probabilities"].values()) - 1) < 1e-6


def test_better_grades_increase_predicted_gpa(sample_features):
    weak = predict({**sample_features, "G1": 6, "G2": 5})
    strong = predict({**sample_features, "G1": 17, "G2": 18})
    assert strong["predicted_gpa"] > weak["predicted_gpa"]
    assert strong["pass_probability"] > weak["pass_probability"]


@pytest.mark.parametrize("task", ["gpa", "pass", "risk"])
def test_shap_is_additive(sample_features, task):
    """SHAP's core property: base value + sum(contributions) = model output."""
    exp = explain(sample_features, task=task, top_k=30)
    total = exp["base_value"] + sum(c["shap_value"] for c in exp["top_contributions"])
    assert abs(total - exp["prediction"]) < 0.05


def test_shap_values_are_not_constant(sample_features):
    a = explain(sample_features, task="gpa")
    b = explain({**sample_features, "G2": 18, "absences": 0}, task="gpa")
    assert a["top_contributions"][0]["shap_value"] != b["top_contributions"][0]["shap_value"]


def test_explain_rejects_unknown_task(sample_features):
    with pytest.raises(ValueError):
        explain(sample_features, task="nonsense")


def test_model_info_lists_selected_models():
    info = model_info()
    assert info["gpa_model"] and info["pass_model"] and info["risk_model"]
    assert info["n_encoded_features"] > len(F.NUMERIC_FEATURES)
