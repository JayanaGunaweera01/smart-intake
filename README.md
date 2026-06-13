# SmartIntake — ML-Powered Production Lead Triage System

> A full-stack, production-grade ML engineering project demonstrating the complete model lifecycle:
> **data generation → training → serving → drift detection → auto-retraining**

[![CI](https://github.com/JayanaGunaweera01/smart-intake/actions/workflows/ci.yml/badge.svg)](https://github.com/JayanaGunaweera01/smart-intake/actions)
[![Retrain](https://github.com/JayanaGunaweera01/smart-intake/actions/workflows/retrain.yml/badge.svg)](https://github.com/JayanaGunaweera01/smart-intake/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![MLflow](https://img.shields.io/badge/MLflow-2.11-blue)](https://mlflow.org)

---

## Architecture

```
 Form Submission
       │
       ▼
 ┌─────────────┐    Redis      ┌──────────────┐
 │  FastAPI    │◄─ dedup/RL ──►│  PostgreSQL  │
 │  (intake)   │               │  leads       │
 └──────┬──────┘               │  features    │
        │                      │  predictions │
        ▼                      │  assignments │
 ┌─────────────┐               └──────────────┘
 │  Feature    │
 │  Extractor  │
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐   MLflow     ┌──────────────┐
 │  XGBoost    │◄─ registry ──│  MLflow      │
 │  Scorer     │              │  Server      │
 │  + SHAP     │              └──────────────┘
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐   Twilio     ┌──────────────┐
 │  Rep Router │──── SMS ────►│  Sales Reps  │
 └─────────────┘              └──────────────┘

 ┌─────────────────────────────────────────────┐
 │  Drift Monitor (cron / GitHub Actions)       │
 │  Evidently PSI → DriftSnapshot → retrain?   │
 └────────────────────────┬────────────────────┘
                          │ PSI > 0.20
                          ▼
              GitHub Actions retrain.yml
              → train → eval gate → promote
```

---

## Quick Start

### Prerequisites

- Docker 24+ and Docker Compose 2.x
- Python 3.11
- Node 18+ (frontend only)

### Setup

```bash
git clone https://github.com/JayanaGunaweera01/smart-intake
cd smart-intake

cp .env.example .env
# Fill in your Supabase DATABASE_URL and other values — see Environment Variables below
```

### Start infrastructure

```bash
docker compose up -d redis mlflow
```

### Train the model

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m ml.generate_synthetic --n 5000 --out ml/data/leads.parquet
python -m ml.train --data ml/data/leads.parquet --experiment lead-scoring
```

### Start the API

```bash
uvicorn api.main:app --reload --port 8000
```

### Start the dashboard

```bash
cd frontend && npm install && npm run dev
```

Visit:
- **API docs** → http://localhost:8000/docs
- **Dashboard** → http://localhost:3000
- **MLflow**    → http://localhost:5000
- **Grafana**   → http://localhost:3001 (admin / admin)

---

## Project Structure

```
smart-intake/
├── api/
│   ├── main.py                  # FastAPI app + middleware
│   ├── config.py                # Pydantic settings
│   ├── database.py              # Async SQLAlchemy engine
│   ├── routes/
│   │   ├── intake.py            # POST /api/v1/leads/submit
│   │   ├── scores.py            # GET  /api/v1/leads/{id}/score
│   │   ├── dashboard.py         # GET  /api/v1/dashboard/*
│   │   └── health.py            # GET  /health
│   ├── services/
│   │   ├── feature_extractor.py # Pure-function feature engineering
│   │   ├── ml_scorer.py         # MLflow model loader + SHAP
│   │   └── twilio_router.py     # Rep assignment + SMS
│   └── models/
│       ├── orm.py               # SQLAlchemy ORM models
│       └── schemas.py           # Pydantic v2 schemas
├── ml/
│   ├── generate_synthetic.py    # Synthetic B2B lead dataset
│   └── train.py                 # XGBoost + MLflow experiment logging
├── db/
│   ├── schema.sql               # PostgreSQL DDL
│   └── migrations/env.py        # Alembic async migrations
├── monitoring/
│   ├── drift_monitor.py         # Evidently PSI + retrain trigger
│   └── prometheus.yml           # Scrape config
├── frontend/
│   └── src/App.jsx              # React dashboard (Recharts)
├── tests/
│   └── test_core.py             # pytest unit tests
├── .github/workflows/
│   ├── ci.yml                   # Test + lint + Docker build
│   └── retrain.yml              # Auto-retrain on drift
├── docker-compose.yml           # Local stack (Redis + MLflow)
├── Dockerfile                   # API container
├── alembic.ini                  # Alembic config
└── scripts/setup.sh             # One-shot setup
```

---

## Key ML Engineering Concepts Demonstrated

| Concept | Implementation |
|---|---|
| **Feature Engineering** | `feature_extractor.py` — pure functions, fully unit-tested |
| **Model Training** | `ml/train.py` — XGBoost + SMOTE + cross-validation |
| **Experiment Tracking** | MLflow — params, metrics, artifacts, model registry |
| **Model Serving** | FastAPI + MLflow pyfunc — async, <50ms p99 |
| **Explainability** | SHAP TreeExplainer — top-5 factors per prediction |
| **Drift Detection** | Evidently PSI — per-feature and dataset-level |
| **Auto-retraining** | GitHub Actions `workflow_dispatch` — gated by AUC ≥ 0.70 |
| **Observability** | Prometheus metrics + Grafana dashboard |
| **Rate Limiting** | Redis sliding window — 30 req/min per IP |
| **Idempotency** | Redis SHA-256 dedup key — 24h TTL |
| **Champion/Challenger** | MLflow `archive_existing_versions` on promotion |
| **Async I/O** | FastAPI + asyncpg + aioredis throughout |
| **Containerisation** | Docker with non-root user and healthchecks |
| **CI/CD** | GitHub Actions — lint + test + coverage + GHCR push |

---

## API Reference

### Submit a lead

```http
POST /api/v1/leads/submit
Content-Type: application/json

{
  "email": "cto@acme.io",
  "company": "Acme Corp",
  "website": "https://acme.io",
  "source": "organic",
  "time_on_site_s": 240,
  "pages_visited": 5
}
```

Response:

```json
{
  "lead_id": "uuid",
  "score": 0.87,
  "tier": "hot",
  "top_factors": [
    {
      "feature": "is_free_email",
      "shap_value": -0.42,
      "direction": "negative",
      "importance_rank": 1
    }
  ],
  "message": "Lead received and classified as HOT (score: 87/100)"
}
```

### Get score + SHAP explanation

```http
GET /api/v1/leads/{lead_id}/score
```

### Dashboard

```http
GET /api/v1/dashboard/stats
GET /api/v1/dashboard/leads?tier=hot&limit=50
GET /api/v1/dashboard/drift
```

---

## Testing

```bash
pytest tests/ -v --cov=api --cov-report=term-missing
```

---

## MLOps Workflow

```bash
# 1. Generate training data
python -m ml.generate_synthetic --n 10000

# 2. Train and register model
python -m ml.train --data ml/data/leads.parquet

# 3. Check for drift manually
python -m monitoring.drift_monitor

# 4. Auto-retrain triggers via GitHub Actions
#    when PSI > 0.20 (configurable via DRIFT_PSI_THRESHOLD)
```

---

## Deployment

| Service | Platform |
|---|---|
| API | Fly.io / Railway |
| PostgreSQL | Supabase (free tier) |
| Redis | Upstash (free tier) |
| MLflow | Self-hosted on Fly.io |
| Frontend | Vercel |
| Monitoring | Grafana Cloud (free tier) |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```bash
# ── Database (Supabase session-mode pooler) ───────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT-REF]:[PASSWORD]@aws-1-[REGION].pooler.supabase.com:5432/postgres
MLFLOW_DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-1-[REGION].pooler.supabase.com:5432/postgres

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379

# ── MLflow ────────────────────────────────────────────────────────────────────
MLFLOW_TRACKING_URI=http://localhost:5000
MODEL_NAME=lead-scorer
MODEL_STAGE=Production

# ── Twilio ────────────────────────────────────────────────────────────────────
TWILIO_ENABLED=false
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+15551234567

# ── Scoring thresholds ────────────────────────────────────────────────────────
HOT_THRESHOLD=0.75
WARM_THRESHOLD=0.45
COLD_THRESHOLD=0.20

# ── Drift detection ───────────────────────────────────────────────────────────
DRIFT_PSI_THRESHOLD=0.20
DRIFT_WINDOW_HOURS=24
REFERENCE_DATA_PATH=ml/data/reference.parquet

# ── GitHub (for drift monitor to trigger retrain) ─────────────────────────────
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_REPOSITORY=YourUsername/smart-intake

# ── Grafana ───────────────────────────────────────────────────────────────────
GRAFANA_PASSWORD=admin

# ── Security ──────────────────────────────────────────────────────────────────
SECRET_KEY=generate-with-python-secrets-token-hex-32

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","https://your-app.vercel.app"]
```

**Required for production:**
- `DATABASE_URL` — Supabase session-mode pooler URI
- `MLFLOW_DATABASE_URL` — same host, plain `postgresql://` driver for MLflow
- `REDIS_URL` — Upstash or local Redis
- `MLFLOW_TRACKING_URI` — MLflow server URL
- `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- `TWILIO_*` — only needed if `TWILIO_ENABLED=true`

---

## License

Apache 2.0 — build on it, learn from it, ship it.
