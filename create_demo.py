import httpx, json, uuid, time
BASE="http://localhost:8000"
c=httpx.Client(base_url=BASE, timeout=60)
# login
r=c.post("/api/auth/login", json={"email":"investigator@trace.dev","password":"TraceInvestigator123!"})
r.raise_for_status()
inv_tok=r.json()["access_token"]
H={"Authorization": f"Bearer {inv_tok}"}
r2=c.post("/api/auth/login", json={"email":"admin@trace.dev","password":"TraceAdmin123!"})
adm_tok=r2.json()["access_token"]
Hadm={"Authorization": f"Bearer {adm_tok}"}

case_name = "Demo TRACE Graph 2026 - Verified"
# Check if exists, else create
existing=c.get("/api/cases", headers=H).json()
found=[x for x in existing if x["name"]==case_name]
if found:
    case_id=found[0]["id"]
    print(f"Found existing case: {case_name} -> {case_id}")
else:
    r=c.post("/api/cases", json={"name": case_name, "description":"Demo test case - graph should render 5 nodes 7 links. Created for verification."}, headers=Hadm)
    r.raise_for_status()
    case_id=r.json()["id"]
    print(f"Created case: {case_name} -> {case_id}")
    users=c.get("/api/users", headers=Hadm).json()
    inv_id=next(u["id"] for u in users if u["email"]=="investigator@trace.dev")
    rr=c.post(f"/api/cases/{case_id}/assign", json={"user_id": inv_id}, headers=Hadm)
    print("assign",rr.status_code, rr.text[:200])

# Check docs
docs=c.get(f"/api/cases/{case_id}/documents", headers=H).json()
print(f"existing docs: {len(docs)}")
if len(docs)==0:
    txt1 = (
        "Demo verification brief (fictional).\n\n"
        "Maya Iyer uses phone +91-90123-45678 and account HDFC-XXXX-9911.\n\n"
        "Arjun Rao used phone +91-90123-45678 in two recorded incidents.\n\n"
        "Maya Iyer transferred funds from HDFC-XXXX-9911 to SBI-XXXX-2210.\n\n"
        "Arjun Rao travelled with Maya Iyer to Hyderabad.\n"
    ).encode()
    txt2 = (
        "Witness statement: Nalini Verma was seen with phone +91-90999-88881 near the depot.\n"
        "Nalini Verma transferred funds from HDFC-XXXX-7741 to AXIS-XXXX-9012.\n"
    ).encode()
    for name, data in [("demo1.txt", txt1), ("demo2.txt", txt2)]:
        r=c.post(f"/api/cases/{case_id}/documents", headers=H, files={"file": (name, data, "text/plain")})
        print(f"upload {name}", r.status_code, r.text[:200])
        time.sleep(0.5)
    docs=c.get(f"/api/cases/{case_id}/documents", headers=H).json()
    print(f"after upload docs: {len(docs)}")

# Extract all docs
for d in docs:
    if not d.get("extracted"):
        r=c.post(f"/api/cases/{case_id}/documents/{d['id']}/extract", headers=H, json={})
        print(f"extract {d['filename']}", r.status_code, r.json())

# Suggest merges
r=c.post(f"/api/cases/{case_id}/resolution/suggest", headers=H)
print("suggest", r.json())
merges=c.get(f"/api/cases/{case_id}/resolution/merges", headers=H).json()
print("merges", json.dumps(merges, indent=2)[:800])
for m in merges.get("suggested", []):
    r=c.post(f"/api/cases/{case_id}/resolution/merges/{m['id']}/accept", headers=H)
    print(f"accept {m['primary_value']} ~ {m['merged_value']}", r.status_code)
    break

# Sync graph
r=c.post(f"/api/cases/{case_id}/graph/sync", headers=H)
print("sync", r.json())
g=c.get(f"/api/cases/{case_id}/graph", headers=H).json()
print(f"GRAPH: {len(g['nodes'])} nodes, {len(g['edges'])} edges")
for n in g["nodes"][:5]:
    print(n["label"], n["entity_type"], n["aliases"])
for e in g["edges"][:5]:
    print(e["source"], e["relation"], e["target"])

print(f"\nCASE NAME: {case_name}")
print(f"CASE ID: {case_id}")
print(f"Graph URL: http://localhost:5173/dashboard/cases/{case_id}/graph")
