from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import authorise_student, current_user, require_teacher
from app.database import db
from app.ml import features as F
from app.schemas.models import MasteryUpdate, StudentCreate
from app.services import pipeline

router = APIRouter(prefix="/api/students", tags=["students"])


def _features_dict(payload: StudentCreate) -> dict:
    data = payload.features.model_dump()
    if data.get("attendance_pct") is None:
        data["attendance_pct"] = 100.0 * (
            1.0 - min(data["absences"], F.TERM_SESSIONS) / F.TERM_SESSIONS
        )
    data["grade_trend"] = data["G2"] - data["G1"]
    return data


@router.get("")
def list_students(user: dict = Depends(require_teacher)) -> list[dict]:
    return [
        {
            "student_id": s["student_id"],
            "display_name": s["display_name"],
            "is_demo": bool(s["is_demo"]),
            "updated_at": s["updated_at"],
        }
        for s in db.list_students()
    ]


@router.post("", status_code=201)
def create_student(payload: StudentCreate, user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "teacher" and user.get("student_id") != payload.student_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Students may only create or update their own record")
    features = _features_dict(payload)
    db.upsert_student(payload.student_id, features, payload.display_name,
                      is_demo=False, learning_style=payload.learning_style)
    if payload.mastery:
        db.set_mastery(payload.student_id, [m.model_dump() for m in payload.mastery])
    return {"student_id": payload.student_id, "status": "saved",
            "mastery_records": len(payload.mastery or [])}


@router.get("/{student_id}")
def get_student(student_id: str, user: dict = Depends(current_user)) -> dict:
    authorise_student(user, student_id)
    student = db.get_student(student_id)
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Student '{student_id}' not found")
    return student


@router.get("/{student_id}/mastery")
def get_mastery(student_id: str, user: dict = Depends(current_user)) -> dict:
    authorise_student(user, student_id)
    if not db.get_student(student_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Student '{student_id}' not found")
    records = db.get_mastery(student_id)
    return {"student_id": student_id, "records": records, "count": len(records)}


@router.put("/{student_id}/mastery")
def update_mastery(student_id: str, payload: MasteryUpdate,
                   user: dict = Depends(current_user)) -> dict:
    authorise_student(user, student_id)
    if not db.get_student(student_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Student '{student_id}' not found")
    from app.graph.knowledge_graph import CONCEPTS

    unknown = [r.concept for r in payload.records if r.concept not in CONCEPTS]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Unknown concepts: {unknown}")
    db.set_mastery(student_id, [r.model_dump() for r in payload.records])
    return {"student_id": student_id, "updated": len(payload.records)}


@router.get("/{student_id}/history")
def history(student_id: str, user: dict = Depends(current_user)) -> dict:
    authorise_student(user, student_id)
    return {"student_id": student_id, "history": db.prediction_history(student_id)}


@router.get("/{student_id}/dashboard")
def dashboard(student_id: str, user: dict = Depends(current_user)) -> dict:
    """One call that runs the whole pipeline - used by the student dashboard."""
    authorise_student(user, student_id)
    try:
        result = pipeline.run(student_id)
    except pipeline.StudentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    result["history"] = db.prediction_history(student_id)
    return result


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_class=Response)
def delete_student(student_id: str, user: dict = Depends(require_teacher)) -> Response:
    if not db.get_student(student_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Student '{student_id}' not found")
    db.delete_student(student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
