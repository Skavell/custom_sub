# backend/app/routers/promo_codes.py
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.promo_code import PromoCodeType
from app.models.user import User
from app.schemas.promo_code import ApplyPromoRequest, ApplyPromoResponse, ValidatePromoResponse
from app.services.promo_code_service import apply_bonus_days, validate_promo_code
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.telegram_alert import send_admin_alert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/promo-codes", tags=["promo-codes"])


@router.get("/validate/{code}", response_model=ValidatePromoResponse)
async def validate_promo(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidatePromoResponse:
    promo, already_used = await validate_promo_code(db, code, current_user)
    return ValidatePromoResponse(
        code=promo.code,
        type=promo.type.value,
        value=promo.value,
        already_used=already_used,
    )


@router.post("/apply", response_model=ApplyPromoResponse)
async def apply_promo(
    data: ApplyPromoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplyPromoResponse:
    # Guard: trial must be activated
    if current_user.remnawave_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала активируйте пробный период",
        )

    # Validate promo (raises 404 if invalid)
    promo, already_used = await validate_promo_code(db, data.code, current_user)

    if promo.type != PromoCodeType.bonus_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот промокод предназначен для скидки при оплате",
        )

    if already_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Промокод уже использован",
        )

    # Load Remnawave client
    url = await get_setting(db, "remnawave_url")
    token = await get_setting_decrypted(db, "remnawave_token")
    if not url or not token:
        await send_admin_alert(
            await get_setting(db, "telegram_bot_token"),
            await get_setting(db, "telegram_admin_chat_id"),
            f"Promo apply error: Remnawave not configured\nUser: {current_user.id}\nCode: {promo.code}",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен",
        )
    rw_client = RemnawaveClient(url, token)

    try:
        days_added, new_expires_at = await apply_bonus_days(db, promo, current_user, rw_client)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("apply_bonus_days failed for user %s code %s: %s", current_user.id, promo.code, exc)
        try:
            await send_admin_alert(
                await get_setting(db, "telegram_bot_token"),
                await get_setting(db, "telegram_admin_chat_id"),
                f"Promo apply error: Remnawave unavailable\nUser: {current_user.id}\nCode: {promo.code}\nError: {exc}",
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен",
        )

    return ApplyPromoResponse(days_added=days_added, new_expires_at=new_expires_at)
