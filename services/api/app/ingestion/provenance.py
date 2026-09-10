"""
TRACE — Provenance Writer
Single helper for writing extraction_log rows (the provenance backbone).
Every downstream feature (entity resolution, graph writes, evidentiary
drawer, chat citations) traces back through these rows.
"""


async def write_extraction_rows(pool, document_id: str, rows: list[dict]) -> int:
    """
    Batch-insert extraction_log provenance rows. Each row must carry:
      entity_or_edge_id, entity_type, snippet, page, paragraph, extractor, confidence
    Optional:
      value (surface form / readable summary),
      head_entity_id + tail_entity_id (relation rows)
    """
    rows = [r for r in rows if r.get("snippet")]
    if not rows:
        return 0
    await pool.executemany(
        """INSERT INTO extraction_log
               (document_id, entity_or_edge_id, entity_type, value, snippet,
                page, paragraph, extractor, confidence, head_entity_id, tail_entity_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
        [
            (
                document_id,
                r["entity_or_edge_id"],
                r.get("entity_type", ""),
                r.get("value", ""),
                r["snippet"],
                int(r.get("page", 0)),
                int(r.get("paragraph", 0)),
                r.get("extractor", "unknown"),
                float(r.get("confidence", 0.0)),
                r.get("head_entity_id", ""),
                r.get("tail_entity_id", ""),
            )
            for r in rows
        ],
    )
    return len(rows)
