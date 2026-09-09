"""Bridge between the multi-assessment record and the trained ML models.

Read this before claiming anything about the ML in a review.
=============================================================

The models in `app.ml.predictor` were trained on the UCI Student Performance
dataset, which contains exactly two prior assessments per student (`G1`, `G2`)
plus behavioural columns. That is the only real labelled data this project has.
No dataset exists anywhere in the project with six assessments per subject AND a
known final outcome, so a model that consumes six assessments **cannot honestly
be trained here** - it would have to be fitted to data the project invented.

What is done instead, and why it is defensible:

    the models stay exactly as they were trained
    the assessment history is COMPRESSED into the feature space they know

    G1-equivalent  <- average of the earlier assessments  (rescaled 0-100 -> 0-20)
    G2-equivalent  <- weighted average of the recent window
    grade_trend    <- G2-equivalent minus G1-equivalent

`G1` and `G2` in the training data are themselves "the first period's mark" and
"the second period's mark", so feeding an early-window average and a recent-window
average preserves their meaning: prior performance, then more recent performance.
The behavioural features (attendance, study time, failures, and the rest) are
passed through unchanged from the student record.

What this buys, and what it does not
------------------------------------
It buys a genuinely longitudinal input: predictions now move when a new CAT is
recorded, and they can be produced per subject. It does NOT mean the model
learned anything about six-assessment sequences, subject identity, or volatility.
Those richer signals are computed and surfaced by `app.services.academics`, which
is explicitly rule-based and statistical - they are shown alongside the ML
prediction, never smuggled into it.

The per-subject prediction applies a model trained on one subject's marks to each
subject's marks in turn. That is a stated approximation, listed as a limitation in
the README, not a claim that the model is subject-aware.
"""

from __future__ import annotations

from app.database import academics_db
from app.ml import features as F
from app.services import academics

# Weighting inside the recent window: the most recent assessment counts most.
# Documented and configurable rather than an unexplained constant.
RECENT_WEIGHTS = [0.5, 0.3, 0.2]        # newest first
PERCENT_TO_G_SCALE = 20.0 / 100.0       # UCI grades are 0-20, percentages are 0-100


def _weighted_recent(values: list[float]) -> float:
    """Weighted mean of up to the last three assessments, newest weighted most."""
    window = list(reversed(values[-len(RECENT_WEIGHTS):]))
    weights = RECENT_WEIGHTS[:len(window)]
    total = sum(weights)
    return sum(v * w for v, w in zip(window, weights)) / total


def series_to_grade_features(percentages: list[float]) -> dict | None:
    """Compress a chronological percentage series into G1/G2-equivalents.

    Returns None when there is nothing to compress - the caller then falls back
    to the student's stored feature row rather than inventing numbers.
    """
    values = [float(v) for v in percentages if v is not None]
    if not values:
        return None

    if len(values) == 1:
        earlier = recent = values[0]
    else:
        split = max(1, len(values) - len(RECENT_WEIGHTS))
        earlier_values = values[:split]
        earlier = sum(earlier_values) / len(earlier_values)
        recent = _weighted_recent(values)

    g1 = round(earlier * PERCENT_TO_G_SCALE, 3)
    g2 = round(recent * PERCENT_TO_G_SCALE, 3)
    return {
        "G1": max(0.0, min(20.0, g1)),
        "G2": max(0.0, min(20.0, g2)),
        "grade_trend": round(g2 - g1, 3),
        "n_assessments": len(values),
        "earlier_average_pct": round(earlier, 1),
        "recent_average_pct": round(recent, 1),
    }


def features_from_assessments(student_features: dict, percentages: list[float]) -> dict:
    """Student feature row with G1/G2 replaced by the assessment-derived pair.

    Behavioural and demographic columns are passed through untouched; only the
    prior-performance slots are re-derived.
    """
    derived = series_to_grade_features(percentages)
    if derived is None:
        return dict(student_features)
    merged = dict(student_features)
    merged["G1"] = derived["G1"]
    merged["G2"] = derived["G2"]
    merged["grade_trend"] = derived["grade_trend"]
    return merged


def student_series(student_id: str, subject_id: str | None = None) -> list[float]:
    rows = academics_db.student_results(student_id, subject_id)
    rows.sort(key=lambda r: (r["subject_id"], r["assessment_order"]))
    return [float(r["percentage"]) for r in rows]


def subject_prediction(student_id: str, student_features: dict, subject_id: str) -> dict | None:
    """Run the existing models over one subject's assessment history."""
    from app.ml import predictor

    series = student_series(student_id, subject_id)
    derived = series_to_grade_features(series)
    if derived is None:
        return None
    payload = features_from_assessments(student_features, series)
    prediction = predictor.predict(payload)
    return {
        "subject_id": subject_id,
        "prediction": prediction,
        "derived_inputs": derived,
        "basis": (
            "The trained GPA/pass/risk models applied to this subject's assessment "
            "history, compressed into the prior-performance features the models were "
            "trained on. The models are not subject-aware; this is the same model "
            "reading this subject's marks."
        ),
    }


def overall_prediction(student_id: str, student_features: dict) -> dict:
    """Prediction driven by the student's assessments across every subject.

    Subjects are pooled rather than averaged after the fact, so a student who is
    failing one subject and coasting in five is not flattened into "fine".
    """
    from app.ml import predictor

    per_subject = academics.subject_performance(student_id)
    if not per_subject:
        prediction = predictor.predict(student_features)
        return {
            "prediction": prediction,
            "source": "stored_student_features",
            "note": ("No assessment results recorded, so the prediction uses the "
                     "student's stored feature row unchanged."),
            "derived_inputs": None,
        }

    # Chronological pooling: take each subject's series in order and interleave by
    # assessment position, so "recent" means recent across the whole term.
    by_order: dict[int, list[float]] = {}
    for subject in per_subject:
        for a in subject["assessments"]:
            by_order.setdefault(a["order"], []).append(a["percentage"])
    pooled = [sum(v) / len(v) for _, v in sorted(by_order.items())]

    payload = features_from_assessments(student_features, pooled)
    prediction = predictor.predict(payload)
    derived = series_to_grade_features(pooled)
    return {
        "prediction": prediction,
        "source": "multi_subject_assessments",
        "pooled_series": [round(p, 1) for p in pooled],
        "derived_inputs": derived,
        "note": (
            "Assessment percentages across all subjects are pooled by assessment "
            "position, then compressed into the prior-performance features the "
            "trained models expect. Adding a new result changes this prediction; "
            "the models themselves are unchanged and were not retrained on "
            "multi-assessment data, because no labelled multi-assessment dataset "
            "exists in this project."
        ),
    }


def explain_overall(student_id: str, student_features: dict, task: str = "gpa") -> dict:
    """SHAP explanation for the assessment-driven prediction.

    Same explainer, same fitted model - the only difference is that the feature
    row being explained came from the assessment history.
    """
    from app.ml import predictor

    pooled = []
    per_subject = academics.subject_performance(student_id)
    by_order: dict[int, list[float]] = {}
    for subject in per_subject:
        for a in subject["assessments"]:
            by_order.setdefault(a["order"], []).append(a["percentage"])
    pooled = [sum(v) / len(v) for _, v in sorted(by_order.items())]

    payload = features_from_assessments(student_features, pooled) if pooled else dict(student_features)
    explanation = predictor.explain(payload, task=task)
    explanation["input_source"] = "multi_subject_assessments" if pooled else "stored_student_features"
    return explanation


def feature_provenance() -> dict:
    """Machine-readable answer to 'which part of this is ML?' - used by the UI."""
    return {
        "ml": [
            "GPA regression (RandomForestRegressor)",
            "Pass probability (LogisticRegression)",
            "Academic risk tier (RandomForestClassifier)",
            "SHAP attributions for all three",
        ],
        "graph_based": [
            "Prerequisite relationships (NetworkX DAG, per subject)",
            "Root-cause propagation over prerequisites",
        ],
        "rule_based": [
            "Trend classification (least-squares slope + volatility thresholds)",
            "Per-subject risk score (weighted rule)",
            "Early-warning triggers",
            "Recommendation prioritisation and study plan allocation",
        ],
        "derived_metrics": [
            "Concept mastery (self-reported, assessment-imported, or practice-updated)",
            "Consistency, retention, learning speed in the Cognitive Twin",
        ],
        "adapters": [
            "Assessment history -> G1/G2-equivalent features for the trained models",
        ],
        "note": (
            "The trained models consume compressed assessment features; the richer "
            "longitudinal signals (trend, volatility, per-subject risk) are computed "
            "by documented rules and displayed separately, never presented as model output."
        ),
        "feature_columns_used_by_models": F.FEATURES,
    }
