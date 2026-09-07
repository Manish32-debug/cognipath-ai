"""Recommendation engine.

Deliberately rule-based, and here is the honest reason: a learning-to-rank or
collaborative-filtering recommender needs interaction data (which resource a
student opened, how long they stayed, whether their next score improved). This
project has none, so a trained recommender would be a black box fitted to
nothing. The rules below are transparent, defensible in a viva, and the
`score_concept` function is the single place a learned model would later plug in.

Priority score for a concept
----------------------------
    priority = 0.45 * root_score_norm      (graph root-cause evidence)
             + 0.30 * gap                  (how far mastery is below target)
             + 0.15 * downstream_norm      (how much curriculum depends on it)
             + 0.10 * risk_boost           (model-predicted academic risk tier)

Root causes therefore outrank equally weak but downstream concepts, which is the
whole point of CogniPath: fix the prerequisite, not the symptom.
"""

from __future__ import annotations

import networkx as nx

from app.graph.knowledge_graph import get_graph, label
from app.graph.root_cause import MASTERY_TARGET, gap, risk_label

RISK_BOOST = {"High": 1.0, "Medium": 0.6, "Low": 0.2}

# Curated catalogue. Resources are real, freely available sources; the mapping
# concept -> resource is a curriculum decision, not a model output.
CATALOGUE: dict[str, list[dict]] = {
    "algebra": [
        {"type": "video", "title": "Khan Academy - Algebra Basics", "url": "https://www.khanacademy.org/math/algebra-basics", "minutes": 45},
        {"type": "practice", "title": "Algebra problem set", "url": "https://www.khanacademy.org/math/algebra", "minutes": 40},
    ],
    "trigonometry": [
        {"type": "video", "title": "Khan Academy - Trigonometry", "url": "https://www.khanacademy.org/math/trigonometry", "minutes": 40},
        {"type": "article", "title": "Paul's Notes - Trig Review", "url": "https://tutorial.math.lamar.edu/Classes/CalcI/TrigFcns.aspx", "minutes": 25},
    ],
    "functions": [
        {"type": "video", "title": "Khan Academy - Functions", "url": "https://www.khanacademy.org/math/algebra/x2f8bb11595b61c86:functions", "minutes": 50},
        {"type": "article", "title": "Paul's Notes - Functions", "url": "https://tutorial.math.lamar.edu/Classes/Alg/FunctionNotation.aspx", "minutes": 25},
    ],
    "limits": [
        {"type": "video", "title": "3Blue1Brown - Limits", "url": "https://www.3blue1brown.com/lessons/limits", "minutes": 20},
        {"type": "practice", "title": "MIT OCW 18.01 - Limits problem set", "url": "https://ocw.mit.edu/courses/18-01sc-single-variable-calculus-fall-2010/", "minutes": 60},
    ],
    "differentiation": [
        {"type": "video", "title": "3Blue1Brown - Essence of Calculus (derivatives)", "url": "https://www.3blue1brown.com/topics/calculus", "minutes": 35},
        {"type": "practice", "title": "Khan Academy - Derivative exercises", "url": "https://www.khanacademy.org/math/differential-calculus", "minutes": 50},
        {"type": "revision", "title": "Paul's Notes - Derivative formula sheet", "url": "https://tutorial.math.lamar.edu/Classes/CalcI/DerivativeIntro.aspx", "minutes": 20},
    ],
    "integration": [
        {"type": "video", "title": "MIT OCW - Integration techniques", "url": "https://ocw.mit.edu/courses/18-01sc-single-variable-calculus-fall-2010/", "minutes": 45},
        {"type": "practice", "title": "Khan Academy - Integral exercises", "url": "https://www.khanacademy.org/math/integral-calculus", "minutes": 50},
    ],
    "differential_equations": [
        {"type": "video", "title": "3Blue1Brown - Differential Equations", "url": "https://www.3blue1brown.com/topics/differential-equations", "minutes": 30},
        {"type": "practice", "title": "MIT OCW 18.03 problem sets", "url": "https://ocw.mit.edu/courses/18-03sc-differential-equations-fall-2011/", "minutes": 60},
    ],
    "linear_algebra": [
        {"type": "video", "title": "3Blue1Brown - Essence of Linear Algebra", "url": "https://www.3blue1brown.com/topics/linear-algebra", "minutes": 40},
        {"type": "practice", "title": "MIT OCW 18.06 problem sets", "url": "https://ocw.mit.edu/courses/18-06sc-linear-algebra-fall-2011/", "minutes": 60},
    ],
    "laplace_transforms": [
        {"type": "video", "title": "MIT OCW - Laplace transform", "url": "https://ocw.mit.edu/courses/18-03sc-differential-equations-fall-2011/", "minutes": 40},
        {"type": "revision", "title": "Laplace transform table", "url": "https://tutorial.math.lamar.edu/Classes/DE/Laplace_Table.aspx", "minutes": 15},
    ],
    "signals_systems": [
        {"type": "video", "title": "MIT OCW 6.007 - Signals and Systems", "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/", "minutes": 50},
        {"type": "practice", "title": "Convolution practice problems", "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/", "minutes": 45},
    ],
    "control_systems": [
        {"type": "video", "title": "Brian Douglas - Control Systems Lectures", "url": "https://engineeringmedia.com/", "minutes": 40},
        {"type": "practice", "title": "Root locus and stability exercises", "url": "https://ocw.mit.edu/courses/16-06-principles-of-automatic-control-fall-2012/", "minutes": 50},
    ],
    "robotics": [
        {"type": "video", "title": "Modern Robotics - Kinematics", "url": "https://modernrobotics.northwestern.edu/nu-gm-book-resource/", "minutes": 45},
        {"type": "practice", "title": "Forward kinematics exercises", "url": "https://modernrobotics.northwestern.edu/nu-gm-book-resource/", "minutes": 45},
    ],
    "probability": [
        {"type": "video", "title": "MIT OCW 6.041 - Probabilistic Systems", "url": "https://ocw.mit.edu/courses/res-6-012-introduction-to-probability-spring-2018/", "minutes": 45},
        {"type": "practice", "title": "Probability problem sets", "url": "https://ocw.mit.edu/courses/res-6-012-introduction-to-probability-spring-2018/", "minutes": 45},
    ],
    "numerical_methods": [
        {"type": "article", "title": "Numerical Methods - root finding notes", "url": "https://ocw.mit.edu/courses/18-330-introduction-to-numerical-analysis-spring-2012/", "minutes": 30},
        {"type": "practice", "title": "Implement bisection and Newton-Raphson", "url": "https://ocw.mit.edu/courses/18-330-introduction-to-numerical-analysis-spring-2012/", "minutes": 60},
    ],
}

ACTION_BY_SEVERITY = {
    "High": "Concept revision from first principles, then guided worked examples",
    "Medium": "Targeted practice problems and a short revision pass",
    "Low": "Light spaced-repetition review to keep it consolidated",
}


def _normalise(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    hi = max(values.values())
    if hi <= 0:
        return {k: 0.0 for k in values}
    return {k: v / hi for k, v in values.items()}


def score_concepts(mastery: dict[str, float], root_result: dict, risk_tier: str) -> list[dict]:
    """Rank concepts by intervention priority. Extension point for a learned ranker."""
    g = get_graph()
    root_scores = {r["concept"]: r["root_score"] for r in root_result.get("root_causes", [])}
    downstream = {
        c: float(sum(1 for _ in nx.descendants(g, c))) for c in mastery if c in g.nodes
    }
    root_norm = _normalise(root_scores)
    down_norm = _normalise(downstream)
    boost = RISK_BOOST.get(risk_tier, 0.5)

    ranked = []
    for concept, m in mastery.items():
        if concept not in g.nodes:
            continue
        gp = gap(m)
        if gp <= 0:
            continue
        priority = (
            0.45 * root_norm.get(concept, 0.0)
            + 0.30 * gp
            + 0.15 * down_norm.get(concept, 0.0)
            + 0.10 * boost
        )
        ranked.append(
            {
                "concept": concept,
                "label": label(concept),
                "mastery": m,
                "gap": round(gp, 4),
                "risk": risk_label(m),
                "is_root_cause": concept in root_scores,
                "root_score": round(root_scores.get(concept, 0.0), 4),
                "priority_score": round(priority, 4),
            }
        )
    ranked.sort(key=lambda r: -r["priority_score"])
    for i, r in enumerate(ranked, start=1):
        r["priority"] = i
    return ranked


def recommend(mastery: dict[str, float], root_result: dict, risk_tier: str,
              max_items: int = 5) -> dict:
    ranked = score_concepts(mastery, root_result, risk_tier)
    if not ranked:
        return {
            "risk_tier": risk_tier,
            "items": [],
            "message": (
                "No concept is currently below the "
                f"{MASTERY_TARGET:.0f}% mastery target - keep up spaced revision."
            ),
        }

    items = []
    for r in ranked[:max_items]:
        resources = CATALOGUE.get(r["concept"], [])
        reason = (
            "Likely root-cause prerequisite gap - fixing this should unblock the "
            "concepts that depend on it."
            if r["is_root_cause"]
            else f"{r['risk']} weakness at {r['mastery']:.0f}% mastery."
        )
        items.append(
            {
                **r,
                "reason": reason,
                "action": ACTION_BY_SEVERITY[r["risk"]],
                "resources": resources,
                "estimated_minutes": sum(x["minutes"] for x in resources),
            }
        )
    return {
        "risk_tier": risk_tier,
        "items": items,
        "n_concepts_below_target": len(ranked),
        "scoring": {
            "root_cause_weight": 0.45,
            "gap_weight": 0.30,
            "downstream_weight": 0.15,
            "risk_weight": 0.10,
        },
        "message": None,
    }
