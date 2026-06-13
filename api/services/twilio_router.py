"""
Twilio router service.
Routes scored leads to the right sales rep via SMS based on tier.
Falls back to dry-run logging when TWILIO_ENABLED=False.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.config import settings
from api.models.orm import Lead, Prediction, Rep, RepAssignment, AuditEvent

log = structlog.get_logger()


def _get_twilio_client():
    from twilio.rest import Client
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def _build_sms_body(lead: Lead, prediction: Prediction, rep: Rep) -> str:
    score_pct = int(prediction.score * 100)
    tier_emoji = {"hot": "🔥", "warm": "🌤️", "cold": "❄️", "disqualified": "✖️"}.get(
        prediction.tier, "❓"
    )
    factors = prediction.top_factors or []
    top_3 = [f["feature"].replace("_", " ") for f in factors[:3]]
    factor_str = ", ".join(top_3) if top_3 else "N/A"

    return (
        f"SmartIntake {tier_emoji} NEW {prediction.tier.upper()} LEAD\n"
        f"Name: {lead.name or 'Unknown'}\n"
        f"Company: {lead.company or 'Unknown'}\n"
        f"Email: {lead.email}\n"
        f"Score: {score_pct}/100\n"
        f"Key signals: {factor_str}\n"
        f"Reply CALL to claim · Reply SKIP to pass"
    )


async def assign_and_notify(
    *,
    db: AsyncSession,
    lead_id: UUID,
) -> Optional[RepAssignment]:
    """
    1. Load lead + prediction from DB
    2. Pick the best available rep for the tier
    3. Insert rep_assignment row
    4. Send Twilio SMS (or log if disabled)
    5. Emit audit event
    """
    # ── Load lead + prediction ────────────────────────────────────────────────
    lead = await db.get(Lead, lead_id)
    # BUG FIX: db.get(Prediction, lead_id) looks up by PRIMARY KEY (Prediction.id),
    # not by the lead_id foreign key — it always returned None and SMS was never sent.
    pred_result = await db.execute(
        select(Prediction).where(Prediction.lead_id == lead_id)
    )
    prediction = pred_result.scalar_one_or_none()

    if not lead or not prediction:
        log.warning("assignment_skip_missing_data", lead_id=str(lead_id))
        return None

    if prediction.tier == "disqualified":
        log.info("assignment_skip_disqualified", lead_id=str(lead_id))
        return None

    # ── Pick rep ──────────────────────────────────────────────────────────────
    rep = await _pick_rep(db=db, tier=prediction.tier)
    if not rep:
        log.warning("no_rep_available", tier=prediction.tier)
        return None

    # ── Send SMS ──────────────────────────────────────────────────────────────
    sms_sid = None
    if settings.TWILIO_ENABLED:
        try:
            client = _get_twilio_client()
            body = _build_sms_body(lead, prediction, rep)
            msg = client.messages.create(
                to=rep.phone,
                from_=settings.TWILIO_FROM_NUMBER,
                body=body,
            )
            sms_sid = msg.sid
            log.info("sms_sent", sid=sms_sid, rep=rep.name, tier=prediction.tier)
        except Exception as e:
            log.error("sms_failed", error=str(e), rep=rep.name)
    else:
        body = _build_sms_body(lead, prediction, rep)
        log.info(
            "sms_dry_run",
            to=rep.phone,
            rep=rep.name,
            tier=prediction.tier,
            body=body,
        )

    # ── Persist assignment ────────────────────────────────────────────────────
    assignment = RepAssignment(
        lead_id=lead_id,
        rep_id=rep.id,
        status="sent" if sms_sid else "pending",
        sms_sid=sms_sid,
    )
    db.add(assignment)

    audit = AuditEvent(
        lead_id=lead_id,
        event="rep_assigned",
        payload={
            "rep_id": str(rep.id),
            "rep_name": rep.name,
            "tier": prediction.tier,
            "sms_sent": bool(sms_sid),
        },
    )
    db.add(audit)
    await db.flush()

    log.info("rep_assigned", lead_id=str(lead_id), rep=rep.name, tier=prediction.tier)
    return assignment


async def _pick_rep(db: AsyncSession, tier: str) -> Optional[Rep]:
    """
    Simple round-robin: pick the active rep whose tier_focus includes `tier`
    with the fewest open assignments in the last 7 days.
    """
    from sqlalchemy import func, text

    stmt = (
        select(Rep)
        .where(Rep.is_active == True)
        .where(Rep.tier_focus.contains([tier]))  # PostgreSQL array contains
        .order_by(func.random())                  # naive load balancing
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
