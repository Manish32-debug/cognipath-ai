"""Persistence for the multi-subject, multi-assessment academic record.

Kept in its own module for the same reason `practice_db.py` is: `db.py` stays the
small readable core. Every statement is CREATE TABLE / CREATE INDEX IF NOT EXISTS,
so running this against the production database adds tables and touches nothing
that already exists - no manual migration, no dropped rows.

Why a normalized structure rather than g3, g4, g5 columns
--------------------------------------------------------
    subjects  ->  assessments  ->  student_assessment_results
                       ^
                    (subject_id, assessment_order)

Adding a subject is a row in `subjects`. Adding an assessment type is a row in
`assessments`. Neither requires a schema change, which is the whole point of
Part 2: the G1/G2 design could only ever hold exactly two numbers.

`assessment_types` is a small configuration table rather than a CHECK constraint,
so a teacher can introduce "Quiz 3" or "Viva" without an ALTER TABLE.

Results store `marks` and the assessment's `max_marks` at read time; `percentage`
is stored too because it is what every analytic downstream actually uses and
recomputing it in SQL on every query is wasted work.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable

from app.database.db import get_conn

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    subject_id  TEXT PRIMARY KEY,           -- knowledge-graph subject id, e.g. 'dsp'
    name        TEXT NOT NULL,
    code        TEXT,
    description TEXT,
    semester    TEXT,
    credits     REAL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessment_types (
    type_id      TEXT PRIMARY KEY,          -- 'cat', 'assignment', 'midterm', 'final'
    name         TEXT NOT NULL,
    weight       REAL NOT NULL DEFAULT 1,   -- relative contribution to the subject grade
    is_terminal  INTEGER NOT NULL DEFAULT 0 -- 1 for the assessment being predicted
);

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id       TEXT NOT NULL,
    assessment_type  TEXT NOT NULL,
    name             TEXT NOT NULL,         -- 'CAT 1', 'Assignment 2'
    assessment_order INTEGER NOT NULL,      -- chronological position within the subject
    max_marks        REAL NOT NULL DEFAULT 100 CHECK (max_marks > 0),
    weight           REAL NOT NULL DEFAULT 1,
    scheduled_on     TEXT,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (subject_id, name),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,
    FOREIGN KEY (assessment_type) REFERENCES assessment_types(type_id)
);
CREATE INDEX IF NOT EXISTS idx_assessments_subject
    ON assessments(subject_id, assessment_order);

CREATE TABLE IF NOT EXISTS student_assessment_results (
    result_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    assessment_id INTEGER NOT NULL,
    marks         REAL NOT NULL CHECK (marks >= 0),
    percentage    REAL NOT NULL CHECK (percentage >= 0 AND percentage <= 100),
    recorded_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    source        TEXT NOT NULL DEFAULT 'entered',  -- entered | simulated | imported
    UNIQUE (student_id, assessment_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_results_student
    ON student_assessment_results(student_id);
"""


def init_academics_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _rows(cur: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in cur]


# --------------------------------------------------------------------------- #
# subjects
# --------------------------------------------------------------------------- #
def upsert_subject(subject: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO subjects (subject_id, name, code, description, semester, credits, is_active)
            VALUES (:subject_id, :name, :code, :description, :semester, :credits, 1)
            ON CONFLICT(subject_id) DO UPDATE SET
                name=excluded.name, code=excluded.code,
                description=excluded.description, semester=excluded.semester,
                credits=excluded.credits
            """,
            {"code": None, "description": None, "semester": None, "credits": None, **subject},
        )


def list_subjects(active_only: bool = True) -> list[dict]:
    sql = "SELECT * FROM subjects"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name"
    with get_conn() as conn:
        return _rows(conn.execute(sql).fetchall())


def get_subject(subject_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM subjects WHERE subject_id = ?", (subject_id,)).fetchone()
    return dict(row) if row else None


def deactivate_subject(subject_id: str) -> None:
    """Soft delete: results already recorded against it stay readable."""
    with get_conn() as conn:
        conn.execute("UPDATE subjects SET is_active = 0 WHERE subject_id = ?", (subject_id,))


# --------------------------------------------------------------------------- #
# assessment types and assessments
# --------------------------------------------------------------------------- #
def upsert_assessment_type(t: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO assessment_types (type_id, name, weight, is_terminal)
            VALUES (:type_id, :name, :weight, :is_terminal)
            ON CONFLICT(type_id) DO UPDATE SET
                name=excluded.name, weight=excluded.weight, is_terminal=excluded.is_terminal
            """,
            {"weight": 1.0, "is_terminal": 0, **t},
        )


def list_assessment_types() -> list[dict]:
    with get_conn() as conn:
        return _rows(conn.execute("SELECT * FROM assessment_types ORDER BY type_id").fetchall())


def upsert_assessment(a: dict) -> int:
    """Create or update an assessment definition; returns its id."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO assessments (subject_id, assessment_type, name, assessment_order,
                                     max_marks, weight, scheduled_on)
            VALUES (:subject_id, :assessment_type, :name, :assessment_order,
                    :max_marks, :weight, :scheduled_on)
            ON CONFLICT(subject_id, name) DO UPDATE SET
                assessment_type=excluded.assessment_type,
                assessment_order=excluded.assessment_order,
                max_marks=excluded.max_marks, weight=excluded.weight,
                scheduled_on=excluded.scheduled_on
            """,
            {"max_marks": 100.0, "weight": 1.0, "scheduled_on": None, **a},
        )
        row = conn.execute(
            "SELECT assessment_id FROM assessments WHERE subject_id = ? AND name = ?",
            (a["subject_id"], a["name"]),
        ).fetchone()
    return int(row["assessment_id"])


def list_assessments(subject_id: str | None = None) -> list[dict]:
    sql = "SELECT * FROM assessments"
    params: list = []
    if subject_id:
        sql += " WHERE subject_id = ?"
        params.append(subject_id)
    sql += " ORDER BY subject_id, assessment_order"
    with get_conn() as conn:
        return _rows(conn.execute(sql, params).fetchall())


def get_assessment(assessment_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM assessments WHERE assessment_id = ?", (assessment_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_assessment(assessment_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM assessments WHERE assessment_id = ?", (assessment_id,))
    return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# results
# --------------------------------------------------------------------------- #
def record_result(student_id: str, assessment_id: int, marks: float,
                  source: str = "entered") -> dict:
    """Store one mark. Percentage is derived from the assessment's max_marks, so
    a 40-mark CAT and a 100-mark final are directly comparable downstream."""
    assessment = get_assessment(assessment_id)
    if assessment is None:
        raise ValueError(f"Unknown assessment id {assessment_id}")
    marks = float(marks)
    if marks < 0 or marks > assessment["max_marks"]:
        raise ValueError(
            f"marks must be between 0 and {assessment['max_marks']} for '{assessment['name']}'"
        )
    percentage = 100.0 * marks / assessment["max_marks"]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO student_assessment_results
                (student_id, assessment_id, marks, percentage, source)
            VALUES (?,?,?,?,?)
            ON CONFLICT(student_id, assessment_id) DO UPDATE SET
                marks=excluded.marks, percentage=excluded.percentage,
                source=excluded.source, recorded_at=CURRENT_TIMESTAMP
            """,
            (student_id, assessment_id, marks, percentage, source),
        )
    return {"student_id": student_id, "assessment_id": assessment_id,
            "marks": marks, "percentage": round(percentage, 2), "source": source}


def record_results_bulk(rows: list[dict]) -> int:
    count = 0
    for r in rows:
        record_result(r["student_id"], r["assessment_id"], r["marks"],
                      r.get("source", "entered"))
        count += 1
    return count


def student_results(student_id: str, subject_id: str | None = None) -> list[dict]:
    """Chronological assessment history, joined with its definition."""
    sql = """
        SELECT r.result_id, r.student_id, r.marks, r.percentage, r.source, r.recorded_at,
               a.assessment_id, a.subject_id, a.assessment_type, a.name,
               a.assessment_order, a.max_marks, a.weight,
               s.name AS subject_name
        FROM student_assessment_results r
        JOIN assessments a ON a.assessment_id = r.assessment_id
        LEFT JOIN subjects s ON s.subject_id = a.subject_id
        WHERE r.student_id = ?
    """
    params: list = [student_id]
    if subject_id:
        sql += " AND a.subject_id = ?"
        params.append(subject_id)
    sql += " ORDER BY a.subject_id, a.assessment_order"
    with get_conn() as conn:
        return _rows(conn.execute(sql, params).fetchall())


def subject_results_for_cohort(subject_id: str | None = None) -> list[dict]:
    sql = """
        SELECT r.student_id, r.percentage, a.subject_id, a.name, a.assessment_order,
               a.assessment_type
        FROM student_assessment_results r
        JOIN assessments a ON a.assessment_id = r.assessment_id
    """
    params: list = []
    if subject_id:
        sql += " WHERE a.subject_id = ?"
        params.append(subject_id)
    sql += " ORDER BY a.subject_id, a.assessment_order, r.student_id"
    with get_conn() as conn:
        return _rows(conn.execute(sql, params).fetchall())


def assessment_averages(subject_id: str | None = None) -> list[dict]:
    """Cohort average per assessment - the teacher's assessment-trend view."""
    sql = """
        SELECT a.subject_id, a.assessment_id, a.name, a.assessment_order,
               COUNT(r.result_id) AS n_results,
               AVG(r.percentage)  AS average_percentage,
               MIN(r.percentage)  AS min_percentage,
               MAX(r.percentage)  AS max_percentage
        FROM assessments a
        LEFT JOIN student_assessment_results r ON r.assessment_id = a.assessment_id
    """
    params: list = []
    if subject_id:
        sql += " WHERE a.subject_id = ?"
        params.append(subject_id)
    sql += " GROUP BY a.assessment_id ORDER BY a.subject_id, a.assessment_order"
    with get_conn() as conn:
        return _rows(conn.execute(sql, params).fetchall())


def students_with_results() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT student_id FROM student_assessment_results ORDER BY student_id"
        ).fetchall()
    return [r["student_id"] for r in rows]


def result_counts() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS results,
                   COUNT(DISTINCT student_id) AS students,
                   COUNT(DISTINCT assessment_id) AS assessments
            FROM student_assessment_results
            """
        ).fetchone()
        subjects = conn.execute("SELECT COUNT(*) AS c FROM subjects").fetchone()["c"]
    return {**dict(row), "subjects": int(subjects)}
