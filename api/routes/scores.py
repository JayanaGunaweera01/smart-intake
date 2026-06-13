"""GET /api/v1/leads/{lead_id}/score — score detail + SHAP explanation."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.orm import Lead, Prediction
from api.models.schemas import ScoreDetail, ShapFactor

router = APIRouter()


@router.get(
    "/leads/{lead_id}/score",
    response_model=ScoreDetail,
    summary="Retrieve ML score and SHAP explanation for a lead",
)
async def get_lead_score(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    pred = await db.get(Prediction, lead_id)
    if not pred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No prediction found for this lead yet",
        )

    top_factors = [
        ShapFactor(
            feature=f["feature"],
            value=f["value"],
            shap_value=f["shap_value"],
            direction=f["direction"],
            importance_rank=f["importance_rank"],
        )
        for f in (pred.top_factors or [])
    ]

    return ScoreDetail(
        lead_id=lead.id,
        email=lead.email,
        company=lead.company,
        score=pred.score,
        tier=pred.tier,
        model_name=pred.model_name,
        model_version=pred.model_version,
        top_factors=top_factors,
        shap_values=pred.shap_values or {},
        created_at=pred.created_at,
    )
