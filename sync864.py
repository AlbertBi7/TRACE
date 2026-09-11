import httpx
c=httpx.Client(base_url='http://localhost:8000')
tok=c.post("/api/auth/login", json={"email":"investigator@trace.dev","password":"TraceInvestigator123!"}).json()["access_token"]
H={"Authorization": f"Bearer {tok}"}
r=c.post("/api/cases/86453645-f6c6-451a-a254-678156c4803d/graph/sync", headers=H)
print(r.json())
g=c.get("/api/cases/86453645-f6c6-451a-a254-678156c4803d/graph", headers=H).json()
print(f"nodes {len(g['nodes'])} edges {len(g['edges'])}")
for n in g["nodes"][:5]:
    print(n)
