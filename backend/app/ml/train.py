"""Reproducible training pipeline for CogniPath AI.

Run:  python -m app.ml.train      (from backend/)

Three supervised tasks are trained on the same feature matrix:

  T1  gpa        regression      (G3 / 2)
  T2  passed     binary          (G3 >= 10)
  T3  risk_tier  3-class         (High / Medium / Low bands on G3)

Design notes for the viva
-------------------------
* The preprocessor is fitted on the TRAIN split only and then reused, so no
  test-set statistics leak into scaling or one-hot categories.
* The split is stratified on `risk_tier`, which keeps the class balance of all
  three targets stable (they are all monotone functions of G3).
* Candidate models are compared by cross-validation on the training split; the
  test split is touched exactly once, for the final reported metrics.
* Models are chosen for accuracy AND for SHAP tractability: tree ensembles get
  exact TreeSHAP, linear models get exact LinearSHAP. No kernel approximation
  is needed at request time, which keeps the API fast.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import Lasso, LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml import features as F
from app.ml.dataset import load_prepared, profile

RANDOM_STATE = 42
TEST_SIZE = 0.20
MODEL_DIR = Path(__file__).resolve().parents[2] / "models"


# --------------------------------------------------------------------------- #
# preprocessing
# --------------------------------------------------------------------------- #
def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), F.NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(drop="if_binary", handle_unknown="ignore", sparse_output=False),
                F.CATEGORICAL_RAW,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def candidate_regressors() -> dict:
    return {
        "LinearRegression": LinearRegression(),
        "Ridge": Ridge(alpha=1.0, random_state=RANDOM_STATE),
        "Lasso": Lasso(alpha=0.01, random_state=RANDOM_STATE, max_iter=5000),
        "RandomForestRegressor": RandomForestRegressor(
            n_estimators=400, min_samples_leaf=2, random_state=RANDOM_STATE, n_jobs=-1
        ),
        "GradientBoostingRegressor": GradientBoostingRegressor(random_state=RANDOM_STATE),
        "HistGradientBoostingRegressor": HistGradientBoostingRegressor(
            random_state=RANDOM_STATE
        ),
    }


def candidate_classifiers() -> dict:
    return {
        "LogisticRegression": LogisticRegression(max_iter=2000, random_state=RANDOM_STATE),
        "RandomForestClassifier": RandomForestClassifier(
            n_estimators=400, min_samples_leaf=2, random_state=RANDOM_STATE, n_jobs=-1
        ),
        "GradientBoostingClassifier": GradientBoostingClassifier(random_state=RANDOM_STATE),
        "HistGradientBoostingClassifier": HistGradientBoostingClassifier(
            random_state=RANDOM_STATE
        ),
    }


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def regression_metrics(y_true, y_pred) -> dict:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": rmse,
        "r2": float(r2_score(y_true, y_pred)),
    }


def binary_metrics(y_true, y_pred, y_proba) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }


def multiclass_metrics(y_true, y_pred, labels) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "labels": list(labels),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def explainer_family(model) -> str:
    """Which SHAP explainer the serving layer should use for this model."""
    tree_like = (
        RandomForestRegressor,
        RandomForestClassifier,
        GradientBoostingRegressor,
        GradientBoostingClassifier,
        HistGradientBoostingRegressor,
        HistGradientBoostingClassifier,
    )
    linear_like = (LinearRegression, Ridge, Lasso, LogisticRegression)
    if isinstance(model, tree_like):
        return "tree"
    if isinstance(model, linear_like):
        return "linear"
    return "kernel"


# --------------------------------------------------------------------------- #
# training
# --------------------------------------------------------------------------- #
def train_all(csv_path: str | Path | None = None, out_dir: Path = MODEL_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = load_prepared(csv_path) if csv_path else load_prepared()
    data_profile = profile(df)

    X = df[F.FEATURES]
    y_gpa = df["gpa"]
    y_pass = df["passed"]
    y_risk = df["risk_tier"]

    X_train, X_test, idx_train, idx_test = train_test_split(
        X,
        df.index,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y_risk,
    )
    y_gpa_tr, y_gpa_te = y_gpa.loc[idx_train], y_gpa.loc[idx_test]
    y_pass_tr, y_pass_te = y_pass.loc[idx_train], y_pass.loc[idx_test]
    y_risk_tr, y_risk_te = y_risk.loc[idx_train], y_risk.loc[idx_test]

    pre = build_preprocessor()
    Xt_train = pre.fit_transform(X_train)          # fitted on TRAIN only
    Xt_test = pre.transform(X_test)
    feature_names = list(pre.get_feature_names_out())

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    report: dict = {
        "random_state": RANDOM_STATE,
        "test_size": TEST_SIZE,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_features_after_encoding": len(feature_names),
        "data_profile": data_profile,
        "tasks": {},
    }

    # ---- T1 regression: GPA -------------------------------------------------
    reg_cv, best_reg_name, best_reg_score = {}, None, -np.inf
    for name, model in candidate_regressors().items():
        scores = cross_val_score(
            model, Xt_train, y_gpa_tr, cv=cv.split(Xt_train, y_risk_tr), scoring="r2"
        )
        reg_cv[name] = {"cv_r2_mean": float(scores.mean()), "cv_r2_std": float(scores.std())}
        if scores.mean() > best_reg_score:
            best_reg_score, best_reg_name = scores.mean(), name
    best_reg = candidate_regressors()[best_reg_name].fit(Xt_train, y_gpa_tr)
    reg_test = regression_metrics(y_gpa_te, best_reg.predict(Xt_test))
    report["tasks"]["gpa_regression"] = {
        "target": "gpa = G3 / 2",
        "candidates": reg_cv,
        "selected_model": best_reg_name,
        "selection_metric": "cross-validated R^2 on the training split",
        "test_metrics": reg_test,
    }

    # ---- T2 binary: pass probability ---------------------------------------
    clf_cv, best_pass_name, best_pass_score = {}, None, -np.inf
    for name, model in candidate_classifiers().items():
        scores = cross_val_score(
            model, Xt_train, y_pass_tr, cv=cv.split(Xt_train, y_pass_tr), scoring="roc_auc"
        )
        clf_cv[name] = {"cv_roc_auc_mean": float(scores.mean()), "cv_roc_auc_std": float(scores.std())}
        if scores.mean() > best_pass_score:
            best_pass_score, best_pass_name = scores.mean(), name
    best_pass = candidate_classifiers()[best_pass_name].fit(Xt_train, y_pass_tr)
    proba = best_pass.predict_proba(Xt_test)[:, 1]
    pass_test = binary_metrics(y_pass_te, (proba >= 0.5).astype(int), proba)
    report["tasks"]["pass_classification"] = {
        "target": "passed = G3 >= 10",
        "candidates": clf_cv,
        "selected_model": best_pass_name,
        "selection_metric": "cross-validated ROC-AUC on the training split",
        "test_metrics": pass_test,
    }

    # ---- T3 multiclass: risk tier ------------------------------------------
    risk_cv, best_risk_name, best_risk_score = {}, None, -np.inf
    for name, model in candidate_classifiers().items():
        scores = cross_val_score(
            model, Xt_train, y_risk_tr, cv=cv.split(Xt_train, y_risk_tr), scoring="f1_macro"
        )
        risk_cv[name] = {"cv_f1_macro_mean": float(scores.mean()), "cv_f1_macro_std": float(scores.std())}
        if scores.mean() > best_risk_score:
            best_risk_score, best_risk_name = scores.mean(), name
    best_risk = candidate_classifiers()[best_risk_name].fit(Xt_train, y_risk_tr)
    risk_test = multiclass_metrics(
        y_risk_te, best_risk.predict(Xt_test), labels=F.RISK_LABELS
    )
    report["tasks"]["risk_classification"] = {
        "target": "risk_tier from G3 bands (High <10, Medium 10-13, Low >=14)",
        "candidates": risk_cv,
        "selected_model": best_risk_name,
        "selection_metric": "cross-validated macro F1 on the training split",
        "test_metrics": risk_test,
    }

    # ---- persistence --------------------------------------------------------
    # A background sample of the TRAIN split is stored for SHAP explainers that
    # need a reference distribution.
    rng = np.random.default_rng(RANDOM_STATE)
    bg_idx = rng.choice(len(Xt_train), size=min(100, len(Xt_train)), replace=False)
    bundle = {
        "preprocessor": pre,
        "feature_names": feature_names,
        "raw_features": F.FEATURES,
        "numeric_features": F.NUMERIC_FEATURES,
        "categorical_features": F.CATEGORICAL_RAW,
        "gpa_model": best_reg,
        "gpa_model_name": best_reg_name,
        "gpa_explainer_family": explainer_family(best_reg),
        "pass_model": best_pass,
        "pass_model_name": best_pass_name,
        "pass_explainer_family": explainer_family(best_pass),
        "risk_model": best_risk,
        "risk_model_name": best_risk_name,
        "risk_labels": list(best_risk.classes_),
        "background": np.asarray(Xt_train)[bg_idx],
        "train_medians": X_train[F.NUMERIC_FEATURES].median().to_dict(),
        "train_modes": {c: X_train[c].mode().iloc[0] for c in F.CATEGORICAL_RAW},
    }
    joblib.dump(bundle, out_dir / "cognipath_models.joblib")
    (out_dir / "evaluation.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":  # pragma: no cover
    rep = train_all()
    print(json.dumps(
        {
            "gpa": {
                "model": rep["tasks"]["gpa_regression"]["selected_model"],
                **rep["tasks"]["gpa_regression"]["test_metrics"],
            },
            "pass": {
                "model": rep["tasks"]["pass_classification"]["selected_model"],
                **{k: v for k, v in rep["tasks"]["pass_classification"]["test_metrics"].items()
                   if k != "confusion_matrix"},
            },
            "risk": {
                "model": rep["tasks"]["risk_classification"]["selected_model"],
                "accuracy": rep["tasks"]["risk_classification"]["test_metrics"]["accuracy"],
                "f1_macro": rep["tasks"]["risk_classification"]["test_metrics"]["f1_macro"],
            },
        },
        indent=2,
    ))
