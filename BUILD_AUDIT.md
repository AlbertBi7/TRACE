# TRACE Build Audit

## Summary

| Area | Status | Note |
|---|---|---|
| Infra | ⚠️ Unclear | Compose, env, migrations, Neo4j init, frontend Dockerfile, and nginx proxy exist; full stack startup was not run in this audit. |
| Milestone 1: Auth & RBAC | ✅ Done | JWT rotation, roles, case scoping, admin management, audit events, frontend guards, and an auth e2e script exist. |
| Milestone 2: Ingestion | ✅ Done | PDF/TXT/CSV/JSON upload, parsing, raw storage, normalized text, page/paragraph provenance, UI upload, and e2e coverage exist. |
| Milestone 3: NLP Extraction | 🟡 Partial | Regex + spaCy entities, pattern relations, scoped LLM fallback, and provenance persistence exist; relation extraction is not dependency-parser-based and runtime coverage is pending. |
| Milestone 4: Entity Resolution | ✅ Done | RapidFuzz, shared-attribute matching, reviewable merge suggestions, accept, and undo are implemented. |
| Milestone 5: Knowledge Graph | ✅ Done | PostgreSQL-backed canonicalization, provenance-backed Neo4j sync/read APIs, reconciliation, and e2e checks exist. |
| Milestone 6: Graph Explorer | ✅ Done | Cytoscape rendering, layouts, filters, search, and path highlighting are implemented. |
| Milestone 7: Evidentiary Drawer | ✅ Done | Node metadata, aliases, cross-case presence, connections, and file/page/paragraph snippets are implemented. |
| Milestone 8: Disruption Simulator | ✅ Done | Articulation points, before/after components, fragmentation metrics, explanations, and UI simulation exist. |
| Milestone 9: Heuristic Links | ✅ Done | Shared infrastructure, Jaccard/common neighbors, indirect funds flow, dashed unconfirmed edges, and no auto-promotion exist. |
| Milestone 10: Priority Score | ✅ Done | 0–100 structural score combines betweenness, PageRank, recurrence, and neutral explanations. |
| Milestone 11: Scoped Chat | ✅ Done | Deterministic entity matching and fixed Cypher shortest path with SSE, citations, fallback summary, and canvas highlighting exist. |
| README | ✅ Done | README and MIT license cover ethics, architecture, setup, features, API, data model, testing, limitations, and scope. |

## Detailed Findings

### 1. Repository & Infra

- ✅ Expected directories exist: `frontend/`, `services/api/`, `db/postgres/`, `db/neo4j/`, and `infra/`.
- ✅ [`infra/.env`](infra/.env#L1-L39) and [`infra/.env.example`](infra/.env.example#L1-L31) document local configuration.
- ✅ [`infra/docker-compose.yml`](infra/docker-compose.yml#L1-L130) defines PostgreSQL, Neo4j, API, frontend, and `neo4j-init` services.
- ✅ [`frontend/Dockerfile`](frontend/Dockerfile#L1-L18) builds the React app and serves it with nginx.
- ✅ [`frontend/nginx.conf`](frontend/nginx.conf#L1-L29) serves the SPA and proxies `/api/`, including SSE-compatible settings.
- ✅ PostgreSQL initial migration is mounted directly; later migrations run through [`services/api/app/db/migrate.py`](services/api/app/db/migrate.py#L1-L40).
- ✅ Neo4j constraints and seed data are applied by the init service.
- ⚠️ `docker compose config` previously passed, but `docker compose up --build` and health checks were not executed in this audit.
- 🟡 Neo4j init reseeds the demo case and should be tested with persistent volumes before non-demo use.

### 2. Milestone 1: Auth & RBAC

- ✅ Login, JWT access/refresh issuance, refresh rotation, revocation, logout, and `/me` exist in [`services/api/app/auth/router.py`](services/api/app/auth/router.py#L42-L190).
- ✅ `admin` and `investigator` roles are defined in [`services/api/app/auth/models.py`](services/api/app/auth/models.py#L12-L18).
- ✅ Admin user management and password reset exist in [`services/api/app/routers/users.py`](services/api/app/routers/users.py#L17-L211).
- ✅ Admin audit-log listing exists in [`services/api/app/routers/audit.py`](services/api/app/routers/audit.py#L14-L83).
- ✅ Investigator case listing and protected resources use assignment checks in [`services/api/app/auth/dependencies.py`](services/api/app/auth/dependencies.py#L47-L70) and [`services/api/app/routers/cases.py`](services/api/app/routers/cases.py#L17-L48).
- ✅ Assignment now rejects non-investigators, covered by [`00_auth_test.py`](services/api/tests_e2e/00_auth_test.py#L55-L60).
- ✅ Frontend route guards, redirect behavior, token refresh, and logout exist in [`ProtectedRoute.jsx`](frontend/src/components/ProtectedRoute.jsx#L1-L38), [`api.js`](frontend/src/lib/api.js#L24-L106), and [`AuthContext.jsx`](frontend/src/contexts/AuthContext.jsx#L28-L53).
- ✅ Startup demo-account seeding is idempotent in [`services/api/app/main.py`](services/api/app/main.py#L42-L82).
- 🟡 [`db/postgres/seed.sql`](db/postgres/seed.sql#L7-L18) still uses older `.local` demo emails while API startup uses `.dev`; the two seed paths should be normalized.
- 🟡 Auth e2e coverage exists, but this audit did not execute it against a live stack.

### 3. Milestone 2: Multi-Format Ingestion

- ✅ Upload accepts PDF, TXT, CSV, and JSON with a 50 MB limit in [`services/api/app/routers/documents.py`](services/api/app/routers/documents.py#L69-L150).
- ✅ Raw files are stored on disk and normalized content plus parsed pages are stored in PostgreSQL.
- ✅ Parsers normalize all four formats into page/paragraph structures in [`services/api/app/ingestion/parsers.py`](services/api/app/ingestion/parsers.py#L1-L137).
- ✅ Document list/detail routes expose uploader, page count, parsed content, and extraction counts.
- ✅ Frontend click/drag-drop multi-file upload exists in [`CaseDetailPage.jsx`](frontend/src/dashboard/CaseDetailPage.jsx#L72-L166).
- ✅ Ingestion e2e coverage exists in [`ingestion_test.py`](services/api/tests_e2e/ingestion_test.py#L1-L123).
- 🟡 PyPDF2 does not OCR scanned/image-only PDFs.

### 4. Milestone 3: Hybrid NLP Extraction

- ✅ Regex extraction covers PHONE, BANK_ACCOUNT, and VEHICLE in [`entities.py`](services/api/app/nlp/entities.py#L15-L105).
- ✅ spaCy NER covers PERSON, ORG, and LOCATION with regex span exclusion.
- ✅ Relation cues cover CALLED, TRANSFERRED_TO, TRAVELLED_WITH, and ASSOCIATED_WITH in [`relations.py`](services/api/app/nlp/relations.py#L18-L181).
- 🟡 Relationships use sentence-scoped cue patterns, not dependency parsing.
- ✅ Optional LLM fallback is restricted to a single sentence, two candidate entities, fixed labels, JSON output, and confidence threshold in [`llm_fallback.py`](services/api/app/nlp/llm_fallback.py#L1-L72).
- ✅ Extraction routes trigger and report the pipeline in [`services/api/app/routers/extraction.py`](services/api/app/routers/extraction.py#L1-L76).
- ✅ Entity and relation rows store exact snippets, page, paragraph, extractor, confidence, and endpoint IDs through [`pipeline.py`](services/api/app/nlp/pipeline.py#L52-L144) and [`provenance.py`](services/api/app/ingestion/provenance.py#L1-L47).
- 🟡 The full pipeline e2e script exercises extraction, but it was not run in this audit; spaCy model/runtime behavior remains unverified here.

### 5. Milestone 4: Entity Resolution & Alias Linking

- ✅ RapidFuzz token matching and initials matching exist in [`matcher.py`](services/api/app/resolution/matcher.py#L1-L70).
- ✅ Exact shared phone/account/vehicle co-occurrence and relation-derived matching exist in [`matcher.py`](services/api/app/resolution/matcher.py#L75-L171).
- ✅ Suggestions persist with method, confidence, rationale-related data, and status through [`004_resolution.sql`](db/postgres/migrations/004_resolution.sql#L1-L25).
- ✅ Accept and undo routes are implemented in [`resolution.py`](services/api/app/routers/resolution.py#L1-L117).
- ✅ The pipeline e2e script checks suggestion, persistence, acceptance, and canonical graph behavior in [`10_pipeline_test.py`](services/api/tests_e2e/10_pipeline_test.py#L76-L111).

### 6. Milestone 5: Unified Knowledge Graph

- ✅ Graph sync derives nodes and relations from PostgreSQL `extraction_log` in [`services/api/app/graph/service.py`](services/api/app/graph/service.py#L1-L230).
- ✅ Accepted merges are canonicalized with union-find; writes are idempotent Neo4j `MERGE` operations.
- ✅ Nodes and edges carry real extraction provenance IDs, case IDs, aliases, and observations.
- ✅ Stale node/edge membership is reconciled against PostgreSQL source data.
- ✅ Graph sync/read/node-detail routes exist in [`services/api/app/routers/graph.py`](services/api/app/routers/graph.py#L1-L180).
- ✅ The pipeline e2e test checks graph writes, reads, provenance, and canonical nodes.
- 🟡 Full Neo4j behavior still depends on running the Compose stack.

### 7. Milestone 6: Interactive Graph Explorer

- ✅ Cytoscape is instantiated and updated in [`GraphExplorer.jsx`](frontend/src/dashboard/GraphExplorer.jsx#L1-L286).
- ✅ Entity type colors, confirmed relation edges, heuristic dashed edges, search, type filters, and `cose`/`breadthfirst` layout controls exist.
- ✅ Deterministic BFS path highlighting and chat-path highlighting exist.
- ✅ Graph sync, graph loading, articulation-point loading, and analysis-panel integration exist.
- ✅ Frontend production build previously passed through the corrected [`frontend/index.html`](frontend/index.html#L1-L10) entrypoint.

### 8. Milestone 7: Node Detail & Evidentiary Traceability

- ✅ Node click opens [`NodeDrawer.jsx`](frontend/src/dashboard/NodeDrawer.jsx#L1-L150).
- ✅ Drawer shows normalized metadata, entity type, aliases, case count, cross-case flag, and connected edges.
- ✅ Backend node detail resolves real `extraction_log` snippets with filename, page, paragraph, extractor, confidence, and provenance ID in [`graph.py`](services/api/app/routers/graph.py#L93-L180).

### 9. Milestone 8: Network Disruption Simulator

- ✅ NetworkX articulation points and connected-component metrics exist in [`analysis.py`](services/api/app/graph/analysis.py#L1-L119).
- ✅ Before/after component count, largest-component share, isolated nodes, fragmented nodes, and explanations are returned.
- ✅ API routes exist in [`analysis.py`](services/api/app/routers/analysis.py#L29-L44).
- ✅ UI simulation and fragmented-node highlighting exist in [`AnalysisPanel.jsx`](frontend/src/dashboard/AnalysisPanel.jsx#L150-L254) and [`GraphExplorer.jsx`](frontend/src/dashboard/GraphExplorer.jsx#L286-L320).

### 10. Milestone 9: Heuristic Link Discovery

- ✅ Shared infrastructure, common-neighbor/Jaccard, and indirect funds-flow heuristics exist in [`heuristics.py`](services/api/app/graph/heuristics.py#L1-L125).
- ✅ Leads are excluded when a confirmed edge already exists and are returned as suggestions only.
- ✅ API route exists in [`services/api/app/routers/analysis.py`](services/api/app/routers/analysis.py#L15-L20).
- ✅ Frontend renders heuristic edges as dashed amber `Heuristic Lead — Unconfirmed` edges in [`GraphExplorer.jsx`](frontend/src/dashboard/GraphExplorer.jsx#L89-L118).
- ✅ No auto-promotion path was found.

### 11. Milestone 10: Explainable Investigation Priority Score

- ✅ Composite 0–100 score combines betweenness, PageRank, and cross-case recurrence in [`priority.py`](services/api/app/graph/priority.py#L1-L107).
- ✅ Every score includes component values, articulation status, and neutral bullet explanations.
- ✅ API route and frontend priority tab exist in [`services/api/app/routers/analysis.py`](services/api/app/routers/analysis.py#L22-L27) and [`AnalysisPanel.jsx`](frontend/src/dashboard/AnalysisPanel.jsx#L257-L302).
- ✅ No guilt or culpability score was found.
- 🟡 Cross-case recurrence is represented as a binary contribution after the first additional case, rather than a continuously scaled count.

### 12. Milestone 11: Scoped NL Connection Chat

- ✅ Entity candidates are extracted deterministically from quoted/capitalized/identifier-like terms and matched against graph names/aliases in [`chat.py`](services/api/app/routers/chat.py#L25-L77).
- ✅ The path query is fixed Cypher with parameterized entity IDs and a four-hop bound in [`chat.py`](services/api/app/routers/chat.py#L80-L94).
- ✅ LLM use is limited to summarizing retrieved path facts and snippets; it never generates Cypher.
- ✅ Deterministic summary fallback works without an LLM; responses stream over SSE in [`chat.py`](services/api/app/routers/chat.py#L180-L287).
- ✅ Chat citations come from PostgreSQL provenance rows.
- ✅ Frontend chat, citations, and path highlighting exist in [`AnalysisPanel.jsx`](frontend/src/dashboard/AnalysisPanel.jsx#L1-L149) and [`GraphExplorer.jsx`](frontend/src/dashboard/GraphExplorer.jsx#L286-L320).
- ✅ The pipeline e2e script covers path found, citations, same-entity handling, and insufficient-entity errors.

### 13. README

- ✅ [`README.md`](README.md#L1-L150) covers pitch/ethics, architecture, stack, local setup, feature status, API overview, data model, testing, limitations, out-of-scope items, and license.
- ✅ [`LICENSE`](LICENSE#L1-L22) contains an MIT license.

### 14. Hard Constraints

- ✅ No GNN library or model was found.
- ✅ No autonomous guilt/culpability scoring exists; priority is explicitly structural and neutral.
- ✅ No freeform Text-to-Cypher or open-ended Graph-RAG exists; chat uses fixed Cypher.
- ✅ Graph nodes, edges, drawer evidence, and chat citations trace back to PostgreSQL `extraction_log` IDs.
- 🟡 Runtime confirmation still requires executing the full stack and e2e scripts.

## Validation Performed

- ✅ Repository inspection confirmed the new resolution, graph, analysis, chat, frontend, README, and license files.
- ✅ Backend compilation passed previously with `python -m compileall -q app`.
- ✅ Frontend production build passed previously with `npm run build`.
- ✅ Compose configuration rendered previously with `docker compose config`.
- ✅ Direct TXT, CSV, and JSON parser smoke checks passed previously.
- ⚠️ Full `docker compose up --build` and the three live e2e scripts were not run in this audit.

## Broken/Risky Items

- Full-stack runtime and Neo4j/PostgreSQL integration are not currently verified in this audit, despite extensive e2e coverage being present.
- `db/postgres/seed.sql` uses `.local` credentials while API startup and tests use `.dev` credentials.
- `neo4j-init` reseeds demo data and should be isolated from production/persistent deployments.
- NLP relations are pattern-based rather than dependency-parsed and may over-generate relations in ambiguous sentences.
- spaCy model download makes API image builds network-dependent; regex-only degradation may reduce entity coverage.
- PyPDF2 does not OCR scanned documents.
- Graph priority recurrence uses a binary cross-case contribution rather than a graded recurrence scale.
- Chat candidate extraction is deliberately narrow and may reject natural-language questions that do not expose two exact graph names or aliases.
- No browser-level automated UI test was found.

## Recommended Next Steps

1. Run `docker compose up --build` from `infra/` with fresh volumes, then execute `00_auth_test.py`, `ingestion_test.py`, and `10_pipeline_test.py`.
2. Fix the `.local` versus `.dev` seed credential mismatch.
3. Add focused unit tests for NLP relation precision, graph reconciliation, heuristic suppression, and chat candidate matching.
4. Add browser-level tests for upload, extraction, merge review, graph sync, drawer, simulation, and chat highlighting.
5. Decide whether priority recurrence should remain binary or use a graded multi-case scale.
6. Keep graph sync, heuristic, priority, and chat results provenance-backed when extending the product.
