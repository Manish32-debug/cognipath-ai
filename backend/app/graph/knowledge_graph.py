"""Prerequisite knowledge graph (NetworkX DiGraph).

Edge direction: prerequisite -> dependent. `Limits -> Differentiation` means
"you need Limits before Differentiation". The graph is a DAG, which is what makes
backward traversal (ancestors = prerequisites) well defined.

The curriculum below is an ECE/CSE mathematics-to-systems chain. It is a
*curriculum design decision*, not data extracted from the dataset, and the
structure is editable: `CONCEPTS` and `PREREQUISITES` are plain data, so adding
a concept means adding one row.
"""

from __future__ import annotations

from functools import lru_cache

import networkx as nx

# concept id -> (display label, subject area, short description)
CONCEPTS: dict[str, tuple[str, str, str]] = {
    "algebra": ("Algebra", "Mathematics", "Symbolic manipulation, equations, inequalities."),
    "trigonometry": ("Trigonometry", "Mathematics", "Circular functions and identities."),
    "functions": ("Functions", "Mathematics", "Mappings, domain/range, composition, inverses."),
    "limits": ("Limits", "Calculus", "Limiting behaviour and continuity."),
    "differentiation": ("Differentiation", "Calculus", "Derivatives and rates of change."),
    "integration": ("Integration", "Calculus", "Antiderivatives, definite integrals, areas."),
    "differential_equations": ("Differential Equations", "Calculus", "ODEs and their solutions."),
    "linear_algebra": ("Linear Algebra", "Mathematics", "Matrices, eigenvalues, vector spaces."),
    "laplace_transforms": ("Laplace Transforms", "Transforms", "s-domain analysis of LTI systems."),
    "signals_systems": ("Signals & Systems", "Systems", "Convolution, LTI properties, frequency response."),
    "control_systems": ("Control Systems", "Systems", "Feedback, stability, transfer functions."),
    "robotics": ("Robotics", "Applications", "Kinematics, dynamics and control of manipulators."),
    "probability": ("Probability", "Mathematics", "Random variables, distributions, expectation."),
    "numerical_methods": ("Numerical Methods", "Computation", "Root finding, numerical integration, stability."),
}

# (prerequisite, dependent, strength) - strength in (0, 1] expresses how strongly
# the dependent concept relies on the prerequisite. Used to weight propagation.
PREREQUISITES: list[tuple[str, str, float]] = [
    ("algebra", "functions", 0.9),
    ("trigonometry", "functions", 0.6),
    ("functions", "limits", 1.0),
    ("limits", "differentiation", 1.0),
    ("differentiation", "integration", 0.9),
    ("integration", "differential_equations", 1.0),
    ("differentiation", "differential_equations", 0.8),
    ("differential_equations", "laplace_transforms", 0.9),
    ("integration", "laplace_transforms", 0.7),
    ("algebra", "linear_algebra", 0.8),
    ("linear_algebra", "signals_systems", 0.6),
    ("laplace_transforms", "signals_systems", 0.9),
    ("signals_systems", "control_systems", 1.0),
    ("differential_equations", "control_systems", 0.8),
    ("control_systems", "robotics", 1.0),
    ("linear_algebra", "robotics", 0.7),
    ("algebra", "probability", 0.6),
    ("integration", "probability", 0.6),
    ("differentiation", "numerical_methods", 0.6),
    ("linear_algebra", "numerical_methods", 0.7),
]


class GraphError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_graph() -> nx.DiGraph:
    """Build (once, cached) the prerequisite DAG."""
    g = nx.DiGraph()
    for cid, (label, area, desc) in CONCEPTS.items():
        g.add_node(cid, label=label, area=area, description=desc)
    for src, dst, strength in PREREQUISITES:
        if src not in CONCEPTS or dst not in CONCEPTS:
            raise GraphError(f"Edge {src}->{dst} references an unknown concept")
        g.add_edge(src, dst, strength=float(strength))
    if not nx.is_directed_acyclic_graph(g):
        raise GraphError("Prerequisite graph must be acyclic")
    return g


def concept_ids() -> list[str]:
    return list(CONCEPTS.keys())


def label(concept_id: str) -> str:
    if concept_id not in CONCEPTS:
        raise GraphError(f"Unknown concept '{concept_id}'")
    return CONCEPTS[concept_id][0]


def prerequisites_of(concept_id: str) -> list[str]:
    return list(get_graph().predecessors(concept_id))


def dependents_of(concept_id: str) -> list[str]:
    return list(get_graph().successors(concept_id))


def topological_levels() -> dict[str, int]:
    """Longest-path depth per node - used by the frontend for layered layout."""
    g = get_graph()
    depth: dict[str, int] = {}
    for node in nx.topological_sort(g):
        preds = list(g.predecessors(node))
        depth[node] = 0 if not preds else 1 + max(depth[p] for p in preds)
    return depth


def graph_payload() -> dict:
    """Serialisable graph for the API / frontend."""
    g = get_graph()
    levels = topological_levels()
    return {
        "nodes": [
            {
                "id": n,
                "label": g.nodes[n]["label"],
                "area": g.nodes[n]["area"],
                "description": g.nodes[n]["description"],
                "level": levels[n],
                "prerequisites": list(g.predecessors(n)),
                "dependents": list(g.successors(n)),
            }
            for n in g.nodes
        ],
        "edges": [
            {"source": u, "target": v, "strength": g.edges[u, v]["strength"]}
            for u, v in g.edges
        ],
        "stats": {
            "n_nodes": g.number_of_nodes(),
            "n_edges": g.number_of_edges(),
            "max_level": max(levels.values()),
        },
    }
