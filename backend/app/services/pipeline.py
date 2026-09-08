"""Orchestration: the end-to-end CogniPath pipeline for one student.

    student features -> ML prediction -> SHAP -> mastery -> graph root cause
    -> recommendations -> weekly plan -> cognitive twin
    -> recommended resources -> recommended practice

Practice performance feeds back into `concept_mastery`, so the next run of this
pipeline reasons over the updated learning state. Mastery is not an ML input, so
that feedback changes the graph half of the pipeline (root cause, recommendations,
plan, twin) and never the prediction or its SHAP explanation.

Every stage calls the real component. Nothing in this module fabricates a value.
"""

from __future__ import annotations

import numpy as np

from app.database import db, practice_db
from app.graph import root_cause
from app.ml import predictor
from app.ml.mastery_simulator import mastery_records
from app.practice import selector
from app.recommendations import engine, study_plan
from app.services import cognitive_twin


class StudentNotFound(LookupError):
    pass


def load_student(student_id: str) -> dict:
    student = db.get_student(student_id)
    if not student:
        raise StudentNotFound(f"No student with id '{student_id}'")
    return student


def mastery_map(student_id: str) -> tuple[dict[str, float], str]:
    rows = db.get_mastery(student_id)
    if not rows:
        return {}, "none"
    sources = {r["source"] for r in rows}
    source = sources.pop() if len(sources) == 1 else "mixed"
    return {r["concept"]: float(r["mastery"]) for r in rows}, source


def ensure_mastery(student_id: str, features: dict) -> tuple[dict[str, float], str]:
    """Return stored mastery; for demo students without any, simulate and store it."""
    mastery, source = mastery_map(student_id)
    if mastery:
        return mastery, source
    records = mastery_records(
        student_id,
        g1=features.get("G1", 10),
        g2=features.get("G2", 10),
        studytime=features.get("studytime", 2),
        failures=features.get("failures", 0),
        attendance_pct=features.get("attendance_pct", 90),
    )
    db.set_mastery(student_id, records)
    return {r["concept"]: r["mastery"] for r in records}, "simulated"


def run(student_id: str, log: bool = True, explain_task: str = "gpa") -> dict:
    student = load_student(student_id)
    features = student["features"]

    prediction = predictor.predict(features)
    explanation = predictor.explain(features, task=explain_task)
    mastery, source = ensure_mastery(student_id, features)
    roots = root_cause.analyse(mastery)
    recs = engine.recommend(mastery, roots, prediction["risk_tier"])
    plan = study_plan.generate(
        recs,
        studytime=int(features.get("studytime", 2)),
        freetime=int(features.get("freetime", 3)),
        risk_tier=prediction["risk_tier"],
    )
    twin = cognitive_twin.build(
        {**features, "student_id": student_id,
         "learning_style": student.get("learning_style"),
         "mastery_source": source},
        mastery,
        prediction,
        roots,
    )

    practice = {
        "recommended": selector.recommended_practice(mastery, roots, prediction["risk_tier"]),
        "totals": practice_db.totals_for_student(student_id),
        "recent_sessions": practice_db.session_history(student_id, limit=5),
        "concept_stats": practice_db.concept_stats(student_id),
    }

    if log:
        db.log_prediction(
            student_id,
            prediction["predicted_gpa"],
            prediction["pass_probability"],
            prediction["risk_tier"],
        )

    return {
        "student": {
            "student_id": student_id,
            "display_name": student.get("display_name"),
            "is_demo": bool(student.get("is_demo")),
            "features": features,
        },
        "prediction": prediction,
        "explanation": explanation,
        "mastery": {
            "source": source,
            "overall": round(float(np.mean(list(mastery.values()))), 1) if mastery else None,
            "concepts": [
                {
                    "concept": c,
                    "mastery": m,
                    "risk": root_cause.risk_label(m),
                    "source": source,
                }
                for c, m in mastery.items()
            ],
        },
        "root_cause": roots,
        "recommendations": recs,
        "study_plan": plan,
        "cognitive_twin": twin,
        "practice": practice,
    }


def cohort_analytics() -> dict:
    """Teacher-side aggregation. Runs the real models over every stored student."""
    students = db.list_students()
    rows, risk_counts = [], {"Low": 0, "Medium": 0, "High": 0}
    concept_gap_totals: dict[str, list[float]] = {}

    for s in students:
        sid = s["student_id"]
        features = s["features"]
        prediction = predictor.predict(features)
        mastery, source = ensure_mastery(sid, features)
        roots = root_cause.analyse(mastery)
        overall = float(np.mean(list(mastery.values()))) if mastery else 0.0
        top_root = roots["root_causes"][0]["label"] if roots["root_causes"] else None

        for concept, m in mastery.items():
            concept_gap_totals.setdefault(concept, []).append(m)

        risk_counts[prediction["risk_tier"]] = risk_counts.get(prediction["risk_tier"], 0) + 1
        rows.append(
            {
                "student_id": sid,
                "display_name": s.get("display_name"),
                "predicted_gpa": prediction["predicted_gpa"],
                "pass_probability": prediction["pass_probability"],
                "risk_tier": prediction["risk_tier"],
                "attendance_pct": round(float(features.get("attendance_pct", 0)), 1),
                "studytime": features.get("studytime"),
                "failures": features.get("failures"),
                "overall_mastery": round(overall, 1),
                "weak_concepts": len(roots["weak_concepts"]),
                "top_root_cause": top_root,
                "mastery_source": source,
            }
        )

    rows.sort(key=lambda r: r["predicted_gpa"])
    n = len(rows) or 1
    from app.graph.knowledge_graph import label as concept_label

    concept_summary = sorted(
        [
            {
                "concept": c,
                "label": concept_label(c),
                "average_mastery": round(float(np.mean(v)), 1),
                "students_below_target": int(sum(1 for m in v if m < root_cause.MASTERY_TARGET)),
            }
            for c, v in concept_gap_totals.items()
        ],
        key=lambda d: d["average_mastery"],
    )

    return {
        "total_students": len(rows),
        "risk_distribution": risk_counts,
        "average_predicted_gpa": round(sum(r["predicted_gpa"] for r in rows) / n, 2),
        "average_attendance": round(sum(r["attendance_pct"] for r in rows) / n, 1),
        "average_mastery": round(sum(r["overall_mastery"] for r in rows) / n, 1),
        "students_requiring_intervention": [r for r in rows if r["risk_tier"] == "High"][:20],
        "concept_summary": concept_summary,
        "students": rows,
    }
