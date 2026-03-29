from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.plan import Plan
from app.schemas.plan import PlanResponse

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("", response_model=list[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[PlanResponse]:
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.sort_order)
    )
    plans = result.scalars().all()
    return [PlanResponse(
        id=str(p.id),
        name=p.name,
        label=p.label,
        duration_days=p.duration_days,
        price_rub=p.price_rub,
        new_user_price_rub=p.new_user_price_rub,
        sort_order=p.sort_order,
    ) for p in plans]
