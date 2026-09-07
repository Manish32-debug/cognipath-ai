"""Concept-mastery generation for the DEMO COHORT ONLY.

Honest statement of limitation
------------------------------
The UCI Student Performance dataset contains no per-concept assessment data. It
has period grades (G1, G2, G3), study time, failures and absences - nothing at
concept granularity. Per-concept mastery therefore CANNOT be derived from it,
and this module does not pretend otherwise.

What this module does: for the seeded demo cohort it produces plausible mastery
values from a documented generative process, and every value it produces is
tagged `source="simulated"` all the way to the UI. Real students entering the
system supply their own scores (`source="self_reported"`) or have them imported
from assessments (`source="assessment"`).

Generative process (deterministic given student_id)
---------------------------------------------------
1. ability = 100 * (0.6*G2 + 0.4*G1) / 20, adjusted by study time (+/- 6),
   past failures (-7 each) and attendance (up to +/- 8). This anchors the
   simulation to the student's REAL academic record.
2. Concepts are walked in topological order. A concept's expected mastery is a
   blend of the student's ability and the mastery already assigned to its
   prerequisites (weighted by edge strength), minus a small depth penalty -
   later curriculum topics are typically less consolidated.
3. One or two concepts per student are given an extra "topic shock" penalty
   (SHOCK_PENALTY). Because step 2 blends prerequisites into their dependents,
   a shock on an upstream concept propagates downwards - which is exactly the
   pattern the root-cause module is meant to detect. Without this, every
   simulated student would have the same monotone weak-at-the-end profile.
4. Gaussian noise (sigma = 7) seeded by hash(student_id) produces per-student
   variation, so different demo students have different weak chains.
"""

from __future__ import annotations

import hashlib

import networkx as nx
import numpy as np

from app.graph.knowledge_graph import get_graph, topological_levels

SIGMA = 7.0
DEPTH_PENALTY = 1.2
PREREQ_WEIGHT = 0.55
SHOCK_PENALTY = 20.0
MAX_SHOCKS = 2


def _seed(student_id: str) -> int:
    return int(hashlib.sha256(student_id.encode()).hexdigest()[:8], 16)


def ability_score(g1: float, g2: float, studytime: float, failures: float,
                  attendance_pct: float) -> float:
    base = 100.0 * (0.6 * float(g2) + 0.4 * float(g1)) / 20.0
    base += (float(studytime) - 2.0) * 6.0
    base -= float(failures) * 7.0
    base += (float(attendance_pct) - 85.0) * 0.16
    return float(np.clip(base, 5.0, 98.0))


def simulate_mastery(student_id: str, g1: float, g2: float, studytime: float,
                     failures: float, attendance_pct: float) -> dict[str, float]:
    g = get_graph()
    levels = topological_levels()
    rng = np.random.default_rng(_seed(student_id))
    ability = ability_score(g1, g2, studytime, failures, attendance_pct)

    nodes = list(nx.topological_sort(g))
    n_shocks = int(rng.integers(1, MAX_SHOCKS + 1))
    shocked = set(rng.choice(nodes, size=n_shocks, replace=False).tolist())

    mastery: dict[str, float] = {}
    for node in nodes:
        preds = list(g.predecessors(node))
        if preds:
            weights = np.array([g.edges[p, node]["strength"] for p in preds])
            prereq_mean = float(np.average([mastery[p] for p in preds], weights=weights))
            expected = (1 - PREREQ_WEIGHT) * ability + PREREQ_WEIGHT * prereq_mean
        else:
            expected = ability
        expected -= DEPTH_PENALTY * levels[node]
        if node in shocked:
            expected -= SHOCK_PENALTY
        value = float(np.clip(expected + rng.normal(0, SIGMA), 5.0, 99.0))
        mastery[node] = round(value, 1)
    return mastery


def mastery_records(student_id: str, **kwargs) -> list[dict]:
    """Mastery values tagged with their provenance."""
    scores = simulate_mastery(student_id, **kwargs)
    return [
        {"concept": c, "mastery": m, "source": "simulated"} for c, m in scores.items()
    ]
