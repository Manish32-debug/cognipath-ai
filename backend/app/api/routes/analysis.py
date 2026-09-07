"""Model, graph and recommendation endpoints.

Two calling styles are supported everywhere:
  * stateless - POST the feature payload, get a result (used by the "try it"
    form on the landing page and by ad-hoc what-if analysis);
  * by student id - GET for a stored student (used by the dashboards).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import authorise_student, current_user, require_teacher
from app.graph import root_cause
from app.graph.knowledge_graph import CONCEPTS, graph_payload
from app.ml import predictor
from app.recommendations import engine, study_plan
from app.schemas.models import (
    ExplanationResponse,
    PredictionResponse,
    RootCauseRequest,
    StudentFeatures,
)
from app.services import cognitive_twin, pipeline

router = APIRouter(prefix="/api", tags=["analysis"])


def _model_guard(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@router.post("/predict", response_model=PredictionResponse)
def predict(payload: StudentFeatures, user: dict = Depends(current_user)):
    try:
        return predictor.predict(payload.model_dump())
    except predictor.ModelNotTrainedError as exc:
        raise _model_guard(exc)


@router.post("/explain", response_model=ExplanationResponse)
def explain(payload: StudentFeatures,
            task: str = Query("gpa", pattern="^(gpa|pass|risk)$"),
            top_k: int = Query(10, ge=3, le=25),
            user: dict = Depends(current_user)):
    try:
        return predictor.explain(payload.model_dump(), task=task, top_k=top_k)
    except predictor.ModelNotTrainedError as exc:
        raise _model_guard(exc)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/knowledge-graph")
def knowledge_graph() -> dict:
    """Static curriculum graph. Cached in-process by `get_graph`'s lru_cache."""
    return graph_payload()


@router.get("/concepts")
def concepts() -> dict:
    return {
        "concepts": [
            {"id": cid, "label": label, "area": area, "description": desc}
            for cid, (label, area, desc) in CONCEPTS.items()
        ],
        "thresholds": root_cause._params(),
    }


@router.post("/root-cause")
def root_cause_analysis(payload: RootCauseRequest, user: dict = Depends(current_user)) -> dict:
    unknown = [c for c in payload.mastery if c not in CONCEPTS]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Unknown concepts: {unknown}")
    return root_cause.analyse(payload.mastery)


@router.get("/root-cause/{student_id}")
def root_cause_for_student(student_id: str, user: dict = Depends(current_user)) -> dict:
    authorise_student(user, student_id)
    try:
        student = pipeline.load_student(student_id)
    except pipeline.StudentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    mastery, _ = pipeline.ensure_mastery(student_id, student["features"])
    return root_cause.analyse(mastery)


@router.get("/recommendations/{student_id}")
def recommendations(student_id: str, user: dict = Depends(current_user)) -> dict:
    authorise_student(user, student_id)
    try:
        student = pipeline.load_student(student_id)
    except pipeline.StudentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    mastery, _ = pipeline.ensure_mastery(student_id, student["features"])
    prediction = predictor.predict(student["features"])
    roots = root_cause.analyse(mastery)
    return engine.recommend(mastery, roots, prediction["risk_tier"])


@router.get("/study-plan/{student_id}")
def plan(student_id: str, user: dict = Depends(current_user)) -> dict:
    authorise_student(user, student_id)
    try:
        student = pipeline.load_student(student_id)
    except pipeline.StudentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    features = student["features"]
    mastery, _ = pipeline.ensure_mastery(student_id, features)
    prediction = predictor.predict(features)
    roots = root_cause.analyse(mastery)
    recs = engine.recommend(mastery, roots, prediction["risk_tier"])
    return study_plan.generate(
        recs,
        studytime=int(features.get("studytime", 2)),
        freetime=int(features.get("freetime", 3)),
        risk_tier=prediction["risk_tier"],
    )


@router.get("/cognitive-twin/{student_id}")
def twin(student_id: str, user: dict = Depends(current_user)) -> dict:
    authorise_student(user, student_id)
    try:
        student = pipeline.load_student(student_id)
    except pipeline.StudentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    features = student["features"]
    mastery, source = pipeline.ensure_mastery(student_id, features)
    prediction = predictor.predict(features)
    roots = root_cause.analyse(mastery)
    return cognitive_twin.build(
        {**features, "student_id": student_id,
         "learning_style": student.get("learning_style"), "mastery_source": source},
        mastery, prediction, roots,
    )


@router.get("/teacher/analytics")
def teacher_analytics(user: dict = Depends(require_teacher)) -> dict:
    return pipeline.cohort_analytics()


@router.get("/teacher/student/{student_id}")
def teacher_student_drilldown(student_id: str, user: dict = Depends(require_teacher)) -> dict:
    try:
        return pipeline.run(student_id, log=False)
    except pipeline.StudentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.get("/model-info")
def model_info() -> dict:
    try:
        return predictor.model_info()
    except predictor.ModelNotTrainedError as exc:
        raise _model_guard(exc)


@router.get("/evaluation")
def evaluation() -> dict:
    """Training/test metrics written by the training pipeline."""
    import json

    from app.core.config import settings

    path = settings.model_path.parent / "evaluation.json"
    if not path.exists():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "No evaluation report found. Run `python -m app.ml.train`.")
    return json.loads(path.read_text())
