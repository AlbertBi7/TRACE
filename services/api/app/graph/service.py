"""
TRACE — Knowledge Graph Write Service (Milestone 5)
Aggregates extraction_log (Postgres source of truth) into Neo4j:
  - Union-find canonicalization over ACCEPTED entity_merges only
  - Deterministic global node ids (case-independent dedupe of the same real-world entity)
  - Idempotent MERGE writes; re-syncs converge to the same graph
  - Every node/edge carries real provenance_ids (extraction_log UUIDs) + case_ids
Static seed.cypher remains a dev/demo fixture, fully separate from this path.
"""

import hashlib
import logging
from collections import defaultdict

from app.db.postgres import get_pool
from app.db.neo4j_driver import run_cypher
from app.config import settings

logger = logging.getLogger("trace.graph")


def _h8(*parts: str) -> str:
    return hashlib.sha1("|".join(p.lower() for p in parts).encode()).hexdigest()[:8].upper()


def _global_entity_id(entity_type: str, canonical_value: str) -> str:
    prefix = {"PERSON": "PER", "ORG": "ORG", "LOCATION": "LOC",
              "PHONE": "PHN", "VEHICLE": "VEH", "BANK_ACCOUNT": "BA"}.get(entity_type, "ENT")
    return f"{prefix}-{_h8(entity_type, canonical_value)}"


def build_canonicalization(merges: list[dict]) -> dict[str, str]:
    """
    Union-find over accepted merges: alias entity id → canonical entity id.
    Merges map extraction ids; canonical value comes from the canonical
    extraction id's most representative value in the caller.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        # Canonical = lexicographically smaller id (stable across runs)
        lo, hi = sorted([ra, rb])
        parent[hi] = lo

    for m in merges:
        union(m["primary_entity_id"], m["merged_entity_id"])

    # Return FULLY resolved roots: the raw parent map holds intermediate links
    # (a→b→c), and consumers treat the result as a direct alias→root lookup.
    return {k: find(k) for k in parent}


def normalize_entities(entity_rows: list[dict], canon_parent: dict[str, str], value_of: dict[str, str]) -> dict[str, dict]:
    """
    Collapse extraction ids to canonical nodes.
    Returns global_id → {entity_type, name, aliases, provenance_ids, case_ids}
    """
    nodes: dict[str, dict] = {}
    for r in entity_rows:
        ext_id = r["entity_or_edge_id"]
        root = canon_parent.get(ext_id, ext_id)
        g_id = _global_entity_id(r["entity_type"], value_of.get(root, r["value"]))
        node = nodes.setdefault(g_id, {
            "entity_type": r["entity_type"],
            "name": value_of.get(root, r["value"]),
            "aliases": set(), "provenance_ids": set(), "case_ids": set(),
        })
        node["aliases"].add(r["value"])
        node["provenance_ids"].add(str(r["provenance_id"]))
        node["case_ids"].add(str(r["case_id"]))

    # Display name = most complete surface form (longest alias); deterministic.
    for node in nodes.values():
        node["name"] = max(node["aliases"], key=len)
    return nodes


def normalize_relations(rel_rows: list[dict], canon_parent: dict[str, str], value_of: dict[str, str]) -> list[dict]:
    """Collapse relation rows to canonical edges (dedupe repeated observations)."""
    edges: dict[tuple, dict] = {}
    for r in rel_rows:
        head_root = canon_parent.get(r["head_entity_id"], r["head_entity_id"])
        tail_root = canon_parent.get(r["tail_entity_id"], r["tail_entity_id"])
        head_type = r["head_type"] or "ENT"
        tail_type = r["tail_type"] or "ENT"
        head_gid = _global_entity_id(head_type, value_of.get(head_root, r["head_value"]))
        tail_gid = _global_entity_id(tail_type, value_of.get(tail_root, r["tail_value"]))
        key = (head_gid, r["relation"], tail_gid)
        e = edges.setdefault(key, {
            "head": head_gid, "tail": tail_gid, "relation": r["relation"],
            "provenance_ids": set(), "case_ids": set(), "count": 0,
        })
        e["provenance_ids"].add(str(r["provenance_id"]))
        e["case_ids"].add(str(r["case_id"]))
        e["count"] += 1
    return list(edges.values())


async def sync_case_to_graph(case_id: str | None = None) -> dict:
    """
    Rebuild the TRACE graph from extraction_log + accepted merges.
    Reads are ALWAYS global: the same entity seen in two cases must become ONE
    node carrying both case_ids — that's what enables cross-case recurrence
    (Milestone 10). A case-scoped read would overwrite shared nodes' case_ids
    with a single case on every per-case sync, destroying recurrence data.
    Reconciliation below still only strips membership for the requested case,
    so per-case syncs remain safe and idempotent.
    """
    pool = await get_pool()

    entity_rows = await pool.fetch(
        """SELECT e.entity_or_edge_id, e.entity_type, e.value,
                  e.id AS provenance_id, d.case_id
            FROM extraction_log e
            JOIN documents d ON d.id = e.document_id
            WHERE e.head_entity_id = '' AND e.value <> ''""",
    )
    rel_rows = await pool.fetch(
        """SELECT e.head_entity_id, e.tail_entity_id, e.entity_type AS relation,
                   e.id AS provenance_id, d.case_id,
                   he.value AS head_value, te.value AS tail_value,
                   he.entity_type AS head_type, te.entity_type AS tail_type
            FROM extraction_log e
            JOIN documents d ON d.id = e.document_id
            LEFT JOIN extraction_log he ON he.entity_or_edge_id = e.head_entity_id
                 AND he.head_entity_id = '' AND he.value <> ''
            LEFT JOIN extraction_log te ON te.entity_or_edge_id = e.tail_entity_id
                 AND te.head_entity_id = '' AND te.value <> ''
            WHERE e.head_entity_id <> ''""",
    )
    merge_rows = await pool.fetch(
        """SELECT primary_entity_id, merged_entity_id FROM entity_merges
           WHERE status = 'accepted'""",
    )

    canon_parent = build_canonicalization([dict(m) for m in merge_rows])

    # value_of: representative (most frequent) surface value per extraction id
    value_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in entity_rows:
        value_counts[r["entity_or_edge_id"]][r["value"]] += 1
    value_of = {eid: max(vals, key=vals.get) for eid, vals in value_counts.items()}

    nodes = normalize_entities([dict(r) for r in entity_rows], canon_parent, value_of)
    edges = normalize_relations([dict(r) for r in rel_rows], canon_parent, value_of)

    # ── Idempotent Neo4j writes ─────────────────────────────────────────
    for gid, n in nodes.items():
        await run_cypher(
            """MERGE (x:Entity {entity_id: $gid})
               SET x.entity_type = $etype,
                   x.name = $name,
                   x.aliases = $aliases,
                   x.provenance_ids = $prov,
                   x.case_ids = $cases""",
            {
                "gid": gid,
                "etype": n["entity_type"],
                "name": n["name"],
                "aliases": sorted(n["aliases"]),
                "prov": sorted(n["provenance_ids"]),
                "cases": sorted(n["case_ids"]),
            },
        )

    for e in edges:
        await run_cypher(
            """MATCH (a:Entity {entity_id: $h}), (b:Entity {entity_id: $t})
               MERGE (a)-[r:LINKED {relation: $rel}]->(b)
               SET r.provenance_ids = $prov,
                   r.case_ids = $cases,
                   r.observations = $count""",
            {
                "h": e["head"], "t": e["tail"], "rel": e["relation"],
                "prov": sorted(e["provenance_ids"]),
                "cases": sorted(e["case_ids"]),
                "count": e["count"],
            },
        )

    # ── Reconcile stale data: Postgres is the source of truth. Any node/edge
    # still carrying this case's membership but no longer supported by current
    # extraction data loses that membership (and is deleted if orphaned).
    await run_cypher(
        """MATCH (n:Entity)
           WHERE $case IN n.case_ids AND NOT n.entity_id IN $keep
           SET n.case_ids = [c IN n.case_ids WHERE c <> $case]
           WITH n WHERE size(n.case_ids) = 0
           DETACH DELETE n""",
        {"case": case_id, "keep": list(nodes.keys())},
    )
    keep_keys = [f"{e['head']}|{e['relation']}|{e['tail']}" for e in edges]
    await run_cypher(
        """MATCH (a:Entity)-[r:LINKED]->(b:Entity)
           WHERE $case IN r.case_ids
             AND NOT (a.entity_id + '|' + r.relation + '|' + b.entity_id) IN $keep
           SET r.case_ids = [c IN r.case_ids WHERE c <> $case]
           WITH r WHERE size(r.case_ids) = 0
           DELETE r""",
        {"case": case_id, "keep": keep_keys},
    )

    n_groups = len({canon_parent.get(k, k) for k in canon_parent})
    logger.info(f"Graph sync complete: {len(nodes)} nodes, {len(edges)} edges, {n_groups} canonical groups")
    return {"nodes": len(nodes), "edges": len(edges), "canonical_groups": n_groups}
