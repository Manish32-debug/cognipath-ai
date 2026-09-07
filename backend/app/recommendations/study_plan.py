"""Weekly study plan generator.

Input signals actually used (all of them come from real student data or from the
pipeline upstream - nothing is invented):

  * prioritised concepts and their resources  -> from `recommendations.engine`
  * predicted risk tier                       -> from the classification model
  * `freetime` (UCI scale 1-5) and `studytime` (1-4) -> weekly budget in minutes
  * mastery gaps                              -> session length and repetition

Budget model
------------
    weekly_minutes = STUDYTIME_MINUTES[studytime] + FREETIME_BONUS * (freetime - 3)
    capped to [120, 900], and increased by 15% for High risk students.

Allocation
----------
Minutes are split across the top concepts proportionally to their priority
score, then chopped into sessions of at most MAX_SESSION minutes and laid out
across the week. Root-cause concepts are scheduled EARLY in the week (Monday
first), because the rest of the plan builds on them.
"""

from __future__ import annotations

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# UCI `studytime`: 1 = <2h, 2 = 2-5h, 3 = 5-10h, 4 = >10h weekly. Midpoints in minutes.
STUDYTIME_MINUTES = {1: 90, 2: 210, 3: 450, 4: 660}
FREETIME_BONUS = 30
MAX_SESSION = 60
MIN_SESSION = 30
RISK_MULTIPLIER = {"High": 1.15, "Medium": 1.0, "Low": 0.9}


def weekly_budget(studytime: int, freetime: int, risk_tier: str) -> int:
    base = STUDYTIME_MINUTES.get(int(studytime), 210)
    base += FREETIME_BONUS * (int(freetime) - 3)
    base *= RISK_MULTIPLIER.get(risk_tier, 1.0)
    return int(max(120, min(900, base)))


def _sessions_for(minutes: int) -> list[int]:
    if minutes < MIN_SESSION:
        return [MIN_SESSION]
    out, left = [], minutes
    while left >= MIN_SESSION:
        block = min(MAX_SESSION, left)
        out.append(int(block))
        left -= block
    if left and out:
        out[-1] = int(min(MAX_SESSION, out[-1] + left))
    return out


def generate(recommendations: dict, studytime: int, freetime: int,
             risk_tier: str) -> dict:
    items = recommendations.get("items", [])
    budget = weekly_budget(studytime, freetime, risk_tier)
    if not items:
        return {
            "weekly_minutes": budget,
            "days": [{"day": d, "sessions": []} for d in DAYS],
            "note": "No concept is below the mastery target; no remedial plan generated.",
        }

    total_priority = sum(i["priority_score"] for i in items) or 1.0
    queue: list[dict] = []
    for item in items:
        share = item["priority_score"] / total_priority
        minutes = int(budget * share)
        resources = item.get("resources", [])
        for n, block in enumerate(_sessions_for(minutes)):
            resource = resources[n % len(resources)] if resources else None
            queue.append(
                {
                    "concept": item["concept"],
                    "label": item["label"],
                    "minutes": block,
                    "focus": _focus(item, n),
                    "is_root_cause": item["is_root_cause"],
                    "resource": resource,
                }
            )

    # Root-cause sessions first, then by concept priority; deal round-robin so a
    # single concept does not occupy the entire week.
    queue.sort(key=lambda s: (not s["is_root_cause"],))
    days: dict[str, list[dict]] = {d: [] for d in DAYS}
    for i, session in enumerate(queue):
        days[DAYS[i % len(DAYS)]].append(session)

    return {
        "weekly_minutes": budget,
        "scheduled_minutes": sum(s["minutes"] for s in queue),
        "budget_inputs": {
            "studytime": int(studytime),
            "freetime": int(freetime),
            "risk_tier": risk_tier,
        },
        "days": [{"day": d, "sessions": days[d]} for d in DAYS],
        "note": (
            "Root-cause concepts are scheduled first in the week because later "
            "topics depend on them."
        ),
    }


def _focus(item: dict, session_index: int) -> str:
    if session_index == 0:
        return f"{item['label']} - concept revision" if item["risk"] == "High" else f"{item['label']} - review"
    if session_index == 1:
        return f"{item['label']} - guided worked examples"
    return f"{item['label']} - practice problems"
