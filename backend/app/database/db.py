"""SQLite persistence layer.

Plain `sqlite3` from the standard library rather than an ORM: the queries are
simple and a viva examiner can read the SQL. Every connection uses row factories
so results come back as dicts.

This module owns the core tables (users, students, concept_mastery, predictions).
The question bank, learning resources, sample papers and practice attempts live
in `app.database.practice_db`, whose schema `init_db` also applies.

Privacy: the tables store a `student_id` and an optional display name. No email,
address, phone number or other identifying data is collected.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('student','teacher')),
    student_id    TEXT,
    full_name     TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students (
    student_id     TEXT PRIMARY KEY,
    display_name   TEXT,
    features       TEXT NOT NULL,        -- JSON of the model input features
    is_demo        INTEGER NOT NULL DEFAULT 0,
    learning_style TEXT,
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS concept_mastery (
    student_id TEXT NOT NULL,
    concept    TEXT NOT NULL,
    mastery    REAL NOT NULL CHECK (mastery >= 0 AND mastery <= 100),
    source     TEXT NOT NULL,            -- simulated | self_reported | assessment
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student_id, concept),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    predicted_gpa    REAL NOT NULL,
    pass_probability REAL NOT NULL,
    risk_tier        TEXT NOT NULL,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_predictions_student ON predictions(student_id);
"""


class DatabaseError(RuntimeError):
    pass


@contextmanager
def get_conn(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    db_path = Path(path or settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as exc:  # pragma: no cover - surfaced as HTTP 500
        conn.rollback()
        raise DatabaseError(str(exc)) from exc
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    """Create every table if absent. Safe to run against an existing database:
    all statements are CREATE TABLE / CREATE INDEX IF NOT EXISTS, so no existing
    row is touched and the call is idempotent."""
    # Imported here rather than at module scope: practice_db imports get_conn
    # from this module.
    from app.database import academics_db, practice_db

    with get_conn(path) as conn:
        # Write-ahead logging: submitting a practice session writes attempts,
        # mastery rows and history in one request. WAL lets readers continue
        # during those writes and is persistent once set on the database file.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        practice_db.init_content_schema(conn)
        # Multi-subject academic records (subjects, assessments, results).
        academics_db.init_academics_schema(conn)


# --------------------------------------------------------------------------- #
# users
# --------------------------------------------------------------------------- #
def create_user(username: str, password_hash: str, salt: str, role: str,
                student_id: str | None = None, full_name: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, student_id, full_name)"
            " VALUES (?,?,?,?,?,?)",
            (username, password_hash, salt, role, student_id, full_name),
        )


def get_user(username: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def user_exists(username: str) -> bool:
    return get_user(username) is not None


# --------------------------------------------------------------------------- #
# students
# --------------------------------------------------------------------------- #
def upsert_student(student_id: str, features: dict, display_name: str | None = None,
                   is_demo: bool = False, learning_style: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO students (student_id, display_name, features, is_demo, learning_style)
            VALUES (?,?,?,?,?)
            ON CONFLICT(student_id) DO UPDATE SET
                display_name = COALESCE(excluded.display_name, students.display_name),
                features = excluded.features,
                learning_style = COALESCE(excluded.learning_style, students.learning_style),
                updated_at = CURRENT_TIMESTAMP
            """,
            (student_id, display_name, json.dumps(features), int(is_demo), learning_style),
        )


def get_student(student_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
    if not row:
        return None
    out = dict(row)
    out["features"] = json.loads(out["features"])
    return out


def list_students() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM students ORDER BY student_id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["features"] = json.loads(d["features"])
        out.append(d)
    return out


def delete_student(student_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))


# --------------------------------------------------------------------------- #
# concept mastery
# --------------------------------------------------------------------------- #
def set_mastery(student_id: str, records: list[dict]) -> None:
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO concept_mastery (student_id, concept, mastery, source)
            VALUES (?,?,?,?)
            ON CONFLICT(student_id, concept) DO UPDATE SET
                mastery = excluded.mastery,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            [(student_id, r["concept"], float(r["mastery"]), r.get("source", "self_reported"))
             for r in records],
        )


def get_mastery(student_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT concept, mastery, source, updated_at FROM concept_mastery"
            " WHERE student_id = ? ORDER BY concept",
            (student_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# prediction history
# --------------------------------------------------------------------------- #
def log_prediction(student_id: str, gpa: float, pass_probability: float, risk: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO predictions (student_id, predicted_gpa, pass_probability, risk_tier)"
            " VALUES (?,?,?,?)",
            (student_id, float(gpa), float(pass_probability), risk),
        )


def prediction_history(student_id: str, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT predicted_gpa, pass_probability, risk_tier, created_at FROM predictions"
            " WHERE student_id = ? ORDER BY id DESC LIMIT ?",
            (student_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]
