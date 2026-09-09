"""Context-aware study advice.

The existing concept-level engine answers *what* to work on (which concept, at
what priority). This module answers *how* to work on it, which is a different
question and needs different inputs: a student with high attendance and falling
marks needs something different from one who has stopped turning up.

This is **rule-based**, deliberately and stated as such. Each rule declares the
condition it fires on, so a reviewer can read the table and predict the output.
There is no model here and none is claimed.

Inputs used: attendance, study time, subject trend, recent average, concept
mastery, practice accuracy. All of them are stored values, not guesses.
"""

from __future__ import annotations

# Thresholds, all named.
HIGH_ATTENDANCE = 85.0
LOW_ATTENDANCE = 70.0
LOW_STUDY_TIME = 2          # UCI scale: 1 = <2h, 2 = 2-5h weekly
HIGH_MASTERY = 65.0
LOW_MASTERY = 45.0
GOOD_PRACTICE_ACCURACY = 0.7
WEAK_SCORE = 60.0


def advise(context: dict) -> list[dict]:
    """Return matching strategies, most specific first.

    `context` keys (all optional; a missing key simply cannot fire a rule):
        attendance_pct, studytime, trend, recent_average,
        average_mastery, practice_accuracy, n_practice_attempts
    """
    attendance = context.get("attendance_pct")
    studytime = context.get("studytime")
    trend = context.get("trend")
    recent = context.get("recent_average")
    mastery = context.get("average_mastery")
    accuracy = context.get("practice_accuracy")
    attempts = context.get("n_practice_attempts") or 0

    out: list[dict] = []

    # --- the three canonical cases from the brief ------------------------- #
    if (attendance is not None and attendance >= HIGH_ATTENDANCE
            and recent is not None and recent < WEAK_SCORE):
        out.append({
            "strategy": "Conceptual revision, not more attendance",
            "advice": ("Focus on conceptual revision and worked examples. You are attending "
                       "consistently, so the gap is in how the material is being absorbed "
                       "rather than in exposure to it."),
            "why": f"Attendance is {attendance:.0f}% but recent scores average {recent:.0f}%.",
            "actions": ["Re-derive each formula from first principles",
                        "Work through solved examples before attempting new problems",
                        "Explain one concept aloud without notes to test understanding"],
            "rule": "attendance >= 85% and recent average < 60%",
        })

    if (attendance is not None and attendance < LOW_ATTENDANCE
            and trend in ("Declining", "Strongly declining")):
        out.append({
            "strategy": "Short daily recovery schedule",
            "advice": ("Follow a short daily recovery schedule and revise the topics covered "
                       "while you were away. Rebuilding contact with the material matters more "
                       "right now than long study sessions."),
            "why": f"Attendance is {attendance:.0f}% and performance is {trend.lower()}.",
            "actions": ["Book 30 focused minutes at the same time each day",
                        "List the topics covered in missed sessions and clear them oldest first",
                        "Ask a peer or the instructor for notes from the missed weeks"],
            "rule": "attendance < 70% and a declining trend",
        })

    if (mastery is not None and mastery >= HIGH_MASTERY
            and recent is not None and recent < WEAK_SCORE):
        out.append({
            "strategy": "Timed mock tests, not basic revision",
            "advice": ("Practise timed mock tests rather than basic concept revision. Your "
                       "concept mastery is reasonable, so the loss is happening under exam "
                       "conditions - pace, question reading, or presentation."),
            "why": f"Average mastery is {mastery:.0f}% but recent scores average {recent:.0f}%.",
            "actions": ["Attempt a full past paper against the clock",
                        "Review only the questions lost to time or misreading",
                        "Practise writing solutions in the format the paper expects"],
            "rule": "average mastery >= 65% but recent average < 60%",
        })

    # --- supporting rules -------------------------------------------------- #
    if studytime is not None and studytime <= LOW_STUDY_TIME and (recent or 100) < WEAK_SCORE:
        out.append({
            "strategy": "Increase contact hours before adding difficulty",
            "advice": ("Reported weekly study time is low for the results you are getting. "
                       "Add one more scheduled session per week before moving to harder material."),
            "why": f"Reported study time band {studytime} of 4 with recent average {recent:.0f}%."
                   if recent is not None else f"Reported study time band {studytime} of 4.",
            "actions": ["Add one fixed 45-minute session to your week",
                        "Protect it in your calendar the way you would a class"],
            "rule": "study time band <= 2 and recent average < 60%",
        })

    if attempts >= 5 and accuracy is not None and accuracy < 0.5 and (mastery or 0) >= LOW_MASTERY:
        out.append({
            "strategy": "Drop back a difficulty band",
            "advice": ("Practice accuracy is low even though stored mastery is not. Work at an "
                       "easier difficulty until accuracy is above 70%, then step back up."),
            "why": f"{attempts} attempts at {accuracy * 100:.0f}% accuracy.",
            "actions": ["Switch the practice difficulty to Easy for this concept",
                        "Read the explanation on every question, including correct ones"],
            "rule": "at least 5 attempts, accuracy < 50%, mastery >= 45%",
        })

    if accuracy is not None and accuracy >= GOOD_PRACTICE_ACCURACY and attempts >= 5:
        out.append({
            "strategy": "Step up the difficulty",
            "advice": ("Practice accuracy is high. Move to harder and application-style "
                       "questions so practice keeps producing new information."),
            "why": f"{attempts} attempts at {accuracy * 100:.0f}% accuracy.",
            "actions": ["Switch this concept's practice to Hard",
                        "Attempt questions that combine two concepts"],
            "rule": "at least 5 attempts with accuracy >= 70%",
        })

    if trend in ("Volatile",):
        out.append({
            "strategy": "Build consistency",
            "advice": ("Results swing between assessments. Consistent short revision beats "
                       "intense preparation before each test."),
            "why": "Assessment-to-assessment variation is high.",
            "actions": ["Revise each topic again 3 days after first studying it",
                        "Keep a one-page summary per unit and review it weekly"],
            "rule": "trend classified as Volatile",
        })

    if not out:
        out.append({
            "strategy": "Maintain",
            "advice": ("Nothing in the current data suggests a change of approach. Keep the "
                       "current routine and use spaced revision to hold the gains."),
            "why": "No rule condition matched this student's current signals.",
            "actions": ["Review each concept once a fortnight",
                        "Use practice to check retention rather than to learn new material"],
            "rule": "default (no other rule fired)",
        })

    return out


def rule_table() -> list[dict]:
    """The full rule set, for the UI's 'why did I get this advice?' panel."""
    return [
        {"rule": "attendance >= 85% and recent average < 60%", "strategy": "Conceptual revision"},
        {"rule": "attendance < 70% and a declining trend", "strategy": "Daily recovery schedule"},
        {"rule": "average mastery >= 65% but recent average < 60%", "strategy": "Timed mock tests"},
        {"rule": "study time band <= 2 and recent average < 60%", "strategy": "Increase contact hours"},
        {"rule": "at least 5 attempts, accuracy < 50%, mastery >= 45%", "strategy": "Drop a difficulty band"},
        {"rule": "at least 5 attempts with accuracy >= 70%", "strategy": "Step up the difficulty"},
        {"rule": "trend classified as Volatile", "strategy": "Build consistency"},
        {"rule": "default", "strategy": "Maintain"},
    ]
