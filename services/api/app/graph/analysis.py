"""
TRACE — Graph Analysis (Milestone 8: Disruption Simulator)
Deterministic topology on the case subgraph (undirected projection):
  - articulation points: nodes whose removal disconnects part of the network
  - connected components before/after a simulated removal
  - fragmentation metrics (component count, largest-component share, isolated nodes)
Pure networkx on explicit node/edge lists — no GNN, no opaque scoring.
Language is deliberately neutral: this is network connectivity analysis,
not a judgement about people.
"""

import networkx as nx

from app.db.neo4j_driver import run_cypher


def _build_graph(node_ids: list[str], edges: list[tuple[str, str]]) -> nx.Graph:
    g = nx.Graph()
    g.add_nodes_from(node_ids)
    g.add_edges_from(edges)
    return g


def _component_summary(g: nx.Graph) -> dict:
    comps = sorted(
        (sorted(c) for c in nx.connected_components(g)),
        key=len, reverse=True,
    )
    sizes = [len(c) for c in comps]
    n = g.number_of_nodes()
    return {
        "components": len(comps),
        "component_sizes": sizes,
        "largest_component": sizes[0] if sizes else 0,
        "largest_share": round(sizes[0] / n, 4) if n else 0.0,
        "isolated": sum(1 for s in sizes if s == 1),
    }


async def load_case_subgraph(case_id: str) -> tuple[list[dict], list[dict]]:
    """Case nodes (with cross-case membership info) + edges from Neo4j."""
    node_recs = await run_cypher(
        "MATCH (n:Entity) WHERE $case IN n.case_ids "
        "RETURN n.entity_id AS id, n.name AS name, n.entity_type AS type, n.case_ids AS case_ids",
        {"case": case_id},
    )
    edge_recs = await run_cypher(
        """MATCH (a:Entity)-[r]->(b:Entity)
           WHERE $case IN a.case_ids AND $case IN b.case_ids
           RETURN a.entity_id AS src, b.entity_id AS tgt, r.relation AS rel""",
        {"case": case_id},
    )
    nodes = [
        {"id": r["id"], "name": r["name"], "type": r["type"], "case_ids": r.get("case_ids") or [case_id]}
        for r in node_recs
    ]
    edges = [{"source": r["src"], "target": r["tgt"], "relation": r["rel"]} for r in edge_recs]
    return nodes, edges


def analyze(nodes: list[dict], edges: list[dict], remove_id: str | None = None) -> dict:
    g = _build_graph([n["id"] for n in nodes], [(e["source"], e["target"]) for e in edges])

    articulation = sorted(nx.articulation_points(g)) if g.number_of_nodes() else []

    before = _component_summary(g)
    result = {
        "node_count": g.number_of_nodes(),
        "edge_count": g.number_of_edges(),
        "articulation_points": articulation,
        "before": before,
    }

    if remove_id:
        if remove_id not in g:
            result["removed"] = {"id": remove_id, "present": False}
            return result
        g2 = g.copy()
        g2.remove_node(remove_id)
        after = _component_summary(g2)

        # Nodes newly cut off from the largest component (fragmented away)
        largest_before = set(max(nx.connected_components(g), key=len)) if g.number_of_nodes() else set()
        largest_after = set(max(nx.connected_components(g2), key=len)) if g2.number_of_nodes() else set()
        fragmented_away = sorted(largest_before - largest_after - {remove_id})

        result["removed"] = {
            "id": remove_id,
            "present": True,
            "is_articulation_point": remove_id in articulation,
        }
        result["after"] = after
        result["metrics"] = {
            "components_delta": after["components"] - before["components"],
            "largest_share_delta": round(after["largest_share"] - before["largest_share"], 4),
            "fragmented_away": fragmented_away,
            "fragmented_count": len(fragmented_away),
            "new_isolated": after["isolated"] - before["isolated"],
        }
        result["explanation"] = _explain(before, after, result["metrics"], remove_id in articulation)

    return result


def _explain(before: dict, after: dict, metrics: dict, is_articulation: bool) -> list[str]:
    """Human-readable, neutral bullet explanations."""
    bullets = []
    bullets.append(
        f"Before removal: {before['components']} connected group(s); largest holds "
        f"{before['largest_share'] * 100:.0f}% of nodes."
    )
    bullets.append(
        f"After removal: {after['components']} group(s); largest holds "
        f"{after['largest_share'] * 100:.0f}% of remaining nodes."
    )
    if metrics["components_delta"] > 0:
        bullets.append(
            f"Removal splits the network into {metrics['components_delta']} additional group(s)."
        )
    else:
        bullets.append("Removal does not disconnect the network — alternate paths exist around this entity.")
    if metrics["fragmented_count"]:
        bullets.append(f"{metrics['fragmented_count']} node(s) become cut off from the main group.")
    if is_articulation:
        bullets.append("This entity is an articulation point: it currently bridges otherwise separate parts of the network.")
    bullets.append("This is a structural connectivity analysis only — it describes the graph, not any individual.")
    return bullets
