import httpx
BASE="http://localhost:8000"
c=httpx.Client(base_url=BASE, timeout=10)
tok=c.post("/api/auth/login", json={"email":"investigator@trace.dev","password":"TraceInvestigator123!"}).json()["access_token"]
H={"Authorization": f"Bearer {tok}"}
case_id="86453645-f6c6-451a-a254-678156c4803d"
print(c.get(f"/api/cases/{case_id}", headers=H).json())
print(c.get(f"/api/cases/{case_id}/documents", headers=H).json())
print(c.get(f"/api/cases/{case_id}/graph", headers=H).json())
# also check extraction count via postgres direct? Use API extraction status for each doc
docs=c.get(f"/api/cases/{case_id}/documents", headers=H).json()
for d in docs:
    print(c.get(f"/api/cases/{case_id}/documents/{d['id']}/extract", headers=H).json())
