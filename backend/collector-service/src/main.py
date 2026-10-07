"""
collector-service
------------------
Collectors see open runs (clusters that crossed quota), accept one, and get
the stop list (which postings/houses to visit, how much each has).

Run: uvicorn main:app --reload --port 8003
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
from db import (
    init_db, get_session, Run, Collector, GeoCluster, WasteCategory, Posting, Generator, OtpSession
)
import otp as otp_module
import kyc as kyc_module

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="REACH collector-service")

# Browsers block the Next.js apps (ports 3001/3002) from calling these APIs
# unless CORS allows them. Override with REACH_CORS_ORIGINS="https://a.com,https://b.com" in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("REACH_CORS_ORIGINS", "http://localhost:3001,http://localhost:3002").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()


class RequestOtpIn(BaseModel):
    phone: str


@app.post("/collectors/request-otp")
def request_otp(body: RequestOtpIn):
    db = get_session()
    code = otp_module.generate_and_send(body.phone)
    session = OtpSession(phone=body.phone, code=code)
    db.add(session)
    db.commit()
    db.refresh(session)
    db.close()
    return {"otp_session_id": session.id}


class VerifyOtpIn(BaseModel):
    otp_session_id: str
    code: str


@app.post("/collectors/verify-otp")
def verify_otp(body: VerifyOtpIn):
    db = get_session()
    session = db.query(OtpSession).filter_by(id=body.otp_session_id).first()
    if not session:
        db.close()
        raise HTTPException(status_code=404, detail="OTP session not found")
    ok = otp_module.verify(session.phone, body.code, expected_code=session.code)
    if ok:
        session.verified = True
        db.commit()
    db.close()
    if not ok:
        raise HTTPException(status_code=400, detail="Incorrect OTP")
    return {"verified": True}


class CollectorIn(BaseModel):
    name: str
    phone: str
    otp_session_id: str


@app.post("/collectors")
def create_collector(body: CollectorIn):
    db = get_session()
    session = db.query(OtpSession).filter_by(id=body.otp_session_id, phone=body.phone).first()
    if not session or not session.verified:
        db.close()
        raise HTTPException(status_code=400, detail="Phone not verified — call /collectors/request-otp and /collectors/verify-otp first")

    # `verified` here means phone-verified (OTP). Identity/KYC verification
    # (Aadhaar eKYC via Setu) is a separate step -- see /collectors/{id}/kyc/*.
    c = Collector(name=body.name, phone=body.phone, verified=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    db.close()
    return {"id": c.id, "name": c.name}


class KycInitiateIn(BaseModel):
    aadhaar_number: str


@app.post("/collectors/{collector_id}/kyc/initiate")
def kyc_initiate(collector_id: str, body: KycInitiateIn):
    db = get_session()
    c = db.query(Collector).filter_by(id=collector_id).first()
    if not c:
        db.close()
        raise HTTPException(status_code=404, detail="Collector not found")
    try:
        reference_id = kyc_module.initiate_ekyc(body.aadhaar_number)
    except kyc_module.KycError as e:
        db.close()
        raise HTTPException(status_code=502, detail=str(e))
    c.kyc_reference_id = reference_id
    db.commit()
    db.close()
    return {"kyc_reference_id": reference_id}


class KycVerifyIn(BaseModel):
    aadhaar_number: str
    otp: str


@app.post("/collectors/{collector_id}/kyc/verify")
def kyc_verify(collector_id: str, body: KycVerifyIn):
    db = get_session()
    c = db.query(Collector).filter_by(id=collector_id).first()
    if not c or not c.kyc_reference_id:
        db.close()
        raise HTTPException(status_code=400, detail="Call /kyc/initiate first")
    try:
        result = kyc_module.verify_ekyc(c.kyc_reference_id, body.aadhaar_number, body.otp)
    except kyc_module.KycError as e:
        db.close()
        raise HTTPException(status_code=502, detail=str(e))
    if not result["verified"]:
        db.close()
        raise HTTPException(status_code=400, detail="Aadhaar eKYC verification failed")
    c.identity_verified = True
    c.kyc_verified_name = result["name"]
    db.commit()
    db.close()
    return {"identity_verified": True, "kyc_verified_name": result["name"]}


class OpenRunOut(BaseModel):
    id: str
    cluster_name: str
    category: str
    status: str


@app.get("/runs/open", response_model=list[OpenRunOut])
def open_runs():
    db = get_session()
    runs = db.query(Run).filter_by(status="open").all()
    out = []
    for r in runs:
        cluster = db.query(GeoCluster).filter_by(id=r.geo_cluster_id).first()
        category = db.query(WasteCategory).filter_by(id=r.category_id).first()
        out.append(OpenRunOut(
            id=r.id, cluster_name=cluster.name, category=category.name, status=r.status
        ))
    db.close()
    return out


class AcceptIn(BaseModel):
    collector_id: str


@app.post("/runs/{run_id}/accept")
def accept_run(run_id: str, body: AcceptIn):
    db = get_session()
    run = db.query(Run).filter_by(id=run_id).first()
    if not run:
        db.close()
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "open":
        db.close()
        raise HTTPException(status_code=400, detail=f"Run is not open (status={run.status})")
    if not db.query(Collector).filter_by(id=body.collector_id).first():
        db.close()
        raise HTTPException(status_code=404, detail="Unknown collector")
    collector = db.query(Collector).filter_by(id=body.collector_id).first()
    if not collector.identity_verified:
        db.close()
        raise HTTPException(
            status_code=403,
            detail="Collector identity not verified — complete /collectors/{id}/kyc/initiate and /kyc/verify first",
        )

    run.collector_id = body.collector_id
    run.status = "accepted"
    db.commit()
    db.close()
    return {"id": run_id, "status": "accepted"}


class StopOut(BaseModel):
    posting_id: str
    stop_name: str
    est_weight_kg: float


@app.get("/runs/{run_id}/stops", response_model=list[StopOut])
def run_stops(run_id: str):
    db = get_session()
    run = db.query(Run).filter_by(id=run_id).first()
    if not run:
        db.close()
        raise HTTPException(status_code=404, detail="Run not found")

    postings = db.query(Posting).filter_by(
        geo_cluster_id=run.geo_cluster_id, category_id=run.category_id, status="assigned"
    ).all()
    out = []
    for p in postings:
        if p.generator_id:
            gen = db.query(Generator).filter_by(id=p.generator_id).first()
            stop_name = gen.name if gen else "Unknown generator"
        elif p.corporate_id:
            from db import Corporate
            corp = db.query(Corporate).filter_by(id=p.corporate_id).first()
            stop_name = f"{corp.name} (corporate)" if corp else "Unknown corporate"
        else:
            stop_name = "Unknown"
        out.append(StopOut(posting_id=p.id, stop_name=stop_name, est_weight_kg=p.est_weight_kg))
    db.close()
    return out
