"""
TRACE e2e — Auth, RBAC, and case scoping.
Run against a live stack:
  docker exec trace-api python /app/tests_e2e/00_auth_test.py
Uses unique case names per run, so it is re-runnable on a persistent dev stack.
"""
import json
import uuid

import httpx

BASE = "http://localhost:8000"
c = httpx.Client(base_url=BASE, timeout=30)

ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"PASS {name}")
    else:
        fail += 1
        print(f"FAIL {name} {extra}")


def req(method, path, body=None, token=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    r = c.request(method, path, json=body, headers=headers)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {}


# ── Auth ──────────────────────────────────────────────────────
s, d = req("POST", "/api/auth/login", {"email": "investigator@trace.dev", "password": "TraceInvestigator123!"})
check("investigator login", s == 200 and "access_token" in d, str(d)[:120])
inv = d.get("access_token")
inv_rt = d.get("refresh_token")

s, d = req("GET", "/api/auth/me", token=inv)
check("me endpoint", s == 200 and d.get("role") == "investigator", str(d)[:120])

s, d = req("POST", "/api/auth/refresh", {"refresh_token": inv_rt})
check("refresh rotation", s == 200 and "access_token" in d, str(d)[:120])
new_rt = d.get("refresh_token")

s, d = req("POST", "/api/auth/refresh", {"refresh_token": inv_rt})
check("old refresh revoked", s == 401, f"status={s}")

s, d = req("POST", "/api/auth/login", {"email": "admin@trace.dev", "password": "TraceAdmin123!"})
check("admin login", s == 200, str(d)[:120])
adm = d.get("access_token")

s, d = req("POST", "/api/auth/login", {"email": "investigator@trace.dev", "password": "wrong"})
check("wrong password rejected", s == 401, f"status={s}")

# ── RBAC / scoping ────────────────────────────────────────────
s, users = req("GET", "/api/users", token=adm)
check("admin user list", s == 200 and isinstance(users, list), f"status={s}")
s, d = req("GET", "/api/users", token=inv)
check("RBAC blocks investigator on admin route", s == 403, f"status={s}")

s, d = req("POST", "/api/cases", {"name": f"RBAC Test {uuid.uuid4().hex[:8]}", "description": "e2e"}, token=adm)
check("admin creates case", s == 201, str(d)[:120])
case_b = d.get("id")

s, d = req("GET", f"/api/cases/{case_b}", token=inv)
check("case scoping blocks investigator", s == 403, f"status={s}")

# assignment role validation
admin_uid = next((u["id"] for u in users if u["role"] == "admin"), None)
s, d = req("POST", f"/api/cases/{case_b}/assign", {"user_id": admin_uid}, token=adm)
check("assign rejects non-investigator", s == 400, f"status={s}")

# ── Logout revocation ─────────────────────────────────────────
s, d = req("POST", "/api/auth/logout", {"refresh_token": new_rt}, token=inv)
check("logout", s == 200, f"status={s}")
s, d = req("POST", "/api/auth/refresh", {"refresh_token": new_rt})
check("post-logout refresh denied", s == 401, f"status={s}")

print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
