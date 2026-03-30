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
from app.schemas.payment import CreatePaymentRequest, PaymentResponse, TransactionHistoryItem
from app.services.payment_providers.base import InvoiceResult
from app.services.payment_providers.factory import get_active_provider
from app.schemas.payment import CryptoBotWebhookPayload
from app.services.payment_service import calculate_final_price, complete_payment, get_pending_transaction
from app.services.rate_limiter import check_rate_limit
from app.services.remnawave_client import RemnawaveClient
from app.services.setting_service import get_setting, get_setting_decrypted
from app.services.telegram_alert import send_admin_alert
import json as _json

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


# ---------------------------------------------------------------------------
# Webhook helper functions (extracted for testability via patching)
# ---------------------------------------------------------------------------

async def _get_webhook_token(db: AsyncSession) -> str | None:
    return await get_setting_decrypted(db, "cryptobot_token")


async def _check_webhook_ip(db: AsyncSession, client_ip: str) -> bool:
    """Returns True if IP is allowed (or no allowlist configured)."""
    allowed_ips_str = await get_setting(db, "cryptobot_webhook_allowed_ips")
    if not allowed_ips_str or allowed_ips_str in ("", "[]"):
        return True
    try:
        allowed = _json.loads(allowed_ips_str)
        return client_ip in allowed
    except (ValueError, TypeError):
        return True


def _verify_webhook_sig(raw_body: bytes, headers: dict, token: str) -> bool:
    from app.services.payment_providers.cryptobot import CryptoBotProvider
    provider = CryptoBotProvider(token=token, usdt_rate=83.0)
    return provider.verify_webhook(raw_body, dict(headers))


async def _load_transaction(db: AsyncSession, order_id: str) -> Transaction | None:
    uid = _uuid_or_none(order_id)
    if uid is None:
        return None
    result = await db.execute(
        select(Transaction).where(Transaction.id == uid)
    )
    return result.scalar_one_or_none()


def _uuid_or_none(s: str):
    try:
        return uuid.UUID(s)
    except (ValueError, AttributeError):
        return None


async def _load_plan_and_user(db: AsyncSession, transaction: Transaction):
    plan_res = await db.execute(select(Plan).where(Plan.id == transaction.plan_id))
    plan = plan_res.scalar_one_or_none()
    user_res = await db.execute(select(User).where(User.id == transaction.user_id))
    user = user_res.scalar_one_or_none()
    return plan, user


async def _get_remnawave_client(db: AsyncSession) -> RemnawaveClient | None:
    url = await get_setting(db, "remnawave_url")
    token = await get_setting_decrypted(db, "remnawave_token")
    if not url or not token:
        return None
    return RemnawaveClient(url, token)


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    client_ip = request.client.host if request.client else "unknown"

    # Verify 1: IP allowlist
    if not await _check_webhook_ip(db, client_ip):
        return Response(status_code=400)

    # Load token for signature verification
    token = await _get_webhook_token(db)
    if not token:
        return Response(status_code=400)

    # Verify 2: HMAC signature
    if not _verify_webhook_sig(raw_body, dict(request.headers), token):
        return Response(status_code=400)

    # Parse payload
    try:
        payload = CryptoBotWebhookPayload.model_validate_json(raw_body)
    except Exception:
        return Response(status_code=400)

    order_id = payload.payload.payload
    tx = await _load_transaction(db, order_id)
    if tx is None:
        return Response(status_code=400)

    # Idempotency
    if tx.status == TransactionStatus.completed:
        return Response(status_code=200)

    if payload.update_type == "invoice_paid" and payload.payload.status == "paid":
        plan, user = await _load_plan_and_user(db, tx)
        if plan is None or user is None:
            return Response(status_code=400)

        rw_client = await _get_remnawave_client(db)

        if rw_client is None:
            await send_admin_alert(
                await get_setting(db, "telegram_bot_token"),
                await get_setting(db, "telegram_admin_chat_id"),
                f"Webhook error: Remnawave not configured\nTransaction: {tx.id}",
            )
            return Response(status_code=500)

        try:
            await complete_payment(db, tx, user, plan, rw_client)
        except Exception as exc:
            logger.exception("complete_payment failed for tx %s: %s", tx.id, exc)
            try:
                await send_admin_alert(
                    await get_setting(db, "telegram_bot_token"),
                    await get_setting(db, "telegram_admin_chat_id"),
                    f"Webhook error: Remnawave unavailable\n"
                    f"Transaction: {tx.id}\nUser: {user.id}\n"
                    f"Plan: {plan.label}\nError: {exc}",
                )
            except Exception as alert_exc:
                logger.warning("Failed to send admin alert: %s", alert_exc)
            return Response(status_code=500)

        return Response(status_code=200)

    # Failed/expired/other
    tx.status = TransactionStatus.failed
    await db.commit()
    return Response(status_code=200)


# ---------------------------------------------------------------------------
# Payment history endpoint
# ---------------------------------------------------------------------------

@router.get("/history", response_model=list[TransactionHistoryItem])
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionHistoryItem]:
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .limit(20)
    )
    transactions = result.scalars().all()
    items = []
    for tx in transactions:
        plan_name = None
        if tx.plan_id is not None:
            plan_res = await db.execute(select(Plan).where(Plan.id == tx.plan_id))
            plan_obj = plan_res.scalar_one_or_none()
            if plan_obj:
                plan_name = plan_obj.label
        items.append(TransactionHistoryItem(
            id=tx.id,
            type=tx.type.value,
            status=tx.status.value,
            amount_rub=tx.amount_rub,
            plan_name=plan_name,
            days_added=tx.days_added,
            created_at=tx.created_at,
            completed_at=tx.completed_at,
        ))
    return items
