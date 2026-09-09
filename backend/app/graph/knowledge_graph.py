"""Prerequisite knowledge graph (NetworkX DiGraph).

Edge direction: prerequisite -> dependent. `Limits -> Differentiation` means
"you need Limits before Differentiation". The graph is a DAG, which is what makes
backward traversal (ancestors = prerequisites) well defined.

The curriculum is a *curriculum design decision*, not data extracted from the
dataset, and the structure is editable: `CONCEPTS` and `PREREQUISITES` are plain
data, so adding a concept means adding one row.

Subject awareness
-----------------
The graph engine stays generic: there is ONE DiGraph containing every concept in
every subject, and each node carries a `subject` attribute. A subject's graph is
the induced subgraph over its own concepts (`subject_graph`), so no subject gets
its own traversal code - the same propagation in `root_cause.py` runs over any
of them. Cross-subject prerequisite edges are allowed (Mathematics feeds DSP and
AI/ML), which is exactly what makes root-cause analysis able to point out of one
subject into another.
"""

from __future__ import annotations

from functools import lru_cache

import networkx as nx

# --------------------------------------------------------------------------- #
# subjects
# --------------------------------------------------------------------------- #
# subject id -> (display name, short code, description)
SUBJECTS: dict[str, tuple[str, str, str]] = {
    "mathematics": ("Mathematics", "MAT", "Calculus, algebra and mathematical methods."),
    "dsp": ("Digital Signal Processing", "DSP", "Sampling, transforms and digital filtering."),
    "vlsi": ("VLSI Design", "VLS", "MOSFET device physics and digital IC design."),
    "networks": ("Computer Networks", "CN", "Switching, protocols, routing and performance."),
    "dbms": ("Database Management Systems", "DB", "Relational design, normalization and queries."),
    "aiml": ("Artificial Intelligence / Machine Learning", "AML", "Learning algorithms and evaluation."),
}

# concept id -> subject id. Concepts that predate the multi-subject upgrade keep
# their ids unchanged, so stored mastery, questions and resources still resolve.
CONCEPT_SUBJECT: dict[str, str] = {}

# concept id -> unit (a subject's chapter grouping; Part 4's Subject -> Unit ->
# Concept hierarchy). Units are labels on concepts rather than a separate table,
# because a concept belongs to exactly one unit.
CONCEPT_UNIT: dict[str, str] = {}

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

    # --- Digital Signal Processing ---------------------------------------- #
    "sampling": ("Sampling", "DSP", "Converting a continuous signal to discrete samples."),
    "nyquist_theorem": ("Nyquist Theorem", "DSP", "The minimum sampling rate for perfect reconstruction."),
    "aliasing": ("Aliasing", "DSP", "Spectral folding caused by under-sampling."),
    "fourier_transform": ("Fourier Transform", "DSP", "Frequency-domain representation of signals."),
    "dft_fft": ("DFT and FFT", "DSP", "Discrete transforms and their fast computation."),
    "digital_filtering": ("Digital Filtering", "DSP", "FIR and IIR filter design and response."),

    # --- VLSI --------------------------------------------------------------- #
    "semiconductor_physics": ("Semiconductor Physics", "VLSI", "Carriers, doping and junctions."),
    "mosfet": ("MOSFET", "VLSI", "Structure and operating regions of the MOS transistor."),
    "threshold_voltage": ("Threshold Voltage", "VLSI", "Gate voltage at which the channel forms."),
    "mobility": ("Carrier Mobility", "VLSI", "How carrier drift velocity responds to a field."),
    "velocity_saturation": ("Velocity Saturation", "VLSI", "Short-channel limit on carrier velocity."),
    "channel_length_modulation": ("Channel Length Modulation", "VLSI", "Effective channel shortening in saturation."),
    "cmos_logic": ("CMOS Logic Design", "VLSI", "Static CMOS gates, sizing and power."),

    # --- Computer Networks --------------------------------------------------- #
    "network_models": ("Network Models", "Networks", "OSI and TCP/IP layering."),
    "circuit_switching": ("Circuit Switching", "Networks", "Dedicated end-to-end paths."),
    "packet_switching": ("Packet Switching", "Networks", "Store-and-forward datagram delivery."),
    "network_delay": ("Network Delay", "Networks", "Transmission, propagation, queueing and processing delay."),
    "tcp": ("TCP", "Networks", "Reliable transport, flow and congestion control."),
    "routing": ("Routing", "Networks", "Path selection and routing algorithms."),

    # --- DBMS ---------------------------------------------------------------- #
    "relational_model": ("Relational Model", "DBMS", "Relations, keys and integrity constraints."),
    "functional_dependencies": ("Functional Dependencies", "DBMS", "Attribute determination and closures."),
    "first_normal_form": ("First Normal Form", "DBMS", "Atomic attribute values."),
    "second_normal_form": ("Second Normal Form", "DBMS", "Removing partial dependencies."),
    "third_normal_form": ("Third Normal Form", "DBMS", "Removing transitive dependencies."),
    "bcnf": ("BCNF", "DBMS", "Every determinant is a candidate key."),
    "sql_queries": ("SQL Queries", "DBMS", "Selection, joins and aggregation."),
    "transactions": ("Transactions", "DBMS", "ACID properties, concurrency and recovery."),

    # --- AI / ML -------------------------------------------------------------- #
    "regression": ("Regression", "AI/ML", "Predicting continuous targets."),
    "classification": ("Classification", "AI/ML", "Predicting discrete labels."),
    "feature_engineering": ("Feature Engineering", "AI/ML", "Constructing and encoding model inputs."),
    "model_evaluation": ("Model Evaluation", "AI/ML", "Splits, metrics and validation."),
    "overfitting": ("Overfitting and Regularisation", "AI/ML", "Bias-variance trade-off and controls."),
    "explainable_ai": ("Explainable AI", "AI/ML", "Attribution methods such as SHAP."),
}

# Which subject each concept belongs to. Everything that existed before the
# multi-subject upgrade stays in Mathematics, so no stored row changes meaning.
CONCEPT_SUBJECT.update({
    **{c: "mathematics" for c in (
        "algebra", "trigonometry", "functions", "limits", "differentiation",
        "integration", "differential_equations", "linear_algebra", "probability",
        "numerical_methods", "laplace_transforms", "signals_systems",
        "control_systems", "robotics",
    )},
    **{c: "dsp" for c in (
        "sampling", "nyquist_theorem", "aliasing", "fourier_transform",
        "dft_fft", "digital_filtering",
    )},
    **{c: "vlsi" for c in (
        "semiconductor_physics", "mosfet", "threshold_voltage", "mobility",
        "velocity_saturation", "channel_length_modulation", "cmos_logic",
    )},
    **{c: "networks" for c in (
        "network_models", "circuit_switching", "packet_switching",
        "network_delay", "tcp", "routing",
    )},
    **{c: "dbms" for c in (
        "relational_model", "functional_dependencies", "first_normal_form",
        "second_normal_form", "third_normal_form", "bcnf", "sql_queries",
        "transactions",
    )},
    **{c: "aiml" for c in (
        "regression", "classification", "feature_engineering",
        "model_evaluation", "overfitting", "explainable_ai",
    )},
})

CONCEPT_UNIT.update({
    "algebra": "Foundations", "trigonometry": "Foundations", "functions": "Foundations",
    "linear_algebra": "Linear Algebra", "probability": "Probability",
    "numerical_methods": "Numerical Methods",
    "limits": "Calculus", "differentiation": "Calculus", "integration": "Calculus",
    "differential_equations": "Calculus",
    "laplace_transforms": "Transforms", "signals_systems": "Systems",
    "control_systems": "Systems", "robotics": "Applications",
    "sampling": "Sampling Theory", "nyquist_theorem": "Sampling Theory",
    "aliasing": "Sampling Theory", "fourier_transform": "Transforms",
    "dft_fft": "Transforms", "digital_filtering": "Filter Design",
    "semiconductor_physics": "Device Physics", "mosfet": "Device Physics",
    "threshold_voltage": "MOSFET Parameters", "mobility": "MOSFET Parameters",
    "velocity_saturation": "Short Channel Effects",
    "channel_length_modulation": "Short Channel Effects", "cmos_logic": "Digital Design",
    "network_models": "Fundamentals", "circuit_switching": "Switching",
    "packet_switching": "Switching", "network_delay": "Performance",
    "tcp": "Transport Layer", "routing": "Network Layer",
    "relational_model": "Relational Model", "functional_dependencies": "Normalization",
    "first_normal_form": "Normalization", "second_normal_form": "Normalization",
    "third_normal_form": "Normalization", "bcnf": "Normalization",
    "sql_queries": "Querying", "transactions": "Transactions",
    "regression": "Supervised Learning", "classification": "Supervised Learning",
    "feature_engineering": "Data Preparation", "model_evaluation": "Evaluation",
    "overfitting": "Evaluation", "explainable_ai": "Interpretability",
})

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

    # --- DSP: builds on the Mathematics chain ------------------------------- #
    ("functions", "sampling", 0.6),
    ("sampling", "nyquist_theorem", 1.0),
    ("nyquist_theorem", "aliasing", 1.0),
    ("integration", "fourier_transform", 0.8),
    ("signals_systems", "fourier_transform", 0.7),
    ("fourier_transform", "dft_fft", 1.0),
    ("sampling", "dft_fft", 0.7),
    ("dft_fft", "digital_filtering", 0.8),
    ("laplace_transforms", "digital_filtering", 0.6),

    # --- VLSI ---------------------------------------------------------------- #
    ("semiconductor_physics", "mosfet", 1.0),
    ("mosfet", "threshold_voltage", 1.0),
    ("semiconductor_physics", "mobility", 0.8),
    ("mobility", "velocity_saturation", 0.9),
    ("mosfet", "velocity_saturation", 0.7),
    ("mosfet", "channel_length_modulation", 0.9),
    ("threshold_voltage", "cmos_logic", 0.8),
    ("channel_length_modulation", "cmos_logic", 0.5),

    # --- Computer Networks ---------------------------------------------------- #
    ("network_models", "circuit_switching", 0.7),
    ("network_models", "packet_switching", 0.9),
    ("packet_switching", "network_delay", 0.9),
    ("network_delay", "tcp", 0.7),
    ("packet_switching", "routing", 0.8),
    ("packet_switching", "tcp", 0.9),
    ("probability", "network_delay", 0.4),

    # --- DBMS ------------------------------------------------------------------ #
    ("relational_model", "functional_dependencies", 0.9),
    ("relational_model", "sql_queries", 0.8),
    ("functional_dependencies", "first_normal_form", 0.6),
    ("first_normal_form", "second_normal_form", 1.0),
    ("second_normal_form", "third_normal_form", 1.0),
    ("functional_dependencies", "third_normal_form", 0.9),
    ("third_normal_form", "bcnf", 1.0),
    ("relational_model", "transactions", 0.6),

    # --- AI / ML ---------------------------------------------------------------- #
    ("linear_algebra", "regression", 0.7),
    ("probability", "regression", 0.6),
    ("regression", "classification", 0.7),
    ("probability", "classification", 0.6),
    ("feature_engineering", "regression", 0.5),
    ("feature_engineering", "classification", 0.5),
    ("classification", "model_evaluation", 0.8),
    ("regression", "model_evaluation", 0.8),
    ("model_evaluation", "overfitting", 0.9),
    ("model_evaluation", "explainable_ai", 0.6),
    ("classification", "explainable_ai", 0.7),
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


# --------------------------------------------------------------------------- #
# subject-aware helpers (multi-subject upgrade)
# --------------------------------------------------------------------------- #
def subject_ids() -> list[str]:
    return list(SUBJECTS)


def subject_name(subject_id: str) -> str:
    if subject_id not in SUBJECTS:
        raise GraphError(f"Unknown subject '{subject_id}'")
    return SUBJECTS[subject_id][0]


def subject_of(concept_id: str) -> str:
    """Which subject a concept belongs to. Unmapped concepts fall back to
    Mathematics, which is where every pre-upgrade concept lives."""
    return CONCEPT_SUBJECT.get(concept_id, "mathematics")


def unit_of(concept_id: str) -> str:
    return CONCEPT_UNIT.get(concept_id, "General")


def concepts_for_subject(subject_id: str) -> list[str]:
    if subject_id not in SUBJECTS:
        raise GraphError(f"Unknown subject '{subject_id}'")
    return [c for c in CONCEPTS if subject_of(c) == subject_id]


@lru_cache(maxsize=len(SUBJECTS) + 1)
def subject_graph(subject_id: str) -> nx.DiGraph:
    """Induced subgraph over one subject's concepts.

    Same engine, same traversal code - only the node set differs. Prerequisites
    that live in another subject are not in this view; use `external_prerequisites`
    to surface them.
    """
    return get_graph().subgraph(concepts_for_subject(subject_id)).copy()


def external_prerequisites(subject_id: str) -> list[dict]:
    """Prerequisite edges that cross INTO this subject from another one.

    These are what let a root cause in Mathematics explain a weakness in DSP.
    """
    g = get_graph()
    own = set(concepts_for_subject(subject_id))
    out = []
    for target in own:
        for src in g.predecessors(target):
            if src not in own:
                out.append({
                    "source": src,
                    "source_label": CONCEPTS[src][0],
                    "source_subject": subject_of(src),
                    "target": target,
                    "target_label": CONCEPTS[target][0],
                    "strength": g.edges[src, target]["strength"],
                })
    return out


def subject_levels(subject_id: str) -> dict[str, int]:
    """Longest-path depth within one subject's subgraph, for layered layout."""
    g = subject_graph(subject_id)
    depth: dict[str, int] = {}
    for node in nx.topological_sort(g):
        preds = list(g.predecessors(node))
        depth[node] = 0 if not preds else 1 + max(depth[p] for p in preds)
    return depth


def subject_graph_payload(subject_id: str) -> dict:
    """Serialisable single-subject graph, same shape as `graph_payload`."""
    g = subject_graph(subject_id)
    levels = subject_levels(subject_id)
    return {
        "subject": subject_id,
        "subject_name": subject_name(subject_id),
        "nodes": [
            {
                "id": n,
                "label": g.nodes[n]["label"],
                "area": g.nodes[n]["area"],
                "unit": unit_of(n),
                "subject": subject_id,
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
        "external_prerequisites": external_prerequisites(subject_id),
        "stats": {
            "n_nodes": g.number_of_nodes(),
            "n_edges": g.number_of_edges(),
            "max_level": max(levels.values()) if levels else 0,
        },
    }


def subject_catalogue() -> list[dict]:
    """Subject -> unit -> concept tree, the structure Part 4 asks for."""
    out = []
    for sid, (name, code, description) in SUBJECTS.items():
        units: dict[str, list[dict]] = {}
        for cid in concepts_for_subject(sid):
            units.setdefault(unit_of(cid), []).append({
                "id": cid,
                "label": CONCEPTS[cid][0],
                "description": CONCEPTS[cid][2],
            })
        out.append({
            "id": sid,
            "name": name,
            "code": code,
            "description": description,
            "n_concepts": len(concepts_for_subject(sid)),
            "units": [{"unit": u, "concepts": c} for u, c in units.items()],
        })
    return out
