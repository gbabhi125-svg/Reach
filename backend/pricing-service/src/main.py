"""
pricing-service
----------------
Owns the transparent rate card (rupees/kg) and quota thresholds (kg) per
waste category. Every other service reads from here so generators and
collectors always see the same number.

Run: uvicorn main:app --reload --port 8001
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
from db import init_db, get_session, WasteCategory as WasteCategoryModel

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="REACH pricing-service")

# Browsers block the Next.js apps (ports 3001/3002) from calling these APIs
# unless CORS allows them. Override with REACH_CORS_ORIGINS="https://a.com,https://b.com" in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("REACH_CORS_ORIGINS", "http://localhost:3001,http://localhost:3002").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# STARTING-POINT figures based on published household-level kabadiwala rates
# (city blogs / online scrap-buyer listings, late 2025/2026) -- NOT a substitute
# for confirming with your actual pilot village's local dealer. Real rates vary
# by city, material grade, and change often; these just replace guesswork with
# a realistic starting range.
#   - plastic: household rates run roughly ₹4-35/kg depending on grade (PET/HDPE
#     vs mixed/low-grade) -- 15 picked as a rough mid-point for MIXED plastic
#   - metal: iron/steel household rates run roughly ₹20-60/kg depending on
#     grade -- 30 picked as a conservative mid-point (mixed household metal,
#     not clean industrial scrap, which sells higher)
#   - paper: household rates run roughly ₹1-9/kg depending on type (newspaper
#     highest, mixed waste paper lowest) -- 8 kept close to the newspaper end
#     since that's the most common household paper waste
#   - e-waste: no reliable published household-rate source found -- this
#     number is STILL a guess and needs direct confirmation more than any
#     other category
DEFAULT_CATEGORIES = [
    {"name": "plastic", "quota_kg": 200, "rate_per_kg": 15},
    {"name": "metal", "quota_kg": 100, "rate_per_kg": 30},
    {"name": "paper", "quota_kg": 150, "rate_per_kg": 8},
    {"name": "e-waste", "quota_kg": 25, "rate_per_kg": 60},
]


def seed():
    init_db()
    db = get_session()
    if db.query(WasteCategoryModel).count() == 0:
        for c in DEFAULT_CATEGORIES:
            db.add(WasteCategoryModel(**c))
        db.commit()
    db.close()


seed()


class WasteCategoryOut(BaseModel):
    id: str
    name: str
    quota_kg: float
    rate_per_kg: float

    class Config:
        from_attributes = True


@app.get("/categories", response_model=list[WasteCategoryOut])
def list_categories():
    db = get_session()
    result = db.query(WasteCategoryModel).all()
    db.close()
    return result


@app.get("/categories/{name}", response_model=WasteCategoryOut)
def get_category(name: str):
    db = get_session()
    category = db.query(WasteCategoryModel).filter_by(name=name).first()
    db.close()
    if not category:
        raise HTTPException(status_code=404, detail="Unknown waste category")
    return category


class RateUpdate(BaseModel):
    rate_per_kg: Optional[float] = None
    quota_kg: Optional[float] = None


@app.patch("/categories/{name}", response_model=WasteCategoryOut)
def update_category(name: str, update: RateUpdate):
    db = get_session()
    category = db.query(WasteCategoryModel).filter_by(name=name).first()
    if not category:
        db.close()
        raise HTTPException(status_code=404, detail="Unknown waste category")
    if update.rate_per_kg is not None:
        category.rate_per_kg = update.rate_per_kg
    if update.quota_kg is not None:
        category.quota_kg = update.quota_kg
    db.commit()
    db.refresh(category)
    db.close()
    return category
