"""Learning-state update: how practice performance moves concept mastery.

    weighted_accuracy = sum(w_d * correct) / sum(w_d)        w from DIFFICULTY_WEIGHT
    alpha_eff         = ALPHA * min(1, n_graded / N_REF)
    new               = (1 - alpha_eff) * old + alpha_eff * weighted_accuracy * 100

The result is clamped to [0, 100] (the `concept_mastery` CHECK constraint) and to
+/- MAX_DELTA_PER_SESSION points, and every change is written to
`mastery_history` with the inputs that produced it.

What this is and is not
-----------------------
This is a bookkeeping rule for an application-maintained learning-state estimate.
It is not a psychometric model, not item-response theory, and not a validated
measurement of what a student knows. The starting values for demo students are
simulated and labelled as such throughout the UI. The value of the rule is that
it is transparent and reproducible: given the stored attempts and the config, any
mastery figure in the system can be recomputed by hand.

Mastery is not an input to the GPA / pass / risk models - `StudentFeatures`
contains no mastery fields - so this update cannot change a prediction or its
SHAP explanation. It feeds the prerequisite graph, root-cause analysis,
recommendations, the weekly plan and the cognitive twin.
"""

from __future__ import annotations

from app.database import db, practice_db
from app.practice import config


def weighted_accuracy(attempts: list[dict]) -> tuple[float, int]:
    """Difficulty-weighted accuracy in [0, 1] plus the number of graded attempts."""
    usable = [
        a for a in attempts
        if config.INCLUDE_SELF_GRADED or a.get("graded_by", "auto") == "auto"
    ]
    if not usable:
        return 0.0, 0

    numerator = denominator = 0.0
    for a in usable:
        w = config.DIFFICULTY_WEIGHT.get(a["difficulty"], 1.0)
        denominator += w
        if a["is_correct"]:
            numerator += w
    return (numerator / denominator if denominator else 0.0), len(usable)


def project(old_mastery: float, attempts: list[dict]) -> dict | None:
    """Compute the new mastery without writing anything. None if nothing usable."""
    accuracy, n = weighted_accuracy(attempts)
    if n == 0:
        return None

    alpha_eff = config.MASTERY_ALPHA * min(1.0, n / config.MASTERY_N_REF)
    target = accuracy * 100.0
    raw = (1.0 - alpha_eff) * float(old_mastery) + alpha_eff * target

    delta = raw - float(old_mastery)
    capped = max(-config.MAX_DELTA_PER_SESSION, min(config.MAX_DELTA_PER_SESSION, delta))
    new = max(0.0, min(100.0, float(old_mastery) + capped))

    return {
        "previous": round(float(old_mastery), 1),
        "updated": round(new, 1),
        "delta": round(new - float(old_mastery), 1),
        "weighted_accuracy": round(accuracy * 100.0, 1),
        "alpha_effective": round(alpha_eff, 4),
        "graded_attempts": n,
        "capped": abs(delta) > config.MAX_DELTA_PER_SESSION,
    }


def apply(student_id: str, attempts: list[dict], current_mastery: dict[str, float],
          session_id: int | None = None) -> list[dict]:
    """Update mastery for every concept touched by `attempts`.

    Writes through the existing `db.set_mastery` with source='practice' so the
    provenance label the UI already renders stays truthful, and appends one
    `mastery_history` row per concept for the trajectory.
    """
    by_concept: dict[str, list[dict]] = {}
    for a in attempts:
        by_concept.setdefault(a["concept"], []).append(a)

    records, changes = [], []
    for concept, concept_attempts in by_concept.items():
        old = float(current_mastery.get(concept, 50.0))
        result = project(old, concept_attempts)
        if result is None:
            continue

        records.append({"concept": concept, "mastery": result["updated"], "source": "practice"})
        practice_db.log_mastery_change(
            student_id=student_id,
            concept=concept,
            previous=result["previous"],
            updated=result["updated"],
            practice_score=result["weighted_accuracy"],
            alpha_effective=result["alpha_effective"],
            n_attempts=result["graded_attempts"],
            session_id=session_id,
        )
        changes.append({"concept": concept, **result})

    if records:
        db.set_mastery(student_id, records)
    return changes
