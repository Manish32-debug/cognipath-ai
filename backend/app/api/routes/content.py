"""Question bank, learning resources and sample papers.

Read endpoints are open to any authenticated user; every write requires the
teacher role via the existing `require_teacher` dependency. Concept ids are
validated against the knowledge graph so the question bank cannot drift away
from the curriculum the rest of CogniPath reasons over.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.api.deps import authorise_student, current_user, require_teacher
from app.database import practice_db
from app.graph import root_cause
from app.graph.knowledge_graph import CONCEPTS, label
from app.ml import predictor
from app.practice import config, selector
from app.schemas.models import (
    QuestionCreate,
    QuestionUpdate,
    ResourceCreate,
    ResourceUpdate,
)
from app.services import pipeline

router = APIRouter(prefix="/api", tags=["content"])


def _check_concept(concept: str | None) -> None:
    if concept is not None and concept not in CONCEPTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown concept '{concept}'. Use an id from GET /api/concepts.",
        )


def _labelled(rows: list[dict]) -> list[dict]:
    for r in rows:
        if r.get("concept") in CONCEPTS:
            r["label"] = label(r["concept"])
    return rows


# --------------------------------------------------------------------------- #
# questions
# --------------------------------------------------------------------------- #
@router.get("/questions")
def list_questions(concept: str | None = None, difficulty: str | None = None,
                   subject: str | None = None, question_type: str | None = None,
                   limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                   user: dict = Depends(current_user)) -> dict:
    """Students get questions without answers; teachers get the full record."""
    is_teacher = user.get("role") == "teacher"
    rows = practice_db.list_questions(
        concept=concept, difficulty=difficulty, subject=subject,
        question_type=question_type, include_inactive=is_teacher,
        include_answer=is_teacher, limit=limit, offset=offset,
    )
    return {"questions": _labelled(rows), "count": len(rows),
            "answers_included": is_teacher}


@router.get("/questions/bank-summary")
def bank_summary(user: dict = Depends(current_user)) -> dict:
    counts = practice_db.question_counts_by_concept()
    return {
        "concepts": [
            {
                "concept": cid,
                "label": meta[0],
                "subject": meta[1],
                "total": sum(counts.get(cid, {}).values()),
                "by_difficulty": counts.get(cid, {}),
            }
            for cid, meta in CONCEPTS.items()
        ],
        "total_questions": sum(sum(v.values()) for v in counts.values()),
    }


@router.post("/questions", status_code=201)
def create_question(payload: QuestionCreate, user: dict = Depends(require_teacher)) -> dict:
    _check_concept(payload.concept)
    data = payload.model_dump()
    data["options"] = [o.model_dump() for o in payload.options] if payload.options else None
    data["created_by"] = user.get("sub")
    question_id = practice_db.create_question(data)
    return {"question_id": question_id, "status": "created"}


@router.get("/questions/{question_id}")
def get_question(question_id: int, user: dict = Depends(current_user)) -> dict:
    is_teacher = user.get("role") == "teacher"
    question = practice_db.get_question(question_id, include_answer=is_teacher)
    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Question {question_id} not found")
    return question


@router.put("/questions/{question_id}")
def update_question(question_id: int, payload: QuestionUpdate,
                    user: dict = Depends(require_teacher)) -> dict:
    _check_concept(payload.concept)
    existing = practice_db.get_question(question_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Question {question_id} not found")

    data = payload.model_dump(exclude_none=True)
    if payload.options is not None:
        data["options"] = [o.model_dump() for o in payload.options]
    if "is_active" in data:
        data["is_active"] = int(data["is_active"])
    if not practice_db.update_question(question_id, data):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nothing to update")
    return {"question_id": question_id, "status": "updated"}


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, user: dict = Depends(require_teacher)) -> dict:
    """Soft delete. Practice attempts reference this row, so retiring the question
    keeps historical analytics honest instead of orphaning them."""
    if not practice_db.delete_question(question_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"Question {question_id} not found or already retired")
    return {"question_id": question_id, "status": "retired"}


# --------------------------------------------------------------------------- #
# resources
# --------------------------------------------------------------------------- #
@router.get("/resources")
def list_resources(concept: str | None = None, resource_type: str | None = None,
                   subject: str | None = None, difficulty: str | None = None,
                   user: dict = Depends(current_user)) -> dict:
    rows = practice_db.list_resources(
        concept=concept, resource_type=resource_type,
        subject=subject, difficulty=difficulty,
        include_inactive=user.get("role") == "teacher",
    )
    return {"resources": _labelled(rows), "count": len(rows)}


@router.get("/resources/recommended/{student_id}")
def recommended_resources(student_id: str, user: dict = Depends(current_user)) -> dict:
    """Feature 6: library resources selected by the same priority ranking that
    drives the existing recommendation engine, with the reason attached."""
    authorise_student(user, student_id)
    try:
        student = pipeline.load_student(student_id)
    except pipeline.StudentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))

    mastery, _ = pipeline.ensure_mastery(student_id, student["features"])
    roots = root_cause.analyse(mastery)
    try:
        risk = predictor.predict(student["features"])["risk_tier"]
    except predictor.ModelNotTrainedError:
        risk = "Medium"

    prescription = selector.recommended_practice(mastery, roots, risk)
    return {
        "student_id": student_id,
        "items": [
            {
                "concept": item["concept"],
                "label": item["label"],
                "mastery": item["mastery"],
                "is_root_cause": item["is_root_cause"],
                "priority": item["priority"],
                "reason": item["reason"],
                "resources": item["resources"],
                "estimated_minutes": sum(r["estimated_minutes"] for r in item["resources"]),
                "practice": {
                    "recommended_questions": item["recommended_questions"],
                    "available_questions": item["available_questions"],
                    "difficulty": item["difficulty"],
                },
            }
            for item in prescription["items"]
        ],
        "message": prescription["message"],
    }


@router.post("/resources", status_code=201)
def create_resource(payload: ResourceCreate, user: dict = Depends(require_teacher)) -> dict:
    _check_concept(payload.concept)
    data = payload.model_dump()
    data["created_by"] = user.get("sub")
    return {"resource_id": practice_db.create_resource(data), "status": "created"}


@router.put("/resources/{resource_id}")
def update_resource(resource_id: int, payload: ResourceUpdate,
                    user: dict = Depends(require_teacher)) -> dict:
    _check_concept(payload.concept)
    data = payload.model_dump(exclude_none=True)
    if "is_active" in data:
        data["is_active"] = int(data["is_active"])
    if not practice_db.update_resource(resource_id, data):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"Resource {resource_id} not found or nothing to update")
    return {"resource_id": resource_id, "status": "updated"}


@router.delete("/resources/{resource_id}")
def delete_resource(resource_id: int, user: dict = Depends(require_teacher)) -> dict:
    if not practice_db.delete_resource(resource_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"Resource {resource_id} not found or already retired")
    return {"resource_id": resource_id, "status": "retired"}


# --------------------------------------------------------------------------- #
# sample papers
# --------------------------------------------------------------------------- #
@router.get("/sample-papers")
def list_papers(subject: str | None = None, user: dict = Depends(current_user)) -> dict:
    papers = practice_db.list_papers(subject)
    grouped: dict[str, list[dict]] = {}
    for p in papers:
        grouped.setdefault(p["subject"], []).append(p)
    return {
        "papers": papers,
        "by_subject": [{"subject": k, "papers": v} for k, v in sorted(grouped.items())],
        "count": len(papers),
        "note": (
            "Papers marked is_demo are generated placeholders created for "
            "development. They are not official university question papers and "
            "carry no institutional status."
        ),
    }


@router.post("/sample-papers", status_code=201)
async def upload_paper(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=160),
    subject: str = Form(..., min_length=2, max_length=60),
    difficulty: str = Form("Medium"),
    year: int | None = Form(None),
    semester: str | None = Form(None),
    description: str | None = Form(None),
    user: dict = Depends(require_teacher),
) -> dict:
    if difficulty not in config.DIFFICULTIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"difficulty must be one of {config.DIFFICULTIES}")
    if file.content_type not in config.ALLOWED_PDF_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            "Only application/pdf uploads are accepted")

    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Uploaded file is empty")
    if len(content) > config.MAX_PDF_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"PDF exceeds {config.MAX_PDF_BYTES // (1024 * 1024)} MB")
    # Content sniff: a declared content-type is client-supplied and not evidence.
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "File does not begin with a PDF header")

    paper_id = practice_db.create_paper(
        {
            "title": title, "subject": subject, "year": year, "semester": semester,
            "difficulty": difficulty, "description": description,
            "filename": file.filename or f"{title}.pdf",
            "is_demo": 0, "uploaded_by": user.get("sub"),
        },
        content,
        file.content_type,
    )
    return {"paper_id": paper_id, "status": "uploaded", "size_bytes": len(content)}


@router.get("/sample-papers/{paper_id}/file")
def download_paper(paper_id: int, download: bool = Query(False),
                   user: dict = Depends(current_user)) -> Response:
    record = practice_db.get_paper_file(paper_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Paper {paper_id} not found")
    content, content_type, filename = record
    disposition = "attachment" if download else "inline"
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.delete("/sample-papers/{paper_id}")
def delete_paper(paper_id: int, user: dict = Depends(require_teacher)) -> dict:
    if not practice_db.delete_paper(paper_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Paper {paper_id} not found")
    return {"paper_id": paper_id, "status": "deleted"}


# --------------------------------------------------------------------------- #
# teacher analytics over practice data
# --------------------------------------------------------------------------- #
@router.get("/teacher/practice-analytics")
def practice_analytics(user: dict = Depends(require_teacher)) -> dict:
    """Feature 11. Every figure is aggregated from stored practice attempts."""
    concepts = _labelled(practice_db.cohort_concept_performance())
    struggling = _labelled(practice_db.struggling_students())

    by_concept: dict[str, list[dict]] = {}
    for row in struggling:
        by_concept.setdefault(row["concept"], []).append(row)

    return {
        "totals": practice_db.practice_totals(),
        "concept_performance": concepts,
        "most_difficult_concepts": concepts[:5],
        "most_attempted_concepts": sorted(
            concepts, key=lambda c: -c["attempted"]
        )[:5],
        "most_attempted_questions": _labelled(practice_db.most_attempted_questions()),
        "struggling_students": [
            {"concept": k, "label": label(k) if k in CONCEPTS else k, "students": v}
            for k, v in sorted(by_concept.items())
        ],
        "bank_coverage": practice_db.question_counts_by_concept(),
    }
