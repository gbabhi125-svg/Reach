"""
shared/db.py
------------
Single SQLite file used by ALL services for local development/testing.
In production this maps 1:1 onto db/schema.sql running on real Postgres+PostGIS —
this file exists so we can actually run and test the full flow end-to-end
without standing up a Postgres server first.
"""

from sqlalchemy import (
    create_engine, Column, String, Float, DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import uuid
import os

DEFAULT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "reach_dev.db"))
DB_PATH = os.environ.get("REACH_DB_PATH", DEFAULT_DB_PATH)
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def uid():
    return str(uuid.uuid4())


class GeoCluster(Base):
    __tablename__ = "geo_clusters"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)


class WasteCategory(Base):
    __tablename__ = "waste_categories"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, unique=True, nullable=False)
    quota_kg = Column(Float, nullable=False)
    rate_per_kg = Column(Float, nullable=False)


class Generator(Base):
    __tablename__ = "generators"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    geo_cluster_id = Column(String, ForeignKey("geo_clusters.id"), nullable=False)


class Collector(Base):
    __tablename__ = "collectors"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    verified = Column(Boolean, default=False)          # phone verified (OTP)
    identity_verified = Column(Boolean, default=False)  # Aadhaar eKYC verified
    kyc_reference_id = Column(String, nullable=True)
    kyc_verified_name = Column(String, nullable=True)   # name as per Aadhaar, for cross-check


class Corporate(Base):
    __tablename__ = "corporates"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    gstin = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    geo_cluster_id = Column(String, ForeignKey("geo_clusters.id"), nullable=False)
    gst_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Posting(Base):
    __tablename__ = "postings"
    id = Column(String, primary_key=True, default=uid)
    generator_id = Column(String, ForeignKey("generators.id"), nullable=True)   # one of generator_id / corporate_id is set
    corporate_id = Column(String, ForeignKey("corporates.id"), nullable=True)
    geo_cluster_id = Column(String, ForeignKey("geo_clusters.id"), nullable=False)
    category_id = Column(String, ForeignKey("waste_categories.id"), nullable=False)
    est_weight_kg = Column(Float, nullable=False)
    status = Column(String, default="listed")  # listed | assigned | collected
    created_at = Column(DateTime, default=datetime.utcnow)


class Run(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True, default=uid)
    geo_cluster_id = Column(String, ForeignKey("geo_clusters.id"), nullable=False)
    category_id = Column(String, ForeignKey("waste_categories.id"), nullable=False)
    collector_id = Column(String, ForeignKey("collectors.id"), nullable=True)
    status = Column(String, default="open")  # open | accepted | completed
    triggered_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class OtpSession(Base):
    __tablename__ = "otp_sessions"
    id = Column(String, primary_key=True, default=uid)
    phone = Column(String, nullable=False)
    code = Column(String, nullable=False)   # only meaningful in mock mode; MSG91 verifies server-side in prod
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, default=uid)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    posting_id = Column(String, ForeignKey("postings.id"), nullable=False)
    actual_weight_kg = Column(Float, nullable=False)
    amount_paid = Column(Float, nullable=False)
    photo_url = Column(String, nullable=True)
    prev_hash = Column(String, nullable=True)
    hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db(fresh=False):
    if fresh and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
