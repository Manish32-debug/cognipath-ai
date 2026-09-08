"""Every tunable constant for practice selection, scoring and the learning-state
update lives here, and every one of them is overridable from the environment.

They are surfaced verbatim through `GET /api/practice/config` and echoed in the
mastery-update response, so a student or examiner can see exactly which numbers
produced a change rather than being told to trust it.
"""

from __future__ import annotations

import os

DIFFICULTIES = ("Easy", "Medium", "Hard")
QUESTION_TYPES = ("MCQ", "Numerical", "Theory")
RESOURCE_TYPES = ("Video", "Article", "Notes", "PDF", "Exercise")


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


# --- learning-state update -------------------------------------------------- #
# new = (1 - alpha_eff) * old + alpha_eff * weighted_accuracy,
# where alpha_eff = ALPHA * min(1, n_graded / N_REF).
#
# The damping term is the point: three lucky MCQs should not move a mastery
# estimate as far as twenty answered questions. Without it a student can swing
# their own learning state - and therefore their root-cause diagnosis - by
# answering a handful of easy items.
MASTERY_ALPHA = _f("COGNIPATH_MASTERY_ALPHA", 0.30)
MASTERY_N_REF = _i("COGNIPATH_MASTERY_N_REF", 8)

# Difficulty weighting for the accuracy that feeds the update. A correct Hard
# answer is stronger evidence of mastery than a correct Easy one.
DIFFICULTY_WEIGHT = {
    "Easy": _f("COGNIPATH_W_EASY", 0.7),
    "Medium": _f("COGNIPATH_W_MEDIUM", 1.0),
    "Hard": _f("COGNIPATH_W_HARD", 1.4),
}

# Theory questions are self-marked by the student. Including self-marked
# evidence in the learning-state update at full weight would let a student
# inflate their own diagnosis, so it is excluded by default.
INCLUDE_SELF_GRADED = os.getenv("COGNIPATH_INCLUDE_SELF_GRADED", "0") == "1"

# A single attempt should never move mastery further than this, in points.
MAX_DELTA_PER_SESSION = _f("COGNIPATH_MAX_MASTERY_DELTA", 15.0)


# --- practice recommendation ------------------------------------------------ #
# Question count for a recommended concept, scaled by its priority in the
# existing recommendation engine.
MIN_QUESTIONS = _i("COGNIPATH_MIN_QUESTIONS", 5)
MAX_QUESTIONS = _i("COGNIPATH_MAX_QUESTIONS", 15)

# Difficulty band selected from current mastery (0-100).
EASY_BELOW = _f("COGNIPATH_EASY_BELOW", 40.0)
HARD_ABOVE = _f("COGNIPATH_HARD_ABOVE", 65.0)

MAX_RECOMMENDED_CONCEPTS = _i("COGNIPATH_MAX_RECOMMENDED_CONCEPTS", 5)

# --- uploads ---------------------------------------------------------------- #
MAX_PDF_BYTES = _i("COGNIPATH_MAX_PDF_BYTES", 10 * 1024 * 1024)
ALLOWED_PDF_TYPES = ("application/pdf",)


def as_dict() -> dict:
    """Serialisable snapshot returned by the API alongside any mastery change."""
    return {
        "mastery_update": {
            "formula": "new = (1 - alpha_eff) * old + alpha_eff * weighted_accuracy",
            "alpha": MASTERY_ALPHA,
            "alpha_effective": "alpha * min(1, graded_attempts / n_ref)",
            "n_ref": MASTERY_N_REF,
            "difficulty_weights": DIFFICULTY_WEIGHT,
            "include_self_graded": INCLUDE_SELF_GRADED,
            "max_delta_per_session": MAX_DELTA_PER_SESSION,
        },
        "practice_selection": {
            "min_questions": MIN_QUESTIONS,
            "max_questions": MAX_QUESTIONS,
            "easy_below_mastery": EASY_BELOW,
            "hard_above_mastery": HARD_ABOVE,
            "max_recommended_concepts": MAX_RECOMMENDED_CONCEPTS,
        },
        "disclaimer": (
            "Mastery is a learning-state estimate maintained by this application "
            "from practice evidence and simulated or self-reported starting "
            "values. It is not a psychometric measurement or a validated "
            "assessment score."
        ),
    }
