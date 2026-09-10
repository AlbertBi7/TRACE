"""
TRACE — Priority Score (Milestone 10)
Composite 0–100 structural score for CASE PRIORITIZATION of analytical
attention. It is explicitly NOT a risk/guilt measure of individuals:
  - betweenness centrality (network bridging)
  - PageRank (relative connectivity weight)
  - cross-case recurrence (how many cases reference this entity)
Every score ships with human-readable bullet explanations and its
provenance-backed graph footprint. Neutral language only.
"""

import networkx as nx

from app.graph.analysis import load_case_subgraph

WEIGHTS = {"betweenness": 0.4, "pagerank": 0.4, "cross_case": 0.2}

# Cross-case recurrence is GRADED, not binary: an entity referenced in 5 cases
# contributes more than one in 2. Contribution ramps linearly with the number
# of ADDITIONAL cases and saturates at RECURRENCE_CAP so a single extremely
# widespread entity cannot dominate the cross-case component:
#   cases:  1   2     3     4     5+  →  cross-case contribution (of 0.2 weight)
#           0  0.05  0.10  0.15  0.20
RECURRENCE_CAP = 4


def _cross_case_norm(case_count: int) -> float:
    """Graded cross-case contribution in [0, 1] (saturating, capped-linear)."""
    if case_count <= 1:
        return 0.0
    return min(case_count - 1, RECURRENCE_CAP) / RECURRENCE_CAP


def _pagerank(g: nx.Graph, alpha: float = 0.85, max_iter: int = 100, tol: float = 1e-8) -> dict:
    """
    Power-iteration PageRank (dependency-free — networkx's implementation
    requires scipy). Deterministic: uniform start, fixed iteration order.
    """
    n = g.number_of_nodes()
    if n == 0:
        return {}
    ranks = {node: 1.0 / n for node in g.nodes}
    out_degree = dict(g.degree)
    # Precompute neighbor lists once (undirected graph)
    neighbors = {node: list(g.neighbors(node)) for node in g.nodes}
    for _ in range(max_iter):
        dangling_mass = sum(ranks[node] for node in g.nodes if out_degree[node] == 0)
        new_ranks = {}
        for node in g.nodes:
            inflow = sum(ranks[nb] / out_degree[nb] for nb in neighbors[node])
            new_ranks[node] = (1 - alpha) / n + alpha * (inflow + dangling_mass / n)
        delta = sum(abs(new_ranks[node] - ranks[node]) for node in g.nodes)
        ranks = new_ranks
        if delta < tol:
            break
    return ranks


def _betweenness_label(v: float) -> str:
    if v >= 0.5: return "very high"
    if v >= 0.2: return "high"
    if v >= 0.05: return "moderate"
    return "low"


def _explain(betweenness: float, pagerank_norm: float, case_count: int, is_articulation: bool) -> list[str]:
    bullets = []
    bullets.append(
        f"Betweenness centrality is {_betweenness_label(betweenness)} ({betweenness:.3f}) — "
        + (
            "this entity sits on many shortest paths between other entities."
            if betweenness >= 0.2 else
            "this entity sits on few shortest paths between others."
        )
    )
    bullets.append(
        f"PageRank weight is {pagerank_norm:.3f} (normalized within this case) — "
        + (
            "strongly connected within the network."
            if pagerank_norm >= 0.5 else
            "moderately to weakly connected within the network."
        )
    )
    if is_articulation:
        bullets.append("Removing this entity would disconnect part of the network (articulation point).")
    if case_count > 1:
        extra = case_count - 1
        bullets.append(
            f"This entity is referenced in {case_count} case(s) ({extra} beyond this one) — "
            "cross-case recurrence is scaled into the score and may warrant coordination between teams."
        )
    bullets.append(
        "This score measures structural position in the network only. It is not an assessment "
        "of any person's conduct, culpability, or risk."
    )
    return bullets


async def compute_priority_scores(case_id: str) -> dict:
    nodes, edges = await load_case_subgraph(case_id)
    g = nx.Graph()
    g.add_nodes_from([n["id"] for n in nodes])
    g.add_edges_from([(e["source"], e["target"]) for e in edges])

    if g.number_of_nodes() == 0:
        return {"scores": []}

    bet = nx.betweenness_centrality(g)
    pr = _pagerank(g, alpha=0.85)
    pr_max = max(pr.values()) or 1.0
    articulation = set(nx.articulation_points(g)) if g.number_of_edges() else set()
    meta = {n["id"]: n for n in nodes}

    scores = []
    for nid in g.nodes:
        b, p = bet.get(nid, 0.0), pr.get(nid, 0.0) / pr_max
        case_count = len(meta.get(nid, {}).get("case_ids", []) or [case_id])
        cross_norm = _cross_case_norm(case_count)

        composite = 100 * (WEIGHTS["betweenness"] * b + WEIGHTS["pagerank"] * p + WEIGHTS["cross_case"] * cross_norm)

        scores.append({
            "entity_id": nid,
            "name": meta.get(nid, {}).get("name", nid),
            "entity_type": meta.get(nid, {}).get("type", "ENT"),
            "score": round(composite, 1),
            "components": {
                "betweenness": round(b, 4),
                "pagerank_normalized": round(p, 4),
                "cross_case_recurrence": max(case_count - 1, 0),
                "cross_case_norm": round(cross_norm, 3),
            },
            "is_articulation_point": nid in articulation,
            "explanation": _explain(b, p, case_count, nid in articulation),
        })

    scores.sort(key=lambda s: -s["score"])
    return {"scores": scores}
