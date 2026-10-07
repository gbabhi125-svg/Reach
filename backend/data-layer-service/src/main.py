"""
data-layer-service
--------------------
Aggregates completed transactions into reportable waste-flow data -- this is
the long-term product for municipal corporations and corporate ESG reporting.

Run: uvicorn main:app --reload --port 8005
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
from db import init_db, get_session, Transaction, Run, WasteCategory, GeoCluster

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func

app = FastAPI(title="REACH data-layer-service")

# Browsers block the Next.js apps (ports 3001/3002) from calling these APIs
# unless CORS allows them. Override with REACH_CORS_ORIGINS="https://a.com,https://b.com" in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("REACH_CORS_ORIGINS", "http://localhost:3001,http://localhost:3002").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()


class CategoryTotal(BaseModel):
    category: str
    total_weight_kg: float
    total_amount_paid: float
    pickup_count: int


class ClusterReport(BaseModel):
    cluster_name: str
    totals: list[CategoryTotal]


@app.get("/reports/cluster/{cluster_id}", response_model=ClusterReport)
def cluster_report(cluster_id: str):
    db = get_session()
    cluster = db.query(GeoCluster).filter_by(id=cluster_id).first()

    rows = (
        db.query(
            WasteCategory.name,
            func.sum(Transaction.actual_weight_kg),
            func.sum(Transaction.amount_paid),
            func.count(Transaction.id),
        )
        .join(Run, Run.id == Transaction.run_id)
        .join(WasteCategory, WasteCategory.id == Run.category_id)
        .filter(Run.geo_cluster_id == cluster_id)
        .group_by(WasteCategory.name)
        .all()
    )
    totals = [
        CategoryTotal(category=r[0], total_weight_kg=r[1] or 0, total_amount_paid=r[2] or 0, pickup_count=r[3])
        for r in rows
    ]
    db.close()
    return ClusterReport(cluster_name=cluster.name if cluster else "unknown", totals=totals)


@app.get("/reports/region", response_model=list[CategoryTotal])
def region_report():
    db = get_session()
    rows = (
        db.query(
            WasteCategory.name,
            func.sum(Transaction.actual_weight_kg),
            func.sum(Transaction.amount_paid),
            func.count(Transaction.id),
        )
        .join(Run, Run.id == Transaction.run_id)
        .join(WasteCategory, WasteCategory.id == Run.category_id)
        .group_by(WasteCategory.name)
        .all()
    )
    db.close()
    return [
        CategoryTotal(category=r[0], total_weight_kg=r[1] or 0, total_amount_paid=r[2] or 0, pickup_count=r[3])
        for r in rows
    ]
