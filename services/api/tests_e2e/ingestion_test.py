"""TRACE Phase 1 ingestion e2e — runs inside the api container using httpx."""
import json
import httpx

BASE = "http://localhost:8000"

ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print(f"PASS {name}")
    else: fail += 1; print(f"FAIL {name} {extra}")

def build_pdf(lines):
    objs = []
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    objs.append("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>")
    stream = "".join(f"BT /F1 12 Tf 72 {760-30*i} Td ({ln}) Tj ET\n" for i, ln in enumerate(lines))
    objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}endstream")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pdf = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    return pdf

c = httpx.Client(base_url=BASE, timeout=30)

r = c.post("/api/auth/login", json={"email":"investigator@trace.dev","password":"TraceInvestigator123!"})
inv = r.json()["access_token"]
H = {"Authorization": f"Bearer {inv}"}

# Own case so the test is re-runnable against a persistent dev stack
import uuid as _uuid
r = c.post("/api/auth/login", json={"email":"admin@trace.dev","password":"TraceAdmin123!"})
adm = r.json()["access_token"]
r = c.post("/api/cases", json={"name": f"Ingestion Test {_uuid.uuid4().hex[:8]}", "description": "e2e"},
           headers={"Authorization": f"Bearer {adm}"})
CASE = r.json()["id"]
users = c.get("/api/users", headers={"Authorization": f"Bearer {adm}"}).json()
inv_uid = next(u["id"] for u in users if u["email"] == "investigator@trace.dev")
c.post(f"/api/cases/{CASE}/assign", json={"user_id": inv_uid}, headers={"Authorization": f"Bearer {adm}"})

# List (empty for this fresh case)
r = c.get(f"/api/cases/{CASE}/documents", headers=H)
check("list documents (200)", r.status_code == 200, f"status={r.status_code} {r.text[:120]}")

txt = ("Case Brief: Operation Nexus (fictional training data).\n\n"
       "Rohan Mehra was in frequent phone contact with Priya Sharma during January.\n\n"
       "Vikram Singh transferred funds from account SBI-XXXX-7832 to ICICI-XXXX-1199.\n\n"
       "Anita Desai travelled to Bengaluru with Rohan Mehra on 2024-01-15.\n").encode()
csv_data = ("from_account,to_account,amount,currency\n"
            "HDFC-XXXX-4521,SBI-XXXX-7832,1500000,INR\n"
            "SBI-XXXX-7832,ICICI-XXXX-1199,750000,INR\n").encode()
json_data = json.dumps([
    {"name": "Kavita Nair", "phone": "+91-91234-56789", "org": "Sunrise Consulting"},
    {"name": "Deepak Joshi", "phone": "+91-88776-65544", "vehicle": "DL-01-CD-5678"},
]).encode()
pdf = build_pdf(["Quarterly Surveillance Summary (fictional).",
                 "Subject Rohan Mehra used vehicle MH-02-AB-1234 on route to Mumbai.",
                 "Suresh Patel contacted +91-98765-43210 eleven times."])

files = [("report.txt", "text/plain", txt), ("ledger.csv", "text/csv", csv_data),
         ("contacts.json", "application/json", json_data), ("brief.pdf", "application/pdf", pdf)]
doc_ids = {}
for fname, ctype, payload in files:
    r = c.post(f"/api/cases/{CASE}/documents", headers=H,
               files={"file": (fname, payload, ctype)})
    body = {}
    try: body = r.json()
    except Exception: pass
    check(f"upload {fname} (201)", r.status_code == 201 and body.get("filename") == fname,
          f"status={r.status_code} {r.text[:150]}")
    if body.get("id"): doc_ids[fname] = body["id"]

r = c.get(f"/api/cases/{CASE}/documents", headers=H)
docs = r.json()
check("list has 4 docs", r.status_code == 200 and len(docs) == 4, f"n={len(docs)}")
check("list includes uploader + extraction_count",
      all(x.get("uploader_name") and "extraction_count" in x for x in docs), str(docs)[:200])

r = c.get(f"/api/cases/{CASE}/documents/{doc_ids['brief.pdf']}", headers=H)
d = r.json()
check("pdf parsed 1 page / 3 paragraphs",
      r.status_code == 200 and len(d["pages"]) == 1 and len(d["pages"][0]["paragraphs"]) == 3,
      str(d.get("pages"))[:150])

r = c.get(f"/api/cases/{CASE}/documents/{doc_ids['report.txt']}", headers=H)
d = r.json()
check("txt parsed 4 paragraphs", len(d["pages"][0]["paragraphs"]) == 4,
      str(len(d["pages"][0]["paragraphs"])))

r = c.get(f"/api/cases/{CASE}/documents/{doc_ids['ledger.csv']}", headers=H)
d = r.json()
check("csv rows normalized with column names",
      any("amount: 1500000" in p for p in d["pages"][0]["paragraphs"]), str(d["pages"])[:200])

# Negative: unsupported extension
r = c.post(f"/api/cases/{CASE}/documents", headers=H,
           files={"file": ("notes.docx", b"xx", "application/octet-stream")})
check("reject .docx (400)", r.status_code == 400, f"status={r.status_code}")

# Negative: empty file
r = c.post(f"/api/cases/{CASE}/documents", headers=H,
           files={"file": ("empty.txt", b"", "text/plain")})
check("reject empty file (400)", r.status_code == 400, f"status={r.status_code}")

# Negative: investigator not assigned to another case
r = c.post("/api/cases", json={"name":"Case C","description":"x"}, headers={"Authorization": f"Bearer {adm}"})
case_c = r.json()["id"]
r = c.post(f"/api/cases/{case_c}/documents", headers=H,
           files={"file": ("x.txt", b"hello", "text/plain")})
check("case scoping blocks upload (403)", r.status_code == 403, f"status={r.status_code}")

print(f"\n{ok} passed, {fail} failed")
