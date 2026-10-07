"""
pickup-service
---------------
Logs completed pickups. Each transaction is hash-chained to the previous one
(SHA-256) so the record can't be silently altered later -- this is what makes
the future ESG/compliance reporting credible.

Run: uvicorn main:app --reload --port 8004
"""

import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
from db import (
    init_db, get_session, Run, Posting, Transaction, WasteCategory
)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="REACH pickup-service")

# Browsers block the Next.js apps (ports 3001/3002) from calling these APIs
# unless CORS allows them. Override with REACH_CORS_ORIGINS="https://a.com,https://b.com" in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("REACH_CORS_ORIGINS", "http://localhost:3001,http://localhost:3002").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()


def compute_hash(prev_hash: str, run_id: str, posting_id: str, weight: float, amount: float) -> str:
    payload = f"{prev_hash or ''}|{run_id}|{posting_id}|{weight}|{amount}"
    return hashlib.sha256(payload.encode()).hexdigest()


class PickupIn(BaseModel):
    posting_id: str
    actual_weight_kg: float
    photo_url: Optional[str] = None


class PickupOut(BaseModel):
    transaction_id: str
    amount_paid: float
    hash: str


@app.post("/runs/{run_id}/pickups", response_model=PickupOut)
def log_pickup(run_id: str, body: PickupIn):
    db = get_session()
    run = db.query(Run).filter_by(id=run_id).first()
    if not run:
        db.close()
        raise HTTPException(status_code=404, detail="Run not found")

    posting = db.query(Posting).filter_by(id=body.posting_id).first()
    if not posting:
        db.close()
        raise HTTPException(status_code=404, detail="Posting not found")

    category = db.query(WasteCategory).filter_by(id=run.category_id).first()
    amount_paid = round(body.actual_weight_kg * category.rate_per_kg, 2)

    last_txn = db.query(Transaction).order_by(Transaction.created_at.desc()).first()
    prev_hash = last_txn.hash if last_txn else None
    new_hash = compute_hash(prev_hash, run_id, body.posting_id, body.actual_weight_kg, amount_paid)

    txn = Transaction(
        run_id=run_id,
        posting_id=body.posting_id,
        actual_weight_kg=body.actual_weight_kg,
        amount_paid=amount_paid,
        photo_url=body.photo_url,
        prev_hash=prev_hash,
        hash=new_hash,
    )
    db.add(txn)
    posting.status = "collected"
    db.commit()
    db.refresh(txn)
    db.close()
    return PickupOut(transaction_id=txn.id, amount_paid=amount_paid, hash=new_hash)


@app.post("/runs/{run_id}/complete")
def complete_run(run_id: str):
    db = get_session()
    run = db.query(Run).filter_by(id=run_id).first()
    if not run:
        db.close()
        raise HTTPException(status_code=404, detail="Run not found")

    remaining = db.query(Posting).filter_by(
        geo_cluster_id=run.geo_cluster_id, category_id=run.category_id, status="assigned"
    ).count()
    if remaining > 0:
        db.close()
        raise HTTPException(
            status_code=400,
            detail=f"{remaining} posting(s) not yet picked up — log them before completing the run",
        )

    run.status = "completed"
    from datetime import datetime
    run.completed_at = datetime.utcnow()
    db.commit()
    db.close()
    return {"id": run_id, "status": "completed"}
