"""Dashboard routes — aggregate stats, lead list, drift status."""

from datetime import date, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.orm import AuditEvent, DriftSnapshot, Lead, Prediction, Rep, RepAssignment
from api.models.schemas import DashboardStats, DriftStatus, LeadSummary

router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    # Tier counts
    tier_q = await db.execute(
        select(Prediction.tier, func.count().label("cnt"))
        .group_by(Prediction.tier)
    )
    tier_counts = {row.tier: row.cnt for row in tier_q}

    # Avg score
    avg_q = await db.execute(select(func.avg(Prediction.score)))
    avg_score = float(avg_q.scalar() or 0)

    # Leads today
    today_start = date.today()
    today_q = await db.execute(
        select(func.count()).where(func.date(Lead.created_at) == today_start)
    )
    leads_today = int(today_q.scalar() or 0)

    # Total
    total_q = await db.execute(select(func.count()).select_from(Lead))
    total = int(total_q.scalar() or 0)

    # Conversion = assignments with status=converted / total
    conv_q = await db.execute(
        select(func.count()).where(RepAssignment.status == "converted")
    )
    converted = int(conv_q.scalar() or 0)
    conversion_rate = round(converted / max(total, 1), 4)

    return DashboardStats(
        total_leads=total,
        hot_count=tier_counts.get("hot", 0),
        warm_count=tier_counts.get("warm", 0),
        cold_count=tier_counts.get("cold", 0),
        disqualified_count=tier_counts.get("disqualified", 0),
        avg_score=round(avg_score, 4),
        leads_today=leads_today,
        conversion_rate=conversion_rate,
    )


@router.get("/dashboard/leads", response_model=List[LeadSummary])
async def list_leads(
    tier: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Lead.id,
            Lead.email,
            Lead.name,
            Lead.company,
            Lead.source,
            Lead.created_at,
            Prediction.score,
            Prediction.tier,
            Rep.name.label("rep_name"),
            RepAssignment.status.label("assignment_status"),
        )
        .outerjoin(Prediction, Prediction.lead_id == Lead.id)
        .outerjoin(RepAssignment, RepAssignment.lead_id == Lead.id)
        .outerjoin(Rep, Rep.id == RepAssignment.rep_id)
        .order_by(Lead.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if tier:
        stmt = stmt.where(Prediction.tier == tier)

    rows = await db.execute(stmt)
    return [
        LeadSummary(
            lead_id=r.id,
            email=r.email,
            name=r.name,
            company=r.company,
            score=r.score,
            tier=r.tier,
            source=r.source,
            created_at=r.created_at,
            rep_name=r.rep_name,
            assignment_status=r.assignment_status,
        )
        for r in rows
    ]


@router.get("/dashboard/drift", response_model=DriftStatus)
async def drift_status(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(DriftSnapshot)
        .order_by(DriftSnapshot.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    snap = result.scalar_one_or_none()
    if not snap:
        return DriftStatus(
            latest_psi=None,
            drift_detected=False,
            window_start=None,
            window_end=None,
            n_samples=None,
            retrain_triggered=False,
            feature_drift=None,
        )
    return DriftStatus(
        latest_psi=snap.psi_score,
        drift_detected=snap.drift_detected,
        window_start=snap.window_start,
        window_end=snap.window_end,
        n_samples=snap.n_samples,
        retrain_triggered=snap.retrain_trigger,
        feature_drift=snap.feature_drift,
    )
