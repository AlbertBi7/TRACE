"""
TRACE — Analysis Router (Milestones 8)
Disruption simulator + articulation points over the case subgraph.
Deterministic networkx topology; neutral, structural language throughout.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth.dependencies import get_current_user, require_case_access
from app.graph.analysis import load_case_subgraph, analyze
from app.graph.deep import compute_deep_analysis
from app.graph.heuristics import compute_heuristic_links
from app.graph.priority import compute_priority_scores
from app.db.neo4j_driver import run_cypher

router = APIRouter(prefix="/api/cases", tags=["analysis"])


@router.get("/{case_id}/heuristic-links")
async def heuristic_links(case_id: str, current_user: dict = Depends(get_current_user)):
    """Unconfirmed structural leads (dashed edges in the explorer). Never auto-promoted."""
    await require_case_access(case_id, current_user)
    return await compute_heuristic_links(case_id)


@router.get("/{case_id}/priority-scores")
async def priority_scores(case_id: str, current_user: dict = Depends(get_current_user)):
    """Composite structural prioritization (0-100) with explanations. Not a risk/guilt measure."""
    await require_case_access(case_id, current_user)
    return await compute_priority_scores(case_id)


@router.get("/{case_id}/analysis/structure")
async def structure(case_id: str, current_user: dict = Depends(get_current_user)):
    """Static structure: articulation points + component summary (no removal)."""
    await require_case_access(case_id, current_user)
    nodes, edges = await load_case_subgraph(case_id)
    return analyze(nodes, edges)


@router.post("/{case_id}/analysis/simulate-removal/{entity_id}")
async def simulate_removal(
    case_id: str,
    entity_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Before/after connectivity metrics when one node is hypothetically removed."""
    await require_case_access(case_id, current_user)
    nodes, edges = await load_case_subgraph(case_id)
    return analyze(nodes, edges, remove_id=entity_id)


@router.get("/{case_id}/analysis/deep")
async def deep_analysis(case_id: str, current_user: dict = Depends(get_current_user)):
    """Deep structural analysis: communities, centrality breakdown, k-core, bridges."""
    await require_case_access(case_id, current_user)
    nodes, edges = await load_case_subgraph(case_id)
    result = compute_deep_analysis(nodes, edges)
    result["case_id"] = case_id
    return result


@router.get("/{case_id}/analysis/cross-case-recurrence")
async def cross_case_recurrence(case_id: str, current_user: dict = Depends(get_current_user)):
    """Entities appearing in multiple cases — deterministic Cypher over global case_ids."""
    await require_case_access(case_id, current_user)
    recs = await run_cypher(
        """
        MATCH (e:Entity)
        WHERE size(e.case_ids) > 1
        RETURN e.entity_id AS entity_id, e.name AS name, e.case_ids AS case_ids, size(e.case_ids) AS case_count
        ORDER BY case_count DESC, e.name ASC
        """,
        {},
    )
    # Normalize for frontend
    out = []
    for r in recs:
        out.append({
            "entity_id": r["entity_id"],
            "name": r["name"],
            "case_ids": r["case_ids"],
            "case_count": r["case_count"],
        })
    return {"case_id": case_id, "recurring_entities": out, "count": len(out)}


@router.get("/{case_id}/analysis/paths")
async def path_explorer(
    case_id: str,
    from_id: str = Query(..., alias="from"),
    to_id: str = Query(..., alias="to"),
    max_hops: int = Query(4, ge=1, le=6),
    current_user: dict = Depends(get_current_user),
):
    """Deterministic multi-hop path explorer — parameterized Cypher, no LLM."""
    await require_case_access(case_id, current_user)
    if from_id == to_id:
        raise HTTPException(status_code=400, detail="from and to must be different entities")
    # Ensure both entities are in the case subgraph (or at least exist)
    # Neo4j does not allow a parameter for variable-length upper bound — interpolate validated int
    query = f"""
        MATCH (a:Entity {{entity_id: $from}}), (b:Entity {{entity_id: $to}})
        MATCH p = (a)-[:LINKED*1..{max_hops}]-(b)
        RETURN [x IN nodes(p) | x.entity_id] AS node_ids,
               [x IN nodes(p) | x.name] AS node_names,
               [x IN nodes(p) | x.entity_type] AS node_types,
               [r IN relationships(p) | r.relation] AS rels,
               length(p) AS hops
        ORDER BY hops ASC
        LIMIT 10
        """
    recs = await run_cypher(query, {"from": from_id, "to": to_id})
    paths = []
    for r in recs:
        paths.append({
            "node_ids": r["node_ids"],
            "node_names": r["node_names"],
            "node_types": r["node_types"],
            "rels": r["rels"],
            "hops": r["hops"],
        })
    return {"case_id": case_id, "from": from_id, "to": to_id, "max_hops": max_hops, "paths": paths, "count": len(paths)}
