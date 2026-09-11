import httpx, json, asyncio
BASE="http://localhost:8000"
c=httpx.Client(base_url=BASE, timeout=30)
tok=c.post("/api/auth/login", json={"email":"investigator@trace.dev","password":"TraceInvestigator123!"}).json()["access_token"]
H={"Authorization": f"Bearer {tok}"}
case_id="86453645-f6c6-451a-a254-678156c4803d"
# Test chat that previously failed with ext-001
q="How is Rohan Mehra connected to Priya Sharma?"
print(f"Testing chat for case {case_id} q='{q}'")
with c.stream("GET", f"/api/cases/{case_id}/chat", params={"q": q}, headers=H) as r:
    print("status", r.status_code, r.headers.get("content-type"))
    for line in r.iter_lines():
        if line.startswith("data: "):
            data=json.loads(line[6:])
            print(data)
            if data.get("type")=="done":
                break
print("\n--- second test with valid extraction case ---")
case2="453bbef1-03fd-428e-9f35-5275c7e3d8a0"
q2="How is Maya Iyer connected to SBI-XXXX-2210?"
with c.stream("GET", f"/api/cases/{case2}/chat", params={"q": q2}, headers=H) as r:
    print("status", r.status_code)
    for line in r.iter_lines():
        if line.startswith("data: "):
            data=json.loads(line[6:])
            print(data)
            if data.get("type")=="done":
                break
