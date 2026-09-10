"""
TRACE — Heuristic Link Discovery (Milestone 9)
Deterministic topology over the case subgraph. Heuristic edges are
SUGGESTIONS only: they are computed on demand, rendered dashed as
"Heuristic Lead — Unconfirmed", and never auto-promoted to confirmed links.
Kinds:
  shared_infrastructure — two entities touch the same phone/account/vehicle
  common_neighbors      — high Jaccard overlap of neighbor sets
  indirect_funds_flow   — A→B→C transfer chain with no direct A→C edge
"""

import networkx as nx

from app.graph.analysis import load_case_subgraph

INFRA_TYPES = {"PHONE", "BANK_ACCOUNT", "VEHICLE"}
JACCARD_THRESHOLD = 0.34
MIN_SHARED_NEIGHBORS = 2


def _undirected(nodes, edges) -> nx.Graph:
    g = nx.Graph()
    for n in nodes:
        g.add_node(n["id"])
    for e in edges:
        g.add_edge(e["source"], e["target"], relation=e["relation"])
    return g


def _directed(edges) -> nx.DiGraph:
    d = nx.DiGraph()
    for e in edges:
        d.add_edge(e["source"], e["target"], relation=e["relation"])
    return d


async def compute_heuristic_links(case_id: str) -> dict:
    """Load the case subgraph, then run the deterministic lead computation."""
    nodes, edges = await load_case_subgraph(case_id)
    return compute_leads(nodes, edges)


def compute_leads(nodes: list[dict], edges: list[dict]) -> dict:
    """
    Pure/deterministic lead computation over an explicit node/edge list
    (kept separate from the data-loading wrapper so it is unit-testable).
    """
    g = _undirected(nodes, edges)
    dg = _directed(edges)
    node_type = {n["id"]: n["type"] for n in nodes}
    node_name = {n["id"]: n["name"] for n in nodes}

    leads: list[dict] = []
    seen: set[tuple] = set()

    def add(a: str, b: str, kind: str, score: float, explanation: str, shared: list[str] | None = None):
        key = (a, b, kind) if a < b else (b, a, kind)
        if key in seen or a == b:
            return
        if g.has_edge(a, b):
            return  # already a confirmed link — heuristics only fill gaps
        seen.add(key)
        leads.append({
            "source": key[0],
            "target": key[1],
            "kind": kind,
            "score": round(score, 3),
            "explanation": explanation,
            "shared_ids": shared or [],
        })

    persons = [n["id"] for n in nodes if n["type"] == "PERSON"]

    # ── 1) Shared infrastructure between persons ─────────────────────
    for i, p1 in enumerate(persons):
        for p2 in persons[i + 1:]:
            n1, n2 = set(g.neighbors(p1)), set(g.neighbors(p2))
            shared_infra = sorted(x for x in (n1 & n2) if node_type.get(x) in INFRA_TYPES)
            if shared_infra:
                names = [node_name.get(x, x) for x in shared_infra]
                add(
                    p1, p2, "shared_infrastructure", 1.0,
                    f"Both connect to the same {' and '.join(names[:3])}"
                    + (f" (+{len(names)-3} more)" if len(names) > 3 else ""),
                    shared_infra,
                )

    # ── 2) Common-neighbor Jaccard (people/orgs, no direct link) ─────
    for i, a in enumerate(persons):
        for b in persons[i + 1:]:
            na, nb = set(g.neighbors(a)), set(g.neighbors(b))
            union = na | nb
            if not union:
                continue
            shared = na & nb
            if len(shared) >= MIN_SHARED_NEIGHBORS:
                jac = len(shared) / len(union)
                if jac >= JACCARD_THRESHOLD:
                    names = sorted(node_name.get(x, x) for x in shared)
                    add(
                        a, b, "common_neighbors", jac,
                        f"{len(shared)} shared contacts (Jaccard {jac:.2f}): {', '.join(names[:3])}",
                        sorted(shared),
                    )

    # ── 3) Indirect funds flow: A→B→C without direct A→C ─────────────
    for a in dg.nodes:
        for b in list(dg.successors(a)):
            if dg.edges[a, b].get("relation") != "TRANSFERRED_TO":
                continue
            for c in list(dg.successors(b)):
                if c == a or dg.edges[b, c].get("relation") != "TRANSFERRED_TO":
                    continue
                if not dg.has_edge(a, c):
                    add(
                        a, c, "indirect_funds_flow", 0.8,
                        "Indirect funds flow: value can move between these accounts via a two-step transfer chain",
                        [b],
                    )

    leads.sort(key=lambda l: (-l["score"], l["source"], l["target"]))
    return {"edges": leads}
