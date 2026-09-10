-- TRACE Migration 003 — Extraction support (Milestone 3, idempotent)
-- - documents.extracted: marks completed NLP extraction
-- - extraction_log.value: the extracted surface form (entity value or
--   human-readable relation summary) so downstream phases can reconstruct
--   entities without re-parsing snippets
-- - extraction_log.head_entity_id / tail_entity_id: resolved endpoint ids for
--   relation rows (empty for entity rows)

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS extracted BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_documents_extracted ON documents(extracted);

ALTER TABLE extraction_log
    ADD COLUMN IF NOT EXISTS value TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS head_entity_id VARCHAR(255) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS tail_entity_id VARCHAR(255) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_extraction_log_value ON extraction_log(value);
