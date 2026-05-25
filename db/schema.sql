-- SmartIntake PostgreSQL Schema
-- Run via: psql -U smartintake -d smartintake -f schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- for fuzzy search

-- ─── Enum types ────────────────────────────────────────────────────────────────

CREATE TYPE lead_tier AS ENUM ('hot', 'warm', 'cold', 'disqualified');
CREATE TYPE assignment_status AS ENUM ('pending', 'sent', 'acknowledged', 'converted', 'lost');
CREATE TYPE event_type AS ENUM (
  'lead_received', 'features_extracted', 'scored', 'rep_assigned',
  'sms_sent', 'drift_detected', 'model_promoted', 'retrain_triggered'
);

-- ─── Sales reps ────────────────────────────────────────────────────────────────

CREATE TABLE reps (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        TEXT NOT NULL,
  phone       TEXT NOT NULL,           -- E.164 format (+1...)
  email       TEXT NOT NULL UNIQUE,
  tier_focus  lead_tier[] DEFAULT '{hot,warm}',
  is_active   BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Leads ─────────────────────────────────────────────────────────────────────

CREATE TABLE leads (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  external_id   TEXT UNIQUE,            -- caller-supplied idempotency key
  email         TEXT NOT NULL,
  name          TEXT,
  company       TEXT,
  phone         TEXT,
  website       TEXT,
  source        TEXT DEFAULT 'web',     -- utm_source or channel
  raw_payload   JSONB NOT NULL,         -- full form submission
  ip_address    INET,
  user_agent    TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_leads_email       ON leads (email);
CREATE INDEX idx_leads_created_at  ON leads (created_at DESC);
CREATE INDEX idx_leads_source      ON leads (source);

-- ─── Extracted features ────────────────────────────────────────────────────────

CREATE TABLE lead_features (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id               UUID NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
  -- Company signals
  company_size_bucket   SMALLINT,        -- 0=solo,1=2-10,2=11-50,3=51-200,4=200+
  has_website           BOOLEAN,
  domain_age_days       INTEGER,
  is_free_email         BOOLEAN,
  -- Behavioral signals
  source_score          FLOAT,           -- organic=1.0, paid=0.8, referral=0.9 …
  time_on_site_s        INTEGER,
  pages_visited         SMALLINT,
  -- Firmographic signals (enriched async)
  linkedin_employees    INTEGER,
  funding_stage         SMALLINT,        -- 0=none,1=seed,2=series-a,…
  industry_code         SMALLINT,
  -- Derived
  email_domain          TEXT,
  submission_hour       SMALLINT,        -- 0-23 local
  submission_dow        SMALLINT,        -- 0=Mon,6=Sun
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (lead_id)
);

-- ─── ML predictions ────────────────────────────────────────────────────────────

CREATE TABLE predictions (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id         UUID NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
  model_name      TEXT NOT NULL,
  model_version   TEXT NOT NULL,
  score           FLOAT NOT NULL CHECK (score BETWEEN 0 AND 1),
  tier            lead_tier NOT NULL,
  shap_values     JSONB,               -- {feature: shap_value}
  top_factors     JSONB,               -- [{feature, value, shap, direction}]
  latency_ms      INTEGER,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (lead_id)                     -- one active prediction per lead
);

CREATE INDEX idx_predictions_score ON predictions (score DESC);
CREATE INDEX idx_predictions_tier  ON predictions (tier);

-- ─── Rep assignments ───────────────────────────────────────────────────────────

CREATE TABLE rep_assignments (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id     UUID NOT NULL REFERENCES leads (id),
  rep_id      UUID NOT NULL REFERENCES reps (id),
  status      assignment_status DEFAULT 'pending',
  sms_sid     TEXT,                    -- Twilio message SID
  notes       TEXT,
  assigned_at TIMESTAMPTZ DEFAULT NOW(),
  ack_at      TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_assignments_rep    ON rep_assignments (rep_id, assigned_at DESC);
CREATE INDEX idx_assignments_status ON rep_assignments (status);

-- ─── Audit / event log ─────────────────────────────────────────────────────────

CREATE TABLE audit_events (
  id          BIGSERIAL PRIMARY KEY,
  lead_id     UUID REFERENCES leads (id),
  event       event_type NOT NULL,
  payload     JSONB,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_lead      ON audit_events (lead_id, created_at DESC);
CREATE INDEX idx_audit_event     ON audit_events (event, created_at DESC);

-- ─── Drift snapshots ───────────────────────────────────────────────────────────

CREATE TABLE drift_snapshots (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  window_start    TIMESTAMPTZ NOT NULL,
  window_end      TIMESTAMPTZ NOT NULL,
  psi_score       FLOAT NOT NULL,       -- Population Stability Index
  ks_statistic    FLOAT,
  n_samples       INTEGER NOT NULL,
  feature_drift   JSONB,               -- per-feature drift scores
  drift_detected  BOOLEAN DEFAULT FALSE,
  retrain_trigger BOOLEAN DEFAULT FALSE,
  report_path     TEXT,                -- path to Evidently HTML report
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Seed data — sales reps ────────────────────────────────────────────────────

INSERT INTO reps (name, phone, email, tier_focus) VALUES
  ('Alice Chen',   '+15550001111', 'alice@company.com',   '{hot}'),
  ('Bob Mehta',    '+15550002222', 'bob@company.com',     '{hot,warm}'),
  ('Carol Santos', '+15550003333', 'carol@company.com',   '{warm}'),
  ('David Kim',    '+15550004444', 'david@company.com',   '{warm,cold}');
