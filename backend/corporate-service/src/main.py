"""
corporate-service
-------------------
Companies onboard with a GST-verified account, schedule direct high-volume
pickups (bypasses the household quota model -- a corporate generates enough
on its own to justify a dedicated run), and pull ESG/compliance reports
tied to their own pickups only.

Run: uvicorn main:app --reload --port 8006
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
from db import (
    init_db, get_session, Corporate, GeoCluster, WasteCategory, Posting, Run, Transaction
)
import gst as gst_module

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func

app = FastAPI(title="REACH corporate-service")

# Browsers block the Next.js apps (ports 3001/3002) from calling these APIs
# unless CORS allows them. Override with REACH_CORS_ORIGINS="https://a.com,https://b.com" in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("REACH_CORS_ORIGINS", "http://localhost:3001,http://localhost:3002").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()


class CorporateIn(BaseModel):
    name: str
    gstin: str
    phone: str
    geo_cluster_id: str


@app.post("/corporates")
def create_corporate(body: CorporateIn):
    db = get_session()
    if not db.query(GeoCluster).filter_by(id=body.geo_cluster_id).first():
        db.close()
        raise HTTPException(status_code=404, detail="Unknown geo cluster")

    try:
        result = gst_module.verify_gstin(body.gstin)
    except gst_module.GstError as e:
        db.close()
        raise HTTPException(status_code=502, detail=str(e))

    if not result["valid"]:
        db.close()
        raise HTTPException(status_code=400, detail="GSTIN could not be verified")

    corp = Corporate(
        name=body.name,
        gstin=body.gstin,
        phone=body.phone,
        geo_cluster_id=body.geo_cluster_id,
        gst_verified=True,
    )
    db.add(corp)
    db.commit()
    db.refresh(corp)
    db.close()
    return {"id": corp.id, "name": corp.name, "legal_name": result["legal_name"]}


class PickupRequestIn(BaseModel):
    category_name: str
    est_weight_kg: float


class PickupRequestOut(BaseModel):
    posting_id: str
    run_id: str


@app.post("/corporates/{corporate_id}/pickups", response_model=PickupRequestOut)
def schedule_pickup(corporate_id: str, body: PickupRequestIn):
    """Direct pickup request -- bypasses the quota model entirely. Every
    request opens its own run immediately, no aggregation/waiting."""
    db = get_session()
    corp = db.query(Corporate).filter_by(id=corporate_id).first()
    if not corp or not corp.gst_verified:
        db.close()
        raise HTTPException(status_code=403, detail="Corporate account not found or not GST-verified")

    category = db.query(WasteCategory).filter_by(name=body.category_name).first()
    if not category:
        db.close()
        raise HTTPException(status_code=404, detail="Unknown waste category")

    posting = Posting(
        corporate_id=corporate_id,
        geo_cluster_id=corp.geo_cluster_id,
        category_id=category.id,
        est_weight_kg=body.est_weight_kg,
        status="assigned",  # skips "listed" -- no quota wait for corporates
    )
    db.add(posting)

    run = Run(
        geo_cluster_id=corp.geo_cluster_id,
        category_id=category.id,
        status="open",
    )
    db.add(run)
    db.commit()
    db.refresh(posting)
    db.refresh(run)
    db.close()
    return PickupRequestOut(posting_id=posting.id, run_id=run.id)


class CategoryTotal(BaseModel):
    category: str
    total_weight_kg: float
    total_amount_paid: float
    pickup_count: int


@app.get("/corporates/{corporate_id}/report", response_model=list[CategoryTotal])
def corporate_report(corporate_id: str):
    """ESG/compliance report scoped to ONLY this corporate's own pickups --
    the data-layer-service's cluster/region reports mix everyone in the
    area, which isn't what a company needs for its own compliance filing."""
    db = get_session()
    rows = (
        db.query(
            WasteCategory.name,
            func.sum(Transaction.actual_weight_kg),
            func.sum(Transaction.amount_paid),
            func.count(Transaction.id),
        )
        .join(Posting, Posting.id == Transaction.posting_id)
        .join(WasteCategory, WasteCategory.id == Posting.category_id)
        .filter(Posting.corporate_id == corporate_id)
        .group_by(WasteCategory.name)
        .all()
    )
    db.close()
    return [
        CategoryTotal(category=r[0], total_weight_kg=r[1] or 0, total_amount_paid=r[2] or 0, pickup_count=r[3])
        for r in rows
    ]
