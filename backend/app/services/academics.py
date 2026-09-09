"""Longitudinal academic analytics: trends, subject performance, early warnings.

What kind of logic lives here (Part 23 honesty)
----------------------------------------------
Everything in this module is **rule-based / statistical**, not machine learning:

* `trend_analysis` fits an ordinary least-squares line through a student's
  assessment percentages and measures volatility as the standard deviation of
  first differences. That is descriptive statistics, not a trained model.
* `subject_risk` is a weighted rule with published constants, listed in the
  response under `weights` so a reader can check the arithmetic.
* `early_warnings` is a set of documented trigger conditions.

The ML models (GPA regression, pass probability, risk classification) and SHAP
are untouched and still live in `app.ml`. `app.ml.assessment_features` is the
bridge that lets those models read a multi-assessment history.
"""

from __future__ import annotations

import statistics
from typing import Sequence

from app.database import academics_db
from app.graph.knowledge_graph import SUBJECTS, subject_name

# --------------------------------------------------------------------------- #
# thresholds - all named, none buried in the code
# --------------------------------------------------------------------------- #
MIN_POINTS_FOR_TREND = 3      # a slope through two points says nothing about a trend
SLOPE_STABLE = 1.5            # |percentage points per assessment| below this is flat
SLOPE_STRONG = 4.0            # above this the trend is called "strong"
VOLATILITY_HIGH = 10.0        # stdev of assessment-to-assessment change, in points
PASS_MARK = 40.0              # subject pass mark (%), institution configurable
CONCERN_LEVEL = 60.0          # below this a declining trend raises a warning
CRITICAL_LEVEL = 50.0         # below this a warning is raised regardless of trend
PEAK_DROP_WARNING = 12.0      # points lost from the student's best assessment

RECENT_WINDOW = 3             # how many assessments count as "recent"

RISK_WEIGHTS = {"level": 0.55, "trend": 0.30, "volatility": 0.15}
RISK_BANDS = {"High": 0.50, "Medium": 0.32}   # score >= threshold -> that band


# --------------------------------------------------------------------------- #
# trend detection
# --------------------------------------------------------------------------- #
def _slope(values: Sequence[float]) -> float:
    """Least-squares slope in percentage points per assessment.

    Written out rather than pulled from numpy so the arithmetic is inspectable:
    slope = sum((x - x̄)(y - ȳ)) / sum((x - x̄)²).
    """
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(values) / n
    denominator = sum((x - mx) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, values)) / denominator


def classify_trend(values: Sequence[float]) -> dict:
    """Classify a chronological series as Improving / Declining / Stable / Volatile.

    Order of the checks matters and is deliberate: a series that swings wildly is
    called Volatile even if its fitted line happens to slope, because the line is
    not describing it well.
    """
    values = [float(v) for v in values]
    n = len(values)
    if n == 0:
        return {"trend": "No data", "slope": 0.0, "volatility": 0.0,
                "confidence": "none", "n_points": 0,
                "description": "No assessment results recorded yet."}
    if n < MIN_POINTS_FOR_TREND:
        return {"trend": "Insufficient data", "slope": 0.0, "volatility": 0.0,
                "confidence": "low", "n_points": n,
                "description": f"Only {n} assessment(s) recorded; at least "
                               f"{MIN_POINTS_FOR_TREND} are needed before a trend is meaningful."}

    slope = _slope(values)
    deltas = [b - a for a, b in zip(values, values[1:])]
    volatility = statistics.pstdev(deltas) if len(deltas) > 1 else abs(deltas[0])

    if volatility >= VOLATILITY_HIGH and abs(slope) < SLOPE_STRONG:
        trend = "Volatile"
        description = (f"Scores swing by about {volatility:.1f} points between assessments "
                       "with no clear direction.")
    elif slope >= SLOPE_STRONG:
        trend = "Strongly improving"
        description = f"Strong improvement trend detected: about +{slope:.1f} points per assessment."
    elif slope >= SLOPE_STABLE:
        trend = "Improving"
        description = f"Gradual improvement of about +{slope:.1f} points per assessment."
    elif slope <= -SLOPE_STRONG:
        trend = "Strongly declining"
        description = (f"Declining performance detected across recent assessments: about "
                       f"{slope:.1f} points per assessment.")
    elif slope <= -SLOPE_STABLE:
        trend = "Declining"
        description = f"Gradual decline of about {slope:.1f} points per assessment."
    else:
        trend = "Stable"
        description = f"Performance is stable (change of {slope:+.1f} points per assessment)."

    return {
        "trend": trend,
        "direction": "up" if slope >= SLOPE_STABLE else "down" if slope <= -SLOPE_STABLE else "flat",
        "slope": round(slope, 2),
        "volatility": round(volatility, 2),
        "confidence": "medium" if n < 5 else "high",
        "n_points": n,
        "description": description,
        "thresholds": {"stable_slope": SLOPE_STABLE, "strong_slope": SLOPE_STRONG,
                       "high_volatility": VOLATILITY_HIGH},
    }


# --------------------------------------------------------------------------- #
# subject performance
# --------------------------------------------------------------------------- #
def summarise_series(results: list[dict]) -> dict:
    """Descriptive statistics over one subject's chronological results."""
    values = [float(r["percentage"]) for r in results]
    if not values:
        return {"n_assessments": 0, "current": None, "average": None,
                "recent_average": None, "best": None, "worst": None,
                "consistency": None, "delta_from_average": None}
    recent = values[-RECENT_WINDOW:]
    return {
        "n_assessments": len(values),
        "current": round(values[-1], 1),
        "average": round(sum(values) / len(values), 1),
        "recent_average": round(sum(recent) / len(recent), 1),
        "best": round(max(values), 1),
        "worst": round(min(values), 1),
        # Consistency: 100 minus the spread of assessment-to-assessment changes,
        # floored at 0. A student who scores the same every time gets 100.
        "consistency": round(max(0.0, 100.0 - (statistics.pstdev(values) * 2 if len(values) > 1 else 0)), 1),
        "delta_from_average": round(values[-1] - sum(values) / len(values), 1),
    }


def subject_risk(summary: dict, trend: dict) -> dict:
    """Rule-based subject risk. Distinct from the ML risk classifier, which
    predicts an overall academic risk tier from the trained model - this one is a
    transparent per-subject rule over the assessment series."""
    if summary["current"] is None:
        return {"risk": "Unknown", "score": None,
                "reason": "No assessment results recorded for this subject."}

    current = summary["recent_average"]
    level_component = max(0.0, min(1.0, (75.0 - current) / 45.0))     # 75% -> 0, 30% -> 1
    slope = trend.get("slope", 0.0)
    trend_component = max(0.0, min(1.0, -slope / SLOPE_STRONG)) if slope < 0 else 0.0
    volatility_component = max(0.0, min(1.0, trend.get("volatility", 0.0) / (VOLATILITY_HIGH * 2)))

    score = (RISK_WEIGHTS["level"] * level_component
             + RISK_WEIGHTS["trend"] * trend_component
             + RISK_WEIGHTS["volatility"] * volatility_component)

    risk = "High" if score >= RISK_BANDS["High"] else "Medium" if score >= RISK_BANDS["Medium"] else "Low"

    reasons = [f"recent average {current:.0f}%"]
    if trend_component > 0:
        reasons.append(f"{trend['trend'].lower()} trend ({slope:+.1f} points per assessment)")
    if volatility_component > 0.4:
        reasons.append(f"inconsistent scores (swing of {trend['volatility']:.0f} points)")

    return {
        "risk": risk,
        "score": round(score, 3),
        "components": {
            "level": round(level_component, 3),
            "trend": round(trend_component, 3),
            "volatility": round(volatility_component, 3),
        },
        "weights": RISK_WEIGHTS,
        "bands": RISK_BANDS,
        "reason": "Risk driven by " + ", ".join(reasons) + ".",
        "method": "rule-based over the assessment series (not the ML risk classifier)",
    }


def subject_performance(student_id: str, subject_id: str | None = None) -> list[dict]:
    """Per-subject academic summary: history, trend, risk."""
    results = academics_db.student_results(student_id, subject_id)
    by_subject: dict[str, list[dict]] = {}
    for r in results:
        by_subject.setdefault(r["subject_id"], []).append(r)

    out = []
    for sid, rows in by_subject.items():
        rows.sort(key=lambda r: r["assessment_order"])
        values = [float(r["percentage"]) for r in rows]
        summary = summarise_series(rows)
        trend = classify_trend(values)
        risk = subject_risk(summary, trend)
        out.append({
            "subject_id": sid,
            "subject_name": rows[0].get("subject_name") or (
                subject_name(sid) if sid in SUBJECTS else sid),
            "summary": summary,
            "trend": trend,
            "risk": risk,
            "assessments": [
                {
                    "assessment_id": r["assessment_id"],
                    "name": r["name"],
                    "type": r["assessment_type"],
                    "order": r["assessment_order"],
                    "marks": round(float(r["marks"]), 1),
                    "max_marks": float(r["max_marks"]),
                    "percentage": round(float(r["percentage"]), 1),
                    "source": r["source"],
                }
                for r in rows
            ],
        })
    out.sort(key=lambda s: (s["risk"]["score"] is None, -(s["risk"]["score"] or 0)))
    return out


def academic_overview(student_id: str) -> dict:
    """The Academic Overview table: subject, current, trend, risk."""
    subjects = subject_performance(student_id)
    if not subjects:
        return {
            "student_id": student_id, "subjects": [], "overall": None,
            "message": "No assessment results recorded for this student yet.",
        }

    currents = [s["summary"]["recent_average"] for s in subjects if s["summary"]["recent_average"] is not None]
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for s in subjects:
        if s["risk"]["risk"] in counts:
            counts[s["risk"]["risk"]] += 1

    strong = [s["subject_name"] for s in subjects if (s["summary"]["recent_average"] or 0) >= 75]
    weak = [s["subject_name"] for s in subjects if (s["summary"]["recent_average"] or 100) < 60]

    return {
        "student_id": student_id,
        "subjects": [
            {
                "subject_id": s["subject_id"],
                "subject_name": s["subject_name"],
                "current": s["summary"]["recent_average"],
                "latest": s["summary"]["current"],
                "average": s["summary"]["average"],
                "n_assessments": s["summary"]["n_assessments"],
                "trend": s["trend"]["trend"],
                "direction": s["trend"].get("direction", "flat"),
                "slope": s["trend"]["slope"],
                "risk": s["risk"]["risk"],
                "risk_reason": s["risk"]["reason"],
            }
            for s in subjects
        ],
        "overall": {
            "average_percentage": round(sum(currents) / len(currents), 1) if currents else None,
            "subjects_tracked": len(subjects),
            "risk_distribution": counts,
            "strong_subjects": strong,
            "weak_subjects": weak,
        },
        "message": None,
    }


# --------------------------------------------------------------------------- #
# early warning
# --------------------------------------------------------------------------- #
def early_warnings(student_id: str) -> dict:
    """Detect deterioration before a fail, with the evidence that triggered it.

    Triggers (all rule-based, all listed in the response):
      1. Declining trend AND recent average below CONCERN_LEVEL
      2. Recent average below CRITICAL_LEVEL, whatever the trend
      3. A drop of more than PEAK_DROP_WARNING points from the student's best
      4. High volatility below a comfortable level
    """
    subjects = subject_performance(student_id)
    warnings = []

    for s in subjects:
        summary, trend = s["summary"], s["trend"]
        if summary["current"] is None:
            continue
        recent = summary["recent_average"]
        fired = []

        if trend["trend"] in ("Declining", "Strongly declining") and recent < CONCERN_LEVEL:
            fired.append({
                "trigger": "declining_trend",
                "severity": "high" if trend["trend"] == "Strongly declining" else "medium",
                "detail": f"{trend['description']} Recent average is {recent:.0f}%, "
                          f"below the {CONCERN_LEVEL:.0f}% concern level.",
            })
        if recent < CRITICAL_LEVEL:
            fired.append({
                "trigger": "low_performance",
                "severity": "high",
                "detail": f"Recent average of {recent:.0f}% is below the "
                          f"{CRITICAL_LEVEL:.0f}% critical level (pass mark {PASS_MARK:.0f}%).",
            })
        drop = summary["best"] - recent
        if drop >= PEAK_DROP_WARNING:
            fired.append({
                "trigger": "drop_from_peak",
                "severity": "medium",
                "detail": f"Down {drop:.0f} points from a best of {summary['best']:.0f}%.",
            })
        if trend["trend"] == "Volatile" and recent < CONCERN_LEVEL + 10:
            fired.append({
                "trigger": "volatile_performance",
                "severity": "low",
                "detail": f"Inconsistent results: {trend['description']}",
            })

        if fired:
            severity = ("high" if any(f["severity"] == "high" for f in fired)
                        else "medium" if any(f["severity"] == "medium" for f in fired) else "low")
            warnings.append({
                "subject_id": s["subject_id"],
                "subject_name": s["subject_name"],
                "severity": severity,
                "recent_average": recent,
                "trend": trend["trend"],
                "series": [a["percentage"] for a in s["assessments"]],
                "assessment_names": [a["name"] for a in s["assessments"]],
                "triggers": fired,
                "why_at_risk": (
                    f"{s['subject_name']}: " + " ".join(f["detail"] for f in fired)
                ),
            })

    order = {"high": 0, "medium": 1, "low": 2}
    warnings.sort(key=lambda w: (order[w["severity"]], w["recent_average"]))

    return {
        "student_id": student_id,
        "warnings": warnings,
        "n_warnings": len(warnings),
        "highest_severity": warnings[0]["severity"] if warnings else None,
        "triggers_documented": {
            "declining_trend": f"declining trend and recent average < {CONCERN_LEVEL}%",
            "low_performance": f"recent average < {CRITICAL_LEVEL}%",
            "drop_from_peak": f"drop of >= {PEAK_DROP_WARNING} points from the best score",
            "volatile_performance": f"volatile series with recent average < {CONCERN_LEVEL + 10}%",
        },
        "method": "rule-based detection over stored assessment results",
        "message": None if warnings else "No early warnings: no subject meets a trigger condition.",
    }


# --------------------------------------------------------------------------- #
# cohort views (teacher)
# --------------------------------------------------------------------------- #
def cohort_subject_analytics() -> dict:
    """Class-level view: subject averages, assessment trends, movers."""
    students = academics_db.students_with_results()
    per_subject: dict[str, dict] = {}
    declining, improving, high_risk = [], [], []

    for student_id in students:
        for s in subject_performance(student_id):
            sid = s["subject_id"]
            bucket = per_subject.setdefault(sid, {
                "subject_id": sid, "subject_name": s["subject_name"],
                "values": [], "risks": {"High": 0, "Medium": 0, "Low": 0},
                "trends": {},
            })
            if s["summary"]["recent_average"] is not None:
                bucket["values"].append(s["summary"]["recent_average"])
            risk = s["risk"]["risk"]
            if risk in bucket["risks"]:
                bucket["risks"][risk] += 1
            bucket["trends"][s["trend"]["trend"]] = bucket["trends"].get(s["trend"]["trend"], 0) + 1

            row = {
                "student_id": student_id,
                "subject_id": sid,
                "subject_name": s["subject_name"],
                "recent_average": s["summary"]["recent_average"],
                "trend": s["trend"]["trend"],
                "slope": s["trend"]["slope"],
                "risk": risk,
            }
            if s["trend"]["trend"] in ("Declining", "Strongly declining"):
                declining.append(row)
            if s["trend"]["trend"] in ("Improving", "Strongly improving"):
                improving.append(row)
            if risk == "High":
                high_risk.append(row)

    subjects = []
    for sid, bucket in per_subject.items():
        values = bucket["values"]
        subjects.append({
            "subject_id": sid,
            "subject_name": bucket["subject_name"],
            "students": len(values),
            "class_average": round(sum(values) / len(values), 1) if values else None,
            "lowest": round(min(values), 1) if values else None,
            "highest": round(max(values), 1) if values else None,
            "risk_distribution": bucket["risks"],
            "trend_distribution": bucket["trends"],
        })
    subjects.sort(key=lambda s: (s["class_average"] is None, s["class_average"]))

    declining.sort(key=lambda r: r["slope"])
    improving.sort(key=lambda r: -r["slope"])
    high_risk.sort(key=lambda r: r["recent_average"] or 0)

    return {
        "students_tracked": len(students),
        "subjects": subjects,
        "assessment_trends": [
            {
                "subject_id": a["subject_id"],
                "assessment": a["name"],
                "order": a["assessment_order"],
                "n_results": int(a["n_results"] or 0),
                "average": round(float(a["average_percentage"]), 1) if a["average_percentage"] is not None else None,
                "min": round(float(a["min_percentage"]), 1) if a["min_percentage"] is not None else None,
                "max": round(float(a["max_percentage"]), 1) if a["max_percentage"] is not None else None,
            }
            for a in academics_db.assessment_averages()
        ],
        "declining_students": declining[:25],
        "improving_students": improving[:25],
        "high_risk_students": high_risk[:25],
    }
