# AGENTS.md — TRACE

## Project Snapshot
Single FastAPI + React investigative network-analysis app. PostgreSQL is source of truth (users/cases/docs/`extraction_log`/`entity_merges`/audit); Neo4j is a derived, rebuildable graph index. No microservices.

## Layout
- `services/api/` — FastAPI backend (`app/main.py` lifespan, `app/routers/`, `app/nlp/`, `app/graph/`, `app/auth/`, `app/db/migrate.py`). Mounted at `/app` in compose with `--reload`.
- `frontend/` — React 19 + Vite + Tailwind v4 (`@tailwindcss/vite` plugin) + Cytoscape.js. Built via `node:20-alpine` → `nginx:1.27-alpine` (`nginx.conf` proxies `/api/` with SSE passthrough).
- `db/postgres/migrations/` — `001_init.sql` via Postgres `docker-entrypoint-initdb.d`; `002-004` via API `migrate.py` + `schema_migrations` table.
- `db/neo4j/` — `constraints.cypher` (always) + `seed.cypher` (MERGE-based demo fixture).
- `infra/` — `docker-compose.yml` + `.env` (gitignored; create from `.env.example`). Services: `trace-postgres:5432`, `trace-neo4j:7474/7687`, `trace-api:8000`, `trace-frontend:5173`, one-shot `trace-neo4j-init`.
- `docs/`, `BUILD_AUDIT.md`, `SETUP_PROMPT.md`, `NOT_VERIFIED.md` — handoff docs; read before changing code.

## Setup & Run (executable truth: `infra/docker-compose.yml`)
```bash
cp infra/.env.example infra/.env   # PowerShell: Copy-Item infra/.env.example infra/.env
cd infra && docker compose up -d --build
docker compose ps
docker compose logs -f api          # also: docker compose logs neo4j-init
docker compose down                 # fresh DBs: docker compose down -v  (deletes pg-data/neo4j-data)
```
- Ports: frontend `5173`, API `8000` (`/api/health`), Neo4j browser `7474`, Bolt `7687`, Postgres `5432`.
- Demo creds (seeded idempotently on API boot, `app/main.py:42`): `admin@trace.dev` / `TraceAdmin123!`, `investigator@trace.dev` / `TraceInvestigator123!`. Pydantic `EmailStr` rejects `.local` — use `.dev`.
- `TRACE_RESEED_DEMO` in `infra/.env` (default `true`): `true` clears & re-MERGEs demo case `c0000000-…0001`; `false` skips demo seed and preserves existing graph (use for persistent/non-demo data).
- API hot-reload via volume mount; `db/postgres/migrations` is `ro`. Frontend needs rebuild unless running `npm run dev` outside Docker.

## Tests — run inside `trace-api` container against a live stack
```bash
docker exec trace-api python -m pytest /app/tests_e2e/unit -q
docker exec trace-api python -m pytest /app/tests_e2e/unit/test_unit.py::test_transfer_between_accounts -q  # single test
docker exec trace-api python /app/tests_e2e/00_auth_test.py       # 13 checks: JWT rotation/RBAC/case scoping
docker exec trace-api python /app/tests_e2e/ingestion_test.py     # 13 checks: upload/parse provenance
docker exec trace-api python /app/tests_e2e/10_pipeline_test.py   # 27 checks: extraction→resolution→graph→heuristics→chat
docker exec trace-api python /app/tests_e2e/phase2_check.py
python -m compileall -q app                                        # quick backend syntax check
```
Frontend (requires live stack on `http://localhost:5173`):
```bash
cd frontend && npm install && npx playwright install chromium
npm run build                              # Vite production build
npx playwright test                        # smoke at tests/smoke.spec.js — serial flow: login→case→upload→extract→merge→graph sync→drawer→chat SSE
```
- Smoke exposes Cytoscape via `window.__traceCy` for canvas assertions.
- No lint/typecheck/pre-commit config in repo; `requirements-dev.txt` is just `pytest`.

## Quirks & Gotchas
- **Migrations split**: don't expect `002-004` in Postgres init volume — they run via `app/db/migrate.py` on boot.
- **Neo4j healthcheck** is generous (`start_period: 90s`, `timeout: 30s`); wait for `service_healthy` before expecting `neo4j-init` to finish.
- **spaCy** model (`SPACY_MODEL`, default `en_core_web_sm`) downloads at image build; if offline, build warns and API degrades to regex-only extraction at runtime (`app/nlp/spacy_model.py`). Network-dependent build.
- **PyPDF2 has no OCR** — scanned PDFs are rejected; provide text-layer PDFs.
- **Entity IDs** are SHA-1 of `(type, canonical value)` — same entity across docs converges; merges use union-find (`app/graph/service.py:build_canonicalization`) with lexicographic root.
- **Graph sync** is idempotent, reconciles stale nodes/edges; rerun `POST /api/cases/{id}/graph/sync` after merges.
- **Do not commit**: `infra/.env`, `uploads/`, `frontend/dist/`, `frontend/node_modules/`, `__pycache__/`, `.pytest_cache/` (all gitignored).

## Product Guardrails — do not violate
- No GNNs, no autonomous guilt/culpability/arrest/risk scores, no freeform Text-to-Cypher. Confirmed by `BUILD_AUDIT.md:14`.
- Chat: fixed parameterized Cypher, 4-hop bound (`app/routers/chat.py:80`), LLM only summarizes retrieved path facts — never generates Cypher. Entity matching via `_extract_candidates`/`_match_nodes` with `FUZZY_THRESHOLD` 80–95.
- Heuristic leads (`app/graph/heuristics.py`) are suggestions only — amber dashed edges, suppressed when confirmed edge exists, never marked `confirmed`.
- Priority score (`app/graph/priority.py`) is 0–100 structural (betweenness + PageRank + recurrence capped at `RECURRENCE_CAP`); explanations must stay neutral — no `criminal`/`guilt`/`arrest` wording.
- Every node/edge/drawer snippet/chat citation must trace to `extraction_log` provenance IDs (`provenance_ids`, `case_ids`, file/page/¶).

## Workflow
- Before edits: read `README.md` + `SETUP_PROMPT.md` + `BUILD_AUDIT.md`/`NOT_VERIFIED.md`; check `docker compose ps`; run narrowest relevant test before/after.
- Keep `nginx.conf` SSE flags (`proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 3600s`) for chat streaming.
