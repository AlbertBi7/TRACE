-- TRACE Migration 002 — Ingestion support (Milestone 2, idempotent)
-- Adds paragraph-anchored parsed content storage to documents so every
-- extraction can cite file + page + paragraph provenance.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS parsed_content JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents(uploaded_by);
