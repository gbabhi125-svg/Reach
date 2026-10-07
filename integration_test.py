"""
integration_test.py
--------------------
Runs the full REACH flow end-to-end using FastAPI's TestClient against all
four services (they share one SQLite file for this local test, the same way
they'd share one Postgres instance in production). Prints each step's result
so bugs surface immediately.
"""

import sys, os

os.environ["REACH_MOCK_EXTERNAL"] = "1"  # no real SMS/geocoding calls during tests -- must be set
                                          # before geocode.py/otp.py are imported below, since they
                                          # read this into a module-level constant at import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "shared"))
import db as shared_db

# fresh DB for a clean test run
shared_db.init_db(fresh=True)

from fastapi.testclient import TestClient
import importlib


def load_service(folder):
    """Import a service's main.py in isolation so each one resolves to its
    OWN file, not whichever src/ dir happens to be first on sys.path."""
    src_dir = os.path.join(os.path.dirname(__file__), "backend", folder, "src")
    sys.path.insert(0, src_dir)
    if "main" in sys.modules:
        del sys.modules["main"]
    module = importlib.import_module("main")
    sys.path.remove(src_dir)
    return module


pricing_client = TestClient(load_service("pricing-service").app)
generator_client = TestClient(load_service("generator-service").app)
collector_client = TestClient(load_service("collector-service").app)
pickup_client = TestClient(load_service("pickup-service").app)
data_client = TestClient(load_service("data-layer-service").app)
corporate_client = TestClient(load_service("corporate-service").app)


def step(label, resp):
    print(f"\n--- {label} [{resp.status_code}] ---")
    print(resp.json())
    assert resp.status_code < 400, f"FAILED: {label}"
    return resp.json()


print("=" * 60)
print("REACH integration test")
print("=" * 60)

# 1. pricing-service: confirm categories seeded
cats = step("pricing: list categories", pricing_client.get("/categories"))
plastic_quota = next(c for c in cats if c["name"] == "plastic")["quota_kg"]
print(f"plastic quota is {plastic_quota} kg")


def onboard_via_otp(client, phone, request_path, verify_path):
    """Simulates the real OTP flow: request an OTP, read it back from the
    server logs (mock mode only -- in production the user reads it off
    their phone), then verify it."""
    otp_resp = step(f"{request_path}: request OTP for {phone}", client.post(request_path, json={"phone": phone}))
    session_id = otp_resp["otp_session_id"]
    # in mock mode the code is printed to stdout by shared/otp.py; for the
    # test we re-derive it the same deterministic way generate_and_send does
    # is impossible since it's random -- so instead we read it straight from
    # the DB via the shared module (acceptable for a test harness).
    import db as shared_db_mod
    dbs = shared_db_mod.get_session()
    otp_session = dbs.query(shared_db_mod.OtpSession).filter_by(id=session_id).first()
    code = otp_session.code
    dbs.close()
    step(f"{verify_path}: verify OTP", client.post(verify_path, json={"otp_session_id": session_id, "code": code}))
    return session_id


# 2. generator-service: create a cluster (auto-geocoded) + 3 OTP-verified generators
cluster = step("generator: create cluster (auto-geocoded)", generator_client.post(
    "/clusters", json={"name": "Hosahalli Village"}
))
cluster_id = cluster["id"]
print(f"cluster geocoded to lat={cluster['lat']}, lng={cluster['lng']}")

gens = []
for i in range(3):
    phone = f"90000000{i}"
    session_id = onboard_via_otp(generator_client, phone, "/generators/request-otp", "/generators/verify-otp")
    g = step(f"generator: create generator {i+1}", generator_client.post(
        "/generators",
        json={"name": f"Household {i+1}", "phone": phone, "geo_cluster_id": cluster_id, "otp_session_id": session_id},
    ))
    gens.append(g["id"])

# 3. Post waste below quota, then cross it (quota=200kg, 3x80kg=240kg crosses on 3rd)
p1 = step("generator: posting 1 (80kg plastic)", generator_client.post(
    "/postings", json={"generator_id": gens[0], "geo_cluster_id": cluster_id, "category_name": "plastic", "est_weight_kg": 80}
))
assert p1["quota_crossed"] is False, "should NOT cross quota yet"

p2 = step("generator: posting 2 (80kg plastic)", generator_client.post(
    "/postings", json={"generator_id": gens[1], "geo_cluster_id": cluster_id, "category_name": "plastic", "est_weight_kg": 80}
))
assert p2["quota_crossed"] is False, "should NOT cross quota yet"

p3 = step("generator: posting 3 (80kg plastic) -- should cross 200kg quota", generator_client.post(
    "/postings", json={"generator_id": gens[2], "geo_cluster_id": cluster_id, "category_name": "plastic", "est_weight_kg": 80}
))
assert p3["quota_crossed"] is True, "SHOULD cross quota on 3rd posting"
run_id = p3["run_id"]
print(f"\n*** quota crossed, run opened: {run_id} ***")

# 4. collector-service: register a collector via OTP, see the open run, accept it, check stops
collector_phone = "9999999999"
collector_session_id = onboard_via_otp(
    collector_client, collector_phone, "/collectors/request-otp", "/collectors/verify-otp"
)
collector = step("collector: create collector", collector_client.post(
    "/collectors",
    json={"name": "Ramesh Kabadiwala", "phone": collector_phone, "otp_session_id": collector_session_id},
))
collector_id = collector["id"]

# Identity (Aadhaar eKYC) verification -- required before a collector can accept a run
import kyc as kyc_mod
kyc_init = step("collector: initiate Aadhaar eKYC", collector_client.post(
    f"/collectors/{collector_id}/kyc/initiate", json={"aadhaar_number": kyc_mod.SANDBOX_TEST_AADHAAR}
))
kyc_result = step("collector: verify Aadhaar eKYC", collector_client.post(
    f"/collectors/{collector_id}/kyc/verify", json={"aadhaar_number": kyc_mod.SANDBOX_TEST_AADHAAR, "otp": "0000"}
))
assert kyc_result["identity_verified"] is True

open_runs = step("collector: list open runs", collector_client.get("/runs/open"))
assert any(r["id"] == run_id for r in open_runs), "our run should be in open runs"

accept = step("collector: accept run", collector_client.post(
    f"/runs/{run_id}/accept", json={"collector_id": collector_id}
))

stops = step("collector: get run stops", collector_client.get(f"/runs/{run_id}/stops"))
assert len(stops) == 3, f"expected 3 stops, got {len(stops)}"

# 5. pickup-service: log all 3 pickups, then complete the run
for stop in stops:
    step(f"pickup: log pickup for {stop['stop_name']}", pickup_client.post(
        f"/runs/{run_id}/pickups",
        json={"posting_id": stop["posting_id"], "actual_weight_kg": stop["est_weight_kg"], "photo_url": "https://example.com/photo.jpg"}
    ))

complete = step("pickup: complete run", pickup_client.post(f"/runs/{run_id}/complete"))
assert complete["status"] == "completed"

# 6. data-layer-service: check the aggregated report
report = step("data-layer: cluster report", data_client.get(f"/reports/cluster/{cluster_id}"))
plastic_total = next(t for t in report["totals"] if t["category"] == "plastic")
assert plastic_total["total_weight_kg"] == 240, f"expected 240kg total, got {plastic_total['total_weight_kg']}"
assert plastic_total["pickup_count"] == 3

region = step("data-layer: region report", data_client.get("/reports/region"))

# 7. corporate-service: onboard a GST-verified corporate, schedule a DIRECT
#    pickup (bypasses quota entirely), collector picks it up, corporate
#    pulls its own scoped ESG report
import gst as gst_mod
corp = step("corporate: onboard (GST-verified)", corporate_client.post(
    "/corporates",
    json={"name": "GreenPack Industries", "gstin": gst_mod.SANDBOX_TEST_GSTIN, "phone": "9888888888", "geo_cluster_id": cluster_id},
))
corp_id = corp["id"]

pickup_req = step("corporate: schedule direct pickup (150kg metal, no quota wait)", corporate_client.post(
    f"/corporates/{corp_id}/pickups", json={"category_name": "metal", "est_weight_kg": 150}
))
corp_run_id = pickup_req["run_id"]

corp_open_runs = step("collector: list open runs (should include the corporate run)", collector_client.get("/runs/open"))
assert any(r["id"] == corp_run_id for r in corp_open_runs)

step("collector: accept corporate run", collector_client.post(
    f"/runs/{corp_run_id}/accept", json={"collector_id": collector_id}
))
corp_stops = step("collector: get corporate run stops", collector_client.get(f"/runs/{corp_run_id}/stops"))
assert len(corp_stops) == 1 and "GreenPack" in corp_stops[0]["stop_name"]

step("pickup: log corporate pickup", pickup_client.post(
    f"/runs/{corp_run_id}/pickups",
    json={"posting_id": corp_stops[0]["posting_id"], "actual_weight_kg": 150, "photo_url": "https://example.com/corp.jpg"},
))
step("pickup: complete corporate run", pickup_client.post(f"/runs/{corp_run_id}/complete"))

corp_report = step("corporate: own ESG report (scoped, not mixed with household pickups)", corporate_client.get(
    f"/corporates/{corp_id}/report"
))
metal_total = next(t for t in corp_report if t["category"] == "metal")
assert metal_total["total_weight_kg"] == 150, f"expected 150kg, got {metal_total['total_weight_kg']}"
assert metal_total["pickup_count"] == 1

print("\n" + "=" * 60)
print("ALL STEPS PASSED — full flow works end-to-end")
print("=" * 60)
