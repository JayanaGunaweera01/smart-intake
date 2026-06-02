"""GET /health — detailed dependency health check."""

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_db
from api.models.schemas import HealthResponse
from api.services.ml_scorer import get_scorer

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health(
    db: AsyncSession = Depends(get_db),
    scorer=Depends(get_scorer),
):
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    redis_status = "ok"
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
    except Exception as e:
        redis_status = f"error: {e}"

    mlflow_status = "ok"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{settings.MLFLOW_TRACKING_URI}/health")
            if resp.status_code != 200:
                mlflow_status = f"http {resp.status_code}"
    except Exception as e:
        mlflow_status = f"error: {e}"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version=settings.VERSION,
        db=db_status,
        redis=redis_status,
        mlflow=mlflow_status,
        model_loaded=scorer.is_loaded,
    )
