"""Seed the demo cohort.

Run:  python -m app.database.seed      (from backend/)

What is real and what is not
----------------------------
* The feature rows come from actual records of the UCI Student Performance
  dataset - they are real anonymised students, re-keyed as DEMO001... and
  given placeholder display names. No names exist in the source data.
* Concept mastery is SIMULATED (see `app.ml.mastery_simulator`) and every row is
  stored with source='simulated'. The UI shows this label.
* Predictions are NOT seeded. They are produced by the trained models when the
  API is called.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.security import hash_password
from app.database import db
from app.ml import features as F
from app.ml.dataset import load_prepared
from app.ml.mastery_simulator import mastery_records

DEMO_PASSWORD = "demo1234"          # documented demo credential, not a secret
TEACHER_PASSWORD = "teach1234"

FIRST_NAMES = [
    "Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ananya", "Vikram", "Sneha",
    "Arjun", "Priya", "Nikhil", "Isha", "Farhan", "Lakshmi", "Yusuf", "Tara",
    "Dev", "Riya", "Manish", "Aisha",
]
LAST_NAMES = ["Sharma", "Iyer", "Nair", "Reddy", "Khan", "Menon", "Gupta", "Rao"]


def _display_name(i: int) -> str:
    return f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i // len(FIRST_NAMES)) % len(LAST_NAMES)]}"


def seed(n: int | None = None, reset_users: bool = False) -> dict:
    n = n or settings.demo_cohort_size
    db.init_db()
    df = load_prepared()
    # Deterministic sample so the demo cohort is identical on every machine.
    sample = df.sample(n=min(n, len(df)), random_state=7).reset_index(drop=True)

    created = 0
    for i, row in sample.iterrows():
        sid = f"DEMO{i + 1:03d}"
        features = {c: (float(row[c]) if c in F.NUMERIC_FEATURES else str(row[c]))
                    for c in F.FEATURES}
        features["actual_G3"] = float(row["G3"])   # kept for teacher-side validation only
        db.upsert_student(
            sid,
            features,
            display_name=_display_name(i),
            is_demo=True,
        )
        db.set_mastery(
            sid,
            mastery_records(
                sid,
                g1=row["G1"],
                g2=row["G2"],
                studytime=row["studytime"],
                failures=row["failures"],
                attendance_pct=row["attendance_pct"],
            ),
        )
        if not db.user_exists(sid.lower()):
            h, s = hash_password(DEMO_PASSWORD)
            db.create_user(sid.lower(), h, s, "student", student_id=sid,
                           full_name=_display_name(i))
        created += 1

    if not db.user_exists("teacher") or reset_users:
        if not db.user_exists("teacher"):
            h, s = hash_password(TEACHER_PASSWORD)
            db.create_user("teacher", h, s, "teacher", full_name="Faculty Coordinator")

    return {
        "students_seeded": created,
        "teacher_login": {"username": "teacher", "password": TEACHER_PASSWORD},
        "sample_student_login": {"username": "demo001", "password": DEMO_PASSWORD},
        "mastery_source": "simulated",
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(seed(), indent=2))
