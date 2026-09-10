"""
TRACE — Graph Router (Milestone 5)
Write path: trigger a re-sync from extraction_log → Neo4j.
Read path: case-scoped nodes/edges for the Cytoscape explorer, plus
provenance detail for the evidentiary drawer.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from app.auth.dependencies import get_current_user, require_case_access
from app.db.postgres import get_pool
from app.graph.service import sync_case_to_graph
from app.db.neo4j_driver import run_cypher

router = APIRouter(prefix="/api/cases", tags=["graph"])


@router.post("/{case_id}/graph/sync")
async def sync_graph(case_id: str, current_user: dict = Depends(get_current_user)):
    """Rebuild the graph for this case from extraction_log + accepted merges."""
    await require_case_access(case_id, current_user)
    result = await sync_case_to_graph(case_id)
    return result


@router.get("/{case_id}/graph")
async def get_case_graph(case_id: str, current_user: dict = Depends(get_current_user)):
    """
    Case-scoped graph for the explorer: nodes of this case plus their direct
    (possibly cross-case) neighbors, and all edges between that node set.
    NOTE: run_cypher serializes relationships as (start, type, end) tuples, so
    edge properties are fetched via properties(r) explicitly.
    """
    await require_case_access(case_id, current_user)

    # 1) Case nodes
    case_node_recs = await run_cypher(
        "MATCH (n:Entity) WHERE $case IN n.case_ids RETURN n",
        {"case": case_id},
    )
    # 2) One-hop neighbors (may belong to other cases — cross-case context)
    neighbor_recs = await run_cypher(
        "MATCH (n:Entity)-[]-(m:Entity) WHERE $case IN n.case_ids RETURN DISTINCT m",
        {"case": case_id},
    )

    def to_node(d: dict) -> dict:
        cases = d.get("case_ids", [])
        return {
            "id": d["entity_id"],
            "label": d.get("name", d["entity_id"]),
            "entity_type": d.get("entity_type", "ENT"),
            "aliases": d.get("aliases", []),
            "provenance_count": len(d.get("provenance_ids", [])),
            "case_ids": cases,
            "in_case": case_id in cases,
        }

    nodes: dict[str, dict] = {}
    for rec in case_node_recs:
        n = to_node(rec["n"])
        nodes[n["id"]] = n
    for rec in neighbor_recs:
        n = to_node(rec["m"])
        nodes.setdefault(n["id"], n)

    # 3) Edges incident to any case node; keep those within the node set.
    edge_recs = await run_cypher(
        """MATCH (a:Entity)-[r]->(b:Entity)
           WHERE $case IN a.case_ids OR $case IN b.case_ids
           RETURN a.entity_id AS source, b.entity_id AS target, properties(r) AS props""",
        {"case": case_id},
    )

    edges: list[dict] = []
    for rec in edge_recs:
        src, tgt, props = rec["source"], rec["target"], rec["props"]
        if src not in nodes or tgt not in nodes:
            continue
        edges.append({
            "id": f"{src}|{props.get('relation', 'LINKED')}|{tgt}",
            "source": src,
            "target": tgt,
            "relation": props.get("relation", "LINKED"),
            "provenance_ids": props.get("provenance_ids", []),
            "case_ids": props.get("case_ids", []),
            "observations": props.get("observations", 1),
        })

    return {
        "case_id": case_id,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


@router.get("/{case_id}/graph/nodes/{entity_id}")
async def get_node_detail(
    case_id: str,
    entity_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Evidentiary drawer payload: node metadata, aliases, cross-case presence,
    and verbatim provenance (snippet + file + page + paragraph) resolved from
    extraction_log.
    """
    await require_case_access(case_id, current_user)

    recs = await run_cypher(
        "MATCH (n:Entity {entity_id: $eid}) RETURN n LIMIT 1",
        {"eid": entity_id},
    )
    if not recs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found in graph")
    n = recs[0]["n"]

    prov_ids = n.get("provenance_ids", [])
    provenance = []
    if prov_ids:
        pool = await get_pool()
        rows = await pool.fetch(
            """SELECT e.id, e.snippet, e.page, e.paragraph, e.entity_type, e.extractor,
                      e.confidence, e.value,
                      d.filename, d.id AS document_id
               FROM extraction_log e
               JOIN documents d ON d.id = e.document_id
               WHERE e.id = ANY($1::uuid[])""",
            prov_ids,
        )
        provenance = [
            {
                "provenance_id": str(r["id"]),
                "document_id": str(r["document_id"]),
                "filename": r["filename"],
                "page": r["page"],
                "paragraph": r["paragraph"],
                "snippet": r["snippet"],
                "entity_type": r["entity_type"],
                "extractor": r["extractor"],
                "confidence": r["confidence"],
                "value": r["value"],
            }
            for r in rows
        ]

    # Edges touching this node — properties via properties(r) (see get_case_graph note)
    edge_recs = await run_cypher(
        """MATCH (n:Entity {entity_id: $eid})-[r]-(m:Entity)
           RETURN m.entity_id AS other_id, m.name AS other_name,
                  m.entity_type AS other_type, r.relation AS relation,
                  startNode(r).entity_id = $eid AS outgoing""",
        {"eid": entity_id},
    )

    return {
        "id": n["entity_id"],
        "label": n.get("name", entity_id),
        "entity_type": n.get("entity_type", "ENT"),
        "aliases": n.get("aliases", []),
        "case_ids": n.get("case_ids", []),
        "cross_case": case_id not in n.get("case_ids", []),
        "provenance": provenance,
        "edges": [
            {
                "other_id": e["other_id"],
                "other_name": e["other_name"],
                "other_type": e["other_type"],
                "relation": e["relation"],
                "direction": "out" if e["outgoing"] else "in",
            }
            for e in edge_recs
        ],
    }
