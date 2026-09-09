"""Seed the multi-subject academic record: subjects, assessment definitions and
per-student results.

Run:  python -m app.database.seed_academics      (from backend/)

What is real and what is simulated (Part 23)
--------------------------------------------
* The demo students themselves come from real anonymised UCI Student Performance
  records - their study time, absences, past failures and period grades are real
  data (see `app/database/seed.py`).
* The **assessment series are SIMULATED**. No public dataset gives six
  assessments per subject per student, so this script generates them from a
  documented, seeded process anchored to each student's REAL academic ability
  (their G1/G2 and failures). Every generated row is stored with
  `source = 'simulated'`, and the API and UI show that label.
* Concept mastery is also SIMULATED. The UCI dataset does not contain
  concept-level assessment results, so mastery is derived from the simulated
  subject assessment performance and stored with `source = 'simulated'`.
* Nothing here is random noise dressed up as data: a student who was weak in the
  source dataset is weak in the generated series, subject offsets are stable per
  student, and trends are drawn from a small set of realistic shapes so the
  dashboard shows genuine improving, declining, stable and volatile cases.

Generation model
----------------
    base_ability      = 100 * (0.6*G2 + 0.4*G1) / 20, minus 6 per past failure
    subject_offset    = deterministic per (student, subject), in [-14, +12]
    trend shape       = one of improving / declining / stable / volatile / dip,
                        chosen per (student, subject) by seeded RNG
    assessment k       = base + subject_offset + shape(k) + N(0, 4), clipped 15..98

Concept mastery
---------------
    recent_subject_score = mean of the latest three recorded assessments
    concept_mastery      = recent_subject_score + deterministic concept variation
                            + N(0, 7), clipped 15..98

All concept mastery rows are explicitly stored with source='simulated'.
"""

from __future__ import annotations

import hashlib

import numpy as np

from app.database import academics_db, db
from app.graph.knowledge_graph import SUBJECTS, CONCEPT_SUBJECT


# --------------------------------------------------------------------------- #
# Assessment configuration
# --------------------------------------------------------------------------- #

# Assessment types: configuration, not a CHECK constraint.
ASSESSMENT_TYPES = [
    {
        "type_id": "cat",
        "name": "Continuous Assessment Test",
        "weight": 1.0,
        "is_terminal": 0,
    },
    {
        "type_id": "assignment",
        "name": "Assignment",
        "weight": 0.5,
        "is_terminal": 0,
    },
    {
        "type_id": "midterm",
        "name": "Midterm Examination",
        "weight": 2.0,
        "is_terminal": 0,
    },
    {
        "type_id": "quiz",
        "name": "Quiz",
        "weight": 0.5,
        "is_terminal": 0,
    },
    {
        "type_id": "final",
        "name": "Final Examination",
        "weight": 3.0,
        "is_terminal": 1,
    },
]


# The default schedule applied to every subject.
# The final exam is defined but deliberately left unrecorded because it is
# the assessment the system is predicting.
DEFAULT_SCHEDULE = [
    {
        "assessment_type": "cat",
        "name": "CAT 1",
        "assessment_order": 1,
        "max_marks": 50,
        "weight": 1.0,
    },
    {
        "assessment_type": "assignment",
        "name": "Assignment 1",
        "assessment_order": 2,
        "max_marks": 20,
        "weight": 0.5,
    },
    {
        "assessment_type": "cat",
        "name": "CAT 2",
        "assessment_order": 3,
        "max_marks": 50,
        "weight": 1.0,
    },
    {
        "assessment_type": "midterm",
        "name": "Midterm",
        "assessment_order": 4,
        "max_marks": 100,
        "weight": 2.0,
    },
    {
        "assessment_type": "assignment",
        "name": "Assignment 2",
        "assessment_order": 5,
        "max_marks": 20,
        "weight": 0.5,
    },
    {
        "assessment_type": "cat",
        "name": "CAT 3",
        "assessment_order": 6,
        "max_marks": 50,
        "weight": 1.0,
    },
    {
        "assessment_type": "final",
        "name": "Final Examination",
        "assessment_order": 7,
        "max_marks": 100,
        "weight": 3.0,
    },
]


# --------------------------------------------------------------------------- #
# Subject metadata
# --------------------------------------------------------------------------- #

SUBJECT_META = {
    "mathematics": {
        "semester": "Semester 3",
        "credits": 4.0,
    },
    "dsp": {
        "semester": "Semester 5",
        "credits": 4.0,
    },
    "vlsi": {
        "semester": "Semester 5",
        "credits": 3.0,
    },
    "networks": {
        "semester": "Semester 4",
        "credits": 3.0,
    },
    "dbms": {
        "semester": "Semester 4",
        "credits": 4.0,
    },
    "aiml": {
        "semester": "Semester 6",
        "credits": 4.0,
    },
}


# --------------------------------------------------------------------------- #
# Simulated trend profiles
# --------------------------------------------------------------------------- #

# Trend shapes as offsets applied across the six recorded assessments.
SHAPES = {
    "improving": [-9, -5, -1, 3, 6, 9],
    "strong_improving": [-14, -9, -3, 3, 9, 14],
    "declining": [9, 5, 1, -3, -7, -11],
    "strong_decline": [12, 6, 0, -6, -12, -18],
    "stable": [0, 1, -1, 0, 1, -1],
    "volatile": [10, -9, 8, -11, 7, -8],
    "late_dip": [4, 5, 3, -2, -8, -13],
}

SHAPE_POOL = [
    "improving",
    "strong_improving",
    "declining",
    "strong_decline",
    "stable",
    "stable",
    "volatile",
    "late_dip",
]

NOISE_SD = 4.0
FAILURE_PENALTY = 6.0


# --------------------------------------------------------------------------- #
# Deterministic random seed
# --------------------------------------------------------------------------- #

def _seed_for(*parts: str) -> int:
    """Return a deterministic integer seed for the supplied identifiers."""
    return int(
        hashlib.sha256("|".join(parts).encode()).hexdigest()[:8],
        16,
    )


# --------------------------------------------------------------------------- #
# Student ability
# --------------------------------------------------------------------------- #

def base_ability(features: dict) -> float:
    """Anchor the simulation to the student's REAL academic record."""
    g1 = float(features.get("G1", 10))
    g2 = float(features.get("G2", 10))
    failures = float(features.get("failures", 0))

    ability = 100.0 * (0.6 * g2 + 0.4 * g1) / 20.0
    ability -= FAILURE_PENALTY * failures

    return float(np.clip(ability, 20.0, 95.0))


# --------------------------------------------------------------------------- #
# Assessment series generation
# --------------------------------------------------------------------------- #

def generate_series(
    student_id: str,
    subject_id: str,
    features: dict,
    n_points: int = 6,
) -> tuple[list[float], str]:
    """Generate deterministic simulated assessment percentages.

    Returns:
        (percentages, trend_shape_name)
    """
    rng = np.random.default_rng(
        _seed_for(student_id, subject_id)
    )

    ability = base_ability(features)

    # Stable subject-specific strength/weakness.
    subject_offset = float(rng.uniform(-14, 12))

    # Stable trend profile for this student-subject pair.
    shape_name = SHAPE_POOL[
        int(rng.integers(0, len(SHAPE_POOL)))
    ]

    shape = SHAPES[shape_name]

    values = []

    for k in range(n_points):
        offset = shape[k % len(shape)]

        value = (
            ability
            + subject_offset
            + offset
            + rng.normal(0, NOISE_SD)
        )

        values.append(
            float(np.clip(value, 15.0, 98.0))
        )

    return values, shape_name


# --------------------------------------------------------------------------- #
# Concept mastery generation
# --------------------------------------------------------------------------- #

def generate_concept_mastery(
    student_id: str,
    subject_id: str,
    assessment_values: list[float],
) -> list[dict]:
    """Generate subject-specific simulated concept mastery.

    Concept-level assessment data is not present in the UCI source dataset.
    Therefore mastery is derived from the student's simulated performance
    in the corresponding subject.

    The latest three recorded assessments are used as the strongest signal,
    while deterministic per-concept variation prevents every concept from
    receiving exactly the same score.
    """
    concepts = [
        concept_id
        for concept_id, mapped_subject in CONCEPT_SUBJECT.items()
        if mapped_subject == subject_id
    ]

    if not concepts:
        return []

    # Use the latest three recorded assessments.
    recent_values = assessment_values[-3:]

    if not recent_values:
        return []

    recent_subject_score = float(
        np.mean(recent_values)
    )

    records = []

    for concept_id in concepts:
        rng = np.random.default_rng(
            _seed_for(
                student_id,
                subject_id,
                concept_id,
                "mastery",
            )
        )

        # Deterministic concept-level variation.
        variation = float(
            rng.normal(0, 7)
        )

        mastery = float(
            np.clip(
                recent_subject_score + variation,
                15.0,
                98.0,
            )
        )

        records.append(
            {
                "concept": concept_id,
                "mastery": round(mastery, 1),
                "source": "simulated",
            }
        )

    return records


# --------------------------------------------------------------------------- #
# Subjects + assessment definitions
# --------------------------------------------------------------------------- #

def seed_subjects_and_assessments() -> dict[str, list[int]]:
    """Create/update all subjects and their assessment definitions."""
    db.init_db()

    for assessment_type in ASSESSMENT_TYPES:
        academics_db.upsert_assessment_type(
            assessment_type
        )

    assessment_ids: dict[str, list[int]] = {}

    for subject_id, (
        name,
        code,
        description,
    ) in SUBJECTS.items():

        meta = SUBJECT_META.get(
            subject_id,
            {},
        )

        academics_db.upsert_subject(
            {
                "subject_id": subject_id,
                "name": name,
                "code": code,
                "description": description,
                "semester": meta.get("semester"),
                "credits": meta.get("credits"),
            }
        )

        ids = []

        for spec in DEFAULT_SCHEDULE:
            ids.append(
                academics_db.upsert_assessment(
                    {
                        "subject_id": subject_id,
                        **spec,
                    }
                )
            )

        assessment_ids[subject_id] = ids

    return assessment_ids


# --------------------------------------------------------------------------- #
# Student results
# --------------------------------------------------------------------------- #

def seed_results(limit: int | None = None) -> dict:
    """Generate assessment results and concept mastery for demo students."""
    assessment_ids = seed_subjects_and_assessments()

    students = [
        student
        for student in db.list_students()
        if student.get("is_demo")
    ]

    if limit:
        students = students[:limit]

    recorded = 0
    mastery_recorded = 0
    shapes: dict[str, int] = {}

    for student in students:

        student_id = student["student_id"]
        features = student["features"]

        for subject_id, ids in assessment_ids.items():

            # --------------------------------------------------------------- #
            # Generate six recorded assessment values.
            # --------------------------------------------------------------- #
            values, shape = generate_series(
                student_id,
                subject_id,
                features,
            )

            shapes[shape] = (
                shapes.get(shape, 0) + 1
            )

            # --------------------------------------------------------------- #
            # Generate subject-specific concept mastery.
            # --------------------------------------------------------------- #
            mastery_records = generate_concept_mastery(
                student_id,
                subject_id,
                values,
            )

            if mastery_records:
                db.set_mastery(
                    student_id,
                    mastery_records,
                )

                mastery_recorded += len(
                    mastery_records
                )

            # --------------------------------------------------------------- #
            # Store assessment results.
            #
            # ids[:-1] means the final examination is intentionally NOT
            # recorded because it is the outcome predicted by the ML model.
            # --------------------------------------------------------------- #
            for assessment_id, percentage in zip(
                ids[:-1],
                values,
            ):

                assessment = academics_db.get_assessment(
                    assessment_id
                )

                marks = round(
                    percentage
                    / 100.0
                    * assessment["max_marks"],
                    1,
                )

                academics_db.record_result(
                    student_id,
                    assessment_id,
                    marks,
                    source="simulated",
                )

                recorded += 1

    counts = academics_db.result_counts()

    return {
        "subjects": len(assessment_ids),
        "assessments_per_subject": len(DEFAULT_SCHEDULE),
        "students": len(students),
        "results_recorded": recorded,
        "mastery_records": mastery_recorded,
        "trend_shapes_used": shapes,
        "totals": counts,
        "labelling": (
            "every generated assessment and concept mastery row "
            "is stored with source='simulated'"
        ),
        "note": (
            "Assessment series and concept mastery are simulated from "
            "each student's real UCI record. The final examination is "
            "left unrecorded because it is the predicted outcome."
        ),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

if __name__ == "__main__":  # pragma: no cover
    import json

    print(
        json.dumps(
            seed_results(),
            indent=2,
        )
    )