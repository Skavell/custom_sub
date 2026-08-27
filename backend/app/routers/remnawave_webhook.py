import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.setting_service import get_setting_decrypted

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


async def _validate_signature(raw_body: bytes, header_sig: str, secret: str) -> bool:
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, header_sig)


@router.post("/remnawave")
async def remnawave_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()

    secret = await get_setting_decrypted(db, "remnawave_webhook_secret")
    if not secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook not configured")

    header_sig = request.headers.get("x-remnawave-signature", "")
    if not await _validate_signature(raw_body, header_sig, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return {"ok": True}

    event = payload.get("event", "")
    if event != "user.first_connected":
        return {"ok": True}

    data = payload.get("data", {})
    rw_user_id = data.get("id")
    if rw_user_id is None:
        return {"ok": True}

    try:
        rw_user_id = int(rw_user_id)
    except (TypeError, ValueError):
        return {"ok": True}

    result = await db.execute(select(User).where(User.remnawave_user_id == rw_user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return {"ok": True}

    if user.first_connected_at is not None:
        return {"ok": True}

    user_traffic = data.get("userTraffic") or {}
    fca_str = user_traffic.get("firstConnectedAt")
    if not fca_str:
        return {"ok": True}

    user.first_connected_at = datetime.fromisoformat(fca_str.replace("Z", "+00:00"))
    await db.commit()
    logger.info("first_connected_at set for user %s via webhook", user.id)

    return {"ok": True}
