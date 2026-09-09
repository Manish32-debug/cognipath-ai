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

    # ---- Digital Signal Processing ------------------------------------- #
    "sampling": [
        {"type": "video", "title": "MIT OCW - Sampling", "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/", "minutes": 40},
        {"type": "practice", "title": "Sampling and reconstruction exercises", "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/", "minutes": 40},
    ],
    "nyquist_theorem": [
        {"type": "article", "title": "Nyquist-Shannon sampling theorem notes", "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/", "minutes": 25},
        {"type": "practice", "title": "Minimum sampling rate problems", "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/", "minutes": 30},
    ],
    "aliasing": [
        {"type": "video", "title": "Aliasing explained", "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/", "minutes": 25},
        {"type": "practice", "title": "Identify aliased frequencies", "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/", "minutes": 30},
    ],
    "fourier_transform": [
        {"type": "video", "title": "3Blue1Brown - But what is the Fourier Transform", "url": "https://www.3blue1brown.com/topics/analysis", "minutes": 25},
        {"type": "practice", "title": "Fourier transform problem set", "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/", "minutes": 50},
    ],
    "dft_fft": [
        {"type": "article", "title": "DFT and the FFT algorithm", "url": "https://ocw.mit.edu/courses/6-341-discrete-time-signal-processing-fall-2005/", "minutes": 35},
        {"type": "practice", "title": "Compute an 8-point DFT by hand", "url": "https://ocw.mit.edu/courses/6-341-discrete-time-signal-processing-fall-2005/", "minutes": 45},
    ],
    "digital_filtering": [
        {"type": "video", "title": "FIR and IIR filter design", "url": "https://ocw.mit.edu/courses/6-341-discrete-time-signal-processing-fall-2005/", "minutes": 45},
        {"type": "practice", "title": "Filter design exercises", "url": "https://ocw.mit.edu/courses/6-341-discrete-time-signal-processing-fall-2005/", "minutes": 50},
    ],

    # ---- VLSI ------------------------------------------------------------ #
    "semiconductor_physics": [
        {"type": "video", "title": "Semiconductor fundamentals", "url": "https://nptel.ac.in/courses/117106091", "minutes": 45},
        {"type": "article", "title": "Carriers, doping and junctions", "url": "https://nptel.ac.in/courses/117106091", "minutes": 30},
    ],
    "mosfet": [
        {"type": "video", "title": "MOSFET operating regions", "url": "https://nptel.ac.in/courses/117101058", "minutes": 40},
        {"type": "practice", "title": "MOSFET I-V characteristic problems", "url": "https://nptel.ac.in/courses/117101058", "minutes": 45},
    ],
    "threshold_voltage": [
        {"type": "article", "title": "Threshold voltage and body effect", "url": "https://nptel.ac.in/courses/117101058", "minutes": 30},
        {"type": "practice", "title": "Threshold voltage calculations", "url": "https://nptel.ac.in/courses/117101058", "minutes": 35},
    ],
    "mobility": [
        {"type": "article", "title": "Carrier mobility and scattering", "url": "https://nptel.ac.in/courses/117106091", "minutes": 25},
        {"type": "practice", "title": "Mobility and drift velocity problems", "url": "https://nptel.ac.in/courses/117106091", "minutes": 30},
    ],
    "velocity_saturation": [
        {"type": "article", "title": "Short-channel velocity saturation", "url": "https://nptel.ac.in/courses/117101058", "minutes": 30},
        {"type": "practice", "title": "Short-channel current model exercises", "url": "https://nptel.ac.in/courses/117101058", "minutes": 40},
    ],
    "channel_length_modulation": [
        {"type": "article", "title": "Channel length modulation and output resistance", "url": "https://nptel.ac.in/courses/117101058", "minutes": 25},
        {"type": "practice", "title": "Early voltage problems", "url": "https://nptel.ac.in/courses/117101058", "minutes": 30},
    ],
    "cmos_logic": [
        {"type": "video", "title": "Static CMOS gate design", "url": "https://nptel.ac.in/courses/117101058", "minutes": 45},
        {"type": "practice", "title": "Pull-up/pull-down network exercises", "url": "https://nptel.ac.in/courses/117101058", "minutes": 45},
    ],

    # ---- Computer Networks ------------------------------------------------ #
    "network_models": [
        {"type": "video", "title": "OSI and TCP/IP layering", "url": "https://gaia.cs.umass.edu/kurose_ross/videos.php", "minutes": 35},
        {"type": "article", "title": "Layered architecture overview", "url": "https://gaia.cs.umass.edu/kurose_ross/", "minutes": 25},
    ],
    "circuit_switching": [
        {"type": "article", "title": "Circuit vs packet switching", "url": "https://gaia.cs.umass.edu/kurose_ross/", "minutes": 20},
        {"type": "practice", "title": "Switching comparison problems", "url": "https://gaia.cs.umass.edu/kurose_ross/", "minutes": 30},
    ],
    "packet_switching": [
        {"type": "video", "title": "Packet switching and store-and-forward", "url": "https://gaia.cs.umass.edu/kurose_ross/videos.php", "minutes": 30},
        {"type": "practice", "title": "Store-and-forward delay exercises", "url": "https://gaia.cs.umass.edu/kurose_ross/", "minutes": 35},
    ],
    "network_delay": [
        {"type": "article", "title": "The four sources of packet delay", "url": "https://gaia.cs.umass.edu/kurose_ross/", "minutes": 25},
        {"type": "practice", "title": "End-to-end delay calculations", "url": "https://gaia.cs.umass.edu/kurose_ross/", "minutes": 40},
    ],
    "tcp": [
        {"type": "video", "title": "TCP reliability and congestion control", "url": "https://gaia.cs.umass.edu/kurose_ross/videos.php", "minutes": 45},
        {"type": "practice", "title": "TCP window and throughput problems", "url": "https://gaia.cs.umass.edu/kurose_ross/", "minutes": 45},
    ],
    "routing": [
        {"type": "video", "title": "Link-state and distance-vector routing", "url": "https://gaia.cs.umass.edu/kurose_ross/videos.php", "minutes": 40},
        {"type": "practice", "title": "Dijkstra and Bellman-Ford exercises", "url": "https://gaia.cs.umass.edu/kurose_ross/", "minutes": 45},
    ],

    # ---- DBMS -------------------------------------------------------------- #
    "relational_model": [
        {"type": "video", "title": "The relational model", "url": "https://www.db-book.com/slides-dir/index.html", "minutes": 35},
        {"type": "article", "title": "Keys and integrity constraints", "url": "https://www.db-book.com/", "minutes": 25},
    ],
    "functional_dependencies": [
        {"type": "article", "title": "Functional dependencies and closures", "url": "https://www.db-book.com/", "minutes": 30},
        {"type": "practice", "title": "Attribute closure exercises", "url": "https://www.db-book.com/slides-dir/index.html", "minutes": 40},
    ],
    "first_normal_form": [
        {"type": "article", "title": "1NF and atomic values", "url": "https://www.db-book.com/", "minutes": 15},
        {"type": "practice", "title": "Normalise to 1NF", "url": "https://www.db-book.com/slides-dir/index.html", "minutes": 25},
    ],
    "second_normal_form": [
        {"type": "article", "title": "2NF and partial dependencies", "url": "https://www.db-book.com/", "minutes": 20},
        {"type": "practice", "title": "Normalise to 2NF", "url": "https://www.db-book.com/slides-dir/index.html", "minutes": 30},
    ],
    "third_normal_form": [
        {"type": "video", "title": "3NF and transitive dependencies", "url": "https://www.db-book.com/slides-dir/index.html", "minutes": 30},
        {"type": "practice", "title": "Decompose into 3NF", "url": "https://www.db-book.com/", "minutes": 40},
    ],
    "bcnf": [
        {"type": "article", "title": "BCNF and lossless decomposition", "url": "https://www.db-book.com/", "minutes": 30},
        {"type": "practice", "title": "BCNF decomposition exercises", "url": "https://www.db-book.com/slides-dir/index.html", "minutes": 45},
    ],
    "sql_queries": [
        {"type": "practice", "title": "SQL joins and aggregation exercises", "url": "https://www.db-book.com/slides-dir/index.html", "minutes": 45},
        {"type": "video", "title": "SQL query fundamentals", "url": "https://www.db-book.com/", "minutes": 40},
    ],
    "transactions": [
        {"type": "article", "title": "ACID, isolation levels and recovery", "url": "https://www.db-book.com/", "minutes": 35},
        {"type": "practice", "title": "Serialisability exercises", "url": "https://www.db-book.com/slides-dir/index.html", "minutes": 40},
    ],

    # ---- AI / ML ----------------------------------------------------------- #
    "regression": [
        {"type": "video", "title": "Linear regression from scratch", "url": "https://www.statlearning.com/", "minutes": 40},
        {"type": "practice", "title": "Fit and evaluate a regression model", "url": "https://scikit-learn.org/stable/supervised_learning.html", "minutes": 45},
    ],
    "classification": [
        {"type": "video", "title": "Classification methods overview", "url": "https://www.statlearning.com/", "minutes": 45},
        {"type": "practice", "title": "Train a classifier and read its metrics", "url": "https://scikit-learn.org/stable/supervised_learning.html", "minutes": 45},
    ],
    "feature_engineering": [
        {"type": "article", "title": "Preprocessing and encoding in scikit-learn", "url": "https://scikit-learn.org/stable/modules/preprocessing.html", "minutes": 30},
        {"type": "practice", "title": "Build a preprocessing pipeline", "url": "https://scikit-learn.org/stable/modules/compose.html", "minutes": 45},
    ],
    "model_evaluation": [
        {"type": "article", "title": "Cross-validation and metrics", "url": "https://scikit-learn.org/stable/modules/cross_validation.html", "minutes": 35},
        {"type": "practice", "title": "Compare models with cross-validation", "url": "https://scikit-learn.org/stable/modules/model_evaluation.html", "minutes": 45},
    ],
    "overfitting": [
        {"type": "video", "title": "Bias-variance trade-off", "url": "https://www.statlearning.com/", "minutes": 30},
        {"type": "practice", "title": "Regularisation experiments", "url": "https://scikit-learn.org/stable/modules/linear_model.html", "minutes": 40},
    ],
    "explainable_ai": [
        {"type": "article", "title": "SHAP documentation and worked examples", "url": "https://shap.readthedocs.io/en/latest/", "minutes": 40},
        {"type": "practice", "title": "Explain a model with SHAP", "url": "https://shap.readthedocs.io/en/latest/example_notebooks/overviews/An%20introduction%20to%20explainable%20AI%20with%20Shapley%20values.html", "minutes": 45},
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
