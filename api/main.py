"""
SmartIntake — Production ML-Powered Lead Triage System
FastAPI application entry point.
"""

import time
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from api.config import settings
from api.database import engine, Base
from api.routes import intake, scores, health, dashboard
from api.services.ml_scorer import scorer

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    log.info("Starting SmartIntake API", version=settings.VERSION)
    # Tables are created via Alembic in prod; this is for dev convenience
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # BUG FIX: load the ML model from MLflow at startup so scorer.is_loaded=True.
    # Without this every request degraded silently to score=0.5 with no SHAP.
    try:
        scorer.load()
        log.info("model_loaded_at_startup", version=scorer.model_version)
    except Exception as e:
        log.warning("model_load_failed_at_startup", error=str(e),
                    note="API will run but scoring will degrade until model is available")
    yield
    log.info("Shutting down SmartIntake API")
    await engine.dispose()


app = FastAPI(
    title="SmartIntake",
    description="Production ML-Powered Lead Triage System",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ──────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_request_id_and_timing(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-ms"] = f"{duration_ms:.1f}"
    log.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 1),
        request_id=request_id,
    )
    return response


# ── Prometheus ──────────────────────────────────────────────────────────────────

Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# ── Routers ─────────────────────────────────────────────────────────────────────

app.include_router(health.router, tags=["Health"])
app.include_router(intake.router, prefix="/api/v1", tags=["Intake"])
app.include_router(scores.router, prefix="/api/v1", tags=["Scores"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
