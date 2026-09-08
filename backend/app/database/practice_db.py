"""Persistence for the question bank, learning resources, sample papers and
practice attempts.

Kept in its own module so `db.py` stays the small, readable core (users,
students, mastery, predictions). The schema below is additive: every statement
is CREATE TABLE IF NOT EXISTS, so running it against an existing CogniPath
database adds tables and touches nothing that already exists.

Design notes
------------
* `concept` columns store the knowledge-graph *id* (`differential_equations`),
  never the display label. Validation against `CONCEPTS` happens at the API
  boundary, mirroring how `PUT /api/students/{id}/mastery` already does it.
* `practice_attempts` denormalises `concept` and `difficulty`. A teacher may
  later edit or retire a question; historical analytics must not mutate
  retroactively.
* Sample paper bytes live in a separate table from the metadata so listing
  papers never drags PDF blobs through the row factory.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

from app.database.db import get_conn

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    question_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    subject        TEXT NOT NULL,
    concept        TEXT NOT NULL,
    difficulty     TEXT NOT NULL CHECK (difficulty IN ('Easy','Medium','Hard')),
    question_type  TEXT NOT NULL CHECK (question_type IN ('MCQ','Numerical','Theory')),
    question_text  TEXT NOT NULL,
    options        TEXT,                       -- JSON array of {key,text}; NULL unless MCQ
    correct_answer TEXT NOT NULL,
    explanation    TEXT,
    marks          REAL NOT NULL DEFAULT 1 CHECK (marks > 0),
    tolerance      REAL,                       -- numerical answers only
    source         TEXT,
    created_by     TEXT,
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    is_active      INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_questions_concept
    ON questions(concept, difficulty, is_active);

CREATE TABLE IF NOT EXISTS resources (
    resource_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT NOT NULL,
    subject           TEXT NOT NULL,
    concept           TEXT NOT NULL,
    resource_type     TEXT NOT NULL CHECK (resource_type IN ('Video','Article','Notes','PDF','Exercise')),
    difficulty        TEXT NOT NULL CHECK (difficulty IN ('Easy','Medium','Hard')),
    description       TEXT,
    url               TEXT,
    estimated_minutes INTEGER NOT NULL DEFAULT 20 CHECK (estimated_minutes > 0),
    created_by        TEXT,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP,
    is_active         INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_resources_concept
    ON resources(concept, is_active);

CREATE TABLE IF NOT EXISTS sample_papers (
    paper_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    subject      TEXT NOT NULL,
    year         INTEGER,
    semester     TEXT,
    difficulty   TEXT NOT NULL CHECK (difficulty IN ('Easy','Medium','Hard')),
    description  TEXT,
    filename     TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL,
    is_demo      INTEGER NOT NULL DEFAULT 0,
    uploaded_by  TEXT,
    uploaded_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sample_paper_files (
    paper_id     INTEGER PRIMARY KEY,
    content      BLOB NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/pdf',
    FOREIGN KEY (paper_id) REFERENCES sample_papers(paper_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS practice_sessions (
    session_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    concept      TEXT,
    difficulty   TEXT,
    origin       TEXT NOT NULL DEFAULT 'manual',   -- manual | recommended | root_cause
    n_requested  INTEGER NOT NULL,
    served_questions TEXT,                            -- JSON array of question_id
    started_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_student
    ON practice_sessions(student_id, started_at);

CREATE TABLE IF NOT EXISTS practice_attempts (
    attempt_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,
    student_id      TEXT NOT NULL,
    question_id     INTEGER NOT NULL,
    concept         TEXT NOT NULL,
    difficulty      TEXT NOT NULL,
    question_type   TEXT NOT NULL,
    selected_answer TEXT,
    is_correct      INTEGER NOT NULL,
    score           REAL NOT NULL,
    max_score       REAL NOT NULL,
    time_taken      REAL,
    graded_by       TEXT NOT NULL DEFAULT 'auto',  -- auto | self
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES practice_sessions(session_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_attempts_student
    ON practice_attempts(student_id, concept, created_at);
CREATE INDEX IF NOT EXISTS idx_attempts_question
    ON practice_attempts(question_id);

CREATE TABLE IF NOT EXISTS mastery_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    concept         TEXT NOT NULL,
    previous        REAL NOT NULL,
    updated         REAL NOT NULL,
    practice_score  REAL NOT NULL,
    alpha_effective REAL NOT NULL,
    n_attempts      INTEGER NOT NULL,
    session_id      INTEGER,
    reason          TEXT NOT NULL DEFAULT 'practice',
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mastery_history_student
    ON mastery_history(student_id, concept, created_at);
"""


def init_content_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _rows(cur: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in cur]


def _decode_question(row: dict, *, include_answer: bool) -> dict:
    out = dict(row)
    out["options"] = json.loads(out["options"]) if out.get("options") else None
    out["is_active"] = bool(out.get("is_active", 1))
    if not include_answer:
        out.pop("correct_answer", None)
        out.pop("explanation", None)
        out.pop("tolerance", None)
    return out


# --------------------------------------------------------------------------- #
# questions
# --------------------------------------------------------------------------- #
def create_question(data: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO questions (subject, concept, difficulty, question_type,
                                   question_text, options, correct_answer, explanation,
                                   marks, tolerance, source, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                data["subject"], data["concept"], data["difficulty"], data["question_type"],
                data["question_text"],
                json.dumps(data["options"]) if data.get("options") else None,
                data["correct_answer"], data.get("explanation"),
                float(data.get("marks", 1)), data.get("tolerance"),
                data.get("source"), data.get("created_by"),
            ),
        )
        return int(cur.lastrowid)


def update_question(question_id: int, data: dict) -> bool:
    fields, values = [], []
    for column in ("subject", "concept", "difficulty", "question_type", "question_text",
                   "correct_answer", "explanation", "marks", "tolerance", "source", "is_active"):
        if data.get(column) is not None:
            fields.append(f"{column} = ?")
            values.append(data[column])
    if data.get("options") is not None:
        fields.append("options = ?")
        values.append(json.dumps(data["options"]))
    if not fields:
        return False
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(question_id)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE questions SET {', '.join(fields)} WHERE question_id = ?", values
        )
        return cur.rowcount > 0


def delete_question(question_id: int) -> bool:
    """Soft delete: attempts reference this row, so retire it rather than drop it."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE questions SET is_active = 0, updated_at = CURRENT_TIMESTAMP"
            " WHERE question_id = ? AND is_active = 1",
            (question_id,),
        )
        return cur.rowcount > 0


def get_question(question_id: int, include_answer: bool = True) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM questions WHERE question_id = ?", (question_id,)
        ).fetchone()
    return _decode_question(dict(row), include_answer=include_answer) if row else None


def list_questions(concept: str | None = None, difficulty: str | None = None,
                   subject: str | None = None, question_type: str | None = None,
                   include_inactive: bool = False, include_answer: bool = True,
                   limit: int = 200, offset: int = 0) -> list[dict]:
    clauses, params = [], []
    if not include_inactive:
        clauses.append("is_active = 1")
    for column, value in (("concept", concept), ("difficulty", difficulty),
                          ("subject", subject), ("question_type", question_type)):
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM questions {where} ORDER BY question_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [_decode_question(dict(r), include_answer=include_answer) for r in rows]


def sample_questions(concept: str, difficulty: str | None, n: int,
                     student_id: str | None = None) -> list[dict]:
    """Pick `n` active questions for a concept.

    When a student is given, unseen questions come first and previously seen ones
    are ordered least-recently-attempted first, so repeated practice on the same
    concept does not just replay the same items.
    """
    params: list[Any] = []
    join = ""
    order = "RANDOM()"

    if student_id:
        join = (
            " LEFT JOIN (SELECT question_id, MAX(created_at) AS last_seen"
            "              FROM practice_attempts WHERE student_id = ?"
            "             GROUP BY question_id) a ON a.question_id = q.question_id"
        )
        params.append(student_id)
        order = "a.last_seen IS NOT NULL, a.last_seen, RANDOM()"

    clauses = ["q.is_active = 1", "q.concept = ?"]
    params.append(concept)
    if difficulty:
        clauses.append("q.difficulty = ?")
        params.append(difficulty)
    params.append(n)

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT q.* FROM questions q{join}"
            f" WHERE {' AND '.join(clauses)} ORDER BY {order} LIMIT ?",
            params,
        ).fetchall()
    return [_decode_question(dict(r), include_answer=True) for r in rows]


def question_counts_by_concept() -> dict[str, dict[str, int]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT concept, difficulty, COUNT(*) AS n FROM questions"
            " WHERE is_active = 1 GROUP BY concept, difficulty"
        ).fetchall()
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        out.setdefault(r["concept"], {})[r["difficulty"]] = int(r["n"])
    return out


# --------------------------------------------------------------------------- #
# resources
# --------------------------------------------------------------------------- #
def create_resource(data: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO resources (title, subject, concept, resource_type, difficulty,
                                   description, url, estimated_minutes, created_by)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (data["title"], data["subject"], data["concept"], data["resource_type"],
             data["difficulty"], data.get("description"), data.get("url"),
             int(data.get("estimated_minutes", 20)), data.get("created_by")),
        )
        return int(cur.lastrowid)


def update_resource(resource_id: int, data: dict) -> bool:
    fields, values = [], []
    for column in ("title", "subject", "concept", "resource_type", "difficulty",
                   "description", "url", "estimated_minutes", "is_active"):
        if data.get(column) is not None:
            fields.append(f"{column} = ?")
            values.append(data[column])
    if not fields:
        return False
    values.append(resource_id)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE resources SET {', '.join(fields)} WHERE resource_id = ?", values
        )
        return cur.rowcount > 0


def delete_resource(resource_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE resources SET is_active = 0 WHERE resource_id = ? AND is_active = 1",
            (resource_id,),
        )
        return cur.rowcount > 0


def list_resources(concept: str | None = None, resource_type: str | None = None,
                   subject: str | None = None, difficulty: str | None = None,
                   include_inactive: bool = False, limit: int = 200) -> list[dict]:
    clauses, params = [], []
    if not include_inactive:
        clauses.append("is_active = 1")
    for column, value in (("concept", concept), ("resource_type", resource_type),
                          ("subject", subject), ("difficulty", difficulty)):
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM resources {where} ORDER BY concept, estimated_minutes LIMIT ?",
            params,
        ).fetchall()
    return _rows(rows)


def resources_for_concepts(concepts: list[str], per_concept: int = 3) -> dict[str, list[dict]]:
    if not concepts:
        return {}
    placeholders = ",".join("?" * len(concepts))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM resources WHERE is_active = 1 AND concept IN ({placeholders})"
            " ORDER BY concept, difficulty, estimated_minutes",
            concepts,
        ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        bucket = grouped.setdefault(r["concept"], [])
        if len(bucket) < per_concept:
            bucket.append(dict(r))
    return grouped


# --------------------------------------------------------------------------- #
# sample papers
# --------------------------------------------------------------------------- #
def create_paper(meta: dict, content: bytes, content_type: str = "application/pdf") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO sample_papers (title, subject, year, semester, difficulty,
                                       description, filename, size_bytes, is_demo, uploaded_by)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (meta["title"], meta["subject"], meta.get("year"), meta.get("semester"),
             meta["difficulty"], meta.get("description"), meta["filename"],
             len(content), int(meta.get("is_demo", 0)), meta.get("uploaded_by")),
        )
        paper_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO sample_paper_files (paper_id, content, content_type) VALUES (?,?,?)",
            (paper_id, sqlite3.Binary(content), content_type),
        )
        return paper_id


def list_papers(subject: str | None = None) -> list[dict]:
    clause, params = ("WHERE subject = ?", [subject]) if subject else ("", [])
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM sample_papers {clause} ORDER BY subject, year DESC, title", params
        ).fetchall()
    return [{**dict(r), "is_demo": bool(r["is_demo"])} for r in rows]


def get_paper(paper_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sample_papers WHERE paper_id = ?", (paper_id,)
        ).fetchone()
    return {**dict(row), "is_demo": bool(row["is_demo"])} if row else None


def get_paper_file(paper_id: int) -> tuple[bytes, str, str] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT f.content, f.content_type, p.filename FROM sample_paper_files f"
            " JOIN sample_papers p ON p.paper_id = f.paper_id WHERE f.paper_id = ?",
            (paper_id,),
        ).fetchone()
    return (bytes(row["content"]), row["content_type"], row["filename"]) if row else None


def delete_paper(paper_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM sample_papers WHERE paper_id = ?", (paper_id,))
        return cur.rowcount > 0


def paper_titles() -> set[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT title FROM sample_papers").fetchall()
    return {r["title"] for r in rows}


# --------------------------------------------------------------------------- #
# practice sessions and attempts
# --------------------------------------------------------------------------- #
def create_session(student_id: str, concept: str | None, difficulty: str | None,
                   origin: str, n_requested: int, served: list[int] | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO practice_sessions (student_id, concept, difficulty, origin,"
            " n_requested, served_questions) VALUES (?,?,?,?,?,?)",
            (student_id, concept, difficulty, origin, n_requested,
             json.dumps(served) if served is not None else None),
        )
        return int(cur.lastrowid)


def get_session(session_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM practice_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    if not row:
        return None
    out = dict(row)
    out["served_questions"] = json.loads(out["served_questions"]) if out["served_questions"] else []
    return out


def record_attempts(session_id: int, student_id: str, attempts: list[dict]) -> None:
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO practice_attempts (session_id, student_id, question_id, concept,
                                           difficulty, question_type, selected_answer,
                                           is_correct, score, max_score, time_taken, graded_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (session_id, student_id, a["question_id"], a["concept"], a["difficulty"],
                 a["question_type"], a.get("selected_answer"), int(a["is_correct"]),
                 float(a["score"]), float(a["max_score"]), a.get("time_taken"),
                 a.get("graded_by", "auto"))
                for a in attempts
            ],
        )
        conn.execute(
            "UPDATE practice_sessions SET completed_at = CURRENT_TIMESTAMP WHERE session_id = ?",
            (session_id,),
        )


def concept_stats(student_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT concept,
                   COUNT(*)                     AS attempted,
                   SUM(is_correct)              AS correct,
                   SUM(score)                   AS score,
                   SUM(max_score)               AS max_score,
                   AVG(time_taken)              AS avg_time,
                   MAX(created_at)              AS last_attempt
            FROM practice_attempts WHERE student_id = ?
            GROUP BY concept ORDER BY concept
            """,
            (student_id,),
        ).fetchall()
    out = []
    for r in rows:
        attempted = int(r["attempted"])
        correct = int(r["correct"] or 0)
        out.append({
            "concept": r["concept"],
            "attempted": attempted,
            "correct": correct,
            "incorrect": attempted - correct,
            "accuracy": round(100.0 * correct / attempted, 1) if attempted else 0.0,
            "score": round(float(r["score"] or 0), 2),
            "max_score": round(float(r["max_score"] or 0), 2),
            "avg_time_seconds": round(float(r["avg_time"]), 1) if r["avg_time"] else None,
            "last_attempt": r["last_attempt"],
        })
    return out


def session_history(student_id: str, limit: int = 25) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.session_id, s.concept, s.difficulty, s.origin,
                   s.started_at, s.completed_at,
                   COUNT(a.attempt_id)          AS questions,
                   SUM(a.is_correct)            AS correct,
                   SUM(a.score)                 AS score,
                   SUM(a.max_score)             AS max_score,
                   SUM(a.time_taken)            AS time_taken
            FROM practice_sessions s
            LEFT JOIN practice_attempts a ON a.session_id = s.session_id
            WHERE s.student_id = ? AND s.completed_at IS NOT NULL
            GROUP BY s.session_id ORDER BY s.session_id DESC LIMIT ?
            """,
            (student_id, limit),
        ).fetchall()
    out = []
    for r in rows:
        questions = int(r["questions"] or 0)
        correct = int(r["correct"] or 0)
        out.append({
            "session_id": r["session_id"],
            "concept": r["concept"],
            "difficulty": r["difficulty"],
            "origin": r["origin"],
            "started_at": r["started_at"],
            "completed_at": r["completed_at"],
            "questions": questions,
            "correct": correct,
            "accuracy": round(100.0 * correct / questions, 1) if questions else 0.0,
            "score": round(float(r["score"] or 0), 2),
            "max_score": round(float(r["max_score"] or 0), 2),
            "time_taken": round(float(r["time_taken"]), 1) if r["time_taken"] else None,
        })
    return out


def totals_for_student(student_id: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS attempted, SUM(is_correct) AS correct,"
            " SUM(score) AS score, SUM(max_score) AS max_score,"
            " SUM(time_taken) AS time_taken"
            " FROM practice_attempts WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    attempted = int(row["attempted"] or 0)
    correct = int(row["correct"] or 0)
    return {
        "attempted": attempted,
        "correct": correct,
        "incorrect": attempted - correct,
        "accuracy": round(100.0 * correct / attempted, 1) if attempted else 0.0,
        "score": round(float(row["score"] or 0), 2),
        "max_score": round(float(row["max_score"] or 0), 2),
        "time_taken": round(float(row["time_taken"]), 1) if row["time_taken"] else 0.0,
    }


# --------------------------------------------------------------------------- #
# mastery history
# --------------------------------------------------------------------------- #
def log_mastery_change(student_id: str, concept: str, previous: float, updated: float,
                       practice_score: float, alpha_effective: float, n_attempts: int,
                       session_id: int | None, reason: str = "practice") -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO mastery_history (student_id, concept, previous, updated,
                                         practice_score, alpha_effective, n_attempts,
                                         session_id, reason)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (student_id, concept, float(previous), float(updated), float(practice_score),
             float(alpha_effective), int(n_attempts), session_id, reason),
        )


def mastery_history(student_id: str, concept: str | None = None, limit: int = 100) -> list[dict]:
    clause, params = "WHERE student_id = ?", [student_id]
    if concept:
        clause += " AND concept = ?"
        params.append(concept)
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM mastery_history {clause} ORDER BY id DESC LIMIT ?", params
        ).fetchall()
    return _rows(rows)


# --------------------------------------------------------------------------- #
# teacher-side aggregates
# --------------------------------------------------------------------------- #
def cohort_concept_performance() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT concept,
                   COUNT(*)                       AS attempted,
                   SUM(is_correct)                AS correct,
                   COUNT(DISTINCT student_id)     AS students
            FROM practice_attempts GROUP BY concept
            """
        ).fetchall()
    out = []
    for r in rows:
        attempted = int(r["attempted"])
        correct = int(r["correct"] or 0)
        out.append({
            "concept": r["concept"],
            "attempted": attempted,
            "correct": correct,
            "students": int(r["students"]),
            "average_accuracy": round(100.0 * correct / attempted, 1) if attempted else 0.0,
        })
    return sorted(out, key=lambda d: d["average_accuracy"])


def struggling_students(threshold: float = 50.0, min_attempts: int = 3) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT a.concept, a.student_id, s.display_name,
                   COUNT(*) AS attempted, SUM(a.is_correct) AS correct
            FROM practice_attempts a
            LEFT JOIN students s ON s.student_id = a.student_id
            GROUP BY a.concept, a.student_id
            HAVING COUNT(*) >= ?
            """,
            (min_attempts,),
        ).fetchall()
    out = []
    for r in rows:
        attempted = int(r["attempted"])
        accuracy = 100.0 * int(r["correct"] or 0) / attempted
        if accuracy < threshold:
            out.append({
                "concept": r["concept"],
                "student_id": r["student_id"],
                "display_name": r["display_name"],
                "attempted": attempted,
                "accuracy": round(accuracy, 1),
            })
    return sorted(out, key=lambda d: (d["concept"], d["accuracy"]))


def practice_totals() -> dict:
    with get_conn() as conn:
        questions = conn.execute(
            "SELECT COUNT(*) AS n FROM questions WHERE is_active = 1"
        ).fetchone()["n"]
        resources = conn.execute(
            "SELECT COUNT(*) AS n FROM resources WHERE is_active = 1"
        ).fetchone()["n"]
        papers = conn.execute("SELECT COUNT(*) AS n FROM sample_papers").fetchone()["n"]
        row = conn.execute(
            "SELECT COUNT(*) AS attempts, SUM(is_correct) AS correct,"
            " COUNT(DISTINCT student_id) AS students FROM practice_attempts"
        ).fetchone()
    attempts = int(row["attempts"] or 0)
    correct = int(row["correct"] or 0)
    return {
        "total_questions": int(questions),
        "total_resources": int(resources),
        "total_sample_papers": int(papers),
        "total_attempts": attempts,
        "students_practised": int(row["students"] or 0),
        "average_accuracy": round(100.0 * correct / attempts, 1) if attempts else 0.0,
    }


def most_attempted_questions(limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT a.question_id, q.question_text, q.concept, q.difficulty,
                   COUNT(*) AS attempted, SUM(a.is_correct) AS correct
            FROM practice_attempts a JOIN questions q ON q.question_id = a.question_id
            GROUP BY a.question_id ORDER BY attempted DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        attempted = int(r["attempted"])
        out.append({
            "question_id": r["question_id"],
            "question_text": r["question_text"],
            "concept": r["concept"],
            "difficulty": r["difficulty"],
            "attempted": attempted,
            "accuracy": round(100.0 * int(r["correct"] or 0) / attempted, 1),
        })
    return out
