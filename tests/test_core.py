"""
Unit tests for SmartIntake core services.
Run: pytest tests/ -v --cov=api
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ──────────────────────────────────────────────────────────────────────────────
# Feature extractor
# ──────────────────────────────────────────────────────────────────────────────

from api.services.feature_extractor import extract_features, features_to_model_input


class TestFeatureExtractor:
    def test_free_email_flagged(self):
        feats = extract_features(
            email="user@gmail.com",
            website=None,
            source="web",
            time_on_site_s=0,
            pages_visited=1,
        )
        assert feats["is_free_email"] is True
        assert feats["email_domain"] == "gmail.com"

    def test_corporate_email_not_flagged(self):
        feats = extract_features(
            email="cto@acme.io",
            website="https://acme.io",
            source="organic",
            time_on_site_s=300,
            pages_visited=5,
        )
        assert feats["is_free_email"] is False
        assert feats["has_website"] is True

    def test_organic_source_score(self):
        feats = extract_features(
            email="a@b.com", website=None, source="organic",
            time_on_site_s=0, pages_visited=1,
        )
        assert feats["source_score"] == 1.0

    def test_unknown_source_defaults(self):
        feats = extract_features(
            email="a@b.com", website=None, source="mystery_channel",
            time_on_site_s=0, pages_visited=1,
        )
        assert feats["source_score"] == 0.5

    def test_model_input_has_no_strings(self):
        feats = extract_features(
            email="cto@corp.com", website="https://corp.com",
            source="referral", time_on_site_s=120, pages_visited=3,
        )
        model_input = features_to_model_input(feats)
        for k, v in model_input.items():
            assert isinstance(v, (int, float)), f"{k}={v!r} is not numeric"

    def test_website_detection(self):
        feats_no_web = extract_features(
            email="x@y.com", website="", source="web",
            time_on_site_s=0, pages_visited=1,
        )
        feats_with_web = extract_features(
            email="x@y.com", website="https://startup.ai", source="web",
            time_on_site_s=0, pages_visited=1,
        )
        assert feats_no_web["has_website"] is False
        assert feats_with_web["has_website"] is True

    def test_submission_hour_range(self):
        from datetime import datetime, timezone
        feats = extract_features(
            email="a@b.com", website=None, source="web",
            time_on_site_s=0, pages_visited=1,
            created_at=datetime(2024, 6, 15, 14, 30, tzinfo=timezone.utc),
        )
        assert feats["submission_hour"] == 14
        assert feats["submission_dow"] == 5   # Saturday


# ──────────────────────────────────────────────────────────────────────────────
# Scoring thresholds
# ──────────────────────────────────────────────────────────────────────────────

from api.services.ml_scorer import LeadScorer


class TestLeadScorerTiers:
    def setup_method(self):
        self.scorer = LeadScorer()

    def test_hot_tier(self):
        assert self.scorer._score_to_tier(0.90) == "hot"
        assert self.scorer._score_to_tier(0.75) == "hot"

    def test_warm_tier(self):
        assert self.scorer._score_to_tier(0.74) == "warm"
        assert self.scorer._score_to_tier(0.45) == "warm"

    def test_cold_tier(self):
        assert self.scorer._score_to_tier(0.44) == "cold"
        assert self.scorer._score_to_tier(0.20) == "cold"

    def test_disqualified_tier(self):
        assert self.scorer._score_to_tier(0.19) == "disqualified"
        assert self.scorer._score_to_tier(0.0) == "disqualified"

    def test_model_not_loaded_raises(self):
        from api.services.ml_scorer import ModelNotLoadedError
        with pytest.raises(ModelNotLoadedError):
            self.scorer.score({"is_free_email": 0})


# ──────────────────────────────────────────────────────────────────────────────
# Drift monitor helpers
# ──────────────────────────────────────────────────────────────────────────────

class TestDriftMonitor:
    def test_threshold_from_env(self):
        import os
        os.environ["DRIFT_PSI_THRESHOLD"] = "0.15"
        import importlib
        import monitoring.drift_monitor as dm
        importlib.reload(dm)
        assert dm.DRIFT_THRESHOLD == 0.15
        del os.environ["DRIFT_PSI_THRESHOLD"]


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic data
# ──────────────────────────────────────────────────────────────────────────────

class TestSyntheticData:
    def test_generate_shape(self):
        from ml.generate_synthetic import generate
        df = generate(n=200)
        assert len(df) == 200
        assert "label" in df.columns
        assert df["label"].isin([0, 1]).all()

    def test_conversion_rate_reasonable(self):
        from ml.generate_synthetic import generate
        df = generate(n=1000)
        rate = df["label"].mean()
        assert 0.10 < rate < 0.70, f"Unexpected conversion rate: {rate}"

    def test_no_nulls_in_numeric_cols(self):
        from ml.generate_synthetic import generate
        df = generate(n=500)
        numeric_cols = ["is_free_email", "has_website", "source_score",
                        "time_on_site_s", "pages_visited"]
        assert df[numeric_cols].isnull().sum().sum() == 0
