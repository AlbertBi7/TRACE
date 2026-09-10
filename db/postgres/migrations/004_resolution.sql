-- TRACE Migration 004 — Entity Resolution (Milestone 4, idempotent)
-- Merge decisions are REVIEWABLE and UNDOABLE: rows are suggestions until an
-- investigator accepts them; undo restores status without deleting history.

CREATE TABLE IF NOT EXISTS entity_merges (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id           UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    primary_entity_id VARCHAR(255) NOT NULL,   -- canonical entity_or_edge_id
    merged_entity_id  VARCHAR(255) NOT NULL,   -- alias folded into canonical
    method            VARCHAR(50) NOT NULL,    -- fuzzy | shared_attribute | manual
    confidence        REAL NOT NULL DEFAULT 0.0,
    status            VARCHAR(20) NOT NULL DEFAULT 'suggested',  -- suggested | accepted | undone
    suggested_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_by        UUID REFERENCES users(id),
    decided_at        TIMESTAMPTZ,
    UNIQUE (case_id, primary_entity_id, merged_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_merges_case ON entity_merges(case_id);
CREATE INDEX IF NOT EXISTS idx_entity_merges_status ON entity_merges(status);
