"""Practice endpoints: recommended practice, session lifecycle, history.

The closed loop the brief asks for lives in `submit()`:

    persist attempts -> recompute concept accuracy -> update learning state
    -> re-run root-cause propagation -> return the delta and the new diagnosis

Every value in that response is computed server side from stored attempts. The
frontend renders the payload and derives nothing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import authorise_student, current_user
from app.database import db, practice_db
from app.graph import root_cause
from app.graph.knowledge_graph import CONCEPTS, label
from app.ml import predictor
from app.practice import config, mastery_update, scoring, selector
from app.schemas.models import PracticeStartRequest, PracticeSubmitRequest
from app.services import pipeline

router = APIRouter(prefix="/api/practice", tags=["practice"])


def _load_student_or_404(student_id: str) -> dict:
    try:
        return pipeline.load_student(student_id)
    except pipeline.StudentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


def _risk_tier(features: dict) -> str:
    """Predicted risk feeds the recommendation weighting. If the model bundle is
    missing the rest of the practice system must still work, so degrade to
    Medium rather than 503 the whole page."""
    try:
        return predictor.predict(features)["risk_tier"]
    except predictor.ModelNotTrainedError:
        return "Medium"


@router.get("/config")
def practice_config() -> dict:
    """The exact constants used for selection and the learning-state update."""
    return config.as_dict()


@router.get("/recommended/{student_id}")
def recommended(student_id: str, user: dict = Depends(current_user)) -> dict:
    """Feature 3 + 6 + 13: what to practise, how much, why, and what to read first."""
    authorise_student(user, student_id)
    student = _load_student_or_404(student_id)
    mastery, source = pipeline.ensure_mastery(student_id, student["features"])
    roots = root_cause.analyse(mastery)
    result = selector.recommended_practice(mastery, roots, _risk_tier(student["features"]))
    return {
        "student_id": student_id,
        "mastery_source": source,
        "root_causes": [
            {"concept": r["concept"], "label": r["label"], "mastery": r["mastery"]}
            for r in roots["root_causes"][:3]
        ],
        **result,
    }


@router.post("/start", status_code=201)
def start(payload: PracticeStartRequest,
          student_id: str = Query(..., min_length=2, max_length=32),
          user: dict = Depends(current_user)) -> dict:
    """Open a session and serve questions without their answers."""
    authorise_student(user, student_id)
    _load_student_or_404(student_id)

    if payload.concept not in CONCEPTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Unknown concept '{payload.concept}'")

    questions = selector.build_session_questions(
        student_id, payload.concept, payload.difficulty, payload.count
    )
    if not questions:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No questions in the bank for '{label(payload.concept)}'"
            + (f" at {payload.difficulty} difficulty" if payload.difficulty else ""),
        )

    session_id = practice_db.create_session(
        student_id=student_id,
        concept=payload.concept,
        difficulty=payload.difficulty,
        origin=payload.origin,
        n_requested=payload.count,
        served=[q["question_id"] for q in questions],
    )

    return {
        "session_id": session_id,
        "concept": payload.concept,
        "label": label(payload.concept),
        "difficulty": payload.difficulty,
        "requested": payload.count,
        "served": len(questions),
        "questions": [
            {
                "question_id": q["question_id"],
                "subject": q["subject"],
                "concept": q["concept"],
                "difficulty": q["difficulty"],
                "question_type": q["question_type"],
                "question_text": q["question_text"],
                "options": q["options"],
                "marks": q["marks"],
            }
            for q in questions
        ],
    }


@router.post("/submit")
def submit(payload: PracticeSubmitRequest, user: dict = Depends(current_user)) -> dict:
    """Grade a session, update the learning state and recompute the diagnosis."""
    session = practice_db.get_session(payload.session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Practice session not found")

    student_id = session["student_id"]
    authorise_student(user, student_id)
    if session["completed_at"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "This session has already been submitted")

    served = set(session["served_questions"] or [])
    submitted = [a for a in payload.answers if not served or a.question_id in served]
    if not submitted:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "No submitted answer belongs to this session")

    student = _load_student_or_404(student_id)
    mastery_before, _ = pipeline.ensure_mastery(student_id, student["features"])
    roots_before = root_cause.analyse(mastery_before)

    graded, feedback = [], []
    for answer in submitted:
        question = practice_db.get_question(answer.question_id, include_answer=True)
        if not question:
            continue
        try:
            is_correct, graded_by = scoring.grade(
                question, answer.selected_answer, answer.self_marked_correct
            )
        except scoring.GradingError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

        score, max_score = scoring.score_attempt(question, is_correct)
        graded.append({
            "question_id": question["question_id"],
            "concept": question["concept"],
            "difficulty": question["difficulty"],
            "question_type": question["question_type"],
            "selected_answer": answer.selected_answer,
            "is_correct": is_correct,
            "score": score,
            "max_score": max_score,
            "time_taken": answer.time_taken,
            "graded_by": graded_by,
        })
        feedback.append({
            "question_id": question["question_id"],
            "concept": question["concept"],
            "label": label(question["concept"]) if question["concept"] in CONCEPTS else question["concept"],
            "difficulty": question["difficulty"],
            "question_type": question["question_type"],
            "question_text": question["question_text"],
            "your_answer": answer.selected_answer,
            "correct_answer": question["correct_answer"],
            "is_correct": is_correct,
            "graded_by": graded_by,
            "explanation": question["explanation"],
            "score": score,
            "max_score": max_score,
        })

    if not graded:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "None of the submitted question ids exist")

    practice_db.record_attempts(payload.session_id, student_id, graded)

    # Feature 8 + 9: practice evidence moves the learning state, then the graph
    # re-runs against the updated values.
    changes = mastery_update.apply(student_id, graded, mastery_before, payload.session_id)
    mastery_after, source_after = pipeline.mastery_map(student_id)
    roots_after = root_cause.analyse(mastery_after)

    before_top = [r["concept"] for r in roots_before["root_causes"][:3]]
    after_top = [r["concept"] for r in roots_after["root_causes"][:3]]

    return {
        "session_id": payload.session_id,
        "student_id": student_id,
        "summary": scoring.summarise(graded, payload.elapsed_seconds),
        "results": feedback,
        "mastery_update": {
            "changes": changes,
            "source": source_after,
            "config": config.as_dict()["mastery_update"],
            "note": (
                "Mastery here is an application-maintained learning-state estimate, "
                "not a validated assessment score. It does not feed the GPA, pass "
                "probability or risk models, so your prediction and its SHAP "
                "explanation are unchanged by this session."
            ),
        },
        "root_cause": {
            "before": before_top,
            "after": after_top,
            "changed": before_top != after_top,
            "current": roots_after["root_causes"][:3],
        },
    }


@router.get("/history/{student_id}")
def history(student_id: str, limit: int = Query(25, ge=1, le=100),
            user: dict = Depends(current_user)) -> dict:
    authorise_student(user, student_id)
    sessions = practice_db.session_history(student_id, limit)
    for s in sessions:
        if s["concept"] in CONCEPTS:
            s["label"] = label(s["concept"])
    return {
        "student_id": student_id,
        "sessions": sessions,
        "totals": practice_db.totals_for_student(student_id),
    }


@router.get("/performance/{student_id}")
def performance(student_id: str, user: dict = Depends(current_user)) -> dict:
    """Feature 7: concept-level practice statistics, plus the mastery trajectory."""
    authorise_student(user, student_id)
    stats = practice_db.concept_stats(student_id)
    current = {r["concept"]: r["mastery"] for r in db.get_mastery(student_id)}
    for row in stats:
        if row["concept"] in CONCEPTS:
            row["label"] = label(row["concept"])
        row["current_mastery"] = current.get(row["concept"])
    return {
        "student_id": student_id,
        "concepts": stats,
        "totals": practice_db.totals_for_student(student_id),
        "mastery_history": practice_db.mastery_history(student_id, limit=100),
    }
