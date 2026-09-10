# TRACE Setup Prompt

Use this document when moving TRACE to another computer, workspace, or coding assistant.

## Project

TRACE is a single FastAPI + React investigative network-analysis application.

Architecture:

- React 19, Vite, Tailwind, Cytoscape.js, and nginx frontend
- FastAPI backend with JWT authentication and role-based access control
- PostgreSQL as the source of truth for users, cases, documents, audit logs, extraction provenance, and entity merges
- Neo4j as the derived knowledge-graph store
- spaCy, regex extraction, RapidFuzz, NetworkX, PyPDF2, and optional OpenAI-compatible LLM calls
- Docker Compose for local deployment

Do not introduce Express, a second backend service, GNNs, autonomous culpability scoring, or freeform Text-to-Cypher.

## Prerequisites

Install the following before running the project:

- Docker Desktop with Docker Compose
- Git
- At least 6 GB available memory for PostgreSQL, Neo4j, the API, and the frontend
- Optional: Node.js 20+ and npm if building the frontend outside Docker
- Optional: Python 3.11+ if running backend modules outside Docker

## Clone

Replace the placeholder URL with the actual repository URL:

```bash
git clone <TRACE_REPOSITORY_URL> trace
cd trace
```

The repository intentionally excludes local secrets in `infra/.env`. Create it from the template:

```bash
cp infra/.env.example infra/.env
```

On Windows PowerShell:

```powershell
Copy-Item infra/.env.example infra/.env
```

For a local demo, the values in `.env.example` are sufficient. Change all passwords and JWT secrets before any shared or production deployment.

## Start the Full Stack

Run from the `infra` directory:

```bash
cd infra
docker compose up -d --build
```

Windows PowerShell:

```powershell
Set-Location infra
docker compose up -d --build
```

Services:

- Frontend: http://localhost:5173
- API: http://localhost:8000
- API health: http://localhost:8000/api/health
- Neo4j Browser: http://localhost:7474
- PostgreSQL: localhost:5432
- Neo4j Bolt: localhost:7687

The first startup performs the following:

1. Starts PostgreSQL.
2. Applies `db/postgres/migrations/001_init.sql` through the PostgreSQL image.
3. Applies migrations 002-004 through the API migration runner.
4. Seeds the demo accounts and Operation Nexus case.
5. Starts Neo4j and applies constraints.
6. Runs the `neo4j-init` one-shot service.
7. Builds and serves the React frontend through nginx.

Check service status:

```bash
docker compose ps
```

Check logs:

```bash
docker compose logs -f api
docker compose logs neo4j-init
```

Stop the stack:

```bash
docker compose down
```

For a completely fresh local database, remove the development volumes. This deletes local data:

```bash
docker compose down -v
```

## Demo Accounts

The local demo accounts are:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@trace.dev` | `TraceAdmin123!` |
| Investigator | `investigator@trace.dev` | `TraceInvestigator123!` |

These are development credentials only.

## First Manual Walkthrough

1. Open http://localhost:5173.
2. Sign in as `investigator@trace.dev`.
3. Open the Operation Nexus case or create a new case.
4. Upload TXT, CSV, JSON, or text-based PDF files.
5. Press **Extract** for each document.
6. Press **Find Matches** and review merge suggestions.
7. Accept a merge only when the investigator confirms it.
8. Open **Graph Explorer**.
9. Press **Sync graph**.
10. Click a node to open its evidentiary drawer.
11. Review source snippets, filename, page, paragraph, and extractor details.
12. Open the analysis panel for:
    - Connections Chat
    - Disruption Simulator
    - Priority Score
13. Confirm heuristic links are shown as unconfirmed dashed edges.

## Backend Tests

Run the pure unit tests inside the running API container:

```bash
docker exec trace-api python -m pytest /app/tests_e2e/unit -q
```

Run the authentication and RBAC checks:

```bash
docker exec trace-api python /app/tests_e2e/00_auth_test.py
```

Run ingestion checks:

```bash
docker exec trace-api python /app/tests_e2e/ingestion_test.py
```

Run the full pipeline check:

```bash
docker exec trace-api python /app/tests_e2e/10_pipeline_test.py
```

Run Phase 2 verification:

```bash
docker exec trace-api python /app/tests_e2e/phase2_check.py
```

A successful test command exits with code 0 and prints `PASS` lines. Save the output when reporting verification results.

## Frontend Tests

The Playwright smoke test is at `frontend/tests/smoke.spec.js`.

Install dependencies if needed:

```bash
cd frontend
npm install
npx playwright install chromium
```

Run the frontend build:

```bash
npm run build
```

Run Playwright against the running stack:

```bash
npx playwright test
```

Preserve the generated Playwright report and test artifacts when reporting results.

## Important Runtime Configuration

`infra/.env.example` documents all supported settings:

- PostgreSQL connection values
- Neo4j URI and credentials
- JWT access and refresh secrets
- JWT expiry values
- Optional LLM endpoint, key, and model
- spaCy model name
- Upload directory
- API port and frontend URL
- `TRACE_RESEED_DEMO`

`TRACE_RESEED_DEMO=true` clears and reseeds only the fictional Operation Nexus demo case when `neo4j-init` runs.

Use `TRACE_RESEED_DEMO=false` when preserving existing non-demo Neo4j data. Do not use development credentials in production.

## API Areas

All protected endpoints require:

```text
Authorization: Bearer <access_token>
```

Main route groups:

- `/api/auth`: login, refresh, logout, current user
- `/api/users`: admin user management
- `/api/audit`: admin audit log
- `/api/cases`: cases and assignments
- `/api/cases/{id}/documents`: upload and document metadata
- `/api/cases/{id}/documents/{document_id}/extract`: NLP extraction
- `/api/cases/{id}/resolution`: merge suggestions, accept, undo
- `/api/cases/{id}/graph`: graph sync, graph reads, provenance detail
- `/api/cases/{id}/analysis`: structure and removal simulation
- `/api/cases/{id}/heuristic-links`: unconfirmed heuristic leads
- `/api/cases/{id}/priority-scores`: structural priority scores
- `/api/cases/{id}/chat`: scoped SSE connection chat

## If You Are a Coding Assistant

Before changing code:

1. Read `README.md`, `BUILD_AUDIT.md`, and `NOT_VERIFIED.md`.
2. Inspect the current working tree and do not overwrite user changes.
3. Confirm the Docker stack status with `docker compose ps`.
4. Run the narrowest relevant test before and after edits.
5. Preserve PostgreSQL as the source of truth for provenance.
6. Keep graph writes parameterized and deterministic.
7. Never allow an LLM to generate or execute Cypher.
8. Keep heuristic links visibly marked as unconfirmed.
9. Keep priority explanations neutral and structural; do not use guilt, criminality, or culpability language.
10. Do not commit `infra/.env`, uploaded files, generated bundles, dependency directories, or runtime caches.

## Known Limitations

- Scanned/image-only PDFs are rejected because OCR is not included.
- spaCy model installation depends on network access during the API image build; extraction degrades to regex-only mode if unavailable.
- NLP relationship extraction uses sentence-scoped patterns rather than dependency parsing.
- Chat intentionally supports scoped two-entity connection questions only.
- Neo4j graph writes may emit Cartesian-product performance notifications that should be reviewed before production use.
- Passlib/bcrypt may emit a backend-version warning even though authentication works.
- This is a local single-tenant development deployment without backup automation.
- Demo data is fictional.
