# TRACE: Not Fixed or Not Verified

## Not Fully Fixed

- Neo4j Cartesian-product performance warnings remain.
- Passlib/bcrypt compatibility warning remains.
- NLP relationship extraction is pattern-based rather than dependency-parser-based.
- OCR for scanned PDFs is unsupported.
- Chat matching remains limited to recognizable names, aliases, and identifiers.
- No browser-level test result or Playwright report is available.
- No Git repository history or commit exists.
- Priority recurrence is graded and capped rather than fully proportional indefinitely.

## Implemented but Not Verified End-to-End

- Full `docker compose up --build` from clean volumes.
- Final pass/fail results for `00_auth_test.py`.
- Final pass/fail results for `ingestion_test.py`.
- Final pass/fail results for `10_pipeline_test.py`.
- Final pass/fail result for `phase2_check.py`.
- Complete Playwright smoke test.
- Full frontend interaction flow in a browser.
- spaCy model download and runtime NER behavior.
- Repeated Neo4j reseeding with persistent data.
- Production-scale graph synchronization and reconciliation.
- LLM fallback behavior with a real configured LLM.
- SSE chat content and citation assertions.
- UI graph highlighting, node drawer, simulation, and merge-review assertions.

## Evidence Gaps

- No saved test output files.
- No Playwright report, screenshots, or traces.
- No saved Phase 2 stdout.
- No saved output for the three original e2e scripts.
- No commit hash or Git diff history.

## Recommended Verification Order

1. Run and save the output of `00_auth_test.py`.
2. Run and save the output of `ingestion_test.py`.
3. Run and save the output of `10_pipeline_test.py`.
4. Run and save the output of `phase2_check.py`.
5. Run the Playwright smoke suite and preserve its report.
6. Review the Neo4j Cartesian-product and Passlib/bcrypt warnings.
