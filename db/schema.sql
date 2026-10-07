-- REACH production schema (PostgreSQL + PostGIS)
-- Mirrors backend/shared/db.py (the SQLite dev models). Keep the two in sync.
-- Local dev does NOT need this file — run_all.py creates a SQLite DB automatically.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

CREATE TABLE geo_clusters (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lng         DOUBLE PRECISION NOT NULL,
    center      GEOGRAPHY(POINT, 4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography) STORED
);

CREATE TABLE waste_categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    quota_kg    NUMERIC NOT NULL,
    rate_per_kg NUMERIC NOT NULL
);

CREATE TABLE generators (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    phone           TEXT NOT NULL,
    geo_cluster_id  UUID NOT NULL REFERENCES geo_clusters(id)
);

CREATE TABLE collectors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    phone               TEXT NOT NULL,
    verified            BOOLEAN NOT NULL DEFAULT false,   -- phone verified (OTP)
    identity_verified   BOOLEAN NOT NULL DEFAULT false,   -- Aadhaar eKYC verified
    kyc_reference_id    TEXT,
    kyc_verified_name   TEXT                              -- name as per Aadhaar
);

CREATE TABLE corporates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    gstin           TEXT NOT NULL,
    phone           TEXT NOT NULL,
    geo_cluster_id  UUID NOT NULL REFERENCES geo_clusters(id),
    gst_verified    BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE otp_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone       TEXT NOT NULL,
    code        TEXT NOT NULL DEFAULT '',   -- only populated in mock mode; MSG91 verifies server-side in prod
    verified    BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Exactly one of generator_id / corporate_id is set
CREATE TABLE postings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generator_id    UUID REFERENCES generators(id),
    corporate_id    UUID REFERENCES corporates(id),
    geo_cluster_id  UUID NOT NULL REFERENCES geo_clusters(id),
    category_id     UUID NOT NULL REFERENCES waste_categories(id),
    est_weight_kg   NUMERIC NOT NULL,
    status          TEXT NOT NULL DEFAULT 'listed',   -- listed | assigned | collected
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((generator_id IS NOT NULL) <> (corporate_id IS NOT NULL))
);

CREATE TABLE runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    geo_cluster_id  UUID NOT NULL REFERENCES geo_clusters(id),
    category_id     UUID NOT NULL REFERENCES waste_categories(id),
    collector_id    UUID REFERENCES collectors(id),
    status          TEXT NOT NULL DEFAULT 'open',     -- open | accepted | completed
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE transactions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL REFERENCES runs(id),
    posting_id          UUID NOT NULL REFERENCES postings(id),
    actual_weight_kg    NUMERIC NOT NULL,
    amount_paid         NUMERIC NOT NULL,
    photo_url           TEXT,
    prev_hash           TEXT,
    hash                TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_postings_cluster_category_status ON postings(geo_cluster_id, category_id, status);
CREATE INDEX idx_runs_cluster_status ON runs(geo_cluster_id, status);
CREATE INDEX idx_transactions_posting ON transactions(posting_id);
CREATE INDEX idx_geo_clusters_center ON geo_clusters USING GIST (center);
