"""Turns the existing concept ranking into a concrete practice prescription.

This module adds no new ranking logic. `app.recommendations.engine.score_concepts`
already orders concepts by

    0.45 * root-cause evidence + 0.30 * mastery gap
  + 0.15 * downstream impact   + 0.10 * predicted risk

and that ordering is the one used here. What this module decides is only *how
much and how hard*: how many questions to prescribe for a ranked concept, at
which difficulty, and which library resources to attach. Nothing is hardcoded per
student - every number below is derived from that student's stored mastery and
root-cause output.
"""

from __future__ import annotations

import networkx as nx

from app.database import practice_db
from app.graph.knowledge_graph import get_graph, label, subject_of, unit_of
from app.graph.root_cause import MASTERY_TARGET
from app.practice import config
from app.recommendations import engine


def difficulty_for(mastery: float) -> str:
    """Meet the student where they are: rebuild from Easy, stretch when close."""
    if mastery < config.EASY_BELOW:
        return "Easy"
    if mastery > config.HARD_ABOVE:
        return "Hard"
    return "Medium"


def question_count_for(priority_score: float, top_score: float) -> int:
    """Scale between MIN and MAX questions by priority relative to the top concept."""
    if top_score <= 0:
        return config.MIN_QUESTIONS
    share = max(0.0, min(1.0, priority_score / top_score))
    span = config.MAX_QUESTIONS - config.MIN_QUESTIONS
    return int(round(config.MIN_QUESTIONS + span * share))


def explain_selection(ranked: dict, dependents: list[str]) -> str:
    """Feature 13: why this concept was chosen, in terms the graph can justify."""
    concept_label = ranked["label"]
    mastery = ranked["mastery"]
    parts = [
        f"{concept_label} is at {mastery:.0f}% mastery against a {MASTERY_TARGET:.0f}% target."
    ]
    if ranked["is_root_cause"]:
        parts.append(
            "Backward propagation over the prerequisite graph identifies it as a likely "
            "root cause rather than a symptom, so practising it should unblock the "
            "concepts built on top of it."
        )
    if dependents:
        names = ", ".join(label(d) for d in dependents[:3])
        more = f" and {len(dependents) - 3} more" if len(dependents) > 3 else ""
        parts.append(f"{len(dependents)} downstream concept(s) depend on it: {names}{more}.")
    if not ranked["is_root_cause"] and not dependents:
        parts.append(
            "It has no dependent concepts in this curriculum, so it is recommended on "
            "the size of its own mastery gap."
        )
    parts.append(
        f"Difficulty is set to {difficulty_for(mastery)} from current mastery."
    )
    return " ".join(parts)


def recommended_practice(mastery: dict[str, float], root_result: dict, risk_tier: str,
                         max_concepts: int | None = None,
                         subject: str | None = None) -> dict:
    """Prescribe practice per weak concept, ordered by the existing priority score.

    `subject` (multi-subject upgrade) restricts the plan to one subject's
    concepts. It filters the ranked list rather than altering the scoring, so a
    concept keeps the same priority in the subject view and the all-subject view.
    """
    max_concepts = max_concepts or config.MAX_RECOMMENDED_CONCEPTS
    ranked = engine.score_concepts(mastery, root_result, risk_tier)
    if subject:
        ranked = [r for r in ranked if subject_of(r["concept"]) == subject]
    if not ranked:
        return {
            "items": [],
            "message": (
                f"No concept is below the {MASTERY_TARGET:.0f}% mastery target - "
                "practice is optional right now."
            ),
            "config": config.as_dict()["practice_selection"],
        }

    graph = get_graph()
    top_score = ranked[0]["priority_score"]
    selected = ranked[:max_concepts]
    available = practice_db.question_counts_by_concept()
    resources = practice_db.resources_for_concepts([r["concept"] for r in selected])

    items = []
    for r in selected:
        concept = r["concept"]
        difficulty = difficulty_for(r["mastery"])
        requested = question_count_for(r["priority_score"], top_score)

        by_difficulty = available.get(concept, {})
        in_band = by_difficulty.get(difficulty, 0)
        total_for_concept = sum(by_difficulty.values())
        # `build_session_questions` serves the target difficulty first and tops
        # up from adjacent difficulties when the band is thin, so the deliverable
        # count is bounded by the concept total, not by the band. Reporting the
        # band alone under-serves the student whenever the bank is uneven.
        deliverable = min(requested, total_for_concept)

        dependents = sorted(nx.descendants(graph, concept)) if concept in graph else []

        items.append({
            "concept": concept,
            "label": r["label"],
            "subject": subject_of(concept),
            "unit": unit_of(concept),
            "mastery": r["mastery"],
            "risk": r["risk"],
            "is_root_cause": r["is_root_cause"],
            "priority": r["priority"],
            "priority_score": r["priority_score"],
            "recommended_questions": requested,
            "available_questions": deliverable,
            "difficulty": difficulty,
            "questions_in_bank": total_for_concept,
            "downstream_concepts": len(dependents),
            "reason": explain_selection(r, dependents),
            "resources": [
                {
                    "resource_id": res["resource_id"],
                    "title": res["title"],
                    "resource_type": res["resource_type"],
                    "difficulty": res["difficulty"],
                    "estimated_minutes": res["estimated_minutes"],
                    "url": res["url"],
                    "description": res["description"],
                }
                for res in resources.get(concept, [])
            ],
        })

    return {
        "items": items,
        "n_concepts_below_target": len(ranked),
        "message": None,
        "config": config.as_dict()["practice_selection"],
    }


def build_session_questions(student_id: str, concept: str, difficulty: str | None,
                            count: int) -> list[dict]:
    """Fetch questions for a session, topping up from other difficulties if short."""
    picked = practice_db.sample_questions(concept, difficulty, count, student_id=student_id)
    if len(picked) < count and difficulty:
        seen = {q["question_id"] for q in picked}
        for fallback in ("Easy", "Medium", "Hard"):
            if fallback == difficulty:
                continue
            extra = practice_db.sample_questions(
                concept, fallback, count - len(picked), student_id=student_id
            )
            picked.extend(q for q in extra if q["question_id"] not in seen)
            seen.update(q["question_id"] for q in extra)
            if len(picked) >= count:
                break
    return picked[:count]
