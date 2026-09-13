DRISHYAM-1 UPLOAD PACK — Disappearance of Varun Prabhakar
Fictional training case dramatized from Jeethu Joseph's Drishyam (2013), for reference and creative purposes only.
All names, phones, accounts, plates and places are synthetic. Any resemblance to real persons is coincidental.

FILES (upload all 6 into ONE new case):
  1. FIR_Drishyam1_Varun_Prabhakar.pdf  — main case file, text PDF (10 paras)
  2. 01_fir_statement.txt               — same narrative as TXT fallback
  3. 02_call_records.csv                — 8 call rows incl. tower codes
  4. 03_bank_ledger.csv                 — 2 transfers SIB-XXXX-2091 -> FED-XXXX-3355
  5. 04_contacts.json                   — 8 persons with phones and vehicles
  6. 05_vehicles_alibi.txt              — vehicle ownership and alibi notes

DO NOT upload: make_pdf.py, test_extract.py, test_extract_docker.py (helpers only, already removed).

STEPS IN TRACE:
  1. Cases → New Case → name it exactly: Drishyam-1 — Varun Prabhakar
  2. Open the case → drag and drop all 6 files → wait for parse.
  3. Press Extract on each file (PDF first, then TXTs, then CSVs, then JSON).
  4. Click Find Matches → accept high-confidence merges:
       - Constable Sahadevan ≈ Sahadevan (if suggested)
       - Anju George (ORG) ≈ Anju George (PERSON) — keep PERSON as primary
       - Kochi (PERSON) ≈ Kochi (LOCATION) — keep LOCATION as primary
     Dismiss junk (tower codes are already non-entities, nothing to dismiss).
  5. Open Graph Explorer → Sync graph → expect ~20 nodes, ~25 edges:
       PERSON 8 (Varun, Anju, Anu, Georgekutty, Rani, Geetha, Sahadevan, Monichan)
       PHONE 7, BANK_ACCOUNT 2, VEHICLE 3, LOCATION 3 (Rajakkad, Kochi, Kerala),
       ORG 1 (Kochi Cable Network).
  6. Visually cool checks:
       - Family cluster (Georgekutty-Rani-Anju-Anu) left, police cluster
         (Geetha-Sahadevan) right, Varun bridging them in the middle.
       - Money edge SIB-XXXX-2091 → FED-XXXX-3355 (Transferred to).
       - Try layouts: Force then Tree. Path tool From Varun Prabhakar To Monichan.
       - Analyze panel: Connections Chat "How is Varun Prabhakar connected to
         Georgekutty Joseph?" → cited path via Anju. Disruption Simulator on
         Varun or Georgekutty (articulation ★). Priority Score neutral bullets.
       - Heuristic leads appear as dashed amber unconfirmed edges.

WHY IT LOOKS GOOD:
  Each paragraph holds 2-3 entities plus one cue word (called, met with,
  travelled with, transferred, works for, owns, uses), so every sentence
  yields 2-6 edges and nothing is isolated. Phones/accounts/plates use
  TRACE regex formats (98470-11223, SIB-XXXX-2091, KL-39-C-1934) for
  high-precision extraction with file/page/paragraph provenance.
