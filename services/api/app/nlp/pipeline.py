"""
TRACE — Extraction Pipeline Orchestrator (Milestone 3)
Runs: entities (regex+NER) → relations (patterns, optional scoped LLM fallback)
→ extraction_log provenance rows → document status update.
Stable entity IDs are deterministic hashes of (type, value) so the same
surface form found in different documents shares one extraction identity —
this is what entity resolution (Milestone 4) builds on.
"""

import asyncio
import hashlib
import json
import logging

from app.db.postgres import get_pool
from app.ingestion.provenance import write_extraction_rows
from app.nlp.entities import extract_entities
from app.nlp.relations import extract_relations, resolve_llm_calls

logger = logging.getLogger("trace.nlp")

TYPE_PREFIX = {
    "PERSON": "PER", "ORG": "ORG", "LOCATION": "LOC",
    "PHONE": "PHN", "VEHICLE": "VEH", "BANK_ACCOUNT": "BA",
}


def _entity_id(entity_type: str, value: str) -> str:
    """Deterministic extraction identity: TYPE-HASH8 of (type, lowercase value)."""
    h = hashlib.sha1(f"{entity_type}|{value.lower()}".encode()).hexdigest()[:8].upper()
    return f"{TYPE_PREFIX.get(entity_type, 'ENT')}-{h}"


def _edge_id(head_id: str, relation: str, tail_id: str) -> str:
    h = hashlib.sha1(f"{head_id}|{relation}|{tail_id}".encode()).hexdigest()[:8].upper()
    return f"REL-{h}"


def _resolve_entity_ids(entities: list[dict], relations: list[dict]) -> None:
    """Attach stable ids to entity rows and map relation values → entity ids."""
    by_value = {(e["entity_type"], e["value"].lower()): _entity_id(e["entity_type"], e["value"]) for e in entities}
    for e in entities:
        e["entity_or_edge_id"] = by_value[(e["entity_type"], e["value"].lower())]
    for r in relations:
        head_type = r.pop("_head_type", "")
        tail_type = r.pop("_tail_type", "")
        r["head_id"] = by_value.get((head_type, r["head_value"].lower()), _entity_id(head_type or "ENT", r["head_value"]))
        r["tail_id"] = by_value.get((tail_type, r["tail_value"].lower()), _entity_id(tail_type or "ENT", r["tail_value"]))
        r["entity_or_edge_id"] = _edge_id(r["head_id"], r["relation"], r["tail_id"])


async def run_extraction(document_id: str, use_llm_fallback: bool = True) -> dict:
    """
    Full extraction for one document. Idempotent: replaces any prior
    extraction_log rows for this document.
    """
    pool = await get_pool()
    doc = await pool.fetchrow(
        "SELECT id, case_id, filename, parsed_content FROM documents WHERE id = $1",
        document_id,
    )
    if not doc:
        raise ValueError("Document not found")

    parsed = doc["parsed_content"] if isinstance(doc["parsed_content"], dict) else json.loads(doc["parsed_content"] or "{}")
    pages = parsed.get("pages", [])
    if not pages:
        raise ValueError("Document has no parsed content — re-upload the file")

    # 1) Entities
    entities = extract_entities(pages)

    # 2) Relations over co-occurring entities; resolve endpoint types first so
    #    relation rows can be joined to entity ids deterministically.
    type_by_value = {}
    for e in entities:
        type_by_value.setdefault(e["value"].lower(), e["entity_type"])
    relations, llm_calls = extract_relations(pages, entities, use_llm_fallback=use_llm_fallback)
    for r in relations:
        r["_head_type"] = type_by_value.get(r["head_value"].lower(), "ENT")
        r["_tail_type"] = type_by_value.get(r["tail_value"].lower(), "ENT")

    # 3) Scoped LLM fallback for below-threshold pairs (no-op without config)
    extra_relations = []
    if llm_calls:
        extra_relations = await resolve_llm_calls(llm_calls)
        relations.extend(extra_relations)

    _resolve_entity_ids(entities, relations)

    # 4) Persist provenance rows (replace any prior rows for this document)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM extraction_log WHERE document_id = $1", document_id)

    entity_rows = [
        {
            "entity_or_edge_id": e["entity_or_edge_id"],
            "entity_type": e["entity_type"],
            "value": e["value"],
            "snippet": e["snippet"],
            "page": e["page"],
            "paragraph": e["paragraph"],
            "extractor": e["extractor"],
            "confidence": e["confidence"],
        }
        for e in entities
    ]
    relation_rows = [
        {
            "entity_or_edge_id": r["entity_or_edge_id"],
            "entity_type": r["relation"],
            "value": f"{r['head_value']} -[{r['relation']}]-> {r['tail_value']}",
            "snippet": r["snippet"],
            "page": r["page"],
            "paragraph": r["paragraph"],
            "extractor": r["extractor"],
            "confidence": r["confidence"],
            "head_entity_id": r["head_id"],
            "tail_entity_id": r["tail_id"],
        }
        for r in relations
    ]
    n_entities = await write_extraction_rows(pool, document_id, entity_rows)
    n_relations = await write_extraction_rows(pool, document_id, relation_rows)

    # 5) Mark document as extracted
    await pool.execute(
        "UPDATE documents SET extracted = true WHERE id = $1",
        document_id,
    )

    return {
        "document_id": document_id,
        "entities": n_entities,
        "relations": n_relations,
        "llm_fallback_calls": len(llm_calls),
        "llm_fallback_accepted": len(extra_relations),
        "llm_used": bool(llm_calls),
    }
