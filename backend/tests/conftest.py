"""Test fixtures. Every test runs against a throwaway SQLite file so the
development database is never touched."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TMP_DB = Path(tempfile.gettempdir()) / "cognipath_test.db"
os.environ["COGNIPATH_DB"] = str(TMP_DB)
os.environ.setdefault("COGNIPATH_SECRET", "test-secret")
os.environ["COGNIPATH_DEMO_SIZE"] = "12"

from app.database import db  # noqa: E402  (import after env setup)
from app.database.seed import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    if TMP_DB.exists():
        TMP_DB.unlink()
    db.init_db()
    seed(n=12)
    yield
    if TMP_DB.exists():
        TMP_DB.unlink()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def teacher_headers(client):
    r = client.post("/api/auth/login", json={"username": "teacher", "password": "teach1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def student_headers(client):
    r = client.post("/api/auth/login", json={"username": "demo001", "password": "demo1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def sample_features() -> dict:
    return {
        "G1": 9, "G2": 8, "studytime": 2, "failures": 1, "absences": 12,
        "health": 3, "freetime": 3, "goout": 4, "age": 17,
    }
