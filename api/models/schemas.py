"""Pydantic v2 schemas — request / response contracts."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator


# ── Intake ──────────────────────────────────────────────────────────────────────

class LeadSubmitRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    source: str = "web"
    external_id: Optional[str] = None
    # Behavioral signals from frontend
    time_on_site_s: Optional[int] = Field(None, ge=0, le=86400)
    pages_visited: Optional[int] = Field(None, ge=1, le=500)
    # Any extra form fields go here
    extras: Optional[Dict[str, Any]] = None

    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, v):
        if v:
            import re
            return re.sub(r"[^\d+]", "", v)
        return v


class LeadSubmitResponse(BaseModel):
    lead_id: UUID
    score: float
    tier: str
    top_factors: List[Dict[str, Any]]
    message: str


# ── Scores ──────────────────────────────────────────────────────────────────────

class ShapFactor(BaseModel):
    feature: str
    value: Any
    shap_value: float
    direction: str          # "positive" | "negative"
    importance_rank: int


class ScoreDetail(BaseModel):
    lead_id: UUID
    email: str
    company: Optional[str]
    score: float
    tier: str
    model_name: str
    model_version: str
    top_factors: List[ShapFactor]
    shap_values: Dict[str, float]
    created_at: datetime


# ── Dashboard ──────────────────────────────────────────────────────────────────

class LeadSummary(BaseModel):
    lead_id: UUID
    email: str
    name: Optional[str]
    company: Optional[str]
    score: Optional[float]
    tier: Optional[str]
    source: str
    created_at: datetime
    rep_name: Optional[str]
    assignment_status: Optional[str]


class DashboardStats(BaseModel):
    total_leads: int
    hot_count: int
    warm_count: int
    cold_count: int
    disqualified_count: int
    avg_score: float
    leads_today: int
    conversion_rate: float


class DriftStatus(BaseModel):
    latest_psi: Optional[float]
    drift_detected: bool
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    n_samples: Optional[int]
    retrain_triggered: bool
    feature_drift: Optional[Dict[str, float]]


# ── Health ──────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    redis: str
    mlflow: str
    model_loaded: bool
