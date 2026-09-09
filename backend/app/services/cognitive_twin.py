"""Cognitive Digital Twin.

Read this before the viva, because it is the part of the project most easily
overclaimed. None of the traits below are psychometrically measured. They are
INFERRED indices computed from behavioural columns that do exist (study time,
absences, past failures, grade trend) plus concept mastery. Every trait carries
`basis` (which inputs produced it) and `evidence_strength`, and the UI prints
"Estimated" next to each one.

`learning_style` is deliberately NOT inferred. There is no data in this project
that could support it, and the learning-styles hypothesis has weak empirical
support anyway (Pashler et al., 2008). It is shown only when the student states
it in their profile, otherwise "Not assessed".
"""

from __future__ import annotations

import numpy as np

from app.graph.knowledge_graph import topological_levels

BANDS = [(0, 35, "Low"), (35, 65, "Moderate"), (65, 101, "High")]


def _band(x: float) -> str:
    for lo, hi, name in BANDS:
        if lo <= x < hi:
            return name
    return "High"


def _trait(name: str, value: float, basis: str, strength: str) -> dict:
    v = float(np.clip(value, 0, 100))
    return {
        "trait": name,
        "value": round(v, 1),
        "band": _band(v),
        "status": "Estimated",
        "basis": basis,
        "evidence_strength": strength,
    }


def build(student: dict, mastery: dict[str, float], prediction: dict,
          root_result: dict) -> dict:
    g1 = float(student.get("G1", 0))
    g2 = float(student.get("G2", 0))
    studytime = float(student.get("studytime", 2))
    failures = float(student.get("failures", 0))
    freetime = float(student.get("freetime", 3))
    attendance = float(student.get("attendance_pct", 100.0))
    trend = g2 - g1

    # Learning speed: grade movement between the two assessed periods, normalised
    # per unit of weekly study effort. Improving on little study time = fast.
    speed = 50.0 + 12.0 * trend - 5.0 * (studytime - 2.0)
    speed_t = _trait(
        "Learning speed",
        speed,
        "Grade movement G2-G1 relative to reported weekly study time",
        "moderate" if abs(trend) >= 1 else "weak",
    )

    # Memory retention: how well early curriculum concepts are still held,
    # compared with recently taught ones.
    levels = topological_levels()
    early = [m for c, m in mastery.items() if levels.get(c, 0) <= 1]
    recent = [m for c, m in mastery.items() if levels.get(c, 0) >= 3]
    if early:
        retention = float(np.mean(early)) - 0.3 * max(0.0, float(np.mean(recent or early)) - float(np.mean(early)))
    else:
        retention = 50.0
    retention_t = _trait(
        "Memory retention",
        retention,
        "Mastery retained in foundational concepts versus recently taught concepts",
        "moderate" if early else "weak",
    )

    # Study consistency: attendance dominates, past failures penalise, declared
    # study time contributes.
    consistency = 0.6 * attendance + 10.0 * (studytime - 1) - 12.0 * failures
    consistency_t = _trait(
        "Study consistency",
        consistency,
        "Attendance %, weekly study time and number of past course failures",
        "moderate",
    )

    # Confidence proxy: prior failures and a falling grade trend erode it.
    confidence = 60.0 + 8.0 * trend - 15.0 * failures + 4.0 * (studytime - 2)
    confidence_t = _trait(
        "Confidence (proxy)",
        confidence,
        "Past failures and grade trend; a behavioural proxy, not a self-report",
        "weak",
    )

    engagement = 0.5 * attendance + 8.0 * (studytime - 1) - 4.0 * (freetime - 3)
    engagement_t = _trait(
        "Academic engagement",
        engagement,
        "Attendance, study time and reported free time",
        "moderate",
    )

    weak = root_result.get("weak_concepts", [])
    roots = root_result.get("root_causes", [])
    overall_mastery = float(np.mean(list(mastery.values()))) if mastery else None

    # --- multi-subject dimensions (upgrade) --------------------------------- #
    # Subject strengths and weaknesses come from the stored assessment record and
    # practice attempts. When a student has no assessment history the keys are
    # present but empty, rather than filled with placeholder values.
    subject_profile = _subject_profile(student.get("student_id"))

    return {
        "student_id": student.get("student_id"),
        "traits": [speed_t, retention_t, consistency_t, confidence_t, engagement_t],
        "learning_style": student.get("learning_style") or "Not assessed",
        "learning_style_note": (
            "Reported by the student. Not inferred by the system - no data in this "
            "project supports inferring a learning style."
        ),
        "academic_risk": prediction.get("risk_tier"),
        "predicted_gpa": prediction.get("predicted_gpa"),
        "pass_probability": prediction.get("pass_probability"),
        "overall_mastery": round(overall_mastery, 1) if overall_mastery is not None else None,
        "weak_concepts": [w["label"] for w in weak],
        "root_cause_concepts": [r["label"] for r in roots[:3]],
        "mastery_source": student.get("mastery_source", "unknown"),
        "strong_subjects": subject_profile["strong"],
        "weak_subjects": subject_profile["weak"],
        "subject_profile": subject_profile["subjects"],
        "practice_accuracy": subject_profile["practice_accuracy"],
        "practice_attempts": subject_profile["practice_attempts"],
        "disclaimer": (
            "All traits are estimated indices derived from academic and "
            "behavioural indicators. They are not psychometric measurements and "
            "must not be used for high-stakes decisions."
        ),
    }


def _subject_profile(student_id: str | None) -> dict:
    """Subject strengths, weaknesses and practice accuracy from stored data.

    Kept out of `build` so the twin still works for a student with no assessment
    history: this returns empty lists rather than inventing subjects. Imports are
    local to avoid a circular import (services.academics reads the graph, which
    this module also uses).
    """
    empty = {"strong": [], "weak": [], "subjects": [],
             "practice_accuracy": None, "practice_attempts": 0}
    if not student_id:
        return empty

    try:
        from app.database import practice_db
        from app.services import academics
    except Exception:  # pragma: no cover
        return empty

    try:
        performance = academics.subject_performance(student_id)
    except Exception:  # pragma: no cover - never break the twin over analytics
        performance = []

    subjects = [
        {
            "subject_id": s["subject_id"],
            "subject_name": s["subject_name"],
            "recent_average": s["summary"]["recent_average"],
            "trend": s["trend"]["trend"],
            "risk": s["risk"]["risk"],
        }
        for s in performance
    ]
    ranked = [s for s in subjects if s["recent_average"] is not None]
    ranked.sort(key=lambda s: -s["recent_average"])
    # 70% / 60% are the same bands the subject-risk rule uses, so the twin and the
    # Academic Overview cannot disagree about which subject is weak.
    strong = [s["subject_name"] for s in ranked if s["recent_average"] >= 70][:3]
    weak = [s["subject_name"] for s in reversed(ranked) if s["recent_average"] < 60][:3]

    try:
        totals = practice_db.totals_for_student(student_id)
        attempts = int(totals.get("attempted") or totals.get("attempts") or 0)
        correct = int(totals.get("correct") or 0)
    except Exception:  # pragma: no cover
        attempts, correct = 0, 0

    return {
        "strong": strong,
        "weak": weak,
        "subjects": subjects,
        "practice_accuracy": round(correct / attempts, 4) if attempts else None,
        "practice_attempts": attempts,
    }
