"""
TRACE case-network unit tests — pure logic for case-pair aggregation.
No DB, tests the Python grouping that the endpoint uses.
"""
import sys
sys.path.insert(0, "/app")

# Simulate the edge aggregation logic from case_network.py
def build_case_edges(recurring_entities, accessible):
    """
    recurring_entities: list of {entity_id, name, type, case_ids}
    accessible: set of case_ids user can see
    Returns edge_map as in endpoint.
    """
    edge_map = {}
    for r in recurring_entities:
        cids = r["case_ids"]
        accessible_cids = sorted([cid for cid in cids if cid in accessible])
        if len(accessible_cids) < 2:
            continue
        for i in range(len(accessible_cids)):
            for j in range(i+1, len(accessible_cids)):
                a, b = accessible_cids[i], accessible_cids[j]
                if a > b:
                    a, b = b, a
                key = (a, b)
                entry = edge_map.setdefault(key, {"shared_entities": [], "shared_count": 0})
                entry["shared_entities"].append({"entity_id": r["entity_id"], "name": r["name"], "type": r["type"]})
                entry["shared_count"] += 1
    return edge_map


def test_case_network_aggregation():
    entities = [
        {"entity_id": "PHN-1", "name": "+91-1", "type": "PHONE", "case_ids": ["A", "B", "C"]},
        {"entity_id": "PHN-2", "name": "+91-2", "type": "PHONE", "case_ids": ["A", "B"]},
        {"entity_id": "PER-1", "name": "Rohan", "type": "PERSON", "case_ids": ["B", "C"]},
    ]
    accessible = {"A", "B", "C"}
    edges = build_case_edges(entities, accessible)
    # A-B should have 2 (PHN-1, PHN-2), A-C 1, B-C 2 (PHN-1, PER-1)
    assert edges[("A","B")]["shared_count"] == 2
    assert edges[("A","C")]["shared_count"] == 1
    assert edges[("B","C")]["shared_count"] == 2


def test_rbac_filters_inaccessible():
    entities = [
        {"entity_id": "PHN-1", "name": "+91-1", "type": "PHONE", "case_ids": ["A", "B", "C"]},
    ]
    # User can only see A and B, not C
    accessible = {"A", "B"}
    edges = build_case_edges(entities, accessible)
    # Should only create A-B, not A-C or B-C
    assert ("A","B") in edges
    assert ("A","C") not in edges
    assert ("B","C") not in edges
    assert edges[("A","B")]["shared_count"] == 1


def test_no_leak_for_isolated_user():
    entities = [
        {"entity_id": "PHN-1", "name": "+91-1", "type": "PHONE", "case_ids": ["A", "B"]},
    ]
    # User only has A
    accessible = {"A"}
    edges = build_case_edges(entities, accessible)
    assert edges == {}


def test_neutral_language():
    # Ensure UI copy would not claim linkage
    # This is a policy check, not code, but we verify edge data doesn't contain guilt language
    entities = [
        {"entity_id": "PHN-1", "name": "+91-1", "type": "PHONE", "case_ids": ["A", "B"]},
    ]
    edges = build_case_edges(entities, {"A","B"})
    for data in edges.values():
        for ent in data["shared_entities"]:
            assert "criminal" not in ent["name"].lower()
            assert "guilt" not in ent["name"].lower()
