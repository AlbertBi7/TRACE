"""
TRACE e2e — Full pipeline: ingestion → extraction → resolution → graph → analysis → chat.
Run against a live stack:
  docker exec trace-api python /app/tests_e2e/10_pipeline_test.py
Creates its own case (unique name) so it never disturbs the demo case, and
leaves its artifacts in place for manual inspection.
"""
import io
import json
import uuid

import httpx

BASE = "http://localhost:8000"
c = httpx.Client(base_url=BASE, timeout=120)

ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"PASS {name}")
    else:
        fail += 1
        print(f"FAIL {name} {extra}")


# ── Login ─────────────────────────────────────────────────────
r = c.post("/api/auth/login", json={"email": "investigator@trace.dev", "password": "TraceInvestigator123!"})
inv = r.json()["access_token"]
H = {"Authorization": f"Bearer {inv}"}
r = c.post("/api/auth/login", json={"email": "admin@trace.dev", "password": "TraceAdmin123!"})
adm = r.json()["access_token"]

# Own case for the run
case_name = f"Pipeline Test {uuid.uuid4().hex[:8]}"
r = c.post("/api/cases", json={"name": case_name, "description": "e2e pipeline run"}, headers={"Authorization": f"Bearer {adm}"})
CASE = r.json()["id"]
check("create test case", r.status_code == 201, f"status={r.status_code}")
c.post(f"/api/cases/{CASE}/assign", json={"user_id": None}, headers=H)  # noop; investigator is creator? (admin created)
# Assign investigator properly (need user id)
users = c.get("/api/users", headers={"Authorization": f"Bearer {adm}"}).json()
inv_uid = next(u["id"] for u in users if u["email"] == "investigator@trace.dev")
r = c.post(f"/api/cases/{CASE}/assign", json={"user_id": inv_uid}, headers={"Authorization": f"Bearer {adm}"})
check("assign investigator to test case", r.status_code == 200, f"status={r.status_code} {r.text[:100]}")

# ── 1) Ingestion ──────────────────────────────────────────────
txt = (
    "Pipeline verification brief (fictional training data).\n\n"
    "Maya Iyer uses phone +91-90123-45678 and account HDFC-XXXX-9911.\n\n"
    "Arjun Rao used phone +91-90123-45678 in two recorded incidents.\n\n"
    "Maya Iyer transferred funds from HDFC-XXXX-9911 to SBI-XXXX-2210.\n\n"
    "Arjun Rao travelled with Maya Iyer to Hyderabad.\n"
).encode()
r = c.post(f"/api/cases/{CASE}/documents", headers=H, files={"file": ("pipeline.txt", txt, "text/plain")})
check("upload document", r.status_code == 201, f"status={r.status_code} {r.text[:120]}")
doc_id = r.json()["id"]

# ── 2) Extraction ─────────────────────────────────────────────
r = c.post(f"/api/cases/{CASE}/documents/{doc_id}/extract", headers=H, json={"use_llm_fallback": True})
res = r.json()
check("extraction runs", r.status_code == 200 and res.get("entities", 0) >= 5, str(res)[:150])

r = c.get(f"/api/cases/{CASE}/documents/{doc_id}", headers=H)
d = r.json()
check("provenance-anchored parse stored", len(d["pages"]) == 1 and len(d["pages"][0]["paragraphs"]) == 5, str(d.get("pages"))[:120])

# extraction_log rows exist and link to the document
r = c.get(f"/api/cases/{CASE}/documents/{doc_id}/extract", headers=H)
st = r.json()
check("extraction status populated", r.status_code == 200 and st.get("extracted") is True, str(st)[:150])

# ── 3) Entity resolution: shared phone should link Maya & Arjun ──
r = c.post(f"/api/cases/{CASE}/resolution/suggest", headers=H)
sug = r.json()
check("resolution suggestions generated", r.status_code == 200 and sug.get("suggested", 0) >= 1, str(sug)[:150])
shared = next((s for s in sug["suggestions"] if s["method"] == "shared_attribute"), None)
check("shared-attribute match found", shared is not None, str(sug)[:200])
if shared:
    # The suggest endpoint returns in-memory suggestions; fetch the persisted
    # merge row id from the list endpoint before accepting.
    merges = c.get(f"/api/cases/{CASE}/resolution/merges", headers=H).json()
    row = next((m for m in merges.get("suggested", [])
                if m["primary_entity_id"] == shared["primary_entity_id"]
                and m["merged_entity_id"] == shared["merged_entity_id"]), None)
    check("suggested merge persisted", row is not None, str(merges)[:200])
    if row:
        r = c.post(f"/api/cases/{CASE}/resolution/merges/{row['id']}/accept", headers=H)
        check("merge accepted", r.status_code == 200, f"status={r.status_code}")

# ── 4) Graph sync + reads ─────────────────────────────────────
r = c.post(f"/api/cases/{CASE}/graph/sync", headers=H)
sync = r.json()
check("graph sync", r.status_code == 200 and sync.get("nodes", 0) >= 5, str(sync)[:120])

g = c.get(f"/api/cases/{CASE}/graph", headers=H).json()
check("graph read returns nodes+edges", len(g["nodes"]) >= 5 and len(g["edges"]) >= 3, f"n={len(g['nodes'])} e={len(g['edges'])}")
check("graph edges carry provenance", all(len(e["provenance_ids"]) >= 1 for e in g["edges"]), str(g["edges"])[:200])

maya = next((n for n in g["nodes"] if n["in_case"] and (
    n["label"] == "Maya Iyer" or "Maya Iyer" in n.get("aliases", []))), None)
check("canonical person node exists", maya is not None,
      str([(n["label"], n.get("aliases")) for n in g["nodes"] if n["in_case"]]))

# node detail provenance
if maya:
    nd = c.get(f"/api/cases/{CASE}/graph/nodes/{maya['id']}", headers=H).json()
    check("node detail has verbatim provenance",
          len(nd["provenance"]) >= 1 and all(p["filename"] == "pipeline.txt" for p in nd["provenance"]),
          str(nd["provenance"])[:200])

# ── 5) Analysis: structure + simulation ───────────────────────
s = c.get(f"/api/cases/{CASE}/analysis/structure", headers=H).json()
in_case_count = len([n for n in g["nodes"] if n["in_case"]])
check("structure analysis", s.get("node_count") == in_case_count,
      f"structure={s.get('node_count')} in_case={in_case_count}")
if maya:
    sim = c.post(f"/api/cases/{CASE}/analysis/simulate-removal/{maya['id']}", headers=H).json()
    check("removal simulation returns metrics", "metrics" in sim and "before" in sim, str(sim)[:150])
    check("simulation explanation is neutral",
          any("structural" in b for b in sim.get("explanation", [])), str(sim.get("explanation"))[:200])

# ── 6) Scoped chat ────────────────────────────────────────────
# Note: Maya Iyer and Arjun Rao were MERGED above (shared phone), so asking
# about the pair must yield the explicit "same entity" explanation, and a real
# path question must use two distinct nodes (Maya ↔ her account).
events_same = []
with c.stream("GET", f"/api/cases/{CASE}/chat", params={"q": "How is Maya Iyer connected to Arjun Rao?"}, headers=H) as resp:
    check("chat streams SSE", resp.status_code == 200 and "text/event-stream" in resp.headers.get("content-type", ""), resp.headers.get("content-type", ""))
    for line in resp.iter_lines():
        if line.startswith("data: "):
            events_same.append(json.loads(line[6:]))
            if events_same[-1]["type"] == "done":
                break
err = next((e for e in events_same if e["type"] == "error"), None)
check("chat explains merged-entity case", bool(err and "same entity" in err["message"]), str(events_same[:2])[:250])

events = []
with c.stream("GET", f"/api/cases/{CASE}/chat", params={"q": "How is Maya Iyer connected to SBI-XXXX-2210?"}, headers=H) as resp:
    for line in resp.iter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
            if events[-1]["type"] == "done":
                break
summary = "".join(e.get("text", "") for e in events if e["type"] == "tokens")
cits = next((e for e in events if e["type"] == "citations"), None)
check("chat finds path", bool(cits and cits.get("path")), str(events[:2])[:250])
# Note: Maya/Arjun are one merged entity by this point — the summary uses the
# canonical label; assert on the account side which is unambiguous.
check("chat summary grounded", "SBI-XXXX-2210" in summary and "connected" in summary, summary[:200])
check("chat cites sources", bool(cits and len(cits["citations"]) >= 1), str(cits)[:150])

# Chat without two entities → graceful error event
events2 = []
with c.stream("GET", f"/api/cases/{CASE}/chat", params={"q": "hello?"}, headers=H) as resp:
    for line in resp.iter_lines():
        if line.startswith("data: "):
            events2.append(json.loads(line[6:]))
            if events2[-1]["type"] == "done":
                break
check("chat requires two entities", any(e["type"] == "error" for e in events2), str(events2)[:200])

# ── 7) Heuristic links + priority scores run without error ────
h = c.get(f"/api/cases/{CASE}/heuristic-links", headers=H)
check("heuristic links endpoint", h.status_code == 200 and "edges" in h.json(), f"status={h.status_code}")
p = c.get(f"/api/cases/{CASE}/priority-scores", headers=H)
ps = p.json().get("scores", [])
check("priority scores endpoint", p.status_code == 200 and len(ps) >= 1, f"status={p.status_code}")
check("priority explanation includes disclaimer",
      bool(ps) and any("not an assessment" in b for b in ps[0]["explanation"]), str(ps[:1])[:200])

print(f"\n{ok} passed, {fail} failed  (test case: {case_name})")
raise SystemExit(1 if fail else 0)
