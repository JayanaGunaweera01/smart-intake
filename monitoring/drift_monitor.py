"""
Drift monitor.
Runs on a cron schedule (or via GitHub Actions) to:
  1. Load reference data + recent production predictions
  2. Compute PSI / KS drift metrics with Evidently
  3. Persist DriftSnapshot to Postgres
  4. Trigger retrain workflow if PSI > threshold

Usage:
    python -m monitoring.drift_monitor
    # or via GitHub Actions on schedule
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import structlog
from evidently.metric_preset import DataDriftPreset
from evidently.report import Report
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger()

FEATURE_COLS = [
    "is_free_email", "has_website", "source_score",
    "time_on_site_s", "pages_visited", "submission_hour",
    "submission_dow", "company_size_bucket", "domain_age_days",
    "linkedin_employees", "funding_stage", "industry_code",
]

DRIFT_THRESHOLD = float(os.getenv("DRIFT_PSI_THRESHOLD", "0.20"))
WINDOW_HOURS = int(os.getenv("DRIFT_WINDOW_HOURS", "24"))
REFERENCE_PATH = os.getenv("REFERENCE_DATA_PATH", "ml/data/reference.parquet")
REPORTS_DIR = Path("monitoring/reports")


async def run_drift_check(db: AsyncSession) -> dict:
    from api.models.orm import DriftSnapshot, LeadFeature

    now = datetime.now(tz=timezone.utc)
    window_start = now - timedelta(hours=WINDOW_HOURS)

    # ── Load production data ───────────────────────────────────────────────────
    stmt = select(LeadFeature).where(LeadFeature.created_at >= window_start)
    result = await db.execute(stmt)
    features_rows = result.scalars().all()

    if len(features_rows) < 30:
        log.info("drift_skip_insufficient_data", n=len(features_rows))
        return {"skipped": True, "reason": "insufficient_data", "n_samples": len(features_rows)}

    current_df = pd.DataFrame(
        [{col: getattr(row, col, None) for col in FEATURE_COLS} for row in features_rows]
    ).fillna(-1)

    # ── Load reference data ────────────────────────────────────────────────────
    try:
        reference_df = pd.read_parquet(REFERENCE_PATH)[FEATURE_COLS].fillna(-1)
    except FileNotFoundError:
        log.error("reference_data_missing", path=REFERENCE_PATH)
        return {"error": "reference_data_missing"}

    # ── Evidently drift report ─────────────────────────────────────────────────
    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference_df, current_data=current_df)
    result_dict = report.as_dict()

    # ── Extract PSI per feature ────────────────────────────────────────────────
    feature_drift: dict[str, float] = {}
    overall_drift_detected = False

    try:
        drift_metrics = result_dict["metrics"][0]["result"]
        overall_drift_detected = drift_metrics.get("dataset_drift", False)
        per_feature = drift_metrics.get("drift_by_columns", {})
        for feat, info in per_feature.items():
            feature_drift[feat] = round(float(info.get("drift_score", 0.0)), 4)
    except (KeyError, IndexError, TypeError) as e:
        log.warning("drift_parse_error", error=str(e))

    # PSI approximation (mean of per-feature drift scores as proxy)
    psi_score = round(sum(feature_drift.values()) / max(len(feature_drift), 1), 4)
    drift_detected = overall_drift_detected or psi_score > DRIFT_THRESHOLD

    # ── Save HTML report ───────────────────────────────────────────────────────
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = str(REPORTS_DIR / f"drift_{now.strftime('%Y%m%d_%H%M%S')}.html")
    report.save_html(report_path)

    # ── Persist snapshot ───────────────────────────────────────────────────────
    snapshot = DriftSnapshot(
        window_start=window_start,
        window_end=now,
        psi_score=psi_score,
        n_samples=len(current_df),
        feature_drift=feature_drift,
        drift_detected=drift_detected,
        retrain_trigger=drift_detected,
        report_path=report_path,
    )
    db.add(snapshot)
    await db.commit()

    log.info(
        "drift_check_complete",
        psi=psi_score,
        drift_detected=drift_detected,
        n_samples=len(current_df),
        report=report_path,
    )

    if drift_detected:
        log.warning("DRIFT_DETECTED — triggering retrain", psi=psi_score)
        _trigger_retrain(psi_score)

    return {
        "psi_score": psi_score,
        "drift_detected": drift_detected,
        "n_samples": len(current_df),
        "feature_drift": feature_drift,
        "report_path": report_path,
    }


def _trigger_retrain(psi_score: float):
    """
    In GitHub Actions: dispatch workflow_dispatch via API.
    Locally: just log.
    """
    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")

    if github_token and repo:
        import httpx
        url = f"https://api.github.com/repos/{repo}/actions/workflows/retrain.yml/dispatches"
        resp = httpx.post(
            url,
            headers={"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"},
            json={"ref": "main", "inputs": {"psi_score": str(psi_score)}},
        )
        log.info("retrain_dispatch", status=resp.status_code, body=resp.text[:200])
    else:
        log.info("retrain_trigger_local_noop", psi=psi_score)


async def main():
    from api.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        result = await run_drift_check(session)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
