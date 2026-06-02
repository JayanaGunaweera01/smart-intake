from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    VERSION: str = "1.0.0"

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://smartintake:smartintake_secret@localhost:5432/smartintake"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL_SECONDS: int = 300
    RATE_LIMIT_REQUESTS: int = 30
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # ── MLflow ────────────────────────────────────────────────────────────────
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MODEL_NAME: str = "lead-scorer"
    MODEL_STAGE: str = "Production"    # Production | Staging | None

    # ── Twilio ────────────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""       # E.164 e.g. +15551234567
    TWILIO_ENABLED: bool = False       # set True in prod

    # ── Scoring thresholds ────────────────────────────────────────────────────
    HOT_THRESHOLD: float = 0.75
    WARM_THRESHOLD: float = 0.45
    COLD_THRESHOLD: float = 0.20       # below → disqualified

    # ── Drift ─────────────────────────────────────────────────────────────────
    DRIFT_PSI_THRESHOLD: float = 0.20
    DRIFT_WINDOW_HOURS: int = 24
    REFERENCE_DATA_PATH: str = "ml/data/reference.parquet"

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = "dev-secret-change-in-prod"
    API_KEY_HEADER: str = "X-API-Key"

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
