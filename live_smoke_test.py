"""
live_smoke_test.py — end-to-end test against the REAL running servers over HTTP.

  Terminal 1:  python run_all.py --backend --fresh
  Terminal 2:  python live_smoke_test.py

Requires REACH_MOCK_EXTERNAL=1 (the default in .env) because it reads OTP codes
straight from the dev database instead of an SMS.
"""
import os, sqlite3, sys, requests

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("REACH_DB_PATH", os.path.join(ROOT, "reach_dev.db"))
PRICING, GEN, COL, PICK, DATA, CORP = (f"http://localhost:{p}" for p in (8001, 8002, 8003, 8004, 8005, 8006))


def check(label, r, expect=200):
    ok = r.status_code == expect
    print(f"[{'OK' if ok else 'FAIL'}] {label} -> {r.status_code}")
    if not ok:
        print("      ", r.text[:300]); sys.exit(1)
    return r.json()


def otp_code(session_id):
    con = sqlite3.connect(DB)
    code = con.execute("select code from otp_sessions where id=?", (session_id,)).fetchone()[0]
    con.close()
    return code


def verified_phone(base, prefix, phone):
    sid = check(f"{prefix}: request OTP", requests.post(f"{base}/{prefix}/request-otp", json={"phone": phone}))["otp_session_id"]
    check(f"{prefix}: verify OTP", requests.post(f"{base}/{prefix}/verify-otp", json={"otp_session_id": sid, "code": otp_code(sid)}))
    return sid


# CORS: the browser apps live on other ports and must be allowed
pre = requests.options(f"{GEN}/postings", headers={"Origin": "http://localhost:3001", "Access-Control-Request-Method": "POST"})
assert pre.headers.get("access-control-allow-origin") == "http://localhost:3001", f"CORS not working: {pre.headers}"
print("[OK] CORS preflight from http://localhost:3001 allowed")

cats = check("pricing: categories", requests.get(f"{PRICING}/categories"))
print("      rate card:", {c['name']: c['rate_per_kg'] for c in cats})

cluster = check("generator: create cluster (geocoded)", requests.post(f"{GEN}/clusters", json={"name": "Hosahalli Village"}))
gens = []
for i in range(3):
    phone = f"90000000{i}"
    sid = verified_phone(GEN, "generators", phone)
    gens.append(check(f"generator {i+1}: register", requests.post(f"{GEN}/generators", json={"name": f"Household {i+1}", "phone": phone, "geo_cluster_id": cluster["id"], "otp_session_id": sid}))["id"])

run_id = None
for i, g in enumerate(gens):
    res = check(f"posting {i+1}: 80kg plastic", requests.post(f"{GEN}/postings", json={"generator_id": g, "geo_cluster_id": cluster["id"], "category_name": "plastic", "est_weight_kg": 80}))
    run_id = res["run_id"] or run_id
assert run_id and res["quota_crossed"], "quota should have crossed on the 3rd posting"
print(f"      quota crossed -> run {run_id}")

sid = verified_phone(COL, "collectors", "9999999999")
col = check("collector: register", requests.post(f"{COL}/collectors", json={"name": "Ramesh Kabadiwala", "phone": "9999999999", "otp_session_id": sid}))["id"]

# accepting before KYC must be refused
r = requests.post(f"{COL}/runs/{run_id}/accept", json={"collector_id": col})
assert r.status_code == 403, "unverified collector must not be able to accept"
print("[OK] accept before KYC correctly refused (403)")

check("collector: KYC initiate", requests.post(f"{COL}/collectors/{col}/kyc/initiate", json={"aadhaar_number": "999999990019"}))
check("collector: KYC verify", requests.post(f"{COL}/collectors/{col}/kyc/verify", json={"aadhaar_number": "999999990019", "otp": "0000"}))

assert any(r["id"] == run_id for r in check("collector: open runs", requests.get(f"{COL}/runs/open")))
check("collector: accept run", requests.post(f"{COL}/runs/{run_id}/accept", json={"collector_id": col}))
stops = check("collector: stops", requests.get(f"{COL}/runs/{run_id}/stops"))
assert len(stops) == 3
for s in stops:
    check(f"pickup: {s['stop_name']}", requests.post(f"{PICK}/runs/{run_id}/pickups", json={"posting_id": s["posting_id"], "actual_weight_kg": s["est_weight_kg"]}))
check("pickup: complete run", requests.post(f"{PICK}/runs/{run_id}/complete"))

rep = check("data-layer: cluster report", requests.get(f"{DATA}/reports/cluster/{cluster['id']}"))
assert rep["totals"][0]["total_weight_kg"] == 240

corp = check("corporate: onboard", requests.post(f"{CORP}/corporates", json={"name": "GreenPack Industries", "gstin": "27AAICB3918J1CT", "phone": "9888888888", "geo_cluster_id": cluster["id"]}))["id"]
pr = check("corporate: direct pickup 150kg metal", requests.post(f"{CORP}/corporates/{corp}/pickups", json={"category_name": "metal", "est_weight_kg": 150}))
check("collector: accept corporate run", requests.post(f"{COL}/runs/{pr['run_id']}/accept", json={"collector_id": col}))
cs = check("collector: corporate stops", requests.get(f"{COL}/runs/{pr['run_id']}/stops"))
check("pickup: corporate", requests.post(f"{PICK}/runs/{pr['run_id']}/pickups", json={"posting_id": cs[0]["posting_id"], "actual_weight_kg": 150}))
check("pickup: complete corporate run", requests.post(f"{PICK}/runs/{pr['run_id']}/complete"))
crep = check("corporate: ESG report", requests.get(f"{CORP}/corporates/{corp}/report"))
assert crep[0]["total_weight_kg"] == 150

print("\nLIVE SMOKE TEST PASSED — all 6 services working over real HTTP")
