TRACE Demo Resources — Drishyam: Kalinjur FIR 2026/0417
====================================================

This folder contains fictional training data for TRACE. Do NOT use real data.

Files:
- FIR_2026_0417_Drishyam.pdf — Main FIR + Supplementary Diary (text PDF, PyPDF2-readable)
- call_records_2026_0417.csv — CDRs with tower data (SHIP: KJR-04 vs RDP-01)
- bank_ledger_2026_0417.csv — Bank transfers including 041720001123 → 041720009981
- contacts_directory.json — All persons/phones/accounts
- hotel_register_sunrise_lodge.csv — Hotel check-ins
- bakery_ledger_kori_bakery.csv — Bakery bills
- workshop_attendance_rudrapuram.txt — Attendance register
- case_timeline_2026_0417.txt — Chronology

How to use in TRACE:
1. Create new case: "Drishyam — Kalinjur 2026/0417" (or "Drishyam - Vantara")
2. Upload ALL files (drag & drop) → Extract each → Find Matches → Accept high-confidence merges
3. Sync graph → Open Graph Explorer → verify 15+ nodes (PERSON/ORG/PHONE/VEHICLE/BANK_ACCOUNT)
4. Try Analysis: Disruption (articulation), Heuristic leads (dashed), Priority, Chat "How is Devraj Oberoi connected to Farhan Qureshi?" → should return 1-2 hops via phone/account
5. Case Network: After syncing, check /dashboard/case-network — this case will link to Operation Nexus via shared phone +91-98765-43210 if you also use that phone in another case.

All data fictional. Inspired by Drishyam narrative structure for training only.
