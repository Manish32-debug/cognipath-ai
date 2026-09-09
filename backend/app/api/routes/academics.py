"""Multi-subject academic record endpoints.

Route files stay thin (Part 21): every calculation lives in
`app.services.academics`, `app.ml.assessment_features` or
`app.recommendations.context`. These handlers validate, authorise and assemble.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.api.deps import authorise_student, current_user, require_teacher
from app.database import academics_db, db, practice_db
from app.graph import root_cause
from app.graph.knowledge_graph import (
    GraphError,
    label as concept_label,
    SUBJECTS,
    concepts_for_subject,
    subject_catalogue,
    subject_graph_payload,
    subject_of,
    unit_of,
)
from app.ml import assessment_features
from app.practice import selector
from app.recommendations import context as context_rules
from app.schemas.models import (
    AssessmentCreate,
    AssessmentResultEntry,
    BulkAssessmentResults,
    SubjectCreate,
)
from app.services import academics, pipeline

router = APIRouter(prefix="/api", tags=["academics"])


def _student_or_404(student_id: str) -> dict:
    try:
        return pipeline.load_student(student_id)
    except pipeline.StudentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


def _known_subject(subject_id: str) -> None:
    if subject_id not in SUBJECTS and academics_db.get_subject(subject_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown subject '{subject_id}'")


# --------------------------------------------------------------------------- #
# subjects and curriculum
# --------------------------------------------------------------------------- #
@router.get("/subjects")
def list_subjects() -> dict:
    """Subjects with their unit -> concept tree. Public: it is curriculum, not data."""
    stored = {s["subject_id"]: s for s in academics_db.list_subjects()}
    catalogue = subject_catalogue()
    for entry in catalogue:
        row = stored.get(entry["id"])
        if row:
            entry.update({"semester": row["semester"], "credits": row["credits"]})
        entry["assessments"] = len(academics_db.list_assessments(entry["id"]))
    return {"count": len(catalogue), "subjects": catalogue}


@router.post("/subjects", status_code=201)
def create_subject(payload: SubjectCreate, user: dict = Depends(require_teacher)) -> dict:
    """Add or update a subject.

    A subject added here appears immediately in assessments, analytics and the
    dashboards. Its concepts, however, come from the knowledge graph module: a
    brand-new subject has no concepts until they are added there, and the
    response says so rather than pretending otherwise.
    """
    academics_db.upsert_subject(payload.model_dump())
    return {
        "subject_id": payload.subject_id,
        "status": "saved",
        "concepts_in_graph": len(concepts_for_subject(payload.subject_id))
        if payload.subject_id in SUBJECTS else 0,
        "note": None if payload.subject_id in SUBJECTS else (
            "This subject has no concepts in the knowledge graph yet, so concept "
            "mastery, root-cause analysis and practice will be empty for it until "
            "concepts are added to app/graph/knowledge_graph.py."
        ),
    }


@router.get("/subjects/{subject_id}/concepts")
def subject_concepts(subject_id: str) -> dict:
    _known_subject(subject_id)
    try:
        ids = concepts_for_subject(subject_id)
    except GraphError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    counts = practice_db.question_counts_by_concept()
    from app.graph.knowledge_graph import CONCEPTS

    return {
        "subject_id": subject_id,
        "concepts": [
            {
                "id": cid,
                "label": CONCEPTS[cid][0],
                "unit": unit_of(cid),
                "description": CONCEPTS[cid][2],
                "questions_in_bank": sum(counts.get(cid, {}).values()),
            }
            for cid in ids
        ],
    }


@router.get("/subjects/{subject_id}/knowledge-graph")
def subject_knowledge_graph(subject_id: str) -> dict:
    """One subject's prerequisite DAG, plus the edges reaching in from elsewhere."""
    _known_subject(subject_id)
    try:
        return subject_graph_payload(subject_id)
    except GraphError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


# --------------------------------------------------------------------------- #
# assessments (teacher-managed configuration)
# --------------------------------------------------------------------------- #
@router.get("/assessments")
def list_assessments(subject_id: str | None = None, user: dict = Depends(current_user)) -> dict:
    if subject_id:
        _known_subject(subject_id)
    return {
        "assessment_types": academics_db.list_assessment_types(),
        "assessments": academics_db.list_assessments(subject_id),
    }


@router.post("/assessments", status_code=201)
def create_assessment(payload: AssessmentCreate, user: dict = Depends(require_teacher)) -> dict:
    _known_subject(payload.subject_id)
    known_types = {t["type_id"] for t in academics_db.list_assessment_types()}
    if payload.assessment_type not in known_types:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown assessment type '{payload.assessment_type}'. Known types: {sorted(known_types)}",
        )
    assessment_id = academics_db.upsert_assessment(payload.model_dump())
    return {"assessment_id": assessment_id, "status": "saved"}


@router.delete("/assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_class=Response)
def delete_assessment(assessment_id: int, user: dict = Depends(require_teacher)) -> Response:
    if not academics_db.delete_assessment(assessment_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Assessment {assessment_id} not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/assessments/{assessment_id}/results", status_code=201)
def record_result(assessment_id: int, payload: AssessmentResultEntry,
                  user: dict = Depends(require_teacher)) -> dict:
    if academics_db.get_assessment(assessment_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Assessment {assessment_id} not found")
    _student_or_404(payload.student_id)
    try:
        return academics_db.record_result(payload.student_id, assessment_id,
                                          payload.marks, source="entered")
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.post("/assessments/results/bulk", status_code=201)
def record_results_bulk(payload: BulkAssessmentResults,
                        user: dict = Depends(require_teacher)) -> dict:
    try:
        written = academics_db.record_results_bulk(
            [r.model_dump() | {"source": "entered"} for r in payload.results]
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return {"recorded": written}


# --------------------------------------------------------------------------- #
# student academic views
# --------------------------------------------------------------------------- #
@router.get("/students/{student_id}/academics")
def student_academics(student_id: str, user: dict = Depends(current_user)) -> dict:
    """Academic Overview: subject, current, trend, risk - plus the ML prediction
    driven by the same assessment history."""
    authorise_student(user, student_id)
    student = _student_or_404(student_id)
    overview = academics.academic_overview(student_id)
    try:
        prediction = assessment_features.overall_prediction(student_id, student["features"])
    except Exception as exc:  # model bundle missing must not blank the page
        prediction = {"prediction": None, "error": str(exc)}
    return {
        **overview,
        "ml_prediction": prediction,
        "provenance": assessment_features.feature_provenance(),
    }


@router.get("/students/{student_id}/academics/{subject_id}")
def student_subject_detail(student_id: str, subject_id: str,
                           user: dict = Depends(current_user)) -> dict:
    """Everything for one subject: history, trend, risk, mastery, root causes,
    recommendations, practice plan, resources and context advice."""
    authorise_student(user, student_id)
    _known_subject(subject_id)
    student = _student_or_404(student_id)

    performance = academics.subject_performance(student_id, subject_id)
    detail = performance[0] if performance else None

    mastery, mastery_source = pipeline.ensure_mastery(student_id, student["features"])
    subject_concepts_ids = set(concepts_for_subject(subject_id)) if subject_id in SUBJECTS else set()
    subject_mastery = {c: m for c, m in mastery.items() if c in subject_concepts_ids}

    # Root cause is run over the FULL graph, then filtered to this subject's view,
    # so a Mathematics prerequisite can still be named as the cause of a DSP gap.
    roots_full = root_cause.analyse(mastery)
    roots_here = [r for r in roots_full.get("root_causes", [])
                  if r["concept"] in subject_concepts_ids
                  or any(a["concept"] in subject_concepts_ids
                         for a in r.get("affected_concepts", []))]

    try:
        risk_tier = assessment_features.subject_prediction(
            student_id, student["features"], subject_id)
    except Exception:
        risk_tier = None
    tier = (risk_tier or {}).get("prediction", {}).get("risk_tier", "Medium")

    plan = selector.recommended_practice(mastery, roots_full, tier, subject=subject_id)

    stats = {s["concept"]: s for s in practice_db.concept_stats(student_id)}
    subject_attempts = [s for c, s in stats.items() if c in subject_concepts_ids]
    attempted = sum(int(s["attempted"]) for s in subject_attempts)
    correct = sum(int(s["correct"]) for s in subject_attempts)

    advice = context_rules.advise({
        "attendance_pct": student["features"].get("attendance_pct"),
        "studytime": student["features"].get("studytime"),
        "trend": detail["trend"]["trend"] if detail else None,
        "recent_average": detail["summary"]["recent_average"] if detail else None,
        "average_mastery": (sum(subject_mastery.values()) / len(subject_mastery)
                            if subject_mastery else None),
        "practice_accuracy": (correct / attempted) if attempted else None,
        "n_practice_attempts": attempted,
    })

    return {
        "student_id": student_id,
        "subject_id": subject_id,
        "performance": detail,
        "ml_prediction": risk_tier,
        "mastery": {
            "source": mastery_source,
            "average": round(sum(subject_mastery.values()) / len(subject_mastery), 1)
            if subject_mastery else None,
            "concepts": sorted(
                [
                    {"concept": c, "label": concept_label(c), "unit": unit_of(c),
                     "mastery": m, "risk": root_cause.risk_label(m)}
                    for c, m in subject_mastery.items()
                ],
                key=lambda x: x["mastery"],
            ),
        },
        "root_causes": roots_here[:3],
        "practice_plan": plan,
        "practice_performance": {
            "attempted": attempted,
            "correct": correct,
            "accuracy": round(correct / attempted, 4) if attempted else None,
        },
        "context_advice": advice,
        "advice_rules": context_rules.rule_table(),
    }


@router.get("/students/{student_id}/early-warnings")
def student_early_warnings(student_id: str, user: dict = Depends(current_user)) -> dict:
    """Why am I at risk, and what should I do next."""
    authorise_student(user, student_id)
    student = _student_or_404(student_id)
    warnings = academics.early_warnings(student_id)

    mastery, _ = pipeline.ensure_mastery(student_id, student["features"])
    roots = root_cause.analyse(mastery)

    # Attach the likely concept-level cause inside each warned subject, and a
    # concrete next step. Both come from existing modules - nothing new is invented.
    for warning in warnings["warnings"]:
        sid = warning["subject_id"]
        concepts = set(concepts_for_subject(sid)) if sid in SUBJECTS else set()
        candidates = [r for r in roots.get("root_causes", []) if r["concept"] in concepts]
        if not candidates and concepts:
            # The global ranking is capped, and one subject can crowd out the rest.
            # Re-run the same propagation over this subject's concepts plus their
            # upstream prerequisites, so a warning always names a concept if one
            # is weak - including a prerequisite that lives in another subject.
            from app.graph.knowledge_graph import get_graph
            import networkx as nx

            graph = get_graph()
            scoped = set(concepts)
            for c in concepts:
                if c in graph:
                    scoped |= nx.ancestors(graph, c)
            local = root_cause.analyse({c: m for c, m in mastery.items() if c in scoped})
            candidates = local.get("root_causes", [])
        warning["likely_root_cause"] = (
            {
                "concept": candidates[0]["concept"],
                "label": candidates[0]["label"],
                "mastery": candidates[0]["mastery"],
                "reasoning": candidates[0]["reasoning"],
                "method": "graph-based prerequisite propagation",
            }
            if candidates else None
        )
        warning["what_to_do_next"] = [
            f"Revise {candidates[0]['label']} before moving on"
            if candidates else f"Revise the weakest concepts in {warning['subject_name']}",
            "Work through the recommended study material for that concept",
            "Practise 10 questions at the difficulty matched to your mastery",
            "Re-check this warning after the next assessment",
        ]
    return warnings


@router.get("/students/{student_id}/academics/{subject_id}/prediction")
def subject_prediction(student_id: str, subject_id: str,
                       user: dict = Depends(current_user)) -> dict:
    authorise_student(user, student_id)
    _known_subject(subject_id)
    student = _student_or_404(student_id)
    result = assessment_features.subject_prediction(student_id, student["features"], subject_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"No assessment results recorded for '{subject_id}'")
    return result


# --------------------------------------------------------------------------- #
# teacher analytics
# --------------------------------------------------------------------------- #
@router.get("/teacher/subject-analytics")
def teacher_subject_analytics(user: dict = Depends(require_teacher)) -> dict:
    """Class average, subject performance, assessment trends and movers."""
    data = academics.cohort_subject_analytics()
    names = {s["student_id"]: s.get("display_name") for s in db.list_students()}
    for key in ("declining_students", "improving_students", "high_risk_students"):
        for row in data[key]:
            row["display_name"] = names.get(row["student_id"])
    return data


@router.get("/ml/provenance")
def ml_provenance() -> dict:
    """Which parts of the system are ML, graph-based, rule-based or derived."""
    return assessment_features.feature_provenance()
