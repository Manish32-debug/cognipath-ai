"""Answer grading.

Three question types, three honest grading strategies:

* MCQ       - exact match on the option key (or the option text, so a client that
              posts the answer text instead of "B" still works).
* Numerical - float comparison within a per-question tolerance, defaulting to a
              relative 1%. Accepts "3,14" and "3.14e0".
* Theory    - NOT auto-graded. There is no defensible way to mark free text
              against a model answer without an NLP model this project does not
              have, and a keyword-overlap heuristic dressed up as marking would
              be exactly the kind of fake result the brief forbids. The student
              is shown the model answer and marks themselves; the attempt is
              stored with graded_by='self' and is excluded from the
              learning-state update by default.
"""

from __future__ import annotations

import re


class GradingError(ValueError):
    pass


def _to_float(text: str) -> float | None:
    if text is None:
        return None
    cleaned = str(text).strip().replace(",", ".").replace(" ", "")
    cleaned = re.sub(r"[^0-9eE.+\-/]", "", cleaned)
    if not cleaned:
        return None
    if "/" in cleaned:  # accept simple fractions like 3/4
        parts = cleaned.split("/")
        if len(parts) == 2:
            try:
                num, den = float(parts[0]), float(parts[1])
                return num / den if den else None
            except (ValueError, ZeroDivisionError):
                return None
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _grade_mcq(question: dict, answer: str | None) -> bool:
    if answer is None:
        return False
    correct = str(question["correct_answer"]).strip()
    given = str(answer).strip()
    if given.casefold() == correct.casefold():
        return True
    # Client may have submitted the option text rather than its key.
    for option in question.get("options") or []:
        key = str(option.get("key", "")).strip()
        text = str(option.get("text", "")).strip()
        if key.casefold() == correct.casefold() and given.casefold() == text.casefold():
            return True
    return False


def _grade_numerical(question: dict, answer: str | None) -> bool:
    expected = _to_float(question["correct_answer"])
    given = _to_float(answer)
    if expected is None or given is None:
        return False
    tolerance = question.get("tolerance")
    if tolerance is None:
        tolerance = max(abs(expected) * 0.01, 1e-9)
    return abs(given - expected) <= float(tolerance)


def grade(question: dict, answer: str | None,
          self_marked_correct: bool | None = None) -> tuple[bool, str]:
    """Return (is_correct, graded_by)."""
    qtype = question["question_type"]

    if qtype == "MCQ":
        return _grade_mcq(question, answer), "auto"
    if qtype == "Numerical":
        return _grade_numerical(question, answer), "auto"
    if qtype == "Theory":
        if self_marked_correct is None:
            raise GradingError(
                "Theory questions are self-marked: send self_marked_correct "
                "(true/false) after reading the model answer."
            )
        return bool(self_marked_correct), "self"

    raise GradingError(f"Unsupported question type '{qtype}'")


def score_attempt(question: dict, is_correct: bool) -> tuple[float, float]:
    """Return (score, max_score). No partial credit - a wrong answer scores zero."""
    max_score = float(question.get("marks", 1))
    return (max_score if is_correct else 0.0), max_score


def summarise(attempts: list[dict], elapsed_seconds: float | None = None) -> dict:
    """Session-level summary from graded attempts."""
    total = len(attempts)
    correct = sum(1 for a in attempts if a["is_correct"])
    score = sum(a["score"] for a in attempts)
    max_score = sum(a["max_score"] for a in attempts)
    timed = [a["time_taken"] for a in attempts if a.get("time_taken") is not None]

    per_concept: dict[str, dict] = {}
    for a in attempts:
        bucket = per_concept.setdefault(a["concept"], {"attempted": 0, "correct": 0})
        bucket["attempted"] += 1
        bucket["correct"] += int(a["is_correct"])

    return {
        "total_questions": total,
        "correct": correct,
        "incorrect": total - correct,
        "score": round(score, 2),
        "max_score": round(max_score, 2),
        "accuracy": round(100.0 * correct / total, 1) if total else 0.0,
        "time_taken_seconds": round(
            elapsed_seconds if elapsed_seconds is not None else sum(timed), 1
        ),
        "concept_performance": [
            {
                "concept": concept,
                "attempted": v["attempted"],
                "correct": v["correct"],
                "accuracy": round(100.0 * v["correct"] / v["attempted"], 1),
            }
            for concept, v in sorted(per_concept.items())
        ],
    }
