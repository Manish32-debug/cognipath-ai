"""Knowledge graph structure and root-cause propagation."""
from __future__ import annotations

import networkx as nx
import pytest

from app.graph.knowledge_graph import (
    CONCEPTS,
    get_graph,
    graph_payload,
    prerequisites_of,
    topological_levels,
)
from app.graph.root_cause import analyse, gap, risk_label


def test_graph_is_a_dag_with_all_concepts():
    g = get_graph()
    assert nx.is_directed_acyclic_graph(g)
    assert set(g.nodes) == set(CONCEPTS)


def test_required_prerequisite_chain_exists():
    g = get_graph()
    chain = ["functions", "limits", "differentiation", "integration",
             "differential_equations"]
    for a, b in zip(chain, chain[1:]):
        assert nx.has_path(g, a, b)
    assert nx.has_path(g, "functions", "robotics")


def test_levels_increase_along_edges():
    g, levels = get_graph(), topological_levels()
    for u, v in g.edges:
        assert levels[v] > levels[u]


def test_graph_payload_serialisable():
    payload = graph_payload()
    assert payload["stats"]["n_nodes"] == len(CONCEPTS)
    assert all({"id", "label", "level"} <= set(n) for n in payload["nodes"])


def test_gap_and_risk_labels():
    assert gap(70) == 0 and gap(100) == 0
    assert gap(35) == pytest.approx(0.5)
    assert risk_label(30) == "High" and risk_label(50) == "Medium" and risk_label(80) == "Low"


def test_root_cause_prefers_upstream_weakness():
    """The spec example: DE is weak but Differentiation/Limits are weaker upstream."""
    mastery = {"functions": 90, "limits": 45, "differentiation": 30,
               "integration": 55, "differential_equations": 35}
    result = analyse(mastery)
    ranked = [r["concept"] for r in result["root_causes"]]
    assert ranked.index("differentiation") < ranked.index("differential_equations")
    assert ranked.index("limits") < ranked.index("differential_equations")


def test_strong_concept_is_never_a_root_cause():
    mastery = {"functions": 95, "limits": 92, "differentiation": 35}
    result = analyse(mastery)
    assert "functions" not in [r["concept"] for r in result["root_causes"]]


def test_isolated_weakness_is_its_own_root_cause():
    mastery = {"functions": 88, "limits": 90, "differentiation": 85, "probability": 30}
    result = analyse(mastery)
    assert result["root_causes"][0]["concept"] == "probability"
    assert result["root_causes"][0]["blocking_prerequisites"] == []


def test_reasoning_path_is_a_real_graph_path():
    g = get_graph()
    mastery = {"limits": 40, "differentiation": 35, "control_systems": 30}
    result = analyse(mastery)
    for root in result["root_causes"]:
        for affected in root["affected_concepts"]:
            path = affected["path"]
            assert all(g.has_edge(a, b) for a, b in zip(path, path[1:]))


def test_empty_mastery_returns_empty_analysis():
    result = analyse({})
    assert result["root_causes"] == [] and result["weak_concepts"] == []
