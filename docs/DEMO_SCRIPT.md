# TRACE Demo Script

This script uses the fictional Operation Nexus training case. It assumes the stack is running at `http://localhost:5173` and that the demo accounts are available from `README.md`.

## 1. Sign in

1. Open `http://localhost:5173`.
2. Enter `investigator@trace.dev`.
3. Enter `TraceInvestigator123!` and click **Sign In**.
4. Open **Operation Nexus**.

Talking point: TRACE keeps the investigator in control. Authentication, case scope, and every consequential action are recorded so the evidence trail is reviewable.

For the admin view, sign out and repeat with `admin@trace.dev` / `TraceAdmin123!`. Open **Audit Log** to show that login and case actions are captured. Return to the investigator account for the investigation walkthrough.

## 2. Upload the source documents

1. In the case page, drag `docs/demo-fixtures/report.txt`, `docs/demo-fixtures/ledger.csv`, and `docs/demo-fixtures/contacts.json` into the upload area.
2. Wait for each file to appear in the document list.
3. Click **Extract** on each document and wait for the status to change to **Extracted**.

Talking point: TRACE preserves the original document and anchors extracted entities and links to the source paragraph. Extraction creates leads for review; it does not turn an automated guess into a fact.

## 3. Review entity matches

1. Click **Find Matches**.
2. Review the suggested aliases and shared-attribute matches.
3. Select **Same entity** for one clearly supported duplicate.
4. Click **Undo** on that accepted merge and confirm it returns to the review state.
5. Accept the same merge again only after reviewing the evidence.

Talking point: entity resolution is deliberately human-in-the-loop. The investigator can accept, dismiss, and undo a proposed merge before it affects graph canonicalization.

## 4. Sync and explore the graph

1. Click **Open Graph Explorer**.
2. Click **Sync graph** and wait for the node and link counts to update.
3. Use the type filters and the search field to locate `Rohan Mehra`, `Nexus Trading Corp`, and `SBI-XXXX-7832`.
4. Confirm that heuristic links appear as dashed amber edges labeled **Heuristic Lead - Unconfirmed**.

Talking point: the graph is a derived, rebuildable view of extracted evidence. Confirmed relationships and unconfirmed heuristic leads are visually distinct so a lead cannot masquerade as a fact.

## 5. Open source evidence

1. Click the `Rohan Mehra` node.
2. In the evidentiary drawer, open **Source evidence**.
3. Point out the verbatim snippet, filename, page, paragraph marker, confidence, and extractor.
4. Repeat on a connected account or organization node if useful.

Talking point: every graph item can be traced back to a concrete source location. The drawer is the credibility check: the audience can inspect what the system actually saw rather than trusting an opaque label.

## 6. Ask the scoped Connections Chat

1. Click **Analyze**, then select **Connections Chat**.
2. Ask: `How is Rohan Mehra connected to SBI-XXXX-7832?`
3. Wait for the streamed response.
4. Point out the highlighted path and the cited source snippets.
5. Optionally ask `How is Rohan Mehra connected to Priya Sharma?` to show another deterministic path.

Talking point: chat is intentionally narrow. It answers how two known entities are connected using a fixed graph query, streams a grounded summary, and cites the underlying evidence. It does not generate guilt findings, recommendations, or arbitrary database queries.

## 7. Run the disruption simulation

1. In **Disruption Simulator**, choose the person or organization marked with a star and **articulation point**.
2. Click **Simulate**.
3. Compare the before and after component counts, largest-group share, and disconnected nodes.
4. Point to the highlighted nodes on the canvas.

Talking point: this is a structural what-if, not a judgment about a person. Removing an articulation point reveals how dependent the observed network is on a particular bridge and makes the topology legible to an investigator.

## 8. Show Priority Score

1. Select **Priority Score**.
2. Expand the top-ranked result.
3. Read the explanation bullets, especially the betweenness, connectivity, and other topology factors.
4. Confirm the disclaimer that the score is not an assessment of a person.

Talking point: the same structural bridge should surface here as a high-priority node, corroborating the disruption view. Priority describes graph topology only; humans decide what evidence means.

## 9. Close with the audit trail

1. Sign out and sign in as `admin@trace.dev`.
2. Open **Audit Log**.
3. Filter or scan for login, document, extraction, merge, graph, analysis, and chat actions performed during the walkthrough.

Talking point: TRACE leaves an operational record of the investigation workflow. That supports accountability and makes the live demonstration itself auditable.

## Demo guardrails

- Keep all data fictional and use the bundled Operation Nexus case.
- Describe heuristic links as unconfirmed leads at all times.
- Describe priority and disruption results as graph topology, never as guilt, danger, or recommended action.
- Keep chat questions within the two-entity connection scope.
- Do not paste real names, records, credentials, or investigative material into the demo.
