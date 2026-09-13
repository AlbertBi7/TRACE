"""
TRACE — Deep Structural Analysis (Extension)
Deterministic networkx on the case subgraph loaded via load_case_subgraph.
All outputs are topology-only, neutral language.
"""

import logging
import networkx as nx
from networkx.algorithms.community import louvain_communities

logger = logging.getLogger("trace.deep")


def compute_deep_analysis(nodes: list[dict], edges: list[dict]) -> dict:
    """
    Single networkx load, multiple algorithms.
    Returns communities, centrality breakdown, k-core, bridges.
    """
    g = nx.Graph()
    g.add_nodes_from([n["id"] for n in nodes])
    g.add_edges_from([(e["source"], e["target"]) for e in edges])

    n_nodes = g.number_of_nodes()
    n_edges = g.number_of_edges()

    # ── Communities (Louvain, seed=42) ──────────────────────────
    communities = []
    node_community = {}
    if n_nodes:
        try:
            # louvain is deterministic with seed; handles disconnected graphs
            comm_sets = louvain_communities(g, seed=42)
            # Sort for determinism: larger first, then lexicographically
            comm_sets = sorted([sorted(c) for c in comm_sets], key=lambda x: (-len(x), x))
            for idx, comm in enumerate(comm_sets):
                communities.append({"community_id": idx, "nodes": comm, "size": len(comm)})
                for nid in comm:
                    node_community[nid] = idx
            # Isolated nodes not assigned by some implementations — assign own
            for nid in g.nodes:
                if nid not in node_community:
                    # find or create singleton
                    communities.append({"community_id": len(communities), "nodes": [nid], "size": 1})
                    node_community[nid] = len(communities) - 1
        except Exception as e:
            logger.warning(f"louvain failed: {e}, falling back to single community")
            # Fallback: one community per connected component
            try:
                comps = sorted([sorted(c) for c in nx.connected_components(g)], key=lambda x: (-len(x), x))
                for idx, comp in enumerate(comps):
                    communities.append({"community_id": idx, "nodes": comp, "size": len(comp)})
                    for nid in comp:
                        node_community[nid] = idx
            except Exception:
                communities = [{"community_id": 0, "nodes": sorted(g.nodes), "size": n_nodes}]
                node_community = {nid: 0 for nid in g.nodes}
    # ── Centrality breakdown ────────────────────────────────────
    betweenness = {}
    closeness = {}
    eigenvector = {}
    degree = {}
    eigenvector_fallback = False
    if n_nodes:
        try:
            betweenness = nx.betweenness_centrality(g, normalized=True)
        except Exception as e:
            logger.warning(f"betweenness failed: {e}")
            betweenness = {nid: 0.0 for nid in g.nodes}
        try:
            closeness = nx.closeness_centrality(g)
        except Exception as e:
            logger.warning(f"closeness failed: {e}")
            closeness = {nid: 0.0 for nid in g.nodes}
        try:
            # eigenvector can fail to converge; try with higher max_iter
            eigenvector = nx.eigenvector_centrality(g, max_iter=1000)
        except Exception as e:
            logger.warning(f"eigenvector failed ({e}), falling back to degree")
            eigenvector_fallback = True
            # fallback: normalized degree
            max_deg = max(dict(g.degree).values()) or 1
            eigenvector = {nid: deg / max_deg for nid, deg in g.degree}
        degree = dict(g.degree)

        # Round for JSON stability
        betweenness = {k: round(float(v), 5) for k, v in betweenness.items()}
        closeness = {k: round(float(v), 5) for k, v in closeness.items()}
        eigenvector = {k: round(float(v), 5) for k, v in eigenvector.items()}
        degree = {k: int(v) for k, v in degree.items()}
    else:
        betweenness = {}
        closeness = {}
        eigenvector = {}
        degree = {}

    # ── K-core decomposition ────────────────────────────────────
    core_numbers = {}
    cores = {}
    max_core = 0
    if n_nodes and n_edges:
        try:
            core_numbers = nx.core_number(g)
            max_core = max(core_numbers.values()) if core_numbers else 0
            # Group nodes by core level
            for nid, lvl in core_numbers.items():
                cores.setdefault(str(lvl), []).append(nid)
            # Sort each level for determinism
            for lvl in cores:
                cores[lvl] = sorted(cores[lvl])
        except Exception as e:
            logger.warning(f"k-core failed: {e}")
            core_numbers = {nid: 0 for nid in g.nodes}
            cores = {"0": sorted(g.nodes)}
    elif n_nodes:
        core_numbers = {nid: 0 for nid in g.nodes}
        cores = {"0": sorted(g.nodes)}

    # ── Bridges (edge-level articulation) ───────────────────────
    bridges = []
    if n_nodes and n_edges:
        try:
            bridges = sorted([sorted(list(b)) for b in nx.bridges(g)])
            bridges = [{"source": b[0], "target": b[1]} for b in bridges]
        except Exception as e:
            logger.warning(f"bridges failed: {e}")
            bridges = []

    return {
        "node_count": n_nodes,
        "edge_count": n_edges,
        "communities": communities,
        "node_community": node_community,
        "centrality": {
            "betweenness": betweenness,
            "closeness": closeness,
            "eigenvector": eigenvector,
            "degree": degree,
            "eigenvector_fallback": eigenvector_fallback,
        },
        "k_core": {
            "core_numbers": core_numbers,
            "cores": cores,
            "max_core": max_core,
        },
        "bridges": bridges,
    }
