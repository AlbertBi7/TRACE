-- TRACE Migration 006 — Explicit procedural legal roles (human-stated only)
-- Stores role like suspect/accused/victim/witness/complainant as metadata on PERSON entities.
-- No autonomous inference; role is extracted only when explicitly stated in source text.

ALTER TABLE extraction_log
    ADD COLUMN IF NOT EXISTS procedural_role VARCHAR(50) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_extraction_log_role ON extraction_log(procedural_role);
