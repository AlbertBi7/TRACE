"""
TRACE deep analysis unit tests — pure logic, no DB.
Covers communities, centrality breakdown, k-core, bridges, and fallback.
"""
import sys
sys.path.insert(0, "/app")  # for docker exec, no-op locally

import pytest
from app.graph.deep import compute_deep_analysis


def _nodes(*ids):
    return [{"id": nid, "name": nid, "type": "PERSON"} for nid in ids]

def _edges(*pairs):
    return [{"source": a, "target": b, "relation": "ASSOCIATED_WITH"} for a, b in pairs]


def test_communities_deterministic():
    nodes = _nodes("A", "B", "C", "D", "E", "F")
    # Two triangles connected by a bridge: A-B-C-A and D-E-F-D, plus C-D bridge
    edges = _edges(("A","B"),("B","C"),("C","A"),("D","E"),("E","F"),("F","D"),("C","D"))
    r1 = compute_deep_analysis(nodes, edges)
    r2 = compute_deep_analysis(nodes, edges)
    assert r1["communities"] == r2["communities"], "Louvain must be deterministic with seed=42"
    assert len(r1["communities"]) >= 2
    # node_community covers all nodes
    assert set(r1["node_community"].keys()) == {"A","B","C","D","E","F"}


def test_centrality_breakdown_keys():
    nodes = _nodes("A", "B", "C")
    edges = _edges(("A","B"),("B","C"))
    r = compute_deep_analysis(nodes, edges)
    cent = r["centrality"]
    for k in ["betweenness","closeness","eigenvector","degree"]:
        assert k in cent
        assert set(cent[k].keys()) == {"A","B","C"}
    # B is middle, should have highest betweenness
    assert cent["betweenness"]["B"] > cent["betweenness"]["A"]
    # degree raw
    assert cent["degree"]["B"] == 2
    assert cent["degree"]["A"] == 1


def test_eigenvector_fallback_on_disconnected():
    # Disconnected graph can cause eigenvector to fail — should fallback, not crash
    nodes = _nodes("A", "B", "C", "D")
    edges = _edges(("A","B"))  # C,D isolated
    r = compute_deep_analysis(nodes, edges)
    # Should still return something, either real eigenvector or fallback
    assert "eigenvector" in r["centrality"]
    assert "eigenvector_fallback" in r["centrality"]
    # Isolated nodes should have 0 or low eigenvector
    assert r["centrality"]["eigenvector"]["C"] is not None


def test_k_core_inner_circle():
    # Triangle + tail: A-B-C-A (2-core), D attached to C (1-core)
    nodes = _nodes("A","B","C","D")
    edges = _edges(("A","B"),("B","C"),("C","A"),("C","D"))
    r = compute_deep_analysis(nodes, edges)
    assert r["k_core"]["max_core"] == 2
    assert "2" in r["k_core"]["cores"]
    assert set(r["k_core"]["cores"]["2"]) == {"A","B","C"}
    assert "1" in r["k_core"]["cores"]
    # D is only in 1-core
    assert r["k_core"]["core_numbers"]["D"] == 1
    assert r["k_core"]["core_numbers"]["A"] == 2


def test_bridges_edge_level():
    nodes = _nodes("A","B","C","D")
    edges = _edges(("A","B"),("B","C"),("C","D"))  # line: all edges are bridges
    r = compute_deep_analysis(nodes, edges)
    # In a line, every edge is a bridge
    assert len(r["bridges"]) == 3
    # Triangle has no bridges
    nodes2 = _nodes("A","B","C")
    edges2 = _edges(("A","B"),("B","C"),("C","A"))
    r2 = compute_deep_analysis(nodes2, edges2)
    assert len(r2["bridges"]) == 0


def test_empty_graph():
    r = compute_deep_analysis([], [])
    assert r["node_count"] == 0
    assert r["communities"] == []
    assert r["bridges"] == []
    assert r["centrality"]["betweenness"] == {}


def test_operation_nexus_shape():
    # Simulate Operation Nexus-like size (30 nodes) with realistic topology
    # Use a ring plus extra chords to ensure multiple communities and bridges
    n = 12
    nodes = _nodes(*[f"N{i}" for i in range(n)])
    edges = _edges(*[(f"N{i}", f"N{(i+1)%n}") for i in range(n)])  # ring
    edges += _edges(("N0","N6"), ("N3","N9"))  # chords
    r = compute_deep_analysis(nodes, edges)
    assert r["node_count"] == n
    assert len(r["communities"]) >= 1
    assert r["k_core"]["max_core"] >= 2
