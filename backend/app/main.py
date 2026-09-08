"""CogniPath AI - FastAPI application entrypoint.

Kept thin on purpose: wiring, middleware, error handlers and lifespan only.
All business logic lives in `app/services`, `app/ml`, `app/graph` and
`app/recommendations`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import analysis, auth, content, practice, students
from app.core.config import settings
from app.database import db
from app.database.db import DatabaseError
from app.graph.knowledge_graph import get_graph
from app.ml.predictor import ModelNotTrainedError, model_info
from app.services.pipeline import StudentNotFound


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger("cognipath")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    get_graph()

    try:
        log.info("Models loaded: %s", model_info())
    except ModelNotTrainedError:
        log.warning(
            "No trained model bundle found. Prediction endpoints will return 503 "
            "until you run: python -m app.ml.train"
        )

    if settings.using_default_secret:
        log.warning(
            "COGNIPATH_SECRET is unset - using the development JWT secret."
        )

    yield


app = FastAPI(
    title="CogniPath AI API",
    version=settings.version,
    description=(
        "Explainable AI for student performance prediction, prerequisite "
        "root-cause diagnosis and personalised learning recommendations.\n\n"
        "**Responsible use:** predictions are statistical estimates intended to "
        "trigger human review, not automated decisions about students."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API ROUTES
# ---------------------------------------------------------------------------

# ORDER MATTERS. The SPA catch-all at the bottom of this file registers
# GET /{full_path:path}. FastAPI matches routes in registration order, so any
# router included *after* it would be shadowed and every GET would return
# index.html instead of JSON. Register new routers here, never below.
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(analysis.router)
app.include_router(practice.router)
app.include_router(content.router)


# ---------------------------------------------------------------------------
# EXCEPTION HANDLERS
# ---------------------------------------------------------------------------

@app.exception_handler(StudentNotFound)
async def student_not_found_handler(
    request: Request,
    exc: StudentNotFound,
):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(ModelNotTrainedError)
async def model_missing_handler(
    request: Request,
    exc: ModelNotTrainedError,
):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc)},
    )


@app.exception_handler(DatabaseError)
async def database_error_handler(
    request: Request,
    exc: DatabaseError,
):
    log.exception("Database failure on %s", request.url.path)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error"},
    )


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["system"])
def health() -> dict:
    try:
        models = model_info()
        model_status = "loaded"
    except ModelNotTrainedError:
        models = None
        model_status = "missing"

    return {
        "status": "ok",
        "version": settings.version,
        "models": model_status,
        "model_info": models,
        "database": str(settings.database_path.name),
    }


# ---------------------------------------------------------------------------
# REACT FRONTEND
# ---------------------------------------------------------------------------

# Project structure:
#
# cognipath/
# ├── backend/
# │   └── app/
# │       └── main.py   <-- this file
# └── frontend/
#     └── dist/
#         └── index.html
#
# Therefore, from backend/app/main.py:
# parents[0] = app/
# parents[1] = backend/
# parents[2] = cognipath/
#
# So frontend/dist is:
# cognipath/frontend/dist

FRONTEND_DIST = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "dist"
)


# Serve Vite-generated static assets.
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )


# Serve React application at the root URL.
if FRONTEND_DIST.exists():

    @app.get("/", include_in_schema=False)
    async def frontend_root():
        return FileResponse(
            FRONTEND_DIST / "index.html"
        )


    # React Router fallback.
    #
    # If the browser requests a frontend route such as:
    # /app
    # /app/dashboard
    # /app/performance
    #
    # FastAPI returns index.html so React Router can handle the route.

    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_spa(full_path: str):
        requested_file = FRONTEND_DIST / full_path

        if requested_file.is_file():
            return FileResponse(requested_file)

        return FileResponse(
            FRONTEND_DIST / "index.html"
        )