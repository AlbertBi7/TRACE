"""
TRACE — Case Network Graph (FIR-level)
Nodes = cases, edges = shared entities (factual, provenance-backed).
Deterministic Cypher + Python aggregation, RBAC-scoped, no LLM.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.dependencies import get_current_user
from app.db.postgres import get_pool
from app.db.neo4j_driver import run_cypher
import uuid

router = APIRouter(prefix="/api/analysis", tags=["case-network"])


async def _accessible_case_ids(current_user: dict) -> set[str]:
    """Return set of case IDs the user can see."""
    pool = await get_pool()
    if current_user["role"] == "admin":
        rows = await pool.fetch("SELECT id FROM cases")
        return {str(r["id"]) for r in rows}
    # investigator: assigned cases + created cases (some tests create via admin but assign)
    rows = await pool.fetch(
        "SELECT case_id FROM case_assignments WHERE user_id = $1",
        str(current_user["id"]),
    )
    assigned = {str(r["case_id"]) for r in rows}
    # also include cases they created (for tests where admin created but investigator is creator? actually no)
    # Check cases where created_by = user (covers own created)
    rows2 = await pool.fetch("SELECT id FROM cases WHERE created_by = $1", str(current_user["id"]))
    created = {str(r["id"]) for r in rows2}
    return assigned | created


@router.get("/case-network")
async def case_network(current_user: dict = Depends(get_current_user)):
    """
    Case-level network: nodes=cases, edges=shared entities.
    Respects RBAC — investigators only see edges where both cases are accessible.
    """
    accessible = await _accessible_case_ids(current_user)
    if not accessible:
        return {"nodes": [], "edges": [], "count": 0}

    # 1) Fetch all recurring entities (global)
    recs = await run_cypher(
        """
        MATCH (e:Entity)
        WHERE size(e.case_ids) > 1
        RETURN e.entity_id AS entity_id, e.name AS name, e.entity_type AS type, e.case_ids AS case_ids
        """,
        {},
    )

    # 2) Build case-case edges in Python, filtering to accessible cases
    # edge key -> {shared_entities: [{id,name,type}], shared_count}
    edge_map: dict[tuple[str, str], dict] = {}
    # Also collect case_ids that actually appear in recurring entities and are accessible
    # For node metadata we need all accessible cases, not just those with edges
    for r in recs:
        cids = r["case_ids"] or []
        # Filter to accessible cases for this entity
        # Keep only cids that are accessible
        accessible_cids = [cid for cid in cids if cid in accessible]
        # Need at least 2 accessible cids to create an edge visible to this user
        if len(accessible_cids) < 2:
            continue
        # Generate all pairs among accessible_cids for this entity
        # Sort to ensure deterministic key
        accessible_cids = sorted(accessible_cids)
        for i in range(len(accessible_cids)):
            for j in range(i + 1, len(accessible_cids)):
                a, b = accessible_cids[i], accessible_cids[j]
                key = (a, b) if a < b else (b, a)
                # Use sorted key
                if a > b:
                    a, b = b, a
                    key = (a, b)
                entry = edge_map.setdefault(key, {"shared_entities": [], "shared_count": 0})
                entry["shared_entities"].append({
                    "entity_id": r["entity_id"],
                    "name": r["name"],
                    "type": r["type"],
                })
                entry["shared_count"] += 1

    # If no edges, still return nodes (all accessible cases)
    # Fetch case metadata for nodes
    pool = await get_pool()
    # Use parameterized query for accessible ids
    # asyncpg doesn't support list of uuid easily via ANY, so we use text conversion
    # Convert to uuid array via ::uuid[]
    # If accessible is large, we can just fetch all and filter in Python
    all_cases = await pool.fetch("SELECT id, name, status, created_at FROM cases")
    accessible_cases = [r for r in all_cases if str(r["id"]) in accessible]

    # Entity/doc counts per case (for sizing)
    # Entity counts via Neo4j: count per case
    # We can do a single Cypher with UNWIND
    entity_counts = {}
    if accessible:
        count_recs = await run_cypher(
            """
            UNWIND $cids AS cid
            MATCH (n:Entity) WHERE cid IN n.case_ids
            RETURN cid AS case_id, count(n) AS cnt
            """,
            {"cids": list(accessible)},
        )
        for r in count_recs:
            entity_counts[r["case_id"]] = r["cnt"]

    doc_counts = {}
    doc_rows = await pool.fetch("SELECT case_id, COUNT(*) AS cnt FROM documents GROUP BY case_id")
    for r in doc_rows:
        cid = str(r["case_id"])
        if cid in accessible:
            doc_counts[cid] = r["cnt"]

    nodes = []
    for r in accessible_cases:
        cid = str(r["id"])
        nodes.append({
            "id": cid,
            "title": r["name"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "entity_count": entity_counts.get(cid, 0),
            "doc_count": doc_counts.get(cid, 0),
        })

    edges = []
    for (a, b), data in edge_map.items():
        # Sort shared entities by name for determinism
        shared_sorted = sorted(data["shared_entities"], key=lambda x: x["name"])
        edges.append({
            "source": a,
            "target": b,
            "shared_count": data["shared_count"],
            "shared_entities": shared_sorted,
            "id": f"{a}|{b}",
        })
    # Sort edges by shared_count desc
    edges.sort(key=lambda e: (-e["shared_count"], e["source"], e["target"]))

    return {"nodes": nodes, "edges": edges, "count": len(nodes)}


@router.get("/case-network/edge")
async def case_network_edge(
    case_a: str = Query(..., alias="case_a"),
    case_b: str = Query(..., alias="case_b"),
    current_user: dict = Depends(get_current_user),
):
    """
    Drill-down for a specific case pair — returns shared entities with provenance per case.
    """
    # RBAC: must have access to both cases
    accessible = await _accessible_case_ids(current_user)
    if case_a not in accessible or case_b not in accessible:
        raise HTTPException(status_code=403, detail="Not assigned to one or both cases")

    # Validate UUIDs
    try:
        uuid.UUID(case_a)
        uuid.UUID(case_b)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid case ID format")

    # Find shared entities
    recs = await run_cypher(
        """
        MATCH (e:Entity)
        WHERE $a IN e.case_ids AND $b IN e.case_ids
        RETURN e.entity_id AS entity_id, e.name AS name, e.entity_type AS type, e.aliases AS aliases, e.provenance_ids AS provenance_ids, e.case_ids AS case_ids
        ORDER BY e.name ASC
        """,
        {"a": case_a, "b": case_b},
    )

    if not recs:
        return {"case_a": case_a, "case_b": case_b, "shared_entities": [], "count": 0}

    # Collect all provenance_ids to fetch in one batch
    all_prov = []
    for r in recs:
        all_prov.extend(r["provenance_ids"] or [])
    # Filter valid UUIDs
    valid_prov = []
    for pid in all_prov:
        try:
            uuid.UUID(str(pid))
            valid_prov.append(pid)
        except (ValueError, AttributeError):
            continue
    # Dedupe
    valid_prov = list(dict.fromkeys(valid_prov))

    # Fetch provenance details
    pool = await get_pool()
    prov_rows = []
    if valid_prov:
        prov_rows = await pool.fetch(
            """SELECT e.id, e.entity_or_edge_id, e.snippet, e.page, e.paragraph, e.entity_type, e.extractor, e.confidence, e.value,
                      d.filename, d.id AS document_id, d.case_id
               FROM extraction_log e JOIN documents d ON d.id = e.document_id
               WHERE e.id = ANY($1::uuid[])""",
            valid_prov,
        )

    # Group prov by entity_id and case
    from collections import defaultdict
    prov_by_entity = defaultdict(list)
    for row in prov_rows:
        prov_by_entity[row["entity_or_edge_id"]].append({
            "provenance_id": str(row["id"]),
            "document_id": str(row["document_id"]),
            "case_id": str(row["case_id"]),
            "filename": row["filename"],
            "page": row["page"],
            "paragraph": row["paragraph"],
            "snippet": row["snippet"],
            "entity_type": row["entity_type"],
            "extractor": row["extractor"],
            "confidence": row["confidence"],
            "value": row["value"],
        })

    shared = []
    for r in recs:
        eid = r["entity_id"]
        # Find provenance for this entity - need to match entity_or_edge_id to eid
        # For merged entities, provenance may be under different IDs (aliases) but stored under global node's provenance_ids
        # So we already have all prov for this node via its provenance_ids list, not via entity_or_edge_id
        # We need to collect prov that are in this node's provenance_ids and group by case
        node_prov_ids = set(r["provenance_ids"] or [])
        entity_provs = [p for p in prov_rows if str(p["id"]) in node_prov_ids]
        # Group by case
        by_case = defaultdict(list)
        for p in entity_provs:
            # p is asyncpg Record, need to convert
            # Re-use prov_by_entity logic but filter to node_prov_ids
            pass
        # Simpler: build from prov_rows filtered to node_prov_ids
        provs_for_node = []
        for row in prov_rows:
            if str(row["id"]) in node_prov_ids:
                provs_for_node.append({
                    "provenance_id": str(row["id"]),
                    "document_id": str(row["document_id"]),
                    "case_id": str(row["case_id"]),
                    "filename": row["filename"],
                    "page": row["page"],
                    "paragraph": row["paragraph"],
                    "snippet": row["snippet"],
                })
        # Group by case for UI
        provs_by_case = defaultdict(list)
        for p in provs_for_node:
            provs_by_case[p["case_id"]].append(p)

        shared.append({
            "entity_id": eid,
            "name": r["name"],
            "type": r["type"],
            "aliases": r["aliases"] or [],
            "case_ids": r["case_ids"],
            "provenance_by_case": dict(provs_by_case),
            "provenance": provs_for_node,  # flat list for convenience
        })

    return {"case_a": case_a, "case_b": case_b, "shared_entities": shared, "count": len(shared)}
