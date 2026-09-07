"""Recommendation prioritisation and weekly study plan."""
from __future__ import annotations

from app.graph.root_cause import analyse
from app.recommendations.engine import CATALOGUE, recommend, score_concepts
from app.recommendations.study_plan import DAYS, generate, weekly_budget

MASTERY = {"functions": 88, "limits": 45, "differentiation": 30,
           "integration": 52, "differential_equations": 35, "control_systems": 40}


def _recs(risk="High"):
    return recommend(MASTERY, analyse(MASTERY), risk)


def test_only_below_target_concepts_are_recommended():
    ranked = score_concepts(MASTERY, analyse(MASTERY), "High")
    assert "functions" not in [r["concept"] for r in ranked]


def test_root_cause_outranks_equally_weak_downstream_concept():
    items = _recs()["items"]
    order = [i["concept"] for i in items]
    assert order.index("differentiation") < order.index("differential_equations")
    assert items[0]["priority"] == 1


def test_every_recommended_concept_has_resources():
    for item in _recs()["items"]:
        assert item["resources"], f"no resources for {item['concept']}"
        assert all(r["url"].startswith("http") for r in item["resources"])
        assert item["estimated_minutes"] > 0


def test_catalogue_covers_every_concept():
    from app.graph.knowledge_graph import CONCEPTS
    assert set(CATALOGUE) == set(CONCEPTS)


def test_no_recommendations_when_all_concepts_strong():
    strong = {c: 85.0 for c in MASTERY}
    out = recommend(strong, analyse(strong), "Low")
    assert out["items"] == [] and out["message"]


def test_budget_scales_with_study_time_and_risk():
    assert weekly_budget(1, 3, "Low") < weekly_budget(3, 3, "Low")
    assert weekly_budget(2, 3, "High") > weekly_budget(2, 3, "Low")
    assert 120 <= weekly_budget(4, 5, "High") <= 900


def test_plan_covers_seven_days_and_respects_budget():
    plan = generate(_recs(), studytime=3, freetime=3, risk_tier="High")
    assert [d["day"] for d in plan["days"]] == DAYS
    assert plan["scheduled_minutes"] <= plan["weekly_minutes"] * 1.2


def test_root_cause_sessions_scheduled_first():
    plan = generate(_recs(), studytime=3, freetime=3, risk_tier="High")
    monday = plan["days"][0]["sessions"]
    assert monday and monday[0]["is_root_cause"]


def test_empty_recommendations_produce_empty_plan():
    plan = generate({"items": []}, studytime=2, freetime=3, risk_tier="Low")
    assert all(d["sessions"] == [] for d in plan["days"])
