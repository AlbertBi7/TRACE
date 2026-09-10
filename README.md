# TRACE — AI-Powered Network Analysis for Investigative Teams

TRACE is an explainable investigative co-pilot: it ingests case documents, extracts
entities and relationships with traceable provenance, builds a knowledge graph, and
surfaces structural insight — **it surfaces evidence and structure; humans decide.**

> **Ethics & scope.** TRACE performs *network structure analysis only*. It contains no
> GNNs, no autonomous culpability or guilt classification, no arrest/action
> recommendations, and no predictive risk scores aimed at individuals. Heuristic leads
> are always labeled *unconfirmed*, priority scores describe graph topology (never
> persons), and every node, edge, and answer cites its source document. The chat
> feature answers only "how is X connected to Y" via a fixed, deterministic graph
> query — the LLM never writes or executes Cypher. All bundled demo data is fictional.

## Feature Summary

| Milestone | Feature | Status |
|---|---|---|
| 1 | Auth & RBAC — JWT access/refresh rotation, admin/investigator, case scoping, audit log | ✅ |
| 2 | Ingestion — PDF/TXT/CSV/JSON upload with paragraph-anchored parsing | ✅ |
| 3 | NLP extraction — regex + spaCy NER, pattern relations, scoped LLM fallback | ✅ |
| 4 | Entity resolution — RapidFuzz + shared-attribute matching, reviewable/undoable merges | ✅ |
| 5 | Knowledge graph — provenance-backed Neo4j writes, canonicalization, read APIs | ✅ |
| 6 | Graph Explorer — Cytoscape.js, layouts, filters, search, multi-hop path highlight | ✅ |
| 7 | Evidentiary drawer — aliases, cross-case flags, verbatim file/page/¶ snippets | ✅ |
| 8 | Disruption simulator — articulation points, before/after fragmentation metrics | ✅ |
| 9 | Heuristic links — shared-infra / Jaccard / funds-flow, dashed *unconfirmed* edges | ✅ |
| 10 | Priority score — betweenness + PageRank + cross-case recurrence, with explanations | ✅ |
| 11 | Scoped NL chat — deterministic path → cited, streamed summary (SSE) | ✅ |

## Architecture

```
┌───────────────────────────── Docker Compose ─────────────────────────────┐
│                                                                          │
│  React + Cytoscape SPA  ──/api──▶  FastAPI (auth, RBAC, NLP, graph)      │
│  (nginx, port 5173)               (uvicorn, port 8000)                   │
│                                        │            │                    │
│                                        ▼            ▼                    │
│                        PostgreSQL 16            Neo4j 5 (graph store)    │
│                        (source of truth,        entities + LINKED edges  │
│                         audit, provenance)      with provenance ids      │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Single FastAPI backend** — auth/RBAC, case & user management, ingestion, NLP,
  graph algorithms, optional LLM calls. No microservices.
- **PostgreSQL is the source of truth** — users, cases, documents, `extraction_log`
  (provenance), `entity_merges`, audit trail. Neo4j is a derived, rebuildable index;
  graph sync reconciles stale nodes/edges on every run.
- **Neo4j** stores canonical `Entity` nodes and `LINKED` edges carrying
  `provenance_ids` + `case_ids`. The bundled `seed.cypher` is a dev fixture only.

## Tech Stack

| Layer | Tools |
|---|---|
| Frontend | React 19, Vite, Tailwind v4, Cytoscape.js, lucide-react |
| Backend | FastAPI, asyncpg, neo4j (async driver), spaCy, RapidFuzz, networkx, PyPDF2, httpx, sse-starlette |
| Data | PostgreSQL 16, Neo4j 5.20 |
| Infra | Docker Compose, nginx (SPA + `/api` proxy with SSE passthrough) |

## Local Setup

Requirements: Docker + Docker Compose.

```bash
cd infra
docker compose up -d --build
```

That single command:

1. Starts Postgres, applies `db/postgres/migrations/*.sql` (init + API-side runner),
   and seeds demo accounts + a demo case.
2. Starts Neo4j; a one-shot `neo4j-init` service applies constraints and the demo
   seed graph. The demo seed is idempotent (MERGE-based) and safe on persistent
   volumes; set `TRACE_RESEED_DEMO=false` in `infra/.env` to skip demo data
   entirely and leave existing graph content untouched.
3. Builds and starts the API (migrations + idempotent demo-account seeding on boot)
   and the frontend (Vite build served by nginx, `/api` proxied).

Then open **http://localhost:5173** and sign in:

| Account | Email | Password |
|---|---|---|
| Admin | `admin@trace.dev` | `TraceAdmin123!` |
| Investigator | `investigator@trace.dev` | `TraceInvestigator123!` |

**Optional LLM** (better chat summaries + relation fallback; the system degrades
gracefully without it): set `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL` in
`infra/.env` (OpenAI-compatible endpoint), then `docker compose up -d api`.

## Trying the Full Pipeline

1. Sign in as the investigator → open *Operation Nexus*.
2. Upload `report.txt` / `ledger.csv` / `contacts.json` (drag & drop), press **Extract**.
3. Click **Find Matches** — review suggested entity merges (accept/dismiss, undoable).
4. **Open Graph Explorer** → **Sync graph** — the network is built from real
   extractions with per-node provenance.
5. Click a node for the evidentiary drawer (verbatim snippets with file/page/¶).
6. Use the path tool ("From → To") or the **Analyze** panel:
   - *Connections Chat*: "How is X connected to Y?" — streamed, cited answer.
   - *Disruption Simulator*: pick a ★ articulation point, simulate removal.
   - *Priority Score*: composite structural score with plain-language bullets.

## API Overview

All routes require `Authorization: Bearer <access_token>`; role gates noted.

| Area | Endpoint | Notes |
|---|---|---|
| Auth | `POST /api/auth/login` / `/refresh` / `/logout`, `GET /api/auth/me` | rotation + revocation, all audited |
| Users | `GET/POST /api/users`, `PATCH/DELETE /api/users/{id}`, `POST /{id}/reset-password` | admin |
| Audit | `GET /api/audit` | admin, paginated/filterable |
| Cases | `GET/POST /api/cases`, `GET/PATCH /api/cases/{id}`, `POST /{id}/assign`, `GET /{id}/assignments` | investigator-scoped |
| Documents | `GET/POST /api/cases/{id}/documents`, `GET /…/documents/{doc_id}` | upload ≤50MB, pdf/txt/csv/json |
| Extraction | `POST/GET /api/cases/{id}/documents/{doc_id}/extract` | writes `extraction_log` |
| Resolution | `POST /{id}/resolution/suggest`, `GET /{id}/resolution/merges`, `POST /…/merges/{mid}/accept` / `/undo` | human-in-the-loop |
| Graph | `POST /{id}/graph/sync`, `GET /{id}/graph`, `GET /{id}/graph/nodes/{eid}` | provenance detail |
| Analysis | `GET /{id}/analysis/structure`, `POST /{id}/analysis/simulate-removal/{eid}` | networkx topology |
| Leads | `GET /{id}/heuristic-links` | unconfirmed suggestions only |
| Priority | `GET /{id}/priority-scores` | structural, with explanations |
| Chat | `GET /{id}/chat?q=…` | SSE stream; fixed Cypher, cited |
| System | `GET /api/health` | — |

## Data Model

```
users ──< case_assignments >── cases ──< documents ──< extraction_log
  │                               │                       ▲
  └──< refresh_tokens             └──< entity_merges ─────┘ (accepted merges drive
                                                            graph canonicalization)
audit_log  (every auth event, upload, merge decision, …)

Neo4j:   (:Entity {entity_id, name, aliases, provenance_ids, case_ids})
         (:Entity)-[:LINKED {relation, provenance_ids, case_ids, observations}]->(:Entity)
```

Deterministic IDs: entity ids are SHA-1 hashes of (type, canonical value) — the same
real-world entity extracted from different documents converges on one node;
accepted merges canonicalize aliases; sync is idempotent and reconciles stale data.

## Testing

Against a running stack:

```bash
docker exec trace-api python /app/tests_e2e/00_auth_test.py       # auth/RBAC (13 checks)
docker exec trace-api python /app/tests_e2e/ingestion_test.py     # upload/parse (13 checks)
docker exec trace-api python /app/tests_e2e/10_pipeline_test.py   # end-to-end pipeline (27 checks)
```

The suite covers auth/rotation/revocation, RBAC + case scoping, ingestion →
provenance linkage, extraction correctness, resolution merge/undo, graph write
correctness (incl. provenance ids), disruption simulation, heuristic/priority
endpoints, and the scoped chat (path found, citations present, merged-entity and
two-entity-error paths).

## Known Limitations & Out of Scope

- **No OCR**: scanned/image PDFs are rejected with a clear error at upload (PyPDF2
  extracts text layers only); provide text-based PDFs.
- **spaCy model downloads at image build** (network-dependent build); the build
  continues with a warning if the download fails, and extraction degrades to
  regex-only at runtime when the model is unavailable.
- Upload storage has no retention/collision policy beyond unique names.
- The small NER model misses some entities; the LLM fallback is scoped to relation
  classification only (by design, never freeform).
- Single-tenant demo deployment; no multi-region, no backup automation.
- Chat covers "how is X connected to Y" only — deliberately.
- Demo data is entirely fictional; TRACE ships with no real-world data.

## License

MIT — see [LICENSE](LICENSE).
