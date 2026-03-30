from __future__ import annotations
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.plan import Plan
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.payment import CreatePaymentRequest, PaymentResponse
from app.services.payment_providers.base import InvoiceResult
from app.services.payment_providers.factory import get_active_provider
from app.services.payment_service import calculate_final_price, get_pending_transaction
from app.services.rate_limiter import check_rate_limit
from app.services.setting_service import get_setting

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

_PAYMENT_RATE_LIMIT = 5
_PAYMENT_RATE_WINDOW = 60  # seconds
_PENDING_EXPIRY_MINUTES = 30


async def _create_transaction(
    db: AsyncSession,
    user: User,
    plan: Plan,
    amount_rub: int,
    promo_id: uuid.UUID | None,
    provider_name: str,
    order_id: str,
    invoice: InvoiceResult,
) -> Transaction:
    """Create and commit a payment transaction with the Cryptobot invoice details.
    order_id must be a UUID string pre-generated before calling the provider —
    it is used as both Transaction.id and the payload sent to CryptoBot.
    """
    tx = Transaction(
        id=uuid.UUID(order_id),
        user_id=user.id,
        type=TransactionType.payment,
        status=TransactionStatus.pending,
        plan_id=plan.id,
        amount_rub=amount_rub,
        days_added=plan.duration_days,
        payment_provider=provider_name,
        promo_code_id=promo_id,
        external_payment_id=invoice.external_id,
        payment_url=invoice.payment_url,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


@router.post("", status_code=201)
async def create_payment(
    data: CreatePaymentRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> PaymentResponse:
    # Guard 1: trial not activated
    if current_user.remnawave_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала активируйте пробный период",
        )

    # Guard 2: rate limit
    client_ip = request.client.host if request.client else "unknown"
    if not await check_rate_limit(redis, f"rate:payment:{client_ip}", _PAYMENT_RATE_LIMIT, _PAYMENT_RATE_WINDOW):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Слишком много запросов")

    # Guard 3: plan exists
    plan_result = await db.execute(select(Plan).where(Plan.id == data.plan_id, Plan.is_active == True))
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тариф не найден")

    # Guard 4: provider configured (raises 503 if not)
    provider = await get_active_provider(db)

    # Guard 5/6: deduplication (FOR UPDATE lock serialises concurrent requests)
    now = datetime.now(tz=timezone.utc)
    pending = await get_pending_transaction(db, current_user.id)
    if pending is not None:
        age = now - pending.created_at.replace(tzinfo=timezone.utc) if pending.created_at.tzinfo is None else now - pending.created_at
        if age < timedelta(minutes=_PENDING_EXPIRY_MINUTES):
            response.status_code = 200
            usdt_rate_str = await get_setting(db, "usdt_exchange_rate") or "83"
            usdt_amount = str(round(pending.amount_rub / float(usdt_rate_str), 2))
            return PaymentResponse(
                payment_url=pending.payment_url or "",
                transaction_id=str(pending.id),
                amount_rub=pending.amount_rub,
                amount_usdt=usdt_amount,
                is_existing=True,
            )
        # Expired pending — mark failed
        pending.status = TransactionStatus.failed
        await db.commit()

    # Price calculation (may raise 400 for invalid promo)
    final_price, promo = await calculate_final_price(db, plan, current_user, data.promo_code)

    # Generate order_id upfront so invoice and transaction share the same UUID
    order_id = str(uuid.uuid4())

    try:
        invoice = await provider.create_invoice(
            amount_rub=final_price,
            order_id=order_id,
            description=plan.label,
        )
    except Exception as exc:
        logger.exception("Payment provider invoice creation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ошибка платёжной системы. Попробуйте позже.",
        )

    tx = await _create_transaction(
        db=db,
        user=current_user,
        plan=plan,
        amount_rub=final_price,
        promo_id=promo.id if promo else None,
        provider_name=provider.name,
        order_id=order_id,
        invoice=invoice,
    )

    usdt_rate_str = await get_setting(db, "usdt_exchange_rate") or "83"
    usdt_amount = str(round(final_price / float(usdt_rate_str), 2))

    return PaymentResponse(
        payment_url=invoice.payment_url,
        transaction_id=str(tx.id),
        amount_rub=final_price,
        amount_usdt=usdt_amount,
        is_existing=False,
    )
