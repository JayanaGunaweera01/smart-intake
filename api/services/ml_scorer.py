"""
ML Scorer service.
Loads the champion model from MLflow Model Registry and scores leads.
Caches the model in-process; reloads on version change.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import mlflow.pyfunc
import numpy as np
import pandas as pd
import shap
import structlog

from api.config import settings

log = structlog.get_logger()


class ModelNotLoadedError(RuntimeError):
    pass


class LeadScorer:
    """Thread-safe (read-only after load) ML scoring wrapper."""

    def __init__(self):
        self._model: Optional[mlflow.pyfunc.PyFuncModel] = None
        self._explainer: Optional[shap.TreeExplainer] = None
        self._model_version: str = "unknown"
        self._model_name: str = settings.MODEL_NAME
        self._feature_names: list[str] = []

    def load(self, stage: str = None) -> None:
        """Load (or reload) the champion model from MLflow registry."""
        stage = stage or settings.MODEL_STAGE
        model_uri = f"models:/{self._model_name}/{stage}"
        log.info("loading_model", uri=model_uri)

        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        self._model = mlflow.pyfunc.load_model(model_uri)

        # Grab the underlying sklearn/xgb model for SHAP
        try:
            underlying = self._model._model_impl.python_model  # custom pyfunc
        except AttributeError:
            underlying = self._model._model_impl             # sklearn flavour

        try:
            self._explainer = shap.TreeExplainer(underlying)
        except Exception as e:
            log.warning("shap_explainer_failed", error=str(e))
            self._explainer = None

        # Resolve version tag
        client = mlflow.MlflowClient(tracking_uri=settings.MLFLOW_TRACKING_URI)
        versions = client.get_latest_versions(self._model_name, stages=[stage])
        self._model_version = versions[0].version if versions else "unknown"

        log.info("model_loaded", name=self._model_name, version=self._model_version)

    def score(self, features: dict) -> Tuple[float, str, Dict[str, Any], list]:
        """
        Score a single lead.

        Returns:
            (score, tier, shap_values_dict, top_factors)
        """
        if self._model is None:
            raise ModelNotLoadedError("Model not loaded; call .load() first")

        df = pd.DataFrame([features])
        t0 = time.perf_counter()
        prediction = self._model.predict(df)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # predict() returns either probability or label depending on flavor
        if hasattr(prediction, "__len__") and len(prediction.shape) == 2:
            score = float(prediction[0, 1])   # proba[:, 1]
        else:
            score = float(prediction[0])

        score = max(0.0, min(1.0, score))
        tier = self._score_to_tier(score)

        # ── SHAP ─────────────────────────────────────────────────────────────
        shap_dict: Dict[str, float] = {}
        top_factors: list = []

        if self._explainer is not None:
            try:
                shap_values = self._explainer.shap_values(df)
                # For binary classifiers, shap_values may be [neg_class, pos_class]
                if isinstance(shap_values, list):
                    sv = shap_values[1][0]
                else:
                    sv = shap_values[0]

                feature_names = df.columns.tolist()
                shap_dict = {k: round(float(v), 4) for k, v in zip(feature_names, sv)}

                # Top 5 factors sorted by |shap|
                sorted_factors = sorted(
                    shap_dict.items(), key=lambda x: abs(x[1]), reverse=True
                )[:5]
                top_factors = [
                    {
                        "feature": feat,
                        "value": features.get(feat),
                        "shap_value": val,
                        "direction": "positive" if val > 0 else "negative",
                        "importance_rank": i + 1,
                    }
                    for i, (feat, val) in enumerate(sorted_factors)
                ]
            except Exception as e:
                log.warning("shap_failed", error=str(e))

        log.info(
            "lead_scored",
            score=round(score, 4),
            tier=tier,
            latency_ms=latency_ms,
            model_version=self._model_version,
        )
        return score, tier, shap_dict, top_factors

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _score_to_tier(self, score: float) -> str:
        if score >= settings.HOT_THRESHOLD:
            return "hot"
        if score >= settings.WARM_THRESHOLD:
            return "warm"
        if score >= settings.COLD_THRESHOLD:
            return "cold"
        return "disqualified"


# ── Singleton ───────────────────────────────────────────────────────────────────

scorer = LeadScorer()


def get_scorer() -> LeadScorer:
    """FastAPI dependency."""
    return scorer
