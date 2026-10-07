"""
generator-service
------------------
Generators post waste. Tracks running quota progress per (geo_cluster, category).
When a cluster crosses quota for a category, opens a run in collector-service.

Run: uvicorn main:app --reload --port 8002
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
from db import (
    init_db, get_session, GeoCluster, WasteCategory, Generator, Posting, Run, OtpSession
)
from geocode import geocode_village, GeocodeError
import otp as otp_module

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func

app = FastAPI(title="REACH generator-service")

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


@app.post("/generators/request-otp")
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


@app.post("/generators/verify-otp")
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


class PostingIn(BaseModel):
    generator_id: str
    geo_cluster_id: str
    category_name: str
    est_weight_kg: float


class PostingOut(BaseModel):
    id: str
    status: str
    quota_progress_kg: float
    quota_kg: float
    quota_crossed: bool
    run_id: str | None = None


@app.post("/postings", response_model=PostingOut)
def create_posting(body: PostingIn):
    db = get_session()

    category = db.query(WasteCategory).filter_by(name=body.category_name).first()
    if not category:
        db.close()
        raise HTTPException(status_code=404, detail="Unknown waste category")

    generator = db.query(Generator).filter_by(id=body.generator_id).first()
    if not generator:
        db.close()
        raise HTTPException(status_code=404, detail="Unknown generator")

    cluster = db.query(GeoCluster).filter_by(id=body.geo_cluster_id).first()
    if not cluster:
        db.close()
        raise HTTPException(status_code=404, detail="Unknown geo cluster")

    posting = Posting(
        generator_id=body.generator_id,
        geo_cluster_id=body.geo_cluster_id,
        category_id=category.id,
        est_weight_kg=body.est_weight_kg,
        status="listed",
    )
    db.add(posting)
    db.commit()

    # sum all "listed" postings for this cluster+category not yet part of a run
    total = (
        db.query(func.sum(Posting.est_weight_kg))
        .filter_by(geo_cluster_id=body.geo_cluster_id, category_id=category.id, status="listed")
        .scalar()
    ) or 0.0

    run_id = None
    quota_crossed = total >= category.quota_kg
    if quota_crossed:
        # is there already an open run for this cluster+category? reuse it.
        existing_run = (
            db.query(Run)
            .filter_by(geo_cluster_id=body.geo_cluster_id, category_id=category.id, status="open")
            .first()
        )
        if not existing_run:
            existing_run = Run(
                geo_cluster_id=body.geo_cluster_id,
                category_id=category.id,
                status="open",
            )
            db.add(existing_run)
            db.commit()
            db.refresh(existing_run)

        # attach every listed posting in this cluster/category to the run
        db.query(Posting).filter_by(
            geo_cluster_id=body.geo_cluster_id, category_id=category.id, status="listed"
        ).update({"status": "assigned"})
        db.commit()
        run_id = existing_run.id

    db.refresh(posting)
    result = PostingOut(
        id=posting.id,
        status=posting.status if not quota_crossed else "assigned",
        quota_progress_kg=total,
        quota_kg=category.quota_kg,
        quota_crossed=quota_crossed,
        run_id=run_id,
    )
    db.close()
    return result


class QuotaProgressOut(BaseModel):
    category: str
    progress_kg: float
    quota_kg: float
    percent: float


@app.get("/clusters/{cluster_id}/quota-progress", response_model=list[QuotaProgressOut])
def quota_progress(cluster_id: str):
    db = get_session()
    categories = db.query(WasteCategory).all()
    out = []
    for cat in categories:
        total = (
            db.query(func.sum(Posting.est_weight_kg))
            .filter_by(geo_cluster_id=cluster_id, category_id=cat.id, status="listed")
            .scalar()
        ) or 0.0
        out.append(QuotaProgressOut(
            category=cat.name,
            progress_kg=total,
            quota_kg=cat.quota_kg,
            percent=round(100 * total / cat.quota_kg, 1) if cat.quota_kg else 0,
        ))
    db.close()
    return out


class GeneratorIn(BaseModel):
    name: str
    phone: str
    geo_cluster_id: str
    otp_session_id: str


@app.post("/generators")
def create_generator(body: GeneratorIn):
    db = get_session()
    if not db.query(GeoCluster).filter_by(id=body.geo_cluster_id).first():
        db.close()
        raise HTTPException(status_code=404, detail="Unknown geo cluster")

    session = db.query(OtpSession).filter_by(id=body.otp_session_id, phone=body.phone).first()
    if not session or not session.verified:
        db.close()
        raise HTTPException(status_code=400, detail="Phone not verified — call /generators/request-otp and /generators/verify-otp first")

    gen = Generator(name=body.name, phone=body.phone, geo_cluster_id=body.geo_cluster_id)
    db.add(gen)
    db.commit()
    db.refresh(gen)
    db.close()
    return {"id": gen.id, "name": gen.name}


class ClusterIn(BaseModel):
    name: str
    lat: float | None = None   # optional override; auto-geocoded from `name` if omitted
    lng: float | None = None


@app.post("/clusters")
def create_cluster(body: ClusterIn):
    db = get_session()
    lat, lng = body.lat, body.lng
    if lat is None or lng is None:
        try:
            lat, lng = geocode_village(body.name)
        except GeocodeError as e:
            db.close()
            raise HTTPException(status_code=422, detail=f"Could not geocode '{body.name}': {e}. Pass lat/lng manually instead.")
    cluster = GeoCluster(name=body.name, lat=lat, lng=lng)
    db.add(cluster)
    db.commit()
    db.refresh(cluster)
    db.close()
    return {"id": cluster.id, "name": cluster.name, "lat": cluster.lat, "lng": cluster.lng}
