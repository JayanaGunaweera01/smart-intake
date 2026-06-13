#  SmartIntake — Production ML Powered Lead Triage System

> A full-stack, production-grade ML engineering project demonstrating the complete model lifecycle:
> **data generation → training → serving → drift detection → auto-retraining**

[![CI](https://github.com/JayanaGunaweera01/smartintake/actions/workflows/main.yml/badge.svg)](https://github.com/JayanaGunaweera01/smartintake/actions)

[![Retrain](https://github.com/JayanaGunaweera01/smartintake/actions/workflows/retrain.yml/badge.svg)](https://github.com/JayanaGunaweera01/smartintake/actions)
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

## Quick Start

```bash
git clone https://github.com/yourusername/smartintake
cd smartintake

# One-shot setup (Docker required)
chmod +x scripts/setup.sh
./scripts/setup.sh

# Run dashboard
cd frontend && npm run dev
```

Visit:
- **API docs** → http://localhost:8000/docs
- **Dashboard** → http://localhost:3000
- **MLflow**    → http://localhost:5000
- **Grafana**   → http://localhost:3001 (admin / admin)

## Project Structure

```
smartintake/
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
├── docker-compose.yml           # Full local stack
└── scripts/setup.sh             # One-shot setup
```

## Key ML Engineering Concepts Demonstrated

| Concept | Implementation |
|---------|---------------|
| **Feature Engineering** | `feature_extractor.py` — pure functions, fully unit-tested |
| **Model Training** | `ml/train.py` — XGBoost + SMOTE + cross-validation |
| **Experiment Tracking** | MLflow — params, metrics, artifacts, model registry |
| **Model Serving** | FastAPI + MLflow pyfunc — async, <50ms p99 |
| **Explainability** | SHAP TreeExplainer — top-5 factors per prediction |
| **Drift Detection** | Evidently PSI + KS — per-feature and dataset-level |
| **Auto-retraining** | GitHub Actions `workflow_dispatch` — gated by AUC ≥ 0.70 |
| **Data Validation** | Pydantic v2 + great-expectations |
| **Observability** | Prometheus metrics + Grafana dashboard |
| **Rate Limiting** | Redis sliding window — 30 req/min per IP |
| **Idempotency** | Redis SHA256 dedup key — 24h TTL |
| **Champion/Challenger** | MLflow `archive_existing_versions` on promotion |
| **Async I/O** | FastAPI + asyncpg + aioredis throughout |
| **Docker** | Multi-stage build, non-root user, healthchecks |
| **CI/CD** | GitHub Actions — lint + test + coverage + GHCR push |

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
    {"feature": "is_free_email", "shap_value": -0.42, "direction": "negative", "importance_rank": 1}
  ],
  "message": "Lead received and classified as HOT (score: 87/100)"
}
```

### Get score + SHAP
```http
GET /api/v1/leads/{lead_id}/score
```

### Dashboard stats
```http
GET /api/v1/dashboard/stats
GET /api/v1/dashboard/leads?tier=hot&limit=50
GET /api/v1/dashboard/drift
```

## Testing

```bash
pytest tests/ -v --cov=api --cov-report=term-missing
```

## 🔄 MLOps Workflow

```bash
# 1. Generate data
python -m ml.generate_synthetic --n 10000

# 2. Train + register
python -m ml.train --data ml/data/leads.parquet

# 3. Check drift
python -m monitoring.drift_monitor

# 4. Retrain triggers automatically via GitHub Actions
#    when PSI > 0.20 (configurable via DRIFT_PSI_THRESHOLD)
```

## Deployment

| Service | Platform |
|---------|----------|
| API | Fly.io / Railway / Render |
| PostgreSQL | Supabase / Neon (free tier) |
| Redis | Upstash (free tier) |
| MLflow | Self-hosted on Fly.io |
| Frontend | Vercel / Netlify |
| Monitoring | Grafana Cloud (free tier) |

## Environment Variables

See `.env.example` for the full list. Required for production:
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `MLFLOW_TRACKING_URI` — MLflow server URL
- `TWILIO_*` — For SMS routing (optional, set `TWILIO_ENABLED=true`)

## License

Apache — build on it, learn from it, ship it.
