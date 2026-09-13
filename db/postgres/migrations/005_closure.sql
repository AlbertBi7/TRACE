-- TRACE Migration 005 — Case Closure (human culprit & charges, Milestone 11+)
-- Stores human-finalized closure attestation; no autonomous scoring.
-- All fields nullable to keep existing cases open; set only when investigator closes.

ALTER TABLE cases
    ADD COLUMN IF NOT EXISTS culprit_entity_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS charges JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS closure_notes TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS closed_by UUID REFERENCES users(id);

CREATE INDEX IF NOT EXISTS idx_cases_closed_by ON cases(closed_by);
