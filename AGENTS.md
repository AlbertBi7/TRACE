# AGENTS.md — TRACE

## Snapshot
Single FastAPI + React network-analysis app. PostgreSQL is source of truth (users/cases/docs/`extraction_log`/`entity_merges`/audit/`schema_migrations`); Neo4j is derived rebuildable graph (`:Entity` + `:LINKED`, always with `provenance_ids`+`case_ids`). No microservices, no GNNs.

## Layout
- `services/api/` — FastAPI `app/main.py` (lifespan: pg + neo4j + `migrate.py` + demo seed). Routers: `app/routers/` (`cases`, `documents`, `extraction`, `resolution`, `graph`, `analysis`, `case_network`, `chat`, `audit`, `users`). Core: `app/nlp/` (regex+spaCy+scoped LLM fallback), `app/graph/` (`service.py` sync/canonicalization, `heuristics.py`, `priority.py`, `analysis.py` + `deep.py`), `app/auth/`, `app/db/` (`migrate.py`, `postgres.py`, `neo4j_driver.py`). Mounted at `/app` with `--reload` in compose.
- `frontend/` — React 19 + Vite + Tailwind v4 (`@tailwindcss/vite`) + Cytoscape.js. Docker: `node:20-alpine` build → `nginx:1.27-alpine` (`nginx.conf` proxies `/api/` with SSE passthrough). Dev outside Docker: `vite.config.js` proxies `/api` → `localhost:8000`.
- `db/postgres/migrations/` — `001_init.sql` via Postgres `docker-entrypoint-initdb.d` mount; `002-004` via API `app/db/migrate.py` on boot (tracked in `schema_migrations`). Don't expect 002+ in init volume.
- `db/neo4j/` — `constraints.cypher` (always, idempotent — unique on `Entity.entity_id`) + `seed.cypher` (MERGE demo case `c0000000-...0001`).
- `infra/` — `docker-compose.yml` (executable truth; must run `docker compose` from this dir) + `docker-compose.local.yml` (port overrides `5433`/`7475`/`7688`) + `.env` (gitignored, create from `.env.example`). Services: `trace-postgres:5432`, `trace-neo4j:7474/7687`, `trace-api:8000`, `trace-frontend:5173`, one-shot `trace-neo4j-init` (waits for `neo4j:service_healthy`).
- Handoff docs: `README.md`, `SETUP_PROMPT.md`, `BUILD_AUDIT.md`, `NOT_VERIFIED.md`, `docs/` — read before changing code.

## Setup & Run
```bash
cp infra/.env.example infra/.env   # PowerShell: Copy-Item infra/.env.example infra/.env
cd infra && docker compose up -d --build
docker compose ps                   # wait for postgres/neo4j healthy before neo4j-init completes
docker compose logs -f api          # also: docker compose logs neo4j-init
docker compose down                 # fresh DBs: docker compose down -v  (deletes pg-data/neo4j-data)
```
- Ports (default): frontend `5173`, API `8000` (`/api/health`), Neo4j `7474`/`7687`, Postgres `5432`. Alt via `docker compose -f docker-compose.yml -f docker-compose.local.yml up`.
- Demo creds seeded idempotently on API boot (`app/main.py:50`): `admin@trace.dev` / `TraceAdmin123!`, `investigator@trace.dev` / `TraceInvestigator123!`. `EmailStr` rejects `.local` — use `.dev`.
- `TRACE_RESEED_DEMO` (default `true`): `true` clears & re-MERGEs only demo case `c0000000-...0001`; `false` skips seed and preserves graph (use for persistent data).
- API hot-reloads via volume mount; `db/postgres/migrations` is `ro`. Frontend needs rebuild unless `npm run dev` outside Docker.

## Tests — live stack required (except unit)
```bash
docker exec trace-api python -m pytest /app/tests_e2e/unit -q
docker exec trace-api python -m pytest /app/tests_e2e/unit/test_unit.py::test_transfer_between_accounts -q  # single test
docker exec trace-api python /app/tests_e2e/00_auth_test.py       # 13 checks: JWT rotation/RBAC/case scoping
docker exec trace-api python /app/tests_e2e/ingestion_test.py     # 13 checks: upload/parse provenance
docker exec trace-api python /app/tests_e2e/10_pipeline_test.py   # 27 checks: extraction→resolution→graph→heuristics→chat
docker exec trace-api python /app/tests_e2e/phase2_check.py
python -m compileall -q app                                        # quick syntax check from services/api/
```
Frontend (needs `http://localhost:5173` live):
```bash
cd frontend && npm install && npx playwright install chromium
npm run build                              # Vite build
npx playwright test                        # smoke at frontend/tests/smoke.spec.js — serial: login→case→upload→extract→merge→sync→drawer→chat SSE
```
- Smoke exposes Cytoscape via `window.__traceCy`.
- No lint/typecheck/pre-commit; `requirements-dev.txt` is just `pytest`.

## Gotchas
- `docker compose` must run from `infra/` — compose file uses `../` relative paths.
- Migrations split: `001` via Postgres init; `002-004` via `app/db/migrate.py`. Both idempotent.
- Neo4j healthcheck generous (`start_period:90s`, `timeout:30s`, `retries:30`); `neo4j-init` waits for `service_healthy`. Don't hit API until `ps` shows healthy.
- spaCy model (`SPACY_MODEL=en_core_web_sm`) downloads at image build (`services/api/Dockerfile:18`); offline build warns, runtime degrades to regex-only (`app/nlp/spacy_model.py`).
- Scanned PDFs route to OCR fallback (`tesseract-ocr` eng+hin + `poppler-utils` pdf2image dpi=200) preserving `file/page/paragraph` (`MAX_PARA_CHARS=600`); blank/failed OCR still `422`. Direct image uploads `png/jpg/jpeg` via `parse_image` OCR. Native text PDFs use fast `PyPDF2` path. Upload limit 50 MB (`app/routers/documents.py`, `app/ingestion/parsers.py`).
- Entity IDs deterministic SHA-1 of `(type, canonical value)` (`app/graph/service.py:_global_entity_id`); merges use union-find with lexicographic root (`build_canonicalization`), longest-alias wins for display.
- Graph sync (`POST /api/cases/{id}/graph/sync`) is idempotent, global read + case-scoped reconciliation; rerun after merges. Neo4j `:Entity` unique on `entity_id` (not per-type labels).
- Uploads: raw files on disk volume (`/uploads` as `caseId_docId_filename`), normalized `extracted_text` + `parsed_content` (pages→paragraphs) in Postgres for provenance.
- Do not commit: `infra/.env`, `uploads/`, `frontend/dist/`, `frontend/node_modules/`, `__pycache__/`, `.pytest_cache/` (gitignored).

## Guardrails — do not violate
- No GNNs, no autonomous guilt/culpability/arrest/risk scores, no freeform Text-to-Cypher (`BUILD_AUDIT.md:14`).
- Chat: fixed parameterized Cypher, `MAX_HOPS=4` (`app/routers/chat.py:27`), LLM only summarizes retrieved path facts — never generates Cypher. Matching via `_extract_candidates`/`_match_nodes`, `FUZZY_THRESHOLD=90` fail-closed.
- Heuristics (`app/graph/heuristics.py`) amber dashed `unconfirmed` edges, suppressed when confirmed edge exists, never promoted.
- Priority (`app/graph/priority.py`) 0–100 structural only (betweenness+PageRank+recurrence capped at `RECURRENCE_CAP`); explanations neutral — no `criminal`/`guilt`/`arrest`.
- Every node/edge/drawer snippet/chat citation must trace to `extraction_log` `provenance_ids` + `case_ids` (file/page/¶).

## Workflow
- Before edits: read `README.md` + `SETUP_PROMPT.md` + `BUILD_AUDIT.md`/`NOT_VERIFIED.md`; `docker compose ps`; run narrowest relevant test before/after.
- Keep `frontend/nginx.conf` SSE flags (`proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 3600s`) and Vite proxy for chat streaming.
- Keep Cypher parameterized, deterministic; Postgres stays source of truth.
