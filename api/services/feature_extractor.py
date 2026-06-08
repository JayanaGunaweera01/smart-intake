"""
Feature extraction service.
Derives ML-ready features from a raw lead submission.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import structlog

log = structlog.get_logger()

# Free e-mail providers (partial list — extend via YAML in prod)
FREE_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "icloud.com", "protonmail.com", "aol.com", "live.com",
        "me.com", "msn.com", "ymail.com", "mail.com",
    }
)

SOURCE_SCORES: dict[str, float] = {
    "organic": 1.0,
    "referral": 0.95,
    "email": 0.85,
    "paid": 0.80,
    "social": 0.70,
    "direct": 0.75,
    "web": 0.70,
    "unknown": 0.50,
}


def extract_features(
    *,
    email: str,
    website: Optional[str],
    source: str,
    time_on_site_s: Optional[int],
    pages_visited: Optional[int],
    created_at: Optional[datetime] = None,
) -> dict:
    """
    Pure-function feature extraction — no I/O, fully testable.

    Returns a flat dict of feature_name → value ready for the model.
    """
    now = created_at or datetime.now(tz=timezone.utc)
    domain = _email_domain(email)

    features = {
        # ── Email signals ─────────────────────────────────────────────────────
        "email_domain": domain,
        "is_free_email": domain in FREE_EMAIL_DOMAINS,

        # ── Website signals ───────────────────────────────────────────────────
        "has_website": _has_website(website),

        # ── Source signals ────────────────────────────────────────────────────
        "source_score": SOURCE_SCORES.get(source.lower(), 0.5),

        # ── Behavioural signals ───────────────────────────────────────────────
        "time_on_site_s": time_on_site_s or 0,
        "pages_visited": pages_visited or 1,

        # ── Temporal signals ──────────────────────────────────────────────────
        "submission_hour": now.hour,
        "submission_dow": now.weekday(),   # 0=Mon, 6=Sun

        # ── Enrichment placeholders (filled async in prod) ────────────────────
        "company_size_bucket": 0,
        "domain_age_days": -1,             # -1 = unknown
        "linkedin_employees": -1,
        "funding_stage": 0,
        "industry_code": 0,
    }

    log.debug("features_extracted", domain=domain, features=features)
    return features


def _email_domain(email: str) -> str:
    try:
        return email.split("@")[1].lower().strip()
    except IndexError:
        return ""


def _has_website(website: Optional[str]) -> bool:
    if not website:
        return False
    try:
        result = urlparse(website)
        return bool(result.netloc)
    except Exception:
        return False


def features_to_model_input(features: dict) -> dict:
    """
    Convert raw feature dict → numeric-only dict for the XGBoost model.
    Categorical columns (email_domain) are dropped; derived booleans cast to int.
    """
    NUMERIC_FEATURES = [
        "is_free_email",
        "has_website",
        "source_score",
        "time_on_site_s",
        "pages_visited",
        "submission_hour",
        "submission_dow",
        "company_size_bucket",
        "domain_age_days",
        "linkedin_employees",
        "funding_stage",
        "industry_code",
    ]
    return {
        k: int(v) if isinstance(v, bool) else (v if v is not None else -1)
        for k, v in features.items()
        if k in NUMERIC_FEATURES
    }
