"""Root-cause reasoning by backward risk propagation over the prerequisite DAG.

Problem
-------
A student is weak in Differential Equations. Recommending more Differential
Equations content is treating the symptom. If Differentiation is also weak, the
DE weakness is *probably* downstream of it.

Algorithm (explainable in one slide)
------------------------------------
1. gap(c)          = max(0, MASTERY_TARGET - mastery(c)) / MASTERY_TARGET  in [0,1]
2. downstream(a)   = sum over weak descendants d of
                        gap(d) * path_strength(a->d) * DECAY^(dist(a,d)-1)
   i.e. how much unexplained weakness sits below `a` in the curriculum.
3. clearance(a)    = 1 - max gap over the *ancestors* of `a`, floored at MIN_CLEARANCE.
   If `a`'s own prerequisites are weak, `a` is not the root of the chain - the
   blame belongs further upstream. This is what stops the algorithm from
   pointing at a mid-chain concept.
4. root_score(a)   = gap(a) * (1 + BETA * downstream(a)) * clearance(a)

Concepts are ranked by root_score. A concept with mastery above target scores 0,
because gap(a) = 0 - a strong prerequisite can never be blamed.

Wording discipline: this is diagnostic inference over a curriculum model, not
causal proof. The API returns "likely root cause" / "probable prerequisite gap".
"""

from __future__ import annotations

import networkx as nx

from app.graph.knowledge_graph import get_graph, label

MASTERY_TARGET = 70.0   # mastery (%) considered "adequate"
WEAK_THRESHOLD = 60.0   # below this a concept is flagged weak
CRITICAL_THRESHOLD = 40.0
DECAY = 0.6             # per-hop attenuation of downstream blame
BETA = 1.2              # weight of downstream evidence vs. the concept's own gap
MIN_CLEARANCE = 0.15


def gap(mastery: float) -> float:
    return max(0.0, (MASTERY_TARGET - float(mastery))) / MASTERY_TARGET


def risk_label(mastery: float) -> str:
    if mastery < CRITICAL_THRESHOLD:
        return "High"
    if mastery < WEAK_THRESHOLD:
        return "Medium"
    return "Low"


def _path_strength(g: nx.DiGraph, path: list[str]) -> float:
    s = 1.0
    for u, v in zip(path, path[1:]):
        s *= g.edges[u, v]["strength"]
    return s


def analyse(mastery: dict[str, float]) -> dict:
    """Run the propagation. `mastery` maps concept_id -> 0..100."""
    g = get_graph()
    known = {c: float(m) for c, m in mastery.items() if c in g.nodes}
    if not known:
        return {
            "weak_concepts": [],
            "root_causes": [],
            "parameters": _params(),
            "note": "No concept mastery data available for this student.",
        }

    gaps = {c: gap(m) for c, m in known.items()}

    downstream: dict[str, float] = {}
    evidence: dict[str, list[dict]] = {c: [] for c in known}
    for a in known:
        total = 0.0
        for d in nx.descendants(g, a):
            if gaps.get(d, 0.0) <= 0:
                continue
            path = nx.shortest_path(g, a, d)
            dist = len(path) - 1
            contribution = gaps[d] * _path_strength(g, path) * (DECAY ** (dist - 1))
            total += contribution
            evidence[a].append(
                {
                    "concept": d,
                    "label": label(d),
                    "mastery": known[d],
                    "distance": dist,
                    "contribution": round(contribution, 4),
                    "path": path,
                    "path_labels": [label(p) for p in path],
                }
            )
        downstream[a] = total

    clearance: dict[str, float] = {}
    blocking: dict[str, list[str]] = {}
    for a in known:
        anc = [p for p in nx.ancestors(g, a) if p in gaps]
        worst = max((gaps[p] for p in anc), default=0.0)
        clearance[a] = max(MIN_CLEARANCE, 1.0 - worst)
        blocking[a] = sorted(
            [p for p in anc if gaps[p] > 0], key=lambda p: -gaps[p]
        )

    scores = {
        a: gaps[a] * (1.0 + BETA * downstream[a]) * clearance[a] for a in known
    }

    weak = sorted(
        [
            {
                "concept": c,
                "label": label(c),
                "mastery": known[c],
                "gap": round(gaps[c], 4),
                "risk": risk_label(known[c]),
            }
            for c in known
            if known[c] < WEAK_THRESHOLD
        ],
        key=lambda d: d["mastery"],
    )

    roots = []
    for c, score in sorted(scores.items(), key=lambda kv: -kv[1]):
        if score <= 0:
            continue
        ev = sorted(evidence[c], key=lambda e: -e["contribution"])[:5]
        roots.append(
            {
                "concept": c,
                "label": label(c),
                "mastery": known[c],
                "risk": risk_label(known[c]),
                "root_score": round(score, 4),
                "own_gap": round(gaps[c], 4),
                "downstream_pressure": round(downstream[c], 4),
                "upstream_clearance": round(clearance[c], 4),
                "blocking_prerequisites": [
                    {"concept": p, "label": label(p), "mastery": known[p]} for p in blocking[c]
                ],
                "affected_concepts": ev,
                "reasoning": _reasoning(c, known[c], gaps[c], downstream[c], clearance[c], ev, blocking[c], known),
            }
        )

    return {
        "weak_concepts": weak,
        "root_causes": roots[:5],
        "parameters": _params(),
        "disclaimer": (
            "Root causes are diagnostic inferences from the curriculum "
            "prerequisite model and current mastery scores. They indicate likely "
            "upstream contributors, not proven causes."
        ),
    }


def _reasoning(cid, mastery, g_, down, clear, ev, blocking, known) -> str:
    parts = [f"{label(cid)} mastery is {mastery:.0f}% (target {MASTERY_TARGET:.0f}%)."]
    if ev:
        names = ", ".join(f"{e['label']} ({e['mastery']:.0f}%)" for e in ev[:3])
        parts.append(
            f"Weakness is also visible in {len(ev)} dependent concept(s) that require it: {names}."
        )
    if blocking:
        names = ", ".join(f"{label(p)} ({known[p]:.0f}%)" for p in blocking[:2])
        parts.append(
            f"However {names} sit upstream and are themselves weak, so part of the gap "
            "probably originates there."
        )
    else:
        parts.append("All of its own prerequisites are adequate, so this is likely the start of the weak chain.")
    return " ".join(parts)


def _params() -> dict:
    return {
        "mastery_target": MASTERY_TARGET,
        "weak_threshold": WEAK_THRESHOLD,
        "critical_threshold": CRITICAL_THRESHOLD,
        "decay": DECAY,
        "beta": BETA,
        "min_clearance": MIN_CLEARANCE,
    }
