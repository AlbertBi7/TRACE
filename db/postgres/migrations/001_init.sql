-- TRACE PostgreSQL Schema — Milestone 1 (idempotent)
-- Safe to re-run: uses IF NOT EXISTS / DO blocks everywhere.
-- Applied by the postgres initdb entrypoint AND by the API startup migrator.

-- ─── Extensions ──────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Enum Types ──────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'investigator');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE case_status AS ENUM ('open', 'closed', 'archived');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ─── Users ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name   VARCHAR(255) NOT NULL DEFAULT '',
    role        user_role NOT NULL DEFAULT 'investigator',
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ─── Cases ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cases (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(500) NOT NULL,
    description TEXT DEFAULT '',
    created_by  UUID NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status      case_status NOT NULL DEFAULT 'open'
);

CREATE INDEX IF NOT EXISTS idx_cases_created_by ON cases(created_by);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);

-- ─── Case Assignments ────────────────────────────────────
CREATE TABLE IF NOT EXISTS case_assignments (
    case_id     UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (case_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_case_assignments_user ON case_assignments(user_id);

-- ─── Documents ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id       UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    filename      VARCHAR(500) NOT NULL,
    filetype      VARCHAR(50) NOT NULL,
    uploaded_by   UUID NOT NULL REFERENCES users(id),
    uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    storage_path  VARCHAR(1000) NOT NULL,
    extracted_text TEXT DEFAULT '',
    page_count    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_documents_case ON documents(case_id);

-- ─── Extraction Log (Provenance) ─────────────────────────
CREATE TABLE IF NOT EXISTS extraction_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_or_edge_id VARCHAR(255) NOT NULL,
    entity_type     VARCHAR(100) DEFAULT '',
    snippet         TEXT NOT NULL,
    page            INTEGER DEFAULT 0,
    paragraph       INTEGER DEFAULT 0,
    extractor       VARCHAR(100) NOT NULL,
    confidence      REAL DEFAULT 0.0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extraction_log_document ON extraction_log(document_id);
CREATE INDEX IF NOT EXISTS idx_extraction_log_entity ON extraction_log(entity_or_edge_id);

-- ─── Audit Log ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES users(id),
    action      VARCHAR(255) NOT NULL,
    target_type VARCHAR(100) DEFAULT '',
    target_id   VARCHAR(255) DEFAULT '',
    metadata    JSONB DEFAULT '{}',
    ip_address  VARCHAR(45) DEFAULT '',
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);

-- ─── Refresh Tokens ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked     BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
