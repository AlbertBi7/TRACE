import httpx, json
BASE="http://localhost:8000"
c=httpx.Client(base_url=BASE, timeout=10)
tok=c.post("/api/auth/login", json={"email":"investigator@trace.dev","password":"TraceInvestigator123!"}).json()["access_token"]
H={"Authorization": f"Bearer {tok}"}
case_id="453bbef1-03fd-428e-9f35-5275c7e3d8a0"
r=c.get(f"/api/cases/{case_id}", headers=H)
print(r.json())
print("---")
g=c.get(f"/api/cases/{case_id}/graph", headers=H).json()
print(f"nodes {len(g['nodes'])} edges {len(g['edges'])}")
for n in g["nodes"]:
    print(n["label"], n["entity_type"], n["id"])
print("---Operation Nexus---")
oid="c0000000-0000-0000-0000-000000000001"
r2=c.get(f"/api/cases/{oid}", headers=H)
print(r2.json())
g2=c.get(f"/api/cases/{oid}/graph", headers=H).json()
print(f"Operation Nexus nodes {len(g2['nodes'])} edges {len(g2['edges'])}")
